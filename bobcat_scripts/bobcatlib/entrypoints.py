"""Every way into a port, and a wrapper scope for the ones that need one.

A Catala file is not one program. Each `declaration scope X` is a separate
entry point with its own inputs, and each top-level `declaration f ... depends
on ...` is a function that runs only if something calls it. BOBCat explores
one entry point per run, so the automatic census names every enterable native
scope and top-level function rather than relying on a curated subset.

This module enumerates them, decides which BOBCat can actually enter, and
writes the wrapper scopes the functions need.

**Enterable** means every input type is one the BOBCat solver encodes.
The local BOBCat patches encode bounded lists and polymorphic optionals, so
those entry points are included as well.

A generated wrapper adds no rule. It declares one input per parameter and one
output, and its body is a single call. Consequently it exposes existing Catala
without adding or paraphrasing a rule.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import identifiers, paths

# The single capability gate used by the census as new encodings are added.
UNENCODABLE = ()

_MODULE = re.compile(r"^>\s*Module\s+(\S+)")
_USING = re.compile(r"^>\s*Using\s+(\S+)\s+as\s+(\S+)")
_TYPEDECL = re.compile(
    r"^(?:declaration (?:structure|enumeration)|"
    r"déclaration (?:structure|énumération)) (\S+)\s*:")
_SCOPEDECL = re.compile(
    r"^(?:declaration scope|déclaration champ d'application) (\S+)\s*:")
_TOPDEF = re.compile(r"^(?:declaration|déclaration) (\S+) "
                     r"(?:content|contenu) ")
_SCOPEITEM = re.compile(
    r"^\s+(input|context|output|internal|entrée|contexte|résultat|interne)"
    r"\s+(\S+)\s+(?:content|contenu)\s+(.*?)\s*$")


def _mentions(type_expr: str, name: str) -> bool:
    """Whether a type expression mentions the (possibly CJK) type ``name``.

    Using the declarations collected from the port avoids assuming that a type
    name has an ASCII uppercase initial. Identifier tokenization uses the same
    Unicode XID rules as the patched Catala lexer.
    """
    return any(token.rsplit(".", 1)[-1] == name
               for _, _, token in identifiers.scan(type_expr))


@dataclass
class Signature:
    """One entry point: a scope, or a top-level function."""
    kind: str                    # scope | function
    name: str
    file: str
    module: str
    line: int
    params: list = field(default_factory=list)   # [(name, type-as-written)]
    result: str = ""                             # functions only

    @property
    def qualified(self) -> str:
        return f"{self.module}.{self.name}"


@dataclass
class Port:
    directory: Path
    types: dict = field(default_factory=dict)      # name -> [member type strings]
    type_file: dict = field(default_factory=dict)  # type name -> declaring file
    modules: dict = field(default_factory=dict)    # file name -> module name
    usings: dict = field(default_factory=dict)     # file name -> [(module, alias)]
    entries: list = field(default_factory=list)


def _block(lines: list, start: int) -> tuple:
    """The indented body that follows `lines[start]`, and the line after it."""
    body, j = [], start + 1
    while j < len(lines) and (lines[j].startswith("  ") or not lines[j].strip()):
        body.append(lines[j])
        j += 1
    return body, j


def scan(directory: Path, sources=None) -> Port:
    """Parse entry-point signatures from ``sources`` (the directory by default)."""
    port = Port(directory=directory)
    for f in (paths.source_files(directory) if sources is None else sources):
        lines = f.read_text().splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            m = _MODULE.match(line)
            if m and identifiers.is_identifier(m.group(1)):
                port.modules[f.name] = m.group(1)
                i += 1
                continue
            m = _USING.match(line)
            if m and identifiers.is_qualified_identifier(m.group(1)) \
                    and identifiers.is_identifier(m.group(2)):
                port.usings.setdefault(f.name, []).append((m.group(1),
                                                           m.group(2)))
                i += 1
                continue
            m = _TYPEDECL.match(line)
            if m and identifiers.is_identifier(m.group(1)):
                body, i = _block(lines, i)
                port.types[m.group(1)] = body
                port.type_file[m.group(1)] = f.name
                continue
            m = _SCOPEDECL.match(line)
            if m and identifiers.is_identifier(m.group(1)):
                body, i = _block(lines, i)
                params = []
                for b in body:
                    im = _SCOPEITEM.match(b)
                    if im and im.group(1) in ("input", "context", "entrée",
                                              "contexte") \
                            and identifiers.is_identifier(im.group(2)):
                        params.append((im.group(2), im.group(3)))
                port.entries.append(Signature(
                    kind="scope", name=m.group(1), file=f.name,
                    module=port.modules.get(f.name, ""),
                    line=i - len(body), params=params))
                continue
            m = _TOPDEF.match(line)
            if m and identifiers.is_identifier(m.group(1)):
                # A top-level declaration runs to its `equals`, or to the end of
                # its indented block if it has none.
                blk, j = [line], i + 1
                while "equals" not in " ".join(blk) and j < len(lines) \
                        and lines[j].startswith("  "):
                    blk.append(lines[j])
                    j += 1
                sig = " ".join(blk)
                if "depends on" in sig:
                    head = sig.split("depends on", 1)
                    result = head[0].split("content", 1)[1].strip()
                    args = re.split(r",(?![^(]*\))",
                                    head[1].split("equals")[0])
                    params = []
                    for a in args:
                        am = re.match(r"\s*(\S+)\s+content\s+(.*?)\s*$", a)
                        if am and identifiers.is_identifier(am.group(1)):
                            params.append((am.group(1), am.group(2).strip()))
                    port.entries.append(Signature(
                        kind="function", name=m.group(1), file=f.name,
                        module=port.modules.get(f.name, ""), line=i + 1,
                        params=params, result=result))
                i = j
                continue
            i += 1
    return port


def unencodable(type_expr: str, types: dict, seen=None) -> bool:
    """Does this type reach an unsupported option, directly or via a field?"""
    seen = seen or set()
    if any(x in type_expr for x in UNENCODABLE):
        return True
    for name in types:
        if name in seen or not _mentions(type_expr, name):
            continue
        seen.add(name)
        if any(unencodable(m, types, seen) for m in types[name]):
            return True
    return False


def enterable(sig: Signature, types: dict) -> bool:
    if not sig.params:
        return sig.kind == "scope"
    if any(unencodable(t, types, set()) for _, t in sig.params):
        return False
    return not (sig.kind == "function"
                and unencodable(sig.result, types, set()))


def scope_name(fn: str) -> str:
    """`carry_on_fits` -> `FnCarryOnFits`, a legal Catala scope name."""
    return "Fn" + "".join(p.capitalize() for p in fn.split("_"))


def qualify(type_expr: str, port: Port, source: str) -> str:
    """Prefix `Src.` onto types the source module declares itself.

    A wrapper sees the source as an imported module, so `Bag` --- a structure
    of `Airline.catala_en` --- has to be written `Src.Bag` there even though
    the declaration it was copied from writes it bare. Types that came from
    somewhere else already carry the source's own alias, which the wrapper
    replicates, so they are left alone.
    """
    # Work from declarations rather than initial-letter case. This covers all
    # Unicode XID names, including scripts without case and combining marks.
    local = [name for name, declared_in in port.type_file.items()
             if declared_in == source]
    replacements = []
    for start, end, token in identifiers.scan(type_expr):
        if "." not in token and token in local:
            replacements.append((start, end, f"Src.{token}"))
    for start, end, replacement in reversed(replacements):
        type_expr = type_expr[:start] + replacement + type_expr[end:]
    return type_expr


def harness_for(port: Port, source: str, sigs: list) -> str:
    """A wrapper file exposing `sigs`, all of them functions of `source`.

    The source's own `> Using ... as ...` lines are replicated verbatim, so the
    parameter types can be copied from the declaration without rewriting the
    aliases in them. The defining module gets the alias `Src`, which no port
    file uses.
    """
    module = port.modules[source]
    out = [f"# Wrapper scopes for `{module}`", "",
           f"> Module {module}Wrappers", ""]
    for mod, alias in port.usings.get(source, []):
        out.append(f"> Using {mod} as {alias}")
    out += [f"> Using {module} as Src", "",
            "Generated by `bobcat_scripts/generate_dataset.py`; edits are",
            "overwritten. Each scope below adds no rule: it declares one input",
            "per parameter of a top-level function of the port and returns what",
            "that function returns. BOBCat explores one entry point per run,",
            "and a top-level function is not one until something names it.", "",
            "```catala-metadata"]
    for s in sigs:
        out.append(f"declaration scope {scope_name(s.name)}:")
        for n, t in s.params:
            out.append(f"  input {n} content {qualify(t, port, source)}")
        out.append(f"  output result content {qualify(s.result, port, source)}")
        out.append("")
    out += ["```", "", "```catala"]
    for s in sigs:
        args = ", ".join(n for n, _ in s.params)
        out += [f"scope {scope_name(s.name)}:",
                f"  definition result equals Src.{s.name} of {args}", ""]
    out.append("```")
    return "\n".join(out) + "\n"


def write_harnesses(port: Port, outdir: Path) -> dict:
    """Write one wrapper file per source that has enterable functions.

    `outdir` is the port's own `harnesses/generated/`: a wrapper is Catala
    against one port and belongs beside it, not beside the pipeline.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    by_source: dict = {}
    for s in port.entries:
        if s.kind == "function" and enterable(s, port.types):
            by_source.setdefault(s.file, []).append(s)
    written = {}
    for source, sigs in sorted(by_source.items()):
        stem, language = source.split(".catala_", 1)
        path = outdir / f"{stem}Wrappers.catala_{language}"
        path.write_text(harness_for(port, source, sigs))
        written[path] = sigs
    return written


