"""Unit tests for Codex CLI agents installer plugin.

Tests validate that:
- validate_prerequisites() skips gracefully when Codex CLI is not detected
- validate_prerequisites() proceeds when Codex CLI directory exists
- install() writes .toml files to ~/.codex/agents/
- install() transforms YAML frontmatter + body to Codex TOML format
- install() drops the tools block with a warning (no Codex equivalent)
- install() writes a manifest tracking installed agent names
- verify() returns success after a successful install
- uninstall() removes only nWave-installed agents, preserving user-created ones

Tests follow hexagonal architecture — mocks only at port boundaries.

State-delta paradigm: install / uninstall mutate multiple filesystem slots
(per-agent .toml presence, manifest presence).  Multi-slot tests use
``assert_state_delta`` so implicit-unchanged catches unintended mutations.

Transform function tests (pure functions) use direct assertions — no state
mutation, bypass delta-first per skill criterion.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import tomllib
from nwave_ai.state_delta import assert_state_delta, set_to

from scripts.install.plugins import (
    codex_agents_plugin,
    codex_des_plugin,
    codex_skills_plugin,
)
from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.codex_agents_plugin import (
    CodexAgentsPlugin,
    _extract_scalar_fields,
    _log_tools_translated,
    _render_toml_agent,
    _toml_multiline_string,
    _toml_string,
    _transform_agent,
    _translate_skill_invocations,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_context(
    tmp_path: Path,
    *,
    agents: dict[str, str] | None = None,
) -> tuple[InstallContext, Path]:
    """Create an InstallContext with a flat-layout agents source.

    Args:
        tmp_path: Pytest temp directory
        agents: Optional mapping of agent_stem -> file content. Defaults to
            a single ``nw-test-agent`` with minimal frontmatter + body.

    Returns:
        Tuple of (context, agents_source_dir).
    """
    project_root = tmp_path / "project"
    framework_source = project_root / "nWave"
    agents_dir = framework_source / "agents"
    agents_dir.mkdir(parents=True)

    templates_dir = framework_source / "templates"
    templates_dir.mkdir(parents=True)

    if agents is None:
        agents = {
            "nw-test-agent": (
                "---\n"
                "name: nw-test-agent\n"
                "description: A test agent\n"
                "model: claude-sonnet-4-5\n"
                "---\n\n"
                "# Test Agent\n\n"
                "You are a test agent.\n"
            )
        }

    for stem, content in agents.items():
        (agents_dir / f"{stem}.md").write_text(content, encoding="utf-8")

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    context = InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts",
        templates_dir=templates_dir,
        logger=MagicMock(),
        project_root=project_root,
        framework_source=framework_source,
        dev_mode=True,  # bypass public-agent filtering
    )
    return context, agents_dir


def _patch_codex_dirs(monkeypatch, codex_agents_dir: Path, codex_config_dir: Path):
    """Redirect _codex_agents_dir() and _codex_config_dir() to tmp paths."""
    monkeypatch.setattr(
        "scripts.install.plugins.codex_agents_plugin._codex_agents_dir",
        lambda: codex_agents_dir,
    )
    monkeypatch.setattr(
        "scripts.install.plugins.codex_agents_plugin._codex_config_dir",
        lambda: codex_config_dir,
    )


# ---------------------------------------------------------------------------
# Pure-function transform tests
# ---------------------------------------------------------------------------


class TestTomlStringRendering:
    """_toml_string / _toml_multiline_string: pure TOML serialisation."""

    def test_simple_string_gets_double_quoted(self):
        # bypass: pure function, single-property assertion
        assert _toml_string("hello") == '"hello"'

    def test_embedded_double_quote_is_escaped(self):
        # bypass: pure function, single-property assertion
        assert _toml_string('say "hi"') == '"say \\"hi\\""'

    def test_embedded_backslash_is_escaped(self):
        # bypass: pure function, single-property assertion
        assert _toml_string("path\\to\\file") == '"path\\\\to\\\\file"'

    def test_multiline_string_uses_triple_quotes(self):
        # bypass: pure function, single-property assertion
        result = _toml_multiline_string("line1\nline2\n")
        assert result.startswith('"""')
        assert result.endswith('"""')
        assert "line1" in result
        assert "line2" in result

    def test_multiline_string_escapes_embedded_triple_quotes(self):
        # bypass: pure function, single-property assertion
        result = _toml_multiline_string('before"""after')
        assert '"""' not in result.split("\n", 1)[1][:-3], (
            "embedded triple-quote must be escaped to prevent premature termination"
        )


