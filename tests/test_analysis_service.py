import unittest

from api.services.analysis_service import build_analysis_prompt
from api.services.analysis_service import parse_structured_analysis
from api.services.analysis_service import validate_input_url


class ValidateInputUrlTests(unittest.TestCase):
    def test_accepts_public_https_url(self) -> None:
        result = validate_input_url("https://example.com/terms")
        self.assertEqual(result, "https://example.com/terms")

    def test_rejects_localhost(self) -> None:
        with self.assertRaises(ValueError):
            validate_input_url("http://localhost:8000")

    def test_rejects_private_ipv4(self) -> None:
        with self.assertRaises(ValueError):
            validate_input_url("http://192.168.1.10/legal")

    def test_rejects_loopback_ipv4(self) -> None:
        with self.assertRaises(ValueError):
            validate_input_url("http://127.0.0.1")

    def test_rejects_non_http_schemes(self) -> None:
        with self.assertRaises(ValueError):
            validate_input_url("ftp://example.com")


class BuildAnalysisPromptTests(unittest.TestCase):
    def test_includes_company_context_when_provided(self) -> None:
        prompt = build_analysis_prompt(
            "https://example.com",
            "B2B SaaS handling employee personal data.",
        )
        self.assertIn("Company context:", prompt)
        self.assertIn("B2B SaaS handling employee personal data.", prompt)

    def test_omits_company_context_section_when_missing(self) -> None:
        prompt = build_analysis_prompt("https://example.com")
        self.assertNotIn("Company context:", prompt)

    def test_requires_json_only_output(self) -> None:
        prompt = build_analysis_prompt("https://example.com")
        self.assertIn("Return only a valid JSON object.", prompt)
        self.assertIn('"summary"', prompt)
        self.assertIn('"highlights"', prompt)


class ParseStructuredAnalysisTests(unittest.TestCase):
    def test_parses_structured_json(self) -> None:
        result = parse_structured_analysis(
            '{"summary":"A concise summary.","highlights":[{"title":"Liability","rationale":"Cap on damages.","risk_level":"high"}]}'
        )
        self.assertEqual(result.summary, "A concise summary.")
        self.assertEqual(len(result.highlights), 1)

    def test_parses_json_wrapped_in_code_fence(self) -> None:
        result = parse_structured_analysis(
            '```json\n{"summary":"A concise summary.","highlights":[]}\n```'
        )
        self.assertEqual(result.summary, "A concise summary.")

    def test_rejects_unstructured_response(self) -> None:
        with self.assertRaises(ValueError):
            parse_structured_analysis("This is not JSON.")


if __name__ == "__main__":
    unittest.main()
