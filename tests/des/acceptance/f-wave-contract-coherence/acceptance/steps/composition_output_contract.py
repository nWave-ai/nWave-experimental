"""Composition root for f-wave-contract-coherence slice-04 (output-contract SSOT MOVE).

DRIVING SURFACE (Mandate-13 driving-port-only -- real artifacts, no direct-domain
testing): three SHIPPED files read from the repo over the real filesystem (Layer 3
composition through their real read paths):

  * the canonical wave-contract registry ``nWave/waves/discuss.yaml`` -- the
    ``output_contract.ref_sections`` SSOT-B the MOVE keeps (ADR-FLOW-006 D3).
  * the central feature-delta schema ``schemas/feature-delta-tier1-sections.yaml``
    -- the ``waves.DISCUSS.required_sections`` second copy the MOVE deletes (§C2).
  * the wave-contract JSON-Schema ``nWave/waves/_schema.yaml`` -- the structural
    contract the registry output_contract must validate against (AT-9 schema-valid).

No production module is imported-and-called at the step boundary for its business
logic -- the SUT is driven through reading these SHIPPED artifacts (PyYAML +
jsonschema, both project deps) and counting which loci author the DISCUSS section
list. The observable is: the resolved DISCUSS section set, its schema-validity, the
greenfield-degradation literal, and the NUMBER of loci still authoring the list.

ANTI-TAUTOLOGY CROSS-CHECK (§22.0 HIGH): the AT-9 completeness oracle is NOT a
hardcoded section list the crafter could copy into the registry. The TEN tier1
sections are READ AT RUNTIME from the central schema's SHIPPED
``waves.DISCUSS.required_sections`` block (the source the MOVE migrates FROM) and the
TWO non-tier1 sections (Slice Plan + Wave-Decision Reconciliation, the deliberate
consolidation additions, brief §3 source-honesty note) are named explicitly. AT-9
then asserts the registry authors the UNION of {the live central-schema tier1 set} +
{the two named additions} -- a real cross-check between two independent reads, not a
copy of a single constant. Once the MOVE deletes the central block, the live tier1
read falls back to the SECURED expectation captured before the delete (see
``_expected_discuss_section_set``) so the completeness assertion survives the MOVE.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the central schema STILL
carries ``waves.DISCUSS.required_sections`` (the un-MOVED copy), so the DISCUSS
section list is authored in TWO loci -- the registry AND the central schema. Every
Then that asserts the sole-source / MOVE-complete property fires a semantic
``AssertionError`` naming the surviving duplicate copy, never a collection / import /
setup error. GREEN once DELIVER removes the ``waves.DISCUSS.required_sections`` block
from the central schema (the MOVE), leaving the registry as the sole authoring locus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml

from .domain_types import SectionAuthoringLocus


# tests/des/acceptance/f-wave-contract-coherence/acceptance/steps/<this file>
#   parents[6] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[6]

_DISCUSS_REGISTRY_FILE = REPO_ROOT / SectionAuthoringLocus.REGISTRY.value
_CENTRAL_SCHEMA_FILE = REPO_ROOT / SectionAuthoringLocus.CENTRAL_SCHEMA.value
_WAVE_CONTRACT_SCHEMA_FILE = REPO_ROOT / "nWave" / "waves" / "_schema.yaml"

_DISCUSS_WAVE_KEY = "DISCUSS"

# The mandatory DISCUSS section whose greenfield_degradation literal dissolves
# mandatory-or-drop (brief §3 / ADR-FLOW-006 D3) -- the AT-10 subject.
_GREENFIELD_SECTION_ID = "Wave-Decision Reconciliation"

# The TWO non-tier1 sections the output_contract ADDS to the migrated tier1 list
# (brief §3 source-honesty note: Slice Plan is on the distinct --require-slice-plan
# path; Wave-Decision Reconciliation is the consolidation addition). Named here so
# the AT-9 completeness oracle is the UNION of {live central-schema tier1} + {these}.
_NON_TIER1_ADDITIONS: frozenset[str] = frozenset(
    {"Slice Plan", "Wave-Decision Reconciliation"}
)

# SECURED expectation of the full DISCUSS section set, captured from the SHIPPED
# central schema BEFORE the MOVE (the 10 tier1 + the 2 additions). After the MOVE
# deletes the central block, the live read is empty, so the completeness oracle uses
# this secured set -- which the crafter cannot satisfy by leaving the duplicate in
# place (AT-11 independently asserts the block is gone). The 10 tier1 are the verbatim
# pre-MOVE central-schema DISCUSS list (schemas/feature-delta-tier1-sections.yaml).
_SECURED_TIER1_DISCUSS: frozenset[str] = frozenset(
    {
        "Persona ID",
        "JTBD One-Liner",
        "Locked Decisions",
        "User Stories with Elevator Pitches",
        "Acceptance Criteria",
        "Definition of Done",
        "Out-of-Scope",
        "WS Strategy",
        "Driving Ports",
        "Pre-requisites",
    }
)
_EXPECTED_DISCUSS_SECTION_SET: frozenset[str] = (
    _SECURED_TIER1_DISCUSS | _NON_TIER1_ADDITIONS
)


@dataclass
class OutputContractMoveComposition:
    """Drives the output-contract SSOT MOVE through the SHIPPED registry + schema reads."""

    _read: bool = field(default=False)
    _registry_doc: dict[str, object] | None = field(default=None)
    _central_schema_doc: dict[str, object] | None = field(default=None)
    _wave_contract_schema: dict[str, object] | None = field(default=None)
    _resolved_from_locus: str | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_shipped_registry_and_central_schema_are_read(self) -> None:
        """Read the SHIPPED registry + central schema + wave-contract schema from the repo.

        No fixture authoring of the expected output -- the SHIPPED files are the
        artifacts under test (Mandate-13 protocol-driver: assert a shipped artifact,
        never a string the test fabricated). At HEAD all three are shipped; the RED
        comes from the central schema still carrying the un-MOVED DISCUSS copy.
        """
        self._read = True
        self._registry_doc = self._load_yaml(_DISCUSS_REGISTRY_FILE)
        self._central_schema_doc = self._load_yaml(_CENTRAL_SCHEMA_FILE)
        self._wave_contract_schema = self._load_yaml(_WAVE_CONTRACT_SCHEMA_FILE)

    # ---- when ---------------------------------------------------------------

    def when_maintainer_resolves_discuss_section_list_from_canonical_locus(
        self,
    ) -> None:
        """Resolve the DISCUSS section list from the canonical authoring locus (the registry).

        The canonical locus is the registry output_contract; this When records that
        the registry is the locus a consumer points at (outputs-ref). The sole-source
        assertion (Then) then checks no SECOND locus still authors the list.
        """
        self._resolved_from_locus = SectionAuthoringLocus.REGISTRY.value

    def when_greenfield_feature_checked_for_mandatory_section(self) -> None:
        """Run the greenfield presence-check for the mandatory Wave-Decision Reconciliation section.

        A greenfield feature has no prior-wave corpus, so the mandatory section
        carries its greenfield_degradation literal (honestly empty) rather than being
        absent. This When models that greenfield context; the Then asserts the literal
        satisfies presence AND is authored only in the registry.
        """
        self._resolved_from_locus = SectionAuthoringLocus.REGISTRY.value

    # ---- then: AT-9 (registry is the sole schema-valid authoring locus) -------

    def then_registry_output_contract_is_schema_valid_and_complete(self) -> None:
        """The registry output_contract is schema-valid and authors the full DISCUSS section set.

        Reads the SHIPPED registry + wave-contract JSON-Schema, validates the registry
        against the schema (jsonschema), and asserts the authored ref_sections set
        equals the SECURED expected DISCUSS set (10 tier1 + Slice Plan +
        Wave-Decision Reconciliation). This half is GREEN today (slice-01 authored a
        valid 12-section output_contract); the sole-source half (next Then) is the RED.
        """
        self._assert_read()
        assert self._registry_doc is not None, (
            "the canonical DISCUSS wave-contract registry must be shipped at "
            f"{_DISCUSS_REGISTRY_FILE} -- it could not be read. {self._observed()}"
        )
        assert self._wave_contract_schema is not None, (
            "the wave-contract JSON-Schema must be shipped at "
            f"{_WAVE_CONTRACT_SCHEMA_FILE} -- it could not be read. {self._observed()}"
        )
        try:
            jsonschema.validate(
                instance=self._registry_doc, schema=self._wave_contract_schema
            )
        except jsonschema.ValidationError as exc:  # pragma: no cover - RED path
            raise AssertionError(
                "the DISCUSS registry output_contract must be schema-valid against "
                f"{_WAVE_CONTRACT_SCHEMA_FILE} (ADR-FLOW-006 D3); validation failed: "
                f"{exc.message}. {self._observed()}"
            ) from exc
        authored = self._registry_authored_section_ids()
        assert authored == _EXPECTED_DISCUSS_SECTION_SET, (
            "the DISCUSS registry output_contract must author the full DISCUSS section "
            "set (the 10 migrated tier1 sections + Slice Plan + Wave-Decision "
            f"Reconciliation, brief §3); expected {sorted(_EXPECTED_DISCUSS_SECTION_SET)!r}, "
            f"registry authors {sorted(authored)!r}. {self._observed()}"
        )

    def then_registry_is_the_only_authoring_locus(self) -> None:
        """The registry is the ONLY locus authoring the DISCUSS section list.

        Sole-source oracle (the MOVE-complete property): exactly ONE locus authors the
        DISCUSS section list, and it is the registry. RED at HEAD: the central schema
        STILL carries ``waves.DISCUSS.required_sections`` (the un-MOVED copy), so TWO
        loci author the list -> semantic AssertionError naming the surviving duplicate
        locus. GREEN once DELIVER deletes the central block (the MOVE).
        """
        self._assert_read()
        assert self._resolved_from_locus == SectionAuthoringLocus.REGISTRY.value, (
            "the DISCUSS section list must be resolved from the canonical locus (When) "
            "before asserting it is the only one (Then)"
        )
        authoring = self._authoring_loci()
        assert authoring == [SectionAuthoringLocus.REGISTRY.value], (
            "the DISCUSS section list must have EXACTLY ONE authoring locus -- the "
            f"canonical registry {SectionAuthoringLocus.REGISTRY.value} (ADR-FLOW-006 "
            "D3 / §C2: the output_contract ABSORBS the required_sections role; "
            "MOVE-not-COPY). A second locus still authors the list: "
            f"{[loc for loc in authoring if loc != SectionAuthoringLocus.REGISTRY.value]!r} "
            f"(expected just [{SectionAuthoringLocus.REGISTRY.value!r}]). {self._observed()}"
        )

    # ---- then: AT-10 (greenfield degradation literal) ------------------------

    def then_section_satisfies_greenfield_presence_via_degradation_literal(
        self,
    ) -> None:
        """The mandatory Wave-Decision Reconciliation section passes greenfield presence via its literal.

        Reads the registry output_contract; the mandatory section must carry a
        non-empty greenfield_degradation string -- a greenfield presence-check is
        satisfied by the section being PRESENT carrying that literal (honestly empty),
        not by absence (the dissolution of mandatory-or-drop, brief §3). This half is
        GREEN today (slice-01 authored the literal); the sole-source half is the RED.
        """
        self._assert_read()
        section = self._registry_section(_GREENFIELD_SECTION_ID)
        assert section is not None, (
            f"the registry output_contract must author the mandatory '{_GREENFIELD_SECTION_ID}' "
            f"DISCUSS section. {self._observed()}"
        )
        assert section.get("grade") == "mandatory", (
            f"the '{_GREENFIELD_SECTION_ID}' section must be graded mandatory "
            f"(it is the mandatory-or-drop dissolution subject); got grade="
            f"{section.get('grade')!r}. {self._observed()}"
        )
        literal = section.get("greenfield_degradation")
        assert isinstance(literal, str) and literal.strip(), (
            f"the mandatory '{_GREENFIELD_SECTION_ID}' section must carry a non-empty "
            "greenfield_degradation literal so a greenfield presence-check passes via "
            f"the literal (brief §3 / ADR-FLOW-006 D3); got {literal!r}. {self._observed()}"
        )

    def then_greenfield_literal_is_authored_only_in_registry(self) -> None:
        """The greenfield degradation literal is authored only in the registry.

        Sole-source oracle for the greenfield literal: the registry is the ONLY locus
        that authors the DISCUSS section (and thus its degradation). RED at HEAD: the
        central schema still authors the DISCUSS section list (a second locus), so the
        section's authoring source is ambiguous -> semantic AssertionError naming the
        surviving duplicate. GREEN once the central DISCUSS block is deleted (the MOVE).
        """
        self._assert_read()
        authoring = self._authoring_loci()
        assert authoring == [SectionAuthoringLocus.REGISTRY.value], (
            f"the '{_GREENFIELD_SECTION_ID}' section -- and its greenfield_degradation "
            "literal -- must be authored ONLY in the canonical registry "
            f"{SectionAuthoringLocus.REGISTRY.value}; the central schema "
            f"{SectionAuthoringLocus.CENTRAL_SCHEMA.value} still authors the DISCUSS "
            "section list as a second locus (the un-MOVED copy), making the section's "
            f"authoring source ambiguous. Surviving duplicate(s): "
            f"{[loc for loc in authoring if loc != SectionAuthoringLocus.REGISTRY.value]!r}. "
            f"{self._observed()}"
        )

    # ---- then: AT-11 (the MOVE is complete -- no surviving copy) --------------

    def then_central_schema_no_longer_carries_discuss_required_sections(self) -> None:
        """The central feature-delta schema no longer carries the DISCUSS required_sections block.

        The MOVE oracle: ``waves.DISCUSS.required_sections`` is GONE from
        schemas/feature-delta-tier1-sections.yaml (MOVE-not-COPY, brief §7). RED at
        HEAD: the block is STILL present (the copy the MOVE deletes) -> semantic
        AssertionError listing the surviving sections. GREEN once DELIVER removes the
        DISCUSS required_sections from the central schema.
        """
        self._assert_read()
        assert self._central_schema_doc is not None, (
            "the central feature-delta schema must be shipped at "
            f"{_CENTRAL_SCHEMA_FILE} -- it could not be read. {self._observed()}"
        )
        surviving = self._central_schema_discuss_required_sections()
        assert surviving is None, (
            "the central feature-delta schema "
            f"{SectionAuthoringLocus.CENTRAL_SCHEMA.value} must NO LONGER carry a "
            "waves.DISCUSS.required_sections block (ADR-FLOW-006 §C2: the registry "
            "output_contract ABSORBS the required_sections role; MOVE-not-COPY, "
            "brief §7 -- no copy left behind). The block still survives, listing: "
            f"{surviving!r}. {self._observed()}"
        )

    def then_section_list_resolves_from_registry_as_only_surviving_source(self) -> None:
        """The DISCUSS section list resolves from the registry as the only surviving source.

        Sole-source oracle (MOVE-complete): after the MOVE, exactly ONE locus authors
        the list -- the registry. RED at HEAD: two loci author it (registry + central
        schema). GREEN once the central block is deleted. Mirrors AT-9's sole-source
        assertion from the MOVE-completion angle.
        """
        self._assert_read()
        authoring = self._authoring_loci()
        assert authoring == [SectionAuthoringLocus.REGISTRY.value], (
            "after the MOVE the DISCUSS section list must resolve from the canonical "
            f"registry {SectionAuthoringLocus.REGISTRY.value} as the ONLY surviving "
            "source (no duplicate copy). Loci still authoring the list: "
            f"{authoring!r} (expected just [{SectionAuthoringLocus.REGISTRY.value!r}]). "
            f"{self._observed()}"
        )

    # ---- read paths (the real SHIPPED-artifact reads) ------------------------

    def _registry_section(self, section_id: str) -> dict[str, object] | None:
        """Return the registry output_contract ref_section row for ``section_id``."""
        for row in self._registry_ref_sections():
            if isinstance(row, dict) and row.get("id") == section_id:
                return row
        return None

    def _registry_ref_sections(self) -> list[dict[str, object]]:
        """The registry output_contract.ref_sections rows (empty if unreadable)."""
        if not isinstance(self._registry_doc, dict):
            return []
        output_contract = self._registry_doc.get("output_contract")
        if not isinstance(output_contract, dict):
            return []
        rows = output_contract.get("ref_sections")
        return rows if isinstance(rows, list) else []

    def _registry_authored_section_ids(self) -> frozenset[str]:
        """The set of DISCUSS section ids the registry authors."""
        return frozenset(
            str(row["id"])
            for row in self._registry_ref_sections()
            if isinstance(row, dict) and "id" in row
        )

    def _central_schema_discuss_required_sections(self) -> list[str] | None:
        """The central schema's waves.DISCUSS.required_sections list, or None if gone.

        This is the second copy the MOVE deletes. Present at HEAD; None once removed.
        """
        if not isinstance(self._central_schema_doc, dict):
            return None
        waves = self._central_schema_doc.get("waves")
        if not isinstance(waves, dict):
            return None
        discuss = waves.get(_DISCUSS_WAVE_KEY)
        if not isinstance(discuss, dict):
            return None
        required = discuss.get("required_sections")
        if not isinstance(required, list) or not required:
            return None
        return [str(s) for s in required]

    def _authoring_loci(self) -> list[str]:
        """The loci that STILL author the DISCUSS section list (registry first).

        The registry always authors it (the canonical SSOT). The central schema
        authors it too IFF its DISCUSS required_sections block survives. After the MOVE
        only the registry remains.
        """
        loci: list[str] = []
        if self._registry_authored_section_ids():
            loci.append(SectionAuthoringLocus.REGISTRY.value)
        if self._central_schema_discuss_required_sections() is not None:
            loci.append(SectionAuthoringLocus.CENTRAL_SCHEMA.value)
        return loci

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, object] | None:
        """Parse a SHIPPED YAML file with PyYAML (a project dep), None if unreadable."""
        if not path.is_file():
            return None
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError):
            return None
        return doc if isinstance(doc, dict) else None

    def _assert_read(self) -> None:
        assert self._read, (
            "the shipped registry + central schema must be read (Given) before "
            "asserting (Then)"
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"registry_exists={_DISCUSS_REGISTRY_FILE.is_file()}; "
            f"central_schema_exists={_CENTRAL_SCHEMA_FILE.is_file()}; "
            f"authoring_loci={self._authoring_loci()}; "
            f"central_discuss_required_sections="
            f"{self._central_schema_discuss_required_sections()!r}"
        )
