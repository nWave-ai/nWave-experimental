"""`des parallel-safety-report` tells an ABSENT Slice Plan from an EMPTY one.

GDP-8 arity corollary: a feature-delta carrying no Slice Plan section at all is
a structural omission, and the rejection must SAY so — not report it as "the
scope names a row that is not declared-parallel (declared-parallel: [])", the
message a present-but-monolithic plan legitimately earns.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.parallel_safety_report import main


#: A Slice Plan that IS present and declares ZERO parallel rows (every row is
#: `depends-on`) — the case that used to be indistinguishable from an absent
#: section, since both yielded an empty declared-parallel set.
_PLAN_WITH_ZERO_PARALLEL_ROWS = (
    "## Wave: DISCUSS / [REF] Slice Plan\n\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|---|---|---|---|---|\n"
    "| slice-01 | Ship the reader | pending | depends-on slice-00 | Base first |\n"
    "| slice-02 | Ship the writer | pending | depends-on slice-01 | Reader first |\n"
)


def _run(tmp_path: Path, content: str) -> int:
    target = tmp_path / "feature-delta.md"
    target.write_text(content, encoding="utf-8")
    return main(
        [
            "--feature-delta",
            str(target),
            "--repo",
            str(tmp_path),
            "--scope",
            "slice-01=src/a.py",
            "--scope",
            "slice-02=src/b.py",
        ]
    )


def test_absent_slice_plan_is_rejected_as_a_structural_omission(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = _run(tmp_path, "# feature-delta\n\nProse only; no Slice Plan.\n")

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["event"] == "ParallelSafetyInputRejected"
    reason = payload["reasons"][0]
    assert "NO '## Wave: DISCUSS / [REF] Slice Plan' section" in reason, (
        "the rejection must name the missing section as the cause, so the "
        f"author is not sent hunting through --scope bindings; got {reason!r}"
    )


def test_present_slice_plan_declaring_no_parallel_row_keeps_the_scope_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = _run(tmp_path, _PLAN_WITH_ZERO_PARALLEL_ROWS)

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    reasons = " ".join(str(r) for r in payload["reasons"])
    assert "NOT a declared-parallel" in reasons
    assert "structural omission" not in reasons, (
        "a plan that IS present but declares zero parallel slices is valid; "
        f"it must not be reported as a missing section; got {reasons!r}"
    )
