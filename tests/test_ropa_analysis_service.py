import unittest

from api.schemas import DpaAnalyzeResponse
from api.schemas import DpaChecklistItem
from api.schemas import DpaChecklistStatus
from api.schemas import DpiaAnalyzeResponse
from api.schemas import DpiaSection
from api.schemas import DpiaSectionFinding
from api.schemas import DpiaThresholdItem
from api.schemas import DpiaThresholdStatus
from api.schemas import RopaField
from api.schemas import RopaFieldEntry
from api.schemas import RopaFieldStatus
from api.services.ropa_analysis_service import build_ropa_synthesis_prompt
from api.services.ropa_analysis_service import calculate_completeness_score
from api.services.ropa_analysis_service import parse_structured_ropa_analysis


def build_dpa_result() -> DpaAnalyzeResponse:
    return DpaAnalyzeResponse(
        input_url="https://example.com/",
        normalized_domain="example.com",
        summary="The DPA addresses most core processor obligations.",
        checklist=[
            DpaChecklistItem(
                requirement_key="security_measures",
                requirement_title="Security measures",
                status=DpaChecklistStatus.SATISFIED,
                rationale="Security measures are described in the DPA annex.",
                source_url="https://example.com/legal/dpa",
            )
        ],
        source_links=["https://example.com/legal/dpa"],
        supporting_links=[],
        blocked_links=[],
        confidence_notes=[],
        raw_analysis="{}",
    )


def build_dpia_result(with_sections: bool = True) -> DpiaAnalyzeResponse:
    return DpiaAnalyzeResponse(
        input_url="https://example.com/",
        normalized_domain="example.com",
        summary="The vendor processes employee account data for access control.",
        dpia_required=with_sections,
        threshold_score=2 if with_sections else 1,
        threshold_criteria=[
            DpiaThresholdItem(
                criterion_key="innovative_technology",
                criterion_name="Innovative technology",
                status=DpiaThresholdStatus.DETECTED,
                evidence="The vendor uses AI-assisted security scoring.",
                source_url="https://example.com/privacy",
            )
        ],
        dpia_sections=(
            [
                DpiaSection(
                    section_key="processing_description",
                    section_title="Systematic description of processing",
                    findings=[
                        DpiaSectionFinding(
                            title="Data processed",
                            detail="Employee names, emails, device identifiers, and authentication logs.",
                        )
                    ],
                    source_url="https://example.com/privacy",
                )
            ]
            if with_sections
            else []
        ),
        source_links=["https://example.com/privacy"],
        supporting_links=[],
        blocked_links=[],
        confidence_notes=[],
        raw_analysis="{}",
    )


class BuildRopaSynthesisPromptTests(unittest.TestCase):
    def test_includes_company_context(self) -> None:
        prompt = build_ropa_synthesis_prompt(
            "https://example.com",
            build_dpa_result(),
            build_dpia_result(),
            "HR SaaS vendor onboarding for employee account management.",
        )

        self.assertIn("Company context:", prompt)
        self.assertIn("HR SaaS vendor onboarding", prompt)

    def test_includes_dpa_checklist(self) -> None:
        prompt = build_ropa_synthesis_prompt("https://example.com", build_dpa_result(), build_dpia_result())

        self.assertIn("DPA analysis:", prompt)
        self.assertIn("security_measures", prompt)

    def test_includes_dpia_threshold(self) -> None:
        prompt = build_ropa_synthesis_prompt("https://example.com", build_dpa_result(), build_dpia_result())

        self.assertIn("DPIA analysis:", prompt)
        self.assertIn("innovative_technology", prompt)

    def test_includes_dpia_sections(self) -> None:
        prompt = build_ropa_synthesis_prompt("https://example.com", build_dpa_result(), build_dpia_result())

        self.assertIn("processing_description", prompt)
        self.assertIn("Employee names, emails", prompt)

    def test_handles_empty_dpia_sections(self) -> None:
        prompt = build_ropa_synthesis_prompt("https://example.com", build_dpa_result(), build_dpia_result(with_sections=False))

        self.assertIn('"dpia_sections": []', prompt)

    def test_includes_json_schema(self) -> None:
        prompt = build_ropa_synthesis_prompt("https://example.com", build_dpa_result(), build_dpia_result())

        self.assertIn('"vendor_name"', prompt)
        self.assertIn('"ropa_fields"', prompt)
        self.assertIn('"controller_details"', prompt)
        self.assertIn('"status": "placeholder"', prompt)


