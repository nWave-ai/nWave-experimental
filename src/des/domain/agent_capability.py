"""What an agent's published spec DECLARES it can do -- and the REGISTER in
which a briefing may therefore speak about that agent's access.

RCA: docs/feature/fix-examiner-blindness-enforced/rca.md (root causes A + D).
``des dispatch`` told every reader of a NON-CODE-FACING envelope that the
dispatched agent had no source / design / acceptance-test access "BY
CONSTRUCTION". Nothing enforced that: the predicate behind the claim was a
frozenset of agent NAMES, never computed from what the agent can actually DO,
while the examiner's own frontmatter granted unrestricted ``Read`` and
``Bash``. "By construction" is precisely the instruction to the orchestrator to
STOP verifying, so the unenforced constraint was also unchecked.

This module supplies the FACT the claim must be derived from, and the
vocabulary the framework was missing (root cause D) -- three mutually
exclusive registers:

``ENFORCED``
    The declared tools grant NOTHING that reaches the tree. An absolute ("by
    construction" / "cannot read") is EARNED here and only here: an ungranted
    tool is genuinely uncallable, so the declaration IS the mechanism.
``INSTRUCTED``
    The role is non-code-facing by INTENT, but its declared tools DO grant a
    source-reaching capability. The honest register: instructed, not
    prevented -- and the reader is owed a concrete place to confirm it.
``UNKNOWN``
    The spec was not found, or carries no parseable frontmatter. Degrade LOUD
    (GDP-6): "I looked and she is blind" and "I never looked" must not produce
    the same sentence. An unreadable capability is an INDETERMINATE, never an
    inferred one -- and NEVER the permissive ``ENFORCED``.

Two deliberate safety properties:

1. **Fail-safe classification.** A tool this module does not recognise is
   treated as SOURCE-REACHING. The only way to reach ``ENFORCED`` is for every
   declared tool to be on the known non-source-reaching list, so an unknown
   tool can never manufacture a false absolute.
2. **First EXISTING candidate wins -- no fall-through on a parse failure.**
   The checkout the caller POINTED AT is consulted before the installed tree
   (a resolver that ignores the checkout it was handed cannot be
   capability-derived in a dev tree). A candidate that exists but will not
   parse yields ``UNKNOWN``; it must NOT silently fall through to a different
   deployment's copy of the spec, which would answer a question about a file
   the caller never named.

An OMITTED ``tools:`` key is NOT an empty capability -- in Claude Code the
omission INHERITS every tool, i.e. maximally permissive. It resolves to
``INSTRUCTED``, never ``ENFORCED``.

Target-machine agnostic: Python + stdlib only. No git, no external CLI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ClaimRegister(Enum):
    """The register a briefing may use when speaking about an agent's access."""

    ENFORCED = "enforced"
    INSTRUCTED = "instructed"
    UNKNOWN = "unknown"


#: Tools that reach only the running product or the web -- never the tree.
#: Everything NOT named here (or matching a prefix below) is treated as
#: source-reaching, so an unrecognised tool can never yield a false absolute.
_NON_SOURCE_REACHING_TOOLS: frozenset[str] = frozenset(
    {
        "WebFetch",
        "WebSearch",
        "AskUserQuestion",
        "TodoWrite",
    }
)

#: Tool-name prefixes for the browser-driving MCP servers (the examiner's real
#: instrument): they exercise the running product, they do not read the tree.
_NON_SOURCE_REACHING_PREFIXES: tuple[str, ...] = (
    "mcp__playwright__",
    "mcp__plugin_playwright_",
)

#: Candidate 1 -- the checkout the caller pointed at (dev tree). Precedent:
#: ``des.cli.mode_registry_completeness`` reads ``root / "nWave" / "agents"``.
_CHECKOUT_AGENT_SPEC_PARTS: tuple[str, ...] = ("nWave", "agents")

#: Candidate 2 -- the installed deployment. Precedent: ``des.cli.health_check``
#: reads ``claude_dir / "agents" / "nw"``. The installed ``nWave`` SSOT axis
#: (``<claude_dir>/lib/nWave/``) ships NO ``agents/``, so this second candidate
#: is what makes the derivation work on an installed machine at all.
_INSTALLED_AGENT_SPEC_PARTS: tuple[str, ...] = ("agents", "nw")

_FRONTMATTER_DELIMITER = "---"
_TOOLS_KEY = "tools:"


def tool_reaches_source(tool: str) -> bool:
    """True when ``tool`` can reach the repository tree.

    Fail-safe: an unrecognised tool answers True. Only a tool KNOWN to be
    confined to the running product / the web answers False.
    """
    if tool in _NON_SOURCE_REACHING_TOOLS:
        return False
    return not tool.startswith(_NON_SOURCE_REACHING_PREFIXES)


