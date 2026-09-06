#!/usr/bin/env python3
"""How much of the Catala does each concolic suite execute, and how well?

Two measurements over one set of runs, because they cost the same runs:

  * **statement coverage** --- was an expression evaluated at all.  A rule
    counts as exercised when at least two of its positions were reached.
  * **branch coverage** --- did every decision come out every way it can.
    That is the criterion a suite has to meet before an execution path can be
    compared against a reasoning trace: a decision taken only one way puts
    nothing on the path for the other way.

Both are read out of the coverage recorded while CUTECat generated each row;
rows from an older dataset without a native companion are replayed through
`catala interpret --code-coverage`.  Neither is optional --- one run of the
compiler answers both questions, and reporting only the first would flatter
every suite.

Writes, per port,

    .port/<port>_cutecat/reports/COVERAGE.md
    .port/<port>_cutecat/dataset/COVERAGE.json

Run `generate_dataset.py` first; this measures what that produced.

    python3 cutecat_scripts/measure_coverage.py
    python3 cutecat_scripts/measure_coverage.py sara_section68
    python3 cutecat_scripts/measure_coverage.py --per-target --uncovered
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cutecatlib import branches, coverage, paths, run, targets

PORT_DIRS = list(paths.PORT_DIRS.values())
HARNESS_FILES = {f.name
                 for port in paths.PORTS
                 for d in (paths.harnesses(port), paths.generated(port))
                 for f in d.glob("*.catala_en")}
# One prepared project per port that holds every one of its sources, so the
# branch plugin can compile each file with `-W` and see the whole thing.
INVENTORY_PROJECT = {"sara": "sara_section68", "airline": "airline_carry_on"}
_PROJECT_CACHE: dict = {}
_INVENTORY_CACHE: dict = {}


def load_rows(port: str, name: str) -> list:
    f = paths.dataset(port) / f"{name}.jsonl"
    if not f.exists():
        return []
    return [json.loads(line) for line in f.read_text().splitlines() if line]


def port_rule_count(directory) -> tuple:
    """Every non-constant item of a whole port, counted from the source.

    The coverage map cannot supply this: a file the program never links holds
    no positions, so it contributes nothing to a ratio built from the map.
    Counting the items straight out of the source is the only way to say what
    share of the *port* --- rather than of the part of it that got linked ---
    the suite runs.
    """
    rules = consts = 0
    for f in sorted(directory.glob("*.catala_en")):
        for i in coverage.parse_items(f):
            if i.header.startswith(("declaration enumeration",
                                    "declaration structure")):
                continue
            if i.constant:
                consts += 1
            else:
                rules += 1
    return rules, consts


def port_files(directory) -> dict:
    """Every Catala file of one port, and its length in lines.

    Needed for the part of the answer the coverage map cannot give: a file no
    target enters at all drops out of the map entirely, so without this the
    denominator would quietly shrink to the sections the suites happen to
    reach.
    """
    return {f.name: (paths.rel(f), len(f.read_text().splitlines()))
            for f in sorted(directory.glob("*.catala_en"))}


def tally(items_by_file: dict) -> dict:
    """Per file: rules, rules exercised, statements, statements reached.

    Constants are held out of both sides of the rule ratio and reported on
    their own: the loader evaluates them for every input, so including them
    would credit the suite with reaching code no test could miss.
    """
    out = {}
    for f, items in items_by_file.items():
        live = [i for i in items if i.positions]
        rules = [i for i in live if not i.constant]
        consts = [i for i in live if i.constant]
        out[f] = {
            "rules": len(rules),
            "rules_exercised": sum(1 for i in rules if i.exercised),
            "constants": len(consts),
            "branches": sum(i.positions for i in rules),
            "branches_reached": sum(i.reached for i in rules),
            "constant_branches": sum(i.positions for i in consts),
            "executed": any(i.exercised for i in rules),
            "harness": f in HARNESS_FILES,
        }
    return out


def sum_rows(rows: list) -> dict:
    keys = ("rules", "rules_exercised", "constants", "branches",
            "branches_reached", "constant_branches")
    return {k: sum(r[k] for r in rows) for k in keys}


def branch_totals(files: dict) -> dict:
    keys = ("decisions", "decisions_full", "decisions_partial",
            "outcomes", "outcomes_covered")
    return {k: sum(getattr(f, k) for f in files.values()) for k in keys}


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "--"


# ---- the branch inventory -------------------------------------------------
def port_inventory(port: str) -> list:
    """Every decision in a port, from compiling each of its files with `-W`.

    One file is not enough: `-W` inlines what a file imports, so a single
    compilation sees only the part of the port reachable from that file. Every
    source is compiled and the outcomes unioned; `Outcome` is frozen and
    hashable, so overlaps between compilations collapse on their own.
    """
    project = paths.build(port) / INVENTORY_PROJECT[port]
    if not project.exists():
        raise RuntimeError(
            f"no prepared project at {paths.rel(project)}; "
            f"run generate_dataset.py first")
    sources = sorted(p.name for p in paths.PORT_DIRS[port].glob("*.catala_en"))
    seen, failed = set(), []
    for src in sources:
        if not (project / src).exists():
            failed.append((src, "not in the prepared project"))
            continue
        try:
            seen.update(branches.inventory(project, src))
        except RuntimeError as e:
            failed.append((src, str(e).splitlines()[-1][:120]))
    for src, why in failed:
        print(f"    !! {port}/{src}: {why}")
    return branches.decisions(list(seen))


# ---- one target -----------------------------------------------------------
def measure(target, rows: list, jobs: int = 16) -> tuple:
    """The coverage map of one target's rows, and the decisions it can reach.

    The dumps are gathered once and both measurements are read off the same
    union: a replay is a compiler process per row, and doing it twice to
    answer two questions about the same execution would double the cost of the
    report for nothing.
    """
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

    def replay(row):
        try:
            return coverage.replay_row(target, project, row), None
        except (RuntimeError, coverage.InputError) as e:
            return None, (row["path"], str(e).splitlines()[0])

    # Replays are independent compiler processes over read-only project files,
    # worth parallelising once bounded lists produce tens of thousands of paths;
    # the coverage union is order-independent.
    dumps, missing = coverage.native_dumps(target.port, target.name, rows)
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(replay, missing))
    dumps += [dump for dump, _ in results if dump is not None]
    failed = [failure for _, failure in results if failure is not None]
    return dumps, inv, failed


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Measure what the concolic suites execute, and how well.")
    ap.add_argument("targets", nargs="*", help="target names (default: all)")
    ap.add_argument("--all-entry-points", action="store_true",
                    help="include every generated entry-point target")
    ap.add_argument("--per-target", action="store_true",
                    help="also report each target on its own, not only the "
                         "union per port")
    ap.add_argument("--uncovered", action="store_true",
                    help="list every outcome no row takes")
    ap.add_argument("--jobs", type=int, default=16,
                    help="parallel row replays per target (default: 16)")
    args = ap.parse_args()

    paths.require_cutecat()
    ts = targets.by_name(args.targets, enumerated=args.all_entry_points)
    coverage.build_tool()
    branches.build_plugin()

    t0 = time.time()
    for port, port_targets in sorted(targets.by_port(ts).items()):
        measure_port(port, port_targets, args)
    print(f"\nmeasured in {time.time() - t0:.0f}s")
    return 0


def measure_port(port: str, ts: list, args) -> None:
    directory = paths.PORT_DIRS[port]
    inventory = port_inventory(port)
    print(f"{port:10} inventory: {len(inventory):5d} decisions, "
          f"{sum(len(d.outcomes) for d in inventory):5d} outcomes")

    per_target: dict = {}
    union_dumps: list = []
    union_covered: dict = {}
    union_decisions: dict = {}
    for t in ts:
        rows = load_rows(port, t.name)
        if not rows:
            print(f"{t.name}: no dataset rows; run generate_dataset.py first")
            continue
        dumps, inv, failed = measure(t, rows, jobs=max(1, args.jobs))
        cov = coverage.union_dumps(dumps) if dumps else {}

        files = tally(coverage.attribute(cov, PORT_DIRS))
        # Port files only: a harness is scaffolding this pipeline wrote, and
        # counting it would report the scaffolding's own 100% as coverage.
        executed = {f: d for f, d in files.items()
                    if d["executed"] and not d["harness"]}
        tot = sum_rows(list(executed.values())) if executed else sum_rows([])

        bfiles = branches.tally(inv, cov)
        btot = branch_totals(bfiles)

        per_target[t.name] = {"files": files, "executed_totals": tot,
                              "rows": len(rows), "failed": failed,
                              "decisions": inv, "reached": cov,
                              "branch_files": bfiles, "branch_totals": btot}
        union_dumps += dumps
        union_covered.update({k: v for k, v in cov.items() if v})
        for d in inv:
            union_decisions[(d.kind, d.group)] = d

        print(f"{t.name:32} {len(rows):4d} rows   "
              f"rules {tot.get('rules_exercised', 0):3d}/{tot.get('rules', 0):<3d} "
              f"statements {tot.get('branches_reached', 0):5d}/"
              f"{tot.get('branches', 0):<5d} "
              f"decisions {btot['decisions_full']:4d}/{btot['decisions']:<4d} "
              f"({pct(btot['decisions_full'], btot['decisions'])})")
        for path, why in failed:
            print(f"    !! path {path}: {why}")

    if not per_target:
        return

    files = tally(coverage.attribute(coverage.union_dumps(union_dumps),
                                     PORT_DIRS))
    port_summary = {
        "files": files,
        "executed": sum_rows([d for d in files.values() if d["executed"]]),
        "linked": sum_rows(list(files.values())),
    }
    reached_decisions = list(union_decisions.values())
    branch_summary = branch_totals(branches.tally(reached_decisions,
                                                  union_covered))

    known = port_files(directory)
    in_map = {f for f in files if f in known}
    executed_files = {f for f, d in files.items()
                      if d["executed"] and f in known}

    write_report(port, directory, per_target, port_summary, branch_summary,
                 inventory, known, in_map, executed_files, args)
    write_json(port, per_target, port_summary, branch_summary, inventory,
               known, in_map, executed_files)
    print(f"  {paths.rel(paths.reports(port))}/COVERAGE.md  "
          f"{paths.rel(paths.dataset(port))}/COVERAGE.json")


def _table(files: dict, only_executed: bool) -> list:
    L = ["| file | rules exercised | statements reached | constants |",
         "|---|--:|--:|--:|"]
    for name, d in sorted(files.items()):
        if only_executed and not d["executed"]:
            continue
        L.append(f"| `{name}` | {d['rules_exercised']}/{d['rules']} "
                 f"({coverage.pct(d['rules_exercised'], d['rules']):.0f}%) "
                 f"| {d['branches_reached']}/{d['branches']} "
                 f"({coverage.pct(d['branches_reached'], d['branches']):.0f}%) "
                 f"| {d['constants']} |")
    return L


def write_report(port, directory, per_target, summary, branch_summary,
                 inventory, known, in_map, executed_files, args) -> None:
    reports_dir = paths.reports(port)
    reports_dir.mkdir(parents=True, exist_ok=True)
    L = [f"# What the {port} concolic suite executes",
         "",
         "Coverage recorded while CUTECat generated each path, then unioned. "
         "Rows from older datasets without native coverage are replayed "
         "through `catala interpret --code-coverage`. Written by "
         "`cutecat_scripts/measure_coverage.py`, which reports statement "
         "coverage and branch coverage from that one union.",
         "",
         "A **rule** is one item of Catala source --- a top-level "
         "`declaration`, a `scope` header, or a `definition` / `rule` / "
         "`exception` inside a scope. A **statement** is one recorded "
         "expression position inside a rule. A **decision** is a point where "
         "control can go more than one way, and an **outcome** is one way it "
         "can go.",
         "",
         "A rule counts as **exercised** only when at least two of its "
         "positions were reached. The reason is an artifact worth stating: in "
         "whole-program mode the interpreter builds a closure for every "
         "top-level definition in every module it links, and that marks "
         "exactly one position --- the definition's own name. Counting those "
         "would report `SaraKinship` as partly covered by a suite that never "
         "calls it.",
         "",
         "**Constants** --- top-level declarations with no `depends on`, such "
         "as `Airline`'s ten country lists --- are held out of the ratio and "
         "counted in their own column. The loader evaluates them once for "
         "every input, so they are always fully covered and say nothing about "
         "what the suite reached.",
         "",
         "Statement coverage is not decision coverage, which is why both are "
         "here. `Section68`'s `suspended` --- the 2018--2025 suspension --- "
         "reports 8/8 statements reached, and yet no row in the suite has a "
         "taxable year in 2018--2025. Catala compiles `and`, `or` and the "
         "comparisons to Z3 *operators* rather than to branches, so both "
         "operands are always evaluated and CUTECat, which enumerates "
         "execution paths, has no branch there to negate.",
         ""]

    l = summary["linked"]
    port_files_ = {f: d for f, d in summary["files"].items()
                   if d["executed"] and not d["harness"]}
    harness_files = {f: d for f, d in summary["files"].items() if d["harness"]}
    e = sum_rows(list(port_files_.values()))
    L += ["## Statement coverage", ""]
    L.append(
        f"**Of the port files this suite runs in: rules exercised "
        f"{e['rules_exercised']}/{e['rules']} "
        f"({coverage.pct(e['rules_exercised'], e['rules']):.0f}%), "
        f"statements reached {e['branches_reached']}/{e['branches']} "
        f"({coverage.pct(e['branches_reached'], e['branches']):.0f}%).**")
    L.append("")
    L += _table(port_files_, only_executed=True)
    L.append("")
    if harness_files:
        L.append("The harnesses themselves, which are not the port and are "
                 "listed apart for that reason:")
        L.append("")
        L += _table(harness_files, only_executed=False)
        L.append("")
    bound = {f: d for f, d in summary["files"].items() if not d["executed"]}
    if bound:
        L.append(f"Linked and bound but never run --- "
                 f"{l['rules'] - e['rules']} further rules and "
                 f"{l['branches'] - e['branches']} further statements, none "
                 f"of them reached:")
        L += ["", "| file | rules | statements |", "|---|--:|--:|"]
        for f, d in sorted(bound.items()):
            L.append(f"| `{f}` | {d['rules']} | {d['branches']} |")
        L.append("")

    never = {n: v for n, v in known.items() if n not in in_map}
    L += ["### Not in the program at all", "",
          "These port files were never linked by any target, so they hold no "
          "positions on either side of a ratio. They are 0%.", "",
          "| file | lines |", "|---|--:|"]
    for name, (rel, lines) in sorted(never.items()):
        L.append(f"| `{rel}` | {lines} |")
    L += ["",
          f"Of the port's {len(known)} Catala files, "
          f"{len(executed_files)} are executed, "
          f"{len(in_map) - len(executed_files)} are linked but only bound, "
          f"and {len(never)} are never linked.",
          "",
          "### Against the whole port", "",
          "The ratios above are over the files the suite links. Counting the "
          "items straight out of the source instead gives the share of the "
          "port itself, which is the number to quote:", "",
          "| port | rules exercised | of the port's rules |", "|---|--:|--:|"]
    total, _consts = port_rule_count(directory)
    got = sum(d["rules_exercised"] for f, d in summary["files"].items()
              if not d["harness"])
    L += [f"| {port} | {got} | {total} ({coverage.pct(got, total):.0f}%) |",
          ""]

    L += branch_report(port, per_target, branch_summary, inventory,
                       args.uncovered)

    if args.per_target:
        L += ["## Per target", ""]
        for name, d in per_target.items():
            t, b = d["executed_totals"], d["branch_totals"]
            L += [f"### `{name}`", "",
                  f"{d['rows']} rows; rules "
                  f"{t.get('rules_exercised', 0)}/{t.get('rules', 0)}, "
                  f"statements {t.get('branches_reached', 0)}/"
                  f"{t.get('branches', 0)}, decisions taken every way "
                  f"{b['decisions_full']}/{b['decisions']}.", ""]
            L += _table({f: x for f, x in d["files"].items()
                         if not x["harness"]}, only_executed=True)
            L.append("")

    (reports_dir / "COVERAGE.md").write_text("\n".join(L))


def branch_report(port, per_target, branch_summary, inventory,
                  want_uncovered: bool) -> list:
    """The decision half: the inventory, then what the suite took of it."""
    by_kind: dict = {}
    for d in inventory:
        k = by_kind.setdefault(d.kind, [0, 0])
        k[0] += 1
        k[1] += len(d.outcomes)
    all_d = len(inventory)
    all_o = sum(len(d.outcomes) for d in inventory)

    L = ["## Branch coverage", "",
         "Every point in the port where control can go more than one way, "
         "found by walking the same dcalc program "
         "`catala interpret --code-coverage` measures. This is the "
         "denominator a suite is scored against.", "",
         "A **decision** is an `if`, a `match`, or a default group with at "
         "least two alternatives --- a `definition` together with one or more "
         "`exception`s. An unconditional `definition` compiles to a default "
         "group with a single alternative and is not counted: it has no "
         "choice in it, and counting it would inflate every ratio that "
         "follows. A decision is **full** when every one of its outcomes was "
         "taken, **partial** when some were and some were not, and **none** "
         "when it was never reached at all.", "",
         f"**The port holds {all_d} decisions and {all_o} outcomes.**", "",
         "| kind | decisions | outcomes |", "|---|--:|--:|"]
    for k in ("if", "match", "default"):
        if k in by_kind:
            L.append(f"| `{k}` | {by_kind[k][0]} | {by_kind[k][1]} |")
    L += ["", "| file | decisions | outcomes |", "|---|--:|--:|"]
    per_file: dict = {}
    for d in inventory:
        entry = per_file.setdefault(d.file, [0, 0])
        entry[0] += 1
        entry[1] += len(d.outcomes)
    for f, (nd, no) in sorted(per_file.items()):
        L.append(f"| `{f}` | {nd} | {no} |")

    L += ["", "### What the suite covers", "",
          "The denominator per target is every decision in the program that "
          "target compiles, which under `-W` is its own file plus everything "
          "it imports --- not the entered scope. A target enters one scope; "
          "the decisions of the other scopes in the same program are inlined "
          "and counted, and nothing calls them.", "",
          "| target | rows | full | partial | none | decisions | "
          "outcomes taken |",
          "|---|--:|--:|--:|--:|--:|--:|"]
    total_partial = 0
    for name, d in sorted(per_target.items()):
        tot = d["branch_totals"]
        none = (tot["decisions"] - tot["decisions_full"]
                - tot["decisions_partial"])
        total_partial += tot["decisions_partial"]
        L.append(f"| `{name}` | {d['rows']} | {tot['decisions_full']} | "
                 f"{tot['decisions_partial']} | {none} | {tot['decisions']} | "
                 f"{tot['outcomes_covered']}/{tot['outcomes']} "
                 f"({pct(tot['outcomes_covered'], tot['outcomes'])}) |")
    L.append("")
    if total_partial == 0:
        L += ["**No decision is partial.** Every decision any suite reached, "
              "it took every way it can go; the entire shortfall is decisions "
              "that were never reached. That is CUTECat's guarantee showing "
              "up as a measurement: within an entered scope it is not leaving "
              "branches behind, and the way to raise these numbers is to "
              "enter more of the program, not to generate more rows.", ""]
    else:
        L += [f"**{total_partial} decisions are partial** --- reached, but "
              "not taken every way. Those are the ones to look at first.", ""]

    L += ["Against the port's whole inventory:", "",
          "| port | decisions full | outcomes taken |", "|---|--:|--:|",
          f"| {port} | {branch_summary['decisions_full']}/{all_d} "
          f"({pct(branch_summary['decisions_full'], all_d)}) | "
          f"{branch_summary['outcomes_covered']}/{all_o} "
          f"({pct(branch_summary['outcomes_covered'], all_o)}) |", ""]

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


def write_json(port, per_target, summary, branch_summary, inventory, known,
               in_map, executed_files) -> None:
    out = {
        "port": port,
        "statements": summary,
        "branches": {
            "inventory": {
                "decisions": len(inventory),
                "outcomes": sum(len(d.outcomes) for d in inventory),
            },
            "covered": branch_summary,
        },
        "targets": {n: {"rows": d["rows"], "failed": d["failed"],
                        "executed_totals": d["executed_totals"],
                        "branch_totals": d["branch_totals"],
                        "files": d["files"]}
                    for n, d in per_target.items()},
        "files": {
            "executed": sorted(executed_files),
            "bound_only": sorted(in_map - executed_files),
            "never_linked": {n: {"path": rel, "lines": lines}
                             for n, (rel, lines) in sorted(known.items())
                             if n not in in_map},
        },
    }
    (paths.dataset(port) / "COVERAGE.json").write_text(
        json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    sys.exit(main())
