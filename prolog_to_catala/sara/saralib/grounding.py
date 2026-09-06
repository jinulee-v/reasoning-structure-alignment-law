#!/usr/bin/env python3
"""Ground every SARA case into a language-neutral JSON world model.

SARA cases are not plain fact sets: several of them define *rules* that generate
an unbounded-looking family of events, e.g.

    bob_household_maintenance(Year,Event,Start,End) :-
        between(2004,2019,Year), atom_concat('bob_maintains_household_',Year,Event), ...
    payment_(Event) :- bob_household_maintenance(_,Event,_,_).

Those extensions are always finite, so rather than reimplementing Prolog we let
SWI compute them: load the case's fact section (with the `% Test` directives
stripped, since they end in `halt/0`), then `findall/3` over each of the 57
case-input event predicates.

The 4 predicates that events.pl declares but utils.pl *defines*
(first_day_year/2, last_day_year/2, is_before/2, gross_income/3) are derived,
not input, and are deliberately excluded.

Output: one JSON per case under .port/sara/build/cases_grounded/, holding the NL text,
the question, the parsed test goal with its expected verdict, and the fully
ground event base.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from .paths import (BUILD, RAW, RAW_CASES as CASES, RAW_STATUTES, STATUTES,
                    SWIPL, GROUNDED as OUT)


def rundir() -> Path:
    """A directory in which `statutes/prolog` names the compat build.

    SARA's case files open with `:- ['statutes/prolog/init'].`, resolved
    against the working directory, so grounding a case unedited means running
    it somewhere that spelling points at the statutes we mean.  The spelling
    is upstream's and stays as it is wherever the corpus itself now lives.
    """
    d = BUILD / "rt"
    (d / "statutes").mkdir(parents=True, exist_ok=True)
    link = d / "statutes/prolog"
    # Repoint an existing link: it holds an absolute path from an earlier run,
    # and a moved tree leaves it dangling.  Prolog does not fail on the missing
    # consult, it just answers false for every case.
    try:
        link.symlink_to(STATUTES)
    except FileExistsError:
        if not link.is_symlink() or link.readlink() != STATUTES:
            tmp = link.with_name(f"prolog.new{os.getpid()}")
            tmp.symlink_to(STATUTES)
            tmp.replace(link)     # atomic: another thread may be consulting it
    return d

DERIVED = {"first_day_year/2", "last_day_year/2", "is_before/2", "gross_income/3"}


def input_predicates() -> list[tuple[str, int]]:
    """The event predicates a case may supply: declared in events.pl, not defined
    by the statute files."""
    decl = (RAW_STATUTES / "events.pl").read_text()
    preds = re.findall(r"discontiguous\s+([a-z_0-9]+)/(\d+)", decl)
    return [(n, int(a)) for n, a in preds if f"{n}/{a}" not in DERIVED]


def split_case(text: str) -> tuple[str, str, str]:
    """Return (nl_text, question, facts_section) for one case file."""
    def section(name: str) -> str:
        m = re.search(rf"^% {name}\n(.*?)(?=^% |\Z)", text, re.S | re.M)
        return m.group(1) if m else ""

    nl = "\n".join(
        line.lstrip("% ").rstrip() for line in section("Text").splitlines()
        if line.startswith("%")
    ).strip()
    q = "\n".join(
        line.lstrip("% ").rstrip() for line in section("Question").splitlines()
        if line.startswith("%")
    ).strip()
    return nl, q, section("Facts")


def split_top_level(s: str, sep: str = ",") -> list[str]:
    """Split on `sep` at paren/bracket depth 0, respecting quotes."""
    out, buf, depth, q, i = [], [], 0, None, 0
    while i < len(s):
        c = s[i]
        if q:
            if c == "\\":
                buf.append(s[i:i + 2]); i += 2; continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == sep and depth == 0:
            out.append("".join(buf).strip()); buf = []; i += 1; continue
        buf.append(c); i += 1
    if "".join(buf).strip():
        out.append("".join(buf).strip())
    return out


def parse_test(text: str) -> dict:
    """Parse the `% Test` directive into a conjunction of goals + expected verdict.

    Most cases are a single goal, optionally under `\\+`.  Six are conjunctions
    spanning several lines, which share variables across conjuncts (and one,
    s152_d_2_D_neg, calls var/1 directly in the test), so the directive is read
    as a whole up to its terminating period rather than line by line.
    """
    body = re.search(r"^% Test\n(.*)", text, re.S | re.M).group(1)
    directives = [d.strip() for d in re.findall(r"^:-\s*(.*?)\.\s*$", body, re.S | re.M)]
    directives = [d for d in directives if d != "halt"]
    if len(directives) != 1:
        raise ValueError(f"expected 1 test directive, got {len(directives)}")
    goal = directives[0].strip()

    negated = goal.startswith(r"\+")
    if negated:
        goal = goal[2:].strip()
    if goal.startswith("(") and goal.endswith(")"):
        goal = goal[1:-1].strip()

    goals = []
    for conjunct in split_top_level(goal):
        m = re.match(r"^([a-z][A-Za-z0-9_]*)\((.*)\)$", conjunct, re.S)
        if not m:
            raise ValueError(f"unparsed conjunct {conjunct!r}")
        goals.append({
            "predicate": m.group(1),
            "args": [a.strip() for a in split_top_level(m.group(2))],
        })

    task = "numeric" if goals[0]["predicate"] == "tax" else "entailment"
    return {
        "task": task,
        "negated": negated,
        "expected": not negated,
        "goals": goals,
        "raw": directives[0],
        # for numeric cases the gold answer is the last argument of tax/3
        "gold_amount": int(goals[0]["args"][-1]) if task == "numeric" else None,
    }


DRIVER = r"""
:- use_module(library(http/json)).
:- use_module(library(time)).
:- ['{facts}'].
:- initialization(main).

