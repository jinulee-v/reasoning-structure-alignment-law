"""Every path the DeonticBench apparatus uses, and the two toolchains.

Three kinds of location, kept apart on purpose, following `prolog_to_catala/sara`:

  * **sources**, never written by any script here --- the pristine corpus under
    `data/prolog/airline/` and the Catala port under `data/catala_gold/airline/`;
  * **build/**, wholly regenerable;
  * **test_cases/** and **reports/**, the two outputs.

Everything under `.port/airline/` is disposable: delete any of it and the next
`generate_test_cases.py` run puts it back.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# ---- sources -------------------------------------------------------------
RAW = ROOT / "data/prolog"
AIRLINE_RAW = RAW / "airline"
RAW_TEXT = ROOT / "data/raw/airline"     # the published bag-fee rules, verbatim

CATALA_PROJECT = ROOT / "data/catala_gold/airline"
CATALA_BUILD = CATALA_PROJECT / "_build"
CATALA_STDLIB = CATALA_BUILD / "libcatala"

PL_SUPPORT = Path(__file__).resolve().parent / "pl"
AIRLINE_ORACLE = PL_SUPPORT / "airline_oracle.pl"

# ---- outputs -------------------------------------------------------------
PORT = ROOT / ".port/airline"
BUILD = PORT / "build"
SCRATCH = BUILD / "scratch"
TEST_CASES = PORT / "test_cases"
REPORTS = PORT / "reports"

# ---- toolchains ----------------------------------------------------------
SWIPL = ROOT / ".toolchain/envs/sara/bin/swipl"
_OPAM = ROOT / ".toolchain/opam"


def catala_env() -> dict:
    """Environment for the vendored Catala 1.2 compiler.

    Shared with the SARA side; see `sara/saralib/paths.py` for why the three OCaml
    variables are needed (opam switches are not relocatable).
    """
    env = os.environ.copy()
    switch = _OPAM / "catala"
    env["OPAMROOT"] = str(_OPAM)
    env["PATH"] = ":".join([str(switch / "bin"),
                            str(ROOT / ".toolchain/envs/catala/bin"),
                            env.get("PATH", "")])
    env["LD_LIBRARY_PATH"] = ":".join(
        [str(ROOT / ".toolchain/envs/catala/lib"), env.get("LD_LIBRARY_PATH", "")])
    env["OCAMLLIB"] = str(switch / "lib/ocaml")
    env["OCAMLPATH"] = str(switch / "lib")
    env["CAML_LD_LIBRARY_PATH"] = ":".join(
        [str(switch / "lib/stublibs"), str(switch / "lib/ocaml/stublibs")])
    return env


def catala_cmd(source: Path, scope: str = "Run", extra: list | None = None,
               whole_program: bool = False) -> list:
    """`catala interpret` on a standalone case file, from any directory."""
    return ["catala", "interpret", str(source), "-s", scope,
            "-I", str(CATALA_PROJECT),
            "--stdlib", str(CATALA_STDLIB),
            "--bin", str(CATALA_BUILD),
            "--color=never"] + (["-W"] if whole_program else []) + (extra or [])


MODULES = ["AirlineWorld", "Airline"]


def build_catala_modules(verbose: bool = True) -> None:
    """Compile the port's modules so a generated case can link against them.

    `clerk start` only lays down the standard library; the port's own modules
    have to be built before `catala interpret --bin` can find them, and a case
    that links against an unbuilt module fails with "Compiled OCaml object ...
    not found" rather than anything a reader could act on.  Doing it here means
    a fresh clone needs `clerk start` and nothing else.
    """
    import subprocess
    env = catala_env()
    if not CATALA_STDLIB.exists():
        r = subprocess.run(["clerk", "start"], cwd=CATALA_PROJECT, env=env,
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("clerk start failed:\n" + r.stdout + r.stderr)
    for m in MODULES:
        r = subprocess.run(["clerk", "raw-target", f"{m}@ocaml-module"],
                           cwd=CATALA_PROJECT, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"building {m} failed:\n" + r.stdout + r.stderr)
    if verbose:
        print(f"  catala modules built: {', '.join(MODULES)}")


def rel(path) -> str:
    """A path as written in reports: relative to the repository root."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)
