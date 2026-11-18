#!/usr/bin/env bash
set -euo pipefail

workspace=${1:-/workspace}
cd "$workspace"
clerk start --color=never >/dev/null
clerk typecheck . --color=never
if [[ -f sara.md || -f airline.md ]]; then
  # The evaluator needs a compiled API even when there are no local test scopes.
  clerk build ocaml/Api.cmo --color=never
fi
clerk test . --color=never

python3 - <<'PY'
import json
import os
import socket

socket_path = os.environ.get("RSA_SUBMISSION_CHECK_SOCKET", "")
if not socket_path:
    raise SystemExit("authoritative submission check is unavailable")
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    try:
        client.connect(socket_path)
        client.sendall(b"check\n")
        chunks = []
        while chunk := client.recv(4096):
            chunks.append(chunk)
    except OSError as error:
        raise SystemExit("authoritative submission check is unavailable") from error
try:
    response = json.loads(b"".join(chunks))
except (ValueError, UnicodeDecodeError) as error:
    raise SystemExit("authoritative submission check is unavailable") from error
if not response.get("accepted"):
    raise SystemExit(response.get("message") or "submission rejected")
if response.get("message"):
    print(response["message"])
print("submission accepted")
PY
