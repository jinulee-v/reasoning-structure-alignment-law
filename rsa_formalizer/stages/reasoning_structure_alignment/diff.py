"""Readable Catala changes between the frozen baseline and a repair candidate."""

from __future__ import annotations

import difflib
from pathlib import Path


def workspace_diff(before: Path, after: Path) -> str:
    paths = {path.relative_to(before) for path in before.rglob("*.catala_*")}
    paths.update(path.relative_to(after) for path in after.rglob("*.catala_*"))
    chunks = []
    for path in sorted(paths):
        old = (before / path).read_text(encoding="utf-8").splitlines() if (before / path).is_file() else []
        new = (after / path).read_text(encoding="utf-8").splitlines() if (after / path).is_file() else []
        chunks.extend(difflib.unified_diff(old, new, fromfile=f"before/{path}",
                                           tofile=f"after/{path}", lineterm=""))
    return "\n".join(chunks) + ("\n" if chunks else "")
