"""SessionStart hook handler for nWave update checks and housekeeping.

Reads hook input JSON from stdin, runs housekeeping, invokes UpdateCheckService,
and writes the update notice JSON to stdout when UPDATE_AVAILABLE.

Fail-open: any exception exits 0 so session is never blocked.
Housekeeping and update check run in independent try/except blocks.
Housekeeping runs before update check; DESConfig is shared between both.

Output format when UPDATE_AVAILABLE (see ``_build_update_output``):
    {
      "systemMessage": "nWave update available: {local} → {latest}. Run /nw-update to update.",
      "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "nWave update available: {local} → {latest}. Changes: {changelog_or_empty}"
      }
    }

``systemMessage`` is shown to the user; ``additionalContext`` is injected into
the model context. The wrapped ``hookSpecificOutput`` form is required -- the
bare ``{"additionalContext": ...}`` form is not honored by current Claude Code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.drivers.hooks.substrate_probe import run_probe


if TYPE_CHECKING:
    from des.adapters.driven.config.des_config import DESConfig
    from des.application.update_check_service import UpdateCheckService
    from des.ports.driven_ports.package_manager_port import PackageManagerPort


def _get_local_version() -> str:
    """Return installed nwave-ai version, or '0.0.0' if unavailable."""
    from des.application.update_check_service import _detect_local_version

    return _detect_local_version()


def _select_package_manager_adapter(pm: str) -> PackageManagerPort:
    """Return the adapter for the given package manager name.

    For ``pm == "unknown"`` returns a ``NullPackageManager`` no-op adapter; the
    service exits via its own ``flag.pm == "unknown"`` branch before invoking
    ``upgrade()`` on it. Always returning a real ``PackageManagerPort`` keeps
    the type contract honest and removes the need for ``# type: ignore`` at
    the call site.
    """
    if pm == "pipx":
        from des.adapters.driven.package_managers.pipx_package_manager_adapter import (
            PipxPackageManagerAdapter,
        )

        return PipxPackageManagerAdapter()
    if pm == "uv":
        from des.adapters.driven.package_managers.uv_package_manager_adapter import (
            UvPackageManagerAdapter,
        )

        return UvPackageManagerAdapter()
    # pm == "unknown": service handles via its existing branch.
    from des.adapters.driven.package_managers.null_package_manager import (
        NullPackageManager,
    )

    return NullPackageManager()


def _apply_pending_update_if_any(des_config: DESConfig, current_version: str) -> None:
    """Early-phase apply of any pending deferred nWave self-update.

    Reads the pending-update flag via DESConfig; when present, composes a
    PendingUpdateService with the adapter matching ``flag.pm`` and invokes
    ``apply()``. For ``flag.pm == "unknown"`` the service handles the branch
    internally (no adapter invoked) and emits a warning banner.

    Fail-open: all exceptions are swallowed so the session is never blocked.
    """
    try:
        flag = des_config.read_pending_update()
        if flag is None:
            return

        from des.application.pending_update_service import PendingUpdateService

        adapter = _select_package_manager_adapter(flag.pm)

        service = PendingUpdateService(
            config=des_config,
            pm=adapter,
            current_version=current_version,
        )
        service.apply()
    except Exception as e:
        sys.stderr.write(f"[nwave] pending-update apply error (fail-open): {e}\n")


def _adopt_prior_use_if_warranted(stdin_text: str) -> None:
    """Trigger-1: silently adopt a prior-use project at SessionStart (DDD-7).

    SessionStart is gate-exempt (always runs), so this is the wiring point for
    prior-use adoption. Resolves the project root from the hook stdin ``cwd``
    (same envelope shape every handler reads), then asks ``AutoMarkingService``
    to write the marker IFF prior-use evidence warrants it. Silent and fail-open:
    any parse/IO error is swallowed so SessionStart's update-notice and
    housekeeping are never disturbed.
    """
    try:
        project_root = _parse_cwd(stdin_text)
        if project_root is None:
            return
        from des.application.auto_marking_service import (
            AdoptionTrigger,
            AutoMarkingService,
        )

        AutoMarkingService().adopt_if_warranted(
            project_root=project_root, trigger=AdoptionTrigger.PRIOR_USE
        )
    except Exception as e:
        sys.stderr.write(f"[nwave] prior-use adoption error (fail-open): {e}\n")


def _parse_cwd(stdin_text: str) -> Path | None:
    """Resolve the project root from the hook stdin envelope's ``cwd`` field."""
    try:
        data = json.loads(stdin_text)
    except (json.JSONDecodeError, TypeError):
        return None
    cwd = data.get("cwd") if isinstance(data, dict) else None
    return Path(cwd) if cwd else None


