#!/usr/bin/env python3
"""Run every test case through both systems and report where they disagree.

Each directory under `sara_port/test_cases/` holds the same world and the same
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

    python3 sara_scripts/run_test_cases.py                 # everything
    python3 sara_scripts/run_test_cases.py --only s7703    # one section
    python3 sara_scripts/run_test_cases.py --no-minimise   # faster, noisier
    python3 sara_scripts/run_test_cases.py --trace-all     # trace agreements too
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

from saralib import (catala, coverage, generate, prolog,           # noqa: E402
                     provisions, traces)
from saralib.paths import CATALA_PROJECT                          # noqa: E402
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
                  out: Path, trace_lines: int = 160,
                  trails: dict | None = None) -> None:
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
                f"`sara_port/test_cases/{g['example']}/`"
                + (f", shrunk from {g['facts_before']} facts to "
                   f"{g['facts']} --- the world below is the shrunk one, the "
                   "directory holds the original."
                   if shrunk else "."),
                "",
                "```",
                f"cd sara_port/test_cases/{g['example']}",
                "swipl -q -f prolog.pl -g main -t halt",
                "catala interpret catala.catala_en -s Run -I ../../../sara_catala \\",
                "    --stdlib ../../../sara_catala/_build/libcatala "
                "--bin ../../../sara_catala/_build",
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

    if trails:
        n = trails["cases"]
        lines += [
            "## Do the two systems follow the same trail?", "",
            "Agreeing on the verdict is weak evidence: two systems can reach "
            "the same answer through different provisions, and one of them is "
            "then right by accident. Both sides can name what they consulted "
            "— SARA in its predicate names (`s7703_a_1`), the port in its "
            "`law_headings` — so the trails can be put side by side, over the "
            f"**{trails['common_vocabulary']} provisions both vocabularies "
            "distinguish**.", "",
            f"| over {n} traced cases | |", "|---|--:|",
            f"| identical provision sets | {trails['identical']} "
            f"({100 * trails['identical'] / n:.0f}%) |",
            f"| Prolog's set contained in the port's | "
            f"{trails['prolog_subset_of_catala']} "
            f"({100 * trails['prolog_subset_of_catala'] / n:.0f}%) |",
            f"| …counting only provisions a trace can show | "
            f"{trails.get('prolog_subset_of_catala_observable', 0)} "
            f"({100 * trails.get('prolog_subset_of_catala_observable', 0) / n:.0f}%) |",
            f"| mean overlap | {trails['mean_overlap']:.3f} |",
            "",
            "**Read this as a measurement, not a test.** One difference is "
            "structural rather than a defect: a Catala scope computes all of "
            "its outputs, so the port evaluates §7703(a)(2) even where (a)(1) "
            "already settled the question and Prolog short-circuited. That "
            "puts provisions in the port's set that are legitimately absent "
            "from SARA's, and it is most of what the second table below is.",
            "",
            "| consulted by Prolog, not by the port | cases |", "|---|--:|",
        ]
        for prov, k in trails["prolog_only"][:12]:
            lines.append(f"| §{prov} | {k} |")
        if trails.get("prolog_only_unobservable"):
            lines += [
                "",
                "Excluded from that table: provisions the port implements as a "
                "top-level `declaration ... equals` — a constant like "
                "§151(d)(1)'s `$2,000`, a function like §68(b)'s "
                "`applicable_amount`. Only *scope* variables leave trace "
                "events, so these are evaluated and invisible, and counting "
                "them as unread invents a finding. Of the port's "
                f"{trails.get('observable_vocabulary', 0)} traceable "
                "provisions this removes the four largest entries:",
                "", "| invisible by construction | cases |", "|---|--:|"]
            for prov, k in trails["prolog_only_unobservable"][:8]:
                lines.append(f"| §{prov} | {k} |")
        lines += ["", "| consulted by the port, not by Prolog | cases |",
                  "|---|--:|"]
        for prov, k in trails["catala_only"][:12]:
            lines.append(f"| §{prov} | {k} |")
        lines += ["",
                  "The first table is the interesting one: a provision SARA "
                  "consults and the port never opens is a rule the port may "
                  "not be reading at all. Per-case detail is in "
                  "`report.json` under `trails.per_case`.", ""]

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


# --------------------------------------------------- do they follow the same
#                                                     trail through the statute?

def compare_trails(metas: list, jobs: int, ptimeout: int, ctimeout: int,
                   sample: int, seed: int = 11) -> dict:
    """Measure whether the two systems consult the same statute provisions.

    Verdict agreement is weak: two systems can reach the same answer through
    different provisions, and one of them is then right by accident.  Both
    sides can name what they consulted --- SARA in its predicate names, the
    port in its `law_headings` --- so the trails can be put side by side; see
    `saralib.provisions` for how, and for why the vocabularies have to be
    aligned before anything is subtracted.

    This is reported as a measurement, not a test.  The two systems are
    factored differently on purpose, and one difference is structural: a Catala
    scope computes *all* its outputs, so the port evaluates §7703(a)(2) even on
    an input where (a)(1) already settled the question and Prolog never looked.
    Set equality would fail on every such case and mean nothing.
    """
    import random as _random
    if sample and len(metas) > sample:
        metas = _random.Random(seed).sample(metas, sample)
    align = provisions.Alignment(
        provisions.prolog_vocabulary(coverage.clause_index()),
        provisions.catala_vocabulary(CATALA_PROJECT.glob("*.catala_en")))
    # Only scope variables leave trace events.  A provision the port implements
    # as a top-level `declaration ... equals` is evaluated and invisible, so
    # counting it as unread invents a finding -- which it did, for the four
    # largest entries on the list.
    observable = provisions.catala_observable(
        CATALA_PROJECT.glob("*.catala_en"))

    def closure(s):
        """A provision implies every provision containing it, so `152(c)(1)`
        counts as having consulted `152(c)` and `152`.  Without this, one
        system annotating a decision at the subsection and the other at the
        paragraph reads as a disagreement about the statute."""
        out = set()
        for prov in s:
            section, labels = provisions.split(align(prov))
            for n in range(len(labels) + 1):
                out.add(section + "".join("(%s)" % x for x in labels[:n]))
        return out

    def one(meta):
        work = SCRATCH / f"trail{os.getpid()}"
        work.mkdir(parents=True, exist_ok=True)
        pt = work / (meta["id"] + ".ptr")
        ct = work / (meta["id"] + ".ctr")
        pv, _pts, _ = prolog.run_program(meta["dir"] / "prolog.pl", trace=pt,
                                         timeout=ptimeout)
        cv, _ = catala.run_program(meta["dir"] / "catala.catala_en", trace=ct,
                                   timeout=ctimeout)
        seq, _cut = traces.read_points(pt)
        pset = provisions.from_prolog_trace(seq, coverage.describe)
        cset = set()
        if ct.exists():
            try:
                cset = provisions.from_catala_trace(json.loads(ct.read_text()))
            except json.JSONDecodeError:
                pass
        pt.unlink(missing_ok=True)
        ct.unlink(missing_ok=True)
        return meta["id"], pv, cv, pset, cset

    rows = []
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        rows = [r for r in pool.map(one, metas)
                if r[1] in ("true", "false") and r[2] in ("true", "false")]
    if not rows:
        return {}

    same = sub = missed = 0
    overlap = 0.0
    only_p, only_c, hidden = (collections.Counter(), collections.Counter(),
                              collections.Counter())
    per_case = []
    for cid, _pv, _cv, pset, cset in rows:
        a, b = closure(pset), closure(cset)
        same += a == b
        sub += a <= b
        overlap += len(a & b) / max(1, len(a | b))
        gap = sorted(a - b)
        real = [x for x in gap if x in observable]
        missed += not real
        only_p.update(real)
        hidden.update(x for x in gap if x not in observable)
        only_c.update(b - a)
        per_case.append({"id": cid, "prolog_only": real,
                         "prolog_only_unobservable": [x for x in gap
                                                      if x not in observable],
                         "catala_only": sorted(b - a)})
    n = len(rows)
    return {
        "cases": n,
        "identical": same,
        "prolog_subset_of_catala": sub,
        "prolog_subset_of_catala_observable": missed,
        "mean_overlap": overlap / n,
        "common_vocabulary": len(align.common),
        "observable_vocabulary": len(observable),
        "prolog_only": only_p.most_common(25),
        "prolog_only_unobservable": hidden.most_common(25),
        "catala_only": only_c.most_common(25),
        "per_case": per_case,
    }


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
    ap.add_argument("--compare-trails", action="store_true",
                    help="also measure whether the two systems consult the "
                         "same statute provisions, not just agree on the verdict")
    ap.add_argument("--trail-sample", type=int, default=150,
                    help="cases traced for --compare-trails (0 for all).  "
                         "Kept small because tracing needs whole-program mode, "
                         "which recompiles the port's module chain per case "
                         "and costs 20-60s where a plain verdict costs 0.3s")
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
              "`python3 sara_scripts/generate_test_cases.py` first")
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
        # An unshrunk example is traced from the test case as it sits on disk,
        # so that what the report explains is the file the reader will open.
        # A shrunk one has to be re-rendered, since the small world exists
        # nowhere else.
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

    trails = {}
    if args.compare_trails:
        print("\ncomparing the statute provisions each system consults")
        trails = compare_trails(metas, args.jobs, args.prolog_timeout,
                                args.catala_timeout, args.trail_sample)
        if trails:
            print(f"  {trails['cases']} cases, common vocabulary "
                  f"{trails['common_vocabulary']} provisions: "
                  f"{trails['identical']} identical, "
                  f"{trails['prolog_subset_of_catala']} with Prolog's set "
                  f"contained in the port's, mean overlap "
                  f"{trails['mean_overlap']:.3f}")

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
    index["trails"] = {k: v for k, v in trails.items() if k != "per_case"}
    (out / "report.json").write_text(json.dumps({
        "index": index,
        "trails": trails,
        "groups": groups,
        "cases": [{k: v for k, v in r.items() if k != "points"}
                  for r in results],
        "untaken_points": audit["untaken"],
    }, indent=1))
    render_report(index, results, groups, audit,
                  out / "DISCREPANCIES.md", args.trace_lines, trails)

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
