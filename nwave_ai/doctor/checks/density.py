"""DensityCheck — surfaces the resolved documentation density and provenance.

Thin doctor shell around the pure `resolve_density()` cascade per D6 + D12:

  1. Reads `~/.nwave/config.json` (driven adapter: real filesystem).
  2. Calls `scripts.shared.density_config.resolve_density()` (pure core).
  3. Formats provenance into a human-readable label and emits a CheckResult.

Provenance label mapping (preserves the exact strings asserted by the
acceptance scenarios AC-3.f / AC-3.g and the cascade Scenario Outline):

  | provenance field          | rendered label                          |
  | ------------------------- | --------------------------------------- |
  | "default"                 | "default (no config)"                   |
  | "explicit_override"       | "explicit override"                     |
  | "rigor.profile=<name>"    | "inherited from rigor.profile=<name>"   |

Hexagonal note: the cascade decision is owned by `resolve_density`. This
module is the doctor adapter that injects a filesystem read and a string
formatter; it never re-implements the cascade.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from nwave_ai.common.check_result import CheckResult
from scripts.shared.density_config import Density, resolve_density
from scripts.shared.install_paths import CONFIG_FILENAME


if TYPE_CHECKING:
    from pathlib import Path

    from nwave_ai.doctor.context import DoctorContext


def _read_global_config(home_dir: Path) -> dict[str, Any]:
    """Return the parsed `~/.nwave/config.json` or an empty dict.

    Pure read at the doctor adapter boundary. Returns {} when the file is
    absent OR when the file is unreadable / not valid JSON, since the doctor
    adapter must remain best-effort: a malformed config should surface as the
    "default" branch rather than crashing the whole doctor pass.
    """
    config_file = home_dir / ".nwave" / CONFIG_FILENAME
    try:
        parsed = json.loads(config_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _format_provenance_label(density: Density) -> str:
    """Render the provenance string per AC-3.f / AC-3.g exact phrasing.

    `provenance` is one of three shapes:
      - "default"
      - "explicit_override"
      - "rigor.profile=<name>"
    """
    provenance = density.provenance
    if provenance == "default":
        return "default (no config)"
    if provenance == "explicit_override":
        return "explicit override"
    if provenance.startswith("rigor.profile="):
        return f"inherited from {provenance}"
    # Defensive fallback: surface the raw provenance verbatim so a future
    # cascade branch is never silently swallowed.
    return provenance


def _format_density_message(density: Density) -> str:
    """Describe the reading surface selected for a completed wave."""
    label = _format_provenance_label(density)
    reading = (
        "local HTML after an applicable completed wave"
        if density.mode == "full"
        else "authoritative documents and handoffs"
    )
    return f"Documentation density: {density.mode} ({label}); {reading}"


class DensityCheck:
    """Validate documentation preferences used at wave entry."""

    name: str = "documentation_density"
    description: str = "Completed-wave documentation preference"

    def run(self, context: DoctorContext) -> CheckResult:
        """Report invalid active preferences before the next wave refuses them."""
        global_config = _read_global_config(context.home_dir)
        try:
            density = resolve_density(global_config)
        except ValueError as exc:
            return CheckResult(
                passed=False,
                error_code="DOCUMENTATION_PREFERENCE_INVALID",
                message=f"Invalid documentation preference: {exc}",
                remediation=(
                    f"Correct documentation or rigor.profile in "
                    f"{context.global_config_path} "
                    "using the reported field and validation error, then retry."
                ),
            )
        return CheckResult(
            passed=True,
            error_code=None,
            message=_format_density_message(density),
            remediation=None,
        )
