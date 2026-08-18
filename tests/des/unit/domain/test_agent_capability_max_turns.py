"""`resolve_declared_max_turns` -- the resolver the Run 8 subagent
budget-exhaustion hook guard reads to know a role's own declared
`maxTurns` boundary, without guessing a default for a role that
declares none."""

from __future__ import annotations

from pathlib import Path

from des.domain.agent_capability import resolve_declared_max_turns


def _write_agent_spec(tmp_path: Path, name: str, frontmatter: str) -> Path:
    agents_dir = tmp_path / "nWave" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    spec_path = agents_dir / f"{name}.md"
    spec_path.write_text(f"---\n{frontmatter}\n---\n\n# {name}\n", encoding="utf-8")
    return spec_path


class TestResolveDeclaredMaxTurns:
    def test_declared_positive_integer_resolves(self, tmp_path: Path) -> None:
        _write_agent_spec(tmp_path, "nw-probe", "name: nw-probe\nmaxTurns: 40\n")
        assert resolve_declared_max_turns("nw-probe", repo_root=tmp_path) == 40

    def test_missing_spec_resolves_none(self, tmp_path: Path) -> None:
        assert (
            resolve_declared_max_turns("nw-does-not-exist", repo_root=tmp_path) is None
        )

    def test_spec_without_max_turns_key_resolves_none(self, tmp_path: Path) -> None:
        _write_agent_spec(tmp_path, "nw-probe", "name: nw-probe\n")
        assert resolve_declared_max_turns("nw-probe", repo_root=tmp_path) is None

    def test_non_integer_value_resolves_none(self, tmp_path: Path) -> None:
        _write_agent_spec(tmp_path, "nw-probe", "name: nw-probe\nmaxTurns: many\n")
        assert resolve_declared_max_turns("nw-probe", repo_root=tmp_path) is None

    def test_zero_resolves_none(self, tmp_path: Path) -> None:
        _write_agent_spec(tmp_path, "nw-probe", "name: nw-probe\nmaxTurns: 0\n")
        assert resolve_declared_max_turns("nw-probe", repo_root=tmp_path) is None

    def test_negative_resolves_none(self, tmp_path: Path) -> None:
        _write_agent_spec(tmp_path, "nw-probe", "name: nw-probe\nmaxTurns: -5\n")
        assert resolve_declared_max_turns("nw-probe", repo_root=tmp_path) is None

    def test_spec_with_no_frontmatter_resolves_none(self, tmp_path: Path) -> None:
        agents_dir = tmp_path / "nWave" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        (agents_dir / "nw-probe.md").write_text("# no frontmatter\n", encoding="utf-8")
        assert resolve_declared_max_turns("nw-probe", repo_root=tmp_path) is None

    def test_real_checked_in_examiner_spec_resolves_forty(self) -> None:
        """The exact real value Run 8's budget guard is threshold-computed
        against -- pinned so this test fails loud if the checked-in spec's
        own maxTurns ever changes without the guard's own tests being
        revisited."""
        repo_root = Path(__file__).resolve().parents[4]
        assert resolve_declared_max_turns("nw-user-examiner", repo_root=repo_root) == 40