class TestExtractScalarFields:
    """_extract_scalar_fields: drops forbidden + non-scalar YAML keys."""

    def test_keeps_name_description_model(self):
        # bypass: pure function, single-property assertion
        frontmatter = {"name": "nw-foo", "description": "bar", "model": "sonnet"}
        result = _extract_scalar_fields(frontmatter)
        assert result == {"name": "nw-foo", "description": "bar", "model": "sonnet"}

    def test_drops_forbidden_fields(self):
        # bypass: pure function — verifies field exclusion
        frontmatter = {
            "name": "nw-foo",
            "tools": ["Read", "Bash"],
            "maxTurns": 20,
            "disable-model-invocation": True,
            "permissionMode": "default",
            "skills": ["nw-skill"],
            "effort": "low",
        }
        result = _extract_scalar_fields(frontmatter)
        assert "tools" not in result
        assert "maxTurns" not in result
        assert "disable-model-invocation" not in result
        assert "permissionMode" not in result
        assert "skills" not in result
        assert "effort" not in result

    def test_drops_non_scalar_values(self):
        # bypass: pure function — lists and dicts are silently dropped
        frontmatter = {
            "name": "nw-foo",
            "some_list": ["a", "b"],
            "some_dict": {"key": "val"},
        }
        result = _extract_scalar_fields(frontmatter)
        assert result == {"name": "nw-foo"}


class TestRenderTomlAgent:
    """_render_toml_agent: TOML output structure."""

    def test_canonical_fields_appear_in_stable_order(self):
        # bypass: pure function — ordering assertion
        scalar_fields = {
            "model": "claude-sonnet-4-5",
            "description": "A test agent",
            "name": "nw-test",
        }
        result = _render_toml_agent(scalar_fields, "body text\n")
        lines = result.splitlines()
        keys_in_order = [ln.split(" = ")[0] for ln in lines if " = " in ln]
        # name, description, model must appear before developer_instructions
        assert keys_in_order.index("name") < keys_in_order.index(
            "developer_instructions"
        )
        assert keys_in_order.index("description") < keys_in_order.index(
            "developer_instructions"
        )
        assert keys_in_order.index("model") < keys_in_order.index(
            "developer_instructions"
        )

    def test_body_appears_as_developer_instructions(self):
        # bypass: pure function
        result = _render_toml_agent({"name": "nw-foo"}, "## Instructions\nDo stuff.\n")
        assert "developer_instructions" in result
        assert "## Instructions" in result
        assert "Do stuff." in result


class TestLogToolsTranslated:
    """_log_tools_translated: logs the translation when tools key present."""

    def test_logs_translation_when_tools_present(self, caplog):
        # bypass: pure function, single observable (log output)
        with caplog.at_level(
            logging.INFO, logger="scripts.install.plugins.codex_agents_plugin"
        ):
            _log_tools_translated("nw-foo", {"tools": ["Read", "Bash"]})
        assert any("capability-mapping preamble" in msg for msg in caplog.messages)
        assert any("nw-foo" in msg for msg in caplog.messages)

    def test_no_log_when_tools_absent(self, caplog):
        # bypass: pure function, single observable
        with caplog.at_level(
            logging.INFO, logger="scripts.install.plugins.codex_agents_plugin"
        ):
            _log_tools_translated("nw-foo", {"name": "nw-foo", "description": "x"})
        assert not caplog.messages


