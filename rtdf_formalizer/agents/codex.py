import json
import os
import tempfile
from pathlib import Path

from .base import AgentConfigurationError, AgentDefinition, formalization_prompt


DEFAULT_REASONING_EFFORT = "xhigh"


def credential_file() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "auth.json"


def prepare_auth(_root: Path) -> tuple[str, ...]:
    source = credential_file()
    if not source.is_file():
        raise AgentConfigurationError(
            f"Codex credential file does not exist: {source}; run `codex login` first"
        )
    return ()


def stage_auth(agent_home: Path) -> None:
    source = credential_file()
    if not source.is_file():
        raise AgentConfigurationError(f"Codex credential file does not exist: {source}")
    destination = agent_home / ".codex/auth.json"
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.write_bytes(source.read_bytes())
    destination.chmod(0o600)


def persist_auth(agent_home: Path) -> None:
    source = agent_home / ".codex/auth.json"
    if not source.is_file():
        return
    data = source.read_bytes()
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as error:
        raise AgentConfigurationError(
            f"refusing to persist malformed Codex credential {source}"
        ) from error
    if not isinstance(parsed, dict):
        raise AgentConfigurationError(
            f"refusing to persist malformed Codex credential {source}"
        )
    destination = credential_file()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def configure_command(
    command: list[str], provider: str | None, model: str
) -> list[str]:
    return command[:-1] + [
        "--model",
        model,
        "-c",
        f'model_reasoning_effort="{DEFAULT_REASONING_EFFORT}"',
        command[-1],
    ]


DEFINITION = AgentDefinition(
    name="codex",
    prepare_auth=prepare_auth,
    stage_auth=stage_auth,
    persist_auth=persist_auth,
    configure_default_command=configure_command,
    default_command=(
        "codex",
        "exec",
        "--json",
        "--dangerously-bypass-approvals-and-sandbox",
        "--skip-git-repo-check",
        "-",
    ),
    prompt_builder=formalization_prompt,
)
