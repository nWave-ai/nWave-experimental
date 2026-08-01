# @feature-unified-event-store
"""Tests for the D80 slice-01 prefactor of `telemetry_paths.py` (Mikado node
D80, `docs/mikado/EXECUTION-SSOT-des-optimization.md` line 2608).

Outcome anchor (feature-delta.md [REF] Slice Plan, slice-01): "As an
architect, I can trust telemetry_paths.py no longer routes to directories
nothing writes, so D71/D70 add families onto a clean base." Behaviour-
preserving prefactor -- no new production behaviour, only the `LedgerFamily`
enum shape (DD-3) and `ledger_path()`'s partition-key parameter name (DD-4).

CONTRACT_SHAPE: pure-function
Universe: `LedgerFamily` member set (names + values); `ledger_path()`'s return
value and accepted-keyword surface. The module under test does no I/O
(its own docstring: "This module is pure: it computes paths and touches no
filesystem"), so every fixture here is a plain in-memory `Path`, never
`tmp_path` -- there is nothing to isolate on disk.

Design measurement this file pins (feature-delta.md Prefactoring Assessment +
Correction 5, Tsunami `binding-resolved`): `reads_of("RED_GREEN")` == 0,
`reads_of("FEATURE_END")` == 0 in PRODUCTION. This file is an INDEPENDENT
measurement over TESTS: zero test file in this repo imports `telemetry_paths`
or references `LedgerFamily` today (grep + Tsunami `callers_of("ledger_path")`
confirm the only 3 importers of `telemetry_paths.ledger_path` are
`record_review_verdict.py`, `carpaccio_slice_gate.py`,
`record_examine_verdict.py` -- all production, none test) -- the production
number is never inherited as a stand-in for the test population.

Every test below decides on a measured PROPERTY, never a token DESIGNATION:
the membership tests pin the full POSITIVE member set (name AND value), not
merely "RED_GREEN is absent" -- an empty, unimported, or non-Enum
`LedgerFamily` must not be able to pass by vacuous absence-of-everything.
Members not yet on the enum (`CONTEXT`, `MIKADO`) are looked up via
`getattr(..., default=None)` at test-body runtime, never referenced at
`@pytest.mark.parametrize`/module-collection time -- referencing a
not-yet-existing attribute at collection time would abort the WHOLE file with
a collection error, not the semantic per-test `AssertionError` the
fail-for-right-reason gate requires.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from des.domain.telemetry_paths import LedgerFamily, ledger_path, telemetry_root


# Pure module under test -- no filesystem needed, a literal path is enough and
# keeps every test hermetic without touching disk or a `tmp_path` fixture.
REPO = Path("/repo")

# The full POSITIVE member set this slice leaves behind: name -> value.
# RED_GREEN / FEATURE_END are deliberately absent -- their absence is
# asserted separately (TestDeadFamiliesAreUnconstructible), never implied by
# this dict alone.
EXPECTED_FAMILIES = {
    "ATDD_PURE": "atdd-pure",
    "EXAMINE": "examine",
    "REVIEW": "review",
    "CONTEXT": "context",
    "MIKADO": "mikado",
}

# Families that exist both BEFORE and AFTER this slice -- safe to reference
# directly at parametrize/collection time.
SURVIVING_FAMILIES = [LedgerFamily.ATDD_PURE, LedgerFamily.EXAMINE, LedgerFamily.REVIEW]

_SAFE_KEY = st.from_regex(r"[A-Za-z0-9_-]{1,40}", fullmatch=True)


class TestTelemetryRoot:
    """`telemetry_root` is public API (`__all__`) and is the ONLY place
    `TELEMETRY_ROOT_PARTS` is joined, so every ledger path in the product
    hangs off it. Pinned literally and separately from `ledger_path` -- the
    prefactor must not move the root, and a test that derived its expectation
    from `TELEMETRY_ROOT_PARTS` could not detect it if it did."""

    def test_root_is_the_literal_dot_nwave_telemetry_directory(self):
        # covers: R3
        assert telemetry_root(REPO) == REPO / ".nwave" / "telemetry"


class TestLedgerFamilyIsGenuinelyAStrEnum:
    """Guards the trivial-pass failure mode named in the dispatch: a test
    asserting only "RED_GREEN is not in LedgerFamily" passes if LedgerFamily
    fails to import, is empty, or is not an Enum at all. Pin the TYPE shape
    and the full POSITIVE membership set so absence-of-everything cannot
    masquerade as the property."""

    def test_ledger_family_is_a_str_mixin_enum(self):
        # covers: R2
        assert issubclass(LedgerFamily, Enum)
        assert issubclass(LedgerFamily, str)

    def test_membership_is_exactly_the_five_written_families(self):
        # covers: R1, R2
        actual_names = {member.name for member in LedgerFamily}
        assert actual_names == set(EXPECTED_FAMILIES), (
            "LedgerFamily member NAMES drifted from the D80 slice-01 shape: "
            f"expected exactly {sorted(EXPECTED_FAMILIES)}, got "
            f"{sorted(actual_names)}"
        )

    def test_member_values_are_exactly_the_five_written_directories(self):
        # covers: R1, R2
        actual = {member.name: member.value for member in LedgerFamily}
        assert actual == EXPECTED_FAMILIES


class TestDeadFamiliesAreUnconstructible:
    """R1: RED_GREEN/FEATURE_END routed to `{family}/{feature}.jsonl` paths
    nothing has ever written (Correction 5, `reads_of` == 0 in production,
    binding-resolved). Their removal must make the family unconstructible by
    NAME (attribute access) AND by VALUE (enum lookup), not merely missing
    from a hand-picked assertion list."""

    def test_red_green_attribute_is_gone(self):
        # covers: R1
        assert not hasattr(LedgerFamily, "RED_GREEN")

    def test_feature_end_attribute_is_gone(self):
        # covers: R1
        assert not hasattr(LedgerFamily, "FEATURE_END")

    @pytest.mark.parametrize("dead_value", ["red-green", "feature-end"])
    def test_dead_value_no_longer_constructs_a_member(self, dead_value):
        # covers: R1
        with pytest.raises(ValueError):
            LedgerFamily(dead_value)


class TestNewFamiliesArePresent:
    """R2: CONTEXT + MIKADO added onto the base enum (D71/D70's clean base).
    Looked up via getattr(default=None) so a missing attribute fails this
    ONE test with a clear AssertionError instead of aborting collection of
    the whole file."""

    def test_context_family_constructs_from_its_declared_value(self):
        # covers: R2
        context_member = getattr(LedgerFamily, "CONTEXT", None)
        assert context_member is not None, "LedgerFamily.CONTEXT missing (DD-3)"
        assert LedgerFamily("context") is context_member

    def test_mikado_family_constructs_from_its_declared_value(self):
        # covers: R2
        mikado_member = getattr(LedgerFamily, "MIKADO", None)
        assert mikado_member is not None, "LedgerFamily.MIKADO missing (DD-3)"
        assert LedgerFamily("mikado") is mikado_member


class TestLedgerPathPositionalResolutionForSurvivingFamilies:
    """R3: the 3 production importers (record_review_verdict.py,
    carpaccio_slice_gate.py, record_examine_verdict.py) all call
    ledger_path(repo, family, feature_id) positionally (Tsunami
    `callers_of("ledger_path")`, all 3 confirmed direct-call, positional).
    The prefactor MUST NOT change resolution for any surviving family --
    this is a regression pin, expected GREEN both before and after."""

    @pytest.mark.parametrize(
        ("family", "expected_dir"),
        [
            (LedgerFamily.ATDD_PURE, "atdd-pure"),
            (LedgerFamily.EXAMINE, "examine"),
            (LedgerFamily.REVIEW, "review"),
        ],
    )
    def test_positional_call_resolves_to_the_literal_pre_existing_path(
        self, family, expected_dir
    ):
        """The expectation is spelled out segment by segment, NOT rebuilt from
        `telemetry_root()` / `family.value` -- which is what an earlier version
        of this test did, and it was tautological: recomputing the expected
        path from the same two helpers the implementation calls means moving
        `TELEMETRY_ROOT_PARTS` or editing a member's value shifts BOTH sides
        together, so the comparison can never come out unequal and green
        attests nothing. Demonstrated, not assumed -- see the commit message:
        with the root parts mutated, the literal form below fails and the
        recomputed form passed.

        A literal is also the honest expectation here: these are the paths
        where the 3,079 atdd-pure / 334 examine / 4 review records measured on
        the main checkout physically live. If this test goes red, existing
        ledgers just became unreadable."""
        # covers: R3
        result = ledger_path(REPO, family, "some-partition-key")

        assert (
            result
            == REPO / ".nwave" / "telemetry" / expected_dir / "some-partition-key.jsonl"
        )

    @pytest.mark.parametrize(
        ("member_name", "expected_dir"), [("CONTEXT", "context"), ("MIKADO", "mikado")]
    )
    def test_new_family_resolves_to_its_own_literal_directory(
        self, member_name, expected_dir
    ):
        # covers: R2, R3
        member = getattr(LedgerFamily, member_name, None)
        assert member is not None, f"LedgerFamily.{member_name} missing (DD-3)"

        result = ledger_path(REPO, member, "some-partition-key")

        assert (
            result
            == REPO / ".nwave" / "telemetry" / expected_dir / "some-partition-key.jsonl"
        )

    @pytest.mark.parametrize("family", SURVIVING_FAMILIES)
    @given(key=_SAFE_KEY)
    def test_ledger_path_is_a_deterministic_pure_function_of_its_inputs(
        self, family, key
    ):
        """CONTRACT_SHAPE: pure-function -- for ANY partition key and any
        surviving family, ledger_path is total and deterministic: same
        inputs always produce the same path, always under
        family.value/{key}.jsonl. Layer-1 domain pure function -> PBT full
        (Mandate 9), not example-pinned.

        The parent-directory leg pins the root LITERALLY rather than via
        `telemetry_root(REPO)`, for the same reason as the example-based test
        above -- an expectation built from the helper under test moves with it
        and cannot fail."""
        # covers: R3
        first = ledger_path(REPO, family, key)
        second = ledger_path(REPO, family, key)
        assert first == second
        assert first.name == f"{key}.jsonl"
        assert first.parent == REPO / ".nwave" / "telemetry" / family.value

    def test_rejects_a_non_ledger_family_naming_only_current_families(self):
        # covers: R1, R2
        with pytest.raises(TypeError) as exc_info:
            ledger_path(REPO, "red-green", "x")  # raw str, never a member

        accepted_clause = str(exc_info.value).split("accepted values:")[-1]
        assert "red-green" not in accepted_clause
        assert "feature-end" not in accepted_clause
        for expected_value in EXPECTED_FAMILIES.values():
            assert expected_value in accepted_clause, (
                f"{expected_value!r} missing from the refusal's accepted-values "
                "list -- the WHAT/WHY/HOW message must stay in sync with the "
                "live LedgerFamily membership (DD-3)"
            )


class TestLedgerPathPartitionKeyGeneralization:
    """DD-4: ledger_path()'s partition-identifying parameter generalizes
    `feature_id` -> `partition_key` (a doc rename; every measured call site
    is positional, so no production caller breaks). This matters beyond mere
    naming: DD-5 (a later slice) has session-scoped families pass a
    session_id through this exact parameter, so the KEYWORD a caller may use
    is itself part of the contract this slice must establish."""

    def test_partition_key_keyword_is_the_accepted_contract(self):
        # covers: R4
        result = ledger_path(
            REPO, family=LedgerFamily.ATDD_PURE, partition_key="my-feature"
        )
        assert (
            result == REPO / ".nwave" / "telemetry" / "atdd-pure" / "my-feature.jsonl"
        )

    def test_positional_and_partition_key_keyword_calls_agree(self):
        # covers: R3, R4
        positional = ledger_path(REPO, LedgerFamily.EXAMINE, "abc")
        keyword = ledger_path(REPO, family=LedgerFamily.EXAMINE, partition_key="abc")
        assert positional == keyword
