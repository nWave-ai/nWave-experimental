"""The bypass detector must be able to RUN, not merely exist.

Marked @pytest.mark.fast_gate so it runs at every commit.

WHY THIS TEST EXISTS, measured rather than imagined: on 2026-02-06 the module
`des.adapters.driven.logging.audit_logger` was deleted. The post-commit bypass
detector imported it inside a broad `try` whose `except Exception: return 0`
swallowed the ModuleNotFoundError, so for FIVE MONTHS the hook exited 0, wrote
nothing, and recorded not one bypass -- while `pre-commit run` kept printing
"nWave Bypass Detector ... Passed". Nobody noticed, because a guard that cannot
fire does not fail loudly: it reports success.

The general rule this pins, and it is not specific to this hook: a check whose
failure is indistinguishable from its success is not a check. The only way to
know a guard still works is for something to verify it can still EXECUTE. An
import-only assertion would not have been enough either -- a changed call
signature imports fine and still explodes at the call site -- so this drives the
detector end to end in a throwaway repo and asserts it DISCRIMINATES.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


_DETECTOR = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "hooks"
    / "nwave-bypass-detector.py"
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "probe"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "probe"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    return repo


def _run(repo: Path) -> int:
    return subprocess.run(
        [sys.executable, str(_DETECTOR)], cwd=repo, capture_output=True, check=False
    ).returncode


@pytest.mark.fast_gate
def test_the_bypass_detector_still_discriminates_a_bypass_from_a_verified_commit(
    tmp_path: Path,
) -> None:
    """Absent marker -> recorded as a bypass; present marker -> not, and consumed.

    Both legs matter. Only the first would pass for a detector that flags
    everything; only the second would pass for one that flags nothing. Together
    they fail for a detector that cannot run at all -- which is the state this
    guard spent five months in.
    """
    repo = _repo(tmp_path)
    log = repo / ".git" / "hooks" / "pre-commit.log"

    assert _run(repo) == 0, (
        "the detector must never block a commit, even when it errors"
    )
    assert log.exists() and log.read_text(encoding="utf-8").strip(), (
        "WHAT: with NO pre-commit marker the detector recorded no bypass. "
        "WHY: an absent marker is the bypass signal, and a detector that cannot "
        "reach its own sink reports success while observing nothing -- exactly "
        "the five-month outage this test exists to prevent. "
        f"HOW: run {_DETECTOR.name} by hand in a scratch repo and read the "
        "traceback its broad `except` is hiding."
    )

    log.unlink()
    marker = repo / ".git" / ".nwave-precommit-ran"
    marker.write_text("", encoding="utf-8")

    assert _run(repo) == 0
    assert not log.exists() or not log.read_text(encoding="utf-8").strip(), (
        "WHAT: a commit whose pre-commit marker was PRESENT was recorded as a "
        "bypass. WHY: a detector that flags every commit carries no information, "
        "and the reviewer stops reading the log. "
        "HOW: check the marker is read before, not after, anything that can raise."
    )
    assert not marker.exists(), (
        "WHAT: the pre-commit marker was not consumed. "
        "WHY: a stale marker makes the NEXT --no-verify commit read as verified "
        "-- a false negative, which is worse than the outage it replaces, "
        "because it looks like evidence. "
        "HOW: consume the marker before any fallible work, never after."
    )
