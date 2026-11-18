"""Concrete exact-branch replay using the BOBCat compiler, without Z3 search."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from . import paths

PLUGIN_DIR = paths.TOOLS / "replay_tool/default"


def inventory(target, project: Path, *, timeout: int = 300) -> list[str]:
    """Statically catalog scope outcomes; never execute the BOBCat solver."""
    environment = paths.bobcat_env()
    environment["CATALA_PLUGINS"] = str(PLUGIN_DIR.resolve())
    command = ["/usr/bin/prlimit", "--stack=268435456:unlimited", "--",
               str(paths.CATALA), "bobcat-replay", target.harness.name,
               "-s", target.scope, "-I", ".", "--stdlib", "_build/libcatala",
               "-W", "--color=never", "--message-format=gnu"]
    if target.output:
        command += ["--coverage-output", target.output]
    for directory in sorted((project / "includes").glob("*")):
        if directory.is_dir():
            command += ["-I", str(directory.relative_to(project))]
    completed = subprocess.run(command, cwd=project, env=environment,
                               capture_output=True, text=True, timeout=timeout)
    if completed.returncode:
        raise RuntimeError((completed.stdout + completed.stderr)[-4000:])
    manifest = json.loads(completed.stdout)
    if not isinstance(manifest, list) or not all(isinstance(pair, str) for pair in manifest):
        raise ValueError("invalid static coverage manifest")
    return manifest


def build_plugin() -> Path:
    PLUGIN_DIR.parent.mkdir(parents=True, exist_ok=True)
    environment = paths.bobcat_env()
    environment["OCAMLPATH"] = str(paths.SOURCE / "_build/install/default/lib") + ":" + environment["OCAMLPATH"]
    completed = subprocess.run(
        ["dune", "build", "--root", str(paths.SCRIPTS / "replay_tool"),
         "--build-dir", str(paths.TOOLS / "replay_tool"),
         "catala_bobcat_replay.cmxs"],
        cwd=paths.ROOT, env=environment, capture_output=True, text=True,
        timeout=300,
    )
    if completed.returncode:
        raise RuntimeError("BOBCat replay plugin build failed:\n" + completed.stdout + completed.stderr)
    return PLUGIN_DIR


def replay_inputs(target, project: Path, inputs: dict, manifest: list[str],
                  *, timeout: int = 300) -> dict:
    """Return only successfully executed native outcomes and printed outputs."""
    environment = paths.bobcat_env()
    environment["CATALA_PLUGINS"] = str(PLUGIN_DIR.resolve())
    with tempfile.TemporaryDirectory(prefix="bobcat-replay-") as directory:
        input_file = Path(directory) / "input.json"
        manifest_file = Path(directory) / "manifest.json"
        input_file.write_text(json.dumps(inputs, ensure_ascii=False), encoding="utf-8")
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        command = ["/usr/bin/prlimit", "--stack=268435456:unlimited", "--",
                   str(paths.CATALA), "bobcat-replay", target.harness.name,
                   "-s", target.scope, "-I", ".", "--stdlib", "_build/libcatala",
                   "-W", "--color=never", "--message-format=gnu",
                   "--replay-input", str(input_file),
                   "--replay-manifest", str(manifest_file)]
        for directory in sorted((project / "includes").glob("*")):
            if directory.is_dir():
                command += ["-I", str(directory.relative_to(project))]
        completed = subprocess.run(command, cwd=project, env=environment,
                                   capture_output=True, text=True, timeout=timeout)
    if completed.returncode:
        raise RuntimeError((completed.stdout + completed.stderr)[-4000:])
    result = json.loads(completed.stdout)
    if not isinstance(result.get("branches"), list) or not set(result["branches"]) <= set(manifest):
        raise ValueError("invalid BOBCat concrete branch trace")
    return result