def _run_housekeeping(des_config: DESConfig) -> None:
    """Run housekeeping using configuration from DESConfig.

    Builds HousekeepingConfig from des_config properties and delegates to
    HousekeepingService. Fail-open: caller must wrap in try/except.
    """
    from des.adapters.driven.time.system_time import SystemTimeProvider
    from des.application.housekeeping_service import (
        HousekeepingConfig,
        HousekeepingService,
    )

    config = HousekeepingConfig(
        enabled=des_config.housekeeping_enabled,
        audit_retention_days=des_config.housekeeping_audit_retention_days,
        signal_staleness_hours=des_config.housekeeping_signal_staleness_hours,
        skill_log_max_bytes=des_config.housekeeping_skill_log_max_bytes,
    )
    HousekeepingService.run_housekeeping(config, SystemTimeProvider())


def _build_update_check_service(des_config: DESConfig) -> UpdateCheckService:
    """Build UpdateCheckService with a shared DESConfig for frequency gating."""
    from des.application import update_check_service

    return update_check_service.UpdateCheckService(des_config=des_config)


def _build_update_message(local: str, latest: str, changelog: str | None) -> str:
    """Format the model-facing additionalContext message for an available update."""
    changes = changelog or ""
    return f"nWave update available: {local} \u2192 {latest}. Changes: {changes}"


# ---------------------------------------------------------------------------
# D6 / M5 \u2014 hook-version skew detection (the PRIMARY skew detector)
# ---------------------------------------------------------------------------


def _parse_version_tuple(version: str) -> tuple[int, ...]:
    """Parse a `MAJOR.MINOR.PATCH` version into an integer tuple for comparison.

    Raises `ValueError` on a non-numeric component -- the caller treats an
    unparseable stamp as skew (fail-closed), never "assume current".
    """
    return tuple(int(part) for part in version.strip().split("."))


def _classify_hook_version_skew(
    installed_hook_version: str | None, checkout_version: str
) -> str | None:
    """Classify hook-version skew into one of the three M13 cases.

    Returns the skew case (`"behind"`, `"ahead"`, `"stamp-absent"`) or None
    when the installed hook version matches the running checkout.

    M13 -- three cases, not one:
      * stamp absent  -> `"stamp-absent"` (S28 partial-install signature or
        pre-D6 hooks; never "assume current");
      * installed < checkout -> `"behind"` (old hooks, U1/U2 intercepts stale);
      * installed > checkout -> `"ahead"` (hook set newer than the running
        checkout -- equally untrustworthy, S27 downgrade signature).
    """
    if not installed_hook_version:
        return "stamp-absent"
    try:
        installed = _parse_version_tuple(installed_hook_version)
        checkout = _parse_version_tuple(checkout_version)
    except ValueError:
        # An unparseable stamp is treated as skew, never silently accepted.
        return "stamp-absent"
    if installed < checkout:
        return "behind"
    if installed > checkout:
        return "ahead"
    return None


def _read_installed_hook_version() -> str | None:
    """Read `nwave_hook_version` from the user's `~/.claude/settings.json`.

    Returns the stamped version string, or None when `settings.json` is
    absent, unreadable, or carries no stamp (a pre-D6 install / partial
    install -- the M13 `stamp-absent` case).
    """
    from pathlib import Path

    settings_path = Path.home() / ".claude" / "settings.json"
    try:
        raw = settings_path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        settings = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(settings, dict):
        return None
    stamp = settings.get("nwave_hook_version")
    return stamp if isinstance(stamp, str) and stamp else None


def _build_skew_message(case: str, installed: str | None, checkout: str) -> str:
    """Format the additionalContext skew finding for a `HookVersionSkew`.

    The SessionStart hook is the PRIMARY skew detector (M5) -- mechanically
    fired every session, so skew surfaces even when the orchestrator skips the
    prose-invoked `/nw-deliver` phase-entry diagnostic.
    """
    payload = {
        "event": "HookVersionSkew",
        "case": case,
        "installed_hook_version": installed or "<absent>",
        "checkout_version": checkout,
        "remediation": (
            "re-run the nWave installer to upgrade DES hooks; the atdd_pure "
            "spine gates (U1/U2/U4) are not enforced by your installed hooks"
        ),
    }
    return json.dumps(payload)


