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
    _render_toml_agent,
    _toml_multiline_string,
    _toml_string,
    _transform_agent,
    _warn_if_tools_dropped,
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

    # Canonical batching-fragment source; install() loads it once per run.
    templates_dir = framework_source / "templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "tool-batching-fragment.md").write_text(
        "BATCH-FRAGMENT\n", encoding="utf-8"
    )

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
        }
        result = _extract_scalar_fields(frontmatter)
        assert "tools" not in result
        assert "maxTurns" not in result
        assert "disable-model-invocation" not in result
        assert "permissionMode" not in result
        assert "skills" not in result

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


class TestWarnIfToolsDropped:
    """_warn_if_tools_dropped: emits warning when tools key present."""

    def test_warns_when_tools_present(self, caplog):
        # bypass: pure function, single observable (log output)
        with caplog.at_level(
            logging.WARNING, logger="scripts.install.plugins.codex_agents_plugin"
        ):
            _warn_if_tools_dropped("nw-foo", {"tools": ["Read", "Bash"]})
        assert any("tools" in msg for msg in caplog.messages)
        assert any("nw-foo" in msg for msg in caplog.messages)

    def test_no_warning_when_tools_absent(self, caplog):
        # bypass: pure function, single observable
        with caplog.at_level(
            logging.WARNING, logger="scripts.install.plugins.codex_agents_plugin"
        ):
            _warn_if_tools_dropped("nw-foo", {"name": "nw-foo", "description": "x"})
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
