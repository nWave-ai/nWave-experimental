#!/usr/bin/env python3
"""nwave-docgen: Deterministic documentation generator for nWave artifacts.

Pipeline: scan → extract → enrich → render → write

Scans nWave agents, commands, skills, and templates from YAML front-matter,
resolves cross-references, and renders navigable Markdown reference pages.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import yaml


# Ensure THIS worktree's project root wins when invoked as a standalone script.
# Editable environments may already append the worktree root after site-packages;
# membership alone is therefore insufficient: ``scripts.shared`` would resolve
# the stale installed projection/filter catalog before the local SSOT.
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root in sys.path:
    sys.path.remove(_project_root)
sys.path.insert(0, _project_root)
# Also expose src/ so `des` resolves under bare python3 (pre-push hooks run
# `language: system` outside the uv venv). Guarded: src/ exists only in the
# dev repo — docgen.py never ships (absent from build_dist.py UTILITY_SCRIPTS
# and both wheel force-include maps), so installed layouts are unaffected.
_project_src = str(Path(_project_root) / "src")
if Path(_project_src).is_dir():
    if _project_src in sys.path:
        sys.path.remove(_project_src)
    sys.path.insert(0, _project_src)

from des._internal import subset_parser  # noqa: E402
from des.application.flavor_dispatcher import (  # noqa: E402
    resolve_mode_descriptor,
    resolve_skill_load_set,
)
from des.application.workflow_mode import resolve_workflow_mode  # noqa: E402
from des.cli.__main__ import _REGISTRY  # noqa: E402
from des.domain.atdd_pure_phases import (  # noqa: E402
    CANONICAL_PHASES,
    normalize_phase_token,
)
from scripts.shared.agent_catalog import (  # noqa: E402
    build_ownership_map,
    detect_command_skills,
    is_public_agent,
    is_public_skill,
    load_public_agents,
)


# Public source repo, for linking released skills to browsable source.
GITHUB_REPO = "https://github.com/nWave-ai/nWave"


class DocgenError(Exception):
    """Raised for any data integrity issue — malformed YAML, missing fields, broken refs."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
class Agent(TypedDict):
    name: str
    description: str
    model: str
    tools: list[str]
    max_turns: int
    skills: list[str]
    source_path: str
    wave: str
    commands: list[str]


class Command(TypedDict):
    name: str
    description: str
    argument_hint: str
    agents: list[str]
    source_path: str


class Skill(TypedDict):
    name: str
    description: str
    agent_dir: str
    source_path: str


class Template(TypedDict):
    name: str
    type: str
    description: str
    version: str
    source_path: str


# ---------------------------------------------------------------------------
# YAML front-matter parser (no pyyaml dependency — front-matter is simple)
# ---------------------------------------------------------------------------
_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?\n)---", re.DOTALL)


def parse_front_matter(path: Path) -> dict:
    """Extract YAML front-matter as a flat dict. Supports scalar and list values."""
    text = path.read_text(encoding="utf-8")
    m = _FRONT_MATTER_RE.match(text)
    if not m:
        raise DocgenError(f"Missing YAML front-matter in {path}")
    result: dict = {}
    current_key: str | None = None
    current_list: list[str] | None = None
    for line in m.group(1).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        list_match = re.match(r"^\s+-\s+(.+)$", line)
        if list_match and current_key is not None:
            if current_list is None:
                current_list = []
                result[current_key] = current_list
            current_list.append(list_match.group(1).strip())
            continue
        kv_match = re.match(r"^(\w[\w-]*):\s*(.*?)$", line)
        if kv_match:
            current_key = kv_match.group(1)
            val = kv_match.group(2).strip().strip('"').strip("'")
            current_list = None
            if val:
                result[current_key] = val
            continue
    return result


def require_fields(data: dict, fields: list[str], path: Path) -> None:
    """Raise DocgenError if any required field is missing."""
    missing = [f for f in fields if f not in data]
    if missing:
        raise DocgenError(f"Missing required fields {missing} in {path}")


# ---------------------------------------------------------------------------
# Stage 1: Scan
# ---------------------------------------------------------------------------
def scan(root: Path, *, public_only: bool = False) -> dict[str, list[Path]]:
    """Discover artifact files grouped by type.

    When *public_only* is True, private agents and their skills are excluded
    using the same shared catalog logic as the build and install pipelines.
    """
    nwave = root / "nWave"

    public_agents: set[str] = set()
    if public_only:
        public_agents = load_public_agents(nwave)

    agents = sorted((nwave / "agents").glob("*.md"))
    if public_agents:
        agents = [a for a in agents if is_public_agent(a.name, public_agents)]

    commands = sorted((nwave / "tasks" / "nw").glob("*.md"))

    skills_dir = nwave / "skills"
    skill_dirs = sorted(d for d in skills_dir.iterdir() if d.is_dir())
    if public_agents:
        skill_dirs = [d for d in skill_dirs if is_public_skill(d.name, public_agents)]
    skills = sorted(md for d in skill_dirs for md in d.rglob("*.md"))

    templates = sorted(
        p for p in (nwave / "templates").glob("*.yaml") if not p.name.startswith(".")
    )
    return {
        "agents": agents,
        "commands": commands,
        "skills": skills,
        "templates": templates,
    }


# ---------------------------------------------------------------------------
# Stage 2: Extract
# ---------------------------------------------------------------------------
def extract_agent(path: Path) -> Agent:
    fm = parse_front_matter(path)
    require_fields(fm, ["name", "description"], path)
    tools_raw = fm.get("tools", "")
    tools = (
        [t.strip() for t in tools_raw.split(",")]
        if isinstance(tools_raw, str)
        else tools_raw
    )
    skills_raw = fm.get("skills", [])
    if isinstance(skills_raw, str):
        skills_raw = [skills_raw]
    skills = [s.split("#")[0].strip() for s in skills_raw]
    return Agent(
        name=fm["name"],
        description=fm["description"],
        model=fm.get("model", "inherit"),
        tools=tools,
        max_turns=int(fm.get("maxTurns", fm.get("max_turns", 0))),
        skills=skills,
        source_path=str(path),
    )


