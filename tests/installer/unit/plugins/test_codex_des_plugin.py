"""Unit tests for Codex CLI DES hook installer plugin.

Tests validate that:
- validate_prerequisites() skips gracefully when Codex CLI is not detected
- validate_prerequisites() fails when Codex is detected but DES module missing
- install() writes a PreToolUse hook entry into ~/.codex/hooks.json
- install() writes a manifest tracking the installed hook config
- verify() returns success after a successful install
- uninstall() removes only nWave DES hook entries, preserving user hooks

Tests follow hexagonal architecture - mocks only at port boundaries.
The state-delta paradigm guards multi-slot mutations (hooks.json content +
manifest presence + user-hook preservation).
"""

from __future__ import annotations

import base64
import inspect
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from nwave_ai.state_delta import assert_state_delta, set_to

from scripts.install.plugins import codex_des_plugin
from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.codex_des_plugin import CodexDESPlugin


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_context(
    tmp_path: Path,
    *,
    des_module_exists: bool = True,
) -> InstallContext:
    """Create an InstallContext with a configurable DES module presence."""
    project_root = tmp_path / "project"
    framework_source = project_root / "nWave"
    framework_source.mkdir(parents=True)

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    if des_module_exists:
        des_dir = tmp_path / ".nwave" / "runtime" / "des"
        des_dir.mkdir(parents=True)
        (des_dir / "__init__.py").write_text("", encoding="utf-8")
        resolver = (
            tmp_path
            / ".nwave"
            / "nWave"
            / "hooks"
            / "orchestrator_affordance_refresh.py"
        )
        resolver.parent.mkdir(parents=True)
        resolver.write_text(
            'import json\nprint(json.dumps({"hookSpecificOutput": '
            '{"hookEventName": "SessionStart", "additionalContext": '
            '"standing-loop catalogue available"}}))\n',
            encoding="utf-8",
        )

    return InstallContext(
        claude_dir=claude_dir,
        scripts_dir=project_root / "scripts",
        templates_dir=framework_source / "templates",
        logger=MagicMock(),
        project_root=project_root,
        framework_source=framework_source,
    )


@pytest.fixture(autouse=True)
def _host_neutral_runtime_is_tmp_scoped(tmp_path: Path, monkeypatch) -> None:
    """Make prerequisite checks observe only the fixture's runtime root."""
    runtime_root = tmp_path / ".nwave" / "runtime"
    monkeypatch.setattr(
        "scripts.install.plugins.codex_des_plugin.host_neutral_runtime_dir",
        lambda: runtime_root,
    )


def _patch_codex_config_dir(monkeypatch, codex_config_dir: Path) -> None:
    """Redirect _codex_config_dir() to a tmp path."""
    monkeypatch.setattr(
        "scripts.install.plugins.codex_des_plugin._codex_config_dir",
        lambda: codex_config_dir,
    )


def _patch_path_resolvers(monkeypatch) -> None:
    """Force deterministic Python and PYTHONPATH resolution."""
    monkeypatch.setattr(
        "scripts.install.plugins.codex_des_plugin.resolve_python_command_for_spawn",
        lambda: "/usr/bin/python3",
    )
    monkeypatch.setattr(
        "scripts.install.plugins.codex_des_plugin.resolve_des_lib_path_for_spawn",
        lambda: "/home/tester/.claude/lib/python",
    )


