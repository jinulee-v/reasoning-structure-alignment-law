from .base import (
    MINI_SWE_AGENT_HELPER_MOUNT,
    AgentDefinition,
    formalization_prompt,
)


def configure_default_command(
    command: list[str], provider: str | None, model: str
) -> list[str]:
    selector = model
    if provider and not model.startswith(f"{provider}/"):
        selector = f"{provider}/{model}"
    return command + ["--model", selector]


DEFINITION = AgentDefinition(
    name="mini-swe-agent",
    default_command=(
        "python3",
        MINI_SWE_AGENT_HELPER_MOUNT,
        "--yolo",
        "--exit-immediately",
        "--cost-limit",
        "0",
    ),
    configure_default_command=configure_default_command,
    prompt_builder=formalization_prompt,
    # `mini` is a Python console script. Binding just its host launcher would
    # omit the corresponding site-packages directory from the container.
    prefer_host_binary=False,
)
