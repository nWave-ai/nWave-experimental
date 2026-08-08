"""Feature-end EXAMINE gate: the done-gate mirrors the per-slice examine gate.

evolution-plan P2.2 (docs/product/evolution-plan.md): the per-slice commit
gate already REFUSES to commit without a fresh PASS ``ExamineVerdict``
(``des.cli.commit_slice.check_examine_verdict``). This closes the feature-end
counterpart: ``run_feature_end_cycle`` REFUSES to sign + declare a feature
done unless EVERY charter under
``docs/product/expectations/{feature_id}/*.md`` carries a fresh feature-end-
scoped (``slice_id="feature-end"``) PASS ``ExamineVerdict``.

Unit-level, hermetic: the upstream legs (walking-skeleton, env-e2e,
coverage-map, full-suite) are stubbed to PASS so the test isolates the NEW
examine leg without spawning real gate subprocesses for THOSE four legs --
mirrors the existing ``monkeypatch.setattr(module, "des_spawn", ...)``
wiring-test pattern already used in this codebase (e.g.
``test_carpaccio_intercept_bugfix_lane_wiring.py``).

The full-suite stub honestly reports ``FullSuiteLegRan`` (mirrors the
``FullSuiteLegRan(pytest_exit_code=0)`` a genuine green suite would
produce), never ``FullSuiteLegNotApplicable``: this fixture models a
NORMAL delivered feature reaching the examine leg -- the realistic case
where at least one leg has genuinely run -- not the pathological
zero-legs-observed repo the certification-legs-observe-real-execution
guard (``census.ran == 0`` -> ``CycleIndeterminate``) exists to catch.
Reporting NOT_APPLICABLE here (as this stub once did) would make THIS
fixture indistinguishable from that pathological case and trip the guard
for the wrong reason -- masking the examine leg this test actually
exercises. The three P0 legs run for real (doc-coherence, execution-reach,
fresh-clone) and genuinely resolve NOT_APPLICABLE against this minimal
fixture (no coverage.xml / demo-recipe / doc claims worth checking) --
that is honest too, since nothing was fabricated for them.
"""

from __future__ import annotations

from pathlib import Path

from des.application import feature_end_cycle_service as svc
from des.application.feature_end_cycle_service import (
    CoverageMapLegRan,
    CycleRefusal,
    CycleSuccess,
    run_feature_end_cycle,
)
from des.cli.record_examine_verdict import record_examine_verdict


def _coverage_map_leg_ran(*, ledger, repo_root, feature_id, feature_dir):
    """The leg that now carries `leg_census.ran >= 1` in these fixtures.

    Until 2026-08-06 that was the full-suite leg, stubbed to `FullSuiteLegRan`.
    It is gone -- it duplicated CI and held the condemned run-contract provider
    alive -- so a leg NONE of these tests measures takes its place. The census
    folds by name suffix, so any surviving `*LegRan` counts identically.

    A named function, not a lambda: it must accept the leg's keyword-only
    signature, which is exactly what ruff's PLW0108 "just inline the call"
    suggestion would break.
    """
    return CoverageMapLegRan()


_FEATURE_ID = "feat-examine-gate"
_SLICE_ID = "feature-end"


def _seed_feature_dir(tmp_path: Path, feature_id: str = _FEATURE_ID) -> Path:
    """A minimal feature-dir with NO feature-delta.md (no Slice-Plan -> no
    undelivered-slice truncation refusal -- keeps the fixture focused on the
    examine leg alone)."""
    feature_dir = tmp_path / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True)
    return feature_dir


def _write_charter(
    tmp_path: Path,
    feature_id: str,
    name: str,
    body: str = "# Charter\n\nDo the thing.\n",
) -> Path:
    charter_dir = tmp_path / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / f"{name}.md"
    charter_path.write_text(body, encoding="utf-8")
    return charter_path


def _stub_upstream_legs(monkeypatch) -> None:
    """Short-circuit every leg that runs BEFORE the feature-end examine leg."""
    monkeypatch.setattr(
        svc,
        "_run_walking_skeleton_gate",
        lambda *, repo_root, feature_dir: repo_root,
    )
    monkeypatch.setattr(
        svc,
        "_run_environmental_e2e_gate",
        lambda *, ledger, repo_root, feature_id, feature_dir, walking_skeleton: None,
    )
    monkeypatch.setattr(
        svc,
        "_run_coverage_map_verify_leg",
        _coverage_map_leg_ran,
    )