def _patch_codex_binary_absent(monkeypatch) -> None:
    """Force shutil.which('codex') to return None inside the plugin."""
    monkeypatch.setattr(
        "scripts.install.plugins.codex_des_plugin._shutil.which",
        lambda _name: None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidatePrerequisites:
    """validate_prerequisites: skip / fail / proceed branches."""

    def test_skips_gracefully_when_codex_not_detected(self, tmp_path, monkeypatch):
        """
        GIVEN: ~/.codex/ does not exist AND `codex` not in PATH
        WHEN: validate_prerequisites() runs
        THEN: Returns success with skip message
        """
        context = _make_context(tmp_path)
        codex_config_dir = tmp_path / "home" / ".codex"  # does NOT exist
        _patch_codex_config_dir(monkeypatch, codex_config_dir)
        _patch_codex_binary_absent(monkeypatch)

        plugin = CodexDESPlugin()
        result = plugin.validate_prerequisites(context)

        assert result.success is True
        assert (
            "skip" in result.message.lower() or "not detected" in result.message.lower()
        )

    def test_fails_when_codex_present_but_des_module_missing(
        self, tmp_path, monkeypatch
    ):
        """
        GIVEN: Codex is detected (~/.codex/ exists) but DES Python module is NOT
        WHEN: validate_prerequisites() runs
        THEN: Returns failure citing the DES module
        """
        context = _make_context(tmp_path, des_module_exists=False)
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_config_dir(monkeypatch, codex_config_dir)

        plugin = CodexDESPlugin()
        result = plugin.validate_prerequisites(context)

        assert result.success is False
        assert "des" in result.message.lower()


class TestInstallWritesHooksJsonAndManifest:
    """install: writes hooks.json with the nWave DES entry + manifest."""

    def test_install_creates_hooks_json_and_manifest(self, tmp_path, monkeypatch):
        """
        GIVEN: Codex detected and DES module installed
        WHEN: install() runs (no prior hooks.json)
        THEN: hooks.json contains exactly one nWave DES entry pointing to the
              claude_code_hook_adapter, and the manifest exists.
        """
        context = _make_context(tmp_path)
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_config_dir(monkeypatch, codex_config_dir)
        _patch_path_resolvers(monkeypatch)

        hooks_path = codex_config_dir / "hooks.json"
        manifest_path = codex_config_dir / ".nwave-des-manifest.json"

        tracked = {"hooks.exists", "manifest.exists"}

        def snapshot() -> dict[str, object]:
            return {
                "hooks.exists": hooks_path.is_file(),
                "manifest.exists": manifest_path.is_file(),
            }

        before = snapshot()

        plugin = CodexDESPlugin()
        result = plugin.install(context)

        after = snapshot()

        assert result.success is True
        assert_state_delta(
            before,
            after,
            universe=tracked,
            expected={
                "hooks.exists": set_to(True),
                "manifest.exists": set_to(True),
            },
        )

        # Verify hooks.json content shape and command wiring.
        # Schema per DDD-1 (codex-empirical-e2e-support, 2026-05-13): event-keyed
        # object root — {"hooks": {"PreToolUse": [<matcher-group>, ...]}}.
        doc = json.loads(hooks_path.read_text(encoding="utf-8"))
        assert isinstance(doc, dict)
        assert isinstance(doc.get("hooks"), dict)
        pretool = doc["hooks"].get("PreToolUse")
        assert isinstance(pretool, list)
        assert len(pretool) == 1
        entry = pretool[0]
        # The matcher is tied to the tool surface observed on the running
        # Codex host. Bash/apply_patch are not emitted tool names here.
        assert entry["matcher"] == "^exec_command$"
        command = entry["hooks"][0]["command"]
        assert "claude_code_hook_adapter" in command
        assert "/usr/bin/python3" not in command
        assert "/home/tester/.claude/lib/python" not in command
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        launcher = Path(manifest["launcher_file"])
        assert str(launcher) in shlex.split(command)
        assert "SessionStart" not in doc["hooks"]
        assert "session_start_launcher_file" not in manifest
        assert "resolver_script_file" not in manifest

    def test_launcher_hook_builder_has_no_fixture_specific_magic_branch(self):
        """CONTRACT_SHAPE: unbounded-preservation

        Outcome anchor: installed semantics never depend on test fixture values.
        """
        source = inspect.getsource(codex_des_plugin._build_launcher_hook_entry)
        assert "/usr/bin/python3" not in source
        assert "/home/tester/.claude/lib/python" not in source

    @pytest.mark.parametrize(
        ("python_path", "pythonpath"),
        [
            (
                "/Users/Ada Lovelace/O'Brien/$(touch nope)/`whoami`;python",
                "/Users/Ada Lovelace/O'Brien/$(touch nope)/`whoami`;lib",
            ),
            (
                'C:/Users/Ada Lovelace/"quoted"/$(touch nope)/`whoami`;python.exe',
                'C:/Users/Ada Lovelace/"quoted"/$(touch nope)/`whoami`;lib',
            ),
        ],
    )
    def test_install_materializes_shell_independent_launcher_for_hostile_paths(
        self, tmp_path, monkeypatch, python_path, pythonpath
    ):
        """CONTRACT_SHAPE: bounded-change

        Outcome anchor: the installed Codex hook cannot reinterpret path bytes.
        """
        context = _make_context(tmp_path)
        codex_dir = tmp_path / "codex home with spaces"
        codex_dir.mkdir()
        _patch_codex_config_dir(monkeypatch, codex_dir)
        monkeypatch.setattr(
            codex_des_plugin,
            "resolve_python_command_for_spawn",
            lambda: python_path,
        )
        monkeypatch.setattr(
            codex_des_plugin,
            "resolve_des_lib_path_for_spawn",
            lambda: pythonpath,
        )

        result = CodexDESPlugin().install(context)
        assert result.success is True
        manifest = json.loads(
            (codex_dir / ".nwave-des-manifest.json").read_text(encoding="utf-8")
        )
        launcher = Path(manifest["launcher_file"])
        launcher_source = launcher.read_text(encoding="utf-8")
        compile(launcher_source, str(launcher), "exec")

        doc = json.loads((codex_dir / "hooks.json").read_text(encoding="utf-8"))
        command = doc["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        command_argv = shlex.split(command)
        assert "pre-tool-use" in command
        assert str(launcher) in command_argv
        assert command_argv[-1] == "pre-tool-use"
        assert python_path not in command
        assert pythonpath not in command
        assert manifest["python_path"] == python_path
        assert manifest["pythonpath"] == pythonpath
        assert launcher in result.installed_files

    def test_exact_installed_launcher_command_executes_without_injection(
        self, tmp_path, monkeypatch
    ):
        """CONTRACT_SHAPE: bounded-change

        Outcome anchor: Codex executes the serialized installed hook safely.
        """
        context = _make_context(tmp_path)
        codex_dir = tmp_path / "codex home; $(touch sentinel) `whoami`"
        codex_dir.mkdir()
        _patch_codex_config_dir(monkeypatch, codex_dir)
        repo_root = Path(__file__).resolve().parents[4]
        pythonpath = str(repo_root / "src")
        monkeypatch.setattr(
            codex_des_plugin,
            "resolve_python_command_for_spawn",
            lambda: sys.executable,
        )
        monkeypatch.setattr(
            codex_des_plugin,
            "resolve_des_lib_path_for_spawn",
            lambda: pythonpath,
        )

        assert CodexDESPlugin().install(context).success is True
        manifest = json.loads(
            (codex_dir / ".nwave-des-manifest.json").read_text(encoding="utf-8")
        )
        launcher = Path(manifest["launcher_file"])
        assert launcher.is_file()
        doc = json.loads((codex_dir / "hooks.json").read_text(encoding="utf-8"))
        command = doc["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        assert shlex.split(command) == [
            sys.executable,
            str(launcher),
            "pre-tool-use",
        ]
        assert pythonpath not in command
        completed = subprocess.run(
            command,
            shell=True,
            input='{"tool_name":"Read","tool_input":{}}',
            text=True,
            capture_output=True,
            cwd=repo_root,
            timeout=10,
            check=False,
        )

        assert completed.returncode == 0, completed.stderr
        assert not (repo_root / "sentinel").exists()

    @pytest.mark.parametrize("override", [False, True], ids=["default-home", "hostile"])
    def test_windows_host_serializes_canonical_launcher_as_encoded_powershell(
        self, tmp_path, monkeypatch, override
    ):
        """CONTRACT_SHAPE: bounded-change

        Outcome anchor: Windows Codex receives an exact, cmd-opaque launcher command.

        Native PowerShell execution remains a Windows CI obligation; on Linux this
        test validates the complete serialization boundary by decoding its payload.
        """
        context = _make_context(tmp_path)
        hostile_name = "Codex O'Brien %NWAVE_TEST%! & ^ (unsafe) with spaces"
        codex_dir = tmp_path / (hostile_name if override else ".codex")
        codex_dir.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        if override:
            monkeypatch.setenv("CODEX_HOME", str(codex_dir))
        else:
            monkeypatch.delenv("CODEX_HOME", raising=False)
        monkeypatch.setattr(
            codex_des_plugin,
            "os",
            SimpleNamespace(name="nt", environ=os.environ),
        )
        _patch_path_resolvers(monkeypatch)

        assert CodexDESPlugin().install(context).success is True
        doc = json.loads((codex_dir / "hooks.json").read_text(encoding="utf-8"))
        command = doc["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        manifest = json.loads(
            (codex_dir / ".nwave-des-manifest.json").read_text(encoding="utf-8")
        )

        launcher = Path(manifest["launcher_file"])
        assert launcher == codex_dir / codex_des_plugin._LAUNCHER_FILENAME
        tokens = command.split()
        assert tokens[:3] == ["powershell", "-NoProfile", "-EncodedCommand"]
        assert len(tokens) == 4
        encoded = tokens[3]
        assert re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", encoded)
        assert hostile_name not in command
        decoded = base64.b64decode(encoded).decode("utf-16le")

        def ps_literal(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"

        expected = (
            f"& {ps_literal(sys.executable)} {ps_literal(str(launcher))} "
            f"{ps_literal('pre-tool-use')}"
        )
        assert decoded == expected

        # A command containing the canonical path/event merely as a substring
        # is not equivalent and must fail semantic verification.
        tampered = base64.b64encode((decoded + " extra").encode("utf-16le")).decode(
            "ascii"
        )
        doc["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = (
            f"powershell -NoProfile -EncodedCommand {tampered}"
        )
        (codex_dir / "hooks.json").write_text(json.dumps(doc), encoding="utf-8")
        assert CodexDESPlugin().verify(context).success is False

    @pytest.mark.parametrize(
        "hostile",
        [
            "/Users/Ada Lovelace/O'Brien/$(touch nope)/`whoami`;still-one",
            'C:/Users/Ada Lovelace/"quoted"/$(touch nope)/`whoami`;still-one',
        ],
    )
    def test_hook_invocation_separates_argv_and_environment_without_shell_parsing(
        self, hostile
    ):
        """CONTRACT_SHAPE: bounded-change

        Outcome anchor: Codex executes DES without reinterpreting user path bytes.
        """
        build_invocation = getattr(codex_des_plugin, "_build_hook_invocation", None)
        assert callable(build_invocation), (
            "WHAT: Codex DES exposes only a shell command string. WHY: shell "
            "grammars reinterpret spaces and metacharacters differently across "
            "hosts. HOW: generate a platform-neutral argv + env invocation."
        )
        invocation = build_invocation(hostile, hostile)

        assert invocation["argv"] == [
            hostile,
            "-m",
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
            "pre-tool-use",
        ]
        assert invocation["env"] == {"PYTHONPATH": hostile}

    def test_hook_invocation_executes_literal_pre_tool_use_argv_without_a_shell(self):
        """CONTRACT_SHAPE: bounded-change

        Outcome anchor: the generated representation reaches Python as literal argv.
        """
        build_invocation = getattr(codex_des_plugin, "_build_hook_invocation", None)
        assert callable(build_invocation)
        invocation = build_invocation(
            sys.executable,
            str(Path(__file__).resolve().parents[4] / "src"),
        )
        env = os.environ.copy()
        env.update(invocation["env"])

        completed = subprocess.run(
            invocation["argv"],
            input='{"tool_name":"Read","tool_input":{}}',
            text=True,
            capture_output=True,
            env=env,
            cwd=Path(__file__).resolve().parents[4],
            timeout=10,
            check=False,
        )

        assert invocation["argv"][-1] == "pre-tool-use"
        assert completed.returncode == 0, completed.stderr

    def test_reinstall_does_not_duplicate_nwave_entries(self, tmp_path, monkeypatch):
        """
        GIVEN: A prior install left one nWave DES entry in hooks.json
            AND a user-created hook entry is also present
        WHEN: install() runs again
        THEN: The user entry is preserved AND there is still exactly one
              nWave DES entry (no duplication on reinstall).
        """
        context = _make_context(tmp_path)
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_config_dir(monkeypatch, codex_config_dir)
        _patch_path_resolvers(monkeypatch)

        plugin = CodexDESPlugin()
        plugin.install(context)

        # Prepend a user-created hook entry into the event-keyed PreToolUse list.
        # DDD-1: root is an object with "hooks.PreToolUse" list of matcher groups.
        hooks_path = codex_config_dir / "hooks.json"
        doc = json.loads(hooks_path.read_text(encoding="utf-8"))
        doc["hooks"].setdefault("PreToolUse", []).insert(
            0,
            {
                "matcher": "^Bash$",
                "hooks": [
                    {
                        "type": "command",
                        "command": "/usr/bin/echo user-hook",
                        "timeout": 10,
                    }
                ],
            },
        )
        hooks_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

        # Reinstall
        result = plugin.install(context)
        assert result.success is True

        final_doc = json.loads(hooks_path.read_text(encoding="utf-8"))
        pretool = final_doc["hooks"]["PreToolUse"]
        nwave_entries = [
            e
            for e in pretool
            if any(
                "claude_code_hook_adapter" in h.get("command", "")
                for h in e.get("hooks", [])
            )
        ]
        user_entries = [
            e
            for e in pretool
            if any("echo user-hook" in h.get("command", "") for h in e.get("hooks", []))
        ]
        assert len(nwave_entries) == 1, "nWave DES entry must not duplicate"
        assert len(user_entries) == 1, "User hook must be preserved"
        assert "SessionStart" not in final_doc["hooks"]

    def test_reinstall_replaces_launcher_owned_hook_after_interpreter_change(
        self, tmp_path, monkeypatch
    ):
        """A changed interpreter does not change nWave hook ownership."""
        context = _make_context(tmp_path)
        codex_dir = tmp_path / "home" / ".codex"
        codex_dir.mkdir(parents=True)
        _patch_codex_config_dir(monkeypatch, codex_dir)
        _patch_path_resolvers(monkeypatch)

        plugin = CodexDESPlugin()
        assert plugin.install(context).success is True
        hooks_path = codex_dir / "hooks.json"
        hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
        user_command = "echo user-owned"
        hooks["hooks"]["PreToolUse"].insert(
            0,
            {
                "matcher": "^Bash$",
                "hooks": [{"type": "command", "command": user_command}],
            },
        )
        hooks_path.write_text(
            json.dumps(hooks).replace(sys.executable, "/obsolete/venv/bin/python"),
            encoding="utf-8",
        )

        assert plugin.install(context).success is True
        commands = [
            hook["command"]
            for group in json.loads(hooks_path.read_text(encoding="utf-8"))["hooks"][
                "PreToolUse"
            ]
            for hook in group["hooks"]
        ]
        assert "/obsolete/venv/bin/python" not in "\n".join(commands)
        assert commands.count(user_command) == 1
        assert len(commands) == 2

    def test_unproven_legacy_direct_hook_survives_reinstall_and_uninstall(
        self, tmp_path, monkeypatch
    ):
        """CONTRACT_SHAPE: unbounded-preservation

        Outcome anchor: a direct legacy hook needs a manifest ownership proof.
        """
        context = _make_context(tmp_path)
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        _patch_codex_config_dir(monkeypatch, codex_dir)
        _patch_path_resolvers(monkeypatch)
        user_command = "echo user-owned"
        legacy_command = (
            "PYTHONPATH=/legacy python3 -m "
            "des.adapters.drivers.hooks.claude_code_hook_adapter pre-tool-use"
        )
        (codex_dir / "hooks.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "^Bash$",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": user_command,
                                        "statusMessage": "nWave DES validation...",
                                    }
                                ],
                            },
                            {
                                "matcher": "^Bash$",
                                "hooks": [
                                    {"type": "command", "command": legacy_command}
                                ],
                            },
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        plugin = CodexDESPlugin()
        assert plugin.install(context).success is True
        after_install = json.loads(
            (codex_dir / "hooks.json").read_text(encoding="utf-8")
        )
        install_commands = [
            hook["command"]
            for group in after_install["hooks"]["PreToolUse"]
            for hook in group.get("hooks", [])
        ]
        assert install_commands.count(user_command) == 1
        assert install_commands.count(legacy_command) == 1
        assert len(install_commands) == 3

        assert plugin.uninstall(context).success is True
        after_uninstall = json.loads(
            (codex_dir / "hooks.json").read_text(encoding="utf-8")
        )
        uninstall_commands = [
            hook["command"]
            for group in after_uninstall["hooks"]["PreToolUse"]
            for hook in group.get("hooks", [])
        ]
        assert uninstall_commands == [user_command, legacy_command]
        assert not (codex_dir / ".nwave-des-manifest.json").exists()


class TestVerify:
    """verify: success after install."""

    def test_verify_passes_after_install(self, tmp_path, monkeypatch):
        """
        GIVEN: A successful install
        WHEN: verify() runs
        THEN: Returns success
        """
        context = _make_context(tmp_path)
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_config_dir(monkeypatch, codex_config_dir)
        _patch_path_resolvers(monkeypatch)

        plugin = CodexDESPlugin()
        plugin.install(context)
        result = plugin.verify(context)

        assert result.success is True

    def test_tampered_manifest_cannot_authorize_external_launcher(
        self, tmp_path, monkeypatch
    ):
        """CONTRACT_SHAPE: bounded-change

        Outcome anchor: Codex verification trusts only its canonical launcher.
        """
        context = _make_context(tmp_path)
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        _patch_codex_config_dir(monkeypatch, codex_dir)
        external = tmp_path / "user-owned.py"
        external.write_text("user data\n", encoding="utf-8")
        canonical = codex_dir / codex_des_plugin._LAUNCHER_FILENAME
        canonical.write_text("canonical\n", encoding="utf-8")
        command = shlex.join([sys.executable, str(canonical), "pre-tool-use"])
        (codex_dir / "hooks.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "^Bash$",
                                "hooks": [{"type": "command", "command": command}],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        (codex_dir / ".nwave-des-manifest.json").write_text(
            json.dumps({"launcher_file": str(external)}), encoding="utf-8"
        )

        plugin = CodexDESPlugin()
        assert plugin.verify(context).success is False
        assert plugin.uninstall(context).success is True
        assert external.read_text(encoding="utf-8") == "user data\n"
        assert canonical.read_text(encoding="utf-8") == "canonical\n"
        assert json.loads((codex_dir / "hooks.json").read_text(encoding="utf-8")) == {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "^Bash$",
                        "hooks": [{"type": "command", "command": command}],
                    }
                ]
            }
        }
        assert (codex_dir / ".nwave-des-manifest.json").read_text(
            encoding="utf-8"
        ) == json.dumps({"launcher_file": str(external)})


