"""The instrumented oracle, and what a branch point means.

`build()` writes `.port/airline/build/airline_oracle_covered.pl`: the shared
oracle with every body goal position wrapped so that reaching it, and failing
at it, are each recorded.  The rewrite is SARA's --- `saralib/pl/
cover_transform.pl` reads clause bodies as terms, which is the only way to
place a point per goal rather than per clause --- and is reused rather than
reimplemented, so the two ports measure coverage the same way and the numbers
are comparable.

A point is `airline_oracle.pl:<line>:<goal>:<c|f|e>`: `c` when the goal is
called, `f` when it is called and has no solution, `e` when a clause body runs
to its end.  A position is fully covered only once it has been seen both ways,
which is branch coverage rather than goal reachability.
"""
from __future__ import annotations

import re
import shutil
import subprocess

from . import paths

#: SARA's transform and runtime, reused unchanged.
SARA_PL = paths.ROOT / "prolog_to_catala/sara/saralib/pl"

COVERED = paths.BUILD / "airline_oracle_covered.pl"
POINTS = paths.BUILD / "airline_points.txt"


def build() -> int:
    """Instrument the oracle. Returns the number of clauses rewritten."""
    paths.BUILD.mkdir(parents=True, exist_ok=True)
    shutil.copy(SARA_PL / "cov_runtime.pl", paths.BUILD / "cov_runtime.pl")
    r = subprocess.run(
        [str(paths.SWIPL), str(SARA_PL / "cover_transform.pl"), "--",
         str(paths.AIRLINE_ORACLE), str(COVERED), "airline_oracle.pl"],
        capture_output=True, text=True, cwd=paths.BUILD)
    if r.returncode != 0:
        raise RuntimeError(f"cover_transform failed:\n{r.stdout}\n{r.stderr}")
    m = re.search(r"(\d+) clauses", r.stdout)
    enumerate_points()
    return int(m.group(1)) if m else 0


_POINT_RE = re.compile(r"cov\('([^']+)'\)")


def enumerate_points() -> list:
    """Every branch point that exists in the instrumented oracle."""
    pts = sorted(set(_POINT_RE.findall(COVERED.read_text())))
    POINTS.write_text("\n".join(pts) + "\n")
    return pts


def source_line(point: str) -> str:
    """Read a point back to the line of the oracle it guards."""
    m = re.match(r"airline_oracle\.pl:(\d+):", point)
    if not m:
        return "?"
    lines = paths.AIRLINE_ORACLE.read_text().split("\n")
    i = int(m.group(1)) - 1
    return lines[i].strip() if 0 <= i < len(lines) else "?"


# ---------------------------------------------- point -> oracle source, audit

_GOAL_RE = re.compile(r"cov\('([^']+):c'\),\s*\(\s*(.*?)\s*\*->", re.S)
_CUT_RE = re.compile(r"cov\('([^']+):c'\),\s*(!)")
_HEAD_RE = re.compile(r"^([a-z][a-zA-Z_0-9]*)", re.M)

#: Goals that usually have no failing execution where the oracle calls them.
#: A hypothesis, so a functor observed failing anywhere is never counted as
#: unfailable anywhere --- the rule `prolog_to_catala/sara` arrived at after
#: `findall/3` and `sum_list/2` were caught failing with a bound output.
PROBABLY_UNFAILABLE = {
    "is", "findall", "sum_list", "length", "format", "forall", "true",
    "assertz", "retractall", "sort", "msort", "nb_getval", "between",
    # `Fee = 45` where `Fee` is the clause head's unbound output argument.
    # Binding a fresh variable to a ground term has no failing execution.
    "(unification)",
}

_goals: dict | None = None


def goal_text() -> dict:
    """`airline_oracle.pl:line:pos` -> the goal guarded there, as source text."""
    global _goals
    if _goals is None:
        text = COVERED.read_text()
        out = {k: re.sub(r"\s+", " ", g).strip() for k, g in _GOAL_RE.findall(text)}
        out.update(dict(_CUT_RE.findall(text)))
        _goals = out
    return _goals


