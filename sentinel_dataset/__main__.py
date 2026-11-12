"""Command-line interface for producing and verifying the POC dataset."""

import argparse
from pathlib import Path
import sys

from . import checkpoints as cp
from .core import (PLAN, ROOT, check_quotas, export_rows, fingerprint, json_bytes, jsonl_bytes, read_json,
                   read_jsonl, scenario_catalog, stats, validate_row, validate_rows)
from .model import blind_review, generate
from .production import validate_document_form
from .review import make_packet, verify_decisions, verify_pairs, write_packet
from .semantic import semantic_scan


def semantic_options(parser):
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".poc-local/embeddings")


def cli():
    parser = argparse.ArgumentParser(prog="python -m sentinel_dataset")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    plan = sub.add_parser("plan")
    plan.add_argument("drafts", type=Path, nargs="*")
    gen = sub.add_parser("generate")
    gen.add_argument("job", type=Path)
    gen.add_argument("output", type=Path)
    gen.add_argument("--model", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("candidates", type=Path, nargs="+")
    prep.add_argument("--packet", type=Path, required=True)
    semantic_options(prep)
    judge = sub.add_parser("review")
    judge.add_argument("packet", type=Path)
    judge.add_argument("output", type=Path)
    judge.add_argument("--model", required=True)
    save = sub.add_parser("checkpoint")
    save.add_argument("candidates", type=Path, nargs="+")
    save.add_argument("--decisions", type=Path, required=True)
    semantic_options(save)
    stage = sub.add_parser("stage-checkpoint")
    stage.add_argument("candidates", type=Path, nargs="+")
    stage.add_argument("--decisions", type=Path, required=True)
    stage.add_argument("--output-dir", type=Path, required=True)
    semantic_options(stage)
    final = sub.add_parser("finalize")
    final.add_argument("--dispositions", type=Path)
    final.add_argument("--pending-alerts", type=Path, default=ROOT / ".poc-local/final-alerts.json")
    semantic_options(final)
    push = sub.add_parser("publish")
    for command in (save, final, push):
        command.add_argument("--remote", default="origin")
    return parser


def prepare(args, state, prior, pilot):
    if state["final"]:
        raise ValueError("Dataset is already finalized")
    rows = [row for path in args.candidates for row in read_jsonl(path)]
    if len(rows) != cp.CHECKPOINT_SIZE:
        raise ValueError(f"Expected exactly {cp.CHECKPOINT_SIZE} candidate rows")
    scenarios, sources = scenario_catalog()
    for row in rows:
        validate_row(row, scenarios, sources)
        validate_document_form(row)
    expected_lengths = state["length_plan"]["next_checkpoint_label_lengths"]
    if stats(rows)["label_lengths"] != expected_lengths:
        raise ValueError(f"Checkpoint does not match the planned label/length quotas: {expected_lengths}")
    check_quotas([*prior, *rows], "production")
    batch = state["last_checkpoint"] + 1
    previous_rate = (read_json(ROOT / cp.batch_paths(batch - 1)[2])["review"]["disagreement_rate"]
                     if batch > 1 else 0)
    packet = make_packet(rows, [*pilot, *prior], scenarios, sources, args.model_dir,
                         args.cache_dir, batch, previous_rate)
    return rows, packet


def final_artifacts(args, state, prior, pilot):
    if state["final"]:
        raise ValueError("Dataset is already finalized")
    metrics = check_quotas(prior, "production", final=True)
    lexical = validate_rows(prior, *scenario_catalog(), prior=pilot)
    semantic, semantic_report = semantic_scan(pilot, prior, args.model_dir, args.cache_dir)
    dispositions = {}
    reviewed = disagreements = rejected = corrected = 0
    for entry in state["checkpoints"]:
        quality = read_json(ROOT / cp.batch_paths(entry["checkpoint"])[2])
        review = quality["review"]
        dispositions.update(review["alert_dispositions"])
        reviewed += review["reviewed"]
        for attempt in review["previous_attempts"]:
            reviewed += attempt["reviewed"]
            disagreements += attempt["disagreements"]
            rejected += attempt["rejected"]
        corrected += review["corrected"]
    alerts = sorted(lexical + semantic, key=lambda item: item["id"])
    pending = [item for item in alerts if item["id"] not in dispositions]
    if pending:
        rows = {fingerprint(row): row["text"] for row in [*pilot, *prior]}
        needed = {key for item in pending for key in item["records"]}
        cp.write_file(args.pending_alerts, json_bytes({
            "alerts": pending, "texts": {key: rows[key] for key in sorted(needed)},
        }))
        if not args.dispositions:
            raise ValueError(f"Review {len(pending)} new final-scan alerts in {args.pending_alerts}")
        extra = read_json(args.dispositions)
        verify_pairs(extra, [item["id"] for item in pending], "final-scan alerts")
        dispositions.update(extra)
    dataset = export_rows(prior)
    data_path = Path(cp.FINAL_NAME)
    report_path = Path("reports/final.json")
    # One compact JSON object per line keeps the array readable and the file small.
    data = b"[\n" + b",\n".join(jsonl_bytes([row]).rstrip(b"\n") for row in dataset) + b"\n]\n"
    report = json_bytes({
        "metrics": metrics, "schema": "passed", "normalized_exact_duplicates": 0,
        "semantic": semantic_report, "similarity_alerts": alerts,
        "alert_dispositions": {item["id"]: dispositions[item["id"]] for item in alerts},
        "label_review": {"reviewed": reviewed, "disagreements": disagreements,
                         "rejected": rejected, "corrected": corrected,
                         "disagreement_rate": disagreements / reviewed},
    })
    files = {data_path: data, report_path: report}
    state["final"] = {path.as_posix(): cp.payload_sha(content) for path, content in files.items()}
    return files


def validated_checkpoint(args, state, prior, pilot):
    rows, packet = prepare(args, state, prior, pilot)
    decisions = read_json(args.decisions)
    review = verify_decisions(packet, decisions, rows)
    return cp.batch_artifacts(state, rows, stats(rows), review, packet, decisions)


def run(args):
    if args.command == "generate":
        job = read_json(args.job)
        rows = generate(args.model, job, *scenario_catalog())
        with args.output.open("xb") as out:
            out.write(jsonl_bytes(rows))
        return f"Generated {len(rows)} candidates"
    if args.command == "review":
        cp.write_file(args.output, json_bytes(blind_review(args.model, read_json(args.packet))))
        return f"Saved review: {args.output}"

    state, prior = cp.load_progress()
    pilot = cp.load_pilot()
    if args.command == "plan":
        plan = state["length_plan"].copy()
        if args.drafts:
            rows = [row for path in args.drafts for row in read_jsonl(path)]
            validate_rows(rows, *scenario_catalog(), prior=[*pilot, *prior])
            for row in rows:
                validate_document_form(row)
            actual = stats(rows)["label_lengths"]
            gap = {label: [goal - used for goal, used in zip(cells, actual[label])]
                   for label, cells in plan["next_checkpoint_label_lengths"].items()}
            if any(count < 0 for cells in gap.values() for count in cells):
                raise ValueError(f"Drafts exceed a planned quota: {gap}")
            plan.update(draft_records=len(rows), draft_label_lengths=actual, remaining_in_checkpoint=gap)
        return json_bytes(plan).decode()
    if args.command == "verify":
        validate_rows([*pilot, *prior], *scenario_catalog())
        return json_bytes({"pilot_quality": state["pilot_quality"], "pilot": stats(pilot),
                           "production": stats(prior), "next_id": state["next_id"],
                           "last_checkpoint": state["last_checkpoint"],
                           "finalized": bool(state["final"])}).decode()
    if args.command == "prepare":
        _, packet = prepare(args, state, prior, pilot)
        write_packet(packet, args.packet)
        return f"Saved blind review packet: {args.packet}"

    if args.command == "stage-checkpoint":
        output = args.output_dir.resolve()
        if output == ROOT or (output.exists() and any(output.iterdir())):
            raise ValueError("Stage into a separate empty directory")
        files = validated_checkpoint(args, state, prior, pilot)
        for path, content in cp.state_artifacts(files, state).items():
            cp.write_file(output / path, content)
        return f"Prepared checkpoint {state['last_checkpoint']:04d} for publication: {output}"

    with cp.checkpoint_lock():
        if args.command == "publish":
            return cp.publish(args.remote)
        head, _ = cp.preflight(args.remote)
        state, prior = cp.load_progress()
        if args.command == "checkpoint":
            files = validated_checkpoint(args, state, prior, pilot)
            message = f"Save validated dataset checkpoint {state['last_checkpoint']:04d}"
        else:
            files = final_artifacts(args, state, prior, pilot)
            message = "Assemble and validate the 100,000-record classification dataset"
        return cp.commit_state(files, state, message, args.remote, head)


def main():
    parser = cli()
    args = parser.parse_args()
    try:
        print(run(args))
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, ImportError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
