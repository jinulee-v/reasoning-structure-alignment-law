# RSA (Reasoning Structure Alignment) formalizer using Catala inputs directly

## Full SARA run

Use Python 3.10 or newer (this checkout uses a Python 3.12 `.venv`).
The full pipeline needs the Python packages, the Catala validation compiler,
the BOBCat compiler and patched Z3 runtime, Apptainer, and a container image.
Importing `main.py` or running `--help` alone does not verify these tools.

Put `OPENAI_API_KEY` in the repository-root `.env` (see `.env.example`),
and authenticate the coding agent with `codex login`. The API key is used by
trace generation and information extraction even when Codex uses a login.
`.env`, `.venv`, `.toolchain`, and `runs` are gitignored.

Check all full-run prerequisites without starting a paid model call:

```bash
bash rsa_formalizer/run.sh --check
```

Start the full run, selecting a model available to your account:

```bash
bash rsa_formalizer/run.sh --agent-model MODEL
```

The launcher uses SARA, Codex, the repository-local Python environment and
Apptainer image, and all default pipeline stages and repair budgets. Additional
`start` arguments are forwarded to `main.py`; for example, add
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
bash install_toolchain.sh swipl,ocaml,catala,bobcat-deps
git submodule update --init --recursive
.venv/bin/python bobcat_scripts/build.py
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
python3 -m rsa_formalizer.main start \
  --dataset data/raw/sara \
  --agent codex --agent-provider openai --agent-model MODEL --image IMAGE
```

Use `python3 -m rsa_formalizer.main start --help` for all arguments.

This variant excludes `INPUT_VARIABLE_DESCRIPTION.json` from each staged input and workspace, does not generate or validate that file, and does not use it during natural-language extraction or generated-test auditing. Those steps use the Catala input JSON schema and Catala source. The final submission check still verifies the Catala program and workspace integrity.

Verification runs the protected Catala scopes in `data/raw/sara/tests_catala/` with `clerk test --json`. The 97 SARA tax cases are generated deterministically from their original Prolog facts and claimed amounts with:

```bash
python3 -m prolog_to_catala.sara_fresh.export_catala_tests
```

The runner omits these oracle tests from the coding agent's workspace and stages them only for verification. Results are written to each run's `validation/results.json`.
