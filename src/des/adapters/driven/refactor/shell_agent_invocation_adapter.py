"""ShellAgentInvocationAdapter -- AgentInvocationPort over a configurable shell cmd.

CREATE_NEW file (des-refactor-fixer-swarm slice-01, ADR-SWARM-001 Decision 7).
Substitutes ``{prompt}``/``{worktree}`` in the configured ``agent_cmd`` template
and runs the resulting command via ``subprocess.run(cwd=worktree)``. Zero nWave
code per AI tool -- the harness does not know or care which AI produced the
diff.

Both methods are pure subprocess/shutil delegation -- no nWave code per tool.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
from typing import TYPE_CHECKING

from des.ports.driven_ports.agent_invocation_port import (
    AgentInvocationPort,
    AgentInvocationResult,
)


if TYPE_CHECKING:
    from pathlib import Path


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
        completed = subprocess.run(
            rendered,
            shell=True,
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
        return AgentInvocationResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


__all__ = ["ShellAgentInvocationAdapter"]
