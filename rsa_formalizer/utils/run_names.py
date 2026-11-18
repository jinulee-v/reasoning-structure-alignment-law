"""Stable UTC initial names and method-specific names derived from them."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from rsa_formalizer.stages.utils.common import RunnerError

METHODS = {
    "reasoning_structure_alignment": "reasoning-structure-alignment",
    "baseline_final_answer_only": "baseline-final-answer-only",
}


def component(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")
    if not result:
        raise RunnerError("run name component must contain a letter or digit")
    return result


def initial_name(model: str, dataset: str, suffix: str | None = None, *, timestamp: str | None = None) -> str:
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    if not re.fullmatch(r"\d{8}-\d{4}", stamp):
        raise RunnerError("run timestamp must be YYYYMMDD-HHMM in UTC")
    name = f"{stamp}-initial-{component(model)}-{component(dataset)}"
    if suffix:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", suffix):
            raise RunnerError("suffix may contain only letters, digits, '.', '_' and '-'")
        name += f"-{suffix}"
    return name


def repair_name(initial: Path | str, mode: str) -> str:
    name = Path(initial).name
    if mode not in METHODS:
        raise RunnerError(f"unknown repair mode: {mode}")
    match = re.fullmatch(r"(\d{8}-\d{4})-initial-([A-Za-z0-9][A-Za-z0-9_.-]*)", name)
    if not match:
        raise RunnerError("repair requires an initial run named YYYYMMDD-HHMM-initial-MODEL-DATASET[-SUFFIX]")
    return f"{match[1]}-repair-{METHODS[mode]}-{match[2]}"
