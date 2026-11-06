"""Generate a candidate-independent JSON-to-compiled-OCaml scope bridge."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any


PRIMITIVES = {"integer", "money", "decimal", "date", "duration", "unit"}
MONEY_TOLERANCE = Decimal("1")


def _decimal_value(value: Any) -> Decimal:
    text = str(value).replace("$", "").replace(",", "").strip()
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        return Decimal(numerator) / Decimal(denominator)
    return Decimal(text)


def schema_at_path(schema: dict[str, Any], path: list[str]) -> dict[str, Any]:
    # Return the advertised schema node at an object/array JSON path.
    definitions = schema.get("definitions", {})

    def resolve(node: Any) -> dict[str, Any]:
        if not isinstance(node, dict):
            return {}
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/definitions/"):
            target = definitions.get(reference.removeprefix("#/definitions/"))
            if isinstance(target, dict):
                return target
        return node

    node: dict[str, Any] = schema
    for component in path:
        resolved = resolve(node)
        if resolved.get("type") == "array":
            node = resolved.get("items", {})
        else:
            node = resolved.get("properties", {}).get(component, {})
    return node


def named_output_schema(schema: dict[str, Any], output: str) -> dict[str, Any]:
    # Keep exactly one scope output, retaining referenced type definitions.
    root = schema_at_path(schema, [])
    reference = root.get("$ref", "")
    if reference.startswith("#/definitions/"):
        root = schema.get("definitions", {}).get(
            reference.removeprefix("#/definitions/"), {}
        )
    properties = root.get("properties", {})
    if output not in properties:
        raise ValueError(f"named output {output!r} is absent from the scope schema")
    return {
        "type": "object",
        "properties": {output: properties[output]},
        "required": [output] if output in root.get("required", []) else [],
        "additionalProperties": False,
        "definitions": schema.get("definitions", {}),
    }


def named_answer(value: Any, output: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("scope answer must be a JSON object")
    return {output: value[output]} if output in value else {}


def json_equivalent(
    left: Any, right: Any, schema: dict[str, Any] | None = None
) -> bool:
    # Compare public JSON values according to their Catala output types.
    root = schema if isinstance(schema, dict) else {}
    definitions = root.get("definitions", {})

    def resolve(node: Any) -> dict[str, Any]:
        if not isinstance(node, dict):
            return {}
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/definitions/"):
            target = definitions.get(reference.removeprefix("#/definitions/"))
            if isinstance(target, dict):
                return target
        return node

    def is_money(node: Any) -> bool:
        if not isinstance(node, dict):
            return False
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.rsplit("/", 1)[-1] == "money":
            return True
        return resolve(node).get("title") == "Catala Money"

    def compare(a: Any, b: Any, node: Any) -> bool:
        if is_money(node):
            try:
                return abs(_decimal_value(a) - _decimal_value(b)) < MONEY_TOLERANCE
            except (InvalidOperation, ValueError, ZeroDivisionError):
                return False
        resolved = resolve(node)
        if isinstance(a, dict) or isinstance(b, dict):
            if not isinstance(a, dict) or not isinstance(b, dict) or set(a) != set(b):
                return False
            properties = resolved.get("properties", {})
            return all(compare(a[key], b[key], properties.get(key, {})) for key in a)
        if isinstance(a, list) or isinstance(b, list):
            if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b):
                return False
            child_schema = resolved.get("items", {})
            return all(compare(x, y, child_schema) for x, y in zip(a, b))
        if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None:
            return a == b
        if a == b:
            return True
        try:
            return _decimal_value(a) == _decimal_value(b)
        except (InvalidOperation, ValueError, ZeroDivisionError):
            return False

    return compare(left, right, root)


def project_output_json(value: Any, schema: dict[str, Any]) -> Any:
    # Project Catala runtime JSON into the public shape advertised by its schema.
    definitions = schema.get("definitions", {})

    def resolve(node: Any, seen: frozenset[str] = frozenset()) -> Any:
        if not isinstance(node, dict):
            return {}
        reference = node.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/definitions/"):
            name = reference.removeprefix("#/definitions/")
            if name in seen or name not in definitions:
                return {}
            return resolve(definitions[name], seen | {name})
        return node

    def project(item: Any, node: Any) -> Any:
        node = resolve(node)
        if node.get("type") == "object" and isinstance(item, dict):
            properties = node.get("properties", {})
            required = set(node.get("required", []))
            result = {}
            for name, child_schema in properties.items():
                if name not in item:
                    continue
                child = item[name]
                if name not in required:
                    if child == "Absent":
                        continue
                    if isinstance(child, dict) and set(child) == {"Present"}:
                        child = child["Present"]
                result[name] = project(child, child_schema)
            return result
        if node.get("type") == "array" and isinstance(item, list):
            return [project(child, node.get("items", {})) for child in item]
        return item

    return project(value, schema)


def ocaml_name(value: str) -> str:
    value = value.replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae")
    value = "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")


def module_name(value: str) -> str:
    # JSON Schema retains Catala module qualification (for example, ``AirlineWorld.Cabin``).
    parts = []
    for component in value.split("."):
        name = ocaml_name(component)
        parts.append(name[:1].upper() + name[1:])
    return ".".join(parts)


def identifier(value: str) -> str:
    name = ocaml_name(value)
    return name[:1].lower() + name[1:]


OCAML_KEYWORDS = {
    "and",
    "as",
    "assert",
    "begin",
    "class",
    "constraint",
    "do",
    "done",
    "downto",
    "else",
    "end",
    "exception",
    "external",
    "false",
    "for",
    "fun",
    "function",
    "functor",
    "if",
    "in",
    "include",
    "inherit",
    "initializer",
    "lazy",
    "let",
    "match",
    "method",
    "module",
    "mutable",
    "new",
    "nonrec",
    "object",
    "of",
    "open",
    "or",
    "private",
    "rec",
    "sig",
    "struct",
    "then",
    "to",
    "true",
    "try",
    "type",
    "val",
    "virtual",
    "when",
    "while",
    "with",
}


def field_identifier(value: str) -> str:
    # Match Catala's OCaml mangling for record labels that are keywords.
    name = identifier(value)
    return name + "__1" if name in OCAML_KEYWORDS else name


def function_name(value: str) -> str:
    return "decode_" + identifier(value)


def literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


class DecoderGenerator:
    def __init__(
        self,
        definitions: dict[str, Any],
        plain_scope_optionals: set[str] | None = None,
    ):
        self.definitions = definitions
        self.plain_scope_optionals = plain_scope_optionals or set()
        self.reachable: set[str] = set()

    def visit(self, schema: dict[str, Any]) -> None:
        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[-1]
            if name in PRIMITIVES or name in self.reachable:
                return
            if name not in self.definitions:
                raise ValueError(f"JSON schema lacks definition {name!r}")
            self.reachable.add(name)
            self.visit(self.definitions[name])
            return
        for child in schema.get("properties", {}).values():
            self.visit(child)
        if "items" in schema:
            self.visit(schema["items"])
        for child in schema.get("oneOf", []):
            self.visit(child)

    def decoder(self, schema: dict[str, Any]) -> str:
        if "$ref" in schema:
            name = schema["$ref"].rsplit("/", 1)[-1]
            return name if name in PRIMITIVES else function_name(name)
        kind = schema.get("type")
        if kind == "array":
            return f"(array ({self.decoder(schema['items'])}))"
        if kind == "boolean":
            return "boolean"
        if kind == "integer":
            return "integer"
        if kind == "number":
            return "decimal"
        if kind == "string":
            return "text"
        if kind == "null":
            return "unit"
        raise ValueError(f"unsupported inline JSON schema {schema!r}")

    def definition(self, name: str) -> str:
        schema = self.definitions[name]
        module = module_name(name)
        function = function_name(name)
        if schema.get("type") == "object" and not schema.get("oneOf"):
            properties = schema.get("properties", {})
            suffix = "_in" if name.endswith("_in") else ""
            required = set(schema.get("required", []))
            fields = []
            for key, value in properties.items():
                decoder = self.decoder(value)
                # Catala exposes every defaulted record field as Optional.t.
                if key not in required:
                    label = field_identifier(key) + suffix
                    helper = (
                        "optional_value_field"
                        if not suffix or label in self.plain_scope_optionals
                        else "optional_field"
                    )
                    decoded = f"{helper} ({decoder}) {literal(key)} j"
                else:
                    decoded = f"({decoder}) (field {literal(key)} j)"
                fields.append(f"{module}.{field_identifier(key)}{suffix} = {decoded};")
            body = "{ " + " ".join(fields) + " }" if fields else "()"
        else:
            alternatives = schema.get("oneOf", [schema])
            arms = []
            for alternative in alternatives:
                for case in alternative.get("enum", []):
                    arms.append(
                        f"| `String {literal(case)} -> {module}.{module_name(case)}"
                    )
                if alternative.get("type") == "object":
                    properties = alternative.get("properties", {})
                    if len(properties) != 1:
                        raise ValueError(
                            f"unsupported variant payload for {name}: {alternative}"
                        )
                    case, payload = next(iter(properties.items()))
                    arms.append(
                        f"| `Assoc [({literal(case)}, value)] -> "
                        f"{module}.{module_name(case)} (({self.decoder(payload)}) value)"
                    )
            if not arms:
                raise ValueError(f"unsupported definition {name}: {schema}")
            body = (
                "(match j with "
                + " ".join(arms)
                + f" | _ -> failwith {literal('invalid ' + name + ' constructor')})"
            )
        return f"{function} j : {module}.t = {body}"

    def generate(self, roots: list[dict[str, Any]]) -> str:
        for root in roots:
            self.visit(root)
        if not self.reachable:
            return ""
        definitions = [self.definition(name) for name in sorted(self.reachable)]
        return "let rec " + "\nand ".join(definitions) + "\n"


HELPERS = r"""
module Json_input = Yojson.Safe

