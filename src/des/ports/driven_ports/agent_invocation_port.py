"""AgentInvocationPort -- driven port for the pluggable AI-agent shell command.

CREATE_NEW (des-refactor-fixer-swarm, ADR-SWARM-001 Decision 7). ``agent_cmd`` is
ONE config knob -- a shell-command template (``"claude -p {prompt}"``,
``"aider --message-file {prompt}"``, ``"./my-ai-wrapper.sh {prompt}"``) with
``{prompt}``/``{worktree}`` placeholders. The harness does not know or care which
AI produced the diff -- zero nWave code per tool (OSS mandate,
``feedback_runtimes_must_be_pluggable_copilot_urgency``).

The PROMPT ITSELF is never hardcoded (Ale 2026-07-14 slice-01 requirement): the
caller renders the user-editable prompt-template file
(``des.domain.refactor.prompt_template``) to a prompt FILE and passes that file's
path here as ``prompt_path`` -- this port only substitutes placeholders and runs
the resulting command.

Pure interface -- no behavior to scaffold. The concrete adapter
(``des.adapters.driven.refactor.shell_agent_invocation_adapter.
ShellAgentInvocationAdapter``) carries the Mandate-7 RED scaffold.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class AgentInvocationResult:
    """Observable outcome of one agent_cmd invocation."""

    exit_code: int
    stdout: str
    stderr: str


class AgentInvocationPort(ABC):
    """Driven port: runs the configured ``agent_cmd`` shell command."""

    @abstractmethod
    def probe(self, agent_cmd: str) -> bool:
        """Earned-Trust startup probe: resolve the ``agent_cmd`` template's
        executable (first token) before dispatching any item. An unresolvable
        command MUST refuse the harness's start."""
        ...

    @abstractmethod
    def invoke(
        self, agent_cmd: str, prompt_path: Path, worktree_path: Path
    ) -> AgentInvocationResult:
        """Substitute ``{prompt}``/``{worktree}`` in ``agent_cmd`` and run the
        resulting command via a checked subprocess with ``cwd=worktree_path``.
        ``prompt_path`` MUST already contain the RENDERED user-editable
        prompt-template content -- this port never renders the prompt text
        itself, only passes the file through."""
        ...
