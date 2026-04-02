import unittest

from api.schemas import RiskLevel
from api.services.formatter import build_confidence_notes
from api.services.formatter import build_highlights
from api.services.formatter import build_summary


class FormatterTests(unittest.TestCase):
    def test_build_summary_uses_first_paragraph(self) -> None:
        raw = "Summary: This policy has moderate data sharing terms.\n\n- Data Use: medium risk wording"
        summary = build_summary(raw)
        self.assertEqual(summary, "This policy has moderate data sharing terms.")

    def test_build_highlights_extracts_bullets_and_risk(self) -> None:
        raw = "- Liability: high risk limitation of liability language"
        highlights = build_highlights(raw)
        self.assertEqual(len(highlights), 1)
        self.assertEqual(highlights[0].title, "Liability")
        self.assertEqual(highlights[0].risk_level, RiskLevel.HIGH)

    def test_build_confidence_notes_mentions_blocked_links(self) -> None:
        notes = build_confidence_notes("analysis text", ["https://example.com/terms"])
        self.assertEqual(len(notes), 1)
        self.assertIn("blocked responses", notes[0])


if __name__ == "__main__":
    unittest.main()
