import base64
import fcntl
import json
import os
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from .base import AgentConfigurationError, AgentDefinition, formalization_prompt


DEFAULT_REASONING_EFFORT = "xhigh"
_AUTH_LOCK = threading.Lock()


def subscription_auth(*, rejected_token: str | None = None) -> tuple[str, str | None]:
    """Borrow CLI OAuth credentials, refreshing under a process/thread lock.

    API keys are deliberately not accepted: these calls must use subscription
    billing. The lock coordinates pipeline workers, not the external Codex CLI.
    """
    path = credential_file()
    with _AUTH_LOCK:
        try:
            with open(path.with_suffix(".subscription.lock"), "a", opener=lambda p, f: os.open(p, f, 0o600)) as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                return _subscription_auth_locked(path, rejected_token)
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise AgentConfigurationError(
                f"Cannot read or refresh Codex subscription credentials at {path}; run `codex login`"
            ) from error


def _subscription_auth_locked(path: Path, rejected_token: str | None) -> tuple[str, str | None]:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise AgentConfigurationError("Malformed Codex credentials; run `codex login`")
    tokens = data.get("tokens") or {}
    if not isinstance(tokens, dict):
        raise AgentConfigurationError("Malformed Codex OAuth tokens; run `codex login`")
    token = tokens.get("access_token")
    if data.get("auth_mode") not in (None, "chatgpt") or not isinstance(token, str) or not token:
        raise AgentConfigurationError("Codex ChatGPT login required; run `codex login`")
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        expires = claims.get("exp")
    except (ValueError, IndexError, TypeError):
        expires = None
    if token == rejected_token or (isinstance(expires, (int, float)) and expires <= time.time() + 30):
        refresh = tokens.get("refresh_token")
        if not refresh:
            raise AgentConfigurationError("Codex token expired without a refresh token; run `codex login`")
        request = urllib.request.Request(
            "https://auth.openai.com/oauth/token",
            data=json.dumps({"client_id": "app_EMoamEEZ73f0CkXaXp7hrann",
                             "grant_type": "refresh_token", "refresh_token": refresh}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                refreshed = json.load(response)
        except urllib.error.URLError as error:
            # Never include token endpoint response bodies in pipeline artifacts.
            raise AgentConfigurationError("Codex credential refresh failed; run `codex login`") from error
        if not refreshed.get("access_token"):
            raise AgentConfigurationError("Codex credential refresh returned no access token")
        for key in ("access_token", "refresh_token", "id_token"):
            if refreshed.get(key):
                tokens[key] = refreshed[key]
        data["last_refresh"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _write_credentials(path, json.dumps(data).encode())
        token = tokens["access_token"]
    return token, tokens.get("account_id")


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
    _write_credentials(credential_file(), data)


def _write_credentials(destination: Path, data: bytes) -> None:
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
