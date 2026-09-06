"""Render a world model as Prolog, and run it against SARA's statutes.

A *world model* is the JSON shape the grounder produces and every generator
here speaks:

    {"id": ..., "events": {pred: [[args], ...]},   # the event base
     "other": {"pred/arity": [[args], ...]},       # injected statute conclusions
     "discontiguous": ["s151_c/4", ...],           # ... declared, or replacing
     "value_kinds": {"location_\\t1\\tusa": "str"},  # atom/string overrides
     "test": {"raw": ..., "goals": [{"predicate":..., "args": [...]}]}}

The renderer is the load-bearing part.  If it does not reproduce SARA's own
cases *in meaning*, every disagreement reported downstream is suspect --- which
is why `generate_test_cases.py` re-renders all 376 and checks them against
their upstream verdicts before generating anything.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
from pathlib import Path

from .paths import (COVERED, DISCONTIGUOUS, GROUNDED, HARNESS, RAW_CASES,
                    SCRATCH, SWIPL)
from .value_types import kind_of, table_for

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BARE_ATOM_RE = re.compile(r"^[a-z][a-zA-Z0-9_]*$")
VAR_RE = re.compile(r"^_VAR\d+$")


# ------------------------------------------------------------- world -> text

def render_value(types: dict, pred: str, pos: int, value) -> str:
    """One fact argument, written the way SARA writes it.

    The atom/string split is semantic, not cosmetic: the statutes compare with
    `==`, so `location_(e,usa)` and `location_(e,"usa")` name different places
    and only the second matches §3306(c)(7)'s United States test.
    """
    kind = kind_of(types, pred, pos, value)
    s = str(value)
    if kind == "int":
        return str(int(value))
    if kind == "var":
        return s                    # `_VAR0` is already a Prolog variable
    if kind == "str":
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if BARE_ATOM_RE.match(s):
        return s
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def render_facts(rec: dict, types: dict | None = None) -> str:
    """The world model as Prolog facts, in a stable order."""
    types = {**(types or table_for(rec.get("id"))), **rec.get("value_kinds", {})}
    lines = []
    for pred in sorted(rec["events"]):
        for row in rec["events"][pred]:
            args = ",".join(render_value(types, pred, i, v)
                            for i, v in enumerate(row))
            lines.append(f"{pred}({args}).")
    for key in sorted(rec.get("other", {})):
        pred = key.split("/")[0]
        for row in rec["other"][key]:
            args = ",".join(render_value(types, pred, i, v)
                            for i, v in enumerate(row))
            lines.append(f"{pred}({args}).")
    return "\n".join(lines)


def goal_of(rec: dict) -> str:
    """The query, with any leading `\\+` stripped.

    `test.raw` is the *directive* a SARA case states, which for a negated case
    is `\\+ Goal`.  The two systems are compared on the goal itself, so that a
    discrepancy is reported against the predicate under test rather than
    against its negation; `test.expected` is already the goal's truth.
    """
    raw = rec["test"]["raw"].strip()
    if raw.startswith(r"\+"):
        raw = raw[2:].strip()
        if raw.startswith("(") and raw.endswith(")"):
            raw = raw[1:-1].strip()
    return raw


def render_program(rec: dict, statutes: Path | None = None,
                   harness: Path | None = None, header: str = "") -> str:
    """A world model as a program that runs on its own.

    Paths to the statutes and the harness are written relative to the file
    when it lands inside the repository, so a test-case directory can be moved
    or read without a runner to explain it.
    """
    statutes = statutes or (COVERED / "init")
    harness = harness or HARNESS
    # An injected conclusion is an extra clause only where the predicate is
    # declared `discontiguous`; without that, SWI takes the file as redefining
    # it and discards the statute's own clauses, which 3 of the 376 cases rely
    # on.  The flag travels with the world model, so a case keeps its seed's
    # reading.
    decls = "\n".join(f":- discontiguous {k}."
                      for k in rec.get("discontiguous", []))
    # Every header line is commented, continuation lines included: six of SARA's
    # queries are conjunctions that wrap, and one uncommented line swallows the
    # file up to the next full stop, `ensure_loaded` included.
    head = "\n".join(l if l.startswith("%") else "% " + l
                      for l in header.rstrip().splitlines())
    return "\n".join(x for x in [
        head,
        decls,
        f":- ensure_loaded('{statutes}').",
        "",
        "% ---- the world -------------------------------------------------",
        render_facts(rec),
        "",
        "% ---- the query -------------------------------------------------",
        # Parenthesised: six cases state a conjunction, and without them
        # `sara_goal(A, B)` is a different predicate the harness never finds.
        f"sara_goal(({goal_of(rec)})).",
        "",
        f":- ensure_loaded('{harness}').",
        "",
    ] if x is not None) + ""


# --------------------------------------------------------------- running it

VERDICT_RE = re.compile(r"^VERDICT (true|false|error)$", re.M)


def run_program(path: Path, cov: Path | None = None, trace: Path | None = None,
                timeout: int = 120) -> tuple[str, set, str]:
    """(verdict, branch points reached, stderr) for one `prolog.pl` on disk.

    verdict is `true`, `false`, `error` (the query raised), `timeout` or
    `crash` (SWI itself died, or printed no verdict).
    """
    env = dict(os.environ)
    env.pop("SARA_COV", None)
    env.pop("SARA_TRACE", None)
    if cov is not None:
        env["SARA_COV"] = str(cov)
    if trace is not None:
        env["SARA_TRACE"] = str(trace)
    env["SARA_LIMIT"] = str(max(1, timeout - 5))
    # Its own session, so a timeout can kill the whole process group.
    # `subprocess.run(timeout=)` kills only the immediate child, then blocks in
    # `communicate()` until every writer to the pipe is gone.
    proc = subprocess.Popen(
        [str(SWIPL), "-q", "-f", str(path), "-g", "main", "-t", "halt"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return "timeout", set(), "swipl exceeded %ds" % timeout
    m = VERDICT_RE.search(out)
    points = set()
    if cov is not None and Path(cov).exists():
        points = set(Path(cov).read_text().split())
    return (m.group(1) if m else "crash"), points, err[-4000:]


def run_world(rec: dict, tag: str, coverage_on: bool = True,
              timeout: int = 60) -> tuple[str, set]:
    """Render a world model to a scratch file and run it.  Used by generation
    and by minimisation, where nothing is meant to survive on disk."""
    work = SCRATCH / f"p{os.getpid()}"
    work.mkdir(parents=True, exist_ok=True)
    src = work / f"{tag}.pl"
    cov = work / f"{tag}.cov" if coverage_on else None
    src.write_text(render_program(rec))
    try:
        verdict, points, _ = run_program(src, cov=cov, timeout=timeout)
    finally:
        src.unlink(missing_ok=True)
        if cov is not None:
            cov.unlink(missing_ok=True)
    return verdict, points


# ------------------------------------------------------- many worlds at once

_BATCH_DRIVER = """
:- ensure_loaded('{init}').
:- use_module(library(time)).
:- ensure_loaded('{worlds}').
% events.pl declares the input predicates `discontiguous`, which makes them
% static procedures with no clauses; asserting a world into them is refused
% until they are made dynamic.
:- forall(member(P-A, {clear}), dynamic(P/A)).

