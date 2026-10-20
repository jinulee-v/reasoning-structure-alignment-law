#!/usr/bin/env python3
"""Measure exact source-branch coverage of the goal-directed suites.

The sole metric is written source outcomes visited by any generated example /
all written source outcomes in the entered definitions. Outcomes are summed,
not multiplied into paths. Statement maps are neither generated nor replayed.

Writes, per port,

    .port/<port>_bobcat/reports/COVERAGE.md
    .port/<port>_bobcat/dataset/COVERAGE.json

Run `generate_dataset.py` first; this measures what that produced.

    python3 bobcat_scripts/measure_coverage.py
    python3 bobcat_scripts/measure_coverage.py sara_scope_Section68_Section68
    python3 bobcat_scripts/measure_coverage.py --per-target --uncovered
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bobcatlib import branches, paths, run, targets

_PROJECT_CACHE: dict = {}
_INVENTORY_CACHE: dict = {}


def load_rows(port: str, name: str) -> list:
    f = paths.dataset(port) / f"{name}.jsonl"
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text().splitlines() if line]


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "--"


# ---- one target -----------------------------------------------------------
def measure(target, want_inventory: bool) -> tuple:
    """Return the source inventory and exact native outcome trace."""
    native_manifest, native_hits = branches.native_trace(
        target.port, target.name)
    if not want_inventory:
        return [], native_manifest, native_hits

    project = _PROJECT_CACHE.get((target.port, target.project_dir))
    if project is None:
        project = run.prepare_project(target)
        _PROJECT_CACHE[(target.port, target.project_dir)] = project

    inv_key = (project, target.harness.name)
    inv = _INVENTORY_CACHE.get(inv_key)
    if inv is None:
        inv = branches.decisions(
            branches.inventory(project, target.harness.name))
        _INVENTORY_CACHE[inv_key] = inv

    return inv, native_manifest, native_hits


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Measure what the goal-directed suites execute, and how well.")
    ap.add_argument("targets", nargs="*", help="target names (default: all)")
    ap.add_argument("--all-entry-points", action="store_true",
                    help="deprecated compatibility flag; requirement-mapped "
                         "scopes are always the selected targets")
    ap.add_argument("--port", choices=paths.PORTS,
                    help="measure only targets belonging to this port")
    ap.add_argument("--per-target", action="store_true",
                    help="also report each target on its own, not only the "
                         "union per port")
    ap.add_argument("--uncovered", action="store_true",
                    help="list every outcome no row takes")
    args = ap.parse_args()

    paths.require_bobcat()
    ts = targets.by_name(args.targets, enumerated=args.all_entry_points)
    if args.port is not None:
        ts = [t for t in ts if t.port == args.port]
    if args.uncovered:
        branches.build_plugin()

    t0 = time.time()
    for port, port_targets in sorted(targets.by_port(ts).items()):
        measure_port(port, port_targets, args)
    print(f"\nmeasured in {time.time() - t0:.0f}s")
    return 0


def measure_port(port: str, ts: list, args) -> None:
    # The denominator is the port's decisions, so the numerator must be
    # restricted to those same files. Harness programs can be compiled with a
    # target and have coverage positions of their own, but they are scaffolding
    # rather than branches of the formalization. Requirement targets enter the
    # native source modules directly, so every top-level source file is known.
    known = {f.name for f in paths.source_files(paths.PORT_DIRS[port])}
    print(f"{port:10} exact native branch traces")

    per_target: dict = {}
    native_inventory: set[str] = set()
    native_reached: set[str] = set()
    for t in ts:
        rows = load_rows(port, t.name)
        inv, native_manifest, native_hits = measure(t, args.uncovered)
        if not native_manifest and not branches.has_native_manifest(
                t.port, t.name):
            print(f"{t.name}: no exact branch manifest; regenerate this "
                  "target with the current BOBCat")
            continue
        inv = [d for d in inv if d.file in known]
        native_manifest = branches.filter_native(native_manifest, set(known))
        native_hits = branches.filter_native(native_hits, set(known))
        inv = branches.restrict(
            inv, branches.native_positions(native_manifest))
        native_inventory.update(native_manifest)
        native_reached.update(native_hits)
        branch_cov = {p: True for p in branches.native_positions(native_hits)}

        # Outcome IDs are authoritative; positions are display metadata only.
        btot = branches.native_totals(native_manifest, native_hits)

        per_target[t.name] = {"rows": len(rows),
                              "decisions": inv, "reached": branch_cov,
                              "branch_totals": btot}

        print(f"{t.name:32} {len(rows):4d} rows   "
              f"branches {btot['outcomes_covered']:4d}/{btot['outcomes']:<4d} "
              f"({pct(btot['outcomes_covered'], btot['outcomes'])})")

    if not per_target:
        return

    branch_summary = branches.native_totals(native_inventory, native_reached)

    write_report(port, per_target, branch_summary, args)
    write_json(port, per_target, branch_summary)
    print(f"  {paths.rel(paths.reports(port))}/COVERAGE.md  "
          f"{paths.rel(paths.dataset(port))}/COVERAGE.json")


def write_report(port, per_target, branch_summary, args) -> None:
    reports_dir = paths.reports(port)
    reports_dir.mkdir(parents=True, exist_ok=True)
    L = [f"# {port} BOBCat branch coverage",
         "",
         "Exact source outcomes recorded during generation; no statement "
         "coverage maps or replay-derived proxies are included.", ""]

    L += branch_report(port, per_target, branch_summary, args.uncovered)

    if args.per_target:
        L += ["## Per target", ""]
        for name, d in per_target.items():
            b = d["branch_totals"]
            L += [f"### `{name}`", "",
                  f"{d['rows']} rows; branch outcomes "
                  f"{b['outcomes_covered']}/{b['outcomes']}.", ""]

    (reports_dir / "COVERAGE.md").write_text("\n".join(L))


def branch_report(port, per_target, branch_summary,
                  want_uncovered: bool) -> list:
    """Report the requested summed source-outcome coverage metric."""
    all_o = branch_summary["outcomes"]
    got = branch_summary["outcomes_covered"]

    L = ["## Branch coverage", "",
         "This is the sole branch metric: **written source outcomes visited "
         "by any generated example / all written source outcomes in the "
         "entered definitions**. Outcomes are summed, not multiplied into "
         "paths.", "",
         "BOBCat's native `(decision_id, outcome_id)` manifest and "
         "per-example traces are counted directly, so two "
         "branches on one line or sharing a source span remain distinct; "
         "source positions are display metadata only. Datasets without exact "
         "native traces must be regenerated and are not approximated with "
         "statement positions.", "",
         f"**{got}/{all_o} ({pct(got, all_o)}) branch outcomes covered.**",
         "", "### Per target", "",
         "| target | rows | outcomes taken |", "|---|--:|--:|"]
    for name, d in sorted(per_target.items()):
        tot = d["branch_totals"]
        L.append(f"| `{name}` | {d['rows']} | "
                 f"{tot['outcomes_covered']}/{tot['outcomes']} "
                 f"({pct(tot['outcomes_covered'], tot['outcomes'])}) |")
    L.append("")

    if want_uncovered:
        L += ["### Outcomes no row takes", "",
              "Grouped by the decision they belong to. A decision listed with "
              "all of its outcomes was never reached; one listed with some of "
              "them was reached and went only the other way.", ""]
        for name, d in sorted(per_target.items()):
            miss = branches.uncovered(d["decisions"], d["reached"])
            L += [f"**`{name}`** --- {len(miss)} of "
                  f"{sum(len(x.outcomes) for x in d['decisions'])} outcomes",
                  ""]
            partial = [(x, o) for x, o in miss if x.covered(d["reached"])]
            if partial:
                L += ["Reached, but only one way:", ""]
                for x, o in partial:
                    L.append(f"- `{o.pos.file}:{o.pos.start_line}` "
                             f"{x.kind} `{o.name}`")
                L.append("")
            groups = len({(x.kind, x.group) for x, _ in miss})
            pgroups = len({(x.kind, x.group) for x, _ in partial})
            L += [f"Never reached: {len(miss) - len(partial)} outcomes in "
                  f"{groups - pgroups} decisions.", ""]
    return L


def write_json(port, per_target, branch_summary) -> None:
    out = {
        "port": port,
        "branches": {
            "inventory": {
                "decisions": branch_summary["decisions"],
                "outcomes": branch_summary["outcomes"],
            },
            "covered": branch_summary,
        },
        "targets": {n: {"rows": d["rows"],
                        "branch_totals": d["branch_totals"]}
                    for n, d in per_target.items()},
    }
    (paths.dataset(port) / "COVERAGE.json").write_text(
        json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    sys.exit(main())
