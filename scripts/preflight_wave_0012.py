"""Read-only partial-wave preflight; no claim of complete content QA."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sentinel_dataset.checkpoints import load_progress, load_external_imports
from sentinel_dataset.core import read_json, read_jsonl, validate_rows, reject_external_text_duplicates, stats
from sentinel_dataset.production import validate_document_form
from sentinel_dataset.domains import batch_targets, coverage


def main():
    state, prior = load_progress(ROOT)
    directory = ROOT / "drafts/chat/batch-0012"
    scenarios = read_json(ROOT / "config/scenarios.json")
    for file in sorted(directory.glob("scenarios-wave-*.json")):
        for key, value in read_json(file).items():
            if key in scenarios and scenarios[key] != value:
                raise ValueError("Scenario conflict: " + key)
            scenarios[key] = value
    rows = [row for file in sorted(directory.glob("candidates-wave-*.jsonl"))
            for row in read_jsonl(file)]
    for row in rows:
        validate_document_form(row)
    alerts = validate_rows(rows, scenarios, read_json(ROOT / "config/sources.json"), prior)
    reject_external_text_duplicates(rows, load_external_imports(state, ROOT))
    actual = coverage(rows)
    quota = batch_targets(12)
    if any(actual["domain_counts"][key] > n for key, n in quota.items()):
        raise ValueError("Partial wave exceeds a domain quota")
    if len(rows) > 500 or any(count > 125 for count in stats(rows)["labels"].values()):
        raise ValueError("Partial wave exceeds a label quota")
    print("PARTIAL_WAVE_PREFLIGHT", json.dumps({"rows": len(rows), "baseline": state["production_records"],
          "label_lengths": stats(rows)["label_lengths"], **actual,
          "lexical_similarity_alerts": len(alerts), "semantic_review": "not_run",
          "publication": "not_authorized"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
