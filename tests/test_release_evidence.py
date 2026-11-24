"""Generic release evidence tests using fictional library examples."""
from copy import deepcopy
from hashlib import sha256
import unittest
from scripts.validate_release_evidence import gate


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.state={"production_records":1000,"last_checkpoint":2,"next_id":1001}
        self.request={"checkpoint":3,"expected_production_before":1000,
                      "expected_production_after":1500,"candidate_git_blob":"blob",
                      "production_progress_sha256":"base","authorization":"test fixture"}
        self.pair={"id":"pair","records":["a","b"],"texts":["ספרייה עירונית","מועדון קריאה"]}
        self.ledger={"checkpoint":3,"production_progress_sha256":"base","candidate_git_blob":"blob",
                     "external_alerts":{"pair":{"status":"keep","records":["a","b"],
                        "reason":"Distinct library events",
                        "text_sha256":[sha256(t.encode()).hexdigest() for t in self.pair["texts"]]}}}
        self.report={"production_records":1000,"production_last_checkpoint":2,"candidate_count":500,
                     "normalized_duplicates":0,"high_risk_count":1,"high_risk":[self.pair]}

    def verify(self, report=None):
        gate(self.request,self.ledger,self.state,"base","blob",self.report if report is None else report)

    def test_valid(self):
        self.verify()

    def test_stale_pair_does_not_block(self):
        self.verify(dict(self.report, high_risk=[], high_risk_count=0))

    def test_new_pair_blocks(self):
        self.report["high_risk"][0]["id"]="unknown"
        with self.assertRaises(ValueError): self.verify()

    def test_changed_text_blocks(self):
        self.report["high_risk"][0]["texts"][0]="Changed fixture"
        with self.assertRaises(ValueError): self.verify()

    def test_changed_baseline_blocks(self):
        self.state["next_id"]=1002
        with self.assertRaises(ValueError): self.verify()
