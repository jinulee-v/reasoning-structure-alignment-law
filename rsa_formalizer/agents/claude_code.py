import os
from pathlib import Path

from .base import AgentConfigurationError, AgentDefinition, formalization_prompt
from .dotenv import load_dotenv


OAUTH_VARIABLE = "CLAUDE_CODE_OAUTH_TOKEN"


def configure_command(
    command: list[str], provider: str | None, model: str
) -> list[str]:
    return command + ["--model", model]


def prepare_auth(root: Path) -> tuple[str, ...]:
    load_dotenv(root / ".env")
    if not os.environ.get(OAUTH_VARIABLE):
        raise AgentConfigurationError(
            f"Claude Code credentials are unavailable; export or define {OAUTH_VARIABLE} in .env"
        )
    return (OAUTH_VARIABLE,)


DEFINITION = AgentDefinition(
    name="claude-code",
    prepare_auth=prepare_auth,
    configure_default_command=configure_command,
    default_command=(
        "claude",
        "-p",
        "--verbose",
        "--output-format",
        "stream-json",
        "--disallowedTools",
        "WebFetch,WebSearch",
        "--dangerously-skip-permissions",
    ),
    prompt_builder=formalization_prompt,
)
