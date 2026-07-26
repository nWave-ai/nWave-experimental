"""Codex users receive one bounded continued-work capsule only when due."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from des.application.codex_standing_loop_driver import (
    CodexSessionStartLoopDriver,
    ContinuedWorkRequest,
)


@dataclass(frozen=True)
class _Clock:
    now: datetime


def _request(project_root: Path, *, due_at: datetime) -> ContinuedWorkRequest:
    return ContinuedWorkRequest(
        project_root=project_root,
        outcome="inspect the declared work and return one bounded next action",
        due_at=due_at,
        max_tokens=1200,
        max_wall_seconds=30,
    )


def test_session_start_gives_a_codex_user_one_bounded_due_work_capsule(
    tmp_path: Path,
) -> None:
    """A due request is made actionable once, with its explicit budget."""
    now = datetime(2026, 7, 26, tzinfo=UTC)
    driver = CodexSessionStartLoopDriver(clock=_Clock(now))

    capsule = driver.session_started(_request(tmp_path, due_at=now))

    assert capsule is not None
    assert (
        capsule.outcome
        == "inspect the declared work and return one bounded next action"
    )
    assert capsule.max_tokens == 1200
    assert capsule.max_wall_seconds == 30


def test_session_start_does_not_claim_work_before_it_is_due(tmp_path: Path) -> None:
    """A user is not interrupted or charged for work that is not yet due."""
    now = datetime(2026, 7, 26, tzinfo=UTC)
    driver = CodexSessionStartLoopDriver(clock=_Clock(now))

    capsule = driver.session_started(
        _request(tmp_path, due_at=now + timedelta(minutes=30))
    )

    assert capsule is None
