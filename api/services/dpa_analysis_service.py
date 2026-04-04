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

from api.schemas import DpaChecklistItem
from api.schemas import DpaChecklistStatus
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

    app = App(name="legal_scout_dpa_web", root_agent=dpa_agent)
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

    prompt = build_dpa_analysis_prompt(url, source_links, company_context)

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

                if event.author != "dpa_agent" or not event.is_final_response():
                    continue

                text_parts = [part.text or "" for part in event.content.parts if part.text]
                combined = "\n".join(part.strip() for part in text_parts if part.strip())
                if combined:
                    final_text = combined
    finally:
        await runner.close()

    if not final_text:
        raise RuntimeError("No DPA analysis text was returned by the agent.")

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