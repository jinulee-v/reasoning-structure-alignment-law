#!/usr/bin/env bash
# Launch from any working directory with the repository-local dependencies.
set -euo pipefail
RSA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RSA_ROOT"
export PATH="$RSA_ROOT/.toolchain/apptainer-relocatable/bin:$RSA_ROOT/.toolchain/bin:$PATH"
export APPTAINER_CACHEDIR="$RSA_ROOT/.toolchain/apptainer-cache"
export APPTAINER_TMPDIR="$RSA_ROOT/.toolchain/tmp"
mkdir -p "$APPTAINER_TMPDIR"
if [[ ! -x .venv/bin/python ]]; then
    echo 'Missing .venv: create it with Python 3.10+ and install rsa_formalizer/requirements.txt.' >&2
    exit 1
fi
if [[ "${1:-}" == --check ]]; then
    shift
    exec .venv/bin/python -m rsa_formalizer.check_environment "$@"
fi
if [[ "${1:-}" == repair ]]; then
    shift
    exec .venv/bin/python -m rsa_formalizer.main_repair "$@"
fi
if [[ "${1:-}" == resume ]]; then
    exec .venv/bin/python rsa_formalizer/main_initial.py "$@"
fi
.venv/bin/python -m rsa_formalizer.check_environment
exec .venv/bin/python rsa_formalizer/main_initial.py start \
    --dataset data/raw/sara --agent codex --agent-provider openai \
    --image "$RSA_ROOT/.toolchain/rsa.sif" "$@"
