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

from api.schemas import DpiaSection
from api.schemas import DpiaSectionRisk
from api.schemas import DpiaThresholdItem
from api.schemas import DpiaThresholdStatus
from api.services.langchain_runner import MAX_RETRIES
from api.services.langchain_runner import invoke_with_retry
from api.services.source_page_service import fetch_source_page_excerpts
from legal_scout.agents.dpia_agent import build_dpia_messages
from legal_scout.agents.dpia_agent import dpia_agent
from legal_scout.tools.find_privacy_from_homepage import find_privacy_from_homepage


DPIA_THRESHOLD = 2


@dataclass
class DpiaAnalysisResult:
    summary: str
    raw_analysis: str
    dpia_required: bool = False
    threshold_score: int = 0
    threshold_criteria: list[DpiaThresholdItem] = field(default_factory=list)
    dpia_sections: list[DpiaSection] = field(default_factory=list)
    source_links: list[str] = field(default_factory=list)
    supporting_links: list[str] = field(default_factory=list)
    blocked_links: list[str] = field(default_factory=list)
    confidence_notes: list[str] = field(default_factory=list)


class StructuredDpiaOutput(BaseModel):
    summary: str = Field(min_length=1)
    threshold_criteria: list[DpiaThresholdItem] = Field(default_factory=list)
    dpia_sections: list[DpiaSection] = Field(default_factory=list)


_THRESHOLD_STATUS_PRIORITY = {
    DpiaThresholdStatus.DETECTED: 0,
    DpiaThresholdStatus.INSUFFICIENT_INFO: 1,
    DpiaThresholdStatus.NOT_DETECTED: 2,
}


def sort_threshold_by_priority(items: list[DpiaThresholdItem]) -> list[DpiaThresholdItem]:
    return sorted(
        items,
        key=lambda item: _THRESHOLD_STATUS_PRIORITY.get(
            item.status, _THRESHOLD_STATUS_PRIORITY[DpiaThresholdStatus.INSUFFICIENT_INFO]
        ),
    )


def _normalize_citation_url(url: str) -> str:
    parsed = urlparse(url.strip())
    normalized_path = parsed.path or "/"
    return parsed._replace(fragment="", path=normalized_path).geturl()


def validate_dpia_sources(
    threshold_criteria: list[DpiaThresholdItem],
    dpia_sections: list[DpiaSection],
    source_links: list[str],
) -> tuple[list[DpiaThresholdItem], list[DpiaSection], list[str]]:
    normalized_sources = {_normalize_citation_url(link) for link in source_links}
    invalid_citation_count = 0

    validated_criteria: list[DpiaThresholdItem] = []
    for item in threshold_criteria:
        if not item.source_url:
            validated_criteria.append(item)
            continue

        try:
            normalized_citation = _normalize_citation_url(item.source_url)
        except ValueError:
            invalid_citation_count += 1
            validated_criteria.append(item.model_copy(update={"source_url": None}))
            continue

        if normalized_citation not in normalized_sources:
            invalid_citation_count += 1
            validated_criteria.append(item.model_copy(update={"source_url": None}))
            continue

        validated_criteria.append(item.model_copy(update={"source_url": normalized_citation}))

    validated_sections: list[DpiaSection] = []
    for section in dpia_sections:
        if not section.source_url:
            validated_sections.append(section)
            continue

        try:
            normalized_citation = _normalize_citation_url(section.source_url)
        except ValueError:
            invalid_citation_count += 1
            validated_sections.append(section.model_copy(update={"source_url": None}))
            continue

        if normalized_citation not in normalized_sources:
            invalid_citation_count += 1
            validated_sections.append(section.model_copy(update={"source_url": None}))
            continue

        validated_sections.append(section.model_copy(update={"source_url": normalized_citation}))

    notes: list[str] = []
    if invalid_citation_count:
        notes.append(
            f"{invalid_citation_count} DPIA citation(s) could not be verified against the discovered pages."
        )

    return validated_criteria, validated_sections, notes


def parse_structured_dpia_analysis(raw_text: str) -> StructuredDpiaOutput:
    cleaned = raw_text.strip()
    if not cleaned:
        raise ValueError("Empty DPIA analysis response.")

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
        raise ValueError("Structured DPIA analysis JSON object not found.")

    json_payload = cleaned[start_index : end_index + 1]

    try:
        parsed = json.loads(json_payload)
    except JSONDecodeError as exc:
        raise ValueError("Structured DPIA analysis JSON could not be decoded.") from exc

    try:
        structured = StructuredDpiaOutput.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("Structured DPIA analysis JSON did not match expected schema.") from exc

    structured.threshold_criteria = sort_threshold_by_priority(structured.threshold_criteria)
    return structured


