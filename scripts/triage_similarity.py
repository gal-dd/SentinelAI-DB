"""Prepare grouped, risk-prioritized LLM review packets; never auto-approve alerts.

Usage:
 python scripts/triage_similarity.py drafts/batch-0003/review.json \
   drafts/batch-0003/candidates.jsonl --out .poc-local/triage-0003
Requires a local checkout of the repository; uses only the standard library.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sentinel_dataset.core import fingerprint, load_saved, read_jsonl  # noqa: E402


def priority(alert):
    """Priority is a REVIEW ORDER, never a similarity or classification verdict."""
    score = alert["score"]
    if score >= 0.97 or (alert["different_labels"] and score >= 0.94):
        return "critical"
    if alert["different_labels"] or alert["intentional_pair"] or score >= 0.95:
        return "high"
    if score >= 0.935:
        return "medium"
    return "routine"


RANK = {"critical": 0, "high": 1, "medium": 2, "routine": 3}


def build_groups(alerts):
    """Connected components group overlapping pairs without discarding any edge."""
    parent = {}

    def find(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a, b):
        parent[find(a)] = find(b)

    for item in alerts:
        union(*item["records"])
    groups = defaultdict(list)
    for item in alerts:
        groups[find(item["records"][0])].append(item)
    return sorted(groups.values(), key=lambda group: (
        min(RANK[priority(item)] for item in group), -len(group),
        min(item["id"] for item in group)))


def load_texts(candidates):
    """Resolve fingerprint references, including previously accepted and pilot rows."""
    entries = []
    pilot = ROOT / "data/pilot/pilot.jsonl"
    if pilot.exists():
        entries.extend(load_saved(pilot, ROOT / "metadata/pilot/pilot.jsonl", 1))
    size = json.loads((ROOT / "config/plan.json").read_text(encoding="utf-8"))["checkpoint_size"]
    for path in sorted((ROOT / "data/checkpoints").glob("batch-*.jsonl")):
        number = int(path.stem.split("-")[-1])
        entries.extend(load_saved(
            path, ROOT / "metadata/checkpoints" / path.name, (number - 1) * size + 1))
    entries.extend(read_jsonl(candidates))
    return {fingerprint(row): {"text": row["text"],
                               "label": row["label"],
                               "source_group_id": row["source_group_id"],
                               "length": row["length"]}
            for row in entries}


def triage(review_path, candidate_path, out_dir, batch_size):
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    alerts = review.get("alerts_pending")
    if not isinstance(alerts, list):
        raise ValueError("Expected alerts_pending list in draft review JSON")
    if batch_size < 1 or batch_size > 30:
        raise ValueError("batch-size must be 1..30")

    ids = [item["id"] for item in alerts]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate alert IDs in draft review")
    rows = load_texts(candidate_path)
    unknown = {key for alert in alerts for key in alert["records"] if key not in rows}
    if unknown:
        raise ValueError(f"Unresolved record fingerprints: {len(unknown)}")

    groups = build_groups(alerts)
    tasks = []
    for component_index, group in enumerate(groups, 1):
        ordered = sorted(group, key=lambda item: (
            RANK[priority(item)], -item["score"], item["id"]))
        for offset in range(0, len(ordered), batch_size):
            edges = ordered[offset:offset + batch_size]
            keys = sorted({key for item in edges for key in item["records"]})
            tasks.append({
                "component": component_index,
                "component_total_edges": len(group),
                "priority": min((priority(item) for item in edges), key=RANK.get),
                "records": {key: rows[key] for key in keys},
                "alerts": [{**item, "review_priority": priority(item)} for item in edges],
                "instruction": (
                    "Each alert is still pending. Review all alert IDs using the actual "
                    "texts and policy. Return individual keep/reject decisions and a "
                    "specific reason for EACH alert; do not approve a whole cluster "
                    "by default. Any uncertainty or problematic candidate requires "
                    "revision before checkpoint. Priority only orders review."
                ),
            })

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for i, task in enumerate(tasks, 1):
        (out / f"packet-{i:04d}.json").write_text(
            json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "checkpoint": review.get("checkpoint"),
        "candidate_count": review.get("metrics", {}).get("records"),
        "alert_count": len(alerts),
        "component_count": len(groups),
        "review_packets": len(tasks),
        "priority_counts": dict(Counter(priority(a) for a in alerts)),
        "largest_component_edges": sorted((len(g) for g in groups), reverse=True)[:10],
        "all_alert_ids_preserved": sorted(ids) == sorted(
            a["id"] for task in tasks for a in task["alerts"]),
        "quality_review_complete": False,
        "note": "Triage is not semantic adjudication; do not checkpoint without validated review.",
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("review", type=Path)
    p.add_argument("candidates", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--batch-size", type=int, default=12)
    args = p.parse_args()
    print(json.dumps(triage(args.review, args.candidates, args.out, args.batch_size),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
