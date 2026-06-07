"""Domain types for the fix-design-component-manifest acceptance set.

F-DESIGN-COMPONENT-MANIFEST (Mandate-12 criterion 1). Every domain noun used in
the five slices' Gherkin is expressed once here as a typed enum / NewType /
frozen dataclass. The composition root consumes these typed parameters; step
bodies coerce a Gherkin phrase to a typed value via the ``*_BY_PHRASE`` maps and
delegate -- no raw ``str`` where a domain enum exists, no inline business logic.

Vocabulary shared across all five slice feature files (slice-01..slice-05) and
their step modules -- the SSOT for the manifest's domain language.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "fix-design-component-manifest").
FeatureId = NewType("FeatureId", str)

# A `path::symbol` SUT reference (e.g. "scripts/cli/validate_component_manifest.py::main").
SutReference = NewType("SutReference", str)


class ManifestVerdict(str, Enum):
    """The exit-code contract of the validate_component_manifest CLI (§5).

    The exit codes are the shared SSOT both downstream gates rely on; the
    error *identifiers* are gate-local. The CLI emits the code, not the name.
    """

    VALID = "valid"  # exit 0 -- schema-valid, every sut: symbol grounded
    STALE = "stale"  # exit 1 -- a sut: symbol is not grep-findable
    MALFORMED = "malformed"  # exit 2 -- schema-invalid / unknown schema-version


# ManifestVerdict -> process exit code (SSOT for the exit-code contract).
EXIT_CODE_BY_VERDICT: dict[ManifestVerdict, int] = {
    ManifestVerdict.VALID: 0,
    ManifestVerdict.STALE: 1,
    ManifestVerdict.MALFORMED: 2,
}


class ManifestState(str, Enum):
    """The four shape states resolve_manifest_state() classifies into (§5).

    A pure SHAPE classification -- grounding is NOT in this universe (F6).
    Mirrors scripts.cli.resolve_manifest_state.ManifestState; re-declared here
    so the acceptance vocabulary does not import a RED scaffold at module load.
    """

    A = "A"  # present, schema-valid, unbounded-input-domains non-empty
    B = "B"  # explicitly-empty + rationale, OR not-applicable marker + reason
    C = "C"  # absent, no marker -- caller fails closed
    D = "D"  # present, schema-invalid / malformed -- caller fails closed


class NotApplicableReason(str, Enum):
    """The reason a `component-manifest: not-applicable` marker MUST carry (V5).

    The population-attractor telemetry distinguisher: legacy markers decay as
    features re-enter DESIGN; a rising count of genuinely-no-sut is the smell.
    """

    LEGACY_PRE_ARTIFACT = "legacy-pre-artifact"
    GENUINELY_NO_SUT = "genuinely-no-sut"


class MalformedShape(str, Enum):
    """A way a component-manifest.yaml can be schema-invalid (slice-01 AT2, C6).

    The closed enumeration of malformed-shape equivalence classes the
    validation CLI must reject fail-closed with exit 2. Each member is the
    canonical-category label of one C6 robustness partition.
    """

    MISSING_UNBOUNDED_KEY = "missing-unbounded-input-domains-key"
    EMPTY_WITHOUT_RATIONALE = "empty-list-without-rationale"
    UNKNOWN_SCHEMA_VERSION = "unknown-forward-incompatible-schema-version"
    NOT_A_MAPPING = "not-a-yaml-mapping"
    MISSING_SCHEMA_VERSION = "missing-schema-version-key"


class CanonicalCategory(str, Enum):
    """The nw-at-completeness-check taxonomy category a domain entry maps to.

    The `canonical-category:` field of an unbounded-input-domains entry -- the
    schema's closed enum (C2 | C5 | C6 | C7).
    """

    C2 = "C2"
    C5 = "C5"
    C6 = "C6"
    C7 = "C7"


# Gherkin phrase -> MalformedShape (slice-01 Scenario Outline Examples rows).
MALFORMED_SHAPE_BY_PHRASE: dict[str, MalformedShape] = {
    "the unbounded-input-domains key is absent": MalformedShape.MISSING_UNBOUNDED_KEY,
    "the input-domains list is empty with no rationale": (
        MalformedShape.EMPTY_WITHOUT_RATIONALE
    ),
    "the manifest declares a future schema version": (
        MalformedShape.UNKNOWN_SCHEMA_VERSION
    ),
    "the manifest is not a structured mapping": MalformedShape.NOT_A_MAPPING,
    "the schema version is absent": MalformedShape.MISSING_SCHEMA_VERSION,
}

# Gherkin phrase -> NotApplicableReason (slice-03 Examples rows).
NOT_APPLICABLE_REASON_BY_PHRASE: dict[str, NotApplicableReason] = {
    "the design wave predates the manifest": (NotApplicableReason.LEGACY_PRE_ARTIFACT),
    "the component genuinely has no unbounded input": (
        NotApplicableReason.GENUINELY_NO_SUT
    ),
}

# Gherkin phrase -> ManifestState (slice-03 Examples rows).
MANIFEST_STATE_BY_PHRASE: dict[str, ManifestState] = {
    "valid with declared input domains": ManifestState.A,
    "honestly empty": ManifestState.B,
    "absent": ManifestState.C,
    "malformed": ManifestState.D,
}