def extract_command(path: Path) -> Command:
    fm = parse_front_matter(path)
    require_fields(fm, ["description"], path)
    # Extract agent references from command body
    text = path.read_text(encoding="utf-8")
    agent_refs = sorted(set(re.findall(r"\bnw-[a-z]+-?[a-z]*(?:-[a-z]+)*", text)))
    return Command(
        name=path.stem,
        description=fm["description"].strip('"').strip("'"),
        argument_hint=fm.get("argument-hint", fm.get("argument_hint", "")),
        agents=agent_refs,
        source_path=str(path),
    )


def _infer_skill_from_content(path: Path) -> dict:
    """Infer name and description from H1 heading and first paragraph."""
    text = path.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    name = path.stem
    description = ""
    for i, line in enumerate(lines):
        h1 = re.match(r"^#\s+(.+)$", line)
        if h1:
            name = h1.group(1).strip()
            # First non-empty line after heading is description
            for subsequent in lines[i + 1 :]:
                stripped = subsequent.strip()
                if (
                    stripped
                    and not stripped.startswith("#")
                    and not stripped.startswith("Cross-ref")
                ):
                    description = stripped
                    break
            break
    return {"name": path.stem, "description": description or name}


def extract_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    if _FRONT_MATTER_RE.match(text):
        fm = parse_front_matter(path)
        require_fields(fm, ["name", "description"], path)
    else:
        fm = _infer_skill_from_content(path)
    return Skill(
        name=fm["name"],
        description=fm["description"],
        agent_dir=path.parent.name,
        source_path=str(path),
    )


def _parse_yaml_keys(path: Path) -> dict:
    """Parse top-level scalar keys from a YAML file (with or without front-matter)."""
    text = path.read_text(encoding="utf-8")
    m = _FRONT_MATTER_RE.match(text)
    content = m.group(1) if m else text
    result: dict = {}
    for line in content.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        kv = re.match(r"^(\w[\w_-]*):\s*[\"']?([^\"'\n]+?)[\"']?\s*$", line)
        if kv:
            result[kv.group(1)] = kv.group(2).strip()
    return result


def extract_template(path: Path) -> Template:
    fm = _parse_yaml_keys(path)
    desc = fm.get("description", fm.get("template_name", fm.get("Purpose", "")))
    if not desc:
        # Use first comment line as description
        for line in path.read_text(encoding="utf-8").splitlines():
            comment = re.match(r"^#\s*(.+)$", line)
            if comment and not comment.group(1).startswith("="):
                desc = comment.group(1).strip()
                break
    if not desc:
        raise DocgenError(f"Cannot determine description for template {path}")
    return Template(
        name=path.stem,
        type=fm.get("template_type", fm.get("type", "unknown")),
        description=desc,
        version=fm.get("version", fm.get("template_version", "")),
        source_path=str(path),
    )


def extract_all(paths: dict[str, list[Path]]) -> dict[str, list]:
    return {
        "agents": [extract_agent(p) for p in paths["agents"]],
        "commands": [extract_command(p) for p in paths["commands"]],
        "skills": [extract_skill(p) for p in paths["skills"]],
        "templates": [extract_template(p) for p in paths["templates"]],
    }


# ---------------------------------------------------------------------------
# Stage 3: Enrich (cross-references)
# ---------------------------------------------------------------------------
# Patterns to detect wave from agent descriptions.
# Uses "X wave" phrase matching to avoid substring false positives
# (e.g., "product discovery" should not match DISCOVER wave).
_WAVE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bDISCOVER(?:Y)?\s+wave\b", re.IGNORECASE), "DISCOVER"),
    (re.compile(r"\bDISCUSS\s+wave\b", re.IGNORECASE), "DISCUSS"),
    (re.compile(r"\bSPIKE\s+wave\b", re.IGNORECASE), "SPIKE"),
    (re.compile(r"\bDISTILL\s+wave\b", re.IGNORECASE), "DISTILL"),
    (re.compile(r"\bDESIGN\s+wave\b", re.IGNORECASE), "DESIGN"),
    (re.compile(r"\bDELIVER\s+wave\b", re.IGNORECASE), "DELIVER"),
    (re.compile(r"\bDEVOPS?\s+wave\b", re.IGNORECASE), "DEVOPS"),
]


def _load_wave_order(root: Path | None = None) -> list[str]:
    """Read wave_phases from framework-catalog.yaml (SSOT) and append 'Other'."""
    if root is None:
        root = Path(__file__).resolve().parent.parent
    catalog_path = root / "nWave" / "framework-catalog.yaml"
    text = catalog_path.read_text(encoding="utf-8")
    phases: list[str] = []
    in_wave_phases = False
    for line in text.splitlines():
        if line.startswith("wave_phases:"):
            in_wave_phases = True
            continue
        if in_wave_phases:
            item_match = re.match(r"^-\s+(\S+)$", line)
            if item_match:
                phases.append(item_match.group(1))
            else:
                break
    if not phases:
        raise DocgenError(f"Could not parse wave_phases from {catalog_path}")
    phases.append("Other")
    return phases


def _infer_wave(description: str) -> str:
    """Infer wave from agent description. Matches 'X wave' to avoid substring hits."""
    for pattern, wave in _WAVE_PATTERNS:
        if pattern.search(description):
            return wave
    return "Other"


