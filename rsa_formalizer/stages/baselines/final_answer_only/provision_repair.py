"""Final-answer-only repair mode over the shared generated cases."""

from __future__ import annotations

from pathlib import Path

from rsa_formalizer.stages.reasoning_structure_alignment import provision_repair as shared


AGENT_PROMPT = """Repair the Catala formalization using /rsa/feedback/index.json.
This is one nonrecursive repair pass across the project. Reports contain the
frozen full-input cases, the LLM's legal reasoning and final answer, and the
Catala final answer. Diagnose each disagreement from the supplied facts and
statutory provisions. A model answer is evidence, not ground truth; reject an
incorrect reasoning answer with its case ID and the first incorrect calculation.
Repair genuine Catala defects in the linked annotated blocks, with minimal
helper changes when necessary. Preserve prose, annotations, API contracts and
the frozen tests. Do not invent missing facts or run protected validation.
Follow the input contract's rules for missing values and defaults. Do not add
evidence-presence requirements solely because facts are absent.

After the final source edits, run replay and write a JSON list explaining ONLY
the remaining disagreements in the CURRENT repaired program. Use
/rsa/feedback/latest_replay.json and its evidence_index as the authority, not
the original /rsa/feedback/index.json or the initial Catala answers. The replay
index provides the current final answers, structured inputs, and frozen LLM
reasoning for every case, including newly disagreeing cases. Include exactly
the latest remaining_case_ids once each; exclude cases that are now aligned.
Explain each remaining discrepancy using the current program's answer and the
frozen reasoning. Rejected LLM answers and unresolved cases remain mismatches.
Save /rsa/submission-check/case_diagnoses.json (outside /workspace). Each entry
must contain exactly:
  {"case_id": "<exact case ID>",
   "diagnosis": "<one nonempty sentence of at most 600 characters>",
   "classification": "Catala wrong | LLM wrong | Both wrong | Unresolved"}
Use a single line for each diagnosis. An empty list is valid only when replay
has no remaining cases. No report is required before calling replay. After any
further source edit, replay again before finalizing the report. Submission
rejects stale snapshots, omitted remaining cases, and cases that are now aligned;
it checks coverage and format, not the legal correctness of the diagnoses.

Preserve the submitted file set throughout the repair: do not create, delete,
or rename project files under /workspace. Edit existing writable Catala files
for source changes. Put all scratch scripts, notes, logs, captured tool responses,
and other temporary files under /tmp, not /workspace. The only new workspace
files allowed are compiler-generated artifacts under _build/ and _targets/
from the required Clerk commands; the runner removes those before integrity
checks. Do not use those directories to store your own temporary files.

Run `clerk start` and `clerk typecheck .` before and after edits. After editing,
run `python3 /rsa/replay_candidate.py` and inspect changed final answers. If
replay fails to build, fix the build and retry. Correct demonstrated defects
and replay updated source as needed; there is no limit on replay calls or repair
iterations. Verify the final source before submission. Finish with
`/rsa/check_submission.sh`. Describe edits and unresolved case IDs. The runner
will validate the candidate afterward; there is no recursive repair pass.
"""


def run(run_directory: Path, config: dict, state: dict) -> dict:
    return shared.run(run_directory, config, state)
