#!/usr/bin/env python3
"""Build a test suite that takes every execution path through SARA's Prolog.

One test case is one *world* plus one *query*, written twice --- as a Prolog
program that runs against SARA's statutes, and as a Catala program that runs
against the port --- so the pair can be put to both systems and their answers
compared.  Both files stand on their own:

    .port/sara/test_cases/<id>/prolog.pl        swipl -q -f prolog.pl -g main -t halt
    .port/sara/test_cases/<id>/catala.catala_en catala interpret ... -s Run
    .port/sara/test_cases/<id>/meta.json        where it came from, what it asks

Worlds come from three methods --- SARA's own 376 cases, bounded-exhaustive
enumeration over each predicate's *reachable* input signature, and
coverage-guided mutation for the predicates too large to enumerate.  Which of
them become test cases is decided by one rule, applied to all three:

    a world is kept when it drives the statutes down an execution path no
    kept world has taken.

The statutes are instrumented so that every goal position records being called
and, separately, being called without a solution; the set of positions a world
reaches is its path.  Two worlds with the same path made the same decisions and
cannot distinguish the two systems, so keeping the second one would only make
the suite slower to run and harder to read.

Selection consults Prolog alone.  Catala is not run until `run_test_cases.py`,
which is what keeps the suite honest: it describes SARA's behaviour, not the
places the port happens to agree with it.

    python3 prolog_to_catala/sara/generate_test_cases.py               # the usual run
    python3 prolog_to_catala/sara/generate_test_cases.py --build       # rebuild inputs first
    python3 prolog_to_catala/sara/generate_test_cases.py --quick       # a small suite, fast
    python3 prolog_to_catala/sara/generate_test_cases.py --only s7703  # one section
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import copy
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from saralib import catala, catala_emit as emit, coverage, generate, prolog  # noqa: E402
from saralib.paths import (COVERED, GROUNDED, HARNESS, PL_SUPPORT, SCRATCH,
                           SIGNATURE, STATUTES, SWIPL, TEST_CASES,
                           VALUE_TYPES, rel)                    # noqa: E402


# ------------------------------------------------------------------- inputs

def build_inputs(force: bool = False) -> None:
    """Everything under `.port/sara/build/`, all of it regenerable from the
    pristine corpus plus the one hand-patched statute build."""
    from saralib import grounding, value_types

    SCRATCH.mkdir(parents=True, exist_ok=True)
    # First: everything downstream reads the statutes, grounder included.
    if force or not STATUTES.exists():
        coverage.build_statutes()
        print(f"  statutes + the SWI compatibility patch -> {rel(STATUTES)}")
    if force or not GROUNDED.exists() or not any(GROUNDED.glob("*.json")):
        print("  grounding SARA's cases to world models ...")
        grounding.main(jobs=16)
    if force or not VALUE_TYPES.exists():
        print("  recovering the atom/string reading of every value ...")
        value_types.main()
    if force or not SIGNATURE.exists():
        SIGNATURE.unlink(missing_ok=True)
        generate.signature()
        print(f"  call graph + literal dictionary -> {rel(SIGNATURE)}")
    if force or not coverage.POINTS.exists() or not HARNESS.exists():
        n = coverage.build()
        print(f"  instrumented statutes: {n} branch points -> {rel(COVERED)}")
    prolog.load_discontiguous()


# Two of SARA's cases contain no executable test: a missing period lets the
# last fact absorb the `:- ... .` directive as its body, so upstream the test
# never runs.  Asked directly, `s3306_c_2(alice_employer,_,2017)` is true in
# both worlds, so the negative case's corpus label was never checked.
INERT = {"s3306_c_2_pos", "s3306_c_2_neg"}


def self_check(seeds: list, jobs: int, limit: int = 0) -> int:
    """Re-run SARA's own cases through the renderer and the instrumented
    statutes.

    The renderer is the load-bearing part of the whole apparatus: if it does
    not reproduce the corpus *in meaning*, every discrepancy reported
    downstream is suspect.  The corpus is the only input with a known right
    answer, so it is the only thing that can check it.
    """
    todo = [r for r in seeds if r["test"].get("expected") is not None
            and r["id"] not in INERT]
    if limit:
        todo = todo[:limit]
    bad = []

    def one(rec):
        verdict, _ = prolog.run_world(rec, f"chk_{rec['id']}",
                                      coverage_on=False, timeout=180)
        return rec["id"], verdict, rec["test"]["expected"]

    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for cid, verdict, expected in pool.map(one, todo):
            if verdict != ("true" if expected else "false"):
                bad.append((cid, verdict, expected))
    print(f"  self-check: {len(todo) - len(bad)}/{len(todo)} of SARA's cases "
          f"reproduce their upstream verdict "
          f"({len(INERT)} excluded: no executable test upstream)")
    for cid, verdict, expected in bad[:10]:
        print(f"    {cid}: got {verdict}, expected {expected}")
    return len(bad)


# --------------------------------------------------------------- generation

class Suite:
    """The kept worlds, one per distinct execution path."""

    def __init__(self, per_query_cap: int) -> None:
        self.by_path: dict[str, dict] = {}
        self.points: set = set()
        self.per_query = collections.Counter()
        self.cap = per_query_cap
        self.seen = 0

    def offer(self, rec: dict, path: str, verdict: str,
              points: set | None = None, capped: bool = True) -> bool:
        self.seen += 1
        if path in self.by_path:
            return False
        query = rec.get("query", "?")
        # Cap per query predicate, so mutation of one heavily branching section
        # cannot crowd out the suite.  Enumeration, which must represent every
        # path in scope, and the rarer `true` answers are exempt.
        if capped and self.per_query[query] >= self.cap and verdict != "true":
            return False
        rec["path"] = path
        rec["prolog"] = verdict
        # The clauses this world entered, so mutation can tell which parents are
        # near an uncovered point.  Clause keys rather than points, since that is
        # the granularity the question is asked at, and far less memory.
        if points:
            rec["_clauses"] = frozenset(p.rsplit(":", 2)[0] for p in points)
            self.points |= points
        self.by_path[path] = rec
        self.per_query[query] += 1
        return True

    def __len__(self) -> int:
        return len(self.by_path)


def _sig(points: set) -> str:
    return hashlib.sha1("\n".join(sorted(points)).encode()).hexdigest()


def run_seeds(suite: Suite, seeds: list, jobs: int) -> None:
    def one(rec):
        verdict, points = prolog.run_world(rec, f"seed_{rec['id']}",
                                           timeout=180)
        return rec, verdict, points

    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for rec, verdict, points in pool.map(one, seeds):
            if verdict in ("true", "false"):
                suite.offer(rec, _sig(points), verdict, points)


def run_exhaustive(suite: Suite, templates: dict, args) -> None:
    """Enumerate each small predicate's input space, in per-predicate batches."""
    reach = generate.reachable_inputs()
    cands = generate.exhaustive_candidates(
        templates, args.max_inputs, args.cap, args.only)
    by_query = collections.defaultdict(list)
    for rec in cands:
        by_query[rec["query"]].append(rec)

    def one(item):
        query, recs = item
        results, points, err = prolog.batch_run(
            recs, reach[query], "x_" + query.replace("/", "_"))
        return query, recs, results, points, err

    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for query, recs, results, points, err in pool.map(
                one, sorted(by_query.items())):
            if not results:
                print(f"    {query:22} no results  {err.strip()[:80]}")
                continue
            kept = 0
            for i, (verdict, path) in sorted(results.items()):
                kept += suite.offer(recs[i], path, verdict, capped=False)
            # Every path in the batch is in the suite, and equal path means equal
            # point set, so the batch's union is the suite's.
            suite.points |= points
            print(f"    {query:22} {len(recs):7} worlds -> "
                  f"{len({p for _, p in results.values()}):5} paths, "
                  f"{kept:4} kept")


