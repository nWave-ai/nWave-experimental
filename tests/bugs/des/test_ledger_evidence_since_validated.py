"""Regression (GDP-6 silent-undercount / GDP-3 self-explaining): `des
verify-slice-ledger-evidence --report --since <bad>` must REJECT a malformed
``--since`` LOUD (exit 2 + a what/why/how diagnostic), never silently emit an
all-zero report at exit 0.

Charter: ``docs/product/expectations/fix-ledger-evidence-since-validated/
a-malformed-since-fails-loud-not-a-silent-zero-report.md``.

Found in ``src/des/cli/verify_slice_ledger_evidence.py``:
  * ``_build_parser`` (~:76) -- ``--since`` is ``required=True`` but its VALUE
    is never validated as a real ``YYYY-MM-DD`` calendar date; argparse only
    checks the flag is present, not that its value parses.
  * ``_count_by_event_since`` (~:167) -- compares ``date_prefix >= since``
    LEXICOGRAPHICALLY. A malformed ``since`` (``"garbage"``, or the
    impossible-but-shaped ``"2026-13-99"``) still participates in that string
    comparison; every event's real date-prefix sorts BELOW the garbage
    string (or the comparison is simply never true), so EVERY event is
    silently filtered out.
  * ``main`` (~:195) -- unconditionally returns ``0`` after emitting the
    JSON report; there is no path that returns ``2`` for a malformed
    ``--since``, even though the module docstring already declares
    ``2 = invalid date`` (line 51) -- the declared contract exists, the
    validation code implementing it does not.

The fix direction (charter, NOT implemented here): ``main()`` validates
``--since`` as a real ``YYYY-MM-DD`` calendar date (e.g. via
``datetime.strptime(value, "%Y-%m-%d")``) BEFORE aggregating; on failure,
emit a diagnostic naming WHAT (the ``--since`` value is not a valid date),
WHY (the report would silently drop every event), and HOW (pass a real
``YYYY-MM-DD``, e.g. ``2026-07-01``), then return 2 -- never proceeding to
build the all-zero report.

CRITICAL CONSTRAINT (preserved, do NOT change): the valid path is
unchanged -- a real ``--since`` still emits the JSON report (the correct
non-zero counts for events on/after that date) at exit 0.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.verify_slice_ledger_evidence.main()`` CLI driver, captured
via ``capsys`` -- mirrors the sibling regression ATs
``tests/bugs/des/test_slice_at_completeness_incomplete_names_how.py`` and
``tests/bugs/des/test_run_slice_ats_fail_names_how.py`` (the GDP-3/GDP-6
pattern this one follows). The module's own freshness/dispatcher wrapper
only fires on the subprocess/dispatcher edge -- calling ``main()`` in-process
bypasses it, same as the sibling ATs.

Fixture: a real ``.nwave/des/logs/audit-1.log`` JSONL file seeded under a
``tmp_path`` target root, pointed to via the
``NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT`` env var (the module's own
test-harness contract, ``_resolve_target_root``) -- 2 real events, one
``SliceCommitVerified`` and one ``SpineBypassUsed``, both dated
``2026-07-08`` (today, per the charter's own example dates).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_slice_ledger_evidence import main as verify_ledger_main


_TARGET_ROOT_ENV = "NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT"

_SLICE_COMMIT_EVENT = (
    '{"event":"SliceCommitVerified","timestamp":"2026-07-08T10:00:00Z"}\n'
)
_BYPASS_USED_EVENT = '{"event":"SpineBypassUsed","timestamp":"2026-07-08T11:00:00Z"}\n'


def _seed_audit_log(target_root: Path) -> None:
    """Seed ``<target_root>/.nwave/des/logs/audit-1.log`` with 2 real events."""
    log_dir = target_root / ".nwave" / "des" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "audit-1.log").write_text(
        _SLICE_COMMIT_EVENT + _BYPASS_USED_EVENT, encoding="utf-8"
    )


def _run_report(
    argv: list[str],
    target_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, str, dict[str, object] | None]:
    """Drive the REAL ``des verify-slice-ledger-evidence`` CLI (``main()``)
    in-process, pointing the module's own target-root env var at
    ``target_root``. Returns ``(exit_code, combined_output, json_payload)``
    -- ``json_payload`` is ``None`` when stdout carries no JSON line (the
    exit-2 diagnostic path).
    """
    monkeypatch.setenv(_TARGET_ROOT_ENV, str(target_root))
    exit_code = verify_ledger_main(argv)
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    payload: dict[str, object] | None = None
    for line in combined.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
    return exit_code, combined, payload


# ===========================================================================
# POSITIVE AT -- active-RED today
# ===========================================================================


@pytest.mark.parametrize(
    "malformed_since",
    ["garbage", "2026-13-99"],
    ids=["non-date-string", "impossible-calendar-date"],
)
def test_malformed_since_is_rejected_loud_not_a_silent_zero_report(
    malformed_since: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A malformed ``--since`` (a non-date string, or an impossible-but-shaped
    calendar date) must be REJECTED LOUD -- exit 2, never a silent exit-0
    all-zero report. This is RED today: ``main()`` unconditionally returns 0
    after building the report; ``_count_by_event_since`` silently drops every
    event because the lexicographic comparison against the garbage
    ``since`` string never matches (semantic AssertionError on the exit
    code / silent-zero, not a crash -- RED for the right reason).
    """
    _seed_audit_log(tmp_path)

    exit_code, combined, payload = _run_report(
        ["--report", "--since", malformed_since], tmp_path, monkeypatch, capsys
    )

    assert exit_code == 2, (
        "a malformed --since must be rejected LOUD (exit 2), never silently "
        f"accepted -- got exit_code={exit_code}; output={combined!r}; "
        f"payload={payload!r}"
    )

    # The silent-undercount signature: today's code proceeds to emit an
    # all-zero report at exit 0 instead of rejecting. Guard against that
    # exact failure shape explicitly, not just the exit code.
    if payload is not None:
        assert not (
            payload.get("slice_commits_verified") == 0
            and payload.get("bypasses_used") == 0
        ), (
            "a malformed --since must never fall through to an all-zero "
            f"report: payload={payload!r}"
        )

    combined_lower = combined.lower()
    assert malformed_since.lower() in combined_lower or "since" in combined_lower, (
        "the diagnostic must name WHAT failed (the invalid --since value) -- "
        f"got output={combined!r}"
    )
    assert "yyyy-mm-dd" in combined_lower or "2026-07-01" in combined_lower, (
        "the diagnostic must name HOW to fix it (a real YYYY-MM-DD date, "
        f"e.g. an example) -- got output={combined!r}"
    )


# ===========================================================================
# NEGATIVE AT -- control, green now AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_valid_since_still_emits_the_correct_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A real ``YYYY-MM-DD`` ``--since`` is unaffected by the fix -- the
    aggregator still emits the JSON report at exit 0 with the correct
    non-zero counts for events on/after that date. Must stay green both
    BEFORE and AFTER the fix (no false rejection, no undercount introduced
    by tightening the validation).
    """
    _seed_audit_log(tmp_path)

    exit_code, combined, payload = _run_report(
        ["--report", "--since", "2026-07-01"], tmp_path, monkeypatch, capsys
    )

    assert exit_code == 0, (
        "a valid --since must still clear (exit 0) -- got "
        f"exit_code={exit_code}; output={combined!r}"
    )
    assert payload is not None, f"expected a JSON report line, got: {combined!r}"
    assert payload.get("since") == "2026-07-01", payload
    assert payload.get("slice_commits_verified") == 1, payload
    assert payload.get("bypasses_used") == 1, payload
