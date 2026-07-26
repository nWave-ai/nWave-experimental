"""Unit tests for the Codex DES plugin matcher whitelist (US-3 / FM-3).

Single-behavior unit test that pins the contract: ``_build_hook_entry`` MUST
produce a matcher regex whose alternations are restricted to tool names the
RUNNING Codex host was observed to announce.

Whitelist source (amended 2026-07-26): the tool names read off the wire of
``codex-cli 0.145.0`` driven against a mock Responses provider. This file
previously sourced its whitelist from a documentation page
(``docs/feature/codex-empirical-e2e-support/spike-codex-hooks-schema.md``,
citing DDD-6 / DDD-8 spike Q6) and consequently blessed a matcher —
``^Bash$|^apply_patch$`` — that the host can never trigger: neither name is a
tool the host emits, ``apply_patch`` being a command passed inside
``exec_command``. A whitelist sourced from a declaration certifies what the
vendor DECLARED, never what the host DOES.

The list below is an INDEPENDENT restatement of that observation, kept
literal here on purpose: importing the production record would make the
membership property tautological.

Budget: 1 behavior (matcher whitelist) x 2 = 2 unit tests. Coverage shape:
1. Alternation-membership property → matcher ⊆ announced tools (catches the
   Task literal and the Bash/apply_patch literals transitively, since the
   host announces none of them).
2. Match-rejection property → ∀ name ∉ announced · matcher rejects name
   (covers Claude-Code-only names + doc-sourced names + fabricated names +
   empty string).
The "matches the tool the host emits" direction is folded into the acceptance
suite (matcher-real-tools.feature) to keep the unit budget honest.

WHY-NEW-FILE: tests/installer/unit/plugins/test_codex_matcher_real_tools.py
  CLOSEST-EXISTING: tests/installer/unit/plugins/test_codex_argv_contract.py
  EXTENSION-COST: existing file is the FM-2 argv contract, scoped to a single
    invariant on the command-string tail. Adding a matcher-whitelist class
    there mixes orthogonal FMs (argv vs matcher) and makes regression triage
    harder to locate by FM ID.
  PARALLEL-RATIONALE: the matcher whitelist is a discrete, FM-tracked
    invariant DDD-6 locks against the Codex hooks documentation. Co-locating
    its test in a 1-class file makes the FM-3 regression net trivially
    greppable and keeps the contract surface explicit.
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.install.plugins.codex_des_plugin import _build_hook_entry


# Tool names announced by the observed host (codex-cli 0.145.0, 2026-07-26),
# transcribed from the wire — not from a documentation page.
_CODEX_TOOL_WHITELIST: tuple[str, ...] = (
    "exec_command",
    "write_stdin",
    "update_plan",
    "request_user_input",
    "view_image",
    "multi_agent_v1",
    "get_goal",
    "create_goal",
    "update_goal",
    "web_search",
)

# Names the observed host never announces, so the matcher must never name
# them: Claude-Code-only tools, the two doc-sourced names that made the
# matcher unfireable, and fabricated input.
_BLACKLIST: tuple[str, ...] = (
    "Task",
    "Read",
    "Edit",
    "Write",
    "Grep",
    "Glob",
    "Bash",
    "apply_patch",
    "FictionalTool",
    "",
)


def _alternations(matcher_regex: str) -> list[str]:
    """Split `^A$|^B$` regex into ['A', 'B']."""
    parts = matcher_regex.split("|")
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p.startswith("^"):
            p = p[1:]
        if p.endswith("$"):
            p = p[:-1]
        out.append(p)
    return out


class TestBuildHookEntryMatcherWhitelist:
    """``_build_hook_entry`` matcher MUST name only tools the host announces."""

    def test_every_alternation_is_in_whitelist(self) -> None:
        """Property: matcher alternations ⊆ tools the observed host announces.

        Catches FM-3 and its successor transitively: neither ``Task`` nor
        ``Bash`` nor ``apply_patch`` is announced by the host, so a matcher
        naming any of them fails this assertion. Covers both "no unfireable
        literal" and "alternations are host-observed" in one property check.
        """
        entry = _build_hook_entry("/usr/bin/python3", "/home/tester/.claude/lib/python")
        matcher = entry["matcher"]
        whitelist = set(_CODEX_TOOL_WHITELIST)
        for alt in _alternations(matcher):
            assert alt in whitelist, (
                f"alternation {alt!r} not in whitelist {sorted(whitelist)}; "
                f"matcher={matcher!r}"
            )

    @given(tool_name=st.sampled_from(_BLACKLIST))
    @settings(max_examples=20, deadline=None)
    def test_matcher_rejects_every_non_whitelisted_name(self, tool_name: str) -> None:
        """Property: ∀ name ∉ whitelist · matcher does NOT match name.

        Covers Claude-Code-only names (Task, Read, Edit), aliases deferred to a
        later slice (Write), and fabricated names — including the empty string.
        """
        entry = _build_hook_entry("/usr/bin/python3", "/home/tester/.claude/lib/python")
        matcher = entry["matcher"]
        assert not re.match(matcher, tool_name), (
            f"matcher {matcher!r} must NOT match non-whitelisted name {tool_name!r}"
        )