class TestTransformAgent:
    """_transform_agent: end-to-end pipeline (parse -> transform -> render)."""

    def test_full_transform_produces_valid_toml_structure(self):
        # bypass: pure function
        source = (
            "---\n"
            "name: nw-craft\n"
            "description: crafts code\n"
            "model: claude-opus-4\n"
            "tools:\n"
            "  - Read\n"
            "  - Bash\n"
            "---\n\n"
            "You are a crafter.\n"
        )
        result = _transform_agent(source, "nw-craft")
        parsed = tomllib.loads(result)

        assert parsed["name"] == "nw-craft"
        assert parsed["description"] == "crafts code"
        assert "model" not in parsed
        assert "You are a crafter." in parsed["developer_instructions"]
        # tools block must NOT appear in TOML output
        assert "tools" not in parsed

    def test_a_dropped_claude_model_is_named_in_the_toml(self):
        """The loss is visible in the artifact, not only in a log line.

        A role that declares `model: sonnet` reaches Codex with no model at
        all, so Codex answers on its own configured default. Ale's decision of
        2026-09-06 to run the reviewing roles on sonnet therefore does not
        reach Codex. The host mapping belongs to the unified config SSOT work
        (F-CONFIG-SSOT-UNIFIED), so this states the gap where an operator will
        see it instead of inventing a mapping here.
        """
        # bypass: pure function
        source = (
            "---\n"
            "name: nw-user-examiner\n"
            "description: judges\n"
            "model: sonnet\n"
            "---\n\n"
            "You judge.\n"
        )

        rendered = _transform_agent(source, "nw-user-examiner")

        assert "model" not in tomllib.loads(rendered)
        assert (
            "# model sonnet not projected for codex: "
            "host mapping pending F-CONFIG-SSOT-UNIFIED" in rendered
        )

    def test_a_dropped_claude_model_is_reported_to_the_installer(self, caplog):
        # bypass: pure function
        source = (
            "---\nname: nw-user-examiner\ndescription: judges\n"
            "model: sonnet\n---\n\nYou judge.\n"
        )

        with caplog.at_level(
            logging.WARNING, logger="scripts.install.plugins.codex_agents_plugin"
        ):
            _transform_agent(source, "nw-user-examiner")

        assert any("not projected for codex" in msg for msg in caplog.messages)
        assert any("nw-user-examiner" in msg for msg in caplog.messages)

    def test_an_explicit_codex_model_reports_no_loss(self, caplog):
        """The mutation pair: nothing was dropped, so nothing is announced."""
        # bypass: pure function
        source = (
            "---\nname: nw-craft\ndescription: crafts\n"
            "model: gpt-5.2-codex\n---\n\nYou craft.\n"
        )

        with caplog.at_level(
            logging.WARNING, logger="scripts.install.plugins.codex_agents_plugin"
        ):
            rendered = _transform_agent(source, "nw-craft")

        assert "not projected for codex" not in rendered
        assert not [m for m in caplog.messages if "not projected" in m]

    def test_full_transform_preserves_explicit_codex_model(self):
        # bypass: pure function — mutation pair for Claude-model omission
        source = (
            "---\n"
            "name: nw-craft\n"
            "description: crafts code\n"
            "model: gpt-5.2-codex\n"
            "---\n\n"
            "You are a crafter.\n"
        )

        parsed = tomllib.loads(_transform_agent(source, "nw-craft"))

        assert parsed["model"] == "gpt-5.2-codex"

    def test_full_transform_drops_effort_field(self):
        # bypass: pure function — Codex agent TOML schema has no effort
        # field: 0.149.0 rejects the whole role file as malformed and the
        # agent silently disappears from the registry (spawn_agent then
        # fails with unknown agent_type).
        source = (
            "---\n"
            "name: nw-acceptance-designer\n"
            "description: distill wave\n"
            "model: sonnet\n"
            "effort: low\n"
            "---\n\n"
            "You design acceptance oracles.\n"
        )

        parsed = tomllib.loads(_transform_agent(source, "nw-acceptance-designer"))

        assert "effort" not in parsed


