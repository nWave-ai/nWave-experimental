"""des.runtime.freshness — the runtime freshness gate (§1).

Fires at the import-time of ``des.cli`` (composition root §1.5): every
unified ``des`` console-script invocation (``des roadmap``, ``des init-log``,
``des <subcommand>``, ...) pays one process-startup probe that the installed
copy of DES is consistent with the source-of-truth it is supposed to enforce.
When the probe REFUSES, the process exits 78 (``EX_CONFIG``) with a
structured JSON event on stderr (§1.7).

Slice-01 scope (per ``feature-delta.md`` §6 sequencing):

* honors ``NWAVE_FRESHNESS=skip`` opt-out (§1.8 + DDD-10) — short-circuit
  ahead of the four-state check, emits ``des.runtime.freshness.skipped``;
* fires the :class:`RepoSourceProbe` for the remaining rows; in slice-01 only
  DEGRADED (no manifest → REFUSE) and state ``A`` (customer install → silent
  PROCEED) are reachable through the ATs.

States ``B`` / ``C`` / ``D`` discrimination + ``verbose`` / ``unrecognised``
opt-out values + DEGRADED corruption sub-kinds land in slice-02 / slice-03.

The module does NOT import from :mod:`des.cli` — no reentrancy hazard
(DDD-12).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from des.ports.driven_ports.freshness_port import FreshnessProbe, FreshnessVerdict


# The concrete probe and its remediation texts are imported AT POINT OF USE, not
# here. This module is imported by `des.cli.__init__`, which runs on every single
# `des <command>` and every hook process -- so a module-scope import of the
# adapter made the whole edge (filesystem, git) part of the cost of starting any
# command. Worse, the probe usually does not even run: in a developer checkout
# the gate auto-skips, so the import was paid for a check that was then skipped.
#
# Measured 2026-07-25: the serial spawn census counted 2781 nested pytest
# invocations at a 279ms floor; anything on this path is multiplied by that.
# Keeping the layering honest and keeping startup cheap turn out to be the same
# edit -- the application-side module now names only its PORT at module scope.


# Exit code 78 = EX_CONFIG (sysexits.h) — configuration error, distinct from
# logic (1) and protocol (2) errors. See §1.7.
_REFUSE_EXIT_CODE = 78

# Env var name + the §1.8 + DDD-10 legal-value set. Anything else → REFUSE as
# DEGRADED (slice-04). The sentinel `__unset__` is a Gherkin-table convention
# for "do not set the var at all"; the actual env-var absence is handled by
# `os.environ.get` returning None and short-circuits ahead of the legal-value
# check below.
_OPT_OUT_ENV_VAR = "NWAVE_FRESHNESS"
_OPT_OUT_SKIP = "skip"
_LEGAL_OPT_OUT_VALUES = frozenset({"skip", "verbose", "enforce", ""})

# Test-only override: when `NWAVE_FRESHNESS_FORCE_GATE=1`, the dev-checkout
# autoskip short-circuit (CWD `.git/` adjacency probe) is BYPASSED so the
# four-state classifier runs end-to-end against the installed-tree probe.
# Required by the installer-side freshness ATs at
# `tests/installer/acceptance/fix-des-self-hosted-gate-sync/`, whose
# customer-scenario subprocess spawns inherit the repo's CWD and would
# otherwise trigger the autoskip regardless of the scenario under test.
# Production code defaults preserved (env var unset → autoskip behaves
# byte-identically). DOES NOT bypass the `NWAVE_FRESHNESS=skip` operator
# opt-out or the legal-values check above — only the autoskip short-circuit.
_FORCE_GATE_ENV_VAR = "NWAVE_FRESHNESS_FORCE_GATE"
_FORCE_GATE_ENABLED = "1"


def _emit_event(payload: dict[str, Any]) -> None:
    """Print one single-line structured JSON event to stderr (§1.9 telemetry)."""
    print(json.dumps(payload), file=sys.stderr)


_REMEDIATION = "python scripts/install/install_nwave.py"


# Reason-keyed remediation overrides (RCA fix-des-silent-config-failure, root
# cause B): the blanket `_REMEDIATION` ("reinstall") is wrong for a DEGRADED
# cause with nothing to reinstall. Keyed off `NO_MANIFEST_REASON` (the SSOT
# text `RepoSourceProbe` returns for the dev-editable-binary-from-non-
# project-cwd topology) so a `FreshnessVerdict` that reproduces this exact
# reason — whether or not it went through `RepoSourceProbe` — still resolves
# to the differentiated fix. Extend this map as more DEGRADED causes gain a
# cause-appropriate remediation; unmapped reasons keep the blanket fallback.
def _reason_remediation_overrides() -> dict[str, str]:
    """The reason->remediation map, built where it is READ rather than at import.

    It was a module-level constant, and building it required importing the
    adapter's texts -- which is what dragged the concrete probe into every
    process that so much as imports a `des.cli` submodule. The map is consumed
    in exactly one place (`_resolve_remediation`), and only on the failure path,
    so paying for it at import time charged every successful command for a
    lookup table that a successful command never reads.
    """
    from des.adapters.driven.freshness.repo_source_probe import (
        NO_MANIFEST_REASON,
        NO_MANIFEST_REMEDIATION,
    )

    return {NO_MANIFEST_REASON: NO_MANIFEST_REMEDIATION}


def _resolve_remediation(verdict: FreshnessVerdict) -> str:
    """Cause-appropriate remediation: probe-supplied > reason-mapped > blanket."""
    if verdict.remediation:
        return verdict.remediation
    return _reason_remediation_overrides().get(verdict.reason, _REMEDIATION)


def _refuse(verdict: FreshnessVerdict) -> None:
    """Emit the structured refusal event + human diagnostic, then exit 78."""
    remediation = _resolve_remediation(verdict)
    _emit_event(
        {
            "event": "des.runtime.freshness.refused",
            "state": verdict.state,
            "reason": verdict.reason,
            "remediation": remediation,
        }
    )
    print(
        f"⚠ freshness check refused — {verdict.reason}. Fix: {remediation}",
        file=sys.stderr,
    )
    sys.exit(_REFUSE_EXIT_CODE)


# Advisory-throttle finding (measured 2026-07-28): the hook adapter fires this
# gate as an IMPORT-TIME side effect on every single hook subprocess (PreToolUse,
# PostToolUse, SubagentStop, SubagentStart, SessionStart — one fresh process per
# Claude Code tool call). In an actively-edited multi-lane repo, `src/des`
# diverges from the shared install within minutes of a reinstall and STAYS
# diverged until the next manual reinstall — nothing auto-clears it. The result:
# ``HEALTH_GATE_INSTALL_FRESHNESS_STALE`` fired 14,378 times over 8 days in this
# project's audit log (measured via `grep -c` over `.nwave/des/logs/audit-*.log`),
# 75/hour on average, and `mcp__tsunami__reads_of` confirms zero production
# readers (only this module and 4 test files touch the symbol). Each individual
# emission is mechanically CORRECT — the installed tree really does differ from
# the live repo tree at that instant — so silencing it outright would hide a real
# condition (GDP-6). What is wrong is the CADENCE: re-announcing an UNCHANGED
# verdict on every hook call defeats "loud" through sheer repetition (habituation
# is silent-wrong-by-volume) and bloats the audit sink with near-duplicate rows
# that add no information a future KPI-1 duration query could use (all of them
# say "still stale", none says "how long" better than the first one did).
#
# Throttle to one emission per (state) per window; a STATE TRANSITION (STALE ->
# fresh, STALE -> CONFIG_DRIFT, a reinstall clearing the drift) is NEVER
# throttled — it always breaks through immediately. This is the GDP-8 arity
# corollary applied to volume: suppress an unchanged repeat, never a change.
# 30 minutes mirrors this repo's existing persona/context reload cadence
# (CLAUDE.md "Mechanism 1"), long enough to cut the measured volume by roughly
# two orders of magnitude, short enough that a stale install is still named
# again well within a single working session.
_DEGRADE_THROTTLE_SECONDS = 1800
_DEGRADE_SENTINEL_FILENAME = "_freshness_degrade_sentinel.json"


def _degrade_sentinel_path() -> Path:
    """Resolve the throttle sentinel next to this project's own audit sink.

    Reuses ``AuditLogPathResolver`` (project-local ``.nwave/des/logs/`` by
    default, honoring ``DES_AUDIT_LOG_DIR``) so the throttle's SCOPE matches the
    audit sink's own scope — per-project, exactly like the records it throttles.
    This also means tests that already redirect ``DES_AUDIT_LOG_DIR`` to a
    ``tmp_path`` get an isolated, empty sentinel for free, with no new env var
    or fixture plumbing required.
    """
    from des.domain.audit_log_path_resolver import AuditLogPathResolver

    return AuditLogPathResolver().resolve() / _DEGRADE_SENTINEL_FILENAME


def _should_emit_degrade(state: str) -> bool:
    """True iff ``state`` merits a fresh degrade-loud emission right now.

    Fail-OPEN (returns True) on a missing sentinel, a corrupt/unreadable one, or
    any parse error — a throttle-machinery bug must never cost the FIRST
    occurrence of a real condition its visibility (GDP-6: degrade-loud, never
    silently-wrong). Only an EXACT, RECENT repeat of the same ``state`` is
    suppressed; a different state (including one never seen before) always
    emits.
    """
    from datetime import datetime, timezone

    path = _degrade_sentinel_path()
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        last_emitted = datetime.fromisoformat(record["last_emitted_iso"])
        elapsed_seconds = (datetime.now(timezone.utc) - last_emitted).total_seconds()
        if record.get("state") == state and elapsed_seconds < _DEGRADE_THROTTLE_SECONDS:
            return False
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        # Absent file (nothing recorded yet), corrupt JSON, missing/malformed
        # key, or an unparsable timestamp all mean "no valid throttle state" —
        # fail open to emitting rather than silently swallowing a first-seen or
        # ambiguous condition.
        pass
    return True


def _record_degrade_emitted(state: str) -> None:
    """Persist ``(state, now)`` so a later call can throttle an unchanged repeat.

    Best-effort: a write failure here must not block the emission that just
    happened, and must not raise — the worst case (sentinel unwritable, e.g. a
    read-only filesystem) is reverting to pre-throttle behavior (every call
    emits again), never silence.
    """
    from datetime import datetime, timezone

    path = _degrade_sentinel_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "state": state,
                    "last_emitted_iso": datetime.now(timezone.utc).isoformat(),
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def _degrade_loud(
    verdict: FreshnessVerdict, *, stderr_event: str, audit_event_name: str
) -> None:
    """Degrade-loud: warn on stderr + persist to the SSOT audit sink, then PROCEED.

    The single degrade-loud path behind both the stale-install (#58, DV-4) and the
    config-drift (SYS-4 / AD-27) verdicts. Dual-emit (DV-5): a LOUD
    ``stderr_event`` on stderr (the operator reads it in-flow) AND a persisted
    record under ``audit_event_name`` in the SSOT audit sink (the single
    ``JsonlAuditLogWriter`` daily log under the ``AuditLogPathResolver`` dir — the
    queryable KPI-1 sink). NEVER exits non-zero — a freshness miss must not brick
    an in-flight session.

    The two callers differ ONLY in their event names: the stderr telemetry string
    and the audit ``EventType`` value. Everything else (state / reason /
    remediation payload, the audit sink) is identical, so both ride one helper.

    Throttled per ``verdict.state`` (see ``_should_emit_degrade``): an unchanged
    repeat within the window is a silent no-op (still PROCEED, just no re-emit);
    a state transition always emits regardless of the window.
    """
    if not _should_emit_degrade(verdict.state):
        return
    _emit_event(
        {
            "event": stderr_event,
            "state": verdict.state,
            "reason": verdict.reason,
            "remediation": _REMEDIATION,
        }
    )
    _persist_audit_record(verdict, audit_event_name=audit_event_name)
    _record_degrade_emitted(verdict.state)


def _warn_stale(verdict: FreshnessVerdict) -> None:
    """Degrade-loud on a stale installed spine (#58): warn + PROCEED (DV-4)."""
    from des.adapters.driven.logging.audit_events import EventType

    _degrade_loud(
        verdict,
        stderr_event="des.runtime.freshness.stale",
        audit_event_name=EventType.HEALTH_GATE_INSTALL_FRESHNESS_STALE.value,
    )


def _warn_config_drift(verdict: FreshnessVerdict) -> None:
    """Degrade-loud on a drifted shipped config asset (SYS-4 / AD-27): warn + PROCEED."""
    from des.adapters.driven.logging.audit_events import EventType

    _degrade_loud(
        verdict,
        stderr_event="des.runtime.freshness.config-drift",
        audit_event_name=EventType.HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT.value,
    )


def _persist_audit_record(verdict: FreshnessVerdict, *, audit_event_name: str) -> None:
    """Append one freshness-degrade record to the SSOT audit sink (DV-5, KPI-1).

    Emits through the existing ``JsonlAuditLogWriter`` — the SINGLE audit sink the
    ``JsonlAuditLogReader``, the KPI-1 query path, and rotation all read
    (``audit-YYYY-MM-DD.log`` under the ``AuditLogPathResolver`` dir, honoring
    ``DES_AUDIT_LOG_DIR``). The caller passes the ``EventType`` value as the
    event-name SSOT (``HEALTH_GATE_INSTALL_FRESHNESS_STALE`` for the stale path,
    ``HEALTH_GATE_INSTALL_FRESHNESS_CONFIG_DRIFT`` for the config-drift path); the
    ``remediation`` business-name rides in ``data`` so the writer surfaces it as a
    top-level KPI-2 field. No second sink, no hardcoded event-name string.
    """
    from datetime import datetime, timezone

    from des.adapters.driven.logging.jsonl_audit_log_writer import JsonlAuditLogWriter
    from des.ports.driven_ports.audit_log_writer import AuditEvent

    event = AuditEvent(
        event_type=audit_event_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
        data={
            "state": verdict.state,
            "reason": verdict.reason,
            "remediation": _REMEDIATION,
        },
    )
    JsonlAuditLogWriter().log_event(event)


def assert_fresh_or_explain(
    probe: FreshnessProbe | None = None,
    *,
    suppress_git_autoskip: bool = False,
) -> None:
    """Run the freshness gate; PROCEED silently, warn-loud on stale, or REFUSE.

    Honors ``NWAVE_FRESHNESS=skip`` ahead of the probe (§1.8) — emits the
    audit-bearing ``des.runtime.freshness.skipped`` event and returns. This is
    the F3 bootstrap-blind closure: without it, every ``uv run python -m
    des.cli.*`` against a repo dev tree without a fresh install would
    deterministically REFUSE.

    ``suppress_git_autoskip`` (DV-2): when True, the ``.git/``-adjacency autoskip
    is bypassed so the content probe RUNS even on a developer checkout. The hook
    hot path passes True — that is the #58 topology (installed-tree drift on a
    project that has ``.git/``) where the coarse autoskip would otherwise neuter
    the gate. The opt-out check above still takes precedence.
    """
    opt_out_value = os.environ.get(_OPT_OUT_ENV_VAR)
    if opt_out_value == _OPT_OUT_SKIP:
        _emit_event(
            {
                "event": "des.runtime.freshness.skipped",
                "reason": f"{_OPT_OUT_ENV_VAR}={_OPT_OUT_SKIP}",
            }
        )
        return
    if opt_out_value is not None and opt_out_value not in _LEGAL_OPT_OUT_VALUES:
        _refuse(
            FreshnessVerdict(
                state="DEGRADED",
                reason=(f"unrecognised {_OPT_OUT_ENV_VAR} value: {opt_out_value!r}"),
            )
        )

    # Developer-checkout auto-skip (friction #16): if invoked from anywhere
    # inside a git checkout (CWD or any ancestor has `.git/`), the operator is
    # in a dev tree and the installed-tree freshness check is structurally
    # irrelevant. Walks parents because subprocess invocations (e.g. carpaccio
    # gate fired by hook) may have CWD different from project root. Emits an
    # audit-bearing `autoskipped` event distinguishable from operator-set
    # `skipped` (NWAVE_FRESHNESS=skip). Customer installs (no `.git/` in any
    # ancestor) preserve fail-closed DEGRADED REFUSE byte-identical.
    #
    # Test-only bypass (friction #12 closure, 2026-05-27): when
    # NWAVE_FRESHNESS_FORCE_GATE=1, skip the autoskip probe entirely and run
    # the four-state classifier. Required by installer-side freshness ATs
    # that exercise the customer-scenario topology via subprocess spawns whose
    # CWD inherits the repo's `.git/` adjacency. Production callers never set
    # this env var; default behavior unchanged.
    if (
        not suppress_git_autoskip
        and os.environ.get(_FORCE_GATE_ENV_VAR) != _FORCE_GATE_ENABLED
    ):
        cwd = Path.cwd()
        while True:
            if (cwd / ".git").exists():  # file (worktree gitdir: pointer) or dir
                _emit_event(
                    {
                        "event": "des.runtime.freshness.autoskipped",
                        "reason": (
                            "developer checkout detected via .git adjacency at "
                            f"{str(cwd)!r}"
                        ),
                    }
                )
                return
            parent = cwd.parent
            if parent == cwd:
                break  # reached filesystem root, no .git/ found
            cwd = parent

    if probe is None:
        # Resolved HERE, past every early return above: an injected probe never
        # needs the concrete one, and a run that auto-skips never reaches this
        # line at all. Importing it at module scope charged both cases for a
        # class neither of them uses.
        from des.adapters.driven.freshness.repo_source_probe import RepoSourceProbe

        probe = RepoSourceProbe()
    verdict = probe.probe()
    if verdict.state in ("DEGRADED", "D"):
        # Degrade-loud contract (feature-delta DISCUSS D1 / DEVOPS DV-2/DV-4,
        # resolving DESIGN OQ#1): "the HOOK degrades LOUD (warns + proceeds, exit
        # 0). It NEVER hard-blocks the session ... The CLI keeps its exit-78
        # REFUSE." The hook path is the `suppress_git_autoskip=True` caller; on a
        # DEGRADED/D verdict it warns + proceeds (never sys.exit) so a bare
        # in-process import of the hook adapter (e.g. during pytest collection of
        # a manifest-less source tree) cannot brick the session. The CLI path
        # (suppress_git_autoskip=False) keeps the fail-closed exit-78 REFUSE
        # byte-identical.
        if suppress_git_autoskip:
            _warn_stale(verdict)
            return
        _refuse(verdict)
    if verdict.state == "STALE":
        _warn_stale(verdict)
        return
    if verdict.state == "CONFIG_DRIFT":
        # SYS-4 / AD-27 degrade-loud (DISCUSS D1 / DEVOPS DV-2/DV-4): the hook
        # path (suppress_git_autoskip=True) warns + proceeds (exit 0) so a stale
        # shipped config asset is named LOUD but never bricks the session. The CLI
        # path keeps the fail-closed exit-78 REFUSE.
        if suppress_git_autoskip:
            _warn_config_drift(verdict)
            return
        _refuse(verdict)
    if verdict.state == "C" and not suppress_git_autoskip:
        # CLI path (AT-02-B): emit a developer-fresh structured event so the
        # installer slice-02 AT can observe state C through stderr. The hook hot
        # path (suppress_git_autoskip=True) stays SILENT on a fresh install —
        # the freshness wiring adds zero noise when the install is current.
        _emit_event(
            {
                "event": "des.runtime.freshness.proceed",
                "state": verdict.state,
                "reason": verdict.reason,
            }
        )


__all__ = ["assert_fresh_or_explain"]
