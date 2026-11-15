"""Defense v2 domain quotas and contextual review requirements."""

from collections import Counter
import random

from .core import LABELS, PLAN, ROOT, fingerprint, read_json

CONFIG_PATH = "config/defense-domain-targets.json"
CONFIG = read_json(ROOT / CONFIG_PATH)
TARGETS = {item["id"]: item["target"] for item in CONFIG["domain_targets"]}
MISSILES = "missile_systems"
MISSILE_MINIMUM = next(item["minimum"] for item in CONFIG["domain_targets"] if item["id"] == MISSILES)
TOTAL = CONFIG["total"]
BATCH_TARGETS = {key: goal * PLAN["checkpoint_size"] // TOTAL for key, goal in TARGETS.items()}
if (sum(TARGETS.values()) != TOTAL or sum(BATCH_TARGETS.values()) != PLAN["checkpoint_size"]
        or any(goal * PLAN["checkpoint_size"] % TOTAL for goal in TARGETS.values())
        or TARGETS[MISSILES] < MISSILE_MINIMUM):
    raise ValueError("Inconsistent defense domain targets")


def validate_domains(row):
    primary = row["primary_domain"]
    secondary = row.get("secondary_domains", [])
    if not isinstance(primary, str) or primary not in TARGETS:
        raise ValueError("Unrecognized primary_domain")
    if (not isinstance(secondary, list)
            or any(not isinstance(value, str) or value not in TARGETS or value == primary
                   for value in secondary)
            or len(set(secondary)) != len(secondary)):
        raise ValueError("Invalid secondary_domains")


def coverage(rows):
    cells = {domain: dict.fromkeys(LABELS, 0) for domain in TARGETS}
    for row in rows:
        validate_domains(row)
        cells[row["primary_domain"]][row["label"]] += 1
    counts = {key: sum(labels.values()) for key, labels in cells.items()}
    return {
        "domain_counts": counts,
        "domain_label_counts": cells,
        "missile_domain_percentage": 100 * counts[MISSILES] / len(rows) if rows else 0,
    }


def require_coverage(rows, batches=1):
    metrics = coverage(rows)
    counts = metrics["domain_counts"]
    if counts[MISSILES] * TOTAL < len(rows) * MISSILE_MINIMUM:
        raise ValueError("Missile coverage is below the required minimum")
    expected = {key: value * batches for key, value in BATCH_TARGETS.items()}
    if counts != expected:
        raise ValueError(f"Domain quotas differ: {counts}; expected {expected}")
    if batches and any(not count for labels in metrics["domain_label_counts"].values()
                       for count in labels.values()):
        raise ValueError("Each domain must include all four sensitivity labels")
    return metrics


def review_sample(rows, batch):
    """Select one blind domain example from each domain/label cell."""
    cells = {}
    for row in rows:
        key = (row["primary_domain"], row["label"])
        cells.setdefault(key, []).append(fingerprint(row))
    rng = random.Random(PLAN["seed"] + batch)
    return sorted(rng.choice(sorted(cells[cell])) for cell in sorted(cells))


def verify_domain_review(rows, batch, judgments):
    if not isinstance(judgments, dict) or set(judgments) != set(review_sample(rows, batch)):
        raise ValueError("Domain review must cover all selected examples")
    expected = {fingerprint(row): row["primary_domain"] for row in rows}
    for key, judgment in judgments.items():
        if (not isinstance(judgment, dict) or judgment.get("primary_domain") != expected[key]
                or not isinstance(judgment.get("reason"), str) or not judgment["reason"].strip()):
            raise ValueError(f"Domain assignment requires correction or a contextual reason: {key}")
    counts = Counter(j["primary_domain"] for j in judgments.values())
    return {"status": "completed", "reviewed": len(judgments), "disagreements": 0,
            "sample_domain_counts": dict(counts), "records": judgments}
