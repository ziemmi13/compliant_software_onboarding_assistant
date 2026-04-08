import unittest
from unittest.mock import AsyncMock
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from api.services.analysis_service import AgentAnalysisResult
from api.services.dpa_analysis_service import DpaAnalysisResult
from api.services.dpia_analysis_service import DpiaAnalysisResult
from api.schemas import LinkPreview
from api.schemas import ClauseHighlight
from api.schemas import DpaChecklistItem
from api.schemas import DpaChecklistStatus
from api.schemas import DpiaThresholdItem
from api.schemas import DpiaThresholdStatus
from api.schemas import DpiaSection
from api.schemas import DpiaSectionFinding
from api.schemas import RiskLevel


class ApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_analyze_endpoint_success(self) -> None:
        mock_result = AgentAnalysisResult(
            summary="Solid baseline.",
            highlights=[
                ClauseHighlight(
                    title="Liability",
                    rationale="Cap on damages.",
                    risk_level=RiskLevel.HIGH,
                    source_url="https://example.com/terms",
                )
            ],
            raw_analysis='{"summary":"Solid baseline.","highlights":[{"title":"Liability","rationale":"Cap on damages.","risk_level":"high","source_url":"https://example.com/terms"}]}',
            source_links=["https://example.com/terms"],
            blocked_links=[],
        )

        with patch("api.main.run_terms_analysis", new=AsyncMock(return_value=mock_result)):
            response = self.client.post(
                "/api/analyze",
                json={
                    "url": "https://example.com",
                    "company_context": "B2B HR SaaS handling employee data.",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["input_url"], "https://example.com/")
        self.assertEqual(payload["normalized_domain"], "example.com")
        self.assertEqual(payload["summary"], "Solid baseline.")
        self.assertEqual(len(payload["highlights"]), 1)
        self.assertEqual(payload["highlights"][0]["source_url"], "https://example.com/terms")

    def test_analyze_endpoint_accepts_missing_company_context(self) -> None:
        mock_result = AgentAnalysisResult(
            summary="Solid baseline.",
            highlights=[],
            raw_analysis='{"summary":"Solid baseline.","highlights":[]}',
            source_links=[],
            blocked_links=[],
        )

        with patch("api.main.run_terms_analysis", new=AsyncMock(return_value=mock_result)) as mock_run:
            response = self.client.post("/api/analyze", json={"url": "https://example.com"})

        self.assertEqual(response.status_code, 200)
        mock_run.assert_awaited_once()

    def test_analyze_endpoint_rejects_invalid_scheme(self) -> None:
        response = self.client.post("/api/analyze", json={"url": "ftp://example.com"})
        self.assertEqual(response.status_code, 422)

    def test_analyze_dpa_endpoint_success(self) -> None:
        mock_result = DpaAnalysisResult(
            summary="Solid DPA baseline.",
            checklist=[
                DpaChecklistItem(
                    requirement_key="breach_notification",
                    requirement_title="Breach notification timing",
                    status=DpaChecklistStatus.SATISFIED,
                    rationale="The DPA requires notice within 36 hours.",
                    source_url="https://example.com/legal/data-processing-agreement",
                )
            ],
            raw_analysis='{"summary":"Solid DPA baseline.","checklist":[{"requirement_key":"breach_notification","requirement_title":"Breach notification timing","status":"satisfied","rationale":"The DPA requires notice within 36 hours.","source_url":"https://example.com/legal/data-processing-agreement"}]}',
            source_links=["https://example.com/legal/data-processing-agreement"],
            supporting_links=["https://example.com/privacy"],
            blocked_links=[],
        )

        with patch("api.main.run_dpa_analysis", new=AsyncMock(return_value=mock_result)):
            response = self.client.post(
                "/api/analyze-dpa",
                json={
                    "url": "https://example.com/legal/data-processing-agreement",
                    "company_context": "Law firm reviewing processor obligations for client data.",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"], "Solid DPA baseline.")
        self.assertEqual(len(payload["checklist"]), 1)
        self.assertEqual(payload["checklist"][0]["status"], "satisfied")
        self.assertEqual(payload["checklist"][0]["source_url"], "https://example.com/legal/data-processing-agreement")
        self.assertEqual(payload["supporting_links"], ["https://example.com/privacy"])

    def test_analyze_dpia_endpoint_success(self) -> None:
        mock_result = DpiaAnalysisResult(
            summary="DPIA likely required due to sensitive data and AI processing.",
            dpia_required=True,
            threshold_score=3,
            threshold_criteria=[
                DpiaThresholdItem(
                    criterion_key="sensitive_data",
                    criterion_name="Sensitive data",
                    status=DpiaThresholdStatus.DETECTED,
                    evidence="Processes biometric data for authentication.",
                    source_url="https://example.com/privacy",
                ),
                DpiaThresholdItem(
                    criterion_key="innovative_technology",
                    criterion_name="Innovative technology",
                    status=DpiaThresholdStatus.DETECTED,
                    evidence="Uses AI/ML for risk scoring.",
                    source_url="https://example.com/privacy",
                ),
                DpiaThresholdItem(
                    criterion_key="large_scale_processing",
                    criterion_name="Large-scale processing",
                    status=DpiaThresholdStatus.DETECTED,
                    evidence="Processes data for millions of users.",
                    source_url=None,
                ),
            ],
            dpia_sections=[
                DpiaSection(
                    section_key="processing_description",
                    section_title="Systematic description of processing",
                    findings=[DpiaSectionFinding(title="Data processed", detail="Employee biometric data for authentication.")],
                    source_url="https://example.com/privacy",
                ),
            ],
            raw_analysis='{"summary":"DPIA likely required.","threshold_criteria":[],"dpia_sections":[]}',
            source_links=["https://example.com/privacy"],
            supporting_links=["https://example.com/security"],
            blocked_links=[],
        )

        with patch("api.main.run_dpia_analysis", new=AsyncMock(return_value=mock_result)):
            response = self.client.post(
                "/api/analyze-dpia",
                json={
                    "url": "https://example.com",
                    "company_context": "AI vendor processing biometric data.",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"], "DPIA likely required due to sensitive data and AI processing.")
        self.assertTrue(payload["dpia_required"])
        self.assertEqual(payload["threshold_score"], 3)
        self.assertEqual(len(payload["threshold_criteria"]), 3)
        self.assertEqual(payload["threshold_criteria"][0]["status"], "detected")
        self.assertEqual(len(payload["dpia_sections"]), 1)
        self.assertEqual(payload["dpia_sections"][0]["section_key"], "processing_description")
        self.assertEqual(payload["supporting_links"], ["https://example.com/security"])

    def test_link_previews_endpoint_success(self) -> None:
        mock_previews = [
            LinkPreview(
                requested_url="https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc",
                resolved_url="https://example.com/privacy",
                title="Privacy Policy",
                hostname="example.com",
                content_type="text/html; charset=utf-8",
            )
        ]

        with patch("api.main.fetch_link_previews", return_value=mock_previews):
            response = self.client.post(
                "/api/link-previews",
                json={"urls": ["https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"]},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["previews"]), 1)
        self.assertEqual(payload["previews"][0]["title"], "Privacy Policy")
        self.assertEqual(payload["previews"][0]["hostname"], "example.com")


if __name__ == "__main__":
    unittest.main()
