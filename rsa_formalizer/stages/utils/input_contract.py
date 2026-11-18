"""Read frozen input contracts without exposing executable implementations."""

from pathlib import Path
import re

from .common import parse_fenced_document


def field_descriptions(run: Path, schema: dict) -> str:
    """Include prose, field comments, and helper documentation from input modules.

    Reachable schema declarations select the contributing frozen modules. Their
    prose is part of the contract even when the statute manifest omits them.
    Executable bodies and candidate workspace files never enter this text.
    """
    wanted = set()
    definitions = schema.get("definitions", {})

    def visit(node):
        if isinstance(node, dict):
            reference = node.get("$ref", "")
            if reference.startswith("#/definitions/"):
                name = reference.rsplit("/", 1)[-1]
                if name not in wanted:
                    wanted.add(name)
                    visit(definitions.get(name, {}))
            for key, value in node.items():
                if key != "definitions":
                    visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(schema)
    lines = []
    for source in sorted((run / "input").rglob("*.catala_en")):
        text = source.read_text(encoding="utf-8")
        module = re.search(r"(?m)^>\s*Module\s+(\w+)\s*$", text)
        namespaces = list(dict.fromkeys([module[1], source.stem] if module else [source.stem]))
        document = parse_fenced_document(source)
        declarations = "\n".join(block.decode("utf-8") for block in document.blocks) if document.blocks else text
        fields = []
        current = None
        continuation = False
        for line in declarations.splitlines():
            declaration = re.match(r"^declaration (?:structure|enumeration) (\w+):(?:\s*#\s*(.*))?$", line)
            if declaration:
                names = [f"{namespace}.{declaration[1]}" for namespace in namespaces]
                current = next((name for name in names if name in wanted), None)
                continuation = bool(current and declaration[2])
                if current:
                    fields.append(f"{current}: {declaration[2] or ''}".rstrip())
                continue
            if line and not line[0].isspace() and not line.startswith("#"):
                current = None
            if current:
                field = re.match(r"\s+data (\w+) content ([^#]+)#\s*(.+)$", line)
                variant = re.match(r"\s+-- (\w+)(?: content [^#]+)?\s+#\s*(.+)$", line)
                if field:
                    fields.append(f"- {current}.{field[1]} ({field[2].strip()}): {field[3]}")
                elif variant:
                    fields.append(f"- {current}.{variant[1]}: {variant[2]}")
                elif continuation and (comment := re.match(r"\s*#\s*(.+)$", line)):
                    fields.append("  " + comment[1])
                    continue
                continuation = bool(field or variant)
            else:
                continuation = False
        if not fields:
            continue
        prose = document.skeleton.decode("utf-8").replace("\r\n", "\n") if document.blocks else ""
        prose = re.sub(r"(?m)^```catala[^\n]*\n<RSA-CATALA-BODY>\n```[ \t]*(?:\n|$)", "", prose)
        prose = re.sub(r"<!--[\s\S]*?-->", "", prose)
        prose = re.sub(r"(?m)^>\s*(?:Module|Using)\b[^\n]*(?:\n|$)", "", prose).strip()
        helpers = []
        for block in document.blocks:
            for line in block.decode("utf-8").splitlines():
                helper = re.match(r"^declaration (?!structure\b|enumeration\b|scope\b)(\w+) content [^#]+#\s*(.+)$", line)
                if helper:
                    helpers.append(f"- {namespaces[0]}.{helper[1]}: {helper[2]}")
        lines.append(f"INPUT CONTRACT MODULE: {source.relative_to(run / 'input').as_posix()}")
        if prose:
            lines.extend(["CONVENTIONS AND DOCUMENTATION", prose])
        lines.extend(["FIELD AND TYPE DESCRIPTIONS", *fields])
        if helpers:
            lines.extend(["HELPER DOCUMENTATION", *dict.fromkeys(helpers)])
    return "\n".join(lines)
