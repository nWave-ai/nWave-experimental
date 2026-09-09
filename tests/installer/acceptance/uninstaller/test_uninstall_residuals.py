"""Regression tests for uninstall residual artifacts (issue #39).

Reporter: DevOpsCraftsman 2026-04-25
Bug: `nwave-ai uninstall --force` reports success but leaves behind:
  1. ~/.claude/skills/nw-* directories (197 dirs survive — install layout is
     flat `skills/nw-<name>/`, uninstaller searches obsolete nested
     `skills/nw/`)
  2. ~/.claude/lib/python/des/ directory (uninstaller never removes lib/)
  3. 3 specific DES hooks in settings.json:
       - des-hook:pre-bash (PreToolUse > Bash matcher)
       - des.adapters.drivers.hooks.claude_code_hook_adapter session-start
       - des.adapters.drivers.hooks.claude_code_hook_adapter subagent-start
     (the SubagentStart registration itself is now retired; uninstall must
     still remove the command an older install wrote there)

Test isolates a fresh install + uninstall in tmp_path_factory and asserts
the residuals are gone. Pinned to the same xdist group as the walking
skeleton test (writes to ~/.config/opencode/, race-prone under loadfile).
"""

from __future__ import annotations

import importlib
import io
import json
import os
import subprocess
import sys

import pytest

from scripts.install.install_utils import Logger, PathUtils
from scripts.install.preflight_checker import CheckResult, PreflightChecker


pytestmark = pytest.mark.xdist_group("installer_walking_skeleton")

# User-owned SubagentStart hooks the uninstaller never wrote and must not touch.
_USER_SUBAGENT_START_COMMAND = "python3 -m operator_tools.subagent_start --audit"
_USER_SUBAGENT_START_SIBLING_COMMAND = "/opt/operator/notify.sh subagent-start"


def _apply_patches(
    original_logger_init, claude_config_dir, opencode_config_dir, home_dir
):
    """Mirror of conftest._apply_patches (no shared import to keep test self-contained)."""
    originals = {
        "logger_init": Logger.__init__,
        "get_config": PathUtils.get_claude_config_dir,
        "get_opencode": PathUtils.get_opencode_config_dir,
        "run_checks": PreflightChecker.run_all_checks,
        "subprocess_run": subprocess.run,
        "argv": sys.argv,
        "opencode_env": os.environ.get("OPENCODE_CONFIG_DIR"),
        "copilot_home_env": os.environ.get("COPILOT_HOME"),
        "home_env": os.environ.get("HOME"),
        "agents_home_env": os.environ.get("NWAVE_AGENTS_HOME"),
        "project_root_env": os.environ.get("NWAVE_PROJECT_ROOT"),
        "claude_config_env": os.environ.get("CLAUDE_CONFIG_DIR"),
    }

    def plain_logger_init(self, *args, **kwargs):
        original_logger_init(self, *args, **kwargs)
        self._rich_console = None

    Logger.__init__ = plain_logger_init
    PathUtils.get_claude_config_dir = staticmethod(lambda: claude_config_dir)
    PathUtils.get_opencode_config_dir = staticmethod(lambda: opencode_config_dir)
    os.environ["OPENCODE_CONFIG_DIR"] = str(opencode_config_dir)
    # Isolate COPILOT_HOME to the tmp tree: on a machine with a real ~/.copilot,
    # auto-detect would otherwise drive the Copilot DES plugin to install/remove
    # in the operator's real ~/.copilot/hooks/, breaching test isolation and
    # racing under xdist -n. Point it at the opencode tmp parent (a scratch dir).
    os.environ["COPILOT_HOME"] = str(opencode_config_dir.parent / "copilot_residuals")
    # HOME → temp. install_nwave.main() runs the attribution plugin, whose
    # migrate_legacy_hook deletes ~/.nwave/hooks/nwave_attribution_hook.py via
    # Path.home(). Without this redirect the install phase below wipes the
    # developer's REAL attribution hook, breaking subsequent commits. (The
    # get_claude_config_dir patch only covers ~/.claude, not ~/.nwave.)
    os.environ["HOME"] = str(home_dir)
    os.environ["NWAVE_AGENTS_HOME"] = str(home_dir)
    project_root = home_dir / "project"
    project_root.mkdir()
    os.environ["NWAVE_PROJECT_ROOT"] = str(project_root)
    os.environ["CLAUDE_CONFIG_DIR"] = str(claude_config_dir)

    passing = [
        CheckResult(
            passed=True,
            error_code=None,
            message="Virtual environment detected.",
            remediation=None,
        ),
        CheckResult(
            passed=True,
            error_code=None,
            message="Pipenv is available.",
            remediation=None,
        ),
        CheckResult(
            passed=True,
            error_code=None,
            message="All required dependencies are available.",
            remediation=None,
        ),
    ]
    PreflightChecker.run_all_checks = lambda self, **kw: passing

    mock_completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="", stderr=""
    )
    subprocess.run = lambda *a, **kw: mock_completed

    return originals


