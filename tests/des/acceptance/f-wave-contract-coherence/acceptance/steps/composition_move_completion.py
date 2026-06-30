"""Composition root for f-wave-contract-coherence slice-06 (MOVE-completion).

DRIVING SURFACE (Mandate-13 driving-port-only -- shipped-artifact + real-seam reads,
no direct-domain testing):

  * Layer 3 composition (pure-seam read path) -- the REAL ``flavor_dispatcher``
    resolving the DISCUSS gate stack, read over the SHIPPED repo files
    (``nWave/flavors/*.yaml``, ``nWave/waves/*.yaml``, ``nWave/waves/_schema.yaml``,
    ``docs/product/glossary.md``). The MOVE-completion (brief §7 slice-06) DELETES
    the now-dead MIGRATED ``discuss`` sub-key from the flavor-private
    ``wave_gate_stacks`` block and makes the registry the SOLE source of the
    ``discuss`` gate stack. The observables are SHIPPED-ARTIFACT facts (Mandate-13
    protocol-driver: assert a shipped artifact, never a string the test fabricated):
      - the flavor file NO LONGER declares a ``discuss`` gate stack, WHILE the
        block itself + its flavor-schema ``$defs`` PERSIST for the ``distill``
        co-tenant (AT-15 -- see CO-TENANT note below),
      - classic never carried it (AT-16),
      - the dispatcher resolves the DISCUSS stack FROM the registry with NO flavor
        block to fall back to, preserving the f-declarative-gate-composition gate
        sequence (AT-17),
      - the registry schema reserves the ``overrides`` hook + the glossary defines
        the three new terms (AT-18).

  ### CO-TENANT note (AT-15 NARROWED, not weakened -- CodeFactPort verified) ###

  f-wave-contract-coherence owns ONLY the ``discuss`` wave contract. The flavor
  ``wave_gate_stacks`` block in ``atdd_pure.yaml`` hosts TWO waves:

    * ``discuss`` -- migrated to the canonical registry by THIS feature; its flavor
      entry is dead config after slice-06 re-points the reader -> AT-15 deletes it.
    * ``distill`` (gate-g / self-attest / verify-test-runner) -- WIRED by a DIFFERENT
      feature, f-coherence-and-attestation slice-06 (JOB-028, flavor lines 192-208).
      Verified via Tsunami + reads: that ``distill`` wiring lives ONLY in this flavor
      block -- it is NOT in the registry (``nWave/waves/discuss.yaml`` carries only the
      ``discuss`` gate_stack) and NOT in lifecycle_events. The closure scorecard's
      ``_term_wired`` (``scripts/flow_v2_closure_scorecard.py``) scans ``WIRING_FILES``
      = ``nWave/flavors/*.yaml`` + hooks for the patterns ``gate.?g`` / ``self.?attest``
      / ``test.?runner`` -- they match SOLELY because of this flavor block.

  => Deleting the WHOLE ``wave_gate_stacks`` block (or its ``$defs``) would make
     f-coherence-and-attestation's three gate patterns ``wired=False`` -> a DONE /
     attested feature would REGRESS from ``YES wired`` to dormant. So AT-15 asserts
     the ``discuss`` ENTRY is removed WHILE the block + its schema ``$defs`` SURVIVE
     to host the ``distill`` co-tenant (which keeps its own flavor wiring until its
     OWN future registry migration). This is the MOVE scoped to what THIS feature
     owns -- narrowed to the ``discuss`` sub-key, not weakened.

No production module is imported-and-called at the step boundary for its business
logic -- the assertions parse SHIPPED repo files via the SAME production stdlib-only
subset parser the dispatcher uses, and AT-17 drives the REAL ``flavor_dispatcher``
registry-resolution seam over the shipped registry.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): slice-06 introduces NO net-new
load-bearing production seam -- it is a MOVE-completion (DELETE the dead flavor
locus + add a reserved DATA hook + glossary prose). The load-bearing seam it
DEPENDS on (the dispatcher reading the gate stack FROM the registry, brief §2 / D6)
is the slice-01 seam; AT-17 witnesses THAT seam reaching the registry with NO flavor
fallback -- the behavioral guarantee f-declarative-gate-composition owns, now
sourced from the moved location.

  ### CRITICAL DELIVER BLOCKER (CodeFactPort, Tsunami tier-1 binding-resolved) ###

  The brief §7 slice-06 row asserts "slice-01 already re-pointed the reader, so this
  is dead config". The CodeFactPort resolution at DISTILL time CONTRADICTS that
  premise -- the flavor block is NOT dead yet:

    * `reads-of wave_gate_stacks`  -> read ONLY inside
      flavor_dispatcher.resolve_wave_gate_stack (flavor_dispatcher.py:323,325).
    * `callers-of resolve_wave_gate_stack` (incl. transitive) -> the AST-resolved
      production caller is wave_gate_stack_dispatch.py:65 (`resolve_stack` ->
      `des.application.flavor_dispatcher.resolve_wave_gate_stack`, confirmed via
      atoms_in_file on wave_gate_stack_dispatch.py). The spine STILL reads the
      flavor block.
    * `callers-of resolve_wave_gate_stack_from_registry` -> EMPTY. The slice-01
      registry-sourced resolver is NEVER-WIRED in production -- its only reader is
      the slice-01 AT. slice-01 ADDED the registry read path but did NOT re-point
      the spine consumer (`resolve_stack`) to it.

  => Deleting the flavor `wave_gate_stacks` block at slice-06 WITHOUT first
     re-pointing `wave_gate_stack_dispatch.resolve_stack` to read the registry
     WOULD BREAK the spine (the DISCUSS stack would vanish: `resolve_wave_gate_stack`
     returns the empty list once the block is gone). This is a HARD BLOCKER the
     DELIVER crafter MUST close as part of slice-06 (re-point `resolve_stack` to the
     registry resolver BEFORE deleting the flavor block -- the MOVE order brief §7
     mandates: registry authored (slice-01) -> consumer re-pointed + green ->
     old locus deleted -> breadth-suite green). AT-17 is the witness: it drives the
     REAL registry resolution with NO flavor block and asserts the DISCUSS sequence
     is preserved -- it stays RED until the spine reads the registry.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the flavor ``discuss`` entry is
STILL present (AT-15 RED -- DELIVER deletes the ``discuss`` sub-key while keeping the
block + ``$defs`` for the ``distill`` co-tenant), the registry-sourced resolution is
not the spine source and the registry overrides/glossary terms are partly present
(AT-17/AT-18 RED for the spine-re-point / glossary). Every Then fires a semantic
``AssertionError`` naming the surviving ``discuss`` entry / missing re-point / missing
term -- never a collection / import / setup error.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import FlavorGateStackLocus, WaveBoundary


# tests/des/acceptance/f-wave-contract-coherence/acceptance/steps/<this file>
#   parents[6] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[6]

# SHIPPED registry + flavor + glossary loci (ADR-FLOW-006 D1/D5/D6, §C3).
_WAVES_DIR = REPO_ROOT / "nWave" / "waves"
_DISCUSS_REGISTRY_FILE = _WAVES_DIR / "discuss.yaml"
_WAVES_SCHEMA_FILE = _WAVES_DIR / "_schema.yaml"
_FLAVORS_DIR = REPO_ROOT / "nWave" / "flavors"
_CLASSIC_FLAVOR_FILE = _FLAVORS_DIR / "classic.yaml"
_GLOSSARY_FILE = REPO_ROOT / "docs" / "product" / "glossary.md"

_DISCUSS_WAVE = "discuss"
_ATDD_PURE = "atdd_pure"

# The three glossary terms ADR-FLOW-006 §C3 mandates be ADDED (verified absent today).
# Each is a discriminating multi-word phrase, NOT a substring of a common word
# (Mandate-13 prose-surface case: avoid false-positive markers like "table").
_GLOSSARY_TERMS = ("wave-contract-registry", "gates-ref", "outputs-ref")


@dataclass
class MoveCompletionComposition:
    """Drives the MOVE-completion assertions over SHIPPED repo artifacts + the REAL seam."""

    _flavor_declares_discuss: bool | None = field(default=None)
    _flavor_block_survives: bool | None = field(default=None)
    _flavor_schema_defs_survives: bool | None = field(default=None)
    # CT-9 (slice-02 of f-distill-wiring-to-registry): the post-MOVE registry facts.
    _distill_cotenant_in_registry: bool | None = field(default=None)
    _registry_distill_gate_ids: tuple[str, ...] | None = field(default=None)
    _classic_has_block_before: bool | None = field(default=None)
    _classic_has_block_after: bool | None = field(default=None)
    _resolved_boundary: WaveBoundary | None = field(default=None)
    _spine_sequence: tuple[str, ...] | None = field(default=None)
    _guaranteed_sequence: tuple[str, ...] | None = field(default=None)
    _registry_sourced: bool | None = field(default=None)
    _tmp_path: Path | None = field(default=None)
    _schema_reserves_overrides: bool | None = field(default=None)
    _glossary_missing_terms: tuple[str, ...] | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_registry_is_sole_gate_stack_source(self) -> None:
        """Arm the SUT to read the SHIPPED registry/flavor/schema/glossary files.

        No fixture authoring of the expected output -- the SHIPPED files (or the
        survival of the dead block in them) are the contract under test
        (Mandate-13 protocol-driver: assert a shipped artifact, never a fabricated
        string). At HEAD the flavor block survives -> the ABSENCE assertions are RED.
        """
        # Nothing to set up beyond pointing at the shipped paths -- the files
        # themselves are the contract under test.

    # ---- when: AT-15 (post-MOVE: block gone, co-tenant migrated to registry) --

    def when_maintainer_inspects_flavor_block_and_schema(self) -> None:
        """Read the SHIPPED flavor + schema + registry for the post-MOVE-completion facts.

        AT-15 PREMISE-UPDATE (f-distill-wiring-to-registry slice-02, CT-9 / DDD-9):
        slice-01 of f-distill-wiring-to-registry COMPLETED the migration AT-15
        anticipated -- it REMOVED the flavor ``wave_gate_stacks`` block (its last
        co-tenant, ``distill``, moved to the canonical registry
        ``nWave/waves/distill.yaml`` gate-out: self-attest + verify-test-runner). So
        the original SURVIVE-assertions (block survives / $defs survives / block hosts
        distill) are now FALSE-of-the-world. AT-15 is re-pointed to assert the NEW true
        state. It records FOUR shipped-artifact / real-resolution facts (Mandate-13
        protocol-driver -- assert a shipped artifact / an observed effect):
          * does ``atdd_pure.yaml`` still declare a ``discuss`` gate stack under
            ``wave_gate_stacks`` (the migrated entry -- must be GONE, GREEN post-MOVE),
          * does the ``wave_gate_stacks`` block itself SURVIVE (it must NOT -- the MOVE
            removed it once the last co-tenant migrated; ``_flavor_block_survives`` False),
          * does the flavor schema ``$defs`` (``properties.wave_gate_stacks``) SURVIVE
            (it must NOT -- DDD-9 removes the dead schema for the deleted block; at HEAD
            it is STILL present -> the leg-c active-RED DELIVER closes),
          * do the ``distill`` co-tenant gates now resolve from the LIVE registry --
            ``resolve_stack("distill","gate-out")`` carries ``self-attest`` +
            ``verify-test-runner`` (the gates the flavor block formerly hosted; the
            migrated-to-registry witness).
        """
        self._flavor_declares_discuss = self._flavor_block_declares_wave(_DISCUSS_WAVE)
        self._flavor_block_survives = self._flavor_block_present()
        self._flavor_schema_defs_survives = self._flavor_schema_defs_present()
        gate_ids = self._registry_distill_gate_out_ids()
        self._registry_distill_gate_ids = gate_ids
        self._distill_cotenant_in_registry = (
            "self-attest" in gate_ids and "verify-test-runner" in gate_ids
        )

    # ---- when: AT-16 (classic inspection) ------------------------------------

    def when_maintainer_inspects_classic_flavor(self) -> None:
        """Read the SHIPPED classic flavor; classic never carried the block (FA-3).

        Classic has NO wave_gate_stacks today (verified) -> the MOVE is additive for
        classic. This reads classic both as the "before" and "after" fact -- the MOVE
        touches only the registry + atdd_pure, never classic.
        """
        carries = self._classic_carries_block()
        self._classic_has_block_before = carries
        self._classic_has_block_after = carries

    # ---- when: AT-17 (registry-sourced resolution, no flavor fallback) -------

    def when_dispatcher_resolves_discuss_stack_with_no_flavor_block(
        self, boundary: WaveBoundary, tmp_path: Path
    ) -> None:
        """Drive the REAL SPINE gate-stack resolver with the flavor block ABSENT.

        AT-17 witnesses the behavioral guarantee f-declarative-gate-composition owns
        (select -> iterate-in-declared-order) sourced from the MOVED location. The
        SUT is the REAL spine entry point ``wave_gate_stack_dispatch.resolve_stack``
        (the function PreToolUseService / SubagentStopService call to resolve a
        wave's declared stack) -- NOT the isolated slice-01 registry helper. Driving
        the isolated helper would be a tautology (two reads of the same registry,
        both already green from slice-01); driving the SPINE resolver is the real
        witness that the MOVE re-points the live consumer.

        To express "no flavor block present" WITHOUT mutating the shipped flavor
        file, point the spine's flavors-dir override (``NWAVE_FLAVORS_DIR``, honored
        by ``wave_gate_stack_dispatch.shipped_flavors_dir``) at a temp flavor that
        carries everything EXCEPT ``wave_gate_stacks`` (the post-MOVE world). Then:

          * if the spine STILL reads the flavor block (today, via
            ``resolve_wave_gate_stack`` over the temp flavor) -> it resolves EMPTY
            (the temp flavor has no block) -> registry_sourced=False -> RED.
          * once the crafter re-points ``resolve_stack`` to the registry resolver
            (the CRITICAL BLOCKER) -> the spine resolves the DISCUSS sequence FROM
            the registry even with no flavor block -> registry_sourced=True -> GREEN.

        Anti-tautology cross-check (§22.0 HIGH): the expected sequence is read AT
        RUNTIME from the SHIPPED registry ``gate_stack`` (the SSOT the MOVE keeps) --
        a SEPARATE read from the spine resolution, never a hardcoded constant.
        """
        self._resolved_boundary = boundary
        self._tmp_path = tmp_path
        self._spine_sequence, self._registry_sourced = (
            self._resolve_sequence_via_spine_without_flavor_block(boundary, tmp_path)
        )
        self._guaranteed_sequence = self._sequence_guaranteed_by_dgc(boundary)

    # ---- when: AT-18 (overrides hook + glossary) -----------------------------

    def when_maintainer_inspects_schema_and_glossary(self) -> None:
        """Read the SHIPPED registry schema + product glossary for the reserved hook + terms."""
        self._schema_reserves_overrides = self._registry_schema_reserves_overrides()
        self._glossary_missing_terms = self._glossary_terms_missing()

    # ---- then: AT-15 ---------------------------------------------------------

    def then_flavor_block_no_longer_declares_discuss(self) -> None:
        """The flavor wave_gate_stacks block has DELETED the migrated ``discuss`` entry.

        Seam-named oracle (MOVE-completion, NARROWED to what THIS feature owns): the
        flavor block carries no ``discuss`` gate stack -- the old authoring locus for
        the DISCUSS contract is gone, no copy left behind (Ale bloat-removal
        MOVE-not-COPY); the DISCUSS gate stack lives ONCE in the canonical registry
        ``nWave/waves/discuss.yaml`` (ADR-FLOW-006 D6). RED at HEAD: the ``discuss``
        entry survives -> semantic AssertionError naming it.
        """
        assert self._flavor_declares_discuss is False, (
            "the flavor wave_gate_stacks block in atdd_pure.yaml must NO LONGER declare "
            "a `discuss` gate stack -- slice-06 completes the MOVE by deleting the now-dead "
            "flavor `discuss` entry (the DISCUSS gate stack lives ONCE in the canonical "
            "registry nWave/waves/discuss.yaml, ADR-FLOW-006 D6); it still declares it "
            f"(declares_discuss={self._flavor_declares_discuss!r}). {self._observed()}"
        )

    def then_distill_cotenant_migrated_to_registry(self) -> None:
        """The flavor block is GONE and the ``distill`` co-tenant resolves from the registry.

        PREMISE-UPDATE oracle (f-distill-wiring-to-registry slice-02, CT-9 / DDD-9):
        AT-15 was authored with an explicit caveat -- the flavor ``wave_gate_stacks``
        block + its ``$defs`` PERSIST to host the ``distill`` co-tenant *(pending
        f-coherence's own future registry migration)* (move-completion.feature:38).
        slice-01 of f-distill-wiring-to-registry IS that migration: it removed the
        block and MOVE-completed the ``distill`` co-tenant (self-attest +
        verify-test-runner) into the canonical registry ``nWave/waves/distill.yaml``
        gate-out -- the SOLE resolved surface (ADR-FLOW-006 D6). AT-15 is re-pointed to
        the migrated-to-registry truth it foresaw -- this is the test honoring the
        change AT-15 itself anticipated (NOT a re-opening of f-wave; see the feature-delta
        §[REF] f-wave stays DONE). Three legs:

          (a) the flavor ``wave_gate_stacks`` block is ABSENT -- GREEN post-MOVE (slice-01
              removed it),
          (b) the ``distill`` co-tenant resolves from the LIVE registry --
              ``resolve_stack("distill","gate-out")`` carries self-attest +
              verify-test-runner -- GREEN post-MOVE (slice-01 wired them),
          (c) the dead flavor schema ``$defs`` (``properties.wave_gate_stacks``) is
              REMOVED -- the leg-c active-RED: at HEAD the ``$defs`` is STILL present
              (a kept-for-a-deleted-block dangling oracle); DDD-9 removes it (no dead
              schema for a deleted feature, bloat-removal / MOVE-not-COPY -- the SF
              override seam is the registry's reserved ``overrides`` hook, not the
              flavor-local ``$defs``). DELIVER closes this leg.
        """
        assert self._flavor_block_survives is False, (
            "the flavor wave_gate_stacks block in atdd_pure.yaml must be ABSENT post-MOVE "
            "-- f-distill-wiring-to-registry slice-01 removed it once its last co-tenant "
            "(`distill`) migrated to the canonical registry nWave/waves/distill.yaml "
            "(ADR-FLOW-006 D6, MOVE-not-COPY); the block still survives "
            f"(block_survives={self._flavor_block_survives!r}). {self._observed()}"
        )
        gate_ids = self._registry_distill_gate_ids or ()
        assert self._distill_cotenant_in_registry is True, (
            "the `distill` co-tenant (self-attest + verify-test-runner) the flavor block "
            "formerly hosted must now resolve from the LIVE registry -- "
            "`resolve_stack('distill','gate-out')` must carry BOTH gate_ids "
            "(f-distill-wiring-to-registry slice-01 wired them as the registry HOME, "
            f"ADR-FLOW-006 D6); resolved gate_ids={gate_ids!r}. {self._observed()}"
        )
        assert self._flavor_schema_defs_survives is False, (
            "the dead flavor schema _schema.yaml properties.wave_gate_stacks $defs must "
            "be REMOVED -- with the wave_gate_stacks block deleted and its last co-tenant "
            "migrated to the registry, the $defs is dead schema for a deleted block (DDD-9 "
            "bloat-removal / MOVE-not-COPY; the SF per-flavor override seam is the "
            "registry's reserved `overrides` hook, ADR-FLOW-006 D5, NOT the flavor-local "
            f"$defs). It is STILL present (defs_survives={self._flavor_schema_defs_survives!r}) "
            f"-- DELIVER removes it (the leg-c active-RED). {self._observed()}"
        )

    # ---- then: AT-16 ---------------------------------------------------------

    def then_classic_carries_no_wave_gate_stacks(self) -> None:
        """Classic never carried the block; the MOVE is additive for classic (FA-3)."""
        assert self._classic_has_block_before is False, (
            "the classic flavor must carry NO wave_gate_stacks declaration -- it never "
            "did (FA-3 non-regression: the MOVE is additive for classic, ADR-FLOW-006 "
            f"D6); got carries={self._classic_has_block_before!r}. {self._observed()}"
        )
        assert self._classic_has_block_after is False, (
            "the classic flavor must remain free of any wave_gate_stacks declaration "
            f"after the MOVE; got carries={self._classic_has_block_after!r}. "
            f"{self._observed()}"
        )

    # ---- then: AT-17 ---------------------------------------------------------

    def then_registry_sourced_sequence_equals_dgc_guarantee(
        self, boundary: WaveBoundary
    ) -> None:
        """The registry-sourced DISCUSS sequence preserves the DGC behavioral guarantee.

        Seam-named oracle (behavior-preservation, the f-declarative-gate-composition
        guarantee): with NO flavor block present, the dispatcher resolves the DISCUSS
        stack FROM the registry and the ordered gate-id sequence equals the sequence
        f-declarative-gate-composition's ATs guarantee (select -> iterate-in-order).
        Behavior preserved, location moved (ADR-DGC-001 location-supersession).

        RED at HEAD: the spine reader (wave_gate_stack_dispatch.resolve_stack) still
        sources the flavor block, and the registry resolver is never-wired -- so a
        resolution sourced ONLY from the registry is not yet the live behavior. The
        crafter must re-point resolve_stack to the registry resolver (the CRITICAL
        BLOCKER above) AND the registry must carry the migrated sequence. GREEN once
        both hold.
        """
        assert self._resolved_boundary is boundary, (
            f"Then boundary {boundary.value!r} must match the boundary resolved in "
            f"When ({self._resolved_boundary.value if self._resolved_boundary else None!r})"
            " -- scenario-outline wiring drift"
        )
        assert self._registry_sourced is True, (
            f"the REAL spine resolver wave_gate_stack_dispatch.resolve_stack must "
            f"resolve the DISCUSS {boundary.value} stack FROM the canonical registry "
            "as the SOLE source even with NO flavor wave_gate_stacks block present "
            "(ADR-FLOW-006 D6) -- it resolved EMPTY against a flavor with no block, so "
            "the spine consumer still reads the flavor block and is NOT yet re-pointed "
            "to the registry resolver (see CRITICAL DELIVER BLOCKER). "
            f"{self._observed()}"
        )
        expected = self._guaranteed_sequence or ()
        assert expected, (
            "the f-declarative-gate-composition guaranteed DISCUSS "
            f"{boundary.value} sequence must be readable from the registry gate_stack "
            "(the SSOT the MOVE keeps); it resolved empty -- the registry does not "
            f"carry the migrated sequence. {self._observed()}"
        )
        assert self._spine_sequence == expected, (
            f"the spine-resolved DISCUSS {boundary.value} gate-id sequence (sourced "
            "from the registry, no flavor block) must equal the sequence "
            "f-declarative-gate-composition guarantees (behavior preserved, location "
            f"moved -- ADR-DGC-001); expected {expected!r}, resolved "
            f"{self._spine_sequence!r}. {self._observed()}"
        )

    # ---- then: AT-18 ---------------------------------------------------------

    def then_overrides_hook_and_glossary_terms_present(self) -> None:
        """The registry schema reserves the overrides hook AND the glossary defines the terms."""
        assert self._schema_reserves_overrides is True, (
            "the registry schema nWave/waves/_schema.yaml must RESERVE an `overrides` "
            "hook (ADR-FLOW-006 D5: the SF per-flavor override seam, schema-valid but "
            "unused by OSS) so a future flavor override is additive, not a schema "
            f"break; the schema does not reserve it. {self._observed()}"
        )
        missing = self._glossary_missing_terms or ()
        assert not missing, (
            "the product glossary docs/product/glossary.md must DEFINE the three new "
            f"wave-contract vocabulary terms {_GLOSSARY_TERMS!r} (ADR-FLOW-006 §C3, "
            "cross-referencing gate-IN/gate-OUT, gate-pair, feature-delta); missing: "
            f"{missing!r}. {self._observed()}"
        )

    # ---- shipped-artifact readers (the REAL parse / resolution paths) --------

    def _registry_distill_gate_out_ids(self) -> tuple[str, ...]:
        """The gate_ids the REAL spine resolves for the DISTILL gate-out stack (CT-9 leg b).

        Drives the REAL spine resolver ``wave_gate_stack_dispatch.resolve_stack`` over
        the SHIPPED registry ``nWave/waves/distill.yaml`` (the SOLE resolved surface,
        ADR-FLOW-006 D6) -- the same Layer-3 composition seam AT-17 drives. The
        ``distill`` co-tenant the flavor block formerly hosted (self-attest +
        verify-test-runner) must now appear here (f-distill-wiring-to-registry slice-01
        registry HOME). Degrades to an empty tuple if resolution fails -> the Then names
        the missing co-tenant.
        """
        from des.application import wave_gate_stack_dispatch

        try:
            stack = wave_gate_stack_dispatch.resolve_stack("distill", "gate-out")
        except (KeyError, ValueError, FileNotFoundError):
            return ()
        return tuple(
            str(row["gate_id"])
            for row in (stack or [])
            if isinstance(row, dict) and "gate_id" in row
        )

    def _flavor_block_declares_wave(self, wave: str) -> bool:
        """Whether atdd_pure.yaml's wave_gate_stacks block declares ``wave`` as a sub-key.

        Parsed via the production subset parser (the SAME reader the dispatcher uses).
        ``discuss`` is the migrated entry the MOVE deletes; ``distill`` is the co-tenant
        that must survive.
        """
        doc = self._parse_yaml(REPO_ROOT / FlavorGateStackLocus.ATDD_PURE.value)
        if not isinstance(doc, dict):
            return False
        block = doc.get("wave_gate_stacks")
        return isinstance(block, dict) and wave in block

    def _flavor_block_present(self) -> bool:
        """Whether atdd_pure.yaml still carries a (non-empty) wave_gate_stacks block."""
        doc = self._parse_yaml(REPO_ROOT / FlavorGateStackLocus.ATDD_PURE.value)
        if not isinstance(doc, dict):
            return False
        block = doc.get("wave_gate_stacks")
        return isinstance(block, dict) and bool(block)

    def _flavor_schema_defs_present(self) -> bool:
        """Whether the flavor schema declares properties.wave_gate_stacks ($defs hosting)."""
        doc = self._parse_yaml(REPO_ROOT / FlavorGateStackLocus.FLAVOR_SCHEMA.value)
        if not isinstance(doc, dict):
            return False
        props = doc.get("properties")
        return isinstance(props, dict) and "wave_gate_stacks" in props

    def _classic_carries_block(self) -> bool:
        doc = self._parse_yaml(_CLASSIC_FLAVOR_FILE)
        return isinstance(doc, dict) and "wave_gate_stacks" in doc

    def _resolve_sequence_via_spine_without_flavor_block(
        self, boundary: WaveBoundary, tmp_path: Path
    ) -> tuple[tuple[str, ...], bool]:
        """Drive the REAL spine resolver with a flavor that has NO wave_gate_stacks.

        The SUT is ``wave_gate_stack_dispatch.resolve_stack`` -- the function the spine
        services call to resolve a wave's declared stack. It honors the
        ``NWAVE_FLAVORS_DIR`` env override (via ``shipped_flavors_dir``). We stage a
        temp flavor dir holding a copy of ``atdd_pure.yaml`` with the
        ``wave_gate_stacks`` block STRIPPED (the post-MOVE world), point the override
        at it, and call ``resolve_stack``.

        Returns (sequence, sourced):
          * TODAY ``resolve_stack`` reads the flavor block -> over the stripped flavor
            it resolves EMPTY -> sourced=False (RED: the spine is not registry-sourced).
          * once re-pointed to the registry resolver -> it resolves the DISCUSS
            sequence from the registry even with no flavor block -> sourced=True.
        """
        from des.application import wave_gate_stack_dispatch

        flavors_dir = self._stage_flavor_without_block(tmp_path)
        if flavors_dir is None:
            return (), False
        prev = os.environ.get("NWAVE_FLAVORS_DIR")
        os.environ["NWAVE_FLAVORS_DIR"] = str(flavors_dir)
        try:
            try:
                stack = wave_gate_stack_dispatch.resolve_stack(
                    _DISCUSS_WAVE, boundary.value
                )
            except (KeyError, ValueError, FileNotFoundError):
                return (), False
        finally:
            if prev is None:
                os.environ.pop("NWAVE_FLAVORS_DIR", None)
            else:
                os.environ["NWAVE_FLAVORS_DIR"] = prev
        seq = tuple(
            str(row["gate_id"])
            for row in (stack or [])
            if isinstance(row, dict) and "gate_id" in row
        )
        return seq, bool(seq)

    def _stage_flavor_without_block(self, tmp_path: Path) -> Path | None:
        """Stage a temp flavors dir holding atdd_pure.yaml with wave_gate_stacks removed.

        Reads the SHIPPED atdd_pure flavor as text and writes a copy with the
        top-level ``wave_gate_stacks:`` block excised -- the post-MOVE flavor shape.
        No production output is fabricated; the temp file is the post-MOVE flavor the
        spine reads, the registry (untouched, shipped) is the source the re-pointed
        spine must reach.
        """
        src = _FLAVORS_DIR / f"{_ATDD_PURE}.yaml"
        if not src.is_file():
            return None
        stripped = self._strip_top_level_block(
            src.read_text(encoding="utf-8"), "wave_gate_stacks"
        )
        flavors_dir = tmp_path / "flavors"
        flavors_dir.mkdir(parents=True, exist_ok=True)
        (flavors_dir / f"{_ATDD_PURE}.yaml").write_text(stripped, encoding="utf-8")
        return flavors_dir

    @staticmethod
    def _strip_top_level_block(text: str, key: str) -> str:
        """Excise a top-level ``key:`` block (the key line + its indented body).

        A top-level block starts at column 0 with ``key:`` and runs until the next
        column-0 non-blank, non-comment line. Removes that span so the resulting
        flavor carries everything EXCEPT the named block (the post-MOVE shape).
        """
        lines = text.splitlines(keepends=True)
        out: list[str] = []
        skipping = False
        for line in lines:
            stripped = line.rstrip("\n")
            at_col0 = bool(stripped) and not stripped[0].isspace()
            if skipping:
                # Stop skipping at the next column-0 line that is NOT a comment.
                if at_col0 and not stripped.lstrip().startswith("#"):
                    skipping = False
                else:
                    continue
            if at_col0 and stripped.split(":", 1)[0].strip() == key:
                skipping = True
                continue
            out.append(line)
        return "".join(out)

    def _sequence_guaranteed_by_dgc(self, boundary: WaveBoundary) -> tuple[str, ...]:
        """The DISCUSS gate-id sequence f-declarative-gate-composition guarantees.

        Read AT RUNTIME from the SHIPPED canonical registry gate_stack (the SSOT the
        MOVE keeps -- f-declarative-gate-composition's behavior is now sourced from
        here). NOT a hardcoded constant: AT-17 cross-checks two independent reads
        (the dispatcher's registry resolution vs the registry file's declared
        sequence). At HEAD the registry already carries the migrated stack (shipped
        slice-01), so this read is LIVE; the RED of AT-17 comes from the spine side
        (the registry resolver is not yet the spine source).
        """
        doc = self._parse_yaml(_DISCUSS_REGISTRY_FILE)
        if not isinstance(doc, dict):
            return ()
        gate_stack = doc.get("gate_stack")
        if not isinstance(gate_stack, dict):
            return ()
        rows = gate_stack.get(boundary.value)
        if not isinstance(rows, list):
            return ()
        return tuple(
            str(row["gate_id"])
            for row in rows
            if isinstance(row, dict) and "gate_id" in row
        )

    def _registry_schema_reserves_overrides(self) -> bool:
        """Whether nWave/waves/_schema.yaml reserves an `overrides` property hook."""
        doc = self._parse_yaml(_WAVES_SCHEMA_FILE)
        if not isinstance(doc, dict):
            return False
        props = doc.get("properties")
        return isinstance(props, dict) and "overrides" in props

    def _glossary_terms_missing(self) -> tuple[str, ...]:
        """The mandated glossary terms NOT yet present in the shipped glossary.

        Reads the REAL shipped docs/product/glossary.md (not an inline string). Each
        term is a discriminating multi-word/kebab phrase (Mandate-13 prose-surface:
        no common-word substring false positives).
        """
        if not _GLOSSARY_FILE.is_file():
            return _GLOSSARY_TERMS
        text = _GLOSSARY_FILE.read_text(encoding="utf-8")
        return tuple(term for term in _GLOSSARY_TERMS if term not in text)

    @staticmethod
    def _parse_yaml(path: Path) -> dict[str, object] | None:
        """Parse a SHIPPED YAML file via the production stdlib-only subset parser.

        Uses the SAME parser the dispatcher reads flavor/registry files with
        (``des._internal.subset_parser``) -- the production reader, not a test-local
        YAML parser; the AT exercises the real parse path.
        """
        if not path.is_file():
            return None
        # mandate-13-ok: production subset parser, not a test-local YAML reader.
        from des._internal import subset_parser

        try:
            doc = subset_parser.load_file(path)
        except (ValueError, OSError):
            return None
        return doc if isinstance(doc, dict) else None

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"flavor_declares_discuss={self._flavor_declares_discuss!r}; "
            f"flavor_block_survives={self._flavor_block_survives!r}; "
            f"flavor_schema_defs_survives={self._flavor_schema_defs_survives!r}; "
            f"distill_cotenant_in_registry={self._distill_cotenant_in_registry!r}; "
            f"registry_distill_gate_ids={self._registry_distill_gate_ids!r}; "
            f"classic_block={self._classic_has_block_before!r}; "
            f"resolved_boundary={self._resolved_boundary!r}; "
            f"spine_seq={self._spine_sequence!r}; "
            f"registry_sourced={self._registry_sourced!r}; "
            f"guaranteed_seq={self._guaranteed_sequence!r}; "
            f"schema_overrides={self._schema_reserves_overrides!r}; "
            f"glossary_missing={self._glossary_missing_terms!r}"
        )
