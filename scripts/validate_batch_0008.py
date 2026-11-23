"""Fail-closed structural preflight for a candidate-only batch 0008.

This validates a draft; it does not make classification or publication decisions.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sentinel_dataset.core import normalize, scenario_catalog, validate_row, read_jsonl
from sentinel_dataset.production import validate_document_form

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    rows = read_jsonl(args.candidates)
    progress = json.loads((ROOT / "progress.json").read_text(encoding="utf-8"))
    targets = json.loads((ROOT / "config/defense-domain-targets.json").read_text(encoding="utf-8"))
    scenarios, sources = scenario_catalog()
    expected_domain = {x["id"]: x["target"] // 200 for x in targets["domain_targets"]}
    expected_cells = {
        (label, length): count
        for label, counts in progress["length_plan"]["next_checkpoint_label_lengths"].items()
        for length, count in zip(progress["length_plan"]["length_order"], counts)
    }
    if len(rows) != 500:
        raise ValueError(f"Must have 500 records, not {len(rows)}")
    seen = set()
    for i, row in enumerate(rows, start=1):
        try:
            validate_row(row, scenarios, sources)
            validate_document_form(row)
        except (ValueError, TypeError, KeyError) as err:
            raise ValueError(f"row {i}: {err}") from err
        key = normalize(row["text"])
        if key in seen:
            raise ValueError(f"Exact normalized duplicate within draft at row {i}")
        seen.add(key)
    observed_domain = Counter(r["primary_domain"] for r in rows)
    observed_cells = Counter((r["label"],r["length"]) for r in rows)
    observed_pairs = {(r["primary_domain"],r["label"]) for r in rows}
    if dict(observed_domain) != expected_domain:
        raise ValueError(f"Domain quotas mismatch: {observed_domain} != {expected_domain}")
    if dict(observed_cells) != expected_cells:
        raise ValueError(f"Label/length quotas mismatch: {observed_cells} != {expected_cells}")
    if len(observed_pairs) != len(expected_domain) * 4:
        raise ValueError(f"Domain-label coverage missing: {len(observed_pairs)}/24")
    info = {
        "candidate_count": len(rows), "production_baseline": progress["production_records"],
        "source_last_checkpoint": progress["last_checkpoint"],
        "next_id_unallocated": progress["next_id"], "unique_normalized_texts": len(seen),
        "domain_counts": dict(observed_domain),
        "label_length_counts": {f"{label}/{length}": count for (label,length),count in observed_cells.items()},
        "domain_label_coverage": len(observed_pairs), "result": "structural_preflight_passed_not_publication_approval"
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(info, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("STRUCTURAL_0008", json.dumps(info, ensure_ascii=False))

if __name__ == "__main__":
    main()
