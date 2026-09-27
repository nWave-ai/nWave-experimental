#!/usr/bin/env python3
"""Make one bounded Jev decision and retain its typed result locally.

The caller supplies a small JSON request and chooses where the response is
written.  This program does not infer a decision, retry, or transmit files.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
_REQUIRED = {"state", "model", "questions"}


def _request_bytes(path: Path) -> bytes:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"request must be readable UTF-8 JSON: {error}") from error
    if not isinstance(payload, dict) or set(payload) != _REQUIRED:
        raise ValueError("request has exactly state, model, and questions")
    questions = payload["questions"]
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions is a non-empty object")
    for identifier, question in questions.items():
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("each question has a non-empty string identifier")
        if not isinstance(question, dict):
            raise ValueError(f"question {identifier!r} is an object")
        if not isinstance(question.get("type"), str) or not question["type"]:
            raise ValueError(f"question {identifier!r} has a non-empty type")
        if (
            not isinstance(question.get("instructions"), str)
            or not question["instructions"]
        ):
            raise ValueError(f"question {identifier!r} has non-empty instructions")
        criteria = question.get("criteria")
        if not isinstance(criteria, dict) or not criteria:
            raise ValueError(f"question {identifier!r} has non-empty criteria")
        if any(not isinstance(key, str) or not key for key in criteria):
            raise ValueError(f"question {identifier!r} criteria have non-empty keys")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()


def _write(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def _exit_code_for_http_error(status_code: int) -> int:
    """Map HTTP status to exit code: caller error, access, transient, or service."""
    if status_code in (400, 422):
        return 2  # Malformed request (caller schema)
    if status_code in (401, 403):
        return 5  # Access or configuration
    if status_code in (408, 429) or 500 <= status_code < 600:
        return 3  # Transient (retry later)
    return 4  # Other HTTP failure


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--endpoint", default=os.environ.get("TYPESAFE_BASE_URL", _ENDPOINT)
    )
    args = parser.parse_args(argv)

    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        print("typesafe: unavailable (TYPESAFE_API_KEY is absent)", file=sys.stderr)
        return 3
    try:
        body = _request_bytes(args.request)
    except ValueError as error:
        print(f"typesafe: invalid request ({error})", file=sys.stderr)
        return 2

    request = Request(
        args.endpoint,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            response_body = response.read()
    except HTTPError as error:
        exit_code = _exit_code_for_http_error(error.code)
        print(f"typesafe: HTTP {error.code}; no retry was attempted", file=sys.stderr)
        return exit_code
    except TimeoutError:
        print("typesafe: unavailable (network timeout)", file=sys.stderr)
        return 3
    except URLError as error:
        print(f"typesafe: unavailable ({error.reason})", file=sys.stderr)
        return 3
    try:
        decoded = json.loads(response_body)
    except json.JSONDecodeError:
        print("typesafe: invalid response JSON", file=sys.stderr)
        return 4
    if not isinstance(decoded, dict) or not isinstance(decoded.get("answers"), dict):
        print("typesafe: response has no typed answers", file=sys.stderr)
        return 4
    _write(args.output, response_body)
    print(f"typesafe: recorded {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
