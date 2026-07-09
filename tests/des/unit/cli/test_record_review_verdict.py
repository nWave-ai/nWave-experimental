"""AT -- `des record-review-verdict` (WS-6 recovery gap for ad-hoc reviewers, #45).

Ad-hoc reviewers (`nw-agent-builder-reviewer` and other non-wave reviewers
dispatched for skill/prose changes) have NO ledger to persist their verdict --
the verdict lives ONLY in the reviewer's final chat message, so a reviewer
that dies before delivering leaves the verdict UNRECOVERABLE (observed 3x in
one session). The WS-6 recovery-fallback (verify-ledger-then-recover, shipped
in `nw-execute` Recovery Fallback) already covers the User-Examiner
(`.nwave/telemetry/examine/*.jsonl`, `des record-examine-verdict`) and the
wave reviewers (`record-at/discuss/design/devops-review`) but NOT ad-hoc
reviewers. `des record-review-verdict` closes the gap: a GENERAL producer that
appends a `ReviewVerdictRecorded` record to
`.nwave/telemetry/review/{feature_id}.jsonl`, mirroring
`des.cli.record_examine_verdict`'s ledger shape (event/JSONL-append/
timestamp) and `des.cli.at_review_verdict`'s reviewer/slice/verdict fields.

Pinned contract:
  - ledger: `.nwave/telemetry/review/{feature_id}.jsonl`
  - event: `ReviewVerdictRecorded`
  - fields: `event`, `feature_id`, `slice_id`, `reviewer_agent_id`, `verdict`
    (closed set: `APPROVED` / `NEEDS_REVISION` / `REJECTED`), `artifact`
    (free text -- what was reviewed), `timestamp`.
  - an unknown `--verdict` value is REJECTED (non-zero exit, no ledger write)
    -- never silently recorded.

RED reason (dispatcher-registry gap, not a collection/import error): the
`record-review-verdict` row does not exist yet in the dispatcher's `_REGISTRY`
(`src/des/cli/__main__.py`). Every test below drives the SAME single entry
point (`des.cli.__main__.main`, the production dispatcher -- Mandate 13
driving-port-only boundary), never a direct import of the not-yet-existing
`des.cli.record_review_verdict` producer module. Today `main(["record-review-
verdict", ...])` raises `SystemExit(2)` (argparse "invalid choice") --
`run_cli_in_process` maps that onto a plain non-zero exit code, so each
assertion below fails for a genuine semantic reason (wrong exit code / absent
ledger file), not a raw `SystemExit` or an `ImportError` escaping the test.

Driving surface: `tests/common.in_process_cli.run_cli_in_process` against the
production `des.cli.__main__.main` dispatcher, in-process (no interpreter
fork), under an isolated `tmp_path` repo (never the real `.nwave/telemetry/`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process


def _ledger_path(repo_root: Path, feature_id: str) -> Path:
    return repo_root / ".nwave" / "telemetry" / "review" / f"{feature_id}.jsonl"


def _read_ledger(repo_root: Path, feature_id: str) -> list[dict[str, object]]:
    path = _ledger_path(repo_root, feature_id)
    if not path.is_file():
        return []
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            records.append(json.loads(stripped))
    return records


def _record_review_verdict(
    repo_root: Path,
    *,
    feature_id: str,
    slice_id: str,
    reviewer_agent_id: str,
    verdict: str,
    artifact: str,
) -> tuple[int, str, str]:
    """Drive the real `des record-review-verdict` CLI in-process (no --repo-root:
    mirrors the production invocation, which resolves the repo root from cwd)."""
    argv = [
        "record-review-verdict",
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--reviewer-agent-id",
        reviewer_agent_id,
        "--verdict",
        verdict,
        "--artifact",
        artifact,
    ]
    return run_cli_in_process(argv, cwd=repo_root)


def test_records_an_approved_verdict_to_the_review_ledger(tmp_path: Path) -> None:
    """WS-6: an ad-hoc reviewer's APPROVED verdict is appended to the review
    ledger with every field the orchestrator needs to recover it."""
    exit_code, stdout, stderr = _record_review_verdict(
        tmp_path,
        feature_id="demo",
        slice_id="slice-01",
        reviewer_agent_id="nw-agent-builder-reviewer",
        verdict="APPROVED",
        artifact="skill prose change",
    )

    assert exit_code == 0, (
        "des record-review-verdict must exit 0 on a valid APPROVED verdict -- "
        f"got exit_code={exit_code}; stdout={stdout!r}; stderr={stderr!r}"
    )
    records = _read_ledger(tmp_path, "demo")
    assert len(records) == 1, (
        f"expected exactly one ledger record, got {records!r} "
        f"(ledger: {_ledger_path(tmp_path, 'demo')})"
    )
    record = records[0]
    assert record["event"] == "ReviewVerdictRecorded"
    assert record["feature_id"] == "demo"
    assert record["slice_id"] == "slice-01"
    assert record["reviewer_agent_id"] == "nw-agent-builder-reviewer"
    assert record["verdict"] == "APPROVED"
    assert record["artifact"] == "skill prose change"
    timestamp = record.get("timestamp")
    assert isinstance(timestamp, str) and timestamp, (
        f"a real (non-fabricated) timestamp must be populated: {record!r}"
    )


def test_the_orchestrator_recovers_every_recorded_verdict_from_the_ledger(
    tmp_path: Path,
) -> None:
    """WS-6 recovery property: the ledger round-trips -- an orchestrator that
    lost a reviewer mid-session can grep `.nwave/telemetry/review/<feature>.jsonl`
    back and recover EACH reviewer's verdict + identity, in append order,
    across multiple slices/verdicts for the same feature."""
    _record_review_verdict(
        tmp_path,
        feature_id="demo",
        slice_id="slice-01",
        reviewer_agent_id="nw-agent-builder-reviewer",
        verdict="APPROVED",
        artifact="agent spec tightened",
    )
    exit_code, stdout, stderr = _record_review_verdict(
        tmp_path,
        feature_id="demo",
        slice_id="slice-02",
        reviewer_agent_id="nw-skill-reviewer",
        verdict="NEEDS_REVISION",
        artifact="SKILL.md scope-discipline pass",
    )

    assert exit_code == 0, (
        f"the second recording must also exit 0 -- stdout={stdout!r}; stderr={stderr!r}"
    )
    records = _read_ledger(tmp_path, "demo")
    assert len(records) == 2, (
        "earlier records must never be altered/dropped by a later "
        f"recording (append-only) -- got {records!r}"
    )
    by_slice = {r["slice_id"]: r for r in records}
    recovered_first = by_slice["slice-01"]
    recovered_second = by_slice["slice-02"]
    assert recovered_first["verdict"] == "APPROVED"
    assert recovered_first["reviewer_agent_id"] == "nw-agent-builder-reviewer"
    assert recovered_second["verdict"] == "NEEDS_REVISION"
    assert recovered_second["reviewer_agent_id"] == "nw-skill-reviewer"


@pytest.mark.negative_at
def test_record_review_verdict_rejects_an_unknown_verdict_value(
    tmp_path: Path,
) -> None:
    """A verdict value outside the closed set (APPROVED/NEEDS_REVISION/REJECTED)
    is REJECTED loud -- non-zero exit, a diagnostic naming the bad value, and
    NOTHING written to the ledger. Never a silent record of a made-up verdict."""
    exit_code, stdout, stderr = _record_review_verdict(
        tmp_path,
        feature_id="demo",
        slice_id="slice-03",
        reviewer_agent_id="nw-agent-builder-reviewer",
        verdict="MAYBE",
        artifact="skill prose change",
    )

    assert exit_code != 0, (
        "an unknown --verdict value must be rejected (non-zero exit) -- got "
        f"exit_code=0; stdout={stdout!r}; stderr={stderr!r}"
    )
    records = _read_ledger(tmp_path, "demo")
    assert records == [], (
        "an unknown --verdict value must NOT be recorded to the ledger -- "
        f"got {records!r}"
    )
    # Non-vacuity (P0.2): the diagnostic must name the OFFENDING VALUE
    # ("maybe"), not merely mention "verdict" in passing -- today (subcommand
    # unregistered) the dispatcher's "invalid choice" message never reaches
    # `--verdict` parsing at all, so `maybe` is genuinely absent from the
    # diagnostic; this assertion only turns GREEN once `--verdict` is itself
    # validated against the closed set and rejects the bad value by name.
    diagnostic = (stdout + stderr).lower()
    assert "verdict" in diagnostic, (
        "the rejection diagnostic must name the offending field (`verdict`) -- "
        f"stdout={stdout!r}; stderr={stderr!r}"
    )
    assert "maybe" in diagnostic, (
        "the rejection diagnostic must name the offending value ('MAYBE'), "
        f"not just mention 'verdict' in passing -- stdout={stdout!r}; "
        f"stderr={stderr!r}"
    )