def run_arguments(suite: Suite, args) -> None:
    """The predicates with no world to enumerate, checked over their arguments."""
    cands = generate.argument_candidates(args.only)
    if not cands:
        print("    nothing to do")
        return
    by_query = collections.defaultdict(list)
    for rec in cands:
        by_query[rec["query"]].append(rec)

    def one(item):
        query, recs = item
        results, points, err = prolog.batch_run(
            recs, [], "a_" + query.replace("/", "_"))
        return query, recs, results, points, err

    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        for query, recs, results, points, err in pool.map(
                one, sorted(by_query.items())):
            if not results:
                print(f"    {query:22} no results  {err.strip()[:80]}")
                continue
            kept = 0
            for i, (verdict, path) in sorted(results.items()):
                kept += suite.offer(recs[i], path, verdict, capped=False)
            suite.points |= points
            print(f"    {query:22} {len(recs):7} tuples -> "
                  f"{len({p for _, p in results.values()}):5} paths, "
                  f"{kept:4} kept")


def backfill_clauses(suite: Suite, jobs: int) -> int:
    """Give the batch-enumerated worlds the clause set the mutator reads.

    `batch_run` returns one union of coverage for a whole batch, not a set per
    world, so an enumerated world arrives without one --- and would then be the
    least attractive parent in the pool despite being the one that reached
    deepest into a small predicate.  Only the kept representatives need it, and
    there are a few hundred, so it is cheaper to re-run them than to make the
    batch driver print a clause list per world.
    """
    todo = [r for r in suite.by_path.values() if "_clauses" not in r]
    if not todo:
        return 0

    def one(rec):
        _v, points = prolog.run_world(rec, "bf_" + str(abs(hash(rec["path"]))),
                                      timeout=60)
        return rec, points

    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for rec, points in pool.map(one, todo):
            rec["_clauses"] = frozenset(p.rsplit(":", 2)[0] for p in points)
    return len(todo)


