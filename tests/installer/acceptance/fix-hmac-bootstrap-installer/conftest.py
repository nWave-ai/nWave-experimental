"""pytest-bdd configuration for the fix-hmac-bootstrap-installer AT set.

Walking-skeleton slice (slice-01): a fresh `install_nwave.py` subprocess
auto-provisions the per-project HMAC reviewer signing key. The driving port
is the real installer CLI invoked as a Python subprocess against a tmp_path
target; the only driven ports are the real filesystem (tmp_path) and the
`NWAVE_REVIEWER_SIGNING_KEY` environment variable.

The conftest is placed at the feature root (sibling of the .feature file)
rather than under steps/ — this mirrors the codex-empirical-e2e-support
precedent and avoids a pytest plugin-name collision with sibling features
that also carry a steps/conftest.py.

RED-for-the-right-reason: there is no production scaffold to write — the
`ReviewerSigningPlugin` and the install pipeline are already shipped. The
acceptance gap is the end-to-end SUBPROCESS seam (install_nwave.py →
.nwave/secrets/reviewer-signing.key → operator-observable surface) that has
no test today. Slice-01 ATs fail with AssertionError because the
composition root's assertions exercise the real install pipeline AND assert
the credibility-blocker postcondition (the key surface is operator-visible
without prior knowledge of the env var) — the seam either holds or it
doesn't.
"""

from __future__ import annotations

import os

import pytest


_SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"


@pytest.fixture(autouse=True)
def _isolate_signing_key_env():
    """Restore NWAVE_REVIEWER_SIGNING_KEY around every test in this suite.

    The composition's `set_env_signing_key` mutates `os.environ` to exercise
    the operator-override path. Without this autouse fixture the var leaks
    into subsequent tests (cross-suite pollution observed 2026-05-24:
    `tests/scripts/cli/atdd_pure_at_review_verdict/` started reading the
    leaked fixture key and verdict-signature verification failed).
    Saves the pre-test value, lets the test run, then restores or unsets.
    """
    sentinel = object()
    saved = os.environ.get(_SIGNING_KEY_ENV, sentinel)
    try:
        yield
    finally:
        if saved is sentinel:
            os.environ.pop(_SIGNING_KEY_ENV, None)
        else:
            os.environ[_SIGNING_KEY_ENV] = saved  # type: ignore[arg-type]