@dataclass(frozen=True)
class DeclaredCapability:
    """An agent's declared capability, plus the register it licenses.

    ``declared_tools`` is ``None`` for BOTH "spec unreadable" and "no ``tools:``
    key" -- ``register`` is what distinguishes them (``UNKNOWN`` vs
    ``INSTRUCTED``), so the two are never conflated by a reader.
    """

    register: ClaimRegister
    spec_path: Path | None
    declared_tools: tuple[str, ...] | None

    @classmethod
    def unknown(cls, spec_path: Path | None) -> DeclaredCapability:
        """The capability could not be determined -- degrade LOUD."""
        return cls(
            register=ClaimRegister.UNKNOWN, spec_path=spec_path, declared_tools=None
        )

    @classmethod
    def inherits_every_tool(cls, spec_path: Path) -> DeclaredCapability:
        """A spec with NO ``tools:`` key: maximally permissive, never blind."""
        return cls(
            register=ClaimRegister.INSTRUCTED,
            spec_path=spec_path,
            declared_tools=None,
        )

    @classmethod
    def from_declared_tools(
        cls, spec_path: Path, tools: tuple[str, ...]
    ) -> DeclaredCapability:
        """Derive the register from the tools the spec actually declares."""
        reaches = any(tool_reaches_source(tool) for tool in tools)
        register = ClaimRegister.INSTRUCTED if reaches else ClaimRegister.ENFORCED
        return cls(register=register, spec_path=spec_path, declared_tools=tools)

    @property
    def source_reaching_tools(self) -> tuple[str, ...]:
        """The declared tools that reach the tree (empty when none/unknown)."""
        if self.declared_tools is None:
            return ()
        return tuple(tool for tool in self.declared_tools if tool_reaches_source(tool))

    def spec_reference(self, agent: str) -> str:
        """A short, falsifiable pointer at the spec the register was read from.

        The last three path components (``nWave/agents/<agent>.md`` in a
        checkout, ``agents/nw/<agent>.md`` when installed) -- enough for the
        reader to open the exact file, without pasting a host-specific absolute
        path into a briefing that travels.
        """
        if self.spec_path is None:
            return f"{'/'.join(_CHECKOUT_AGENT_SPEC_PARTS)}/{agent}.md (not found)"
        return "/".join(self.spec_path.parts[-3:])


def _default_claude_dir() -> Path:
    """The Claude configuration directory (``CLAUDE_CONFIG_DIR`` or ``~/.claude``)."""
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    if configured:
        return Path(configured)
    return Path.home() / ".claude"


def candidate_spec_paths(
    agent: str, *, repo_root: Path, claude_dir: Path | None = None
) -> tuple[Path, ...]:
    """The ordered candidate locations of ``agent``'s spec.

    The checkout the caller POINTED AT first, the installed deployment second.
    """
    installed_root = claude_dir if claude_dir is not None else _default_claude_dir()
    return (
        repo_root.joinpath(*_CHECKOUT_AGENT_SPEC_PARTS, f"{agent}.md"),
        installed_root.joinpath(*_INSTALLED_AGENT_SPEC_PARTS, f"{agent}.md"),
    )


def _frontmatter_lines(text: str) -> tuple[str, ...] | None:
    """The YAML frontmatter block's lines, or ``None`` when there is no block.

    A spec whose first non-empty line is not the ``---`` delimiter, or whose
    block is never closed, has no parseable frontmatter -- the ``UNKNOWN``
    case, stated rather than guessed at.
    """
    lines = text.splitlines()
    opened = False
    collected: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not opened:
            if not stripped:
                continue
            if stripped != _FRONTMATTER_DELIMITER:
                return None
            opened = True
            continue
        if stripped == _FRONTMATTER_DELIMITER:
            return tuple(collected)
        collected.append(line)
    return None


def _declared_tools(frontmatter: tuple[str, ...]) -> tuple[str, ...] | None:
    """The ``tools:`` value as a tuple, or ``None`` when the key is absent."""
    for line in frontmatter:
        if not line.startswith(_TOOLS_KEY):
            continue
        raw = line[len(_TOOLS_KEY) :]
        return tuple(tool.strip() for tool in raw.split(",") if tool.strip())
    return None


def _capability_from_spec(spec_path: Path) -> DeclaredCapability:
    """Read ONE spec file into a capability. Never falls through on failure."""
    try:
        text = spec_path.read_text(encoding="utf-8")
    except OSError:
        return DeclaredCapability.unknown(spec_path)
    frontmatter = _frontmatter_lines(text)
    if frontmatter is None:
        return DeclaredCapability.unknown(spec_path)
    tools = _declared_tools(frontmatter)
    if tools is None:
        return DeclaredCapability.inherits_every_tool(spec_path)
    return DeclaredCapability.from_declared_tools(spec_path, tools)


def resolve_declared_capability(
    agent: str, *, repo_root: Path, claude_dir: Path | None = None
) -> DeclaredCapability:
    """Resolve ``agent``'s declared capability from its published spec.

    The FIRST candidate that EXISTS decides -- including deciding ``UNKNOWN``
    when it exists but will not parse. Falling through on a parse failure would
    answer with a different deployment's copy of the spec, i.e. answer a
    question the caller never asked.
    """
    for candidate in candidate_spec_paths(
        agent, repo_root=repo_root, claude_dir=claude_dir
    ):
        if candidate.is_file():
            return _capability_from_spec(candidate)
    return DeclaredCapability.unknown(None)