main :-
    forall(world(Id, Facts, Goal), run_world(Id, Facts, Goal)),
    dump_cov('{cov}').

run_world(Id, Facts, goal(Name, Args0)) :-
    forall(member(f(P, As), Facts), ( G =.. [P|As], assertz(G) )),
    maplist(freshen, Args0, Args),
    G2 =.. [Name|Args],
    reset_cov,
    % A raised goal and a timed-out goal are NOT `false`.  Folding them into
    % `false`, which this did first, selects a world whose verdict the standalone
    % `prolog.pl` then contradicts -- caught by the on-disk verification pass,
    % which is what it is there for.  `batch_run` keeps only true/false, so an
    % `error` world is simply not selected.
    (   catch(call_with_time_limit({limit}, ( G2 -> R = true ; R = false )),
              _, R = error)
    ->  true
    ;   R = error ),
    cov_signature(H),
    format("~w ~w ~w~n", [Id, R, H]),
    forall(member(P-A, {clear}), ( functor(C, P, A), retractall(C) )).

freshen('$free', _) :- !.
freshen(X, X).
"""


def batch_run(recs: list, inputs: list, tag: str,
              limit: int = 5, timeout: int = 1800) -> tuple[dict, set, str]:
    """Run many worlds in one SWI process; return {index: (verdict, path)}.

    One process asserting and retracting thousands of small worlds is three
    orders of magnitude cheaper than one process per world, which is what
    makes enumerating a predicate's whole input space affordable.  It only
    works where every world is built from the same input predicates and
    injects nothing --- an injection's meaning depends on a `discontiguous`
    declaration made before the statutes load, which is a property of the
    file, not of a runtime assert.  Seeds and mutants therefore go through
    `run_world` instead.

    `path` is `cov_signature/1`: a hash of the set of branch points the world
    reached.  Two worlds with the same path drove the statutes through exactly
    the same decisions and cannot tell the two systems apart --- which is also
    why the batch's *union* of points is the union over the kept
    representatives: equal path, equal point set.
    """
    work = SCRATCH / f"b{os.getpid()}"
    work.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, rec in enumerate(recs):
        types = {**table_for(rec.get("id")), **rec.get("value_kinds", {})}
        facts = []
        for pred in sorted(rec["events"]):
            for row in rec["events"][pred]:
                args = ",".join(render_value(types, pred, j, v)
                                for j, v in enumerate(row))
                facts.append(f"f({pred},[{args}])")
        g = rec["test"]["goals"][0]
        gargs = ",".join("'$free'" if a.strip() in ("_", "") else a.strip()
                         for a in g["args"])
        lines.append("world(%d,[%s],goal(%s,[%s]))."
                     % (i, ",".join(facts), g["predicate"], gargs))
    worlds = work / f"{tag}_worlds.pl"
    worlds.write_text("\n".join(lines) + "\n")
    clear = "[" + ",".join(f"{p.split('/')[0]}-{p.split('/')[1]}"
                           for p in inputs) + "]"
    driver = work / f"{tag}_driver.pl"
    cov = work / f"{tag}.cov"
    driver.write_text(_BATCH_DRIVER.format(
        init=COVERED / "init", worlds=worlds, clear=clear, limit=limit,
        cov=cov))
    try:
        proc = subprocess.run(
            [str(SWIPL), "-q", "-f", str(driver), "-g", "main", "-t", "halt"],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {}, set(), f"swipl exceeded {timeout}s"
    finally:
        worlds.unlink(missing_ok=True)
        driver.unlink(missing_ok=True)
    out = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] in ("true", "false"):
            out[int(parts[0])] = (parts[1], parts[2])
    points = set(cov.read_text().split()) if cov.exists() else set()
    cov.unlink(missing_ok=True)
    return out, points, proc.stderr[-2000:]


# ---------------------------------------------------------------- the seeds

def load_discontiguous() -> dict:
    """case id -> the `discontiguous` declarations its Prolog file makes."""
    if not DISCONTIGUOUS.exists():
        DISCONTIGUOUS.parent.mkdir(parents=True, exist_ok=True)
        out = {}
        for path in sorted(RAW_CASES.glob("*.pl")):
            out[path.stem] = sorted(
                f"{n}/{a}" for n, a in
                re.findall(r"discontiguous\s+([a-z_0-9]+)/(\d+)",
                           path.read_text()))
        DISCONTIGUOUS.write_text(json.dumps(out, indent=1))
    return json.loads(DISCONTIGUOUS.read_text())


def load_seeds() -> list:
    """SARA's 376 cases as world models, each carrying its own declarations
    and its own reading of the values SARA quotes inconsistently."""
    from .value_types import load
    disc = load_discontiguous()
    per_case = load().get("per_case", {})
    recs = []
    for path in sorted(GROUNDED.glob("*.json")):
        rec = json.loads(path.read_text())
        rec["discontiguous"] = disc.get(rec["id"], [])
        rec["value_kinds"] = per_case.get(rec["id"], {})
        recs.append(rec)
    return recs


__all__ = ["render_facts", "render_program", "run_program", "run_world",
           "batch_run", "goal_of", "load_seeds"]
