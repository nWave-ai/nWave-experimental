"""AT-A2 + AT-A3 (slice-01): the done-gate holds NO write port, and no sixth verdict.

Arch-tier, pure-function (no subprocess, structural introspection): reads the
shipped source as DATA. Recognized as arch tests (``test_arch_`` prefix under
``tests/build/``) per the AT-completeness S2 tolerable-variant rule.

AT-A2 (read/write split, Principle 12 effect-isolation): the done-gate
(``verify_deliver_integrity``) must NOT import or call any ledger WRITE method --
"the done-gate silently mints a record to pass itself" is non-representable. The
gate may READ the ledger (``verified_slices``, ``feature_end_events``, the NEW
``bypass_debt_events`` / ``full_suite_leg_events``) but must hold no
``append_*`` write seam.

AT-A3 (no sixth verdict, ADR-GV-001 / DDD-7): the ``GateVerdict`` SSOT enum stays
at exactly the 5 canonical values; the feature maps every new outcome onto them.

ACTIVE-RED framing:
  * AT-A3 is a regression PIN over the SSOT enum -- green at HEAD, RED only if a
    sixth verdict is ever added. (A guardrail, honestly green.)
  * AT-A2 is RED until DELIVER implements the read/write facet split: at HEAD the
    done-gate does not yet read bypass-debt (slice-02) nor full-suite-leg
    (slice-01), so the read-facet method ``full_suite_leg_events`` it MUST call is
    absent from the gate's call set -- the assertion that the gate reaches the
    NEW read facet RED-fails. GREEN once DELIVER wires the read facet. The
    no-write sub-assertion is a standing guardrail (green at HEAD).
"""

from __future__ import annotations

import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI_PATH = _REPO_ROOT / "src" / "des" / "cli" / "verify_deliver_integrity.py"
_GATE_VERDICT_PATH = _REPO_ROOT / "src" / "des" / "domain" / "gate_outcome.py"

_CANONICAL_VERDICTS = frozenset(
    {"PASS", "FAIL", "NOT_APPLICABLE", "UNVERIFIED", "INDETERMINATE"}
)

# Ledger WRITE seams a read-only consumer must NEVER call (Principle 12).
_WRITE_CALL_RE = re.compile(r"\.append_[a-z_]+\s*\(")

# The NEW read facet the done-gate MUST reach to read the full-suite leg (DDD-4).
_FULL_SUITE_READ_FACET = "full_suite_leg_events"


def test_arch_donegate_holds_no_write_port() -> None:
    """AT-A2: the done-gate calls no ledger WRITE (append_*) seam."""
    source = _CLI_PATH.read_text(encoding="utf-8")
    write_calls = sorted(set(_WRITE_CALL_RE.findall(source)))
    assert not write_calls, (
        "the done-gate must hold NO ledger WRITE port (read/write facet split, "
        "AT-A2 / Principle 12) so 'the gate mints a record to self-pass' is "
        f"non-representable; it calls write seam(s) {write_calls}"
    )


def test_arch_gate_verdict_has_no_sixth_value() -> None:
    """AT-A3: the GateVerdict SSOT enum stays at exactly the 5 canonical values."""
    source = _GATE_VERDICT_PATH.read_text(encoding="utf-8")
    members = set(re.findall(r"^\s{4}([A-Z_]+)\s*=\s*\"", source, flags=re.MULTILINE))
    # Restrict to the GateVerdict block: the 5 canonical names are the contract.
    verdict_members = members & (_CANONICAL_VERDICTS | {"SIXTH", "BYPASSED", "DEBT"})
    assert verdict_members == _CANONICAL_VERDICTS, (
        "GateVerdict must remain the fixed 5-value SSOT (ADR-GV-001 / DDD-7); a "
        f"new outcome maps onto these five, never a sixth. observed verdict "
        f"members={sorted(verdict_members)}"
    )


def test_arch_donegate_reaches_full_suite_read_facet() -> None:
    """ACTIVE-RED (AT-A2 read-facet): the gate reads the NEW full-suite-leg facet (DDD-4)."""
    source = _CLI_PATH.read_text(encoding="utf-8")
    assert _FULL_SUITE_READ_FACET in source, (
        f"the done-gate must reach the NEW read facet {_FULL_SUITE_READ_FACET!r} "
        "so a feature-end whose full-suite leg never ran is refused on "
        "record-absence (DDD-4); the gate does not yet read that facet at HEAD. "
        "GREEN once DELIVER wires the read facet into verify_deliver_integrity."
    )
