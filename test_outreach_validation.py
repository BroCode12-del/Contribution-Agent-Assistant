"""Synthetic fixtures only: no model request, saved draft, or sent message."""

import copy
import json
import unittest

from outreach_validation import validate_draft


class DraftValidationTests(unittest.TestCase):
    def setUp(self):
        self.context = {"opportunity_id": "O1", "fit": [{"evidence_ids": ["E1"]}]}
        self.draft = {
            "opportunity_id": "O1",
            "draft": (
                "I am interested in learning about pandas CSV handling after the issue status "
                "has been reviewed. Static observations of the reviewed code show pandas.read_csv "
                "calls; they do not establish authorship or mastery. Both practice solutions "
                "were AI-written references. Their passing checks on fixed inputs do not "
                "establish my independent ability. The saved availability snapshot says hold, "
                "and I am not requesting assignment or offering to implement the issue."
            ),
            "evidence_ids": ["E1"],
            "review_notes": ["Private fixture only; hold is a saved availability snapshot."],
        }

    def test_valid_structure(self):
        self.assertEqual(validate_draft(json.dumps(self.draft), "stop", self.context), self.draft)

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            validate_draft("not JSON", "stop", self.context)

    def test_incomplete_generation(self):
        with self.assertRaisesRegex(ValueError, "finish normally"):
            validate_draft(json.dumps(self.draft), "length", self.context)

    def test_non_object(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            validate_draft("[]", "stop", self.context)

    def test_rejects_bad_fields(self):
        for field, value in (
            ("opportunity_id", "O99"),
            ("draft", "Expression of interest."),
            ("draft", "word " * 101),
            ("evidence_ids", ["E99"]),
            ("evidence_ids", []),
            ("evidence_ids", [123]),
            ("evidence_ids", "E1"),
            ("review_notes", []),
            ("review_notes", [" "]),
        ):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(self.draft)
                changed[field] = value
                with self.assertRaises(ValueError):
                    validate_draft(json.dumps(changed), "stop", self.context)


if __name__ == "__main__":
    unittest.main()
