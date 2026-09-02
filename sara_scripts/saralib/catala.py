"""Render a world model as Catala, and run it against the port.

The rendering itself lives in `catala_emit` (large, one renderer per statute
predicate).  This module is the thin part around it: the frozen symbol table,
a standalone program on disk, and the interpreter.

Catala 1.2 has no string type, so every atom, date and number is interned into
one integer key space.  That space is frozen in `sara_port/build/symbols.json`
because the port's own modules refer to predicate keys by generated name
(`P.pred_s7703_4`); a table copy is made per rendering so that two threads
allocating a key for a newly invented atom cannot hand it the same id.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
from pathlib import Path

from . import catala_emit as emit
from .paths import (CATALA_BUILD, CATALA_PROJECT, CATALA_STDLIB, SCRATCH,
                    SYMBOLS, catala_cmd, catala_env)

PORTED = emit.PORTED


class NotPorted(Exception):
    """The query predicate has no Catala renderer."""


PREDICATES = CATALA_PROJECT / "SaraPredicates.catala_en"
_PRED_RE = re.compile(r"declaration pred_(\S+) content integer equals (\d+)")


def recover_symbols() -> dict:
    """Rebuild the key space from the port's own generated constants module.

    Only the *predicate* keys have to survive: the port's Layer-1 modules were
    compiled against `SaraPredicates.pred_s7703_4` and friends, so those
    integers are load-bearing.  Everything else in the table --- entities,
    dates, amounts --- is allocated per rendered program and only has to be
    consistent within it, which `Symbols` guarantees on its own.  So the module
    that depends on the key space is also enough to reconstruct the part of it
    that matters, and `sara_port/build/` holds nothing irreplaceable.
    """
    out = {}
    for name, key in _PRED_RE.findall(PREDICATES.read_text()):
        pred, arity = name.rsplit("_", 1)      # `s151_c_4` -> `s151_c/4`
        out[f"p:{pred}/{arity}"] = int(key)
    if not out:
        raise SystemExit(f"no interned predicate keys found in {PREDICATES}")
    return out


def load_symbols() -> emit.Symbols:
    sym = emit.Symbols()
    if not SYMBOLS.exists():
        SYMBOLS.parent.mkdir(parents=True, exist_ok=True)
        SYMBOLS.write_text(json.dumps(recover_symbols(), indent=1))
    sym.table = json.loads(SYMBOLS.read_text())
    return sym


def render(sym: emit.Symbols, rec: dict, provenance: str = "") -> str:
    """One world model as a standalone Catala program."""
    local = emit.Symbols()
    local.table = dict(sym.table)
    text = emit.emit_case(local, rec, standalone=True, provenance=provenance)
    if "UNPORTED" in text:
        raise NotPorted(rec["test"]["goals"][0]["predicate"])
    return text


VERDICT_RE = re.compile(r"^\s*│?\s*verdict = (true|false)\s*$", re.M)


def run_program(path: Path, trace: Path | None = None,
                timeout: int = 120) -> tuple[str, str]:
    """(verdict, detail) for one `catala.catala_en` on disk.

    verdict is `true`, `false`, `error` (the interpreter refused the program or
    raised) or `timeout`.
    """
    extra = ["--trace=" + str(trace), "--trace-format=json"] if trace else []
    # Its own session, so a timeout kills the whole process group.  The same
    # trap as in `prolog.run_program`: `subprocess.run(timeout=)` kills only
    # the immediate child and then blocks in `communicate()`, which stalled a
    # `--compare-trails` run indefinitely with thirteen whole-program
    # interpreters alive and none of them being reaped.
    proc = subprocess.Popen(
        catala_cmd(Path(path), "Run", extra, whole_program=bool(trace)),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=catala_env(), start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return "timeout", f"catala exceeded {timeout}s"
    m = VERDICT_RE.search(out)
    if not m:
        return "error", (err or out)[-4000:]
    return m.group(1), ""


def run_world(sym: emit.Symbols, rec: dict, tag: str,
              timeout: int = 120) -> tuple[str, str]:
    """Render a world model to a scratch file and run it."""
    try:
        text = render(sym, rec)
    except NotPorted as exc:
        return "unported", str(exc)
    work = SCRATCH / f"c{os.getpid()}"
    work.mkdir(parents=True, exist_ok=True)
    path = work / f"{tag}.catala_en"
    path.write_text(text)
    try:
        return run_program(path, timeout=timeout)
    finally:
        path.unlink(missing_ok=True)


def ensure_built() -> None:
    """The port has to be compiled before any case can reference its modules."""
    if not CATALA_STDLIB.exists() or not (CATALA_BUILD / "ocaml").exists():
        raise SystemExit(
            "the Catala port is not built: run `clerk build` in sara_catala/ "
            f"(expected {CATALA_STDLIB} and {CATALA_BUILD}/ocaml)")