def _session_cwd_is_atdd_pure(cwd: str | None) -> bool:
    """True when the session cwd is an `atdd_pure`-mode nWave project.

    Reads `{cwd}/.nwave/config.yaml` `workflow.mode`. ADR-030 D6 scopes the
    skew gate to `atdd_pure` -- classic-mode projects (and non-project cwds)
    are unaffected, so the SessionStart detector stays silent there.
    """
    if not cwd:
        return False
    from pathlib import Path

    from des.application.workflow_mode import ATDD_PURE_MODE, resolve_workflow_mode

    try:
        return resolve_workflow_mode(Path(cwd)) == ATDD_PURE_MODE
    except Exception:
        return False


def _emit_hook_version_skew_finding(cwd: str | None) -> None:
    """Detect hook-version skew and write a `HookVersionSkew` finding to stdout.

    The D6/M5 primary skew detector: reads the installed `nwave_hook_version`
    stamp, compares it to the running checkout's nWave version, and on skew
    emits a structured finding as `additionalContext`. Fail-open -- any
    exception is swallowed so the session is never blocked (the `/nw-deliver`
    phase-entry diagnostic remains the fail-CLOSED gate for atdd_pure).

    ADR-030 D6: the skew gate is scoped to `atdd_pure`. The detector emits
    only when the session cwd is an `atdd_pure`-mode project -- classic
    sessions are unaffected.
    """
    try:
        if not _session_cwd_is_atdd_pure(cwd):
            return
        checkout_version = _get_local_version()
        installed = _read_installed_hook_version()
        case = _classify_hook_version_skew(installed, checkout_version)
        if case is None:
            return
        message = _build_skew_message(case, installed, checkout_version)
        print(json.dumps({"additionalContext": message}))
    except Exception:
        pass


def _build_visible_message(local: str, latest: str) -> str:
    """Format the user-visible systemMessage shown on screen at session start."""
    return f"nWave update available: {local} \u2192 {latest}. Run /nw-update to update."


def _build_update_output(
    local: str, latest: str, changelog: str | None
) -> dict[str, object]:
    """Build the SessionStart hook JSON payload for an available update.

    Emits BOTH:
    - ``systemMessage`` (top-level) -- rendered visibly to the user at session
      start. ``additionalContext`` alone is injected silently and never shown,
      so a visible notice requires this field.
    - ``hookSpecificOutput.additionalContext`` -- the canonical wrapped form for
      context injection. The bare ``{"additionalContext": ...}`` form is dropped
      by current Claude Code versions, so the wrapper is required for the model
      to actually receive the update context.
    """
    return {
        "systemMessage": _build_visible_message(local, latest),
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": _build_update_message(local, latest, changelog),
        },
    }


_GATE_AFFORDANCE_NUDGE_TEXT = (
    "nWave gate-affordance: an active feature-delta is present in this repo. "
    "Satisfy each gate's expectation BEFORE it fires -- see the nw-buddy "
    "gate-affordance knowledge for the gate -> expectation -> producing-tool "
    "map, or run `des feature-delta-doctor` / `des dispatch` directly."
)


def build_gate_affordance_nudge(cwd: str | None) -> str | None:
    """Return the proactive gate-affordance nudge, or ``None`` (WS-17-A / GDP-2).

    An active feature-delta is any readable ``docs/feature/<id>/feature-delta.md``
    directly under ``cwd``. Fail-open: any error -- ``cwd`` is ``None``, ``cwd``
    is not a directory, no ``docs/feature`` tree, or a malformed/unreadable
    ``feature-delta.md`` (directory-where-file-expected, permission denied) --
    degrades to ``None``, never raises.

    The nudge text POINTS at the nw-buddy gate-affordance SSOT and names a
    concrete producing tool (``des feature-delta-doctor`` / ``des dispatch``)
    rather than duplicating the gate table inline (M1 single content locus).
    """
    try:
        if not cwd:
            return None
        feature_root = Path(cwd) / "docs" / "feature"
        if not feature_root.is_dir():
            return None
        for entry in sorted(feature_root.iterdir()):
            delta_path = entry / "feature-delta.md"
            try:
                delta_path.read_text(encoding="utf-8")
            except OSError:
                continue
            return _GATE_AFFORDANCE_NUDGE_TEXT
        return None
    except Exception:
        return None


