"""Launch mini-swe-agent with the runner's mounted prompt as its task."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    prompt = Path("/rtdf/prompt.txt").read_text(encoding="utf-8")
    # mini-swe-agent launches an interactive first-run wizard unless this
    # marker is set. In the contained runner that wizard would consume the
    # mounted task from stdin as setup answers before honoring --task. The CLI
    # already receives the model explicitly and credentials via its environment.
    os.environ.setdefault("MSWEA_CONFIGURED", "true")
    os.execvp("mini", ["mini", *sys.argv[1:], "--task", prompt])


if __name__ == "__main__":
    main()
