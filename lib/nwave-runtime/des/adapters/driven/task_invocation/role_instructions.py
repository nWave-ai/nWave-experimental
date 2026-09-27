"""Materialize declared role knowledge from the role's own asset tree."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


_SKILL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_INVOCATION = re.compile(r"Invoke (?:ONE )?Skill\(([A-Za-z0-9][A-Za-z0-9._-]*)\)")
_PREFIXES = ("~/.claude/skills/", "~/.agents/skills/")


def _declared_skills(text: str) -> tuple[str, ...]:
    lines = text.lstrip().splitlines()
    if not lines or lines[0].strip() != "---":
        return ()
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError(
            "Agent frontmatter has no closing delimiter; close it before loading skills."
        )
    frontmatter = "\n".join(lines[1:end])
    match = re.search(
        r"(?:^|[,{]\s*)skills\s*:\s*\[([^\]]*)\]", frontmatter, re.MULTILINE
    )
    if match is None:
        # The public role contract permits a block sequence too.  Do not try
        # to be a YAML parser: role skill names deliberately have a much
        # narrower grammar than YAML and this module ships without PyYAML.
        block = re.search(r"^skills\s*:\s*$", frontmatter, re.MULTILINE)
        if block is None:
            if re.search(r"(?:^|[,{]\s*)skills\s*:", frontmatter, re.MULTILINE):
                raise ValueError(
                    "Agent skills must be a bracketed or block list of plain skill directory names; correct the skills declaration."
                )
            return ()
        tail = frontmatter[block.end() :].splitlines()
        names: list[str] = []
        for line in tail:
            if not line.strip():
                continue
            item = re.fullmatch(r"\s+-\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*", line)
            if item is None:
                break
            names.append(item.group(1))
        if not names:
            raise ValueError(
                "Agent skills must be a bracketed or block list of plain skill directory names; correct the skills declaration."
            )
        return tuple(dict.fromkeys(names))

    raw_names = [name.strip() for name in match.group(1).split(",")]
    if not raw_names or any(
        not _SKILL_NAME.fullmatch(name) or name.isdecimal() for name in raw_names
    ):
        raise ValueError(
            "Agent skills must be a list of plain skill directory names; correct the skills declaration."
        )
    return tuple(dict.fromkeys(raw_names))


def _without_skills_key(text: str) -> str:
    """Remove the narrow, validated ``skills`` field without requiring PyYAML."""
    lines = text.splitlines(keepends=True)
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None or lines[first].strip() != "---":
        return text
    end = next(
        (i for i in range(first + 1, len(lines)) if lines[i].strip() == "---"), None
    )
    if end is None:
        return text

    frontmatter = "".join(lines[first + 1 : end])
    # Flow-map metadata is used by an existing compatibility fixture.  The
    # field itself has already passed the deliberately narrow parser above.
    frontmatter = re.sub(
        r"(\{|,)\s*skills\s*:\s*\[[^\]]*\]\s*(?=,|\})",
        lambda match: "{" if match.group(1) == "{" else "",
        frontmatter,
    )
    frontmatter_lines = frontmatter.splitlines(keepends=True)
    retained: list[str] = []
    skip_block_items = False
    for line in frontmatter_lines:
        if re.fullmatch(r"skills\s*:\s*\[[^\]]*\]\s*(?:\n)?", line):
            skip_block_items = False
            continue
        if re.fullmatch(r"skills\s*:\s*(?:\n)?", line):
            skip_block_items = True
            continue
        if skip_block_items and re.fullmatch(r"\s+-\s*[^\n]+(?:\n)?", line):
            continue
        skip_block_items = False
        retained.append(line)
    return "".join(lines[: first + 1]) + "".join(retained) + "".join(lines[end:])


def _skills_dir(spec: Path) -> Path:
    if spec.parent.name == "agents" and spec.parent.parent.name == "nWave":
        return spec.parent.parent / "skills"
    if spec.parent.name == "nw" and spec.parent.parent.name == "agents":
        return spec.parent.parent.parent / "skills"
    raise ValueError(
        f"Cannot resolve skills owned by {spec}; place the role under nWave/agents or agents/nw."
    )


def _portable_reads(text: str, directory: Path) -> str:
    text = _INVOCATION.sub(
        lambda match: f"Read {directory / match[1] / 'SKILL.md'}", text
    )
    for prefix in _PREFIXES:
        text = text.replace(prefix, str(directory) + "/")
    return text


def load_role_instructions(spec_path: Path, semantic_task: str | None = None) -> str:
    """Preload explicit frontmatter skills once; keep conditional loads conditional.

    No transitive preload or ambient installation fallback. The provider argv
    already records the complete resulting instructions as invocation evidence.
    """
    instructions = _expand(spec_path)
    if semantic_task != "expectation-charter":
        return instructions
    if spec_path.stem != "nw-product-owner":
        raise ValueError(
            "expectation-charter task requires the installed nw-product-owner"
        )
    skill = _skills_dir(spec_path.resolve()) / "nw-expectation-charter" / "SKILL.md"
    try:
        knowledge = skill.read_text(encoding="utf-8")
    except OSError as error:
        raise OSError(f"Cannot load installed charter knowledge at {skill}") from error
    return (
        instructions
        + f"\n<!-- TASK SKILL START: nw-expectation-charter; source: {skill} -->\n"
        + f"{knowledge}\n<!-- TASK SKILL END: nw-expectation-charter -->\n"
        + "\nFor this expectation-charter task, return only the closed structured "
        "qualitative charter answer. DES constructs Markdown and copies the "
        "caller's exact public recipe. Do not read product files or write a charter.\n"
    )


def _expand(spec_path: Path) -> str:
    text = spec_path.read_text(encoding="utf-8")
    skills = _declared_skills(text)
    if (
        not skills
        and not _INVOCATION.search(text)
        and not any(p in text for p in _PREFIXES)
    ):
        return text
    directory = _skills_dir(spec_path.resolve())
    sections = [_portable_reads(text, directory)]
    if skills:
        sections.append(
            "\n\nThe following skills are already loaded. Do not reload them. "
            "Apply their knowledge within this role's explicit scope and tool boundaries. "
            "Conditional references remain on demand; a general method does not expand your role.\n"
        )
    for name in skills:
        path = directory / name / "SKILL.md"
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            raise OSError(
                f"Cannot preload declared skill {name} at {path}; restore its readable SKILL.md or correct the role declaration."
            ) from error
        sections.append(
            f"\n<!-- PRELOADED SKILL START: {name}; source: {path} -->\n"
            f"Relative references in this skill resolve against {path.parent}.\n"
            f"{_portable_reads(content, directory)}\n"
            f"<!-- PRELOADED SKILL END: {name} -->\n"
        )
    return "".join(sections)


def render_installed_role(spec_path: Path, deployed_skills_root: str) -> str:
    """Self-contained installed snapshot: skills preloaded, ``skills:`` removed,
    conditional reads pointing at the deployed skills root."""
    text = _expand(spec_path)
    try:
        owned = str(_skills_dir(spec_path.resolve()))
    except ValueError:
        owned = None
    if owned:
        text = text.replace(owned, deployed_skills_root)
    return _without_skills_key(text)
