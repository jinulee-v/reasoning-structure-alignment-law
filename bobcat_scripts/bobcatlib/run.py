"""Driving BOBCat: one clerk project per target, then `catala bobcat`.

Two things about the invocation are not obvious and both are load-bearing.

`-W` (whole program).  Without it a `> Using Airline as A` is a *linked*
module: the compiler resolves it to a compiled OCaml object and the interpreter
calls into it as one opaque external operation. `-W` inlines module sources so
BOBCat can construct reachability formulas for their branch objectives.

The private project directory. BOBCat is forked from `cutecat-rebase`, not
from the 1.2.1 release, so it must not be pointed at
`data/catala_gold/airline/_build` --- that standard library was laid down by the other
compiler.  Each target instead gets its own directory under
the port's own `build/` under `.port/`, holding the harness, copies of the modules it
uses, and a `libcatala` that *this* compiler produced.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import paths


DEFAULT_TARGET_TIMEOUT = 1800  # 30 minutes; individual Z3 queries remain capped
BOBCAT_STACK_BYTES = 256 * 1024 * 1024
DEFAULT_REPRESENTATION_CAPACITY = 64


@dataclass
class Target:
    """One scope whose branch objectives BOBCat should solve."""
    name: str
    port: str                         # "sara" or "airline": whose tree it
                                      # reads its modules from and writes into
    harness: Path                     # the file holding the scope
    scope: str                        # the scope to explore
    output: str | None = None         # optional top-level dynamic-slice root
    modules: list = field(default_factory=list)   # port sources it `Using`s
    include_dirs: list = field(default_factory=list)  # external module trees
    max_list_length: int | None = None  # None keeps BOBCat's default (5)
    representation_capacity: int = DEFAULT_REPRESENTATION_CAPACITY
    strategy: str = "demand"
    objective_order: str = "depth"
    positive_hundred_money_inputs: bool = False
    solver_timeout_ms: int | None = None  # initial per-query Z3 budget
    solver_timeout_max_ms: int | None = None  # progressive retry ceiling
    objective_timeout_ms: int | None = None  # total solve/replay/refinement budget
    timings: bool = False
    timeout: int = DEFAULT_TARGET_TIMEOUT  # a partial run still yields data
    note: str = ""
    # Targets naming different scopes of the same file share one clerk project,
    # since assembling one costs more than the concolic run that follows.
    # Defaults to the target's own name, i.e. a private directory.
    project: str = ""

    @property
    def project_dir(self) -> str:
        return self.project or self.name


@dataclass
class RunResult:
    stdout: str
    stderr: str
    returncode: int
    seconds: float
    timed_out: bool
    command: list


def prepare_project(target: Target, force: bool = False) -> Path:
    """Assemble and prime `.port/<port>_bobcat/build/<project>/`.

    The modules are *copied*, not symlinked: a symlinked source would make the
    directory's contents depend on the port at run time, and the point of
    keeping the build directory is to be able to say afterwards which text was
    explored.
    """
    d = paths.build(target.port) / target.project_dir
    if force and d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)

    copied_includes = []
    for i, source in enumerate(target.include_dirs):
        if not source.exists():
            raise RuntimeError(f"missing include directory {paths.rel(source)}")
        # Clerk ignores underscore-prefixed source directories as build
        # artifacts, so dependency modules must live under a regular name.
        dest = d / "includes" / f"{i}_{source.name}"
        shutil.copytree(source, dest, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("_build", "_targets"))
        copied_includes.append(dest.relative_to(d))

    include_config = ", ".join(
        f'"{path}"' for path in [Path("."), *copied_includes])
    (d / "clerk.toml").write_text(
        '# Written by bobcat_scripts; regenerable, do not edit.\n'
        '[project]\n'
        'build_dir = "_build"\n'
        f'include_dirs = [{include_config}]\n')
    for m in target.modules:
        shutil.copyfile(m, d / m.name)
    shutil.copyfile(target.harness, d / target.harness.name)

    if not (d / "_build/libcatala").exists():
        r = subprocess.run([str(paths.CLERK), "start"], cwd=d,
                           env=paths.bobcat_env(),
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(
                f"`clerk start` failed in {paths.rel(d)}:\n{r.stdout}{r.stderr}")

    # `catala bobcat` interprets the candidate source, but the front end still
    # dynamically loads OCaml plugins for imported modules while resolving the
    # whole-program source graph. Build those and the standard-library plugins
    # directly. Asking Clerk for the candidate's OCaml module as a proxy would
    # make BOBCat depend on an unrelated backend accepting the entry scope
    # before it can interpret otherwise valid Catala.
    stdlib_targets = sorted(
        f"_build/libcatala/ocaml/{source.stem.removesuffix('.catala').capitalize()}.cmxs"
        for source in (d / "_build/libcatala").glob("stdlib_*.catala_*")
    )
    # Include directories can themselves contain imported proper modules
    # (notably prologue_france/France.catala_fr). Whole-program expansion reads
    # their sources, but the front end still dynamically loads their plugins.
    # Ask Clerk for those modules exactly as for same-port imports.
    module_sources = [*target.modules]
    for include_dir in target.include_dirs:
        module_sources.extend(include_dir.rglob("*.catala_*"))
    module_targets = sorted({
        f"{name}@ocaml-module"
        for source in module_sources
        if (name := _declared_module_name(source)) is not None
    })
    r = subprocess.run(
        [str(paths.CLERK), "raw-target", *stdlib_targets, *module_targets],
                       cwd=d, env=paths.bobcat_env(),
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"building imported-module plugins failed in {paths.rel(d)}:\n"
            f"{r.stdout}{r.stderr}")
    return d


def bobcat_cmd(target: Target, project: Path) -> list:
    """Build the direct solver command; this must never invoke `concolic`."""
    # Catala source graphs are acyclic, but deeply nested generated DCalc still
    # uses the native OCaml call stack. Raise Linux's low 8 MiB default for the
    # child only; this is headroom, not a replacement for DAG sharing.
    cmd = ["/usr/bin/prlimit", f"--stack={BOBCAT_STACK_BYTES}:unlimited", "--",
           str(paths.CATALA), "bobcat", target.harness.name,
           "-s", target.scope,
           "-I", ".",
           "--stdlib", "_build/libcatala",
           "-W",
           "--message-format=gnu",
           "--color=never"]
    for i, source in enumerate(target.include_dirs):
        cmd += ["-I", f"includes/{i}_{source.name}"]
    cmd.append(f"--bobcat-strategy={target.strategy}")
    cmd.append(f"--bobcat-objective-order={target.objective_order}")
    if target.positive_hundred_money_inputs:
        cmd.append("--bobcat-positive-hundred-money-inputs")
    cmd.append(
        f"--bobcat-max-representation-capacity={target.representation_capacity}")
    if target.output is not None:
        cmd.append(f"--bobcat-output={target.output}")
    if target.max_list_length is not None:
        cmd.append(f"--bobcat-max-list-length={target.max_list_length}")
    if target.solver_timeout_ms is not None:
        cmd.append(f"--bobcat-solver-timeout-ms={target.solver_timeout_ms}")
    if target.solver_timeout_max_ms is not None:
        cmd.append(
            f"--bobcat-solver-timeout-max-ms={target.solver_timeout_max_ms}")
    if target.objective_timeout_ms is not None:
        cmd.append(f"--bobcat-objective-timeout-ms={target.objective_timeout_ms}")
    if target.timings:
        cmd.append("--bobcat-timings")
    return cmd


def _declares_module(source: Path) -> bool:
    return _declared_module_name(source) is not None


def _declared_module_name(source: Path) -> str | None:
    for line in source.read_text().splitlines():
        if line.startswith("> Module "):
            return line.removeprefix("> Module ").strip()
    return None


def run_bobcat(target: Target, project: Path) -> RunResult:
    """Run the direct engine, keeping completed goal results on timeout.

    SAT/UNSAT/UNKNOWN is final per objective. A process timeout may retain
    earlier completed objectives, never a partially processed one.
    """
    cmd = bobcat_cmd(target, project)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=project, env=paths.bobcat_env(),
                           capture_output=True, text=True,
                           timeout=target.timeout)
        out, err, rc, timed_out = r.stdout, r.stderr, r.returncode, False
    except subprocess.TimeoutExpired as e:
        out = _text(e.stdout)
        err = _text(e.stderr)
        rc, timed_out = None, True
    return RunResult(out, err, rc, time.time() - t0, timed_out, cmd)


def _text(b) -> str:
    if b is None:
        return ""
    return b if isinstance(b, str) else b.decode("utf-8", "replace")
