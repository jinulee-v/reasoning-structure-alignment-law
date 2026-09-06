"""Every path the SARA apparatus uses, and the two toolchain environments.

Three kinds of location, kept apart on purpose:

  * **sources**, never written by any script here --- upstream SARA under
    `data/prolog/sara/` and the Catala port under `data/catala_gold/sara/`;
  * **build/**, wholly regenerable by `generate_test_cases.py --build`, the
    oracle's own statutes included;
  * **test_cases/** and **reports/**, the two outputs.

So everything under `.port/sara/` except its two documents is disposable: delete
any of it and `--build` puts it back.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# ---- sources -------------------------------------------------------------
RAW = ROOT / "data/prolog/sara"
RAW_CASES = RAW / "cases"
RAW_STATUTES = RAW / "statutes"
RAW_TEXT = ROOT / "data/raw/sara"        # the statute prose, section by section

PORT = ROOT / ".port/sara"

CATALA_PROJECT = ROOT / "data/catala_gold/sara"
CATALA_BUILD = CATALA_PROJECT / "_build"
CATALA_STDLIB = CATALA_BUILD / "libcatala"

PL_SUPPORT = Path(__file__).resolve().parent / "pl"

# ---- build/ (regenerable) ------------------------------------------------
BUILD = PORT / "build"
STATUTES = BUILD / "statutes"            # upstream + the SWI>=8 fix; the oracle
COVERED = BUILD / "prolog_covered"       # statutes + per-goal branch points
POINTS = COVERED / "POINTS.txt"
HARNESS = BUILD / "harness.pl"           # main/0 for a generated prolog.pl
GROUNDED = BUILD / "cases_grounded"      # SARA's 376 cases as world models
SIGNATURE = BUILD / "signature.json"     # call graph + literal dictionary
VALUE_TYPES = BUILD / "value_types.json"
SYMBOLS = BUILD / "symbols.json"         # the port's interned key space
DISCONTIGUOUS = BUILD / "discontiguous.json"
SCRATCH = BUILD / "scratch"              # per-run temporaries, safe to delete

# ---- outputs -------------------------------------------------------------
TEST_CASES = PORT / "test_cases"
REPORTS = PORT / "reports"

# ---- toolchains ----------------------------------------------------------
SWIPL = ROOT / ".toolchain/envs/sara/bin/swipl"
_OPAM = ROOT / ".toolchain/opam"


def catala_env() -> dict:
    """Environment for the vendored Catala 1.2 compiler.

    `OPAMROOT` and `PATH` find the switch; the three OCaml variables make it
    *relocatable*.  opam switches are not: `catala` and `clerk` are native
    binaries with the switch prefix compiled in, so a switch built under one
    directory and then moved keeps asking for its libraries at the old path
    ("Required OCaml library not found at .../lib/ocaml/zarith").  `OCAMLLIB`
    overrides the compiled-in stdlib, `OCAMLPATH` the findlib search path and
    `CAML_LD_LIBRARY_PATH` the C stubs, all three derived from `ROOT` --- so
    the tree can be moved anywhere without rebuilding the switch.
    """
    env = os.environ.copy()
    _switch = _OPAM / "catala"
    env["OPAMROOT"] = str(_OPAM)
    env["PATH"] = ":".join([str(_switch / "bin"),
                            str(ROOT / ".toolchain/envs/catala/bin"),
                            env.get("PATH", "")])
    env["LD_LIBRARY_PATH"] = ":".join(
        [str(ROOT / ".toolchain/envs/catala/lib"),
         env.get("LD_LIBRARY_PATH", "")])
    env["OCAMLLIB"] = str(_switch / "lib/ocaml")
    env["OCAMLPATH"] = str(_switch / "lib")
    env["CAML_LD_LIBRARY_PATH"] = ":".join(
        [str(_switch / "lib/stublibs"), str(_switch / "lib/ocaml/stublibs")])
    return env


def catala_cmd(source: Path, scope: str = "Run", extra: list | None = None,
               whole_program: bool = False) -> list:
    """`catala interpret` on a standalone case file, from any directory.

    A generated `catala.catala_en` declares no module of its own, so the file
    name is free and it can live next to its Prolog twin rather than inside
    the port's source tree.  The port's modules and the standard library are
    reached through the flags rather than through the working directory.

    `whole_program` re-reads the port's sources instead of linking its
    compiled modules.  It is how a trace gets any depth --- a linked module
    executes as one opaque step, so the trace of a §7703 query shows a single
    `MaritalStatusA` call and no article of the statute at all --- and it costs
    a few times the run time, so it is used for tracing and not for verdicts.
    """
    return ["catala", "interpret", str(source), "-s", scope,
            "-I", str(CATALA_PROJECT),
            "--stdlib", str(CATALA_STDLIB),
            "--bin", str(CATALA_BUILD),
            "--color=never"] + (["-W"] if whole_program else []) + (extra or [])


def rel(path: Path) -> str:
    """A path as written in reports: relative to the repository root."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)