% A case may assert a fact with an unbound argument, e.g.
%     purpose_(_,"agricultural labor").
% which universally quantifies over the first argument.  Dropping that would
% silently weaken the world model, so unbound arguments are reified as "_VARn",
% numbered per row so that sharing between arguments survives the round trip.
reify(Args, Out) :-
    copy_term(Args, Out),
    term_variables(Out, Vars),
    foldl([V,I,J]>>(atom_concat('_VAR', I, V), J is I+1), Vars, 0, _).

% For a predicate the case shares with the statutes (s63/3, s7703/4, ...) the
% case is *injecting* a conclusion, and calling the predicate would run the
% statute's own clauses as well.  Enumerate only the clauses whose source is the
% case file, then solve each body to get that clause's ground extension.
case_clauses(N-A, Rows) :-
    functor(H, N, A),
    catch(
        call_with_time_limit(20,
            findall(R,
                ( clause(H, B, Ref),
                  clause_property(Ref, file('{facts}')),
                  call(B),
                  H =.. [_|Args], reify(Args, R) ),
                Rows0)),
        _, Rows0 = []),
    sort(Rows0, Rows).

collect_safe(G, Rows) :-
    catch(
        call_with_time_limit(20,
            findall(R, (call(G), G =.. [_|Args], reify(Args, R)), Rows)),
        _, Rows = []).

% A case may define a *role* predicate as a rule that only works once its
% subject is bound:
%
%     agent_(Service_event,Employee) :-
%         split_string(Service_event,"_","",[X,Y,Z]), ...
%
% Calling that with both arguments free raises an instantiation error, and
% since `findall/3` aborts on the exception the whole predicate -- including
% its plain facts -- would come back empty. The statutes never call it that
% way: by the time they reach `agent_/2` they hold an event. So the identifiers
% every unary case predicate names are collected first, and each binary
% predicate is then re-solved with its first argument bound to each of them,
% falling back to binding both where even that throws.
event_universe(Universe) :-
    findall(E,
        ( member(P-1, {spec}),
          functor(G, P, 1),
          collect_safe(G, Rows),
          member([E], Rows),
          atom(E) ),
        Es),
    sort(Es, Universe).

solve_bound(G, Rows) :-
    catch(call_with_time_limit(5,
        findall(R, (call(G), G =.. [_|Args], reify(Args, R)), Rows)),
        _, fail).

collect_bound(P, Universe, Rows) :-
    findall(R,
        ( member(E1, Universe),
          functor(G, P, 2), arg(1, G, E1),
          (   solve_bound(G, Rs)
          ->  true
          ;   findall(R2,
                  ( member(E2, Universe),
                    functor(G2, P, 2), arg(1, G2, E1), arg(2, G2, E2),
                    catch(call_with_time_limit(5, call(G2)), _, fail),
                    G2 =.. [_|Args2], reify(Args2, R2) ),
                  Rs)
          ),
          member(R, Rs) ),
        Rows).

