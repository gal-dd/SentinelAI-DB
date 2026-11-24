"""Export a point-in-time JSON array of the published production records.

The export is a convenience snapshot, not a signed checkpoint or finalization.
Never scan draft/archive folders or rewrite source texts and labels.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sentinel_dataset.checkpoints import load_progress, load_external_imports
from sentinel_dataset.core import read_jsonl


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def export(root, destination, source_commit):
    state, reviewed = load_progress(root)
    external = load_external_imports(state, root)
    rows = list(external)
    sources = []
    for batch in state["checkpoints"]:
        path = root / f'data/checkpoints/batch-{batch["checkpoint"]:04d}.jsonl'
        cohort = read_jsonl(path)
        expected_ids = list(range(batch["start_id"], batch["end_id"] + 1))
        if [row["ID"] for row in cohort] != expected_ids:
            raise ValueError(f"Checkpoint ID order mismatch: {path}")
        rows.extend(cohort)
        sources.append({"path": path.relative_to(root).as_posix(),
                        "records": len(cohort), "sha256": file_hash(path),
                        "provenance": "reviewed_checkpoint"})
    for entry in state.get("external_imports", []):
        mp = root / entry["manifest"]
        manifest = json.loads(mp.read_text(encoding="utf-8"))
        path = mp.parent / manifest["prepared_jsonl_file"]
        sources.append({"path": path.relative_to(root).as_posix(),
                        "records": manifest["record_count"], "sha256": file_hash(path),
                        "provenance": "external_unreviewed"})
    rows.sort(key=lambda row: row["ID"])
    n = state["production_records"]
    if len(rows) != n or [r["ID"] for r in rows] != list(range(1, n + 1)):
        raise ValueError("Missing, overlapping, or unexpected production IDs")
    if len(reviewed) + len(external) != n or state["next_id"] != n + 1:
        raise ValueError("Production totals disagree")
    if any(set(row) != {"ID", "אובייקט", "סיווג"} for row in rows):
        raise ValueError("Unexpected output schema")
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "synthetic_security_classification_current.json"
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    if json.loads(output.read_text(encoding="utf-8")) != rows:
        raise ValueError("JSON roundtrip changed production records")
    manifest = {
        "snapshot_type": "current_production_export_not_final",
        "source_commit": source_commit,
        "source_progress_sha256": file_hash(root / "progress.json"),
        "record_count": n,
        "assigned_id_range": [1, n],
        "last_checkpoint": state["last_checkpoint"],
        "next_id": state["next_id"],
        "reviewed_checkpoint_records": len(reviewed),
        "external_unreviewed_records": len(external),
        "label_counts": dict(Counter(row["סיווג"] for row in rows)),
        "output_file": output.name,
        "output_sha256": file_hash(output),
        "sources": sources,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    print("EXPORT_VERIFIED", json.dumps({k: v for k, v in manifest.items()
          if k != "sources"}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "exports")
    parser.add_argument("--source-commit", default=None)
    args = parser.parse_args()
    sha = args.source_commit or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    export(ROOT, args.output_dir, sha)


if __name__ == "__main__":
    main()
