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


class AnalyzeRequest(BaseModel):
    url: AnyHttpUrl


class ClauseHighlight(BaseModel):
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    risk_level: RiskLevel = RiskLevel.UNKNOWN


class AnalyzeResponse(BaseModel):
    input_url: str
    normalized_domain: str
    summary: str
    highlights: list[ClauseHighlight] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)
    blocked_links: list[str] = Field(default_factory=list)
    confidence_notes: list[str] = Field(default_factory=list)
    raw_analysis: str


class ErrorResponse(BaseModel):
    error: str
    details: str
