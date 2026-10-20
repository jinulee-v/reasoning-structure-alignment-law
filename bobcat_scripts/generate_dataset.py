#!/usr/bin/env python3
"""Turn BOBCat's solved branch objectives into an input/output dataset.

Each benchmark supplies ``REQUIREMENT_OUTPUTS.json``. Its unique native scopes
are the targets; mappings that select different outputs of the same scope share
one whole-scope branch campaign.

Then, for every automatically discovered enterable target, this

  1. assembles a private clerk project under
     `.port/<port>_bobcat/build/<target>/` and primes it with a standard
     library built by *this* compiler,
  2. runs `catala bobcat -W`, which asks Z3 directly about each source branch
     outcome;
  3. decodes SAT models into Catala JSON inputs, concretely replays them, and
     stores both validated rows and SAT/UNSAT/UNKNOWN classifications.

Each port owns its output tree, so a run over one port writes nothing into the
other's.  Everything under `.port/` is regenerable; nothing else is written.

    python3 bobcat_scripts/generate_dataset.py                # all targets
    python3 bobcat_scripts/generate_dataset.py --list
    python3 bobcat_scripts/generate_dataset.py sara_scope_Section68_Section68
    python3 bobcat_scripts/generate_dataset.py --timeout 1800 --jobs 8

A completed objective remains valid if the process later times out. The
currently active objective is not recorded until it has a final solver status.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bobcatlib import dataset, parse, paths, run, targets


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate the goal-directed dataset from the Catala ports.")
    ap.add_argument("targets", nargs="*",
                    help="target names (default: all of them)")
    ap.add_argument("--list", action="store_true",
                    help="list the targets and what each one is for")
    ap.add_argument("--timeout", type=int, default=None,
                    help="override every target's timeout, in seconds "
                         f"(default: {run.DEFAULT_TARGET_TIMEOUT})")
    ap.add_argument("--bobcat-strategy", choices=("demand", "eager"), default="demand",
                    help="compilation strategy (default: demand)")
    ap.add_argument("--bobcat-objective-order", choices=("legacy", "depth"),
                    default="depth", help="objective ordering (default: depth)")
    ap.add_argument("--bobcat-positive-hundred-money-inputs",
                    action="store_true",
                    help="restrict symbolic money inputs to positive multiples "
                         "of 100")
    ap.add_argument("--bobcat-max-list-length", type=int, default=None,
                    metavar="LENGTH",
                    help="maximum symbolic list length (engine default: 5)")
    ap.add_argument("--bobcat-max-representation-capacity", type=int, default=64,
                    metavar="ELEMENTS",
                    help="maximum symbolic intermediate-list storage "
                         "(default: 64)")
    ap.add_argument("--solver-timeout-ms", type=int, default=None,
                    metavar="MILLISECONDS",
                    help="initial per-query Z3 timeout (engine default: 2000)")
    ap.add_argument("--solver-timeout-max-ms", type=int, default=None,
                    metavar="MILLISECONDS",
                    help="maximum progressive Z3 retry timeout "
                         "(engine default: 60000)")
    ap.add_argument("--objective-timeout-ms", type=int, default=None,
                    metavar="MILLISECONDS",
                    help="total wall-clock budget per objective (engine default: unlimited)")
    ap.add_argument("--bobcat-timings", action="store_true",
                    help="record compilation, solving, replay and refinement timings")
    ap.add_argument("--port", choices=paths.PORTS,
                    help="run only targets belonging to this port")
    ap.add_argument("--dedup", action="store_true",
                    help="drop rows whose inputs repeat an earlier row's")
    ap.add_argument("--all-entry-points", action="store_true",
                    help="deprecated compatibility flag; requirement-mapped "
                         "scopes are always the only selected targets")
    ap.add_argument("--rebuild", action="store_true",
                    help="rebuild each target's project directory from scratch")
    ap.add_argument("--jobs", type=int, default=1,
                    help="parallel goal-directed runs after serial project setup "
                         "(default: 1)")
    args = ap.parse_args()
    if args.timeout is not None and args.timeout <= 0:
        ap.error("--timeout must be positive")
    if (args.bobcat_max_list_length is not None
            and args.bobcat_max_list_length < 0):
        ap.error("--bobcat-max-list-length must be nonnegative")
    if args.bobcat_max_representation_capacity <= 0:
        ap.error("--bobcat-max-representation-capacity must be positive")
    if (args.bobcat_max_list_length is not None
            and args.bobcat_max_representation_capacity
                < max(1, args.bobcat_max_list_length)):
        ap.error("--bobcat-max-representation-capacity must be at least "
                 "--bobcat-max-list-length")
    if args.solver_timeout_ms is not None and args.solver_timeout_ms <= 0:
        ap.error("--solver-timeout-ms must be positive")
    if (args.solver_timeout_max_ms is not None
            and args.solver_timeout_max_ms <= 0):
        ap.error("--solver-timeout-max-ms must be positive")
    if args.objective_timeout_ms is not None and args.objective_timeout_ms <= 0:
        ap.error("--objective-timeout-ms must be positive")
    if (args.solver_timeout_ms is not None
            and args.solver_timeout_max_ms is not None
            and args.solver_timeout_max_ms < args.solver_timeout_ms):
        ap.error("--solver-timeout-max-ms must be at least --solver-timeout-ms")

    all_targets = targets.enumerated_targets()
    targets_by_port = targets.by_port(all_targets)
    for port in paths.PORTS:
        requirement_file = paths.requirement_outputs_file(port)
        requirement_targets = targets_by_port.get(port, [])
        reports_dir = paths.reports(port)
        reports_dir.mkdir(parents=True, exist_ok=True)
        lines = [f"# {port} BOBCat requirement targets", "",
                 f"Mapping: `{paths.rel(requirement_file)}`", "",
                 "Unique whole-scope branch targets:", ""]
        lines += [f"- `{t.harness.name}:{t.scope}` — {t.note}"
                  for t in requirement_targets]
        (reports_dir / "ENTRY_POINTS.md").write_text("\n".join(lines) + "\n")
        print(f"{port:24} {len(requirement_targets):3d} requirement scopes   "
              f"{paths.rel(reports_dir)}/ENTRY_POINTS.md")
    ts = targets.by_name(args.targets, enumerated=args.all_entry_points)
    if args.port is not None:
        ts = [t for t in ts if t.port == args.port]

    if args.list:
        for t in ts:
            where = f"{paths.rel(t.harness)} -s {t.scope}"
            print(f"{t.name}\n    {where}\n    {t.note}")
        return 0

    paths.require_bobcat()

    entries, schemas = [], {}
    t_start = time.time()
    prepared = []
    prepared_projects = {}
    for t in ts:
        t.timings = args.bobcat_timings
        t.strategy = args.bobcat_strategy
        t.objective_order = args.bobcat_objective_order
        t.positive_hundred_money_inputs = (
            args.bobcat_positive_hundred_money_inputs)
        t.representation_capacity = args.bobcat_max_representation_capacity
        if args.timeout is not None:
            t.timeout = args.timeout
        if args.bobcat_max_list_length is not None:
            t.max_list_length = args.bobcat_max_list_length
        if args.solver_timeout_ms is not None:
            t.solver_timeout_ms = args.solver_timeout_ms
        if args.solver_timeout_max_ms is not None:
            t.solver_timeout_max_ms = args.solver_timeout_max_ms
        if args.objective_timeout_ms is not None:
            t.objective_timeout_ms = args.objective_timeout_ms

        print(f"preparing {t.name}")
        try:
            project = prepared_projects.get(t.project_dir)
            if project is None:
                project = run.prepare_project(t, force=args.rebuild)
                prepared_projects[t.project_dir] = project
        except RuntimeError as e:
            print(f"  !! {e}")
            continue
        prepared.append((t, project))

    def execute(item):
        t, project = item
        return t, run.run_bobcat(t, project)

    if args.jobs > 1:
        pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, args.jobs))
        futures = [pool.submit(execute, item) for item in prepared]
        completed = (future.result() for future in
                     concurrent.futures.as_completed(futures))
    else:
        pool = None
        completed = map(execute, prepared)

    try:
        for t, result in completed:
            print(t.name)
            run_ = parse.parse_run(result.stdout, result.stderr)
            entry = dataset.write_target(t, run_, result, dedup=args.dedup)
            schemas[t.name] = dataset.schema_of(run_)
            entries.append(entry)

            flags = []
            if result.timed_out:
                flags.append("timed out")
            elif not run_.finished:
                flags.append(f"did not finish (rc={result.returncode})")
            if run_.incomplete:
                flags.append("incomplete")
            if run_.unparsed:
                flags.append(f"{len(run_.unparsed)} unparsed")
            print(f"  {entry['objectives']:6d} objectives "
                  f"({entry['objectives_sat']} SAT, "
                  f"{entry['objectives_unsat']} UNSAT, "
                  f"{entry['objectives_unknown']} UNKNOWN, "
                  f"{entry['objectives_spurious']} rejected by replay), "
                  f"{entry['paths']} validated examples, "
                  f"{entry['coverage_paths']} coverage maps, "
                  f"{entry['seconds']:.0f}s"
                  + ("   " + "; ".join(flags) if flags else ""))
            if not run_.paths and not result.timed_out:
                tail = ((result.stderr or result.stdout).strip()
                        .splitlines()[-6:])
                for line in tail:
                    print(f"     | {line}")
    finally:
        if pool is not None:
            pool.shutdown()

    # One index and one report per port: a run touching only one port must not
    # rewrite the other's index, whose rows are still on disk.
    print()
    valid_targets = targets.by_port(targets.enumerated_targets(refresh=False))
    for port in sorted(targets.by_port(ts)):
        index = dataset.write_index(
            port, [e for e in entries if e["port"] == port],
            valid_names={t.name for t in valid_targets.get(port, [])})
        dataset.write_report(port, index, schemas)
        print(f"{port}: {index['totals']['objectives']} objectives and "
              f"{index['totals']['paths']} validated rows over "
              f"{index['totals']['targets']} targets "
              f"({index['totals']['coverage_paths']} carry native coverage)")
        print(f"  {paths.rel(paths.dataset(port))}/  "
              f"{paths.rel(paths.reports(port))}/DATASET.md")
        if index["totals"]["unparsed"]:
            print(f"  !! {index['totals']['unparsed']} printed value(s) could "
                  f"not be read back; see INDEX.json")
    print(f"\nfinished in {time.time() - t_start:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
