"""Minimal dotenv loading for coding-agent environment variables."""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path

from .base import AgentConfigurationError


ASSIGNMENT = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def load_dotenv(path: Path) -> tuple[str, ...]:
    # Load every assignment in *path*, preserving values from the host.
    if not path.is_file():
        return ()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise AgentConfigurationError(
            f"cannot read environment file {path}: {error}"
        ) from error

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = ASSIGNMENT.fullmatch(line)
        if match is None:
            raise AgentConfigurationError(
                f"invalid assignment in {path} at line {line_number}"
            )
        try:
            words = shlex.split(match.group(2), comments=True, posix=True)
        except ValueError as error:
            raise AgentConfigurationError(
                f"invalid value in {path} at line {line_number}"
            ) from error
        values[match.group(1)] = " ".join(words)

    for name, value in values.items():
        os.environ.setdefault(name, value)
    return tuple(values)
