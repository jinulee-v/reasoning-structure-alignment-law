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
from rtdf_formalizer.stages.reasoning_trace_diff_fuzzing.repair import RepairMode
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
        "--repair-mode",
        choices=[mode.value for mode in RepairMode],
        default=RepairMode.NO_TESTING.value,
        help=("repair strategy: no-testing, answer-only, dependency-first recursive"),
    )
    start.add_argument(
        "--max-iteration",
        type=int,
        default=2,
        help=(
            "global inclusive iteration cap for legacy modes; maximum attempts per "
            "scope for recursive mode (default: 2)"
        ),
    )
    start.add_argument("--reasoning-trace-provider", required=True)
    start.add_argument("--reasoning-trace-model", required=True)
    start.add_argument(
        "--statute-source",
        choices=("gold", "search"),
        default="gold",
        help="full statute context; search is reserved for a future implementation",
    )
    start.add_argument("--bobcat-timeout-seconds", type=int, default=1800)
    start.add_argument(
        "--bobcat-positive-hundred-money-inputs",
        action="store_true",
        help="require every money input to be > 0 and divisible by $100",
    )
    start.add_argument("--bobcat-max-list-length", type=int)
    start.add_argument("--bobcat-representation-capacity", type=int, default=64)
    start.add_argument("--bobcat-solver-timeout-ms", type=int)
    start.add_argument("--bobcat-solver-timeout-max-ms", type=int)
    start.add_argument("--bobcat-objective-timeout-ms", type=int)
    start.add_argument(
        "--stop-before-reasoning",
        action="store_true",
        help="legacy pause setting; answer-only always pauses before reasoning",
    )
    start.add_argument(
        "--reasoning-base-url",
        help="OpenAI-compatible API URL for non-OpenAI providers",
    )
    start.add_argument("--reasoning-api-key-env", default="OPENAI_API_KEY")
    start.add_argument(
        "--extraction-provider",
        choices=("openai",),
        required=True,
        help="provider for per-test natural-language information extraction",
    )
    start.add_argument(
        "--extraction-model",
        required=True,
        help="model for per-test scope selection and schema-constrained extraction",
    )
    start.add_argument("--extraction-base-url")
    start.add_argument("--extraction-api-key-env", default="OPENAI_API_KEY")
    start.add_argument("--extraction-jobs", type=int, default=8)
    agents.add_cli_arguments(start)
    apptainer.add_cli_arguments(start, runner.ROOT)
    resume = commands.add_parser("resume", help="continue a durable run")
    resume.add_argument("run_directory", type=Path)
    resume.add_argument(
        "--continue-reasoning",
        action="store_true",
        help="authorize reasoning for the current answer-only iteration",
    )
    migrate = commands.add_parser(
        "migrate-snapshots", help="backfill iteration snapshots in existing runs"
    )
    migrate.add_argument("runs_directory", nargs="?", type=Path, default=runner.RUNS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser()
    args = parser.parse_args(argv)
    try:
        load_dotenv(runner.ROOT / ".env")
        if args.subcommand == "migrate-snapshots":
            migrated = runner.migrate_run_snapshots(args.runs_directory)
            print(
                json.dumps(
                    {"migrated": [str(path.resolve()) for path in migrated]}, indent=2
                )
            )
            return 0
        run_directory = (
            runner.create_run(args)
            if args.subcommand == "start"
            else args.run_directory
        )
        state = runner.resume_run(
            run_directory, continue_reasoning=getattr(args, "continue_reasoning", False)
        )
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
