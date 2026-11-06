from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from .base import (
    DOCUMENTATION_MOUNT,
    FEEDBACK_MOUNT,
    INPUT_REQUIREMENTS_HELPER_MOUNT,
    MINI_SWE_AGENT_HELPER_MOUNT,
    PROMPT_MOUNT,
    REGENERATE_ANALYSIS_HELPER_MOUNT,
    SUBMISSION_CHECK_HELPER_MOUNT,
    WORKSPACE_MOUNT,
    AgentConfigurationError,
)


DOCUMENTATION_SOURCE = Path(__file__).resolve().parents[1] / "catala_book"
SUBMISSION_CHECK_HELPER_SOURCE = (
    Path(__file__).resolve().parents[1] / "check_submission.sh"
)
REGENERATE_ANALYSIS_HELPER_SOURCE = (
    Path(__file__).resolve().parents[1] / "regenerate_scope_analysis.py"
)
MINI_SWE_AGENT_HELPER_SOURCE = Path(__file__).with_name("run_mini_swe_agent.py")
SUBMISSION_CHECK_DIRECTORY_MOUNT = "/rtdf/submission-check"
SUBMISSION_CHECK_SOCKET_MOUNT = f"{SUBMISSION_CHECK_DIRECTORY_MOUNT}/validator.sock"


def parse_mount(value: str) -> dict[str, Any]:
    pieces = value.rsplit(":", 2)
    if len(pieces) not in (2, 3):
        raise argparse.ArgumentTypeError("mount must be SOURCE:CONTAINER_PATH[:ro]")
    source, target = pieces[0], pieces[1]
    mode = pieces[2] if len(pieces) == 3 else "ro"
    source_path = Path(source).expanduser().resolve()
    forbidden = (WORKSPACE_MOUNT, "/rtdf", "/agent-home")
    if not source_path.exists():
        raise argparse.ArgumentTypeError(f"mount source does not exist: {source_path}")
    if not target.startswith("/") or target in forbidden or target.startswith("/rtdf/"):
        raise argparse.ArgumentTypeError(
            "mount target conflicts with an RTDF-managed path"
        )
    if mode != "ro":
        raise argparse.ArgumentTypeError("extra mounts must be read-only (:ro)")
    return {"source": str(source_path), "target": target, "read_only": True}


def add_cli_arguments(parser: argparse.ArgumentParser, root: Path) -> None:
    parser.add_argument(
        "--image", required=True, help="Apptainer SIF, sandbox, or OCI URI"
    )
    parser.add_argument("--mount", action="append", default=[], type=parse_mount)
    parser.add_argument("--apptainer-binary", default="apptainer")
    parser.add_argument("--network-policy", choices=("host", "none"), default="host")
    parser.add_argument("--agent-binary", type=Path)
    parser.add_argument("--no-host-agent", action="store_false", dest="use_host_agent")
    parser.set_defaults(use_host_agent=True)
    parser.add_argument("--agent-home-seed", type=Path)
    parser.add_argument("--host-toolchain", type=Path, default=root / ".toolchain")
    parser.add_argument(
        "--no-host-toolchain", action="store_const", const=None, dest="host_toolchain"
    )
    parser.add_argument("--cpus", type=float)
    parser.add_argument("--memory")
    parser.add_argument("--pids-limit", type=int)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument(
        "--progress-interval",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="print live agent progress this often; 0 disables it (default: 30)",
    )


