#!/usr/bin/env python3
"""Run every test case through both systems and report where they disagree.

Each directory under `.port/sara/test_cases/` holds the same world and the same
question written twice.  This runs both, compares the verdicts, and writes one
report.

The report is grouped, not enumerated.  A raw list of discrepancies is mostly
repetition: one defect in a shared helper shows up in every world that reaches
it, and reading two hundred near-identical entries is how a real finding gets
missed.  So each discrepancy is first *shrunk* --- facts are dropped one at a
time for as long as the two systems still disagree --- and then grouped by what
is left: the predicate asked, the direction of the disagreement, and the shape
of the minimal world.  One worked example is written out per group, in full:

    the input        the minimal world, as Prolog facts, and the query
    Prolog's reasoning   which clause of which section was entered, what it
                         tried, and which goal failed
    Catala's reasoning   which scope was entered, under which article, and
                         what it concluded

    python3 prolog_to_catala/sara/run_test_cases.py                 # everything
    python3 prolog_to_catala/sara/run_test_cases.py --only s7703    # one section
    python3 prolog_to_catala/sara/run_test_cases.py --no-minimise   # faster, noisier
    python3 prolog_to_catala/sara/run_test_cases.py --trace-all     # trace agreements too
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from saralib import catala, coverage, generate, prolog, traces    # noqa: E402
from saralib.paths import REPORTS, SCRATCH, TEST_CASES, rel        # noqa: E402


# --------------------------------------------------------------- one case

def load_case(d: Path) -> dict:
    meta = json.loads((d / "meta.json").read_text())
    meta["dir"] = d
    return meta


def as_world(meta: dict) -> dict:
    """The world model a `meta.json` describes, in the shape both renderers
    read --- so a shrunk variant can be re-rendered and re-run."""
    return {"id": meta["id"], "events": meta["events"],
            "other": meta.get("other", {}),
            "discontiguous": meta.get("discontiguous", []),
            "value_kinds": meta.get("value_kinds", {}),
            "question": "", "test": meta["test"]}


def run_one(meta: dict, trace: bool, ptimeout: int, ctimeout: int) -> dict:
    """Both verdicts for one test case, and both traces when asked."""
    d = meta["dir"]
    work = SCRATCH / f"run{os.getpid()}"
    work.mkdir(parents=True, exist_ok=True)
    cov = work / f"{meta['id']}.cov"
    ptrace = work / f"{meta['id']}.ptrace" if trace else None
    ctrace = work / f"{meta['id']}.ctrace" if trace else None

    pv, points, perr = prolog.run_program(
        d / "prolog.pl", cov=cov, trace=ptrace, timeout=ptimeout)
    cv, cerr = catala.run_program(
        d / "catala.catala_en", trace=ctrace, timeout=ctimeout)

    res = {"id": meta["id"], "query": meta.get("query"),
           "origin": meta.get("origin"), "goal": meta.get("goal"),
           "expected": meta.get("expected"),
           "prolog": pv, "catala": cv, "points": points,
           "prolog_error": perr.strip()[-1200:] if pv in ("error", "crash",
                                                          "timeout") else "",
           "catala_error": cerr.strip()[-1200:] if cv in ("error", "timeout")
           else ""}
    if trace:
        seq, cut = traces.read_points(ptrace)
        res["prolog_trace"] = traces.prolog_trace(seq)
        res["prolog_frontier"] = traces.prolog_failure_frontier(seq)
        res["prolog_trace_truncated"] = cut
        res["catala_trace"] = traces.catala_trace(ctrace)
    for p in (cov, ptrace, ctrace):
        if p is not None:
            p.unlink(missing_ok=True)
    return res


def status_of(res: dict) -> str:
    pv, cv = res["prolog"], res["catala"]
    if pv in ("true", "false") and cv in ("true", "false"):
        return "agree" if pv == cv else "disagree"
    if pv in ("error", "crash", "timeout"):
        return "prolog_" + pv
    return "catala_" + cv


# ------------------------------------------------------------- shrinking

class Oracle:
    """Do the two systems still disagree on this world?"""

    def __init__(self, sym, ptimeout: int, ctimeout: int) -> None:
        self.sym, self.ptimeout, self.ctimeout = sym, ptimeout, ctimeout
        self.calls = 0

    def verdicts(self, rec: dict, tag: str) -> tuple[str, str]:
        self.calls += 1
        rec = dict(rec, id=tag)
        pv, _ = prolog.run_world(rec, tag, coverage_on=False,
                                 timeout=self.ptimeout)
        if pv not in ("true", "false"):
            return pv, "-"
        cv, _ = catala.run_world(self.sym, rec, tag, timeout=self.ctimeout)
        return pv, cv

    def disagrees(self, rec: dict, tag: str) -> bool:
        pv, cv = self.verdicts(rec, tag)
        return pv in ("true", "false") and cv in ("true", "false") and pv != cv


def signature(rec: dict, pv: str, cv: str) -> str:
    """What makes two discrepancies the same finding: the predicate asked, the
    direction of the disagreement, and the shape of the minimal world."""
    return "|".join([
        rec["test"]["goals"][0]["predicate"],
        f"{pv}>{cv}",
        ",".join(sorted(rec["events"])),
        ",".join(sorted(rec.get("other", {}))),
    ])


# ---------------------------------------------------------------- report

def fence(text: str, lang: str = "") -> str:
    return f"```{lang}\n{text.rstrip()}\n```"


def elide(text: str, keep: int) -> str:
    """A long trace, cut in the middle.

    A `tax/3` derivation runs to thousands of steps and nobody reads the
    middle of one.  What is worth reading is the top --- what the query set out
    to prove --- and the bottom, where it was decided.  The whole trace is in
    `report.json` either way.
    """
    lines = text.splitlines()
    if len(lines) <= keep:
        return text
    head, tail = keep // 2, keep - keep // 2
    return "\n".join(lines[:head]
                      + [f"", f"... {len(lines) - keep} steps elided; "
                         f"the full trace is in report.json ...", ""]
                      + lines[-tail:])


def render_report(index: dict, results: list, groups: list, audit: dict,
                  out: Path, trace_lines: int = 160) -> None:
    n = len(results)
    by_status = collections.Counter(status_of(r) for r in results)
    lines = [
        "# SARA's Prolog against the Catala port",
        "",
        f"{n} test cases, run {index['run']}.  Each is one world and one "
        "query, put to both systems.",
        "",
        "| outcome | cases |",
        "|---|--:|",
    ]
    for k, v in by_status.most_common():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        f"Branch coverage of SARA's statutes by this suite: "
        f"**{audit['covered']}/{audit['total']} = {audit['pct_all']:.1f}%** "
        "of all goal positions. Of the "
        f"{audit['total'] - audit['covered']} not reached, "
        f"{len(audit['untaken'])} are reachable — the goal they guard has been "
        f"seen failing somewhere else — and {len(audit['unproven'])} are `f` "
        "markers on deterministic builtins that no run has ever seen fail. "
        "Excluding only the latter gives "
        f"**{audit['pct_reachable']:.1f}%**, an upper bound rather than a "
        "second measurement: nothing here is known to be unreachable.",
        "",
    ]

    if not groups:
        lines += ["## No discrepancies", "",
                  "Every case on which both systems returned a verdict "
                  "returned the same one.", ""]
    else:
        lines += [
            f"## {len(groups)} distinct discrepancies",
            "",
            "Grouped by cause: the query predicate, the direction, and the "
            "shape of the world left after shrinking.  One worked example "
            "per group.",
            "",
            "| # | query | Prolog | Catala | cases | facts | example |",
            "|--:|---|---|---|--:|--:|---|",
        ]
        for i, g in enumerate(groups, 1):
            lines.append(
                f"| {i} | `{g['predicate']}` | {g['prolog']} | {g['catala']} "
                f"| {len(g['members'])} | {g['facts_before']}→{g['facts']} "
                f"| `{g['example']}` |")
        lines.append("")

        for i, g in enumerate(groups, 1):
            shrunk = g["facts"] != g["facts_before"]
            lines += [
                f"### {i}. `{g['predicate']}` --- Prolog says "
                f"**{g['prolog']}**, Catala says **{g['catala']}**",
                "",
                f"{len(g['members'])} test case(s).  Worked example: "
                f"`.port/sara/test_cases/{g['example']}/`"
                + (f", shrunk from {g['facts_before']} facts to "
                   f"{g['facts']} --- the world below is the shrunk one, the "
                   "directory holds the original."
                   if shrunk else "."),
                "",
                "```",
                f"cd .port/sara/test_cases/{g['example']}",
                "swipl -q -f prolog.pl -g main -t halt",
                "catala interpret catala.catala_en -s Run -I ../../../../data/catala_gold/sara \\",
                "    --stdlib ../../../../data/catala_gold/sara/_build/libcatala "
                "--bin ../../../../data/catala_gold/sara/_build",
                "```",
                "",
                "**The input**", "",
                fence((g["world"] or "% no facts at all: the empty world")
                      + "\n\n?- " + g["goal"] + ".", "prolog"),
                "",
                "**Prolog's reasoning**", "",
                fence(elide(g["prolog_trace"], trace_lines)),
                "",
            ]
            if g.get("frontier"):
                lines += ["Goals that failed, deepest first:", ""]
                for f in g["frontier"][:8]:
                    lines.append(f"- `{f['goal']}` — {f['file']}:{f['line']} "
                                 f"in `{f['predicate']}`")
                lines.append("")
            lines += [
                "**Catala's reasoning**", "",
                fence(elide(g["catala_trace"], trace_lines)),
                "",
            ]
            if len(g["members"]) > 1:
                lines += ["<details><summary>the other "
                          f"{len(g['members']) - 1} case(s)</summary>", "",
                          ", ".join(f"`{m}`" for m in g["members"][1:]), "",
                          "</details>", ""]

    errs = [r for r in results if status_of(r).startswith(("prolog_",
                                                           "catala_"))]
    if errs:
        lines += [f"## {len(errs)} cases returned no verdict", "",
                  "| case | Prolog | Catala | detail |", "|---|---|---|---|"]
        for r in errs[:60]:
            detail = (r["prolog_error"] or r["catala_error"] or "").split("\n")
            detail = " ".join(detail)[:140].replace("|", "\\|")
            lines.append(f"| `{r['id']}` | {r['prolog']} | {r['catala']} "
                         f"| {detail} |")
        if len(errs) > 60:
            lines.append(f"| ... | | | {len(errs) - 60} more |")
        lines.append("")

    untaken = audit["untaken"]
    if untaken:
        by_goal = collections.Counter(
            coverage.functor_of(u["goal"]) for u in untaken)
        lines += [
            f"## {len(untaken)} branch points the suite never took", "",
            "These are reachable — the goal they guard has been observed "
            f"failing elsewhere. A further {len(audit['unproven'])} points are "
            "`f` markers on deterministic builtins that no run has ever seen "
            "fail, which *probably* have no failing execution; probably is not "
            "certainly, and "
            + (f"`{'`, `'.join(audit['observed_failable'])}` "
               "turned out to fail after all once the output argument was "
               "bound. " if audit.get("observed_failable") else "")
            + "By goal:", "",
            "| goal | points |", "|---|--:|",
        ]
        for name, count in by_goal.most_common(20):
            lines.append(f"| `{name}` | {count} |")
        lines.append("")

    out.write_text("\n".join(lines))


# ------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default=str(TEST_CASES))
    ap.add_argument("--out", default=str(REPORTS))
    ap.add_argument("--only", default="", help="restrict to matching case ids")
    ap.add_argument("--jobs", type=int, default=min(32, (os.cpu_count() or 8)))
    ap.add_argument("--prolog-timeout", type=int, default=180)
    ap.add_argument("--catala-timeout", type=int, default=180)
    ap.add_argument("--no-minimise", action="store_true",
                    help="report discrepancies as generated, unshrunk")
    ap.add_argument("--trace-all", action="store_true",
                    help="also trace the cases that agree (slow; for debugging)")
    ap.add_argument("--shrink-budget", type=int, default=2000,
                    help="oracle calls per discrepancy while shrinking it")
    ap.add_argument("--trace-lines", type=int, default=160,
                    help="trace lines per system in the markdown report; the "
                         "full traces are always in report.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cases_dir = Path(args.cases)
    dirs = sorted(d for d in cases_dir.iterdir()
                  if d.is_dir() and (d / "meta.json").exists()) \
        if cases_dir.exists() else []
    if args.only:
        dirs = [d for d in dirs if args.only in d.name]
    if args.limit:
        dirs = dirs[:args.limit]
    if not dirs:
        print(f"no test cases under {rel(cases_dir)}; run "
              "`python3 prolog_to_catala/sara/generate_test_cases.py` first")
        return 1

    catala.ensure_built()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    metas = [load_case(d) for d in dirs]
    t0 = time.time()
    print(f"running {len(metas)} test cases through both systems "
          f"({args.jobs} at a time)")

    results = []
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        futs = {pool.submit(run_one, m, args.trace_all, args.prolog_timeout,
                            args.catala_timeout): m for m in metas}
        for k, fut in enumerate(concurrent.futures.as_completed(futs), 1):
            results.append(fut.result())
            if k % 200 == 0 or k == len(metas):
                done = collections.Counter(status_of(r) for r in results)
                print(f"  {k}/{len(metas)}  " +
                      "  ".join(f"{s}={n}" for s, n in done.most_common()))

    results.sort(key=lambda r: r["id"])
    points = set().union(*[r["points"] for r in results]) if results else set()
    audit = coverage.audit(points)

    # ---- shrink and group the discrepancies ----
    disagreeing = [r for r in results if status_of(r) == "disagree"]
    by_id = {m["id"]: m for m in metas}
    print(f"\n{len(disagreeing)} discrepancies; "
          f"{'grouping' if args.no_minimise else 'shrinking and grouping'}")

    sym = catala.load_symbols()

    def shrink(res: dict) -> tuple:
        rec = as_world(by_id[res["id"]])
        oracle = Oracle(sym, args.prolog_timeout, args.catala_timeout)
        before = sum(len(v) for v in rec["events"].values())
        small = rec
        if not args.no_minimise:
            if not oracle.disagrees(rec, res["id"] + "_s0"):
                return res, None, before, 0     # not reproducible in isolation
            small = generate.minimise(rec, oracle.disagrees, res["id"],
                                      budget=args.shrink_budget)
        return res, small, before, sum(len(v) for v in small["events"].values())

    shrunk = []
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for k, (res, small, before, after) in enumerate(
                pool.map(shrink, disagreeing), 1):
            if small is None:
                res["note"] = "not reproducible in isolation"
                print(f"  [{k}/{len(disagreeing)}] {res['id']}: not "
                      "reproducible in isolation")
                continue
            shrunk.append((res, small, before, after))
            print(f"  [{k}/{len(disagreeing)}] {res['id']} "
                  f"({res['query']}, prolog={res['prolog']} "
                  f"catala={res['catala']}): {before} -> {after} facts")

    grouped: dict[str, list] = {}
    for res, small, before, after in shrunk:
        grouped.setdefault(signature(small, res["prolog"], res["catala"]),
                           []).append((res, small, before, after))

    print(f"{len(shrunk)} reproducible -> {len(grouped)} distinct causes; "
          "tracing one example of each")

    def trace_example(item):
        sig, members = item
        res, small, before, after = members[0]
        # Trace an unshrunk example from the test case on disk, so the report
        # explains the file the reader will open; a shrunk world exists nowhere
        # else and has to be re-rendered.
        temp = None
        if after == before and small["events"] == by_id[res["id"]]["events"]:
            d = by_id[res["id"]]["dir"]
        else:
            temp = d = SCRATCH / "examples" / res["id"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "prolog.pl").write_text(prolog.render_program(small))
            (d / "catala.catala_en").write_text(catala.render(sym, small))
        traced = run_one({"id": res["id"], "dir": d, "query": res["query"],
                          "origin": res["origin"], "goal": prolog.goal_of(small),
                          "expected": None},
                         True, args.prolog_timeout, args.catala_timeout)
        if temp is not None:
            shutil.rmtree(temp, ignore_errors=True)
        return {
            "signature": sig,
            "predicate": small["test"]["goals"][0]["predicate"],
            "prolog": res["prolog"], "catala": res["catala"],
            "example": res["id"],
            "members": [m[0]["id"] for m in members],
            "facts_before": before, "facts": after,
            "world": prolog.render_facts(small),
            "goal": prolog.goal_of(small),
            "prolog_trace": traced.get("prolog_trace", ""),
            "frontier": traced.get("prolog_frontier", []),
            "catala_trace": traced.get("catala_trace", ""),
        }

    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        groups = list(pool.map(trace_example, sorted(grouped.items())))
    groups.sort(key=lambda g: (-len(g["members"]), g["predicate"]))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    index = {"run": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "cases": len(results),
             "outcomes": dict(collections.Counter(status_of(r)
                                                  for r in results)),
             "distinct_discrepancies": len(groups),
             "coverage": {k: audit[k] for k in
                          ("total", "covered", "reachable", "pct_all",
                           "pct_reachable")}}
    (out / "report.json").write_text(json.dumps({
        "index": index,
        "groups": groups,
        "cases": [{k: v for k, v in r.items() if k != "points"}
                  for r in results],
        "untaken_points": audit["untaken"],
    }, indent=1))
    render_report(index, results, groups, audit,
                  out / "DISCREPANCIES.md", args.trace_lines)

    counts = collections.Counter(status_of(r) for r in results)
    print(f"\n{len(results)} cases: " +
          ", ".join(f"{n} {s}" for s, n in counts.most_common()))
    print(f"coverage {audit['covered']}/{audit['total']} "
          f"= {audit['pct_all']:.1f}% of goal positions "
          f"({audit['pct_reachable']:.1f}% of reachable)")
    print(f"{len(groups)} distinct discrepancies -> "
          f"{rel(out / 'DISCREPANCIES.md')}")
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
