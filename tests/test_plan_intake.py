"""Focused tests for the autonomous intake's quota-constrained selector."""
import unittest

from scripts.plan_intake import choose


def row(domain, label, length, text):
    return {
        "primary_domain": domain,
        "label": label,
        "length": length,
        "text": text,
    }


class IntakePlanningTests(unittest.TestCase):
    def test_meets_domain_label_and_length_quotas(self):
        domains = {"missile_systems": 2, "cyber_communications_c2": 2}
        cells = {("בלמס", "sentence"): 2, ("שמור", "paragraph"): 2}
        rows = [
            row("missile_systems", "בלמס", "sentence", "a"),
            row("missile_systems", "שמור", "paragraph", "b"),
            row("cyber_communications_c2", "בלמס", "sentence", "c"),
            row("cyber_communications_c2", "שמור", "paragraph", "d"),
        ]
        selected, report = choose(rows, domains, cells)
        self.assertEqual(len(selected), 4)
        self.assertTrue(report["domain_label_coverage_feasible"])
        self.assertEqual(report["missing_domains"], {})
        self.assertEqual(report["missing_label_lengths"], {})
        self.assertEqual(report["missing_domain_labels"], [])

    def test_coverage_is_not_falsely_claimed(self):
        domains = {"missile_systems": 2, "cyber_communications_c2": 2}
        cells = {("בלמס", "sentence"): 2, ("שמור", "paragraph"): 2}
        rows = [
            row("missile_systems", "בלמס", "sentence", "a"),
            row("missile_systems", "שמור", "paragraph", "b"),
            row("cyber_communications_c2", "בלמס", "sentence", "c"),
        ]
        selected, report = choose(rows, domains, cells)
        self.assertEqual(len(selected), 3)
        self.assertFalse(report["domain_label_coverage_feasible"])
        self.assertIn("cyber_communications_c2/שמור", report["missing_domain_labels"])

    def test_skips_rows_that_cannot_fit_target_cells(self):
        domains = {"missile_systems": 2}
        cells = {("בלמס", "sentence"): 1, ("שמור", "paragraph"): 1}
        rows = [
            row("missile_systems", "בלמס", "long", "outside"),
            row("missile_systems", "בלמס", "sentence", "good"),
            row("missile_systems", "שמור", "paragraph", "good2"),
        ]
        selected, report = choose(rows, domains, cells)
        self.assertEqual(selected, [1, 2])
        self.assertEqual(report["selected_count"], 2)

    def test_no_candidates_reports_entire_gap(self):
        domains = {"missile_systems": 2, "cyber_communications_c2": 2}
        cells = {("בלמס", "sentence"): 2, ("שמור", "paragraph"): 2}
        selected, report = choose([], domains, cells)
        self.assertEqual(selected, [])
        self.assertFalse(report["domain_label_coverage_feasible"])
        self.assertEqual(sum(report["missing_domains"].values()), 4)

    def test_quota_oversupply_is_never_selected(self):
        domains = {"missile_systems": 2}
        cells = {("בלמס", "sentence"): 1, ("שמור", "paragraph"): 1}
        rows = [row("missile_systems", "בלמס", "sentence", str(i)) for i in range(10)]
        rows.append(row("missile_systems", "שמור", "paragraph", "needed"))
        selected, report = choose(rows, domains, cells)
        self.assertEqual(len(selected), 2)
        self.assertIn(10, selected)
        self.assertEqual(report["missing_domains"], {})


if __name__ == "__main__":
    unittest.main()
