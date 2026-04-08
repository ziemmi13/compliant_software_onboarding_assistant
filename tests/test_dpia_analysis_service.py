import unittest

from google.genai import types

from api.schemas import DpiaSection
from api.schemas import DpiaSectionFinding
from api.schemas import DpiaSectionRisk
from api.schemas import DpiaThresholdItem
from api.schemas import DpiaThresholdStatus
from api.services.dpia_analysis_service import build_dpia_analysis_prompt
from api.services.dpia_analysis_service import extract_supporting_links_from_grounding
from api.services.dpia_analysis_service import parse_structured_dpia_analysis
from api.services.dpia_analysis_service import sort_threshold_by_priority
from api.services.dpia_analysis_service import validate_dpia_sources


class BuildDpiaAnalysisPromptTests(unittest.TestCase):
    def test_includes_company_context_when_provided(self) -> None:
        prompt = build_dpia_analysis_prompt(
            "https://example.com",
            ["https://example.com/privacy"],
            "AI vendor processing biometric data for employee authentication.",
        )
        self.assertIn("Company context:", prompt)
        self.assertIn("AI vendor processing biometric data", prompt)

    def test_includes_privacy_allowlist(self) -> None:
        prompt = build_dpia_analysis_prompt(
            "https://example.com",
            ["https://example.com/privacy", "https://example.com/security"],
        )
        self.assertIn("Discovered privacy and compliance pages:", prompt)
        self.assertIn("https://example.com/security", prompt)
        self.assertIn("Do not invent, rewrite, or infer any other URL.", prompt)

    def test_requests_threshold_criteria_schema(self) -> None:
        prompt = build_dpia_analysis_prompt("https://example.com", [])
        self.assertIn('"threshold_criteria"', prompt)
        self.assertIn('"criterion_key"', prompt)
        self.assertIn('"status"', prompt)
        self.assertIn("evaluation_or_scoring", prompt)
        self.assertIn("automated_decision_making", prompt)
        self.assertIn("systematic_monitoring", prompt)
        self.assertIn("sensitive_data", prompt)
        self.assertIn("large_scale_processing", prompt)
        self.assertIn("dataset_combining", prompt)
        self.assertIn("vulnerable_subjects", prompt)
        self.assertIn("innovative_technology", prompt)
        self.assertIn("cross_border_transfers", prompt)

    def test_requests_dpia_sections_schema(self) -> None:
        prompt = build_dpia_analysis_prompt("https://example.com", [])
        self.assertIn('"dpia_sections"', prompt)
        self.assertIn("processing_description", prompt)
        self.assertIn("necessity_and_proportionality", prompt)
        self.assertIn("risks_to_data_subjects", prompt)
        self.assertIn("safeguards_and_measures", prompt)

    def test_omits_context_when_not_provided(self) -> None:
        prompt = build_dpia_analysis_prompt("https://example.com", [])
        self.assertNotIn("Company context:", prompt)

    def test_instructs_null_source_when_no_links(self) -> None:
        prompt = build_dpia_analysis_prompt("https://example.com", [])
        self.assertIn("Set source_url to null for every item.", prompt)


class ParseStructuredDpiaAnalysisTests(unittest.TestCase):
    def test_parses_structured_json(self) -> None:
        result = parse_structured_dpia_analysis(
            '{"summary":"The vendor processes sensitive data at scale.",'
            '"threshold_criteria":[{"criterion_key":"sensitive_data","criterion_name":"Sensitive data",'
            '"status":"detected","evidence":"Processes biometric data for authentication.",'
            '"source_url":"https://example.com/privacy"}],'
            '"dpia_sections":[]}'
        )
        self.assertEqual(result.summary, "The vendor processes sensitive data at scale.")
        self.assertEqual(len(result.threshold_criteria), 1)
        self.assertEqual(result.threshold_criteria[0].status, DpiaThresholdStatus.DETECTED)

    def test_parses_json_with_dpia_sections(self) -> None:
        result = parse_structured_dpia_analysis(
            '{"summary":"High-risk processing identified.",'
            '"threshold_criteria":[{"criterion_key":"sensitive_data","criterion_name":"Sensitive data",'
            '"status":"detected","evidence":"Biometric data.","source_url":null},'
            '{"criterion_key":"innovative_technology","criterion_name":"Innovative technology",'
            '"status":"detected","evidence":"Uses AI/ML models.","source_url":null}],'
            '"dpia_sections":[{"section_key":"processing_description",'
            '"section_title":"Systematic description of processing",'
            '"findings":[{"title":"Data processed","detail":"Employee biometric data for authentication."}],"risk_level":null,"source_url":null}]}'
        )
        self.assertEqual(len(result.dpia_sections), 1)
        self.assertEqual(result.dpia_sections[0].section_key, "processing_description")

    def test_strips_code_fences(self) -> None:
        result = parse_structured_dpia_analysis(
            '```json\n{"summary":"Stripped.","threshold_criteria":[],"dpia_sections":[]}\n```'
        )
        self.assertEqual(result.summary, "Stripped.")

    def test_raises_on_empty_input(self) -> None:
        with self.assertRaises(ValueError):
            parse_structured_dpia_analysis("")

    def test_raises_on_invalid_json(self) -> None:
        with self.assertRaises(ValueError):
            parse_structured_dpia_analysis("not json at all")