def enrich(data: dict[str, list]) -> dict[str, list]:
    """Resolve cross-references and add derived fields."""
    # Build lookup: skill name, directory name, and agent-dir/skill-name all resolve.
    # In flat layout (nw-*/SKILL.md), agent_dir IS the directory name (e.g., "nw-ad-critique-dimensions").
    # Agent frontmatter references skills by directory name, not by frontmatter name.
    skill_lookup: set[str] = set()
    for s in data["skills"]:
        skill_lookup.add(s["name"])  # frontmatter name
        skill_lookup.add(s["agent_dir"])  # directory name (flat layout key)
        skill_lookup.add(
            f"{s['agent_dir']}/{s['name']}"
        )  # legacy: agent-dir/skill-name
    agent_names = {a["name"] for a in data["agents"]}
    agent_dirs = {a["name"].removeprefix("nw-") for a in data["agents"]}

    # Validate agent→skill refs
    for agent in data["agents"]:
        for skill_ref in agent["skills"]:
            if skill_ref not in skill_lookup:
                raise DocgenError(
                    f"Agent '{agent['name']}' references skill '{skill_ref}' which does not exist"
                )

    # Validate skill→agent refs (parent dir must match an agent)
    # In flat layout (nw-*/SKILL.md), agent_dir is the skill directory name — skip validation.
    # In old layout (agent-name/skill.md), agent_dir must match an agent.
    shared_skill_dirs = {"common"}
    for skill in data["skills"]:
        if skill["agent_dir"] in shared_skill_dirs:
            continue
        if skill["agent_dir"].startswith("nw-"):
            continue  # flat layout: skill dir is standalone, not agent-named
        if skill["agent_dir"] not in agent_dirs:
            raise DocgenError(
                f"Skill '{skill['name']}' in dir '{skill['agent_dir']}' has no matching agent"
            )

    # Enrich: infer wave for each agent
    for agent in data["agents"]:
        agent["wave"] = _infer_wave(agent["description"])

    # Enrich: reviewer agents inherit parent agent's wave
    agent_wave = {a["name"]: a["wave"] for a in data["agents"]}
    for agent in data["agents"]:
        if agent["wave"] == "Other" and agent["name"].endswith("-reviewer"):
            parent = agent["name"].removesuffix("-reviewer")
            if parent in agent_wave and agent_wave[parent] != "Other":
                agent["wave"] = agent_wave[parent]

    # Enrich: filter command agent refs to only valid agent names
    for cmd in data["commands"]:
        cmd["agents"] = [a for a in cmd["agents"] if a in agent_names]

    # Enrich: build agent→commands reverse mapping
    agent_commands: dict[str, list[str]] = {}
    for cmd in data["commands"]:
        for agent_name in cmd["agents"]:
            agent_commands.setdefault(agent_name, []).append(cmd["name"])
    for agent in data["agents"]:
        agent["commands"] = sorted(set(agent_commands.get(agent["name"], [])))

    return data


# ---------------------------------------------------------------------------
# Stage 4: Render
# ---------------------------------------------------------------------------
def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _skills_for_agent(agent: Agent, skills: list[Skill]) -> list[Skill]:
    """Return skills referenced by an agent, matching both 'name' and 'dir/name' forms."""
    skill_refs = set(agent["skills"])
    result = []
    for s in skills:
        if s["name"] in skill_refs or f"{s['agent_dir']}/{s['name']}" in skill_refs:
            result.append(s)
    return result


def released_skill_dirs(root: Path | None) -> set[str] | None:
    """Skill directory names that survive the public release (the "released" set).

    Consults the SAME catalog logic the release pipeline's strip_private_agents
    uses (public agents + frontmatter ownership map + command skills). Returns
    ``None`` when no catalog is available (e.g. a synthetic test tree), meaning
    "treat every skill as released".
    """
    if root is None:
        return None
    nwave = root / "nWave"
    public_agents = load_public_agents(nwave, strict=False)
    if not public_agents:
        return None  # catalog absent — caller treats all as released
    ownership = build_ownership_map(nwave / "agents")
    command_skills = detect_command_skills(nwave / "skills")
    dirs: set[str] = set()
    for d in (nwave / "skills").iterdir() if (nwave / "skills").is_dir() else []:
        if d.is_dir() and is_public_skill(
            d.name, public_agents, ownership, command_skills
        ):
            dirs.add(d.name)
    return dirs


def skill_slug(skill: Skill) -> str:
    """Stable, unique in-site slug for a skill page (under reference/skills/).

    nWave/skills/nw-divio-framework/SKILL.md -> "nw-divio-framework"
    nWave/skills/crafter/tdd.md              -> "crafter-tdd"
    """
    parts = Path(skill["source_path"]).with_suffix("").parts
    if "skills" in parts:
        sub = list(parts[parts.index("skills") + 1 :])
    else:
        sub = [skill["agent_dir"], Path(skill["source_path"]).stem]
    if sub and sub[-1] == "SKILL":
        sub = sub[:-1] or [skill["agent_dir"]]
    return "-".join(sub)


def _skill_source_url(skill: Skill) -> str:
    """Browsable GitHub blob URL (at main) for a skill's source file."""
    parts = Path(skill["source_path"]).parts
    if "nWave" in parts:
        rel = "/".join(parts[parts.index("nWave") :])
    else:
        rel = f"nWave/skills/{skill['agent_dir']}/{Path(skill['source_path']).name}"
    return f"{GITHUB_REPO}/blob/main/{rel}"


def _is_released(skill: Skill, released: set[str] | None) -> bool:
    """A skill is released when no catalog is loaded (None) or its dir is public."""
    return released is None or skill["agent_dir"] in released


