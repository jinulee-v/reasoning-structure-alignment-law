#!/usr/bin/env python3
"""Recover the atom/string distinction the grounder erased.

SARA writes `purpose_(alice_pays,alice_employer)` with an atom and
`purpose_(alice_employer,"walking her dog")` with a string, and the statutes
compare both with `==`, so the two are different terms.  `json_write_dict`
renders atom and string alike, so sara_port/build/cases_grounded/*.json cannot tell
them apart; this reads the distinction back off the raw case sources.

It matters twice over:

  * the closed vocabularies (`"agricultural labor"`, `"cash"`, `"private
    home"`) are strings, and matching an *atom* of the same spelling against
    them makes the port answer a question the statutes would have refused;
  * six values are quoted inconsistently by SARA itself -- `usa`, `baltimore`,
    `maryland`, `virginia`, `arlington`, `disability`, all in `location_/2` and
    `reason_/2` -- so the table is kept per case as well as globally.

    python3 sara_scripts/generate_test_cases.py --build   # rebuilds it
"""
from __future__ import annotations

import json
import re

from .paths import RAW_CASES, VALUE_TYPES as OUT, rel

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
BARE_ATOM_RE = re.compile(r"^[a-z][a-zA-Z0-9_]*$")
VAR_RE = re.compile(r"^_VAR\d+$")


def build() -> dict:
    from .grounding import split_case, split_top_level

    seen: dict[str, set] = {}
    per_case: dict[str, dict] = {}
    for path in sorted(RAW_CASES.glob("*.pl")):
        _, _, facts = split_case(path.read_text())
        buf = ""
        for line in facts.splitlines():
            line = line.split("%")[0].strip()
            if not line:
                continue
            buf = (buf + " " + line).strip()
            if not buf.endswith("."):
                continue
            term, buf = buf[:-1].strip(), ""
            if ":-" in term:
                continue          # a case-defined rule; its expansion is in the JSON
            m = re.match(r"^([a-z][A-Za-z0-9_]*)\((.*)\)$", term, re.S)
            if not m:
                continue
            pred, args = m.group(1), split_top_level(m.group(2))
            for pos, arg in enumerate(args):
                arg = arg.strip()
                if arg.startswith('"'):
                    kind, value = "str", arg[1:-1]
                elif arg.startswith("'"):
                    kind, value = "atom", arg[1:-1]
                elif re.match(r"^-?\d+$", arg) or re.match(r"^[A-Z_]", arg):
                    continue
                else:
                    kind, value = "atom", arg
                key = f"{pred}\t{pos}\t{value}"
                seen.setdefault(key, set()).add(kind)
                per_case.setdefault(path.stem, {})[key] = kind

    table, conflicts = {}, []
    for key, kinds in sorted(seen.items()):
        if len(kinds) > 1:
            conflicts.append(key)
            table[key] = "str"
        else:
            table[key] = kinds.pop()
    ambiguous = set(conflicts)
    per_case = {cid: {k: v for k, v in tab.items() if k in ambiguous}
                for cid, tab in per_case.items()}
    return {"types": table, "conflicts": conflicts,
            "per_case": {k: v for k, v in per_case.items() if v}}


_CACHE: dict | None = None


def load() -> dict:
    global _CACHE
    if _CACHE is None:
        if not OUT.exists():
            OUT.write_text(json.dumps(build(), indent=1))
        _CACHE = json.loads(OUT.read_text())
    return _CACHE


def table_for(case_id: str | None = None) -> dict:
    """The global table, with the case's own reading of the six ambiguous
    values layered on top."""
    d = load()
    if case_id and case_id in d.get("per_case", {}):
        return {**d["types"], **d["per_case"][case_id]}
    return d["types"]


def kind_of(types: dict, pred: str, pos: int, value) -> str:
    """'int' | 'var' | 'str' | 'atom' for one fact argument."""
    if isinstance(value, bool):
        return "atom"
    if isinstance(value, int):
        return "int"
    s = str(value)
    if VAR_RE.match(s) or s == "_":
        return "var"
    kind = types.get(f"{pred}\t{pos}\t{s}")
    if kind:
        return kind
    # Unseen value -- one a case-defined rule generated, or one the fuzzer
    # invented.  Dates and anything that is not a legal bare atom are strings,
    # which is how every such value is written upstream.
    if DATE_RE.match(s) or not BARE_ATOM_RE.match(s):
        return "str"
    return "atom"


def main() -> int:
    d = build()
    OUT.write_text(json.dumps(d, indent=1))
    print(f"{len(d['types'])} typed values -> {rel(OUT)}")
    print(f"  quoted inconsistently by SARA: {len(d['conflicts'])}")
    for c in d["conflicts"]:
        pred, pos, value = c.split("\t")
        print(f"    {pred} pos {pos}: {value}")
    return 0
