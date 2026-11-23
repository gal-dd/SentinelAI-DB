"""Quota-compatible intake planning (does not approve or publish records).

Select as many candidates as possible under the existing domain and
label/length quotas. Enforce one example in every domain/label pair when
feasible. Rejected candidates stay untouched in their source files.

Run from the repository root:
  python scripts/plan_intake.py drafts/.../candidates.jsonl --report report.json
"""
import argparse
from collections import Counter, deque
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sentinel_dataset.core import normalize, scenario_catalog, validate_row
from sentinel_dataset.production import validate_document_form


class Flow:
    def __init__(self, size):
        self.graph = [[] for _ in range(size)]

    def add(self, u, v, capacity):
        if capacity < 0:
            raise ValueError("Negative flow capacity")
        index = len(self.graph[u])
        self.graph[u].append([v, capacity, len(self.graph[v])])
        self.graph[v].append([u, 0, index])
        return (u, index)

    def max_flow(self, source, sink):
        total = 0
        while True:
            level = [-1] * len(self.graph)
            level[source] = 0
            queue = deque([source])
            while queue:
                u = queue.popleft()
                for v, capacity, _ in self.graph[u]:
                    if capacity and level[v] == -1:
                        level[v] = level[u] + 1
                        queue.append(v)
            if level[sink] == -1:
                break
            pos = [0] * len(self.graph)

            def send(u, amount):
                if u == sink:
                    return amount
                while pos[u] < len(self.graph[u]):
                    edge = self.graph[u][pos[u]]
                    v, capacity, reverse = edge
                    if capacity and level[v] == level[u] + 1:
                        moved = send(v, min(amount, capacity))
                        if moved:
                            edge[1] -= moved
                            self.graph[v][reverse][1] += moved
                            return moved
                    pos[u] += 1
                return 0

            while moved := send(source, 10**9):
                total += moved
        return total

    def disable_edge(self, position):
        u, i = position
        v, _, j = self.graph[u][i]
        self.graph[u][i][1] = 0
        self.graph[v][j][1] = 0


def _pick(rows, domains, cells, require_domain_labels):
    domain_keys = list(domains)
    cell_keys = list(cells)
    labels = list(dict.fromkeys(label for label, _ in cell_keys))
    pair_keys = [(domain, label) for domain in domain_keys for label in labels]
    n = len(rows)
    source = 0
    d0 = 1
    p0 = d0 + len(domain_keys)
    r0 = p0 + len(pair_keys)
    c0 = r0 + n
    sink = c0 + len(cell_keys)
    ss, tt = sink + 1, sink + 2
    flow = Flow(tt + 1)
    balance = [0] * (tt + 1)

    def bounded(u, v, lower, upper):
        position = flow.add(u, v, upper - lower)
        balance[u] -= lower
        balance[v] += lower
        return position

    for i, domain in enumerate(domain_keys):
        bounded(source, d0 + i, 0, domains[domain])
    pair_index = {key: i for i, key in enumerate(pair_keys)}
    for i, (domain, label) in enumerate(pair_keys):
        bound = 1 if require_domain_labels else 0
        bounded(d0 + domain_keys.index(domain), p0 + i, bound, domains[domain])
    for i, key in enumerate(cell_keys):
        bounded(c0 + i, sink, 0, cells[key])
    cell_index = {key: i for i, key in enumerate(cell_keys)}
    selected_edges = []
    for i, row in enumerate(rows):
        pair = row.get("primary_domain"), row.get("label")
        cell = row.get("label"), row.get("length")
        if pair not in pair_index or cell not in cell_index:
            continue
        bounded(p0 + pair_index[pair], r0 + i, 0, 1)
        position = bounded(r0 + i, c0 + cell_index[cell], 0, 1)
        selected_edges.append((i, position))

    # The sink->source edge transforms a bounded s/t flow into a circulation.
    cycle = flow.add(sink, source, sum(domains.values()))
    demand = 0
    for node, amount in enumerate(balance[:sink + 1]):
        if amount > 0:
            flow.add(ss, node, amount)
            demand += amount
        elif amount < 0:
            flow.add(node, tt, -amount)
    if flow.max_flow(ss, tt) != demand:
        return None
    for u in range(len(flow.graph)):
        for i in range(len(flow.graph[u])):
            if u in (ss, tt) or flow.graph[u][i][0] in (ss, tt):
                flow.graph[u][i][1] = 0
    flow.disable_edge(cycle)
    flow.max_flow(source, sink)
    return sorted(i for i, (u, j) in selected_edges if flow.graph[u][j][1] == 0)