def skill_ref(skill: Skill, released: set[str] | None, *, in_skills_dir: bool) -> str:
    """Link target for a skill from an agent page or the skills index.

    Released skills get an in-site reference page (resolves on the published
    site). Private skills — whose referencing agent page is itself stripped
    from the public repo — link to source instead, so no private skill page is
    ever emitted into the public-synced docs/reference tree.
    """
    if _is_released(skill, released):
        return (
            f"{skill_slug(skill)}.md"
            if in_skills_dir
            else f"../skills/{skill_slug(skill)}.md"
        )
    name = "SKILL" if skill["agent_dir"].startswith("nw-") else skill["name"]
    return f"../../../nWave/skills/{skill['agent_dir']}/{name}.md"


def render_skill_detail(skill: Skill, used_by: list[str]) -> str:
    """Render a per-skill reference page (emitted only for released skills)."""
    lines = [f"# {skill['name']}", "", skill["description"], ""]
    if used_by:
        agent_links = ", ".join(f"[{a}](../agents/{a}.md)" for a in sorted(used_by))
        lines += [f"**Used by:** {agent_links}", ""]
    lines += [
        f"**Source:** [{Path(skill['source_path']).name} on GitHub]"
        f"({_skill_source_url(skill)})",
        "",
    ]
    return "\n".join(lines)


def render_master_index(data: dict[str, list]) -> str:
    return "\n".join(
        [
            "# nWave Reference",
            "",
            f"Auto-generated documentation for {len(data['agents'])} agents, "
            f"{len(data['commands'])} commands, {len(data['skills'])} skills, "
            f"and {len(data['templates'])} templates.",
            "",
            "## Contents",
            "",
            f"- [Agents](agents/index.md) ({len(data['agents'])})",
            f"- [Commands](commands/index.md) ({len(data['commands'])})",
            f"- [Skills](skills/index.md) ({len(data['skills'])})",
            f"- [Templates](templates/index.md) ({len(data['templates'])})",
            "",
            "## CLI & configuration references",
            "",
            "Hand-authored reference for the CLI and configuration files:",
            "",
            "- [CLI Reference](cli.md) — the `nwave-ai` command and its subcommands",
            "- [Global Config Reference](global-config.md) — "
            "`~/.nwave/global-config.json` keys",
            "- [Outcomes CLI Reference](outcomes-cli.md) — `nwave-ai outcomes …`",
            "- [DES Markers Reference](des-markers.md) — DES task-prompt markers",
            "- [Feature-delta Format](feature-format.md) — feature-delta.md schema",
            "",
        ]
    )


def render_agents_index(agents: list[Agent], skills: list[Skill]) -> str:
    lines = ["# Agents", ""]
    # Group by wave
    by_wave: dict[str, list[Agent]] = {}
    for a in agents:
        by_wave.setdefault(a.get("wave", "Other"), []).append(a)
    for wave in _load_wave_order():
        wave_agents = by_wave.get(wave, [])
        if not wave_agents:
            continue
        lines.append(f"## {wave}")
        lines.append("")
        rows = []
        for a in sorted(wave_agents, key=lambda x: x["name"]):
            agent_skills = _skills_for_agent(a, skills)
            link = f"[{a['name']}]({a['name']}.md)"
            rows.append([link, a["description"], str(len(agent_skills))])
        lines.append(_md_table(["Name", "Description", "Skills"], rows))
        lines.append("")
    # All Agents reference table
    lines.append("## All Agents")
    lines.append("")
    all_rows = []
    for a in sorted(agents, key=lambda x: x["name"]):
        agent_skills = _skills_for_agent(a, skills)
        link = f"[{a['name']}]({a['name']}.md)"
        wave = a.get("wave", "Other")
        all_rows.append([link, wave, a["description"], str(len(agent_skills))])
    lines.append(_md_table(["Name", "Wave", "Description", "Skills"], all_rows))
    lines.append("")
    return "\n".join(lines)


def render_agent_detail(
    agent: Agent, skills: list[Skill], released: set[str] | None = None
) -> str:
    agent_skills = _skills_for_agent(agent, skills)
    wave = agent.get("wave", "Other")
    commands = agent.get("commands", [])
    lines = [
        f"# {agent['name']}",
        "",
        agent["description"],
        "",
        f"**Wave:** {wave}",
        f"**Model:** {agent['model']}",
        f"**Max turns:** {agent['max_turns']}",
        f"**Tools:** {', '.join(agent['tools'])}",
        "",
    ]
    if commands:
        lines.append("## Commands")
        lines.append("")
        for cmd_name in commands:
            lines.append(f"- [`/nw-{cmd_name}`](../commands/index.md)")
        lines.append("")
    if agent_skills:
        lines.append("## Skills")
        lines.append("")
        for s in sorted(agent_skills, key=lambda x: x["name"]):
            skill_path = skill_ref(s, released, in_skills_dir=False)
            lines.append(f"- [{s['name']}]({skill_path}) — {s['description']}")
        lines.append("")
    return "\n".join(lines)


def render_commands_index(commands: list[Command]) -> str:
    rows = []
    for c in sorted(commands, key=lambda x: x["name"]):
        agent_links = ", ".join(f"[{a}](../agents/{a}.md)" for a in c.get("agents", []))
        rows.append(
            [f"`/nw-{c['name']}`", c["description"], agent_links, c["argument_hint"]]
        )
    table = _md_table(["Command", "Description", "Agents", "Arguments"], rows)
    return f"# Commands\n\n{table}\n"