class TestSessionStartReinstallReconciliation:
    """Reinstall reconciles only exact nWave SessionStart commands."""

    @pytest.mark.parametrize("command_format", ["posix", "encoded-powershell"])
    def test_reinstall_does_not_retain_legacy_nwave_session_start_hook(
        self, tmp_path, monkeypatch, command_format
    ):
        """CONTRACT_SHAPE: unbounded-preservation

        A reinstall leaves one current nWave hook and every foreign hook intact.

        The legacy command is the public pre-provenance form: interpreter,
        canonical launcher, then ``session-start``.  A lookalike with an extra
        argument is user-owned and must survive just like the Lyra hook.
        """
        context = _make_context(tmp_path)
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        _patch_codex_config_dir(monkeypatch, codex_dir)
        _patch_path_resolvers(monkeypatch)
        if command_format == "encoded-powershell":
            monkeypatch.setattr(
                codex_des_plugin,
                "os",
                SimpleNamespace(name="nt", environ=os.environ),
            )

        launcher_path = codex_dir / codex_des_plugin._SESSION_START_LAUNCHER_FILENAME
        current_command = codex_des_plugin._build_session_start_hook_entry(
            launcher_path
        )["hooks"][0]["command"]
        if command_format == "posix":
            legacy_command = shlex.join(
                ["/legacy/bin/python", str(launcher_path), "session-start"]
            )
            near_miss_command = shlex.join(
                [
                    "/legacy/bin/python",
                    str(launcher_path),
                    "session-start",
                    "--host-provenance=codex",
                    "--user-extension",
                ]
            )
        else:

            def encoded_command(*argv: str) -> str:
                powershell = " ".join(
                    ["&", *[codex_des_plugin._powershell_literal(arg) for arg in argv]]
                )
                encoded = base64.b64encode(powershell.encode("utf-16le")).decode(
                    "ascii"
                )
                return f"powershell -NoProfile -EncodedCommand {encoded}"

            legacy_command = encoded_command(
                "C:\\legacy\\python.exe", str(launcher_path), "session-start"
            )
            near_miss_command = encoded_command(
                "C:\\legacy\\python.exe",
                str(launcher_path),
                "session-start",
                "--host-provenance=codex",
                "--user-extension",
            )

        lyra_command = "python3 /developer/lyra/session_start.py session-start"
        hooks_path = codex_dir / "hooks.json"
        hooks_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "matcher": "startup|resume",
                                "hooks": [
                                    {"type": "command", "command": current_command}
                                ],
                            },
                            {
                                "matcher": "startup",
                                "hooks": [
                                    {"type": "command", "command": legacy_command}
                                ],
                            },
                            {
                                "matcher": "startup",
                                "hooks": [{"type": "command", "command": lyra_command}],
                            },
                            {
                                "matcher": "startup",
                                "hooks": [
                                    {"type": "command", "command": near_miss_command}
                                ],
                            },
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        def session_start_state() -> dict[str, object]:
            document = json.loads(hooks_path.read_text(encoding="utf-8"))
            commands = [
                hook["command"]
                for group in document["hooks"].get("SessionStart", [])
                for hook in group["hooks"]
            ]
            return {
                "session_start.current_nwave_count": commands.count(current_command),
                "session_start.legacy_nwave_present": legacy_command in commands,
                "session_start.lyra_present": lyra_command in commands,
                "session_start.near_miss_present": near_miss_command in commands,
            }

        before = session_start_state()
        result = CodexDESPlugin().install(context)
        after = session_start_state()

        assert result.success, (
            "WHAT: Codex reinstall did not complete. WHY: developers cannot restore a "
            "single current SessionStart affordance. HOW: make the installer accept the "
            "legacy SessionStart command while preserving user-owned hooks."
        )
        assert_state_delta(
            before,
            after,
            universe=set(before),
            expected={
                "session_start.current_nwave_count": set_to(0),
                "session_start.legacy_nwave_present": set_to(False),
            },
        )
        assert after["session_start.lyra_present"] is True, (
            "WHAT: the Lyra SessionStart hook disappeared. WHY: reinstall must preserve "
            "independent developer customisation. HOW: remove only exact nWave commands."
        )
        assert after["session_start.near_miss_present"] is True, (
            "WHAT: a SessionStart command with user-supplied extra arguments disappeared. "
            "WHY: a near-miss is not nWave-owned. HOW: require an exact legacy or current "
            "nWave command before removal."
        )

    @pytest.mark.parametrize("command_format", ["posix", "encoded-powershell"])
    def test_verify_rejects_stale_nwave_session_start_hook(
        self, tmp_path, monkeypatch, command_format
    ):
        """CONTRACT_SHAPE: bounded-change

        Verification cannot report healthy while a recognized legacy hook remains.
        """
        context = _make_context(tmp_path)
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        _patch_codex_config_dir(monkeypatch, codex_dir)
        _patch_path_resolvers(monkeypatch)
        if command_format == "encoded-powershell":
            monkeypatch.setattr(
                codex_des_plugin,
                "os",
                SimpleNamespace(name="nt", environ=os.environ),
            )

        plugin = CodexDESPlugin()
        assert plugin.install(context).success
        launcher_path = codex_dir / codex_des_plugin._SESSION_START_LAUNCHER_FILENAME
        if command_format == "posix":
            legacy_command = shlex.join(
                ["/legacy/bin/python", str(launcher_path), "session-start"]
            )
        else:
            powershell = " ".join(
                [
                    "&",
                    codex_des_plugin._powershell_literal("C:\\legacy\\python.exe"),
                    codex_des_plugin._powershell_literal(str(launcher_path)),
                    codex_des_plugin._powershell_literal("session-start"),
                ]
            )
            encoded = base64.b64encode(powershell.encode("utf-16le")).decode("ascii")
            legacy_command = f"powershell -NoProfile -EncodedCommand {encoded}"

        hooks_path = codex_dir / "hooks.json"
        document = json.loads(hooks_path.read_text(encoding="utf-8"))
        document["hooks"].setdefault("SessionStart", []).append(
            {
                "matcher": "startup",
                "hooks": [{"type": "command", "command": legacy_command}],
            }
        )
        hooks_path.write_text(json.dumps(document), encoding="utf-8")

        result = plugin.verify(context)

        assert result.success is False, (
            "WHAT: verification accepted an additional stale nWave SessionStart hook. "
            "WHY: a healthy Codex configuration contains exactly one current affordance. "
            "HOW: count both exact legacy and current nWave SessionStart commands and fail "
            "when the recognized population is not exactly one current command."
        )


