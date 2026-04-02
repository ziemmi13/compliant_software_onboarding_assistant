import unittest

from api.schemas import DpaChecklistItem
from api.schemas import DpaChecklistStatus
from api.services.dpa_analysis_service import build_dpa_analysis_prompt
from api.services.dpa_analysis_service import parse_structured_dpa_analysis
from api.services.dpa_analysis_service import sort_checklist_by_priority
from api.services.dpa_analysis_service import validate_dpa_checklist_sources


class BuildDpaAnalysisPromptTests(unittest.TestCase):
    def test_includes_company_context_when_provided(self) -> None:
        prompt = build_dpa_analysis_prompt(
            "https://example.com/legal/dpa",
            ["https://example.com/legal/dpa"],
            "Law firm onboarding an AI vendor that processes client matter data.",
        )
        self.assertIn("Company context:", prompt)
        self.assertIn("Law firm onboarding an AI vendor", prompt)

    def test_includes_dpa_allowlist(self) -> None:
        prompt = build_dpa_analysis_prompt(
            "https://example.com/legal/dpa",
            ["https://example.com/legal/dpa", "https://example.com/legal/subprocessors"],
        )
        self.assertIn("Discovered DPA pages and annexes:", prompt)
        self.assertIn("https://example.com/legal/subprocessors", prompt)
        self.assertIn("Do not invent, rewrite, or infer any other URL.", prompt)

    def test_requests_article_28_checklist_schema(self) -> None:
        prompt = build_dpa_analysis_prompt("https://example.com/legal/dpa", [])
        self.assertIn('"checklist"', prompt)
        self.assertIn('"requirement_key"', prompt)
        self.assertIn('"status"', prompt)
        self.assertIn("documented_instructions", prompt)


class ParseStructuredDpaAnalysisTests(unittest.TestCase):
    def test_parses_structured_json(self) -> None:
        result = parse_structured_dpa_analysis(
            '{"summary":"The DPA addresses most processor obligations.","checklist":[{"requirement_key":"breach_notification","requirement_title":"Breach notification timing","status":"satisfied","rationale":"Notice is due within 36 hours.","source_url":"https://example.com/legal/dpa"}]}'
        )
        self.assertEqual(result.summary, "The DPA addresses most processor obligations.")
        self.assertEqual(len(result.checklist), 1)
        self.assertEqual(result.checklist[0].status, DpaChecklistStatus.SATISFIED)


class SortChecklistByPriorityTests(unittest.TestCase):
    def test_orders_missing_before_satisfied(self) -> None:
        checklist = [
            DpaChecklistItem(
                requirement_key="audit_rights",
                requirement_title="Audit rights",
                status=DpaChecklistStatus.SATISFIED,
                rationale="Audits are allowed annually.",
            ),
            DpaChecklistItem(
                requirement_key="deletion_or_return",
                requirement_title="Deletion or return",
                status=DpaChecklistStatus.MISSING,
                rationale="No deletion obligation was identified.",
            ),
        ]

        sorted_items = sort_checklist_by_priority(checklist)

        self.assertEqual(
            [item.status for item in sorted_items],
            [DpaChecklistStatus.MISSING, DpaChecklistStatus.SATISFIED],
        )


class ValidateDpaChecklistSourcesTests(unittest.TestCase):
    def test_preserves_verified_source(self) -> None:
        checklist = [
            DpaChecklistItem(
                requirement_key="security_measures",
                requirement_title="Security measures",
                status=DpaChecklistStatus.PARTIAL,
                rationale="Security measures are referenced in an annex.",
                source_url="https://example.com/legal/security-measures",
            )
        ]

        validated, notes = validate_dpa_checklist_sources(checklist, ["https://example.com/legal/security-measures"])

        self.assertEqual(validated[0].source_url, "https://example.com/legal/security-measures")
        self.assertEqual(notes, [])

    def test_nulls_unverified_source(self) -> None:
        checklist = [
            DpaChecklistItem(
                requirement_key="subprocessor_controls",
                requirement_title="Subprocessor controls",
                status=DpaChecklistStatus.PARTIAL,
                rationale="A separate subprocessor page appears to exist.",
                source_url="https://example.com/legal/subprocessors",
            )
        ]

        validated, notes = validate_dpa_checklist_sources(checklist, ["https://example.com/legal/dpa"])

        self.assertIsNone(validated[0].source_url)
        self.assertEqual(len(notes), 1)
        self.assertIn("could not be verified", notes[0])


if __name__ == "__main__":
    unittest.main()