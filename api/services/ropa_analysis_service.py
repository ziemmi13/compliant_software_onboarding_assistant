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

from api.schemas import DpaAnalyzeResponse
from api.schemas import DpiaAnalyzeResponse
from api.schemas import RopaField
from api.schemas import RopaFieldEntry
from api.schemas import RopaFieldStatus
from api.services.langchain_runner import MAX_RETRIES
from api.services.langchain_runner import invoke_with_retry
from legal_scout.agents.ropa_agent import build_ropa_messages
from legal_scout.agents.ropa_agent import ropa_agent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RopaFieldDefinition:
    field_key: str
    field_title: str
    article_ref: str
    placeholder_title: str
    placeholder_detail: str
    placeholder_source_note: str


ROPA_FIELD_DEFINITIONS = [
    RopaFieldDefinition(
        field_key="controller_details",
        field_title="Controller and DPO details",
        article_ref="Art. 30(1)(a)",
        placeholder_title="Internal controller record required",
        placeholder_detail="Insert the controller name, contact details, and DPO or representative details from internal records.",
        placeholder_source_note="Requires controller-owned contact details rather than vendor-facing public materials.",
    ),
    RopaFieldDefinition(
        field_key="purposes_of_processing",
        field_title="Purposes of processing",
        article_ref="Art. 30(1)(b)",
        placeholder_title="Processing purpose not confirmed",
        placeholder_detail="Document the business purpose served by the vendor before relying on this ROPA entry.",
        placeholder_source_note="Populate from the intended business use if the supplied DPA and DPIA material is incomplete.",
    ),
    RopaFieldDefinition(
        field_key="data_subject_categories",
        field_title="Categories of data subjects",
        article_ref="Art. 30(1)(c)",
        placeholder_title="Data subject categories not confirmed",
        placeholder_detail="List the relevant categories of individuals affected by the processing, such as employees, customers, or end users.",
        placeholder_source_note="Complete from internal deployment scope when vendor materials do not identify data subjects clearly.",
    ),
    RopaFieldDefinition(
        field_key="personal_data_categories",
        field_title="Categories of personal data",
        article_ref="Art. 30(1)(c)",
        placeholder_title="Personal data categories not confirmed",
        placeholder_detail="Specify the personal data categories involved in the deployment, including any special categories if applicable.",
        placeholder_source_note="Complete from internal deployment scope when vendor materials do not identify data categories clearly.",
    ),
    RopaFieldDefinition(
        field_key="recipients",
        field_title="Recipients",
        article_ref="Art. 30(1)(d)",
        placeholder_title="Recipient mapping not confirmed",
        placeholder_detail="Document the processor, subprocessors, and any external recipient categories involved in the arrangement.",
        placeholder_source_note="Use DPA subprocessor and service-delivery information, supplemented with internal onboarding records if needed.",
    ),
    RopaFieldDefinition(
        field_key="international_transfers",
        field_title="International transfers",
        article_ref="Art. 30(1)(e)",
        placeholder_title="Transfer mechanism not confirmed",
        placeholder_detail="Record whether personal data is transferred internationally and which transfer mechanism applies.",
        placeholder_source_note="Use DPA transfer clauses and DPIA cross-border findings; confirm missing details internally.",
    ),
    RopaFieldDefinition(
        field_key="retention_periods",
        field_title="Retention periods",
        article_ref="Art. 30(1)(f)",
        placeholder_title="Retention schedule not confirmed",
        placeholder_detail="State the relevant retention period or the criteria used to determine deletion and return timelines.",
        placeholder_source_note="Use DPA deletion terms and DPIA processing notes; confirm missing timelines internally.",
    ),
    RopaFieldDefinition(
        field_key="security_measures",
        field_title="Technical and organizational security measures",
        article_ref="Art. 30(1)(g)",
        placeholder_title="Security measures not confirmed",
        placeholder_detail="Summarize the technical and organizational safeguards relied on for this processing activity.",
        placeholder_source_note="Use DPA security clauses and DPIA safeguards analysis; supplement with internal security review where needed.",
    ),
]

ROPA_FIELD_INDEX = {definition.field_key: definition for definition in ROPA_FIELD_DEFINITIONS}
ROPA_FIELD_ORDER = {definition.field_key: index for index, definition in enumerate(ROPA_FIELD_DEFINITIONS)}


