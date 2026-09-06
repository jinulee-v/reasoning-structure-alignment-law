"""Driving CUTECat: one clerk project per target, then `catala concolic`.

Two things about the invocation are not obvious and both are load-bearing.

`-W` (whole program).  Without it a `> Using Airline as A` is a *linked*
module: the compiler resolves it to a compiled OCaml object and the interpreter
calls into it, which for a concolic run means the statute executes as one
opaque step and contributes no path constraints at all.  The run would finish
in a second having found one path.  `-W` inlines the module sources instead,
which is what makes the port's own branches visible to Z3.  It is the same flag
`saralib.paths.catala_cmd` passes to get a trace with any depth in it.

The private project directory.  CUTECat is built from the `cutecat-rebase`
branch, not from the 1.2.1 release, so it must not be pointed at
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


@dataclass
class Target:
    """One thing to run CUTECat on."""
    name: str
    port: str                         # "sara" or "airline": whose tree it
                                      # reads its modules from and writes into
    harness: Path                     # the file holding the scope
    scope: str                        # the scope to explore
    modules: list = field(default_factory=list)   # port sources it `Using`s
    # `incremental` is the incremental Z3 solver, which CUTECat's own test suite
    # runs with.  Not merely a speedup: without it `sara_section68` aborts at
    # `[ERROR] [compare_paths] the negated condition lead to the same path` after
    # 6 of its 12 paths.  Optimizations that change what is explored
    # (`lazy-default`, the mutation family) are left to `--optim`.
    optims: list = field(default_factory=lambda: ["incremental"])
    seed: int | None = None
    timeout: int = 300                # seconds; a partial run still yields data
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
    """Assemble and prime `.port/<port>_cutecat/build/<project>/`.

    The modules are *copied*, not symlinked: a symlinked source would make the
    directory's contents depend on the port at run time, and the point of
    keeping the build directory is to be able to say afterwards which text was
    explored.
    """
    d = paths.build(target.port) / target.project_dir
    if force and d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)

    (d / "clerk.toml").write_text(
        '# Written by cutecat_scripts; regenerable, do not edit.\n'
        '[project]\n'
        'build_dir = "_build"\n'
        'include_dirs = ["."]\n')
    for m in target.modules:
        shutil.copyfile(m, d / m.name)
    shutil.copyfile(target.harness, d / target.harness.name)

    if not (d / "_build/libcatala").exists():
        r = subprocess.run([str(paths.CLERK), "start"], cwd=d,
                           env=paths.cutecat_env(),
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(
                f"`clerk start` failed in {paths.rel(d)}:\n{r.stdout}{r.stderr}")

    # `clerk start` lays down the standard-library sources, but a direct
    # `catala concolic` call needs their OCaml objects too.  Building the target
    # module compiles them all as dependencies; Ninja makes reruns a no-op.
    module = target.harness.name.split(".catala_", 1)[0]
    r = subprocess.run([str(paths.CLERK), "raw-target",
                        f"{module}@ocaml-module"],
                       cwd=d, env=paths.cutecat_env(),
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"building {module} failed in {paths.rel(d)}:\n"
            f"{r.stdout}{r.stderr}")
    return d


def concolic_cmd(target: Target, project: Path) -> list:
    cmd = [str(paths.CATALA), "concolic", target.harness.name,
           "-s", target.scope,
           "-I", ".",
           "--stdlib", "_build/libcatala",
           "-W",
           "--conc-code-coverage",
           "--message-format=gnu",
           "--color=never"]
    for o in target.optims:
        cmd.append(f"--conc-optim={o}")
    if target.seed is not None:
        cmd += ["--seed", str(target.seed)]
    return cmd


def run_concolic(target: Target, project: Path) -> RunResult:
    """Run the engine, keeping the output of a run that had to be cut short.

    A concolic run does not converge on anything in particular --- it enumerates
    until it runs out of unexplored branches, which for a scope with a wide
    enumeration in it is a very long time.  So the timeout is a normal outcome
    and not an error: `TimeoutExpired` carries the output produced so far, every
    path in it is complete and already printed, and those paths are kept.
    """
    cmd = concolic_cmd(target, project)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=project, env=paths.cutecat_env(),
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