def _restore_patches(originals, original_logger_init):
    Logger.__init__ = original_logger_init
    PathUtils.get_claude_config_dir = originals["get_config"]
    PathUtils.get_opencode_config_dir = originals["get_opencode"]
    PreflightChecker.run_all_checks = originals["run_checks"]
    subprocess.run = originals["subprocess_run"]
    sys.argv = originals["argv"]
    if originals["opencode_env"] is None:
        os.environ.pop("OPENCODE_CONFIG_DIR", None)
    else:
        os.environ["OPENCODE_CONFIG_DIR"] = originals["opencode_env"]
    if originals["copilot_home_env"] is None:
        os.environ.pop("COPILOT_HOME", None)
    else:
        os.environ["COPILOT_HOME"] = originals["copilot_home_env"]
    if originals["home_env"] is None:
        os.environ.pop("HOME", None)
    else:
        os.environ["HOME"] = originals["home_env"]
    if originals["agents_home_env"] is None:
        os.environ.pop("NWAVE_AGENTS_HOME", None)
    else:
        os.environ["NWAVE_AGENTS_HOME"] = originals["agents_home_env"]
    if originals["project_root_env"] is None:
        os.environ.pop("NWAVE_PROJECT_ROOT", None)
    else:
        os.environ["NWAVE_PROJECT_ROOT"] = originals["project_root_env"]
    if originals["claude_config_env"] is None:
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
    else:
        os.environ["CLAUDE_CONFIG_DIR"] = originals["claude_config_env"]


@pytest.fixture(scope="module")
def post_uninstall_state(tmp_path_factory) -> dict:
    """Run install → uninstall against a fresh tmp config dir, return residual snapshot."""
    claude_config_dir = tmp_path_factory.mktemp("claude_residuals")
    opencode_config_dir = tmp_path_factory.mktemp("opencode_residuals")
    home_dir = tmp_path_factory.mktemp("home_residuals")
    original_logger_init = Logger.__init__
    originals = _apply_patches(
        original_logger_init, claude_config_dir, opencode_config_dir, home_dir
    )

    try:
        # Install
        sys.argv = ["install_nwave.py", "--platform", "claude-code"]
        devnull = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = devnull

        import scripts.install.install_nwave as install_mod

        importlib.reload(install_mod)
        install_mod.main()

        sys.stdout = old_stdout

        # Snapshot pre-uninstall (to confirm install populated nw-* skills)
        nw_skill_dirs_pre = sorted(claude_config_dir.glob("skills/nw-*"))
        lib_des_pre = (claude_config_dir / "lib" / "python" / "des").exists()

        # These are deliberately close to retired DES lifecycle commands, but
        # belong to Lyra and to the operator.  Drive the real uninstaller CLI
        # through this state: it must not use a broad marker/substring sweep.
        settings_path = claude_config_dir / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        hooks = settings.setdefault("hooks", {})
        hooks["SessionStart"] = [
            {
                "hooks": [
                    {"type": "command", "command": "python3 -m lyra.session_start"}
                ]
            },
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            "# des-hook:orchestrator-affordance-refresh-standalone\n"
                            "python3 /opt/operator/session_start.py --keep"
                        ),
                    }
                ]
            },
        ]
        # An operator upgrading from a build that still registered the retired
        # SubagentStart skill-loading reminder: settings.json carries this
        # installer's own modern (`-m ... adapter subagent-start`) and legacy
        # (flat script-path) commands, plus unrelated user hooks -- one
        # standalone entry, one nested as a sibling of the DES command under
        # the same entry. Uninstall must remove both DES commands and leave
        # the user's two hooks byte-for-byte.
        hooks["SubagentStart"] = [
            {"hooks": [{"type": "command", "command": _USER_SUBAGENT_START_COMMAND}]},
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": (
                            "PYTHONPATH=/anywhere/lib/python python3 -m "
                            "des.adapters.drivers.hooks."
                            "claude_code_hook_adapter subagent-start"
                        ),
                    },
                    {
                        "type": "command",
                        "command": _USER_SUBAGENT_START_SIBLING_COMMAND,
                    },
                ]
            },
            {
                "command": (
                    "python3 src/des/adapters/drivers/hooks/"
                    "claude_code_hook_adapter.py subagent-start"
                )
            },
        ]
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        # Uninstall
        sys.argv = ["uninstall_nwave.py", "--force"]
        sys.stdout = devnull
        import scripts.install.uninstall_nwave as uninstall_mod

        importlib.reload(uninstall_mod)
        exit_code = uninstall_mod.main()
        sys.stdout = old_stdout

        # Snapshot post-uninstall
        nw_skill_dirs_post = sorted(claude_config_dir.glob("skills/nw-*"))
        lib_des_post = (claude_config_dir / "lib" / "python" / "des").exists()
        settings_path = claude_config_dir / "settings.json"
        settings_text = settings_path.read_text() if settings_path.exists() else ""

        return {
            "claude_config_dir": claude_config_dir,
            "exit_code": exit_code,
            "nw_skill_dirs_pre": nw_skill_dirs_pre,
            "nw_skill_dirs_post": nw_skill_dirs_post,
            "lib_des_pre": lib_des_pre,
            "lib_des_post": lib_des_post,
            "settings_text_post": settings_text,
            "settings_post": json.loads(settings_text) if settings_text else {},
        }
    finally:
        sys.stdout = sys.__stdout__
        _restore_patches(originals, original_logger_init)


