"""Filesystem primitives and shared runner constants."""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs"
SCHEMA_VERSION = 2
VERIFICATION_SCHEMA_VERSION = 1
SNAPSHOT_SCHEMA_VERSION = 1
TRANSLATOR_MODEL = "gpt-5.6-sol"
FENCE_START = re.compile(r"^```(catala(?:-metadata)?)(?:[ \t].*)?\r?\n?$")
FENCE_END = re.compile(r"^```[ \t]*\r?\n?$")
SCOPE_DECLARATION = re.compile(
    r"^[ \t]*(?:#[^\n]*\n[ \t]*)*(?:declaration[ \t]+scope|"
    r"déclaration[ \t]+champ[ \t]+d'application)[ \t]+"
    r"([^\W\d]\w*)[ \t]*:",
    re.MULTILINE,
)


class RunnerError(RuntimeError):
    # An expected, user-actionable experiment-runner failure.
    pass


@dataclasses.dataclass(frozen=True)
class FenceDocument:
    skeleton: bytes
    blocks: tuple[bytes, ...]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any, *, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, indent=indent, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunnerError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise RunnerError(f"expected a JSON object in {path}")
    return value


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(descriptor, line.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def run_lock(run_directory: Path) -> Iterator[None]:
    lock_path = run_directory / ".lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RunnerError(
                f"another process is operating on {run_directory}"
            ) from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def parse_fenced_document(path: Path) -> FenceDocument:
    # Replace Catala fence bodies with a marker while retaining every other byte.
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    skeleton: list[bytes] = []
    blocks: list[bytes] = []
    body: list[bytes] | None = None
    opening_line = 0

    for line_number, line in enumerate(lines, start=1):
        decoded = line.decode("utf-8", errors="surrogateescape")
        if body is None:
            if FENCE_START.fullmatch(decoded):
                body = []
                opening_line = line_number
                skeleton.append(line)
                skeleton.append(b"<RTDF-CATALA-BODY>\n")
            else:
                skeleton.append(line)
        elif FENCE_END.fullmatch(decoded):
            blocks.append(b"".join(body))
            skeleton.append(line)
            body = None
        else:
            body.append(line)

    if body is not None:
        raise RunnerError(f"unclosed Catala fence in {path} at line {opening_line}")
    return FenceDocument(skeleton=b"".join(skeleton), blocks=tuple(blocks))


def normalize_protected_whitespace(value: bytes) -> bytes:
    # Canonicalize whitespace outside Catala bodies for integrity comparison.
    return b" ".join(value.split())


def relative_files(directory: Path) -> dict[str, Path]:
    return {
        path.relative_to(directory).as_posix(): path
        for path in directory.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def cleanup_clerk_artifacts(workspace: Path) -> None:
    # Remove generated Clerk output before integrity checks and snapshots.
    for name in ("_build", "_targets"):
        path = workspace / name
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()