class TestUninstallPreservesUserHooks:
    """uninstall: removes only nWave DES entries; user hooks survive."""

    def test_uninstall_preserves_user_hook_entries(self, tmp_path, monkeypatch):
        """
        GIVEN: hooks.json contains one nWave DES entry AND one user hook
        WHEN: uninstall() runs
        THEN: The user hook remains, the nWave entry is removed,
              and the manifest is deleted.
        """
        context = _make_context(tmp_path)
        codex_config_dir = tmp_path / "home" / ".codex"
        codex_config_dir.mkdir(parents=True)
        _patch_codex_config_dir(monkeypatch, codex_config_dir)
        _patch_path_resolvers(monkeypatch)

        plugin = CodexDESPlugin()
        plugin.install(context)

        hooks_path = codex_config_dir / "hooks.json"
        manifest_path = codex_config_dir / ".nwave-des-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        launcher_path = Path(manifest["launcher_file"])
        assert launcher_path.is_file()

        # Add a user-created hook on the event-keyed PreToolUse list (DDD-1).
        doc = json.loads(hooks_path.read_text(encoding="utf-8"))
        doc["hooks"].setdefault("PreToolUse", []).append(
            {
                "matcher": "^Bash$",
                "hooks": [
                    {
                        "type": "command",
                        "command": "/usr/bin/echo user-hook",
                        "timeout": 10,
                    }
                ],
            }
        )
        doc["hooks"].setdefault("SessionStart", []).append(
            {
                "matcher": "startup",
                "hooks": [
                    {
                        "type": "command",
                        "command": "/usr/bin/echo user-session-start",
                        "timeout": 10,
                    }
                ],
            }
        )
        hooks_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

        tracked = {
            "manifest.exists",
            "user_hook.present",
            "nwave_hook.present",
        }

        def snapshot() -> dict[str, object]:
            # DDD-1 event-keyed schema: walk every event's matcher-group list.
            if hooks_path.exists():
                doc = json.loads(hooks_path.read_text(encoding="utf-8"))
                events = doc.get("hooks", {}) if isinstance(doc, dict) else {}
                groups = [
                    entry
                    for entries in events.values()
                    if isinstance(entries, list)
                    for entry in entries
                ]
            else:
                groups = []
            user_present = any(
                any("echo user-" in h.get("command", "") for h in e.get("hooks", []))
                for e in groups
            )
            nwave_present = any(
                any("nwave_" in h.get("command", "") for h in e.get("hooks", []))
                for e in groups
            )
            return {
                "manifest.exists": manifest_path.is_file(),
                "user_hook.present": user_present,
                "nwave_hook.present": nwave_present,
            }

        before = snapshot()
        assert before == {
            "manifest.exists": True,
            "user_hook.present": True,
            "nwave_hook.present": True,
        }

        result = plugin.uninstall(context)

        after = snapshot()

        assert result.success is True
        assert not launcher_path.exists()
        assert_state_delta(
            before,
            after,
            universe=tracked,
            expected={
                "manifest.exists": set_to(False),
                "nwave_hook.present": set_to(False),
                # user_hook.present implicit-unchanged
            },
        )


