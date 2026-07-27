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

``handle_session_start`` may have several independent contributors fire in
the same session (the update notice, the gate-affordance nudge, the
hook-version-skew finding, the workflow-mode guidance, the orchestrator
affordance). Every one of them APPENDS its text to a single accumulator
instead of printing its own JSON line -- ``handle_session_start`` prints AT
MOST ONE combined JSON object per invocation, always in the wrapped
``hookSpecificOutput`` form, with contributions joined by
``_ORCHESTRATOR_AFFORDANCE_SEPARATOR``. This is deliberate: multiple
independent ``print(json.dumps(...))`` calls in one invocation produce
multiple JSON objects on separate stdout lines, which is not valid JSON as a
whole and silently drops every contribution but the first for any consumer
that reads/parses the full stdout as one object. The substrate-probe
advisory (``run_probe``) is the one exception -- it is a plain one-line
human-readable string, not JSON, and is printed on its own line by design.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from des.adapters.drivers.hooks.substrate_probe import run_probe
from des.domain.iso_utc import format_iso_utc


if TYPE_CHECKING:
    from des.adapters.driven.config.des_config import DESConfig
    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
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
    to write the marker IFF prior-use evidence warrants it. Fail-open: any
    parse/IO error is swallowed so SessionStart's update-notice and
    housekeeping are never disturbed -- but degrades LOUD (a labeled
    ``[nwave] ...`` diagnostic on stderr), never silently, so a swallowed
    error is never byte-identical to the genuine no-op (a valid envelope
    whose cwd is a real directory with no ``.nwave/``).
    """
    try:
        project_root = _parse_cwd(stdin_text)
        from des.application.auto_marking_service import (
            AdoptionTrigger,
            AutoMarkingService,
        )

        AutoMarkingService().adopt_if_warranted(
            project_root=project_root, trigger=AdoptionTrigger.PRIOR_USE
        )
    except Exception as e:
        sys.stderr.write(f"[nwave] prior-use adoption error (fail-open): {e}\n")


def _parse_cwd(stdin_text: str) -> Path:
    """Resolve the project root from the hook stdin envelope's ``cwd`` field.

    Raises ``ValueError`` for every malformed-envelope class -- unparseable
    JSON, a non-object payload, a missing/null/non-string ``cwd``, or a
    ``cwd`` that does not point at an existing directory -- so the caller
    routes each of them through the labeled fail-open stderr degrade path.
    Returns the resolved ``Path`` ONLY for a genuinely valid envelope whose
    ``cwd`` points at an existing directory -- the sole case that must stay
    fully silent (no stdout, no stderr).
    """
    try:
        data = json.loads(stdin_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"malformed JSON stdin envelope: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"stdin envelope is not a JSON object: {data!r}")
    cwd = data.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise ValueError(f"stdin envelope cwd is missing or not a string: {cwd!r}")
    project_root = Path(cwd)
    if not project_root.is_dir():
        raise ValueError(f"stdin envelope cwd is not an existing directory: {cwd!r}")
    return project_root


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


def _emit_codex_continued_work_opportunity(
    cwd: str | None, host_provenance: str | None
) -> None:
    """Execute one due bounded work item through the host-agnostic loop runner."""
    if cwd is None or host_provenance != "codex":
        return
    try:
        from des.application.standing_loop_facade import StandingLoopFacade

        execution = StandingLoopFacade().execute_for_session_start(Path(cwd))
        if execution is None:
            return
        opportunity, attestation = execution
        limits = opportunity.limits
        if (
            attestation.budget_verdict == "EXHAUSTED"
            and attestation.execution_receipt is None
        ):
            message = (
                f"Continued-work opportunity: {opportunity.outcome}. "
                "TOKEN_BUDGET_EXHAUSTED: no bounded action was executed. "
                "Authorised limits: "
                f"max tokens {limits['max_tokens_per_tick']}; "
                f"max wall seconds {limits['max_wall_seconds']}. "
                f"{'Replayed' if attestation.replayed else 'Completed'} canonical terminal loop occurrence."
            )
        else:
            message = (
                f"Continued-work opportunity: {opportunity.outcome}. "
                f"Continued-work execution receipt: {opportunity.outcome}. "
                "Authorised limits: "
                f"max tokens {limits['max_tokens_per_tick']}; "
                f"max wall seconds {limits['max_wall_seconds']}. "
                f"{'Replayed' if attestation.replayed else 'Completed'} canonical loop occurrence."
            )
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": message,
                    }
                }
            )
        )
    except Exception as error:
        sys.stderr.write(
            "[nwave] Codex continued-work opportunity unavailable (fail-open): "
            f"{error}. The session was not blocked and no work was started.\n"
        )


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
    """True when the session cwd is an `atdd_pure`-mode nWave PROJECT.

    Two conjuncts, both required:

    1. The cwd is an nWave PROJECT -- a `.nwave/` directory exists directly
       under it. This is the project gate the mode-resolution default cannot
       supply: `resolve_workflow_mode` DEFAULTS an unconfigured directory to
       `atdd_pure` (DDD-7), so reading the mode ALONE returns `atdd_pure` on a
       PLAIN non-nWave dir that has no `.nwave/` at all. Without this conjunct
       the predicate contradicts its own documented contract below.
    2. The project is `atdd_pure` -- `resolve_workflow_mode` reads
       `{cwd}/.nwave/config.yaml` `workflow.mode` (a tracked `.nwave/` with no
       explicit `classic` config still resolves to the `atdd_pure` default).

    ADR-030 D6 scopes the skew gate to `atdd_pure` -- classic-mode projects
    (and NON-PROJECT cwds) are unaffected, so the SessionStart detector stays
    silent there. The `.nwave/`-exists conjunct is what makes "non-project cwds
    are unaffected" TRUE (a fresh clone of an nWave repo HAS `.nwave/` --
    `local-config.json` is tracked -- so a genuine nWave project is unaffected).
    """
    if not cwd:
        return False
    from pathlib import Path

    from des.application.workflow_mode import ATDD_PURE_MODE, resolve_workflow_mode

    try:
        project_dir = Path(cwd)
        if not (project_dir / ".nwave").is_dir():
            return False
        return resolve_workflow_mode(project_dir).effective_mode == ATDD_PURE_MODE
    except Exception:
        return False


def _emit_hook_version_skew_finding(cwd: str | None) -> str | None:
    """Classify hook-version skew and return the finding's additionalContext text.

    The D6/M5 primary skew detector: reads the installed `nwave_hook_version`
    stamp, compares it to the running checkout's nWave version, and on skew
    returns a structured finding string for the caller to fold into the
    SINGLE combined SessionStart payload -- this function never touches
    stdout itself (see `handle_session_start`'s additional-context
    accumulator). Fail-open -- any exception is swallowed and `None` is
    returned (the `/nw-deliver` phase-entry diagnostic remains the
    fail-CLOSED gate for atdd_pure).

    ADR-030 D6: the skew gate is scoped to `atdd_pure`. Returns non-`None`
    only when the session cwd is an `atdd_pure`-mode project -- classic
    sessions are unaffected.
    """
    try:
        if not _session_cwd_is_atdd_pure(cwd):
            return None
        checkout_version = _get_local_version()
        installed = _read_installed_hook_version()
        case = _classify_hook_version_skew(installed, checkout_version)
        if case is None:
            return None
        return _build_skew_message(case, installed, checkout_version)
    except Exception:
        return None


def _is_an_nwave_project(project_dir: Path) -> bool:
    """True when this directory is nWave's business at all.

    Two independent traces, either sufficient: a declared `.nwave/` directory,
    or PRIOR USE -- feature work left on disk by earlier nWave runs. The second
    matters because the population that most needs to hear "the classic
    selector is gone" is precisely the one that used nWave BEFORE any mode was
    declared, and so has no `.nwave/` to key on.

    The prior-use predicate is deliberately the same shape the auto-marking
    service already uses (`_has_prior_use`): re-deriving "what counts as prior
    use" in a second place would be the very long-locality coupling this lane
    exists to remove -- two answers to one question, drifting apart silently.
    """
    if (project_dir / ".nwave").is_dir():
        return True
    feature_dir = project_dir / "docs" / "feature"
    return (
        any(feature_dir.glob("*/feature-delta.md"))
        or any(feature_dir.glob("*/execution-log.json"))
        or any(p.is_dir() for p in feature_dir.glob("*/deliver"))
    )


def _workflow_mode_session_guidance(cwd: str | None) -> str | None:
    """Return non-mutating, operator-actionable mode guidance for SessionStart.

    SessionStart is the earliest public seam.  It must distinguish an empty
    fresh workspace (the active workflow is ready), a legacy project whose
    mode was never declared, and a project still carrying a removed selector.
    Resolving here only reads bytes; it never repairs ``config.yaml``.
    """
    if not cwd:
        return None
    try:
        project_dir = Path(cwd)
        # SILENCE OUTSIDE AN nWave PROJECT IS A CONTRACT, not an oversight.
        # `resolve_workflow_selection` answers "which mode does this project
        # run", and for a directory carrying no `.nwave/` at all it answers
        # SELECTED/atdd_pure -- correct for its own question (nothing declares
        # anything else) and wrong as a reason to SPEAK. A session opened in an
        # unrelated directory must produce zero bytes: announcing there injects
        # context nobody asked for into every foreign session -- a surprise to
        # the operator, and a token cost re-paid on every turn that follows.
        # The adjacent `_session_cwd_is_atdd_pure` already draws this line; this
        # seam has to draw it too, because the question it asks is not the
        # question it must answer.
        #
        # But "is this an nWave project" is NOT the same as "does it carry a
        # `.nwave/` directory". A project that used nWave before the mode was
        # ever declared has no config and still deserves the guidance -- it is
        # exactly the population that must be told the selector it may remember
        # no longer exists. Silence is owed only where there is NO trace at all.
        if not _is_an_nwave_project(project_dir):
            return None

        from des.application.workflow_mode import resolve_workflow_selection

        selection = resolve_workflow_selection(project_dir)
    except Exception:
        return None
    if selection.selected:
        return (
            "nWave workflow ready: atdd_pure is the sole active workflow. "
            "Use the per-slice ATDD-pure spine."
        )
    return selection.diagnostic


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


# ---------------------------------------------------------------------------
# slice-05 (autonomous-consolidation-and-bugfix-loops) -- SessionStart wiring
# for the three pending-loop-tick request files slices 02-04 shipped as
# driving ports with zero production callers (OQ-3/DA-13). Each wrapper below
# is its OWN independent fail-open trigger, appended to `handle_session_start`
# exactly like the existing `_adopt_prior_use_if_warranted` /
# `_apply_pending_update_if_any` triggers. None of them is named
# `_stabilize_tick` -- that name is reserved by a DIFFERENT, not-yet-DELIVERed
# feature (`background-loops-hybrid-c`) extending the SAME hook function; see
# tests/des/acceptance/autonomous_consolidation_and_bugfix_loops/steps/
# domain_types_slice_05.py Sec. "HOOK-POINT COEXISTENCE".
# ---------------------------------------------------------------------------

_LOOP_TICK_WORK_EXHAUSTED_FILENAME = "loop-tick-work-exhausted.json"
_LOOP_TICK_BUGFIX_PIPELINE_FILENAME = "loop-tick-bugfix-pipeline.json"
_LOOP_TICK_CONSOLIDATION_SIGNAL_FILENAME = "loop-tick-consolidation-signal.json"


def _read_loop_tick_request(cwd: str | None, filename: str) -> dict[str, Any] | None:
    """Read+parse one optional ``.nwave/{filename}`` pending loop-tick request.

    Absence (no ``cwd``, or the file does not exist under it) is a safe no-op
    -- returns ``None``, distinguishable from a parsed empty payload. Raises
    ``ValueError``/``json.JSONDecodeError`` for an unparseable or non-object
    payload -- the caller routes that through the D-8 class-2 (no derivable
    feature_id) fail-open degrade, since a request that cannot even be
    parsed can never yield a feature_id to target.
    """
    if not cwd:
        return None
    request_path = Path(cwd) / ".nwave" / filename
    if not request_path.is_file():
        return None
    data = json.loads(request_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"loop-tick request {filename} is not a JSON object")
    return data


def _loop_tick_feature_id(payload: dict[str, Any]) -> str:
    """Derive the request's ``feature_id``, or raise (D-8 class 2).

    Raises ``ValueError`` when ``feature_id`` is absent, empty, or not a
    string -- there is no feature ledger to target, so the caller's own
    fail-open handling degrades to a labeled stderr diagnostic only, with no
    ledger write attempted.
    """
    feature_id = payload.get("feature_id")
    if not isinstance(feature_id, str) or not feature_id:
        raise ValueError("loop-tick request names no derivable feature_id")
    return feature_id


def _build_loop_tick_ledger(feature_id: str, cwd: str | None) -> AtCompletionLedger:
    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

    return AtCompletionLedger(feature_id, Path(cwd) if cwd else Path())


def _maybe_tick_work_exhausted(cwd: str | None) -> None:
    """Fire the pending work-exhausted tick (slice-02 seam), fail-open (D-8).

    A ``.nwave/loop-tick-work-exhausted.json`` request's absence is a safe
    no-op. A known ``feature_id`` missing the domain-required
    ``queue_state`` field is ledger-attested (``WorkExhaustedTickAttemptFailed``,
    reusing ``append_work_exhausted_event``). No derivable ``feature_id``, or
    any other unexpected error, degrades to a labeled stderr diagnostic only.
    """
    filename = _LOOP_TICK_WORK_EXHAUSTED_FILENAME
    try:
        payload = _read_loop_tick_request(cwd, filename)
        if payload is None:
            return
        feature_id = _loop_tick_feature_id(payload)
        now = datetime.now(timezone.utc)
        ledger = _build_loop_tick_ledger(feature_id, cwd)
        if "queue_state" not in payload:
            ledger.append_work_exhausted_event(
                "WorkExhaustedTickAttemptFailed",
                timestamp=format_iso_utc(now),
                gap_minutes=0,
                reason="missing field: queue_state",
                feature_id=feature_id,
            )
            return

        from des.domain.work_exhausted_ladder import evaluate_and_record

        evaluate_and_record(
            ledger=ledger,
            feature_id=feature_id,
            queue_state=payload["queue_state"],
            now=now,
            gated_reasons=payload.get("gated_reasons"),
        )
    except Exception as e:
        sys.stderr.write(f"[nwave] {filename} loop-tick error (fail-open): {e}\n")


def _maybe_tick_bugfix_pipeline(cwd: str | None) -> None:
    """Fire the pending bugfix-pipeline tick (slice-03 seam), fail-open (D-8).

    A ``.nwave/loop-tick-bugfix-pipeline.json`` request's absence is a safe
    no-op. A known ``feature_id`` missing a domain-required field
    (``defect_id`` / ``action`` / ``stage`` when not ``claim-drained``) is
    ledger-attested (``BugfixPipelineTickAttemptFailed``, reusing
    ``append_bugfix_pipeline_event``). No derivable ``feature_id``, or any
    other unexpected error, degrades to a labeled stderr diagnostic only.
    """
    filename = _LOOP_TICK_BUGFIX_PIPELINE_FILENAME
    try:
        payload = _read_loop_tick_request(cwd, filename)
        if payload is None:
            return
        feature_id = _loop_tick_feature_id(payload)
        now = datetime.now(timezone.utc)
        ledger = _build_loop_tick_ledger(feature_id, cwd)

        missing = _bugfix_pipeline_missing_field(payload)
        if missing is not None:
            ledger.append_bugfix_pipeline_event(
                "BugfixPipelineTickAttemptFailed",
                defect_id=payload.get("defect_id") or "<unknown>",
                timestamp=format_iso_utc(now),
                reason=f"missing field: {missing}",
                feature_id=feature_id,
            )
            return

        from des.domain.bugfix_pipeline import evaluate_and_record

        evaluate_and_record(
            ledger=ledger,
            feature_id=feature_id,
            defect_id=payload["defect_id"],
            action=payload["action"],
            stage=payload.get("stage"),
            now=now,
            reason=payload.get("reason"),
        )
    except Exception as e:
        sys.stderr.write(f"[nwave] {filename} loop-tick error (fail-open): {e}\n")


def _bugfix_pipeline_missing_field(payload: dict[str, Any]) -> str | None:
    """The first domain-required bugfix-pipeline field absent from ``payload``.

    ``defect_id`` and ``action`` are always required; ``stage`` is required
    unless ``action == "claim-drained"`` (mirrors
    ``des.cli.bugfix_pipeline_tick``'s own ``--stage`` requirement).
    """
    if "defect_id" not in payload:
        return "defect_id"
    if "action" not in payload:
        return "action"
    if payload.get("action") != "claim-drained" and "stage" not in payload:
        return "stage"
    return None


def _maybe_tick_consolidation_intake(cwd: str | None) -> None:
    """Fire the pending consolidation-signal tick (slice-04 seam), fail-open (D-8).

    A ``.nwave/loop-tick-consolidation-signal.json`` request's absence is a
    safe no-op. A known ``feature_id`` missing a domain-required field
    (``signal_type`` / ``signal_key``) is ledger-attested
    (``ConsolidationSignalTickAttemptFailed``, reusing
    ``append_bugfix_pipeline_event`` -- the SAME shared pipeline write
    surface slice-04's intake reuses for its success path). No derivable
    ``feature_id``, or any other unexpected error, degrades to a labeled
    stderr diagnostic only.
    """
    filename = _LOOP_TICK_CONSOLIDATION_SIGNAL_FILENAME
    try:
        payload = _read_loop_tick_request(cwd, filename)
        if payload is None:
            return
        feature_id = _loop_tick_feature_id(payload)
        now = datetime.now(timezone.utc)
        ledger = _build_loop_tick_ledger(feature_id, cwd)

        missing = next(
            (f for f in ("signal_type", "signal_key") if f not in payload), None
        )
        if missing is not None:
            signal_type = payload.get("signal_type") or "<unknown>"
            signal_key = payload.get("signal_key") or "<unknown>"
            ledger.append_bugfix_pipeline_event(
                "ConsolidationSignalTickAttemptFailed",
                defect_id=f"consolidation-{signal_type}-{signal_key}",
                timestamp=format_iso_utc(now),
                reason=f"missing field: {missing}",
                feature_id=feature_id,
            )
            return

        from des.domain.consolidation_queue_intake import intake_signal

        intake_signal(
            ledger=ledger,
            feature_id=feature_id,
            signal_type=payload["signal_type"],
            signal_key=payload["signal_key"],
            now=now,
        )
    except Exception as e:
        sys.stderr.write(f"[nwave] {filename} loop-tick error (fail-open): {e}\n")


def handle_session_start(host_provenance: str | None = None) -> int:
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
    envelope_defect: str | None = None
    try:
        # `_parse_cwd` ALREADY classifies every malformed-envelope class and
        # says so in its docstring. Re-deriving that classification inline
        # would be a second answer to one question -- the long-locality
        # coupling this lane exists to remove -- so this reads the existing
        # authority instead of restating it.
        session_cwd = str(_parse_cwd(raw_stdin))
    except ValueError as exc:
        envelope_defect = str(exc)

    # A MALFORMED ENVELOPE MUST DEGRADE LOUD, and that is independent of what
    # workflow policy decides. Removing classic legitimately removed the SILENT
    # PRIOR-USE ADOPTION that used to live here -- but that same call was also
    # the only caller of `_parse_cwd`, so deleting it wholesale made "the hook
    # could not read its input" indistinguishable from "the hook read a valid
    # plain directory and correctly did nothing". Both produced zero bytes.
    # That is the could-not-verify collapsed into nothing-to-do, and it stays
    # fixed here rather than travelling with the adoption behaviour that was
    # rightly deleted.
    if envelope_defect is not None:
        sys.stderr.write(
            f"[nwave] session-start envelope unreadable (fail-open): "
            f"{envelope_defect}. No project-specific guidance is emitted for "
            f"this session; the session itself is never blocked.\n"
        )

    # Every trigger below APPENDS its text to this accumulator instead of
    # printing its own JSON line -- see the module docstring. At most one
    # combined JSON object is printed for this whole invocation, always in
    # the wrapped `hookSpecificOutput` form (never the bare
    # `{"additionalContext": ...}` form current Claude Code drops).
    additional_context_parts: list[str] = []
    system_message: str | None = None

    # Workflow policy is the first project-specific authority at SessionStart.
    # Prior-use evidence never authorises mutation or silent mode adoption.
    try:
        guidance = _workflow_mode_session_guidance(session_cwd)
        if guidance:
            additional_context_parts.append(guidance)
    except Exception:
        # WHAT: workflow-mode guidance lookup failed (e.g. unreadable
        # config, malformed mode file).
        # WHY: SessionStart hooks are fail-open by design -- a guidance
        # failure must never block the session itself.
        # HOW: safe to continue -- no guidance is appended for this
        # session, later contributors still run.
        pass

    from des.adapters.driven.config.des_config import DESConfig

    des_config = DESConfig()

    # Early phase: apply any pending deferred self-update BEFORE housekeeping
    # and update-check. A just-upgraded session must not run update-check with
    # a stale current_version comparison.
    _apply_pending_update_if_any(des_config, _get_local_version())

    try:
        _run_housekeeping(des_config)
    except Exception:
        # WHAT: housekeeping run raised (should be rare -- HousekeepingService
        # already fail-isolates its own sub-tasks).
        # WHY/HOW: same SessionStart fail-open rationale as the guidance
        # guard above -- never block the session; continue to the
        # update-check below.
        pass

    try:
        service = _build_update_check_service(des_config)
        result = service.check_for_updates()

        from des.application.update_check_service import UpdateStatus

        if result.status == UpdateStatus.UPDATE_AVAILABLE:
            local_version = _get_local_version()
            latest_version = result.latest or ""
            system_message = _build_visible_message(local_version, latest_version)
            additional_context_parts.append(
                _build_update_message(local_version, latest_version, result.changelog)
            )

    except Exception:
        # WHAT: update-check (network/version-metadata lookup) failed.
        # WHY/HOW: same SessionStart fail-open rationale -- a network or
        # metadata error must never block the session; continue to the
        # substrate-probe advisory below.
        pass

    # The substrate-probe advisory is a plain one-line human-readable string,
    # not JSON -- printed on its own line by design (see module docstring),
    # never folded into the additionalContext accumulator below.
    try:
        advisory = run_probe()
        if advisory:
            print(advisory, end="")
    except Exception:
        # WHAT: substrate probe failed (environment inspection error).
        # WHY/HOW: same SessionStart fail-open rationale -- an advisory
        # probe failure must never block the session; continue to the
        # gate-affordance nudge below.
        pass

    # WS-17-A / GDP-2: proactive gate-affordance nudge -- surfaces the
    # gate -> expectation -> producing-tool pointer BEFORE any gate fires,
    # when an active feature-delta exists under the session cwd. Fail-open.
    try:
        nudge = build_gate_affordance_nudge(session_cwd)
        if nudge:
            additional_context_parts.append(nudge)
    except Exception:
        # WHAT: gate-affordance nudge build failed (e.g. unreadable
        # feature-delta under session_cwd).
        # WHY: explicitly documented "Fail-open" (WS-17-A / GDP-2 comment
        # above).
        # HOW: safe to continue -- no nudge is appended for this session.
        pass

    _emit_codex_continued_work_opportunity(session_cwd, host_provenance)

    # D6 / M5: the PRIMARY hook-version skew detector. Mechanically fired every
    # session start -- catches skew even when the orchestrator skips the
    # prose-invoked /nw-deliver phase-entry diagnostic. Scoped to atdd_pure
    # projects (ADR-030 D6); fail-open.
    skew_finding = _emit_hook_version_skew_finding(session_cwd)
    if skew_finding:
        additional_context_parts.append(skew_finding)

    # orchestrator-affordance-injection (slice-01): load the shipped
    # spine-discipline + producing-tool affordance from text assets and
    # inject it as additionalContext. Additive to the update-notice and the
    # gate-affordance nudge above; fail-open. Gated on
    # `_session_cwd_is_atdd_pure` (ADR-030 D6 pattern, mirrored from the skew
    # detector above) -- a non-atdd_pure / non-nWave cwd must see zero
    # spine-teaching noise.
    try:
        if _session_cwd_is_atdd_pure(session_cwd):
            affordance = load_orchestrator_affordance(
                _ORCHESTRATOR_AFFORDANCE_ASSETS_DIR
            )
            if affordance:
                additional_context_parts.append(affordance)
    except Exception:
        # WHAT: orchestrator-affordance asset load failed (e.g. missing/
        # unreadable text asset under _ORCHESTRATOR_AFFORDANCE_ASSETS_DIR).
        # WHY: explicitly documented "fail-open" (comment above).
        # HOW: safe to continue -- no affordance text is appended; the
        # combined JSON payload below still emits whatever else was
        # collected.
        pass

    # ONE combined JSON payload for the whole invocation -- every contributor
    # above appended to `additional_context_parts` / set `system_message`
    # instead of printing independently, so this is the ONLY
    # `print(json.dumps(...))` call in this function.
    if additional_context_parts or system_message:
        output: dict[str, object] = {}
        if system_message:
            output["systemMessage"] = system_message
        if additional_context_parts:
            output["hookSpecificOutput"] = {
                "hookEventName": "SessionStart",
                "additionalContext": _ORCHESTRATOR_AFFORDANCE_SEPARATOR.join(
                    additional_context_parts
                ),
            }
        print(json.dumps(output))

    # slice-05 (autonomous-consolidation-and-bugfix-loops, OQ-3/DA-13): fire
    # every pending autonomous-loop tick left from a prior iteration. Each
    # wrapper is independently fail-open (its own internal try/except) so one
    # tick's exception never blocks the other two or any trigger above.
    _maybe_tick_work_exhausted(session_cwd)
    _maybe_tick_bugfix_pipeline(session_cwd)
    _maybe_tick_consolidation_intake(session_cwd)

    return 0
