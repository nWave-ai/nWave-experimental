"""Composition root for the copilot-cli-integration acceptance set.

Wires the PRODUCTION install pipeline — `scripts/install/install_nwave.py` and
`scripts/install/uninstall_nwave.py` invoked as real Python subprocesses — against
a tmp_path target. The driving port is the installer/uninstaller CLI subprocess
(`python <install_nwave.py> --target <tmp-claude> ...`, mirroring how the
`nwave-ai` console entry forwards `--target`); the only driven ports are the real
filesystem (tmp COPILOT_HOME tree + tmp Claude config dir) and the COPILOT_HOME /
HOME / COPILOT_CLI environment variables.

Mandate-13 (driving-port-only): every observation is made by running the real
installer subprocess + reading the real filesystem. ZERO direct production import
of the (not-yet-existing) `copilot_des_plugin.py`. ZERO live `copilot` binary
invocation — Copilot presence is simulated for the installer's detector by a tmp
`COPILOT_HOME` tree + `COPILOT_CLI=1` env (the spike-validated detection signals,
spike §4 "TargetPlatform detection").

Spike-validated install contract this fixture asserts (FM-1 + FS-1):
  - FM-1: the nWave DES hook config is a FILE in `<COPILOT_HOME>/hooks/`
    (canonical name `nwave-des.json`), NOT an inline `hooks` block in
    `<COPILOT_HOME>/settings.json` (the documented-but-broken mount point).
  - FS-1: each hook entry is DOUBLE-NESTED
    `{matcher?, hooks: [{type: "command", bash: ...}]}` — never flat.

Standalone fixture — `CopilotInstallFixture` does NOT inherit from any sibling
feature's fixture (fresh feature per the dispatch brief).

RED-for-the-right-reason: the production `copilot_des_plugin.py` and the
`TargetPlatform.COPILOT_CLI` enum do NOT exist yet (DELIVER scope). When the
installer subprocess runs, the plugin registry has no Copilot plugin, so NO
`<COPILOT_HOME>/hooks/nwave-des.json` is written. The first `Then` assertion
(`assert_hook_file_present`) then fires AssertionError — the assertion fires
because the install-time behavior is unimplemented, NOT because of an import
error or fixture setup bug. That is the correct RED classification.

Business logic — building the subprocess invocation, capturing the
operator-observable Copilot hook surface, deriving the install/uninstall verdict —
lives here as the single source of truth (Mandate-12 criterion 2/3); step bodies
delegate to `CopilotInstallFixture` methods and never inline logic.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# Repo root:
# tests/installer/acceptance/copilot-cli-integration/steps/composition.py
# → up five levels.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_INSTALL_NWAVE = _REPO_ROOT / "scripts" / "install" / "install_nwave.py"
_UNINSTALL_NWAVE = _REPO_ROOT / "scripts" / "install" / "uninstall_nwave.py"

# FM-1 install surface: file-in-dir, NOT inline settings.json.
_HOOKS_DIRNAME = "hooks"
_DES_HOOK_FILENAME = "nwave-des.json"
_SETTINGS_FILENAME = "settings.json"

# The shared DES adapter module the Copilot hook command must invoke (mirrors the
# Codex plugin precedent which bakes the adapter module + event token into the
# command string).
_DES_ADAPTER_MODULE = "claude_code_hook_adapter"

# Foreign (operator-authored) hook fixture — must survive uninstall untouched.
_FOREIGN_HOOK_FILENAME = "my-own-hook.json"
_FOREIGN_HOOK_CONTENT = {
    "sessionStart": [
        {"hooks": [{"type": "command", "bash": "echo operator-authored-hook"}]}
    ]
}


@dataclass(frozen=True)
class CopilotHookObservation:
    """One captured observation of the operator-visible Copilot hook surface.

    Every field is read from the real filesystem after a real installer
    subprocess run — these are the port-exposed universe entries for the
    state-delta assertions (Mandate 8).
    """

    install_returncode: int
    hook_file_exists: bool
    hook_file_content: dict | None
    settings_inline_block_present: bool
    foreign_hook_content: dict | None
    install_stdout_tail: str
    install_stderr_tail: str


class CopilotInstallFixture:
    """Drives the production installer/uninstaller against a tmp COPILOT_HOME.

    Each instance is bound to one tmp_path tree carrying:
      - a tmp Claude config dir (the installer's primary `--target`),
      - a tmp COPILOT_HOME (where the Copilot plugin must write its hook file),
      - a fake HOME (so the real dev-machine ~/.copilot and ~/.claude are never
        touched).

    The fixture exposes composition methods the step bodies invoke; no business
    logic is inlined in any step (Mandate-12 criterion 3).
    """

    def __init__(self, tmp_root: Path) -> None:
        self._tmp_root = tmp_root
        self._fake_home = tmp_root / "fake_home"
        self._claude_dir = tmp_root / "claude_config"
        self._copilot_home = tmp_root / "copilot_home"
        self._project_root = tmp_root / "project"
        for d in (
            self._fake_home,
            self._claude_dir,
            self._copilot_home,
            self._project_root,
        ):
            d.mkdir(parents=True, exist_ok=True)
        # Stashed post-install surface for the uninstall round-trip non-vacuity
        # guard (set by run_uninstall before the uninstaller runs).
        self._post_install: CopilotHookObservation | None = None

    # --- paths (port-exposed surface) --------------------------------------

    def hook_file_path(self) -> Path:
        """Absolute path to the nWave DES hook config (FM-1 file-in-dir)."""
        return self._copilot_home / _HOOKS_DIRNAME / _DES_HOOK_FILENAME

    def settings_file_path(self) -> Path:
        """Absolute path to the Copilot settings.json (FM-1 broken mount point)."""
        return self._copilot_home / _SETTINGS_FILENAME

    def foreign_hook_file_path(self) -> Path:
        """Absolute path to the operator-authored Copilot hook fixture."""
        return self._copilot_home / _HOOKS_DIRNAME / _FOREIGN_HOOK_FILENAME

    # --- GIVEN composition methods -----------------------------------------

    def stage_copilot_runtime_without_nwave_hook(self) -> None:
        """Make the installer detect Copilot, with no nWave hook present yet.

        Stages the spike-validated detection signal: a `<COPILOT_HOME>/settings.json`
        file (created by the CLI on first launch — the detector's fallback signal
        per spike §4). The `COPILOT_CLI=1` env is set at subprocess-launch time by
        `_run_installer`. No nWave hook file exists — clean install precondition.
        """
        self.settings_file_path().write_text("{}\n", encoding="utf-8")

    def stage_operator_authored_copilot_hook(self) -> None:
        """Seed a non-nWave Copilot hook the operator authored themselves.

        Uninstall MUST preserve this file byte-for-byte. Also stages the Copilot
        detection signal so the installer recognises the runtime.
        """
        self.settings_file_path().write_text("{}\n", encoding="utf-8")
        foreign = self.foreign_hook_file_path()
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text(
            json.dumps(_FOREIGN_HOOK_CONTENT, indent=2) + "\n", encoding="utf-8"
        )

    # --- WHEN composition methods ------------------------------------------

    def run_install(self) -> CopilotHookObservation:
        """Run the real installer subprocess and capture the Copilot surface."""
        completed = self._run_installer(_INSTALL_NWAVE)
        return self._capture_surface(completed)

    def run_uninstall(self) -> CopilotHookObservation:
        """Run install, capture the post-install surface, then uninstall.

        Returns the POST-UNINSTALL surface, but also stashes the post-install
        surface on the returned observation's carrier (`_post_install`) so the
        uninstall ATs can prove the hook was actually present BEFORE asserting it
        is gone -- the non-vacuity guard against a Fixture-Theater pass where the
        installer wrote nothing and the removal assertion is trivially satisfied.
        """
        install_completed = self._run_installer(_INSTALL_NWAVE)
        post_install = self._capture_surface(install_completed)
        self._post_install = post_install
        uninstall_completed = self._run_installer(_UNINSTALL_NWAVE)
        return self._capture_surface(uninstall_completed)

    # --- subprocess driving port -------------------------------------------

    def _sandboxed_env(self) -> dict[str, str]:
        """Build a hermetic env: fake HOME + tmp COPILOT_HOME + COPILOT_CLI=1.

        Strips the inherited HOME/USERPROFILE/XDG/COPILOT_HOME so the real
        dev-machine config dirs are never read or written, then points them at
        the tmp tree. `COPILOT_CLI=1` is the spike-validated native detection
        signal the Copilot binary exports into hook subprocesses; setting it here
        lets the installer's detector recognise the runtime without the live
        binary.
        """
        stripped = {
            k: v
            for k, v in os.environ.items()
            if k not in ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "COPILOT_HOME")
        }
        stripped["HOME"] = str(self._fake_home)
        stripped["COPILOT_HOME"] = str(self._copilot_home)
        stripped["COPILOT_CLI"] = "1"
        stripped["PYTHONDONTWRITEBYTECODE"] = "1"
        return stripped

    def _run_installer(self, script: Path) -> subprocess.CompletedProcess:
        """Invoke an installer script as a real subprocess against the tmp target.

        Mirrors how the `nwave-ai` console entry forwards `--target` (it sets
        `CLAUDE_CONFIG_DIR` and runs `install_nwave.py`); here we set
        `CLAUDE_CONFIG_DIR` directly and pass `--force` on uninstall (scripted
        mode, matching `nwave_ai.cli._handle_uninstall`).
        """
        env = self._sandboxed_env()
        env["CLAUDE_CONFIG_DIR"] = str(self._claude_dir)
        argv = [sys.executable, str(script)]
        if script == _UNINSTALL_NWAVE:
            argv.append("--force")
        return subprocess.run(
            argv,
            cwd=str(self._project_root),
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
            check=False,
        )

    def _capture_surface(
        self, completed: subprocess.CompletedProcess
    ) -> CopilotHookObservation:
        """Read the operator-observable Copilot hook surface from the filesystem."""
        hook_file = self.hook_file_path()
        settings_file = self.settings_file_path()
        foreign_file = self.foreign_hook_file_path()
        return CopilotHookObservation(
            install_returncode=completed.returncode,
            hook_file_exists=hook_file.is_file(),
            hook_file_content=_read_json_or_none(hook_file),
            settings_inline_block_present=_settings_has_inline_hooks(settings_file),
            foreign_hook_content=_read_json_or_none(foreign_file),
            install_stdout_tail="\n".join(completed.stdout.splitlines()[-30:]),
            install_stderr_tail="\n".join(completed.stderr.splitlines()[-30:]),
        )

    # --- THEN composition methods (assertions — RED-for-right-reason) ------

    def assert_hook_file_present(self, obs: CopilotHookObservation) -> None:
        """AT-1: install wrote the nWave DES hook config to the hooks dir (FM-1).

        Fires AssertionError when the install pipeline does not deliver the
        file-in-dir surface — the correct RED while the Copilot plugin is
        unimplemented.
        """
        assert obs.hook_file_exists, (
            "Installing nWave for a Copilot operator MUST write the DES hook "
            f"config to {self.hook_file_path()} (FM-1 file-in-dir). It was not "
            f"written.\ninstaller exit={obs.install_returncode}\n"
            f"stdout tail:\n{obs.install_stdout_tail}\n"
            f"stderr tail:\n{obs.install_stderr_tail}"
        )

    def assert_hook_invokes_des_adapter(self, obs: CopilotHookObservation) -> None:
        """AT-1: the written hook command invokes the shared DES adapter."""
        command_text = json.dumps(obs.hook_file_content or {})
        assert _DES_ADAPTER_MODULE in command_text, (
            "The nWave DES hook command MUST invoke the shared DES adapter "
            f"module '{_DES_ADAPTER_MODULE}'. Observed content: "
            f"{obs.hook_file_content!r}."
        )

    def assert_no_inline_settings_block(self, obs: CopilotHookObservation) -> None:
        """AT-1: no inline hooks block written into settings.json (FM-1).

        The documented-but-broken mount point MUST stay empty — installing the
        DES hook there would silently not fire on Copilot v1.0.54.
        """
        assert not obs.settings_inline_block_present, (
            "Install MUST NOT write an inline 'hooks' block into the Copilot "
            "settings.json (FM-1: that mount point does not fire in v1.0.54). "
            "The hook config belongs in the hooks/ directory."
        )

    def assert_schema_double_nested(self, obs: CopilotHookObservation) -> None:
        """AT-2: each hook entry is double-nested {matcher?, hooks:[{type,bash}]} (FS-1)."""
        content = obs.hook_file_content
        assert content is not None and isinstance(content, dict) and content, (
            "AT-2 requires AT-1's hook file to exist and parse as a non-empty "
            f"JSON object; observed {content!r}."
        )
        entries = _flatten_event_entries(content)
        assert entries, (
            "The Copilot hook config MUST register at least one event entry; "
            f"observed {content!r}."
        )
        for entry in entries:
            assert isinstance(entry, dict) and isinstance(entry.get("hooks"), list), (
                "FS-1: each hook entry MUST group its handlers under a nested "
                f"'hooks' list ({{matcher?, hooks:[...]}}); observed flat/other "
                f"shape: {entry!r}."
            )

    def assert_each_handler_named(self, obs: CopilotHookObservation) -> None:
        """AT-2: each nested handler names its kind ('type') and the 'bash' command (FS-1)."""
        for entry in _flatten_event_entries(obs.hook_file_content or {}):
            for handler in entry.get("hooks", []):
                assert isinstance(handler, dict) and "type" in handler, (
                    "FS-1: each handler MUST name its kind via 'type'; observed "
                    f"{handler!r}."
                )
                assert "bash" in handler, (
                    "FS-1: each handler MUST name the command Copilot runs via "
                    f"'bash'; observed {handler!r}."
                )

    def assert_not_flat_shape(self, obs: CopilotHookObservation) -> None:
        """AT-2: the hook config is NOT the flat single-handler shape (FS-1)."""
        for entry in _flatten_event_entries(obs.hook_file_content or {}):
            assert not ("type" in entry and "bash" in entry and "hooks" not in entry), (
                "FS-1: the hook entry MUST NOT use the flat {type, bash} shape "
                f"directly under the event array; observed flat entry: {entry!r}."
            )

    def assert_hook_file_removed(self, obs: CopilotHookObservation) -> None:
        """AT-3: uninstall removed the nWave DES hook config file.

        Non-vacuity guard FIRST: the hook MUST have been present after install,
        otherwise "removed" is trivially satisfied by an installer that wrote
        nothing (Fixture Theater / closed-world trap). This guard makes AT-3 RED
        for the right reason while the Copilot plugin is unimplemented -- the
        post-install surface has no hook file, so this assertion fires before the
        removal claim is even reached.
        """
        assert self._post_install is not None and self._post_install.hook_file_exists, (
            "AT-3 non-vacuity guard: the nWave DES hook MUST be present after "
            "install before uninstall can meaningfully remove it. Post-install "
            f"surface had no hook file at {self.hook_file_path()} -- the removal "
            "assertion would be vacuous."
        )
        assert not obs.hook_file_exists, (
            "Uninstalling nWave MUST remove the DES hook config at "
            f"{self.hook_file_path()}; it is still present after uninstall.\n"
            f"uninstaller exit={obs.install_returncode}\n"
            f"stderr tail:\n{obs.install_stderr_tail}"
        )

    def assert_no_orphan_artifact(self, obs: CopilotHookObservation) -> None:
        """AT-3: no orphan nWave hook artifact left behind after uninstall."""
        hooks_dir = self._copilot_home / _HOOKS_DIRNAME
        orphans = [
            p.name
            for p in (hooks_dir.glob("*") if hooks_dir.is_dir() else [])
            if "nwave" in p.name.lower() or "des" in p.name.lower()
        ]
        assert not orphans, (
            "Uninstall MUST leave no orphan nWave hook artifact in the Copilot "
            f"hooks dir; found: {orphans}."
        )

    def assert_foreign_hook_preserved(self, obs: CopilotHookObservation) -> None:
        """AT-3: the operator-authored Copilot hook survived uninstall unchanged."""
        assert obs.foreign_hook_content == _FOREIGN_HOOK_CONTENT, (
            "Uninstall MUST preserve the operator-authored Copilot hook "
            f"byte-for-byte; expected {_FOREIGN_HOOK_CONTENT!r}, observed "
            f"{obs.foreign_hook_content!r}."
        )


# --- module-level pure helpers (no I/O state, deterministic) ---------------


def _read_json_or_none(path: Path) -> dict | None:
    """Read a JSON file into a dict, or None when absent / unparseable."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _settings_has_inline_hooks(path: Path) -> bool:
    """True when settings.json carries a non-empty inline 'hooks' block (FM-1)."""
    data = _read_json_or_none(path)
    if data is None:
        return False
    return bool(data.get("hooks"))


def _flatten_event_entries(content: dict) -> list:
    """Flatten a Copilot hook config into the list of per-event hook entries.

    Tolerates both a top-level event-keyed object ({"sessionStart": [...], ...})
    and a {"hooks": {<event>: [...]}} root (mirrors the Codex event-keyed shape).
    Each element returned is one event entry whose correct (FS-1) shape is
    {matcher?, hooks:[{type, bash}]}.
    """
    root = content.get("hooks") if isinstance(content.get("hooks"), dict) else content
    entries: list = []
    for value in root.values():
        if isinstance(value, list):
            entries.extend(value)
    return entries