def render_skills_index(skills: list[Skill], released: set[str] | None = None) -> str:
    lines = ["# Skills", ""]
    by_agent: dict[str, list[Skill]] = {}
    # List released skills only — private skill names/descriptions must not
    # reach the public-synced docs/reference tree.
    for s in skills:
        if _is_released(s, released):
            by_agent.setdefault(s["agent_dir"], []).append(s)
    for agent_dir in sorted(by_agent):
        if agent_dir == "common":
            lines.append("## Shared Skills")
        else:
            # In flat layout, agent_dir is the skill directory (nw-prefixed).
            # Don't double-prefix with nw-.
            display_name = (
                agent_dir if agent_dir.startswith("nw-") else f"nw-{agent_dir}"
            )
            lines.append(f"## {display_name}")
        lines.append("")
        for s in sorted(by_agent[agent_dir], key=lambda x: x["name"]):
            skill_path = skill_ref(s, released, in_skills_dir=True)
            lines.append(f"- [{s['name']}]({skill_path}) — {s['description']}")
        lines.append("")
    return "\n".join(lines)


def render_templates_index(templates: list[Template]) -> str:
    rows = []
    for t in sorted(templates, key=lambda x: x["name"]):
        rows.append([t["name"], t["type"], t["description"]])
    table = _md_table(["Name", "Type", "Description"], rows)
    return f"# Templates\n\n{table}\n"


def render(data: dict[str, list], *, root: Path | None = None) -> dict[str, str]:
    """Render all pages. Returns {relative_path: content}."""
    # The "released" (public) skill set drives which skills get an in-site page.
    # Released skills are linked in-site (so links resolve on the published
    # site); private skills link to source and get NO page — keeping private
    # skill names/descriptions out of the public-synced docs/reference tree.
    released = released_skill_dirs(root)
    # Public agent names, to keep private agent names off public skill pages.
    public_agents = load_public_agents(root / "nWave", strict=False) if root else set()

    pages: dict[str, str] = {}
    pages["index.md"] = render_master_index(data)
    pages["agents/index.md"] = render_agents_index(data["agents"], data["skills"])
    pages["commands/index.md"] = render_commands_index(data["commands"])
    pages["skills/index.md"] = render_skills_index(data["skills"], released)
    pages["templates/index.md"] = render_templates_index(data["templates"])

    for agent in data["agents"]:
        filename = f"agents/{agent['name']}.md"
        pages[filename] = render_agent_detail(agent, data["skills"], released)

    # Per-skill reference pages — released skills only. "Used by" lists public
    # agents only: a released skill page ships to the public repo, so naming a
    # private agent there would leak it (and link to a stripped agent page).
    used_by: dict[str, list[str]] = {}
    for agent in data["agents"]:
        if public_agents and not is_public_agent(f"{agent['name']}.md", public_agents):
            continue
        for s in _skills_for_agent(agent, data["skills"]):
            used_by.setdefault(skill_slug(s), []).append(agent["name"])
    for s in data["skills"]:
        if not _is_released(s, released):
            continue
        slug = skill_slug(s)
        pages[f"skills/{slug}.md"] = render_skill_detail(s, used_by.get(slug, []))

    return pages


# ---------------------------------------------------------------------------
# Stage 5: Write
# ---------------------------------------------------------------------------
def write_pages(pages: dict[str, str], output_dir: Path) -> None:
    """Write pages to output_dir surgically.

    Files in pages.keys() are created or overwritten with the new content.
    Files NOT in pages.keys() (foreign / hand-authored / out-of-band) are
    left untouched. output_dir is created if it does not yet exist.

    This replaces the prior shutil.rmtree-based regeneration which destroyed
    any file under output_dir that the renderer did not reproduce. See
    docs/analysis/rca-pre-push-hook-untracked-deletion-2026-05-06.md for the
    RCA that motivated this surgical-write design.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    for rel_path, content in pages.items():
        full_path = output_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")


def check_pages(pages: dict[str, str], output_dir: Path) -> list[str]:
    """Return list of stale/missing files. Empty = up to date."""
    stale: list[str] = []
    for rel_path, content in pages.items():
        full_path = output_dir / rel_path
        if not full_path.exists():
            stale.append(f"missing: {rel_path}")
        elif full_path.read_text(encoding="utf-8") != content:
            stale.append(f"stale: {rel_path}")
    return stale


# ---------------------------------------------------------------------------
# GENERATED region projection (mode-registry-single-locus slice-02)
#
# Marker grammar per the DESIGN SSOT (analysis §2.3.2):
#   <!-- GENERATED:<region-id> START ... --> body <!-- GENERATED:<region-id> END -->
#
# The mode registry (`nWave/flavors/*.yaml`) is the sole author of every
# region body; assets carry projections only. Region read APIs are the
# flavor_dispatcher seams (`resolve_skill_load_set`, `resolve_mode_descriptor`)
# — one registry-read SSOT, two consumers: gates + docgen.
# ---------------------------------------------------------------------------
_GENERATED_REGION_RE = re.compile(
    r"<!--\s*GENERATED:(?P<region_id>[a-z][a-z0-9-]*)\s+START[^>]*-->\n"
    r"(?P<body>.*?)"
    r"<!--\s*GENERATED:(?P=region_id)\s+END\s*-->",
    re.DOTALL,
)


@dataclass(frozen=True)
class AssetProjection:
    """One asset's re-rendered GENERATED-region state vs what is on disk."""

    path: Path
    current_text: str
    projected_text: str

    @property
    def stale(self) -> bool:
        return self.current_text != self.projected_text


def _declared_flavor_ids(flavors_dir: Path) -> list[str]:
    """Every declared mode, one per flavor file (schema file excluded)."""
    return sorted(
        p.stem for p in flavors_dir.glob("*.yaml") if not p.name.startswith("_")
    )


# A region's marker DECLARES where its body comes from; a marker naming a source
# that did not produce the body is a false fact shipped inside generated prose,
# so each region names its own source instead of inheriting the flavors default.
_REGION_SOURCE_OF_TRUTH = {
    "des-command-catalog": "src/des/cli/__main__.py::_REGISTRY",
}
_DEFAULT_REGION_SOURCE_OF_TRUTH = "nWave/flavors/*.yaml"


