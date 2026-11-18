"""Select frozen tests, generate reports, repair, and validate a derived run."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rsa_formalizer import agents
from rsa_formalizer.agents.dotenv import load_dotenv
from rsa_formalizer.pipeline import complete_repair
from rsa_formalizer.utils.cli_support import logged, pair_summary
from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.reasoning_structure_alignment import experiment
from rsa_formalizer.utils.run_names import METHODS


def _positive_jobs(value: str) -> int:
    jobs = int(value)
    if jobs < 1:
        raise argparse.ArgumentTypeError("replay jobs must be positive")
    return jobs


def _set_agent_timeout(config: dict, seconds: int) -> None:
    runtime = config.setdefault("runtime", {})
    runtime["agent_timeout_seconds"] = seconds or None
    if seconds > 0:
        runtime["timeout_seconds"] = seconds


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="subcommand", required=True)
    start = commands.add_parser("start", help="fork an initial checkpoint and run repair")
    start.add_argument("--from-run", type=Path, required=True)
    start.add_argument("--mode", choices=tuple(METHODS.values()), required=True)
    start.add_argument("--filter-by-target-provision-reachability", action=argparse.BooleanOptionalAction,
                       default=False, help="opt in to rejecting graphs that do not apply the target (RSA only; default retains all executable cases)")
    start.add_argument("--replay-trace-mode", choices=("xml_scopes", "full"), default="xml_scopes")
    start.add_argument("--replay-jobs", type=_positive_jobs, default=4,
                       help="concurrent compiled replay cases (default: 4; 1 runs serially)")
    start.add_argument("--timeout", type=int, help="repair-agent timeout in seconds; 0 disables the agent time limit (default: inherit initial)")
    start.add_argument("--prepare-only", action="store_true", help="create the repair fork without executing it")
    resume = commands.add_parser("resume", aliases=["drive"], help="resume selection, repair, or evaluation")
    resume.add_argument("run_directory", type=Path)
    resume.add_argument("--timeout", type=int,
                        help="override and save the repair-agent timeout; 0 disables the agent time limit")
    resume.add_argument("--replay-jobs", type=_positive_jobs,
                        help="override and save the number of concurrent compiled replay cases")
    pair = commands.add_parser("pair-summary", help="compare held-out results for both methods")
    pair.add_argument("initial_run", type=Path)
    for command in ("prune-artifacts", "restore-artifacts"):
        sub = commands.add_parser(command)
        sub.add_argument("run_directory", type=Path)
        if command == "restore-artifacts":
            sub.add_argument("--stage", required=True, help="analysis, evaluation, or attempt-N")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = argument_parser()
    args = parser.parse_args(argv)
    try:
        load_dotenv(exp.ROOT / ".env")
        if args.subcommand in {"start", "resume", "drive"} and args.timeout is not None and args.timeout < 0:
            raise exp.RunnerError("repair timeout must be non-negative; use 0 for no agent time limit")
        if args.subcommand == "start":
            mode = next(k for k, v in METHODS.items() if v == args.mode)
            run = experiment.fork(args.from_run, mode)
            config = exp.load_json(run / "config.json")
            config["repair"]["filter_by_target_provision_reachability"] = args.filter_by_target_provision_reachability
            config.setdefault("execution", {})["replay_trace_mode"] = args.replay_trace_mode
            config["execution"]["replay_jobs"] = args.replay_jobs
            if args.timeout is not None:
                _set_agent_timeout(config, args.timeout)
            exp.atomic_json(run / "config.json", config)
            state = (exp.load_json(run / "state.json") if args.prepare_only
                     else logged(run, lambda: complete_repair(run)))
        elif args.subcommand in {"resume", "drive"}:
            run = args.run_directory.resolve()
            if args.replay_jobs is not None or args.timeout is not None:
                config = exp.load_json(run / "config.json")
                if args.replay_jobs is not None:
                    config.setdefault("execution", {})["replay_jobs"] = args.replay_jobs
                if args.timeout is not None:
                    _set_agent_timeout(config, args.timeout)
                exp.atomic_json(run / "config.json", config)
            state = logged(run, lambda: complete_repair(run))
        elif args.subcommand == "pair-summary":
            print(json.dumps(pair_summary(args.initial_run), indent=2))
            return 0
        else:
            from rsa_formalizer.stages.reasoning_structure_alignment.artifact_retention import prune_completed, restore
            result = (prune_completed(args.run_directory) if args.subcommand == "prune-artifacts"
                      else restore(args.run_directory, args.stage))
            print(json.dumps(result, indent=2))
            return 0
    except (agents.AgentConfigurationError, exp.RunnerError) as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps({"run_directory": str(run), "state": state}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
