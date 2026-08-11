"""Agent specs stay provider-neutral: no literal Tsunami/Graphify wiring.

Coverage is catalog-driven (``load_public_agents``) for the public-roster
check, plus an unconditional sweep of every ``nWave/agents/nw-*.md`` file --
the public agent count drifts as the catalog evolves, so no count is
restated here. Every agent spec must carry no `graphify` or `tsunami`
literal (covers both the `mcp__tsunami__*` tool grant and bare operational
prose mentions); this deliberately does not blanket-ban `mcp__` at the agent
level, since unrelated MCP tool grants (e.g. Playwright, Miro) are legitimate
and out of this check's scope. No `des code-fact` need may be expressed
except through the provider-neutral port.
"""

from pathlib import Path

from scripts.shared.agent_catalog import is_public_agent, load_public_agents
from scripts.shared.frontmatter import parse_frontmatter_file


REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTS_DIR = REPO_ROOT / "nWave" / "agents"

FORBIDDEN_LITERALS = ("graphify", "tsunami")


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
        text_lower = agent_file.read_text(encoding="utf-8").lower()

        for literal in FORBIDDEN_LITERALS:
            assert literal not in text_lower, f"{agent_file.name} contains '{literal}'"


def test_code_analysis_port_users_have_bash():
    """Every agent whose skills include nw-code-analysis-port must grant Bash.

    Catalog-independent: derives its coverage set directly from each spec's
    parsed ``skills`` frontmatter rather than a hardcoded agent list, so a
    newly wired-in consumer of the port is checked automatically. Also pins
    the reviewer's safety boundary: nw-security-analyst-reviewer must carry
    Bash (needed to resolve code facts via the port) while never gaining
    Write/Edit (it reviews only, it never modifies).
    """
    agent_files = sorted(AGENTS_DIR.glob("nw-*.md"))

    assert agent_files, "No agents found in nWave/agents"

    port_users = []

    for agent_file in agent_files:
        metadata, _ = parse_frontmatter_file(agent_file)
        assert metadata is not None, f"{agent_file.name} has unparseable frontmatter"

        skills = metadata.get("skills") or []
        if "nw-code-analysis-port" not in skills:
            continue

        port_users.append(agent_file.name)
        tools = [t.strip() for t in (metadata.get("tools") or "").split(",")]
        assert "Bash" in tools, (
            f"{agent_file.name} uses nw-code-analysis-port but lacks Bash"
        )

    assert port_users, "No agent references nw-code-analysis-port"

    reviewer_file = AGENTS_DIR / "nw-security-analyst-reviewer.md"
    reviewer_metadata, _ = parse_frontmatter_file(reviewer_file)
    reviewer_tools = [
        t.strip() for t in (reviewer_metadata.get("tools") or "").split(",")
    ]

    assert "Bash" in reviewer_tools
    assert "Write" not in reviewer_tools
    assert "Edit" not in reviewer_tools


def test_every_agent_spec_provider_neutrality():
    """Every nw-*.md agent spec (public or private) is provider-neutral.

    Broader than the public-roster check above: this sweeps the whole
    ``nWave/agents/`` directory unconditionally, so a residue introduced on
    a not-yet-public agent is caught before it ever reaches the catalog.
    """
    agent_files = sorted(AGENTS_DIR.glob("nw-*.md"))

    assert agent_files, "No agents found in nWave/agents"

    for agent_file in agent_files:
        text_lower = agent_file.read_text(encoding="utf-8").lower()

        for literal in FORBIDDEN_LITERALS:
            assert literal not in text_lower, f"{agent_file.name} contains '{literal}'"
