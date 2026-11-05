from .base import AgentDefinition, formalization_prompt


def configure_default_command(
    command: list[str], provider: str | None, model: str
) -> list[str]:
    selector = model
    if provider and not model.startswith(f"{provider}/"):
        selector = f"{provider}/{model}"
    return command + ["--model", selector]


DEFINITION = AgentDefinition(
    name="opencode",
    default_command=("opencode", "run", "--format", "json"),
    configure_default_command=configure_default_command,
    prompt_builder=formalization_prompt,
)
