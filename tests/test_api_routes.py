import unittest
from unittest.mock import AsyncMock
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from api.services.analysis_service import AgentAnalysisResult


class ApiRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_analyze_endpoint_success(self) -> None:
        mock_result = AgentAnalysisResult(
            raw_analysis="Summary: Solid baseline.\n- Liability: high risk cap on damages",
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
        self.assertTrue(payload["summary"])
        self.assertEqual(len(payload["highlights"]), 1)

    def test_analyze_endpoint_accepts_missing_company_context(self) -> None:
        mock_result = AgentAnalysisResult(
            raw_analysis="Summary: Solid baseline.",
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


if __name__ == "__main__":
    unittest.main()