def _generated_region(region_id: str, body: str) -> str:
    """The canonical full region text (markers + body) docgen owns."""
    source = _REGION_SOURCE_OF_TRUTH.get(region_id, _DEFAULT_REGION_SOURCE_OF_TRUTH)
    return (
        f"<!-- GENERATED:{region_id} START — source of truth: "
        f"{source}; do not hand-edit (docgen renders this region) -->\n"
        f"{body}\n"
        f"<!-- GENERATED:{region_id} END -->"
    )


def _skill_load_set_body(agent_id: str, flavors_dir: Path) -> str:
    """Render the per-mode conditional-skill directive for one agent.

    Body content comes from the slice-01 registry-read seam
    `resolve_skill_load_set` — never a second YAML read, never a baked table.
    """
    lines = [
        "Conditional skills by active workflow mode — projected from the mode",
        "registry `skill_load_set` via `flavor_dispatcher.resolve_skill_load_set`;",
        "re-render with `python scripts/docgen.py`:",
        "",
    ]
    for flavor_id in _declared_flavor_ids(flavors_dir):
        skills = resolve_skill_load_set(agent_id, flavor_id, flavors_dir=flavors_dir)
        rendered = ", ".join(f"`{skill}`" for skill in skills) or "(none)"
        lines.append(f"- `{flavor_id}`: {rendered}")
    return "\n".join(lines)


def _mode_descriptor_body(flavors_dir: Path) -> str:
    """Render one descriptor + DELIVER phase shape per declared mode."""
    lines: list[str] = []
    for flavor_id in _declared_flavor_ids(flavors_dir):
        mode = resolve_mode_descriptor(flavor_id, flavors_dir=flavors_dir)
        lines.append(f"- `{flavor_id}` — {mode.descriptor}")
        lines.append(f"  Deliver phase shape: `{mode.deliver_phase_shape}`")
    return "\n".join(lines)


def _module_first_docstring_line(module_path: str) -> str:
    """First line of *module_path*'s module docstring, read via ``ast.parse``
    on its source file under ``src/`` — parse only, NEVER import-and-execute
    (DD-10; a registry target module may run CLI argument parsing, ledger
    writes, etc. as import-time side effects)."""
    file_path = Path(_project_src).joinpath(*module_path.split(".")).with_suffix(".py")
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    doc = ast.get_docstring(tree)
    if not doc:
        raise DocgenError(
            f"module {module_path} ({file_path}) carries no module docstring — "
            "the des-command-catalog GENERATED region needs one to render a "
            "Description cell; add a one-line module docstring"
        )
    return doc.splitlines()[0]


def _command_catalog_body() -> str:
    """Render the ``des-command-catalog`` GENERATED region: one row per
    ``des.cli.__main__._REGISTRY`` entry (declaration order), Description
    sourced from that module's own first docstring line."""
    header = "| Verb | Module | Description |"
    sep = "| --- | --- | --- |"
    rows = [
        f"| `{row.name}` | `{row.module_path}` | "
        f"{_module_first_docstring_line(row.module_path)} |"
        for row in _REGISTRY
    ]
    return "\n".join([header, sep, *rows])


def _render_region_body(region_id: str, asset_path: Path, flavors_dir: Path) -> str:
    if region_id == "skill-load-set":
        return _skill_load_set_body(asset_path.stem, flavors_dir)
    if region_id == "mode-descriptor":
        return _mode_descriptor_body(flavors_dir)
    if region_id == "des-command-catalog":
        return _command_catalog_body()
    raise DocgenError(
        f"Unknown GENERATED region id '{region_id}' in {asset_path} — "
        "refusing to serve a region no renderer owns"
    )


def _project_asset(path: Path, text: str, flavors_dir: Path) -> AssetProjection:
    def _replace(match: re.Match[str]) -> str:
        region_id = match.group("region_id")
        return _generated_region(
            region_id, _render_region_body(region_id, path, flavors_dir)
        )

    return AssetProjection(
        path=path,
        current_text=text,
        projected_text=_GENERATED_REGION_RE.sub(_replace, text),
    )


def project_generated_regions(
    root: Path, asset_paths: dict[str, list[Path]]
) -> list[AssetProjection]:
    """Re-render every GENERATED region across the scanned asset tree."""
    flavors_dir = root / "nWave" / "flavors"
    files = [
        *asset_paths["agents"],
        *asset_paths["commands"],
        *asset_paths["skills"],
    ]
    projections: list[AssetProjection] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if not _GENERATED_REGION_RE.search(text):
            continue
        projections.append(_project_asset(path, text, flavors_dir))
    return projections


def write_generated_regions(projections: list[AssetProjection]) -> None:
    """Write re-rendered regions in place (bounded change: regions only)."""
    for projection in projections:
        if projection.stale:
            projection.path.write_text(projection.projected_text, encoding="utf-8")