def build_dpia_analysis_prompt(
    url: str,
    source_links: list[str],
    company_context: str | None = None,
    source_excerpts: list[tuple[str, str]] | None = None,
) -> str:
    cleaned_context = (company_context or "").strip()
    prompt_lines = [
        f"Perform a DPIA threshold screening and, if required, a preliminary DPIA for: {url}",
        "Evaluate the vendor's data processing against the WP29 nine-criteria threshold test (GDPR Article 35).",
    ]

    if cleaned_context:
        prompt_lines.extend(
            [
                "",
                "Company context:",
                cleaned_context,
                "Use this context to tailor the DPIA assessment to the specific processing scenario.",
            ]
        )

    if source_links:
        prompt_lines.extend(
            [
                "",
                "Discovered privacy and compliance pages:",
                *[f"- {link}" for link in source_links],
                "Use only one of the exact URLs above as source_url for each item. Do not invent, rewrite, or infer any other URL.",
            ]
        )
    else:
        prompt_lines.extend(
            [
                "",
                "No discovered privacy or compliance pages were confirmed.",
                "Set source_url to null for every item.",
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
            "Always assess these nine threshold criteria:",
            "- evaluation_or_scoring",
            "- automated_decision_making",
            "- systematic_monitoring",
            "- sensitive_data",
            "- large_scale_processing",
            "- dataset_combining",
            "- vulnerable_subjects",
            "- innovative_technology",
            "- cross_border_transfers",
            "",
            "If two or more criteria are detected, also produce a preliminary DPIA with these four sections:",
            "- processing_description (Systematic description of the envisaged processing)",
            "- necessity_and_proportionality (Assessment of necessity and proportionality)",
            "- risks_to_data_subjects (Assessment of risks to the rights and freedoms of data subjects)",
            "- safeguards_and_measures (Measures envisaged to address the risks)",
            "",
            "Return only a valid JSON object. Do not include markdown, headings, commentary, or code fences.",
            "Use this exact schema:",
            "{",
            '  "summary": "One concise paragraph summarizing the DPIA screening result and key findings.",',
            '  "threshold_criteria": [',
            "    {",
            '      "criterion_key": "evaluation_or_scoring",',
            '      "criterion_name": "Evaluation or scoring",',
            '      "status": "detected",',
            '      "evidence": "Short explanation of what was found or why this criterion applies.",',
            '      "source_url": "https://example.com/privacy"',
            "    }",
            "  ],",
            '  "dpia_sections": [',
            "    {",
            '      "section_key": "processing_description",',
            '      "section_title": "Systematic description of processing",',
            '      "findings": [{"title": "Data collected", "detail": "Names, emails, and IP addresses."}, {"title": "Purpose", "detail": "Authentication and access control."}],',
            '      "risk_level": null,',
            '      "source_url": "https://example.com/privacy"',
            "    },",
            "    {",
            '      "section_key": "risks_to_data_subjects",',
            '      "section_title": "Risks to data subjects",',
            '      "findings": [{"title": "Unauthorized access", "detail": "Medium likelihood, high severity."}, {"title": "Data loss", "detail": "Low likelihood, high severity."}],',
            '      "risk_level": "high",',
            '      "source_url": null',
            "    }",
            "  ]",
            "}",
            'Allowed threshold status values: detected, not_detected, insufficient_info.',
            'Allowed risk_level values for dpia_sections: low, medium, high, or null when not applicable.',
            "Use detected when there is clear evidence, not_detected when the documentation shows this does not apply, and insufficient_info when public documentation is not clear enough to determine.",
            "If fewer than two criteria are detected, return an empty dpia_sections array.",
        ]
    )

    return "\n".join(prompt_lines)


async def run_dpia_analysis(url: str, company_context: str | None = None) -> DpiaAnalysisResult:
    discovered = find_privacy_from_homepage(url)
    source_links = discovered.get("valid", [])
    blocked_links = discovered.get("blocked", [])
    supporting_links: list[str] = []
    logger.info("DPIA analysis for %s: %d source links, %d blocked", url, len(source_links), len(blocked_links))

    source_excerpts = [(item.url, item.content) for item in fetch_source_page_excerpts(source_links)]

    prompt = build_dpia_analysis_prompt(url, source_links, company_context, source_excerpts)

    final_text = await invoke_with_retry(
        llm=dpia_agent,
        messages=build_dpia_messages(prompt),
        logger=logger,
        label="DPIA agent",
        max_retries=MAX_RETRIES,
    )

    structured = parse_structured_dpia_analysis(final_text)
    validated_criteria, validated_sections, confidence_notes = validate_dpia_sources(
        structured.threshold_criteria, structured.dpia_sections, source_links
    )

    threshold_score = sum(
        1 for item in validated_criteria if item.status == DpiaThresholdStatus.DETECTED
    )
    dpia_required = threshold_score >= DPIA_THRESHOLD

    return DpiaAnalysisResult(
        summary=structured.summary,
        dpia_required=dpia_required,
        threshold_score=threshold_score,
        threshold_criteria=validated_criteria,
        dpia_sections=validated_sections if dpia_required else [],
        raw_analysis=final_text,
        source_links=source_links,
        supporting_links=supporting_links,
        blocked_links=blocked_links,
        confidence_notes=confidence_notes,
    )