class TestTranslateSkillInvocations:
    """Codex has no Skill tool: native `Invoke Skill(NAME)` directives must
    become explicit reads of the installed skill file."""

    def test_invoke_skill_becomes_exact_read_path(self):
        result = _translate_skill_invocations("Invoke Skill(nw-tdd-methodology)")
        assert result == "Read `~/.agents/skills/nw-tdd-methodology/SKILL.md`"

    def test_invoke_one_skill_becomes_exact_read_path(self):
        result = _translate_skill_invocations("Invoke ONE Skill(nw-property-fsharp)")
        assert result == "Read ONE `~/.agents/skills/nw-property-fsharp/SKILL.md`"

    def test_on_trigger_suffix_is_preserved(self):
        result = _translate_skill_invocations(
            "- Invoke Skill(nw-algebraic-design-protocol) ON-TRIGGER — contested law"
        )
        assert result == (
            "- Read `~/.agents/skills/nw-algebraic-design-protocol/SKILL.md` "
            "ON-TRIGGER — contested law"
        )

    def test_idempotent_on_already_translated_text(self):
        once = _translate_skill_invocations("Invoke Skill(nw-tdd-methodology)")
        twice = _translate_skill_invocations(once)
        assert once == twice

    def test_unrelated_text_unchanged(self):
        text = "Plain prose about invoking a skillful reviewer, no directive here."
        assert _translate_skill_invocations(text) == text

    def test_regex_looking_backslashes_in_body_survive_toml_parse(self):
        source = (
            "---\n"
            "name: nw-craft\n"
            "description: crafts code\n"
            "model: gpt-5.2-codex\n"
            "---\n\n"
            "Invoke Skill(nw-tdd-methodology) ON-TRIGGER — path is C:\\Users\\x\\1\n"
        )
        result = _transform_agent(source, "nw-craft")
        parsed = tomllib.loads(result)
        assert (
            "~/.agents/skills/nw-tdd-methodology/SKILL.md"
            in (parsed["developer_instructions"])
        )
        assert "C:\\Users\\x\\1" in parsed["developer_instructions"]


# ---------------------------------------------------------------------------
# Plugin lifecycle tests
# ---------------------------------------------------------------------------


class TestValidatePrerequisites:
    """validate_prerequisites: skip vs proceed based on Codex detection."""

    def test_skips_gracefully_when_codex_not_detected(self, tmp_path, monkeypatch):
        """
        GIVEN: ~/.codex/ does not exist AND `codex` binary is not in PATH
        WHEN: validate_prerequisites() is called
        THEN: Returns success with skip message (NOT an error)
        """
        context, _ = _make_context(tmp_path)
        codex_agents_dir = tmp_path / "home" / ".codex" / "agents"
        codex_config_dir = tmp_path / "home" / ".codex"  # does NOT exist
        _patch_codex_dirs(monkeypatch, codex_agents_dir, codex_config_dir)
        monkeypatch.setattr(
            "scripts.install.plugins.codex_agents_plugin.shutil.which",
            lambda _name: None,
        )

        plugin = CodexAgentsPlugin()
        result = plugin.validate_prerequisites(context)

        assert result.success is True
        assert (
            "skip" in result.message.lower() or "not detected" in result.message.lower()
        )

    def test_proceeds_when_codex_config_dir_exists(self, tmp_path, monkeypatch):
        """
        GIVEN: ~/.codex/ exists
        WHEN: validate_prerequisites() is called
        THEN: Returns success with non-skip message
        """
        context, _ = _make_context(tmp_path)
        codex_agents_dir = tmp_path / "home" / ".codex" / "agents"
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_dirs(monkeypatch, codex_agents_dir, codex_config_dir)

        plugin = CodexAgentsPlugin()
        result = plugin.validate_prerequisites(context)

        assert result.success is True
        assert "validated" in result.message.lower()