let field name = function
  | `Assoc fields ->
      (try List.assoc name fields with Not_found -> failwith ("missing field " ^ name))
  | _ -> failwith "expected JSON object"

let bridge_input_location : Catala_runtime.code_location =
  { filename = "<json-input>";
    start_line = 1;
    start_column = 1;
    end_line = 1;
    end_column = 1;
    law_headings = [] }

let optional_field decoder name = function
  | `Assoc fields ->
      (match List.assoc_opt name fields with
       | None | Some `Null -> Catala_runtime.Optional.Absent
       | Some value ->
           Catala_runtime.Optional.Present
             (decoder value, bridge_input_location))
  | _ -> failwith "expected JSON object"

let optional_value_field decoder name = function
  | `Assoc fields ->
      (match List.assoc_opt name fields with
       | None | Some `Null -> Catala_runtime.Optional.Absent
       | Some value -> Catala_runtime.Optional.Present (decoder value))
  | _ -> failwith "expected JSON object"

let text = function
  | `String value | `Intlit value -> value
  | `Int value -> string_of_int value
  | `Float value -> Printf.sprintf "%.17g" value
  | _ -> failwith "expected JSON scalar"

let boolean = function
  | `Bool value -> value
  | _ -> failwith "expected boolean"
let unit = function
  | `Null -> ()
  | _ -> failwith "expected null"
let integer value = Z.of_string (text value)
let decimal value = Q.of_string (text value)
let money value = Catala_runtime.round (Q.mul (decimal value) (Q.of_int 100))
let array decoder = function
  | `List values -> Array.of_list (List.map decoder values)
  | _ -> failwith "expected JSON array"
let date = function
  | `String value -> Dates_calc.date_of_string value
  | value -> Dates_calc.make_date
      ~year:(int_of_string (text (field "year" value)))
      ~month:(int_of_string (text (field "month" value)))
      ~day:(int_of_string (text (field "day" value)))
let duration value = Dates_calc.make_period
  ~years:(int_of_string (text (field "years" value)))
  ~months:(int_of_string (text (field "months" value)))
  ~days:(int_of_string (text (field "days" value)))
"""


def _parenthesize_record_field_lets(generated_ml: str) -> str:
    # Repair Catala 1.2.1's missing parentheses around let-valued fields.
    lines = generated_ml.splitlines(keepends=True)
    let_field = re.compile(r"^(\s+)\{?[A-Z][A-Za-z0-9_]*\.[a-z][A-Za-z0-9_]*\s*=\s*$")
    any_field = re.compile(r"^(\s+)\{?[A-Z][A-Za-z0-9_]*\.[a-z][A-Za-z0-9_]*\s*=")
    index = 0
    while index + 1 < len(lines):
        matched = let_field.match(lines[index].rstrip("\r\n"))
        if not matched or not lines[index + 1].lstrip().startswith("let "):
            index += 1
            continue
        indentation = len(matched.group(1))
        end = index + 2
        while end < len(lines):
            candidate = any_field.match(lines[end].rstrip("\r\n"))
            if candidate and len(candidate.group(1)) == indentation:
                break
            end += 1
        if end >= len(lines):
            index += 1
            continue
        newline = "\r\n" if lines[index + 1].endswith("\r\n") else "\n"
        lines[index + 1] = (
            lines[index + 1].rstrip("\r\n").replace("let ", "(let ", 1) + newline
        )
        previous = lines[end - 1].rstrip("\r\n")
        if previous.rstrip().endswith(";"):
            offset = previous.rfind(";")
            lines[end - 1] = previous[:offset] + ");" + previous[offset + 1 :] + newline
        index = end
    return "".join(lines)


def _trace_conditional_constant_reads(
    generated_ml: str, source_text: str, source_name: str
) -> str:
    # Trace reads of named top-level constants in selected OCaml if arms.
    declarations = re.finditer(
        r"(?m)^[ \t]*declaration[ \t]+([a-z][A-Za-z0-9_]*)"
        r"[ \t]+content[ \t]+[^\n]*?[ \t]+equals\b",
        source_text,
    )
    for declaration in declarations:
        name = declaration.group(1)
        # A same-named local binding would make text substitution ambiguous.
        if len(re.findall(rf"(?m)^let {re.escape(name)}\s*:", generated_ml)) != 1:
            continue
        line = source_text.count("\n", 0, declaration.start()) + 1
        position = (
            "{filename = "
            + json.dumps(f"../{source_name}")
            + f"; start_line={line}; start_column=1; end_line={line}; "
            + f"end_column={len(declaration.group(0)) + 1}; law_headings=[]"
            + "}"
        )
        pattern = re.compile(rf"\b(then|else)(\s+)({re.escape(name)})(?![A-Za-z0-9_'])")
        generated_ml = pattern.sub(
            lambda match: (
                f"{match.group(1)}{match.group(2)}"
                f"(let _ = log_decision_taken {position} true in {name})"
            ),
            generated_ml,
        )
    return generated_ml


def _trace_generated_function_calls(generated_ml: str, source_name: str) -> str:
    # Wrap generated Catala top-level helpers in concrete call events.
    marker = re.compile(r"(?m)^\(\* (Toplevel def|Scope) ([^ ]+) \*\)$")
    matches = list(marker.finditer(generated_ml))
    if not matches:
        return generated_ml
    registration = re.search(
        r"(?m)^let \(\) =\s*\n\s*Catala_runtime\.register_module\b", generated_ml
    )
    additions: list[tuple[int, str]] = []
    for offset, found in enumerate(matches):
        if found.group(1) == "Scope":
            continue
        start = found.end()
        end = (
            matches[offset + 1].start()
            if offset + 1 < len(matches)
            else (
                registration.start() if registration is not None else len(generated_ml)
            )
        )
        block = generated_ml[start:end]
        lines = list(re.finditer(r"(?m)^.*(?:\n|$)", block))
        let_index = next(
            (
                index
                for index, line in enumerate(lines)
                if line.group().lstrip().startswith("let ")
            ),
            None,
        )
        if let_index is None:
            continue
        function_line = None
        for index in range(let_index, min(let_index + 8, len(lines))):
            text = lines[index].group().rstrip("\r\n")
            equals = text.find("=")
            rhs = text[equals + 1 :].lstrip() if equals >= 0 else text.lstrip()
            if rhs.startswith("fun ") and rhs.rstrip().endswith("->"):
                function_line = lines[index]
                break
            # Once a non-empty RHS other than `fun` begins, this is a constant top-level definition containing a nested callback,…
            if equals >= 0 and rhs:
                break
        if function_line is None:
            continue
        line_text = function_line.group().rstrip("\r\n")
        indentation = re.match(r"\s*", line_text).group()
        body_indentation = indentation + "  "
        newline = "\r\n" if function_line.group().endswith("\r\n") else "\n"
        insertion = start + function_line.end()
        call_name = f"{Path(source_name).name}::{found.group(2)}"
        additions.append(
            (
                insertion,
                body_indentation
                + "log_runtime_call "
                + json.dumps(call_name)
                + " (fun () ->"
                + newline,
            )
        )
        close = end
        while close > start and generated_ml[close - 1] in "\r\n":
            close -= 1
        additions.append((close, newline + body_indentation + ")"))
    for position, addition in sorted(additions, reverse=True):
        generated_ml = generated_ml[:position] + addition + generated_ml[position:]
    return generated_ml


def _qualify_generated_scope_calls(generated_ml: str, source_name: str) -> str:
    # Give the compiler's native nested-scope events stable source identity.
    pattern = re.compile(r'(log_(?:begin|end)_call\s*)\["([^"]+)";\s*"direct"\]')
    return pattern.sub(
        lambda match: (
            match.group(1)
            + "["
            + json.dumps(f"{Path(source_name).name}::{match.group(2)}")
            + "]"
        ),
        generated_ml,
    )


def _instrument_trace_source(
    generated_ml: str, source_text: str, source_name: str
) -> str:
    # Add complete call/dependency instrumentation to traced Catala OCaml.
    before, runtime_open, after = generated_ml.partition("open Catala_runtime\n")
    helper = (
        "let log_value_condition f = f ()\n"
        "let log_runtime_call name f =\n"
        '  let token = "$call-return:" ^ name in\n'
        "  ignore (log_begin_call [name] ());\n"
        '  match log_variable_definition_with_reads token [name; "$return"]\n'
        "    {io_input=NoInput; io_output=false}\n"
        "    (fun value -> Value.embed Value.Polymorphic value) f with\n"
        "  | value ->\n"
        "    let value = log_variable_read token value in\n"
        "    log_end_call [name] value\n"
        "  | exception error ->\n"
        "    ignore (log_end_call [name] ());\n"
        "    raise error\n"
    )
    generated_ml = (
        before + runtime_open + helper + after
        if runtime_open
        else helper + generated_ml
    )
    generated_ml = _trace_conditional_constant_reads(
        generated_ml, source_text, source_name
    )
    generated_ml = _qualify_generated_scope_calls(generated_ml, source_name)
    return _trace_generated_function_calls(generated_ml, source_name)


def generate_source(
    generated_ml: str,
    scopes: list[dict[str, Any]],
    *,
    source_text: str | None = None,
    source_name: str | None = None,
) -> str:
    # The old runtime's log_value_condition discards predicate reads.
    generated_ml = _instrument_trace_source(
        generated_ml, source_text or "", source_name or "unknown"
    )
    generated_ml = _parenthesize_record_field_lets(generated_ml)
    # Catala emits private (non-exported) scopes as anonymous `let _` values.
    for scope in scopes:
        name = scope["scope"]
        function = identifier(re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower())
        marker = re.compile(
            r"(\(\* Scope " + re.escape(name) + r" \*\)\s*)let _(?=\s*:)"
        )
        generated_ml = marker.sub(
            lambda match: match.group(1) + "let " + function, generated_ml, count=1
        )
    definitions: dict[str, Any] = {}
    for scope in scopes:
        for name, schema in scope["input_schema"].get("definitions", {}).items():
            if name in definitions and definitions[name] != schema:
                raise ValueError(f"conflicting JSON definition {name!r}")
            definitions[name] = schema
    roots = [scope["input_schema"] for scope in scopes]
    plain_scope_optionals = {
        match.group(1)
        for match in re.finditer(
            r"(?m)^\s+([a-zA-Z0-9_]+_in):\s+\(([^\n]*)\) Optional\.t;",
            generated_ml,
        )
        if "code_location" not in match.group(2)
    }
    decoders = DecoderGenerator(definitions, plain_scope_optionals).generate(roots)
    arms = []
    for scope in scopes:
        scope_name = scope["scope"]
        input_type = scope["input_schema"]["$ref"].rsplit("/", 1)[-1]
        input_decoder = function_name(input_type)
        output_module = module_name(scope_name)
        ocaml_function = identifier(re.sub(r"(?<!^)(?=[A-Z])", "_", scope_name).lower())
        call_name = f"{Path(source_name or 'unknown').name}::{scope_name}"
        arms.append(
            f"| {literal(scope_name)} ->\n"
            f"  let result = log_runtime_call {literal(call_name)} "
            f"(fun () -> {ocaml_function} ({input_decoder} input)) in\n"
            f"  Catala_runtime.Json.runtime_value "
            f"(Catala_runtime.Value.embed {output_module}.rtype result)"
        )
    dispatch = "\n".join(arms)
    driver = f"""
let execute scope input = match scope with
{dispatch}
| _ -> failwith ("unknown compiled scope " ^ scope)

let () =
  let scope = if Array.length Sys.argv > 1 then Sys.argv.(1) else failwith "missing scope" in
  let trace = Array.length Sys.argv > 2 && Sys.argv.(2) = "--trace" in
  try while true do
    let line = read_line () in
    if String.trim line <> "" then begin
      try
        Catala_runtime.reset_log ();
        let input = Json_input.from_string line in
        let result = execute scope input
        in
        if trace then begin
          let events = Catala_runtime.retrieve_log () |> List.map
            (fun event -> Json_input.from_string (Catala_runtime.Json.raw_event event)) in
          print_endline (Json_input.to_string (`Assoc [
            "dependency_semantics", `String "runtime_reads_branch_outcomes_call_returns_scope_inputs_v5";
            "result", Json_input.from_string result;
            "events", `List events]))
        end else print_endline result
      with error -> print_endline (Json_input.to_string (`Assoc [
        "__bridge_error__", `String (Printexc.to_string error)]))
    end
  done with End_of_file -> ()
