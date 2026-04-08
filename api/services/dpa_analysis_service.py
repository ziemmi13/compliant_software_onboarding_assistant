from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from dataclasses import field
from json import JSONDecodeError
from urllib.parse import urlparse

from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError

logger = logging.getLogger(__name__)

from api.schemas import DpaChecklistItem
from api.schemas import DpaChecklistStatus
from api.services.langchain_runner import MAX_RETRIES
from api.services.langchain_runner import invoke_with_retry
from api.services.source_page_service import fetch_source_page_excerpts
from legal_scout.agents.dpa_agent import build_dpa_messages
from legal_scout.agents.dpa_agent import dpa_agent
from legal_scout.tools.find_dpa_from_homepage import find_dpa_from_homepage


@dataclass
class DpaAnalysisResult:
    summary: str
    raw_analysis: str
    checklist: list[DpaChecklistItem] = field(default_factory=list)
    source_links: list[str] = field(default_factory=list)
    supporting_links: list[str] = field(default_factory=list)
    blocked_links: list[str] = field(default_factory=list)
    confidence_notes: list[str] = field(default_factory=list)


class StructuredDpaOutput(BaseModel):
    summary: str = Field(min_length=1)
    checklist: list[DpaChecklistItem] = Field(default_factory=list)


_DPA_STATUS_PRIORITY = {
    DpaChecklistStatus.MISSING: 0,
    DpaChecklistStatus.PARTIAL: 1,
    DpaChecklistStatus.UNCLEAR: 2,
    DpaChecklistStatus.SATISFIED: 3,
}


def sort_checklist_by_priority(items: list[DpaChecklistItem]) -> list[DpaChecklistItem]:
    return sorted(items, key=lambda item: _DPA_STATUS_PRIORITY.get(item.status, _DPA_STATUS_PRIORITY[DpaChecklistStatus.UNCLEAR]))


def _normalize_citation_url(url: str) -> str:
    parsed = urlparse(url.strip())
    normalized_path = parsed.path or "/"
    return parsed._replace(fragment="", path=normalized_path).geturl()


def validate_dpa_checklist_sources(
    checklist: list[DpaChecklistItem],
    source_links: list[str],
) -> tuple[list[DpaChecklistItem], list[str]]:
    if not checklist:
        return checklist, []

    normalized_sources = {_normalize_citation_url(link) for link in source_links}
    validated_items: list[DpaChecklistItem] = []
    invalid_citation_count = 0

    for item in checklist:
        if not item.source_url:
            validated_items.append(item)
            continue

        try:
            normalized_citation = _normalize_citation_url(item.source_url)
        except ValueError:
            invalid_citation_count += 1
            validated_items.append(item.model_copy(update={"source_url": None}))
            continue

        if normalized_citation not in normalized_sources:
            invalid_citation_count += 1
            validated_items.append(item.model_copy(update={"source_url": None}))
            continue

        validated_items.append(item.model_copy(update={"source_url": normalized_citation}))

    notes: list[str] = []
    if invalid_citation_count:
        notes.append(
            f"{invalid_citation_count} DPA citation(s) could not be verified against the discovered DPA pages."
        )

    return validated_items, notes


def parse_structured_dpa_analysis(raw_text: str) -> StructuredDpaOutput:
    cleaned = raw_text.strip()
    if not cleaned:
        raise ValueError("Empty DPA analysis response.")

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
        raise ValueError("Structured DPA analysis JSON object not found.")

    json_payload = cleaned[start_index : end_index + 1]

    try:
        parsed = json.loads(json_payload)
    except JSONDecodeError as exc:
        raise ValueError("Structured DPA analysis JSON could not be decoded.") from exc

    try:
        structured = StructuredDpaOutput.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("Structured DPA analysis JSON did not match expected schema.") from exc

    structured.checklist = sort_checklist_by_priority(structured.checklist)
    return structured


def build_dpa_analysis_prompt(
    url: str,
    source_links: list[str],
    company_context: str | None = None,
    source_excerpts: list[tuple[str, str]] | None = None,
) -> str:
    cleaned_context = (company_context or "").strip()
    prompt_lines = [
        f"Analyze the Data Processing Agreement for: {url}",
        "Evaluate the document against a GDPR Article 28-style processor checklist.",
    ]

    if cleaned_context:
        prompt_lines.extend(
            [
                "",
                "Company context:",
                cleaned_context,
                "Use this context to emphasize the most material privacy and security review concerns.",
            ]
        )

    if source_links:
        prompt_lines.extend(
            [
                "",
                "Discovered DPA pages and annexes:",
                *[f"- {link}" for link in source_links],
                "Use only one of the exact URLs above as source_url for each checklist item. Do not invent, rewrite, or infer any other URL.",
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
    else:
        prompt_lines.extend(
            [
                "",
                "No discovered DPA pages were confirmed.",
                "Set source_url to null for every checklist item.",
            ]
        )

    prompt_lines.extend(
        [
            "",
            "Always assess these checklist items:",
            "- documented_instructions",
            "- confidentiality",
            "- security_measures",
            "- subprocessor_controls",
            "- data_subject_assistance",
            "- breach_notification",
            "- deletion_or_return",
            "- audit_rights",
            "- international_transfers",
            "Return only a valid JSON object. Do not include markdown, headings, commentary, or code fences.",
            "Use this exact schema:",
            "{",
            '  "summary": "One concise paragraph summarizing the DPA posture.",',
            '  "checklist": [',
            "    {",
            '      "requirement_key": "documented_instructions",',
            '      "requirement_title": "Processing on documented instructions",',
            '      "status": "satisfied",',
            '      "rationale": "Short explanation of whether the DPA addresses this obligation.",',
            '      "source_url": "https://example.com/legal/data-processing-agreement"',
            "    }",
            "  ]",
            "}",
            "Allowed status values: satisfied, partial, missing, unclear.",
            "Use missing when the obligation is absent, partial when it is present but qualified or incomplete, unclear when the text is ambiguous, and satisfied when the obligation is clearly addressed.",
            "Prefer the main DPA page, but use linked annexes such as subprocessors, processing specifications, or security measures when they are necessary to assess the requirement.",
        ]
    )

    return "\n".join(prompt_lines)


async def run_dpa_analysis(url: str, company_context: str | None = None) -> DpaAnalysisResult:
    discovered = find_dpa_from_homepage(url)
    source_links = discovered.get("valid", [])
    blocked_links = discovered.get("blocked", [])
    supporting_links: list[str] = []
    logger.info("DPA analysis for %s: %d source links, %d blocked", url, len(source_links), len(blocked_links))

    source_excerpts = [(item.url, item.content) for item in fetch_source_page_excerpts(source_links)]

    prompt = build_dpa_analysis_prompt(url, source_links, company_context, source_excerpts)

    final_text = await invoke_with_retry(
        llm=dpa_agent,
        messages=build_dpa_messages(prompt),
        logger=logger,
        label="DPA agent",
        max_retries=MAX_RETRIES,
    )

    structured = parse_structured_dpa_analysis(final_text)
    validated_checklist, confidence_notes = validate_dpa_checklist_sources(structured.checklist, source_links)

    return DpaAnalysisResult(
        summary=structured.summary,
        checklist=validated_checklist,
        raw_analysis=final_text,
        source_links=source_links,
        supporting_links=supporting_links,
        blocked_links=blocked_links,
        confidence_notes=confidence_notes,
    )