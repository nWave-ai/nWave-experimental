"""``des loop arm`` must refuse an implicit scope, not silently default it.

The installed Claude/Codex project-guidance fragment
(``nWave/templates/loop-consent-fragment.md``) promises the operator
"explicit repo, scope, mode, budget" before a standing loop is armed. Prior
to this test, ``--outcome`` (the runtime's name for "scope") was optional
and silently fell back to a generic placeholder string when omitted, so an
``arm`` request could reach ``status: ok`` without the caller ever stating
what the loop was scoped to do -- contradicting the consent promise.
"""

from __future__ import annotations

from pathlib import Path

from des.cli.loop import main


def _run(tmp_path: Path, *extra: str) -> tuple[int, str]:
    import io
    import sys

    captured = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured
    try:
        exit_code = main(
            [
                "arm",
                "--project",
                str(tmp_path),
                "--loop",
                "standing",
                "--max-tokens",
                "100",
                "--max-wall-seconds",
                "10",
                "--idempotency-key",
                "test-key",
                "--dry-run",
                "--format",
                "json",
                *extra,
            ]
        )
    finally:
        sys.stdout = original_stdout
    return exit_code, captured.getvalue()


def test_arm_without_outcome_is_refused_not_defaulted(tmp_path: Path) -> None:
    exit_code, output = _run(tmp_path)

    assert exit_code == 2
    assert '"status": "refused"' in output
    assert '"code": "INVALID_LIMIT"' in output
    assert "--outcome" in output


def test_arm_with_explicit_outcome_is_planned(tmp_path: Path) -> None:
    exit_code, output = _run(
        tmp_path, "--outcome", "run one bounded consolidation tick"
    )

    assert exit_code == 0
    assert '"status": "ok"' in output
    assert '"event_type": "LOOP_ARM_PLANNED"' in output
