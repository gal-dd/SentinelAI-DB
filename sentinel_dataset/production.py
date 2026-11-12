"""Plan checkpoint length and label quotas from the verified production counts."""

import re

from .core import LABELS, LENGTHS, PLAN, word_count

CORRECTION_HORIZON = 2_500
TARGET = PLAN["production"]["label_lengths"]
TARGET_TOTAL = sum(sum(lengths) for lengths in TARGET.values())
SEGMENT_END = re.compile(r"[.!?…](?=\s|$)|\n+")


def apportion(seats, weights):
    """Integer largest-remainder allocation with a stable order for ties."""
    if seats == 0:
        return [0] * len(weights)
    total = sum(weights)
    allocations, remainders = zip(*(divmod(seats * weight, total) for weight in weights))
    result = list(allocations)
    pending = seats - sum(result)
    order = sorted(range(len(weights)), key=lambda idx: -remainders[idx])
    for index in order[:pending]:
        result[index] += 1
    return result


def plan_lengths(accepted):
    count = sum(sum(cells) for cells in accepted.values())
    seats = min(PLAN["checkpoint_size"], TARGET_TOTAL - count)
    horizon = min(TARGET_TOTAL, max(CORRECTION_HORIZON, count + seats))

    def deficit(goal, actual):
        return max(0, goal * horizon - actual * TARGET_TOTAL)

    label_seats = apportion(seats, [deficit(sum(TARGET[label]), sum(accepted[label])) for label in LABELS])
    next_checkpoint = {}
    remaining = {}
    for label, size in zip(LABELS, label_seats):
        cells = accepted[label]
        quotas = TARGET[label]
        weights = [deficit(goal, actual) for goal, actual in zip(quotas, cells)]
        next_checkpoint[label] = apportion(size, weights)
        remaining[label] = [goal - actual for goal, actual in zip(quotas, cells)]
    return {
        "length_order": list(LENGTHS),
        "correction_horizon_records": horizon,
        "accepted_label_lengths": accepted,
        "remaining_label_lengths": remaining,
        "next_checkpoint_label_lengths": next_checkpoint,
    }


def add_counts(left, right):
    return {label: [a + b for a, b in zip(left[label], right[label])] for label in LABELS}


def validate_document_form(row):
    minimum = {"paragraph": 2, "long": 3}.get(row["length"], 0)
    if not minimum:
        return
    segments = sum(word_count(part) >= 4 for part in SEGMENT_END.split(row["text"]))
    if segments < minimum:
        raise ValueError(f"{row['length']} requires at least {minimum} substantial sentences or sections")
