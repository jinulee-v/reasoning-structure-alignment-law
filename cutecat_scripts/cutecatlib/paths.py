"""Every path the CUTECat pipeline uses, and the environment of its compiler.

Same three-way split as `saralib.paths` and `airlinelib.paths`:

  * **sources** --- the two Catala ports under `data/catala_gold/`, and the
    harnesses beside each of them in `harnesses/`, of which only the generated
    wrappers are written from here;
  * **build/**, wholly regenerable --- one clerk project per harness, holding
    the standard library as *this* compiler compiles it;
  * **dataset/** and **reports/**, the two outputs.

Every output is *per port*: `.port/sara_cutecat/` and `.port/airline_cutecat/`
hold a complete tree each, so a run over one port neither reads nor rewrites
anything belonging to the other, and each port's `INDEX.json`, `DATASET.md`
and `COVERAGE.md` describe that port alone.  The two OCaml tools are the one
thing both share --- they are built against the compiler, not against a port
--- so they live beside the trees in `.port/cutecat_tools/`.

The compiler is not the one the ports are validated against.  CUTECat is a
second Catala, on its own opam switch, and the two must not be confused:
`install_toolchain.sh` builds

    .toolchain/opam/catala    Catala 1.2.1, the release --- `catala interpret`
    .toolchain/opam/cutecat   the `cutecat-rebase` branch --- `catala concolic`

and only the first has a verdict to give about the ports.  What the second one
produces is a dataset, not a judgement.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = Path(__file__).resolve().parent.parent

# ---- sources -------------------------------------------------------------
AIRLINE_CATALA = ROOT / "data/catala_gold/airline"
SARA_CATALA = ROOT / "data/catala_gold/sara"

# ---- outputs -------------------------------------------------------------
PORTS = ("sara", "airline")
PORT_DIRS = {"sara": SARA_CATALA, "airline": AIRLINE_CATALA}

PORT_ROOT = ROOT / ".port"
TOOLS = PORT_ROOT / "cutecat_tools"      # the two OCaml tools, port-agnostic


def harnesses(port: str) -> Path:
    """`data/catala_gold/<port>/harnesses/` --- the entry scopes of that port.

    A harness is Catala written against one port and nothing else, so it lives
    with the port rather than with the pipeline that runs it.  It sits in a
    subdirectory because the port's own modules are the `*.catala_en` at the
    top of that directory: a harness is scaffolding for entering the port, not
    a part of the statute, and everything that counts what the port contains
    globs one level and must keep seeing only the statute.
    """
    return PORT_DIRS[port] / "harnesses"


def generated(port: str) -> Path:
    """The wrapper scopes written by the census, one file per port source."""
    return harnesses(port) / "generated"


def out(port: str) -> Path:
    """`.port/<port>_cutecat/` --- one port's whole output tree."""
    if port not in PORTS:
        raise ValueError(f"no such port: {port}")
    return PORT_ROOT / f"{port}_cutecat"


def build(port: str) -> Path:
    return out(port) / "build"           # one clerk project per harness


def raw(port: str) -> Path:
    return out(port) / "raw"             # CUTECat's stdout, kept verbatim


def coverage(port: str) -> Path:
    return out(port) / "coverage"        # native coverage, per target/path


def dataset(port: str) -> Path:
    return out(port) / "dataset"         # <target>.jsonl + INDEX.json


def reports(port: str) -> Path:
    return out(port) / "reports"

# ---- toolchain -----------------------------------------------------------
_OPAM = ROOT / ".toolchain/opam"
SWITCH = _OPAM / "cutecat"
CATALA = SWITCH / "bin/catala"
CLERK = SWITCH / "bin/clerk"

INSTALLER = ROOT / "install_toolchain.sh"
CUTECAT_PATCHES = tuple(SCRIPTS / "patches" / name for name in (
    "unused-option-sort.patch",
    "coverage-with-input.patch",
    "epos-is-a-value.patch",
    "toint-rat.patch",
    "concolic-lists.patch",
    "concolic-list-stdlib.patch",
    "concolic-nested-lists.patch",
    "concolic-coverage.patch",
    "concolic-options.patch",
    "concolic-representation-fixes.patch",
    "unicode-identifiers.patch",
))


def cutecat_env() -> dict:
    """Environment for the CUTECat compiler.

    The three OCaml variables are there for the same reason `catala_env`'s
    are --- an opam switch has its prefix compiled into its binaries, so a
    tree that has been moved needs them to find its own libraries.  See the
    docstring in `saralib/paths.py`.
    """
    env = os.environ.copy()
    env["OPAMROOT"] = str(_OPAM)
    env["PATH"] = ":".join([str(SWITCH / "bin"),
                            str(ROOT / ".toolchain/envs/catala/bin"),
                            env.get("PATH", "")])
    env["LD_LIBRARY_PATH"] = ":".join(
        [str(ROOT / ".toolchain/envs/catala/lib"),
         env.get("LD_LIBRARY_PATH", "")])
    env["OCAMLLIB"] = str(SWITCH / "lib/ocaml")
    env["OCAMLPATH"] = str(SWITCH / "lib")
    env["CAML_LD_LIBRARY_PATH"] = ":".join(
        [str(SWITCH / "lib/stublibs"), str(SWITCH / "lib/ocaml/stublibs")])
    return env


def require_cutecat() -> None:
    """Fail with the command that installs it, rather than with ENOENT."""
    if not CATALA.exists():
        raise SystemExit(
            f"CUTECat is not installed ({rel(CATALA)} does not exist).\n"
            f"  Build it with:\n"
            f"      bash {rel(INSTALLER)} cutecat")


def rel(path) -> str:
    """A path as written in reports: relative to the repository root."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)
