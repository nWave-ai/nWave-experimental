"""Composition root for mode-registry-single-locus slice-01 (the SSOT-via-Types-Services-DSL mandate).

Pillar 3 (App as in production): the SUT is the flavor registry's
conditional-skill resolution seam — the DESIGN D-inject declared driving
surface (feature-delta `## Wave: DESIGN`, analysis §2.3.1). AT-01/AT-02 read
the REAL shipped registry at `nWave/flavors/{atdd_pure,classic}.yaml` (the
production data the dispatch path loads); AT-03 authors a deliberately
defective registry under tmp_path — both via the real filesystem (@real-io,
Mandate 9 v2 OR-reduction -> example-based, zero PBT machinery).

Driving-Port-Only Boundary attestation (the Driving-Port-Only Boundary
mandate, SSOT `nw-test-design-mandates`; S2 gate):
`resolve_skill_load_set` is THE driving-port entry function for the
registry-resolution seam — Layer 3 composition root, the exact surface class
the d4_phase_3 precedent attests for `dispatch_lifecycle_event`
(tests/des/acceptance/d4_phase_3_flavor_dispatcher/conftest.py). The M15
anti-pattern (importing an internal domain helper and invoking it at the
function boundary) does NOT apply: the imported callable IS the public entry
point the dispatch-time injection consumes (D-inject). This composition never
imports `des._internal.subset_parser`, never hand-parses YAML, never inspects
the agent markdown prose.

Dormant-Seam Reconciliation (D11 / S3): the AT-oracle target is the
DESIGN-declared SEAM (registry -> conditional-skill answer for one agent),
named here verbatim, driven through its real entry point, asserting the
observable effect at the port (the resolved skill tuple OR the typed
ValueError refusal). The dispatch-prompt injection call-site + the agent-spec
reference line are DELIVER slice-01 GREEN scope.

DISTILL-authored ACTIVE-RED (ADR-025 / ADR-GV-001 D6): the seam is scaffolded
in `src/des/application/flavor_dispatcher.py` (Mandate 7 RED-not-BROKEN —
import succeeds, the call raises a semantic AssertionError). All three
scenarios RUN and FAIL with `MISSING_FUNCTIONALITY` today; none is skipped.
Refusal capture below catches ONLY `ValueError` (the declared refusal type) so
the scaffold's AssertionError always propagates — AT-03 cannot false-green on
the scaffold.

Mandate 8 note: resolution is a READ — no observable state mutates, so no
`assert_state_delta` universe applies. Observables are port-exposed only:
resolved tuple / typed refusal.
"""

from __future__ import annotations

from pathlib import Path

from des.application.flavor_dispatcher import resolve_skill_load_set

from .domain_types_slice_01 import (
    AUTHORED_DEFECTIVE_FLAVOR_ID,
    CRAFTER_AGENT,
    EXPECTED_ATDD_PURE_CRAFTER_SKILLS,
    SHIPPED_FLAVORS,
    RegistryDefect,
    SkillName,
    WorkflowFlavor,
)


REPO_ROOT = Path(__file__).resolve().parents[5]
SHIPPED_FLAVORS_DIR = REPO_ROOT / "nWave" / "flavors"


# AT-03 fixtures — minimal subset-parser-compatible registry bodies, one per
# named declaration defect. Required schema fields present so the refusal is
# about the crafter declaration, never about an otherwise-broken flavor file.
_DEFECTIVE_REGISTRY_BODY: dict[RegistryDefect, str] = {
    RegistryDefect.CONDITIONAL_NOT_A_LIST: (
        "flavor_id: defective\n"
        "description: |\n"
        "  Deliberately defective registry fixture authored by the slice-01\n"
        "  acceptance test: the crafter's conditional entry is one bare word\n"
        "  instead of a list.\n"
        "skill_load_set:\n"
        "  nw-software-crafter:\n"
        "    conditional: nw-crafter-discipline-atdd-pure\n"
        "lifecycle_events:\n"
        "  session.init:\n"
        "    - gate_id: health-check\n"
        "      on_failure: log\n"
    ),
    RegistryDefect.CRAFTER_ROW_MISSING: (
        "flavor_id: defective\n"
        "description: |\n"
        "  Deliberately defective registry fixture authored by the slice-01\n"
        "  acceptance test: the skill_load_set declares another agent but the\n"
        "  crafter row is missing entirely.\n"
        "skill_load_set:\n"
        "  nw-acceptance-designer:\n"
        "    conditional:\n"
        "      - nw-test-design-mandates\n"
        "lifecycle_events:\n"
        "  session.init:\n"
        "    - gate_id: health-check\n"
        "      on_failure: log\n"
    ),
}


