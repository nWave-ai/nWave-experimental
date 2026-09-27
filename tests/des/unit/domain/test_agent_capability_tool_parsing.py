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
    tool_reaches_source,
)
from des.runtime.packaged_asset import AssetOrigin, AssetResolution


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


class TestStructuredOutputIsNonSourceReaching:
    """``StructuredOutput`` shapes the reply schema, never the tree.

    Declaring it in frontmatter (so a provider emits ``--json-schema
    structured_output``) must not move a role's register off ``ENFORCED``.
    """

    def test_structured_output_does_not_reach_source(self):
        assert tool_reaches_source("StructuredOutput") is False

    def test_a_role_declaring_only_confined_tools_plus_structured_output_stays_enforced(
        self, tmp_path
    ):
        spec = tmp_path / "nWave/agents/role.md"
        spec.parent.mkdir(parents=True)
        spec.write_text(
            "---\ntools: WebFetch, StructuredOutput\n---\nbody\n", encoding="utf-8"
        )

        capability = resolve_declared_capability("role", repo_root=tmp_path)

        assert capability.register is ClaimRegister.ENFORCED


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

    def test_codex_only_runtime_reads_the_packaged_public_role_spec(
        self, tmp_path, monkeypatch
    ):
        """A wheel's nWave asset works when no Claude profile was installed."""
        package_spec = tmp_path / "site-packages/nWave/agents/role.md"
        package_spec.parent.mkdir(parents=True)
        package_spec.write_text("---\ntools: \n---\nbody\n", encoding="utf-8")
        repo_root = tmp_path / "codex-only-project"
        repo_root.mkdir()
        claude_dir = tmp_path / "no-claude-profile"

        import des.domain.agent_capability as capability_module

        monkeypatch.setattr(
            capability_module,
            "resolve_packaged_asset",
            lambda *_args, **_kwargs: AssetResolution(
                AssetOrigin.INSTALLED,
                package_spec,
                package_spec,
                None,
                "read from installed package",
            ),
        )

        capability = resolve_declared_capability(
            "role", repo_root=repo_root, claude_dir=claude_dir
        )

        assert capability.spec_path == package_spec
        assert capability.register is ClaimRegister.ENFORCED

    def test_packaged_asset_ambiguity_never_falls_through_to_claude_profile(
        self, tmp_path, monkeypatch
    ):
        repo_root = tmp_path / "project"
        repo_root.mkdir()
        legacy = tmp_path / "claude/agents/nw/role.md"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("---\ntools: Read\n---\nbody\n", encoding="utf-8")

        import des.domain.agent_capability as capability_module

        monkeypatch.setattr(
            capability_module,
            "resolve_packaged_asset",
            lambda *_args, **_kwargs: AssetResolution(
                AssetOrigin.AMBIGUOUS,
                None,
                tmp_path / "installed/nWave/agents/role.md",
                tmp_path / "repo/nWave/agents/role.md",
                "copies differ",
            ),
        )

        capability = resolve_declared_capability(
            "role", repo_root=repo_root, claude_dir=tmp_path / "claude"
        )

        assert capability.register is ClaimRegister.UNKNOWN
        assert capability.spec_path is None

    def test_framework_role_wins_over_the_invoked_repository_role(
        self, tmp_path
    ) -> None:
        framework = tmp_path / "framework"
        runtime = framework / "nWave" / "agents" / "role.md"
        runtime.parent.mkdir(parents=True)
        runtime.write_text("---\nmodel: runtime\ntools: Read\n---\nnew\n")
        subject = tmp_path / "subject" / "nWave" / "agents" / "role.md"
        subject.parent.mkdir(parents=True)
        subject.write_text("---\nmodel: stale\ntools: Edit\n---\nold\n")

        capability = resolve_declared_capability(
            "role", repo_root=subject.parents[2], framework_root=framework
        )

        assert capability.spec_path == runtime
        assert capability.declared_model == "runtime"
        assert capability.declared_tools == ("Read",)

    def test_runtime_competence_uses_the_published_base_role_spec(
        self, tmp_path
    ) -> None:
        self._spec(tmp_path, "tools: Read, Bash")

        capability = resolve_declared_capability("role#advanced", repo_root=tmp_path)

        assert capability.spec_path == tmp_path / "nWave/agents/role.md"
        assert capability.declared_tools == ("Read", "Bash")

    def test_malformed_framework_role_is_unknown_without_subject_fallback(
        self, tmp_path
    ) -> None:
        framework = tmp_path / "framework"
        runtime = framework / "nWave" / "agents" / "role.md"
        runtime.parent.mkdir(parents=True)
        runtime.write_text("not frontmatter\n")
        subject = tmp_path / "subject" / "nWave" / "agents" / "role.md"
        subject.parent.mkdir(parents=True)
        subject.write_text("---\nmodel: stale\ntools: Edit\n---\nold\n")

        capability = resolve_declared_capability(
            "role", repo_root=subject.parents[2], framework_root=framework
        )

        assert capability.register is ClaimRegister.UNKNOWN
        assert capability.spec_path == runtime

    def test_broken_framework_role_link_is_unknown_without_subject_fallback(
        self, tmp_path
    ) -> None:
        framework = tmp_path / "framework"
        runtime = framework / "nWave" / "agents" / "role.md"
        runtime.parent.mkdir(parents=True)
        runtime.symlink_to(framework / "missing-role.md")
        subject = tmp_path / "subject" / "nWave" / "agents" / "role.md"
        subject.parent.mkdir(parents=True)
        subject.write_text("---\nmodel: stale\ntools: Edit\n---\nold\n")

        capability = resolve_declared_capability(
            "role", repo_root=subject.parents[2], framework_root=framework
        )

        assert capability.register is ClaimRegister.UNKNOWN
        assert capability.spec_path == runtime

    def test_custom_role_absent_from_framework_falls_back_to_subject(
        self, tmp_path
    ) -> None:
        framework = tmp_path / "framework"
        framework.mkdir()
        subject = tmp_path / "subject" / "nWave" / "agents" / "custom.md"
        subject.parent.mkdir(parents=True)
        subject.write_text("---\nmodel: subject\ntools: Read\n---\ncustom\n")

        capability = resolve_declared_capability(
            "custom", repo_root=subject.parents[2], framework_root=framework
        )

        assert capability.spec_path == subject
        assert capability.declared_model == "subject"
