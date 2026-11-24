"""Read-only generic candidate validation against a verified production worktree."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sentinel_dataset.checkpoints import load_progress, load_external_imports
from sentinel_dataset.core import read_json, read_jsonl, validate_rows, reject_external_text_duplicates, stats
from sentinel_dataset.production import validate_document_form
from sentinel_dataset.domains import require_coverage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--scenarios", type=Path, required=True)
    parser.add_argument("--checkpoint", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    state, prior = load_progress(ROOT)
    if state["last_checkpoint"] not in {args.checkpoint - 2, args.checkpoint - 1}:
        raise ValueError("Unexpected production checkpoint; inspect live progress")
    rows = read_jsonl(args.candidates)
    if len(rows) != 500:
        raise ValueError("Expected 500 records")
    scenarios = read_json(ROOT / "config/scenarios.json")
    for key, value in read_json(args.scenarios).items():
        if key in scenarios and scenarios[key] != value:
            raise ValueError("Conflicting scenario: " + key)
        scenarios[key] = value
    for row in rows:
        validate_document_form(row)
    alerts = validate_rows(rows, scenarios, read_json(ROOT / "config/sources.json"), prior)
    reject_external_text_duplicates(rows, load_external_imports(state, ROOT))
    actual = stats(rows)
    expected = state["length_plan"]["next_checkpoint_label_lengths"]
    if actual["label_lengths"] != expected:
        raise ValueError(f"Live length quotas differ: {actual['label_lengths']} != {expected}")
    domains = require_coverage(rows, checkpoint=args.checkpoint)
    report = {"candidate_count": len(rows), "baseline": state["production_records"],
              "baseline_checkpoint": state["last_checkpoint"], "checkpoint": args.checkpoint,
              "official_baseline": state["last_checkpoint"] == args.checkpoint - 1,
              "exact_normalized_duplicates": 0, "lexical_alert_count": len(alerts),
              "label_lengths": actual["label_lengths"], **domains,
              "scope": "structural screening, not content approval"}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("FULL_BATCH_STRUCTURAL", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