collect(P-A, P-Rows) :-
    functor(G, P, A),
    collect_safe(G, Rows0),
    (   A =:= 2
    ->  event_universe(U), collect_bound(P, U, Rows1)
    ;   Rows1 = []
    ),
    append(Rows0, Rows1, Rows2),
    sort(Rows2, Rows),
    Rows \== [].

main :-
    findall(P-Rows, ( member(Spec, {spec}), collect(Spec, P-Rows) ), EventPairs),
    dict_pairs(Events, facts, EventPairs),
    % Everything the case file itself defines, straight from SWI's source index.
    % A case may inject the *conclusion* of a statute predicate rather than let
    % it be derived (e.g. `s152_c_1(bob,alice,2015).`), and it may define local
    % helper predicates; both matter to the port and neither is an event.
    findall(N-A,
        ( source_file(H, '{facts}'), functor(H, N, A) ), Defined0),
    sort(Defined0, Defined),
    findall(Key-Rows,
        ( member(N-A, Defined),
          \+ memberchk(N-A, {spec}),
          case_clauses(N-A, Rows),
          Rows \== [],
          format(atom(Key), '~w/~w', [N, A])
        ), OtherPairs),
    dict_pairs(Other, other, OtherPairs),
    findall(K, (member(N-A, Defined), format(atom(K), '~w/~w', [N, A])), DefKeys),
    dict_pairs(Top, top, [events-Events, other-Other, defined-DefKeys]),
    json_write_dict(current_output, Top, [width(0)]), nl,
    halt.
"""


def ground_one(case: Path, preds, tmpdir: Path, timeout: int) -> dict:
    text = case.read_text()
    nl, question, facts = split_case(text)
    test = parse_test(text)

    facts_file = tmpdir / f"{case.stem}_facts.pl"
    facts_file.write_text(facts)
    spec = "[" + ",".join(f"{n}-{a}" for n, a in preds) + "]"
    driver = tmpdir / f"{case.stem}_driver.pl"
    driver.write_text(
        DRIVER.replace("{facts}", str(facts_file)).replace("{spec}", spec)
    )

    proc = subprocess.run(
        [str(SWIPL), "-q", str(driver)],
        cwd=rundir(), capture_output=True, text=True, timeout=timeout,
    )
    start = proc.stdout.find("{")
    if start < 0:
        return {"id": case.stem, "error": proc.stderr[-2000:]}
    try:
        events = json.loads(proc.stdout[start:])
    except json.JSONDecodeError as exc:
        return {"id": case.stem,
                "error": f"unparseable JSON ({exc}): {proc.stdout[start:start+300]!r}"}
    return {
        "id": case.stem,
        "split": "",  # filled in by caller
        "text": nl,
        "question": question,
        "test": test,
        "events": events["events"],
        "defined": events["defined"],
        "other": events["other"],
        "n_facts": sum(len(v) for v in events["events"].values()),
    }


def main(jobs: int = 16, timeout: int = 120) -> int:
    """Ground every SARA case to a world model.  Called by
    `generate_test_cases.py --build`, not from a command line of its own."""
    preds = input_predicates()
    print(f"grounding over {len(preds)} case-input predicates")
    OUT.mkdir(parents=True, exist_ok=True)
    tmpdir = OUT / "_tmp"
    tmpdir.mkdir(exist_ok=True)

    splits = {}
    for name in ("train", "test"):
        for line in (RAW / "splits" / name).read_text().split():
            splits[line] = name

    cases = sorted(CASES.glob("*.pl"))
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        results = list(pool.map(
            lambda c: ground_one(c, preds, tmpdir, timeout), cases))

    bad = [r for r in results if "error" in r]
    for r in results:
        if "error" in r:
            continue
        r["split"] = splits.get(r["id"], "?")
        (OUT / f"{r['id']}.json").write_text(json.dumps(r, indent=1))

    ok = [r for r in results if "error" not in r]
    print(f"grounded {len(ok)}/{len(results)} cases")
    print(f"  total ground facts: {sum(r['n_facts'] for r in ok)}")
    print(f"  facts/case: min={min(r['n_facts'] for r in ok)} "
          f"max={max(r['n_facts'] for r in ok)} "
          f"mean={sum(r['n_facts'] for r in ok)/len(ok):.1f}")
    for r in bad:
        print(f"  [ERROR] {r['id']}: {r['error'].splitlines()[-1][:120] if r['error'] else ''}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
