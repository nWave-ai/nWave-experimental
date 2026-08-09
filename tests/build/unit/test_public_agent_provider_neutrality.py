"""Public agent specs stay provider-neutral: no literal Tsunami/Graphify wiring.

Coverage is catalog-driven (``load_public_agents``), not a hardcoded roster --
the public agent count drifts as the catalog evolves, so no count is restated
here. Every public spec must carry no `graphify` or `tsunami` literal
(covers both the `mcp__tsunami__*` tool grant and bare operational prose
mentions), and no `des code-fact` need may be expressed except through that
port.
"""

from pathlib import Path

from scripts.shared.agent_catalog import is_public_agent, load_public_agents


REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTS_DIR = REPO_ROOT / "nWave" / "agents"


def test_public_agents_provider_neutrality():
    """Verify all public agents are provider-neutral."""
    public_agents = load_public_agents(REPO_ROOT / "nWave", strict=True)

    # Enumerate all nWave/agents/nw-*.md and retain public ones
    agent_files = sorted(
        f for f in AGENTS_DIR.glob("nw-*.md") if is_public_agent(f.name, public_agents)
    )

    assert agent_files, "No public agents found in nWave/agents"

    # For each public spec, assert case-insensitive absence of provider-specific literals
    for agent_file in agent_files:
        text = agent_file.read_text(encoding="utf-8")
        text_lower = text.lower()

        assert "graphify" not in text_lower, f"{agent_file.name} contains 'graphify'"
        assert "tsunami" not in text_lower, (
            f"{agent_file.name} contains 'tsunami' (tool grant or operational prose)"
        )
