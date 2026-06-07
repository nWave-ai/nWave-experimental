"""SSOT for resolving ``workflow.mode`` from a project's ``.nwave/config.yaml``.

Resolves whether a project runs the ``atdd_pure`` or ``classic`` DELIVER spine
by reading and parsing ``{project_dir}/.nwave/config.yaml`` with a stdlib-only
parser (the standalone DES bundle must stay PyYAML-free).

This is application-layer logic -- it reads a config file from the filesystem --
so it lives above the domain but below the CLI. The CLI driving ports
(``init_log``, ``verify_deliver_integrity``) and the hook adapter
(``session_start_handler``) all import these helpers from here. They previously
lived in ``des.cli.init_log`` and were imported DOWNWARD by the adapter,
inverting the hexagonal layering (AD-05). The CLI may depend on the application
layer; the reverse is illegal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


ATDD_PURE_MODE = "atdd_pure"
CLASSIC_MODE = "classic"


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
    on PyYAML). Handles the simple two-level `workflow:` -> `mode:` nesting
    written by scripts/automation/atdd_pure_falsifier_gate.py, tolerating
    indentation, blank lines, comments, and quoted/unquoted values.

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


def resolve_workflow_mode(project_dir: Path) -> str:
    """SSOT resolver for `workflow.mode` (DDD-5/6/7, slice-03 consolidation).

    The ONE canonical mode resolver every driving port reads through. Resolves
    `workflow.mode` from {project_dir}/.nwave/config.yaml with a stdlib-only
    parser (the standalone DES bundle stays PyYAML-free).

    Absent config file or absent key -> `atdd_pure` (DDD-7: the canonical
    absent-key default). An unconfigured project IS an atdd_pure spine project;
    classic is the explicit-only fallback. This dissolves #65 -- on an
    unconfigured project every port now resolves the SAME answer (atdd_pure),
    so verify-integrity never hunts for a roadmap.json the active mode never
    wrote, and init-log refuses-as-atdd_pure consistently.

    This replaces the prior two-resolver / two-opposite-default divergence:
    the classic-defaulting `_resolve_workflow_mode` and the atdd_pure-defaulting
    `init_log.resolve_dispatch_mode` are both consolidated here.
    """
    config_path = project_dir / ".nwave" / "config.yaml"
    if not config_path.exists():
        return ATDD_PURE_MODE
    return _parse_workflow_mode(config_path.read_text()) or ATDD_PURE_MODE


def _read_workflow_mode(project_dir: Path) -> str | None:
    """Resolve `workflow.mode`, returning None when the key is absent.

    Raw read distinct from `resolve_workflow_mode`, which collapses an absent
    key to the `atdd_pure` default: `resolve_dispatch_mode` uses this raw read
    so it can emit the `ClassicSpineDeprecated` advisory only on an *explicit*
    classic mode, never on the absent-key default.
    """
    config_path = project_dir / ".nwave" / "config.yaml"
    if not config_path.exists():
        return None
    return _parse_workflow_mode(config_path.read_text())
