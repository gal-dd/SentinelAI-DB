import unittest
from scripts.collaboration_status import summarize


class CollaborationStatusTests(unittest.TestCase):
    def setUp(self):
        self.progress = {
            "production_records": 5, "last_checkpoint": 1, "next_id": 6,
            "checkpoints": [{"start_id": 1, "end_id": 3}],
        }
        self.manifest = {"record_count": 5, "last_checkpoint": 1, "next_id": 6}

    def test_counts(self):
        result = summarize(self.progress, self.manifest)
        self.assertEqual(result["reviewed_checkpoint_records"], 3)
        self.assertEqual(result["external_unreviewed_records"], 2)
        self.assertTrue(result["export_counters_match"])

    def test_stale_export(self):
        self.manifest["record_count"] = 4
        self.assertFalse(summarize(self.progress, self.manifest)["export_counters_match"])

    def test_invalid_next_id(self):
        self.progress["next_id"] = 7
        with self.assertRaises(ValueError):
            summarize(self.progress, self.manifest)

    def test_invalid_signed_count(self):
        self.progress["checkpoints"][0]["end_id"] = 6
        with self.assertRaises(ValueError):
            summarize(self.progress, self.manifest)