def _build_gate_affordance_output(nudge: str) -> dict[str, object]:
    """Build the SessionStart hookSpecificOutput payload for the gate-affordance nudge."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": nudge,
        }
    }


# ---------------------------------------------------------------------------
# orchestrator-affordance-injection (slice-01): load the orchestrator's
# spine-discipline + producing-tool affordance from shipped text assets,
# never hardcoded in code.
# ---------------------------------------------------------------------------

_ORCHESTRATOR_AFFORDANCE_SEPARATOR = "\n\n"

# Resolved the same way `carpaccio_intercept.py` resolves `nWave/flavors/`
# (`Path(__file__).resolve().parents[N]/nWave/...`): this module lives at
# src/des/adapters/drivers/hooks/, so parents[5] is the repo / install root.
_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR = (
    Path(__file__).resolve().parents[5] / "nWave" / "data" / "orchestrator-affordance"
)


def load_orchestrator_affordance(assets_dir: Path) -> str | None:
    """Load and concatenate every `*.md` file under `assets_dir`.

    Reads every `*.md` file directly under `assets_dir`, sorted by name, and
    concatenates their text with a separator. Content is read fresh on every
    call -- never cached or hardcoded -- so editing a shipped asset surfaces
    on the next call with zero code change.

    Fail-open: returns `None` when `assets_dir` does not exist, contains no
    `.md` file, or is unreadable for any reason. Never raises.
    """
    try:
        if not assets_dir.is_dir():
            return None
        md_paths = sorted(assets_dir.glob("*.md"))
        if not md_paths:
            return None
        contents = [path.read_text(encoding="utf-8") for path in md_paths]
        return _ORCHESTRATOR_AFFORDANCE_SEPARATOR.join(contents)
    except Exception:
        return None


def _build_orchestrator_affordance_output(affordance: str) -> dict[str, object]:
    """Build the SessionStart hookSpecificOutput payload for the affordance text."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": affordance,
        }
    }


def handle_session_start() -> int:
    """Handle session-start hook: run housekeeping then check for nWave updates.

    Reads JSON from stdin (Claude Code hook protocol), runs housekeeping,
    calls UpdateCheckService, and writes additionalContext to stdout when an
    update is available. DESConfig is shared between both operations.

    Returns:
        0 always (fail-open: session must never be blocked).
    """
    # Read stdin ONCE; both the cwd-parse (skew detector) and the prior-use
    # adoption consume the same payload (a second sys.stdin.read() would return
    # empty after the first).
    raw_stdin = sys.stdin.read()
    session_cwd: str | None = None
    try:
        parsed_input = json.loads(raw_stdin) if raw_stdin.strip() else {}
        if isinstance(parsed_input, dict):
            cwd_value = parsed_input.get("cwd")
            session_cwd = cwd_value if isinstance(cwd_value, str) else None
    except json.JSONDecodeError:
        session_cwd = None

    # Trigger-1 (prior-use adoption): SessionStart is gate-exempt, so this is
    # where an unmarked project with prior nWave use is silently adopted. Runs
    # first and fail-open so it never disturbs the update-notice / housekeeping.
    _adopt_prior_use_if_warranted(raw_stdin)

    from des.adapters.driven.config.des_config import DESConfig

    des_config = DESConfig()

    # Early phase: apply any pending deferred self-update BEFORE housekeeping
    # and update-check. A just-upgraded session must not run update-check with
    # a stale current_version comparison.
    _apply_pending_update_if_any(des_config, _get_local_version())

    try:
        _run_housekeeping(des_config)
    except Exception:
        pass

    try:
        service = _build_update_check_service(des_config)
        result = service.check_for_updates()

        from des.application.update_check_service import UpdateStatus

        if result.status == UpdateStatus.UPDATE_AVAILABLE:
            output = _build_update_output(
                local=_get_local_version(),
                latest=result.latest or "",
                changelog=result.changelog,
            )
            print(json.dumps(output))

    except Exception:
        pass

    try:
        advisory = run_probe()
        if advisory:
            print(advisory, end="")
    except Exception:
        pass

    # WS-17-A / GDP-2: proactive gate-affordance nudge -- surfaces the
    # gate -> expectation -> producing-tool pointer BEFORE any gate fires,
    # when an active feature-delta exists under the session cwd. Fail-open.
    try:
        nudge = build_gate_affordance_nudge(session_cwd)
        if nudge:
            print(json.dumps(_build_gate_affordance_output(nudge)))
    except Exception:
        pass

    # D6 / M5: the PRIMARY hook-version skew detector. Mechanically fired every
    # session start -- catches skew even when the orchestrator skips the
    # prose-invoked /nw-deliver phase-entry diagnostic. Scoped to atdd_pure
    # projects (ADR-030 D6); fail-open.
    _emit_hook_version_skew_finding(session_cwd)

    # orchestrator-affordance-injection (slice-01): load the shipped
    # spine-discipline + producing-tool affordance from text assets and
    # inject it as additionalContext. Additive to the update-notice and the
    # gate-affordance nudge above; fail-open.
    try:
        affordance = load_orchestrator_affordance(_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR)
        if affordance:
            print(json.dumps(_build_orchestrator_affordance_output(affordance)))
    except Exception:
        pass

    return 0
