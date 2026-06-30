"""Composition root for the fix-wave-marker-bypass-benign-passthrough slice-02 AT.

AT-7 -- the contract-test isolation invariant (Fix-2). The ONE driving port
(Mandate-13 driving-port-only, Layer-3 composition):

  * THE SHIPPED CONTRACT-TEST HARNESS -- the REAL ``claude_code_hook_stdin``
    fixture from
    ``tests/bugs/des/task-to-agent-migration/acceptance/test_agent_tool_hook_processing.py``
    (loaded from the file shipped in the repo, its raw ``__wrapped__`` function
    invoked with a ``tmp_path``). The harness in turn drives the production
    ``handle_pre_tool_use`` hook adapter in-process. AT-7 witnesses THE ACTUAL
    SHIPPED HARNESS -- not a re-implementation -- so the slice-02 fix to that
    fixture is exactly what flips this AT from RED to GREEN.

WHAT AT-7 WITNESSES (the isolation invariant). The production
``PreToolUseService`` sources its wave floor off ``Path.cwd()``
(``pre_tool_use_service.py:439`` -- ``WaveActiveReader.read(Path.cwd())``). The
shipped fixture takes ``tmp_path`` but NEVER sets CWD/store-root, so the
in-process handler reads whatever floor is armed in the AMBIENT working tree --
the env-coupling defect (the 9 reds). AT-7 asserts the opposite: the harness
decision is a function ONLY of the floor in the fixture's INJECTED ``tmp_path``
root, INDEPENDENT of the ambient working-tree floor.

UN-GAMEABLE, NON-AMBIENT-DEPENDENT DESIGN. The witness does NOT rely on the
developer's tree being armed. It arms a real CONTAMINANT floor in a root IT
controls and drives the shipped harness WHILE chdir'd there (modelling the
developer's armed working tree deterministically). The contaminant floor and the
``tmp_path``-injected floor are chosen so the discriminating partial-context
dispatch yields OPPOSITE decisions under each, so a leaked contaminant floor is
always observable and no incidental agreement can pass the test.

DISCRIMINATING PROBE. A PARTIAL-context dispatch (``DES-PROJECT-ID`` +
``DES-STEP-ID``, NO ``DES-VALIDATION``) -> ``carries_partial_wave_context`` True
-> BLOCK iff a floor is armed, ALLOW under a clean root. Its decision FLIPS on
floor identity, so it reveals which floor the harness actually read. (A
fully-markerless prompt ALLOWs under every floor and cannot witness isolation.)

RED-for-right-reason (pre-DELIVER fail-for-right-reason gate). At HEAD the
shipped fixture ignores ``tmp_path`` and reads the ambient (contaminant) floor:
  * Scenario 1 (contaminant ARMED, inject CLEAN tmp_path): the intrinsic
    decision under the CLEAN injected floor is ALLOW; the HEAD harness reads the
    contaminant ARMED floor -> BLOCK -> diverges -> the Then asserts
    ALLOW / injected-floor -> semantic ``AssertionError``.
  * Scenario 2 (contaminant CLEAN, inject ARMED 'design' tmp_path): the intrinsic
    decision under the injected ARMED floor is BLOCK; the HEAD harness reads the
    clean contaminant tree -> ALLOW -> diverges -> the Then asserts
    BLOCK / injected-floor -> semantic ``AssertionError``.
slice-02 wires the fixture's ``tmp_path`` as the handler's CWD/store-root, so the
harness reads the INJECTED floor in both scenarios -> both GREEN. Because the AT
drives the SHIPPED fixture's own function, that single edit is what greens it.

Only test-local types + the shipped fixture file (loaded by path) are referenced,
so the suite COLLECTS cleanly and each RED is a semantic ``AssertionError``,
never a collection / import / setup error.
"""

from __future__ import annotations

import importlib.util
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import FloorState, GateDecision


# DESIGN-PINNED floor path (slice-04 contract, reused as the one SSOT).
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# The SHIPPED contract-test harness AT-7 witnesses (Fix-2 target). Loaded from
# the repo file -- the fixture dir name carries hyphens, so it is not an
# importable dotted module; path-load is the faithful way to drive the ACTUAL
# shipped fixture so the slice-02 fix to it flips this AT.
_SHIPPED_FIXTURE_FILE = (
    Path(__file__).resolve().parents[4]
    / "bugs/des/task-to-agent-migration/acceptance/test_agent_tool_hook_processing.py"
)
_SHIPPED_FIXTURE_NAME = "claude_code_hook_stdin"

