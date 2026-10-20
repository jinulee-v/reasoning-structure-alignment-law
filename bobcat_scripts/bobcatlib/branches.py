"""Branch coverage: what fraction of the port's decisions went every way.

BOBCat emits deterministic `(decision_id, outcome_id)` pairs for the manifest
and for every concrete execution. Those IDs are the metric; source positions
are never used as identities. The `branches` plugin retained below supplies
human-readable names and locations only when an uncovered-outcome listing is
requested.

A **decision** is a point where control can go more than one way: an
`if`/`then`/`else`, a `match` (one outcome per arm), or a default group with at
least two alternatives (`definition` plus one or more `exception`s). A single
unconditional `definition` compiles to a default group with one alternative and
is *not* a decision --- counting it would put a rule with no choice in it into
the denominator and quietly inflate the result.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .coverage import Position

TOOL_SRC = paths.SCRIPTS / "branch_tool"
PLUGIN_DIR = paths.TOOLS / "branch_tool" / "default"


def build_plugin(verbose: bool = True) -> Path:
    """Build `catala_branches.cmxs` against the BOBCat switch's libraries.

    Like the coverage tool, it lives outside the pinned compiler checkout: that
    checkout is an upstream commit plus two patches and should stay
    recognizable as one. `catala.driver` is an ordinary findlib library in the
    switch, so a plugin can be built against it from anywhere.
    """
    r = subprocess.run(
        ["dune", "build", "--root", str(TOOL_SRC),
         "--build-dir", str(paths.TOOLS / "branch_tool"),
         "catala_branches.cmxs"],
        env=paths.bobcat_env(), capture_output=True, text=True,
        cwd=str(paths.ROOT))
    if r.returncode != 0:
        raise RuntimeError("building catala_branches.cmxs failed:\n"
                           + r.stdout + r.stderr)
    if verbose:
        print(f"  branch plugin: {paths.rel(PLUGIN_DIR)}")
    return PLUGIN_DIR


def plugin_env() -> dict:
    env = paths.bobcat_env()
    env["CATALA_PLUGINS"] = str(PLUGIN_DIR.resolve())
    return env


# ---- the inventory --------------------------------------------------------
@dataclass(frozen=True)
class Outcome:
    """One way a decision can go, and where that shows up in the coverage map."""
    kind: str            # if | match | default
    name: str            # then/else, Enum.Constructor, base/exception
    guarded: bool        # False only for a default's unconditional base case
    group: Position      # identifies the decision
    pos: Position        # reached exactly when this outcome is taken


@dataclass
class Decision:
    kind: str
    group: Position
    outcomes: list = field(default_factory=list)

    @property
    def file(self) -> str:
        return self.group.file

    @property
    def real(self) -> bool:
        """Is there actually a choice here?

        `if` and `match` always are. A default group is only a decision once it
        has an alternative to the base case --- an `exception`, or a
        `definition ... under condition`. An unconditional `definition` is one
        alternative and no choice.
        """
        return len(self.outcomes) >= 2

    def covered(self, reached: dict) -> int:
        return sum(1 for o in self.outcomes if reached.get(o.pos, False))

    def full(self, reached: dict) -> bool:
        return self.covered(reached) == len(self.outcomes)


# `-W` inlines the standard library like any other module, so `if`s inside
# `Money.min` land in the inventory.  The coverage side already drops them
# (`Coverage.filter_files` on the stdlib directory), so they must leave the
# denominator too, else ratios count decisions no port author wrote.
STDLIB_PREFIX = "_build/libcatala"


def is_stdlib(pos: Position) -> bool:
    return STDLIB_PREFIX in pos.file


def inventory(project: Path, source: str, whole_program: bool = True) -> list:
    """Run the plugin over `source` in `project`; return its Outcomes.

    `whole_program` must match the replay in `coverage.replay_row`: with `-W`
    the modules are inlined and their decisions are part of the program, and
    without it they are opaque compiled objects with no positions to reach.
    """
    cmd = [str(paths.CATALA), "branches", source,
           "-I", ".", "--stdlib", "_build/libcatala",
           "--color=never", "-o", "-"]
    includes = project / "includes"
    if includes.exists():
        for directory in sorted(p for p in includes.iterdir() if p.is_dir()):
            cmd += ["-I", str(directory.relative_to(project))]
    if whole_program:
        cmd.insert(3, "-W")
    r = subprocess.run(cmd, cwd=project, env=plugin_env(),
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"branch inventory of {source} failed:\n"
                           f"{r.stdout}{r.stderr}")
    out = []
    for line in r.stdout.splitlines()[1:]:      # drop the header
        if not line.strip():
            continue
        (kind, name, guarded,
         gf, gsl, gsc, gel, gec,
         of_, osl, osc, oel, oec) = line.split("\t")
        o = Outcome(
            kind=kind, name=name, guarded=guarded == "true",
            group=Position(gf, int(gsl), int(gsc), int(gel), int(gec)),
            pos=Position(of_, int(osl), int(osc), int(oel), int(oec)))
        if not is_stdlib(o.group):
            out.append(o)
    return out


def decisions(outcomes: list) -> list:
    """Fold outcomes into decisions, keeping only the ones with a real choice."""
    by_group: dict = defaultdict(list)
    for o in outcomes:
        group = by_group[(o.kind, o.group)]
        # A source wildcard is lowered to one arm per missing enum constructor;
        # all those compiler arms retain the wildcard body's exact span. They
        # are one written outcome and must have one denominator entry.
        if not any(existing.pos == o.pos for existing in group):
            group.append(o)
    ds = [Decision(kind=k, group=g, outcomes=os)
          for (k, g), os in by_group.items()]
    return [d for d in ds if d.real]


_POSITION = re.compile(
    r"^(?P<file>.*):(?P<sl>\d+):(?P<sc>\d+)-(?P<el>\d+):(?P<ec>\d+)$")


def _native_outcome_position(pair: str) -> Position:
    separators = [pair.rfind("/branch@"), pair.rfind("/default@")]
    split_at = max(separators)
    if split_at < 0:
        raise ValueError(f"invalid native branch pair: {pair}")
    outcome = pair[split_at + 1:]
    encoded = outcome.split("=>", 1)[-1]
    encoded = encoded.split("@", 1)[-1]
    match = _POSITION.match(encoded)
    if not match:
        raise ValueError(f"invalid native branch ID: {pair}")
    return Position(match["file"], int(match["sl"]), int(match["sc"]),
                    int(match["el"]), int(match["ec"]))


def native_trace(port: str, target_name: str) -> tuple[set[str], set[str]]:
    """Return the exact native outcome IDs in the manifest and trace.

    An empty manifest means this is an older run that must be regenerated;
    branch coverage is never approximated from statement positions.
    """
    src = paths.coverage(port) / f"{target_name}.jsonl"
    if not src.exists():
        return set(), set()
    manifest_pairs, reached = set(), set()
    for line in src.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("kind") == "branch_manifest":
            manifest_pairs.update(record["branches"])
        elif record.get("kind") == "branch_path":
            reached.update(record["branches"])
    return manifest_pairs, reached


def has_native_manifest(port: str, target_name: str) -> bool:
    """Whether generation emitted a manifest, including an empty one."""
    src = paths.coverage(port) / f"{target_name}.jsonl"
    if not src.exists():
        return False
    return any(json.loads(line).get("kind") == "branch_manifest"
               for line in src.read_text().splitlines() if line.strip())


def native_positions(pairs: set[str]) -> set[Position]:
    """Project native IDs to spans for display/plugin-inventory joins only."""
    return {_native_outcome_position(pair) for pair in pairs}


def filter_native(pairs: set[str], files: set[str]) -> set[str]:
    """Keep IDs whose outcome belongs to a formalization source file."""
    return {pair for pair in pairs
            if Path(_native_outcome_position(pair).file).name in files}


def native_totals(manifest: set[str], reached: set[str]) -> dict:
    """Count exact source decisions/outcomes without collapsing their spans."""
    decisions: dict[str, list[str]] = defaultdict(list)
    for pair in manifest:
        separators = [pair.rfind("/branch@"), pair.rfind("/default@")]
        split_at = max(separators)
        if split_at < 0:
            raise ValueError(f"invalid native branch pair: {pair}")
        decisions[pair[:split_at]].append(pair)

    full = partial = 0
    for outcomes in decisions.values():
        covered = sum(outcome in reached for outcome in outcomes)
        if covered == len(outcomes):
            full += 1
        elif covered:
            partial += 1
    return {
        "decisions": len(decisions),
        "decisions_full": full,
        "decisions_partial": partial,
        "outcomes": len(manifest),
        "outcomes_covered": len(manifest & reached),
    }


def restrict(ds: list[Decision], manifest: set[Position]) -> list[Decision]:
    """Restrict a compiler inventory to outcomes in a native manifest."""
    out = []
    for decision in ds:
        outcomes = [outcome for outcome in decision.outcomes
                    if outcome.pos in manifest]
        candidate = Decision(decision.kind, decision.group, outcomes)
        if candidate.real:
            out.append(candidate)
    return out


# ---- the join -------------------------------------------------------------
@dataclass
class FileBranches:
    file: str
    decisions: int = 0
    decisions_full: int = 0
    decisions_partial: int = 0
    outcomes: int = 0
    outcomes_covered: int = 0

    @property
    def decisions_none(self) -> int:
        return self.decisions - self.decisions_full - self.decisions_partial


def tally(ds: list, reached: dict) -> dict:
    """{file: FileBranches} for the decisions in `ds` under coverage `reached`."""
    files: dict = {}
    for d in ds:
        f = files.setdefault(d.file, FileBranches(d.file))
        c = d.covered(reached)
        f.decisions += 1
        f.outcomes += len(d.outcomes)
        f.outcomes_covered += c
        if c == len(d.outcomes):
            f.decisions_full += 1
        elif c:
            f.decisions_partial += 1
    return files


def uncovered(ds: list, reached: dict) -> list:
    """Every outcome a suite never took, most-decided-against first.

    This is the actionable half of the report: each row is a branch of the
    statute that no generated input exercises.
    """
    out = []
    for d in ds:
        for o in d.outcomes:
            if not reached.get(o.pos, False):
                out.append((d, o))
    out.sort(key=lambda t: (t[1].pos.file, t[1].pos.start_line,
                            t[1].pos.start_col))
    return out
