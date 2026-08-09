"""AttributionCheck — read-only activation-aware attribution report (AB-9).

DESIGN ADR-CA-007. The check is read-only (Principle 12 pure-read): it reads
``~/.claude/settings.json`` and the activation config via the injected
DoctorContext and reports four diagnostic lines so a user can answer "why did
this commit (not) get the credit?":

  1. is the activation-gated attribution commit hook registered?
  2. is THIS repo activation-resolved active? (reuses the canonical
     ``resolve_activation`` policy over the marker + global mode — no
     re-derivation here, DDD discipline)
  3. is there leftover nWave-managed legacy ``settings.json`` residue?
  4. the deprecated ``includeCoAuthoredBy`` flag, read from its correct
     TOP-LEVEL location (DDD-7 bug fix — it was previously read nested under
     ``attribution``).

It never mutates settings.json.

Three-valued verdict (fix-attribution-trailer-never-applied, P7): the check
observes TWO axes (GDP-8 witness corollary) -- (a) is the hook registered in
settings.json, (b) does the producing-tool resolver (the SAME resolution
``attribute_commit_message`` performs: activation AND ``attribution.enabled``)
now attribute for this repo. AGREED (both axes agree, live or dark) ->
passed=True. DISAGREED (axes disagree) -> passed=False,
``ATTRIBUTION_DISAGREEMENT``, remediation naming the real producing-tool
command ``nwave-ai attribution on``. COULD_NOT_VERIFY (the resolution itself
raises) -> passed=False, ``ATTRIBUTION_UNVERIFIABLE`` -- its own third state
reaching the aggregate rather than being silently folded into AGREED.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from nwave_ai.common.check_result import CheckResult


if TYPE_CHECKING:
    from pathlib import Path

    from nwave_ai.doctor.context import DoctorContext


_LEGACY_RUNTIME = "nwave_attribution_hook.py"

# Current registration shape (ADR-CA-006/007): the universal PreToolUse
# adapter observes attribution.enabled at invocation time -- there is no
# dedicated attribution hook entry anymore. `_HOOK_MARKER` below matched the
# retired independent `pre-commit-attribution` action
# (scripts/install/attribution_utils.py:_attribution_hook_command, tombstoned
# as the cleanup-only removal baseline); real installs have never written
# that shape since ADR-CA-006. `_hook_registered` must key on the module +
# action actually installed by scripts/install/plugins/des_plugin.py
# (HOOK_COMMAND_TEMPLATE): "...claude_code_hook_adapter pre-tool-use".
_HOOK_MODULE = "des.adapters.drivers.hooks.claude_code_hook_adapter"
_HOOK_ACTION = "pre-tool-use"


class AttributionCheck:
    """Read-only diagnostic: 4-line activation-aware attribution report (AB-9)."""

    name: str = "attribution"
    description: str = (
        "Reports hook registration, this repo's activation state, legacy "
        "settings residue, and the deprecated includeCoAuthoredBy state"
    )

    def run(self, context: DoctorContext) -> CheckResult:
        """Return a read-only attribution diagnostic — never mutates.

        See the module docstring for the three-valued AGREED / DISAGREED /
        COULD_NOT_VERIFY verdict this returns.
        """
        settings = self._read_settings(context.settings_path)

        hook_present = self._hook_registered(settings)
        hook_line = (
            f"attribution commit hook: "
            f"{'registered' if hook_present else 'not registered'}"
        )

        active, attribution_enabled, resolution_error = self._resolve_attribution_state(
            context
        )
        activation_line = f"this repo activation: {'active' if active else 'inactive'}"

        residue_present = self._legacy_residue_present(context, settings)
        residue_line = (
            f"legacy settings residue: {'present' if residue_present else 'absent'}"
        )

        deprecated = settings.get("includeCoAuthoredBy")
        deprecated_state = "unset" if deprecated is None else str(deprecated).lower()
        deprecated_line = f"deprecated includeCoAuthoredBy: {deprecated_state}"

        message = "\n".join([hook_line, activation_line, residue_line, deprecated_line])

        if resolution_error is not None:
            return CheckResult(
                passed=False,
                error_code="ATTRIBUTION_UNVERIFIABLE",
                message=message,
                remediation=(
                    "Could not resolve the attribution configuration "
                    f"({resolution_error}). Fix the underlying config read, "
                    "then re-run `nwave-ai doctor`."
                ),
            )

        would_attribute = active and attribution_enabled
        if hook_present == would_attribute:
            return CheckResult(
                passed=True,
                error_code=None,
                message=message,
                remediation=None,
            )

        return CheckResult(
            passed=False,
            error_code="ATTRIBUTION_DISAGREEMENT",
            message=message,
            remediation=(
                "The attribution commit hook registration and the resolved "
                "attribution state disagree. Run `nwave-ai attribution on` "
                "to re-register the hook and align both."
            ),
        )

    @staticmethod
    def _read_settings(settings_path: Path) -> dict:
        if not settings_path.exists():
            return {}
        try:
            return json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _hook_registered(settings: dict) -> bool:
        entries = settings.get("hooks", {}).get("PreToolUse", [])
        return any(
            _HOOK_MODULE in (command := hook.get("command", ""))
            and _HOOK_ACTION in command
            for entry in entries
            if isinstance(entry, dict)
            for hook in entry.get("hooks", [])
            if isinstance(hook, dict)
        )

    @staticmethod
    def _resolve_attribution_state(
        context: DoctorContext,
    ) -> tuple[bool, bool, Exception | None]:
        """Resolve ``(active, attribution_enabled, resolution_error)``.

        Reuses the SAME resolution
        ``des.application.commit_message_attribution.attribute_commit_message``
        performs (the canonical ``resolve_activation`` policy over the two
        scalars ``DESConfig`` exposes -- marker ``enabled_for_repo`` + global
        ``activation.mode`` -- AND ``DESConfig.attribution_enabled``) — the
        policy is NOT re-derived here.

        On a config-read exception, returns ``(False, False, exc)`` rather
        than raising: ``active=False`` lets the diagnostic message still fail
        OPEN to "inactive" (never more optimistic than the enforcement gate),
        while the returned exception lets the caller surface its own
        COULD_NOT_VERIFY third state instead of silently folding the failure
        into AGREED.
        """
        try:
            from des.adapters.driven.config.des_config import DESConfig
            from des.domain.activation_policy import resolve_activation

            config = DESConfig(
                cwd=context.project_root,
                global_config_path=context.global_config_path,
            )
            active = resolve_activation(config.enabled_for_repo, config.activation_mode)
            return active, config.attribution_enabled, None
        except Exception as exc:
            return False, False, exc

    @classmethod
    def _legacy_residue_present(cls, context: DoctorContext, settings: dict) -> bool:
        """Report leftover nWave-managed legacy residue.

        Residue is the ``settings.json attribution.commit`` block still set AND
        recognised as nWave-managed (its value matches the global-config
        ``last_written_value`` baseline that 01-03's migration cleans), or a
        legacy on-disk attribution runtime hook.
        """
        attribution = settings.get("attribution") or {}
        commit = attribution.get("commit")
        if commit and commit == cls._managed_baseline(context):
            return True
        return cls._legacy_hook_present(context.home_dir)

    @staticmethod
    def _managed_baseline(context: DoctorContext) -> str | None:
        try:
            data = json.loads(context.global_config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return (data.get("attribution") or {}).get("last_written_value")

    @staticmethod
    def _legacy_hook_present(home_dir: Path) -> bool:
        return (home_dir / ".nwave" / "hooks" / _LEGACY_RUNTIME).exists()
