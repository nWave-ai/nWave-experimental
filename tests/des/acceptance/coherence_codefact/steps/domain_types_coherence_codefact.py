"""Typed domain vocabulary for the f-coherence-and-attestation slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-01
Gherkin names is expressed once here as a typed enum / frozen dataclass, so the
composition methods consume typed parameters (no raw ``str`` where an enum
exists). The DSL emerges from these typed concepts -- the slice-01 scenarios
range over the LOCKED capability-id set and the LOCKED ``{provider, confidence,
reason_code}`` token sets, not over decorator proliferation.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports (Mandate-13). The token
*values* below are CONSUMED BYTE-IDENTICAL from the cross-tier-LOCKED Published
Language (``ADR-LA-001`` §2 capability ids + §5a verdict envelope; ratified
with the SF team 2026-06-14; kebab-lowercase; byte-locked). They are NOT
re-authored here -- AT-4 (the byte-lock guard) is the mechanical witness that the
PRODUCTION serialization is byte-identical to the committed locked-vocabulary
fixture; this module is the AT-side mirror used to author the spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# LOCKED Published Language (ADR-LA-001 §2 / §5a) -- CONSUMED byte-identical.
# kebab-lowercase. Renaming ANY of these tokens is the exact cross-tier-lock
# drift AT-4 is designed to catch RED.
# ---------------------------------------------------------------------------


class CapabilityId(Enum):
    """The 5-capability frozen stable core (ADR-LA-001 §2), LOCKED byte-identical."""

    CALLERS_OF = "query.callers-of"
    READS_OF = "query.reads-of"
    NEVER_WIRED = "query.never-wired"
    ATOMS_IN_FILE = "query.atoms-in-file"
    ADR_SECTION = "query.adr-section"


class Provider(Enum):
    """Which adapter answered (ADR-LA-001 §5a; additive field, 1:1 with confidence)."""

    AST = "ast"
    TEXTSEARCH = "textsearch"


class Confidence(Enum):
    """The ONLY cross-seam-readable token (ADR-LA-001 §5a; 1:1 down the chain)."""

    BINDING_RESOLVED = "binding-resolved"  # Tsunami (precise)
    APPROX = "approx"  # AstAdapter (structural)
    NOISY = "noisy"  # TextSearchAdapter (textual, the universal floor)


class ReasonCode(Enum):
    """Cures live-but-non-callable vs genuinely-absent (ADR-LA-001 §5a)."""

    LIVE_NON_CALLABLE = "live-non-callable"
    ABSENT = "absent"


# Frozen LOCKED token *sets* -- the byte-lock guard (AT-4) asserts the production
# serialization equals these sets exactly. Authored as the AT-side SSOT mirror.
LOCKED_CAPABILITY_IDS: frozenset[str] = frozenset(c.value for c in CapabilityId)
LOCKED_PROVIDERS: frozenset[str] = frozenset(p.value for p in Provider)
LOCKED_CONFIDENCES: frozenset[str] = frozenset(c.value for c in Confidence)
LOCKED_REASON_CODES: frozenset[str] = frozenset(r.value for r in ReasonCode)


# ---------------------------------------------------------------------------
# slice-01 scenario vocabulary
# ---------------------------------------------------------------------------


class WiringCase(Enum):
    """The two never-wired cases the slice-01 code-fact gate distinguishes.

    The gate re-derives ``query.never-wired`` (does a net-new effectful symbol
    have a production call-site?) THROUGH the port. The textual floor answers it
    at ``noisy`` confidence -- it must answer BOTH the wired and the never-wired
    case (the always-answer floor invariant), tagged with provenance.
    """

    WIRED = "wired"  # a net-new symbol WITH a production call-site
    NEVER_WIRED = "never-wired"  # a net-new symbol with NO production call-site


class GuardProbe(Enum):
    """The byte-lock guard self-probe states (Earned-Trust, Principle 13).

    PRISTINE -- the committed locked-vocabulary fixture, byte-identical to the
                LOCKED Published Language -> the guard PASSES (no drift).
    DRIFTED  -- a planted-drift variant (e.g. ``binding-resolved`` renamed to
                ``precise``) -> the guard must go RED (drift caught).
    """

    PRISTINE = "PRISTINE"
    DRIFTED = "DRIFTED"


@dataclass(frozen=True)
class CodeFactObservable:
    """The observable slice of a ``CodeFactResult`` the ATs assert on.

    Port-exposed names only (Mandate-8 universe discipline): the envelope's
    ``{provider, confidence}`` provenance + whether a usable (non-empty)
    answer came back + the ``never-wired`` capability's own payload-owned
    disambiguating flag (ADR-LA-001 D9 slice (c), D6-R3: the envelope-level
    ``reason_code`` is deleted -- ``absent``/``live-non-callable`` is now a
    ``never-wired`` *payload* distinction, never an envelope field).
    """

    answered: bool  # a usable answer came back (the always-answer floor)
    provider: str | None  # which adapter answered (LOCKED token)
    confidence: str | None  # the cross-seam-readable confidence (LOCKED token)
    never_wired: bool | None  # the never-wired payload's own disambiguating flag
