"""Unit tests for `audit_seal_provenance` -- the pure, git-free consumer
logic that decides VERIFIED / PREMATURE / INDETERMINATE per
`SliceCommitVerified` record.

A fake `CommitTreePathPort` drives every branch without touching real git --
mirrors how the sibling gate-logic tests in this tree stub their driven
ports (e.g. `check_at_review`'s `CommitDiffPort` fakes).
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application.seal_provenance import SealVerdict, audit_seal_provenance
from des.ports.driven_ports.commit_tree_path_port import (
    CommitTreePathPort,
    Indeterminate,
)


class _FakeCommitTreePathPort(CommitTreePathPort):
    """Answers ``path_exists_at_commit`` from a canned table, keyed by
    ``(commit_sha, rel_path)``. A miss in the table returns ``False`` unless
    ``default`` overrides it."""

    def __init__(
        self,
        table: dict[tuple[str, str], bool | Indeterminate] | None = None,
        default: bool | Indeterminate = False,
    ) -> None:
        self._table = table or {}
        self._default = default

    def path_exists_at_commit(
        self, repo: Path, commit_sha: str, rel_path: str
    ) -> bool | Indeterminate:
        return self._table.get((commit_sha, rel_path), self._default)


_FEATURE = "seal-provenance-unit-fixture"


def _feature_at_dir(repo: Path) -> Path:
    at_dir = repo / "tests" / "acceptance" / _FEATURE.replace("-", "_")
    at_dir.mkdir(parents=True, exist_ok=True)
    return at_dir


def _write_feature_file(repo: Path, slice_id: str) -> str:
    at_dir = _feature_at_dir(repo)
    rel = at_dir.relative_to(repo) / f"{slice_id}.feature"
    (repo / rel).write_text(
        f"@feature-{_FEATURE}\nFeature: x\n\n  @{slice_id}\n  Scenario: y\n"
        "    Given a\n    When b\n    Then c\n",
        encoding="utf-8",
    )
    return str(rel)


def _seal(repo: Path, slice_id: str, *, commit_sha: str | None) -> None:
    AtCompletionLedger(_FEATURE, repo).append_gate_event(
        "SliceCommitVerified", slice_id, commit_sha=commit_sha
    )


def test_record_without_commit_sha_is_indeterminate_never_a_silent_pass(
    tmp_path: Path,
) -> None:
    _write_feature_file(tmp_path, "slice-03")
    _seal(tmp_path, "slice-03", commit_sha=None)

    findings = audit_seal_provenance(
        tmp_path, _FEATURE, path_port=_FakeCommitTreePathPort(default=True)
    )

    assert len(findings) == 1
    assert findings[0].verdict is SealVerdict.INDETERMINATE
    assert "commit_sha" in findings[0].reason


def test_at_missing_at_attested_commit_is_premature(tmp_path: Path) -> None:
    rel = _write_feature_file(tmp_path, "slice-03")
    _seal(tmp_path, "slice-03", commit_sha="abc123")

    port = _FakeCommitTreePathPort(table={("abc123", rel): False})
    findings = audit_seal_provenance(tmp_path, _FEATURE, path_port=port)

    assert len(findings) == 1
    assert findings[0].verdict is SealVerdict.PREMATURE
    assert findings[0].commit_sha == "abc123"
    assert rel in findings[0].checked_paths


def test_at_present_at_attested_commit_is_verified(tmp_path: Path) -> None:
    rel = _write_feature_file(tmp_path, "slice-03")
    _seal(tmp_path, "slice-03", commit_sha="abc123")

    port = _FakeCommitTreePathPort(table={("abc123", rel): True})
    findings = audit_seal_provenance(tmp_path, _FEATURE, path_port=port)

    assert len(findings) == 1
    assert findings[0].verdict is SealVerdict.VERIFIED


def test_git_indeterminate_propagates_never_collapsed_to_pass_or_fail(
    tmp_path: Path,
) -> None:
    rel = _write_feature_file(tmp_path, "slice-03")
    _seal(tmp_path, "slice-03", commit_sha="abc123")

    port = _FakeCommitTreePathPort(
        table={("abc123", rel): Indeterminate("git could not resolve abc123")}
    )
    findings = audit_seal_provenance(tmp_path, _FEATURE, path_port=port)

    assert findings[0].verdict is SealVerdict.INDETERMINATE
    assert "could not resolve" in findings[0].reason


def test_no_discoverable_at_is_indeterminate(tmp_path: Path) -> None:
    """A slice with a commit_sha but zero AT files findable on this working
    tree (e.g. deleted since, or a naming-convention mismatch) cannot be
    checked -- INDETERMINATE, not a silent VERIFIED."""
    _seal(tmp_path, "slice-99-no-at", commit_sha="abc123")

    findings = audit_seal_provenance(
        tmp_path, _FEATURE, path_port=_FakeCommitTreePathPort(default=True)
    )

    assert findings[0].verdict is SealVerdict.INDETERMINATE
    assert "no AT file is discoverable" in findings[0].reason


def test_absent_ledger_yields_empty_findings(tmp_path: Path) -> None:
    findings = audit_seal_provenance(
        tmp_path, "no-such-feature", path_port=_FakeCommitTreePathPort()
    )
    assert findings == []


def test_multiple_records_audited_independently_in_seq_order(
    tmp_path: Path,
) -> None:
    rel = _write_feature_file(tmp_path, "slice-01")
    _seal(tmp_path, "slice-01", commit_sha=None)  # historical, no sha
    _seal(tmp_path, "slice-01", commit_sha="good-sha")  # honest re-seal

    port = _FakeCommitTreePathPort(table={("good-sha", rel): True})
    findings = audit_seal_provenance(tmp_path, _FEATURE, path_port=port)

    assert [f.verdict for f in findings] == [
        SealVerdict.INDETERMINATE,
        SealVerdict.VERIFIED,
    ]
    assert findings[0].seq < findings[1].seq
