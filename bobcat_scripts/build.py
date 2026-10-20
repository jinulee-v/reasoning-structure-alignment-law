#!/usr/bin/env python3
"""Initialize and build the independent BOBCat compiler submodule.

BOBCat shares the already provisioned OCaml/Z3 dependencies of the CUTECat
opam switch, but its executable is built from `.toolchain/src/catala-bobcat`.
The script intentionally never builds or invokes `.toolchain/src/catala-cutecat`.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from build_z3 import ensure_z3


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / ".toolchain/src/catala-bobcat"
OPAM = ROOT / ".toolchain/envs/catala/bin/opam"
OPAMROOT = ROOT / ".toolchain/opam"
BINARY = SOURCE / "_build/default/compiler/catala.exe"
REPOSITORY = "https://github.com/jinulee-v/bobcat.git"


def bootstrap() -> None:
    """Initialize the pinned submodule, with a direct-clone fallback."""
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    relative = SOURCE.relative_to(ROOT)
    initialized = subprocess.run(
        ["git", "-C", str(ROOT), "submodule", "update", "--init",
         "--recursive", "--", str(relative)]).returncode == 0
    if not initialized or not (SOURCE / ".git").exists():
        subprocess.run(["git", "clone", REPOSITORY, str(SOURCE)], check=True)


def main() -> int:
    ensure_z3()
    if not (SOURCE / ".git").exists():
        bootstrap()
    if not (SOURCE / "compiler/bobcat").is_dir():
        raise SystemExit(
            f"{SOURCE} is not a BOBCat compiler checkout; initialize the "
            "submodule with `git submodule update --init --recursive`")
    if not OPAM.exists():
        raise SystemExit(
            f"missing opam executable: {OPAM}\n"
            "Run `bash install_toolchain.sh cutecat` once for dependencies.")

    env = os.environ.copy()
    env["OPAMROOT"] = str(OPAMROOT)
    command = [str(OPAM), "exec", "--switch=cutecat", "--",
               "dune", "build", "compiler/catala.exe"]
    subprocess.run(command, cwd=SOURCE, env=env, check=True)
    subprocess.run([str(BINARY), "bobcat", "--help=plain"],
                   env=env, stdout=subprocess.DEVNULL, check=True)
    print(BINARY.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
