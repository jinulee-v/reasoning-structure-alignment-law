#!/usr/bin/env python3
"""Regenerate SARA's category-specific Catala event input schema.

The authoritative category/role matrix lives in ``saralib.catala_emit`` so
the schema and case emitter cannot drift.  This script only owns the mechanical
Catala declarations and call-site rewrite.
"""

from pathlib import Path
import re

from saralib.catala_emit import (
    EVENT_CATEGORY_ROLES,
    EVENT_FIELDS,
    EVENT_KINDS,
    OPTIONAL_EVENT_FIELDS,
    OPTIONAL_CATEGORY_ROLES,
    ROLE_FACTS,
)


ROOT = Path(__file__).resolve().parents[2]
SARA = ROOT / "data" / "catala_gold" / "sara"
WORLD = SARA / "Section7703.catala_en"

ROLE_TYPES = {
    "agents": "list of Entity",
    "patients": "list of Entity",
    "starts": "list of date",
    "ends": "optional of date",
    "amounts": "list of money",
    "purposes": "optional of Purpose",
    "places": "list of Place",
    "media": "list of Medium",
    "reasons": "optional of Entity",
    "beneficiaries": "list of Entity",
    "countries": "optional of Entity",
    "types": "optional of Purpose",
    "destinations": "optional of Place",
}
SCALAR_ROLE_TYPES = {
    "agents": "Entity", "patients": "Entity", "starts": "date",
    "ends": "date", "amounts": "money", "purposes": "Purpose",
    "places": "Place", "media": "Medium", "reasons": "Entity",
    "beneficiaries": "Entity", "countries": "Entity", "types": "Purpose",
    "destinations": "Place",
}

