"""Every path the BOBCat pipeline uses, and the environment of its compiler.

Same three-way split as `saralib.paths` and `airlinelib.paths`:

  * **sources** --- the two Catala ports under `data/catala_gold/`, and the
    harnesses beside each of them in `harnesses/`, of which only the generated
    wrappers are written from here;
  * **build/**, wholly regenerable --- one clerk project per harness, holding
    the standard library as *this* compiler compiles it;
  * **dataset/** and **reports/**, the two outputs.

Every output is *per port*: `.port/sara_bobcat/` and `.port/airline_bobcat/`
hold a complete tree each, so a run over one port neither reads nor rewrites
anything belonging to the other, and each port's `INDEX.json`, `DATASET.md`
and `COVERAGE.md` describe that port alone.  The two OCaml tools are the one
thing both share --- they are built against the compiler, not against a port
--- so they live beside the trees in `.port/bobcat_tools/`.

The compiler is not the Catala release used to validate the ports. BOBCat is a
separate source build, and the binaries must not be confused:

    .toolchain/opam/catala/bin/catala
                              Catala 1.2.1 validation compiler
    .toolchain/src/catala-bobcat/_build/default/compiler/catala.exe
                              BOBCat --- `catala bobcat`

Only the first gives the independent validation verdict. BOBCat produces test
objectives and, after concrete replay, a dataset.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = Path(__file__).resolve().parent.parent

# ---- sources -------------------------------------------------------------
AIRLINE_CATALA = ROOT / "data/catala_gold/airline"
SARA_CATALA = ROOT / "data/catala_gold/sara"
AIDES_LOGEMENT_CATALA = ROOT / "data/catala_gold/aides_logement"
ALLOCATIONS_FAMILIALES_CATALA = ROOT / "data/catala_gold/allocations_familiales"
NSW_COMMUNITY_GAMING_CATALA = ROOT / "data/catala_gold/NSW_community_gaming"

# ---- outputs -------------------------------------------------------------
PORTS = ("sara", "airline", "aides_logement", "allocations_familiales",
         "nsw_community_gaming")
PORT_DIRS = {
    "sara": SARA_CATALA,
    "airline": AIRLINE_CATALA,
    "aides_logement": AIDES_LOGEMENT_CATALA,
    "allocations_familiales": ALLOCATIONS_FAMILIALES_CATALA,
    "nsw_community_gaming": NSW_COMMUNITY_GAMING_CATALA,
}
PORT_ROOT_FILES = {
    "aides_logement": "Aides_logement.catala_fr",
    "allocations_familiales": "Allocations_familiales.catala_fr",
}

# Legacy compatibility modules retained for reading older campaign artifacts.
PORT_WRAPPER_FILES = {
    "sara": "sara_wrapper.catala_en",
    "airline": "airline_wrapper.catala_en",
    "aides_logement": "aides_logement_wrapper.catala_fr",
    "allocations_familiales": "allocations_familiales_wrapper.catala_fr",
    "nsw_community_gaming": "nsw_community_gaming_wrapper.catala_en",
}


def wrapper_file(port: str) -> Path:
    return PORT_DIRS[port] / PORT_WRAPPER_FILES[port]


def requirement_outputs_file(port: str) -> Path:
    """The current benchmark target contract for ``port``."""
    return PORT_DIRS[port] / "REQUIREMENT_OUTPUTS.json"


def source_files(directory: Path) -> list[Path]:
    """Top-level Catala modules, independent of source language."""
    return sorted(directory.glob("*.catala_*"))

PORT_ROOT = ROOT / ".port"
TOOLS = PORT_ROOT / "bobcat_tools"       # the two OCaml tools, port-agnostic
CATALA_EXAMPLES_SOURCE = PORT_ROOT / "catala_examples_source"


def extra_include_dirs(port: str) -> list[Path]:
    """External module source trees required by the upstream French laws."""
    if port not in ("aides_logement", "allocations_familiales"):
        return []
    dirs = [
        CATALA_EXAMPLES_SOURCE / "base_mensuelle_allocations_familiales",
        CATALA_EXAMPLES_SOURCE / "smic",
        CATALA_EXAMPLES_SOURCE / "prologue_france",
        CATALA_EXAMPLES_SOURCE / "prestations_familiales",
    ]
    if port == "aides_logement":
        dirs.append(ALLOCATIONS_FAMILIALES_CATALA)
    return dirs


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
    """BOBCat-owned wrappers, isolated from CUTECat's source-side wrappers."""
    return out(port) / "generated"


