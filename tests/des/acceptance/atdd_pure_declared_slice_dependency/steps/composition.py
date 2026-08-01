"""Composition root for slice-01 of `slice-dependency-declared` (mikado D94).

Wires the PRODUCTION M8 carpaccio-order check via the SAME driving port
`atdd_pure_spine_hardening` slice-01 already proved:
`des.adapters.drivers.hooks.carpaccio_intercept.intercept_atdd_pure_dispatch`
(focused scenarios) and the real `handle_pre_tool_use` PreToolUse hook entry,
driven via the Claude Code JSON stdin protocol (the @walking_skeleton
scenario). Business logic lives in production code; step bodies delegate to
`DeclaredSliceDependencyComposition` methods and never inline logic
(Mandate-12 criterion 3).

Placement precedent (one-line justification): this slice wires the M8 order
check inside `carpaccio_intercept.py` (an `adapters/drivers/hooks` module),
driven IN-PROCESS through its own public entry points -- the identical
driving port `tests/des/acceptance/atdd_pure_spine_hardening/steps/
slice01_composition.py` already exercises for the SAME production function.
This suite therefore sits under `tests/des/acceptance/`, mirroring that
sibling, rather than `tests/scripts/cli/` -- the latter precedent is for a
`des.cli` module driven as a `python -m des.cli.<module>` subprocess, which M8
is not (it is a hook adapter with no CLI entry point of its own).

RED contract: `resolve_predecessor_slice` / `DeclaredDependencyMalformed` /
`declared_dependency_targets` do not exist yet on this branch, and
`_carpaccio_order_block` still computes the predecessor as bare
`slice-(N-1)` arithmetic, ignoring any `depends-on` annotation entirely.
Every scenario that exercises a DECLARED or MALFORMED dependency therefore
fails RED for a real assertion (the observed verdict/event/reason does not
match the declared-dependency contract this feature adds), never for an
import or collection error. The scenarios that only exercise the SILENT /
degraded-read fallback (CT-1 + CT-7) pin BYTE-IDENTICAL pre-feature
behaviour and are allowed to already be GREEN today -- the same
"non-regression guards, correctly green now" shape the sibling
`atdd_pure_validate_feature_delta_slice_dependency_justification` composition
already documents for an incremental verdict-set extension. No production
scaffold file is required: every scenario drives the STABLE, already-shipped
`intercept_atdd_pure_dispatch` / `handle_pre_tool_use` entry points -- the
absent behaviour surfaces as a wrong OBSERVED verdict, not a missing import
(the in-process active-RED pattern, P1-P4, applied with zero new module).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.carpaccio_intercept import (
    intercept_atdd_pure_dispatch,
)

from .domain_types import FeatureId, HookVerdict, PlanShape, SliceId


_FEATURE_ID = FeatureId("declared-dependency-demo")

# The five-row baseline every fixture starts from -- slice-01..slice-05,
# matching this feature's OWN shipped Slice Plan shape (5 rows), so a
# forward-reference (CT-6) or typo target (CT-5) has real rows to be
# absent-from / ahead-of.
_BASELINE_SLICE_IDS: tuple[str, ...] = (
    "slice-01",
    "slice-02",
    "slice-03",
    "slice-04",
    "slice-05",
)


class _PlanMode(str, Enum):
    """The shape of the feature-delta.md fixture written before invocation."""

    NORMAL = "normal"
    NO_FILE = "no_file"
    NO_SLICE_PLAN_SECTION = "no_slice_plan_section"
    MALFORMED_TABLE = "malformed_table"
    PATH_IS_DIRECTORY = "path_is_directory"


def _dispatch_prompt(slice_id: str) -> str:
    """Render a valid atdd_pure A_GREEN_ATS dispatch prompt entering `slice_id`."""
    lines = [
        "<!-- DES-VALIDATION : required -->",
        "<!-- DES-MODE : atdd_pure -->",
        "<!-- DES-PHASE : A_GREEN_ATS -->",
        f"<!-- DES-SLICE : {slice_id} -->",
    ]
    return "\n".join(lines) + "\n\natdd_pure dispatch body.\n"


@dataclass
class InterceptOutcome:
    """The observable result of one M8 order-check evaluation.

    `reason`/`how` carry the block's human-facing text (CT-2b pins that a
    silent-row block names BOTH the rebuild remedy and the declare-depends-on
    alternative).
    """

    verdict: HookVerdict
    event: str | None
    reason: str | None
    how: str | None


@dataclass
class DeclaredSliceDependencyComposition:
    """Production-wired composition root for slice-01's declared-dependency ATs.

    The driving port is `intercept_atdd_pure_dispatch` for focused scenarios
    and the real `handle_pre_tool_use` hook for the walking skeleton. The
    observable surface is the M8 verdict, the emitted event, and the block's
    reason/how text.
    """

    project_root: Path
    feature_id: FeatureId = field(default=_FEATURE_ID)
    _slice_id: str = field(default="slice-03", init=False)
    _annotations: dict[str, str] = field(default_factory=dict, init=False)
    _omitted_rows: set[str] = field(default_factory=set, init=False)
    _plan_mode: _PlanMode = field(default=_PlanMode.NORMAL, init=False)

    def __post_init__(self) -> None:
        self._ledger = AtCompletionLedger(self.feature_id, self.project_root)

    # --- paths -----------------------------------------------------------

    @property
    def _feature_delta_path(self) -> Path:
        return (
            self.project_root
            / "docs"
            / "feature"
            / self.feature_id
            / "feature-delta.md"
        )

    # --- Given: the ledger -------------------------------------------------

    def mark_verified(self, slice_id: SliceId) -> None:
        """Record a terminal SliceCommitVerified for `slice_id` in the ledger."""
        self._ledger.append_gate_event(
            event="SliceCommitVerified", slice_id=str(slice_id)
        )

    def mark_unverified(self, slice_id: SliceId) -> None:
        # No setup: absence of a SliceCommitVerified record IS "unverified" --
        # this Given names the precondition the chained scenarios share
        # (Pillar 2), mirroring the sibling `given_feature_with_ledger` no-op.
        pass

    # --- Given: the entering dispatch --------------------------------------

    def enter_slice(self, slice_id: SliceId) -> None:
        """The dispatch under test enters `slice_id` (slice-NN)."""
        self._slice_id = str(slice_id)

    # --- Given: the Slice Plan fixture --------------------------------------

    def declare_dependency(self, slice_id: SliceId, annotation: str) -> None:
        """`slice_id`'s own Slice-Plan row carries `annotation` verbatim."""
        self._annotations[str(slice_id)] = annotation

    def apply_plan_shape(self, shape: PlanShape) -> None:
        """Apply one of CT-1/CT-7's degraded-read shapes to the fixture.

        `ROW_ABSENT`/`ANNOTATION_EMPTY` act on the CURRENTLY entering slice
        (`enter_slice` must have already run) -- the other shapes are
        document-wide and ignore the entering slice entirely.
        """
        if shape is PlanShape.NO_FILE:
            self._plan_mode = _PlanMode.NO_FILE
        elif shape is PlanShape.NO_SLICE_PLAN_SECTION:
            self._plan_mode = _PlanMode.NO_SLICE_PLAN_SECTION
        elif shape is PlanShape.MALFORMED_TABLE:
            self._plan_mode = _PlanMode.MALFORMED_TABLE
        elif shape is PlanShape.PATH_IS_DIRECTORY:
            self._plan_mode = _PlanMode.PATH_IS_DIRECTORY
        elif shape is PlanShape.ROW_ABSENT:
            self._omitted_rows.add(self._slice_id)
        elif shape is PlanShape.ANNOTATION_EMPTY:
            self._annotations[self._slice_id] = ""

    def _write_plan(self) -> None:
        """Materialise the feature-delta.md fixture per the accumulated state."""
        path = self._feature_delta_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if self._plan_mode is _PlanMode.NO_FILE:
            return
        if self._plan_mode is _PlanMode.PATH_IS_DIRECTORY:
            path.mkdir(parents=True, exist_ok=True)
            return
        if self._plan_mode is _PlanMode.NO_SLICE_PLAN_SECTION:
            path.write_text(
                "# Feature Delta: declared-slice-dependency fixture\n\n"
                "## Wave: DESIGN / [REF] Handoff\n\n"
                "No Slice Plan section anywhere in this document.\n",
                encoding="utf-8",
            )
            return
        if self._plan_mode is _PlanMode.MALFORMED_TABLE:
            path.write_text(
                "# Feature Delta: declared-slice-dependency fixture\n\n"
                "## Wave: DISCUSS / [REF] Slice Plan\n\n"
                "No table follows this heading -- deliberately malformed.\n",
                encoding="utf-8",
            )
            return
        rows = []
        for slice_id in _BASELINE_SLICE_IDS:
            if slice_id in self._omitted_rows:
                continue
            annotation = self._annotations.get(slice_id, "")
            rows.append(
                f"| {slice_id} | Operator ships {slice_id} | pending | "
                f"{annotation} |  |"
            )
        body = (
            "# Feature Delta: declared-slice-dependency fixture\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|-------|-----------------|--------|------------|----------------|\n"
            + "\n".join(rows)
            + "\n"
        )
        path.write_text(body, encoding="utf-8")

    # --- When: driving-port invocation --------------------------------------

    def evaluate(self) -> InterceptOutcome:
        """Evaluate the M8 order check via `intercept_atdd_pure_dispatch`."""
        self._write_plan()
        decision = intercept_atdd_pure_dispatch(
            prompt=_dispatch_prompt(self._slice_id),
            feature_id=self.feature_id,
            project_root=self.project_root,
            carpaccio_runner=lambda feature_id, entering_slice: (
                0,
                json.dumps({"event": "SliceCleared", "slice_id": entering_slice}),
            ),
            readiness_runner=lambda _f, _s: (0, ""),
        )
        return InterceptOutcome(
            verdict=(HookVerdict.BLOCKED if decision.is_block else HookVerdict.ALLOWED),
            event=decision.event,
            reason=decision.reason,
            how=decision.how,
        )

    def drive_real_pre_tool_use_hook(self) -> InterceptOutcome:
        """Drive the real PreToolUse hook via the Claude Code JSON stdin protocol.

        The genuine @walking_skeleton path: constructs the exact JSON envelope
        Claude Code sends, feeds it on stdin to the production
        `handle_pre_tool_use`, and reads the block decision off stdout.
        """
        from des.adapters.drivers.hooks.pre_tool_use_handler import (
            handle_pre_tool_use,
        )

        self._write_plan()
        prompt = _dispatch_prompt(self._slice_id)
        prompt += f"\n<!-- DES-PROJECT-ROOT : {self.project_root} -->\n"
        hook_input = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "nw-software-crafter",
                "prompt": prompt,
                "description": f"Dispatch crafter into {self._slice_id}",
            },
        }
        stdin_data = json.dumps(hook_input)
        with patch("sys.stdin", StringIO(stdin_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = handle_pre_tool_use()
                stdout = mock_stdout.getvalue()

        event = None
        reason = None
        is_block = False
        if stdout.strip():
            payload = json.loads(stdout)
            event = payload.get("event")
            reason = payload.get("reason")
            is_block = payload.get("decision") == "block"
        verdict = (
            HookVerdict.BLOCKED if (is_block or exit_code != 0) else HookVerdict.ALLOWED
        )
        return InterceptOutcome(verdict=verdict, event=event, reason=reason, how=None)
