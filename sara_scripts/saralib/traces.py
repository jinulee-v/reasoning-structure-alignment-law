"""Both systems' reasoning, rendered for a reader.

A discrepancy report that says only `prolog=true catala=false` moves the work
of finding out *why* onto whoever reads it.  Both systems can be made to say
what they did, and both say it in a form nobody wants to read raw --- SWI's
`trace/0` is interactive and unfiltered, and `catala interpret --trace` prints
the entire world model at every step.  This module turns each into a short
indented account of the decisions that were actually taken.

**Prolog.**  The instrumented statutes record, in order, every goal position
they call (`:c`), every one that then has no solution (`:f`), and every clause
body that runs to its end (`:e`).  Each point carries the statute file and the
line of the clause it sits in, so the sequence can be read back as: which
clause of which section was entered, what it tried, and what failed.  Nesting
is reconstructed from the enclosing predicate changing --- exact except across
a directly recursive call, where two activations of one predicate share a
frame.

**Catala.**  The interpreter's JSON trace is a flat event stream of scope calls
and variable definitions.  Scope calls give the tree; the `law_headings` on
each decision give the article of the statute it came from; the world model,
which appears in full at every scope boundary, is dropped.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import coverage

MARKS = {"c": "✓", "f": "✗", "e": "◆"}
MAX_EVENTS = 4000

# `utils.pl` predicates that are date plumbing rather than statute.  Unfolded,
# they are most of any trace --- every comparison of two days expands into two
# string splits and a timestamp --- and none of it is a decision anybody reads
# a report to see.  The call to them still appears in the caller's frame, with
# its outcome, so nothing is hidden; only the arithmetic underneath it is.
PLUMBING = {"day_to_stamp", "is_before", "first_day_year", "last_day_year",
            "duration", "day_of_week"}


def read_points(path: Path, limit: int = 400_000) -> tuple[list, bool]:
    """The ordered point sequence, and whether it was cut short."""
    if not Path(path).exists():
        return [], False
    seq = Path(path).read_text().split()
    return (seq[:limit], len(seq) > limit)


def _collapse(seq: list) -> list:
    """Pair each `:c` with its own `:f`, so a failed goal is one line, not two.

    A goal that was called and had no solution shows up as two points at the
    same position.  Scanning forward from the call to the next event at that
    position tells the two apart: an `f` before any re-entry means this
    activation failed.
    """
    kinds, prefixes = [], []
    for pt in seq:
        prefix, kind = pt.rsplit(":", 1)
        prefixes.append(prefix)
        kinds.append(kind)
    consumed = set()
    out = []
    for i, pt in enumerate(seq):
        if i in consumed:
            continue
        if kinds[i] != "c":
            out.append((prefixes[i], kinds[i]))
            continue
        failed = False
        for j in range(i + 1, len(seq)):
            if prefixes[j] != prefixes[i]:
                continue
            if kinds[j] == "f":
                failed, consumed = True, consumed | {j}
            break
        out.append((prefixes[i], "f" if failed else "c"))
    return out


def prolog_trace(seq: list, max_events: int = MAX_EVENTS,
                 full: bool = False) -> str:
    """The point sequence as an indented account of the statutes' reasoning.

    Variable names are the instrumented build's (`A`, `B`, ...), not SARA's:
    the goal text is read back out of a `portray_clause`d source, which
    renumbers them.  Sharing between positions in one clause is preserved, so
    the same letter still means the same variable.
    """
    if not seq:
        return "(no trace: the query reached no instrumented goal)"
    events = _collapse(seq)
    truncated = len(events) > max_events
    events = events[:max_events]

    lines, stack = [], []
    for prefix, kind in events:
        info = coverage.describe(prefix + ":" + kind)
        pred = info["predicate"]
        if not full and pred in PLUMBING:
            continue
        if pred in stack:
            del stack[stack.index(pred) + 1:]
        else:
            stack.append(pred)
            lines.append("%s→ %s   (%s:%d)"
                         % ("  " * (len(stack) - 1), pred,
                            info["file"], info["line"]))
        pad = "  " * len(stack)
        if kind == "e":
            lines.append(f"{pad}◆ clause succeeded   ({info['file']}:"
                         f"{info['line']})")
        else:
            goal = info["goal"] or "(goal not recovered)"
            lines.append(f"{pad}{MARKS[kind]} {goal}")
    if truncated:
        lines.append(f"... trace truncated at {max_events} steps")
    return "\n".join(lines)


def prolog_failure_frontier(seq: list, limit: int = 12) -> list:
    """The goals that failed deepest into the derivation.

    When the two systems disagree, this is usually the answer: the statute
    goal Prolog could not satisfy and the port evidently could, or the reverse.
    Reported as the last distinct failing positions, most recent first, since
    the tail of the trace is where the query was decided.
    """
    seen, out = set(), []
    for prefix, kind in reversed(_collapse(seq)):
        if kind != "f" or prefix in seen:
            continue
        seen.add(prefix)
        info = coverage.describe(prefix + ":f")
        out.append(info)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- Catala

SKIP_SUFFIX = (".input",)
_VALUE_CHARS = 200

# Layer-0 scaffolding every generated case computes whether or not its query
# looks at it: the kinship closures, and the case's own world and injections.
# Ten scope calls and a full world dump before the first statute is reached is
# not reasoning, it is setup.
QUIET_SCOPES = {"Kinships.direct", "InLaws.direct"}
QUIET_VARS = {"Run.world", "Run.injections", "Run.child_of", "Run.sibling_of",
              "Run.descendent_of", "Run.stepsibling_of", "Run.stepparent_of",
              "Run.child_in_law_of", "Run.parent_in_law_of",
              "Run.sibling_in_law_of"}


def _brief(value) -> str:
    s = json.dumps(value, separators=(",", ":")) if not isinstance(value, str) \
        else value
    s = " ".join(s.split())
    return s if len(s) <= _VALUE_CHARS else s[:_VALUE_CHARS] + " ..."


def catala_trace(path: Path, max_events: int = MAX_EVENTS,
                 full: bool = False) -> str:
    """The interpreter's JSON trace as an indented account of the port's
    reasoning: which scope was entered, under which article of the statute,
    and what it concluded."""
    p = Path(path)
    if not p.exists():
        return "(no trace: the interpreter produced none)"
    try:
        events = json.loads(p.read_text())
    except json.JSONDecodeError:
        return "(no trace: the interpreter's trace was not valid JSON)"

    lines, depth, heading, muted, shown = [], 0, None, 0, 0
    scaffolding = 0
    for ev in events:
        kind = ev.get("event")
        if muted:
            if kind == "BeginCall":
                muted += 1
            elif kind == "EndCall":
                muted -= 1
            continue
        if kind == "DecisionTaken":
            heads = ev.get("pos", {}).get("law_headings") or []
            # The outermost heading is the generated case's own title, which
            # says nothing; the statute articles are the inner ones.
            heads = [h for h in heads if not h.startswith("Case ")] or heads
            new = " / ".join(heads[-2:])
            if new and new != heading and (full or not new.startswith("Case ")):
                heading = new
                lines.append("%s§ %s" % ("  " * depth, new))
            continue
        if kind == "BeginCall":
            name = ev.get("name", "?")
            if not full and name in QUIET_SCOPES:
                muted, scaffolding = 1, scaffolding + 1
                continue
            lines.append("%s→ %s" % ("  " * depth, name))
            depth += 1
            continue
        if kind == "EndCall":
            depth = max(0, depth - 1)
            continue
        if kind == "VariableDefinition":
            name = ev.get("name", "?")
            if name.endswith(SKIP_SUFFIX):
                continue
            if not full and name in QUIET_VARS:
                continue
            lines.append("%s≔ %s = %s"
                         % ("  " * depth, name, _brief(ev.get("value"))))
            shown += 1
            if shown >= max_events:
                lines.append("... trace truncated at %d definitions" % max_events)
                break
    if scaffolding:
        lines.insert(0, f"({scaffolding} Layer-0 scaffolding calls elided: "
                        "the kinship closures and the world model)")
    return "\n".join(lines) if lines else "(no trace events)"
