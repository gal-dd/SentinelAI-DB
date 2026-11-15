"""Dataset contracts, normalized deduplication and distribution checks."""

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / "config/plan.json").read_text(encoding="utf-8"))
LABELS = tuple(PLAN["pilot"]["label_lengths"])
LENGTHS = tuple(PLAN["lengths"])
ORIGINS = tuple(PLAN["pilot"]["origins"])
CANDIDATE_FIELDS = {
    "text", "label", "length", "origin", "scenario_id", "source_group_id",
    "style", "rationale", "edge_case", "pair_id", "source_id", "primary_domain",
}
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,95}\Z")
HEBREW = re.compile(r"[א-ת]")
WORD = re.compile(r"[^\W_]+")
MARKER = re.compile(r"(?:^|\n)\s*(?:סיווג\s*[:=]|classification\s*[:=]|scenario_id\s*[:=])", re.I)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def jsonl_bytes(rows):
    return "".join(canonical(row) + "\n" for row in rows).encode("utf-8")


def normalize(text):
    chars = unicodedata.normalize("NFKC", text.casefold())
    stripped = "".join(char for char in chars if unicodedata.category(char) not in {"Mn", "Cf"})
    return " ".join(WORD.findall(stripped))


def word_count(text):
    return len(normalize(text).split())


def length_of(text):
    count = word_count(text)
    for kind, (lower, upper) in PLAN["lengths"].items():
        if lower <= count and (upper is None or count <= upper):
            return kind
    return None


def fingerprint(row):
    return digest(row)


def shape(text):
    stripped = re.sub(r'[״“"][^״“"\n]{1,25}[״”"]', " entity ", text)
    return re.sub(r"\d+", " number ", normalize(stripped))


def grams(text):
    padded = f" {text} "
    return {padded[i:i + 4] for i in range(max(1, len(padded) - 3))}


class SimilarityIndex:
    """Bounded rare-shingle candidate lookup and exact normalized text keys."""

    def __init__(self):
        self.exact = {}
        self.shapes = defaultdict(list)
        self.postings = defaultdict(list)
        self.entries = []

    def add(self, row, check=True):
        key = normalize(row["text"])
        if key in self.exact:
            previous = self.exact[key]
            qualifier = "conflicting labels" if previous["label"] != row["label"] else "same label"
            raise ValueError(f"Exact duplicate ({qualifier}): {fingerprint(previous)[:12]} / {fingerprint(row)[:12]}")
        self.exact[key] = row
        skeleton = shape(row["text"])
        features = grams(key)
        matches = []
        if check:
            votes = Counter()
            for feature in features:
                indices = self.postings.get(feature, ())
                if len(indices) <= 96:
                    votes.update(indices)
            candidates = set(sorted(votes, key=lambda i: (-votes[i], i))[:24])
            candidates.update(self.shapes.get(skeleton, ()))
            for candidate in sorted(candidates):
                other, other_key, other_shape = self.entries[candidate]
                other_features = grams(other_key)
                score = 2 * len(features & other_features) / (len(features) + len(other_features))
                if score >= 0.80 or skeleton == other_shape:
                    matches.append(alert(row, other, "structure" if skeleton == other_shape else "lexical", score))
        idx = len(self.entries)
        self.entries.append((row, key, skeleton))
        if len(self.shapes[skeleton]) < 8:
            self.shapes[skeleton].append(idx)
        for feature in features:
            if len(self.postings[feature]) <= 96:
                self.postings[feature].append(idx)
        return matches


def alert(row, other, method, score):
    keys = sorted((fingerprint(row), fingerprint(other)))
    intentional = bool(row["pair_id"] and row["pair_id"] == other["pair_id"]
                       and row["source_group_id"] == other["source_group_id"])
    return {
        "id": digest([method, *keys]),
        "records": keys,
        "method": method,
        "score": round(float(score), 5),
        "different_labels": row["label"] != other["label"],
        "intentional_pair": intentional,
    }


