#!/usr/bin/env python3
"""The ACTUATOR for ``des refactor --pile`` -- the executable you pass as ``--agent-cmd``.

WHY THIS EXISTS
    ``des refactor --pile`` is a complete drain mechanism (worktree-from-tip, per-worktree
    environment, green-to-green verification, merge-back, mandatory cleanup) whose last mile
    is a command it invokes per item. Until this script existed the only concrete values
    anyone could pass were ``true`` (in the acceptance tests) and placeholders in the docs,
    so the pile could never actually drain: the mechanism was wired, the actuator was absent.

CONTRACT (see ``des.adapters.driven.refactor.shell_agent_invocation_adapter``)
    * The harness probes the FIRST token with ``shutil.which``, so this file must stay
      executable and reachable from the repo root.
    * It substitutes ``{prompt}`` / ``{worktree}`` and runs the result with ``shell=True``
      and ``cwd`` ALREADY set to the isolated worktree -- you are inside the worktree when
      this runs, so it never changes directory.
    * ``argv[1]`` is the RENDERED prompt FILE (rendered from the user-editable template at
      ``.nwave/refactor-agent-prompt.md``, carrying item_id / defect / proposed_solution /
      paradigm / worktree). The maintainer's own edit of that template is what the fixer
      receives -- never a string baked into the harness, and never one baked in here.
    * Exit 0 means "the fixer did its work". Any non-zero exit fails THIS item only; the
      harness still runs green-to-green and still cleans the worktree up either way.

USE
    des refactor --pile techdebt.md \\
        --agent-cmd 'scripts/refactor_agent.py {prompt}' --max-parallel 2

TUNING (environment, all optional)
    NWAVE_REFACTOR_AGENT_MODEL       model for the fixer            (default: sonnet)
    NWAVE_REFACTOR_AGENT_PERMISSION  --permission-mode value        (default: acceptEdits)
    NWAVE_REFACTOR_AGENT_MAX_TURNS   turn budget per item           (default: 60)
    NWAVE_REFACTOR_AGENT_CLI         the headless assistant binary  (default: claude)

PERMISSIONS -- read before widening
    The default is ``acceptEdits``: the fixer may edit files, which is the whole point, but
    it is not given blanket permission to do anything. It runs inside an EPHEMERAL, ISOLATED
    worktree the harness removes on success OR failure, so the blast radius of a bad edit is
    that worktree. Widening this to skip permission checks entirely removes that boundary for
    every item in the pile at once -- decide it deliberately, per target, never as a default.

Python, not a shell script, by policy: nWave assets must run on any target with Python and
nothing else assumed present.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


EXIT_MALFORMED_INPUT = 2
EXIT_NO_CLI = 3


def fail(code: int, what: str, why: str, how: str) -> int:
    """Emit a self-explaining failure -- never a bare non-zero exit."""
    print(
        f"refactor-agent FAILED\n  WHAT: {what}\n  WHY:  {why}\n  HOW:  {how}",
        file=sys.stderr,
    )
    return code


def main(argv: list[str]) -> int:
    if len(argv) < 2 or not argv[1].strip():
        return fail(
            EXIT_MALFORMED_INPUT,
            "no prompt file argument was passed to the actuator",
            "the harness substitutes the rendered prompt path into {prompt}; an empty "
            "argv[1] means the --agent-cmd template omitted the placeholder",
            "pass it explicitly: --agent-cmd 'scripts/refactor_agent.py {prompt}'",
        )

    prompt_file = Path(argv[1])
    worktree = Path(argv[2]) if len(argv) > 2 and argv[2].strip() else Path.cwd()

    try:
        prompt_text = prompt_file.read_text(encoding="utf-8")
    except OSError as exc:
        return fail(
            EXIT_MALFORMED_INPUT,
            f"prompt file {str(prompt_file)!r} could not be read ({exc.strerror})",
            "the harness writes the rendered template to this path before invoking the "
            "actuator; an unreadable path means rendering failed or the path was rewritten",
            "re-run the drain and inspect the template at .nwave/refactor-agent-prompt.md "
            "(the harness bootstraps a default there on first run)",
        )

    if not prompt_text.strip():
        return fail(
            EXIT_MALFORMED_INPUT,
            "the rendered prompt is empty",
            "an empty task text would dispatch a fixer with nothing to do and report a "
            "success it did not earn",
            "check .nwave/refactor-agent-prompt.md -- it must carry the item's defect and "
            "proposed solution",
        )

    cli = os.environ.get("NWAVE_REFACTOR_AGENT_CLI", "claude")
    if shutil.which(cli) is None:
        return fail(
            EXIT_NO_CLI,
            f"the headless assistant CLI {cli!r} is not on PATH",
            "the actuator drives a headless assistant to perform the fix; without it there "
            "is nothing to dispatch to",
            "install it and re-run, or name a different binary with "
            "NWAVE_REFACTOR_AGENT_CLI=<binary>",
        )

    model = os.environ.get("NWAVE_REFACTOR_AGENT_MODEL", "sonnet")
    permission = os.environ.get("NWAVE_REFACTOR_AGENT_PERMISSION", "acceptEdits")
    max_turns = os.environ.get("NWAVE_REFACTOR_AGENT_MAX_TURNS", "60")

    print(
        f"refactor-agent: dispatching {cli} (model={model}, permission={permission}, "
        f"max-turns={max_turns}) in {worktree}",
        file=sys.stderr,
    )

    completed = subprocess.run(
        [
            cli,
            "-p",
            prompt_text,
            "--model",
            model,
            "--permission-mode",
            permission,
            "--max-turns",
            max_turns,
            "--add-dir",
            str(worktree),
        ],
        cwd=str(worktree),
        check=False,
    )

    if completed.returncode != 0:
        return fail(
            completed.returncode,
            f"the headless fixer exited {completed.returncode} for this item",
            "the fixer did not complete its task -- it may have hit the turn budget, been "
            "refused a permission it needed, or judged the item unfixable",
            "read the item's stderr above; raise NWAVE_REFACTOR_AGENT_MAX_TURNS if it ran "
            "out of turns, or drop the item from the pile if it is not mechanically "
            "fixable. The harness has already cleaned up this item's worktree.",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
