from __future__ import annotations

from enum import Enum

from pydantic import AnyHttpUrl
from pydantic import BaseModel
from pydantic import Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class DpaChecklistStatus(str, Enum):
    MISSING = "missing"
    PARTIAL = "partial"
    UNCLEAR = "unclear"
    SATISFIED = "satisfied"


class DpiaThresholdStatus(str, Enum):
    DETECTED = "detected"
    NOT_DETECTED = "not_detected"
    INSUFFICIENT_INFO = "insufficient_info"


class DpiaSectionRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AnalyzeRequest(BaseModel):
    url: AnyHttpUrl
    company_context: str | None = Field(default=None, max_length=2000)


class LinkPreviewRequest(BaseModel):
    urls: list[AnyHttpUrl] = Field(default_factory=list, max_length=20)


class ClauseHighlight(BaseModel):
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    source_url: str | None = None


class DpaChecklistItem(BaseModel):
    requirement_key: str = Field(min_length=1)
    requirement_title: str = Field(min_length=1)
    status: DpaChecklistStatus = DpaChecklistStatus.UNCLEAR
    rationale: str = Field(min_length=1)
    source_url: str | None = None


class AnalyzeResponse(BaseModel):
    input_url: str
    normalized_domain: str
    summary: str
    highlights: list[ClauseHighlight] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)
    blocked_links: list[str] = Field(default_factory=list)
    confidence_notes: list[str] = Field(default_factory=list)
    raw_analysis: str


class DpaAnalyzeResponse(BaseModel):
    input_url: str
    normalized_domain: str
    summary: str
    checklist: list[DpaChecklistItem] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)
    supporting_links: list[str] = Field(default_factory=list)
    blocked_links: list[str] = Field(default_factory=list)
    confidence_notes: list[str] = Field(default_factory=list)
    raw_analysis: str


class LinkPreview(BaseModel):
    requested_url: str
    resolved_url: str
    title: str | None = None
    hostname: str
    content_type: str | None = None


class LinkPreviewResponse(BaseModel):
    previews: list[LinkPreview] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: str
    details: str


class DpiaThresholdItem(BaseModel):
    criterion_key: str = Field(min_length=1)
    criterion_name: str = Field(min_length=1)
    status: DpiaThresholdStatus = DpiaThresholdStatus.INSUFFICIENT_INFO
    evidence: str = Field(min_length=1)
    source_url: str | None = None


class DpiaSection(BaseModel):
    section_key: str = Field(min_length=1)
    section_title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    risk_level: DpiaSectionRisk | None = None
    source_url: str | None = None


class DpiaAnalyzeResponse(BaseModel):
    input_url: str
    normalized_domain: str
    summary: str
    dpia_required: bool
    threshold_score: int
    threshold_criteria: list[DpiaThresholdItem] = Field(default_factory=list)
    dpia_sections: list[DpiaSection] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)
    supporting_links: list[str] = Field(default_factory=list)
    blocked_links: list[str] = Field(default_factory=list)
    confidence_notes: list[str] = Field(default_factory=list)
    raw_analysis: str
