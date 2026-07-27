"""Regression (defects.md: verify-slice-commit-e2-wrapper-divergence):
``verify_slice_commit_completeness._run_contract_gate`` composed its E2
subprocess (``des.cli.run_contract_gate``) with ``des_spawn(...,
capture_output=True, text=True)`` -- an IN-MEMORY pipe pair drained via
``Popen.communicate()``. Under a large feature-scoped suite this was
suspected (RCA hypothesis, not independently reproduced against the real
``run_contract_gate`` child -- see the pile row's investigation note) to be
the proximate cause of an observed divergence: the composed wrapper call
returned exit 1 while an identical hand-run of the SAME child returned exit
0.

Fix: the child's stdout/stderr now stream to real on-disk tempfiles
(``_spawn_streamed_to_tempfiles``) instead of an in-memory pipe -- nothing to
fill, full text read back only once the child has genuinely exited.

This file directly regression-tests the GENERAL hazard class the fix
removes: a child that writes an amount of combined stdout/stderr large
enough to fill (many times over) the OS pipe buffer (typically 64 KiB on
Linux) before exiting must still report its OWN true exit code and its OWN
complete output through the streamed wrapper -- never truncated, never
corrupted, never silently swapped for a different code. ``script=`` (a
test-only escape hatch on ``_spawn_streamed_to_tempfiles`` -- see its
docstring) drives the REAL streaming helper with a synthetic child, so this
is a genuine subprocess exercise of the production streaming mechanism, not
a mock of it.
"""

from __future__ import annotations

import pytest

from des.cli.verify_slice_commit_completeness import _spawn_streamed_to_tempfiles


# Comfortably larger than the 64 KiB Linux default pipe-buffer size on BOTH
# streams combined, so a naive in-memory-pipe implementation that mishandled
# concurrent stdout+stderr draining would be exercised well past that ceiling.
_LINE = "x" * 1000 + "\n"
_LINE_COUNT = 200  # ~200 KB per stream, ~400 KB combined


_BIG_OUTPUT_SCRIPT = (
    "import sys\n"
    f"for _ in range({_LINE_COUNT}):\n"
    f"    sys.stdout.write({_LINE!r})\n"
    f"    sys.stderr.write({_LINE!r})\n"
    "sys.exit(0)\n"
)

_BIG_OUTPUT_THEN_FAIL_SCRIPT = (
    "import sys\n"
    f"for _ in range({_LINE_COUNT}):\n"
    f"    sys.stdout.write({_LINE!r})\n"
    f"    sys.stderr.write({_LINE!r})\n"
    "sys.exit(7)\n"
)


def test_large_combined_output_child_reports_its_own_true_exit_code_zero() -> None:
    """A child that writes ~400KB combined stdout+stderr and exits 0 must be
    observed as exit 0 through the streamed wrapper -- the exact false-
    divergence class the defect described (a PASSING child observed as a
    refusal).
    """
    completed = _spawn_streamed_to_tempfiles(None, script=_BIG_OUTPUT_SCRIPT)

    assert completed.returncode == 0, (
        "a large-output child that genuinely exits 0 must be reported as "
        f"exit 0 through the streamed wrapper -- got {completed.returncode!r}"
    )


def test_large_combined_output_child_reports_its_own_true_nonzero_exit_code() -> None:
    """The mirror case: a large-output child that genuinely fails must be
    observed with its OWN exit code, not silently coerced to 0 or to some
    other value.
    """
    completed = _spawn_streamed_to_tempfiles(None, script=_BIG_OUTPUT_THEN_FAIL_SCRIPT)

    assert completed.returncode == 7, (
        "a large-output child's genuine non-zero exit code must survive the "
        f"streamed wrapper unchanged -- got {completed.returncode!r}"
    )


def test_large_combined_output_is_captured_complete_never_truncated() -> None:
    """Every line the child wrote to stdout AND stderr must come back intact
    -- streaming to a tempfile must never truncate or drop output the way a
    pipe-buffer-fill hazard would.
    """
    completed = _spawn_streamed_to_tempfiles(None, script=_BIG_OUTPUT_SCRIPT)

    stdout_lines = completed.stdout.splitlines()
    stderr_lines = completed.stderr.splitlines()
    assert len(stdout_lines) == _LINE_COUNT, (
        f"expected {_LINE_COUNT} stdout lines, got {len(stdout_lines)} -- "
        "output was truncated"
    )
    assert len(stderr_lines) == _LINE_COUNT, (
        f"expected {_LINE_COUNT} stderr lines, got {len(stderr_lines)} -- "
        "output was truncated"
    )
    assert all(line == "x" * 1000 for line in stdout_lines), (
        "captured stdout content was corrupted/interleaved"
    )
    assert all(line == "x" * 1000 for line in stderr_lines), (
        "captured stderr content was corrupted/interleaved"
    )


def test_small_output_still_works_additivity_guard() -> None:
    """Additivity guard: an ordinary small-output child (the common case --
    a normal feature-scoped suite run) must still round-trip correctly
    through the streamed wrapper.
    """
    completed = _spawn_streamed_to_tempfiles(
        None, script="import sys; sys.stdout.write('ok\\n'); sys.exit(0)"
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "ok"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
