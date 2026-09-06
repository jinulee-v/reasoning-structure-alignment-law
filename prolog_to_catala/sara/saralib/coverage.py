"""The instrumented statutes, and what a branch point means.

`build()` writes `.port/sara/build/prolog_covered/`: SARA's statutes with every
body goal position wrapped so that reaching it, and failing at it, are each
recorded.  The rewrite is done by SWI reading clause bodies as *terms*
(`pl/cover_transform.pl`), which is the only way to place a point per goal
rather than per clause.

The rest of this module is the inverse map --- given a point like
`section151.pl:31:2:f`, say which clause it is in and which goal it guards ---
because a coverage number nobody can read back to a line of statute is not
evidence of anything.
"""
from __future__ import annotations

import re
import shutil
import subprocess

from .paths import (COVERED, HARNESS, PL_SUPPORT, POINTS, RAW_STATUTES,
                    STATUTES, SWIPL, rel)

# events.pl is nothing but `discontiguous` directives and init.pl nothing but
# loads; neither holds a goal position.
SKIP = {"events.pl", "init.pl"}

# Builtins that usually have no failing execution where the statutes call them:
# with the output argument unbound, `sum_list/2` and `findall/3` succeed or
# throw rather than fail.  A hypothesis, not a fact --- with the argument bound
# (`tax(alice,2015,1000)`) they do fail --- so a point is reported only as
# *possibly* unreachable, and never when the goal was seen failing elsewhere.
PROBABLY_UNFAILABLE = {
    "is", "findall", "findall_traced", "sum_list", "sumlist", "length",
    "format", "atom_string", "string_concat", "atom_number", "number_string",
    "split_string", "atomic_list_concat", "term_to_atom", "copy_term",
    "list_to_set", "sort", "msort", "true", "aggregate_all", "forall",
    "first_day_year", "last_day_year", "duration", "day_to_stamp",
    "format_time", "stamp_date_time", "date_time_stamp", "nb_getval",
}


# The only edit made to SARA's Prolog, and the reason a copy exists.  SWI >= 8
# refuses `rdiv/2` on the float `date_time_stamp/2` returns; these stamps are
# whole seconds at UTC offset 0, so truncating is value-preserving.  D1 in
# DEVIATIONS.md.
COMPAT_PATCH = ("utils.pl", """\tdate_time_stamp(date(YI,MI,DI1,0,0,0,0,-,-), Stamp).""",
                """\tdate_time_stamp(date(YI,MI,DI1,0,0,0,0,-,-), Stamp_f),
\tStamp is integer(Stamp_f). % COMPAT: SWI>=8 rdiv/2 rejects floats; stamps are whole seconds at UTC offset 0, so this is value-preserving.""")


def build_statutes() -> None:
    """Copy the pristine statutes out of `data/prolog/` and apply the one patch.

    `data/prolog/sara/` is never edited --- it is the upstream corpus, alongside
    the other datasets --- so the oracle runs against a copy.  Applying the
    patch here rather than keeping a hand-edited directory means there is no
    second source of truth to drift, and `--build` really does rebuild
    everything.
    """
    if STATUTES.exists():
        shutil.rmtree(STATUTES)
    shutil.copytree(RAW_STATUTES, STATUTES)
    name, before, after = COMPAT_PATCH
    path = STATUTES / name
    text = path.read_text()
    if text.count(before) != 1:
        raise RuntimeError(
            f"the SWI compatibility patch no longer applies to {name}: expected "
            f"exactly one occurrence of\n{before!r}\nfound "
            f"{text.count(before)}.  Upstream has changed; re-derive the patch "
            "before trusting any verdict.")
    path.write_text(text.replace(before, after))


def build() -> int:
    """(Re)generate the instrumented statutes.  Returns the number of points."""
    if COVERED.exists():
        shutil.rmtree(COVERED)
    COVERED.mkdir(parents=True)
    shutil.copy(PL_SUPPORT / "cov_runtime.pl", COVERED / "cov_runtime.pl")

    for src in sorted(STATUTES.glob("*.pl")):
        if src.name in SKIP:
            shutil.copy(src, COVERED / src.name)
            continue
        proc = subprocess.run(
            [str(SWIPL), str(PL_SUPPORT / "cover_transform.pl"), "--",
             str(src), str(COVERED / src.name), src.name],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stdout + proc.stderr)

    # init.pl must pull the runtime in before the statutes that call cov/1.
    init = COVERED / "init.pl"
    init.write_text(":- [cov_runtime].\n" + init.read_text())
    shutil.copy(PL_SUPPORT / "harness.pl", HARNESS)

    pts = set()
    for p in COVERED.glob("*.pl"):
        pts |= set(re.findall(r"cov\('([^']+)'\)", p.read_text()))
    POINTS.write_text("\n".join(sorted(pts)) + "\n")
    return len(pts)


def all_points() -> set:
    return set(POINTS.read_text().split())


# --------------------------------------------------- point -> statute source

_GOAL_RE = re.compile(r"cov\('([^']+):c'\),\s*\(\s*(.*?)\s*\*->", re.S)
_CUT_RE = re.compile(r"cov\('([^']+):c'\),\s*(!)")
_HEAD_RE = re.compile(r"^([a-z][a-zA-Z_0-9]*)\(", re.M)

