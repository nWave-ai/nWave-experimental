"""Composition root for the copilot-cli-integration slice-02 e2e firing proof.

slice-02 goes one level deeper than slice-01. slice-01 proved the INSTALL
behaviour (the production installer writes ``<COPILOT_HOME>/hooks/nwave-des.json``
in the FM-1 file-in-dir / FS-1 double-nested shape) against the filesystem. This
slice proves the hook ACTUALLY FIRES inside the real ``copilot`` binary, end to
end:

    install (production plugin path) → real `copilot -p ...` against a mock LLM →
    the installed hook runs → an observable marker file is written.

Driving port (Mandate-13): the REAL ``copilot`` subprocess is the entry point.
Zero direct production import of the hook logic.

----------------------------------------------------------------------------
THE TWO OBSERVABLES (revised iter-2 per reviewer Option A — OBS-1 fix):
----------------------------------------------------------------------------
AT-1 (walking-skeleton) and AT-2 (harness-soundness) observe DIFFERENT
side-effects, and that difference is the whole point of the fix:

  * AT-1 observes the PRODUCTION hook's REAL side-effect — the **DES audit-log
    entry** the installed adapter command writes when Copilot fires it. The
    production install wires ``python -m
    des.adapters.drivers.hooks.claude_code_hook_adapter <event>``; that adapter
    logs ``HOOK_INVOKED`` + ``HOOK_COMPLETED`` JSON lines to its audit log on
    EVERY invocation (``log_hook_invoked`` at entry, ``log_hook_completed`` in a
    ``finally`` block — fires on allow / block / error alike, see
    ``des/adapters/drivers/hooks/hook_protocol.py``). The audit-log directory is
    ``DES_AUDIT_LOG_DIR``-controlled (highest-priority env override in
    ``AuditLogPathResolver``), so the AT points it at a tmp dir and reads back the
    real production entry. This is the side-effect the PRODUCTION command
    actually produces — NOT the probe marker. AT-1 can therefore reach GREEN only
    via the real production path (closed-world / Pista-2 false-GREEN trap avoided
    at its root).

  * AT-2 observes a PROBE marker written by a HAND-WIRED ``sessionStart`` hook.
    The probe marker proves the harness (mock server + real binary + hook
    firing) is SOUND, independent of the production-plugin gap — so a RED on AT-1
    is unambiguously a production gap, not a harness bug. The marker is fine for
    AT-2 precisely because AT-2's job is harness detection, not production proof.

----------------------------------------------------------------------------
THE CRUX FINDINGS (documented in at-scaffold-notes-slice-02.md):
----------------------------------------------------------------------------
CRUX-1 — slice-01's production ``copilot_des_plugin.py`` installs the DES hook
ONLY on the ``preToolUse`` event. The spike
(docs/analysis/copilot-cli-prereq-spike-2026-05-28.md §2) established that
``preToolUse`` is NOT reliably firable (mock tool-dispatch did not occur within a
25 s timeout), whereas ``sessionStart`` fires reliably on every ``copilot -p``
invocation. So Copilot never fires the installed command → the adapter is never
invoked → NO audit-log entry is written.

CRUX-2 — the installed config uses the un-wrapped event-keyed shape, which
v1.0.54 REJECTS (``hooks must be an object``) → the hook never fires even when
the event would.

Therefore AT-1 is RED for the right reason against slice-01: the production
command is never fired by the real binary (wrong event + wrong schema), so its
audit-log side-effect never appears. slice-02 DELIVER must (a) add a
``sessionStart`` hook entry and (b) wrap the event map under a top-level
``hooks`` key, after which the real binary fires the production adapter and the
audit-log entry appears → AT-1 GREEN.

----------------------------------------------------------------------------
BOUNDARY FINDING — adapter Copilot-event-shape support (slice-03 scope):
----------------------------------------------------------------------------
The DES audit-log side-effect is EVENT-SHAPE-AGNOSTIC: ``log_hook_invoked`` /
``log_hook_completed`` write based on the handler name + exit code, NOT on any
Copilot-specific stdin field (the ``finally`` block logs ``HOOK_COMPLETED`` even
on the empty-stdin early-return and on the fail-closed exception path). So even
though Copilot's hook-event JSON differs from Claude Code's (spike found
undocumented fields), the adapter STILL emits its audit-log side-effect on any
invocation. AT-1 therefore proves FIRING (Copilot invoked our production command
end-to-end) via a real production side-effect, which is the minimum bar.

Whether the adapter's full DES DECISION logic (carpaccio intercept, service
validation) correctly handles Copilot's event shape is a DEEPER question — the
adapter was built for Claude Code's protocol and may no-op or fail-closed on
Copilot's shape. That is NOT solved here; it is flagged as slice-03 scope
(adapter Copilot-protocol support). AT-1 observes the invocation side-effect (the
audit-log entry), which is present regardless, so the firing proof holds even if
full decision-logic support lands in slice-03.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .mock_llm_server import MockLLMServer


_HOOKS_DIRNAME = "hooks"
_DES_HOOK_FILENAME = "nwave-des.json"
_PROBE_HOOK_FILENAME = "nwave-e2e-probe.json"
_MARKER_FILENAME = "nwave-session-start-fired.marker"

# Spike-proven-firing event (§2: sessionStart fires reliably on every -p run).
_SESSION_START_EVENT = "sessionStart"

# The marker content the probe hook writes — distinctive so the assertion cannot
# pass on an unrelated pre-existing file.
_MARKER_CONTENT = "nwave-copilot-hook-fired"

# Directory name (under the tmp tree) the production DES adapter writes its audit
# log into. Pointed at via DES_AUDIT_LOG_DIR — the highest-priority override in
# AuditLogPathResolver — so the real production side-effect lands in tmp and the
# real ~/.claude/des/logs/ is NEVER touched. The adapter writes a daily file
# ``audit-YYYY-MM-DD.log`` here (JsonlAuditLogWriter._get_log_file).
_DES_AUDIT_DIRNAME = "des-audit"

# Audit event types the production adapter emits on EVERY invocation (entry +
# finally-block). Their presence in the audit log is the production-firing proof:
# Copilot invoked our installed command end-to-end.
_HOOK_INVOKED_EVENT = "HOOK_INVOKED"
_HOOK_COMPLETED_EVENT = "HOOK_COMPLETED"

# Generous, deterministic timeout for the live binary turn (flake mitigation).
_COPILOT_TURN_TIMEOUT_S = 90

# Mock-server readiness probe budget before launching copilot (flake mitigation).
_READINESS_TIMEOUT_S = 10
_READINESS_POLL_S = 0.1


def copilot_binary_path() -> str | None:
    """Absolute path to the real ``copilot`` binary, or None when absent.

    The skipif guard at the test-module head uses this; the e2e proves the
    integration WHERE the binary exists and SKIPS (never fails) where it does
    not (CI without it / customer machine).
    """
    return shutil.which("copilot")


@dataclass(frozen=True)
class CopilotFiringObservation:
    """One captured observation of the real-binary hook-firing surface.

    Read from the real filesystem after a real ``copilot`` subprocess run.

    Two firing surfaces are carried, one per AT:
      - ``des_audit_event_types`` — the PRODUCTION observable (AT-1): the audit
        event types the installed DES adapter wrote when Copilot fired it.
      - ``marker_exists`` / ``marker_content`` — the PROBE observable (AT-2):
        the hand-wired sessionStart marker that proves the harness is sound.
    """

    copilot_returncode: int
    marker_exists: bool
    marker_content: str | None
    installed_hook_events: tuple[str, ...]
    des_audit_event_types: tuple[str, ...]
    copilot_stdout_tail: str
    copilot_stderr_tail: str


class CopilotE2EFixture:
    """Drives the REAL ``copilot`` binary against a mock LLM, observes hook firing.

    Each instance is bound to one tmp tree carrying:
      - a tmp COPILOT_HOME (where the install plugin / probe writes the hook file),
      - a fake HOME (so the real dev-machine ~/.copilot is NEVER touched),
      - a tmp Claude config dir (the installer's primary --target),
      - a tmp project cwd for the copilot session.

    Composition methods are invoked by the step bodies; no business logic is
    inlined in any step (Mandate-12 criterion 3).
    """

    def __init__(self, tmp_root: Path) -> None:
        self._tmp_root = tmp_root
        self._fake_home = tmp_root / "fake_home"
        self._claude_dir = tmp_root / "claude_config"
        self._copilot_home = tmp_root / "copilot_home"
        self._project_root = tmp_root / "project"
        self._marker_path = tmp_root / _MARKER_FILENAME
        self._des_audit_dir = tmp_root / _DES_AUDIT_DIRNAME
        for d in (
            self._fake_home,
            self._claude_dir,
            self._copilot_home,
            self._project_root,
            self._des_audit_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)
        self._server: MockLLMServer | None = None

    # --- paths (port-exposed surface) --------------------------------------

    def hooks_dir(self) -> Path:
        return self._copilot_home / _HOOKS_DIRNAME

    def des_hook_path(self) -> Path:
        return self.hooks_dir() / _DES_HOOK_FILENAME

    def probe_hook_path(self) -> Path:
        return self.hooks_dir() / _PROBE_HOOK_FILENAME

    def marker_path(self) -> Path:
        return self._marker_path

    def des_audit_dir(self) -> Path:
        return self._des_audit_dir

    # --- GIVEN composition methods -----------------------------------------

    def stage_copilot_runtime(self) -> None:
        """Make the binary recognise this tmp tree as a Copilot home.

        Writes a ``<COPILOT_HOME>/settings.json`` (the CLI creates this on first
        launch; also the installer's detection fallback per spike §4) so the
        runtime is present with no nWave hook yet.
        """
        (self._copilot_home / "settings.json").write_text("{}\n", encoding="utf-8")

    def stage_probe_session_start_hook(self) -> None:
        """Hand-write a sessionStart marker hook (harness-soundness path).

        Proves the mock-server + real-binary + hook-firing harness is sound,
        independent of the production-plugin gap. The hook is a tiny inline bash
        command that touches the marker file when sessionStart fires — no DES
        adapter, because this AT proves FIRING, not DES decision logic.

        SCHEMA (empirically established by slice-02 DISTILL against v1.0.54): the
        hook config MUST wrap the event-keyed map under a TOP-LEVEL ``hooks``
        object — ``{"hooks": {"sessionStart": [{matcher, hooks:[{type, bash}]}]}}``.
        The event-keyed-at-top-level shape (no ``hooks`` wrapper) — the shape
        slice-01's plugin and the spike's FS-1 sample emit — is REJECTED by the
        binary with ``Invalid hook configuration: hooks must be an object`` and
        the hook never fires. This is a crux finding for slice-02 DELIVER (see
        at-scaffold-notes-slice-02.md FS-1-bis).
        """
        self.hooks_dir().mkdir(parents=True, exist_ok=True)
        bash = f"printf '%s' '{_MARKER_CONTENT}' > {self._marker_path}"
        config = {
            "hooks": {
                _SESSION_START_EVENT: [
                    {
                        "matcher": ".*",
                        "hooks": [{"type": "command", "bash": bash, "timeoutSec": 30}],
                    }
                ]
            }
        }
        self.probe_hook_path().write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

    def install_via_production_plugin(self) -> None:
        """Run the REAL installer subprocess (the production driving port).

        After DELIVER adds sessionStart wiring + the top-level ``hooks`` wrapper to
        ``copilot_des_plugin.py``, the real binary fires the installed adapter
        command and the adapter writes its DES audit-log entry (HOOK_INVOKED /
        HOOK_COMPLETED). Before DELIVER, only a (non-firing) preToolUse hook is
        installed in the un-wrapped schema v1.0.54 rejects → the command is never
        fired → no audit entry → AT-1 is RED for the right reason.

        AT-1 observes the production adapter's OWN side-effect (the DES audit-log
        entry under the tmp ``DES_AUDIT_LOG_DIR``), NOT this fixture's probe
        marker. The probe marker is the harness-soundness surface (AT-2) only.
        """
        repo_root = Path(__file__).resolve().parents[5]
        install_nwave = repo_root / "scripts" / "install" / "install_nwave.py"
        env = self._sandboxed_env()
        env["CLAUDE_CONFIG_DIR"] = str(self._claude_dir)
        import sys as _sys

        subprocess.run(
            [_sys.executable, str(install_nwave)],
            cwd=str(self._project_root),
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
            check=False,
        )

    # --- WHEN composition method -------------------------------------------

    def run_real_copilot_session(self) -> CopilotFiringObservation:
        """Start the mock LLM, invoke the real ``copilot`` binary, capture firing.

        Determinism contract (flake mitigation):
          1. Bind the mock server on an ephemeral port.
          2. Probe the server's readiness endpoint until it answers (or budget
             exhausted) BEFORE launching copilot.
          3. Launch ``copilot -p "say ok" --allow-all-tools`` with
             ``COPILOT_OFFLINE=true`` + ``COPILOT_PROVIDER_BASE_URL`` pointed at
             the mock, a fake HOME, and the tmp COPILOT_HOME.
          4. A generous turn timeout (90 s) absorbs cold-start extraction.
          5. Tear the server down in a finally block.

        Before launching, the tmp DES audit dir is reset to empty so any
        audit entries the INSTALL subprocess may have written are not mistaken
        for the copilot-session firing — the captured audit events are then
        unambiguously attributable to Copilot invoking the installed hook.
        """
        binary = copilot_binary_path()
        assert binary is not None, "copilot binary must be present (guarded by skipif)"

        self._reset_des_audit_dir()
        self._server = MockLLMServer().start()
        try:
            base_url = self._server.base_url
            self._await_server_ready(base_url)
            completed = self._invoke_copilot(binary, base_url)
        finally:
            self._server.stop()
            self._server = None

        return self._capture_surface(completed)

    # --- subprocess + server plumbing --------------------------------------

    def _reset_des_audit_dir(self) -> None:
        """Empty the tmp DES audit dir so only the copilot session populates it."""
        for log_file in self._des_audit_dir.glob("audit-*.log"):
            log_file.unlink()

    def _await_server_ready(self, base_url: str) -> None:
        """Poll the mock server until it answers a GET, or the budget expires."""
        deadline = time.monotonic() + _READINESS_TIMEOUT_S
        last_err: Exception | None = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(base_url, timeout=1) as resp:
                    if resp.status == 200:
                        return
            except (urllib.error.URLError, OSError) as exc:  # not ready yet
                last_err = exc
                time.sleep(_READINESS_POLL_S)
        raise AssertionError(
            f"mock LLM server at {base_url} never became ready within "
            f"{_READINESS_TIMEOUT_S}s (last error: {last_err!r})"
        )

    def _invoke_copilot(
        self, binary: str, base_url: str
    ) -> subprocess.CompletedProcess:
        """Invoke the real copilot binary against the mock server (BYOK offline).

        BYOK mode is activated by ``COPILOT_PROVIDER_BASE_URL`` alone (no GitHub
        auth required, per ``copilot help providers``). A model is REQUIRED for
        BYOK — ``COPILOT_MODEL`` is the simplest option (it sets both the model
        ID and the wire model); the spike used ``COPILOT_MODEL=probe-model``. The
        provider base URL carries the OpenAI ``/v1`` prefix the binary expects;
        the mock server tolerates the prefix (it matches any path ending in
        ``chat/completions``). ``COPILOT_PROVIDER_TYPE=openai`` is the default but
        is set explicitly for determinism.
        """
        env = self._sandboxed_env()
        env["COPILOT_OFFLINE"] = "true"
        env["COPILOT_PROVIDER_BASE_URL"] = f"{base_url}/v1"
        env["COPILOT_PROVIDER_TYPE"] = "openai"
        env["COPILOT_MODEL"] = "probe-model"
        return subprocess.run(
            [binary, "-p", "say ok", "--allow-all-tools"],
            cwd=str(self._project_root),
            capture_output=True,
            text=True,
            timeout=_COPILOT_TURN_TIMEOUT_S,
            env=env,
            check=False,
        )

    def _sandboxed_env(self) -> dict[str, str]:
        """Hermetic env: fake HOME + tmp COPILOT_HOME + tmp DES audit dir.

        Strips inherited HOME/USERPROFILE/XDG/COPILOT_HOME/DES_AUDIT_LOG_DIR so
        the real dev-machine ~/.copilot, ~/.claude and the real DES audit log are
        NEVER read or written.

        ``DES_AUDIT_LOG_DIR`` is exported so that when Copilot fires the installed
        production hook command, the DES adapter (running as a child of the
        copilot subprocess) writes its audit-log side-effect into THIS tmp dir —
        the production observable AT-1 reads back. ``DES_AUDIT_LOGGING_ENABLED``
        is pinned on for determinism (it defaults to True, but a stray global
        config could disable it).
        """
        import os

        _drop = (
            "HOME",
            "USERPROFILE",
            "XDG_CONFIG_HOME",
            "COPILOT_HOME",
            "DES_AUDIT_LOG_DIR",
            "DES_AUDIT_LOGGING_ENABLED",
        )
        stripped = {k: v for k, v in os.environ.items() if k not in _drop}
        stripped["HOME"] = str(self._fake_home)
        stripped["COPILOT_HOME"] = str(self._copilot_home)
        stripped["COPILOT_CLI"] = "1"
        stripped["DES_AUDIT_LOG_DIR"] = str(self._des_audit_dir)
        stripped["DES_AUDIT_LOGGING_ENABLED"] = "1"
        stripped["PYTHONDONTWRITEBYTECODE"] = "1"
        return stripped

    def _installed_hook_events(self) -> tuple[str, ...]:
        """Event names the installed DES hook config registers (empty if absent).

        This is the universe entry the WALKING-SKELETON AT uses to make the
        production-plugin gap explicit: until DELIVER adds sessionStart, the
        production hook config carries only ``preToolUse`` — a non-firing event.
        """
        path = self.des_hook_path()
        if not path.is_file():
            return ()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return ()
        if not isinstance(data, dict):
            return ()
        root = data.get("hooks") if isinstance(data.get("hooks"), dict) else data
        return tuple(k for k in root if isinstance(root.get(k), list))

    def _des_audit_event_types(self) -> tuple[str, ...]:
        """Audit event types the production DES adapter wrote (empty if none).

        Reads every ``audit-*.log`` file under the tmp ``DES_AUDIT_LOG_DIR`` and
        collects each line's ``event`` field. A non-empty result means Copilot
        fired the installed production command end-to-end (the adapter logs
        ``HOOK_INVOKED`` at entry + ``HOOK_COMPLETED`` in its finally block on
        EVERY invocation — see hook_protocol.py). This is the PRODUCTION
        observable AT-1 asserts on — NOT the probe marker.
        """
        audit_dir = self._des_audit_dir
        if not audit_dir.is_dir():
            return ()
        event_types: list[str] = []
        for log_file in sorted(audit_dir.glob("audit-*.log")):
            for line in log_file.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except (json.JSONDecodeError, ValueError):
                    continue
                event = record.get("event") if isinstance(record, dict) else None
                if isinstance(event, str):
                    event_types.append(event)
        return tuple(event_types)

    def _capture_surface(
        self, completed: subprocess.CompletedProcess
    ) -> CopilotFiringObservation:
        marker = self._marker_path
        return CopilotFiringObservation(
            copilot_returncode=completed.returncode,
            marker_exists=marker.is_file(),
            marker_content=(
                marker.read_text(encoding="utf-8") if marker.is_file() else None
            ),
            installed_hook_events=self._installed_hook_events(),
            des_audit_event_types=self._des_audit_event_types(),
            copilot_stdout_tail="\n".join(completed.stdout.splitlines()[-30:]),
            copilot_stderr_tail="\n".join(completed.stderr.splitlines()[-30:]),
        )

    # --- THEN composition methods (assertions) -----------------------------

    def assert_production_hook_fired(self, obs: CopilotFiringObservation) -> None:
        """Walking-skeleton THEN (AT-1): the PRODUCTION hook fired end-to-end.

        The observable proof is the REAL PRODUCTION side-effect — a DES audit-log
        entry written by the installed adapter command when the real ``copilot``
        binary fired it. The adapter logs ``HOOK_INVOKED`` + ``HOOK_COMPLETED`` on
        EVERY invocation (see hook_protocol.py), so a non-empty audit log proves
        Copilot invoked our production command end-to-end. This is NOT the probe
        marker — there is no fixture path that writes a DES audit entry, so a
        GREEN can only come from the real production command firing (closed-world
        / Pista-2 false-GREEN trap avoided at its root).

        RED-for-the-right-reason against slice-01: the production install wires
        only ``preToolUse`` (a non-firing event, CRUX-1) in the un-wrapped schema
        v1.0.54 rejects (CRUX-2), so Copilot never fires the installed command →
        the adapter is never invoked → NO audit entry → empty event set. The
        assertion message surfaces the installed events so the gap is unambiguous.

        Boundary note (slice-03): the audit side-effect is event-shape-agnostic,
        so this proves FIRING even if the adapter's full DES decision logic does
        not yet support Copilot's event shape (that support is slice-03 scope).
        """
        fired = bool(obs.des_audit_event_types)
        assert fired, (
            "The installed PRODUCTION nWave Copilot hook MUST fire when the real "
            "`copilot` binary runs a session — the DES adapter should have written "
            f"a HOOK_INVOKED / HOOK_COMPLETED audit entry under {self._des_audit_dir}, "
            "but the audit log is empty (the production command was never fired).\n"
            f"Installed hook events: {obs.installed_hook_events or '(none)'}\n"
            f"DES audit event types observed: {obs.des_audit_event_types or '(none)'}\n"
            "  (slice-01 installs only 'preToolUse' in the un-wrapped schema that "
            "v1.0.54 rejects; slice-02 DELIVER must add a 'sessionStart' hook entry "
            "AND wrap the event map under a top-level 'hooks' key so the real "
            "binary fires the production adapter.)\n"
            f"copilot exit={obs.copilot_returncode}\n"
            f"stdout tail:\n{obs.copilot_stdout_tail}\n"
            f"stderr tail:\n{obs.copilot_stderr_tail}"
        )

    def assert_probe_hook_fired(self, obs: CopilotFiringObservation) -> None:
        """Harness-soundness THEN (AT-2): the hand-wired probe hook FIRED.

        The observable proof is the marker file written by the hand-wired
        ``sessionStart`` probe hook when the real ``copilot`` binary ran a session.
        The probe marker is legitimate HERE because AT-2's job is to prove the
        harness (mock server + real binary + hook firing) is SOUND — not to prove
        the production path. A passing AT-2 means a RED on AT-1 is unambiguously a
        production gap, not a harness bug.
        """
        assert obs.marker_exists, (
            "The hand-wired probe sessionStart hook MUST fire when the real "
            "`copilot` binary runs a session — it should have written the marker "
            f"at {self._marker_path}, but it was not written. A RED here means the "
            "harness (mock server + real binary + hook firing) is itself unsound.\n"
            f"copilot exit={obs.copilot_returncode}\n"
            f"stdout tail:\n{obs.copilot_stdout_tail}\n"
            f"stderr tail:\n{obs.copilot_stderr_tail}"
        )

    def assert_marker_content(self, obs: CopilotFiringObservation) -> None:
        """THEN: the marker carries the distinctive content the hook writes.

        Guards against a false pass on an unrelated pre-existing file (the marker
        path is unique to this tmp tree, but the content check makes the proof
        that THIS hook fired, not some ambient touch).
        """
        assert obs.marker_content == _MARKER_CONTENT, (
            "The fired-hook marker MUST carry the distinctive content "
            f"{_MARKER_CONTENT!r} (proving THIS hook wrote it); observed "
            f"{obs.marker_content!r}."
        )

    def assert_production_hook_registers_firing_event(
        self, obs: CopilotFiringObservation
    ) -> None:
        """Walking-skeleton THEN: the PRODUCTION install registers a firing event.

        Makes the crux finding mechanically checkable: the production
        ``copilot_des_plugin`` MUST register the spike-proven-firing
        ``sessionStart`` event (not only the non-firing ``preToolUse``). RED
        against slice-01 (events == ('preToolUse',)); GREEN after DELIVER adds
        sessionStart wiring.
        """
        assert _SESSION_START_EVENT in obs.installed_hook_events, (
            "The production Copilot install MUST register the spike-proven-firing "
            f"'{_SESSION_START_EVENT}' event so the DES hook actually fires in the "
            "real binary. The installed hook config registers only "
            f"{obs.installed_hook_events or '(none)'} — slice-02 DELIVER must add "
            "a sessionStart hook entry to copilot_des_plugin.py."
        )
