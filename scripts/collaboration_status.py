"""Read-only project counters; never read record text or external imports."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def summarize(progress, manifest):
    count = progress["production_records"]
    checkpoint = progress["last_checkpoint"]
    next_id = progress["next_id"]
    if any(type(v) is not int or v < 0 for v in (count, checkpoint, next_id)):
        raise ValueError("Invalid progress counters")
    if next_id != count + 1:
        raise ValueError("Non-contiguous reported production IDs")
    signed = sum(c["end_id"] - c["start_id"] + 1 for c in progress["checkpoints"])
    if signed < 0 or signed > count:
        raise ValueError("Invalid signed checkpoint count")
    current = (
        manifest.get("record_count") == count
        and manifest.get("last_checkpoint") == checkpoint
        and manifest.get("next_id") == next_id
    )
    return {
        "production_records": count,
        "last_checkpoint": checkpoint,
        "next_id": next_id,
        "reviewed_checkpoint_records": signed,
        "external_unreviewed_records": count - signed,
        "export_counters_match": current,
        "scope": "metadata only; not signature or content verification",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    progress = json.loads((args.root / "progress.json").read_text(encoding="utf-8"))
    manifest = json.loads((args.root / "exports/manifest.json").read_text(encoding="utf-8"))
    result = summarize(progress, manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["export_counters_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
