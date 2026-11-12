"""Unit tests for lossless similarity triage (no model calls)."""
import unittest

from scripts.triage_similarity import RANK, build_groups, priority


def edge(name, left, right, score, different=False, intentional=False):
    return {
        "id": name,
        "records": [left, right],
        "method": "semantic",
        "score": score,
        "different_labels": different,
        "intentional_pair": intentional,
    }


class TriageTests(unittest.TestCase):
    def test_priority_is_ordering_only(self):
        self.assertEqual(priority(edge("a", "1", "2", 0.921)), "routine")
        self.assertEqual(priority(edge("b", "1", "2", 0.936)), "medium")
        self.assertEqual(priority(edge("c", "1", "2", 0.921, different=True)), "high")
        self.assertEqual(priority(edge("d", "1", "2", 0.945, different=True)), "critical")
        self.assertEqual(priority(edge("e", "1", "2", 0.975)), "critical")
        self.assertEqual(priority(edge("f", "1", "2", 0.923, intentional=True)), "high")

    def test_components_include_each_alert_once(self):
        alerts = [
            edge("one", "a", "b", 0.92),
            edge("two", "b", "c", 0.96),
            edge("three", "d", "e", 0.93),
            edge("four", "c", "a", 0.925, different=True),
        ]
        groups = build_groups(alerts)
        self.assertEqual(sorted(len(group) for group in groups), [1, 3])
        self.assertEqual(sorted(x["id"] for group in groups for x in group),
                         sorted(x["id"] for x in alerts))
        self.assertTrue(RANK[priority(groups[0][0])] <= 1)


if __name__ == "__main__":
    unittest.main()