# ---- the census -----------------------------------------------------------
def blocker(sig, types) -> str:
    """The first parameter that keeps this entry point out, and why."""
    for name, t in sig.params:
        if unencodable(t, types, set()):
            direct = any(x in t for x in UNENCODABLE)
            return f"{name}: {t}" + ("" if direct else " (through a field)")
    if sig.kind == "function" and unencodable(sig.result, types, set()):
        return f"returns {sig.result}"
    return "no inputs"


def census(name: str, directory: Path, outdir: Path | None = None) -> dict:
    """Count one port's entry points, and write the wrappers for them.

    Returns the counts and the lines of `ENTRY_POINTS.md`.  With `outdir` set,
    one wrapper file per source holding enterable functions is (re)written
    there --- the wrappers are what turn those functions into targets, so the
    census and the files it describes are produced in the same pass and cannot
    drift apart.
    """
    p = scan(directory)
    sc = [s for s in p.entries if s.kind == "scope"]
    fn = [s for s in p.entries if s.kind == "function"]
    ok_sc = [s for s in sc if enterable(s, p.types)]
    ok_fn = [s for s in fn if enterable(s, p.types)]
    ok, total = len(ok_sc) + len(ok_fn), len(sc) + len(fn)

    L = [f"# Entry points of the {name} port", "",
         "Every `declaration scope` and every top-level "
         "`declaration ... depends on ...`. BOBCat explores one per run.",
         "",
         f"**{ok} of {total} entry points are enterable.**",
         "",
         "**Enterable** means every input type is one the BOBCat solver "
         "encodes. The local BOBCat patches encode bounded "
         "lists, including list fields reached through structures. "
         "They also encode polymorphic optionals as symbolic `Absent` / "
         "`Present payload` sums.", "",
         "| | entry points | enterable |", "|---|--:|--:|",
         f"| scopes | {len(sc)} | {len(ok_sc)} |",
         f"| top-level functions | {len(fn)} | {len(ok_fn)} |",
         f"| **total** | **{total}** | **{ok}** |", "",
         "Enterable:", "",
         "| kind | name | where |", "|---|---|---|"]
    for s in ok_sc + ok_fn:
        L.append(f"| {s.kind} | `{s.name}` | `{s.file}:{s.line}` |")
    L += ["", "Blocked, with the first input that blocks it:", "",
          "| kind | name | blocked by |", "|---|---|---|"]
    for s in sc + fn:
        if not enterable(s, p.types):
            L.append(f"| {s.kind} | `{s.name}` | `{blocker(s, p.types)}` |")
    L.append("")

    written = write_harnesses(p, outdir) if outdir is not None else {}
    return {"port": p, "scopes": len(sc), "scopes_enterable": len(ok_sc),
            "functions": len(fn), "functions_enterable": len(ok_fn),
            "enterable": ok, "total": total, "lines": L, "written": written}