def validate_rows(rows, scenarios, sources, prior=()):
    index = SimilarityIndex()
    pair_members = defaultdict(list)
    for row in prior:
        index.add(row, check=False)
        if row["pair_id"]:
            pair_members[row["pair_id"]].append(row)
    alerts = []
    for i, row in enumerate(rows, 1):
        try:
            validate_row(row, scenarios, sources)
            alerts.extend(index.add(row))
            if row["pair_id"]:
                pair_members[row["pair_id"]].append(row)
        except ValueError as error:
            raise ValueError(f"Candidate {i}: {error}") from error
    for key, members in pair_members.items():
        signature = {(row["source_group_id"], row["scenario_id"]) for row in members}
        if len(members) != 2 or len(signature) != 1 or len({r["label"] for r in members}) != 2:
            raise ValueError(f"Invalid counterfactual pair {key}: expected two members of one scenario with distinct labels")
    return alerts


def validate_row(row, scenarios, sources):
    if not isinstance(row, dict) or not CANDIDATE_FIELDS <= row.keys() <= CANDIDATE_FIELDS | {"secondary_domains"}:
        raise ValueError("Unexpected candidate fields")
    from .domains import validate_domains

    validate_domains(row)
    for key in ("text", "label", "length", "origin", "scenario_id", "source_group_id", "style", "rationale"):
        if not isinstance(row[key], str) or not row[key].strip() or row[key].strip() != row[key]:
            raise ValueError(f"Expected a nonempty trimmed string for {key}")
    for key in ("scenario_id", "source_group_id", "style", "pair_id", "source_id"):
        if key in ("pair_id", "source_id") and row[key] is None:
            continue
        if not isinstance(row[key], str) or not SLUG.fullmatch(row[key]):
            raise ValueError(f"Invalid identifier {key}")
    if type(row["edge_case"]) is not bool:
        raise ValueError("edge_case must be a boolean")
    if row["label"] not in LABELS or row["origin"] not in ORIGINS:
        raise ValueError("Unrecognized label or origin")
    if row["length"] not in LENGTHS or row["length"] != length_of(row["text"]):
        raise ValueError(f"Length bucket mismatch ({word_count(row['text'])} words)")
    if not HEBREW.search(row["text"]) or MARKER.search(row["text"]):
        raise ValueError("Expected Hebrew text without an explicit classification marker")
    scenario = scenarios.get(row["scenario_id"])
    if scenario is None:
        raise ValueError("Unknown scenario")
    if row["source_group_id"] != scenario.get("source_group_id", row["scenario_id"]):
        raise ValueError("Incorrect source grouping")
    for key in (row["scenario_id"], row["source_group_id"], row["pair_id"]):
        if key and re.search(r"\b(?:scenario|תרחיש)[\s:=#-]+" + re.escape(key) + r"\b", row["text"], re.I):
            raise ValueError("Scenario identifier in training text")
    if row["origin"] == "public_adapted":
        source = sources.get(row["source_id"])
        if not source or not all(source.get(k) for k in ("title", "publisher", "url", "license", "terms_url")):
            raise ValueError("Public content requires a registered source and terms")
        if row["label"] != "נמוך":
            raise ValueError("Public adaptations contain only public facts")
        if row["source_id"] != scenario.get("source_id", row["scenario_id"]):
            raise ValueError("Public source differs from its registered scenario")
        if row["source_group_id"] != source.get("source_group_id", row["source_id"]):
            raise ValueError("Public adaptations of the same source must share its group")
    elif row["source_id"] is not None:
        raise ValueError("Only sourced public adaptations have source_id")


