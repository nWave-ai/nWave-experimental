"""`reused-gate-assumption-unreviewed` gap tests (GDP-1/GDP-2 authoring-time
affordance, sister-inspired ATD lesson 2026-08-02).

Fixtures build their OWN `nWave/gates/<id>.yaml` under `tmp_path` -- never
the real repo's catalog -- so these tests stay correct even if the live
`verify-slice-commit.yaml` content changes independently.
"""

from __future__ import annotations

from pathlib import Path

from des.cli.feature_delta_doctor import diagnose


_GATE_ID = "fake-gate"
_GATE_MODULE = "des.cli.fake_gate_module"
_GATE_REPO_PATH = "src/des/cli/fake_gate_module.py"


def _write_fake_gate(repo_root: Path, *, input_assumptions: list[str] | None) -> None:
    gates_dir = repo_root / "nWave" / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"gate_id: {_GATE_ID}",
        "responsibility: a fake gate for testing the doctor's reuse-assumption check",
        f"module: {_GATE_MODULE}",
        "entry_function: main",
        "language_neutral_contract: true",
    ]
    if input_assumptions:
        lines.append("input_assumptions:")
        for a in input_assumptions:
            lines.append(f'  - "{a}"')
    (gates_dir / f"{_GATE_ID}.yaml").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def _reuse_analysis_content(
    *, decision: str = "EXTEND", justification: str = "needed for the seal"
) -> str:
    return (
        "## Reuse Analysis\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| fake_gate_module | `{_GATE_REPO_PATH}` | reuse | {decision} | {justification} |\n"
    )


def test_extend_row_on_a_gate_with_assumptions_and_no_review_marker_is_a_gap(
    tmp_path: Path,
) -> None:
    _write_fake_gate(
        tmp_path,
        input_assumptions=["the caller's population is always the current tree"],
    )
    gaps = diagnose(_reuse_analysis_content(), repo_root=tmp_path)
    gap_ids = [g["id"] for g in gaps]
    assert "reused-gate-assumption-unreviewed" in gap_ids


def test_the_gap_names_the_gate_id_and_renders_every_assumption(tmp_path: Path) -> None:
    _write_fake_gate(
        tmp_path,
        input_assumptions=[
            "assumption one about the caller",
            "assumption two about the caller",
        ],
    )
    gaps = diagnose(_reuse_analysis_content(), repo_root=tmp_path)
    gap = next(g for g in gaps if g["id"] == "reused-gate-assumption-unreviewed")
    assert _GATE_ID in gap["what"]
    assert "assumption one about the caller" in gap["why"]
    assert "assumption two about the caller" in gap["why"]
    assert _GATE_ID in gap["how"]
    assert "Assumptions-Reviewed" in gap["how"]


def test_assumptions_reviewed_marker_naming_the_gate_clears_the_gap(
    tmp_path: Path,
) -> None:
    _write_fake_gate(tmp_path, input_assumptions=["some assumption"])
    content = _reuse_analysis_content(
        justification=f"Assumptions-Reviewed: {_GATE_ID}, still holds for our case"
    )
    gaps = diagnose(content, repo_root=tmp_path)
    assert "reused-gate-assumption-unreviewed" not in [g["id"] for g in gaps]


def test_marker_naming_a_different_gate_does_not_clear_the_gap(tmp_path: Path) -> None:
    """The marker is scoped to THIS gate -- reviewing a different reused
    gate's assumptions must not silently clear this one's."""
    _write_fake_gate(tmp_path, input_assumptions=["some assumption"])
    content = _reuse_analysis_content(
        justification="Assumptions-Reviewed: some-other-gate-entirely"
    )
    gaps = diagnose(content, repo_root=tmp_path)
    assert "reused-gate-assumption-unreviewed" in [g["id"] for g in gaps]


def test_create_new_decision_never_fires_this_check(tmp_path: Path) -> None:
    """The check is scoped to EXTEND -- a CREATE_NEW row is not reusing
    anything and has no inherited assumption to review."""
    _write_fake_gate(tmp_path, input_assumptions=["some assumption"])
    content = _reuse_analysis_content(
        decision="CREATE_NEW", justification="brand new module"
    )
    gaps = diagnose(content, repo_root=tmp_path)
    assert "reused-gate-assumption-unreviewed" not in [g["id"] for g in gaps]


def test_a_gate_with_no_declared_assumptions_never_fires(tmp_path: Path) -> None:
    """Absence of `input_assumptions` on the gate itself means undeclared,
    never a reason to demand a review marker for nothing."""
    _write_fake_gate(tmp_path, input_assumptions=None)
    gaps = diagnose(_reuse_analysis_content(), repo_root=tmp_path)
    assert "reused-gate-assumption-unreviewed" not in [g["id"] for g in gaps]


def test_a_file_not_matching_any_catalogued_gate_module_never_fires(
    tmp_path: Path,
) -> None:
    _write_fake_gate(tmp_path, input_assumptions=["some assumption"])
    content = (
        "## Reuse Analysis\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|---|---|---|---|---|\n"
        "| unrelated_helper | `src/des/cli/totally_unrelated_helper.py` | overlap | EXTEND | fine |\n"
    )
    gaps = diagnose(content, repo_root=tmp_path)
    assert "reused-gate-assumption-unreviewed" not in [g["id"] for g in gaps]


def test_no_repo_root_skips_this_leg_entirely(tmp_path: Path) -> None:
    """Mirrors `_dangling_adr_ref_gaps`'s own no-repo_root contract: with no
    tree supplied, this doctor has no gate catalog to check against, so it
    stays silent rather than guessing."""
    gaps = diagnose(_reuse_analysis_content(), repo_root=None)
    assert "reused-gate-assumption-unreviewed" not in [g["id"] for g in gaps]


def test_no_gates_directory_at_repo_root_is_silent_not_an_error(tmp_path: Path) -> None:
    """A repo_root with no nWave/gates/ at all (e.g. a non-nWave checkout)
    must degrade to silence, never raise."""
    gaps = diagnose(_reuse_analysis_content(), repo_root=tmp_path)
    assert "reused-gate-assumption-unreviewed" not in [g["id"] for g in gaps]


def test_malformed_gate_yaml_is_skipped_not_fatal(tmp_path: Path) -> None:
    gates_dir = tmp_path / "nWave" / "gates"
    gates_dir.mkdir(parents=True)
    (gates_dir / "broken.yaml").write_text(
        "not: valid: yaml: [unclosed", encoding="utf-8"
    )
    # Must not raise -- and must still find no match since the only gate
    # present is unparseable.
    gaps = diagnose(_reuse_analysis_content(), repo_root=tmp_path)
    assert "reused-gate-assumption-unreviewed" not in [g["id"] for g in gaps]