def configurations(
    args: argparse.Namespace, agent: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    missing = [name for name in agent["environment"] if name not in os.environ]
    if missing:
        raise AgentConfigurationError(
            f"host environment variables are not set: {', '.join(missing)}"
        )
    binary = args.agent_binary
    if (
        binary is None
        and args.use_host_agent
        and agent.get("prefer_host_binary", True)
    ):
        discovered = shutil.which(agent["command"][0])
        binary = Path(discovered) if discovered else None
    binary = binary.expanduser().resolve() if binary else None
    toolchain = (
        args.host_toolchain.expanduser().resolve() if args.host_toolchain else None
    )
    home_seed = (
        args.agent_home_seed.expanduser().resolve() if args.agent_home_seed else None
    )
    for path, kind, predicate in (
        (binary, "agent binary", Path.is_file),
        (toolchain, "host toolchain", Path.is_dir),
        (home_seed, "agent home seed", Path.is_dir),
    ):
        if path and not predicate(path):
            raise AgentConfigurationError(f"{kind} does not exist: {path}")
    if any(value is not None and value <= 0 for value in (args.cpus, args.pids_limit)):
        raise AgentConfigurationError("resource limits must be positive")
    if args.timeout <= 0:
        raise AgentConfigurationError("--timeout must be positive")
    if args.progress_interval < 0:
        raise AgentConfigurationError("--progress-interval must be non-negative")
    agent.update(
        image=args.image,
        mounts=args.mount,
        host_binary=str(binary) if binary else None,
        home_seed=str(home_seed) if home_seed else None,
    )
    runtime = {
        "kind": "apptainer",
        "binary": args.apptainer_binary,
        "host_toolchain": str(toolchain) if toolchain else None,
        "network_policy": args.network_policy,
        "cpus": args.cpus,
        "memory": args.memory,
        "pids_limit": args.pids_limit,
        "timeout_seconds": args.timeout,
        "progress_interval_seconds": args.progress_interval,
    }
    return agent, runtime


def invocation(
    config: dict[str, Any],
    run_directory: Path,
    prompt_path: Path,
    runtime_workdir: Path,
    agent_home: Path,
    feedback: Path | None,
    submission_check_directory: Path | None = None,
) -> list[str]:
    runtime, agent = config["runtime"], config["agent"]
    if not DOCUMENTATION_SOURCE.is_dir():
        raise AgentConfigurationError(
            f"bundled Catala documentation does not exist: {DOCUMENTATION_SOURCE}"
        )
    command = [
        runtime["binary"],
        "exec",
        "--containall",
        "--cleanenv",
        "--no-eval",
        "--no-mount",
        "home,cwd,hostfs",
        "--cwd",
        WORKSPACE_MOUNT,
        "--workdir",
        str(runtime_workdir),
        "--bind",
        f"{run_directory / 'workspace'}:{WORKSPACE_MOUNT}:rw",
        "--bind",
        f"{prompt_path}:{PROMPT_MOUNT}:ro",
        "--bind",
        f"{DOCUMENTATION_SOURCE}:{DOCUMENTATION_MOUNT}:ro",
        # Dataset guidance retains the original generator name; the generic prompt uses the second name for the opaque final…
        "--bind",
        f"{SUBMISSION_CHECK_HELPER_SOURCE}:{INPUT_REQUIREMENTS_HELPER_MOUNT}:ro",
        "--bind",
        f"{SUBMISSION_CHECK_HELPER_SOURCE}:{SUBMISSION_CHECK_HELPER_MOUNT}:ro",
        "--bind",
        f"{REGENERATE_ANALYSIS_HELPER_SOURCE}:{REGENERATE_ANALYSIS_HELPER_MOUNT}:ro",
        "--bind",
        f"{MINI_SWE_AGENT_HELPER_SOURCE}:{MINI_SWE_AGENT_HELPER_MOUNT}:ro",
        "--bind",
        f"{agent_home}:/agent-home:rw",
    ]
    if submission_check_directory is not None:
        command.extend(
            [
                "--bind",
                f"{submission_check_directory}:{SUBMISSION_CHECK_DIRECTORY_MOUNT}:rw",
            ]
        )
    if (
        (run_directory / "workspace/replay_cases.py").is_file()
        or feedback is not None
        and (feedback / "task.json").is_file()
    ):
        package = Path(__file__).resolve().parents[1]
        command.extend(["--bind", f"{package}:/rtdf/python/rtdf_formalizer:ro"])
    if runtime.get("network_policy") == "none":
        command.extend(["--net", "--network", "none"])
    for option, key in (
        ("--cpus", "cpus"),
        ("--memory", "memory"),
        ("--pids-limit", "pids_limit"),
    ):
        if runtime.get(key) is not None:
            command.extend([option, str(runtime[key])])
    toolchain = runtime.get("host_toolchain")
    if toolchain:
        command.extend(["--bind", f"{toolchain}:{toolchain}:ro"])
    container_binary = None
    if agent.get("host_binary"):
        binary = Path(agent["host_binary"])
        command.extend(["--bind", f"{binary.parent}:/opt/rtdf/agent:ro"])
        container_binary = f"/opt/rtdf/agent/{binary.name}"
    for mount in agent["mounts"]:
        command.extend(["--bind", f"{mount['source']}:{mount['target']}:ro"])
    if feedback and feedback.is_dir():
        command.extend(["--bind", f"{feedback}:{FEEDBACK_MOUNT}:ro"])
    command.append(agent["image"])
    agent_command = [
        value.replace("{workspace}", WORKSPACE_MOUNT).replace(
            "{prompt_file}", PROMPT_MOUNT
        )
        for value in agent["command"]
    ]
    if container_binary:
        agent_command[0] = container_binary
    # --containall supplies an empty synthetic home and masks Apptainer's --home source mapping.
    return command + ["/usr/bin/env", "HOME=/agent-home"] + agent_command


def environment(
    config: dict[str, Any], *, submission_check: bool = False
) -> dict[str, str]:
    result = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("APPTAINERENV_", "SINGULARITYENV_"))
    }
    toolchain = config["runtime"].get("host_toolchain")
    path = ["/opt/rtdf/agent", "/opt/mini-swe-agent/bin"]
    if toolchain:
        path += [f"{toolchain}/opam/catala/bin", f"{toolchain}/opam/cutecat/bin"]
        path += [f"{toolchain}/envs/catala/bin", f"{toolchain}/envs/cutecat/bin"]
    path += [
        "/usr/local/sbin",
        "/usr/local/bin",
        "/usr/sbin",
        "/usr/bin",
        "/sbin",
        "/bin",
    ]
    result["APPTAINERENV_XDG_CACHE_HOME"] = "/agent-home/.cache"
    result["APPTAINERENV_PATH"] = ":".join(path)
    if config["agent"].get("base_url"):
        result["APPTAINERENV_OPENAI_API_BASE"] = config["agent"]["base_url"]
        result["APPTAINERENV_OPENAI_API_KEY"] = os.environ[
            config["agent"]["api_key_env"]
        ]
    if submission_check:
        result["APPTAINERENV_RTDF_SUBMISSION_CHECK_SOCKET"] = (
            SUBMISSION_CHECK_SOCKET_MOUNT
        )
    for name in config["agent"]["environment"]:
        result[f"APPTAINERENV_{name}"] = os.environ[name]
    return result


