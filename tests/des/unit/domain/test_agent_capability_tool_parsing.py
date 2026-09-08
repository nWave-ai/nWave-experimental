"""The declared-tools field is parsed as specifiers, not as bare comma text.

A declared entry may be a permission SPECIFIER whose own scope contains commas
(``Bash(des code-fact:*, des dispatch:*)``). Splitting the field on every comma
turns one such grant into two broken halves, and a broken half registers no tool
at all with the provider -- the role silently loses the capability its spec
granted, which is the failure this parser exists to prevent.
"""

from pathlib import Path

import pytest

from des.domain.agent_capability import (
    ClaimRegister,
    UnbalancedToolSpecifier,
    provider_tool_name,
    resolve_declared_capability,
    split_declared_tools,
)


class TestSplitDeclaredTools:
    def test_bare_names_split_on_commas(self):
        assert split_declared_tools(" Read, Glob, Grep ") == ("Read", "Glob", "Grep")

    def test_a_comma_inside_a_specifier_does_not_split_it(self):
        raw = "Read, Bash(des code-fact:*, des dispatch:*), Edit"
        assert split_declared_tools(raw) == (
            "Read",
            "Bash(des code-fact:*, des dispatch:*)",
            "Edit",
        )

    def test_empty_field_is_an_empty_capability(self):
        assert split_declared_tools("") == ()

    @pytest.mark.parametrize("raw", ["Read, Bash(des code-fact:*", "Bash)", "Read, )("])
    def test_unbalanced_parentheses_are_refused_loud(self, raw):
        with pytest.raises(UnbalancedToolSpecifier):
            split_declared_tools(raw)


class TestProviderToolName:
    @pytest.mark.parametrize(
        ("entry", "expected"),
        [
            ("Read", "Read"),
            ("Bash(des code-fact:*)", "Bash"),
            ("Bash(des code-fact:*, des dispatch:*)", "Bash"),
        ],
    )
    def test_the_bare_name_is_the_text_before_the_scope(self, entry, expected):
        assert provider_tool_name(entry) == expected


class TestResolveDeclaredCapability:
    @staticmethod
    def _spec(tmp_path: Path, tools_line: str) -> Path:
        spec = tmp_path / "nWave/agents/role.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(f"---\n{tools_line}\n---\nbody\n", encoding="utf-8")
        return spec

    def test_a_specifier_carrying_commas_stays_one_declared_entry(self, tmp_path):
        self._spec(tmp_path, "tools: Read, Bash(des code-fact:*, des dispatch:*)")
        capability = resolve_declared_capability("role", repo_root=tmp_path)

        assert capability.declared_tools == (
            "Read",
            "Bash(des code-fact:*, des dispatch:*)",
        )
        assert capability.register is ClaimRegister.INSTRUCTED

    def test_an_unparseable_tools_field_is_unknown_never_permissive(self, tmp_path):
        """UNKNOWN, not INSTRUCTED: a field nobody could read grants nothing.

        INSTRUCTED is the register for a spec that OMITS the key, which inherits
        every tool. Reaching it from a malformed field would answer a question
        about a capability that was never established.
        """
        self._spec(tmp_path, "tools: Read, Bash(des code-fact:*")
        capability = resolve_declared_capability("role", repo_root=tmp_path)

        assert capability.register is ClaimRegister.UNKNOWN
        assert capability.declared_tools is None
