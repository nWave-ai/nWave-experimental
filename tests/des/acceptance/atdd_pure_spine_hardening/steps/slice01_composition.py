"""Composition root for slice-01 -- the U1 carpaccio PreToolUse intercept.

slice-01 of F-DES-ATDD-PURE-HOOK-GATES (U1 / ADR-030 D1).

Wires the PRODUCTION U1 intercept:
  * `des.adapters.drivers.hooks.carpaccio_intercept.evaluate_atdd_pure_dispatch`
    -- the pure-ish U1 decision function: parses the dispatch markers, runs the
    M3 positive-recognition classification, the M8 carpaccio-order check against
    the U3 ledger, and the carpaccio CLI invocation, returning an
    `InterceptDecision` (allow / block).
  * `des.adapters.drivers.hooks.pre_tool_use_handler.handle_pre_tool_use` --
    the real PreToolUse hook entry point, driven via JSON stdin for the
    walking-skeleton @wiring_e2e scenario.
  * `des.adapters.driven.logging.at_completion_ledger.AtCompletionLedger` --
    the U3 ledger the M8 order check reads (slice-(N-1) must be verified).

The driving port for the focused scenarios is `evaluate_atdd_pure_dispatch`;
for the walking-skeleton scenario it is `handle_pre_tool_use` driven via the
real Claude Code JSON hook protocol on stdin.

Business logic lives in the production module; step bodies delegate to
`CarpaccioInterceptComposition` methods and never inline logic
(Mandate-12 criterion 3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.carpaccio_intercept import (
    intercept_atdd_pure_dispatch,
)

from .slice01_domain_types import (
    CarpaccioOutcome,
    DispatchShape,
    FeatureId,
    HookVerdict,
    SliceId,
)


_FEATURE_ID = FeatureId("atdd-pure-demo")


def _dispatch_prompt(shape: DispatchShape, slice_id: str) -> str:
    """Render a Task dispatch prompt carrying the marker set for ``shape``."""
    lines = ["<!-- DES-VALIDATION : required -->"]
    if shape is DispatchShape.MODE_LESS:
        lines.append("<!-- DES-MODE : orchestrator -->")
        lines.append("<!-- DES-PROJECT-ID : atdd-pure-demo -->")
        lines.append("<!-- DES-STEP-ID : 01-01 -->")
        return "\n".join(lines) + "\n\nClassic dispatch body.\n"
    lines.append("<!-- DES-MODE : atdd_pure -->")
    if shape is not DispatchShape.PHASE_MISSING:
        lines.append("<!-- DES-PHASE : A_GREEN_ATS -->")
    if shape is not DispatchShape.SLICE_MISSING:
        lines.append(f"<!-- DES-SLICE : {slice_id} -->")
    return "\n".join(lines) + "\n\natdd_pure dispatch body.\n"


@dataclass
class InterceptOutcome:
    """The observable result of a U1 carpaccio intercept evaluation."""

    verdict: HookVerdict
    event: str | None
    carpaccio_invoked: bool


class CarpaccioInterceptComposition:
    """Production-wired composition root for the U1 carpaccio intercept slice.

    The driving port is `evaluate_atdd_pure_dispatch` (focused scenarios) or the
    real `handle_pre_tool_use` hook entry (walking skeleton). The observable
    surface is the intercept verdict, the emitted event name, and whether the
    carpaccio CLI was invoked.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._feature_id = _FEATURE_ID
        self._slice_id = "slice-01"
        self._shape = DispatchShape.ATDD_PURE_VALID
        self._carpaccio_outcome = CarpaccioOutcome.CLEARED
        self._handler_raises = False
        self._ledger = AtCompletionLedger(self._feature_id, project_root)

    # --- dispatch setup ------------------------------------------------------

    def use_dispatch(self, shape: DispatchShape) -> None:
        """The PreToolUse dispatch under test carries the markers for ``shape``."""
        self._shape = shape

    def enter_slice(self, slice_id: SliceId) -> None:
        """The dispatch enters ``slice_id`` (slice-NN)."""
        self._slice_id = str(slice_id)

    def carpaccio_will(self, outcome: CarpaccioOutcome) -> None:
        """The (stubbed) carpaccio CLI clears or rejects the entering slice."""
        self._carpaccio_outcome = outcome

    def predecessor_is_verified(self, slice_id: SliceId) -> None:
        """Record a terminal SliceCommitVerified for ``slice_id`` in the ledger."""
        self._ledger.append_gate_event(
            event="SliceCommitVerified", slice_id=str(slice_id)
        )

    def handler_will_raise(self) -> None:
        """The U1 intercept body raises an internal exception (M1 probe)."""
        self._handler_raises = True

    # --- driving-port invocation: focused scenarios -------------------------

    def evaluate(self) -> InterceptOutcome:
        """Evaluate the U1 intercept via `intercept_atdd_pure_dispatch`."""
        invoked: dict[str, bool] = {"carpaccio": False}

        def carpaccio_runner(feature_id: str, entering_slice: str) -> tuple[int, str]:
            invoked["carpaccio"] = True
            if self._handler_raises:
                raise RuntimeError("injected carpaccio runner failure")
            if self._carpaccio_outcome is CarpaccioOutcome.REJECTED:
                return 45, json.dumps(
                    {"event": "AtReviewNotApproved", "slice_id": entering_slice}
                )
            return 0, json.dumps({"event": "SliceCleared", "slice_id": entering_slice})

        prompt = _dispatch_prompt(self._shape, self._slice_id)
        decision = intercept_atdd_pure_dispatch(
            prompt=prompt,
            feature_id=self._feature_id,
            project_root=self._project_root,
            carpaccio_runner=carpaccio_runner,
            # slice-05 multi-gate prod YAML wires verify-readiness-pre-dispatch
            # ahead of carpaccio; this fixture pre-clears readiness so the
            # focused intercept ATs observe the carpaccio verdict unchanged.
            readiness_runner=lambda _f, _s: (0, ""),
        )
        return InterceptOutcome(
            verdict=(HookVerdict.BLOCKED if decision.is_block else HookVerdict.ALLOWED),
            event=decision.event,
            carpaccio_invoked=invoked["carpaccio"],
        )

    # --- driving-port invocation: walking skeleton (real hook) --------------

    def drive_real_pre_tool_use_hook(self) -> InterceptOutcome:
        """Drive the real PreToolUse hook via the Claude Code JSON stdin protocol.

        This is the genuine @wiring_e2e path: it constructs the exact JSON
        envelope Claude Code sends, feeds it on stdin to the production
        `handle_pre_tool_use`, and reads the block decision off stdout.
        """
        from des.adapters.drivers.hooks.pre_tool_use_handler import (
            handle_pre_tool_use,
        )

        prompt = _dispatch_prompt(self._shape, self._slice_id)
        prompt += f"\n<!-- DES-PROJECT-ROOT : {self._project_root} -->\n"
        hook_input = {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "nw-software-crafter",
                "prompt": prompt,
                "description": "Dispatch crafter into slice-01",
            },
        }
        stdin_data = json.dumps(hook_input)
        with patch("sys.stdin", StringIO(stdin_data)):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                exit_code = handle_pre_tool_use()
                stdout = mock_stdout.getvalue()

        event = None
        if stdout.strip():
            payload = json.loads(stdout)
            event = payload.get("event")
            is_block = payload.get("decision") == "block"
        else:
            is_block = False
        verdict = (
            HookVerdict.BLOCKED
            if (is_block or exit_code != 0)
            else (HookVerdict.ALLOWED)
        )
        return InterceptOutcome(verdict=verdict, event=event, carpaccio_invoked=True)
