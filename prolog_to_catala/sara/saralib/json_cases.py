"""Turn a generated SARA seed world into the gold wrapper's JSON input.

The Catala case emitter is authoritative for symbol IDs and fact grouping. This
module decodes its literals so a model adapter can replay a case through a JSON
scope without guessing IDs or changing the original Catala test program.
"""
from __future__ import annotations

import re

from .catala_emit import (EVENT_CATEGORY_ROLES, EVENT_FIELDS,
                          OPTIONAL_CATEGORY_ROLES, OPTIONAL_EVENT_FIELDS,
                          ROLE_FACTS, ROLE_FIELDS, Symbols,
                          build_events, build_injections, entity_lit,
                          _discontiguous_table)
from .value_types import table_for


ENTITY = re.compile(r"W\.Entity \{ -- id: (-?\d+) -- tag: W\.EntityTag\.([A-Za-z]+) \}")
INJECTION = re.compile(
    r"W\.Injection \{ -- pred: (-?\d+)"
    r" -- replaces_statute: (true|false)"
    r" -- arguments: W\.InjectionArguments\.Args([1-8]) content"
    r" \(W\.InjectionArgs\3 \{ (.*) \}\) \}"
)
INJECTION_FIELD = re.compile(
    r"-- (one|two|three|four|five|six|seven|eight): (-?\d+)"
)
INJECTION_DATE_FIELD = re.compile(
    r"-- (three_date|four_date|five_date|six_date): "
    r"(Absent|Present content \(\|([^|]+)\|\))"
)


def _entity(literal: str) -> dict:
    match = ENTITY.fullmatch(literal.strip())
    if not match:
        raise ValueError(f"unrecognized SARA entity literal: {literal}")
    return {"id": match[1], "tag": match[2]}


def _date(literal: str) -> dict:
    year, month, day = map(int, literal.strip("| ").split("-"))
    return {"year": year, "month": month, "day": day}


def _values(literal: str, field: str) -> list:
    body = literal.strip()
    if not (body.startswith("[") and body.endswith("]")):
        raise ValueError(f"not a SARA list literal: {literal}")
    body = body[1:-1].strip()
    if not body:
        return []
    values = []
    for item in body.split("; "):
        item = item.strip()
        if field in {"agents", "patients", "reasons", "beneficiaries", "countries"}:
            values.append(_entity(item))
        elif field in {"starts", "ends"}:
            values.append(_date(item))
        elif field == "amounts":
            match = re.fullmatch(r"\(money of (-?\d+)\)", item)
            if not match:
                raise ValueError(f"unrecognized SARA money literal: {item}")
            values.append(match[1])
        else:
            enum_type = {"purposes": "Purpose", "types": "Purpose", "places": "Place",
                         "destinations": "Place", "media": "Medium"}[field]
            prefix = f"W.{enum_type}."
            if not item.startswith(prefix):
                raise ValueError(f"unrecognized SARA enum literal: {item}")
            value = item[len(prefix):]
            if " content (" in value:
                constructor, payload = value.split(" content (", 1)
                values.append({constructor: _entity(payload[:-1])})
            else:
                values.append(value)
    return values


def _optional_value(literal: str, field: str):
    """Decode the Catala optional emitted for a corpus-bounded event role."""
    body = literal.strip()
    if body == "Absent":
        return None
    prefix = "Present content ("
    if not (body.startswith(prefix) and body.endswith(")")):
        raise ValueError(f"not a SARA optional literal: {literal}")
    values = _values("[" + body[len(prefix):-1] + "]", field)
    if len(values) != 1:
        raise ValueError(f"invalid SARA optional payload: {literal}")
    return values[0]


