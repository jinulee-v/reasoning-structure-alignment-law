"""Versioned semantic-interface guidance for candidate adapters."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DATASET_ALIASES = {
    "airline": "airline",
    "sara": "sara",
    "nsw_community_gaming": "nsw_community_gaming",
    "aides_logement": "aides_logement",
    "allocations_familiales": "allocations_familiales",
}
RAW_DATASET_DIRECTORIES = {
    "airline": "airline",
    "sara": "sara",
    "nsw_community_gaming": "NSW_community_gaming",
    "aides_logement": "aides_logement",
    "allocations_familiales": "allocations_familiales",
}

PUBLIC_WRAPPER_FILES = {
    "airline": "airline_wrapper.catala_en",
    "sara": "sara_wrapper.catala_en",
    "nsw_community_gaming": "nsw_community_gaming_wrapper.catala_en",
    "aides_logement": "aides_logement_wrapper.catala_fr",
    "allocations_familiales": "allocations_familiales_wrapper.catala_fr",
}

PUBLIC_SCOPE_DECLARATION = re.compile(
    r"^[ \t]*(?:declaration[ \t]+scope|déclaration[ \t]+champ d'application)"
    r"[ \t]+([^:\r\n]+):",
    re.MULTILINE,
)


def canonical_dataset_name(name: str) -> str | None:
    normalized = name.casefold().replace("-", "_")
    return DATASET_ALIASES.get(normalized)


def semantic_guidance(name: str) -> str | None:
    # Return the prompt fragment for a known benchmark dataset.
    canonical = canonical_dataset_name(name)
    if canonical is None:
        return None
    dataset_directory = RAW_DATASET_DIRECTORIES[canonical]
    path = REPOSITORY_ROOT / "data/raw" / dataset_directory / f"{canonical}.md"
    return path.read_text(encoding="utf-8").strip()


def public_endpoint_scopes(name: str) -> tuple[str, ...]:
    # Return the endpoint surface declared by the dataset's public wrapper.
    canonical = canonical_dataset_name(name)
    if canonical is None:
        return ()
    dataset_directory = RAW_DATASET_DIRECTORIES[canonical]
    wrapper = (
        REPOSITORY_ROOT
        / "data/catala_gold"
        / dataset_directory
        / PUBLIC_WRAPPER_FILES[canonical]
    )
    return tuple(PUBLIC_SCOPE_DECLARATION.findall(wrapper.read_text(encoding="utf-8")))


def public_endpoint_test_targets(name: str) -> tuple[str, ...]:
    # Return exact BOBCat target IDs generated from public wrapper scopes.
    canonical = canonical_dataset_name(name)
    if canonical is None:
        return ()
    wrapper_stem = Path(PUBLIC_WRAPPER_FILES[canonical]).stem
    return tuple(
        f"{canonical}_scope_{wrapper_stem}_{scope}"
        for scope in public_endpoint_scopes(canonical)
    )


def endpoint_test_files(name: str, source: Path | None) -> tuple[str, ...]:
    # Discover frozen cases whose target is exactly a public wrapper scope.
    if source is None or not source.is_dir():
        return ()
    allowed = set(public_endpoint_test_targets(name))
    selected: list[str] = []
    for path in sorted(source.glob("*.jsonl")):
        targets: set[str] = set()
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                value = json.loads(line)
                target = value.get("target")
                if isinstance(target, str):
                    targets.add(target)
        if len(targets) == 1 and targets <= allowed:
            selected.append(path.name)
    return tuple(selected)
