"""Civilian fixture tests for explicit review reconciliation."""
from copy import deepcopy
from hashlib import sha256
import unittest

from scripts.reconcile_review_decisions import reconcile
from sentinel_dataset.core import digest, fingerprint


class ReviewReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"text": "ספרייה קהילתית פתוחה לקהל", "label": "בלמס",
                      "primary_domain": "general_negative_controls"}]
        self.key = fingerprint(self.rows[0])
        self.packet = {"candidate_digest": digest([self.key]),
                       "texts": {self.key: self.rows[0]["text"]},
                       "domain_texts": {self.key: self.rows[0]["text"]},
                       "random_sample": [self.key], "targeted_sample": [],
                       "alerts": [{"id": "current", "records": [self.key, "prior"]}],
                       "review_alerts": [{"id": "current", "records": [self.key, "prior"]}],
                       "counterfactual_pairs": {}}
        text_hash = sha256(self.rows[0]["text"].encode("utf-8")).hexdigest()
        self.ledger = {
            "candidate_digest": self.packet["candidate_digest"],
            "production_progress_sha256": "baseline",
            "checkpoint": 12, "reviewer": "civilian fixture",
            "records": {self.key: {"label": "בלמס", "status": "pass",
                                   "text_sha256": text_hash, "reason": "public library notice"}},
            "domains": {self.key: {"primary_domain": "general_negative_controls",
                                   "text_sha256": text_hash, "reason": "civilian library"}},
            "alerts": {"current": {"status": "keep", "reason": "different event",
                                   "records": [self.key, "prior"]},
                       "stale": {"status": "keep", "reason": "old reviewed pair",
                                 "records": ["old", "other"]}}
        }

    def test_disappeared_pair_does_not_block(self):
        result = reconcile(self.packet, self.ledger, self.rows, 12, "baseline")
        self.assertEqual(set(result["alerts"]), {"current"})

    def test_new_pair_fails_closed(self):
        packet = deepcopy(self.packet)
        packet["alerts"].append({"id": "new", "records": [self.key, "new-prior"]})
        packet["review_alerts"].append(packet["alerts"][-1])
        with self.assertRaisesRegex(ValueError, "Missing explicit review reason"):
            reconcile(packet, self.ledger, self.rows, 12, "baseline")

    def test_changed_baseline_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            reconcile(self.packet, self.ledger, self.rows, 12, "different")

    def test_changed_pair_fails_closed(self):
        packet = deepcopy(self.packet)
        packet["review_alerts"][0]["records"] = [self.key, "other"]
        with self.assertRaisesRegex(ValueError, "changed similarity pair"):
            reconcile(packet, self.ledger, self.rows, 12, "baseline")

    def test_changed_text_evidence_fails_closed(self):
        ledger = deepcopy(self.ledger)
        ledger["records"][self.key]["text_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "mismatched review"):
            reconcile(self.packet, ledger, self.rows, 12, "baseline")

    def test_unreviewed_record_fails_closed(self):
        ledger = deepcopy(self.ledger)
        ledger["records"] = {}
        with self.assertRaisesRegex(ValueError, "Missing explicit review reason"):
            reconcile(self.packet, ledger, self.rows, 12, "baseline")

    def test_rejected_label_fails_closed(self):
        ledger = deepcopy(self.ledger)
        ledger["records"][self.key]["status"] = "reject"
        with self.assertRaisesRegex(ValueError, "Rejected review"):
            reconcile(self.packet, ledger, self.rows, 12, "baseline")
