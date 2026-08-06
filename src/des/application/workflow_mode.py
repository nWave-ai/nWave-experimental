"""SSOT for resolving ``workflow.mode`` from a project's ``.nwave/config.yaml``.

Resolves whether a project runs the ``atdd_pure`` or ``classic`` DELIVER spine
by reading and parsing ``{project_dir}/.nwave/config.yaml`` with a stdlib-only
parser (the standalone DES bundle must stay PyYAML-free).

This is application-layer logic -- it reads a config file from the filesystem --
so it lives above the domain but below the CLI. The CLI driving ports
(``verify_deliver_integrity``) import these helpers from here. They previously
lived in a CLI command module and were imported DOWNWARD by the adapter,
inverting the hexagonal layering (AD-05). The CLI may depend on the application
layer; the reverse is illegal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


ATDD_PURE_MODE = "atdd_pure"
CLASSIC_MODE = "classic"
ACTIVE_MODES: frozenset[str] = frozenset({ATDD_PURE_MODE})

#: Where a project DECLARES its mode -- named in every diagnostic below, because
#: an operator who is told to "repair the project" and not WHERE cannot act.
MODE_DECLARATION_LOCUS = ".nwave/config.yaml (key `workflow.mode`)"

#: The PRODUCING tool for the repair (GDP-4: the HOW invokes the tool, never
#: hand-editing). `--dry-run` previews and writes nothing; `--rollback` undoes a
#: partial conversion.
_CONVERT = "des convert-to-atdd-pure --workspace <project-dir>"

_REFUSAL_DIAGNOSTICS: dict[str, str] = {
    "CLASSIC_MODE_REMOVED": (
        "WHAT: the project declares the retired classic spine. "
        "WHY: classic was removed; copied or quoted configuration does not "
        "restore that authority. "
        f"HOW: run `{_CONVERT} --dry-run` to preview the conversion, then "
        "without --dry-run to apply it (`--rollback` undoes a partial run). "
        f"The declaration being refused lives in {MODE_DECLARATION_LOCUS}."
    ),
    "MODE_UNDECLARED": (
        f"WHAT: {MODE_DECLARATION_LOCUS} exists but declares no mode. "
        "WHY: an absent declaration is ambiguous -- it is NOT read as a "
        "default, because a legacy project and a fresh one look identical here. "
        f"HOW: run `{_CONVERT}` to declare atdd_pure explicitly (`--dry-run` "
        "first to see what it would write)."
    ),
    "MODE_UNSUPPORTED": (
        "WHAT: the requested workflow mode is not one this build executes. "
        "WHY: atdd_pure is the sole active mode; every other value is refused "
        "rather than silently coerced. "
        f"HOW: set `workflow.mode: atdd_pure` in {MODE_DECLARATION_LOCUS} via "
        f"`{_CONVERT}`, which is the tool that owns that edit."
    ),
    "DISPATCH_MODE_UNRESOLVED": (
        "WHAT: the dispatch envelope carries no `workflow_mode=atdd_pure` "
        "marker, or carries a different one. "
        "WHY: a missing carrier never implies a mode -- inferring one is how a "
        "retired spine gets executed by accident. "
        "HOW: GENERATE the envelope with `des dispatch` (the producing tool, "
        "which emits the marker) and pass its output verbatim. Do not "
        "hand-assemble or edit the envelope."
    ),
    "HALTED_UNHEALTHY": (
        "WHAT: the caller supplied falsifier-state UNHEALTHY. "
        "WHY: selection halts on a health breach rather than proceeding on an "
        "unverified falsifier. "
        "HOW: no nWave command inspects this state -- it is supplied BY the "
        "caller (see `--falsifier-state` on `des resolve-workflow-mode`), so "
        "the fix belongs to whatever computed it. Fix the falsifier there, "
        "then retry; do not re-run with the flag omitted to get past this."
    ),
}


def refusal_diagnostic(outcome: str) -> str:
    """The operator-actionable WHAT/WHY/HOW for a refusal outcome.

    Public because refusal surfaces OUTSIDE this module (the subagent-stop hook
    payload) must speak the SAME words: a second copy of the text drifts from
    this one silently, and the operator then gets a different HOW depending on
    which surface refused them.
    """
    return _REFUSAL_DIAGNOSTICS[outcome]


@dataclass(frozen=True)
class WorkflowModeSelection:
    """Closed, read-only result of resolving a workflow request."""

    outcome: str
    effective_mode: str | None
    reason_code: str | None = None
    diagnostic: str = ""

    @property
    def selected(self) -> bool:
        return self.outcome == "SELECTED"


def resolve_workflow_selection(
    project_dir: Path,
    *,
    requested_mode: str | None = None,
    dispatch_marker: str | None = None,
    stop_context_mode: str | None = None,
    classic_attestation: str | None = None,
    dispatch_source: str | None = None,
    require_dispatch_marker: bool = False,
    falsifier_state: str | None = None,
) -> WorkflowModeSelection:
    """Resolve the sole executable mode without repairing or executing it.

    Historical classic signals are classified only to refuse them.  In
    particular, no caller can turn an attestation, source label, or marker
    into an executable mode.
    """
    if falsifier_state == "UNHEALTHY":
        return _refused("HALTED_UNHEALTHY")

    raw_mode = _read_workflow_mode(project_dir)
    classic_signals = (
        raw_mode == CLASSIC_MODE,
        requested_mode == CLASSIC_MODE,
        dispatch_marker is not None and "classic" in dispatch_marker.lower(),
        stop_context_mode == CLASSIC_MODE,
        classic_attestation is not None,
        dispatch_source is not None,
    )
    if any(classic_signals):
        return _refused("CLASSIC_MODE_REMOVED", "MIGRATION_REQUIRED")

    if requested_mode is not None and requested_mode != ATDD_PURE_MODE:
        return _refused("MODE_UNSUPPORTED")
    if raw_mode is not None and raw_mode != ATDD_PURE_MODE:
        return _refused("MODE_UNSUPPORTED")
    if require_dispatch_marker and dispatch_marker is None:
        return _refused("DISPATCH_MODE_UNRESOLVED")
    if dispatch_marker is not None and dispatch_marker != "workflow_mode=atdd_pure":
        return _refused("DISPATCH_MODE_UNRESOLVED")

    config_path = project_dir / ".nwave" / "config.yaml"
    if config_path.exists() and raw_mode is None:
        return _refused("MODE_UNDECLARED")
    return WorkflowModeSelection("SELECTED", ATDD_PURE_MODE)


def _refused(outcome: str, reason_code: str | None = None) -> WorkflowModeSelection:
    """Return a typed, operator-actionable refusal selection."""
    return WorkflowModeSelection(
        outcome=outcome,
        effective_mode=None,
        reason_code=reason_code,
        diagnostic=_REFUSAL_DIAGNOSTICS[outcome],
    )


def _strip_inline_comment(value: str) -> str:
    """Drop a trailing ` # comment` from a YAML scalar (outside quotes)."""
    in_single = in_double = False
    for index, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or value[index - 1].isspace():
                return value[:index]
    return value


def _unquote(value: str) -> str:
    """Strip matching surrounding single or double quotes from a scalar."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_workflow_mode(text: str) -> str | None:
    """Extract `workflow.mode` from a machine-managed `.nwave/config.yaml`.

    Stdlib-only parser (the DES bundle installs standalone and must not depend
    on PyYAML). Handles the simple two-level `workflow:` -> `mode:` nesting of
    a machine-managed `.nwave/config.yaml`, tolerating indentation, blank
    lines, comments, and quoted/unquoted values.

    Returns the mode string, or None if the key is absent.
    """
    inside_workflow = False
    workflow_indent = -1
    for raw_line in text.splitlines():
        without_comment = _strip_inline_comment(raw_line)
        if not without_comment.strip():
            continue
        indent = len(without_comment) - len(without_comment.lstrip())
        stripped = without_comment.strip()
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        if not inside_workflow:
            if key == "workflow" and not value:
                inside_workflow = True
                workflow_indent = indent
            continue

        # Inside the `workflow:` block: a key at or below its indent ends it.
        if indent <= workflow_indent:
            inside_workflow = False
            if key == "workflow" and not value:
                inside_workflow = True
                workflow_indent = indent
            continue
        if key == "mode" and value:
            return _unquote(value)
    return None


def resolve_workflow_mode(project_dir: Path) -> WorkflowModeSelection:
    """Compatibility entry point for the closed, read-only selection algebra.

    Historical callers used this name when it returned a bare executable
    string.  Returning the selection result instead makes it impossible for a
    legacy caller to mistake ``classic`` bytes for authority to run classic.
    """
    return resolve_workflow_selection(project_dir)


def _read_workflow_mode(project_dir: Path) -> str | None:
    """Resolve `workflow.mode`, returning None when the key is absent.

    Raw read distinct from the closed selection result, which preserves the
    difference between a fresh absence and a legacy declaration so the latter
    can be refused without mutation.
    """
    config_path = project_dir / ".nwave" / "config.yaml"
    if not config_path.exists():
        return None
    return _parse_workflow_mode(config_path.read_text())
