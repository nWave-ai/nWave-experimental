"""Typed domain vocabulary for mode-registry-single-locus slice-05.

The SSOT-via-Types-Services-DSL mandate, criterion 1 — every domain noun the
slice-05 Gherkin speaks has a typed home here. Shared nouns are IMPORTED from
the earlier slices' modules (one definition per concept, never re-declared):
`WorkflowFlavor` comes from the slice-01 vocabulary; `RegionId` from slice-02.

Slice-05 is the GUARDRAIL slice: it elevates the slices-02/03 `docgen --check`
from an existing check to a WIRED DES gate, and adds the two new mechanical
gates that make the NEXT mode shotgun-surgery STRUCTURALLY IMPOSSIBLE. Its
nouns are the three orthogonal, Python-only, git-free gate teeth (analysis §3):

  * Layer A — `mode-locus-gate`: no naked mode literal outside a GENERATED
    region or a `<!-- mode-ref-ok -->` allow-marker (analysis §3.1). The
    bare-`classic` disambiguation DECISION is pinned here as DATA (see
    `BARE_CLASSIC_RULE` below) — `classic` flags ONLY in config/declaration
    shapes; bare English AND descriptive prose (`classic mode`/`classic-mode`,
    17 legitimate documentation lines, slice-04 KEEP) pass. Empirical corpus
    anchor restated in the constant.
  * Layer B — `mode-registry-completeness`: the schema-required 4-tuple
    fields, exactly one `default: true`, every `skill_load_set` agent exists,
    no conflicting `selection` (analysis §3.2). Half-declared mode → refused
    naming the defect.
  * Layer C — `docgen --check` resolver↔registry agreement + projection==source
    (analysis §3.3): the resolver's absent-config default MUST equal the flavor
    with `default: true`, AND the runtime canonical DELIVER phase shape MUST
    equal the registry's `deliver_phase_shape` for the default flavor — the
    registry↔runtime parity that CLOSES the KEEP-row-10 open leg of
    `tests/des/acceptance/atdd_pure_phase_count_slice03`.

The WIRING witness (the dormant-seam lesson, D11 / S3): each gate is driven
through its REAL `des <gate-id>` entry (proving the `__main__.py:_REGISTRY`
dispatch row exists) AND the catalog 1:1-mirror is asserted to declare it (no
dormant gate CLI — a CLI reachable from the dispatcher but absent from the
catalog, or vice-versa, would break the shipped arch test). Layer C reuses the
already-shipped `scripts/docgen.py --check` entry.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from .domain_types_slice_01 import WorkflowFlavor
from .domain_types_slice_02 import RegionId


__all__ = [
    "ALLOW_MARKER",
    "BARE_CLASSIC_RULE",
    "BENIGN_CLASSIC_SAMPLES",
    "CATALOG_REL",
    "FLAVORS_REL",
    "GATE_BY_PHRASE",
    "LAYER_A_GATE_ID",
    "LAYER_B_GATE_ID",
    "NAKED_LITERAL_SENTINEL",
    "REGISTRY_DEFECT_BY_PHRASE",
    "GateUnderTest",
    "RegionId",
    "RegistryCompletenessDefect",
    "WorkflowFlavor",
]


# --- Repo-relative anchors ----------------------------------------------------

FLAVORS_REL = Path("nWave") / "flavors"
CATALOG_REL = Path("nWave") / "gates" / "_catalog.yaml"


# --- The three gates under test (the wiring witness names them) ---------------

LAYER_A_GATE_ID = "mode-locus-gate"
LAYER_B_GATE_ID = "mode-registry-completeness"


class GateUnderTest(Enum):
    """The three orthogonal guardrail gates (analysis §3.1-§3.3).

    Each carries the `des <gate-id>` subcommand name it is reachable through
    (Layer A/B are net-new DES gates; Layer C is the already-shipped
    `scripts/docgen.py --check`, driven by file path not by `des`-subcommand).
    """

    LAYER_A_LOCUS = "mode-locus-gate"
    LAYER_B_COMPLETENESS = "mode-registry-completeness"
    LAYER_C_AGREEMENT = "docgen-check"


GATE_BY_PHRASE: dict[str, GateUnderTest] = {
    "the no-naked-mode-literal gate": GateUnderTest.LAYER_A_LOCUS,
    "the registry-completeness gate": GateUnderTest.LAYER_B_COMPLETENESS,
    "the projection-and-resolver-agreement gate": GateUnderTest.LAYER_C_AGREEMENT,
}


# --- Layer A: the bare-`classic` disambiguation DECISION, pinned as DATA -------

NAKED_LITERAL_SENTINEL = "atdd_pure"
"""The unambiguous literal the Layer-A teeth scenario plants by hand outside a
GENERATED region / allow-marker — `atdd_pure` has no benign English sense, so
its bare presence is unconditionally the duplication smell."""

ALLOW_MARKER = "<!-- mode-ref-ok -->"
"""A line carrying this marker is an EXPLICIT mode reference (analysis §3.1):
the gate tolerates it; everything else outside a GENERATED region is a
hand-written re-statement of the mode."""

BARE_CLASSIC_RULE: str = (
    "Layer-A counts `classic` as a mode literal ONLY when it co-occurs in a "
    "config/declaration shape — `workflow.mode == classic` / `mode: classic` "
    "/ `--mode classic` / flavor vocabulary (`flavor_id: classic`, "
    "`classic.yaml`) — NEVER the bare English word (`classic Scenario`, "
    "`classic TDD`, `classic 3-phase`) nor descriptive prose (`classic mode`, "
    "`classic-mode`), which legitimately survives in migrated documentation "
    "(17 such lines, slice-04 KEEP). `atdd_pure` and `workflow.mode` stay "
    "unconditionally flagged (no benign English sense). "
    "Empirical corpus anchor (2026-06-11, restated under this rule): 31 files "
    "carry `classic` in nWave/{skills,agents,tasks}; only config/declaration "
    "shapes flag — bare English prose AND the 17 descriptive "
    "`classic mode`/`classic-mode` documentation lines MUST pass, and the "
    "shipped tree is accepted clean (AT-01's clean baseline)."
)

BENIGN_CLASSIC_SAMPLES: tuple[str, ...] = (
    "We follow the classic Scenario Outline pattern here.",
    "This is the classic 3-phase TDD cycle, not a mode statement.",
    "A classic example of the Postel robustness principle.",
)
"""Bare-prose `classic` lines the Layer-A gate MUST accept (the rule's accept
side). None co-occurs with a mode-context shape, so none is the duplication
smell — the rule's empirical anchor in executable form."""


