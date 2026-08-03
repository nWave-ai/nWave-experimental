"""Regression: `mode-locus-gate` livelocks pre-commit because its ONLY write
path (`AtCompletionLedger.append_gate_event`, called unconditionally for
every one of the three exit codes -- PASS/FAIL/INDETERMINATE, see
`_record_outcome` in `des.cli.mode_locus_gate`) mutates the git-TRACKED file
`.nwave/audit/atdd-pure-events.jsonl` on every single run.

Reproduction (measured, `.pre-commit-config.yaml:138-141`, entry
``uv run python -m des.cli mode-locus-gate``): pre-commit diffs the whole
working tree before/after each hook and rejects the commit with "files were
modified by this hook" the moment the tracked ledger changes. The gate's own
retry re-runs the scan, which re-writes the ledger -- an unbreakable
live-lock, reproduced twice in a row against a real commit on
``nWave/skills/nw-hotspot/SKILL.md`` with HEAD never advancing.

The already-measured TRAP this suite exists to close: the existing
``NWAVE_AUDIT_LOG_MIGRATING=1`` env var does NOT fix this -- it swaps the
``GateOutcomeRecorded`` record for a ``MigrationQuiesced`` diagnostic
(``AtCompletionLedger._append_record``), but still APPENDS to the same
tracked file, so the live-lock is unchanged. A fix that merely substitutes
one event name for another falls into the identical trap; every test below
that asserts "the ledger is unchanged" checks the FULL parsed record content
(zero records of ANY event name), never a count of one specific event type.

Fix under test (not yet implemented -- these ATs are active-RED): a new
``--no-audit`` CLI flag on ``mode-locus-gate`` that skips the
``_record_outcome`` call entirely -- a git-optional trigger declaring itself
non-authoritative, as `.pre-commit-config.yaml`'s own comment already frames
the hooks ("the gates are the SSOT; the hooks are the git-optional second
trigger").

Driving surface (Mandate 16): the REAL ``mode_locus_gate.main()`` CLI edge,
driven in-process via ``run_cli_in_process`` -- never a direct import of an
internal helper. The wiring test additionally reads the REAL
``.pre-commit-config.yaml`` (read-only) to prove the config, not only the
CLI, was updated -- "catalogued != wired".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from des.cli.mode_locus_gate import main as _mode_locus_gate_main
from des.domain.gate_outcome import GateVerdict
from tests.common.in_process_cli import run_cli_in_process


_GATE_NAME = "mode-locus-gate"
_LEDGER_RELPATH = Path(".nwave") / "audit" / "atdd-pure-events.jsonl"
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PRE_COMMIT_CONFIG = _PROJECT_ROOT / ".pre-commit-config.yaml"


# ---------------------------------------------------------------------------
# tree builders -- isolated tmp_path fixtures, never the real repo's own
# nWave/ tree or its own ledger
# ---------------------------------------------------------------------------


def _clean_tree(root: Path) -> None:
    """A `nWave/skills` tree with no naked mode literal -> gate exit 0."""
    skills_dir = root / "nWave" / "skills" / "demo-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "This skill discusses the classic mode of operation in prose.\n",
        encoding="utf-8",
    )


def _naked_literal_tree(root: Path) -> None:
    """A naked, unconditional `atdd_pure` literal outside a sanctuary ->
    gate exit 2 (a genuinely guilty file the gate must still flag)."""
    skills_dir = root / "nWave" / "skills" / "demo-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "workflow.mode == atdd_pure\n", encoding="utf-8"
    )


def _zero_family_tree(root: Path) -> None:
    """An `nWave/` tree with none of the scanned families -> gate exit 3."""
    (root / "nWave").mkdir()


def _ledger_path(root: Path) -> Path:
    return root / _LEDGER_RELPATH


def _ledger_bytes(root: Path) -> bytes | None:
    path = _ledger_path(root)
    return path.read_bytes() if path.is_file() else None


def _ledger_records(root: Path) -> list[dict[str, object]]:
    path = _ledger_path(root)
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# 1 + 2 (POSITIVE + the measured NEGATIVE trap) -- --no-audit writes ZERO
# bytes and ZERO records of ANY event name, across every one of the gate's
# three exit codes (PASS/FAIL/INDETERMINATE all call `_record_outcome` today)
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("seed", "expected_exit_code", "stream_name", "observable_marker"),
    (
        (_clean_tree, 0, "stdout", "no naked mode literal found"),
        (_naked_literal_tree, 2, "stdout", "atdd_pure"),
        (_zero_family_tree, 3, "stderr", "INDETERMINATE"),
    ),
    ids=("pass-verdict", "fail-verdict", "indeterminate-verdict"),
)
def test_no_audit_rejects_any_ledger_mutation_across_every_gate_verdict(
    tmp_path: Path,
    seed,
    expected_exit_code: int,
    stream_name: str,
    observable_marker: str,
) -> None:
    """`--no-audit` must not change the gate's own scan verdict/observable
    output (audit suppression is a side channel, not a behavior change), AND
    must append literally zero bytes / zero parsed records of ANY event name
    to the tracked ledger -- not merely avoid the specific
    `GateOutcomeRecorded` name. This is exactly the shape
    `NWAVE_AUDIT_LOG_MIGRATING=1` fails: it swaps `GateOutcomeRecorded` for a
    `MigrationQuiesced` diagnostic and the file mutates anyway."""
    seed(tmp_path)
    before_bytes = _ledger_bytes(tmp_path)
    before_records = _ledger_records(tmp_path)

    exit_code, stdout, stderr = run_cli_in_process(
        ["--root", str(tmp_path), "--no-audit"],
        cwd=tmp_path,
        main=_mode_locus_gate_main,
    )

    observed_stream = stdout if stream_name == "stdout" else stderr
    after_bytes = _ledger_bytes(tmp_path)
    after_records = _ledger_records(tmp_path)

    assert exit_code == expected_exit_code and observable_marker in observed_stream, (
        "WHAT: --no-audit changed the gate's own scan verdict or observable "
        f"output; WHY: audit suppression must gate only the ledger write, "
        "never the scan itself; HOW: guard the single `_record_outcome` "
        f"call site, leave `scan_for_naked_literals`/exit-code logic untouched. "
        f"exit_code={exit_code} stdout={stdout!r} stderr={stderr!r}"
    )
    assert after_bytes == before_bytes, (
        "WHAT: the tracked audit ledger changed by at least one byte under "
        "--no-audit; WHY: pre-commit diffs the whole tree before/after the "
        "hook and rejects the commit the instant a tracked file mutates -- "
        "this is the exact live-lock; HOW: skip "
        "AtCompletionLedger.append_gate_event entirely when --no-audit is "
        f"set. before={before_bytes!r} after={after_bytes!r}"
    )
    assert after_records == before_records == [], (
        "WHAT: --no-audit appended a record of SOME event name even though "
        "the byte-identity check above passed; WHY: this is the measured "
        "NWAVE_AUDIT_LOG_MIGRATING=1 trap -- swapping GateOutcomeRecorded "
        "for a MigrationQuiesced (or any other) diagnostic still mutates "
        "the tracked file; HOW: --no-audit must produce ZERO ledger "
        f"records of any shape, not merely a different one. records={after_records!r}"
    )


# ---------------------------------------------------------------------------
# 4 -- NEGATIVE: suppressing the audit must not disarm the check itself
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_no_audit_still_flags_a_genuinely_guilty_file(tmp_path: Path) -> None:
    """`--no-audit` suppresses the ledger write, never the naked-literal
    check: a real offender is still named on stdout and the gate still
    exits 2. Suppressing the audit trail must not defang the guardrail it
    audits."""
    _naked_literal_tree(tmp_path)

    exit_code, stdout, _stderr = run_cli_in_process(
        ["--root", str(tmp_path), "--no-audit"],
        cwd=tmp_path,
        main=_mode_locus_gate_main,
    )

    offending_relpath = str(Path("nWave") / "skills" / "demo-skill" / "SKILL.md")
    assert exit_code == 2 and "atdd_pure" in stdout and offending_relpath in stdout, (
        "WHAT: --no-audit disarmed the naked-mode-literal check itself; "
        "WHY: audit-trail suppression must be orthogonal to the scan's own "
        "refusal -- a genuinely guilty file must still be named and still "
        "block; HOW: gate only the ledger append, never the offender scan "
        f"or its exit code. exit_code={exit_code} stdout={stdout!r}"
    )


# ---------------------------------------------------------------------------
# 3 -- PRESERVATION: without --no-audit, the original ledger write survives
# unchanged (the fix must not regress the pre-existing, correctly-working
# per-run audit trail this same file's records feed)
# ---------------------------------------------------------------------------


def test_without_no_audit_gate_outcome_recorded_is_still_written(
    tmp_path: Path,
) -> None:
    """PRESERVATION (sibling-branch pin): omitting `--no-audit` must still
    append the original `GateOutcomeRecorded` record exactly as before --
    the fix adds an opt-out, it must not silently flip the default."""
    _clean_tree(tmp_path)

    exit_code, stdout, _stderr = run_cli_in_process(
        ["--root", str(tmp_path)], cwd=tmp_path, main=_mode_locus_gate_main
    )

    records = _ledger_records(tmp_path)
    assert exit_code == 0 and "no naked mode literal found" in stdout, (
        f"expected an unmodified clean-tree PASS; exit_code={exit_code} stdout={stdout!r}"
    )
    assert (
        len(records) == 1
        and records[0].get("event") == "GateOutcomeRecorded"
        and records[0].get("gate") == _GATE_NAME
        and records[0].get("outcome") == GateVerdict.PASS.value
    ), (
        "WHAT: the default (no --no-audit) run no longer records "
        "GateOutcomeRecorded; WHY: the --no-audit fix must be strictly "
        "additive -- the pre-existing audited-by-default behavior is a "
        f"sibling branch that must not regress. records={records!r}"
    )


# ---------------------------------------------------------------------------
# 5 -- WIRING: catalogued != wired -- the config must actually pass the flag
# ---------------------------------------------------------------------------


def _mode_locus_gate_hook() -> dict[str, object] | None:
    config = yaml.safe_load(_PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            if hook.get("id") == "mode-locus-gate":
                return hook
    return None


@pytest.mark.negative_at
def test_precommit_still_invokes_mode_locus_gate_but_now_with_no_audit() -> None:
    """A CLI flag with no corresponding config change leaves the live-lock
    live: pre-commit must actually pass `--no-audit` to the gate, not merely
    have the capability exist unwired ("catalogued != wired")."""
    hook = _mode_locus_gate_hook()

    assert hook is not None, (
        "WHAT: no .pre-commit-config.yaml hook with id 'mode-locus-gate' "
        "was found; WHY: this test targets the existing hook, not a new "
        "one; HOW: the hook must still exist at "
        f"{_PRE_COMMIT_CONFIG} with id 'mode-locus-gate'."
    )
    entry = str(hook.get("entry", ""))
    assert "--no-audit" in entry, (
        "WHAT: the mode-locus-gate pre-commit hook's `entry` does not pass "
        "--no-audit; WHY: the CLI flag alone does not fix the live-lock -- "
        "pre-commit invokes exactly this entry string, so an unwired flag "
        "leaves every commit touching nWave/{skills,agents,tasks} still "
        "live-locked; HOW: update the hook's `entry` to "
        f"'uv run python -m des.cli mode-locus-gate --no-audit'. entry={entry!r}"
    )
