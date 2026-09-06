"""CUTECat's `[RESULT]` stream, read back as paths.

A concolic run prints one block per path it drove the scope down:

    [RESULT]
    [RESULT] Evaluating with inputs:
    [RESULT] . b_in = true
    [RESULT] Output of scope after evaluation:
    [RESULT] . o = 1

and closes with `Concolic interpreter done`.  A path whose evaluation raised
instead prints `Found error ... at ...` where the outputs would be, and one
whose constraints could not be encoded prints nothing extra --- the warning for
that goes to stderr, and it is a property of the *run*, not of a path, so it is
picked up separately by `incomplete_run`.

`--message-format=gnu` is what makes this parseable: the default renders every
message in a Unicode box, wrapped to the terminal width, so a long struct comes
back across several lines with `│` down the left.  Under GNU each message is
exactly one line and newlines inside it become spaces (`unformat` in
`compiler/catala_utils/message.ml`).  `run.py` always passes it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import values
from .values import ParseError, Value

# `gnu_msg` puts a source position before the marker when the message carries
# one.  A result never does today, but tolerating the prefix is one group and
# keeps a whole run from reading as empty if that changes.
_RESULT = re.compile(r"^(?:[^\s\[]+: )?\[RESULT\] ?(?P<body>.*)$")

_FIELD = re.compile(r"^\. (?P<name>[^ ]+) = (?P<value>.*)$")
_ERROR = re.compile(r"^Found error (?P<what>.*?) at (?P<pos>\S+)$")
_COVERAGE_REACHABLE = re.compile(
    r"^CONCOLIC_COVERAGE_REACHABLE (?P<dump>[0-9a-fA-F]+)$")
_COVERAGE_INITIAL = re.compile(
    r"^CONCOLIC_COVERAGE_INITIAL (?P<dump>[0-9a-fA-F]+)$")
_COVERAGE_PATH = re.compile(
    r"^CONCOLIC_COVERAGE_PATH (?P<index>\d+) (?P<dump>[0-9a-fA-F]+)$")
_INCOMPLETE = "cannot be encoded"


@dataclass
class Path:
    """One concolic path: what went in, what came out."""
    index: int
    inputs: dict = field(default_factory=dict)     # name -> Value
    outputs: dict = field(default_factory=dict)    # name -> Value
    error: str | None = None                       # set instead of outputs
    coverage: str | None = None                    # reached positions only

    @property
    def exact(self) -> bool:
        return all(v.exact for v in
                   list(self.inputs.values()) + list(self.outputs.values()))


@dataclass
class Run:
    """Everything one `catala concolic` invocation said."""
    paths: list = field(default_factory=list)
    finished: bool = False        # "Concolic interpreter done" was printed
    incomplete: bool = False      # a path was dropped as unencodable
    stats: str | None = None
    coverage_reachable: str | None = None
    coverage_initial: str | None = None
    unparsed: list = field(default_factory=list)   # (line, reason)


def result_lines(stdout: str):
    """The `[RESULT]` payloads, in order, with the marker stripped."""
    for line in stdout.splitlines():
        m = _RESULT.match(line)
        if m:
            yield m["body"].strip()


def parse_run(stdout: str, stderr: str = "") -> Run:
    """Fold a whole run's stdout into paths.

    Anything that does not parse is collected into `run.unparsed` rather than
    raised: one struct this module cannot read should cost that one field, not
    the several thousand paths around it.
    """
    run = Run(incomplete=_INCOMPLETE in stderr)
    cur: Path | None = None
    mode: str | None = None

    for line in result_lines(stdout):
        if not line:
            continue
        m = _COVERAGE_REACHABLE.match(line)
        if m:
            run.coverage_reachable = m["dump"]
            continue
        m = _COVERAGE_INITIAL.match(line)
        if m:
            run.coverage_initial = m["dump"]
            continue
        m = _COVERAGE_PATH.match(line)
        if m:
            i = int(m["index"])
            if i < len(run.paths):
                run.paths[i].coverage = m["dump"]
            else:
                run.unparsed.append((line, "coverage precedes its path"))
            continue
        if line == "Evaluating with inputs:":
            cur = Path(index=len(run.paths))
            run.paths.append(cur)
            mode = "inputs"
            continue
        if line == "Output of scope after evaluation:":
            mode = "outputs"
            continue
        if line == "Concolic interpreter done":
            run.finished = True
            cur, mode = None, None
            continue
        if line.startswith("=== Concolic execution statistics ==="):
            run.stats = line
            continue

        m = _ERROR.match(line)
        if m and cur is not None:
            cur.error = f"{m['what']} at {m['pos']}"
            continue

        m = _FIELD.match(line)
        if m and cur is not None and mode is not None:
            try:
                v = values.parse(m["value"])
            except ParseError as e:
                run.unparsed.append((line, str(e)))
                continue
            getattr(cur, mode)[m["name"]] = v
            continue

        # "Incomplete execution finished ...", "time of test: ...", the per-scope
        # "Computation successful!", and anything else CUTECat says: not paths.
        if line.startswith("Incomplete execution"):
            run.incomplete = True

    return run
