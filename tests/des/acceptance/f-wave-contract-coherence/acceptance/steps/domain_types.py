"""Typed domain vocabulary for the f-wave-contract-coherence ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum, so each composition method consumes
a typed parameter (no raw ``str`` where an enum exists). The DSL emerges from these
enums, not from decorator proliferation -- one parametrized scenario shape ranges
over each enum's members.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through the composition-root resolution seam (Mandate-13
driving-port-only).
"""

from __future__ import annotations

from enum import Enum


class WaveBoundary(Enum):
    """The two boundaries a wave's declared gate stack covers.

    ``gate-in`` is the wave-entering stack; ``gate-out`` the wave-return stack.
    The canonical wave-contract registry (ADR-FLOW-006 D2) declares
    ``gate_stack.{gate-in,gate-out}`` per wave -- the SAME ordered GateInvocation
    row schema the flavor's ``wave_gate_stacks`` block carries today.
    """

    GATE_IN = "gate-in"
    GATE_OUT = "gate-out"


class DiscussProseLocus(Enum):
    """The two shipped DISCUSS wave-prose loci the slice-03 cure re-points.

    Brief §4 + §6 name BOTH the command prose and the skill prose as the targets of
    the prose-pointer cure: each must carry the ``gates-ref``/``outputs-ref``
    pointers and drop the inline gate-id / [REF]-section restatement. The value is
    the repo-relative path the coherence-check gate scans and the maintainer edits.
    """

    COMMAND = "nWave/tasks/nw/discuss.md"
    SKILL = "nWave/skills/nw-discuss/SKILL.md"


class SectionAuthoringLocus(Enum):
    """The candidate loci that could AUTHOR the DISCUSS [REF]-section list (slice-04).

    The output-contract SSOT MOVE (ADR-FLOW-006 D3 / §C2) requires the DISCUSS
    section list to have exactly ONE authoring locus -- the canonical registry. The
    central feature-delta schema carried a second copy (the per-wave
    ``required_sections`` block); the MOVE removes it. The value is the repo-relative
    path the AT reads to count which loci still author the list.

    * ``REGISTRY`` -- ``nWave/waves/discuss.yaml output_contract.ref_sections``: the
      canonical authoring locus the MOVE keeps (authored slice-01).
    * ``CENTRAL_SCHEMA`` -- ``schemas/feature-delta-tier1-sections.yaml``
      ``waves.DISCUSS.required_sections``: the second copy the MOVE deletes. Present
      at HEAD (the RED); gone once DELIVER completes the MOVE.
    """

    REGISTRY = "nWave/waves/discuss.yaml"
    CENTRAL_SCHEMA = "schemas/feature-delta-tier1-sections.yaml"


class DiscussBootstrapLocus(Enum):
    """The two shipped DISCUSS wave-prose loci that declare greenfield bootstrap
    ownership -- the slice-05 AT-13 reconcile target.

    Brief §6 names the contradiction: ``nw-discuss`` SKILL (~:126) says "DISCUSS
    will bootstrap docs/product", while the canonical order (DISCOVER -> DIVERGE ->
    DISCUSS) makes DIVERGE the bootstrap owner -- and ``discuss.md`` itself restates
    the stale "DISCUSS will create it" promise. AT-13 asserts BOTH loci agree on the
    reconciled DIVERGE-owns-bootstrap statement (no surviving DISCUSS-bootstraps
    contradiction). The value is the repo-relative path the AT scans.
    """

    COMMAND = "nWave/tasks/nw/discuss.md"
    SKILL = "nWave/skills/nw-discuss/SKILL.md"


class FlavorGateStackLocus(Enum):
    """The two shipped flavor loci the slice-06 MOVE deletes the gate-stack from.

    Brief §7 slice-06 names BOTH the flavor instance file and the flavor schema as
    the deletion targets: the now-dead ``wave_gate_stacks`` block in
    ``atdd_pure.yaml`` AND its ``$defs`` in the flavor ``_schema.yaml`` (the schema
    that DECLARES the block's shape). The MOVE deletes the old locus -- no copy left
    behind. The value is the repo-relative path the AT reads to assert ABSENCE.

    * ``ATDD_PURE`` -- ``nWave/flavors/atdd_pure.yaml``: the flavor INSTANCE carrying
      the migrated ``wave_gate_stacks.discuss`` data (present at HEAD -> the RED).
    * ``FLAVOR_SCHEMA`` -- ``nWave/flavors/_schema.yaml``: the flavor SCHEMA whose
      ``properties.wave_gate_stacks`` ``$defs`` declares the block's shape (present
      at HEAD -> the RED).
    """

    ATDD_PURE = "nWave/flavors/atdd_pure.yaml"
    FLAVOR_SCHEMA = "nWave/flavors/_schema.yaml"


class CoherenceVerdict(Enum):
    """The §17 GateVerdict tokens the coherence-check gate emits (slice-02).

    ADR-GV-001's five existing verdicts -- the coherence-check introduces NO sixth
    (ADR-FLOW-006 D7/D9: an ordinary structural gate, no new verdict, no engine).
    The token is the gate's observable on JSON-stdout. Slice-02 asserts three of the
    five: PASS (valid pointers, zero restatement), FAIL (inline restatement found),
    INDETERMINATE (registry unreadable -- degrade-LOUD, Invariant 2).
    """

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"
