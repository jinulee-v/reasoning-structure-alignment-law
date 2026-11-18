"""Console logging and paired-result reporting for the CLI entry points."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from rsa_formalizer.stages import utils as exp
from rsa_formalizer.stages.reasoning_structure_alignment import experiment


def pair_summary(shared: Path) -> dict:
    shared = shared.resolve()
    forks = exp.load_json(shared / "forks.json")
    if set(forks) != set(experiment.MODES):
        raise exp.RunnerError("both experiment forks are required")
    output = {"shared_run": str(shared), "branches": {}}
    source = exp.load_json(shared / "config.json")
    checkpoint = exp.load_json(shared / "provision_repair/checkpoint.json")
    parent_result = exp.load_json(shared / "initial/validation/results.json")
    expected_total = parent_result["summary"]["total"]
    for mode, path in forks.items():
        run = Path(path)
        config = exp.load_json(run / "config.json")
        state = exp.load_json(run / "state.json")
        if config.get("validation_suite_sha256") != source.get("validation_suite_sha256"):
            raise exp.RunnerError(f"validation suite differs in {run}")
        if config.get("shared_checkpoint") != checkpoint:
            raise exp.RunnerError(f"shared evidence differs in {run}")
        if (exp.sha256_file(run / "provision_repair/tests.json") != checkpoint["tests_sha256"]
                or exp.sha256_file(run / "provision_repair/computation_oracles.json")
                != checkpoint["computation_oracles_sha256"]):
            raise exp.RunnerError(f"fork evidence changed in {run}")
        output["branches"][mode] = {
            "run": str(run), "status": state.get("status"),
            "validation": state.get("verification_summary"),
            "accepted_cases": (exp.load_json(run / "provision_repair/summary.json").get("accepted_cases")
                               if (run / "provision_repair/summary.json").is_file() else None),
        }
    scores = [output["branches"][mode]["validation"] for mode in experiment.MODES]
    if any(score and score.get("total") != expected_total for score in scores):
        raise exp.RunnerError("paired validation case counts differ from the initial run")
    if all(score and score.get("total") == expected_total for score in scores):
        output["held_out_pass_difference"] = scores[0]["passed"] - scores[1]["passed"]
    output["held_out_total"] = expected_total
    exp.atomic_json(shared / "paired_results.json", output)
    return output


class _Tee:
    def __init__(self, console, log):
        self.console, self.log = console, log

    def write(self, value):
        self.console.write(value)
        self.log.write(value)
        self.log.flush()
        return len(value)

    def flush(self):
        self.console.flush()
        self.log.flush()


def logged(run: Path, action):
    """Append driver output while retaining the interactive console stream."""
    from contextlib import redirect_stdout, redirect_stderr
    with (run / "run.log").open("a", encoding="utf-8") as log:
        with redirect_stdout(_Tee(sys.stdout, log)), redirect_stderr(_Tee(sys.stderr, log)):
            print(f"[{exp.utc_now()}] Resuming {run.name}", flush=True)
            result = action()
            print(json.dumps(result, indent=2), flush=True)
            return result
