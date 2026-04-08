from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field
from json import JSONDecodeError
from urllib.parse import urlparse
from uuid import uuid4

from google.adk.apps.app import App
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.utils.context_utils import Aclosing
from google.genai import types
from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError

from api.schemas import DpiaSection
from api.schemas import DpiaSectionRisk
from api.schemas import DpiaThresholdItem
from api.schemas import DpiaThresholdStatus
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


def extract_supporting_links_from_grounding(
    grounding_metadata: types.GroundingMetadata | None,
    source_links: list[str],
) -> list[str]:
    if not grounding_metadata or not grounding_metadata.grounding_chunks:
        return []

    normalized_sources = {_normalize_citation_url(link) for link in source_links}
    supporting_links: list[str] = []
    seen_links: set[str] = set()

    for chunk in grounding_metadata.grounding_chunks:
        candidates = []
        if chunk.web and chunk.web.uri:
            candidates.append(chunk.web.uri)
        if chunk.retrieved_context and chunk.retrieved_context.uri:
            candidates.append(chunk.retrieved_context.uri)

        for candidate in candidates:
            try:
                normalized_candidate = _normalize_citation_url(candidate)
            except ValueError:
                continue

            if normalized_candidate in normalized_sources or normalized_candidate in seen_links:
                continue

            seen_links.add(normalized_candidate)
            supporting_links.append(normalized_candidate)

    return supporting_links


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

    app = App(name="legal_scout_dpia_web", root_agent=dpia_agent)
    session_service = InMemorySessionService()
    runner = Runner(
        app=app,
        session_service=session_service,
        artifact_service=InMemoryArtifactService(),
        credential_service=InMemoryCredentialService(),
    )

    user_id = "web_user"
    session_id = str(uuid4())
    await session_service.create_session(app_name=app.name, user_id=user_id, session_id=session_id)

    prompt = build_dpia_analysis_prompt(url, source_links, company_context)

    final_text = ""
    try:
        content = types.Content(role="user", parts=[types.Part(text=prompt)])
        async with Aclosing(
            runner.run_async(user_id=user_id, session_id=session_id, new_message=content)
        ) as event_stream:
            async for event in event_stream:
                for link in extract_supporting_links_from_grounding(event.grounding_metadata, source_links):
                    if link not in supporting_links:
                        supporting_links.append(link)

                if not event.content or not event.content.parts:
                    continue

                if event.author != "dpia_agent" or not event.is_final_response():
                    continue

                text_parts = [part.text or "" for part in event.content.parts if part.text]
                combined = "\n".join(part.strip() for part in text_parts if part.strip())
                if combined:
                    final_text = combined
    finally:
        await runner.close()

    if not final_text:
        raise RuntimeError("No DPIA analysis text was returned by the agent.")

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
