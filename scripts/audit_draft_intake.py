"""Read-only intake audit against signed production plus external import cohort."""
import json
from pathlib import Path
import subprocess
import sys

from sentinel_dataset import checkpoints as cp
from sentinel_dataset.core import normalize, LABELS, LENGTHS

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = [7, 50, 43, 25]
BATCHES = {
    "0006": (None, "drafts/work/batch-0006/candidates.jsonl", 403),
    "0007": ("origin/producer/chat-defense-v2", "drafts/chat/batch-0007/candidates.jsonl", 433),
    "0008": ("origin/producer/chat-defense-v2", "drafts/chat/batch-0008/candidates.jsonl", 427),
    "0009": ("origin/producer/chat-defense-v2", "drafts/chat/batch-0009/candidates.jsonl", 438),
}

def read_rows(ref, path):
    if ref is None:
        raw = (ROOT / path).read_text(encoding="utf-8")
    else:
        raw = subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT).decode("utf-8")
    return [json.loads(line) for line in raw.splitlines() if line.strip()]

def run():
    state, reviewed = cp.load_progress()
    external = cp.load_external_imports(state)
    index = {}
    for row in external:
        index.setdefault(normalize(row["אובייקט"]), []).append(row["ID"])
    result = {"production_records": state["production_records"], "next_id": state["next_id"],
              "external_records_unreviewed": len(external), "draft_batches": {}}
    for name, (ref, path, held) in BATCHES.items():
        rows = read_rows(ref, path)
        matrix = {label: [sum(r["label"] == label and r["length"] == kind for r in rows) for kind in LENGTHS]
                  for label in LABELS}
        duplicates = [{"candidate_position": i, "external_ids": index[normalize(row["text"])]}
                      for i, row in enumerate(rows, 1) if normalize(row["text"]) in index]
        valid = len(rows) == 500 and all(row["label"] in LABELS for row in rows)
        quota = all(cells == EXPECTED for cells in matrix.values())
        result["draft_batches"][name] = {
            "candidate_count": len(rows), "valid_label_schema": valid,
            "label_length_counts": matrix, "quota_ready": quota,
            "external_exact_duplicates": duplicates,
            "existing_human_review_holds": held,
            "publication_ready": False,
            "reason": "Outstanding independent review and human holds; this audit is not content approval",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if state["next_id"] != 6101 or len(external) != 3600:
        raise SystemExit("Unexpected production baseline")

if __name__ == "__main__":
    run()