def run_mutation(suite: Suite, templates: dict, args) -> None:
    """Coverage-guided mutation, for what enumeration cannot reach.

    Reaching a deep guard needs several conditions to hold at once, and random
    mutation does not assemble four conditions --- but it does reach the
    sections whose input signature is far too large to enumerate, which is
    §3306 and `tax/3`.  A mutant is bred from a kept world, so the population
    drifts toward whatever has already been shown to reach somewhere new.
    """
    rng = random.Random(args.seed)
    mut = generate.Mutator(rng)
    injectable = sorted({k for rec in suite.by_path.values()
                         for k in rec.get("other", {})})
    all_pts = coverage.all_points()
    rounds = max(1, args.mutants // max(1, args.batch))
    for rnd in range(rounds):
        parents = list(suite.by_path.values())
        # `--frontier-bias` breeds from worlds already reaching a clause with an
        # uncovered point.  Off by default because it measured worse: such worlds
        # are the largest, costing an order of magnitude more Prolog time for
        # fewer new paths (132/95 in the first two rounds against 158/115 for
        # uniform choice).  It may need to penalise size.
        if args.frontier_bias:
            frontier = {p.rsplit(":", 2)[0] for p in all_pts - suite.points}
            weights = [1 + 3 * len(r.get("_clauses", ()) & frontier)
                       for r in parents]
            chosen = rng.choices(parents, weights, k=args.batch)
        else:
            chosen = [rng.choice(parents) for _ in range(args.batch)]
        batch = []
        for n, parent in enumerate(chosen):
            parent = dict(parent)
            parent["_inject_pool"] = injectable
            batch.append(mut.spawn(parent, templates,
                                   f"m{rnd:03d}_{n:04d}"))

        def one(rec):
            verdict, points = prolog.run_world(rec, rec["id"], timeout=60)
            return rec, verdict, points

        kept = 0
        with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
            for rec, verdict, points in pool.map(one, batch):
                if verdict not in ("true", "false"):
                    continue
                if args.only and args.only not in rec["query"]:
                    continue
                kept += suite.offer(rec, _sig(points), verdict, points)
        print(f"    round {rnd + 1}/{rounds}: {args.batch} mutants, "
              f"{kept} kept, suite now {len(suite)}")


# ------------------------------------------------------------------ writing

PROLOG_HEADER = """% SARA differential test case: {id}
%
% Origin  : {origin}
% Query   : {raw}
% Expected: {expected}
%
% Run it:
%     swipl -q -f prolog.pl -g main -t halt        -> VERDICT true | false
%
% The Catala program in this directory states the same world and asks the same
% question of the port.  `run_test_cases.py` runs both and compares.
"""

CATALA_PROVENANCE = """Generated by `prolog_to_catala/sara/generate_test_cases.py`; the world and the query
are the same ones `prolog.pl` in this directory puts to SARA's statutes.
Run it with:

    catala interpret catala.catala_en -s Run -I data/catala_gold/sara \\
        --stdlib data/catala_gold/sara/_build/libcatala --bin data/catala_gold/sara/_build
"""


LITERAL = re.compile(r"-?\d+|\[[^\]]*\]")


def _probe_source(rec: dict) -> str:
    """The case, with every literal argument marked for the value probe."""
    marked = copy.deepcopy(rec)
    g = marked["test"]["goals"][0]
    args = list(g["args"])
    hits = []
    for i, a in enumerate(args):
        a = a.strip()
        if LITERAL.fullmatch(a):
            args[i] = f"'$probe'({i},{a})"
            hits.append(i)
    if not hits:
        return ""
    g["args"] = args
    marked["test"]["raw"] = "%s(%s)" % (g["predicate"], ",".join(args))
    return prolog.render_program(marked, harness=PL_SUPPORT / "values_harness.pl")


PROBE_RE = re.compile(r"^PROBE (\d+) (.+)$", re.M)


def _probe(rec: dict, timeout: int = 90) -> dict:
    """{position: [values]} for the positions the world determines.

    A position that raises, times out or yields nothing is an *input* and is
    left out; only a position SARA can bind is a candidate for rebinding.
    """
    src = _probe_source(rec)
    if not src:
        return {}
    work = SCRATCH / f"v{os.getpid()}"
    work.mkdir(parents=True, exist_ok=True)
    f = work / f"{abs(hash(rec['id'])) % (10 ** 9)}.pl"
    f.write_text(src)
    try:
        proc = subprocess.run(
            [str(SWIPL), "-q", "-f", str(f), "-g", "main", "-t", "halt"],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {}
    finally:
        f.unlink(missing_ok=True)
    out = {}
    for pos, vals in PROBE_RE.findall(proc.stdout):
        vals = vals.strip()
        if vals in ("'$err'", "[]"):
            continue
        out[int(pos)] = vals
    return out


VARIABLE = re.compile(r"(?<![\w])_[A-Z0-9]\w*")


def _sole_value(vals: str) -> str | None:
    """The value of a `~q`-printed Prolog list, if the goal determines exactly one.

    `None` unless every solution is the same ground value.  Both halves matter:

    *Ground*, because a goal can succeed without binding the argument at all --
    `latest/2` and `earliest/2` leave their output unbound to mean "no
    constraint" -- and `_35856` is a variable, not a value.

    *Sole*, because SARA's predicates are **relations, not functions**.  Where a
    case injects a conclusion additively the statute's own derivation survives
    beside the injected row, so `s63_c_1(alice,2017,V)` has four answers ---
    3000, 6000, 2000 and 5000, being each basic amount against each additional
    one.  The port computes a single value.  Binding the goal to an arbitrary
    member would then assert something the port may legitimately not compute,
    and report a discrepancy that is an artefact of which member was picked.
    So a non-deterministic goal is left alone; see DEVIATIONS.md D77.
    """
    inner = vals.strip()
    if not (inner.startswith("[") and inner.endswith("]")):
        return None
    inner = inner[1:-1].strip()
    if not inner:
        return None
    depth, buf, seen = 0, [], set()
    for ch in inner + ",":
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == "," and depth == 0:
            seen.add("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    seen.discard("")
    if len(seen) != 1:
        return None
    tok = seen.pop()
    if VARIABLE.search(tok):
        return None
    return tok


def strengthen_goals(suite: "Suite", jobs: int) -> dict:
    """Replace a stale expected value with the one SARA derives.

    A mutant inherits its goal from the seed it was bred from, so once the
    world is mutated a bound output --- `tax(alice,2018,259487)` --- is stale
    and the case comes out `false`.  Two systems agreeing on `false` agree only
    that each differs from that literal; they may differ from it, and from each
    other, by any amount.  Rebinding to SARA's own value makes the case `true`
    by construction, and a `true` verdict on a bound output *is* an exact
    value assertion on both sides.

    Only `false` cases are touched: a `true` one already pins the value.  A
    position that raises when freed is an input --- an unbound year reaches
    `first_day_year/2` and raises rather than failing (D12) --- and is left
    alone, so nothing has to declare which arguments are outputs.
    """
    todo = [r for r in suite.by_path.values() if r.get("prolog") == "false"]
    stats = collections.Counter(probed=len(todo))

    def one(rec):
        found = _probe(rec)
        for pos in sorted(found):
            claimed = rec["test"]["goals"][0]["args"][pos].strip()
            value = _sole_value(found[pos])
            if value is None or value == claimed:
                continue
            return rec, pos, value
        return rec, None, None

    changed = []
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for rec, pos, value in pool.map(one, todo):
            if pos is None:
                continue
            args = list(rec["test"]["goals"][0]["args"])
            args[pos] = value
            generate.set_goal(rec, rec["test"]["goals"][0]["predicate"], args)
            changed.append(rec)
    stats["rebound"] = len(changed)

    # The goal changed, so re-measure verdict and path: a strengthened case
    # drives the statutes further, and its points belong in the coverage union.
    def rerun(rec):
        verdict, points = prolog.run_world(rec, f"sg{abs(hash(rec['id'])) % 10 ** 9}")
        return rec, verdict, points

    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for rec, verdict, points in pool.map(rerun, changed):
            stats[f"now_{verdict}"] += 1
            rec["prolog"] = verdict
            if points:
                rec["path"] = _sig(points)
                suite.points |= points
    return stats


def write_case(sym, rec: dict, out: Path) -> bool:
    """One test case directory.  False if the query has no Catala renderer."""
    try:
        catala_text = catala.render(sym, rec, provenance=CATALA_PROVENANCE)
    except catala.NotPorted:
        return False

    d = out / rec["id"]
    d.mkdir(parents=True, exist_ok=True)
    header = PROLOG_HEADER.format(
        id=rec["id"], origin=rec.get("origin", "?"),
        raw=" ".join(prolog.goal_of(rec).split()),
        expected=("unknown --- Prolog is the oracle"
                  if rec["test"].get("expected") is None
                  else rec["test"]["expected"]))
    # Relative, so the directory reads and runs without a runner to explain it.
    statutes = os.path.relpath(COVERED / "init", d)
    harness = os.path.relpath(HARNESS, d)
    (d / "prolog.pl").write_text(
        prolog.render_program(rec, statutes=statutes, harness=harness,
                              header=header))
    (d / "catala.catala_en").write_text(catala_text)
    (d / "meta.json").write_text(json.dumps({
        "id": rec["id"],
        "origin": rec.get("origin"),
        "query": rec.get("query"),
        "goal": prolog.goal_of(rec),
        "expected": rec["test"].get("expected"),
        "prolog_verdict_at_generation": rec.get("prolog"),
        "execution_path": rec.get("path"),
        "n_facts": sum(len(v) for v in rec["events"].values()),
        "n_injections": sum(len(v) for v in rec.get("other", {}).values()),
        "events": rec["events"],
        "other": rec.get("other", {}),
        "discontiguous": rec.get("discontiguous", []),
        "value_kinds": rec.get("value_kinds", {}),
        "test": rec["test"],
    }, indent=1))
    return True


def verify_written(out: Path, jobs: int, sample: int) -> list:
    """Re-run written cases from disk and check they still say what they said.

    Selection runs a world model through an in-memory rendering; a test case is
    a *file*, and the two can differ.  They did: a wrapped query in the header
    comment left its continuation line uncommented, which swallowed the
    `ensure_loaded` with it, and six cases silently ran against no statutes at
    all.  Nothing but this pass would have noticed --- the case still produced
    a verdict, just not from the statutes.
    """
    dirs = sorted(d for d in out.iterdir()
                  if d.is_dir() and (d / "meta.json").exists())
    if sample and len(dirs) > sample:
        dirs = random.Random(0).sample(dirs, sample)
    if not dirs:
        return []

    def one(d: Path):
        meta = json.loads((d / "meta.json").read_text())
        verdict, _points, err = prolog.run_program(d / "prolog.pl", timeout=180)
        want = meta.get("prolog_verdict_at_generation")
        if verdict == want:
            return None
        return {"id": meta["id"], "expected": want, "got": verdict,
                "detail": err.strip()[-300:]}

    bad = []
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for row in pool.map(one, dirs):
            if row:
                bad.append(row)
    print(f"  verified {len(dirs)} written cases on disk: "
          f"{len(dirs) - len(bad)} reproduce their verdict")
    for row in bad[:10]:
        print(f"    {row['id']}: wrote {row['expected']}, the file says "
              f"{row['got']}  {row['detail'][:120]}")
    return bad


# --------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true",
                    help="rebuild .port/sara/build/ from the corpus first")
    ap.add_argument("--methods", default="seed,exhaustive,arguments,mutation",
                    help="which generators to run")
    ap.add_argument("--out", default=str(TEST_CASES))
    ap.add_argument("--jobs", type=int, default=min(32, (os.cpu_count() or 8)))
    ap.add_argument("--max-inputs", type=int, default=5,
                    help="enumerate predicates whose reachable signature is "
                         "at most this many event predicates")
    ap.add_argument("--cap", type=int, default=40000,
                    help="worlds enumerated per predicate before sampling")
    ap.add_argument("--mutants", type=int, default=12000,
                    help="mutants bred; the main lever on coverage")
    ap.add_argument("--batch", type=int, default=400)
    ap.add_argument("--per-query", type=int, default=120,
                    help="test cases kept per query predicate")
    ap.add_argument("--only", default="", help="restrict to matching predicates")
    ap.add_argument("--seed", type=int, default=20260831)
    ap.add_argument("--frontier-bias", action="store_true",
                    help="breed from worlds nearest an uncovered branch; "
                         "measured slower and no better, see run_mutation")
    ap.add_argument("--quick", action="store_true",
                    help="a small suite, for checking the pipeline works")
    ap.add_argument("--no-strengthen", action="store_true",
                    help="skip rebinding stale expected values to the value "
                         "SARA derives; leaves those cases as weak `false`s")
    ap.add_argument("--verify", type=int, default=200,
                    help="written cases re-run from disk afterwards "
                         "(0 for all of them)")
    ap.add_argument("--skip-self-check", action="store_true")
    args = ap.parse_args()

    if args.quick:
        args.cap, args.mutants, args.per_query = 400, 200, 12
        args.batch = min(args.batch, args.mutants)
        args.verify = 40

    out = Path(args.out)
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    t0 = time.time()

    print("building inputs")
    build_inputs(force=args.build)
    catala.ensure_built()

    seeds = generate.seed_candidates()
    if args.only:
        seeds = [r for r in seeds if args.only in r["query"]]
    print(f"  {len(seeds)} of SARA's cases as world models")
    if not args.skip_self_check:
        if self_check(seeds, args.jobs, limit=40 if args.quick else 0):
            print("  the renderer does not reproduce SARA's own verdicts; "
                  "generation would be unsound.  Fix that before continuing, "
                  "or pass --skip-self-check to look anyway.")
            return 1

    templates = generate.goal_templates(seeds)
    suite = Suite(args.per_query)

    if "seed" in methods:
        print("\nmethod 1: SARA's own cases")
        run_seeds(suite, seeds, args.jobs)
        print(f"  {len(suite)} distinct execution paths")
    if "exhaustive" in methods:
        print("\nmethod 2: bounded-exhaustive enumeration over worlds")
        run_exhaustive(suite, templates, args)
        print(f"  suite now {len(suite)}")
    if "arguments" in methods:
        print("\nmethod 3: exhaustive over arguments, where there is no world")
        run_arguments(suite, args)
        print(f"  suite now {len(suite)}")
    if "mutation" in methods:
        print("\nmethod 4: coverage-guided mutation")
        n = backfill_clauses(suite, args.jobs) if args.frontier_bias else 0
        if n:
            print(f"    measured the clause set of {n} enumerated worlds, so "
                  "they can be bred from too")
        run_mutation(suite, templates, args)

    if not args.no_strengthen:
        print("\nstrengthening goals: asking SARA for the value it derives")
        st = strengthen_goals(suite, args.jobs)
        print(f"    {st['probed']} cases answered false; "
              f"{st['rebound']} had an output the world determines")
        for k in sorted(k for k in st if k.startswith("now_")):
            print(f"    rebound -> {k[4:]}: {st[k]}")

    print(f"\nwriting {len(suite)} test cases -> {rel(out)}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    sym = catala.load_symbols()
    written, unported = 0, collections.Counter()
    # A renderer that raises must not take the whole suite with it: the output
    # directory is already emptied, so an exception leaves a half-written suite.
    # Collect the failures, report them, and exit non-zero.
    broken = []
    out_of_domain = []
    for rec in suite.by_path.values():
        try:
            ok = write_case(sym, rec, out)
        except emit.EventCardinalityError as exc:
            out_of_domain.append((rec.get("id", "?"), prolog.goal_of(rec),
                                  str(exc)))
            continue
        except Exception as exc:                        # noqa: BLE001
            broken.append((rec.get("id", "?"), prolog.goal_of(rec),
                           f"{type(exc).__name__}: {exc}"))
            continue
        if ok:
            written += 1
        else:
            unported[rec.get("query", "?")] += 1

    if broken:
        print(f"\n  !! {len(broken)} case(s) could not be rendered and were "
              f"dropped from the suite:")
        for cid, goal, err in broken[:10]:
            print(f"       {cid}  {goal}\n         {err}")

    if out_of_domain:
        print(f"\n  {len(out_of_domain)} case(s) intentionally dropped: generated "
              "world exceeds a 0-or-1 category role")
        for cid, goal, err in out_of_domain[:10]:
            print(f"       {cid}  {goal}\n         {err}")

    bad = verify_written(out, args.jobs, args.verify)
    audit = coverage.audit(suite.points)
    index = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "methods": methods,
        "cases": written,
        "candidates_evaluated": suite.seen,
        "distinct_paths": len(suite),
        "unported_dropped": dict(unported),
        "event_cardinality_dropped": len(out_of_domain),
        "coverage": {k: audit[k] for k in
                     ("total", "covered", "reachable", "pct_all",
                      "pct_reachable")},
        "by_origin": dict(collections.Counter(
            r.get("origin") for r in suite.by_path.values())),
        "by_query": dict(collections.Counter(
            r.get("query") for r in suite.by_path.values())),
    }
    index["verify_failures"] = bad
    (out / "INDEX.json").write_text(json.dumps(index, indent=1))

    print(f"  {written} written, {sum(unported.values())} dropped "
          f"(no Catala renderer for the query)")
    print(f"\nbranch coverage of SARA's statutes")
    print(f"  points reached      : {audit['covered']}/{audit['total']} "
          f"= {audit['pct_all']:.1f}%")
    print(f"  of reachable points : {audit['covered']}/{audit['reachable']} "
          f"= {audit['pct_reachable']:.1f}%   "
          f"({len(audit['unfailable'])} cannot fail by construction)")
    print(f"  genuinely untaken   : {len(audit['untaken'])}")
    print(f"\n{time.time() - t0:.0f}s.  Next: "
          f"python3 prolog_to_catala/sara/run_test_cases.py")
    if bad:
        # A written case that does not reproduce the verdict selection saw is
        # still compared against Catala, and its answer believed.
        print(f"\n{len(bad)} written cases do not reproduce the verdict they "
              "were selected on; the suite is not trustworthy until that is "
              "fixed (see INDEX.json:verify_failures).")
        return 1
    if broken:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
