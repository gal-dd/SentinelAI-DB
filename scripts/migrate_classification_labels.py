"""One-time, idempotent classification-label migration for active dataset files.

Preserves all object/text content and historical review fingerprints. Rewrites only
label keys and label-valued fields, then updates the checkpoint SHA-256 manifest.
A caller MUST run dataset verification before committing the modified tree.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {"נמוך": "בלמס", "בינוני": "שמור", "גבוה": "סודי", "חמור": "סודי ביותר"}
LABEL_VALUE_FIELDS = {
    "label", "labels", "סיווג", "classification", "classification_label",
    "expected_label", "predicted_label", "review_label", "assigned_label",
}
CONTENT_DIRS = ("data", "metadata", "reports", "drafts", "config")
SKIP_PREFIXES = ("archive/",)
SKIP_FILES = {"progress.json"}


def rewrite(value, field=None):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            new_key = LABELS.get(key, key)
            if new_key in result:
                raise ValueError(f"Label key collision: {key}")
            result[new_key] = rewrite(item, key)
        return result
    if isinstance(value, list):
        return [rewrite(item, field) for item in value]
    if isinstance(value, str) and field in LABEL_VALUE_FIELDS:
        return LABELS.get(value, value)
    return value


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_structured(path):
    data = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        entries = [json.loads(line) for line in data.splitlines() if line.strip()]
        changed = [rewrite(entry) for entry in entries]
        if changed == entries:
            return False
        new_data = "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in changed
        )
    else:
        original = json.loads(data)
        changed = rewrite(original)
        if changed == original:
            return False
        new_data = json.dumps(changed, ensure_ascii=False, indent=2) + "\n"
    path.write_text(new_data, encoding="utf-8", newline="\n")
    return True


def migrate():
    changed_paths = []
    for folder in CONTENT_DIRS:
        base = ROOT / folder
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in (".json", ".jsonl"):
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative in SKIP_FILES or any(relative.startswith(p) for p in SKIP_PREFIXES):
                continue
            if write_structured(path):
                changed_paths.append(relative)

    progress_path = ROOT / "progress.json"
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        if progress.get("final"):
            raise ValueError("Finalized datasets need an explicitly reviewed migration")

        # Existing pilot audit hashes cover the signed files and the policy/prompts.
        pilot_report = ROOT / "reports/pilot/quality.json"
        if pilot_report.is_file():
            pilot = json.loads(pilot_report.read_text(encoding="utf-8"))
            hashes = pilot.get("data_hashes")
            if isinstance(hashes, dict):
                for name in hashes:
                    target = ROOT / name
                    if not target.is_file():
                        raise ValueError(f"Missing pilot artifact: {name}")
                    hashes[name] = sha(target)
                pilot_report.write_text(
                    json.dumps(pilot, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n",
                )

        for checkpoint in progress.get("checkpoints", []):
            for name in checkpoint["sha256"]:
                path = ROOT / name
                if not path.is_file():
                    raise ValueError(f"Missing checkpoint artifact: {name}")
                checkpoint["sha256"][name] = sha(path)

        if progress.get("pilot_hashes"):
            for name in progress["pilot_hashes"]:
                path = ROOT / name
                if not path.is_file():
                    raise ValueError(f"Missing signed pilot dependency: {name}")
                progress["pilot_hashes"][name] = sha(path)

        progress = rewrite(progress)
        new_progress = json.dumps(progress, ensure_ascii=False, indent=2) + "\n"
        if new_progress != progress_path.read_text(encoding="utf-8"):
            progress_path.write_text(new_progress, encoding="utf-8", newline="\n")
            changed_paths.append("progress.json")

    print(f"Migrated {len(changed_paths)} active files")
    for path in changed_paths:
        print(path)


if __name__ == "__main__":
    migrate()
