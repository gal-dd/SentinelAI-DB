"""Command-line interface for producing and verifying the POC dataset."""

import argparse
from pathlib import Path
import sys

from . import checkpoints as cp
from .core import (PLAN, ROOT, check_quotas, fingerprint, json_bytes, jsonl_bytes, read_json,
                   read_jsonl, scenario_catalog, stats, validate_row, validate_rows)
from .domains import BATCH_TARGETS, coverage, require_coverage, verify_domain_review
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
        command.add_argument("--branch", choices=[cp.BRANCH], default=cp.BRANCH)
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
    from .core import reject_external_text_duplicates
    reject_external_text_duplicates(rows, cp.load_external_imports(state))
    expected_lengths = state["length_plan"]["next_checkpoint_label_lengths"]
    if stats(rows)["label_lengths"] != expected_lengths:
        raise ValueError(f"Checkpoint does not match the planned label/length quotas: {expected_lengths}")
    require_coverage(rows)
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
    domains = require_coverage(prior, state["last_checkpoint"])
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
    # Monitor all semantic neighbors; only unresolved high-risk alerts block finalization.
    required = [item for item in alerts if item["intentional_pair"]
                or item["score"] >= 0.97
                or (item["different_labels"] and item["score"] >= 0.94)]
    pending = [item for item in required if item["id"] not in dispositions]
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
    external = cp.load_external_imports(state)
    dataset = cp.export_production(state, prior, external)
    data_path = Path(cp.FINAL_NAME)
    report_path = Path("reports/final.json")
    # One compact JSON object per line keeps the array readable and the file small.
    data = b"[\n" + b",\n".join(jsonl_bytes([row]).rstrip(b"\n") for row in dataset) + b"\n]\n"
    report = json_bytes({
        "metrics": metrics, "schema": "passed", "normalized_exact_duplicates": 0,
        "reviewed_metrics_scope": "reviewed checkpoints only",
        "production_records": len(dataset), "external_records_without_content_review": len(external),
        **domains, "domain_review": {"status": "completed", "checkpoints": state["last_checkpoint"]},
        "semantic": semantic_report, "similarity_alerts": alerts,
        "similarity_policy": "monitor_all_review_high_risk_v1",
        "alert_count_total": len(alerts),
        "alert_count_high_risk": len(required),
        "alert_count_unreviewed_routine": sum(item["id"] not in dispositions for item in alerts if item not in required),
        "alert_dispositions": {item["id"]: dispositions[item["id"]] for item in alerts if item["id"] in dispositions},
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
    domains = require_coverage(rows)
    domain_review = verify_domain_review(rows, state["last_checkpoint"] + 1, decisions.get("domains"))
    return cp.batch_artifacts(state, rows, stats(rows), review, packet, decisions, domains, domain_review)


def run(args):
    for name in ("drafts", "candidates"):
        for path in getattr(args, name, ()):
            cp.active_path(path)
    for name in ("job", "output", "packet", "decisions", "output_dir", "dispositions",
                 "pending_alerts", "model_dir", "cache_dir"):
        if getattr(args, name, None) is not None:
            cp.active_path(getattr(args, name))
    if args.command == "generate":
        job = read_json(args.job)
        rows = generate(args.model, job, *scenario_catalog())
        cp.write_file(args.output, jsonl_bytes(rows), overwrite=False)
        return f"Generated {len(rows)} candidates"
    if args.command == "review":
        cp.write_file(args.output, json_bytes(blind_review(args.model, read_json(args.packet))))
        return f"Saved review: {args.output}"

    state, prior = cp.load_progress()
    pilot = cp.load_pilot()
    if args.command == "plan":
        plan = dict(state["length_plan"], next_checkpoint_domain_counts=BATCH_TARGETS if not state["final"] and len(prior) < 100000 else {})
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
            domain_metrics = coverage(rows)
            domain_gap = {key: goal - domain_metrics["domain_counts"][key] for key, goal in BATCH_TARGETS.items()}
            if min(domain_gap.values()) < 0:
                raise ValueError(f"Drafts exceed a domain quota: {domain_gap}")
            plan.update(draft_records=len(rows), draft_label_lengths=actual, remaining_in_checkpoint=gap,
                        draft_domain_counts=domain_metrics["domain_counts"], remaining_domains=domain_gap)
        return json_bytes(plan).decode()
    if args.command == "verify":
        validate_rows([*pilot, *prior], *scenario_catalog())
        external = cp.load_external_imports(state)
        reviewed = {**stats(prior), **coverage(prior)}
        labels = reviewed["labels"].copy()
        for row in external:
            labels[row["סיווג"]] += 1
        return json_bytes({"pilot_quality": state["pilot_quality"], "pilot": stats(pilot),
                           "production": ({"records": state["production_records"], "labels": labels}
                                          if external else reviewed),
                           "reviewed_checkpoints": reviewed,
                           "external_records_without_content_review": len(external),
                           "next_id": state["next_id"],
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
            return cp.publish(args.remote, args.branch)
        head, _ = cp.preflight(args.remote, branch=args.branch)
        state, prior = cp.load_progress()
        if args.command == "checkpoint":
            files = validated_checkpoint(args, state, prior, pilot)
            message = f"Save validated dataset checkpoint {state['last_checkpoint']:04d}"
        else:
            files = final_artifacts(args, state, prior, pilot)
            message = "Assemble and validate the 100,000-record classification dataset"
        return cp.commit_state(files, state, message, args.remote, head, args.branch)


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
