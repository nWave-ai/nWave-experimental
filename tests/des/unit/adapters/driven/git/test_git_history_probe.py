"""Unit tests for GitHistoryProbe's test-state lookup.

Regression coverage for techdebt.md
`failed-lookup-recorded-as-absence-git-history-probe-py`:
``_tests_green_at`` used to fold ANY non-zero ``git cat-file blob`` exit into
"tests are green" -- both genuine absence (the test-state file was never
committed) and a real git failure (corruption, permission denied). This
masked real errors as an established fact instead of surfacing them.

The fix distinguishes the two cases via the specific stderr git emits for a
genuinely-absent path/blob (``does not exist in``); any other non-zero exit
now surfaces as ``ShaVerdict.PROBE_ERROR``, never silently as GREEN.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from des.adapters.driven.git.git_history_probe import GitHistoryProbe, ShaVerdict


SHA = "deadbeef" * 5


def _completed(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr
    return result


def _probe() -> GitHistoryProbe:
    return GitHistoryProbe(Path("/repo"))


def _side_effect_for(
    cat_file_e: MagicMock, merge_base: MagicMock, cat_file_blob: MagicMock
):
    def _run(cmd, **_kwargs):
        if cmd[3:5] == ["cat-file", "-e"]:
            return cat_file_e
        if cmd[3] == "merge-base":
            return merge_base
        if cmd[3:5] == ["cat-file", "blob"]:
            return cat_file_blob
        raise AssertionError(f"unexpected git invocation: {cmd}")

    return _run


def test_genuinely_absent_test_state_file_is_green() -> None:
    """A commit that never recorded test-state is treated as green (unchanged)."""
    sha_exists = _completed(0)
    reachable = _completed(0)
    blob_absent = _completed(
        128, stderr=f"fatal: path '.nwave/step-test-state' does not exist in '{SHA}'\n"
    )
    with patch(
        "subprocess.run",
        side_effect=_side_effect_for(sha_exists, reachable, blob_absent),
    ):
        assert _probe().verify_sha(SHA) == ShaVerdict.GREEN


def test_genuine_git_failure_on_test_state_lookup_is_probe_error_not_green() -> None:
    """A real git failure (corruption/permission/etc) must NOT be recorded as green."""
    sha_exists = _completed(0)
    reachable = _completed(0)
    real_failure = _completed(128, stderr="fatal: loose object is corrupt\n")
    with patch(
        "subprocess.run",
        side_effect=_side_effect_for(sha_exists, reachable, real_failure),
    ):
        assert _probe().verify_sha(SHA) == ShaVerdict.PROBE_ERROR


def test_red_test_state_is_tests_red() -> None:
    sha_exists = _completed(0)
    reachable = _completed(0)
    red = _completed(0, stdout="red\n")
    with patch(
        "subprocess.run",
        side_effect=_side_effect_for(sha_exists, reachable, red),
    ):
        assert _probe().verify_sha(SHA) == ShaVerdict.TESTS_RED
