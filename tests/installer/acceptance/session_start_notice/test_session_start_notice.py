"""Executable oracle: the route notice reaches the agent's own starting context.

Authority: docs/product/architecture/brief.md#Session Start Carries the Route
Notice Into the Agent's Own Context.

The observation itself lives in ``public_oracle.py`` beside this file, which
drives only published artefacts -- the real installer process and the hook
command it publishes into ``settings.json`` -- and imports no production
symbol. This module is the declared entry point: running it EXECUTES the
observation, so the exit status carries the verdict.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent))

from public_oracle import (
    EXPECTED_SEMANTIC_OBSERVATION,
    observe_session_start_notice,
)


def test_session_start_carries_the_route_notice_into_the_agents_context() -> None:
    """An agent beginning a session in a project where nWave is installed and
    enabled finds, in its own starting context, a short notice naming the
    available routes and what each one leaves behind -- observable by starting a
    session and reading the injected text, without opening any project file."""
    observed = observe_session_start_notice()

    assert observed["semantic"] == EXPECTED_SEMANTIC_OBSERVATION, (
        "WHAT: the session-start observation differed from the approved contract.\n"
        f"Observed: {observed['semantic']!r}\n"
        f"Expected: {EXPECTED_SEMANTIC_OBSERVATION!r}\n"
        f"Diagnostics: {observed['diagnostics']!r}\n"
        "WHY: the route notice must reach the agent's starting context through "
        "one matcher-less published registration, only for an enabled project, "
        "and in the single published wording.\n"
        "HOW: restore the published SessionStart registration and its read-only "
        "handler without adding a new port, flag or second notice wording."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