def out(port: str) -> Path:
    """One port's output tree, optionally rooted in an experiment iteration."""
    if port not in PORTS and not (os.environ.get("BOBCAT_CAMPAIGN_ROOT")
                                  and re.fullmatch(r"[A-Za-z0-9_-]+", port)):
        raise ValueError(f"no such port: {port}")
    campaign_root = Path(os.environ.get("BOBCAT_CAMPAIGN_ROOT", str(PORT_ROOT)))
    if not campaign_root.is_absolute():
        campaign_root = ROOT / campaign_root
    return campaign_root / f"{port}_bobcat"


def build(port: str) -> Path:
    return out(port) / "build"           # one clerk project per harness


def raw(port: str) -> Path:
    return out(port) / "raw"             # BOBCat's stdout, kept verbatim


def goals(port: str) -> Path:
    return out(port) / "goals"           # SAT/UNSAT/UNKNOWN, per objective


def coverage(port: str) -> Path:
    return out(port) / "coverage"        # native coverage, per target/path


def dataset(port: str) -> Path:
    return out(port) / "dataset"         # <target>.jsonl + INDEX.json


def dataset_minimal(port: str) -> Path:
    return out(port) / "dataset_minimal" # greedy maximal branch-cover suite


def reports(port: str) -> Path:
    return out(port) / "reports"

# ---- toolchain -----------------------------------------------------------
_OPAM = ROOT / ".toolchain/opam"
# BOBCat is developed as a separate compiler checkout.  It deliberately uses
# CUTECat's already-installed OCaml dependency switch, but never its compiler
# binary.  This keeps iteration cheap while ensuring `catala bobcat` is always
# the executable built from `.toolchain/src/catala-bobcat`.
DEPENDENCY_SWITCH = _OPAM / "cutecat"
SOURCE = ROOT / ".toolchain/src/catala-bobcat"
CATALA = SOURCE / "_build/default/compiler/catala.exe"
CLERK = DEPENDENCY_SWITCH / "bin/clerk"
BOBCAT_REPOSITORY = "https://github.com/jinulee-v/bobcat.git"

INSTALLER = ROOT / "install_toolchain.sh"


def bobcat_env() -> dict:
    """Environment for the BOBCat source build and its dependency switch.

    The three OCaml variables are there for the same reason `catala_env`'s
    are --- an opam switch has its prefix compiled into its binaries, so a
    tree that has been moved needs them to find its own libraries.  See the
    docstring in `saralib/paths.py`.
    """
    env = os.environ.copy()
    env["OPAMROOT"] = str(_OPAM)
    env["PATH"] = ":".join([str(CATALA.parent),
                            str(DEPENDENCY_SWITCH / "bin"),
                            str(ROOT / ".toolchain/envs/catala/bin"),
                            env.get("PATH", "")])
    bobcat_z3 = ROOT / ".toolchain/bobcat-z3/lib"
    env["LD_LIBRARY_PATH"] = ":".join(part for part in
        [env.get("LD_LIBRARY_PATH", ""),
         str(bobcat_z3) if (bobcat_z3 / "libz3.so").exists() else "",
         str(ROOT / ".toolchain/envs/catala/lib")] if part)
    env["OCAMLLIB"] = str(DEPENDENCY_SWITCH / "lib/ocaml")
    env["OCAMLPATH"] = str(DEPENDENCY_SWITCH / "lib")
    env["CAML_LD_LIBRARY_PATH"] = ":".join(
        [str(DEPENDENCY_SWITCH / "lib/stublibs"),
         str(DEPENDENCY_SWITCH / "lib/ocaml/stublibs")])
    return env


def require_bobcat() -> None:
    """Fail with the command that installs it, rather than with ENOENT."""
    if not CATALA.exists():
        raise SystemExit(
            f"BOBCat is not built ({rel(CATALA)} does not exist).\n"
            f"  Build it with:\n"
            f"      python3 bobcat_scripts/build.py")


def rel(path) -> str:
    """A path as written in reports: relative to the repository root."""
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)