def stats(rows):
    matrix = {label: [0] * len(LENGTHS) for label in LABELS}
    for row in rows:
        matrix[row["label"]][LENGTHS.index(row["length"])] += 1
    return {
        "records": len(rows),
        "label_lengths": matrix,
        "labels": {label: sum(counts) for label, counts in matrix.items()},
        "lengths": dict(zip(LENGTHS, map(sum, zip(*matrix.values())))),
        "origins": dict(Counter(r["origin"] for r in rows)),
        "styles": dict(Counter(r["style"] for r in rows)),
        "scenario_count": len({r["scenario_id"] for r in rows}),
        "source_group_count": len({r["source_group_id"] for r in rows}),
        "edge_cases": sum(r["edge_case"] for r in rows),
        "counterfactual_pairs": len({r["pair_id"] for r in rows if r["pair_id"]}),
        "records_with_latin": sum(bool(re.search("[A-Za-z]", r["text"])) for r in rows),
    }


def check_quotas(rows, phase, final=False):
    actual = stats(rows)
    target = PLAN[phase]
    origins = target.get("origins", {})
    if "allowed_origins" in target and set(actual["origins"]) - set(target["allowed_origins"]):
        raise ValueError("Origin is not permitted for synthetic defense v2 production")
    exact = final or phase == "pilot"
    for label, cells in target["label_lengths"].items():
        for kind, count, limit in zip(LENGTHS, actual["label_lengths"][label], cells):
            if count > limit or (exact and count != limit):
                raise ValueError(f"Quota mismatch for {label}/{kind}: {count} vs {limit}")
    for origin, limit in origins.items():
        count = actual["origins"].get(origin, 0)
        if count > limit or (exact and count != limit):
            raise ValueError(f"Origin quota mismatch for {origin}: {count} vs {limit}")
    return actual


def scenario_catalog():
    return read_json(ROOT / "config/scenarios.json"), read_json(ROOT / "config/sources.json")


def export_rows(rows, start=1):
    return [
        {"ID": i, "אובייקט": row["text"], "סיווג": row["label"]}
        for i, row in enumerate(rows, start)
    ]


def metadata_rows(rows, start, reviews, alerts):
    scenarios, sources = scenario_catalog()
    by_row = defaultdict(list)
    for item in alerts:
        for key in item["records"]:
            by_row[key].append(item["id"])
    results = []
    for i, row in enumerate(rows, start):
        key = fingerprint(row)
        public = row["origin"] == "public_adapted"
        review = reviews.get(key)
        results.append({
            "ID": i,
            **{k: v for k, v in row.items() if k not in {"text", "label"}},
            "policy_version": PLAN["policy_version"],
            "prompt_version": PLAN["prompt_version"],
            "scenario_domain": scenarios[row["scenario_id"]]["domain"],
            "source": sources[row["source_id"]] if public else {"type": "original_fictional_content"},
            "processing": {
                "synthetic": "original_ai_authored",
                "fictional_document": "ai_authored_generic_document_conventions",
                "public_adapted": "ai_hebrew_factual_paraphrase",
            }[row["origin"]],
            "validation": {"schema": "passed", "exact_duplicate": False, "alert_ids": sorted(by_row[key])},
            "review": review if review else {"status": "not_sampled"},
        })
    return results


def load_saved(data_path, metadata_path, first_id):
    data = read_jsonl(data_path)
    meta = read_jsonl(metadata_path)
    if len(data) != len(meta):
        raise ValueError(f"Mismatched data and metadata sizes in {data_path}")
    rows = []
    for identifier, item, details in zip(range(first_id, first_id + len(data)), data, meta):
        if item.keys() != {"ID", "אובייקט", "סיווג"} or type(item["ID"]) is not int:
            raise ValueError(f"Unexpected training schema in {data_path}")
        if item["ID"] != identifier or details["ID"] != identifier:
            raise ValueError(f"Nonconsecutive ID in {data_path}")
        if details["policy_version"] != PLAN["policy_version"]:
            raise ValueError(f"Policy version mismatch in {metadata_path}")
        row = {key: details[key] for key in CANDIDATE_FIELDS - {"text", "label"}}
        if "secondary_domains" in details:
            row["secondary_domains"] = details["secondary_domains"]
        row.update(text=item["אובייקט"], label=item["סיווג"])
        rows.append(row)
    return rows