# The discriminating probe: PARTIAL wave context (a DES marker subset, so
# carries_partial_wave_context is True) but MISSES DES-VALIDATION. Its hook
# decision FLIPS on floor identity (BLOCK under an armed floor, ALLOW under a
# clean root), so it witnesses WHICH floor the harness actually read.
_PARTIAL_CONTEXT_PROMPT = (
    "DES-PROJECT-ID: fix-wave-marker-bypass-benign-passthrough\n"
    "DES-STEP-ID: design-1\n"
    "proceed with the in-wave work"
)

# The wave the contaminant floor carries when armed -- DELIBERATELY a different
# wave from any injected one, so a leaked contaminant floor is unambiguous.
_CONTAMINANT_FLOOR_WAVE = "deliver"


def _load_shipped_harness_factory() -> Callable[[Path], Callable[..., tuple]]:
    """Return the SHIPPED fixture's raw function(tmp_path) -> invoke_hook callable.

    Loads the actual repo file and returns the underlying ``__wrapped__``
    function of the ``claude_code_hook_stdin`` pytest fixture, so AT-7 drives the
    EXACT harness slice-02 fixes (no re-implementation, no tautology).
    """
    spec = importlib.util.spec_from_file_location(
        "_at7_shipped_fixture_mod", _SHIPPED_FIXTURE_FILE
    )
    assert spec is not None and spec.loader is not None, (
        f"cannot load the shipped contract-test fixture file at {_SHIPPED_FIXTURE_FILE}"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fixture = getattr(mod, _SHIPPED_FIXTURE_NAME)
    # pytest wraps the fixture function; .__wrapped__ is the raw function(tmp_path).
    return getattr(fixture, "__wrapped__", fixture)


@dataclass
class ContractIsolationComposition:
    """Drives the SHIPPED contract-test harness and witnesses floor isolation.

    The SUT-under-witness is the contract-test HARNESS (the shipped
    ``claude_code_hook_stdin`` fixture path). AT-7 asserts the harness reads the
    INJECTED ``tmp_path`` floor, never the ambient working-tree floor.
    """

    _contaminant_root: Path | None = field(default=None)
    _injected_root: Path | None = field(default=None)
    _injected_floor: FloorState | None = field(default=None)
    _injected_wave: str | None = field(default=None)
    _decision_action: str | None = field(default=None)

    # ---- given: arm / clear the AMBIENT contaminant working tree ------------

    def given_live_nonclean_floor(self, contaminant_root: Path) -> None:
        """Arm a real, NON-clean contaminant floor in the ambient working tree.

        The harness is driven WHILE chdir'd here, modelling a developer running
        the contract suite on a branch with a wave floor armed. A leaky harness
        (ignores the injected ``tmp_path``) reads THIS floor.
        """
        self._contaminant_root = contaminant_root
        self._seed_floor(
            contaminant_root, wave=_CONTAMINANT_FLOOR_WAVE, provenance="command"
        )

    def given_live_clean_tree(self, contaminant_root: Path) -> None:
        """Model a CLEAN ambient working tree (no floor armed).

        Used by the BLOCK-isolation scenario: with the ambient tree clean and an
        ARMED floor injected into ``tmp_path``, a leaky harness reads the clean
        ambient tree (ALLOW) while the isolated harness must read the injected
        armed floor (BLOCK) -- the divergence that makes env-coupling observable.
        """
        self._contaminant_root = contaminant_root
        # Write nothing -> the ambient tree resolves to NoWaveActive (clean).

    # ---- given: inject the harness's tmp_path floor -------------------------

    def given_injected_clean_root(self, injected_root: Path) -> None:
        """Inject a CLEAN isolated ``tmp_path`` floor (no wave armed)."""
        self._injected_root = injected_root
        self._injected_floor = FloorState.NO_FLOOR
        self._injected_wave = None
        # NO_FLOOR: write nothing -> the injected root resolves to NoWaveActive.

    def given_injected_armed_floor(self, injected_root: Path, wave: str) -> None:
        """Inject an ARMED floor of ``wave`` into the harness's ``tmp_path``."""
        self._injected_root = injected_root
        self._injected_floor = FloorState.DESIGN_ARMED
        self._injected_wave = wave
        self._seed_floor(injected_root, wave=wave, provenance="command")

    # ---- when: drive the SHIPPED harness (Layer-3 composition driving port) -

    def when_harness_validates_partial_dispatch(self) -> None:
        """Drive the shipped harness on the discriminating partial-context dispatch.

        Obtains the SHIPPED ``invoke_hook`` bound to the injected ``tmp_path``,
        chdir's to the contaminant root (the ambient tree), and invokes it. At
        HEAD the harness ignores ``tmp_path`` and reads the contaminant floor
        (RED); after slice-02 it honours ``tmp_path`` (GREEN).
        """
        self._decision_action = self._drive_shipped_harness()

    # ---- then: the isolation invariant --------------------------------------

    def then_decision_reflects_injected_floor(self) -> None:
        """The harness decision equals the decision intrinsic to the INJECTED floor.

        Pins isolation against an oracle computed by driving the shipped harness
        with the injected ``tmp_path`` WITHOUT a contaminant tree (chdir'd to the
        injected root, so even a leaky HEAD harness reads the injected floor).
        If the witnessed harness leaked the contaminant floor, the observed
        decision diverges from this injected-floor oracle -> AssertionError. The
        oracle is the hook's OWN decision under the injected floor (an observed
        effect, never a test-fabricated value), so the assertion is not a
        self-fulfilling fixture.
        """
        observed = self._gate_decision()
        oracle = self._intrinsic_decision_under_injected_floor()
        assert observed is oracle, (
            "the contract-test harness must assert the hook's INTRINSIC decision "
            "against its INJECTED tmp_path floor, independent of the ambient "
            f"working-tree floor; the harness returned {observed.value!r} but the "
            f"decision intrinsic to the injected floor (wave={self._injected_wave!r}) "
            f"is {oracle.value!r} -- the harness leaked the ambient working-tree "
            "floor. " + self._observed()
        )

    def then_decision_is_allow(self) -> None:
        assert self._gate_decision() is GateDecision.ALLOW, (
            "under a CLEAN injected floor a partial-context dispatch is ALLOWED "
            f"(no floor armed -> not in-the-wave); harness returned "
            f"{self._decision_action!r}. " + self._observed()
        )

    def then_decision_is_block(self) -> None:
        assert self._gate_decision() is GateDecision.BLOCK, (
            "under an ARMED injected floor a partial-context dispatch is BLOCKED "
            f"(K1 bypass loud); harness returned {self._decision_action!r}. "
            + self._observed()
        )

    # ---- shipped-harness invocation (the Fix-2 seam) ------------------------

    def _drive_shipped_harness(self) -> str:
        """Drive the SHIPPED fixture's invoke_hook under the contaminant tree.

        The injected ``tmp_path`` is what slice-02 must make the harness honour;
        the contaminant root is the ambient floor a HEAD (leaky) harness reads.
        """
        assert self._contaminant_root is not None
        assert self._injected_root is not None
        return self._run_under_contaminant(
            self._injected_root, self._contaminant_root, _PARTIAL_CONTEXT_PROMPT
        )

    def _intrinsic_decision_under_injected_floor(self) -> GateDecision:
        """The hook's OWN decision for the probe under the injected floor alone.

        Drives the shipped harness with the injected ``tmp_path`` AND chdir'd to
        the injected root (no contaminant), so even a leaky HEAD harness reads
        the injected floor -- yielding the intrinsic decision the isolated
        harness MUST reproduce. Observed effect, not a fabricated oracle.
        """
        assert self._injected_root is not None
        action = self._run_under_contaminant(
            self._injected_root, self._injected_root, _PARTIAL_CONTEXT_PROMPT
        )
        return GateDecision.BLOCK if action == "block" else GateDecision.ALLOW

    def _run_under_contaminant(
        self, tmp_path: Path, ambient_root: Path, prompt: str
    ) -> str:
        """Invoke the shipped invoke_hook(tmp_path) while chdir'd to ambient_root."""
        harness_factory = _load_shipped_harness_factory()
        invoke_hook = harness_factory(tmp_path)
        hook_stdin = json.dumps(
            {
                "tool_input": {
                    "subagent_type": "Explore",
                    "prompt": prompt,
                    "description": "contract-test isolation probe",
                }
            }
        )
        prev_cwd = Path.cwd()
        try:
            os.chdir(ambient_root)
            exit_code, _stdout, _stderr = invoke_hook("pre-task", hook_stdin)
        finally:
            os.chdir(prev_cwd)
        return "block" if exit_code == 2 else "allow"

    # ---- observable-surface readers -----------------------------------------

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the harness must be driven (When) before asserting (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == "allow"
            else GateDecision.BLOCK
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) ---------------

    def _seed_floor(self, root: Path, wave: str, provenance: str) -> None:
        """Seed the pinned floor record (precondition state, NOT the SUT)."""
        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        floor_path.write_text(
            json.dumps({"wave": wave, "provenance": provenance}),
            encoding="utf-8",
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"decision.action={self._decision_action!r}; "
            f"contaminant_floor_wave={_CONTAMINANT_FLOOR_WAVE!r}; "
            f"injected_floor={self._injected_floor!r}; "
            f"injected_wave={self._injected_wave!r}; "
            f"contaminant_root={self._contaminant_root!r}; "
            f"injected_root={self._injected_root!r}"
        )