@dataclass
class RopaAnalysisResult:
    summary: str
    vendor_name: str
    raw_analysis: str
    ropa_fields: list[RopaField] = field(default_factory=list)
    completeness_score: int = 0
    confidence_notes: list[str] = field(default_factory=list)


class StructuredRopaOutput(BaseModel):
    summary: str = Field(min_length=1)
    vendor_name: str = Field(min_length=1)
    ropa_fields: list[RopaField] = Field(default_factory=list)


def _normalize_vendor_name(url: str, vendor_name: str | None) -> str:
    cleaned = (vendor_name or "").strip()
    if cleaned:
        return cleaned

    hostname = urlparse(url).hostname or url
    return hostname.removeprefix("www.")


def _build_placeholder_field(field_key: str) -> RopaField:
    definition = ROPA_FIELD_INDEX[field_key]
    return RopaField(
        field_key=definition.field_key,
        field_title=definition.field_title,
        article_ref=definition.article_ref,
        status=RopaFieldStatus.PLACEHOLDER,
        entries=[
            RopaFieldEntry(
                title=definition.placeholder_title,
                detail=definition.placeholder_detail,
            )
        ],
        source_notes=[definition.placeholder_source_note],
    )


def normalize_ropa_fields(ropa_fields: list[RopaField]) -> list[RopaField]:
    normalized_fields: dict[str, RopaField] = {}

    for field_item in ropa_fields:
        definition = ROPA_FIELD_INDEX.get(field_item.field_key)
        if definition is None:
            continue

        normalized_entries = field_item.entries
        normalized_source_notes = [note.strip() for note in field_item.source_notes if note.strip()]
        status = field_item.status

        if not normalized_entries:
            if status == RopaFieldStatus.PLACEHOLDER:
                normalized_entries = _build_placeholder_field(field_item.field_key).entries
            else:
                status = RopaFieldStatus.PARTIAL

        normalized_fields[field_item.field_key] = RopaField(
            field_key=definition.field_key,
            field_title=definition.field_title,
            article_ref=definition.article_ref,
            status=status,
            entries=normalized_entries,
            source_notes=normalized_source_notes,
        )

    for definition in ROPA_FIELD_DEFINITIONS:
        normalized_fields.setdefault(definition.field_key, _build_placeholder_field(definition.field_key))

    return sorted(normalized_fields.values(), key=lambda item: ROPA_FIELD_ORDER[item.field_key])


def calculate_completeness_score(ropa_fields: list[RopaField]) -> int:
    if not ropa_fields:
        return 0

    status_weights = {
        RopaFieldStatus.POPULATED: 1.0,
        RopaFieldStatus.PARTIAL: 0.5,
        RopaFieldStatus.PLACEHOLDER: 0.0,
    }
    weighted_total = sum(status_weights.get(field_item.status, 0.0) for field_item in ropa_fields)
    return round((weighted_total / len(ropa_fields)) * 100)


def parse_structured_ropa_analysis(raw_text: str) -> StructuredRopaOutput:
    cleaned = raw_text.strip()
    if not cleaned:
        raise ValueError("Empty ROPA analysis response.")

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
        raise ValueError("Structured ROPA analysis JSON object not found.")

    json_payload = cleaned[start_index : end_index + 1]

    try:
        parsed = json.loads(json_payload)
    except JSONDecodeError as exc:
        raise ValueError("Structured ROPA analysis JSON could not be decoded.") from exc

    try:
        return StructuredRopaOutput.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("Structured ROPA analysis JSON did not match expected schema.") from exc


