from __future__ import annotations

import ipaddress
import json
import logging
from dataclasses import dataclass
from dataclasses import field
from json import JSONDecodeError
from urllib.parse import urlparse

from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError

from api.schemas import ClauseHighlight
from api.schemas import RiskLevel
from api.services.langchain_runner import MAX_RETRIES
from api.services.langchain_runner import invoke_with_retry
from api.services.source_page_service import fetch_source_page_excerpts
from legal_scout.agents.terms_agent import build_terms_messages
from legal_scout.agents.terms_agent import terms_agent
from legal_scout.tools.find_terms_from_homepage import find_terms_from_homepage

logger = logging.getLogger(__name__)


@dataclass
class AgentAnalysisResult:
    summary: str
    raw_analysis: str
    highlights: list[ClauseHighlight] = field(default_factory=list)
    source_links: list[str] = field(default_factory=list)
    blocked_links: list[str] = field(default_factory=list)
    confidence_notes: list[str] = field(default_factory=list)


class StructuredAgentOutput(BaseModel):
    summary: str = Field(min_length=1)
    highlights: list[ClauseHighlight] = Field(default_factory=list)


_RISK_PRIORITY = {
    RiskLevel.HIGH: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.LOW: 2,
    RiskLevel.UNKNOWN: 3,
}


def sort_highlights_by_severity(highlights: list[ClauseHighlight]) -> list[ClauseHighlight]:
    return sorted(
        highlights,
        key=lambda highlight: _RISK_PRIORITY.get(highlight.risk_level, _RISK_PRIORITY[RiskLevel.UNKNOWN]),
    )


def _normalize_citation_url(url: str) -> str:
    parsed = urlparse(url.strip())
    normalized_path = parsed.path or "/"
    return parsed._replace(fragment="", path=normalized_path).geturl()


def validate_highlight_sources(
    highlights: list[ClauseHighlight],
    source_links: list[str],
) -> tuple[list[ClauseHighlight], list[str]]:
    if not highlights:
        return highlights, []

    normalized_sources = {_normalize_citation_url(link) for link in source_links}
    validated_highlights: list[ClauseHighlight] = []
    invalid_citation_count = 0

    for highlight in highlights:
        if not highlight.source_url:
            validated_highlights.append(highlight)
            continue

        try:
            normalized_citation = _normalize_citation_url(highlight.source_url)
        except ValueError:
            invalid_citation_count += 1
            validated_highlights.append(highlight.model_copy(update={"source_url": None}))
            continue

        if normalized_citation not in normalized_sources:
            invalid_citation_count += 1
            validated_highlights.append(highlight.model_copy(update={"source_url": None}))
            continue

        validated_highlights.append(highlight.model_copy(update={"source_url": normalized_citation}))

    notes: list[str] = []
    if invalid_citation_count:
        notes.append(
            f"{invalid_citation_count} highlight citation(s) could not be verified against the discovered source pages."
        )

    return validated_highlights, notes


def parse_structured_analysis(raw_text: str) -> StructuredAgentOutput:
    cleaned = raw_text.strip()
    if not cleaned:
        raise ValueError("Empty analysis response.")

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    start_index = cleaned.find("{")
    end_index = cleaned.rfind("}")
    if start_index == -1 or end_index == -1 or end_index < start_index:
        raise ValueError("Structured analysis JSON object not found.")

    json_payload = cleaned[start_index : end_index + 1]

    try:
        parsed = json.loads(json_payload)
    except JSONDecodeError as exc:
        raise ValueError("Structured analysis JSON could not be decoded.") from exc

    try:
        structured = StructuredAgentOutput.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("Structured analysis JSON did not match expected schema.") from exc

    structured.highlights = sort_highlights_by_severity(structured.highlights)
    return structured


def build_analysis_prompt(
    url: str,
    source_links: list[str],
    company_context: str | None = None,
    source_excerpts: list[tuple[str, str]] | None = None,
) -> str:
    cleaned_context = (company_context or "").strip()
    prompt_lines = [
        f"Analyze the Terms and Conditions for: {url}",
    ]

    if cleaned_context:
        prompt_lines.extend(
            [
                "",
                "Company context:",
                cleaned_context,
                "Use this context to prioritize the most relevant legal and operational risks.",
            ]
        )

    if source_links:
        prompt_lines.extend(
            [
                "",
                "Discovered source pages:",
                *[f"- {link}" for link in source_links],
                "Use only one of the exact URLs above as source_url for each highlight. Do not invent, rewrite, or infer any other URL.",
            ]
        )
    else:
        prompt_lines.extend(
            [
                "",
                "No discovered source pages were confirmed.",
                "Set source_url to null for every highlight.",
            ]
        )

    if source_excerpts:
        prompt_lines.extend(["", "Fetched source excerpts:"])
        for excerpt_url, excerpt_text in source_excerpts:
            prompt_lines.extend([
                f"URL: {excerpt_url}",
                excerpt_text,
                "",
            ])

    prompt_lines.extend(
        [
            "",
            "Return only a valid JSON object. Do not include markdown, headings, commentary, or code fences.",
            "Use this exact schema:",
            "{",
            '  "summary": "One concise paragraph summarizing the most important contractual points.",',
            '  "highlights": [',
            "    {",
            '      "title": "Short clause name",',
            '      "rationale": "Why this clause matters, with emphasis on the provided company context when relevant.",',
            '      "risk_level": "low",',
            '      "source_url": "https://example.com/terms"',
            "    }",
            "  ]",
            "}",
            "Allowed risk_level values: low, medium, high, unknown.",
            "For every highlight, include source_url as the exact page URL that supports the finding, chosen only from the discovered source pages listed above. Use null if you cannot reliably attribute the highlight to one of those URLs.",
            "If no reliable terms were found, set summary to explain that clearly and return an empty highlights array.",
            "Limit highlights to the most important clauses only.",
        ]
    )

    return "\n".join(prompt_lines)


def validate_input_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are allowed.")

    if not parsed.netloc:
        raise ValueError("URL must include a valid domain.")

    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Localhost URLs are not allowed.")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # Non-IP hosts are expected for normal domains.
        ip = None

    if ip and (ip.is_private or ip.is_loopback or ip.is_reserved):
        raise ValueError("Private or loopback IP URLs are not allowed.")

    return parsed.geturl()


async def run_terms_analysis(url: str, company_context: str | None = None) -> AgentAnalysisResult:
    discovered = find_terms_from_homepage(url)
    source_links = discovered.get("valid", [])
    blocked_links = discovered.get("blocked", [])
    logger.info("Terms analysis for %s: %d source links, %d blocked", url, len(source_links), len(blocked_links))

    source_excerpts = [(item.url, item.content) for item in fetch_source_page_excerpts(source_links)]

    prompt = build_analysis_prompt(url, source_links, company_context, source_excerpts)

    final_text = await invoke_with_retry(
        llm=terms_agent,
        messages=build_terms_messages(prompt),
        logger=logger,
        label="Terms agent",
        max_retries=MAX_RETRIES,
    )

    structured = parse_structured_analysis(final_text)
    validated_highlights, confidence_notes = validate_highlight_sources(structured.highlights, source_links)

    return AgentAnalysisResult(
        summary=structured.summary,
        highlights=validated_highlights,
        raw_analysis=final_text,
        source_links=source_links,
        blocked_links=blocked_links,
        confidence_notes=confidence_notes,
    )
