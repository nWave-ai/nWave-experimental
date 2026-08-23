"""ConfigSsotCheck -- reports the merged effective config (ADR-CFG-001 Slice 2).

Thin doctor shell around ``DESConfig.effective_config()`` (the I/O boundary
that reuses the pure ``config_merge.merge_config`` law over the two real
``.nwave/config.json`` tiers -- global ``context.home_dir`` and per-repo
``context.project_root``). Never re-derives the cascade: this module only
formats the already-resolved effective values and distinguishes a fully
migrated tree (unified ``config.json`` present at either tier) from a tree
still carrying the three legacy scattered files (``global-config.json``,
``des-config.json``, ``local-config.json``) with no unified file at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.adapters.driven.config.des_config import DESConfig
from nwave_ai.common.check_result import CheckResult


if TYPE_CHECKING:
    from pathlib import Path

    from nwave_ai.doctor.context import DoctorContext


def _legacy_config_paths(context: DoctorContext) -> tuple[Path, ...]:
    return (
        context.home_dir / ".nwave" / "global-config.json",
        context.project_root / ".nwave" / "des-config.json",
        context.project_root / ".nwave" / "local-config.json",
    )


def _unified_config_paths(context: DoctorContext) -> tuple[Path, ...]:
    return (
        context.home_dir / ".nwave" / "config.json",
        context.project_root / ".nwave" / "config.json",
    )


class ConfigSsotCheck:
    """Surface the merged config and flag an un-migrated legacy tree."""

    name: str = "config_ssot"
    description: str = "Unified config.json cascade (ADR-CFG-001 Slice 2)"

    def run(self, context: DoctorContext) -> CheckResult:
        """Report the effective enabled/verbosity/attribution values.

        Passes whenever the unified ``config.json`` cascade resolves --
        including the fresh-install branch where both tiers are absent and
        ``merge_config``'s own DEFAULT values apply (never raises). Fails
        only when the tree still carries the three legacy scattered files
        (``global-config.json`` / ``des-config.json`` / ``local-config.json``)
        with NO unified ``config.json`` anywhere -- the not-yet-migrated
        state -- so the row is sensitive to which files are actually present,
        not merely to "some config file exists".
        """
        global_config_path = context.home_dir / ".nwave" / "config.json"
        config = DESConfig(
            cwd=context.project_root, global_config_path=global_config_path
        )
        effective = config.effective_config()

        legacy_present = any(p.exists() for p in _legacy_config_paths(context))
        unified_present = any(p.exists() for p in _unified_config_paths(context))

        if legacy_present and not unified_present:
            return CheckResult(
                passed=False,
                error_code="CONFIG_NOT_MIGRATED",
                message=(
                    "Legacy scattered config files (global-config.json / "
                    "des-config.json / local-config.json) found, no unified "
                    "config.json -- effective (defaults applied): "
                    f"enabled={effective['enabled']}, "
                    f"verbosity={effective['verbosity']!r}, "
                    f"attribution={effective['attribution']}"
                ),
                remediation=(
                    "Create ~/.nwave/config.json (and optionally .nwave/"
                    "config.json in this repo) with "
                    '{"schema-version": "1", "verbosity": ..., '
                    '"attribution": ..., "enabled": ...} -- the unified '
                    "config.json cascade supersedes the three legacy files."
                ),
            )

        return CheckResult(
            passed=True,
            error_code=None,
            message=(
                f"Effective config: enabled={effective['enabled']}, "
                f"verbosity={effective['verbosity']!r}, "
                f"attribution={effective['attribution']}"
            ),
            remediation=None,
        )
