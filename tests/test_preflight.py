"""Tests for non-publishing deterministic preflight (no model download)."""
import unittest
from unittest.mock import patch

from sentinel_dataset.preflight import analyze, _blocks, _sentences


def candidate(text, label="נמוך", length="paragraph", domain="missile_systems"):
    return {"text": text, "label": label, "length": length, "primary_domain": domain}


class PreflightTests(unittest.TestCase):
    def scan(self, rows, references=()):
        with patch("sentinel_dataset.preflight.validate_row"), patch(
            "sentinel_dataset.preflight.validate_document_form"
        ):
            return analyze(rows, references=references,
                           reference_names=["active-reference.jsonl"] * len(references),
                           scenarios={}, sources={})

    def test_repeated_paragraph_is_review_queue_not_auto_rejection(self):
        repeated = "המסמך מתאר הסכמה מנהלית שהתקבלה בוועדה ונשמרה ליד מקור מאושר כדי לאפשר ביקורת עתידית."
        rows = [candidate(repeated + "\n\nסקירה אחת נבדקה לאחר דיון."),
                candidate(repeated + "\n\nנציגי הפורום הוסיפו הערת הבהרה נוספת.")]
        report = self.scan(rows)
        self.assertTrue(any(x["code"] == "repeated_paragraph"
                            and x["rows"] == [1, 2] for x in report["warnings"]))
        self.assertFalse(any(x["code"] == "exact_duplicate_within" for x in report["errors"]))

    def test_exact_duplicate_blocks(self):
        rows = [candidate("מיזם הגנה אווירית הציג לציבור הסבר כללי."),
                candidate("מיזם הגנה אווירית הציג לציבור הסבר כללי.")]
        report = self.scan(rows)
        self.assertTrue(any(x["code"] == "exact_duplicate_within" for x in report["errors"]))
        self.assertEqual(report["status"], "blocked")

    def test_references_support_production_training_field(self):
        text = "התוכנית הוכיחה שהחלטת הוועדה נשמרה במסמך המקור."
        report = self.scan([candidate(text)], references=[[{"אובייקט": text}]])
        self.assertTrue(any(x["code"] == "exact_duplicate_reference" for x in report["errors"]))

    def test_lengths_and_dynamic_quotas(self):
        report = self.scan([candidate("מסמך קצר", length="short")])
        self.assertNotEqual(report["status"], "preflight_pass_with_review")
        with patch("sentinel_dataset.preflight.validate_row"), patch(
            "sentinel_dataset.preflight.validate_document_form"
        ):
            out = analyze([candidate("מסמך קצר", length="short")],
                          expected_lengths={"נמוך": [7, 50, 43, 25]},
                          scenarios={}, sources={})
        self.assertTrue(any(x["code"] == "length_quota" for x in out["errors"]))

    def test_substantial_fragments_only(self):
        self.assertEqual(_blocks("הערה קטנה\n\nעוד הערה"), [])
        sentence = "הוועדה תיעדה את החלטתה במסמך חתום והעבירה אותו לביקורת חיצונית לטובת בדיקה נוספת."
        self.assertEqual(len(_sentences(sentence)), 1)


if __name__ == "__main__":
    unittest.main()
