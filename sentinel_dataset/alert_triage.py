"""Collapse similarity alerts into connected review components without losing pair decisions.

Usage: python -m sentinel_dataset.alert_triage .poc-local/packet.json
    --output .poc-local/alert-groups.json

This is a navigation/reporting tool only; it does not approve or disposition alerts.
"""
import argparse
import json
from collections import Counter
from pathlib import Path


def group_alerts(alerts):
    parent = {}

    def root(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = root(parent[x])
        return parent[x]

    def union(a, b):
        x, y = root(a), root(b)
        if x != y:
            parent[max(x, y)] = min(x, y)

    for item in alerts:
        members = item["records"]
        if len(members) != 2 or not all(isinstance(x, str) for x in members):
            raise ValueError("Similarity alert requires exactly two fingerprint strings")
        union(members[0], members[1])
    groups = {}
    for item in alerts:
        node = root(item["records"][0])
        groups.setdefault(node, []).append(item)
    results = []
    for key, items in groups.items():
        unique = sorted({node for item in items for node in item["records"]})
        required = [item["id"] for item in items
                    if item.get("intentional_pair") or item["score"] >= 0.97
                    or (item.get("different_labels") and item["score"] >= 0.94)]
        results.append({
            "group_id": key[:16], "record_fingerprints": unique,
            "alert_ids": sorted({item["id"] for item in items}),
            "alert_count": len(items), "record_count": len(unique),
            "mandatory_review_alert_ids": sorted(set(required)),
            "different_label_pairs": sum(bool(x.get("different_labels")) for x in items),
            "highest_score": max(x["score"] for x in items),
            "methods": dict(Counter(x["method"] for x in items)),
        })
    results.sort(key=lambda x: (-len(x["mandatory_review_alert_ids"]),
                                -x["alert_count"], x["group_id"]))
    return {
        "groups": results,
        "alert_count": len(alerts),
        "group_count": len(results),
        "mandatory_alert_count": sum(len(x["mandatory_review_alert_ids"]) for x in results),
        "approved_alert_count": 0,
        "semantics": "presentation grouping only; every required alert needs individual disposition",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    from .checkpoints import active_path
    active_path(args.packet)
    active_path(args.output)
    source = json.loads(args.packet.read_text(encoding="utf-8"))
    alerts = source if isinstance(source, list) else source.get("alerts", [])
    result = group_alerts(alerts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"groups": result["group_count"],
                      "alerts": result["alert_count"],
                      "mandatory": result["mandatory_alert_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