def choose(rows, domains, cells):
    """Return selected indices and a factual structural-only report."""
    selected = _pick(rows, domains, cells, True)
    covered = selected is not None
    if not covered:
        selected = _pick(rows, domains, cells, False)
    if selected is None:
        raise ValueError("No feasible quota flow")
    chosen = [rows[i] for i in selected]
    domain_counts = Counter(row["primary_domain"] for row in chosen)
    cell_counts = Counter((row["label"], row["length"]) for row in chosen)
    pair_counts = Counter((row["primary_domain"], row["label"]) for row in chosen)
    labels = list(dict.fromkeys(label for label, _ in cells))
    report = {
        "candidate_count": len(rows),
        "selected_count": len(selected),
        "target_count": sum(domains.values()),
        "domain_label_coverage_feasible": covered,
        "missing_domains": {d: q - domain_counts[d] for d, q in domains.items()
                            if q > domain_counts[d]},
        "missing_label_lengths": {f"{label}/{length}": q - cell_counts[(label, length)]
                                  for (label, length), q in cells.items()
                                  if q > cell_counts[(label, length)]},
        "missing_domain_labels": [f"{d}/{label}" for d in domains for label in labels
                                  if not pair_counts[d, label]],
        "status": "structural_only_not_reviewed",
        "warning": "Selection is not a classification judgment or publication approval.",
    }
    return selected, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, help="Save a full structurally valid candidate checkpoint")
    parser.add_argument("--partial-out", type=Path, help="Save best partial selection as draft only")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    progress = json.loads((ROOT / "progress.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config/defense-domain-targets.json").read_text(encoding="utf-8"))
    lengths = progress["length_plan"]["next_checkpoint_label_lengths"]
    order = progress["length_plan"]["length_order"]
    cells = {(label, length): count for label, counts in lengths.items()
             for length, count in zip(order, counts)}
    size = sum(cells.values())
    domains = {item["id"]: item["target"] * size // config["total"]
               for item in config["domain_targets"]}
    if sum(domains.values()) != size:
        raise ValueError("Inconsistent domain checkpoint quotas")

    scenarios, sources = scenario_catalog()
    rows, seen = [], set()
    for path in args.candidates:
        with path.open(encoding="utf-8") as stream:
            for line_num, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                try:
                    validate_row(row, scenarios, sources)
                    validate_document_form(row)
                except (ValueError, TypeError, KeyError) as exc:
                    raise ValueError(f"{path}:{line_num}: {exc}") from exc
                key = normalize(row["text"])
                if key in seen:
                    raise ValueError(f"{path}:{line_num}: duplicate normalized text in intake pool")
                rows.append(row)
                seen.add(key)
    selected, report = choose(rows, domains, cells)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(output, end="")
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    if args.partial_out:
        args.partial_out.write_text(
            "".join(json.dumps(rows[i], ensure_ascii=False) + "\n" for i in selected),
            encoding="utf-8")
    if args.out:
        if len(selected) != size or report["missing_domain_labels"]:
            raise SystemExit("No complete quota-compatible batch; use --report or --partial-out")
        args.out.write_text(
            "".join(json.dumps(rows[i], ensure_ascii=False) + "\n" for i in selected),
            encoding="utf-8")


if __name__ == "__main__":
    main()
