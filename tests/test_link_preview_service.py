import unittest
from unittest.mock import Mock
from unittest.mock import patch

import requests

from api.services.link_preview_service import fetch_link_preview


class FetchLinkPreviewTests(unittest.TestCase):
    def test_extracts_title_and_final_response_metadata(self) -> None:
        response = Mock()
        response.url = "https://example.com/privacy"
        response.headers = {"Content-Type": "text/html; charset=utf-8"}
        response.text = "<html><head><title>Privacy Policy</title></head><body></body></html>"
        response.raise_for_status = Mock()

        with patch("api.services.link_preview_service.requests.get", return_value=response) as mock_get:
            preview = fetch_link_preview("https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc")

        mock_get.assert_called_once()
        self.assertEqual(preview.requested_url, "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc")
        self.assertEqual(preview.resolved_url, "https://example.com/privacy")
        self.assertEqual(preview.title, "Privacy Policy")
        self.assertEqual(preview.hostname, "example.com")
        self.assertEqual(preview.content_type, "text/html; charset=utf-8")

    def test_falls_back_when_request_fails(self) -> None:
        with patch("api.services.link_preview_service.requests.get", side_effect=requests.RequestException("boom")):
            preview = fetch_link_preview("https://example.com/unreachable")

        self.assertEqual(preview.requested_url, "https://example.com/unreachable")
        self.assertEqual(preview.resolved_url, "https://example.com/unreachable")
        self.assertIsNone(preview.title)
        self.assertEqual(preview.hostname, "example.com")
        self.assertIsNone(preview.content_type)