class CalculateCompletenessScoreTests(unittest.TestCase):
    def test_all_placeholder(self) -> None:
        score = calculate_completeness_score(
            [
                RopaField(
                    field_key="controller_details",
                    field_title="Controller and DPO details",
                    article_ref="Art. 30(1)(a)",
                    status=RopaFieldStatus.PLACEHOLDER,
                )
            ]
        )

        self.assertEqual(score, 0)

    def test_all_populated(self) -> None:
        score = calculate_completeness_score(
            [
                RopaField(
                    field_key="purposes_of_processing",
                    field_title="Purposes of processing",
                    article_ref="Art. 30(1)(b)",
                    status=RopaFieldStatus.POPULATED,
                ),
                RopaField(
                    field_key="security_measures",
                    field_title="Technical and organizational security measures",
                    article_ref="Art. 30(1)(g)",
                    status=RopaFieldStatus.POPULATED,
                ),
            ]
        )

        self.assertEqual(score, 100)

    def test_empty_fields(self) -> None:
        self.assertEqual(calculate_completeness_score([]), 0)

    def test_mixed_statuses(self) -> None:
        score = calculate_completeness_score(
            [
                RopaField(
                    field_key="purposes_of_processing",
                    field_title="Purposes of processing",
                    article_ref="Art. 30(1)(b)",
                    status=RopaFieldStatus.POPULATED,
                ),
                RopaField(
                    field_key="data_subject_categories",
                    field_title="Categories of data subjects",
                    article_ref="Art. 30(1)(c)",
                    status=RopaFieldStatus.PARTIAL,
                ),
                RopaField(
                    field_key="retention_periods",
                    field_title="Retention periods",
                    article_ref="Art. 30(1)(f)",
                    status=RopaFieldStatus.PLACEHOLDER,
                ),
                RopaField(
                    field_key="security_measures",
                    field_title="Technical and organizational security measures",
                    article_ref="Art. 30(1)(g)",
                    status=RopaFieldStatus.PARTIAL,
                ),
            ]
        )

        self.assertEqual(score, 50)


class ParseStructuredRopaAnalysisTests(unittest.TestCase):
    def test_parses_valid_json(self) -> None:
        result = parse_structured_ropa_analysis(
            '{"summary":"Vendor processes employee account data.","vendor_name":"Example","ropa_fields":[{"field_key":"purposes_of_processing","field_title":"Purposes of processing","article_ref":"Art. 30(1)(b)","status":"populated","entries":[{"title":"Access management","detail":"Provide user authentication and account administration."}],"source_notes":["Derived from DPIA processing description."]}]}'
        )

        self.assertEqual(result.vendor_name, "Example")
        self.assertEqual(len(result.ropa_fields), 1)
        self.assertEqual(result.ropa_fields[0].status, RopaFieldStatus.POPULATED)

    def test_strips_code_fences(self) -> None:
        result = parse_structured_ropa_analysis(
            '```json\n{"summary":"Stripped.","vendor_name":"Example","ropa_fields":[]}\n```'
        )

        self.assertEqual(result.summary, "Stripped.")

    def test_raises_on_empty_input(self) -> None:
        with self.assertRaises(ValueError):
            parse_structured_ropa_analysis("")

    def test_raises_on_invalid_json(self) -> None:
        with self.assertRaises(ValueError):
            parse_structured_ropa_analysis("not json")

    def test_raises_on_missing_summary(self) -> None:
        with self.assertRaises(ValueError):
            parse_structured_ropa_analysis('{"vendor_name":"Example","ropa_fields":[]}')


if __name__ == "__main__":
    unittest.main()