#!/usr/bin/env python3
"""Turn CUTECat's concolic paths into a dataset of inputs and outputs.

Every run begins with the **census**: each port is scanned for its entry
points --- every `declaration scope` and every top-level `declaration f ...
depends on ...` --- they are split into the ones CUTECat can encode the inputs
of and the ones it cannot, and one wrapper scope is written per enterable
top-level function.  The wrappers are what make those functions targets at
all, so the census is not a separate step to remember: nothing else can turn
them into a dataset, and running it every time is what keeps
`ENTRY_POINTS.md` describing the wrappers actually on disk.  It costs a
sub-second scan of the two ports.

Then, for every target in `cutecatlib/targets.py`, this

  1. assembles a private clerk project under
     `.port/<port>_cutecat/build/<target>/` and primes it with a standard
     library built by *this* compiler,
  2. runs `catala concolic -W` on it, which walks the scope's paths under Z3
     and prints one input/output pair per path,
  3. reads that output back and writes
     `.port/<port>_cutecat/dataset/<target>.jsonl`, one JSON row per path,
     plus that port's `INDEX.json`, `DATASET.md` and `ENTRY_POINTS.md`.

Each port owns its output tree, so a run over one port writes nothing into the
other's.  Everything under `.port/` is regenerable; nothing else is written.

    python3 cutecat_scripts/generate_dataset.py                # all targets
    python3 cutecat_scripts/generate_dataset.py --list
    python3 cutecat_scripts/generate_dataset.py sara_section68 # just one
    python3 cutecat_scripts/generate_dataset.py --timeout 300 --jobs 8

A run that times out is not a failure: the engine enumerates until it runs out
of unexplored branches, which for a wide enumeration is a very long time, and
every path it printed before the clock ran out is a complete row.  The timeout
is recorded per target in `INDEX.json`.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cutecatlib import dataset, entrypoints, parse, paths, run, targets


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate the concolic dataset from the Catala ports.")
    ap.add_argument("targets", nargs="*",
                    help="target names (default: all of them)")
    ap.add_argument("--list", action="store_true",
                    help="list the targets and what each one is for")
    ap.add_argument("--timeout", type=int, default=None,
                    help="override every target's timeout, in seconds")
    ap.add_argument("--optim", action="append", default=None,
                    metavar="OPT",
                    help="pass --conc-optim=OPT to the engine (repeatable): "
                         "incremental, trivial, lazy-default, ...")
    ap.add_argument("--seed", type=int, default=None,
                    help="the engine's mutation seed")
    ap.add_argument("--dedup", action="store_true",
                    help="drop rows whose inputs repeat an earlier row's")
    ap.add_argument("--all-entry-points", action="store_true",
                    help="also run every other entry point CUTECat can enter: "
                         "the port's remaining scopes, and its top-level "
                         "functions behind generated wrapper scopes")
    ap.add_argument("--rebuild", action="store_true",
                    help="rebuild each target's project directory from scratch")
    ap.add_argument("--jobs", type=int, default=1,
                    help="parallel concolic runs after serial project setup "
                         "(default: 1)")
    args = ap.parse_args()

    for port, directory in paths.PORT_DIRS.items():
        c = entrypoints.census(port, directory, outdir=paths.generated(port))
        reports_dir = paths.reports(port)
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "ENTRY_POINTS.md").write_text("\n".join(c["lines"]) + "\n")
        print(f"{port:8} {c['enterable']:3d}/{c['total']:3d} enterable  "
              f"(scopes {c['scopes_enterable']}/{c['scopes']}, "
              f"functions {c['functions_enterable']}/{c['functions']})   "
              f"{paths.rel(reports_dir)}/ENTRY_POINTS.md")
        for path, sigs in sorted(c["written"].items()):
            print(f"   wrote {paths.rel(path)}  ({len(sigs)} scopes)")
    ts = targets.by_name(args.targets, enumerated=args.all_entry_points)

    if args.list:
        for t in ts:
            where = f"{paths.rel(t.harness)} -s {t.scope}"
            print(f"{t.name}\n    {where}\n    {t.note}")
        return 0

    paths.require_cutecat()

    entries, schemas = [], {}
    t_start = time.time()
    prepared = []
    prepared_projects = {}
    for t in ts:
        if args.timeout is not None:
            t.timeout = args.timeout
        if args.optim is not None:
            t.optims = args.optim
        if args.seed is not None:
            t.seed = args.seed

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
        return t, run.run_concolic(t, project)

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
            print(f"  {entry['paths']:6d} paths, "
                  f"{entry['distinct_outputs']} distinct outputs, "
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
    for port in sorted(targets.by_port(ts)):
        index = dataset.write_index(
            port, [e for e in entries if e["port"] == port])
        dataset.write_report(port, index, schemas)
        print(f"{port}: {index['totals']['paths']} rows over "
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
