"""Semantic and exact-duplicate audit against current remote production.

Read-only: never stages or publishes a checkpoint.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sentinel_dataset.core import read_jsonl, normalize
from sentinel_dataset.semantic import semantic_scan


def load_production(root):
    state = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    records = []
    for checkpoint in state["checkpoints"]:
        number = checkpoint["checkpoint"]
        file = root / f"data/checkpoints/batch-{number:04d}.jsonl"
        records.extend(read_jsonl(file))
    for ext in state.get("external_imports", []):
        manifest_path = root / ext["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        file = manifest_path.parent / manifest["prepared_jsonl_file"]
        records.extend(read_jsonl(file))
    if len(records) != state["production_records"]:
        raise RuntimeError(f"Production count differs: {len(records)} != {state['production_records']}")
    ids = [r["ID"] for r in records]
    if sorted(ids) != list(range(1, state["production_records"] + 1)):
        raise RuntimeError("Production IDs are not consecutive")
    return state, [
        {"text": r["אובייקט"], "label": r["סיווג"],
         "pair_id": None, "source_group_id": f"production-{r['ID']}"}
        for r in records
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", required=True, type=Path)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--cache-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    state, prior = load_production(args.production)
    rows = read_jsonl(args.candidates)
    if len(rows) != 500:
        raise RuntimeError(f"Expected 500 candidates, got {len(rows)}")
    baseline = {normalize(x["text"]) for x in prior}
    internal = [normalize(r["text"]) for r in rows]
    exact_duplicates = [i for i, text in enumerate(internal, 1) if text in baseline]
    if exact_duplicates or len(set(internal)) != len(internal):
        raise RuntimeError(f"Normalized duplicates: production={exact_duplicates}")
    alerts, report = semantic_scan(prior, rows, args.model_dir, args.cache_dir)
    important = [a for a in alerts if a["intentional_pair"]
                 or a["score"] >= 0.97 or (a["different_labels"] and a["score"] >= 0.94)]
    texts_by_fp = {}
    from sentinel_dataset.core import fingerprint
    for row in [*prior, *rows]:
        texts_by_fp[fingerprint(row)] = row["text"]
    def detail(a):
        return {**a, "texts": [texts_by_fp.get(key, "") for key in a["records"]]}
    sorted_alerts = sorted(alerts, key=lambda a: a["score"], reverse=True)
    data = {
        "production_records": state["production_records"],
        "production_last_checkpoint": state["last_checkpoint"],
        "candidate_count": len(rows),
        "normalized_duplicates": 0,
        "semantic_metrics": report,
        "alert_count": len(alerts),
        "high_risk_count": len(important),
        "high_risk": [detail(a) for a in important],
        "top_60": [detail(a) for a in sorted_alerts[:60]],
        "result": "screening_only_not_independent_approval"
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("E5_FULL_BASELINE", json.dumps(
        {k: data[k] for k in ["production_records", "candidate_count", "alert_count", "high_risk_count"]},
        ensure_ascii=False))
    for item in data["high_risk"]:
        print("HIGH_RISK_E5", json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    main()
