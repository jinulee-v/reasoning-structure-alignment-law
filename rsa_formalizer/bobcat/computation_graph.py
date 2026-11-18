"""Domain-independent, provision-aware comparison of concrete computations.

The extractor sees labels and public input bindings, never computed Catala values.
Correspondence is partial: missing or ambiguous nodes are not proof of a defect.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import re
import unicodedata

from .trace import _block_provisions, _definition_blocks, provision_ids_overlap
from .compiled_json import MONEY_TOLERANCE

FORMAT = "provision_computation_graph_v1"
_SCALAR = re.compile(r"^(?:optional of )?(?:boolean|integer|decimal|money|date|duration|string)$")


def unwrap(value):
    if isinstance(value, dict) and "Present" in value:
        inner = value["Present"]
        if isinstance(inner, list) and len(inner) == 2 and isinstance(inner[1], dict) and "file" in inner[1]:
            return unwrap(inner[0])
        return unwrap(inner)
    return value


def normalize_quote(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def source_catalog(snapshot: Path) -> dict:
    """A stable source-only catalog, shared across all cases for this snapshot."""
    aliases, declarations = [], {}
    for file in sorted(snapshot.glob("*.catala_*")):
        scope, children = None, {}
        lines = file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            match = re.match(r"declaration scope (\w+):", line)
            if match:
                scope = match[1]
                children.setdefault(scope, {})
                continue
            match = re.match(r"\s+(input|output|internal) (\w+) content (.+)", line)
            if match and scope:
                name = scope + "." + match[2]
                declaration = {"type": match[3].split("#")[0].strip(), "direction": match[1]}
                if name in declarations and declarations[name].get("file") != file.name:
                    declaration["ambiguous_declaration"] = True
                declarations[name] = {**declaration, "file": file.name}
            match = re.match(r"\s+(\w+) scope ([\w.]+)", line)
            if match and scope:
                children.setdefault(scope, {})[match[1]] = match[2].rsplit(".", 1)[-1]
        scope = None
        for line in lines:
            match = re.match(r"scope (\w+):", line)
            if match:
                scope = match[1]
            match = re.match(r"\s+definition ([\w.]+) equals ([\w.]+)\s*$", line)
            if match and scope:
                def resolve(name):
                    if "." in name:
                        child, variable = name.split(".", 1)
                        return children.get(scope, {}).get(child, child) + "." + variable
                    return scope + "." + name
                aliases.append((resolve(match[1]), resolve(match[2])))
    declarations = {name: decl for name, decl in declarations.items() if _SCALAR.fullmatch(decl["type"])}
    parent = {name: name for name in declarations}

    def find(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    for left, right in aliases:
        if left in parent and right in parent:
            parent[find(left)] = find(right)
    groups = {}
    for name in parent:
        groups.setdefault(find(name), []).append(name)
    definition_blocks = _definition_blocks(snapshot)
    block_provisions = _block_provisions(snapshot)
    alias_targets = {left for left, _ in aliases}
    catalog, canonical = [], {}
    for members in groups.values():
        def score(name):
            decl = declarations[name]
            return (decl["direction"] == "input", name in alias_targets,
                    decl["direction"] != "output", name)
        name = min(members, key=score)
        for member in members:
            canonical[member] = name
        blocks = sorted({block for member in members
                         for block in definition_blocks.get(tuple(member.split(".", 1)), ())})
        catalog.append({"quantity": name, "aliases": sorted(members),
                        "type": declarations[name]["type"], "blocks": blocks,
                        "provisions": sorted({block_provisions[b] for b in blocks if b in block_provisions}),
                        "ambiguous_declaration": any(declarations[m].get("ambiguous_declaration") for m in members)})
    return {"catalog": sorted(catalog, key=lambda row: row["quantity"]),
            "canonical": canonical, "declarations": declarations}


def prepare(tree, snapshot: Path, public_inputs=None, live_tree=None, source=None):
    """Bind catalog quantities to observed invocations and dependency ancestry."""
    source = source or source_catalog(snapshot)
    nodes, occurrences, contexts, public_records = {}, {}, {}, {}

    def normalized(value):
        if isinstance(value, dict):
            return {key: normalized(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalized(item) for item in value]
        if not isinstance(value, bool):
            try:
                return str(Decimal(str(value)).normalize())
            except InvalidOperation:
                pass
        return value

    def key(value):
        return json.dumps(normalized(value), sort_keys=True)

    def collect(value):
        if isinstance(value, (dict, list)):
            if len(json.dumps(value)) <= 512:
                public_records[key(value)] = value
            for child in value.values() if isinstance(value, dict) else value:
                collect(child)
    if public_inputs is not None:
        collect(public_inputs)

    def bindings(children):
        result = {}
        for child in children:
            if child.get("kind") == "variable" and child.get("io", {}).get("io_input") == "OnlyInput":
                value = unwrap(child.get("value"))
                if isinstance(value, (dict, list)) and len(json.dumps(value)) <= 512:
                    signature = key(value)
                    if signature in public_records:
                        result[child.get("name", "").split(".", 1)[-1]] = public_records[signature]
        return result

    live_ids = None
    if live_tree is not None:
        live_ids = set()
        def index_live(xs):
            for node in xs:
                if node.get("kind") == "variable":
                    live_ids.add(node.get("definition_id"))
                index_live(node.get("children", []))
        index_live(live_tree)

    def visit(xs, depth=0, context=None):
        for node in xs:
            if node.get("kind") == "call":
                visit(node.get("children", []), depth + 1, bindings(node.get("children", [])))
                continue
            identifier = node.get("definition_id")
            if node.get("kind") == "variable" and isinstance(identifier, int):
                nodes[identifier] = node
                contexts[identifier] = context or {}
                if (live_ids is None or identifier in live_ids) and isinstance(unwrap(node.get("value")), (bool, int, float, str)):
                    occurrences.setdefault(node.get("name"), []).append((depth, node))
            visit(node.get("children", []), depth, context)
    visit(tree)
    canonical = source["canonical"]
    selected, ambiguous, quantity_contexts = {}, {}, {}
    for row in source["catalog"]:
        name = row["quantity"]
        available = [member for member in row["aliases"] if member in occurrences]
        if not available:
            continue
        member = name if name in available else min(available, key=lambda m: (
            source["declarations"][m]["direction"] == "input", m))
        candidates = occurrences[member]
        depth = min(d for d, _ in candidates)
        closest = [node for d, node in candidates if d == depth]
        values = {json.dumps(unwrap(node.get("value")), sort_keys=True) for node in closest}
        bindings_set = {json.dumps(contexts[node["definition_id"]], sort_keys=True) for node in closest}
        quantity_contexts[name] = [json.loads(value) for value in sorted(bindings_set)]
        if len(values) != 1 or len(bindings_set) != 1 or row["ambiguous_declaration"]:
            ambiguous[name] = {"reason": "multiple values, contexts, or declarations",
                               "public_input_contexts": quantity_contexts[name]}
        else:
            selected[name] = closest[-1]
    ancestors = {}
    for name, node in selected.items():
        pending = [read["definition_id"] for read in node.get("reads", [])]
        seen = set()
        while pending:
            identifier = pending.pop()
            if identifier in seen:
                continue
            seen.add(identifier)
            pending.extend(read["definition_id"] for read in nodes.get(identifier, {}).get("reads", []))
        ancestors[name] = {canonical[nodes[i]["name"]] for i in seen
                           if i in nodes and nodes[i].get("name") in canonical} - {name}
    return {**source, "selected": selected, "ancestors": ancestors,
            "ambiguous": ambiguous, "quantity_contexts": quantity_contexts}


def extraction_context(prepared):
    """Intern repeated public bindings; never expose computed runtime values."""
    records, quantities, signatures = {}, {}, {}
    for quantity, contexts in sorted(prepared["quantity_contexts"].items()):
        references = []
        for context in contexts:
            signature = json.dumps(context, sort_keys=True)
            if signature not in signatures:
                identifier = "context-" + str(len(records))
                signatures[signature] = identifier
                records[identifier] = context
            references.append(signatures[signature])
        quantities[quantity] = references
    return {"public_contexts": records, "observed_quantity_contexts": quantities,
            "ambiguous_quantities": sorted(prepared["ambiguous"])}


def validate_graph(graph, catalog, solution):
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list):
        raise ValueError("computation graph must have a nodes array")
    labels = {row["quantity"] for row in catalog}
    index = {}
    normalized = []
    for node in graph["nodes"]:
        identifier = node.get("id")
        if type(identifier) is not int or identifier in index:
            raise ValueError("node IDs must be unique integers")
        premises = node.get("premises")
        if not isinstance(premises, list) or any(type(p) is not int or p not in index for p in premises):
            raise ValueError(f"node {identifier} references an unknown or later premise")
        if len(premises) != len(set(premises)):
            raise ValueError(f"node {identifier} repeats a premise")
        if node.get("quantity") is not None and node["quantity"] not in labels:
            raise ValueError(f"unknown quantity: {node['quantity']}")
        if not isinstance(node.get("value"), str) or not isinstance(node.get("label"), str):
            raise ValueError("node values and labels must be strings")
        evidence = node.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip() or normalize_quote(evidence) not in normalize_quote(solution):
            raise ValueError(f"node {identifier} evidence is not a source quotation: {evidence}")
        normalized.append({**node, "id": len(index), "premises": [index[p] for p in premises]})
        index[identifier] = len(index)
    return {"nodes": normalized}


def _equal(actual, expected, kind):
    if isinstance(actual, bool):
        return str(actual).lower() == str(expected).lower() if str(expected).lower() in {"true", "false"} else None
    try:
        left, right = Decimal(str(actual)), Decimal(str(expected))
        if not left.is_finite() or not right.is_finite():
            return None
        return abs(left - right) < MONEY_TOLERANCE if kind.endswith("money") else left == right
    except InvalidOperation:
        return str(actual) == str(expected) if kind in {"string", "date", "duration"} else None


def compare(prepared, graph, solution, original_catalog=None):
    original_catalog = original_catalog or prepared["catalog"]
    graph = validate_graph(graph, original_catalog, solution)
    old = {row["quantity"]: row for row in original_catalog}
    by_quantity = {row["quantity"]: row for row in prepared["catalog"]}
    unmapped, llm, dependencies = [], {}, {k: set(v) for k, v in prepared["ancestors"].items()}
    mapped_nodes = []
    for node in graph["nodes"]:
        quantity = node["quantity"]
        candidates = {prepared["canonical"][alias] for alias in old.get(quantity, {}).get("aliases", [quantity])
                      if alias in prepared["canonical"]}
        mapped = next(iter(candidates)) if len(candidates) == 1 else None
        mapped_nodes.append({**node, "quantity": mapped, "original_quantity": quantity})
        if mapped is None:
            unmapped.append({**node, "reason": "no unique runtime counterpart"})
        else:
            llm.setdefault(mapped, []).append(node)
    for node in mapped_nodes:
        if node["quantity"]:
            dependencies.setdefault(node["quantity"], set()).update(mapped_nodes[p]["quantity"] for p in node["premises"]
                if mapped_nodes[p]["quantity"] and mapped_nodes[p]["quantity"] != node["quantity"])
    matched, missing, mismatches, attribution, incomparable = [], [], [], [], []
    ambiguous = dict(prepared["ambiguous"])
    for name, actual in prepared["selected"].items():
        row = by_quantity[name]
        actual_value = unwrap(actual.get("value"))
        if name not in llm:
            missing.append({"quantity": name, "catala_value": actual_value, "catala_provisions": row["provisions"]})
            continue
        values = {node["value"] for node in llm[name]}
        if len(values) != 1:
            ambiguous[name] = {"reason": "multiple reasoning conclusions", "values": sorted(values)}
            continue
        node = llm[name][-1]
        equal = _equal(actual_value, node["value"], row["type"])
        support = set(row["provisions"])
        for ancestor in prepared["ancestors"].get(name, ()):
            support.update(by_quantity.get(ancestor, {}).get("provisions", []))
        pair = {"quantity": name, "catala_value": actual_value, "llm_value": node["value"],
                "catala_provisions": row["provisions"], "supporting_provisions": sorted(support),
                "llm_provision": node.get("provision"), "evidence": node["evidence"],
                "public_input_contexts": prepared["quantity_contexts"].get(name, []),
                "catala_definition_id": actual.get("definition_id"), "llm_node_id": node["id"]}
        if equal is None:
            incomparable.append({**pair, "reason": "incomparable value representation"})
        elif equal:
            matched.append(name)
        else:
            mismatches.append(pair)
        if support and node.get("provision") and not any(provision_ids_overlap(p, node["provision"]) for p in support):
            attribution.append({**pair, "requires_review": True})
    unequal = {row["quantity"] for row in mismatches}
    def closure(name):
        pending, seen = list(dependencies.get(name, ())), set()
        while pending:
            item = pending.pop()
            if item not in seen:
                seen.add(item)
                pending.extend(dependencies.get(item, ()))
        return seen - {name}
    frontier = [row for row in mismatches if not (closure(row["quantity"]) & unequal)]
    catala_nodes = [{"quantity": name, "value": unwrap(node.get("value")),
                    "provisions": by_quantity[name]["provisions"],
                    "ancestor_quantities": sorted(prepared["ancestors"].get(name, ())),
                    "public_input_contexts": prepared["quantity_contexts"].get(name, [])}
                   for name, node in prepared["selected"].items()]
    return {"format": FORMAT, "status": "compared", "matched_quantities": matched,
            "value_mismatches": mismatches, "provision_attribution_differences": attribution,
            "earliest_comparable_mismatches": frontier, "missing_llm_counterparts": missing,
            "unmapped_llm_nodes": unmapped, "ambiguous": ambiguous, "incomparable": incomparable,
            "unobserved_catala_quantities": sorted(set(llm) - set(prepared["selected"])),
            "catala_graph": {"nodes": catala_nodes, "dependency_semantics": "transitive runtime definition ancestry"},
            "llm_graph": {"nodes": mapped_nodes},
            "limitation": "Partial label-based correspondence. Missing, ambiguous, or unmatched nodes do not establish a defect."}