class TestCodexHookPayloadCompatibility:
    """Empirical payload compatibility: Codex hook JSON shape vs Claude Code.

    Finding (2026-05-05, Issue 3):

    Claude Code PreToolUse payload includes ``transcript_path``; Codex's
    equivalent does not. The DES adapter reads only ``tool_input`` (and its
    sub-keys ``prompt``, ``subagent_type``) from the PreToolUse payload — it
    never accesses ``transcript_path`` — so both shapes are accepted without
    any translation shim.

    For the SubagentStop / Stop boundary there IS a field-name gap:
    Claude Code sends ``agent_transcript_path``; Codex's ``Stop`` hook sends
    ``transcript_path`` (different key).  The DES subagent-stop handler calls
    ``hook_input.get("agent_transcript_path")`` which returns None on a Codex
    payload, causing the handler to fall through to ``{"decision": "allow"}``
    (graceful pass-through, no crash).

    These tests document both behaviours so future adapters know the exact gap.
    """

    def _invoke_pre_tool_use_handler(self, payload: dict) -> tuple[int, str]:
        """Run handle_pre_tool_use() with a custom stdin payload.

        Patches:
        - sys.stdin: supplies the JSON payload
        - hook_protocol._audit_writer_factory: returns NullAuditLogWriter
        - service_factory.create_pre_tool_use_service: returns allow-all stub

        Returns:
            (exit_code, stdout_text)
        """
        import io
        from unittest.mock import MagicMock, patch

        from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
        from des.adapters.drivers.hooks import hook_protocol, service_factory
        from des.adapters.drivers.hooks.pre_tool_use_handler import handle_pre_tool_use
        from des.ports.driver_ports.pre_tool_use_port import HookDecision

        stdin_data = json.dumps(payload)
        captured_stdout = io.StringIO()

        # Stub service returns allow for any input — we are testing the
        # payload parsing layer, not the enforcement logic.
        allow_decision = HookDecision(action="allow", reason="stub allow")
        stub_service = MagicMock()
        stub_service.validate.return_value = allow_decision

        with (
            patch("sys.stdin", io.StringIO(stdin_data)),
            patch("sys.stdout", captured_stdout),
            patch.object(
                hook_protocol,
                "_audit_writer_factory",
                return_value=NullAuditLogWriter(),
            ),
            patch.object(
                service_factory,
                "create_pre_tool_use_service",
                return_value=stub_service,
            ),
        ):
            try:
                exit_code = handle_pre_tool_use()
            except SystemExit as exc:
                exit_code = exc.code if isinstance(exc.code, int) else 1

        return exit_code, captured_stdout.getvalue()

    def test_codex_pretooluse_payload_accepted_by_des_adapter(self):
        """
        GIVEN: A Codex-shaped PreToolUse payload (no transcript_path field)
        WHEN: The DES adapter's handle_pre_tool_use() processes it
        THEN: The adapter returns exit code 0 (allow) without raising or crashing.
              The missing transcript_path field does NOT cause a parse error.

        Codex payload shape (per research 2026-05-05):
          {"hook_event_name": "PreToolUse", "tool_name": "Bash",
           "tool_input": {"command": "echo hello"}, "session_id": "abc123"}

        vs Claude Code which also includes:
          "transcript_path": "/path/to/transcript.jsonl"
        """
        # bypass: single-property assertion on exit_code
        codex_payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "session_id": "codex-session-abc123",
            # NOTE: transcript_path deliberately absent (Codex doesn't send it)
        }

        exit_code, stdout_text = self._invoke_pre_tool_use_handler(codex_payload)

        assert exit_code == 0, (
            f"DES adapter must allow Codex-shaped PreToolUse payload; "
            f"got exit_code={exit_code}, stdout={stdout_text!r}"
        )

    def test_claude_code_pretooluse_payload_still_accepted(self):
        """
        GIVEN: A Claude Code-shaped PreToolUse payload (with transcript_path)
        WHEN: The DES adapter's handle_pre_tool_use() processes it
        THEN: The adapter returns exit code 0 (allow) — regression guard.
        """
        # bypass: single-property assertion on exit_code
        claude_code_payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hello"},
            "session_id": "claude-session-xyz",
            "transcript_path": "/home/user/.claude/projects/proj/transcript.jsonl",
        }

        exit_code, _stdout = self._invoke_pre_tool_use_handler(claude_code_payload)

        assert exit_code == 0, (
            "Claude Code PreToolUse payload must still be accepted after Codex work"
        )
