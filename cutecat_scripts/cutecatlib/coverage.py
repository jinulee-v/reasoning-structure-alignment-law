"""How much of the port each suite actually executes.

The dataset says how many paths CUTECat found.  That is a property of the
engine, not of the statute: fifteen paths through a scope with three rules and
fifteen through a scope with forty are not the same achievement.  This module
answers the other question --- of the Catala the suite runs against, how much
does it reach --- and it answers it with the compiler's own coverage machinery
rather than with a guess.

Three steps.

1. **Record.** `catala concolic --conc-code-coverage` writes a reachable map,
   the one-time initialization map, and a reached-only map for every generated
   path. Older dataset rows are replayed through `catala interpret
   --code-coverage --quiet`; that fallback needs
   `patches/coverage-with-input.patch`.

2. **Union.**  Each run ends its line with `Scope: passed|<hex>`, and the hex
   is a marshalled OCaml value that nothing outside the compiler can read.  So
   the union happens in OCaml --- `coverage_tool/catala_coverage.ml`, built
   against the libraries the CUTECat switch installs --- and what crosses over
   here is one tab-separated record per position.

3. **Count**, in the statute's units and in the compiler's, because the two do
   not agree and only the second is exact:

   * a **rule** is one item of Catala source --- a top-level `declaration`, a
     `scope` header, or a `definition` / `rule` / `exception` inside a scope ---
     which `parse_items` recovers from the file itself;
   * a **branch** is one recorded expression position inside a rule: an arm of
     a `match`, a side of an `and`, a candidate of a default.  This is the
     compiler's own unit and the numerator and denominator are exact.

Two things have to be read with the numbers or they will be believed too
easily.

`merge_with_reachable_positions` drops a file in which *nothing* was reached, so
the denominator is the part of the program the suite enters --- not the whole
port.  The report names the port files that fell out that way; they are 0%, and
quoting the ratio without them would flatter the suite.

And "reached" is not "run".  In whole-program mode the interpreter builds a
closure for every top-level definition in every module it links, and that marks
one position: the definition's own name.  A module nothing calls therefore comes
back with one reached position per declaration and no arm of any body ---
`Item.exercised` is what tells the two apart.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

TOOL_SRC = paths.SCRIPTS / "coverage_tool"
TOOL = paths.TOOLS / "coverage_tool/default/catala_coverage.exe"


class InputError(ValueError):
    """A dataset value this module cannot express as interpreter input."""


# ---- dataset row -> `catala interpret --input` JSON -----------------------
def input_json(inputs: dict) -> dict:
    """The row's inputs in the shape `--input` accepts.

    Two differences from the dataset's own encoding, both of them the
    compiler's convention rather than a choice made here: the scope's input
    struct names a field `agi_in` where the scope declares `agi`, and an
    enumeration is a bare string.  `catala json-schema -s SCOPE` prints the
    shape this has to produce.
    """
    return {_strip_in(k): _value(v) for k, v in inputs.items()}


def _strip_in(name: str) -> str:
    return name[:-3] if name.endswith("_in") else name


def _value(v):
    if isinstance(v, dict):
        if "cons" in v:
            if "payload" in v:
                # The reader takes `{"Cons": payload}` for a constructor that
                # carries one.  Written but not exercised: nothing needs it yet.
                return {v["cons"]: _value(v["payload"])}
            return v["cons"]
        if "struct" in v:
            return {k: _value(x) for k, x in v["fields"].items()}
        if set(v) == {"years", "months", "days"}:
            raise InputError("durations are not expressible as scope input here")
        raise InputError(f"unrecognized value {v!r}")
    if isinstance(v, list):
        return [_value(x) for x in v]
    return v                       # bool, int, and the strings: money, date


# ---- the OCaml union tool -------------------------------------------------
def build_tool(verbose: bool = True) -> Path:
    """Build `catala_coverage.exe` against the CUTECat switch's libraries.

    It lives outside the pinned compiler checkout on purpose: that checkout is
    an upstream commit plus two patches, and it should stay recognizable as
    that.  Everything the tool needs --- `catala.shared_ast` --- the switch
    installs as an ordinary findlib library.
    """
    r = subprocess.run(
        ["dune", "build", "--root", str(TOOL_SRC),
         "--build-dir", str(paths.TOOLS / "coverage_tool"),
         "catala_coverage.exe"],
        env=paths.cutecat_env(), capture_output=True, text=True,
        cwd=str(paths.ROOT))
    if r.returncode != 0:
        raise RuntimeError("building catala_coverage.exe failed:\n"
                           + r.stdout + r.stderr)
    if verbose:
        print(f"  coverage tool: {paths.rel(TOOL)}")
    return TOOL


@dataclass(frozen=True)
class Position:
    file: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    def contains(self, other: "Position") -> bool:
        if self.file != other.file or self == other:
            return False
        a = (self.start_line, self.start_col) <= (other.start_line,
                                                  other.start_col)
        b = (other.end_line, other.end_col) <= (self.end_line, self.end_col)
        return a and b


def union_dumps(dumps: list) -> dict:
    """Feed the hex dumps to the tool; return {Position: reached}."""
    r = subprocess.run([str(TOOL)], input="\n".join(dumps), text=True,
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("catala_coverage.exe failed:\n" + r.stderr)
    out: dict = {}
    for line in r.stdout.splitlines():
        f, sl, sc, el, ec, reached, _scopes = line.split("\t")
        out[Position(f, int(sl), int(sc), int(el), int(ec))] = reached == "1"
    return out


def native_dumps(port: str, target_name: str, rows: list) -> tuple[list, list]:
    """Return native dumps and rows that still require an interpreter replay.

    New datasets record one reachable-position baseline and one reached-only
    dump per generated path.  Older datasets have no companion file and fall
    back transparently to the replay path.
    """
    src = paths.coverage(port) / f"{target_name}.jsonl"
    if not src.exists():
        return [], rows
    reachable = None
    initial = None
    by_path = {}
    for line in src.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("kind") == "reachable":
            reachable = record["coverage"]
        elif record.get("kind") == "initial":
            initial = record["coverage"]
        elif record.get("kind") == "path":
            by_path[record["path"]] = record["coverage"]
    if reachable is None:
        return [], rows
    dumps = [reachable]
    if initial is not None:
        dumps.append(initial)
    missing = []
    for row in rows:
        dump = by_path.get(row["path"])
        if dump is None:
            missing.append(row)
        else:
            dumps.append(dump)
    return dumps, missing


# ---- replay ---------------------------------------------------------------
def replay_row(target, project: Path, row: dict, timeout: int = 300):
    """One `catala interpret --code-coverage` run; returns its hex dump."""
    cmd = [str(paths.CATALA), "interpret", target.harness.name,
           "-s", target.scope,
           "-I", ".",
           "--stdlib", "_build/libcatala",
           "-W", "--color=never", "--message-format=gnu",
           "--code-coverage", "--quiet",
           "--input", json.dumps(input_json(row["inputs"]))]
    r = subprocess.run(cmd, cwd=project, env=paths.cutecat_env(),
                       capture_output=True, text=True, timeout=timeout)
    for line in r.stdout.splitlines():
        if "|" in line and ": passed|" in line:
            return line.split("|", 1)[1].strip()
    raise RuntimeError(
        f"no coverage dump from {target.name} path {row['path']}:\n"
        f"{r.stdout}{r.stderr}")


# ---- counting -------------------------------------------------------------
@dataclass
class FileCoverage:
    file: str
    positions: int = 0
    positions_reached: int = 0
    rules: int = 0                 # maximal spans
    rules_reached: int = 0         # ... with the rule's own span reached
    rules_full: int = 0            # ... and every span nested in it too
    branches: int = 0              # spans nested inside a rule
    branches_reached: int = 0
    lines: set = field(default_factory=set)
    lines_reached: set = field(default_factory=set)


def summarise(cov: dict) -> dict:
    """{Position: reached} -> per-file and total counts.

    A *rule* is a maximal position: one contained in no other.  In a Catala
    file that is the span of a whole top-level definition, of a scope rule, or
    of an exception --- so counting them counts the statute's own units rather
    than the compiler's.  Everything nested inside one is a *branch* of it.
    """
    by_file: dict = defaultdict(list)
    for pos, reached in cov.items():
        by_file[pos.file].append((pos, reached))

    out: dict = {}
    for f, entries in sorted(by_file.items()):
        fc = FileCoverage(file=f)
        positions = [p for p, _ in entries]
        reached_of = dict(entries)
        # Maximal spans: sort longest-first, keep one only if no already kept
        # span contains it.  Quadratic in the file's few thousand spans.
        order = sorted(positions,
                       key=lambda p: (p.start_line, p.start_col,
                                      -p.end_line, -p.end_col))
        maximal: list = []
        for p in order:
            if not any(m.contains(p) for m in maximal):
                maximal.append(p)
        maximal_set = set(maximal)

        for p in positions:
            fc.positions += 1
            for ln in range(p.start_line, p.end_line + 1):
                fc.lines.add(ln)
            if reached_of[p]:
                fc.positions_reached += 1
                for ln in range(p.start_line, p.end_line + 1):
                    fc.lines_reached.add(ln)
            if p not in maximal_set:
                fc.branches += 1
                if reached_of[p]:
                    fc.branches_reached += 1

        for m in maximal:
            fc.rules += 1
            if reached_of[m]:
                fc.rules_reached += 1
                inner = [p for p in positions if m.contains(p)]
                if all(reached_of[p] for p in inner):
                    fc.rules_full += 1
        out[f] = fc
    return out


def totals(files: dict) -> dict:
    t = {"positions": 0, "positions_reached": 0, "rules": 0,
         "rules_reached": 0, "rules_full": 0, "branches": 0,
         "branches_reached": 0, "lines": 0, "lines_reached": 0}
    for fc in files.values():
        for k in ("positions", "positions_reached", "rules", "rules_reached",
                  "rules_full", "branches", "branches_reached"):
            t[k] += getattr(fc, k)
        t["lines"] += len(fc.lines)
        t["lines_reached"] += len(fc.lines_reached)
    return t


def pct(num: int, den: int) -> float:
    return 100.0 * num / den if den else 0.0


# ---- the statute's own units: top-level items and scope rules -------------
# The span-based counts above are the compiler's units: exact, but not the ones
# a reader of the statute has.  These map coverage back onto the Catala source:
# one item per `declaration`, per `scope`, and per `definition` / `rule` /
# `exception` inside a scope.
_ITEM_TOP = re.compile(r"^(declaration|scope)\b")
_ITEM_RULE = re.compile(r"^ {2}(definition|rule|exception|assertion|label)\b")
_FENCE = re.compile(r"^```(catala(-metadata)?)?\s*$")


@dataclass
class Item:
    """One top-level declaration, or one rule inside a scope."""
    file: str
    kind: str                      # declaration | scope | definition | ...
    header: str                    # the source line that opens it
    start_line: int
    end_line: int
    text: str = ""                 # the item's source, for classifying it
    positions: int = 0
    reached: int = 0

    @property
    def name(self) -> str:
        return " ".join(self.header.split()[:4])

    @property
    def constant(self) -> bool:
        """A top-level value, as against a function or a scope rule.

        `declaration us_pr content list of W.Country equals [...]` has no
        `depends on`, so the interpreter computes it once while loading the
        program and every position in it is reached --- by the loader, for
        every input, whether or not one line of the statute consults it.  Ten
        such lists in `Airline.catala_en` would otherwise report as ten rules
        the carry-on suite "exercised".  They are counted, and counted apart.
        """
        return (self.kind == "declaration"
                and "depends on" not in self.text
                and not self.header.startswith(
                    ("declaration scope", "declaration enumeration",
                     "declaration structure")))

    @property
    def exercised(self) -> bool:
        """Did the suite evaluate anything *in* this item?

        Two reached positions rather than one, and the distinction is not a
        fudge.  In whole-program mode the interpreter builds a closure for
        every top-level definition in every module it links, including modules
        nothing calls, and that marks exactly one position: the definition's
        own name.  `SaraKinship`'s fifteen "reached" positions are all of that
        kind --- one per declaration, no arm of any body --- and counting them
        as executed statute would be counting the loader's work as the suite's.

        A constant is excluded for the same reason at the other extreme: the
        loader reaches all of it, so it would always count.
        """
        return self.reached >= 2 and not self.constant


def parse_items(path: Path) -> list:
    """The items of a Catala file, in source order.

    Only fenced `catala` and `catala-metadata` blocks hold code; the prose
    between them is the statute and has no positions.  An item runs from its
    keyword line to the line before the next item's, so the comments that
    precede a definition belong to the item they introduce, which is where a
    reader would put them.
    """
    lines = path.read_text().splitlines()
    items: list = []
    in_block = False
    for i, line in enumerate(lines, start=1):
        m = _FENCE.match(line)
        if m:
            if in_block:
                in_block = False
            elif line.startswith("```catala"):
                in_block = True
            continue
        if not in_block:
            continue
        stripped = line.rstrip()
        if _ITEM_TOP.match(stripped) or _ITEM_RULE.match(stripped):
            kind = stripped.strip().split()[0]
            items.append(Item(file=path.name, kind=kind, header=stripped.strip(),
                              start_line=i, end_line=len(lines)))
            if len(items) > 1:
                items[-2].end_line = i - 1
    # Close the last item of each block at the fence that follows it.
    for it in items:
        end = it.end_line
        for j in range(it.start_line, min(end, len(lines)) + 1):
            if _FENCE.match(lines[j - 1]) and j > it.start_line:
                end = j - 1
                break
        it.end_line = end
        it.text = "\n".join(lines[it.start_line - 1:it.end_line])
    return items


def attribute(cov: dict, port_dirs: list) -> dict:
    """{file: [Item]} with each item's positions and reached count filled in.

    Only files the coverage map mentions are parsed: a file the program never
    linked has no positions to attribute and would otherwise show up as a row
    of zeroes with no way to tell it from one that was linked and never run.
    """
    sources = {}
    for d in port_dirs:
        for f in d.glob("*.catala_en"):
            sources[f.name] = f
    for d in port_dirs:
        for sub in ("harnesses", "harnesses/generated"):
            for f in (d / sub).glob("*.catala_en"):
                sources.setdefault(f.name, f)

    out: dict = {}
    for f in sorted({p.file for p in cov}):
        if f not in sources:
            continue
        items = parse_items(sources[f])
        for pos, reached in cov.items():
            if pos.file != f:
                continue
            for it in items:
                if it.start_line <= pos.start_line <= it.end_line:
                    it.positions += 1
                    if reached:
                        it.reached += 1
                    break
        out[f] = items
    return out
