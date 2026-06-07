"""Domain types for the fix-distill-human-signoff acceptance set.

F-DISTILL-HUMAN-SIGNOFF (Mandate-12 criterion 1). Every domain noun used in
the six slices' Gherkin is expressed once here as a typed enum / NewType /
frozen dataclass. The composition root consumes these typed parameters; step
bodies coerce a Gherkin phrase to a typed value via the ``*_BY_PHRASE`` maps
and delegate -- no raw ``str`` where a domain enum exists, no inline business
logic.

Vocabulary shared across all six slice feature files (slice-01..slice-05) and
their step modules -- the SSOT for the human-sign-off domain language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-distill-human-signoff").
FeatureId = NewType("FeatureId", str)

# A kebab-case unbounded-input-domain identifier from a component manifest --
# matches the manifest schema pattern ``^[a-z0-9-]+$`` (the shared anchor per
# F-DESIGN-COMPONENT-MANIFEST schema).
ManifestDomainId = NewType("ManifestDomainId", str)


class CoverageMapVerdict(str, Enum):
    """The exit-code contract of the derive_coverage_map + verify_coverage_map CLIs.

    Shared across slices 01 (derive) and 03 (verify). The error *identifiers*
    are gate-local prose; the CLI emits the code, not the name (the same
    earned-trust contract as the manifest gate -- exit code is the SSOT, the
    name is documentation).
    """

    RENDERED = "rendered"  # exit 0 -- coverage-map rendered / verified
    REFUSED = "refused"  # exit 1 -- signoff-missing / stale / structurally-incomplete / over-cap / omission-detected / trailer-mismatch
    MALFORMED = "malformed"  # exit 2 -- malformed manifest / coverage-map / ledger / unparseable yaml / malformed @covers: id


# CoverageMapVerdict -> process exit code (SSOT for the exit-code contract).
EXIT_CODE_BY_VERDICT: dict[CoverageMapVerdict, int] = {
    CoverageMapVerdict.RENDERED: 0,
    CoverageMapVerdict.REFUSED: 1,
    CoverageMapVerdict.MALFORMED: 2,
}


class CoverageDimension(str, Enum):
    """The four mandatory dimension rows in ``## NOT covered -- and why`` (§5.1).

    The coarse partition the negative-space document must always carry --
    present even when empty (the row reads ``none`` rather than being omitted,
    so a human sees the ATD explicitly claimed nothing-uncovered).
    """

    ENVIRONMENTAL = "environmental"
    BEHAVIOURAL = "behavioural"
    PROCESS = "process"
    OTHER = "other"


class ManifestBranch(str, Enum):
    """How the consuming gate routes the manifest state (§4.2 keystone).

    The feature-delta §4.2 prose says "state-C-with-not-applicable", but the
    shipped ``resolve_manifest_state()`` folds the marker into ``ManifestState.B``
    (with marker). This enum names the BRANCH the consuming gate takes -- not
    the resolver state -- so the acceptance vocabulary is insulated from the
    upstream naming reconciliation. See ``red-classification.md`` §5.
    """

    POPULATED = "populated"  # state-A: real domains, normal path
    NOT_APPLICABLE = "not-applicable"  # state-B with marker, §4.2 fail-functional
    EMPTY_PENDING = "empty-pending"  # state-B no marker, fail-closed via anti-omission


class AntiOmissionVerdict(str, Enum):
    """Slice-02 + slice-03 named refusal tokens (§4 step 2 anti-omission contract).

    Each token is a structured cause-of-refusal the renderer / verifier emits
    on stderr when the coverage-map producer or gate refuses. The CLI emits
    the exit code; the cause-of-refusal token is the stderr SSOT (earned-trust
    contract -- the exit code is the gate, the token is documentation).
    """

    OMISSION_DETECTED = "OmissionDetected"  # exit 1 -- a manifest domain dropped
    COVERAGE_MAP_OVER_CAP = "CoverageMapOverCap"  # exit 1 -- > CAP uncovered entries
    SIGNOFF_MISSING = "SignoffMissing"  # exit 1 -- not-applicable attestation absent
    STRUCTURAL_INCOMPLETE = (
        "StructuralIncomplete"  # exit 1 -- missing/disordered section (slice-03)
    )
    SIGNOFF_STALE = "SignoffStale"  # exit 1 -- post-signoff body edit (slice-03)


# AntiOmissionVerdict -> exit code. All current refusal tokens map to exit 1.
EXIT_CODE_BY_REFUSAL: dict[AntiOmissionVerdict, int] = {
    AntiOmissionVerdict.OMISSION_DETECTED: 1,
    AntiOmissionVerdict.COVERAGE_MAP_OVER_CAP: 1,
    AntiOmissionVerdict.SIGNOFF_MISSING: 1,
    AntiOmissionVerdict.STRUCTURAL_INCOMPLETE: 1,
    AntiOmissionVerdict.SIGNOFF_STALE: 1,
}


class CapAndNotApplicableState(str, Enum):
    """The three equivalence classes for slice-02 AT3 Scenario Outline.

    Each value is one of the AT3 outline rows -- a closed finite domain
    (Mandate 9 layer-3 example-only).
    """

    OVER_CAP = "over-cap"
    NOT_APPLICABLE_ATTESTED = "not-applicable-attested"
    NOT_APPLICABLE_NOT_ATTESTED = "not-applicable-not-attested"


# Gherkin phrase -> CapAndNotApplicableState (slice-02 AT3 outline rows).
CAP_AND_NOT_APPLICABLE_BY_PHRASE: dict[str, CapAndNotApplicableState] = {
    "more than seven uncovered manifest domains are present": (
        CapAndNotApplicableState.OVER_CAP
    ),
    "the manifest carries a not-applicable marker and the human attestation line is present in the signoff": (
        CapAndNotApplicableState.NOT_APPLICABLE_ATTESTED
    ),
    "the manifest carries a not-applicable marker and the human attestation line is missing from the signoff": (
        CapAndNotApplicableState.NOT_APPLICABLE_NOT_ATTESTED
    ),
}


# Gherkin verdict-phrase -> the CLI exit-class the renderer must produce.
# Slice-02 AT3 outline's Then clause maps a verdict phrase to either a
# `CoverageMapVerdict.RENDERED` (exit 0, coverage-map written) OR a specific
# `AntiOmissionVerdict` refusal token (exit 1). The composition layer asserts
# the exit code matches and -- for refusals -- the token appears on stderr.
VERDICT_BY_PHRASE: dict[str, AntiOmissionVerdict | CoverageMapVerdict] = {
    "the renderer refuses for an undeclared omission": (
        AntiOmissionVerdict.OMISSION_DETECTED
    ),
    "the renderer refuses for an over cap surface": (
        AntiOmissionVerdict.COVERAGE_MAP_OVER_CAP
    ),
    "the renderer refuses for a missing signoff": (AntiOmissionVerdict.SIGNOFF_MISSING),
    "a coverage map is written to the feature distill directory": (
        CoverageMapVerdict.RENDERED
    ),
}


# The lean CAP value enforced by slice-02 -- the producer refuses a coverage
# map with more than CAP uncovered manifest domains. Open-question §8 #1 in
# the feature-delta calibrates this against the first 2-3 dogfood features;
# 7 is the documented current value.
CAP: int = 7


class ParserEdgeShape(str, Enum):
    """A parser-edge equivalence class for the §4.1b @covers: binding (G9).

    Slice-01 AT3 Scenario Outline rows -- each row witnesses one mechanically
    decidable parser-edge contract.
    """

    MULTI_TAG_ONE_LINE = "multi-tag-one-line"
    OUTLINE_COVERS_ONCE = "outline-covers-once"
    FEATURE_LINE_IGNORED = "feature-line-ignored"
    NO_TAG_EMPTY = "no-tag-empty"
    MALFORMED_DOMAIN_ID = "malformed-domain-id"


# Gherkin phrase -> ParserEdgeShape (slice-01 Scenario Outline Examples rows).
PARSER_EDGE_BY_PHRASE: dict[str, ParserEdgeShape] = {
    "the tag line carries two covers tags for two distinct manifest domains": (
        ParserEdgeShape.MULTI_TAG_ONE_LINE
    ),
    "a scenario outline carries one covers tag with three Examples rows": (
        ParserEdgeShape.OUTLINE_COVERS_ONCE
    ),
    "the covers tag sits on the Feature line instead of the Scenario tag line": (
        ParserEdgeShape.FEATURE_LINE_IGNORED
    ),
    "the scenario carries no covers tag at all": ParserEdgeShape.NO_TAG_EMPTY,
    "the covers tag names a domain identifier that is not lowercase kebab case": (
        ParserEdgeShape.MALFORMED_DOMAIN_ID
    ),
}


@dataclass(frozen=True)
class ManifestDomain:
    """One unbounded-input-domains entry the manifest declares (§5.1 surface).

    The frozen-dataclass keeps slice-02 and slice-03's anti-omission set-difference
    operating on a typed value, not a dict shape.
    """

    id: ManifestDomainId
    dimension: CoverageDimension
    sut: str
    canonical_category: (
        str  # "C2" | "C5" | "C6" | "C7" (re-typed in component-manifest)
    )


@dataclass(frozen=True)
class CoverageMapDocument:
    """The rendered coverage-map artefact -- a port-exposed observable.

    Universe-bound names: callers reference fields here in their state-delta
    universe, not internal struct details.
    """

    path: str  # POSIX path under docs/feature/{id}/distill/[slice-NN/]coverage-map.md
    mandatory_sections_in_order: tuple[str, ...]
    dimension_rows: tuple[CoverageDimension, ...]
    not_covered_rows: tuple[tuple[CoverageDimension, ManifestDomainId], ...] = field(
        default_factory=tuple
    )


# =====================================================================
# SLICE-03 -- verify_coverage_map gate CLI domain vocabulary.
# =====================================================================
#
# The slice-03 read-side gate verifies a coverage-map already authored +
# signed (slices 01-02) for: (a) structural completeness (mandatory sections
# in order); (b) signoff freshness against the §5.3 canonical-content digest;
# (c) malformed-input fail-closed (exit 2 distinct from exit 1); (d) §5.3
# canonicalization cross-tree conformance (golden fixtures).
#
# The §5.3 G3 widened section set: ALL FOUR signed sections feed the digest.
# Excluded section: ``## Signoff`` alone (cannot digest the field carrying
# the digest). The slice-03 AT3 tamper outline witnesses one row per signed
# section -- post-signoff body edit in ANY one of them MUST move the digest.


class SignedSection(str, Enum):
    """One of the four §5.3 signed sections fed into the canonical-content digest.

    Slice-03 AT3 outline enumerates one tamper case per signed section
    (G3 widened section set). Each value is the literal Markdown heading
    text as it appears in the rendered coverage-map.
    """

    FEATURE_SURFACE_DECLARED = "## Feature surface declared"
    NOT_COVERED_TABLE = "## NOT covered -- and why"
    KNOWN_RESIDUES = "## Known residues carried forward"
    NEGATIVE_SPACE = "## Negative-space completeness statement"


# Gherkin phrase -> SignedSection (slice-03 AT3 tamper outline rows a-d).
SIGNED_SECTION_BY_PHRASE: dict[str, SignedSection] = {
    "the acceptance designer has edited the feature surface declared section after signoff": (
        SignedSection.FEATURE_SURFACE_DECLARED
    ),
    "the acceptance designer has edited the not covered table after signoff": (
        SignedSection.NOT_COVERED_TABLE
    ),
    "the acceptance designer has edited the known residues carried forward section after signoff": (
        SignedSection.KNOWN_RESIDUES
    ),
    "the acceptance designer has edited the negative space completeness statement after signoff": (
        SignedSection.NEGATIVE_SPACE
    ),
}


class VerifyTamperOrInput(str, Enum):
    """The slice-03 AT3 Scenario Outline equivalence classes.

    Closed finite domain (Mandate 9 layer-3 example-only). The four
    body-tamper rows are encoded via ``SIGNED_SECTION_BY_PHRASE`` above; the
    two remaining rows are the malformed-input case + the golden-fixture
    canonicalization conformance case.
    """

    TAMPER_FEATURE_SURFACE = "tamper-feature-surface-declared"
    TAMPER_NOT_COVERED = "tamper-not-covered-table"
    TAMPER_KNOWN_RESIDUES = "tamper-known-residues"
    TAMPER_NEGATIVE_SPACE = "tamper-negative-space"
    MALFORMED_INPUT = "malformed-input"
    GOLDEN_FIXTURE_CONFORMANCE = "golden-fixture-conformance"


# Gherkin phrase -> VerifyTamperOrInput (slice-03 AT3 outline rows).
TAMPER_OR_INPUT_BY_PHRASE: dict[str, VerifyTamperOrInput] = {
    "the acceptance designer has edited the feature surface declared section after signoff": (
        VerifyTamperOrInput.TAMPER_FEATURE_SURFACE
    ),
    "the acceptance designer has edited the not covered table after signoff": (
        VerifyTamperOrInput.TAMPER_NOT_COVERED
    ),
    "the acceptance designer has edited the known residues carried forward section after signoff": (
        VerifyTamperOrInput.TAMPER_KNOWN_RESIDUES
    ),
    "the acceptance designer has edited the negative space completeness statement after signoff": (
        VerifyTamperOrInput.TAMPER_NEGATIVE_SPACE
    ),
    "the manifest or coverage map cannot be parsed": VerifyTamperOrInput.MALFORMED_INPUT,
    "the canonical content of a golden fixture is digested by the local implementation": (
        VerifyTamperOrInput.GOLDEN_FIXTURE_CONFORMANCE
    ),
}


# Gherkin verdict-phrase -> the slice-03 verify-gate exit class.
# Returns either a `CoverageMapVerdict` (RENDERED = exit 0 -- accepted /
# golden-digest matches) OR an `AntiOmissionVerdict` refusal token. The
# composition layer asserts the exit code matches and -- for refusals -- the
# token appears on stderr.
VERIFY_VERDICT_BY_PHRASE: dict[str, AntiOmissionVerdict | CoverageMapVerdict] = {
    "the verify gate refuses for a stale signoff": (AntiOmissionVerdict.SIGNOFF_STALE),
    "the verify gate refuses for a malformed input": (CoverageMapVerdict.MALFORMED),
    "the verify gate produces the golden fixture digest": (CoverageMapVerdict.RENDERED),
}


# The four §5.1 mandatory section headings, in the §5.1 fixed L1 order. The
# slice-03 structural check (AT2) asserts every heading is present and in
# this order; the digest (AT3 rows a-d) is computed over the first four
# (§5.3 G3 widened set), excluding only ``## Signoff``.
MANDATORY_SECTIONS_IN_ORDER: tuple[str, ...] = (
    "## Feature surface declared",
    "## NOT covered -- and why",
    "## Known residues carried forward",
    "## Negative-space completeness statement",
    "## Signoff",
)


# =====================================================================
# SLICE-04 -- signature-contract domain vocabulary.
# =====================================================================
#
# Slice-04 binds the three signoff surfaces -- the in-document ``## Signoff``
# block, the ``Coverage-Map-Signed-Off-By:`` git trailer, and the
# ``CoverageMapSignedOff`` ledger record -- to a single identity (the §5.3
# canonical-content digest). The driving ports are:
#
#   * ``verify_coverage_map emit-trailer`` (block -> trailer projection;
#     subprocess CLI).
#   * The deterministic engine function
#     ``src/des/adapters/driven/ledger/coverage_map_signoff_writer.write_coverage_map_signed_off``
#     (call-graph reachability via static AST scan -- NO subprocess for AT3).


class SignoffSurface(str, Enum):
    """One of the three signature surfaces bound by the slice-04 contract.

    The three surfaces share one identity -- the §5.3 canonical-content
    digest the ``## Signoff`` block carries. A hand-edited trailer (or a
    trailer asserted independently of the block) diverges from the re-derived
    value and is refused; a ledger record written by anything other than the
    deterministic engine is refused at the architecture level.
    """

    BLOCK = "block"
    TRAILER = "trailer"
    LEDGER = "ledger"


# The exact conventional-commit trailer key the verify CLI projects from the
# ``## Signoff`` block. Trailer SSOT for the slice-04 AT1 re-derivation check.
TRAILER_KEY: str = "Coverage-Map-Signed-Off-By"


# The fixed event-name the deterministic engine writes into the HMAC-chained
# ledger when ``write_coverage_map_signed_off`` appends a record. Slice-04 AT2
# asserts this exact string appears under the ``event`` field of the appended
# JSONL record.
LEDGER_EVENT_COVERAGE_MAP_SIGNED_OFF: str = "CoverageMapSignedOff"


class TrailerRefusalToken(str, Enum):
    """Named refusal tokens the slice-04 verify path emits on stderr.

    The CLI emits the exit code; the structured token is the cause-of-refusal
    SSOT (earned-trust contract -- the exit code is the gate, the token is
    documentation). Same pattern as ``AntiOmissionVerdict`` for slices 02/03.
    """

    TRAILER_MISMATCH = "TrailerMismatch"  # exit 1 -- trailer != re-derived projection


# TrailerRefusalToken -> exit code (single-element table; mirrors the EXIT_CODE_BY_*
# pattern slices 02/03 use so the slice-04 step methods read the same shape).
EXIT_CODE_BY_TRAILER_REFUSAL: dict[TrailerRefusalToken, int] = {
    TrailerRefusalToken.TRAILER_MISMATCH: 1,
}


class CallGraphLayer(str, Enum):
    """The two layers of the slice-04 AT3 architecture-test (G5 two-layer).

    The architecture-test is a STATIC AST check (no subprocess, no
    composition root) -- it is the only slice-04 scenario where the driving
    port is the repository source-tree itself, not a CLI. The two layers
    compose into a closed-world contract on the ledger writer's callers.
    """

    DENYLIST = "denylist"  # (a) -- no Agent(...) / subagent / claude -p dispatch reaches the engine fn
    ALLOWLIST = "allowlist"  # (b) -- the only callers live in a whitelisted set of src/des/ modules


# Repository-relative path to the deterministic-engine ledger writer slice-04
# AT3 inspects. The architecture-test scans every other module's AST for
# call-sites resolving to this dotted name; non-allowlisted callers fail.
LEDGER_WRITER_MODULE: str = "src.des.adapters.driven.ledger.coverage_map_signoff_writer"
LEDGER_WRITER_FUNCTION: str = "write_coverage_map_signed_off"


# =====================================================================
# SLICE-05 -- omission-class attestation domain vocabulary.
# =====================================================================
#
# The slice-05 ATs probe the cardinality-agnostic attestation contract: the
# `## Signoff` block's `omission-classes-attested:` list must cover every
# class-id present in `nWave/data/omission-classes.json` -- N classes, not a
# hard-coded six. An empty or unparseable file is `MalformedInput` (exit 2)
# rather than a vacuous pass (RC-G1 non-empty floor, §4.1a).


class OmissionClassListShape(str, Enum):
    """One of the §4.1a outline equivalence classes for the imported list.

    Slice-05 AT3 Scenario Outline rows -- each row witnesses one cardinality
    or parseability case (Mandate 9 layer-3 example-only; closed finite
    domain). FIVE_CLASSES + SEVEN_CLASSES probe the cardinality-agnostic
    surface (G8). EMPTY + UNPARSEABLE probe the RC-G1 non-empty floor.
    """

    FIVE_CLASSES = "five-classes"
    SEVEN_CLASSES = "seven-classes"
    EMPTY = "empty"
    UNPARSEABLE = "unparseable"


# Gherkin phrase -> OmissionClassListShape (slice-05 AT3 outline rows).
OMISSION_CLASS_SHAPE_BY_PHRASE: dict[str, OmissionClassListShape] = {
    "a list of five named classes": OmissionClassListShape.FIVE_CLASSES,
    "a list of seven named classes": OmissionClassListShape.SEVEN_CLASSES,
    "an empty list with zero entries": OmissionClassListShape.EMPTY,
    "a list that cannot be parsed": OmissionClassListShape.UNPARSEABLE,
}


class OmissionClassVerdict(str, Enum):
    """Named refusal tokens / verdicts the slice-05 verify path produces.

    `SIGNOFF_MISSING` is reused from `AntiOmissionVerdict` for AT1 (the
    `## Signoff` block omits an attested class-id -- a missing-signoff
    refusal token already exists). The slice-05 outline also reuses
    `CoverageMapVerdict.MALFORMED` for the RC-G1 non-empty-floor cases.
    The composition layer wires both via the verdict phrase map below.
    """

    SIGNOFF_MISSING = "SignoffMissing"  # AT1 -- attested omission class missing
    ACCEPTED = "rendered"  # outline pass -- gate accepts the coverage map
    MALFORMED = "MalformedInput"  # outline floor -- empty/unparseable list


# Gherkin verdict-phrase -> OmissionClassVerdict (slice-05 AT3 outline rows).
OMISSION_CLASS_VERDICT_BY_PHRASE: dict[str, OmissionClassVerdict] = {
    "the verify gate accepts the coverage map": OmissionClassVerdict.ACCEPTED,
    "the verify gate refuses for a malformed input": OmissionClassVerdict.MALFORMED,
}


# OmissionClassVerdict -> process exit code. ACCEPTED is exit 0; SIGNOFF_MISSING
# is exit 1; MALFORMED is exit 2 -- mirroring the CoverageMapVerdict /
# AntiOmissionVerdict tables for slice-02/03 so step bodies read the same
# shape.
EXIT_CODE_BY_OMISSION_CLASS_VERDICT: dict[OmissionClassVerdict, int] = {
    OmissionClassVerdict.ACCEPTED: 0,
    OmissionClassVerdict.SIGNOFF_MISSING: 1,
    OmissionClassVerdict.MALFORMED: 2,
}


# =====================================================================
# SLICE-06 -- touchpoint wiring domain vocabulary.
# =====================================================================
#
# The slice-06 ATs probe the BOTH-TOUCHPOINT wiring: the `verify_coverage_map
# verify --touchpoint <name>` CLI runs at the DISTILL-exit handoff to DELIVER
# and again at the DELIVER-exit handoff to feature-end. The U4 SubagentStop
# enforcer (and its verify_deliver_integrity CLI mirror) is the consumer that
# turns a missing heartbeat into a feature-end block -- the env-e2e + walking-
# skeleton 5th-sibling pattern.


class Touchpoint(str, Enum):
    """One of the two `verify_coverage_map verify --touchpoint <name>` modes.

    The DISTILL exit fires on the DISTILL -> DELIVER handoff (catches an
    absent / unsigned / structurally-incomplete coverage-map). The DELIVER
    exit fires on the DELIVER -> feature-end handoff (catches a coverage-map
    that went stale during DELIVER -- body edit OR AT-population change).
    """

    DISTILL_EXIT = "distill_exit"
    DELIVER_EXIT = "deliver_exit"


class UnsignedState(str, Enum):
    """One of the three DISTILL-exit refusal causes (slice-06 AT1 outline).

    Closed finite domain (Mandate 9 layer-3 example-only). Each row witnesses
    one untrustworthy-coverage-map equivalence class the verify gate must
    refuse at the DISTILL exit.
    """

    ABSENT = "absent"
    UNSIGNED = "unsigned"
    STRUCTURAL_INCOMPLETE = "structural-incomplete"


# Gherkin phrase -> UnsignedState (slice-06 AT1 outline rows).
UNSIGNED_STATE_BY_PHRASE: dict[str, UnsignedState] = {
    "absent from the feature distill directory": UnsignedState.ABSENT,
    "present but not signed by any human": UnsignedState.UNSIGNED,
    "present and signed but missing a mandatory section": (
        UnsignedState.STRUCTURAL_INCOMPLETE
    ),
}


class StalenessCause(str, Enum):
    """One of the two DELIVER-exit staleness causes (slice-06 AT2 outline).

    G2 two-sensor enum (feature-delta §6.4): BODY_EDIT moves the §5.3 digest
    so `verify_coverage_map` refuses with `SignoffStale`; AT_DROP changes the
    `.feature` `@covers:` tag population but leaves the coverage-map body
    untouched, so the digest does NOT move -- the anti-omission re-run is
    the real sensor and the gate refuses with `OmissionDetected`. Two
    distinct sensors, two distinct exit names -- they must not be conflated.
    """

    BODY_EDIT = "body-edit"
    AT_DROP = "at-drop"


# Gherkin phrase -> StalenessCause (slice-06 AT2 outline rows).
STALENESS_CAUSE_BY_PHRASE: dict[str, StalenessCause] = {
    "the acceptance designer edited a signed section of the coverage map": (
        StalenessCause.BODY_EDIT
    ),
    "an acceptance scenario carrying a covers tag was dropped": StalenessCause.AT_DROP,
}


class StalenessVerdict(str, Enum):
    """The two DELIVER-exit refusal tokens (slice-06 AT2 outline verdict column).

    Mapped one-to-one to the `StalenessCause` enum: `BODY_EDIT -> SIGNOFF_STALE`,
    `AT_DROP -> OMISSION_DETECTED`. The composition layer asserts both the
    exit code AND the structured stderr token (earned-trust contract -- the
    exit code is the gate, the token is documentation).
    """

    SIGNOFF_STALE = "SignoffStale"
    OMISSION_DETECTED = "OmissionDetected"


# Gherkin verdict-phrase -> StalenessVerdict (slice-06 AT2 outline verdict cells).
STALENESS_VERDICT_BY_PHRASE: dict[str, StalenessVerdict] = {
    "the verify gate refuses for a stale signoff": StalenessVerdict.SIGNOFF_STALE,
    "the verify gate refuses for an undeclared omission": (
        StalenessVerdict.OMISSION_DETECTED
    ),
}


# Heartbeat event names the verify_coverage_map gate emits to the AT-completion
# ledger on a passing touchpoint (slice-06). The U4 SubagentStop enforcer (and
# its verify_deliver_integrity CLI mirror) is the consumer that turns a
# missing heartbeat into a feature-end block -- env-e2e + walking-skeleton 5th-
# sibling pattern.
COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT: str = "CoverageMapVerifiedAtDistillExit"
COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT: str = "CoverageMapVerifiedAtDeliverExit"
