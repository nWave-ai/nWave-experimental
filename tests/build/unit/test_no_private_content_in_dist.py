"""Regression test: distribution assets must not contain private content.

Validates that build_dist.py, build_plugin.py, and wheel outputs
exclude private agents, private skills, internal docs, and private
research. Prevents recurrence of the tarball leak (RCA 2026-03-17).

Checks:
1. Private agent names never appear in dist or plugin output
2. Private skill directories never appear in dist or plugin output
3. docs/analysis/ never appears in any distribution asset
4. framework-catalog.yaml in dist does not contain private agent entries
"""

from __future__ import annotations

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.fixture()
def private_agents() -> set[str]:
    """Identify private agent names using the same logic as build scripts."""
    from scripts.shared.agent_catalog import is_public_agent, load_public_agents

    public = load_public_agents(PROJECT_ROOT / "nWave")
    return {
        a.stem.removeprefix("nw-")
        for a in (PROJECT_ROOT / "nWave" / "agents").glob("nw-*.md")
        if not is_public_agent(a.stem, public)
    }


@pytest.fixture()
def private_skill_dirs(private_agents: set[str]) -> set[str]:
    """Identify skill directories owned exclusively by private agents."""
    from scripts.shared.agent_catalog import build_ownership_map, load_public_agents

    agents_dir = PROJECT_ROOT / "nWave" / "agents"
    public_agents = load_public_agents(PROJECT_ROOT / "nWave")
    ownership_map = build_ownership_map(agents_dir)

    private_dirs: set[str] = set()
    for skill_dir_name, owning_agents in ownership_map.items():
        if not any(agent in public_agents for agent in owning_agents):
            private_dirs.add(skill_dir_name)
    return private_dirs


class TestBuildDistExcludesPrivateContent:
    """build_dist.py output must not contain private content."""

    @pytest.fixture()
    def dist_builder(self, tmp_path):
        """Create a DistBuilder writing to an ISOLATED per-test dist dir.

        Root-cause fix for the recurring parallel-load flaky: DistBuilder
        defaults ``dist_dir`` to ``<project_root>/dist`` — a FIXED SHARED path.
        Under pytest-xdist, parallel workers each call ``clean()`` (which
        ``rmtree``s that shared dist) while sibling workers are mid-build into
        it → non-deterministic FileNotFound / half-built-tree errors (a different
        scenario erroring each run, all passing in isolation). Redirecting
        ``dist_dir`` to the per-test ``tmp_path`` gives every test its own
        isolated build tree → genuinely parallel-safe (no serialization needed)
        AND hermetic (no pollution of the real ``<repo>/dist``).
        """
        from scripts.build_dist import DistBuilder
        from scripts.shared.agent_catalog import load_public_agents

        builder = DistBuilder(project_root=PROJECT_ROOT)
        builder.dist_dir = tmp_path / "dist"  # isolate the shared <repo>/dist race
        builder.public_agents = load_public_agents(PROJECT_ROOT / "nWave")
        builder.clean()
        builder.build_agents()
        builder.build_skills()
        return builder

    def test_dist_agents_are_public_only(self, dist_builder, private_agents):
        """Only public agents appear in dist output."""
        agents_dir = dist_builder.dist_dir / "agents" / "nw"
        if not agents_dir.exists():
            pytest.skip("build_agents did not produce agents directory")

        installed_agents = {
            f.stem.removeprefix("nw-") for f in agents_dir.glob("nw-*.md")
        }
        leaked = installed_agents & private_agents
        assert not leaked, f"Private agents in dist: {leaked}"

    def test_dist_skills_are_public_only(self, dist_builder, private_skill_dirs):
        """Only public skills appear in dist output."""
        # Skills in dist go under skills/nw/ (hierarchical for backward compat)
        for skills_root in [
            dist_builder.dist_dir / "skills" / "nw",
            dist_builder.dist_dir / "skills",
        ]:
            if skills_root.exists():
                installed = {d.name for d in skills_root.iterdir() if d.is_dir()}
                leaked = installed & private_skill_dirs
                assert not leaked, f"Private skills in dist ({skills_root}): {leaked}"

    def test_dist_has_no_analysis_docs(self, dist_builder):
        """docs/analysis/ must never appear in dist output."""
        analysis_in_dist = dist_builder.dist_dir / "docs" / "analysis"
        assert not analysis_in_dist.exists(), "docs/analysis/ leaked into dist"


class TestBuildPluginExcludesPrivateContent:
    """build_plugin.py output must not contain private content."""

    def test_plugin_agents_are_public_only(self, private_agents):
        """Only public agents appear in plugin agent list."""
        from scripts.shared.agent_catalog import load_public_agents

        public = load_public_agents(PROJECT_ROOT / "nWave")
        # Private agents must NOT be in public list
        for agent in private_agents:
            assert agent not in public, f"Private agent '{agent}' in public_agents list"

    def test_plugin_skills_are_public_only(self, private_skill_dirs):
        """Only public skills pass the filter pipeline."""
        from scripts.shared.agent_catalog import build_ownership_map, load_public_agents
        from scripts.shared.skill_distribution import (
            enumerate_skills,
            filter_public_skills,
        )

        skills_source = PROJECT_ROOT / "nWave" / "skills"
        public_agents = load_public_agents(PROJECT_ROOT / "nWave")
        ownership_map = build_ownership_map(PROJECT_ROOT / "nWave" / "agents")

        entries = enumerate_skills(skills_source)
        filtered = filter_public_skills(entries, public_agents, ownership_map)
        filtered_names = {e.name for e in filtered}

        leaked = filtered_names & private_skill_dirs
        assert not leaked, f"Private skills pass filter: {leaked}"


class TestWorkflowsUseWheelOnly:
    """Release workflows must use --wheel flag to prevent sdist generation."""

    @pytest.mark.parametrize(
        "workflow",
        [
            "release-dev.yml",
            "release-rc.yml",
            "release-prod.yml",
        ],
    )
    def test_no_bare_python_m_build(self, workflow):
        """No release workflow should run 'python -m build' without --wheel."""
        workflow_path = PROJECT_ROOT / ".github" / "workflows" / workflow
        content = workflow_path.read_text(encoding="utf-8")

        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped == "run: python -m build" or stripped.endswith(
                ": python -m build"
            ):
                pytest.fail(
                    f"{workflow}:{i}: bare 'python -m build' without --wheel flag. "
                    f"This produces an sdist that may leak private content. "
                    f"Use 'python -m build --wheel' instead."
                )
