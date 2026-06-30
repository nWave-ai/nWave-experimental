"""Domain types for the algebra-projections-enforced slice-01 acceptance slice.

DISCUSS WD-1/WD-3(a) + DESIGN DA-1/DA-2/DA-6 (Mandate-12 criterion 1). Every
domain noun used in the Gherkin is expressed once here as a typed enum or
NewType. Step bodies and the composition service consume these typed parameters
— no raw ``str`` where a domain enum exists, no control flow in step bodies.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A wave id whose registry (``nWave/waves/<wave>.yaml``) the check reads.
WaveId = NewType("WaveId", str)


class RegistrySectionVerdict(str, Enum):
    """User-observable verdict of one registry-section check invocation.

    The slice-01 CLI is invoked with ``--require-registry-sections <wave>
    --format=json`` and emits a single JSON object whose ``verdict`` field is one
    of a closed token set. The verdict is read from that STRUCTURED token, never
    from free-text stdout substrings.

    ACCEPTED                -- token ``accepted``: every ``[REF]`` section the
                               feature-delta carries is declared by the wave's
                               registry ``output_contract.ref_sections``.
    UNDECLARED_SECTION      -- token ``undeclared-section``: the feature-delta
                               carries a ``[REF]`` section the wave's registry
                               does NOT declare (WD-3 direction (a)). The
                               diagnostic NAMES the offending section.
    UNRECOGNISED_INVOCATION -- NO structured ``verdict`` token in stdout: the CLI
                               did not produce JSON output. At HEAD the
                               ``--require-registry-sections`` flag is unknown, so
                               every invocation lands here — this is the
                               active-RED signal, NOT a real verdict.
    """

    ACCEPTED = "accepted"
    UNDECLARED_SECTION = "undeclared_section"
    UNRECOGNISED_INVOCATION = "unrecognised_invocation"


#: The closed ``verdict`` token set the slice-01 CLI emits under
#: ``--require-registry-sections <wave> --format=json``. This mapping IS the
#: structured contract the slice-01 crafter must implement — the AT reads the
#: token, never a free-text stdout substring. An off-contract or absent token is
#: handled by the composition (raise / UNRECOGNISED) so a wrong token fails
#: loudly, never silently misclassifies. The crafter is free to add further
#: rejection tokens in later slices (e.g. unknown-wave, indeterminate); slice-01
#: only pins ``accepted`` + ``undeclared-section``.
VERDICT_TOKEN: dict[str, RegistrySectionVerdict] = {
    "accepted": RegistrySectionVerdict.ACCEPTED,
    "undeclared-section": RegistrySectionVerdict.UNDECLARED_SECTION,
}


class DeltaShape(str, Enum):
    """The shape of the feature-delta presented to the registry-section check.

    ALL_DECLARED        -- every ``[REF]`` section the feature-delta carries is
                           declared by the discuss registry (the happy path /
                           walking skeleton). The check ACCEPTS.
    UNDECLARED_SECTION  -- the feature-delta carries a ``[REF]`` section absent
                           from the discuss registry ``ref_sections`` (a section
                           id that is in NEITHER the registry NOR the legacy
                           hard-coded list). The check REJECTS, naming it
                           (WD-3 direction (a)).
    LEGACY_TUPLE_ONLY   -- the feature-delta carries a section that the legacy
                           hard-coded ``LOCKED_REF_SECTIONS`` tuple honours
                           (``Reuse Analysis``) but the LIVE discuss registry does
                           NOT declare. A tuple-reading check would PASS it; a
                           live-registry-reading check REJECTS it. This is the
                           discriminator that proves the check reads the registry,
                           not the hard-coded tuple.
    REGISTRY_ONLY       -- the feature-delta carries only a section the LIVE
                           discuss registry declares (``Persona ID``) but the
                           legacy hard-coded tuple omits. A check that whitelisted
                           by the 4-entry tuple would mishandle it; a
                           live-registry-reading direction-(a) check ACCEPTS it
                           (it is declared). The complementary discriminator.
    """

    ALL_DECLARED = "all_declared"
    UNDECLARED_SECTION = "undeclared_section"
    LEGACY_TUPLE_ONLY = "legacy_tuple_only"
    REGISTRY_ONLY = "registry_only"


# Gherkin-phrase -> typed-value lookups. Keeping these as module-level dicts lets
# each step body stay a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

# Keyed by the Gherkin phrase that follows "a feature-delta " in each Given line.
DELTA_SHAPE_BY_PHRASE: dict[str, DeltaShape] = {
    "whose [REF] sections are all declared by the discuss registry": (
        DeltaShape.ALL_DECLARED
    ),
    "carrying a [REF] section the discuss registry does not declare": (
        DeltaShape.UNDECLARED_SECTION
    ),
    "carrying a section honoured by the legacy hard-coded list but "
    "absent from the discuss registry": DeltaShape.LEGACY_TUPLE_ONLY,
    "carrying only a section the discuss registry declares but the "
    "legacy hard-coded list omits": DeltaShape.REGISTRY_ONLY,
}

VERDICT_BY_PHRASE: dict[str, RegistrySectionVerdict] = {
    "accepts the feature-delta": RegistrySectionVerdict.ACCEPTED,
    "rejects the feature-delta for an undeclared section": (
        RegistrySectionVerdict.UNDECLARED_SECTION
    ),
}
