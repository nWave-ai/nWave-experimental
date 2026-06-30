"""Domain types for the algebra-projections-enforced slice-05 acceptance slice.

slice-05 = the fail-closed boundary of the registry-section check (DISCUSS WD-3
boundary / DESIGN DA-5 / DD-A5, the LAST slice). DISCUSS DoD:
"Unknown-wave -> REJECT; unreadable registry -> INDETERMINATE (degrade-LOUD,
never silent green)."

It PROMOTES the slice-01 degrade-LOUD precursor to TYPED verdicts: at HEAD the
``_run_require_registry_sections`` shell, when ``read_wave_output_contract``
returns ``None`` (the registry the check reads is absent / undecodable), prints a
plain-text ``error: ... is unreadable`` to stderr and returns exit 1 WITHOUT a
structured JSON ``verdict`` line (``validate_feature_delta.py:1224-1231``). That is
degrade-LOUD-by-exit but NOT degrade-LOUD-by-verdict: a composition reading the
structured token sees NOTHING and must guess. slice-05 closes that — the boundary
emits a closed-set verdict token so the boundary is observable, never a silent
green and never a guess.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed once
here as a typed enum / NewType. Step bodies and the composition consume these
typed parameters — no raw ``str`` where a domain enum exists, no control flow in
step bodies.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A wave id whose registry (``nWave/waves/<wave>.yaml``) the check would read. For
# slice-05 the wave is either a NON-canonical name (unknown-wave) or a canonical
# name whose registry file is unreadable (the INDETERMINATE boundary).
WaveId = NewType("WaveId", str)


class BoundaryVerdict(str, Enum):
    """User-observable verdict of one registry-section check at the fail-closed
    boundary (slice-05).

    The slice-05 boundary promotes the slice-01 ``None`` -> ``return 1``-without-
    verdict degrade precursor to TWO typed closed-set verdict tokens. The verdict
    is read from the STRUCTURED JSON ``verdict`` token, never from a free-text
    stderr / stdout substring.

    UNKNOWN_WAVE            -- token ``unknown-wave``: the ``<wave>`` argument names
                              a wave that has NO registry entry at all (a
                              non-canonical wave name). The cross-check cannot run
                              because there is no contract to cross-check against,
                              and the wave is not a known wave whose registry is
                              merely missing -> a deterministic REJECT. (DESIGN
                              DA-5 / DD-A5(b): unknown-wave -> REJECT.)
    INDETERMINATE          -- token ``indeterminate`` (already a §17 GateVerdict
                              token): the ``<wave>`` argument names a KNOWN wave but
                              its registry file is unreadable (absent / garbled /
                              undecodable). The check refuses to decide LOUD rather
                              than silently passing — a missing/garbled registry is
                              NEVER a silent green. (DESIGN DA-5 / DD-A5(b):
                              unreadable registry -> INDETERMINATE; mirrors
                              ``verify_wave_contract_coherence._indeterminate``.)
    ACCEPTED               -- token ``accepted``: emitted on the byte-stable happy
                              path (a known wave with a readable registry + an
                              all-declared delta). slice-05 pins it ONLY as the
                              never-reached-on-the-boundary preservation witness:
                              the boundary verdicts must NEVER collapse a boundary
                              case into ``accepted`` (the un-gameable contract).
    UNRECOGNISED_INVOCATION -- NO structured ``verdict`` token in stdout: the CLI
                              produced no JSON verdict line. At HEAD an unknown-wave
                              / unreadable-registry invocation lands here (the shell
                              prints stderr + exits 1 with NO JSON envelope) — this
                              is the active-RED signal the slice-05 DELIVER promotes
                              into a typed verdict, NOT a real verdict.
    """

    UNKNOWN_WAVE = "unknown_wave"
    INDETERMINATE = "indeterminate"
    ACCEPTED = "accepted"
    UNRECOGNISED_INVOCATION = "unrecognised_invocation"


#: The closed ``verdict`` token set the slice-05 boundary CLI emits under
#: ``--require-registry-sections <wave> --format=json``. This mapping IS the
#: structured contract the slice-05 crafter must implement — the AT reads the
#: token, never a free-text stderr / stdout substring. An off-contract or absent
#: token is handled by the composition (raise / UNRECOGNISED) so a wrong token
#: fails loudly, never silently misclassifies a boundary case as a pass.
#:
#: ``indeterminate`` reuses the existing §17 GateVerdict token verbatim (it is NOT
#: a new sixth token — the OSS hook-only mandate forbids new GateVerdict tokens);
#: ``unknown-wave`` is the additive REJECT token (a refusal, non-zero exit, NOT a
#: GateVerdict — it is a section-check verdict in the same family as slice-01's
#: ``undeclared-section``).
BOUNDARY_VERDICT_TOKEN: dict[str, BoundaryVerdict] = {
    "accepted": BoundaryVerdict.ACCEPTED,
    "unknown-wave": BoundaryVerdict.UNKNOWN_WAVE,
    "indeterminate": BoundaryVerdict.INDETERMINATE,
}


class BoundaryCase(str, Enum):
    """The fail-closed boundary case the registry-section check is driven into.

    UNKNOWN_WAVE       -- the ``<wave>`` argument is a NON-canonical wave name
                          (``bogus``) that has no registry entry. The check must
                          emit ``unknown-wave`` (REJECT) — a deterministic refusal,
                          never ``accepted``, never a crash/stacktrace.
    UNREADABLE_GARBLED -- the ``<wave>`` argument is a KNOWN wave whose
                          ``<wave>.yaml`` registry file exists but is GARBLED
                          (invalid bytes / undecodable). The check must emit
                          ``indeterminate`` (degrade-LOUD) — a refusal-to-decide,
                          never ``accepted``, never a crash.
    UNREADABLE_ABSENT  -- the ``<wave>`` argument is a KNOWN wave whose
                          ``<wave>.yaml`` registry file is ABSENT (the registry the
                          known wave should have is missing). The check must emit
                          ``indeterminate`` (degrade-LOUD) — the same refusal class
                          as garbled; a known wave's missing registry is an
                          infrastructure fault, NOT an unknown wave and NEVER a
                          silent green.
    KNOWN_READABLE     -- a KNOWN wave (``discuss``) with a readable registry + an
                          all-declared delta. The byte-stable happy-path
                          preservation witness: the boundary promotion must NOT
                          regress the slice-01/03 happy path to a boundary verdict.
    """

    UNKNOWN_WAVE = "unknown_wave"
    UNREADABLE_GARBLED = "unreadable_garbled"
    UNREADABLE_ABSENT = "unreadable_absent"
    KNOWN_READABLE = "known_readable"


# Gherkin-phrase -> typed-value lookups. Keeping these as module-level dicts lets
# each step body stay a single typed lookup + a single composition call
# (Mandate-12 criterion 3: no control flow in step bodies).

# Keyed by the Gherkin phrase that follows "the maintainer checks " in each Given.
BOUNDARY_CASE_BY_PHRASE: dict[str, BoundaryCase] = {
    "a feature-delta against a wave the registry never declared": (
        BoundaryCase.UNKNOWN_WAVE
    ),
    "a feature-delta against a known wave whose registry file is garbled": (
        BoundaryCase.UNREADABLE_GARBLED
    ),
    "a feature-delta against a known wave whose registry file is missing": (
        BoundaryCase.UNREADABLE_ABSENT
    ),
    "a feature-delta against a known wave with a readable registry": (
        BoundaryCase.KNOWN_READABLE
    ),
}

BOUNDARY_VERDICT_BY_PHRASE: dict[str, BoundaryVerdict] = {
    "rejects the check for an unknown wave": BoundaryVerdict.UNKNOWN_WAVE,
    "refuses to decide and degrades to indeterminate": BoundaryVerdict.INDETERMINATE,
    "accepts the feature-delta": BoundaryVerdict.ACCEPTED,
}
