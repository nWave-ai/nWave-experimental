"""Centralized error code registry for all nWave lifecycle stages.

Every error code follows the format NW-{S}{NNN} where:
- S = single-letter stage identifier (I=install, H=hook, B=build, P=plugin)
- NNN = 3-digit number within the stage

Provides lookup by code, by stage, and by category.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCategory(str, Enum):
    """Classification of error types across all stages."""

    ENVIRONMENT = "ENVIRONMENT"
    DEPENDENCY = "DEPENDENCY"
    VALIDATION = "VALIDATION"
    PERMISSION = "PERMISSION"
    TEMPLATE = "TEMPLATE"
    IO = "IO"
    DISPATCH = "DISPATCH"
    INTERNAL = "INTERNAL"
    CONFIG = "CONFIG"


@dataclass(frozen=True)
class NWError:
    """Classified error with recovery guidance.

    Attributes:
        code: Error code in NW-{S}{NNN} format.
        category: Error classification from ErrorCategory.
        stage: Lifecycle stage (install, hook, build, plugin).
        message: Human-readable error description.
        recovery: Actionable recovery suggestion.
    """

    code: str
    category: ErrorCategory
    stage: str
    message: str
    recovery: str


# ---------------------------------------------------------------------------
# Registry: canonical error definitions for all 4 lifecycle stages
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, NWError] = {}


def _register(*errors: NWError) -> None:
    for error in errors:
        _REGISTRY[error.code] = error


# -- Installation Errors (NW-I) --------------------------------------------

_register(
    NWError(
        code="NW-I001",
        category=ErrorCategory.ENVIRONMENT,
        stage="install",
        message="No virtual environment detected",
        recovery="Create and activate a venv: python -m venv .venv && source .venv/bin/activate",
    ),
    NWError(
        code="NW-I002",
        category=ErrorCategory.ENVIRONMENT,
        stage="install",
        message="Pipenv not available",
        recovery="Install pipenv: pipx install pipenv",
    ),
    NWError(
        code="NW-I003",
        category=ErrorCategory.DEPENDENCY,
        stage="install",
        message="Required module missing",
        recovery="Install missing dependency: pipenv install {module}",
    ),
    NWError(
        code="NW-I010",
        category=ErrorCategory.IO,
        stage="install",
        message="Agent source directory not found",
        recovery="Verify nWave/agents/ exists in project root",
    ),
    NWError(
        code="NW-I011",
        category=ErrorCategory.IO,
        stage="install",
        message="Agent copy failed",
        recovery="Check file permissions on ~/.claude/agents/nw/",
    ),
    NWError(
        code="NW-I050",
        category=ErrorCategory.IO,
        stage="install",
        message="DES module source not found",
        recovery="Verify src/des/ exists",
    ),
    NWError(
        code="NW-I080",
        category=ErrorCategory.VALIDATION,
        stage="install",
        message="Post-install verification failed",
        recovery="Run nwave-ai install again. If persists, file issue.",
    ),
    NWError(
        code="NW-I090",
        category=ErrorCategory.IO,
        stage="install",
        message="Backup creation failed",
        recovery="Check disk space and permissions on ~/.claude/backups/",
    ),
)

# -- Hook Execution Errors (NW-H) ------------------------------------------

_register(
    NWError(
        code="NW-H001",
        category=ErrorCategory.DISPATCH,
        stage="hook",
        message="Unknown command argument",
        recovery="Check hook configuration in ~/.claude/settings.json",
    ),
    NWError(
        code="NW-H002",
        category=ErrorCategory.DISPATCH,
        stage="hook",
        message="Missing command argument",
        recovery="Verify hook command string includes action suffix",
    ),
    NWError(
        code="NW-H010",
        category=ErrorCategory.VALIDATION,
        stage="hook",
        message="Prompt template validation failed",
        recovery="Regenerate step file, check template sections",
    ),
    NWError(
        code="NW-H011",
        category=ErrorCategory.VALIDATION,
        stage="hook",
        message="DES markers incomplete",
        recovery="Ensure markers present: DES-VALIDATION, DES-PROJECT-ID, DES-STEP-ID",
    ),
    NWError(
        code="NW-H030",
        category=ErrorCategory.PERMISSION,
        stage="hook",
        message="Source write blocked during deliver",
        recovery="Write through DES sub-agent or use des.cli tools",
    ),
    NWError(
        code="NW-H040",
        category=ErrorCategory.TEMPLATE,
        stage="hook",
        message="Template section missing",
        recovery="Check step file for required 9 sections",
    ),
    NWError(
        code="NW-H050",
        category=ErrorCategory.INTERNAL,
        stage="hook",
        message="Unhandled exception in handler",
        recovery="Check nwave-YYYY-MM-DD.jsonl for stack trace",
    ),
    NWError(
        code="NW-H060",
        category=ErrorCategory.CONFIG,
        stage="hook",
        message="Housekeeping failed (non-blocking)",
        recovery="Check .nwave/des-config.json housekeeping settings",
    ),
)

# -- Build Errors (NW-B) ---------------------------------------------------

_register(
    NWError(
        code="NW-B001",
        category=ErrorCategory.IO,
        stage="build",
        message="Source tree missing required directory",
        recovery="Verify nWave/ directory structure is complete",
    ),
    NWError(
        code="NW-B002",
        category=ErrorCategory.IO,
        stage="build",
        message="pyproject.toml not found",
        recovery="Verify project root is correct",
    ),
    NWError(
        code="NW-B041",
        category=ErrorCategory.VALIDATION,
        stage="build",
        message="Import rewrite produced invalid syntax",
        recovery="Check source file for unusual import patterns",
    ),
    NWError(
        code="NW-B060",
        category=ErrorCategory.VALIDATION,
        stage="build",
        message="Hook configuration generation failed",
        recovery="Verify hook_definitions.py is valid",
    ),
    NWError(
        code="NW-B081",
        category=ErrorCategory.VALIDATION,
        stage="build",
        message="Manifest generation failed",
        recovery="Check permissions on output directory",
    ),
)

# -- Plugin Discovery Errors (NW-P) ----------------------------------------

_register(
    NWError(
        code="NW-P001",
        category=ErrorCategory.CONFIG,
        stage="plugin",
        message="CLAUDE_PLUGIN_ROOT not set (expected)",
        recovery="Normal when using glob fallback",
    ),
    NWError(
        code="NW-P002",
        category=ErrorCategory.IO,
        stage="plugin",
        message="Glob discovery found no plugin cache",
        recovery="Reinstall nWave plugin or use CLI install",
    ),
    NWError(
        code="NW-P003",
        category=ErrorCategory.IO,
        stage="plugin",
        message="CLI install path not found",
        recovery="Run nwave-ai install to install framework",
    ),
    NWError(
        code="NW-P004",
        category=ErrorCategory.VALIDATION,
        stage="plugin",
        message="Resolved path missing des/__init__.py",
        recovery="Plugin installation may be corrupted; reinstall",
    ),
    NWError(
        code="NW-P010",
        category=ErrorCategory.INTERNAL,
        stage="plugin",
        message="DES module import failed after resolution",
        recovery="Check Python version (requires 3.10+) and module integrity",
    ),
)


# ---------------------------------------------------------------------------
# Public lookup API
# ---------------------------------------------------------------------------


def get_error(code: str) -> NWError | None:
    """Look up an error by its code.

    Args:
        code: Error code string (e.g., "NW-I001").

    Returns:
        NWError if found, None otherwise.
    """
    return _REGISTRY.get(code)


def get_errors_by_stage(stage: str) -> list[NWError]:
    """Return all errors for a given lifecycle stage.

    Args:
        stage: One of "install", "hook", "build", "plugin".

    Returns:
        List of NWError instances matching the stage.
    """
    return [e for e in _REGISTRY.values() if e.stage == stage]


def get_errors_by_category(category: ErrorCategory) -> list[NWError]:
    """Return all errors of a given category.

    Args:
        category: ErrorCategory enum member.

    Returns:
        List of NWError instances matching the category.
    """
    return [e for e in _REGISTRY.values() if e.category == category]
