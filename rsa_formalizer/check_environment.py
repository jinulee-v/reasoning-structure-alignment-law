"""Check full-run prerequisites without making paid model calls or creating a run."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rsa_formalizer.agents.codex import credential_file
from rsa_formalizer.agents.dotenv import load_dotenv
from rsa_formalizer.stages.utils.catala import toolchain_environment


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    environment = toolchain_environment({})
    failures = []

    def check(label: str, ok: bool) -> None:
        print(f"{'OK' if ok else 'MISSING'}: {label}")
        if not ok:
            failures.append(label)

    for module in ("openai", "yaml", "jsonschema"):
        try:
            __import__(module)
            check(f"Python package {module}", True)
        except ImportError:
            check(f"Python package {module}", False)
    check("Codex credentials (codex login)", credential_file().is_file())
    for name in ("codex", "apptainer", "catala", "clerk"):
        binary = shutil.which(name, path=environment["PATH"])
        ok = False
        if binary:
            result = subprocess.run(
                [binary, "--version"], env=environment, capture_output=True, text=True
            )
            ok = result.returncode == 0
            if not ok:
                print(result.stderr.strip())
        check(f"{name} executable", ok)
    for relative in (
        ".toolchain/rsa.sif",
        ".toolchain/src/catala-bobcat/_build/default/compiler/catala.exe",
        ".toolchain/bobcat-z3/lib/libz3.so",
        "data/raw/sara/RSA_MANIFEST.json",
        "data/raw/sara/tests_catala/SaraTaxCases.catala_en",
    ):
        check(relative, (root / relative).is_file())
    runtime_interface = (
        root / ".toolchain/src/catala-bobcat/runtimes/ocaml/catala_runtime.mli"
    )
    check(
        "BOBCat dependency-tracing runtime",
        runtime_interface.is_file()
        and "log_variable_definition_with_reads" in runtime_interface.read_text(),
    )
    clerk = shutil.which("clerk", path=environment["PATH"])
    if clerk:
        result = subprocess.run(
            [clerk, "json-schema", "--help=plain"],
            env=environment, capture_output=True, text=True,
        )
        check("Clerk json-schema support", result.returncode == 0)
    if not failures:
        result = subprocess.run(
            ["apptainer", "exec", str(root / ".toolchain/rsa.sif"), "true"],
            capture_output=True, text=True, env=environment,
        )
        check("Apptainer container execution", result.returncode == 0)
        if result.returncode:
            print(result.stderr.strip())
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