class TestInstallWritesTomlAgents:
    """install: writes TOML agent files and manifest."""

    def test_install_creates_toml_file_and_manifest(self, tmp_path, monkeypatch):
        """
        GIVEN: A source agents dir with one agent (nw-test-agent.md)
            AND ~/.codex/ exists (Codex detected)
        WHEN: install() runs
        THEN: ~/.codex/agents/nw-test-agent.toml exists AND
              the manifest exists, while no other slots are mutated.
        """
        context, _ = _make_context(tmp_path)
        codex_agents_dir = tmp_path / "home" / ".codex" / "agents"
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_dirs(monkeypatch, codex_agents_dir, codex_config_dir)

        tracked_keys = {
            "nw-test-agent.exists",
            "manifest.exists",
            "stranger-agent.exists",
        }

        def snapshot() -> dict[str, object]:
            return {
                "nw-test-agent.exists": (
                    codex_agents_dir / "nw-test-agent.toml"
                ).is_file(),
                "manifest.exists": (
                    codex_agents_dir / ".nwave-agents-manifest.json"
                ).is_file(),
                "stranger-agent.exists": (
                    codex_agents_dir / "stranger-agent.toml"
                ).is_file(),
            }

        before = snapshot()

        plugin = CodexAgentsPlugin()
        result = plugin.install(context)

        after = snapshot()

        assert result.success is True
        assert_state_delta(
            before,
            after,
            universe=tracked_keys,
            expected={
                "nw-test-agent.exists": set_to(True),
                "manifest.exists": set_to(True),
                # stranger-agent.exists must remain False (implicit-unchanged)
            },
        )

    def test_installed_toml_contains_required_fields(self, tmp_path, monkeypatch):
        """
        GIVEN: A source agent with name, description, Claude model, and a body
        WHEN: install() runs
        THEN: The .toml file is valid TOML containing name, description, and
              developer_instructions, without promoting the Claude model
        """
        # bypass: single-slot content assertion after install
        context, _ = _make_context(tmp_path)
        codex_agents_dir = tmp_path / "home" / ".codex" / "agents"
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_dirs(monkeypatch, codex_agents_dir, codex_config_dir)

        plugin = CodexAgentsPlugin()
        result = plugin.install(context)
        assert result.success is True

        toml_content = (codex_agents_dir / "nw-test-agent.toml").read_text(
            encoding="utf-8"
        )
        parsed = tomllib.loads(toml_content)

        assert parsed["name"] == "nw-test-agent"
        assert parsed["description"] == "A test agent"
        assert "model" not in parsed
        assert "You are a test agent." in parsed["developer_instructions"]

    def test_install_manifest_records_installed_names(self, tmp_path, monkeypatch):
        """
        GIVEN: Two agents in source (nw-alpha, nw-beta)
        WHEN: install() runs
        THEN: The manifest's installed_agents list contains both names sorted
        """
        agents = {
            "nw-alpha": "---\nname: nw-alpha\ndescription: a\n---\nbody-a\n",
            "nw-beta": "---\nname: nw-beta\ndescription: b\n---\nbody-b\n",
        }
        context, _ = _make_context(tmp_path, agents=agents)
        codex_agents_dir = tmp_path / "home" / ".codex" / "agents"
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_dirs(monkeypatch, codex_agents_dir, codex_config_dir)

        plugin = CodexAgentsPlugin()
        plugin.install(context)

        manifest = json.loads(
            (codex_agents_dir / ".nwave-agents-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["installed_agents"] == ["nw-alpha", "nw-beta"]


class TestVerify:
    """verify: success path after install."""

    def test_verify_passes_after_successful_install(self, tmp_path, monkeypatch):
        """
        GIVEN: A successful install
        WHEN: verify() runs
        THEN: Returns success
        """
        context, _ = _make_context(tmp_path)
        codex_agents_dir = tmp_path / "home" / ".codex" / "agents"
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_dirs(monkeypatch, codex_agents_dir, codex_config_dir)

        plugin = CodexAgentsPlugin()
        plugin.install(context)
        result = plugin.verify(context)

        assert result.success is True

    def test_verify_rejects_empty_installed_agent_population(
        self, tmp_path, monkeypatch
    ):
        """CONTRACT_SHAPE: bounded-change

        Outcome anchor: an empty Codex role population is never reported healthy.
        """
        context, _ = _make_context(tmp_path)
        target = tmp_path / ".codex" / "agents"
        target.mkdir(parents=True)
        _patch_codex_dirs(monkeypatch, target, target.parent)
        (target / ".nwave-agents-manifest.json").write_text(
            '{"installed_agents": []}\n', encoding="utf-8"
        )

        assert CodexAgentsPlugin().verify(context).success is False

    def test_verify_rejects_malformed_or_unloadable_agent_toml(
        self, tmp_path, monkeypatch
    ):
        """CONTRACT_SHAPE: bounded-change

        Outcome anchor: advertised Codex roles are TOML-loadable with required fields.
        """
        context, _ = _make_context(tmp_path)
        target = tmp_path / ".codex" / "agents"
        target.mkdir(parents=True)
        _patch_codex_dirs(monkeypatch, target, target.parent)
        (target / ".nwave-agents-manifest.json").write_text(
            '{"installed_agents": ["nw-broken"]}\n', encoding="utf-8"
        )
        (target / "nw-broken.toml").write_text(
            'name = "nw-broken"\ndeveloper_instructions = "unterminated\n',
            encoding="utf-8",
        )

        assert CodexAgentsPlugin().verify(context).success is False

    @pytest.mark.parametrize("mutation", ["missing-one", "unexpected-one"])
    def test_verify_conserves_exact_public_source_population(
        self, tmp_path, monkeypatch, mutation
    ):
        """CONTRACT_SHAPE: bounded-change

        Outcome anchor: every and only public Codex roles are reported loadable.
        """
        agents = {
            name: (
                "---\n"
                f"name: {name}\n"
                f"description: {name}\n"
                "---\n\n"
                f"Instructions for {name}.\n"
            )
            for name in ("nw-alpha", "nw-beta")
        }
        context, _ = _make_context(tmp_path, agents=agents)
        context.dev_mode = False
        target = tmp_path / ".codex" / "agents"
        target.parent.mkdir(parents=True)
        _patch_codex_dirs(monkeypatch, target, target.parent)
        monkeypatch.setattr(
            codex_agents_plugin,
            "load_public_agents",
            lambda _root: {"alpha", "beta"},
        )
        plugin = CodexAgentsPlugin()
        assert plugin.install(context).success is True

        manifest_path = target / ".nwave-agents-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if mutation == "missing-one":
            manifest["installed_agents"].remove("nw-beta")
        else:
            manifest["installed_agents"].append("nw-unexpected")
            (target / "nw-unexpected.toml").write_text(
                'name = "nw-unexpected"\n'
                'description = "unexpected"\n'
                'developer_instructions = "unexpected"\n',
                encoding="utf-8",
            )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        assert plugin.verify(context).success is False


def test_empty_codex_home_is_consistently_treated_as_unset(
    tmp_path, monkeypatch
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: an empty CODEX_HOME uses the same native default everywhere.
    """
    monkeypatch.setenv("CODEX_HOME", "")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    expected = tmp_path / ".codex"

    assert codex_agents_plugin._codex_config_dir() == expected
    assert codex_agents_plugin._codex_agents_dir() == expected / "agents"
    assert codex_des_plugin._codex_config_dir() == expected
    assert codex_skills_plugin._codex_config_dir() == expected


class TestInstallCleansPreviouslyOwnedAgents:
    """install: clean-then-write -- the target holds ONLY what this run wrote.

    Defect 2026-08-22: a --dev install wrote private agents plus a 51-entry
    manifest; the next public install rewrote the manifest to 35 but left the
    16 private TOMLs on disk (IP leak past the public filter).
    """

    def _seed_previous_install(
        self, codex_agents_dir: Path, owned: list[str], foreign: list[str]
    ) -> None:
        codex_agents_dir.mkdir(parents=True)
        for stem in owned + foreign:
            (codex_agents_dir / f"{stem}.toml").write_text(
                f'name = "{stem}"\n', encoding="utf-8"
            )
        (codex_agents_dir / ".nwave-agents-manifest.json").write_text(
            json.dumps({"installed_agents": sorted(owned), "version": "1.0"}),
            encoding="utf-8",
        )

    def test_stale_manifest_owned_private_agent_is_removed(self, tmp_path, monkeypatch):
        """
        GIVEN: the previous install wrote nw-private-agent.toml and listed it
               in the manifest, and the current source no longer ships it
        WHEN: install() runs
        THEN: nw-private-agent.toml is GONE, the shipped agent is written,
              and a foreign user agent is untouched.
        """
        context, _ = _make_context(tmp_path)
        codex_agents_dir = tmp_path / "home" / ".codex" / "agents"
        codex_config_dir = tmp_path / "home" / ".codex"
        self._seed_previous_install(
            codex_agents_dir,
            owned=["nw-test-agent", "nw-private-agent"],
            foreign=["my-own-agent"],
        )
        _patch_codex_dirs(monkeypatch, codex_agents_dir, codex_config_dir)

        def snapshot() -> dict[str, object]:
            return {
                "nw-test-agent.exists": (
                    codex_agents_dir / "nw-test-agent.toml"
                ).is_file(),
                "nw-private-agent.exists": (
                    codex_agents_dir / "nw-private-agent.toml"
                ).is_file(),
                "my-own-agent.exists": (
                    codex_agents_dir / "my-own-agent.toml"
                ).is_file(),
            }

        before = snapshot()
        result = CodexAgentsPlugin().install(context)
        after = snapshot()

        assert result.success is True, result.errors
        assert_state_delta(
            before,
            after,
            universe=set(before),
            expected={"nw-private-agent.exists": set_to(False)},
        )
        manifest = json.loads(
            (codex_agents_dir / ".nwave-agents-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["installed_agents"] == ["nw-test-agent"]

    def test_unmanifested_nw_prefixed_file_is_not_ownership(
        self, tmp_path, monkeypatch
    ):
        """A nw-* file absent from the previous manifest is foreign (the
        preflight's concern), not the plugin's to delete."""
        context, _ = _make_context(tmp_path)
        codex_agents_dir = tmp_path / "home" / ".codex" / "agents"
        codex_config_dir = tmp_path / "home" / ".codex"
        self._seed_previous_install(
            codex_agents_dir, owned=["nw-test-agent"], foreign=["nw-user-made"]
        )
        _patch_codex_dirs(monkeypatch, codex_agents_dir, codex_config_dir)

        result = CodexAgentsPlugin().install(context)

        assert result.success is True, result.errors
        assert (codex_agents_dir / "nw-user-made.toml").is_file()


class TestUninstallRemovesOnlyNwaveAgents:
    """uninstall: removes only manifest-listed agents, preserves user-created ones."""

    def test_uninstall_preserves_user_created_agents(self, tmp_path, monkeypatch):
        """
        GIVEN: nWave-installed agent (nw-test-agent.toml) AND a user-created
               agent (custom-user-agent.toml) in the same target directory
        WHEN: uninstall() runs
        THEN: nw-test-agent.toml is removed, custom-user-agent.toml is preserved,
              and the manifest is removed.
        """
        context, _ = _make_context(tmp_path)
        codex_agents_dir = tmp_path / "home" / ".codex" / "agents"
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_dirs(monkeypatch, codex_agents_dir, codex_config_dir)

        plugin = CodexAgentsPlugin()
        plugin.install(context)

        # Plant a user-created agent the plugin must NOT touch
        user_toml = codex_agents_dir / "custom-user-agent.toml"
        user_toml.write_text('name = "custom"\ndeveloper_instructions = """\nbody\n"""')

        tracked_keys = {
            "nw-test-agent.exists",
            "custom-user-agent.exists",
            "manifest.exists",
        }

        def snapshot() -> dict[str, object]:
            return {
                "nw-test-agent.exists": (
                    codex_agents_dir / "nw-test-agent.toml"
                ).is_file(),
                "custom-user-agent.exists": user_toml.is_file(),
                "manifest.exists": (
                    codex_agents_dir / ".nwave-agents-manifest.json"
                ).is_file(),
            }

        before = snapshot()
        assert before == {
            "nw-test-agent.exists": True,
            "custom-user-agent.exists": True,
            "manifest.exists": True,
        }

        result = plugin.uninstall(context)
        after = snapshot()

        assert result.success is True
        assert_state_delta(
            before,
            after,
            universe=tracked_keys,
            expected={
                "nw-test-agent.exists": set_to(False),
                "manifest.exists": set_to(False),
                # custom-user-agent.exists is implicit-unchanged
            },
        )


class TestCapabilityPreamble:
    """Capability-mapping preamble derived mechanically from the tools block.

    Codex's agent TOML schema has no tools field, so a role body written
    against Claude semantic tools (Read, Write, ...) must carry an explicit
    translation: granted tools map to the native Codex surface, undeclared
    tools become explicit denials (source-blind roles stay source-blind).
    """

    @staticmethod
    def _instructions(tools_line: str) -> str:
        source = (
            "---\n"
            "name: nw-x\n"
            "description: d\n"
            f"{tools_line}"
            "---\n\n"
            "# Role\n\n"
            "Never use Bash to read files.\n"
        )
        document = tomllib.loads(_transform_agent(source, "nw-x"))
        return document["developer_instructions"]

    def test_declared_read_sanctions_native_readonly_shell(self):
        # bypass: pure function
        instructions = self._instructions("tools: Read, Write, Edit, Bash\n")
        assert "ARE the sanctioned Read on this platform" in instructions

    def test_write_only_agent_denies_reading_and_execution(self):
        # bypass: pure function -- source-blind by design must survive
        instructions = self._instructions("tools: Write\n")
        assert "sanctioned Read" not in instructions
        assert "Reading file contents is NOT granted" in instructions
        assert "Command execution is NOT granted" in instructions

    def test_list_shaped_tools_block_also_yields_preamble(self):
        # bypass: pure function -- frontmatter may declare tools as a YAML list
        instructions = self._instructions("tools: [Read, Glob, Grep]\n")
        assert "ARE the sanctioned Read on this platform" in instructions
        assert "Creating or modifying files is NOT granted" in instructions
        assert "Command execution is NOT granted" in instructions

    def test_scoped_shell_specifier_grants_only_what_it_names(self):
        # bypass: pure function -- a Bash(...) specifier is not bare Bash
        instructions = self._instructions("tools: Read, Bash(des code-fact:*)\n")
        assert "run EXACTLY these commands via your native shell" in instructions
        assert "Bash(des code-fact:*)" in instructions
        # The scope IS the grant: the specifier must neither widen the role to
        # the whole shell nor lift a denial it never named.
        assert "command execution via your native shell." not in instructions
        assert "Command execution is NOT granted" not in instructions
        assert "File and content search is NOT granted" in instructions
        assert "Creating or modifying files is NOT granted" in instructions

    def test_agent_without_tools_is_unchanged(self):
        # bypass: pure function -- absent tools block keeps today's output
        source = "---\nname: nw-x\ndescription: d\n---\n\n# Role\n\nBody.\n"
        transformed = _transform_agent(source, "nw-x")
        assert "Codex Capability Mapping" not in transformed
        document = tomllib.loads(transformed)
        assert document["developer_instructions"] == "\n\n# Role\n\nBody.\n"
