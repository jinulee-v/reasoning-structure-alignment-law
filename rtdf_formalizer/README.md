# RTDF formalizer using Catala inputs directly

Run the formalizer with:

```bash
python3 -m rtdf_formalizer.main start \
  --dataset data/raw/sara \
  --agent codex --agent-provider openai --agent-model MODEL --image IMAGE
```

Use `python3 -m rtdf_formalizer.main start --help` for all arguments.

This variant excludes `INPUT_VARIABLE_DESCRIPTION.json` from each staged input and workspace, does not generate or validate that file, and does not use it during natural-language extraction or generated-test auditing. Those steps use the Catala input JSON schema and Catala source. The final submission check still verifies the Catala program and workspace integrity.

Verification runs the protected Catala scopes in `data/raw/sara/tests_catala/` with `clerk test --json`. The 97 SARA tax cases are generated deterministically from their original Prolog facts and claimed amounts with:

```bash
python3 -m prolog_to_catala.sara_fresh.export_catala_tests
```

The runner omits these oracle tests from the coding agent's workspace and stages them only for verification. Results are written to each run's `validation/results.json`.
