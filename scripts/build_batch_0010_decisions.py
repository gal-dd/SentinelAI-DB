"""Build an audited decision file from explicit text-first AI judgements.

Does not predict labels, copy producer labels, or auto-resolve E5 alerts.
Any newly sampled or changed fingerprint fails closed.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sentinel_dataset.core import fingerprint, read_jsonl

LABELS = {"בלמס", "שמור", "סודי", "סודי ביותר"}
KEY_LENGTH = 8

def identify(full_key, annotations, category):
    matches = [label for prefix, label in annotations.items() if full_key.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"Unreviewed or ambiguous {category} fingerprint: {full_key[:16]}")
    return matches[0]


def evidence(judgment, text):
    reason = judgment.get("reason", "")
    if not isinstance(reason,str) or not reason.strip():
        raise ValueError("Missing actual text-grounded review rationale")
    return reason


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
    rows = read_jsonl(args.candidates)
    by_key = {fingerprint(row): row for row in rows}
    if len(rows) != 500 or len(by_key) != len(rows):
        raise ValueError("Expected 500 distinct candidate fingerprints")
    judgments, domains, mismatches = {}, {}, []
    for key, text in packet["texts"].items():
        judgment = identify(key, annotations["labels"], "label")
        expected = judgment["label"]
        if expected not in LABELS or key not in by_key or by_key[key]["text"] != text:
            raise ValueError(f"Bad label review evidence: {key[:16]}")
        actual = by_key[key]["label"]
        if actual != expected:
            mismatches.append({"fingerprint": key[:16], "expected": expected, "candidate_label": actual})
        judgments[key] = {"label": expected, "status": "pass" if expected == actual else "reject",
                          "reason": evidence(judgment, text), "mode": "same_model_text_first_review"}
    for key, text in packet["domain_texts"].items():
        judgment = identify(key, annotations["domains"], "domain")
        expected = judgment["primary_domain"]
        if key not in by_key or by_key[key]["primary_domain"] != expected or by_key[key]["text"] != text:
            mismatches.append({"fingerprint": key[:16], "expected_domain": expected,
                               "candidate_domain": by_key.get(key, {}).get("primary_domain")})
        domains[key] = {"primary_domain": expected, "reason": evidence(judgment, text)}
    if mismatches:
        raise ValueError(f"Review disagreements require content corrections: {mismatches}")
    manual_alerts = annotations.get("alerts", {})
    needed = {item["id"] for item in packet["review_alerts"]}
    if needed != set(manual_alerts):
        raise ValueError(f"E5 high-risk alerts require explicit dispositions. Missing: {needed-set(manual_alerts)}")
    for alert_id, decision in manual_alerts.items():
        if decision.get("status") != "keep" or not str(decision.get("reason", "")).strip():
            raise ValueError(f"Unresolved high-risk alert: {alert_id}")
    if packet["counterfactual_pairs"]:
        raise ValueError("Counterfactual pairs need explicit manual dispositions")
    result = {
        "candidate_digest": packet["candidate_digest"],
        "reviewer": "ChatGPT same-model text-first review of batch 0010; not independent-model verification",
        "records": judgments,
        "domains": domains,
        "alerts": manual_alerts,
        "counterfactual_pairs": {},
        "previous_attempts": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"reviewed_labels": len(judgments), "domain_reviews": len(domains),
                      "high_risk_adjudicated": len(manual_alerts), "disagreements": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
