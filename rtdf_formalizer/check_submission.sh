#!/usr/bin/env bash
set -euo pipefail

workspace=${1:-/workspace}
output=${2:-$workspace/INPUT_VARIABLE_DESCRIPTION.json}
check=${3:-}

cd "$workspace"
clerk start --color=never >/dev/null

python3 - "$workspace" "$output" "$check" <<'PY'
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

workspace = Path(sys.argv[1])
output = Path(sys.argv[2])

old_descriptions = {"fields": {}, "enums": {}, "structs": {}}

def remember(category, name, value):
    description = (
        value.get("description", "")
        if category == "fields" and isinstance(value, dict)
        else value
    )
    if not isinstance(description, str):
        return
    previous = old_descriptions[category].get(name, "")
    if previous and description and previous != description:
        raise SystemExit(f"conflicting existing descriptions for {category}.{name}")
    old_descriptions[category][name] = previous or description

if output.is_file():
    try:
        value = json.loads(output.read_text(encoding="utf-8"))
        if all(isinstance(value.get(category), dict) for category in old_descriptions):
            for category in old_descriptions:
                for name, description in value[category].items():
                    remember(category, name, description)
        elif isinstance(value.get("descriptions"), dict):
            for category in old_descriptions:
                entries = value["descriptions"].get(category, {})
                if isinstance(entries, dict):
                    for name, description in entries.items():
                        remember(category, name, description)
        else:
            # Migrate the original per-scope format without losing completed text.
            for item in value.get("scopes", []):
                for category in old_descriptions:
                    entries = item.get(category, {})
                    if not isinstance(entries, dict):
                        continue
                    for name, description in entries.items():
                        remember(category, name, description)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        old_descriptions = {"fields": {}, "enums": {}, "structs": {}}

mapping_path = workspace / "REQUIREMENT_OUTPUTS.json"
if mapping_path.is_file():
    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SystemExit(f"REQUIREMENT_OUTPUTS.json is not valid JSON: {error}")
    requirements = mapping.get("requirements", [])
    unresolved = [
        item.get("requirement_id", f"entry {index}")
        for index, item in enumerate(requirements)
        if not isinstance(item, dict)
        or not isinstance(item.get("file"), str) or not item["file"]
        or not isinstance(item.get("scope"), str) or not item["scope"]
    ]
    if not requirements or unresolved:
        raise SystemExit(
            "fill every file and scope in REQUIREMENT_OUTPUTS.json before running "
            f"this helper (unresolved: {unresolved})"
        )
else:
    contract_pattern = re.compile(
        r"(?m)^-[ \t]+Requirement ID[ \t]+`([A-Z0-9][A-Z0-9-]*)`:"
        r"[ \t]+scope[ \t]+`([^`]+)`,[ \t]+output[ \t]+`([^`]+)`\.\s*$"
    )
    requirements = []
    for source in sorted(workspace.glob("*.catala_*")):
        if source.name.split(".catala_", 1)[0].casefold() != "api":
            continue
        for requirement_id, scope, output_name in contract_pattern.findall(
            source.read_text(encoding="utf-8")
        ):
            requirements.append({
                "requirement_id": requirement_id,
                "file": source.name,
                "scope": scope,
                "output": output_name,
            })
    if not requirements:
        raise SystemExit(
            "no protected Api.catala_* requirement contract or "
            "REQUIREMENT_OUTPUTS.json was found"
        )
selected = sorted({(item["file"], item["scope"]) for item in requirements})

def parse_json(text):
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if not text[index + end:].strip():
            return value
    raise ValueError("clerk json-schema produced no JSON value")

primitive_names = {
    "money", "decimal", "date", "duration", "unit",
    "integer", "boolean", "string", "number",
}

def inventory(schema):
    definitions = schema.get("definitions", {})
    root_reference = schema.get("$ref", "")
    root_name = root_reference.rsplit("/", 1)[-1] if root_reference else None
    fields, enums, structs = set(), set(), set()

    def walk(node, path, seen):
        if not isinstance(node, dict):
            return
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/definitions/"):
            name = reference.rsplit("/", 1)[-1]
            definition = definitions.get(name, {})
            if name != root_name and name not in primitive_names:
                if isinstance(definition.get("enum"), list):
                    enums.add(name)
                elif isinstance(definition.get("properties"), dict):
                    structs.add(name)
            if name in seen:
                return
            walk(definition, path, seen | {name})
            return
        if node.get("type") == "array":
            walk(node.get("items", {}), path + "[]", seen)
            return
        properties = node.get("properties", {})
        if isinstance(properties, dict):
            for name, child in sorted(properties.items()):
                child_path = f"{path}.{name}" if path else name
                fields.add(child_path)
                walk(child, child_path, seen)

    walk(schema, "", frozenset())
    return sorted(fields), sorted(enums), sorted(structs)