class TestUninstallResiduals:
    """Issue #39: nwave-ai uninstall must leave zero residual artifacts."""

    def test_install_populated_nw_skills(self, post_uninstall_state):
        """Sanity: install must have created at least one nw-* skill (else the
        residual test below is meaningless — the install never ran)."""
        pre = post_uninstall_state["nw_skill_dirs_pre"]
        assert len(pre) > 0, (
            "Install fixture failed: no nw-* skill directories were created. "
            "Test is invalid until install populates skills."
        )

    def test_no_residual_skills(self, post_uninstall_state):
        """All `skills/nw-*` directories must be removed by uninstall."""
        residual = post_uninstall_state["nw_skill_dirs_post"]
        assert residual == [], (
            f"Uninstall left {len(residual)} residual skills/nw-* dirs:\n  "
            + "\n  ".join(str(p) for p in residual[:10])
        )

    def test_no_residual_lib_python_des(self, post_uninstall_state):
        """`lib/python/des/` must be removed by uninstall."""
        assert not post_uninstall_state["lib_des_post"], (
            f"Uninstall left lib/python/des/ at: "
            f"{post_uninstall_state['claude_config_dir']}/lib/python/des"
        )

    def test_no_residual_des_hooks_in_settings(self, post_uninstall_state):
        """The active hook events contain no installer-owned DES commands."""
        hooks = post_uninstall_state["settings_post"].get("hooks", {})
        forbidden_patterns = [
            "des-hook:",
            "des.adapters.drivers.hooks.claude_code_hook_adapter",
        ]
        active_hook_text = json.dumps(
            {
                event: hooks.get(event, [])
                for event in (
                    "PreToolUse",
                    "SubagentStart",
                    "SubagentStop",
                    "PostToolUse",
                )
            }
        )
        found = [p for p in forbidden_patterns if p in active_hook_text]
        assert not found, f"Uninstall left DES hook patterns in settings.json: {found}"

    def test_real_uninstall_preserves_lyra_and_near_miss_lifecycle_hooks(
        self, post_uninstall_state
    ):
        """The CLI cleanup keeps entries it did not write exactly."""
        session_entries = post_uninstall_state["settings_post"]["hooks"]["SessionStart"]
        commands = [entry["hooks"][0]["command"] for entry in session_entries]

        assert commands == [
            "python3 -m lyra.session_start",
            "# des-hook:orchestrator-affordance-refresh-standalone\n"
            "python3 /opt/operator/session_start.py --keep",
        ]

    def test_uninstall_removes_retired_subagent_start_hook_keeping_user_siblings(
        self, post_uninstall_state
    ):
        """Old DES SubagentStart commands go; the operator's own hooks stay."""
        entries = post_uninstall_state["settings_post"]["hooks"]["SubagentStart"]
        commands = [
            hook["command"] for entry in entries for hook in entry.get("hooks", [])
        ]
        commands.extend(entry["command"] for entry in entries if "command" in entry)

        assert commands == [
            _USER_SUBAGENT_START_COMMAND,
            _USER_SUBAGENT_START_SIBLING_COMMAND,
        ]
        assert entries[0] == {
            "hooks": [{"type": "command", "command": _USER_SUBAGENT_START_COMMAND}]
        }
        assert entries[1]["hooks"] == [
            {"type": "command", "command": _USER_SUBAGENT_START_SIBLING_COMMAND}
        ]

    def test_uninstall_exit_code_zero(self, post_uninstall_state):
        """Uninstall reports success even with residuals — sanity check on exit code."""
        assert post_uninstall_state["exit_code"] == 0, (
            f"Uninstall reported failure (exit {post_uninstall_state['exit_code']})"
        )