def build_ropa_synthesis_prompt(
    url: str,
    dpa_result: DpaAnalyzeResponse,
    dpia_result: DpiaAnalyzeResponse,
    company_context: str | None = None,
) -> str:
    cleaned_context = (company_context or "").strip()
    prompt_lines = [
        f"Synthesize a Record of Processing Activities for vendor: {url}",
        "Use the supplied DPA and DPIA analysis only. Do not infer facts from outside the provided material.",
        "Always return all eight ROPA fields, using placeholders where internal controller data is still required.",
    ]

    if cleaned_context:
        prompt_lines.extend(
            [
                "",
                "Company context:",
                cleaned_context,
                "Use this context to resolve what the processing activity is intended to cover when the supplied DPA and DPIA outputs leave room for interpretation.",
            ]
        )

    prompt_lines.extend(
        [
            "",
            "DPA analysis:",
            dpa_result.model_dump_json(indent=2),
            "",
            "DPIA analysis:",
            dpia_result.model_dump_json(indent=2),
            "",
            "Map the supplied findings into these Article 30(1) fields:",
            "- controller_details (Art. 30(1)(a))",
            "- purposes_of_processing (Art. 30(1)(b))",
            "- data_subject_categories (Art. 30(1)(c))",
            "- personal_data_categories (Art. 30(1)(c))",
            "- recipients (Art. 30(1)(d))",
            "- international_transfers (Art. 30(1)(e))",
            "- retention_periods (Art. 30(1)(f))",
            "- security_measures (Art. 30(1)(g))",
            "",
            "Guidance:",
            "- Use DPA subprocessor and annex information to populate recipients and security measures when available.",
            "- Use DPIA threshold criteria and sections to populate purposes, subject categories, personal data categories, transfer indicators, risks, and safeguards.",
            "- For controller_details, prefer a placeholder unless the supplied material explicitly identifies the controller-side details needed for the registry.",
            "- For retention_periods, use deletion, return, or retention language from the DPA or DPIA. If none is available, keep it as a placeholder.",
            "- Keep entries short and operational, suitable for a registry rather than a memo.",
            "",
            "Return only a valid JSON object. Do not include markdown, headings, commentary, or code fences.",
            "Use this exact schema:",
            "{",
            '  "summary": "One concise paragraph summarizing the vendor processing activity and major completion gaps.",',
            '  "vendor_name": "Vendor name",',
            '  "ropa_fields": [',
            "    {",
            '      "field_key": "controller_details",',
            '      "field_title": "Controller and DPO details",',
            '      "article_ref": "Art. 30(1)(a)",',
            '      "status": "placeholder",',
            '      "entries": [{"title": "Internal controller record required", "detail": "Insert the controller name, contact details, and DPO details from internal records."}],',
            '      "source_notes": ["Requires controller-owned information that is usually not present in vendor-facing policies."]',
            "    }",
            "  ]",
            "}",
            "Allowed status values: populated, partial, placeholder.",
            "Every field must include field_key, field_title, article_ref, status, entries, and source_notes.",
            "Entries should be specific factual registry lines, not generic advice, unless the field is a placeholder.",
        ]
    )

    return "\n".join(prompt_lines)


async def run_ropa_analysis(
    url: str,
    dpa_result: DpaAnalyzeResponse,
    dpia_result: DpiaAnalyzeResponse,
    company_context: str | None = None,
) -> RopaAnalysisResult:
    logger.info(
        "ROPA synthesis for %s using %d DPA checklist items and %d DPIA criteria",
        url,
        len(dpa_result.checklist),
        len(dpia_result.threshold_criteria),
    )

    prompt = build_ropa_synthesis_prompt(url, dpa_result, dpia_result, company_context)
    final_text = await invoke_with_retry(
        llm=ropa_agent,
        messages=build_ropa_messages(prompt),
        logger=logger,
        label="ROPA agent",
        max_retries=MAX_RETRIES,
    )

    structured = parse_structured_ropa_analysis(final_text)
    ropa_fields = normalize_ropa_fields(structured.ropa_fields)
    completeness_score = calculate_completeness_score(ropa_fields)

    confidence_notes = [
        "ROPA output is synthesized from the DPA and DPIA analyses and may still require controller-side validation before final registration.",
    ]
    if any(field_item.status == RopaFieldStatus.PLACEHOLDER for field_item in ropa_fields):
        confidence_notes.append(
            "One or more Article 30 fields remain placeholders because the supplied vendor materials did not contain controller-owned registry information."
        )

    return RopaAnalysisResult(
        summary=structured.summary,
        vendor_name=_normalize_vendor_name(url, structured.vendor_name),
        ropa_fields=ropa_fields,
        completeness_score=completeness_score,
        raw_analysis=final_text,
        confidence_notes=confidence_notes,
    )