include_pattern = re.compile(
    r"(?m)^\s*>\s*(?:Inclusion|Include)\s*:\s*([^\r\n]+)"
)

def compiler_file(source):
    owners = [
        candidate for candidate in source.parent.glob("*.catala_*")
        if candidate != source
        and source.name in include_pattern.findall(
            candidate.read_text(encoding="utf-8", errors="replace")
        )
    ]
    if len(owners) > 1:
        relative = source.relative_to(workspace).as_posix()
        raise SystemExit(
            f"cannot identify one compiler file for included source {relative}: "
            f"{[owner.relative_to(workspace).as_posix() for owner in owners]}"
        )
    return owners[0] if owners else source

all_names = {"fields": set(), "enums": set(), "structs": set()}
field_scopes = {}
for relative, scope in selected:
    source = workspace / relative
    if not source.is_file():
        raise SystemExit(f"mapped Catala file does not exist: {relative}")
    compiler = compiler_file(source)
    compiler_relative = compiler.relative_to(workspace).as_posix()
    result = subprocess.run(
        ["clerk", "json-schema", compiler_relative, "--scope", scope,
         "--whole-program", "--color=never"],
        cwd=workspace, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[-4000:]
        raise SystemExit(
            f"could not extract schema for {relative}::{scope} via "
            f"{compiler_relative}:\n{detail}"
        )
    try:
        schemas = parse_json(result.stdout)
    except ValueError as error:
        raise SystemExit(f"could not parse schema for {relative}::{scope}: {error}")
    if not isinstance(schemas, list) or len(schemas) != 2:
        raise SystemExit(f"unexpected schema result for {relative}::{scope}")
    fields, enums, structs = inventory(schemas[0])
    if not fields:
        raise SystemExit(f"selected scope has no JSON input fields: {relative}::{scope}")
    scope_id = f"{relative}::{scope}"
    for name in fields:
        field_scopes.setdefault(name, set()).add(scope_id)
    all_names["fields"].update(fields)
    all_names["enums"].update(enums)
    all_names["structs"].update(structs)

output.write_text(json.dumps({
    "schema_version": 3,
    "fields": {
        name: {
            "scopes": sorted(field_scopes[name]),
            "description": old_descriptions["fields"].get(name, ""),
        }
        for name in sorted(all_names["fields"])
    },
    "enums": {
        name: old_descriptions["enums"].get(name, "")
        for name in sorted(all_names["enums"])
    },
    "structs": {
        name: old_descriptions["structs"].get(name, "")
        for name in sorted(all_names["structs"])
    },
}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    f"wrote {output} from {len(selected)} input scopes with "
    + ", ".join(f"{len(all_names[name])} {name}" for name in ("fields", "enums", "structs"))
)
if sys.argv[3] == "--check":
    missing = [
        f"{category}.{name}"
        for category, names in all_names.items()
        for name in sorted(names)
        if not old_descriptions[category].get(name, "").strip()
    ]
    if missing:
        raise SystemExit("fill non-blank descriptions for: " + ", ".join(missing))
    print("all generated input descriptions are non-blank")
    socket_path = os.environ.get("RTDF_SUBMISSION_CHECK_SOCKET", "")
    if not socket_path:
        raise SystemExit("authoritative submission check is unavailable")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(socket_path)
        client.sendall(b"check\n")
        response_bytes = bytearray()
        while True:
            chunk = client.recv(4096)
            if not chunk:
                break
            response_bytes.extend(chunk)
    except OSError:
        raise SystemExit("authoritative submission check is unavailable")
    finally:
        client.close()
    try:
        response = json.loads(response_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SystemExit("authoritative submission check is unavailable")
    if not response.get("accepted"):
        message = response.get("message")
        raise SystemExit(
            message if isinstance(message, str) and message
            else "submission rejected"
        )
    message = response.get("message")
    if isinstance(message, str) and message.strip():
        print(message)
    print("submission accepted")
elif sys.argv[3]:
    raise SystemExit(f"unknown check option: {sys.argv[3]}")
PY
