"""Requirement-derived native scopes used as BOBCat coverage targets.

``REQUIREMENT_OUTPUTS.json`` is the benchmark contract. Several requirements
may name different outputs of one scope; branch-coverage campaigns enter that
scope once and retain all its outputs so BOBCat and path-oriented engines have
the same whole-scope coverage universe.
"""
from __future__ import annotations

import json

from . import entrypoints, paths
from .run import Target, _declares_module


def _stem(filename: str) -> str:
    return filename.split(".catala_", 1)[0]


def _requirement_groups(port: str) -> list[tuple[str, str, list[dict]]]:
    """Return unique ``(file, scope)`` targets in declaration order."""
    manifest = paths.requirement_outputs_file(port)
    if not manifest.is_file():
        raise RuntimeError(f"missing requirement mapping {manifest}")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 \
            or not isinstance(payload.get("requirements"), list):
        raise RuntimeError(f"invalid requirement mapping {manifest}")
    grouped: dict[tuple[str, str], list[dict]] = {}
    for index, item in enumerate(payload["requirements"]):
        if not isinstance(item, dict) or any(
                not isinstance(item.get(key), str) or not item[key]
                for key in ("requirement_id", "file", "scope", "output")):
            raise RuntimeError(
                f"invalid requirement mapping {manifest}: requirements[{index}]")
        grouped.setdefault((item["file"], item["scope"]), []).append(item)
    return [(file, scope, mappings)
            for (file, scope), mappings in grouped.items()]


def enumerated_targets(refresh: bool = True) -> list[Target]:
    """One whole-scope target per unique requirement-mapped native scope."""
    _ = refresh
    out: list[Target] = []
    for port, directory in paths.PORT_DIRS.items():
        census = entrypoints.scan(directory)
        siblings = paths.source_files(directory)
        root_name = paths.PORT_ROOT_FILES.get(port)
        root = directory / root_name if root_name else None
        signatures = {(sig.file, sig.name): sig for sig in census.entries
                      if sig.kind == "scope"}
        signatures_by_name: dict[str, list] = {}
        for sig in signatures.values():
            signatures_by_name.setdefault(sig.name, []).append(sig)
        for filename, scope, mappings in _requirement_groups(port):
            source = directory / filename
            if not source.is_file():
                raise RuntimeError(
                    f"requirement target source does not exist: {source}")
            sig = signatures.get((filename, scope))
            # French Inclusion projects expose scopes from their fragments as
            # members of the root compiler unit. REQUIREMENT_OUTPUTS therefore
            # names the root file even though the declaration text is in (for
            # example) prologue.catala_fr.
            if sig is None and source == root:
                candidates = signatures_by_name.get(scope, [])
                if len(candidates) == 1:
                    sig = candidates[0]
            if sig is None:
                raise RuntimeError(
                    f"requirement target scope does not exist: {filename}:{scope}")
            if not entrypoints.enterable(sig, census.types):
                raise RuntimeError(
                    f"requirement target is not BOBCat-enterable: {filename}:{scope}")
            # Inclusion fragments in the French examples are entered through
            # their project root. A proper Module is directly enterable.
            harness = source if _declares_module(source) else root or source
            requirement_ids = [item["requirement_id"] for item in mappings]
            outputs = list(dict.fromkeys(item["output"] for item in mappings))
            out.append(Target(
                name=f"{port}_scope_{_stem(filename)}_{scope}",
                port=port,
                harness=harness,
                scope=scope,
                modules=[module for module in siblings if module != harness],
                include_dirs=paths.extra_include_dirs(port),
                project=(f"{port}_requirement_root" if harness == root else
                         f"{port}_requirement_{_stem(filename)}"),
                note=(f"Requirements {', '.join(requirement_ids)}; native "
                      f"scope {filename}:{scope}; outputs "
                      f"{', '.join(outputs)}. Whole-scope branch campaign."),
            ))
    return out


def by_port(ts: list[Target]) -> dict[str, list[Target]]:
    out = {port: [] for port in paths.PORTS}
    for target in ts:
        out[target.port].append(target)
    return {port: values for port, values in out.items() if values}


def by_name(names: list[str], enumerated: bool = False) -> list[Target]:
    _ = enumerated
    ts = enumerated_targets()
    if not names:
        return ts
    index = {target.name: target for target in ts}
    missing = [name for name in names if name not in index]
    if missing:
        raise SystemExit(
            f"no such target: {', '.join(missing)}\n"
            f"  known targets: {', '.join(sorted(index))}")
    return [index[name] for name in names]
