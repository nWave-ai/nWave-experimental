"""Composition root for the nwave-flow-v2-enforcement slice-07c ATs.

The *only* place the production system is wired for slice-07c. Two driving
ports (Mandate-13 driving-port-only):

  * WAVE-ENTRY LIFECYCLE (AT-1 / AT-2) -- Layer 4 wiring, two REAL hook
    subprocesses over a tmp ``project_root``:
      (a) the prompt-submission anchor
          (``python -m des.adapters.drivers.hooks.user_prompt_submit_handler``
          with stdin ``{prompt, cwd}``) -- arms the wave-active floor from the
          raw ``/nw-discuss`` literal;
      (b) the PreToolUse hook adapter
          (``python -m des.adapters.drivers.hooks.claude_code_hook_adapter
          pre-tool-use`` with hook-protocol stdin JSON) -- the composition
          seat of the NET-NEW peek_entry -> validate(wave_entering=...) ->
          clear-on-allow lifecycle (DESIGN slice-07c "Composition"), so it IS
          the real entry point for those seams.
    Observables: hook exit code (0 allow / 2 block) + the block reason JSON +
    the floor record at the DESIGN-PINNED path
    ``.nwave/wave-active/active.json`` (floor v1.1: optional 4th key
    ``entry_pending``; key omitted <=> false).

  * REVIEW-VERDICT AUDIT (AT-3, the 07b routed gap) -- the SHIPPED pure core
    ``DiscussReviewGate.evaluate(record, key, expected_feature_delta_hash)``
    invoked direct in-process. Mandate-13 adjudication: the 07b design
    declared the pure core the contract surface ("a seam-level unit AT
    exercises DiscussReviewGate.evaluate directly over a crafted record+key
    to pin each closed token"); slice-06 pure-function driving-port
    precedent; architect-reviewer APPROVED (a06237ced). This is the
    DESIGN-declared seam callable, not an internal convenience import.

State lives on the instance; every ``given_/when_/then_`` method mutates or
reads it. Step functions are thin delegations (Mandate-12).

RED-for-right-reason (pre-DELIVER fail-for-right-reason gate): at HEAD the
floor record has NO ``entry_pending`` field (the anchor writes only
wave/provenance), ``WaveActivationService`` does not exist, and the gate-IN
keys on the AD-66 keyword heuristic -- which a wording-free dispatch never
trips. So:
  * AT-1 -- ``then_arm_marked_entry_pending`` raises a semantic
    ``AssertionError`` (the floor carries no entry-pending mark); were the
    flag present, the wording-free dispatch would still be ALLOWED where the
    structural entry gate must BLOCK (second semantic RED behind it).
  * AT-2 -- same pending-mark semantic ``AssertionError``; the allow +
    once-only legs already hold at HEAD (preservation) and MUST keep holding.
  * AT-3 -- GREEN-preservation: the 07b core shipped; the four rows PIN the
    routed INDETERMINATE reasons (key-absent / stale-artefact /
    schema-unknown / unknown-verdict-literal -> closed detail
    ``schema-unknown``).
No collection / import error (only test-local types, shipped production
modules, and stdlib are imported).

DESIGN-PINNED CONTRACTS this AT-seed conforms to (feature-delta § slice-07c
code-design -- ONE SSOT shared by the AT-seed and the crafter; no drift):
  * floor v1.1: single JSON object at ``.nwave/wave-active/active.json``;
    optional 4th key ``entry_pending`` (bool); key omitted <=> false;
    the COMMAND arm writes ``"entry_pending": true`` (INVARIANT I4).
  * clear-on-allow (NORMATIVE): gate-IN BLOCK -> the flag STAYS pending
    (the retry re-runs the entry preconditions); ALLOW -> the flag clears,
    the wave record itself stays armed (bounded change, same single file).
  * once-only: a cleared entry is never re-gated -- a later in-wave dispatch
    passes even when the preconditions have degraded (the entry check ran
    exactly once; strand-2 seam gates still apply downstream).
  * product SSOT preconditions: ``docs/product/`` + the four SSOT docs
    (slice-07 pinned shape, re-declared per-slice).
  * DISCUSS_SIGNED_FIELDS canonical signing for the AT-3 record seed
    (arrange-side stdlib hmac/hashlib, mirroring the slice-07b seed).

Reason tokens: an entry-precondition block must carry a gate-IN class token
(K1 named-LOUD); the AT-3 INDETERMINATE details are the shipped closed set.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from des.adapters.drivers.hooks.hook_router import main as _hook_router_main
from des.adapters.drivers.hooks.user_prompt_submit_handler import (
    handle_user_prompt_submit,
)
from tests.common.in_process_cli import run_hook_in_process

from .domain_types_slice_07c import (
    EntryPreconditions,
    GateDecision,
    ReviewVerdictFlaw,
)


# tests/des/acceptance/nwave_flow_v2_enforcement/steps/composition_slice_07c.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# DESIGN-PINNED floor path (slice-04 contract, extended by floor v1.1).
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# DESIGN-PINNED product-SSOT layout (slice-07 gate-IN precondition shape).
# The jobs slot is satisfied by docs/product/jobs.yaml (the structured JOB
# registry wired into validate_ssot_propagation + the discuss/diverge skills) --
# NOT jobs.md. Migrating the jobs slot off .md is a pure correctness fix;
# vision/backlog/glossary stay .md.
_PRODUCT_DIR_REL = "docs/product"
_REQUIRED_SSOT_DOCS: tuple[str, ...] = (
    "vision.md",
    "backlog.md",
    "glossary.md",
    "jobs.yaml",
)

# The raw user submission literal the anchor keys on (slice-04 contract).
_DISCUSS_COMMAND_PROMPT = "/nw-discuss continue the feature work"

# ---- AT-3 (review-verdict audit) DESIGN-PINNED record contract --------------
_FEATURE_ID = "nwave-flow-v2-enforcement"
_KNOWN_SCHEMA_VERSION = "1.0.0"
_UNKNOWN_SCHEMA_VERSION = "0.0.1"
_REVIEWER_AGENT_ID = "nw-product-owner-reviewer"
_CURRENT_DELTA_HASH = hashlib.sha256(b"the current feature-delta bytes").hexdigest()
_DRIFTED_DELTA_HASH = hashlib.sha256(
    b"an EDITED feature-delta judged earlier"
).hexdigest()


def _keyless_review_record(
    verdict: str,
    feature_delta_hash: str,
    schema_version: str = _KNOWN_SCHEMA_VERSION,
) -> dict[str, object]:
    """A keyless DiscussReviewVerdict record (no ``hmac_sha256`` field).

    Post-demotion (oss-review-verdict-demotion S3): the gate evaluates present
    fields only; no signing key is needed. The arrange-side hmac/signing surface
    is REMOVED; pre-existing ``hmac_sha256`` fields on old records are
    tolerated-and-ignored (D-tolerate-old).
    """
    return {
        "event": "DiscussReviewVerdict",
        "schema_version": schema_version,
        "feature_id": _FEATURE_ID,
        "verdict": verdict,
        "reviewer_agent_id": _REVIEWER_AGENT_ID,
        "feature_delta_hash": feature_delta_hash,
        "timestamp": "2026-06-10T00:00:00+00:00",
    }


@dataclass
class WaveEntryComposition:
    """Drives the anchor-owned wave-entry lifecycle (AT-1 / AT-2) end to end."""

    _project_root: Path | None = field(default=None)
    _floor_after_arm: dict[str, object] | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)
    _later_action: str | None = field(default=None)
    _later_reason: str | None = field(default=None)

    # ---- given ---------------------------------------------------------------

    def given_armed_discuss_via_command(self, tmp_path: Path) -> None:
        """Arm the discuss wave through the REAL submission anchor (subprocess)."""
        self._project_root = tmp_path
        self._activate_project()
        self._run_submission_hook(_DISCUSS_COMMAND_PROMPT)
        self._floor_after_arm = self._read_floor()

    def given_entry_preconditions(self, preconditions: EntryPreconditions) -> None:
        """Arrange the product-SSOT precondition state (slice-07 pinned shape)."""
        assert self._project_root is not None
        if preconditions is EntryPreconditions.MET:
            product_dir = self._project_root / _PRODUCT_DIR_REL
            product_dir.mkdir(parents=True, exist_ok=True)
            for doc in _REQUIRED_SSOT_DOCS:
                (product_dir / doc).write_text(f"# {doc}\n", encoding="utf-8")
        # UNMET: write nothing -> docs/product/ absent (migration-unmet).

    # ---- when ------------------------------------------------------------------

    def when_wordless_in_wave_dispatch_checked(self) -> None:
        """Drive the REAL PreToolUse hook adapter with a keyword-free dispatch."""
        self._decision_action, self._decision_reason = self._run_pre_tool_use_hook()

    def when_later_dispatch_checked_after_degraded_preconditions(self) -> None:
        """Degrade the preconditions, then drive a later in-wave dispatch."""
        assert self._project_root is not None
        shutil.rmtree(self._project_root / _PRODUCT_DIR_REL, ignore_errors=True)
        self._later_action, self._later_reason = self._run_pre_tool_use_hook()

    # ---- then ------------------------------------------------------------------

    def then_arm_marked_entry_pending(self) -> None:
        """INVARIANT I4: the COMMAND arm writes entry_pending: true on the floor."""
        assert self._floor_after_arm is not None
        assert self._floor_after_arm.get("entry_pending") is True, (
            "the arming command (the anchor, which deterministically saw the "
            "/nw-discuss literal) must mark the wave entry as PENDING on the "
            "floor record (floor v1.1 'entry_pending': true -- the F3 "
            "anchor-owned signal, INVARIANT I4); the floor written by the arm "
            f"was {self._floor_after_arm!r}. {self._observed()}"
        )

    def then_dispatch_allowed(self) -> None:
        """An entering dispatch passes the gate-IN (no veto).

        Two scenarios share this Then (Pillar-2 shared vocabulary): a MET
        precondition (AT-2) and a greenfield product model absent (AT-1,
        MIGRATION_UNMET) -- the slice-05 declass turned the latter from a hard
        veto into a soft advisory, so BOTH now ALLOW the entry. The still-vetoing
        preconditions (MISSING_SSOT / INDETERMINATE) keep a hard BLOCK and are
        exercised by the slice-07 gate-IN ATs; here the observable is simply that
        the gate did NOT block (action == "allow").
        """
        assert self._first_decision() is GateDecision.ALLOW, (
            "an entering dispatch whose product preconditions are MET -- or whose "
            "only objection is the greenfield product model being absent "
            "(MIGRATION_UNMET, declassed to a soft advisory in slice-05) -- must "
            "be ALLOWED (the entry gate only hard-vetoes MISSING_SSOT / "
            f"INDETERMINATE, §22.0); the hook returned {self._decision_action!r}. "
            f"{self._observed()}"
        )

    def then_entry_cleared_by_allowed_entry(self) -> None:
        """Clear-on-allow: the flag clears; the wave record itself stays armed."""
        floor = self._read_floor()
        assert floor.get("wave") == "discuss", (
            "clearing the entry flag must be a BOUNDED change: the wave record "
            "itself stays armed (only entry_pending clears); the floor after "
            f"the allowed entry was {floor!r}. {self._observed()}"
        )
        assert floor.get("entry_pending") in (False, None), (
            "the ALLOWED entering dispatch must CLEAR the pending flag "
            "(clear-on-allow: the entry check runs exactly once; key omitted "
            "<=> false per floor v1.1); the floor after the allowed entry was "
            f"{floor!r}. {self._observed()}"
        )

    def then_later_dispatch_not_regated(self) -> None:
        """Once-only: a cleared entry is never re-gated (K2-style in-wave)."""
        assert self._later_action == GateDecision.ALLOW.value, (
            "a LATER in-wave dispatch after a cleared entry must NOT re-run "
            "the entry preconditions (the entry check ran exactly once -- "
            "even though the preconditions have since degraded, re-gating "
            "every child would re-introduce the per-dispatch interference K2 "
            f"forbids); the hook returned {self._later_action!r} with reason="
            f"{self._later_reason!r}. {self._observed()}"
        )

    # ---- driving-port invocations (Layer 4 subprocess black boxes) -------------

    def _activate_project(self) -> None:
        """ACTIVATE the tmp project so the ADR-AG-001 activation gate dispatches
        the hook handler (an INACTIVE project short-circuits with sys.exit(0)
        before the wave-entry lifecycle ever runs -- a state production never
        produces, so the wave-entry seams must be exercised on an active root)."""
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
        # Sandbox HOME so hook-side signal/log writes stay inside the tmp root.
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
        stdin-protocol handler the ``python -m ...user_prompt_submit_handler`` fork
        invoked) directly, feeding the same JSON payload on stdin under the same
        sandboxed ``HOME``/env — no interpreter fork.
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
            "the prompt-submission anchor must exit 0 (arm-and-"
            f"continue); got rc={returncode}, stdout="
            f"{stdout!r}, stderr={stderr!r}"
        )

    def _run_pre_tool_use_hook(self) -> tuple[str, str | None]:
        """Drive the REAL PreToolUse hook adapter (hook-protocol stdin JSON).

        Exit 0 = allow; exit 2 = block with a `{decision:block, reason}` body
        on stdout. Any other exit is an infrastructure failure surfaced loud.
        """
        assert self._project_root is not None
        payload = json.dumps(
            {
                "tool_name": "Agent",
                "tool_input": {
                    "prompt": self._wordless_in_wave_prompt(),
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

    def _first_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the dispatch must be checked (When) before asserting (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == GateDecision.ALLOW.value
            else GateDecision.BLOCK
        )

    def _read_floor(self) -> dict[str, object]:
        """Read the single wave-active record at the DESIGN-PINNED fixed path."""
        assert self._project_root is not None
        floor_path = self._project_root / _FLOOR_FILE_REL
        assert floor_path.is_file(), (
            "the wave-active floor record must exist at the DESIGN-PINNED path "
            f"{_FLOOR_FILE_REL!r} after the arm (slice-04 contract); absent "
            f"under {self._project_root!r}"
        )
        loaded = json.loads(floor_path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict), (
            f"the floor record must be a single JSON object; got {loaded!r}"
        )
        return loaded

    # ---- dispatch shapes ----------------------------------------------------------

    @staticmethod
    def _wordless_in_wave_prompt() -> str:
        """A marked in-wave dispatch carrying ZERO entry keywords.

        Deliberately free of any wave-entry wording ("begin"/"enter"/"start"):
        at TARGET only the anchor-owned structural signal can classify it as
        the entering dispatch (F3); at HEAD the AD-66 keyword heuristic never
        trips on it, exposing the missing structural signal as semantic RED.
        """
        return (
            "DES-VALIDATION: required\n"
            "DES-PROJECT-ID: nwave-flow-v2-enforcement\n"
            "DES-PROJECT-ROOT: .\n"
            "DES-STEP-ID: discuss-1\n"
            "proceed with the in-wave product work"
        )

    # ---- diagnostics -----------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"first=({self._decision_action!r}, {self._decision_reason!r}); "
            f"later=({self._later_action!r}, {self._later_reason!r}); "
            f"floor_after_arm={self._floor_after_arm!r}; "
            f"project_root={self._project_root!r}"
        )


# Expected closed detail reason per flaw (the shipped DiscussReviewGateResult
# closed set post-demotion; the unknown-verdict-literal cause maps to
# `schema-unknown`). KEY_ABSENT is REMOVED -- no key to be absent post-demotion
# (oss-review-verdict-demotion S3).
_EXPECTED_DETAIL: dict[ReviewVerdictFlaw, str] = {
    ReviewVerdictFlaw.STALE_ARTEFACT: "stale-artefact",
    ReviewVerdictFlaw.SCHEMA_UNKNOWN: "schema-unknown",
    ReviewVerdictFlaw.UNKNOWN_VERDICT_LITERAL: "schema-unknown",
}


@dataclass
class ReviewVerdictAuditComposition:
    """Drives the SHIPPED DiscussReviewGate.evaluate pure core (AT-3 outline).

    The 07b routed gap: the three production-implemented, probe-verified but
    not-AT-pinned INDETERMINATE reasons (post-demotion: KEY_ABSENT removed;
    three keyless flaws remain). Driving port = the pure core direct
    (the DESIGN-declared seam callable; Mandate-13 adjudicated, a06237ced).

    Post-demotion (oss-review-verdict-demotion S3): evaluate() takes no key
    param; records are keyless (no ``hmac_sha256``).
    """

    _record: dict[str, object] | None = field(default=None)
    _flaw: ReviewVerdictFlaw | None = field(default=None)
    _result_token: str | None = field(default=None)
    _result_detail: str | None = field(default=None)

    # ---- given ---------------------------------------------------------------

    def given_flawed_verdict(self, flaw: ReviewVerdictFlaw) -> None:
        """Arrange the keyless record for the given unverifiable shape."""
        self._flaw = flaw
        if flaw is ReviewVerdictFlaw.STALE_ARTEFACT:
            self._record = _keyless_review_record("approved", _DRIFTED_DELTA_HASH)
        elif flaw is ReviewVerdictFlaw.SCHEMA_UNKNOWN:
            self._record = _keyless_review_record(
                "approved", _CURRENT_DELTA_HASH, schema_version=_UNKNOWN_SCHEMA_VERSION
            )
        else:  # UNKNOWN_VERDICT_LITERAL -- current, unreadable verdict literal
            self._record = _keyless_review_record("maybe-later", _CURRENT_DELTA_HASH)

    # ---- when ------------------------------------------------------------------

    def when_verdict_evaluated(self) -> None:
        """Invoke the shipped pure core (the DESIGN-declared seam callable)."""
        # Mandate-13 adjudicated direct seam call (07b design + slice-06
        # pure-function driving-port precedent; architect-reviewer APPROVED).
        from des.domain.discuss_review_gate import DiscussReviewGate

        result = DiscussReviewGate.evaluate(
            self._record, expected_feature_delta_hash=_CURRENT_DELTA_HASH
        )
        self._result_token = result.token.value
        self._result_detail = result.detail

    # ---- then ------------------------------------------------------------------

    def then_indeterminate_naming(self, cause: str) -> None:
        """Token INDETERMINATE + the closed detail reason -- degrade-LOUD, named."""
        assert self._flaw is not None and self._result_token is not None
        assert self._result_token == "indeterminate", (
            f"an unverifiable PO-review verdict ({self._flaw.value}) must be "
            "INDETERMINATE (degrade-LOUD block, §17) -- NEVER coerced to PASS "
            "and NEVER to VETOED ('mechanism couldn't run' is not 'reviewer "
            f"said no', §22.7); the gate returned token="
            f"{self._result_token!r}, detail={self._result_detail!r}."
        )
        expected_detail = _EXPECTED_DETAIL[self._flaw]
        assert cause == expected_detail, (
            f"example-row drift: the Gherkin row for {self._flaw.value} names "
            f"cause={cause!r} but the shipped closed detail set maps it to "
            f"{expected_detail!r} -- fix the .feature row, not the core."
        )
        assert self._result_detail == expected_detail, (
            f"the INDETERMINATE verdict for {self._flaw.value} must NAME its "
            f"cause with the closed detail reason {expected_detail!r} (the "
            "shipped DiscussReviewGateResult closed set -- a loud, "
            f"attributable degrade); got detail={self._result_detail!r}."
        )
