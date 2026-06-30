"""Step definitions: the discuss surfaces carry the caveman reasoning mandate
and the new epic-mode text is caveman-native.

discuss-epic-mode slice-07 (the caveman reasoning mandate + the caveman-native
audit of the new epic-mode text). FINAL slice.

Honest mechanical-vs-prompt boundary: the caveman reasoning mandate + the epic-mode
sections are LLM-authored prose (DESIGN: the slice's "code" is SKILL / AGENT text,
NO ``src/des`` surface; mandate-only re-scope). The QUALITATIVE "reads dry +
domain-coherent" judgment is routed to the Sentinel review of this slice (the LSC-4
prose-owned-split precedent). These ATs pin the STRUCTURAL contract over the REAL
``nWave/`` files (read-only, Layer 3 FS acceptance, the slice-06 dogfood model one
wave-surface up):
  - AT-1 mandate presence: the discuss execution surfaces (SKILL + the
    nw-product-owner agent that EXECUTES the discuss wave) carry the three
    load-bearing mandate clauses. ACTIVE-RED -- absent today.
  - AT-2 native style: the NEW epic-mode sections carry tables + zero
    narrative-padding markers. WITNESS -- authored caveman-native by instruction.
  - AT-3 zero compression: a pre-existing SKILL.md section is preserved across the
    mandate insertion. WITNESS -- the state-delta inverse of the SUPERSEDED
    retro-compression target.

Layer 3 (FS acceptance). Example-only, no PBT machinery (Mandate 9/11): the audit is
a finite, enumerable closed contract over the discuss surfaces + the closed set of
new epic-mode section headings.

Step bodies delegate to ``CavemanComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a composition observation plus a single
assertion, or a typed lookup plus a composition call.

Active-RED contract (atdd_pure): AT-1 FAILS on the current tip (the caveman
reasoning mandate is undefined in any discuss surface -- the audit reads ABSENT) and
PASSES once slice-07 lands. AT-2/AT-3 are WITNESSES (GREEN today). The composition
module imports ZERO production code, so the RED is a semantic AssertionError, never
a collection / import error.
"""

from __future__ import annotations

from pytest_bdd import given, scenarios, then, when

from .composition import CavemanComposition
from .domain_types import (
    CompressionVerdict,
    DiscussSurface,
    MandatePresence,
    NativeStyleVerdict,
)


scenarios("../epic-mode-caveman.feature")


# --- Given ------------------------------------------------------------------


@given(
    "the discuss execution surfaces on the real nWave files",
    target_fixture="caveman",
)
def given_discuss_surfaces() -> CavemanComposition:
    """Establish the composition over the REAL nWave/ discuss surfaces (read-only)."""
    return CavemanComposition()


# --- When -------------------------------------------------------------------


@when("the maintainer audits the discuss surfaces for the caveman reasoning mandate")
def when_audit_mandate(caveman: CavemanComposition) -> None:
    """Audit the discuss execution surfaces for the caveman reasoning mandate (AT-1)."""
    caveman.audited_skill = caveman.observe_mandate_presence(DiscussSurface.SKILL)
    caveman.audited_agent = caveman.observe_mandate_presence(DiscussSurface.AGENT)


@when("the maintainer audits the new epic-mode sections for caveman-native style")
def when_audit_native(caveman: CavemanComposition) -> None:
    """Audit the new epic-mode sections for caveman-native house style (AT-2)."""
    caveman.audited_native = caveman.observe_native_style()


@when("the maintainer audits the mandate insertion for retroactive compression")
def when_audit_compression(caveman: CavemanComposition) -> None:
    """Audit the mandate insertion for retroactive compression (AT-3)."""
    caveman.audited_compression = caveman.observe_compression()


# --- Then -------------------------------------------------------------------


@then("the discuss skill surface carries the caveman reasoning mandate")
def then_skill_carries_mandate(caveman: CavemanComposition) -> None:
    assert caveman.audited_skill is MandatePresence.PRESENT, (
        "the discuss SKILL surface does not carry the caveman reasoning mandate "
        "(verdict-first / tables / depth-via-rigor) -- AT-1 active-RED"
    )


@then("the discuss-wave agent surface carries the caveman reasoning mandate")
def then_agent_carries_mandate(caveman: CavemanComposition) -> None:
    assert caveman.audited_agent is MandatePresence.PRESENT, (
        "the nw-product-owner agent surface (the discuss-wave executor) does not "
        "carry the caveman reasoning mandate -- AT-1 active-RED"
    )


@then("every new epic-mode section is authored caveman-native")
def then_sections_native(caveman: CavemanComposition) -> None:
    assert caveman.audited_native is NativeStyleVerdict.NATIVE, (
        "a new epic-mode section is not caveman-native (missing tables or carrying "
        "narrative-padding markers) -- AT-2 witness"
    )


@then("the pre-existing discuss skill section is preserved")
def then_section_preserved(caveman: CavemanComposition) -> None:
    assert caveman.audited_compression is CompressionVerdict.PRESERVED, (
        "a pre-existing discuss skill section was removed by the mandate insertion "
        "-- retroactive compression is out of scope (AT-3 witness)"
    )