_goals: dict | None = None
_clauses: dict | None = None


def goal_text() -> dict:
    """`file:line:pos` -> the goal guarded at that position, as source text."""
    global _goals
    if _goals is None:
        out = {}
        for path in sorted(COVERED.glob("*.pl")):
            text = path.read_text()
            for key, goal in _GOAL_RE.findall(text):
                out[key] = re.sub(r"\s+", " ", goal).strip()
            for key, goal in _CUT_RE.findall(text):
                out[key] = goal
        _goals = out
    return _goals


def clause_index() -> dict:
    """`file` -> sorted [(line, head predicate)] of the uninstrumented source.

    The instrumented points carry the line the clause *started* on in the
    unrewritten build, so the enclosing predicate is read off that one rather
    than off the rewritten copy, whose lines no longer correspond.
    """
    global _clauses
    if _clauses is None:
        out = {}
        for path in sorted(STATUTES.glob("*.pl")):
            rows, depth = [], 0
            for n, line in enumerate(path.read_text().splitlines(), 1):
                stripped = line.split("%")[0]
                if depth == 0:
                    m = _HEAD_RE.match(line)
                    if m:
                        rows.append((n, m.group(1)))
                depth += stripped.count("(") - stripped.count(")")
                if stripped.rstrip().endswith("."):
                    depth = 0
            out[path.name] = rows
        _clauses = out
    return _clauses


def clause_of(point: str) -> tuple[str, int, str]:
    """(file, clause start line, head predicate) for one point."""
    fname, line = point.split(":")[0], int(point.split(":")[1])
    rows = clause_index().get(fname, [])
    head = "?"
    for start, pred in rows:
        if start <= line:
            head = pred
        else:
            break
    return fname, line, head


def describe(point: str) -> dict:
    """Everything a report needs to say about one branch point.

    `kind` is `c` (the goal was called), `f` (it was called and had no
    solution) or `e` (a clause body ran to its end).
    """
    fname, line, _pos, kind = point.split(":")
    prefix = ":".join(point.split(":")[:3])
    _, _, pred = clause_of(point)
    return {"point": point, "file": fname, "line": int(line), "kind": kind,
            "predicate": pred, "goal": goal_text().get(prefix, "")}


def functor_of(goal: str) -> str:
    """The name a point is reported under.

    Two goals have no name of their own: a bare variable, which is a metacall
    the transform wrapped in `call/1`, and a position whose goal could not be
    read back out of the source.  Both are labelled rather than reported under
    the variable letter the instrumented build happened to give them.
    """
    if re.match(r"^[A-Z_][A-Za-z0-9_]*$", goal.strip()):
        return "(metacall)"
    m = re.match(r"^\\?\+?\s*([a-zA-Z_][a-zA-Z_0-9]*)", goal)
    return m.group(1) if m else "(not recovered)"


def audit(covered: set) -> dict:
    """Classify every branch point the suite did not reach.

    There is no such thing here as a point that "cannot be checked".  Every one
    of the 3,195 exists in the source and a good enough input reaches it.  What
    differs is how much is *known*:

      `reachable`   the goal has been observed failing at some other position,
                    so nothing about the goal itself prevents this point ---
                    this is a straightforward gap in the suite;
      `unproven`    an `f` point on a goal that no run has ever seen fail, and
                    that is a deterministic builtin.  Probably it has no
                    failing execution (`sum_list(L, Total)` with `Total`
                    unbound succeeds or throws).  Probably is not certainly:
                    bind the output and it fails, which is what four such
                    points in this very corpus do.

    So the headline is `pct_all`, over all 3,195.  `pct_reachable` excludes the
    unproven ones and is an upper bound offered for comparison --- report both,
    and never call the residual unreachable.
    """
    total = all_points()
    goals = goal_text()

    # Evidence first: any goal seen failing anywhere can fail, whatever the
    # hypothesis above says about it.
    failable = {functor_of(goals.get(p.rsplit(":", 1)[0], "?"))
                for p in covered if p.endswith(":f")}

    reachable_missing, unproven = [], []
    for pt in sorted(total - covered):
        prefix, kind = pt.rsplit(":", 1)
        goal = goals.get(prefix, "?")
        fn = functor_of(goal)
        row = {"point": pt, "goal": goal, "functor": fn,
               "predicate": clause_of(pt)[2]}
        if kind == "f" and fn in PROBABLY_UNFAILABLE and fn not in failable:
            unproven.append(row)
        else:
            reachable_missing.append(row)

    denom = len(total) - len(unproven)
    return {
        "total": len(total), "covered": len(covered),
        "untaken": reachable_missing, "unproven": unproven,
        # kept under the old name so existing callers and reports keep working
        "unfailable": unproven, "reachable": denom,
        "observed_failable": sorted(failable & PROBABLY_UNFAILABLE),
        "pct_all": 100.0 * len(covered) / max(1, len(total)),
        "pct_reachable": 100.0 * len(covered) / max(1, denom),
    }


def ensure_built() -> None:
    if not POINTS.exists() or not HARNESS.exists():
        n = build()
        print(f"  instrumented statutes: {n} branch points -> {rel(COVERED)}")
