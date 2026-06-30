"""Composition root for wave-gateout slice-06 (fail-closed boundary + ADD-not-mutate).

WHAT slice-06 ASSERTS (the fail-closed boundary + the no-regression contract):

  (1) FAIL-CLOSED on an UNRESOLVABLE DES return -- ACTIVE-RED at HEAD.
      A wave-agent return carrying a ``DES-WAVE`` marker that the wave-only resolver
      CANNOT resolve -- the wave is OUT-OF-VOCABULARY, OR the ``DES-PROJECT-ID`` is
      absent -- must degrade LOUD (refuse / block), NOT silently passthrough-allow.
      DESIGN DDD-6 (design-notes.md slice-06) wants a DES-WAVE-present-but-unresolvable
      return distinguished from a genuine non-DES return.

      RED at HEAD (committed slice-01 code 2ff1bbab): ``_resolve_wave_only_context``
      (subagent_stop_handler.py:396) returns ``None`` when
      ``declared_wave not in WAVE_VOCABULARY or not project_id``; the caller then
      falls through to the EXISTING ``return None, {"decision":"allow"}, 0`` (silent
      passthrough). So an unresolvable DES return is SILENTLY ALLOWED -- the
      fail-closed boundary does not exist yet. These ATs are ACTIVE-RED: they RUN and
      fail for the right reason (a missing-functionality refusal, observed as the hook
      allowing where it must block), no setup/import error.

  (2) GENUINE NON-DES return -> the EXISTING passthrough-allow -- GREEN-ON-KEYSTONE.
      A return carrying NO ``DES-WAVE`` marker at all (a genuinely non-DES agent) MUST
      stay allowed (the passthrough is byte-stable). This regression-lock pins that
      the fail-closed cure (1) does NOT over-reach and start blocking non-DES agents.
      GREEN today and after the cure.

  (3) CLASSIC + atdd_pure context resolution -- ADD-not-mutate regression, GREEN.
      The classic ({project_id, step_id}) and atdd_pure (mode==atdd_pure) resolution
      paths stay byte-stable -- the wave-only fail-closed branch is an ADDED sibling,
      never an in-place rewrite (port-invariant WD-5, F2 blast-radius). Asserted by a
      classic execution-log return reaching the classic Step-1 pipeline (a
      LogFileNotFound block, unchanged) -- proving the wave-only guard does NOT
      hijack the classic path.

DRIVING SURFACE (Mandate-13 driving-port-only -- REUSED from slice-01..05): the REAL
``handle_subagent_stop`` hook entry, driven as a subprocess
(``python -m des.adapters.drivers.hooks.claude_code_hook_adapter subagent-stop``) with
a constructed return on stdin. The hook routes through the production composition root
(``service_factory.create_subagent_stop_service``); the observable is the hook
decision carried as a ``{"decision":"block"|"allow",...}`` JSON body on stdout. No
``des.domain.*`` import at the step boundary -- the hook process IS the SUT.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): slice-06 declares ONE net-new
load-bearing seam reached from the REAL hook entry:

  (seam-2) the fail-closed degrade-LOUD branch on an unresolvable DES return. Today
           ``_resolve_wave_only_context`` returns ``None`` for an out-of-vocab wave /
           a missing project id, which the caller maps to the silent
           passthrough-allow. The cure makes an unresolvable DES-WAVE-bearing return
           REFUSE (degrade-LOUD), distinct from the genuine-non-DES allow. The
           ACTIVE-RED ATs (1) NAME this seam, drive it through the REAL hook entry,
           and assert the observable effect (the hook block decision).

REUSE (Mandate-12): ``HookResult`` + ``_run_module`` from the slice-01 surface;
``arm_design_floor`` from the floor fixture. This composition re-derives NO plumbing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .composition_wave_gateout import HookResult, _run_module
from .domain_types import MarkerShape, WaveClosure
from .floor_fixture import activate_des_governance, arm_design_floor


_HOOK_ADAPTER_MODULE = "des.adapters.drivers.hooks.claude_code_hook_adapter"
_SUBAGENT_STOP_COMMAND = "subagent-stop"

_GATED_FEATURE_ID = "synthetic-orchestrated-boundary-feature"

# A wave value deliberately OUTSIDE WaveActiveRecord.WAVE_VOCABULARY (which is
# {distill, deliver, design, discuss, devops, feature-end}). The wave-only resolver
# must NOT map this to a governed wave -- yet a DES-WAVE was clearly declared, so a
# silent passthrough is a fail-OPEN leak the boundary must close.
_OUT_OF_VOCAB_WAVE = "bogus-not-a-wave"

# A governed wave used as the floor + the DES-WAVE for the NO_PROJECT_ID arm (the
# resolver rejects on the missing project id, not on the wave value).
_GOVERNED_WAVE = "design"


@dataclass
class WaveBoundaryComposition:
    """Drives the fail-closed boundary + the ADD-not-mutate regression for slice-06.

    Operates on a tmp work-tree. The orchestration return is a stdin payload fed to
    the REAL ``subagent-stop`` hook subcommand; the marker subset is chosen per the
    selected ``MarkerShape``. Reuses the slice-01 subprocess primitives (Mandate-12).
    """

    repo_dir: Path
    feature_id: str = field(default=_GATED_FEATURE_ID)
    _shape: MarkerShape = field(default=MarkerShape.OUT_OF_VOCAB)
    _hook_result: HookResult | None = field(default=None)

    def __post_init__(self) -> None:
        # ADR-AG-001 precondition: opt the synthetic project into DES governance
        # so the hook DISPATCHES into the production handler instead of the
        # activation gate silencing it (exit 0) before the wave gate-out / classic
        # pipeline runs. Covers the classic scenario too (its Given provisions no
        # tree), since the direct-DES protocol carries no cwd and the gate falls
        # back to the process cwd == this tmp tree.
        activate_des_governance(self.repo_dir)

    # ---- paths --------------------------------------------------------------

    @property
    def _feature_delta_path(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id / "feature-delta.md"

    @property
    def _transcript_path(self) -> Path:
        return self.repo_dir / ".nwave" / "_at" / "boundary_transcript.json"

    # ---- given: select the marker shape --------------------------------------

    def given_marker_shape(self, shape: MarkerShape) -> None:
        """Select the DES-marker subset the orchestration return carries."""
        self._shape = shape

    # ---- given: the orchestration return precondition state ------------------

    def given_return_under_orchestration(self) -> None:
        """Provision the tmp feature + arm a governed floor + write the transcript.

        Precondition state ONLY (NOT the SUT): a feature-delta, an armed governed
        (design) wave floor, and an agent transcript carrying the marker subset for
        the selected shape. The floor is armed to a governed wave for ALL shapes so
        the boundary discriminant is the RETURN's resolvability, not a missing floor.
        """
        self._feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self._feature_delta_path.write_text(
            "# Feature Delta: synthetic orchestrated boundary feature fixture\n\n"
            "## Wave: DESIGN\n\n"
            "### [REF] Inherited commitments\n\n"
            "| Origin | Commitment | DDD | Impact |\n"
            "|--------|------------|-----|--------|\n"
            "| n/a | a synthetic DESIGN deliverable the gate seals against | n/a | "
            "the bytes the review verdict's content seal binds to |\n",
            encoding="utf-8",
        )
        arm_design_floor(self.repo_dir, _GOVERNED_WAVE)
        self._write_transcript()

    def _write_transcript(self) -> None:
        """Write the agent transcript for the selected marker shape.

        OUT_OF_VOCAB  -- a DES-WAVE whose value is not in WAVE_VOCABULARY + a project
                         id (a DES return the resolver cannot map to a governed wave).
        NO_PROJECT_ID -- a governed DES-WAVE but NO DES-PROJECT-ID.
        NON_DES       -- NO DES-WAVE marker at all (a genuinely non-DES agent return).
        """
        if self._shape is MarkerShape.OUT_OF_VOCAB:
            markers = (
                "<!-- DES-VALIDATION : required -->\n"
                f"<!-- DES-WAVE : {_OUT_OF_VOCAB_WAVE} -->\n"
                f"<!-- DES-PROJECT-ID : {self.feature_id} -->\n"
                f"<!-- DES-PROJECT-ROOT : {self.repo_dir} -->\n"
            )
        elif self._shape is MarkerShape.NO_PROJECT_ID:
            markers = (
                "<!-- DES-VALIDATION : required -->\n"
                f"<!-- DES-WAVE : {_GOVERNED_WAVE} -->\n"
                f"<!-- DES-PROJECT-ROOT : {self.repo_dir} -->\n"
            )
        else:  # NON_DES -- no DES marker of any kind
            markers = (
                "I completed the requested refactor. No DES markers here -- this is "
                "a genuinely non-DES agent return that must pass through untouched.\n"
            )
        transcript_line = json.dumps(
            {"type": "assistant", "message": {"role": "assistant", "content": markers}}
        )
        self._transcript_path.parent.mkdir(parents=True, exist_ok=True)
        self._transcript_path.write_text(transcript_line + "\n", encoding="utf-8")

    # ---- when ----------------------------------------------------------------

    def when_orchestration_return_evaluated(self) -> None:
        """Drive the REAL subagent-stop hook with the chosen return on stdin."""
        hook_input = {
            "agent_type": "nw-some-agent",
            "agent_id": "at-boundary-return",
            "agent_transcript_path": str(self._transcript_path),
            "cwd": str(self.repo_dir),
        }
        self._hook_result = _run_module(
            _HOOK_ADAPTER_MODULE,
            [_SUBAGENT_STOP_COMMAND],
            cwd=self.repo_dir,
            stdin=json.dumps(hook_input),
        )

    def when_classic_return_evaluated(self) -> None:
        """Drive the REAL subagent-stop hook with a CLASSIC direct-DES return.

        The classic protocol carries executionLogPath + projectId + stepId (the
        direct-DES fields, no transcript). It must route into the classic Step-1
        pipeline unchanged -- the wave-only guard (step_id=='' AND
        execution_log_path=='') must NOT hijack it. With a non-existent log the
        classic path blocks with LogFileNotFound (byte-stable behavior).
        """
        missing_log = str(
            self.repo_dir
            / "docs"
            / "feature"
            / self.feature_id
            / "deliver"
            / "execution-log.json"
        )
        hook_input = {
            "executionLogPath": missing_log,
            "projectId": self.feature_id,
            "stepId": "step-01",
        }
        self._hook_result = _run_module(
            _HOOK_ADAPTER_MODULE,
            [_SUBAGENT_STOP_COMMAND],
            cwd=self.repo_dir,
            stdin=json.dumps(hook_input),
        )

    # ---- then ----------------------------------------------------------------

    def then_wave_closure_refused(self) -> None:
        """An unresolvable DES return is REFUSED (the fail-closed boundary).

        Seam-named oracle (Mandate-15 seam-2): a DES-WAVE-bearing return the resolver
        cannot resolve (out-of-vocab wave / missing project id) must degrade LOUD --
        a block on the hook's stdout decision body -- NOT a silent passthrough-allow.
        ACTIVE-RED at HEAD: ``_resolve_wave_only_context`` returns None for such a
        return, so the caller emits the silent passthrough-allow (no block body) ->
        the observed closure is ALLOWED, not REFUSED -> a semantic AssertionError
        naming the missing fail-closed boundary (a missing-functionality RED, not a
        test bug -- every dependency resolves cleanly).
        """
        self._assert_closure(WaveClosure.REFUSED)

    def then_wave_closure_allowed(self) -> None:
        """A genuinely non-DES return is ALLOWED (the existing passthrough byte-stable).

        Regression-lock (green-on-keystone): a return carrying NO DES-WAVE marker is a
        genuinely non-DES agent and MUST stay allowed. Pins that the fail-closed cure
        does not over-reach and block non-DES agents (no block body on stdout).
        """
        self._assert_closure(WaveClosure.ALLOWED)

    def then_classic_path_blocks_on_missing_log(self) -> None:
        """The classic direct-DES path blocks on LogFileNotFound (ADD-not-mutate).

        Regression-lock (green-on-keystone): a classic return (executionLogPath +
        projectId + stepId) routes into the classic Step-1 pipeline UNCHANGED -- the
        wave-only guard does NOT hijack it. With a non-existent log the classic path
        emits its byte-stable ``Execution log not found`` block. The discriminating
        observable is that the block reason is the CLASSIC log-not-found one, proving
        the wave-only branch left the classic path byte-stable.
        """
        result = self._hook_result
        assert result is not None, (
            "the classic return must be evaluated (When) before asserting the "
            "classic path stayed byte-stable (Then)"
        )
        reason = result.block_reason.lower()
        assert (
            result.closure is WaveClosure.REFUSED
            and "execution log not found" in reason
        ), (
            "the classic direct-DES return (executionLogPath + projectId + stepId) "
            "must route into the classic Step-1 pipeline UNCHANGED -- the wave-only "
            "guard (step_id=='' AND execution_log_path=='') must not hijack it. With "
            "a non-existent log the classic path blocks with 'Execution log not "
            "found' (the byte-stable behavior the ADD-not-mutate invariant preserves)."
            f" Observed closure {result.closure.value!r}, "
            f"reason={result.block_reason[:300]!r}. {self._observed()}"
        )

    # ---- assertion helpers ---------------------------------------------------

    def _assert_closure(self, expected: WaveClosure) -> None:
        result = self._hook_result
        assert result is not None, (
            "the orchestration return must be evaluated at the wave boundary (When) "
            "before asserting the wave-closure decision (Then)"
        )
        assert result.closure is expected, (
            f"a {self._shape.value} return must project the wave closure as "
            f"{expected.value!r} onto the hook's stdout decision body "
            '(REFUSED -> {"decision":"block"}, ALLOWED -> no block body). The '
            "fail-closed boundary (DDD-6) refuses a DES-WAVE-bearing return the "
            "resolver cannot resolve (out-of-vocab / no project id), distinct from a "
            "genuine non-DES return which stays allowed. At HEAD an unresolvable DES "
            "return is SILENTLY ALLOWED (_resolve_wave_only_context returns None -> "
            "the caller's passthrough-allow at subagent_stop_handler.py:312-313), so "
            f"the observed closure is {result.closure.value!r} "
            f"(decision={result.decision!r}). {self._observed()}"
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        hook = self._hook_result
        return (
            f"shape={self._shape.value}; "
            f"floor_armed={(self.repo_dir / '.nwave' / 'wave-active' / 'active.json').is_file()}; "
            "hook=(decision="
            + (repr(hook.decision) if hook else "n/a")
            + ", stdout="
            + (repr(hook.stdout[:300]) if hook else "n/a")
            + ", stderr="
            + (repr(hook.stderr[:300]) if hook else "n/a")
            + ")"
        )
