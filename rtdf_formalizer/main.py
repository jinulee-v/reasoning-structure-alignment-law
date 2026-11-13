"""Command-line entry point for the resumable RTDF formalizer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rtdf_formalizer import runner
from rtdf_formalizer import agents
from rtdf_formalizer.agents import apptainer
from rtdf_formalizer.agents.dotenv import load_dotenv


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the resumable RTDF formalizer.")
    commands = parser.add_subparsers(dest="subcommand", required=True)
    start = commands.add_parser(
        "start", help="create a run and execute until its next pause or completion"
    )
    start.add_argument("--dataset", required=True)
    start.add_argument("--run-id")
    start.add_argument(
        "--max-scope-revisions",
        type=int,
        default=2,
        help="maximum accepted repair revisions per scope (default: 2)",
    )
    start.add_argument(
        "--repair-scope-selection",
        choices=("all", "entry"),
        default="all",
        help="repair all scopes or only top-level entry scopes (default: all)",
    )
    start.add_argument(
        "--reasoning-trace-provider",
        help="reasoning-trace provider (default: coding-agent provider)",
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
    start.add_argument("--bobcat-timeout-seconds", type=int, default=1800)
    start.add_argument(
        "--bobcat-positive-hundred-money-inputs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "require every money input to be > 0 and divisible by $100 "
            "(default: enabled)"
        ),
    )
    start.add_argument("--bobcat-max-list-length", type=int)
    start.add_argument("--bobcat-representation-capacity", type=int, default=64)
    start.add_argument("--bobcat-solver-timeout-ms", type=int)
    start.add_argument("--bobcat-solver-timeout-max-ms", type=int)
    start.add_argument("--bobcat-objective-timeout-ms", type=int)
    start.add_argument(
        "--llm-generated-tests-per-scope",
        type=int,
        default=6,
        help="scope-mapped NL specification tests designed during recursive repair (default: 6)",
    )
    start.add_argument(
        "--metamorphic-pairs-per-scope",
        type=int,
        default=6,
        help="provision-preserving BOBCat/LLM pairs per scope (default: 6)",
    )
    start.add_argument(
        "--reasoning-base-url",
        help="OpenAI-compatible API URL for non-OpenAI providers",
    )
    start.add_argument("--reasoning-api-key-env", default="OPENAI_API_KEY")
    start.add_argument(
        "--extraction-provider",
        choices=("openai",),
        default="openai",
        help="provider for per-test natural-language information extraction (default: openai)",
    )
    start.add_argument(
        "--extraction-model",
        default="gpt-6-luna",
        help=(
            "model for per-test scope selection and schema-constrained extraction "
            "(default: gpt-6-luna)"
        ),
    )
    start.add_argument("--extraction-base-url")
    start.add_argument("--extraction-api-key-env", default="OPENAI_API_KEY")
    start.add_argument("--extraction-jobs", type=int, default=8)
    agents.add_cli_arguments(start)
    apptainer.add_cli_arguments(start, runner.ROOT)
    resume = commands.add_parser("resume", help="continue a durable run")
    resume.add_argument("run_directory", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser()
    args = parser.parse_args(argv)
    try:
        load_dotenv(runner.ROOT / ".env")
        run_directory = (
            runner.create_run(args)
            if args.subcommand == "start"
            else args.run_directory
        )
        state = runner.resume_run(run_directory)
    except (agents.AgentConfigurationError, runner.RunnerError) as error:
        parser.exit(2, f"error: {error}\n")
    print(
        json.dumps(
            {"run_directory": str(Path(run_directory).resolve()), "state": state},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
