"""Request fresh BOBCat cases and LLM traces for the active repair scope."""

from __future__ import annotations

import json
import os
import socket
import sys


def main() -> int:
    socket_path = os.environ.get("RTDF_SUBMISSION_CHECK_SOCKET")
    if not socket_path:
        sys.stderr.write("error: regeneration service is unavailable\n")
        return 2
    request = json.dumps({"command": "regenerate_scope_analysis"}).encode() + b"\n"
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(socket_path)
        client.sendall(request)
        chunks = []
        while chunk := client.recv(4096):
            chunks.append(chunk)
    finally:
        client.close()
    response = json.loads(b"".join(chunks))
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response.get("accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
