#!/usr/bin/env python3
"""Fill descriptions generated from SARA's category-specific input schema."""

from __future__ import annotations

import json
import re
from pathlib import Path

from saralib.catala_emit import EVENT_FIELDS, ROLE_FACTS


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "data/catala_gold/sara/INPUT_VARIABLE_DESCRIPTION.json"

ROLE_LABELS = {
    "agents": "agent entities",
    "patients": "patient entities",
    "starts": "start dates",
    "ends": "end date",
    "amounts": "monetary amounts",
    "purposes": "purpose",
    "places": "locations",
    "media": "payment media",
    "reasons": "reason entity",
    "beneficiaries": "beneficiary entities",
    "countries": "country entity",
    "types": "semantic type",
    "destinations": "destination",
}


def words(name: str) -> str:
    return name.replace("_", " ")


def field_description(path: str) -> str:
    leaf = path.rsplit(".", 1)[-1]
    if leaf == "id":
        return "The interned identifier; equal identifiers denote the same entity."
    if leaf == "tag":
        return "The semantic classification used by statute comparisons."

    for role, (_, field) in ROLE_FACTS.items():
        prefix = f"world.{field}"
        if path == prefix:
            return f"Standalone {words(role)} facts whose subject has no matching category field."
        if path == prefix + "[].subject":
            return f"The entity about which this {words(role)} fact is asserted."
        if path == prefix + "[].value":
            return f"The asserted {ROLE_LABELS[role]} value."

    match = re.match(r"world\.([a-z_]+)_events(?:\[\])?(?:\.(.+))?$", path)
    if match:
        category, member = match.groups()
        label = words(category)
        if member is None:
            return f"The case's {label} records, represented only by fields relevant to that category."
        member = member.replace("[]", "")
        if member == "ident":
            return f"The identifier of this {label} record."
        if member in ROLE_LABELS:
            return f"The {ROLE_LABELS[member]} attached to this {label} record."

    return f"Input value for {words(leaf.replace('[]', ''))}."


def main() -> None:
    data = json.loads(PATH.read_text())
    for path, spec in data["fields"].items():
        if not spec["description"]:
            spec["description"] = field_description(path)
    for name, description in data["structs"].items():
        if description:
            continue
        short = name.rsplit(".", 1)[-1]
        if short.endswith("Fact"):
            role = re.sub(r"(?<!^)(?=[A-Z])", " ", short[:-4]).lower()
            data["structs"][name] = (
                f"A narrow binary {role} fact with one subject and one value."
            )
        else:
            category = re.sub(r"(?<!^)(?=[A-Z])", " ", short[:-5]).lower()
            data["structs"][name] = (
                f"A category-specific {category} record containing only roles "
                "used for that category."
            )
    if "Section7703.World" in data["structs"]:
        data["structs"]["Section7703.World"] = (
            "All case facts as category-specific records and narrow standalone "
            "role relations; no universal event record is present."
        )
    PATH.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
