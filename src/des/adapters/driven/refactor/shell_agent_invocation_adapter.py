"""ShellAgentInvocationAdapter -- AgentInvocationPort over a configurable shell cmd.

CREATE_NEW file (des-refactor-fixer-swarm slice-01, ADR-SWARM-001 Decision 7).
Substitutes ``{prompt}``/``{worktree}`` in the configured ``agent_cmd`` template
and runs the resulting command through the spawn boundary (``cwd=worktree``). Zero nWave
code per AI tool -- the harness does not know or care which AI produced the
diff.

Both methods are pure shutil/spawn-boundary delegation -- no nWave code per tool.

``invoke`` is the site that DEADLOCKED ``des refactor --pile`` (RCA
``docs/feature/fix-inherited-stdin-deadlocks-spawns/rca.md``, ROOT CAUSE A): it
spawned a third-party CLI subtree with neither ``stdin=`` nor ``timeout=``, so the
deepest grandchild inherited the drain's stdin and blocked on a descriptor that
never reached EOF, while this frame blocked draining the capture pipes that
grandchild held open. It now runs through ``des.runtime.spawn.spawn``, which cuts
stdin at this OUTERMOST boundary -- inheritance means the outermost cut immunises
the whole subtree (measured: 0.22s vs never) -- and bounds the invocation on the
AGENT tier. This is the tier that opts INTO ``reap_process_group``: it shells a
third-party CLI subtree, so a fired bound that killed only the direct child would
leave grandchildren alive once per pile item (RCA §8 measured caveat).
"""

from __future__ import annotations

import shlex
import shutil
from typing import TYPE_CHECKING

from des.ports.driven_ports.agent_invocation_port import (
    AgentInvocationPort,
    AgentInvocationResult,
)
from des.runtime.spawn import (
    AGENT_TIMEOUT_ENV,
    SpawnTimeout,
    agent_timeout_seconds,
    spawn,
)


if TYPE_CHECKING:
    from pathlib import Path


EXIT_AGENT_TIMED_OUT = 124
"""Exit code reported for an agent whose bound fired -- the POSIX ``timeout(1)``
convention, so a reader who knows the shell already knows what 124 means. The
invocation still RETURNS a result rather than raising: one stuck item must fail
its own item, not abort the whole drain, and the operator gets the WHAT/WHY/HOW
on stderr instead of a traceback."""


class ShellAgentInvocationAdapter(AgentInvocationPort):
    """Real adapter -- runs the ``agent_cmd`` shell-command template."""

    def probe(self, agent_cmd: str) -> bool:
        tokens = shlex.split(agent_cmd)
        if not tokens:
            return False
        return shutil.which(tokens[0]) is not None

    def invoke(
        self, agent_cmd: str, prompt_path: Path, worktree_path: Path
    ) -> AgentInvocationResult:
        rendered = agent_cmd.replace("{prompt}", str(prompt_path)).replace(
            "{worktree}", str(worktree_path)
        )
        try:
            completed = spawn(
                rendered,
                shell=True,
                cwd=worktree_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=agent_timeout_seconds(),
                timeout_env=AGENT_TIMEOUT_ENV,
                reap_process_group=True,
            )
        except SpawnTimeout as timed_out:
            return AgentInvocationResult(
                exit_code=EXIT_AGENT_TIMED_OUT,
                stdout=timed_out.captured_text,
                stderr=str(timed_out),
            )
        return AgentInvocationResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


__all__ = ["ShellAgentInvocationAdapter"]
