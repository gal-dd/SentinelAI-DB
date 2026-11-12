"""Create deterministic, blind review packets and verify their decisions."""

from collections import Counter
from math import ceil
import random

from .core import LABELS, PLAN, digest, fingerprint, json_bytes, validate_rows
from .semantic import semantic_scan


def make_packet(rows, prior, scenarios, sources, model_dir, cache_dir, batch, previous_rate=0):
    alerts = validate_rows(rows, scenarios, sources, prior)
    semantic, metrics = semantic_scan(prior, rows, model_dir, cache_dir)
    alerts = sorted(alerts + semantic, key=lambda entry: entry["id"])
    by_key = {fingerprint(row): row for row in [*prior, *rows]}
    keys = [fingerprint(row) for row in rows]
    random_count = ceil(len(rows) * (0.20 if previous_rate > 0.05 else 0.10))
    rng = random.Random(PLAN["seed"] + batch)
    long_cells = {}
    for key, row in zip(keys, rows):
        if row["length"] in {"paragraph", "long"}:
            long_cells.setdefault((row["label"], row["length"]), []).append(key)
    picked = {rng.choice(cell) for cell in long_cells.values()}
    remaining_keys = [key for key in keys if key not in picked]
    picked.update(rng.sample(remaining_keys, max(0, random_count - len(picked))))
    targeted = {key for key, row in zip(keys, rows) if row["edge_case"] or row["pair_id"]}
    candidate_keys = set(keys)
    targeted.update(key for hit in alerts for key in hit["records"] if key in candidate_keys)
    pairs = {}
    for row in rows:
        if row["pair_id"]:
            pairs.setdefault(row["pair_id"], []).append(fingerprint(row))
    return {
        "candidate_digest": digest(keys),
        "random_sample": sorted(picked),
        "targeted_sample": sorted(targeted),
        "texts": {key: by_key[key]["text"] for key in sorted(picked | targeted)},
        "alerts": alerts,
        "alert_texts": {key: by_key[key]["text"] for hit in alerts for key in hit["records"]},
        "counterfactual_pairs": {key: {member: by_key[member]["text"] for member in members}
                                 for key, members in pairs.items()},
        "semantic": metrics,
    }


def verify_decisions(packet, decisions, rows):
    if decisions.get("candidate_digest") != packet["candidate_digest"]:
        raise ValueError("Review is for a different candidate batch")
    reviewer = decisions.get("reviewer", "")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise ValueError("Review requires a reviewer or model identifier")
    labels = {fingerprint(row): row["label"] for row in rows}
    judgments = decisions.get("records", {})
    if set(judgments) != set(packet["texts"]):
        raise ValueError("Review must cover the full random and targeted sample")
    disagreements = [key for key, judgment in judgments.items() if judgment.get("label") != labels[key]]
    rejected = [key for key, judgment in judgments.items() if judgment.get("status") != "pass"]
    for key, judgment in judgments.items():
        if judgment.get("label") not in (*LABELS, "reject") or not str(judgment.get("reason", "")).strip():
            raise ValueError(f"Missing review label or reason for {key}")
    dispositions = decisions.get("alerts", {})
    verify_pairs(dispositions, [item["id"] for item in packet["alerts"]], "similarity alerts")
    pair_dispositions = decisions.get("counterfactual_pairs", {})
    verify_pairs(pair_dispositions, packet["counterfactual_pairs"], "counterfactual pairs")
    if disagreements or rejected:
        raise ValueError(f"Review requires candidate fixes: {len(disagreements)} disagreements, "
                         f"{len(rejected)} rejected; candidate keys: {sorted(set(disagreements + rejected))}")
    attempts = decisions.get("previous_attempts", [])
    if not isinstance(attempts, list):
        raise ValueError("previous_attempts must be a list")
    for attempt in attempts:
        for field in ("reviewed", "disagreements", "rejected", "corrected"):
            if type(attempt.get(field)) is not int or attempt[field] < 0:
                raise ValueError(f"Invalid previous review metric: {field}")
        if attempt["disagreements"] > attempt["reviewed"] or attempt["rejected"] > attempt["reviewed"]:
            raise ValueError("Previous review metrics exceed the sample")
    total_reviewed = len(judgments) + sum(attempt["reviewed"] for attempt in attempts)
    total_disagreements = sum(attempt["disagreements"] for attempt in attempts)
    modes = Counter(judgment.get("mode", "unspecified") for judgment in judgments.values())
    return {
        "reviewer": reviewer,
        "review_modes": dict(modes),
        "random_sample_count": len(packet["random_sample"]),
        "targeted_sample_count": len(packet["targeted_sample"]),
        "reviewed": len(judgments),
        "disagreements": len(disagreements),
        "disagreement_rate": total_disagreements / total_reviewed,
        "rejected": len(rejected),
        "corrected": sum(attempt["corrected"] for attempt in attempts),
        "previous_attempts": attempts,
        "alert_dispositions": dispositions,
        "counterfactual_dispositions": pair_dispositions,
    }


def verify_pairs(dispositions, keys, description):
    if set(dispositions) != set(keys):
        raise ValueError(f"Review must cover all {description}")
    for key, judgment in dispositions.items():
        if judgment.get("status") != "keep" or not str(judgment.get("reason", "")).strip():
            raise ValueError(f"Unresolved {description}: {key}")


def write_packet(packet, path):
    path.write_bytes(json_bytes(packet))