def schema_block() -> str:
    out = ["""## Category-specific event records.  There is deliberately no universal event
## record: keeping irrelevant roles out of each symbolic value is essential for
## tractable concolic execution.
"""]

    for pred, constructor in EVENT_KINDS.items():
        if pred == "deduction_":
            # A deduction claim is observable before it has an amount in
            # §63(c)(6)(A), while §63(d) observes only a complete dated
            # amount.  A sum type represents exactly those observable states
            # without independent optional date/amount fields (and their
            # unobservable Cartesian combinations).
            out.extend([
                "declaration structure DeductionOccurrence:",
                "  data start content date",
                "  data amount content money",
                "",
                "declaration enumeration DeductionEvidence:",
                "  -- Undated",
                "  -- DatedClaim content date",
                "  -- DatedAmount content DeductionOccurrence",
                "",
                "declaration structure DeductionEvent:",
                "  data agents content list of Entity",
                "  data evidence content DeductionEvidence",
                "",
            ])
            continue
        out.append(f"declaration structure {constructor}Event:")
        if pred == "income_":
            # `gross_income/3` observes the Cartesian solutions of
            # income_/agent_/start_/amount_, never the partially populated
            # event identifier. One record is therefore one complete solution.
            out.extend([
                "  data agent content Entity",
                "  data start content date",
                "  data amount content money",
            ])
            out.append("")
            continue
        out.append("  data ident content Entity")
        for role in EVENT_CATEGORY_ROLES[pred]:
            role_type = (f"optional of {SCALAR_ROLE_TYPES[role]}"
                         if (pred, role) in OPTIONAL_CATEGORY_ROLES
                         else ROLE_TYPES[role])
            out.append(f"  data {role} content {role_type}")
        out.append("")

    # A role whose subject has no recognised category is a narrow binary fact,
    # not a synthetic event carrying every possible role.  This both models
    # the Prolog relation faithfully and avoids a large symbolic product.
    for role, (constructor, _) in ROLE_FACTS.items():
        value_type = ROLE_TYPES[role]
        if value_type.startswith("list of "):
            value_type = value_type.removeprefix("list of ")
        elif value_type.startswith("optional of "):
            value_type = value_type.removeprefix("optional of ")
        out.append(f"declaration structure {constructor}:")
        out.append("  data subject content Entity")
        out.append(f"  data value content {value_type}")
        out.append("")

    out.append("""## Scalar optional roles retain their scalar representation.  These helpers
## are internal compatibility views only; they do not introduce symbolic lists.
declaration date_values content list of date
  depends on value content optional of date
  equals match value with pattern
    -- Absent: []
    -- Present content x: [x]

declaration purpose_values content list of Purpose
  depends on value content optional of Purpose
  equals match value with pattern
    -- Absent: []
    -- Present content x: [x]

declaration entity_values content list of Entity
  depends on value content optional of Entity
  equals match value with pattern
    -- Absent: []
    -- Present content x: [x]

declaration place_values content list of Place
  depends on value content optional of Place
  equals match value with pattern
    -- Absent: []
    -- Present content x: [x]

## A whole case. Category multiplicity is preserved independently of payload
## shape: corpus-singleton categories are options, not bounded lists.
declaration structure World:""")
    for pred, constructor in EVENT_KINDS.items():
        field = EVENT_FIELDS[pred]
        cardinality = (f"optional of {constructor}Event"
                       if field in OPTIONAL_EVENT_FIELDS
                       else f"list of {constructor}Event")
        out.append(f"  data {field} content {cardinality}")
    for _, (constructor, field) in ROLE_FACTS.items():
        out.append(f"  data {field} content list of {constructor}")
    out.extend(["  data universal_purposes content list of Purpose", ""])

    for pred, constructor in EVENT_KINDS.items():
        field = EVENT_FIELDS[pred]
        accessor = field.removesuffix("_events") + "_event_values"
        out.append(f"declaration {accessor} content list of {constructor}Event")
        out.append("  depends on world content World")
        if field in OPTIONAL_EVENT_FIELDS:
            out.append(f"  equals match world.{field} with pattern")
            out.append("    -- Absent: []")
            out.append("    -- Present content ev: [ev]")
        else:
            out.append(f"  equals world.{field}")
        out.append("")

    people_members = []
    for role in ("agents", "patients"):
        for pred in EVENT_KINDS:
            if role not in EVENT_CATEGORY_ROLES[pred]:
                continue
            accessor = EVENT_FIELDS[pred].removesuffix("_events") + "_event_values"
            if pred == "income_" and role == "agents":
                people_members.append(
                    f"(map each ev among ({accessor} of world) to ev.agent)"
                )
                continue
            value = f"ev.{role}"
            if (pred, role) in OPTIONAL_CATEGORY_ROLES:
                scalar = SCALAR_ROLE_TYPES[role]
                helper = {
                    "Entity": "entity_values", "date": "date_values",
                    "money": "money_values", "Purpose": "purpose_values",
                    "Place": "place_values",
                }[scalar]
                value = f"({helper} of ev.{role})"
            people_members.append(
                "(combine all xs among (map each ev among "
                f"({accessor} of world) to {value}) "
                "in acc initially [] with acc ++ xs)"
            )
        fact_field = ROLE_FACTS[role][1]
        people_members.append(
            f"(map each fact among world.{fact_field} to fact.value)"
        )
    out.extend([
        "## Every person named in an entity role. Duplicates are intentional:",
        "## consumers either use existential membership or apply their own stable dedup.",
        "declaration people_entities content list of Entity",
        "  depends on world content World",
        "  equals " + "\n    ++ ".join(people_members),
        "",
    ])
    return "\n".join(out)


def main() -> None:
    text = WORLD.read_text()
    old_markers = (
        "## One reified event",
        "## A normalized internal view",
        "## Category-specific event records",
    )
    start = next(text.index(marker) for marker in old_markers if marker in text)
    end = text.index("## first_day_year/2")
    tail = text[end:]
    for field in EVENT_FIELDS.values():
        accessor = field.removesuffix("_events") + "_event_values"
        tail = re.sub(rf"\(event_values of world\.{re.escape(field)}\)",
                      f"({accessor} of world)", tail)
        tail = re.sub(rf"world\.{re.escape(field)}\b",
                      f"({accessor} of world)", tail)
    WORLD.write_text(text[:start] + schema_block() + tail)

    # All statute modules consume normalized views. World construction remains
    # unchanged and is handled by the emitter's specialized constructors.
    for path in sorted(SARA.glob("Section*.catala_en")):
        if path == WORLD:
            continue
        body = path.read_text()
        for field in EVENT_FIELDS.values():
            accessor = field.removesuffix("_events") + "_event_values"
            body = re.sub(
                rf"\(W\.event_values of \(W\.{accessor} of world\)\)",
                f"(W.{accessor} of world)", body)
            body = re.sub(rf"world\.{re.escape(field)}\b",
                          f"(W.{accessor} of world)", body)
        path.write_text(body)


if __name__ == "__main__":
    main()
