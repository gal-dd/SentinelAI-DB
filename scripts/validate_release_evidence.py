"""Validate release provenance and explicitly adjudicated current screening pairs."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gate(request, ledger, state, state_hash, blob, report=None):
    index = request["checkpoint"]
    if (type(index) is not int or index < 1
            or request["expected_production_before"] != state["production_records"]
            or request["expected_production_after"] != state["production_records"] + 500
            or index != state["last_checkpoint"] + 1
            or state["next_id"] != state["production_records"] + 1
            or request.get("candidate_git_blob") != blob
            or request.get("production_progress_sha256") != state_hash
            or ledger.get("production_progress_sha256") != state_hash
            or ledger.get("candidate_git_blob") != blob
            or ledger.get("checkpoint") != index
            or not str(request.get("authorization", "")).strip()):
        raise ValueError("Release baseline, candidate blob or authorization mismatch")
    if report is None:
        return
    if (report["production_records"] != state["production_records"]
            or report["production_last_checkpoint"] != state["last_checkpoint"]
            or report["candidate_count"] != 500
            or report["normalized_duplicates"] != 0
            or report["high_risk_count"] != len(report["high_risk"])):
        raise ValueError("Screening report is incomplete or has a different baseline")
    for pair in report["high_risk"]:
        decision = ledger.get("external_alerts", {}).get(pair["id"])
        if (not decision or decision.get("status") != "keep"
                or decision.get("records") != pair["records"]
                or not str(decision.get("reason", "")).strip()):
            raise ValueError(f"Unreviewed or changed full-baseline pair: {pair['id']}")
        hashes = [sha256(t.encode("utf-8")).hexdigest() for t in pair["texts"]]
        if decision.get("text_sha256") != hashes:
            raise ValueError(f"Full-baseline text evidence mismatch: {pair['id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "ledger", "progress", "candidates"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    request = read(args.request)
    if Path(request["source"]) != args.candidates:
        raise ValueError("Unexpected candidate path")
    blob = subprocess.check_output(["git", "hash-object", str(args.candidates)], text=True).strip()
    gate(request, read(args.ledger), read(args.progress), sha256(args.progress.read_bytes()).hexdigest(),
         blob, read(args.report) if args.report else None)
    print("RELEASE_GATE_PASSED")


if __name__ == "__main__":
    main()
