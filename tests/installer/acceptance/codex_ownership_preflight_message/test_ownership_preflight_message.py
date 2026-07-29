"""Regression: the Codex ownership preflight refusal is WHAT/WHY/HOW-complete.

Guards against the incident of 2026-07-28 (see
docs/mikado/codex-parity-and-performance-delivery.mikado.md context): a flood
of same-shape collisions printed one near-identical, HOW-less log line per
collision (172 lines observed live) and the log simply ended -- no remedy, no
explicit outcome. See scripts/install/install_nwave.py
NWaveInstaller._report_ownership_preflight_errors and
_OWNERSHIP_PREFLIGHT_REMEDIES for the fix.
"""

from __future__ import annotations

from pathlib import Path

from scripts.install.install_nwave import NWaveInstaller


def _installer() -> NWaveInstaller:
    return NWaveInstaller(platform_override={"codex"}, dev_mode=True)


def _write_foreign_skills(skills_dir: Path, count: int) -> None:
    for i in range(count):
        skill = skills_dir / f"nw-foreign-{i}"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("foreign\n", encoding="utf-8")


def test_flooded_collisions_aggregate_with_how_and_a_verdict_line(
    tmp_path: Path, monkeypatch
) -> None:
    """A flood of same-shape collisions must not become N HOW-less log lines.

    Three properties, each independently falsifiable:
    1. Aggregation -- fewer printed collision lines than raw collisions once
       the count exceeds the bounded sample (never one line per collision).
    2. HOW -- the exact adoption flag AND its precondition, named verbatim,
       not left for the operator to discover by reading installer source.
    3. Verdict -- the log ends on an explicit, falsifiable outcome, not on
       the last collision line with the result left to be inferred.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    monkeypatch.setenv("CODEX_HOME", str(home / ".codex"))
    collision_count = 9
    _write_foreign_skills(home / ".agents" / "skills", collision_count)
    (home / ".codex" / "agents").mkdir(parents=True)

    installer = _installer()
    lines: list[str] = []
    monkeypatch.setattr(installer.logger, "error", lines.append)

    assert not installer.validate_codex_ownership_preflight()

    collision_lines = [
        line for line in lines if "foreign or untracked Codex skill collision" in line
    ]
    assert 0 < len(collision_lines) < collision_count, (
        f"expected a bounded sample, not one line per collision: {lines}"
    )
    assert any("more" in line for line in lines), (
        "expected a '... and N more' summary for the truncated tail"
    )

    how_lines = [line for line in lines if "--adopt-legacy-codex-dev" in line]
    assert how_lines, f"refusal must name the adoption flag verbatim: {lines}"
    assert any("--dev --platform codex" in line for line in how_lines), (
        f"refusal must also name the flag's precondition: {how_lines}"
    )

    verdict = lines[-1]
    assert "Installation refused" in verdict, (
        f"log must not simply end on the last collision line: {lines}"
    )
    assert str(collision_count) in verdict, (
        f"verdict must state the actual collision count: {verdict}"
    )
    assert "0 files written" in verdict or "nothing changed" in verdict, (
        f"verdict must state the outcome explicitly, not leave it implied: {verdict}"
    )
