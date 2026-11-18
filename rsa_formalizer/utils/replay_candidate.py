#!/usr/bin/env python3
"""Ask the host to replay frozen generated cases against the current workspace."""

import json
import os
import socket


path = os.environ.get("RSA_SUBMISSION_CHECK_SOCKET", "")
if not path:
    raise SystemExit("candidate replay service is unavailable")
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
    client.connect(path)
    client.sendall(b'{"command":"replay_candidate"}\n')
    chunks = []
    while chunk := client.recv(65536):
        chunks.append(chunk)
result = json.loads(b"".join(chunks))
if not result.get("accepted"):
    raise SystemExit(result.get("message") or "candidate replay failed")
print(json.dumps({key: value for key, value in result.items() if key != "accepted"}, indent=2))
