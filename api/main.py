from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import urlparse
import asyncio

_log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(level=_log_level, format="%(levelname)s:%(name)s:%(message)s")
logging.getLogger("api").setLevel(_log_level)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import AnalyzeRequest
from api.schemas import AnalyzeResponse
from api.schemas import DpaAnalyzeResponse
from api.schemas import DpiaAnalyzeResponse
from api.schemas import ErrorResponse
from api.schemas import LinkPreviewRequest
from api.schemas import LinkPreviewResponse
from api.services.analysis_service import run_terms_analysis
from api.services.analysis_service import validate_input_url
from api.services.dpa_analysis_service import run_dpa_analysis
from api.services.dpia_analysis_service import run_dpia_analysis
from api.services.formatter import build_confidence_notes
from api.services.link_preview_service import fetch_link_previews


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(
    title="Legal Scout API",
    version="0.1.0",
    description="HTTP wrapper for Legal Scout ADK agents.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/link-previews", response_model=LinkPreviewResponse, responses={500: {"model": ErrorResponse}})
async def link_previews(request: LinkPreviewRequest) -> LinkPreviewResponse:
    try:
        previews = await asyncio.to_thread(fetch_link_previews, [str(url) for url in request.urls])
    except Exception as exc:
        logger.exception("Link preview failed")
        raise HTTPException(
            status_code=500,
            detail={"error": "preview_failed", "details": str(exc)},
        ) from exc

    return LinkPreviewResponse(previews=previews)


@app.post("/api/analyze", response_model=AnalyzeResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    try:
        normalized_url = validate_input_url(str(request.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_url", "details": str(exc)}) from exc

    try:
        result = await run_terms_analysis(
            normalized_url,
            company_context=request.company_context,
        )
    except Exception as exc:
        logger.exception("Terms analysis failed for %s", normalized_url)
        raise HTTPException(
            status_code=500,
            detail={"error": "analysis_failed", "details": str(exc)},
        ) from exc

    parsed = urlparse(normalized_url)
    return AnalyzeResponse(
        input_url=normalized_url,
        normalized_domain=parsed.netloc,
        summary=result.summary,
        highlights=result.highlights,
        source_links=result.source_links,
        blocked_links=result.blocked_links,
        confidence_notes=build_confidence_notes(result.raw_analysis, result.blocked_links) + result.confidence_notes,
        raw_analysis=result.raw_analysis,
    )


@app.post("/api/analyze-dpa", response_model=DpaAnalyzeResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def analyze_dpa(request: AnalyzeRequest) -> DpaAnalyzeResponse:
    try:
        normalized_url = validate_input_url(str(request.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_url", "details": str(exc)}) from exc

    try:
        result = await run_dpa_analysis(
            normalized_url,
            company_context=request.company_context,
        )
    except Exception as exc:
        logger.exception("DPA analysis failed for %s", normalized_url)
        raise HTTPException(
            status_code=500,
            detail={"error": "analysis_failed", "details": str(exc)},
        ) from exc

    parsed = urlparse(normalized_url)
    return DpaAnalyzeResponse(
        input_url=normalized_url,
        normalized_domain=parsed.netloc,
        summary=result.summary,
        checklist=result.checklist,
        source_links=result.source_links,
        supporting_links=result.supporting_links,
        blocked_links=result.blocked_links,
        confidence_notes=build_confidence_notes(result.raw_analysis, result.blocked_links) + result.confidence_notes,
        raw_analysis=result.raw_analysis,
    )


@app.post("/api/analyze-dpia", response_model=DpiaAnalyzeResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def analyze_dpia(request: AnalyzeRequest) -> DpiaAnalyzeResponse:
    try:
        normalized_url = validate_input_url(str(request.url))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_url", "details": str(exc)}) from exc

    try:
        result = await run_dpia_analysis(
            normalized_url,
            company_context=request.company_context,
        )
    except Exception as exc:
        logger.exception("DPIA analysis failed for %s", normalized_url)
        raise HTTPException(
            status_code=500,
            detail={"error": "analysis_failed", "details": str(exc)},
        ) from exc

    parsed = urlparse(normalized_url)
    return DpiaAnalyzeResponse(
        input_url=normalized_url,
        normalized_domain=parsed.netloc,
        summary=result.summary,
        dpia_required=result.dpia_required,
        threshold_score=result.threshold_score,
        threshold_criteria=result.threshold_criteria,
        dpia_sections=result.dpia_sections,
        source_links=result.source_links,
        supporting_links=result.supporting_links,
        blocked_links=result.blocked_links,
        confidence_notes=build_confidence_notes(result.raw_analysis, result.blocked_links) + result.confidence_notes,
        raw_analysis=result.raw_analysis,
    )
