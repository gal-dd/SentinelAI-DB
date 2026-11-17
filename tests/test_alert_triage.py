"""No-model tests for similarity alert grouping."""
import unittest

from sentinel_dataset.alert_triage import group_alerts


class AlertTriageTests(unittest.TestCase):
    def test_components_preserve_alert_ids_and_required_pairs(self):
        alerts = [
            {"id": "ab", "records": ["a", "b"], "score": 0.93,
             "method": "semantic", "different_labels": False, "intentional_pair": False},
            {"id": "bc", "records": ["b", "c"], "score": 0.98,
             "method": "semantic", "different_labels": False, "intentional_pair": False},
            {"id": "de", "records": ["d", "e"], "score": 0.95,
             "method": "lexical", "different_labels": True, "intentional_pair": False},
        ]
        result = group_alerts(alerts)
        self.assertEqual(result["group_count"], 2)
        self.assertEqual(result["alert_count"], 3)
        self.assertEqual(result["mandatory_alert_count"], 2)
        ids = {i for g in result["groups"] for i in g["alert_ids"]}
        self.assertEqual(ids, {"ab", "bc", "de"})
        self.assertEqual(result["approved_alert_count"], 0)

    def test_empty_packet(self):
        result = group_alerts([])
        self.assertEqual(result["groups"], [])
        self.assertEqual(result["mandatory_alert_count"], 0)

    def test_invalid_pair_is_error(self):
        with self.assertRaises(ValueError):
            group_alerts([{"id": "a", "records": ["one"]}])

    def test_packet_required_alert_ids_are_authoritative(self):
        alerts = [{"id": "a", "records": ["x", "y"], "score": 0.99, "method": "semantic"}]
        self.assertEqual(group_alerts(alerts, [])["mandatory_alert_count"], 0)
        self.assertEqual(group_alerts(alerts, ["a"])["mandatory_alert_count"], 1)
        with self.assertRaises(ValueError):
            group_alerts(alerts, ["missing"])


if __name__ == "__main__":
    unittest.main()