# --- Layer B: the half-declared-mode defects (named sad paths) ----------------


class RegistryCompletenessDefect(Enum):
    """A way a flavor registry can be a half-declared mode (analysis §3.2).

    Each member is one explicitly named sad path (example-based per the
    layered-discipline sad-path rule, Mandate 11). The completeness gate must
    refuse each, NAMING the defect — never improvise an answer for a defective
    registry (the slice-01 fail-closed contract, lifted to the registry level).
    """

    MISSING_REQUIRED_FIELD = "missing_required_field"
    """A flavor file drops a schema-required 4-tuple field (e.g. `descriptor`)."""

    TWO_DEFAULTS = "two_defaults"
    """Two flavors both declare `default: true` (the historic divergence)."""

    SKILL_LOAD_SET_NAMES_NONEXISTENT_AGENT = "skill_load_set_names_nonexistent_agent"
    """A `skill_load_set` row names an agent that has no spec under nWave/agents/."""


REGISTRY_DEFECT_BY_PHRASE: dict[str, RegistryCompletenessDefect] = {
    "a flavor is missing a required mode field": (
        RegistryCompletenessDefect.MISSING_REQUIRED_FIELD
    ),
    "two flavors both claim to be the default": (
        RegistryCompletenessDefect.TWO_DEFAULTS
    ),
    "a flavor directs an agent that does not exist": (
        RegistryCompletenessDefect.SKILL_LOAD_SET_NAMES_NONEXISTENT_AGENT
    ),
}
