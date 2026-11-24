"""Reconcile explicit reviewed decisions with a current review packet.

Pure review bookkeeping. Never predict a label or approve an unreviewed pair.
A ledger is reusable only for the same candidate digest and production snapshot.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sentinel_dataset.core import digest, fingerprint, read_jsonl, json_bytes
from sentinel_dataset.review import verify_decisions
from sentinel_dataset.domains import verify_domain_review


def require_reason(decision, key):
    if not isinstance(decision, dict) or not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
        raise ValueError(f"Missing explicit review reason: {key}")
    return decision


def reconcile(packet, ledger, rows, checkpoint, baseline_hash):
    keys = [fingerprint(row) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Candidate fingerprints are not unique")
    if (packet["candidate_digest"] != digest(keys)
            or ledger.get("candidate_digest") != packet["candidate_digest"]
            or ledger.get("production_progress_sha256") != baseline_hash
            or ledger.get("checkpoint") != checkpoint):
        raise ValueError("Candidate or production review provenance mismatch")
    by_key = dict(zip(keys, rows))
    decisions = {"candidate_digest": packet["candidate_digest"],
                 "reviewer": ledger.get("reviewer"),
                 "records": {}, "domains": {}, "alerts": {},
                 "counterfactual_pairs": {},
                 "previous_attempts": ledger.get("previous_attempts", [])}
    for packet_field, ledger_field, destination, label_field in (
            ("texts", "records", "records", "label"),
            ("domain_texts", "domains", "domains", "primary_domain")):
        for key, value in packet[packet_field].items():
            if key not in by_key or by_key[key]["text"] != value:
                raise ValueError(f"Review text differs from candidate: {key}")
            decision = require_reason(ledger.get(ledger_field, {}).get(key), key)
            if (decision.get("text_sha256") != sha256(value.encode("utf-8")).hexdigest()
                    or decision.get(label_field) != by_key[key][label_field]):
                raise ValueError(f"Unresolved or mismatched review: {key}")
            if destination == "records" and decision.get("status") != "pass":
                raise ValueError(f"Rejected review: {key}")
            decisions[destination][key] = {k: v for k, v in decision.items() if k != "text_sha256"}
    for alert in packet.get("review_alerts", packet["alerts"]):
        key = alert["id"]
        decision = require_reason(ledger.get("alerts", {}).get(key), key)
        if (decision.get("status") != "keep" or decision.get("records") != alert["records"]):
            raise ValueError(f"Unresolved or changed similarity pair: {key}")
        decisions["alerts"][key] = decision
    for key, members in packet["counterfactual_pairs"].items():
        decision = require_reason(ledger.get("counterfactual_pairs", {}).get(key), key)
        if (decision.get("status") != "keep" or decision.get("members") != sorted(members)):
            raise ValueError(f"Unresolved or changed counterfactual pair: {key}")
        decisions["counterfactual_pairs"][key] = decision
    verify_decisions(packet, decisions, rows)
    verify_domain_review(rows, checkpoint, decisions["domains"])
    return decisions


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("packet", "ledger", "candidates", "progress", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--checkpoint", type=int, required=True)
    args = p.parse_args()
    state = json.loads(args.progress.read_text(encoding="utf-8"))
    if args.checkpoint != state["last_checkpoint"] + 1:
        raise ValueError("Review is not for the next production checkpoint")
    result = reconcile(json.loads(args.packet.read_text(encoding="utf-8")),
                       json.loads(args.ledger.read_text(encoding="utf-8")),
                       read_jsonl(args.candidates), args.checkpoint,
                       sha256(args.progress.read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(json_bytes(result))


if __name__ == "__main__":
    main()
