#!/usr/bin/env python3
"""Fix agent skill paths from old nested layout to new flat layout.

Old layout: ~/.claude/skills/nw/{agent-name}/{skill-name}.md
New layout: ~/.claude/skills/nw-{skill-name}/SKILL.md

Reads each agent file in nWave/agents/*.md, parses the skills: frontmatter,
and replaces all old-style skill path references with new-style paths.

Usage:
    python scripts/fix_agent_skill_paths.py          # dry-run (show changes)
    python scripts/fix_agent_skill_paths.py --apply   # write changes to files
"""

import argparse
import re
import sys
from pathlib import Path


AGENTS_DIR = Path(__file__).resolve().parent.parent / "nWave" / "agents"


def parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from agent file content."""
    if not content.startswith("---"):
        return {}

    end = content.find("---", 3)
    if end == -1:
        return {}

    fm_text = content[3:end].strip()
    result = {}

    # Parse name
    name_match = re.search(r"^name:\s*(.+)$", fm_text, re.MULTILINE)
    if name_match:
        result["name"] = name_match.group(1).strip()

    # Parse skills list
    skills = []
    in_skills = False
    for line in fm_text.split("\n"):
        if line.strip().startswith("skills:"):
            in_skills = True
            continue
        if in_skills:
            stripped = line.strip()
            if stripped.startswith("- "):
                skill_name = stripped[2:].strip()
                skills.append(skill_name)
            elif stripped and not stripped.startswith("#"):
                # End of skills list (hit another key)
                in_skills = False
    result["skills"] = skills

    return result


def build_replacements(
    content: str, skills: list[str], agent_name: str
) -> list[tuple[str, str, str]]:
    """Build list of (old_text, new_text, description) replacements.

    Handles all known path patterns in agent files.
    """
    replacements = []

    # Derive the agent slug (remove nw- prefix for directory matching)
    # e.g., nw-software-crafter -> software-crafter
    agent_name.removeprefix("nw-")

    # Pattern 1: "Skills path: `~/.claude/skills/nw/{slug}/{skill-name}.md`"
    # e.g., Skills path: `~/.claude/skills/nw/software-crafter/{skill-name}.md`
    pattern1 = re.compile(r"Skills path: `~/.claude/skills/nw/[^`]+`")
    for match in pattern1.finditer(content):
        old = match.group(0)
        new = "Skills path: `~/.claude/skills/nw-{skill-name}/SKILL.md`"
        if old != new:
            replacements.append((old, new, "Skills path line"))

    # Pattern 1b: "Skills paths: `~/.claude/skills/nw/X/` and `~/.claude/skills/nw/Y/`"
    # e.g., nw-documentarist-reviewer has two paths
    pattern1b = re.compile(
        r"Skills paths: `~/.claude/skills/nw/[^`]+` and `~/.claude/skills/nw/[^`]+`"
    )
    for match in pattern1b.finditer(content):
        old = match.group(0)
        new = "Skills path: `~/.claude/skills/nw-{skill-name}/SKILL.md`"
        if old != new:
            replacements.append((old, new, "Multi-path Skills path line"))

    # Pattern 2b: "**How**: ... `~/.claude/skills/nw/X/` (desc) or `~/.claude/skills/nw/Y/` (desc)."
    # e.g., nw-functional-software-crafter has two path references
    # IMPORTANT: check multi-path BEFORE single-path to avoid partial matches
    pattern2b = re.compile(
        r"\*\*How\*\*: Use the Read tool to load files from `~/.claude/skills/nw/[^`]+`[^.\n]+`~/.claude/skills/nw/[^`]+`[^.\n]*\."
    )
    how_multipath_ranges = set()
    for match in pattern2b.finditer(content):
        old = match.group(0)
        new = "**How**: Use the Read tool to load skill files. Check `~/.claude/skills/nw-{skill-name}/SKILL.md` first; if not found, load from the project repo at `nWave/skills/nw-{skill-name}/SKILL.md`."
        if old != new:
            replacements.append((old, new, "**How** multi-path instruction line"))
            how_multipath_ranges.add((match.start(), match.end()))

    # Pattern 2: "**How**: Use the Read tool to load files from `~/.claude/skills/nw/{slug}/`"
    # This is the most common pattern across agents
    # Skip if already handled by multi-path pattern above
    pattern2 = re.compile(
        r"\*\*How\*\*: Use the Read tool to load files from `~/.claude/skills/nw/[^`]+`"
    )
    for match in pattern2.finditer(content):
        # Skip if this match falls within a multi-path match
        if any(start <= match.start() < end for start, end in how_multipath_ranges):
            continue
        old = match.group(0)
        new = "**How**: Use the Read tool to load skill files. Check `~/.claude/skills/nw-{skill-name}/SKILL.md` first; if not found, load from the project repo at `nWave/skills/nw-{skill-name}/SKILL.md`"
        if old != new:
            replacements.append((old, new, "**How** instruction line"))

    # Pattern 3: Lines like "- `~/.claude/skills/nw/{slug}/` -- description"
    # e.g., nw-software-crafter-reviewer has bullet points with paths
    pattern3 = re.compile(r"- `~/.claude/skills/nw/([^`]+)/`([^\n]*)")
    for match in pattern3.finditer(content):
        old = match.group(0)
        slug_in_path = match.group(1)
        description = match.group(2)
        new = f"- `~/.claude/skills/nw-{{skill-name}}/SKILL.md`{description}"
        if old != new:
            replacements.append((old, new, f"Bullet path reference ({slug_in_path})"))

    # Pattern 4: "Skills loaded from `~/.claude/skills/nw/{slug}/`"
    pattern4 = re.compile(r"Skills loaded from `~/.claude/skills/nw/[^`]+`")
    for match in pattern4.finditer(content):
        old = match.group(0)
        new = "Skills loaded from `~/.claude/skills/nw-{skill-name}/SKILL.md`"
        if old != new:
            replacements.append((old, new, "Skills loaded from line"))

    # Pattern 5: Standalone path refs like "from `~/.claude/skills/nw/{slug}/`"
    # in table cells, e.g., documentarist-reviewer table
    pattern5 = re.compile(r"`~/.claude/skills/nw/([^/`]+)/`")
    for match in pattern5.finditer(content):
        old = match.group(0)
        slug_in_path = match.group(1)
        # Skip if this match is part of a larger pattern already handled
        # (check surrounding context)
        start = match.start()
        line_start = content.rfind("\n", 0, start)
        line_end = content.find("\n", start)
        line = content[line_start + 1 : line_end if line_end != -1 else len(content)]

        # Skip lines already handled by other patterns
        if (
            "Skills path:" in line
            or "**How**:" in line
            or line.strip().startswith("- `~/.claude/skills")
        ):
            continue
        if "Skills loaded from" in line:
            continue

        new = "`~/.claude/skills/nw-{skill-name}/SKILL.md`"
        if old != new:
            replacements.append((old, new, f"Inline path reference to {slug_in_path}"))

    # Pattern 6: Multi-location "Skills are in two locations:" sections
    # e.g., nw-functional-software-crafter
    pattern6 = re.compile(
        r"- Shared TDD skills: `~/.claude/skills/nw/[^`]+`\n- FP-specific skills: `~/.claude/skills/nw/[^`]+`"
    )
    for match in pattern6.finditer(content):
        old = match.group(0)
        new = "- All skills: `~/.claude/skills/nw-{skill-name}/SKILL.md`"
        if old != new:
            replacements.append((old, new, "Multi-location skill paths"))

    # Pattern 6b: "Skills are in two locations:" line
    pattern6b = re.compile(r"Skills are in two locations:")
    for match in pattern6b.finditer(content):
        old = match.group(0)
        new = "Skills location:"
        if old != new:
            replacements.append((old, new, "Skills location header"))

    # Pattern 7: Inline "Load ... from `~/.claude/skills/nw/{slug}/`"
    pattern7 = re.compile(r"from `~/.claude/skills/nw/([^/`]+)/`\.? ")
    for match in pattern7.finditer(content):
        old = match.group(0)
        slug_in_path = match.group(1)
        # Skip if already handled by **How** pattern
        start = match.start()
        line_start = content.rfind("\n", 0, start)
        line_end = content.find("\n", start)
        line = content[line_start + 1 : line_end if line_end != -1 else len(content)]
        if "**How**:" in line:
            continue
        new = "from `~/.claude/skills/nw-{skill-name}/SKILL.md`. "
        if old != new:
            replacements.append(
                (old, new, f"Inline 'from' path reference ({slug_in_path})")
            )

    # Pattern 8: "Run `Glob(...)` ... Load ... from `~/.claude/skills/nw/{slug}/`."
    pattern8 = re.compile(r"from `~/.claude/skills/nw/([^`]+)/`\.")
    for match in pattern8.finditer(content):
        old = match.group(0)
        slug_in_path = match.group(1)
        # Skip if already handled
        start = match.start()
        line_start = content.rfind("\n", 0, start)
        line_end = content.find("\n", start)
        line = content[line_start + 1 : line_end if line_end != -1 else len(content)]
        if "**How**:" in line or "Skills path" in line:
            continue
        new = "from `~/.claude/skills/nw-{skill-name}/SKILL.md`."
        if old != new:
            replacements.append(
                (old, new, f"Trailing 'from' path reference ({slug_in_path})")
            )

    # Pattern 9: nw-researcher special case — "Write only to ... `~/.claude/skills/nw/{agent}/`"
    # This is a scope/output path, not a read path. Update to new structure.
    pattern9 = re.compile(r"`~/.claude/skills/nw/\{agent\}/`")
    for match in pattern9.finditer(content):
        old = match.group(0)
        new = "`nWave/skills/nw-{skill-name}/`"
        if old != new:
            replacements.append((old, new, "Output path reference (researcher)"))

    # Pattern 10: Table cell paths like "| `~/.claude/skills/nw/{slug}/` |"
    pattern10 = re.compile(r"\| `~/.claude/skills/nw/([^`]+)/` \|")
    for match in pattern10.finditer(content):
        old = match.group(0)
        slug_in_path = match.group(1)
        new = "| `~/.claude/skills/nw-{skill-name}/SKILL.md` |"
        if old != new:
            replacements.append(
                (old, new, f"Table cell path reference ({slug_in_path})")
            )

    # Deduplicate replacements (same old text might be matched multiple times)
    seen = set()
    unique = []
    for old, new, desc in replacements:
        if old not in seen:
            seen.add(old)
            unique.append((old, new, desc))

    return unique


def apply_replacements(content: str, replacements: list[tuple[str, str, str]]) -> str:
    """Apply all replacements to content."""
    result = content
    for old, new, _ in replacements:
        result = result.replace(old, new)
    return result


def process_agent(agent_path: Path, apply: bool) -> dict:
    """Process a single agent file. Returns report dict."""
    content = agent_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)

    agent_name = fm.get("name", agent_path.stem)
    skills = fm.get("skills", [])

    report = {
        "file": agent_path.name,
        "agent_name": agent_name,
        "skills_count": len(skills),
        "changes": [],
        "already_updated": False,
    }

    # Check if already using new-style paths (nw-agent-builder already updated)
    if "~/.claude/skills/nw/" not in content:
        report["already_updated"] = True
        return report

    replacements = build_replacements(content, skills, agent_name)

    if not replacements:
        report["already_updated"] = True
        return report

    for old, new, desc in replacements:
        report["changes"].append(
            {
                "description": desc,
                "old": old[:120] + ("..." if len(old) > 120 else ""),
                "new": new[:120] + ("..." if len(new) > 120 else ""),
            }
        )

    if apply:
        new_content = apply_replacements(content, replacements)
        agent_path.write_text(new_content, encoding="utf-8")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Fix agent skill paths from old nested layout to new flat layout."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write changes to files (default: dry-run)",
    )
    args = parser.parse_args()

    if not AGENTS_DIR.exists():
        print(f"ERROR: Agents directory not found: {AGENTS_DIR}", file=sys.stderr)
        sys.exit(1)

    agent_files = sorted(AGENTS_DIR.glob("*.md"))
    if not agent_files:
        print(f"ERROR: No .md files found in {AGENTS_DIR}", file=sys.stderr)
        sys.exit(1)

    mode = "APPLYING" if args.apply else "DRY-RUN"
    print(f"\n{'=' * 70}")
    print(f"  Agent Skill Path Fixer ({mode})")
    print(f"{'=' * 70}")
    print(f"  Agents directory: {AGENTS_DIR}")
    print(f"  Agent files found: {len(agent_files)}")
    print()

    total_changes = 0
    already_updated = 0
    files_changed = 0

    for agent_path in agent_files:
        report = process_agent(agent_path, args.apply)

        if report["already_updated"]:
            already_updated += 1
            continue

        if report["changes"]:
            files_changed += 1
            total_changes += len(report["changes"])
            print(f"  {report['file']} ({report['skills_count']} skills)")
            for change in report["changes"]:
                print(f"    [{change['description']}]")
                print(f"      - OLD: {change['old']}")
                print(f"      + NEW: {change['new']}")
            print()

    print(f"{'=' * 70}")
    print("  Summary:")
    print(f"    Files scanned:       {len(agent_files)}")
    print(f"    Already up-to-date:  {already_updated}")
    print(f"    Files to change:     {files_changed}")
    print(f"    Total replacements:  {total_changes}")
    if not args.apply and total_changes > 0:
        print("\n  Run with --apply to write changes to files.")
    elif args.apply and total_changes > 0:
        print("\n  Changes applied successfully.")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()