def _event(literal: str, roles=None, optional_roles=()) -> dict:
    fields = {}
    for line in literal.splitlines():
        match = re.match(r"\s*-- ([a-z_]+): (.*)$", line)
        if match:
            value = match[2].strip()
            # The constructor's closing brace follows whichever field is last.
            # An `ident` value already ends in the Entity's own ` }`, so only
            # strip it there when a second brace closes an ident-only record.
            if ((match[1] == "ident" and value.endswith(" } }"))
                    or (match[1] != "ident" and value.endswith(" }"))):
                value = value[:-2]
            fields[match[1]] = value
    all_roles = tuple(ROLE_FIELDS.values())
    required = {"ident", *(all_roles if roles is None else roles)}
    if set(fields) != required:
        raise ValueError(f"incomplete SARA event literal: {set(fields) ^ required}")
    return {
        name: (_entity(value) if name == "ident" else
               _optional_value(value, name) if name in optional_roles else
               _values(value, name))
        for name, value in fields.items()
    }


def _optional_event(literals: list[str], field: str, roles, optional_roles):
    if len(literals) > 1:
        raise ValueError(
            f"world has {len(literals)} events for 0-or-1 category {field!r}")
    return (None if not literals
            else _event(literals[0], roles, optional_roles))


def _income_event(literal: str) -> dict:
    match = re.fullmatch(
        r"W\.IncomeEvent \{ -- agent: (W\.Entity \{.*?\})"
        r" -- start: (\|[^|]+\|) -- amount: \(money of (-?\d+)\) \}",
        literal.strip(),
    )
    if not match:
        raise ValueError(f"incomplete SARA income occurrence: {literal}")
    return {
        "agent": _entity(match[1]),
        "start": _date(match[2]),
        "amount": match[3],
    }


def _deduction_event(literal: str) -> dict:
    """Decode the typed quotient of deduction facts used by the statutes."""
    prefix = "W.DeductionEvent {\n        -- agents: "
    separator = "\n        -- evidence: "
    body = literal.strip()
    if not body.startswith(prefix) or separator not in body or not body.endswith(" }"):
        raise ValueError(f"unrecognized SARA deduction event: {literal}")
    agents_literal, evidence_literal = body[len(prefix):-2].split(separator, 1)
    agents = _values(agents_literal, "agents")
    if evidence_literal == "W.DeductionEvidence.Undated":
        evidence = "Undated"
    else:
        claim_prefix = "W.DeductionEvidence.DatedClaim content ("
        amount_prefix = "W.DeductionEvidence.DatedAmount content (W.DeductionOccurrence {"
        if evidence_literal.startswith(claim_prefix) and evidence_literal.endswith(")"):
            evidence = {
                "DatedClaim": _date(evidence_literal[len(claim_prefix):-1])
            }
        elif evidence_literal.startswith(amount_prefix) and evidence_literal.endswith(" })"):
            occurrence = evidence_literal[len(amount_prefix):-3].strip()
            match = re.fullmatch(
                r"-- start: (\|[^|]+\|) -- amount: \(money of (-?\d+)\)",
                occurrence,
            )
            if not match:
                raise ValueError(f"invalid SARA dated deduction: {literal}")
            evidence = {
                "DatedAmount": {
                    "start": _date(match[1]),
                    "amount": match[2],
                }
            }
        else:
            raise ValueError(f"invalid SARA deduction evidence: {literal}")
    return {"agents": agents, "evidence": evidence}


def _role_fact(literal: str, role: str) -> dict:
    match = re.fullmatch(
        r"W\.[A-Za-z]+Fact \{ -- subject: (W\.Entity \{.*?\})"
        r" -- value: (.*?) \}", literal.strip())
    if not match:
        raise ValueError(f"unrecognized SARA {role} fact literal: {literal}")
    values = _values(f"[{match[2]}]", role)
    if len(values) != 1:
        raise ValueError(f"invalid SARA {role} fact literal: {literal}")
    return {"subject": _entity(match[1]), "value": values[0]}


