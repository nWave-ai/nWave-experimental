"""Domain types for the f-deliver-entry-contract-freeze acceptance suite (Mandate-12).

Every Gherkin domain noun is a typed enum / dataclass here -- the step bodies
consume these typed parameters, never raw ``str`` where an enum exists. The DSL
emerges from the typed vocabulary (one parameterised step per contract-shape, not
one decorator per literal).

The §17 verdict vocabulary mirrors the production ``GateVerdict`` SSOT
(``src/des/domain/gate_outcome.py``). The freeze gate (DDD-4/DDD-5) emits only
PASS / FAIL / INDETERMINATE -- it never emits UNVERIFIED (that is gate-G's
exhaustiveness cap, a different gate) -- but the full LOCKED FIVE are declared so a
Then can assert "one of the SSOT five, no sixth".
"""

from __future__ import annotations

from enum import Enum


class FreezeVerdict(str, Enum):
    """The §17 verdict the DELIVER-entry contract-freeze gate emits.

    DDD-5: present+valid -> PASS; a missing/malformed locked section OR a
    planned-slice-with-no-AT-module -> FAIL; an unreadable feature-delta /
    AT-module set -> INDETERMINATE. The gate never emits UNVERIFIED or
    NOT_APPLICABLE (DDD-4) -- but they are listed so the LOCKED-FIVE assertion
    is honest.
    """

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    UNVERIFIED = "unverified"
    INDETERMINATE = "indeterminate"


# The five SSOT values -- the gate must return one of these, never a sixth
# (ADR-GV-001, AT-A3).
LOCKED_VERDICTS: frozenset[str] = frozenset(v.value for v in FreezeVerdict)


class ContractShape(str, Enum):
    """The structural completeness of the contract a DELIVER-entry presents.

    COMPLETE         -- every locked ``[REF]`` section present-and-valid AND every
                        planned Slice-Plan row has an authored AT module (the
                        walking-skeleton PASS case, CT-1).
    MISSING_SECTION  -- a named locked ``[REF]`` section is absent (CT-2b -> FAIL).
    SLICE_WITHOUT_AT -- a planned Slice-Plan row has no authored AT module
                        (CT-3 -> FAIL).
    UNREADABLE       -- the feature-delta is unreadable/undecodable (CT-6 ->
                        INDETERMINATE, never a false freeze).
    """

    COMPLETE = "complete"
    MISSING_SECTION = "missing_section"
    SLICE_WITHOUT_AT = "slice_without_at"
    UNREADABLE = "unreadable"


class PostFreezeEdit(str, Enum):
    """How the LIVE feature-delta differs from the FROZEN baseline at a per-slice
    re-verify (slice-02, ADR-FLOW-002 D8 / CT-5).

    The freeze is feature-level: once a ``ContractFrozen`` baseline exists, every
    subsequent per-slice DELIVER gate-IN RE-VERIFIES the LIVE feature-delta against
    that baseline. ADR-FLOW-002 D8 (line 101) permits EXACTLY ONE post-freeze
    mutation -- the status-flip "slice shipped"; ANY other mutation is drift and
    must HALT.

    UNCHANGED      -- the live feature-delta is byte-identical to the frozen
                      baseline (a per-slice re-verify with no edits) -> PASS, the
                      freeze re-earned (OUT=IN), no second freeze written (CT-7).
    STATUS_FLIP    -- ONLY a Slice-Plan row status flipped to "shipped" (the one
                      permitted post-freeze mutation, D8 line 101) -> PASS, no halt,
                      no second freeze written.
    EDITED_SECTION -- a locked ``[REF]`` section body was edited after freeze (a
                      value statement / contract row rewritten) -> HALT (drift),
                      the gate names the drifted section (CT-5).
    ADDED_SLICE    -- a Slice-Plan row was ADDED after freeze (the ratification
                      window cannot re-open per-slice) -> HALT (drift), the gate
                      names the added slice (CT-5).
    """

    UNCHANGED = "unchanged"
    STATUS_FLIP = "status_flip"
    EDITED_SECTION = "edited_section"
    ADDED_SLICE = "added_slice"


#: The §17 verdict a re-verify emits on detected drift (CT-5). Drift is a
#: confirmable structural defect -> FAIL (HALT), the same definite class as a
#: missing locked section. The gate never invents a sixth verdict for "drift".
DRIFT_VERDICT = FreezeVerdict.FAIL


class ManifestState(str, Enum):
    """How a ``code-design.manifest.yaml`` participates in the DELIVER-entry
    structural check (slice-03, CT-4 / KPI-3 / ADR-FLOW-004 DDD-5).

    DESIGN is optional (ADR-FLOW-002 D2): a feature MAY ship a code-design
    manifest. When present, its VALIDITY is FOLDED into the freeze gate's
    structural-completeness check via ``validate_component_manifest`` (subprocess,
    F-D-09: it lives under ``scripts/cli/**`` so the gate invokes it as a
    subprocess, never ``from scripts.* import``). When absent, DESIGN was
    consciously skipped and the gate must NOT re-block on manifest grounds.

    VALID   -- a schema-valid manifest whose every ``sut:`` symbol is
               grep-findable (the validator exits 0) -> the fold CONTRIBUTES to
               PASS; the structurally-complete contract still freezes.
    INVALID -- a manifest the validator REFUSES: a stale ``sut:`` symbol (exit 1)
               OR a schema-invalid document (exit 2) -> the fold turns the freeze
               gate FAIL, the diagnostic naming the manifest defect.
    ABSENT  -- no manifest ships (DESIGN consciously skipped) -> NO re-block on
               manifest grounds; the contract freezes on its other halves alone.
    """

    VALID = "valid"
    INVALID = "invalid"
    ABSENT = "absent"