def _display_path(path: Path, root: Path) -> str:
    """*path* relative to *root* when it lives under it, else the raw path --
    a projection may legitimately name a file outside *root* (e.g. an
    isolated test working copy exercising the mechanism)."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def check_generated_regions(
    root: Path, projections: list[AssetProjection]
) -> list[str]:
    """Stale-asset list, each entry NAMING the drifted asset. Empty = fresh."""
    return [
        f"stale generated region: {_display_path(projection.path, root)}"
        for projection in projections
        if projection.stale
    ]


# ---------------------------------------------------------------------------
# Command front-matter projection (mode-registry-single-locus slice-03)
#
# The framework catalog (`commands:` in nWave/framework-catalog.yaml) is the
# sole author of every command guide's `description:` / `argument-hint:`
# front-matter values; the guides carry projections only. A catalog entry's
# existence IS the projection declaration — GENERATED markers cannot live
# inside YAML front-matter without corrupting the host's parse. Key↔file
# rule: catalog key underscores become filename hyphens. Equality contract:
# YAML-parsed value equality (quoting style belongs to the renderer; the
# parsed value is what the host consumes). Catalog entries with no guide
# file are skipped; guide files outside the catalog keep hand-authored
# front-matter, still guarded by extract_command's missing-description
# refusal.
# ---------------------------------------------------------------------------
_COMMAND_GUIDES_REL = Path("nWave") / "tasks" / "nw"

# (catalog field, front-matter field) pairs the catalog projects into guides.
_PROJECTED_COMMAND_FIELDS: tuple[tuple[str, str], ...] = (
    ("description", "description"),
    ("argument_hint", "argument-hint"),
)

_TOP_LEVEL_KEY_RE = re.compile(r"^\w[\w-]*:")


def _catalog_command_declarations(root: Path) -> dict:
    """The `commands:` section of the framework catalog, fully YAML-parsed."""
    catalog_path = root / "nWave" / "framework-catalog.yaml"
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    return catalog.get("commands", {})


def _front_matter_line(field: str, value: str) -> str:
    """One single-line front-matter entry whose YAML-parsed value is *value*."""
    return yaml.safe_dump(
        {field: value},
        default_flow_style=False,
        width=sys.maxsize,
        allow_unicode=True,
    ).strip()


def _replace_front_matter_field(
    lines: list[str], field: str, rendered: str
) -> list[str]:
    """Replace *field*'s line span (key line plus continuation lines) with
    *rendered*; append the entry when the guide does not carry the field yet."""
    span = _field_line_span(lines, field)
    if span is None:
        return [*lines, rendered]
    start, end = span
    return [*lines[:start], rendered, *lines[end:]]


def _field_line_span(lines: list[str], field: str) -> tuple[int, int] | None:
    for index, line in enumerate(lines):
        if not line.startswith(f"{field}:"):
            continue
        end = index + 1
        while end < len(lines) and not _TOP_LEVEL_KEY_RE.match(lines[end]):
            end += 1
        return index, end
    return None


def _project_guide_front_matter(
    path: Path, text: str, declared: dict
) -> AssetProjection:
    match = _FRONT_MATTER_RE.match(text)
    if match is None:
        raise DocgenError(f"Missing YAML front-matter in {path}")
    block = match.group(1)
    values = yaml.safe_load(block) or {}
    lines = block.splitlines()
    for catalog_field, front_matter_field in _PROJECTED_COMMAND_FIELDS:
        if catalog_field not in declared:
            continue
        if values.get(front_matter_field) == declared[catalog_field]:
            continue
        lines = _replace_front_matter_field(
            lines,
            front_matter_field,
            _front_matter_line(front_matter_field, declared[catalog_field]),
        )
    projected_block = "\n".join(lines) + "\n"
    projected = text[: match.start(1)] + projected_block + text[match.end(1) :]
    return AssetProjection(path=path, current_text=text, projected_text=projected)


def project_command_front_matter(root: Path) -> list[AssetProjection]:
    """Re-render catalog-authored front-matter for every declared command guide."""
    projections: list[AssetProjection] = []
    for command_key, declared in sorted(_catalog_command_declarations(root).items()):
        guide_path = root / _COMMAND_GUIDES_REL / f"{command_key.replace('_', '-')}.md"
        if not guide_path.exists():
            continue  # declared command without a guide file (e.g. update)
        text = guide_path.read_text(encoding="utf-8")
        projections.append(_project_guide_front_matter(guide_path, text, declared))
    return projections


def check_command_front_matter(
    root: Path, projections: list[AssetProjection]
) -> list[str]:
    """Stale-guide list, each entry NAMING the drifted guide. Empty = fresh."""
    return [
        f"stale command front-matter (catalog is the sole author): "
        f"{projection.path.relative_to(root)}"
        for projection in projections
        if projection.stale
    ]


# ---------------------------------------------------------------------------
# Resolver↔registry + registry↔runtime agreement (mode-registry-single-locus
# slice-05, Layer C / analysis §3.3)
#
# The elevated `docgen --check` leg: beyond "projection == source", it asserts
# the registry AGREES with the running system:
#   (1) the flavor declaring `default: true` equals
#       `workflow_mode.resolve_workflow_mode`'s absent-config default — closing
#       the historic two-default divergence mechanically;
#   (2) the default flavor's `deliver_phase_shape` names exactly the runtime
#       canonical DELIVER phases (`atdd_pure_phases.CANONICAL_PHASES`) in order
#       — closing the KEEP-row-10 registry↔runtime parity open leg.
# Refuses on drift, NAMING the disagreement (each entry carries the drifted
# field name so the operator can act). The write pass never invokes this — it
# is a `--check`-only agreement assertion, so a clean copy still writes/exits 0.
# ---------------------------------------------------------------------------
def _resolver_absent_config_default() -> str:
    """The mode the resolver returns for a project with no `.nwave/config.yaml`.

    Derived from the REAL resolver behaviour (a throwaway empty dir has no
    config), never a hand-restated constant — so the agreement leg cannot drift
    from the resolver.
    """
    with tempfile.TemporaryDirectory() as empty:
        return resolve_workflow_mode(Path(empty)).effective_mode


def _declared_phase_tokens(shape: str) -> tuple[str, ...]:
    """The ordered phase tokens a `deliver_phase_shape` string names."""
    return tuple(token.strip() for token in shape.split("->") if token.strip())


_DELIVER_PHASE_SHAPE_RE = re.compile(r"^deliver_phase_shape:\s*(.+)$", re.MULTILINE)


def _authoritative_phase_shape(flavor_file: Path) -> str | None:
    """The flavor's FIRST `deliver_phase_shape` declaration.

    A well-formed registry declares the field EXACTLY ONCE — that invariant
    is enforced fail-closed by the Layer-B gate (`mode_registry_completeness`
    refuses any flavor carrying a duplicate top-level mode-field declaration).
    Under that invariant first == only == the effective value the runtime
    reads, so this read names the registry's authoritative phase shape and an
    in-place drift is caught here. The duplicate-shadowing state (an appended
    second declaration that a last-wins parser would silently prefer) is NOT
    this leg's territory: it is refused by Layer B — the §3.4 orthogonality
    property (a one-layer bypass is caught by ≥1 of the other gates).
    """
    match = _DELIVER_PHASE_SHAPE_RE.search(flavor_file.read_text(encoding="utf-8"))
    if match is None:
        return None
    return match.group(1).strip().strip("'\"")


def check_registry_runtime_agreement(root: Path) -> list[str]:
    """Disagreement list (each NAMING the drifted field). Empty = in agreement.

    The Layer-C agreement leg (mode-registry-single-locus slice-05, analysis
    §3.3): asserts the registry AGREES with the running system —
      (1) the flavor declaring `default: true` equals the resolver's
          absent-config default;
      (2) that default flavor's authoritative `deliver_phase_shape` names
          exactly the runtime canonical DELIVER phases, in order.
    Pure read; never invoked by the write pass.
    """
    flavors_dir = root / "nWave" / "flavors"
    flavor_ids = _declared_flavor_ids(flavors_dir)
    disagreements: list[str] = []

    resolver_default = _resolver_absent_config_default()
    defaulting = [
        flavor_id
        for flavor_id in flavor_ids
        if subset_parser.load_file(flavors_dir / f"{flavor_id}.yaml").get("default")
        is True
    ]
    if defaulting != [resolver_default]:
        disagreements.append(
            "resolver↔registry disagreement: the resolver's absent-config "
            f"default is {resolver_default!r} but the flavor(s) declaring "
            f"`default: true` are {defaulting!r}"
        )

    if resolver_default in flavor_ids:
        shape = _authoritative_phase_shape(flavors_dir / f"{resolver_default}.yaml")
        declared = tuple(
            normalize_phase_token(token)
            for token in _declared_phase_tokens(shape or "")
        )
        if declared != tuple(CANONICAL_PHASES):
            disagreements.append(
                "registry↔runtime disagreement: the default flavor's "
                f"`deliver_phase_shape` names {list(declared)} but the running "
                f"system's canonical DELIVER phases are {list(CANONICAL_PHASES)}"
            )
    return disagreements


# ---------------------------------------------------------------------------
# Link validation
# ---------------------------------------------------------------------------
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def check_links(root: Path, dirs: list[str]) -> list[str]:
    """Validate markdown links in specified directories. Returns list of broken links."""
    broken: list[str] = []
    files_to_check: list[Path] = []

    for d in dirs:
        target = root / d
        if target.is_file():
            files_to_check.append(target)
        elif target.is_dir():
            files_to_check.extend(target.rglob("*.md"))

    for md_file in sorted(files_to_check):
        text = md_file.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in _MD_LINK_RE.finditer(line):
                target = match.group(2)
                # Skip external URLs, anchors-only, mailto
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                # Strip anchor from target
                target_path = target.split("#")[0]
                if not target_path:
                    continue
                # Resolve relative to the file's directory
                resolved = (md_file.parent / target_path).resolve()
                if not resolved.exists():
                    rel = md_file.relative_to(root)
                    broken.append(f"{rel}:{lineno}: broken link → {target}")
    return broken


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def run_pipeline(
    root: Path, output_dir: Path, *, public_only: bool = False
) -> dict[str, str]:
    """Execute full pipeline: scan → extract → enrich → render. Returns pages."""
    paths = scan(root, public_only=public_only)
    data = extract_all(paths)
    data = enrich(data)
    return render(data, root=root)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate nWave reference documentation"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help=("Root of the asset tree to scan and project (default: this repository)"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: docs/reference/)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if generated docs are up to date (exit 1 if stale)",
    )
    parser.add_argument(
        "--check-links",
        action="store_true",
        help="Validate markdown links in README and docs/ (exit 1 if broken)",
    )
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Exclude private agents and their skills from generated docs",
    )
    args = parser.parse_args(argv)

    root = args.root or Path(__file__).resolve().parent.parent
    output_dir = args.output_dir or root / "docs" / "reference"

    try:
        asset_paths = scan(root, public_only=args.public_only)
        projections = project_generated_regions(root, asset_paths)
        if not args.check:
            write_generated_regions(projections)
        front_matter_projections = project_command_front_matter(root)
        if not args.check:
            write_generated_regions(front_matter_projections)
        pages = run_pipeline(root, output_dir, public_only=args.public_only)
    except DocgenError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.check:
        stale = (
            check_generated_regions(root, projections)
            + check_command_front_matter(root, front_matter_projections)
            + check_registry_runtime_agreement(root)
            + check_pages(pages, output_dir)
        )
        if stale:
            print("Documentation is out of date:", file=sys.stderr)
            for s in stale:
                print(f"  {s}", file=sys.stderr)
            return 1
        print("Documentation is up to date.")
        return 0

    if args.check_links:
        broken = check_links(root, ["README.md", "docs/guides", "docs/reference"])
        if broken:
            print(f"Found {len(broken)} broken link(s):", file=sys.stderr)
            for b in broken:
                print(f"  {b}", file=sys.stderr)
            return 1
        print("All links valid.")
        return 0

    write_pages(pages, output_dir)
    print(f"Generated {len(pages)} pages in {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
