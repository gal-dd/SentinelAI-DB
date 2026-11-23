"""Plan a quota-compatible production intake without approving content.

Read existing candidate JSONL files, select a maximum feasible subset using
bipartite flow, and report what the AI must generate next.
This is NOT a semantic review or a production checkpoint.
"""
import argparse
from collections import Counter, deque
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def choose(rows, domains, cells):
    domain_names, cell_names = list(domains), list(cells)
    n = len(rows)
    source, d0, r0, c0 = 0, 1, 1 + len(domains), 1 + len(domains) + n
    sink = c0 + len(cells)
    graph = [[] for _ in range(sink + 1)]

    def add(u, v, cap):
        graph[u].append([v, cap, len(graph[v])])
        graph[v].append([u, 0, len(graph[u]) - 1])
        return len(graph[u]) - 1

    for j, name in enumerate(domain_names):
        add(source, d0 + j, domains[name])
    for j, name in enumerate(cell_names):
        add(c0 + j, sink, cells[name])
    d_index = {key: i for i, key in enumerate(domain_names)}
    c_index = {key: i for i, key in enumerate(cell_names)}
    eligible = []
    for i, row in enumerate(rows):
        domain = row.get("primary_domain")
        cell = (row.get("label"), row.get("length"))
        if domain not in d_index or cell not in c_index:
            continue
        u = d0 + d_index[domain]
        eligible.append((i, u, add(u, r0 + i, 1)))
        add(r0 + i, c0 + c_index[cell], 1)

    total = 0
    while True:
        levels = [-1] * len(graph)
        levels[source] = 0
        queue = deque([source])
        while queue:
            u = queue.popleft()
            for v, cap, _ in graph[u]:
                if cap and levels[v] == -1:
                    levels[v] = levels[u] + 1
                    queue.append(v)
        if levels[sink] == -1:
            break
        positions = [0] * len(graph)

        def send(u, amount):
            if u == sink:
                return amount
            while positions[u] < len(graph[u]):
                e = graph[u][positions[u]]
                v, cap, reverse = e
                if cap and levels[v] == levels[u] + 1:
                    moved = send(v, min(amount, cap))
                    if moved:
                        e[1] -= moved
                        graph[v][reverse][1] += moved
                        return moved
                positions[u] += 1
            return 0

        while moved := send(source, 10**9):
            total += moved

    selected = sorted(i for i, u, e in eligible if graph[u][e][1] == 0)
    domain_counts = Counter(rows[i]["primary_domain"] for i in selected)
    cell_counts = Counter((rows[i]["label"], rows[i]["length"]) for i in selected)
    pair_counts = Counter((rows[i]["primary_domain"], rows[i]["label"]) for i in selected)
    report = {
        "candidate_count": len(rows),
        "selected_count": total,
        "target_count": sum(domains.values()),
        "missing_domains": {d: q - domain_counts[d] for d, q in domains.items() if q > domain_counts[d]},
        "missing_label_lengths": {f"{label}/{length}": q - cell_counts[(label, length)]
                                  for (label, length), q in cells.items() if q > cell_counts[(label, length)]},
        "missing_domain_labels": [f"{d}/{label}" for d in domains for label in
                                  sorted({key[0] for key in cells}) if not pair_counts[d, label]],
        "warning": "Structural selection only; still requires quality, blinded classification and domain review.",
    }
    return selected, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, help="Write selection only if all structural requirements are met")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    state = json.loads((ROOT / "progress.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config/defense-domain-targets.json").read_text(encoding="utf-8"))
    labels = state["length_plan"]["next_checkpoint_label_lengths"]
    order = state["length_plan"]["length_order"]
    cells = {(label, length): count for label, counts in labels.items()
             for length, count in zip(order, counts)}
    size = sum(cells.values())
    domains = {item["id"]: item["target"] * size // config["total"]
               for item in config["domain_targets"]}
    if sum(domains.values()) != size:
        raise ValueError("Invalid domain quotas")
    rows, seen = [], set()
    for path in args.candidates:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                key = json.dumps(row, ensure_ascii=False, sort_keys=True)
                if key not in seen:
                    rows.append(row)
                    seen.add(key)
    picked, report = choose(rows, domains, cells)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(output, end="")
    if args.report:
        args.report.write_text(output, encoding="utf-8")
    if args.out:
        if len(picked) != size or report["missing_domain_labels"]:
            raise SystemExit("Cannot produce a full quota-compatible intake yet; see report")
        args.out.write_text("".join(json.dumps(rows[i], ensure_ascii=False) + "\n" for i in picked),
                            encoding="utf-8")


if __name__ == "__main__":
    main()