class SortThresholdByPriorityTests(unittest.TestCase):
    def test_orders_detected_before_not_detected(self) -> None:
        criteria = [
            DpiaThresholdItem(
                criterion_key="sensitive_data",
                criterion_name="Sensitive data",
                status=DpiaThresholdStatus.NOT_DETECTED,
                evidence="No sensitive data processed.",
            ),
            DpiaThresholdItem(
                criterion_key="innovative_technology",
                criterion_name="Innovative technology",
                status=DpiaThresholdStatus.DETECTED,
                evidence="Uses AI/ML models.",
            ),
        ]

        sorted_items = sort_threshold_by_priority(criteria)

        self.assertEqual(
            [item.status for item in sorted_items],
            [DpiaThresholdStatus.DETECTED, DpiaThresholdStatus.NOT_DETECTED],
        )

    def test_orders_insufficient_info_between_detected_and_not_detected(self) -> None:
        criteria = [
            DpiaThresholdItem(
                criterion_key="cross_border_transfers",
                criterion_name="Cross-border transfers",
                status=DpiaThresholdStatus.NOT_DETECTED,
                evidence="No evidence.",
            ),
            DpiaThresholdItem(
                criterion_key="dataset_combining",
                criterion_name="Dataset combining",
                status=DpiaThresholdStatus.INSUFFICIENT_INFO,
                evidence="Documentation unclear.",
            ),
            DpiaThresholdItem(
                criterion_key="systematic_monitoring",
                criterion_name="Systematic monitoring",
                status=DpiaThresholdStatus.DETECTED,
                evidence="Tracks user behavior.",
            ),
        ]

        sorted_items = sort_threshold_by_priority(criteria)

        self.assertEqual(
            [item.status for item in sorted_items],
            [DpiaThresholdStatus.DETECTED, DpiaThresholdStatus.INSUFFICIENT_INFO, DpiaThresholdStatus.NOT_DETECTED],
        )


class ValidateDpiaSourcesTests(unittest.TestCase):
    def test_preserves_verified_source(self) -> None:
        criteria = [
            DpiaThresholdItem(
                criterion_key="sensitive_data",
                criterion_name="Sensitive data",
                status=DpiaThresholdStatus.DETECTED,
                evidence="Processes health data.",
                source_url="https://example.com/privacy",
            )
        ]
        sections: list[DpiaSection] = []

        validated_criteria, validated_sections, notes = validate_dpia_sources(
            criteria, sections, ["https://example.com/privacy"]
        )

        self.assertEqual(validated_criteria[0].source_url, "https://example.com/privacy")
        self.assertEqual(notes, [])

    def test_nulls_unverified_source_in_criteria(self) -> None:
        criteria = [
            DpiaThresholdItem(
                criterion_key="innovative_technology",
                criterion_name="Innovative technology",
                status=DpiaThresholdStatus.DETECTED,
                evidence="Uses AI models.",
                source_url="https://example.com/unknown-page",
            )
        ]
        sections: list[DpiaSection] = []

        validated_criteria, validated_sections, notes = validate_dpia_sources(
            criteria, sections, ["https://example.com/privacy"]
        )

        self.assertIsNone(validated_criteria[0].source_url)
        self.assertEqual(len(notes), 1)
        self.assertIn("could not be verified", notes[0])

    def test_nulls_unverified_source_in_sections(self) -> None:
        criteria: list[DpiaThresholdItem] = []
        sections = [
            DpiaSection(
                section_key="processing_description",
                section_title="Processing description",
                findings=[DpiaSectionFinding(title="Data processed", detail="Employee data for HR.")],
                source_url="https://example.com/bad-link",
            )
        ]

        validated_criteria, validated_sections, notes = validate_dpia_sources(
            criteria, sections, ["https://example.com/privacy"]
        )

        self.assertIsNone(validated_sections[0].source_url)
        self.assertEqual(len(notes), 1)

    def test_preserves_null_sources(self) -> None:
        criteria = [
            DpiaThresholdItem(
                criterion_key="large_scale_processing",
                criterion_name="Large-scale processing",
                status=DpiaThresholdStatus.INSUFFICIENT_INFO,
                evidence="Unclear from docs.",
                source_url=None,
            )
        ]

        validated_criteria, _, notes = validate_dpia_sources(criteria, [], [])

        self.assertIsNone(validated_criteria[0].source_url)
        self.assertEqual(notes, [])


class ExtractSupportingLinksFromGroundingTests(unittest.TestCase):
    def test_collects_grounding_links_not_in_sources(self) -> None:
        grounding_metadata = types.GroundingMetadata(
            grounding_chunks=[
                types.GroundingChunk(
                    web=types.GroundingChunkWeb(uri="https://example.com/blog/gdpr", title="GDPR Blog")
                ),
                types.GroundingChunk(
                    web=types.GroundingChunkWeb(uri="https://example.com/privacy", title="Privacy")
                ),
            ]
        )

        supporting_links = extract_supporting_links_from_grounding(
            grounding_metadata,
            ["https://example.com/privacy"],
        )

        self.assertEqual(supporting_links, ["https://example.com/blog/gdpr"])

    def test_returns_empty_list_without_grounding(self) -> None:
        self.assertEqual(extract_supporting_links_from_grounding(None, []), [])


if __name__ == "__main__":
    unittest.main()
