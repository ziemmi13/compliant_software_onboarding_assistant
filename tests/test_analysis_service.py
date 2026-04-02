import unittest

from api.services.analysis_service import build_analysis_prompt
from api.services.analysis_service import parse_structured_analysis
from api.services.analysis_service import sort_highlights_by_severity
from api.services.analysis_service import validate_highlight_sources
from api.services.analysis_service import validate_input_url
from api.schemas import ClauseHighlight
from api.schemas import RiskLevel


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
            ["https://example.com/terms"],
            "B2B SaaS handling employee personal data.",
        )
        self.assertIn("Company context:", prompt)
        self.assertIn("B2B SaaS handling employee personal data.", prompt)

    def test_omits_company_context_section_when_missing(self) -> None:
        prompt = build_analysis_prompt("https://example.com", ["https://example.com/terms"])
        self.assertNotIn("Company context:", prompt)

    def test_requires_json_only_output(self) -> None:
        prompt = build_analysis_prompt("https://example.com", ["https://example.com/terms"])
        self.assertIn("Return only a valid JSON object.", prompt)
        self.assertIn('"summary"', prompt)
        self.assertIn('"highlights"', prompt)

    def test_requests_source_url_for_highlights(self) -> None:
        prompt = build_analysis_prompt("https://example.com", ["https://example.com/terms"])
        self.assertIn('"source_url"', prompt)
        self.assertIn("chosen only from the discovered source pages", prompt)

    def test_includes_discovered_source_allowlist(self) -> None:
        prompt = build_analysis_prompt(
            "https://example.com",
            ["https://example.com/terms", "https://example.com/privacy"],
        )
        self.assertIn("Discovered source pages:", prompt)
        self.assertIn("https://example.com/terms", prompt)
        self.assertIn("https://example.com/privacy", prompt)
        self.assertIn("Do not invent, rewrite, or infer any other URL.", prompt)

    def test_requires_null_citations_when_no_discovered_sources(self) -> None:
        prompt = build_analysis_prompt("https://example.com", [])
        self.assertIn("No discovered source pages were confirmed.", prompt)
        self.assertIn("Set source_url to null for every highlight.", prompt)


class ParseStructuredAnalysisTests(unittest.TestCase):
    def test_parses_structured_json(self) -> None:
        result = parse_structured_analysis(
            '{"summary":"A concise summary.","highlights":[{"title":"Liability","rationale":"Cap on damages.","risk_level":"high","source_url":"https://example.com/terms"}]}'
        )
        self.assertEqual(result.summary, "A concise summary.")
        self.assertEqual(len(result.highlights), 1)
        self.assertEqual(result.highlights[0].source_url, "https://example.com/terms")

    def test_parses_json_wrapped_in_code_fence(self) -> None:
        result = parse_structured_analysis(
            '```json\n{"summary":"A concise summary.","highlights":[]}\n```'
        )
        self.assertEqual(result.summary, "A concise summary.")

    def test_rejects_unstructured_response(self) -> None:
        with self.assertRaises(ValueError):
            parse_structured_analysis("This is not JSON.")

    def test_sorts_highlights_from_high_to_low(self) -> None:
        result = parse_structured_analysis(
            '{"summary":"A concise summary.","highlights":[{"title":"Privacy","rationale":"Data use clause.","risk_level":"low"},{"title":"Liability","rationale":"Cap on damages.","risk_level":"high"},{"title":"Termination","rationale":"Broad termination right.","risk_level":"medium"},{"title":"Misc","rationale":"Other note.","risk_level":"unknown"}]}'
        )
        self.assertEqual(
            [highlight.risk_level for highlight in result.highlights],
            [RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW, RiskLevel.UNKNOWN],
        )


class SortHighlightsBySeverityTests(unittest.TestCase):
    def test_preserves_high_to_low_priority(self) -> None:
        highlights = [
            ClauseHighlight(title="Low", rationale="Low issue", risk_level=RiskLevel.LOW),
            ClauseHighlight(title="High", rationale="High issue", risk_level=RiskLevel.HIGH),
            ClauseHighlight(title="Unknown", rationale="Unknown issue", risk_level=RiskLevel.UNKNOWN),
            ClauseHighlight(title="Medium", rationale="Medium issue", risk_level=RiskLevel.MEDIUM),
        ]

        sorted_highlights = sort_highlights_by_severity(highlights)

        self.assertEqual(
            [highlight.risk_level for highlight in sorted_highlights],
            [RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW, RiskLevel.UNKNOWN],
        )


class ValidateHighlightSourcesTests(unittest.TestCase):
    def test_preserves_verified_citation(self) -> None:
        highlights = [
            ClauseHighlight(
                title="Liability",
                rationale="Cap on damages.",
                risk_level=RiskLevel.HIGH,
                source_url="https://example.com/terms",
            )
        ]

        validated, notes = validate_highlight_sources(highlights, ["https://example.com/terms"])

        self.assertEqual(validated[0].source_url, "https://example.com/terms")
        self.assertEqual(notes, [])

    def test_nulls_unverified_citation_and_adds_note(self) -> None:
        highlights = [
            ClauseHighlight(
                title="Privacy",
                rationale="Broad data use rights.",
                risk_level=RiskLevel.MEDIUM,
                source_url="https://example.com/privacy",
            )
        ]

        validated, notes = validate_highlight_sources(highlights, ["https://example.com/terms"])

        self.assertIsNone(validated[0].source_url)
        self.assertEqual(len(notes), 1)
        self.assertIn("could not be verified", notes[0])


if __name__ == "__main__":
    unittest.main()
