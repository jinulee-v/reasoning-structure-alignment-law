"""Validate formalized programs against natural-language test cases."""

from .translator import (
    generate_translator,
    stage_translator_trial_tool,
    translator_prompt,
)
from .verification import (
    run,
    run_verification_stage,
    validate_verification_result,
)

__all__ = [
    "generate_translator",
    "run",
    "run_verification_stage",
    "stage_translator_trial_tool",
    "translator_prompt",
    "validate_verification_result",
]
