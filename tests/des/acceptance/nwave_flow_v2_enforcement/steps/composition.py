"""Composition root for the nwave-flow-v2-enforcement slice-04 ATs.

The *only* place the production system is wired for slice-04. Two driving ports,
both composition-root (Mandate-13 driving-port-only):

  * WALKING SKELETON (Layer 4 wiring_e2e) -- the REAL prompt-submission hook
    process, invoked as ``python -m
    des.adapters.drivers.hooks.user_prompt_submit_handler`` with the runtime's
    stdin JSON. The anchor port / writer are NEVER imported-and-called here; the
    observable surface is the wave-active FLOOR FILE the hook writes under
    ``project_root`` (a filesystem driven-internal port -- reading it back is
    observing the effect, not the SUT).

  * READ + SCOPE (Layer 3 composition) -- the REAL ``PreToolUseService.validate``
    built via the production composition root
    (``service_factory.create_pre_tool_use_service``). The service is the SUT;
    only the wave-active floor (precondition state) is arranged. The assertion is
    on the service's ``HookDecision`` (allow vs block).

State lives on the instance; every ``given_/when_/then_`` method mutates or reads
it. Step functions are thin delegations (Mandate-12: no business logic in step
bodies).

RED-for-right-reason: the net-new seams are RED scaffolds, so (a) the hook
subprocess raises AssertionError and writes no floor file -> the walking-skeleton
read-back raises a semantic AssertionError (no record armed); (b) the production
service has no wave-aware reader wiring yet -> a markerless in-wave dispatch is
ALLOWED where a DENY is expected -> the S2 assertion fails for the right reason.
No collection / import error in the test process (only test-local types +
already-shipped production composition are imported).

DESIGN-PINNED FLOOR CONTRACT (feature-delta § slice-04 design -- ONE SSOT shared
by the AT-seed and the crafter's WaveActiveReader; no drift): a single JSON
object at the FIXED path ``{project_root}/.nwave/wave-active/active.json`` -- one
record per project (NOT a directory scan). Keys: ``wave`` (required, closed vocab
``discuss|design|devops|distill|deliver|feature-end``), ``provenance`` (required,
closed set ``"command"|"inferred"``), ``scope`` (optional -- key OMITTED when
whole-wave, never null). Absent file <=> NoWaveActive. A missing / out-of-vocab
required key is a degrade-LOUD Indeterminate, never coerced to NoWaveActive.

The path + serialization format are NOT the crafter's choice -- they are
DESIGN-PINNED; the crafter's writer CONFORMS to this exact path/shape, and only
the write-mechanics (atomic rename / fsync) are the crafter's. If the crafter's
writer puts the record anywhere else, AT-1 SHOULD fail -- that is the drift this
fixed-path read now catches. The ATs pin: after the discuss command, the project
records the discuss wave with COMMAND provenance at the pinned path, and no other
wave.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from des.adapters.drivers.hooks.user_prompt_submit_handler import (
    handle_user_prompt_submit,
)
from tests.common.in_process_cli import run_hook_in_process

from .domain_types import (
    GateDecision,
    Provenance,
    Wave,
    WaveActiveState,
)


# The production prompt-submission hook module under test. Its handler is a RED
# scaffold at HEAD -> RED-for-right-reason (no floor written).
SUBMISSION_HOOK_MODULE = "des.adapters.drivers.hooks.user_prompt_submit_handler"

# DESIGN-PINNED floor path: a single JSON object at this FIXED relative path under
# project_root (one record per project, NOT a directory scan). The AT-seed and the
# crafter's WaveActiveReader share this one SSOT; a record written anywhere else is
# drift that AT-1 must catch.
_FLOOR_FILE_REL = ".nwave/wave-active/active.json"

# Closed vocabularies the floor contract pins (DESIGN slice-04). A required key
# whose value is out-of-vocab is a degrade-LOUD Indeterminate, never coerced.
_WAVE_VOCAB: frozenset[str] = frozenset(
    {"discuss", "design", "devops", "distill", "deliver", "feature-end"}
)
_PROVENANCE_VOCAB: frozenset[str] = frozenset({"command", "inferred"})

# Tokens a loud S2 denial reason must carry so a generic block cannot satisfy the
# bypass-named assertion (K1: a bypass is LOUD, not a silent green).
_BYPASS_TOKENS: tuple[str, ...] = (
    "wave",
    "bypass",
    "marker",
    "in-wave",
)


@dataclass
class WaveActiveAnchorComposition:
    """Drives the production wave-active anchor seams for the slice-04 ATs."""

    _project_root: Path | None = field(default=None)
    _armed_wave: Wave | None = field(default=None)
    _submission_completed: subprocess.CompletedProcess[str] | None = field(default=None)
    _decision_action: str | None = field(default=None)
    _decision_reason: str | None = field(default=None)

    # ---- given (walking skeleton) -------------------------------------------

    def given_clean_project_no_wave_active(self, tmp_path: Path) -> None:
        """A clean project_root with no wave-active floor record (S1 floor)."""
        self._project_root = tmp_path
        # No floor written -> the absent state the anchor must arm from.

    # ---- given (read + scope) -----------------------------------------------

    def given_wave_active(self, tmp_path: Path, wave: Wave) -> None:
        """Arrange precondition state: a wave is armed on the floor.

        The floor is seeded directly (precondition state, NOT the SUT). DELIVER's
        WaveActiveReader reads this same single-record floor; seeding it here is
        the arrangement the read+scope SUT consumes.
        """
        self._project_root = tmp_path
        self._armed_wave = wave
        self._seed_floor(tmp_path, wave=wave, provenance=Provenance.COMMAND)

    def given_no_wave_active(self, tmp_path: Path) -> None:
        """Arrange precondition state: NoWaveActive (the S1 floor)."""
        self._project_root = tmp_path
        self._armed_wave = None
        # No floor file -> NoWaveActive.

    # ---- when (walking skeleton) --------------------------------------------

    def when_user_submits_wave_command(self, wave: Wave) -> None:
        """Invoke the REAL prompt-submission hook as a subprocess black box."""
        self._run_submission_hook(prompt=f"/nw-{wave.value} let's begin")

    # ---- when (read + scope) ------------------------------------------------

    def when_markerless_in_wave_dispatch_checked(self) -> None:
        """Drive PreToolUseService.validate with a markerless in-wave sub-dispatch."""
        self._run_gate(prompt=self._markerless_child_prompt())

    def when_in_wave_dispatch_with_markers_checked(self) -> None:
        """Drive PreToolUseService.validate with an in-wave child carrying markers."""
        self._run_gate(prompt=self._child_prompt_with_markers())

    def when_bare_non_wave_dispatch_checked(self) -> None:
        """Drive PreToolUseService.validate with a bare non-wave dispatch (S1)."""
        self._run_gate(prompt="please refactor the helper for readability")

    # ---- then (walking skeleton) --------------------------------------------

    def then_wave_recorded_active(self, wave: Wave) -> None:
        """The floor records the wave as active (the arm effect is observable)."""
        record = self._read_floor()
        assert record.get("wave") == wave.value, (
            f"the submission hook did not record the {wave.value!r} wave as "
            f"active on the floor; the wave-active anchor seam is dormant or "
            f"misfired. {self._observed_submission()}"
        )

    def then_armed_deterministically_from_command(self) -> None:
        """The record's provenance is COMMAND (deterministic, not self-reported)."""
        record = self._read_floor()
        assert record.get("provenance") == Provenance.COMMAND.value, (
            "the wave was not armed with COMMAND provenance -- it must be written "
            "deterministically from the literal /nw-<wave>, never inferred from a "
            f"self-reported marker. got provenance={record.get('provenance')!r}. "
            f"{self._observed_submission()}"
        )

    def then_no_other_wave_active(self, wave: Wave) -> None:
        """The single pinned record names exactly the commanded wave, no other.

        The floor contract is one JSON object at one fixed path (one record per
        project), so "no other wave is active" reduces to: the single record's
        wave value equals the commanded wave -- no second wave can coexist.
        """
        record = self._read_floor()
        assert record.get("wave") == wave.value, (
            f"the single floor record names wave={record.get('wave')!r}, not the "
            f"commanded {wave.value!r}; the anchor must arm exactly the commanded "
            f"wave (one record per project). {self._observed_submission()}"
        )
        # AT-review L1: independently witness "no other wave" by enforcing the
        # pinned closed-key contract -- no extra key may smuggle a second wave
        # onto the single record (e.g. {"wave": "discuss", "extra_wave":
        # "design"}). Floor v1.1 (slice-07c): the optional anchor-owned
        # ``entry_pending`` key is IN-contract (the COMMAND arm writes it).
        extra = set(record.keys()) - {"wave", "provenance", "scope", "entry_pending"}
        assert not extra, (
            f"the floor record carries keys outside the pinned contract "
            f"{{wave, provenance, scope, entry_pending}}: {sorted(extra)!r} -- a "
            f"second wave or out-of-contract field must not leak onto the single "
            f"record. {self._observed_submission()}"
        )

    # ---- then (read + scope) ------------------------------------------------

    def then_gate_denies(self) -> None:
        """The gate DENIES the sub-dispatch (S2: bypass made loud, not silent-allow)."""
        assert self._gate_decision() is GateDecision.DENY, (
            "the gate must DENY a markerless in-wave sub-dispatch (S2 bypass made "
            f"loud); it returned {self._decision_action!r}. a wave-active read + "
            "wave-aware hinge would deny it. "
            f"{self._observed_gate()}"
        )

    def then_denial_names_bypass(self) -> None:
        """The denial reason names the wave-bypass so it cannot pass as success."""
        reason = (self._decision_reason or "").lower()
        assert any(token in reason for token in _BYPASS_TOKENS), (
            "the denial must name the wave-bypass (one of "
            f"{_BYPASS_TOKENS!r}) so it surfaces as a loud failure, not a silent "
            f"success; got reason={self._decision_reason!r}. {self._observed_gate()}"
        )

    def then_gate_allows(self) -> None:
        """The gate ALLOWS the sub-dispatch."""
        assert self._gate_decision() is GateDecision.ALLOW, (
            "the gate must ALLOW this dispatch; it returned "
            f"{self._decision_action!r}. {self._observed_gate()}"
        )

    def then_bare_dispatch_untouched(self) -> None:
        """S1 non-interference: a bare non-wave dispatch is allowed with no block reason."""
        assert self._gate_decision() is GateDecision.ALLOW, (
            "an ad-hoc non-wave dispatch must NEVER be blocked when no wave is "
            f"active (K2 zero false-positive); the gate returned "
            f"{self._decision_action!r}. {self._observed_gate()}"
        )
        assert self._decision_reason in (None, ""), (
            "the bare dispatch must be left completely untouched (no block "
            f"reason); got reason={self._decision_reason!r}. {self._observed_gate()}"
        )

    # ---- driving-port invocations -------------------------------------------

    def _run_submission_hook(self, prompt: str) -> None:
        """Run the real prompt-submission hook IN-PROCESS over its stdin protocol.

        Faithful to the JSON-hook-protocol fork it replaces: the production
        ``handle_user_prompt_submit`` no-argv handler reads the SAME ``{prompt,
        cwd}`` payload from the SAME ``sys.stdin`` contract, under ``cwd=
        project_root`` (the shared ``run_hook_in_process`` driver save/restores
        ``sys.stdin`` + ``cwd``). The result is wrapped in a ``CompletedProcess``
        so the observable readers (returncode/stdout/stderr) stay 1:1.
        """
        assert self._project_root is not None
        payload = json.dumps({"prompt": prompt, "cwd": str(self._project_root)})
        exit_code, stdout, stderr = run_hook_in_process(
            handle_user_prompt_submit,
            stdin_text=payload,
            cwd=str(self._project_root),
        )
        self._submission_completed = subprocess.CompletedProcess(
            args=[SUBMISSION_HOOK_MODULE],
            returncode=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    def _run_gate(self, prompt: str) -> None:
        """Drive the REAL PreToolUseService.validate via the production composition root.

        The service is built by the production factory (Pillar 3). The wave-active
        floor under project_root is the arranged precondition the wave-aware hinge
        reads. RED-for-right-reason: the production service has no wave-reader
        wiring at HEAD, so an armed-floor + markerless-child case returns allow()
        where the S2 AT expects DENY.
        """
        assert self._project_root is not None
        from des.adapters.drivers.hooks import service_factory
        from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput

        # The service composition reads the wave-active floor under the project
        # CWD; run with cwd=project_root so the production reader (once wired)
        # resolves the same floor the precondition seeded.
        prev_cwd = Path.cwd()
        try:
            os.chdir(self._project_root)
            service = service_factory.create_pre_tool_use_service()
            decision = service.validate(PreToolUseInput(prompt=prompt))
        finally:
            os.chdir(prev_cwd)
        self._decision_action = decision.action
        self._decision_reason = decision.reason

    # ---- observable-surface readers -----------------------------------------

    def _gate_decision(self) -> GateDecision:
        assert self._decision_action is not None, (
            "the gate must be run (When) before asserting on its decision (Then)"
        )
        return (
            GateDecision.ALLOW
            if self._decision_action == "allow"
            else GateDecision.DENY
        )

    def _read_floor(self) -> dict[str, object]:
        """Read the single wave-active record at the DESIGN-PINNED fixed path.

        Reads EXACTLY ``{project_root}/.nwave/wave-active/active.json`` -- no
        directory scan. A record the crafter's writer puts anywhere else is
        invisible here, so AT-1 fails: that is the drift this fixed-path read
        catches (one SSOT shared by the AT-seed and the production reader).

        Raises a semantic AssertionError (RED-for-right-reason) when the pinned
        file is absent / unreadable / not a JSON object, OR when a required key
        is missing / out-of-vocab (degrade-LOUD Indeterminate, never coerced to
        a quiet pass). ``scope`` is optional and not validated here.
        """
        floor_path = self._floor_file()
        if not floor_path.exists():
            raise AssertionError(
                "no wave-active record was written to the pinned floor path "
                f"{floor_path!r}; the prompt-submission anchor seam did not arm "
                f"the wave (or wrote it elsewhere -- drift). "
                f"{self._observed_submission()}"
            )
        try:
            payload = json.loads(floor_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise AssertionError(
                f"the pinned floor file {floor_path!r} is not readable JSON "
                f"({exc!r}); the wave-active contract requires a single JSON "
                f"object. {self._observed_submission()}"
            ) from exc
        if not isinstance(payload, dict):
            raise AssertionError(
                f"the pinned floor file {floor_path!r} is not a JSON object; the "
                f"wave-active contract pins a single object with wave/provenance. "
                f"{self._observed_submission()}"
            )
        wave_value = payload.get("wave")
        if wave_value not in _WAVE_VOCAB:
            raise AssertionError(
                f"the floor record's wave={wave_value!r} is missing / out of the "
                f"closed vocabulary {sorted(_WAVE_VOCAB)!r} -- a degrade-LOUD "
                f"Indeterminate, never a quiet pass. {self._observed_submission()}"
            )
        provenance_value = payload.get("provenance")
        if provenance_value not in _PROVENANCE_VOCAB:
            raise AssertionError(
                f"the floor record's provenance={provenance_value!r} is missing / "
                f"out of the closed set {sorted(_PROVENANCE_VOCAB)!r} -- a "
                f"degrade-LOUD Indeterminate. {self._observed_submission()}"
            )
        return payload

    # ---- substrate plumbing (precondition state, NOT the SUT) ---------------

    def _seed_floor(self, root: Path, wave: Wave, provenance: Provenance) -> None:
        """Seed the pinned floor record (precondition state, NOT the SUT).

        Writes exactly the DESIGN-PINNED shape: a single JSON object at
        ``.nwave/wave-active/active.json`` with required ``wave`` + ``provenance``
        (lowercase closed-vocab values) and ``scope`` OMITTED for whole-wave.
        """
        floor_path = root / _FLOOR_FILE_REL
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        floor_path.write_text(
            json.dumps({"wave": wave.value, "provenance": provenance.value}),
            encoding="utf-8",
        )

    def _floor_file(self) -> Path:
        assert self._project_root is not None
        return self._project_root / _FLOOR_FILE_REL

    def _markerless_child_prompt(self) -> str:
        """An in-wave sub-dispatch that dropped its DES wave markers."""
        return "Agent dispatch: do the discuss work (no DES markers carried)"

    def _child_prompt_with_markers(self) -> str:
        """An in-wave sub-dispatch carrying the required DES markers."""
        return (
            "DES-VALIDATION: required\n"
            "DES-PROJECT-ID: nwave-flow-v2-enforcement\n"
            "DES-PROJECT-ROOT: .\n"
            "DES-STEP-ID: discuss-1\n"
            "proceed with the discuss wave work"
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed_submission(self) -> str:
        if self._submission_completed is None:
            return "(submission hook not run)"
        c = self._submission_completed
        return (
            f"hook returncode={c.returncode}; stdout={c.stdout!r}; "
            f"stderr={c.stderr!r}; floor_file={self._floor_file()!r}"
        )

    def _observed_gate(self) -> str:
        return (
            f"decision.action={self._decision_action!r}; "
            f"decision.reason={self._decision_reason!r}; "
            f"armed_wave={self._armed_wave!r}"
        )

    # ---- state-machine doc (C2 -- AT module docstring requirement) ----------
    # SUT state machine (read+scope hinge): states = {NO_WAVE_ACTIVE, WAVE_ACTIVE}.
    #   NO_WAVE_ACTIVE --(/nw-<wave> submission)--> WAVE_ACTIVE   (arm, COMMAND)
    #   NO_WAVE_ACTIVE --(bare non-wave dispatch)--> NO_WAVE_ACTIVE (S1 allow)
    #   WAVE_ACTIVE   --(markerless in-wave child)--> WAVE_ACTIVE  (S2 DENY)
    #   WAVE_ACTIVE   --(in-wave child w/ markers)--> WAVE_ACTIVE  (allow)
    # Illegal-event-from-state: a markerless child from NO_WAVE_ACTIVE is the S1
    # allow (not a denial) -- the gate is consent-gated (D-nonintf).
    _ = WaveActiveState  # keep the typed state vocabulary referenced