def clause_index() -> list:
    """Sorted [(line, head predicate)] over the uninstrumented oracle."""
    rows, depth = [], 0
    for n, line in enumerate(paths.AIRLINE_ORACLE.read_text().splitlines(), 1):
        stripped = line.split("%")[0]
        if depth == 0 and not line.startswith((" ", "\t", "%")):
            m = _HEAD_RE.match(line)
            if m:
                rows.append((n, m.group(1)))
        depth += stripped.count("(") - stripped.count(")")
        if stripped.rstrip().endswith("."):
            depth = 0
    return rows


def describe(point: str) -> dict:
    """Everything a report needs to say about one branch point.

    `kind` is `c` (the goal was called), `f` (it was called and had no
    solution) or `e` (a clause body ran to its end).
    """
    fname, line, _pos, kind = point.split(":")
    pred = "?"
    for start, name in clause_index():
        if start <= int(line):
            pred = name
        else:
            break
    return {"point": point, "line": int(line), "kind": kind, "predicate": pred,
            "goal": goal_text().get(":".join(point.split(":")[:3]), ""),
            "source": source_line(point)}


def functor_of(goal: str) -> str:
    """The name a point is reported under.

    Three goals have no functor of their own, and lumping them under whatever
    letter the instrumented build happened to use would be worse than useless
    --- every unification in the file would share one name, so one observed
    failure anywhere would make all of them look failable:

      `(unification)`     `Fee = 45`, `Total is T + B`.  Where the left side
                          is a variable the clause head left unbound, this
                          cannot fail, which is why so many of them sit in the
                          residual.  Never `=\\=`, `=:=`, `==` or `=<` --- those
                          are comparisons and fail all the time;
      `(comparison)`      `Dim =< 62`, `F =\\= 0`.  These fail readily, so an
                          uncovered `f` point on one is a real gap;
      `(nested wrapper)`  a bare variable, a position the transform wrapped
                          inside another wrapper;
      `(not recovered)`   a position whose goal could not be read back out of
                          the instrumented source at all.
    """
    g = goal.strip()
    # `=` only: `=\=`, `=:=`, `==` and `=<` are comparisons, and they do fail.
    if re.match(r"^[A-Z_][A-Za-z0-9_]*\s*(?:=(?![=\\<>:])|is\s)\s*\S", g):
        return "(unification)"
    if re.match(r"^[A-Z_][A-Za-z0-9_]*\s*(?:=\\=|=:=|\\==|==|=<|>=|<|>)", g):
        return "(comparison)"
    if re.match(r"^[A-Z_][A-Za-z0-9_]*$", g):
        return "(nested wrapper)"
    m = re.match(r"^\\?\+?\s*([a-zA-Z_][a-zA-Z_0-9]*)", g)
    return m.group(1) if m else "(not recovered)"


def audit(covered: set) -> dict:
    """Classify every branch point the suite did not reach.

    Nothing here is unreachable in principle --- every point exists in the
    oracle and some input reaches it.  What differs is how much is known:

      `harness`     in `main/0`, which the enumerator never calls: it asks
                    `total_cost/1` and `accepted/0` directly, so these points
                    are outside the suite by construction rather than missed;
      `unproven`    an `f` point on a goal no run has ever been seen to fail,
                    and whose functor is a deterministic builtin.  Probably it
                    has no failing execution.  Probably is not certainly;
      `reachable`   the goal has been observed failing at some other position,
                    so nothing about the goal itself is in the way.  A plain
                    gap in the suite.
    """
    points = set(enumerate_points())
    missed = points - covered
    failing_functors = {functor_of(describe(p)["goal"])
                        for p in covered if p.endswith(":f")}
    buckets: dict = {"harness": [], "unproven": [], "reachable": []}
    for p in sorted(missed):
        d = describe(p)
        f = functor_of(d["goal"])
        if d["predicate"] == "main":
            buckets["harness"].append(d)
        elif (d["kind"] == "f" and f not in failing_functors
              and f in PROBABLY_UNFAILABLE):
            buckets["unproven"].append(d)
        elif d["kind"] == "f" and f not in failing_functors:
            buckets["unproven"].append(d)
        else:
            buckets["reachable"].append(d)
    return {"points": len(points), "covered": len(covered & points),
            "missed": len(missed),
            "counts": {k: len(v) for k, v in buckets.items()}, "buckets": buckets}