def _injections(literals: list[str]) -> list[dict]:
    """Decode the fixed injection-key tuples used by the gold wrapper."""
    injections = []
    names = ("one", "two", "three", "four", "five", "six", "seven", "eight")
    for literal in literals:
        match = INJECTION.fullmatch(literal)
        if not match:
            raise ValueError(f"unrecognized SARA injection literal: {literal}")
        fields = {name: int(value)
                  for name, value in INJECTION_FIELD.findall(match[4])}
        arity = int(match[3])
        if set(fields) != set(names[:arity]):
            raise ValueError(f"incomplete SARA injection tuple: {literal}")
        expected_dates = {
            4: ("three_date", "four_date"),
            5: ("four_date",),
            6: ("five_date", "six_date"),
        }.get(arity, ())
        dates = {}
        for name, raw, payload in INJECTION_DATE_FIELD.findall(match[4]):
            dates[name] = None if raw == "Absent" else _date(f"|{payload}|")
        if set(dates) != set(expected_dates):
            raise ValueError(f"incomplete SARA injection dates: {literal}")
        injections.append({
            "pred": int(match[1]),
            "replaces_statute": match[2] == "true",
            "arguments": {f"Args{arity}": {**fields, **dates}},
        })
    return injections


def wrapper_input_for_seed(meta: dict, symbol_table: dict[str, int]) -> dict:
    """Build a gold wrapper-compatible input for a directly mapped seed."""
    goal = meta["test"]["goals"][0]
    if meta["query"] not in {"tax/3", "s152_c_1/3", "s152_a/5", "s3301/6",
                             "s1_a/4", "s1_b/4", "s1_c/4", "s1_d/5",
                             "s151_a/3", "s63_a/5", "s63_b/4"}:
        raise ValueError(f"no direct wrapper equivalent for {meta['query']}")
    symbols = Symbols()
    symbols.table = dict(symbol_table)
    types = {**table_for(meta["id"]), **meta.get("value_kinds", {})}
    event_literals, universal_literals = build_events(symbols, meta["events"], types)
    discontiguous = meta.get("discontiguous")
    if discontiguous is None:
        discontiguous = _discontiguous_table().get(meta["id"], ())
    injection_literals = build_injections(symbols, meta["other"], discontiguous)
    injections = _injections(injection_literals)
    if meta["query"] == "tax/3":
        taxpayer, year, _claimed = goal["args"]
        extra = {}
    elif meta["query"] in {"s152_c_1/3", "s152_a/5"}:
        dependent, taxpayer, year = goal["args"][:3]
        extra = {"candidate_dependent": _entity(entity_lit(symbols, dependent))}
    elif meta["query"] == "s1_d/5":
        taxpayer, _spouse, year = goal["args"][:3]
        extra = {}
    elif meta["query"] == "s151_a/3":
        taxpayer, _claimed, year = goal["args"]
        extra = {"exempt_individual": _entity(entity_lit(symbols, taxpayer))}
    else:
        taxpayer, year = goal["args"][:2]
        extra = {}
    return {
        "world": {
            **{
                field: ([_income_event(literal)
                         for literal in event_literals[field]]
                        if pred == "income_" else
                        [_deduction_event(literal)
                         for literal in event_literals[field]]
                        if pred == "deduction_" else
                        _optional_event(
                            event_literals[field], field, roles,
                            {role for role in roles
                             if (pred, role) in OPTIONAL_CATEGORY_ROLES})
                        if field in OPTIONAL_EVENT_FIELDS
                        else [_event(
                                  literal, roles,
                                  {role for role in roles
                                   if (pred, role) in OPTIONAL_CATEGORY_ROLES})
                              for literal in event_literals[field]])
                for pred in EVENT_FIELDS
                for field, roles in [(EVENT_FIELDS[pred],
                                      EVENT_CATEGORY_ROLES[pred])]
            },
            **{
                field: [_role_fact(literal, role)
                        for literal in event_literals[field]]
                for role, (_, field) in ROLE_FACTS.items()
            },
            "universal_purposes": _values(
                "[" + "; ".join(universal_literals) + "]", "purposes"),
        },
        "injections": injections,
        ("employer" if meta["query"] == "s3301/6" else "taxpayer"):
            _entity(entity_lit(symbols, taxpayer)),
        ("calendar_year" if meta["query"] == "s3301/6" else "taxable_year"):
            str(year),
        **extra,
    }
