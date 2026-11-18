# RSA (Reasoning Structure Alignment) formalizer using Catala inputs directly

## Initial SARA run

Use Python 3.10 or newer (this checkout uses a Python 3.12 `.venv`).
The full pipeline needs the Python packages, the Catala validation compiler,
the BOBCat compiler and patched Z3 runtime, Apptainer, and a container image.
Importing the entry points or running `--help` alone does not verify these tools.

Authenticate with `codex login` using a ChatGPT subscription. Trace generation
and information extraction reuse that login directly. For Claude subscription
calls, define `CLAUDE_CODE_OAUTH_TOKEN` in the repository-root `.env`
(see `.env.example`).
`.env`, `.venv`, `.toolchain`, and `runs` are gitignored.

Check all full-run prerequisites without starting a model call:

```bash
bash rsa_formalizer/run.sh --check
```

Start the initial run, selecting a model available to your account:

```bash
bash rsa_formalizer/run.sh --agent-model MODEL
```

The launcher uses SARA, Codex, the repository-local Python environment and
Apptainer image, and initial formalization, validation, and shared test generation. Additional
`start` arguments are forwarded to `main_initial.py`; for example, add
`--reasoning-trace-model MODEL` to select a separate trace model.
Information extraction defaults to the model shown by `start --help`.
Progress and durable outputs are saved under `runs/<run-id>/`.
Resume an interrupted run with:

```bash
bash rsa_formalizer/run.sh resume runs/RUN_ID
```

To rebuild dependencies on another checkout:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r rsa_formalizer/requirements.txt
bash install_toolchain.sh swipl,ocaml,catala,bobcat-deps,claude-code
git submodule update --init --recursive
.venv/bin/python bobcat_scripts/build.py
```

To install just Claude Code, run `bash install_toolchain.sh claude-code`.
This downloads the pinned native binary, verifies its published SHA-256, and
installs it under `.toolchain/claude-code/`, with a launcher at
`.toolchain/bin/claude`. The agent adapter discovers this local installation
automatically. Define `CLAUDE_CODE_OAUTH_TOKEN` in `.env` to authenticate it.
Reasoning and information extraction now use subscription credentials for
direct inference: `codex` reads the same `$CODEX_HOME/auth.json` (default
`~/.codex/auth.json`) as the Codex agent, and `claude-subscription` uses
`CLAUDE_CODE_OAUTH_TOKEN` from the environment or `.env`. Run `codex login`
with a ChatGPT account to provision Codex credentials. Expired Codex OAuth
tokens are refreshed and atomically persisted with owner-only permissions;
pipeline threads and processes serialize refreshes. Avoid logging in or
refreshing credentials in an external CLI while pipeline requests are active.

The legacy provider names `openai` and `anthropic` select these subscription
transports too, including when resuming existing configurations. They no
longer read `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `api_key_env`. There is
no API-key billing fallback. Custom `base_url` values are rejected for these
providers; other OpenAI-compatible providers retain their configured endpoint
and API-key behavior. `claude-code` still selects the existing CLI backend.
The formalization coding-agent adapters retain their existing behavior.

Codex calls use the Codex Responses endpoint directly, without the CLI agent
loop or repository context. They preserve strict JSON schemas, response IDs,
reasoning items, and token usage. Set `reasoning_effort` in the provider's
settings to control it explicitly; otherwise the backend chooses its default.
Codex streaming is collected into a completed response; failed, incomplete,
or interrupted streams fail the call. Prompt caching uses a stable prefix
and `prompt_cache_key` with automatic backend caching. Public API explicit
cache TTLs, breakpoints, and comparison diagnostics are not sent.