"""
    return generated_ml + "\n" + HELPERS + "\n" + decoders + "\n" + driver


def compiled_path(project: Path, source: str, scope: str) -> Path:
    # Use both source and scope, since different modules can reuse scope names.
    relative = Path(source)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"invalid candidate source {source!r}")
    return project / ".compiled_scopes" / relative.with_suffix("") / scope


def _object_closure(
    project: Path, bridge: Path, environment: dict[str, str]
) -> list[Path]:
    # Order native objects by their actual OCaml implementation imports.
    inspector = shutil.which("ocamlobjinfo", path=environment.get("PATH"))
    if not inspector:
        raise RuntimeError("ocamlobjinfo unavailable")
    objects: dict[str, Path] = {}
    for path in (project / "_build").rglob("*.cmx"):
        objects.setdefault(path.stem, path)
        objects.setdefault(path.stem[:1].upper() + path.stem[1:], path)
    bridge_name = bridge.stem
    ordered: list[Path] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited or name == bridge_name or name not in objects:
            return
        visited.add(name)
        path = objects[name]
        result = subprocess.run(
            [inspector, str(path)],
            cwd=project,
            env=environment,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr[-1000:])
        imports = result.stdout.split("Implementations imported:", 1)
        if len(imports) == 2:
            for line in imports[1].split("\nClambda approximation:", 1)[0].splitlines():
                fields = line.split()
                if len(fields) == 2:
                    visit(fields[1])
        ordered.append(path)

    result = subprocess.run(
        [inspector, str(bridge)],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-1000:])
    for line in (
        result.stdout.split("Implementations imported:", 1)[-1]
        .split("\nClambda approximation:", 1)[0]
        .splitlines()
    ):
        fields = line.split()
        if len(fields) == 2:
            visit(fields[1])
    return ordered


def _catala_project_modules(project: Path) -> dict[str, tuple[Path, str, set[str]]]:
    # Index project Catala modules and their source-level module imports.
    modules: dict[str, tuple[Path, str, set[str]]] = {}
    for path in project.rglob("*.catala_*"):
        relative = path.relative_to(project)
        if any(
            part.startswith("_build") or part.startswith(".compiled")
            for part in relative.parts
        ):
            continue
        source = path.read_text(encoding="utf-8")
        declared = re.search(r"(?m)^> Module ([^\s]+)", source)
        if declared is None:
            continue
        imports = set(re.findall(r"(?m)^> Using ([^\s]+)", source))
        modules[declared.group(1)] = (relative, source, imports)
    return modules


def _traced_dependencies(
    project: Path,
    source: str,
    *,
    environment: dict[str, str],
    timeout: int,
    catala: str,
    ocamlfind: str,
    include_dirs: list[Path],
) -> dict[str, Path]:
    # Compile traced, ABI-compatible replacements for imported Catala modules.
    modules = _catala_project_modules(project)
    target_text = (project / source).read_text(encoding="utf-8")
    roots = set(re.findall(r"(?m)^> Using ([^\s]+)", target_text))
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited or name not in modules:
            return
        if name in visiting:
            raise RuntimeError(f"cyclic Catala module import involving {name}")
        visiting.add(name)
        for dependency in sorted(modules[name][2]):
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        ordered.append(name)

    for root in sorted(roots):
        visit(root)
    if not ordered:
        return {}

    trace_dir = project / ".compiled_scopes" / "traced_modules"
    trace_dir.mkdir(parents=True, exist_ok=True)
    includes = [
        part
        for directory in [trace_dir, *include_dirs]
        for part in ("-I", str(directory.relative_to(project)))
    ]
    replacements: dict[str, Path] = {}
    for name in ordered:
        relative, source_text, _ = modules[name]
        generated = trace_dir / f"{name}.ml"
        produced = subprocess.run(
            [
                catala,
                "ocaml",
                "--trace",
                "--stdlib",
                "_build/libcatala",
                "--directory",
                "_build",
                "-I",
                "_build/.",
                "-o",
                str(generated.relative_to(project)),
                "--",
                str(relative),
            ],
            cwd=project,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if produced.returncode:
            raise RuntimeError((produced.stdout + produced.stderr)[-3000:])
        generated.write_text(
            _instrument_trace_source(
                generated.read_text(encoding="utf-8"), source_text, str(relative)
            ),
            encoding="utf-8",
        )
        compiled = subprocess.run(
            [
                ocamlfind,
                "ocamlopt",
                "-package",
                "zarith,yojson",
                *includes,
                "-c",
                str(generated.relative_to(project)),
            ],
            cwd=project,
            env=environment,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if compiled.returncode:
            raise RuntimeError((compiled.stdout + compiled.stderr)[-3000:])
        replacements[name] = generated.with_suffix(".cmx")
    return replacements


def build_bridges(
    project: Path,
    candidate_format: dict[str, Any],
    *,
    environment: dict[str, str],
    timeout: int = 600,
    selected: set[tuple[str, str]] | None = None,
) -> dict[str, str]:
    # Compile JSON-line runners for schema-described Catala scopes.
    groups: dict[str, list[dict[str, Any]]] = {}
    for scope in candidate_format.get("scopes", []):
        source = scope.get("compiler_file")
        if not source or "input_schema" not in scope:
            continue
        if selected is not None and not (
            (scope["file"], scope["scope"]) in selected
            or (source, scope["scope"]) in selected
        ):
            continue
        groups.setdefault(source, []).append(scope)
    errors: dict[str, str] = {}
    clerk = shutil.which("clerk", path=environment.get("PATH"))
    ocamlfind = shutil.which("ocamlfind", path=environment.get("PATH"))
    if not clerk or not ocamlfind:
        return {source: "clerk or ocamlfind unavailable" for source in groups}
    for source, scopes in groups.items():
        stem = Path(source).stem
        source_text = (project / source).read_text(encoding="utf-8")
        declared = re.search(r"(?m)^> Module ([^\s]+)", source_text)
        compiler_stem = declared.group(1) if declared else stem
        generated = project / "_build/ocaml" / f"{compiler_stem}.ml"
        stage = "clerk"
        try:
            built = subprocess.run(
                [clerk, "raw-target", f"_build/ocaml/{compiler_stem}.cmx"],
                cwd=project,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if built.returncode:
                raise RuntimeError((built.stdout + built.stderr)[-3000:])
            runtime = subprocess.run(
                [clerk, "raw-target", "_build/libcatala/ocaml/catala_runtime.cmx"],
                cwd=project,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if runtime.returncode:
                raise RuntimeError((runtime.stdout + runtime.stderr)[-3000:])
            stage = "decoder"
            bridge = generated.with_name(f"{stem}__json_bridge.ml")
            trace_source = generated.with_name(f"{stem}__trace.ml")
            catala = shutil.which("catala", path=environment.get("PATH"))
            if not catala:
                raise RuntimeError("catala unavailable for traced OCaml generation")
            traced = subprocess.run(
                [
                    catala,
                    "ocaml",
                    "--trace",
                    "--stdlib",
                    "_build/libcatala",
                    "--directory",
                    "_build",
                    "-I",
                    "_build/.",
                    "-o",
                    str(trace_source.relative_to(project)),
                    "--",
                    str((project / source).relative_to(project)),
                ],
                cwd=project,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if traced.returncode:
                raise RuntimeError((traced.stdout + traced.stderr)[-3000:])
            bridge.write_text(
                generate_source(
                    trace_source.read_text(encoding="utf-8"),
                    scopes,
                    source_text=source_text,
                    source_name=source,
                ),
                encoding="utf-8",
            )
            include_dirs = sorted(
                {path.parent for path in (project / "_build").rglob("*.cmx")}
            )
            replacements = _traced_dependencies(
                project,
                source,
                environment=environment,
                timeout=timeout,
                catala=catala,
                ocamlfind=ocamlfind,
                include_dirs=include_dirs,
            )
            includes = [
                part
                for directory in include_dirs
                for part in ("-I", str(directory.relative_to(project)))
            ]
            compile_cmd = [
                ocamlfind,
                "ocamlopt",
                "-package",
                "zarith,yojson",
                *includes,
                "-c",
                str(bridge.relative_to(project)),
            ]
            compiled = subprocess.run(
                compile_cmd,
                cwd=project,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if compiled.returncode:
                raise RuntimeError((compiled.stdout + compiled.stderr)[-3000:])
            bridge_cmx = str(bridge.with_suffix(".cmx").relative_to(project))
            signature = hashlib.sha256(
                "\n".join(sorted(scope["scope"] for scope in scopes)).encode("utf-8")
            ).hexdigest()[:12]
            executable = project / ".compiled_scopes" / "bin" / f"{stem}-{signature}"
            executable.parent.mkdir(parents=True, exist_ok=True)
            objects = []
            for path in _object_closure(
                project, bridge.with_suffix(".cmx"), environment
            ):
                if path == project / "_build/ocaml" / f"{compiler_stem}.cmx":
                    continue
                replacement = replacements.get(path.stem)
                objects.append(str((replacement or path).relative_to(project)))
            linked = subprocess.run(
                [
                    ocamlfind,
                    "ocamlopt",
                    "-package",
                    "zarith,yojson",
                    "-linkpkg",
                    *includes,
                    *objects,
                    bridge_cmx,
                    "-o",
                    str(executable),
                ],
                cwd=project,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if linked.returncode:
                raise RuntimeError((linked.stdout + linked.stderr)[-3000:])
            for scope in scopes:
                for source_path in {scope["file"], scope["compiler_file"]}:
                    target = compiled_path(project, source_path, scope["scope"])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists() or target.is_symlink():
                        target.unlink()
                    target.symlink_to(os.path.relpath(executable, target.parent))
        except (OSError, ValueError, subprocess.TimeoutExpired, RuntimeError) as error:
            if len(scopes) > 1 and stage == "decoder":
                # One unusual scope schema must not hide other callable scopes in the same Catala module.
                for scope in scopes:
                    partial = build_bridges(
                        project,
                        candidate_format,
                        environment=environment,
                        timeout=timeout,
                        selected={(scope["file"], scope["scope"])},
                    )
                    if partial:
                        errors[f"{source}:{scope['scope']}"] = next(
                            iter(partial.values())
                        )
            else:
                errors[source] = str(error)[-3000:]
    return errors


def translated_scope_pairs(
    translator: Path,
    corpora: list[Path],
    *,
    environment: dict[str, str],
    timeout: int = 60,
) -> set[tuple[str, str]]:
    # Discover candidate entry points in a corpus using the semantic adapter.
    selected: set[tuple[str, str]] = set()
    for corpus in corpora:
        if not corpus.is_dir():
            continue
        for path in corpus.rglob("*.jsonl"):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    translated = subprocess.run(
                        [os.sys.executable, str(translator), "--reference-test", line],
                        env=environment,
                        text=True,
                        capture_output=True,
                        timeout=timeout,
                    )
                    if translated.returncode == 0:
                        value = json.loads(translated.stdout)
                        selected.add((value["path"], value["target"]))
                except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                    continue
    return selected