@contextlib.contextmanager
def submission_check_service(
    socket_path: Path,
    check: Callable[[], tuple[bool, str]],
    commands: dict[str, Callable[[], dict[str, Any]]] | None = None,
):
    # Serve opaque host-side submission validation to the contained agent.
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(socket_path))
    server.listen(4)
    server.settimeout(0.2)
    stopped = threading.Event()

    def serve() -> None:
        while not stopped.is_set():
            try:
                connection, _ = server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with connection:
                try:
                    request = connection.recv(4096).strip()
                    if request == b"check":
                        accepted, message = check()
                        response = {"accepted": accepted, "message": message}
                    else:
                        value = json.loads(request)
                        command = value.get("command") if isinstance(value, dict) else None
                        if command not in (commands or {}):
                            raise ValueError("invalid service command")
                        response = {"accepted": True, **commands[command]()}
                except Exception as error:
                    response = {
                        "accepted": False,
                        "message": f"service command failed: {type(error).__name__}: {error}",
                    }
                connection.sendall((json.dumps(response) + "\n").encode("utf-8"))

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        yield
    finally:
        stopped.set()
        server.close()
        worker.join(timeout=2)
        with contextlib.suppress(FileNotFoundError):
            socket_path.unlink()


def _terminate(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def execute(
    command: Sequence[str],
    prompt: str,
    stdout_path: Path,
    stderr_path: Path,
    timeout: int,
    process_environment: dict[str, str],
    progress: Callable[[float], None] | None = None,
    progress_interval: float = 30.0,
) -> tuple[int, bool, float]:
    started, timed_out = time.monotonic(), False
    monitor_stop = threading.Event()

    def report_progress() -> None:
        if progress is None or progress_interval <= 0:
            return
        while not monitor_stop.wait(progress_interval):
            try:
                progress(time.monotonic() - started)
            except Exception:
                # Reporting must never terminate or alter the agent attempt.
                pass

    try:
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                env=process_environment,
            )
            monitor = threading.Thread(target=report_progress, daemon=True)
            monitor.start()
            try:
                process.communicate(input=prompt.encode(), timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _terminate(process)
            except BaseException:
                _terminate(process)
                raise
            finally:
                monitor_stop.set()
                monitor.join()
    except FileNotFoundError as error:
        raise AgentConfigurationError(
            f"Apptainer executable not found: {command[0]}"
        ) from error
    elapsed = time.monotonic() - started
    if progress is not None and progress_interval > 0:
        try:
            progress(elapsed)
        except Exception:
            pass
    return process.returncode, timed_out, elapsed
