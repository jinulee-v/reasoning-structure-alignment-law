#!/usr/bin/env python3
"""Build the DeonticBench -> Catala differential suite.

Writes `.port/airline/test_cases/<id>/`, three files per case:

    prolog.pl           the world as facts + the query, runnable on its own
    catala.catala_en    the same world, as a standalone Catala program
    meta.json           the world, where it came from, and its path signature

A world is kept when it drives the shared oracle down a path no kept world has
taken.  See prolog_to_catala/airline/README.md.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from airlinelib import airline, corpus, coverage, generate, paths


def build_airline(args, report: dict) -> None:
    t0 = time.time()
    paths.build_catala_modules()
    clauses = coverage.build()
    points = set(coverage.enumerate_points())
    print(f"  instrumented oracle: {clauses} clauses, {len(points)} branch points")

    seen: set = set()
    cov: set = set()
    kept: list = []
    batches = [("seed", generate.seed_worlds(corpus.load_airline()))]
    if not args.quick:
        batches.append(("exhaustive", generate.exhaustive_worlds()))
        batches.append(("boundary", generate.boundary_worlds()))
        # The two sections no case can state and no reference program
        # formalizes, so generate exhaustively over their own vocabulary.
        # DEVIATIONS C1.
        batches.append(("complimentary", generate.complimentary_worlds()))
        batches.append(("carryon", generate.carry_on_worlds()))
    mismatches: list = []
    for name, worlds in batches:
        k, mm = generate.select(worlds, seen, name[:3])
        mismatches += mm
        cov |= generate.LAST_COVERAGE
        kept += k
        print(f"  {name:11s} {len(k):6d} kept of {len(worlds):6d}"
              f"   coverage {len(cov & points):3d}/{len(points)}"
              f" = {100*len(cov & points)/len(points):.1f}%")

    if args.mutants:
        import random
        rng = random.Random(args.seed)
        cities = list(generate.COUNTRY_REPS)
        pool = list(kept)
        for rnd in range(args.mutation_rounds):
            batch = []
            for i in range(args.mutants):
                t = generate.mutate(rng.choice(pool), rng, cities)
                t.id = f"m{rnd}_{i:06d}"
                batch.append(t)
            k, _ = generate.select(batch, seen, f"mut{rnd}")
            cov |= generate.LAST_COVERAGE
            kept += k
            pool += k
            print(f"  mutation r{rnd}  {len(k):6d} kept of {len(batch):6d}"
                  f"   coverage {len(cov & points):3d}/{len(points)}"
                  f" = {100*len(cov & points)/len(points):.1f}%")

    # Step 1 of the two-step validation: the shared oracle against every
    # reference program, on that program's own world.  Step 2, the Catala port
    # against the oracle, is `run_test_cases.py`.
    if mismatches:
        print(f"  !! the oracle disagrees with {len(mismatches)} reference program(s); "
              f"step 1 has regressed and nothing below is meaningful:")
        for m in mismatches[:10]:
            print(f"       {m['id']}: reference {m['reference']}, oracle {m['oracle']}")
    else:
        print(f"  oracle vs. all {len(batches[0][1])} reference programs: agree")

    # Removing the previous suite in place costs minutes on a network filesystem
    # (16,000 directories), all before any new case exists.  Rename instead, and
    # unlink the old tree once the new one is written.
    out = paths.TEST_CASES
    stale = None
    if out.exists():
        stale = out.with_name(f"{out.name}.stale-{os.getpid()}")
        out.rename(stale)
    out.mkdir(parents=True)
    for i, t in enumerate(kept):
        cid = t.id if t.method == "seed" else f"{t.method[:3]}_{i:06d}"
        d = out / cid
        d.mkdir()
        (d / "prolog.pl").write_text(airline.render_prolog(t))
        (d / "catala.catala_en").write_text(airline.render_catala(t))
        (d / "meta.json").write_text(json.dumps(
            {"id": cid, "source": t.id, "method": t.method,
             "expected": t.label, "world": t.to_json()}, indent=1))
    (out / "INDEX.json").write_text(json.dumps(
        {"cases": len(kept), "points": len(points), "covered": len(cov & points)}, indent=1))
    if stale is not None:
        # Nothing downstream needs the old tree gone, so detach the unlink and
        # let `run_test_cases.py` start immediately.
        subprocess.Popen(["rm", "-rf", str(stale)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  previous suite being removed in the background ({stale.name})")
    report["airline"] = {"cases": len(kept), "points": len(points),
                         "covered": len(cov & points), "seconds": round(time.time() - t0, 1),
                         "reference_programs": len(batches[0][1]),
                         "oracle_vs_reference_mismatches": mismatches,
                         "unreached": sorted(points - cov)}
    print(f"  {len(kept)} airline cases written in {time.time()-t0:.0f}s")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quick", action="store_true", help="seeds only, ~1 min")
    ap.add_argument("--mutants", type=int, default=4000, help="mutants per round")
    ap.add_argument("--mutation-rounds", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    paths.BUILD.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    build_airline(args, report)
    paths.REPORTS.mkdir(parents=True, exist_ok=True)
    (paths.REPORTS / "generation.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