Claude calls send the existing Claude Code OAuth token as a bearer credential
to the Messages endpoint, preserving JSON schemas and raw thinking/usage
blocks. Anthropic may restrict direct subscription OAuth inference to Claude
Code; rejected requests fail explicitly. OAuth requests require the first
system block `You are Claude Code, Anthropic's official CLI for Claude.`;
this adapter includes that block before any configured instructions, with
the OAuth and Claude Code beta headers. This prompt difference means Claude
subscription inference is not identical to an API-key request. See upstream
issues [#87420](https://github.com/anthropics/claude-code/issues/87420) and
[#103731](https://github.com/anthropics/claude-code/issues/103731).
Renew an expired token through Claude Code and update
`CLAUDE_CODE_OAUTH_TOKEN`; this adapter has no Claude refresh token.

For example, use `--reasoning-trace-provider codex` and
`--extraction-provider codex` (the extraction default), or choose
`claude-subscription` for either stage with an appropriate Claude model.
To use it for the initial run:

```bash
bash rsa_formalizer/run.sh --agent claude-code --agent-provider anthropic \
  --agent-model MODEL --reasoning-trace-provider openai --reasoning-trace-model TRACE_MODEL
```

The toolchain build can take approximately two hours. It requires network
access, a C/C++ compiler, CMake, and `patch`. The container requires Apptainer
and unprivileged user namespaces. With a system Apptainer installation:

```bash
apptainer build --fakeroot .toolchain/rsa.sif rsa_formalizer/Apptainer.def
```

This checkout also supports the official relocatable Apptainer installation
at `.toolchain/apptainer-relocatable/bin/apptainer`. On hosts with `/etc/subuid`
entries but no `newuidmap`, build using its root-mapped fallback:

```bash
mkdir -p .toolchain/tmp
APPTAINER_CACHEDIR="$PWD/.toolchain/apptainer-cache" \
APPTAINER_TMPDIR="$PWD/.toolchain/tmp" \
  .toolchain/apptainer-relocatable/bin/apptainer build --fakeroot --ignore-subuid \
  .toolchain/rsa.sif rsa_formalizer/Apptainer.def
```

## Direct invocation

Run the formalizer with:

```bash
python3 -m rsa_formalizer.main_initial start \
  --dataset data/raw/sara \
  --agent codex --agent-provider openai --agent-model MODEL --image IMAGE
```

Use `python3 -m rsa_formalizer.main_initial start --help` for all arguments.

Compiled case replay runs up to four cases concurrently by default. Set
`execution.replay_jobs` in the run config, or pass `--replay-jobs N` to
`main_repair start` or `main_repair resume`; use `1` for serial replay.
Workers share bridges built before replay, write separate case files, and return
results in input order. Each worker holds one case's trace in memory, so reduce
the worker count for large traces. An already running replay keeps its current
worker count; the setting takes effect on the next invocation.

Coding agents have no wall-clock limit by default; `runtime.timeout_seconds`
only bounds tools and validation. Repair `start` and `resume` accept
`--timeout SECONDS` to explicitly set an agent deadline. Use `--timeout 0`
to remove an explicitly configured agent limit. This saves
`runtime.agent_timeout_seconds: null`; compiler, replay-case, and validation
timeouts remain bounded by their existing settings. Resuming preserves the
workspace and archives the interrupted agent's logs before starting a new session.

RSA and final-answer baseline repairs require `case_diagnoses.json` containing
exactly the remaining non-aligned cases from the latest replay of the submitted
source, including newly introduced discrepancies. RSA also includes
intermediate-value mismatches; baseline reports use final answers only.
Each entry has `case_id`, a one-sentence
`diagnosis`, and `classification` equal to `Catala wrong`, `LLM wrong`,
`Both wrong`, or `Unresolved`, concerning the current program and frozen LLM.
The agent writes `/rsa/submission-check/case_diagnoses.json`; this file is not
required before replay. Submission validates format, unique IDs, exact coverage
of the latest remaining-case list, and that the current workspace matches the
replayed source snapshot. Further source edits require another replay. Resolved
cases and omitted remaining cases are rejected; an empty list is accepted only
when the replay has no remaining discrepancies. The report is saved under
`provision_repair/session/agent/case_diagnoses.json`, alongside
`case_diagnoses_replay.json` binding it to the replay and source hash. Validation
does not establish the legal correctness of the diagnoses. The initial feedback
index and original-baseline comparisons are not the final report's case list.
`/rsa/feedback/latest_replay.json` identifies the latest replay and its evidence
index, including when the latest request reused a cached source snapshot.

RSA candidate replay publishes `/rsa/feedback/replays/attempt-N/index.json`
through the existing read-only feedback mount. Its `reports` cover every frozen
case and `remaining_case_ids` includes final-answer and intermediate mismatches.
Each case has full structured inputs, baseline/current comparison, frozen LLM
reasoning and computation graph, alignment details, and the concrete Catala
trace. Replay responses include `evidence_index`; newly disagreeing cases have
the same evidence access as cases in the original feedback index.

This variant excludes `INPUT_VARIABLE_DESCRIPTION.json` from each staged input and workspace, does not generate or validate that file, and does not use it during natural-language extraction or generated-test auditing. Those steps use the Catala input JSON schema and Catala source. The final submission check still verifies the Catala program and workspace integrity.

Verification runs the protected Catala scopes in `data/catala_gold/sara/tests_catala/` with `clerk test --json`. The 97 SARA tax cases are generated deterministically from their original Prolog facts and claimed amounts with:

```bash
python3 -m prolog_to_catala.sara_fresh.export_catala_tests
```

The runner omits these oracle tests from the coding agent's workspace and stages them only for verification. Generated money-literal equality assertions are staged as strict lower and upper bounds, accepting an absolute difference of less than $1, matching the JSON evaluator. Other assertions remain exact. Protected source tests are unchanged, and the cache fingerprint records the tolerance policy. Results are written to each run's `validation/results.json`.

Money assertions in native Catala evaluation allow absolute error strictly less
than $1; an error of exactly $1 fails. Non-money assertions remain exact.

## Initial and repair phases

`main_initial.py start` formalizes the source, validates it on the protected suite,
and generates exactly three full-input attempts per XML-annotated provision.
For every valid input, it saves independent statute reasoning and an extracted
computation graph. It stops at `fork_ready`, before test selection or repair.
The initial validation, generation prompts, responses, snapshots, and usage stay
in this one run. An interrupted initial run resumes with
`main_initial.py resume RUN_DIRECTORY`.

Names use UTC and the coding-agent model:

```text
YYYYMMDD-HHMM-initial-MODEL-DATASET[-SUFFIX]
YYYYMMDD-HHMM-repair-reasoning-structure-alignment-MODEL-DATASET[-SUFFIX]
YYYYMMDD-HHMM-repair-baseline-final-answer-only-MODEL-DATASET[-SUFFIX]
```

Only initial creation accepts `--suffix`. Arbitrary `--run-id` values are rejected.
Each repair inherits the complete initial name, replacing only `initial` with
`repair-METHOD`. A second repair of the same method cannot overwrite an existing run;
create a separately suffixed initial experiment to compare another configuration.

CoT provider/model, reasoning concurrency, statute source, generation concurrency,
and graph extraction attempts belong to `main_initial.py`.
Repair selection, replay trace mode and repair timeout belong to `main_repair.py`.
The repair coding agent and CoT evidence are inherited from the initial run.

```bash
.venv/bin/python -m rsa_formalizer.main_initial start \
  --dataset sara --agent codex --agent-provider openai --agent-model MODEL \
  --image .toolchain/rsa.sif --suffix experiment-1 \
  --reasoning-trace-model COT_MODEL --generation-jobs 4

.venv/bin/python -m rsa_formalizer.main_repair start \
  --from-run runs/INITIAL_RUN --mode reasoning-structure-alignment
.venv/bin/python -m rsa_formalizer.main_repair start \
  --from-run runs/INITIAL_RUN --mode baseline-final-answer-only
.venv/bin/python -m rsa_formalizer.main_repair pair-summary runs/INITIAL_RUN
```

Both entry points offer `start --prepare-only` to create a run without model calls.
`main_repair.py resume RUN_DIRECTORY` continues a repair. Each run contains a
`run.sh` targeting its phase. The launcher also accepts
`bash rsa_formalizer/run.sh repair start --from-run runs/INITIAL_RUN --mode METHOD`.
`main_initial.py` and `main_repair.py` parse commands and configure their runs.
`pipeline.py` owns phase orchestration, durable stage dispatch, and execution loops.
Console logging and paired-result reporting live in `utils/cli_support.py`, naming
in `utils/run_names.py`, and the container replay client in `utils/replay_candidate.py`.
Run creation lives in `stages/utils/run_state.py`; there is no separate `runner.py`.

The RSA method retains all executable generated cases by default. Target graph
reachability is recorded as diagnostic metadata. Use
`--filter-by-target-provision-reachability` to opt into rejecting complete graphs
that omit the target or disconnect it from the final answer. Inconclusive
extractions are retained. RSA repair reports include final-answer failures and
intermediate value divergences; attribution-only differences do not independently
trigger repair. Oracle-error rejections require structured input evidence,
context-specific values and calculations, the governing source provision, and
the precise incorrect reasoning step. Unresolved grounding or mappings remain
explicitly unresolved. The final-answer baseline compares only final answers.
RSA repair guidance requires entity deduplication with `W.same_entity` before
dependency or child-qualification checks over expanded claimant lists. This
preserves distinct claimants while avoiding repeated calls and inflated traces;
financial events and their multiplicities remain separate.
Both exclude invalid inputs
and cases Catala cannot execute, then repair independently and validate against
the same protected native Catala suite.

Each repair preserves the initial records, frozen tests, and inherited usage.
`usage.jsonl` includes the shared physical call IDs: deduplicate `usage_id` when
summing costs across branches. `run.log` appends the repair driver output to the
inherited initial log. `pair-summary` checks frozen evidence and suite hashes,
then reports the held-out pass difference.

RSA and final-answer baseline repairs also retain host-only records under
`private_submissions/submission-NNNN/` for every candidate replay request,
submission check, and agent exit. Each record preserves an immutable source
snapshot, held-out validation results (or a private scoring error), the agent log
prefix, available cumulative token counts, and Codex session rollouts when
available. Identical repeated submissions receive separate records even when
public replay is cached. `private_submissions/index.json` lists their scores.
These records are never mounted into the agent container or included in tool
responses; scoring uses private state and cannot complete the live repair stage.
They are retained after normal artifact pruning.

Completed repair runs automatically remove bulky reproducible replay artifacts:
symbolic case trees, compiled replay projects, comparison caches, and copied
Catala traces in feedback. They retain the frozen inputs, input schemas, every
Catala snapshot, reports, candidate review verdicts, diff, and validation score.
`provision_repair/artifact_retention.json` records the retained source hashes and
the number of bytes removed. To regenerate a stage's symbolic replay, comparison,
and feedback trace copies, run:

```bash
.venv/bin/python -m rsa_formalizer.main_repair restore-artifacts runs/RUN_ID --stage analysis
.venv/bin/python -m rsa_formalizer.main_repair restore-artifacts runs/RUN_ID --stage evaluation
.venv/bin/python -m rsa_formalizer.main_repair restore-artifacts runs/RUN_ID --stage attempt-1
```

`prune-artifacts runs/RUN_ID` reapplies cleanup to a completed run, including
after a restoration. Restoration checks the frozen input hashes and verifies
the regenerated answer-agreement count against the saved review.
