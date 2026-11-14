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
from .mini_swe_agent import DEFINITION as MINI_SWE_AGENT


AGENTS = {
    agent.name: agent
    for agent in (CODEX, CLAUDE_CODE, MINI_SWE_AGENT)
}


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
        "--agent-base-url",
        help="OpenAI-compatible endpoint for mini-swe-agent",
    )
    parser.add_argument(
        "--agent-api-key-env",
        help="host environment variable containing that endpoint's API key",
    )
    parser.add_argument(
        "--agent-command",
        help='override agent argv as JSON, e.g. `["codex", "exec", "-"]`',
    )


def configuration(args: argparse.Namespace, root: Path | None = None) -> dict[str, Any]:
    definition = get(args.agent)
    base_url = getattr(args, "agent_base_url", None)
    api_key_env = getattr(args, "agent_api_key_env", None)
    if (base_url or api_key_env) and definition.name != "mini-swe-agent":
        raise AgentConfigurationError(
            "--agent-base-url and --agent-api-key-env are supported only by mini-swe-agent"
        )
    if bool(base_url) != bool(api_key_env):
        raise AgentConfigurationError(
            "--agent-base-url and --agent-api-key-env must be supplied together"
        )
    repository = root or Path(__file__).resolve().parents[2]
    environment = set(load_dotenv(repository / ".env"))
    if api_key_env:
        environment.add(api_key_env)
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
        "prefer_host_binary": definition.prefer_host_binary,
        "base_url": base_url,
        "api_key_env": api_key_env,
    }


__all__ = [
    "AGENTS",
    "AgentConfigurationError",
    "AgentDefinition",
    "add_cli_arguments",
    "configuration",
    "get",
]