class ModeRegistryResolutionComposition:
    """Single source of truth for all slice-01 step-method business logic.

    Step bodies delegate here (the SSOT-via-Types-Services-DSL mandate,
    criterion 3: <=2 statements, no control flow inline).
    """

    def __init__(self, tmp_path: Path) -> None:
        self._authored_flavors_dir = tmp_path / "flavors"
        self._resolved: frozenset[str] | None = None
        self._refusal: ValueError | None = None

    # --- Given ----------------------------------------------------------

    def use_shipped_registry(self) -> None:
        """Pin the precondition: the REAL shipped registry files exist."""
        # Iterate what the product SHIPS, not every name the enum knows. The
        # enum keeps a retired id so fixtures can author a second flavor in
        # tmp_path; asserting that id exists on disk asserts the product still
        # ships a mode it removed.
        for flavor in SHIPPED_FLAVORS:
            flavor_file = SHIPPED_FLAVORS_DIR / f"{flavor.value}.yaml"
            assert flavor_file.is_file(), (
                f"shipped mode registry file missing: {flavor_file} -- the "
                "slice-01 SUT is the real registry, not a fixture"
            )

    def author_registry_with_crafter_defect(self, defect: RegistryDefect) -> None:
        """Author a tmp_path registry whose crafter entry carries the defect."""
        self._authored_flavors_dir.mkdir(parents=True, exist_ok=True)
        target = self._authored_flavors_dir / f"{AUTHORED_DEFECTIVE_FLAVOR_ID}.yaml"
        target.write_text(_DEFECTIVE_REGISTRY_BODY[defect], encoding="utf-8")

    # --- When -------------------------------------------------------------

    def resolve_crafter_conditional_skills(self, flavor: WorkflowFlavor) -> None:
        """Drive the seam against the REAL shipped registry."""
        self._resolve(flavor.value, SHIPPED_FLAVORS_DIR)

    def resolve_crafter_conditional_skills_in_authored_registry(self) -> None:
        """Drive the seam against the tmp_path-authored defective registry."""
        self._resolve(AUTHORED_DEFECTIVE_FLAVOR_ID, self._authored_flavors_dir)

    def _resolve(self, flavor_id: str, flavors_dir: Path) -> None:
        # Catch ONLY the declared refusal type (ValueError). The RED-scaffold
        # AssertionError -- and any unexpected error class -- propagates, so
        # the active-RED state and the closed refusal contract both hold.
        try:
            skills = resolve_skill_load_set(
                CRAFTER_AGENT, flavor_id, flavors_dir=flavors_dir
            )
        except ValueError as refusal:
            self._refusal = refusal
            self._resolved = None
        else:
            self._refusal = None
            self._resolved = frozenset(skills)

    # --- Then ---------------------------------------------------------------

    def assert_directed_exactly(self, skill: SkillName) -> None:
        assert self._refusal is None, (
            f"expected a resolved skill directive, got refusal: {self._refusal}"
        )
        assert self._resolved == frozenset({skill}), (
            f"registry answer {sorted(self._resolved or ())} != the retired "
            f"inline-table set {sorted(frozenset({skill}))} -- dispatch "
            "behaviour is NOT byte-identical"
        )

    def assert_single_directive(self) -> None:
        assert self._resolved is not None and len(self._resolved) == 1, (
            f"expected exactly one conditional-skill directive, got "
            f"{sorted(self._resolved or ())}"
        )
        assert self._resolved == EXPECTED_ATDD_PURE_CRAFTER_SKILLS, (
            f"registry injected {sorted(self._resolved)} -- the inline table "
            f"carries {sorted(EXPECTED_ATDD_PURE_CRAFTER_SKILLS)}"
        )

    def assert_refused_retired_flavor(self) -> None:
        """The registry refuses a retired flavor rather than answering empty."""
        assert self._refusal is not None, (
            "expected a refusal for the retired flavor, got the answer "
            f"{sorted(self._resolved or ())} -- an empty answer for a removed "
            "mode is indistinguishable from a valid one"
        )

    def assert_directed_to_load_nothing(self) -> None:
        assert self._refusal is None, (
            f"expected the declared-empty answer, got refusal: {self._refusal}"
        )
        assert self._resolved == frozenset(), (
            f"under classic the crafter must load NO conditional skills, "
            f"got {sorted(self._resolved or ())}"
        )

    def assert_answer_was_declared(self) -> None:
        # Declared-empty vs absent-fallback: resolution SUCCEEDED (no refusal,
        # a real answer object). The refusal contract (AT-03 crafter-row-
        # missing example) is what makes this distinction observable.
        assert self._refusal is None and self._resolved is not None, (
            "the empty answer must be the registry's own declaration -- "
            f"resolution did not succeed (refusal: {self._refusal})"
        )

    def assert_refused_as_declaration_defect(self) -> None:
        assert self._refusal is not None, (
            "a defective crafter declaration MUST be refused (ValueError); "
            f"instead the registry answered {sorted(self._resolved or ())}"
        )

    def assert_no_skills_improvised(self) -> None:
        assert self._resolved is None, (
            f"no conditional skills may be improvised on a declaration "
            f"defect, got {sorted(self._resolved or ())}"
        )
