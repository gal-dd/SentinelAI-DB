"""Fast, deterministic, non-publishing QA for v2 candidate drafts.

Run independently of Work: python -m sentinel_dataset.preflight draft.jsonl
  --reference another-draft.jsonl --output .poc-local/preflight-0006.json

All paths stay inside the checkout; archive/general-v1 is expressly excluded.
Warnings are review queues, not automatic rejection of semantically distinct rows.
"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re

from . import checkpoints as cp
from .core import PLAN, ROOT, normalize, read_json, read_jsonl, scenario_catalog, validate_row
from .domains import BATCH_TARGETS
from .production import TARGET_TOTAL, add_counts, plan_lengths, validate_document_form

MIN_PARAGRAPH_WORDS = 12
MIN_REPEATED_SENTENCE_WORDS = 10
HEBREW_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…׃])\s+|\n+")
MAX_REPEATED_ROW_SHARE = 0.20  # Gate for widespread reused substantive prose


def _digest(text):
    return sha256(normalize(text).encode("utf-8")).hexdigest()


def _blocks(text):
    """Exclude small shared fragments; retain substantive whole paragraphs."""
    return [normalize(block) for block in re.split(r"\n\s*\n", text)
            if len(normalize(block).split()) >= MIN_PARAGRAPH_WORDS]


def _sentences(text):
    return [normalize(sentence) for sentence in HEBREW_SENTENCE_BOUNDARY.split(text)
            if len(normalize(sentence).split()) >= MIN_REPEATED_SENTENCE_WORDS]


def _quota_from_state(state, batch=None):
    plan = state["length_plan"]
    next_batch = state["last_checkpoint"] + 1
    if batch is None or batch == next_batch:
        return plan["next_checkpoint_label_lengths"]
    if not next_batch < batch <= TARGET_TOTAL // PLAN["checkpoint_size"]:
        raise ValueError("Batch must be an upcoming checkpoint within the production target")
    for _ in range(next_batch, batch):
        accepted = add_counts(plan["accepted_label_lengths"], plan["next_checkpoint_label_lengths"])
        plan = plan_lengths(accepted)
    return plan["next_checkpoint_label_lengths"]


def analyze(rows, references=(), reference_names=(), expected_lengths=None, scenarios=None, sources=None):
    """Return a stable, finite QA report with 1-based candidate positions."""
    if scenarios is None or sources is None:
        scenarios, sources = scenario_catalog()
    references = tuple(references)
    reference_names = tuple(reference_names)
    if reference_names and len(reference_names) != len(references):
        raise ValueError("Expected one name per reference")
    if not reference_names:
        reference_names = tuple(f"reference-{i}" for i in range(1, len(references) + 1))
    errors = []
    warnings = []
    length_counts = defaultdict(Counter)
    domains = Counter()
    text_index = defaultdict(list)
    phrase_index = defaultdict(list)
    for pos, row in enumerate(rows, 1):
        if not isinstance(row, dict) or not isinstance(row.get("text"), str):
            errors.append({"row": pos, "code": "invalid_row"})
            continue
        text = row["text"]
        try:
            validate_row(row, scenarios, sources)
            validate_document_form(row)
        except (ValueError, KeyError, TypeError) as exc:
            errors.append({"row": pos, "code": "schema_or_document", "detail": str(exc)})
            continue
        length_counts[row.get("label", "?")][row.get("length", "?")] += 1
        domains[row.get("primary_domain", "?")] += 1
        key = normalize(text)
        text_index[key].append(pos)
        for kind, chunks in (("paragraph", _blocks(text)), ("sentence", _sentences(text))):
            for chunk in sorted(set(chunks)):
                phrase_index[(kind, chunk)].append(pos)
        if re.search(r"(?:רכזת|עורכת|מנהלת|מזכירת|אחראית)\s+[^.:\n]{0,35}\s+ציין(?:\s|$)", text):
            warnings.append({"row": pos, "code": "possible_gender_agreement"})
        if row.get("primary_domain") == "missile_systems" and not re.search(
                r"טיל|יירוט|מיירט|בליסט|הגנה אווירית", text):
            warnings.append({"row": pos, "code": "missile_semantic_check_required",
                             "detail": "Keyword-only warning; not a domain verdict"})
    for key, positions in text_index.items():
        if len(positions) > 1:
            errors.append({"code": "exact_duplicate_within", "rows": positions})
    for (kind, chunk), positions in phrase_index.items():
        if len(positions) > 1:
            warnings.append({"code": "repeated_" + kind, "rows": sorted(set(positions)),
                             "words": len(chunk.split()), "digest": _digest(chunk)})
    for domain, target in BATCH_TARGETS.items():
        actual = domains[domain]
        if actual != target:
            errors.append({"code": "domain_quota", "domain": domain,
                           "expected": target, "actual": actual})
    if len(rows) != PLAN["checkpoint_size"]:
        errors.append({"code": "batch_count", "expected": PLAN["checkpoint_size"], "actual": len(rows)})
    if expected_lengths:
        for label, quotas in expected_lengths.items():
            for kind, target in zip(PLAN["lengths"], quotas):
                actual = length_counts[label][kind]
                if actual != target:
                    errors.append({"code": "length_quota", "label": label, "length": kind,
                                   "expected": target, "actual": actual})

    # Compare to explicit ACTIVE v2 reference files. Never load archived files.
    prior_exact = defaultdict(list)
    prior_phrase = defaultdict(list)
    ref_count = 0
    for name, records in zip(reference_names, references):
        for pos, reference in enumerate(records, 1):
            text = reference.get("text", reference.get("אובייקט")) if isinstance(reference, dict) else None
            if not isinstance(text, str):
                errors.append({"code": "bad_reference_text", "file": name, "row": pos})
                continue
            ref_count += 1
            prior_exact[normalize(text)].append({"file": name, "row": pos})
            for kind, chunks in (("paragraph", _blocks(text)), ("sentence", _sentences(text))):
                for chunk in set(chunks):
                    prior_phrase[kind, chunk].append({"file": name, "row": pos})
    for key, positions in text_index.items():
        if key in prior_exact:
            for pos in positions:
                errors.append({"code": "exact_duplicate_reference", "row": pos,
                               "matches": prior_exact[key][:10], "match_count": len(prior_exact[key])})
    for (kind, chunk), positions in phrase_index.items():
        if (kind, chunk) in prior_phrase:
            warnings.append({"code": f"repeated_{kind}_reference",
                             "rows": sorted(set(positions)), "digest": _digest(chunk),
                             "matches": prior_phrase[kind, chunk][:10],
                             "match_count": len(prior_phrase[kind, chunk])})

    # Deterministic groups for editorial review. No claim of semantic deduplication.
    groups = [w for w in warnings if w["code"].startswith("repeated_")]
    affected = sorted({row for group in groups for row in group["rows"]})
    repeated_share = len(affected) / len(rows) if rows else 0.0
    if repeated_share > MAX_REPEATED_ROW_SHARE:
        errors.append({"code": "systemic_repeated_prose",
                       "affected_rows": len(affected),
                       "share": round(repeated_share, 4),
                       "max_share": MAX_REPEATED_ROW_SHARE})
    return {
        "schema_version": 1, "status": "blocked" if errors else "preflight_pass_with_review",
        "records": len(rows), "reference_records": ref_count,
        "domains": dict(sorted(domains.items())),
        "label_lengths": {label: dict(counts) for label, counts in sorted(length_counts.items())},
        "expected_label_lengths": expected_lengths,
        "errors": errors, "warnings": warnings,
        "summary": {"blocking_errors": len(errors), "review_warnings": len(warnings),
                    "repetition_groups": len(groups), "repetition_affected_rows": len(affected),
                    "repetition_affected_share": round(repeated_share, 4)},
        "requires": ["semantic embedding scan", "independent blind label/domain review",
                     "editorial review of repeated meaning and evidence",
                     "repository-native checkpoint validation before publication"],
        "publication_approved": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--reference", type=Path, action="append", default=[])
    parser.add_argument("--progress", type=Path, default=ROOT / "progress.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenarios", type=Path, help="Use a verified active v2 scenario catalogue.")
    quotas = parser.add_mutually_exclusive_group()
    quotas.add_argument("--batch", type=int,
                        help="Project length quotas from --progress for an upcoming batch.")
    quotas.add_argument("--skip-live-quotas", action="store_true",
                        help="For draft inspection only, not final intake.")
    args = parser.parse_args(argv)
    for path in [args.candidates, *args.reference, args.progress, args.output, args.scenarios]:
        if path is None:
            continue
        cp.active_path(path)
    rows = read_jsonl(args.candidates)
    reference_rows = [read_jsonl(path) for path in args.reference]
    state = None if args.skip_live_quotas else read_json(args.progress)
    try:
        expected = None if state is None else _quota_from_state(state, args.batch)
    except ValueError as exc:
        parser.error(str(exc))
    scenarios, sources = scenario_catalog()
    if args.scenarios is not None:
        scenarios = read_json(args.scenarios)
    report = analyze(rows, references=reference_rows,
                     reference_names=[str(p) for p in args.reference],
                     expected_lengths=expected, scenarios=scenarios, sources=sources)
    report["quota_basis"] = {
        "reference_checkpoint": None if state is None else state["last_checkpoint"],
        "batch": None if state is None else args.batch or state["last_checkpoint"] + 1,
        "mode": ("skipped" if state is None else "projected"
                 if args.batch and args.batch > state["last_checkpoint"] + 1 else "next_checkpoint"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(args.output), **report["summary"]}, ensure_ascii=False))
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
