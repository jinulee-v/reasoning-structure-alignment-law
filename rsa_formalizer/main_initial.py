"""Initial formalization, held-out validation, and shared CoT test generation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rsa_formalizer import agents
from rsa_formalizer.agents import apptainer
from rsa_formalizer.agents.dotenv import load_dotenv
from rsa_formalizer.pipeline import complete_initial
from rsa_formalizer.utils.cli_support import logged
from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.utils.run_state import create_run
from rsa_formalizer.stages.reasoning_structure_alignment import experiment


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="subcommand", required=True)
    start = commands.add_parser("start", help="formalize, validate, and generate shared tests")
    start.add_argument("--dataset", required=True)
    start.add_argument("--suffix", help="optional suffix appended to the generated initial run name")
    start.add_argument(
        "--reasoning-trace-provider",
        help="reasoning provider: codex, claude-subscription, claude-code, or compatible endpoint (openai/anthropic are subscription aliases; default: coding-agent provider)",
    )
    start.add_argument(
        "--reasoning-trace-model",
        help="reasoning-trace model (default: coding-agent model)",
    )
    start.add_argument("--reasoning-jobs", type=int, default=8)
    start.add_argument(
        "--statute-source",
        choices=("gold", "search"),
        default="gold",
        help="full statute context; search is reserved for a future implementation",
    )
    start.add_argument(
        "--reasoning-base-url",
        help="OpenAI-compatible API URL for non-OpenAI providers",
    )
    start.add_argument("--reasoning-api-key-env", default="OPENAI_API_KEY",
                       help="API-key variable for other compatible endpoints; ignored by subscription providers")
    start.add_argument(
        "--extraction-provider",
        choices=("codex", "claude-subscription", "openai", "anthropic"),
        default="codex",
        help="subscription provider for information extraction (default: codex; openai/anthropic are legacy aliases)",
    )
    start.add_argument(
        "--extraction-model",
        default="gpt-6-luna",
        help=(
            "model for per-test scope selection and schema-constrained extraction "
            "(default: gpt-6-luna)"
        ),
    )
    start.add_argument("--extraction-base-url", help="legacy option; subscription providers use fixed endpoints")
    start.add_argument("--extraction-api-key-env", default="OPENAI_API_KEY",
                       help="legacy option; subscription providers use coding-agent credentials")
    start.add_argument("--extraction-jobs", type=int, default=8)
    agents.add_cli_arguments(start)
    apptainer.add_cli_arguments(start, exp.ROOT)
    start.add_argument("--generation-jobs", type=int, default=4)
    start.add_argument("--max-extraction-attempts", type=int, default=2)
    start.add_argument("--prepare-only", action="store_true", help="create the run without model calls")
    resume = commands.add_parser("resume", aliases=["drive"], help="resume initial stages through test generation")
    resume.add_argument("run_directory", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser()
    args = parser.parse_args(argv)
    try:
        load_dotenv(exp.ROOT / ".env")
        if args.subcommand == "start":
            if min(args.generation_jobs, args.max_extraction_attempts) < 1:
                raise exp.RunnerError("generation and graph extraction budgets must be positive")
            run = create_run(args)
            config = exp.load_json(run / "config.json")
            config["test_generation"] = {"jobs": args.generation_jobs,
                "max_extraction_attempts": args.max_extraction_attempts}
            exp.atomic_json(run / "config.json", config)
            experiment._write_shell(run)
            state = (exp.load_json(run / "state.json") if args.prepare_only
                     else logged(run, lambda: complete_initial(run)))
        else:
            run = args.run_directory.resolve()
            state = logged(run, lambda: complete_initial(run))
    except (agents.AgentConfigurationError, exp.RunnerError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps({"run_directory": str(run), "state": state}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
