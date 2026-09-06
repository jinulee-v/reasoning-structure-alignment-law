#!/usr/bin/env python3
"""Run the differential suite and report.

For every case in `.port/airline/test_cases/`, runs both programs --- the shared
Prolog oracle over the case's world, and the Catala port over the same world
--- compares the verdicts, and writes `.port/airline/reports/DISCREPANCIES.md`
and `report.json`.

The report is grouped, not enumerated: one defect in a shared rule shows up in
every world that reaches it, so a raw list would be mostly repetition.  Each
disagreement is first shrunk by delta debugging --- drop an item, drop a bag,
simplify the route, keep the drop if the two systems still disagree --- and
then grouped by what is left.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from airlinelib import airline, minimise, paths
from airlinelib.corpus import Trip


def case_dirs(only: str | None) -> list:
    root = paths.TEST_CASES
    if not root.exists():
        return []
    ds = sorted(d for d in root.iterdir() if d.is_dir())
    return [d for d in ds if only in d.name] if only else ds


def check_suite_is_current(sample: Path) -> None:
    """Refuse to run a suite that was generated against a different tree.

    A generated `prolog.pl` names the oracle by absolute path, so that a case
    is runnable on its own from any directory.  The cost is that moving or
    renaming the tree invalidates every case at once --- and the symptom is
    16,000 disagreements with no Prolog value, each one then delta-debugged,
    which is a slow and thoroughly misleading way to be told to regenerate.
    """
    text = (sample / "prolog.pl").read_text()
    if str(paths.AIRLINE_ORACLE) not in text:
        sys.exit(
            f"{paths.rel(sample)}/prolog.pl does not reference the current oracle\n"
            f"  ({paths.rel(paths.AIRLINE_ORACLE)}).  The suite was generated against a\n"
            f"  different tree, probably before a move or rename.  Regenerate it:\n"
            f"      python3 prolog_to_catala/airline/generate_test_cases.py")


def run_case(d: Path) -> dict:
    meta = json.loads((d / "meta.json").read_text())
    pl = airline.run_prolog(d / "prolog.pl")
    ct = airline.run_catala(d / "catala.catala_en")
    agree = (pl["total"] is not None
             and pl["total"] == ct["total"] and pl["accepted"] == ct["accepted"])
    return {"id": meta["id"], "method": meta.get("method"), "source": meta.get("source"),
            "expected": meta.get("expected"), "world": meta["world"], "agree": agree,
            "prolog": {"total": pl["total"], "accepted": pl["accepted"]},
            "catala": {"total": ct["total"], "accepted": ct["accepted"]},
            "dir": str(d), "prolog_err": pl["stderr"][:600], "catala_err": ct["stderr"][:600]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="substring of the case id")
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--no-minimise", action="store_true",
                    help="skip delta debugging; faster, noisier reports")
    args = ap.parse_args()

    ds = case_dirs(args.only)
    if args.limit:
        ds = ds[:args.limit]
    if not ds:
        sys.exit("no test cases; run generate_test_cases.py first")
    check_suite_is_current(ds[0])

    t0 = time.time()
    results = []
    with ThreadPoolExecutor(args.jobs) as ex:
        for i, r in enumerate(ex.map(run_case, ds), 1):
            results.append(r)
            if i % 500 == 0 or i == len(ds):
                rate = i / max(time.time() - t0, 1e-9)
                print(f"  {i}/{len(ds)}  {sum(1 for x in results if not x['agree'])} "
                      f"disagreeing  ({rate:.0f}/s, "
                      f"{(len(ds)-i)/max(rate,1e-9):.0f}s left)", flush=True)
    elapsed = time.time() - t0

    bad = [r for r in results if not r["agree"]]
    seeds = [r for r in results if r["method"] == "seed"]
    seed_ok = sum(1 for r in seeds if r["agree"] and r["prolog"]["total"] == r["expected"])
    print(f"{len(results)-len(bad)}/{len(results)} agree   ({elapsed:.0f}s)")
    hard = [r for r in seeds if r["world"].get("hard")]
    hard_ok = sum(1 for r in hard if r["agree"] and r["prolog"]["total"] == r["expected"])
    print(f"  of which the {len(seeds)} seed cases: {seed_ok} agree *and* match "
          f"the reference program's own answer")
    print(f"  DeonticBench's `hard` subset: {hard_ok}/{len(hard)}")

    if bad and not args.no_minimise:
        print(f"  minimising {len(bad)} disagreement(s)...")
        for r in bad:
            r["minimal"] = minimise.shrink(Trip.from_json(r["world"]))

    # A filtered run is a spot check, not the suite, and must not overwrite the
    # report that says what the suite did.
    partial = bool(args.only or args.limit)
    suffix = ".partial" if partial else ""
    paths.REPORTS.mkdir(parents=True, exist_ok=True)
    (paths.REPORTS / f"report{suffix}.json").write_text(json.dumps(
        {"total": len(results), "agree": len(results) - len(bad),
         "seed_cases": len(seeds), "seed_agree_and_correct": seed_ok,
         "hard_cases": len(hard), "hard_agree_and_correct": hard_ok,
         "seconds": round(elapsed, 1), "disagreements": bad}, indent=1))
    write_discrepancies(results, bad, suffix)
    print(f"  -> {paths.rel(paths.REPORTS)}/report{suffix}.json"
          + ("   (filtered run; the full report is untouched)" if partial else ""))
    sys.exit(1 if bad else 0)


def write_discrepancies(results: list, bad: list, suffix: str = "") -> None:
    lines = ["# Discrepancies", "",
             f"{len(results) - len(bad)} of {len(results)} cases agree "
             f"(shared Prolog oracle vs. the Catala port).", ""]
    if not bad:
        lines += ["No disagreement in this run.", ""]
    else:
        groups = defaultdict(list)
        for r in bad:
            m = r.get("minimal", r["world"])
            key = (r["prolog"]["total"] == r["catala"]["total"],
                   r["prolog"]["accepted"] == r["catala"]["accepted"],
                   m["cabin"], len(m["items"]))
            groups[key].append(r)
        lines += [f"{len(groups)} distinct cause(s).", ""]
        for key, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            r = rs[0]
            m = r.get("minimal", r["world"])
            lines += [f"## {m['cabin']}, {m['origin']} -> {m['destination']}, "
                      f"{len(m['items'])} item(s) --- {len(rs)} case(s)", "",
                      f"Worked example `{r['id']}` (method `{r['method']}`), minimised.", "",
                      "| | total | accepted |", "|---|--:|---|",
                      f"| Prolog | {r['prolog']['total']} | {r['prolog']['accepted']} |",
                      f"| Catala | {r['catala']['total']} | {r['catala']['accepted']} |", "",
                      "The minimal world:", "", "```json", json.dumps(m, indent=1), "```", ""]
            if r["catala_err"].strip():
                lines += ["Catala stderr:", "```", r["catala_err"], "```", ""]
            if r["prolog_err"].strip():
                lines += ["Prolog stderr:", "```", r["prolog_err"], "```", ""]
    (paths.REPORTS / f"DISCREPANCIES{suffix}.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
