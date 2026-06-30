#!/usr/bin/env python3
"""Sweep the deprecated ``Task`` agent-dispatch tool -> ``Agent`` in nWave agent
frontmatter ``tools:`` lines.

SCOPE (deliberately narrow, deletion-safe): ONLY the ``tools:`` line of each
``nWave/agents/*.md``. It NEVER touches ``TaskCreate`` / ``TaskUpdate`` / ``TaskList`` /
``TaskStop`` / ``TaskGet`` / ``TaskOutput`` (the valid task-list tools), nor any prose,
code example (e.g. Scala ZIO ``Task[...]``), or hook-event reference (``PreToolUse:Task``).
The broader prose/skill dispatch-references are a separate, judgement-required pass.

Dry-run by default (prints the diff); pass ``--apply`` to write. Idempotent.
Run from repo root: ``python scripts/maintenance/sweep_task_to_agent_tools.py [--apply]``.
"""

from __future__ import annotations

import pathlib
import re
import sys


_AGENTS = pathlib.Path("nWave/agents")
_TASK = re.compile(
    r"\bTask\b"
)  # word-boundary -> never matches TaskCreate/TaskUpdate/...


def main() -> int:
    apply = "--apply" in sys.argv
    changed: list[tuple[str, str, str]] = []
    for f in sorted(_AGENTS.glob("*.md")):
        lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
        hit = False
        for i, ln in enumerate(lines):
            if ln.startswith("tools:") and _TASK.search(ln):
                new = _TASK.sub("Agent", ln)
                if new != ln:
                    changed.append((f.name, ln.strip(), new.strip()))
                    lines[i] = new
                    hit = True
        if hit and apply:
            f.write_text("".join(lines), encoding="utf-8")
    for name, before, after in changed:
        print(f"--- {name}\n  - {before}\n  + {after}\n")
    print(
        f"{len(changed)} agent file(s) {'APPLIED' if apply else 'WOULD CHANGE (dry-run)'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
