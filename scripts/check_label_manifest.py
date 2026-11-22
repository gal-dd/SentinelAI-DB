"""Validate migrated label values and signed SHA-256 manifests without changing QA status."""
from hashlib import sha256
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
p = json.loads((root / "progress.json").read_text(encoding="utf-8"))
allowed = {"בלמס", "שמור", "סודי", "סודי ביותר"}
old = {"נמוך", "בינוני", "גבוה", "חמור"}
records = 0

for cp in p["checkpoints"]:
    for name, digest in cp["sha256"].items():
        actual = sha256((root / name).read_bytes()).hexdigest()
        if actual != digest:
            raise SystemExit(f"SHA-256 mismatch: {name}")
    path = root / f"data/checkpoints/batch-{cp['checkpoint']:04d}.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row["סיווג"] not in allowed:
                raise SystemExit(f"Legacy/invalid label: {path}")
            records += 1

if records != p["production_records"]:
    raise SystemExit(f"Count mismatch: {records} != {p['production_records']}")

for line in (root / "data/pilot/pilot.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip() and json.loads(line)["סיווג"] not in allowed:
        raise SystemExit("Legacy/invalid pilot label")

for name, digest in p["pilot_hashes"].items():
    if sha256((root / name).read_bytes()).hexdigest() != digest:
        raise SystemExit(f"Pilot SHA mismatch: {name}")

for path in (root / "config/plan.json", root / "progress.json"):
    data = json.loads(path.read_text(encoding="utf-8"))
    if path.name == "plan.json":
        keys = set(data["production"]["label_lengths"])
    else:
        keys = set(data["length_plan"]["accepted_label_lengths"])
    if keys != allowed:
        raise SystemExit(f"Invalid label key set: {path}")

print(f"Label-and-integrity audit passed: {records} production records, {len(p['checkpoints'])} checkpoints")
