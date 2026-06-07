"""GOLDEN FIXTURE leaf — a fully-wired subcommand module (clean corpus).

This module imports cleanly AND exposes a callable ``main`` — exactly the
registration contract every real ``des`` subcommand module satisfies. The
clean fixture's registry points one row here; the gate MUST resolve it,
import it, and find the callable ``main`` (the precision half).
"""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    return 0
