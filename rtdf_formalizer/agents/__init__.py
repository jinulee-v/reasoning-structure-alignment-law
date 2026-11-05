"""Coding-agent definitions used by the experiment runner."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from .base import AgentConfigurationError, AgentDefinition
from .claude_code import DEFINITION as CLAUDE_CODE
from .codex import DEFINITION as CODEX
from .dotenv import load_dotenv
from .opencode import DEFINITION as OPENCODE


AGENTS = {agent.name: agent for agent in (CODEX, CLAUDE_CODE, OPENCODE)}


def get(name: str) -> AgentDefinition:
    try:
        return AGENTS[name]
    except KeyError as error:
        raise AgentConfigurationError(f"unsupported agent: {name}") from error


def add_cli_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--agent", choices=sorted(AGENTS), required=True)
    parser.add_argument(
        "--agent-provider",
        required=True,
        help="coding-agent model provider",
    )
    parser.add_argument("--agent-model", "--model", dest="agent_model", required=True)
    parser.add_argument(
        "--agent-command",
        help='override agent argv as JSON, e.g. `["codex", "exec", "-"]`',
    )


def configuration(args: argparse.Namespace, root: Path | None = None) -> dict[str, Any]:
    definition = get(args.agent)
    repository = root or Path(__file__).resolve().parents[2]
    environment = set(load_dotenv(repository / ".env"))
    if definition.prepare_auth is not None:
        environment.update(definition.prepare_auth(repository))
    missing = sorted(name for name in environment if name not in os.environ)
    if missing:
        raise AgentConfigurationError(
            "host environment variables are not set: " + ", ".join(missing)
        )
    return {
        "framework": definition.name,
        "provider": args.agent_provider,
        "model": args.agent_model,
        "command": definition.command(
            args.agent_command, provider=args.agent_provider, model=args.agent_model
        ),
        "environment": sorted(environment),
    }


__all__ = [
    "AGENTS",
    "AgentConfigurationError",
    "AgentDefinition",
    "add_cli_arguments",
    "configuration",
    "get",
]