def _run_cycle(tmp_path: Path, feature_dir: Path, feature_id: str = _FEATURE_ID):
    return run_feature_end_cycle(
        repo_root=tmp_path,
        feature_id=feature_id,
        feature_dir=feature_dir,
        reviewer_agent_id="nw-software-crafter-reviewer",
        verdict="APPROVED",
    )


def test_charter_with_no_feature_end_examine_record_refuses_done(
    tmp_path: Path, monkeypatch
) -> None:
    """NEGATIVE: a charter exists but was never examined at feature scope."""
    _stub_upstream_legs(monkeypatch)
    feature_dir = _seed_feature_dir(tmp_path)
    _write_charter(tmp_path, _FEATURE_ID, "main")

    result = _run_cycle(tmp_path, feature_dir)

    assert isinstance(result, CycleRefusal)
    assert "expectations" in result.error and "main.md" in result.error
    assert "no recorded FEATURE-END examine-verdict" in result.error
    assert "nw-user-examiner" in result.error
    assert "record-examine-verdict" in result.error
    print(f"VERBATIM (missing): {result!r}")


def test_stale_charter_seal_after_pass_refuses_done(
    tmp_path: Path, monkeypatch
) -> None:
    """NEGATIVE: a feature-end PASS exists, but the charter changed after exam."""
    _stub_upstream_legs(monkeypatch)
    feature_dir = _seed_feature_dir(tmp_path)
    charter_path = _write_charter(tmp_path, _FEATURE_ID, "main", body="# Charter v1\n")

    record_examine_verdict(
        repo=tmp_path,
        feature_id=_FEATURE_ID,
        slice_id=_SLICE_ID,
        charter_path=charter_path,
        verdict="PASS",
        observations="walked the charter, all good",
        examiner="nw-user-examiner",
        timestamp="2026-07-03T00:00:00Z",
    )
    # The charter changes AFTER the exam -- the recorded charter_seal is now stale.
    charter_path.write_text("# Charter v2 (edited after exam)\n", encoding="utf-8")

    result = _run_cycle(tmp_path, feature_dir)

    assert isinstance(result, CycleRefusal)
    assert "changed after its feature-end examination" in result.error
    assert "stale-seal" in result.error
    print(f"VERBATIM (stale): {result!r}")


def test_fresh_pass_for_every_charter_proceeds_to_done(
    tmp_path: Path, monkeypatch
) -> None:
    """POSITIVE: a fresh feature-end PASS for every charter -> cycle proceeds."""
    _stub_upstream_legs(monkeypatch)
    feature_dir = _seed_feature_dir(tmp_path)
    charter_one = _write_charter(tmp_path, _FEATURE_ID, "main", body="# Charter one\n")
    charter_two = _write_charter(
        tmp_path, _FEATURE_ID, "second", body="# Charter two\n"
    )

    for charter_path in (charter_one, charter_two):
        record_examine_verdict(
            repo=tmp_path,
            feature_id=_FEATURE_ID,
            slice_id=_SLICE_ID,
            charter_path=charter_path,
            verdict="PASS",
            observations="walked the charter through the real surface, all good",
            examiner="nw-user-examiner",
            timestamp="2026-07-03T00:00:00Z",
        )

    result = _run_cycle(tmp_path, feature_dir)

    assert isinstance(result, CycleSuccess)
    assert result.verdict_hash
    print(f"VERBATIM (positive): {result!r}")


def test_feature_with_no_charters_is_unarmed_and_proceeds(
    tmp_path: Path, monkeypatch
) -> None:
    """BACKWARD-COMPAT: no docs/product/expectations charters -> leg is a no-op."""
    _stub_upstream_legs(monkeypatch)
    feature_dir = _seed_feature_dir(tmp_path)
    # Deliberately NO docs/product/expectations/{feature_id}/*.md charter.

    result = _run_cycle(tmp_path, feature_dir)

    assert isinstance(result, CycleSuccess)
    assert result.verdict_hash
    print(f"VERBATIM (unarmed): {result!r}")
