"""Composition root for the nwave-flow-v2-enforcement slice-07d ATs.

The *only* place the production system is wired for slice-07d. One driving
port (Mandate-13 driving-port-only, Layer 4 wiring): the REAL PreToolUse hook
adapter (``python -m des.adapters.drivers.hooks.claude_code_hook_adapter
pre-tool-use``, hook-protocol stdin JSON, subprocess black box) over a tmp
``project_root``; AT-2 arms the floor first via the REAL prompt-submission
anchor subprocess (slice-04 protocol). The hook adapter is the composition
seat of the NET-NEW fallback branch (DESIGN slice-07d "Composition": reader
``NoWaveActive`` + valid ``markers.declared_wave`` ->
``activation.arm_inferred(...)`` -> proceed as wave-entering in the SAME
pass), so it IS the real entry point for the declared seams.

Observables: hook exit code (0 allow / 2 block) + block reason JSON + the
floor record at the DESIGN-PINNED path ``.nwave/wave-active/active.json``.

State lives on the instance; ``given_/when_/then_`` methods mutate/read it.
Step functions are thin delegations (Mandate-12).

RED-for-right-reason (pre-DELIVER fail-for-right-reason gate): at HEAD the
``DES-WAVE`` marker is an inert HTML comment (``DesMarkers`` has no
``declared_wave``), ``WaveActivationService.arm_inferred`` does not exist and
the adapter has no fallback branch -- an empty floor stays empty and the
declaring dispatch rides the S1 allow path. So:
  * AT-1 -- semantic ``AssertionError``: the dispatch is ALLOWED where the
    same-pass INFERRED gating must BLOCK (unmet preconditions); behind it,
    the floor stays ABSENT where an INFERRED record must be armed.
  * AT-2 -- preservation-GREEN at HEAD: nothing writes INFERRED today, so
    the COMMAND record trivially survives; at TARGET the fallback sees a
    non-empty reader and no-ops (I3) -- the AT pins the no-clobber contract
    END-TO-END through the real path, not just the store unit guarantee.
  * AT-3 (outline x2) -- preservation-GREEN: absent/out-of-vocab declaration
    -> no arm, no record, allow untouched (K2/S1) -- holds at HEAD and MUST
    keep holding once the fallback ships (the vocabulary validation is the
    no-garbage-record guard).
No collection / import error (only test-local types + shipped hook modules).

DESIGN-PINNED CONTRACTS this AT-seed conforms to (feature-delta § slice-07d
code-design -- ONE SSOT shared by the AT-seed and the crafter; no drift):
  * marker: ``<!-- DES-WAVE: <wave> -->`` (the `_WAVE_PATTERN` shape);
    validation at the USE site against ``WAVE_VOCABULARY``
    (``src/des/domain/wave_active.py``) -- out-of-vocab == absent (no arm).
  * INFERRED arm record: ``wave=<declared>``, ``provenance=inferred``,
    ``entry_pending`` false/omitted (self-entry rule: arm and gate-IN happen
    in the SAME PreToolUse pass -- no cross-event channel needed).
  * I3 dominance: INFERRED never clobbers COMMAND (store-enforced; pinned
    here end-to-end through the adapter path).
  * floor: single JSON object at ``.nwave/wave-active/active.json``
    (slice-04 contract + 07c floor v1.1).
  * product preconditions: ``docs/product/`` + four SSOT docs (slice-07
    pinned shape, re-declared per-slice).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from des.adapters.drivers.hooks.hook_router import main as _hook_router_main
from des.adapters.drivers.hooks.user_prompt_submit_handler import (
    handle_user_prompt_submit,
)
from tests.common.in_process_cli import run_hook_in_process

from .domain_types_slice_07d import GateDecision, WaveDeclarationShape


# tests/des/acceptance/nwave_flow_v2_enforcement/steps/composition_slice_07d.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

_FLOOR_FILE_REL = ".nwave/wave-active/active.json"
_PRODUCT_DIR_REL = "docs/product"
# The jobs slot is satisfied by docs/product/jobs.yaml (structured JOB registry),
# NOT jobs.md -- vision/backlog/glossary stay .md.
_REQUIRED_SSOT_DOCS: tuple[str, ...] = (
    "vision.md",
    "backlog.md",
    "glossary.md",
    "jobs.yaml",
)

_DISCUSS_COMMAND_PROMPT = "/nw-discuss continue the feature work"


@dataclass
class InferredFallbackComposition:
    """Drives the INFERRED fallback strand seams for the slice-07d ATs."""

    _project_root: Path | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)

    # ---- given ---------------------------------------------------------------

    def given_no_wave_armed(self, tmp_path: Path) -> None:
        """An empty floor: the submission anchor never fired (observe-only /
        missed write -- the F4 scenario). No floor file is written."""
        self._project_root = tmp_path
        self._activate_project()

    def given_discuss_armed_by_command(self, tmp_path: Path) -> None:
        """Arm the discuss wave through the REAL submission anchor (COMMAND)."""
        self._project_root = tmp_path
        self._activate_project()
        self._run_submission_hook(_DISCUSS_COMMAND_PROMPT)

    def given_preconditions_missing(self) -> None:
        """docs/product absent entirely -- the coarsest unmet entry shape."""
        assert self._project_root is not None
        # Write nothing -> migration-gate unmet.

    def given_preconditions_satisfied(self) -> None:
        """docs/product + the four SSOT docs present (slice-07 pinned shape)."""
        assert self._project_root is not None
        product_dir = self._project_root / _PRODUCT_DIR_REL
        product_dir.mkdir(parents=True, exist_ok=True)
        for doc in _REQUIRED_SSOT_DOCS:
            (product_dir / doc).write_text(f"# {doc}\n", encoding="utf-8")

    # ---- when ------------------------------------------------------------------

    def when_declaring_dispatch_checked(self) -> None:
        """Drive the hook adapter with a DES-marked dispatch declaring discuss."""
        self._decision_action, self._decision_reason = self._run_pre_tool_use_hook(
            self._declaring_dispatch_prompt()
        )

    def when_adhoc_dispatch_checked(self, shape: WaveDeclarationShape) -> None:
        """Drive the hook adapter with an ad-hoc dispatch (no/garbage declaration)."""
        self._decision_action, self._decision_reason = self._run_pre_tool_use_hook(
            self._adhoc_prompt(shape)
        )

    # ---- then ------------------------------------------------------------------

    def then_allowed_greenfield_advisory_same_pass(self) -> None:
        """Self-entry greenfield ADVISORY (slice-05 declass): the arming dispatch
        is ITSELF entry-checked in the same pass and ALLOWED.

        The fallback arms INFERRED enforcement and runs the entry gate in that
        SAME pass (self-entry, F4: closes S2 even when the submission anchor
        never fired). With the product model absent (MIGRATION_UNMET) the entry
        gate now ALLOWS (the slice-05 declass turned the migration-unmet veto
        into a soft advisory) rather than BLOCKING -- but the INFERRED arm STILL
        happens (asserted by the sibling Then steps): the declass relaxes only
        the entry VETO, never the S2-closing arm. The still-vetoing
        preconditions (MISSING_SSOT / INDETERMINATE) keep the same-pass hard
        veto. The observable here is action == "allow".
        """
        assert self._gate_decision() is GateDecision.ALLOW, (
            "a dispatch declaring the discuss wave on an EMPTY floor with the "
            "product model absent (MIGRATION_UNMET) must be ALLOWED in the same "
            "pass -- the slice-05 declass turned the greenfield migration-unmet "
            "veto into a soft advisory (a declared wave can still only ADD "
            "gating; the INFERRED arm still happens, only the entry veto "
            f"relaxes); the hook returned {self._decision_action!r}. "
            f"{self._observed()}"
        )

    def then_floor_records_inferred_discuss(self) -> None:
        """The fallback armed an INFERRED record (the F4 strand produced it)."""
        floor = self._read_floor_expecting_inferred_arm()
        assert (
            floor.get("wave") == "discuss" and floor.get("provenance") == "inferred"
        ), (
            "the fallback must arm the DECLARED wave with INFERRED provenance "
            "(the lower trust class I3 bounds -- never COMMAND, never "
            f"unrecorded); the floor was {floor!r}. {self._observed()}"
        )

    def then_inferred_entry_not_pending(self) -> None:
        """Self-entry rule: an INFERRED arm writes entry_pending=false/omitted."""
        floor = self._read_floor_expecting_inferred_arm()
        assert floor.get("entry_pending") in (False, None), (
            "an INFERRED arm must carry NO pending flag (arm and gate-IN "
            "coincide in the same PreToolUse pass -- no cross-event channel, "
            "no stale pending state; DESIGN self-entry NORMATIVE); the floor "
            f"was {floor!r}. {self._observed()}"
        )

    def then_armed_dispatch_allowed(self) -> None:
        """Met requirements on the COMMAND-armed floor -> the dispatch proceeds."""
        assert self._gate_decision() is GateDecision.ALLOW, (
            "a dispatch on the operator-armed floor with the product "
            "requirements satisfied must be ALLOWED (the gate only vetoes, "
            f"§22.0); the hook returned {self._decision_action!r}. "
            f"{self._observed()}"
        )

    def then_floor_keeps_command_provenance(self) -> None:
        """I3 dominance end-to-end: INFERRED never clobbers COMMAND."""
        floor = self._read_floor_expecting_inferred_arm()
        assert (
            floor.get("wave") == "discuss" and floor.get("provenance") == "command"
        ), (
            "a wave-declaring dispatch must NEVER overwrite the operator's "
            "explicit arming (I3 dominance: INFERRED never clobbers COMMAND "
            "-- pinned here through the REAL adapter path, not just the store "
            f"unit guarantee); the floor was {floor!r}. {self._observed()}"
        )

    def then_allowed_untouched(self) -> None:
        """K2/S1: ad-hoc work is allowed with zero wave-gate interference."""
        assert self._gate_decision() is GateDecision.ALLOW, (
            "an ad-hoc dispatch without a usable wave declaration must be "
            "ALLOWED untouched (K2 consent-gate / S1 zero false-positive -- "
            "an absent/out-of-vocab declaration is treated as absent, never "
            f"armed); the hook returned {self._decision_action!r}. "
            f"{self._observed()}"
        )
        assert self._decision_reason in (None, ""), (
            "the ad-hoc dispatch must carry NO block reason (left completely "
            f"untouched); got reason={self._decision_reason!r}. "
            f"{self._observed()}"
        )

    def then_no_wave_record_created(self) -> None:
        """The fallback is inert without a valid declaration: no garbage record."""
        assert self._project_root is not None
        floor_path = self._project_root / _FLOOR_FILE_REL
        assert not floor_path.exists(), (
            "an absent/out-of-vocabulary wave declaration must arm NOTHING -- "
            "no floor record may be created (a garbage record would arm "
            "enforcement off a non-declaration; out-of-vocab is validated at "
            "the use site and treated as absent); found "
            f"{floor_path.read_text(encoding='utf-8')!r}. {self._observed()}"
        )

    # ---- driving-port invocations (Layer 4 subprocess black boxes) -------------

    def _activate_project(self) -> None:
        """ACTIVATE the tmp project so the ADR-AG-001 activation gate dispatches
        the hook handler (an INACTIVE project short-circuits with sys.exit(0)
        before the wave-entry/fallback lifecycle ever runs -- a state production
        never produces, so the declared seams must run on an active root). Writes
        the activation marker only; the wave-active floor stays absent until a
        wave actually arms."""
        assert self._project_root is not None
        gc = self._project_root / ".nwave" / "global-config.json"
        gc.parent.mkdir(parents=True, exist_ok=True)
        gc.write_text(json.dumps({"activation": {"mode": "all"}}), encoding="utf-8")

    def _hook_env(self) -> dict[str, str]:
        assert self._project_root is not None
        env = dict(os.environ)
        env["NWAVE_FRESHNESS"] = "skip"
        env["PIPENV_DONT_LOAD_ENV"] = "1"
        env["PYTHONPATH"] = (
            str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        )
        env["HOME"] = str(self._project_root)
        # Mirror the dispatch cwd into DES_PROJECT_DIR so `resolve_nwave_root()`
        # (now consulted by activation_gate.apply_gate and pre_tool_use_handler's
        # peek_entry/arm_inferred/clear_entry) resolves the SAME root this call
        # chdir's to, not the per-test isolation root the autouse
        # `_isolate_nwave_root` fixture set (tests/conftest.py) -- this dict is a
        # FULL os.environ replacement (run_hook_in_process's `env=`), so the
        # ambient DES_PROJECT_DIR must be explicitly re-pinned here.
        env["DES_PROJECT_DIR"] = str(self._project_root)
        return env

    def _run_submission_hook(self, prompt: str) -> None:
        """Run the real prompt-submission anchor IN-PROCESS (slice-04 shape).

        Drives the production hook EDGE ``handle_user_prompt_submit`` (the no-argv
        stdin-protocol handler) directly under the same sandboxed ``HOME``/env.
        """
        assert self._project_root is not None
        payload = json.dumps({"prompt": prompt, "cwd": str(self._project_root)})
        returncode, stdout, stderr = run_hook_in_process(
            handle_user_prompt_submit,
            stdin_text=payload,
            cwd=str(self._project_root),
            env=self._hook_env(),
        )
        assert returncode == 0, (
            "the prompt-submission anchor must exit 0; got "
            f"rc={returncode}, stdout={stdout!r}, "
            f"stderr={stderr!r}"
        )

    def _run_pre_tool_use_hook(self, prompt: str) -> tuple[str, str | None]:
        """Drive the REAL PreToolUse hook adapter IN-PROCESS (hook-protocol stdin)."""
        assert self._project_root is not None
        payload = json.dumps(
            {
                "tool_name": "Agent",
                "tool_input": {
                    "prompt": prompt,
                    "subagent_type": "nw-product-owner",
                },
            }
        )
        returncode, stdout, stderr = run_hook_in_process(
            _hook_router_main,
            stdin_text=payload,
            cwd=str(self._project_root),
            argv=["claude_code_hook_adapter", "pre-tool-use"],
            env=self._hook_env(),
        )
        assert returncode in (0, 2), (
            "the PreToolUse hook must resolve to allow (0) or "
            f"block (2); got rc={returncode}, stdout="
            f"{stdout!r}, stderr={stderr!r}"
        )
        if returncode == 0:
            return (GateDecision.ALLOW.value, None)
        reason: str | None = None
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    reason = json.loads(line).get("reason")
                except json.JSONDecodeError:
                    reason = line
                break
        return (GateDecision.BLOCK.value, reason)

    # ---- observable-surface readers ---------------------------------------------

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the dispatch must be checked (When) before asserting (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == GateDecision.ALLOW.value
            else GateDecision.BLOCK
        )

    def _read_floor_expecting_inferred_arm(self) -> dict[str, object]:
        """Read the floor record, failing SEMANTICALLY when no arm happened."""
        assert self._project_root is not None
        floor_path = self._project_root / _FLOOR_FILE_REL
        assert floor_path.is_file(), (
            "the floor record must exist at the DESIGN-PINNED path "
            f"{_FLOOR_FILE_REL!r} -- a wave-declaring dispatch on an empty "
            "floor must ARM the wave (WaveActivationService.arm_inferred, the "
            "F4 fallback strand); no record was written (the strand is not "
            f"wired). {self._observed()}"
        )
        loaded = json.loads(floor_path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict), (
            f"the floor record must be a single JSON object; got {loaded!r}"
        )
        return loaded

    # ---- dispatch shapes ----------------------------------------------------------

    @staticmethod
    def _declaring_dispatch_prompt() -> str:
        """A DES-marked dispatch DECLARING its wave via the DES-WAVE marker.

        DESIGN-PINNED marker shape: ``<!-- DES-WAVE: <wave> -->``. The
        declaration is consumed ONLY to arm enforcement (never the active-wave
        source, never authorization -- §22.7 fail-direction: it can only ADD
        gating). No entry keywords anywhere (AD-66 deleted in 07c).
        """
        return (
            "DES-VALIDATION: required\n"
            "DES-PROJECT-ID: nwave-flow-v2-enforcement\n"
            "DES-PROJECT-ROOT: .\n"
            "DES-STEP-ID: discuss-1\n"
            "<!-- DES-WAVE: discuss -->\n"
            "proceed with the declared wave work"
        )

    @staticmethod
    def _adhoc_prompt(shape: WaveDeclarationShape) -> str:
        """An ad-hoc (non-DES) dispatch with no usable wave declaration."""
        base = "please tidy the helper module for readability"
        if shape is WaveDeclarationShape.OUT_OF_VOCAB:
            return base + "\n<!-- DES-WAVE: pizza -->"
        return base

    # ---- diagnostics -----------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"decision=({self._decision_action!r}, {self._decision_reason!r}); "
            f"project_root={self._project_root!r}"
        )
