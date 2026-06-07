#!/usr/bin/env python3
"""Migrate nWave commands from tasks/nw/*.md to skills/nw-{name}/SKILL.md.

BREAKING CHANGE: /nw-deliver → /nw-deliver (colon → hyphen)

Command-skills get `user-invocable: true` in frontmatter.
Commands that had `disable-model-invocation: true` get `user-invocable: false`
(hidden from menu but still callable).

Usage:
    python scripts/migrate_commands_to_skills.py          # dry-run
    python scripts/migrate_commands_to_skills.py --apply   # write files
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def parse_command_frontmatter(content: str) -> tuple[dict[str, str], str] | None:
    """Parse YAML frontmatter and return (fields, body)."""
    if not content.startswith("---"):
        return None
    end = content.find("\n---\n", 3)
    if end == -1:
        return None

    fm_text = content[4:end]
    body = content[end + 5 :]  # skip \n---\n

    fields: dict[str, str] = {}
    for line in fm_text.splitlines():
        m = re.match(r"^(\S+):\s*(.*)", line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fields, body


def build_skill_frontmatter(name: str, fields: dict[str, str]) -> str:
    """Build skill frontmatter from command fields."""
    lines = ["---"]
    lines.append(f"name: {name}")
    lines.append(f'description: "{fields.get("description", "")}"')

    # Commands with disable-model-invocation were hidden → user-invocable: false
    # All others → user-invocable: true (visible in / menu)
    if fields.get("disable-model-invocation") == "true":
        lines.append("user-invocable: false")
    else:
        lines.append("user-invocable: true")

    if "argument-hint" in fields:
        hint = fields["argument-hint"]
        lines.append(f"argument-hint: '{hint}'")

    lines.append("---")
    return "\n".join(lines)


def update_body_references(body: str) -> str:
    """Update /nw-command references to /nw-command in body text."""
    # Replace /nw-name patterns with /nw-name
    body = re.sub(r"/nw:(\w[\w-]*)", r"/nw-\1", body)
    # Replace `nw-name` backtick patterns
    body = re.sub(r"`nw:(\w[\w-]*)`", r"`nw-\1`", body)
    # Replace /nw:* glob patterns
    body = body.replace("/nw:*", "/nw-*")
    return body


def migrate_command(
    cmd_file: Path, skills_dir: Path, *, apply: bool = False
) -> list[str]:
    """Migrate one command file to skill format. Returns change descriptions."""
    content = cmd_file.read_text(encoding="utf-8")
    result = parse_command_frontmatter(content)
    if result is None:
        return [f"  SKIP: no frontmatter in {cmd_file.name}"]

    fields, body = result
    cmd_name = cmd_file.stem  # e.g. "deliver"
    skill_name = f"nw-{cmd_name}"  # e.g. "nw-deliver"
    skill_dir = skills_dir / skill_name
    skill_file = skill_dir / "SKILL.md"

    changes = []

    # Check if skill already exists
    if skill_file.exists():
        changes.append(f"  OVERWRITE: {skill_name}/SKILL.md already exists")

    # Build new content
    new_fm = build_skill_frontmatter(skill_name, fields)
    updated_body = update_body_references(body)
    new_content = new_fm + "\n" + updated_body

    visibility = (
        "visible" if fields.get("disable-model-invocation") != "true" else "hidden"
    )
    changes.append(f"  {cmd_file.name} → {skill_name}/SKILL.md ({visibility})")

    if apply:
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(new_content, encoding="utf-8")

    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write files")
    parser.add_argument(
        "--commands-dir",
        type=Path,
        default=Path("nWave/tasks/nw"),
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=Path("nWave/skills"),
    )
    args = parser.parse_args()

    if not args.commands_dir.exists():
        print(f"Commands directory not found: {args.commands_dir}")
        return

    mode = "APPLYING" if args.apply else "DRY-RUN"
    print(f"{'=' * 70}")
    print(f"  Command → Skill Migration ({mode})")
    print(f"{'=' * 70}")

    commands = sorted(args.commands_dir.glob("*.md"))
    print(f"\n  Found {len(commands)} commands to migrate\n")

    migrated = 0
    for cmd_file in commands:
        changes = migrate_command(cmd_file, args.skills_dir, apply=args.apply)
        for c in changes:
            print(f"  {c}")
        if not any("SKIP" in c for c in changes):
            migrated += 1

    print(f"\n{'=' * 70}")
    print(f"  Migrated: {migrated}/{len(commands)}")
    if not args.apply and migrated > 0:
        print("  Run with --apply to write files.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
