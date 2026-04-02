from __future__ import annotations

import re

from api.schemas import ClauseHighlight
from api.schemas import RiskLevel


_BULLET_PATTERN = re.compile(r"^(?:[-*]|\d+\.)\s+(.+)$")
_HEADING_PREFIX_PATTERN = re.compile(r"^(?:summary|overview|analysis)\s*:\s*", re.IGNORECASE)
_MARKDOWN_EMPHASIS_PATTERN = re.compile(r"\*{1,2}([^*]+)\*{1,2}")
_SECTION_HEADING_PATTERN = re.compile(
    r"^(?:\d+\.?\s*)?(?:concise\s+summary|summary|overview|analysis|key\s+highlights?)\s*:?$",
    re.IGNORECASE,
)


def _clean_inline_markdown(text: str) -> str:
    text = _MARKDOWN_EMPHASIS_PATTERN.sub(r"\1", text)
    return text.replace("`", "").strip()


def _is_structural_heading(text: str) -> bool:
    return bool(_SECTION_HEADING_PATTERN.fullmatch(text.strip()))


def _infer_risk_level(text: str) -> RiskLevel:
    lowered = text.lower()
    if any(token in lowered for token in ("high risk", "critical", "severe")):
        return RiskLevel.HIGH
    if any(token in lowered for token in ("medium risk", "moderate", "caution")):
        return RiskLevel.MEDIUM
    if any(token in lowered for token in ("low risk", "minor", "low concern")):
        return RiskLevel.LOW
    return RiskLevel.UNKNOWN


def build_summary(raw_analysis: str) -> str:
    cleaned = raw_analysis.strip()
    if not cleaned:
        return "No summary generated."

    paragraphs = [segment.strip() for segment in cleaned.split("\n\n") if segment.strip()]

    for paragraph in paragraphs:
        candidate = _HEADING_PREFIX_PATTERN.sub("", paragraph).strip()
        candidate = _clean_inline_markdown(candidate)
        if not candidate or _is_structural_heading(candidate):
            continue
        return candidate

    return "No summary generated."


def build_highlights(raw_analysis: str) -> list[ClauseHighlight]:
    highlights: list[ClauseHighlight] = []

    for line in raw_analysis.splitlines():
        candidate = line.strip()
        if not candidate:
            continue

        match = _BULLET_PATTERN.match(candidate)
        if not match:
            continue

        content = match.group(1).strip()
        if not content:
            continue

        if ":" in content:
            title, rationale = content.split(":", maxsplit=1)
            title = title.strip().strip("*")
            rationale = rationale.strip()
        else:
            title = "Clause note"
            rationale = content

        if not rationale:
            continue

        highlights.append(
            ClauseHighlight(
                title=title or "Clause note",
                rationale=rationale,
                risk_level=_infer_risk_level(content),
            )
        )

    return highlights[:10]


def build_confidence_notes(raw_analysis: str, blocked_links: list[str]) -> list[str]:
    notes: list[str] = []

    if blocked_links:
        notes.append(
            "Some candidate legal pages returned blocked responses and could not be fetched directly."
        )

    lowered = raw_analysis.lower()
    if any(token in lowered for token in ("could not access", "not found", "unable to verify")):
        notes.append("The analysis indicates parts of the policy discovery may be incomplete.")

    return notes
