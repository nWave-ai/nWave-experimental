"""Regression test: public skills are free of Graphify/MCP residue and project des code-fact."""

import json
import re
from pathlib import Path

import pytest

from scripts.shared.agent_catalog import (
    build_ownership_map,
    detect_command_skills,
    load_public_agents,
)
from scripts.shared.skill_distribution import enumerate_skills, filter_public_skills


PROJECT_ROOT = Path(__file__).resolve().parents[3]
NWAVE_DIR = PROJECT_ROOT / "nWave"
SKILLS_DIR = NWAVE_DIR / "skills"
AGENTS_DIR = NWAVE_DIR / "agents"

TARGET_SKILLS = {"nw-code-analysis-port"}

ALLOWED_COMMAND_IDS = {
    "query.callers-of",
    "query.reads-of",
    "query.never-wired",
    "query.atoms-in-file",
    "query.adr-section",
}

EXACT_COMMAND_FORMS = (
    "des code-fact query.callers-of SYMBOL --root ROOT",
    "des code-fact query.reads-of SYMBOL --root ROOT",
    "des code-fact query.never-wired SYMBOL --root ROOT",
    "des code-fact query.atoms-in-file --root FILE_OR_ROOT",
    "des code-fact query.adr-section ANCHOR --root ROOT",
)

GRAPHIFY_PATTERN = re.compile(r"graphify", re.IGNORECASE)
MCP_PATTERN = re.compile(r"mcp__")
CODE_FACT_COMMAND_PATTERN = re.compile(r"des code-fact query\.[\w-]+")


@pytest.fixture(scope="module")
def public_skill_entries():
    public_agents = load_public_agents(NWAVE_DIR)
    ownership_map = build_ownership_map(AGENTS_DIR)
    command_skills = detect_command_skills(SKILLS_DIR)
    entries = enumerate_skills(SKILLS_DIR)
    return filter_public_skills(entries, public_agents, ownership_map, command_skills)


@pytest.fixture(scope="module")
def public_skill_names(public_skill_entries) -> set[str]:
    return {entry.name for entry in public_skill_entries}


@pytest.mark.parametrize("skill_name", sorted(TARGET_SKILLS))
def test_target_skill_is_public(skill_name, public_skill_names):
    assert skill_name in public_skill_names


def test_every_public_skill_has_no_graphify_or_mcp_residue(public_skill_entries):
    for entry in public_skill_entries:
        content = (SKILLS_DIR / entry.name / "SKILL.md").read_text(encoding="utf-8")
        assert not GRAPHIFY_PATTERN.search(content), (
            f"{entry.name}: operational graphify reference found"
        )
        assert not MCP_PATTERN.search(content), f"{entry.name}: mcp__ reference found"


def test_every_skill_textual_asset_has_no_graphify_tsunami_or_mcp_residue():
    """Sweep ALL textual assets under nWave/skills, public or not.

    Broader than the public-only check above: any SKILL.md/md/yaml/yml/json
    file under nWave/skills must be case-insensitively free of graphify,
    tsunami, and mcp__ -- catches residue on skills not yet in the public
    catalog.
    """
    tsunami_pattern = re.compile(r"tsunami", re.IGNORECASE)
    graphify_pattern = re.compile(r"graphify", re.IGNORECASE)

    asset_files = sorted(
        f
        for pattern in ("*.md", "*.yaml", "*.yml", "*.json")
        for f in SKILLS_DIR.rglob(pattern)
    )

    assert asset_files, "No textual assets found under nWave/skills"

    for asset_file in asset_files:
        content = asset_file.read_text(encoding="utf-8")
        rel = asset_file.relative_to(SKILLS_DIR)

        assert not graphify_pattern.search(content), f"{rel}: contains 'graphify'"
        assert not tsunami_pattern.search(content), f"{rel}: contains 'tsunami'"
        assert not MCP_PATTERN.search(content), f"{rel}: contains 'mcp__'"


@pytest.mark.parametrize("skill_name", sorted(TARGET_SKILLS))
def test_target_skill_projects_executable_code_fact_command(skill_name):
    content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
    matches = CODE_FACT_COMMAND_PATTERN.findall(content)
    assert matches, (
        f"{skill_name}: no executable `des code-fact query.<capability>` command found"
    )
    found_ids = {match.split("query.", 1)[1].split()[0] for match in matches}
    for command_id in found_ids:
        assert f"query.{command_id}" in ALLOWED_COMMAND_IDS, (
            f"{skill_name}: unsupported command id `query.{command_id}` found"
        )
    assert found_ids & {cid.split("query.", 1)[1] for cid in ALLOWED_COMMAND_IDS}, (
        f"{skill_name}: no allowed `des code-fact query.<capability>` command found"
    )


def test_code_analysis_port_projects_all_five_exact_command_forms():
    content = (SKILLS_DIR / "nw-code-analysis-port" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for command_form in EXACT_COMMAND_FORMS:
        assert command_form in content, (
            f"nw-code-analysis-port: missing exact command form `{command_form}`"
        )


ENVELOPE_LINE_PATTERN = re.compile(r"The CLI returns JSON: `\{([^}]*)\}`")


def test_skill_documented_envelope_matches_real_cli_output(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The `{provider, confidence, payload, trace}` envelope SKILL.md documents
    must be the exact key set `des code-fact` actually emits. Guards against
    doc drift on the next envelope-shape change (e.g. the reason_code
    relocation into payload, ADR-LA-001 D9 slice (c))."""
    from des.cli.code_fact import main

    (tmp_path / "subject.py").write_text(
        "def target():\n    return 1\n\ndef caller():\n    return target()\n",
        encoding="utf-8",
    )
    exit_code = main(["query.callers-of", "target", "--root", str(tmp_path)])
    captured = capsys.readouterr()
    assert exit_code == 0
    real_keys = set(json.loads(captured.out))

    content = (SKILLS_DIR / "nw-code-analysis-port" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    match = ENVELOPE_LINE_PATTERN.search(content)
    assert match, "nw-code-analysis-port: no documented CLI envelope line found"
    documented_keys = {token.strip() for token in match.group(1).split(",")}

    assert documented_keys == real_keys, (
        f"nw-code-analysis-port SKILL.md documents envelope keys "
        f"{sorted(documented_keys)!r} but `des code-fact` actually emits "
        f"{sorted(real_keys)!r} -- fix the SKILL.md envelope line"
    )
