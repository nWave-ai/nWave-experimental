"""Storage laws for the one restart graph."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from des.application.handover import (
    Blocked,
    HandoverValue,
    StoredHandover,
    _canonical_bytes,
    acquire_delivery_lock,
    create_handover,
    design_basis_sha256,
    design_facts_defect,
    finalize_handover,
    handover_path,
    load_handover,
    read_handover,
    rewrite_handover,
    valid_design_facts,
)
from des.domain.architecture_brief_resolver import DESIGN_ORACLE_LOCATOR_PATTERN
from des.ports.driven_ports.task_invocation_port import (
    ApplicableADR,
    ApplicableImpactClosure,
    DesignFacts,
    DesignTarget,
    ImpactItem,
    LegacyDesignFacts,
    NotApplicable,
    ReuseAnalysis,
    ReuseCandidate,
)


def test_canonical_graph_carries_exact_minimal_bytes_on_restart(
    tmp_path,
) -> None:
    values = (
        HandoverValue("A", (), None),
        HandoverValue("B", ("A",), "docs/brief.md#B"),
    )
    first = create_handover(tmp_path, "deliver", values)
    second = load_handover(tmp_path, "deliver")

    assert isinstance(first, StoredHandover)
    assert isinstance(second, StoredHandover)
    assert first.raw == second.raw == handover_path(tmp_path).read_bytes()
    assert first.raw == (
        b'{"request":"deliver","scope":{"kind":"project"},"values":['
        b'{"observation":"A","dependencies":[],"authority":null},'
        b'{"observation":"B","dependencies":["A"],"authority":"docs/brief.md#B"}]}'
    )
    assert second.values[0].authority is None
    assert second.values[1].authority == "docs/brief.md#B"


def test_reader_rejects_forward_duplicate_old_design_or_typed_authority_facts() -> None:
    forward = b'{"request":"x","values":[{"observation":"A","dependencies":["B"],"authority":null},{"observation":"B","dependencies":[],"authority":null}]}'
    duplicate = b'{"request":"x","values":[{"observation":"A","dependencies":[],"authority":null},{"observation":"B","dependencies":["A","A"],"authority":null}]}'
    old_design = b'{"request":"x","values":[{"observation":"A","dependencies":[],"design":null}]}'
    typed_authority = (
        b'{"request":"x","values":[{"observation":"A","dependencies":[],'
        b'"authority":{"locator":"docs/a.md"}}]}'
    )

    for raw in (forward, duplicate, old_design, typed_authority):
        parsed = read_handover(raw)
        assert isinstance(parsed, Blocked), raw
        assert parsed.what == "HandoverMalformed", raw


def test_reader_refuses_noncanonical_bytes_that_parse_to_a_valid_graph() -> None:
    canonical = (
        b'{"request":"x","values":'
        b'[{"observation":"A","dependencies":[],"authority":null}]}'
    )
    pretty = b'{"request": "x", "values": [{"observation": "A", "dependencies": [], "authority": null}]}'
    reordered = (
        b'{"values":[{"observation":"A","dependencies":[],"authority":null}],'
        b'"request":"x"}'
    )

    assert isinstance(read_handover(canonical), StoredHandover)
    for raw in (pretty, reordered):
        parsed = read_handover(raw)
        assert isinstance(parsed, Blocked)
        assert parsed.what == "HandoverMalformed"


def test_reader_validates_raw_obligation_members_without_breaking_legacy_shape() -> (
    None
):
    facts = DesignFacts(
        (DesignTarget("src/value.py", "EXTEND"),),
        "object_oriented",
        ("reuse the existing boundary",),
        "tests/test_value.py",
        (),
        (("python", "-m", "pytest"),),
        0,
        ("constraint",),
        architectural_tests=NotApplicable(
            "The fixture has no structural boundary change."
        ),
        contract_tests=NotApplicable("The fixture changes no shared contract."),
        prefactoring=NotApplicable("The fixture requires no preservation move."),
        agreement_analysis=NotApplicable("The fixture has no affected agreement."),
        reuse_analysis=ReuseAnalysis(()),
        impact_closure=NotApplicable(
            "The fixture reaches no public surface, consumer or build metadata."
        ),
    )
    canonical = json.loads(
        _canonical_bytes("deliver", (HandoverValue("A", (), facts),))
    )

    for malformed in (1, [1], [""], [" "], ["constraint", "constraint"]):
        payload = json.loads(json.dumps(canonical))
        payload["values"][0]["authority"]["obligations"] = malformed
        raw = json.dumps(payload, separators=(",", ":")).encode()
        parsed = read_handover(raw)
        assert isinstance(parsed, Blocked), malformed
        assert parsed.what == "HandoverMalformed", malformed

    legacy = json.loads(json.dumps(canonical))
    del legacy["values"][0]["authority"]["obligations"]
    parsed_legacy = read_handover(json.dumps(legacy, separators=(",", ":")).encode())
    assert isinstance(parsed_legacy, StoredHandover)
    assert isinstance(parsed_legacy.values[0].authority, DesignFacts)
    assert parsed_legacy.values[0].authority.obligations == ()


def test_reader_validates_raw_public_oracle_members_without_breaking_legacy_shape() -> (
    None
):
    from des.ports.driven_ports.task_invocation_port import PublicOracle

    facts = DesignFacts(
        (DesignTarget("src/value.py", "EXTEND"),),
        "object_oriented",
        ("reuse the existing boundary",),
        "tests/test_value.py",
        (),
        (("python", "-m", "pytest"),),
        0,
        ("constraint",),
        public_oracle=PublicOracle(
            observation="observed",
            stimulus="stimulus text",
            expected="expected outcome",
            falsifier="falsifier text",
        ),
        architectural_tests=NotApplicable(
            "The fixture has no structural boundary change."
        ),
        contract_tests=NotApplicable("The fixture changes no shared contract."),
        prefactoring=NotApplicable("The fixture requires no preservation move."),
        agreement_analysis=NotApplicable("The fixture has no affected agreement."),
        reuse_analysis=ReuseAnalysis(()),
        impact_closure=NotApplicable(
            "The fixture reaches no public surface, consumer or build metadata."
        ),
    )
    canonical = json.loads(
        _canonical_bytes("deliver", (HandoverValue("A", (), facts),))
    )

    # Malformed public_oracle values should be rejected
    for malformed in (
        1,  # not an object
        [],  # not an object
        {"observation": "obs"},  # missing keys
        {
            "observation": "obs",
            "stimulus": "",
            "expected": "exp",
            "falsifier": "fals",
        },  # empty string
        {
            "observation": "obs",
            "stimulus": " ",
            "expected": "exp",
            "falsifier": "fals",
        },  # whitespace only
        {
            "observation": "obs",
            "stimulus": "stim",
            "expected": "exp",
            "falsifier": "fals",
            "extra": "key",
        },  # extra key
    ):
        payload = json.loads(json.dumps(canonical))
        payload["values"][0]["authority"]["public_oracle"] = malformed
        raw = json.dumps(payload, separators=(",", ":")).encode()
        parsed = read_handover(raw)
        assert isinstance(parsed, Blocked), malformed
        assert parsed.what == "HandoverMalformed", malformed

    # Legacy absence (no public_oracle field) should be accepted
    legacy = json.loads(json.dumps(canonical))
    del legacy["values"][0]["authority"]["public_oracle"]
    parsed_legacy = read_handover(json.dumps(legacy, separators=(",", ":")).encode())
    assert isinstance(parsed_legacy, StoredHandover)
    assert isinstance(parsed_legacy.values[0].authority, DesignFacts)
    assert parsed_legacy.values[0].authority.public_oracle is None

    # Re-encode should be byte-identical when public_oracle was absent
    reparsed = read_handover(
        json.dumps(
            json.loads(parsed_legacy.raw.decode()), separators=(",", ":")
        ).encode()
    )
    assert isinstance(reparsed, StoredHandover)
    # Both should have identical bytes when no public_oracle is present
    legacy_bytes = json.dumps(legacy, separators=(",", ":")).encode()
    reparsed_bytes = reparsed.raw
    assert json.loads(legacy_bytes.decode()) == json.loads(reparsed_bytes.decode()), (
        "re-encode must preserve legacy shape for handovers without public_oracle"
    )


def test_create_rejects_unusable_graph_facts_before_write(tmp_path) -> None:
    invalid = (
        (HandoverValue("A", (), None), HandoverValue("A", (), None)),
        (HandoverValue("A", ("missing",), None),),
        (HandoverValue("A", ("B",), None), HandoverValue("B", ("A",), None)),
        (HandoverValue("A", None, None),),  # type: ignore[arg-type]
        (HandoverValue("A", 1, None),),  # type: ignore[arg-type]
    )

    for values in invalid:
        result = create_handover(tmp_path, "deliver", values)
        assert isinstance(result, Blocked), values
        assert result.what == "HandoverMalformed", values
        assert not handover_path(tmp_path).exists(), values


def test_typed_design_facts_reject_every_non_repository_locator() -> None:
    def facts(*, target="src/value.py", oracle="tests/test_value.py", support=()):
        return DesignFacts(
            (DesignTarget(target, "EXTEND"),),
            "object_oriented",
            ("reuse the existing boundary",),
            oracle,
            support,
            (("python", "-m", "pytest"),),
            0,
            architectural_tests=NotApplicable(
                "The fixture has no structural boundary change."
            ),
            contract_tests=NotApplicable("The fixture changes no shared contract."),
            prefactoring=NotApplicable("The fixture requires no preservation move."),
            agreement_analysis=NotApplicable("The fixture has no affected agreement."),
            reuse_analysis=ReuseAnalysis(()),
            impact_closure=NotApplicable(
                "The fixture reaches no public surface, consumer or build metadata."
            ),
        )

    assert valid_design_facts(facts())
    assert not valid_design_facts(facts(target="../outside.py"))
    assert not valid_design_facts(facts(oracle="/tmp/oracle.py"))
    assert not valid_design_facts(facts(support=("../support.py",)))


def test_handover_persists_and_restores_the_explicit_oracle_command_binding(
    tmp_path,
) -> None:
    broad = ("python", "manage.py", "test", "hc.api.tests")
    selected = (
        "python",
        "manage.py",
        "test",
        "hc.api.tests.test_maintenance_windows",
    )
    facts = _facts(verification=(broad, selected), oracle_verification_index=1)

    stored = create_handover(tmp_path, "deliver", (HandoverValue("A", (), facts),))
    restored = load_handover(tmp_path, "deliver")

    assert isinstance(stored, StoredHandover)
    assert isinstance(restored, StoredHandover)
    authority = restored.values[0].authority
    assert isinstance(authority, DesignFacts)
    assert authority.oracle_verification_index == 1
    assert authority.verification[authority.oracle_verification_index] == selected
    assert broad != authority.verification[authority.oracle_verification_index]


@pytest.mark.parametrize("index", [-1, 1, True, "0"])
def test_handover_refuses_a_missing_or_invalid_oracle_command_binding(index) -> None:
    facts = _facts(oracle_verification_index=index)

    parsed = read_handover(
        _canonical_bytes("deliver", (HandoverValue("A", (), facts),))
    )

    assert isinstance(parsed, Blocked)
    assert parsed.what == "HandoverMalformed"
    assert "oracle_verification_index" in parsed.why


def test_restored_legacy_handover_names_the_missing_oracle_binding(tmp_path) -> None:
    facts = _facts()
    canonical = json.loads(
        _canonical_bytes("deliver", (HandoverValue("A", (), facts),))
    )
    del canonical["values"][0]["authority"]["oracle_verification_index"]

    parsed = read_handover(json.dumps(canonical, separators=(",", ":")).encode())

    assert isinstance(parsed, Blocked)
    assert parsed.what == "HandoverMalformed"
    assert (
        parsed.why == "design facts omit the required oracle_verification_index binding"
    )


def test_create_normalizes_an_out_of_order_semantic_graph(tmp_path) -> None:
    stored = create_handover(
        tmp_path,
        "deliver",
        (
            HandoverValue("B", ("A", "A"), None),
            HandoverValue("A", (), None),
            HandoverValue("C", (), None),
        ),
    )

    assert isinstance(stored, StoredHandover)
    assert [value.observation for value in stored.values] == ["A", "B", "C"]
    assert stored.values[1].dependencies == ("A",)
    assert handover_path(tmp_path).read_bytes() == stored.raw


def test_create_uses_po_position_to_break_ready_ties(tmp_path) -> None:
    stored = create_handover(
        tmp_path,
        "deliver",
        (
            HandoverValue("C", (), None),
            HandoverValue("B", (), None),
            HandoverValue("A", (), None),
        ),
    )

    assert isinstance(stored, StoredHandover)
    assert [value.observation for value in stored.values] == ["C", "B", "A"]


def test_concurrent_different_requests_never_overwrite_winner(tmp_path) -> None:
    values = (HandoverValue("A", (), None),)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = tuple(
            pool.map(
                lambda request: create_handover(tmp_path, request, values),
                ("one", "two"),
            )
        )

    stored = [item for item in (first, second) if isinstance(item, StoredHandover)]
    blocked = [item for item in (first, second) if isinstance(item, Blocked)]
    assert len(stored) == len(blocked) == 1
    assert handover_path(tmp_path).read_bytes() == stored[0].raw


def test_second_runner_observes_busy_shared_delivery_lock(tmp_path) -> None:
    first = acquire_delivery_lock(tmp_path)
    second = acquire_delivery_lock(tmp_path)
    try:
        assert not isinstance(first, Blocked)
        assert isinstance(second, Blocked)
        assert second.what == "DeliveryBusy"
        assert second.retry
    finally:
        if not isinstance(first, Blocked):
            first.release()


def test_rewrite_expected_mismatch_preserves_winner(tmp_path) -> None:
    original = create_handover(tmp_path, "deliver", (HandoverValue("A", (), None),))
    assert isinstance(original, StoredHandover)
    result = rewrite_handover(
        tmp_path, b"other", "deliver", (HandoverValue("B", (), None),)
    )

    assert isinstance(result, Blocked)
    assert result.what == "HandoverDrift"
    assert handover_path(tmp_path).read_bytes() == original.raw


def test_rewrite_preserves_started_prefix_and_normalizes_suffix(tmp_path) -> None:
    original = create_handover(
        tmp_path,
        "deliver",
        (HandoverValue("A", (), "brief#A"),),
    )
    assert isinstance(original, StoredHandover)

    rewritten = rewrite_handover(
        tmp_path,
        original.raw,
        "deliver",
        (
            HandoverValue("A", (), "brief#A"),
            HandoverValue("C", ("A",), None),
            HandoverValue("B", ("A",), None),
        ),
    )

    assert isinstance(rewritten, StoredHandover)
    assert rewritten.values == (
        HandoverValue("A", (), "brief#A"),
        HandoverValue("C", ("A",), None),
        HandoverValue("B", ("A",), None),
    )


def test_cleanup_fsync_failure_restores_owned_bytes(tmp_path, monkeypatch) -> None:
    stored = create_handover(tmp_path, "deliver", (HandoverValue("A", (), None),))
    assert isinstance(stored, StoredHandover)
    monkeypatch.setattr(
        "des.application.handover._fsync_directory",
        lambda _path: Blocked("HandoverUnavailable", "fsync failed", "repair"),
    )

    result = finalize_handover(tmp_path, stored.raw)

    assert isinstance(result, Blocked)
    assert result.what == "HandoverCleanupUnproven"
    assert handover_path(tmp_path).read_bytes() == stored.raw


def _facts(**overrides) -> DesignFacts:
    fields = {
        "targets": (DesignTarget("src/value.py", "EXTEND"),),
        "paradigm": "object_oriented",
        "decisions": ("reuse the existing boundary",),
        "oracle": "tests/test_value.py",
        "acceptance_supports": (),
        "verification": (("python", "-m", "pytest"),),
        "oracle_verification_index": 0,
    }
    fields.update(overrides)
    return DesignFacts(
        *fields.values(),
        architectural_tests=NotApplicable(
            "The fixture has no structural boundary change."
        ),
        contract_tests=NotApplicable("The fixture changes no shared contract."),
        prefactoring=NotApplicable("The fixture requires no preservation move."),
        agreement_analysis=NotApplicable("The fixture has no affected agreement."),
        reuse_analysis=ReuseAnalysis(()),
        impact_closure=NotApplicable(
            "The fixture reaches no public surface, consumer or build metadata."
        ),
    )


def test_the_guard_still_owns_every_clause_json_schema_cannot_express() -> None:
    """What stays here, and why it cannot move into the provider's schema.

    A duplicate target PATH is invisible to `uniqueItems`, which compares whole
    items and would admit two targets differing only by `decision`.  An oracle
    repeated as its own acceptance support is a relation BETWEEN two fields,
    which JSON Schema has no vocabulary for.  Both are checked on facts the
    provider validator never sees, too: `read_handover` reconstructs them from
    bytes on disk.
    """
    duplicate_paths = _facts(
        targets=(
            DesignTarget("src/value.py", "EXTEND"),
            DesignTarget("src/value.py", "CREATE_NEW"),
        )
    )
    oracle_as_its_own_support = _facts(
        acceptance_supports=("tests/test_value.py",),
    )

    assert not valid_design_facts(duplicate_paths)
    assert not valid_design_facts(oracle_as_its_own_support)
    assert design_facts_defect(duplicate_paths) == (
        'targets[1].path repeats an earlier target: "src/value.py"'
    )
    assert design_facts_defect(oracle_as_its_own_support) == (
        "acceptance_supports[0] repeats the oracle, which is never its own "
        'support: "tests/test_value.py"'
    )


@pytest.mark.parametrize("decision", ["CREATE_NEW", "EXTEND"])
def test_a_non_oracle_target_cannot_also_be_required_acceptance_support(
    decision: str,
) -> None:
    """Craft changes its targets; the oracle witness pins its supports."""
    conflict = _facts(
        targets=(DesignTarget("src/value.py", decision),),
        acceptance_supports=("tests/support/helper.py", "src/value.py"),
    )

    defect = design_facts_defect(conflict)
    assert defect is not None
    assert "src/value.py" in defect and "helper.py" not in defect


def test_a_persisted_extend_support_binding_stays_readable_for_correction() -> None:
    """Bindings stored before the EXTEND half was refused remain correctable."""
    extended = _facts(
        targets=(DesignTarget("src/value.py", "EXTEND"),),
        acceptance_supports=("src/value.py",),
    )
    created = _facts(
        targets=(DesignTarget("src/value.py", "CREATE_NEW"),),
        acceptance_supports=("src/value.py",),
    )

    assert design_facts_defect(extended, historical=True) is None
    assert design_facts_defect(created, historical=True) is not None


def test_a_support_only_helper_beside_an_extended_target_is_valid() -> None:
    support_only = _facts(acceptance_supports=("tests/support/new_helper.py",))
    extended = _facts(
        targets=(DesignTarget("src/value.py", "EXTEND"),),
        acceptance_supports=("tests/support/new_helper.py",),
    )

    assert design_facts_defect(support_only) is None
    assert design_facts_defect(extended) is None


def test_a_rejection_names_the_field_and_the_value_it_refused() -> None:
    """ "Incomplete facts" was false: the recorded facts were COMPLETE and of
    the wrong type.  A rejection that misnames its cause aims the next turn at
    the wrong repair."""
    prose = "USER OBSERVATION: an operator running the CLI gets exit 0."

    defect = design_facts_defect(_facts(acceptance_supports=(prose,)))

    assert defect is not None
    assert defect.startswith("acceptance_supports[0] is not a repository-relative")
    assert prose in defect


def test_every_rejected_value_is_bounded_and_carries_no_raw_newline() -> None:
    """A defect string is interpolated into an operator-facing failure, so an
    unbounded or newline-bearing value would break the message it explains."""
    defect = design_facts_defect(_facts(oracle="../escape\nsecond line" * 40))

    assert defect is not None
    assert "\n" not in defect
    assert "\\n" in defect
    assert len(defect) < 200


def test_the_guard_admits_well_formed_facts_unchanged() -> None:
    assert design_facts_defect(_facts()) is None
    assert valid_design_facts(_facts())
    assert valid_design_facts(_facts(acceptance_supports=("src/support.py",)))


def test_restoring_inadmissible_design_facts_names_the_rejected_field() -> None:
    """Persisted external bytes must identify the invalid field and value."""
    prose = "USER OBSERVATION: an operator running the CLI gets exit 0."
    values = (
        HandoverValue(
            "A",
            (),
            DesignFacts(
                (DesignTarget("src/value.py", "EXTEND"),),
                "object_oriented",
                ("reuse the existing boundary",),
                "tests/test_value.py",
                (prose,),
                (("python", "-m", "pytest"),),
                0,
                architectural_tests=NotApplicable(
                    "The fixture has no structural boundary change."
                ),
                contract_tests=NotApplicable("The fixture changes no shared contract."),
                prefactoring=NotApplicable(
                    "The fixture requires no preservation move."
                ),
                agreement_analysis=NotApplicable(
                    "The fixture has no affected agreement."
                ),
                reuse_analysis=ReuseAnalysis(()),
                impact_closure=NotApplicable(
                    "The fixture reaches no public surface, consumer or build metadata."
                ),
            ),
        ),
    )

    parsed = read_handover(_canonical_bytes("deliver", values))

    assert isinstance(parsed, Blocked)
    assert parsed.what == "HandoverMalformed"
    assert parsed.why == (
        "restored design facts are inadmissible: acceptance_supports[0] is "
        f'not a repository-relative file locator: "{prose}"'
    )


@pytest.mark.parametrize(
    "oracle",
    [
        "tests/test_value.py",
        "tests/test_value.py::TestClass::test_case",
        "vendor/example.com/mod/@v/v1.2.0.info",
        "../outside.py",
        "/tmp/oracle.py",
        "tests/test_value.py::x/../y",
        "tests/test_value.py::selector\nsecond",
        "tests/test_value.py::selector\rsecond",
        "USER OBSERVATION: prose",
    ],
)
def test_the_guard_and_the_provider_schema_decide_an_oracle_identically(
    oracle: str,
) -> None:
    """One grammar, one definition, asserted rather than asserted-about.

    The guard used to validate only the part before `::`, so it accepted three
    shapes the schema pattern refuses: a `..` segment hiding in the selector,
    and a selector carrying LF or CR.  Those are exactly the shapes
    `is_canonical_oracle_locator` already calls unsafe, so the guard was
    aligned to the pattern.  This test fails the moment either side drifts.
    """
    facts = _facts(oracle=oracle)
    schema_admits = re.fullmatch(DESIGN_ORACLE_LOCATOR_PATTERN, oracle) is not None
    guard_admits = design_facts_defect(facts) is None

    assert guard_admits == schema_admits


def _rich_facts() -> DesignFacts:
    return replace(
        _facts(),
        reuse_analysis=ReuseAnalysis(
            (
                ReuseCandidate(
                    "Value.render",
                    "src/value.py:10",
                    "CREATE_NEW",
                    "No existing renderer fits the contract.",
                ),
            )
        ),
        impact_closure=ApplicableImpactClosure(
            (
                ImpactItem(
                    "runtime",
                    "src/value.py",
                    "CHANGED",
                    "The target is rewritten.",
                ),
            )
        ),
        adr=ApplicableADR(
            "context", "decision", ("alternative",), ("consequence",), "accepted"
        ),
    )


def test_reuse_closure_and_adr_survive_the_handover_round_trip() -> None:
    facts = _rich_facts()

    parsed = read_handover(
        _canonical_bytes("deliver", (HandoverValue("A", (), facts),))
    )

    assert isinstance(parsed, StoredHandover)
    assert parsed.values[0].authority == facts


def test_each_of_reuse_adr_and_closure_changes_the_design_basis() -> None:
    base = _rich_facts()
    changed = {
        "reuse_analysis": ReuseAnalysis(()),
        "adr": NotApplicable("The fixture needs no decision record."),
        "impact_closure": ApplicableImpactClosure(
            (
                ImpactItem(
                    "runtime", "src/value.py", "MIGRATED", "The target is migrated."
                ),
            )
        ),
    }
    reference = design_basis_sha256(None, HandoverValue("A", (), base))

    for name, value in changed.items():
        basis = design_basis_sha256(
            None, HandoverValue("A", (), replace(base, **{name: value}))
        )
        assert basis != reference, name


def test_a_persisted_authority_without_reuse_and_closure_is_legacy() -> None:
    canonical = json.loads(
        _canonical_bytes("deliver", (HandoverValue("A", (), _facts()),))
    )
    del canonical["values"][0]["authority"]["reuse_analysis"]
    del canonical["values"][0]["authority"]["impact_closure"]

    parsed = read_handover(json.dumps(canonical, separators=(",", ":")).encode())

    assert isinstance(parsed, StoredHandover)
    authority = parsed.values[0].authority
    assert isinstance(authority, LegacyDesignFacts)
    assert {"reuse_analysis", "impact_closure"} <= set(authority.missing_decisions)


def test_native_receipts_preserve_the_graph_and_survive_other_graph_writers(
    tmp_path, monkeypatch
):
    from des.application.architect_handoff import HandoverReceiptStore, g10_run

    values = (
        HandoverValue("A", (), _rich_facts()),
        HandoverValue("B", ("A",), "docs/brief.md#B"),
    )
    stored = create_handover(tmp_path, "deliver", values)
    assert isinstance(stored, StoredHandover)
    monkeypatch.setattr(g10_run, "fcntl", None)
    store = HandoverReceiptStore(tmp_path, stored)
    receipt = g10_run.record_authored(
        str(tmp_path / ".nwave/des"),
        "NATIVE",
        "script",
        "declared-v1",
        "implementation",
        "fixed",
        ["command"],
        0,
        "ok",
        receipt_store=store,
    )
    loaded = load_handover(tmp_path, "deliver")
    assert isinstance(loaded, StoredHandover)
    assert loaded.values == stored.values
    assert loaded.product_authority == stored.product_authority
    assert loaded.shared_design == stored.shared_design
    assert loaded.architect_receipts == (receipt,)
    assert not (tmp_path / ".nwave/des/g10.receipts.json").exists()

    rewritten = rewrite_handover(tmp_path, loaded.raw, loaded.request, loaded.values)
    assert isinstance(rewritten, StoredHandover)
    assert rewritten.architect_receipts == (receipt,)
    assert load_handover(tmp_path, "deliver").architect_receipts == (receipt,)

    before = rewritten.raw
    with pytest.raises(g10_run.RunError, match="already recorded"):
        g10_run.record_authored(
            str(tmp_path / ".nwave/des"),
            "NATIVE",
            "script",
            "declared-v2",
            "implementation",
            "fixed",
            ["command"],
            0,
            "ok",
            receipt_store=store,
        )
    assert handover_path(tmp_path).read_bytes() == before
    replaced = g10_run.record_authored(
        str(tmp_path / ".nwave/des"),
        "NATIVE",
        "script",
        "declared-v2",
        "implementation",
        "fixed",
        ["command"],
        0,
        "ok",
        receipt_store=store,
        replace=True,
    )
    assert load_handover(tmp_path, "deliver").architect_receipts == (replaced,)


def test_snapshot_bound_receipt_writer_refuses_stale_graph_without_losing_facts(
    tmp_path,
):
    from des.application.architect_handoff import HandoverReceiptStore, g10_run

    original = create_handover(tmp_path, "deliver", (HandoverValue("A", (), _facts()),))
    assert isinstance(original, StoredHandover)
    stale_store = HandoverReceiptStore(tmp_path, original)
    updated = rewrite_handover(
        tmp_path,
        original.raw,
        original.request,
        (replace(original.values[0], authority=_rich_facts()),),
    )
    assert isinstance(updated, StoredHandover)
    with pytest.raises(g10_run.RunError) as refusal:
        g10_run.record_authored(
            str(tmp_path / ".nwave/des"),
            "STALE",
            "script",
            "v1",
            "implementation",
            "fixed",
            ["command"],
            0,
            "ok",
            receipt_store=stale_store,
        )
    assert refusal.value.defect.rule == "RUN5"
    assert refusal.value.defect.what == "HandoverDrift"
    assert refusal.value.defect.where == ".nwave/des/handover.json"
    assert refusal.value.defect.why and refusal.value.defect.how
    assert handover_path(tmp_path).read_bytes() == updated.raw
    assert load_handover(tmp_path, "deliver").values == updated.values


def test_native_prompt_keeps_literal_root_context_and_refuses_bad_value_positions(
    tmp_path, capsys
):
    from des.cli.handoff import main

    stored = create_handover(tmp_path, "deliver", (HandoverValue("A", (), _facts()),))
    assert isinstance(stored, StoredHandover)
    context = "\n  {{literal_root_text}}\nDO NOT DROP THIS CONTEXT.\n\n"
    path = tmp_path / "root.txt"
    path.write_bytes(context.encode("utf-8"))
    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "prompt",
                "--role",
                "nw-solution-architect",
                "--root-context",
                str(path),
            ]
        )
        == 0
    )
    printed = capsys.readouterr().out
    assert context in printed
    assert "UNASSESSED" in printed
    assert "reuse the existing boundary" in printed
    for position in ("0", "-1", "2"):
        assert (
            main(
                [
                    "prompt",
                    "--repo-root",
                    str(tmp_path),
                    "--role",
                    "nw-solution-architect",
                    "--root-context",
                    str(path),
                    "--value",
                    position,
                ]
            )
            == 1
        )
        assert "one-based position" in capsys.readouterr().err


def test_native_receipt_execution_uses_the_canonical_store_without_posix_file_lock(
    tmp_path, monkeypatch
):
    import sys

    from des.application.architect_handoff import HandoverReceiptStore, g10_run

    stored = create_handover(tmp_path, "deliver", (HandoverValue("A", (), _facts()),))
    assert isinstance(stored, StoredHandover)
    monkeypatch.setattr(g10_run, "fcntl", None)
    rejected = tmp_path / "standalone"
    marker = tmp_path / "must-not-run"
    with pytest.raises(g10_run.RunError) as refusal:
        g10_run.execute(
            str(rejected),
            "REFUSED",
            "script",
            "implementation",
            "fixed",
            [sys.executable, "-c", f"open({str(marker)!r}, 'w').write('ran')"],
            version_argv=[sys.executable, "--version"],
        )
    assert refusal.value.defect.rule == "RUN5"
    assert (
        refusal.value.defect.what
        and refusal.value.defect.why
        and refusal.value.defect.how
    )
    assert not rejected.exists()
    assert not marker.exists()
    run = g10_run.execute(
        str(tmp_path / ".nwave/des"),
        "OBSERVED",
        "script",
        "implementation",
        "fixed",
        [sys.executable, "-c", "print('native observed output')"],
        version_argv=[sys.executable, "--version"],
        receipt_store=HandoverReceiptStore(tmp_path, stored),
    )
    loaded = load_handover(tmp_path, "deliver")
    assert isinstance(loaded, StoredHandover)
    assert loaded.values == stored.values
    assert loaded.architect_receipts == (run,)
    assert run.exit_status == 0 and run.result_class == "ok"
    assert run.artifacts
    assert (
        (tmp_path / ".nwave/des" / run.artifacts[0].path)
        .read_bytes()
        .startswith(b"native observed output\n")
    )
    assert not (tmp_path / ".nwave/des/g10.receipts.json").exists()


def test_literal_receipt_argv_keeps_empty_data_arguments_and_refuses_invalid_executables(
    tmp_path,
):
    import sys

    from des.application.architect_handoff import (
        HandoverReceiptStore,
        g10_codec,
        g10_run,
    )
    from des.application.architect_handoff import g10_types as types

    stored = create_handover(tmp_path, "deliver", (HandoverValue("A", (), _facts()),))
    assert isinstance(stored, StoredHandover)
    argv = [sys.executable, "-c", "import sys; print(repr(sys.argv[1:]))", "", " \t"]
    run = g10_run.execute(
        str(tmp_path / ".nwave/des"),
        "EMPTY",
        "script",
        "implementation",
        "fixed",
        argv,
        version_argv=[sys.executable, "--version"],
        receipt_store=HandoverReceiptStore(tmp_path, stored),
    )
    assert list(run.argv) == argv
    output = (tmp_path / ".nwave/des" / run.artifacts[0].path).read_bytes()
    assert output.startswith(b"['', ' \\t']\n")
    for bad in (
        [],
        [""],
        [" "],
        ["command", 1],
        ["command", "\ud800"],
        ["command", "\x00"],
    ):
        defects = []
        decoded = g10_codec.dec(
            types.Run, {**g10_codec.enc(run), "argv": bad}, "$.run", defects
        )
        assert decoded is g10_codec.BAD and defects, bad


def test_native_receipt_collection_is_canonical_after_out_of_order_append_and_replace(
    tmp_path,
):
    from des.application.architect_handoff import HandoverReceiptStore, g10_run

    stored = create_handover(
        tmp_path, "deliver", (HandoverValue("A", (), _rich_facts()),)
    )
    assert isinstance(stored, StoredHandover)
    store = HandoverReceiptStore(tmp_path, stored)
    for run_id, version, replacing in (
        ("Z", "v1", False),
        ("A", "v1", False),
        ("A", "v2", True),
    ):
        g10_run.record_authored(
            str(tmp_path / ".nwave/des"),
            run_id,
            "script",
            version,
            "implementation",
            "fixed",
            ["command"],
            0,
            "ok",
            receipt_store=store,
            replace=replacing,
        )
        loaded = load_handover(tmp_path, "deliver")
        assert isinstance(loaded, StoredHandover)
        assert loaded.values == stored.values
        assert [run.id for run in loaded.architect_receipts] == sorted({run_id, "Z"})
    assert loaded.architect_receipts[0].tool_version == "v2"


def test_design_import_refusal_names_the_handoff_instead_of_valid_stdin(
    tmp_path, monkeypatch, capsys
):
    import io
    import sys

    from des.cli.design import main
    from tests.des.unit.domain.test_design_document import manifest

    for intent in (["--value", "1"], ["--shared"]):
        monkeypatch.setattr(
            sys, "stdin", io.TextIOWrapper(io.BytesIO(json.dumps(manifest()).encode()))
        )
        assert (
            main(
                [
                    "--repo-root",
                    str(tmp_path),
                    *intent,
                    "--input",
                    "-",
                    "--architect-handoff",
                    "nonexistent.json",
                ]
            )
            == 1
        )
        output = capsys.readouterr().out
        assert "nonexistent.json" in output
        assert "cannot read the file" in output
        assert "one closed typed handoff input" in output
        assert "stdin must carry" not in output


def test_native_architect_prompt_returns_semantic_input_for_host_owned_submission(
    tmp_path, capsys
):
    from des.cli.handoff import main

    assert isinstance(
        create_handover(tmp_path, "deliver", (HandoverValue("A", (), _facts()),)),
        StoredHandover,
    )
    context = tmp_path / "root.txt"
    context.write_text("host context\n")
    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "prompt",
                "--role",
                "nw-solution-architect",
                "--root-context",
                str(context),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    submit = output.split("## SUBMIT", 1)[1].split("## FROM THE ROOT", 1)[0]
    assert "The host submits" in submit
    assert "Return only the closed complete semantic manifest" in submit
    assert "Do not execute" in submit
    assert "Submit each manifest yourself" not in submit
    assert "Hand a manifest to no one else" not in submit


def test_product_owner_prompt_is_reachable_before_design_and_uses_its_own_permissions(
    tmp_path, capsys
):
    from des.application.architect_handoff import projection
    from des.cli.handoff import main

    assert isinstance(
        create_handover(
            tmp_path,
            "product intent",
            (HandoverValue("product observation", (), None),),
        ),
        StoredHandover,
    )
    context = tmp_path / "root.txt"
    context.write_text("actual human context\n")
    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "prompt",
                "--role",
                "nw-product-owner",
                "--root-context",
                str(context),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "# Product Owner" in out
    assert "Read-only subagent" in out
    assert "actual human context\n" in out
    assert "product intent" in out and "product observation" in out
    assert {row["kind"] for row in projection("nw-product-owner", {})} == {
        "scenarios",
        "closure",
    }


def test_refused_native_writer_cannot_overwrite_committed_output_even_on_replace(
    tmp_path,
):
    import hashlib
    import sys
    import time

    from des.application.architect_handoff import HandoverReceiptStore, g10_run

    stored = create_handover(tmp_path, "deliver", (HandoverValue("A", (), _facts()),))
    assert isinstance(stored, StoredHandover)
    directory = tmp_path / ".nwave/des"
    for replacing in (False, True):
        snapshot = load_handover(tmp_path, "deliver")
        assert isinstance(snapshot, StoredHandover)
        ready = [tmp_path / f"ready-{replacing}-{i}" for i in range(2)]
        release = [tmp_path / f"release-{replacing}-{i}" for i in range(2)]

        def execute(
            index,
            *,
            ready=ready,
            release=release,
            snapshot=snapshot,
            replacing=replacing,
        ):
            body = (
                "from pathlib import Path; import time\n"
                f"Path({str(ready[index])!r}).touch()\n"
                "deadline = time.monotonic() + 10\n"
                f"while not Path({str(release[index])!r}).exists():\n"
                "    if time.monotonic() > deadline: raise SystemExit(9)\n"
                "    time.sleep(0.01)\n"
                f"print({f'writer-{replacing}-{index}'!r})\n"
            )
            return g10_run.execute(
                str(directory),
                "SAME",
                "script",
                "implementation",
                "fixed",
                [sys.executable, "-c", body],
                version_argv=[sys.executable, "--version"],
                receipt_store=HandoverReceiptStore(tmp_path, snapshot),
                replace=replacing,
                timeout_s=15,
            )

        with ThreadPoolExecutor(max_workers=2) as workers:
            first, second = workers.submit(execute, 0), workers.submit(execute, 1)
            try:
                deadline = time.monotonic() + 8
                while not all(path.exists() for path in ready):
                    assert time.monotonic() < deadline, (
                        "both executions must reach the shared starting snapshot"
                    )
                    time.sleep(0.01)
                release[0].touch()
                committed = first.result(timeout=15)
                release[1].touch()
                with pytest.raises(g10_run.RunError, match="HandoverDrift"):
                    second.result(timeout=15)
            finally:
                for path in release:
                    path.touch()
        loaded = load_handover(tmp_path, "deliver")
        assert isinstance(loaded, StoredHandover)
        assert loaded.architect_receipts == (committed,)
        artifact = directory / committed.artifacts[0].path
        assert (
            hashlib.sha256(artifact.read_bytes()).hexdigest()
            == committed.artifacts[0].sha256
        )


def test_receipt_publication_preserves_visible_evidence_when_post_rename_sync_fails(
    tmp_path, monkeypatch
):
    import hashlib
    import sys

    from des.application import handover
    from des.application.architect_handoff import HandoverReceiptStore, g10_run

    for replacing in (False, True):
        for phase in ("after", "before"):
            root = tmp_path / f"{replacing}-{phase}"
            root.mkdir()
            stored = create_handover(
                root, "deliver", (HandoverValue("A", (), _facts()),)
            )
            assert isinstance(stored, StoredHandover)
            directory = root / ".nwave/des"
            store = HandoverReceiptStore(root, stored)
            if replacing:
                g10_run.execute(
                    str(directory),
                    "SYNC",
                    "script",
                    "implementation",
                    "fixed",
                    [sys.executable, "-c", "print('old')"],
                    version_argv=[sys.executable, "--version"],
                    receipt_store=store,
                )
            before = handover_path(root).read_bytes()
            previous = directory / "artifacts/SYNC.out"
            old_output = previous.read_bytes() if previous.exists() else None

            def refused_storage(*args, **kwargs):
                return Blocked(
                    "InjectedStorageFailure", "injected durability failure", "retry"
                )

            with monkeypatch.context() as injection:
                injection.setattr(
                    handover,
                    "_fsync_directory" if phase == "after" else "_write_temporary",
                    refused_storage,
                )
                with pytest.raises(g10_run.RunError) as refused:
                    g10_run.execute(
                        str(directory),
                        "SYNC",
                        "script",
                        "implementation",
                        "fixed",
                        [sys.executable, "-c", "print('new')"],
                        version_argv=[sys.executable, "--version"],
                        receipt_store=store,
                        replace=replacing,
                    )
            loaded = load_handover(root, "deliver")
            assert isinstance(loaded, StoredHandover)
            if phase == "after":
                (receipt,) = loaded.architect_receipts
                assert previous.exists(), (
                    "a visible receipt must retain its matching output"
                )
                assert previous.read_bytes().startswith(b"new\n")
                assert (
                    hashlib.sha256(previous.read_bytes()).hexdigest()
                    == receipt.artifacts[0].sha256
                )
                assert "durability is uncertain" in refused.value.defect.why
                assert "inspect" in refused.value.defect.how
            else:
                assert loaded.raw == before
                assert (
                    previous.read_bytes() if previous.exists() else None
                ) == old_output


def test_fifo_output_is_refused_without_blocking_or_retaining_delivery_lock(tmp_path):
    import os
    import subprocess
    import sys

    from des.runtime.spawn import spawn

    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO custody requires a platform with mkfifo")
    for phase in ("before", "publication"):
        root = tmp_path / phase
        root.mkdir()
        stored = create_handover(root, "deliver", (HandoverValue("A", (), _facts()),))
        assert isinstance(stored, StoredHandover)
        directory = root / ".nwave/des"
        artifacts = directory / "artifacts"
        artifacts.mkdir()
        output = artifacts / "FIFO.out"
        marker = root / "command-ran"
        if phase == "before":
            os.mkfifo(output)
        command = f"from pathlib import Path; Path({str(marker)!r}).touch()"
        if phase == "publication":
            command += f"; import os; os.mkfifo({str(output)!r})"
        program = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "from des.application.handover import stored_handover\n"
            "from des.application.architect_handoff import HandoverReceiptStore, g10_run\n"
            f"root = Path({str(root)!r})\n"
            "try:\n"
            f"    g10_run.execute({str(directory)!r}, 'FIFO', 'script', 'implementation', 'fixed', "
            f"[sys.executable, '-c', {command!r}], version_argv=[sys.executable, '--version'], "
            "receipt_store=HandoverReceiptStore(root, stored_handover(root)), timeout_s=1)\n"
            "except g10_run.RunError as error:\n"
            "    print(json.dumps([error.defect.what, error.defect.why, error.defect.how]))\n"
            "else:\n"
            "    raise SystemExit('special output accepted')\n"
        )
        try:
            completed = spawn(
                [sys.executable, "-c", program],
                timeout=3,
                capture_output=True,
                text=True,
                check=False,
                reap_process_group=(os.name == "posix"),
            )
        except subprocess.TimeoutExpired:
            pytest.fail(
                "FIFO destination blocked past the external bound; process group reaped"
            )
        assert completed.returncode == 0, completed.stderr
        what, why, how = json.loads(completed.stdout)
        assert "regular file" in what
        assert why and how
        assert marker.exists() is (phase == "publication")
        assert handover_path(root).read_bytes() == stored.raw
        lock = acquire_delivery_lock(root)
        assert not isinstance(lock, Blocked), lock
        lock.release()


def test_detached_handoff_check_reads_defects_without_creating_a_handover(
    tmp_path, capsys
):
    from des.cli.handoff import main

    source = tmp_path / "defective.g10.json"
    original = b'{"sections": []}\n'
    source.write_bytes(original)
    assert main(["check", "--repo-root", str(tmp_path), source.name]) == 1
    out, err = capsys.readouterr()
    assert "X1" in out and "no entry" in out
    assert err == ""
    assert source.read_bytes() == original
    assert set(tmp_path.rglob("*")) == {source}


def test_detached_handoff_summary_reads_file_without_creating_a_handover(
    tmp_path, capsys
):
    from des.application.architect_handoff import g10_types
    from des.cli.handoff import main

    source = tmp_path / "defective.g10.json"
    original = b'{"sections": []}\n'
    source.write_bytes(original)
    assert main(["summary", "--repo-root", str(tmp_path), source.name]) == 0
    out, err = capsys.readouterr()
    assert set(json.loads(out)["missing_shared"]) == set(g10_types.REQUIRED_SHARED)
    assert err == ""
    assert source.read_bytes() == original
    assert set(tmp_path.rglob("*")) == {source}


def test_detached_handoff_render_writes_only_the_requested_html_without_a_handover(
    tmp_path, capsys
):
    from des.cli.handoff import main

    source = tmp_path / "defective.g10.json"
    original = b'{"sections": []}\n'
    source.write_bytes(original)
    page = tmp_path / "inspection.html"
    assert (
        main(
            [
                "render",
                "--repo-root",
                str(tmp_path),
                source.name,
                "--html",
                page.name,
            ]
        )
        == 0
    )
    out, err = capsys.readouterr()
    assert f"wrote {page}" in out and err == ""
    assert page.read_text().startswith("<!doctype html>")
    assert source.read_bytes() == original
    assert set(tmp_path.rglob("*")) == {source, page}


def test_handoff_graph_operations_still_refuse_missing_handover_without_effects(
    tmp_path, capsys
):
    import sys

    from des.cli.handoff import main

    marker = tmp_path / "must-not-run"
    commands = (
        ["check"],
        ["summary"],
        ["render"],
        ["prompt", "--role", "nw-solution-architect", "--root-context", "unused.txt"],
        [
            "run",
            "--id",
            "REFUSED",
            "--tool",
            "script",
            "--target",
            "implementation",
            "--variant",
            "fixed",
            "--version-argv",
            f"{sys.executable} --version",
            "--",
            sys.executable,
            "-c",
            f"open({str(marker)!r}, 'w').write('ran')",
        ],
        [
            "record",
            "--id",
            "REFUSED",
            "--tool",
            "script",
            "--tool-version",
            "v1",
            "--target",
            "implementation",
            "--variant",
            "fixed",
            "--exit",
            "0",
            "--result",
            "ok",
            "--",
            "command",
        ],
    )
    for command in commands:
        assert main(["--repo-root", str(tmp_path), *command]) == 1
        out, err = capsys.readouterr()
        assert out == ""
        assert "no accumulated handover" in err
        assert "WHAT:" in err and "WHY:" in err and "HOW:" in err
        assert "des po" in err and "des design" in err
        assert not list(tmp_path.iterdir())


def test_detached_file_with_handover_keeps_file_payload_and_existing_target_defaults(
    tmp_path, capsys
):
    from des.application.architect_handoff import g10_types
    from des.cli.handoff import main

    stored = create_handover(tmp_path, "deliver", (HandoverValue("A", (), _facts()),))
    assert isinstance(stored, StoredHandover)
    source = tmp_path / "detached.g10.json"
    source.write_text(
        json.dumps(
            {
                "sections": [
                    {
                        "kind": kind,
                        "scope": "shared",
                        "status": {
                            "tag": "not_applicable",
                            "reason": "Detached inspection.",
                        },
                    }
                    for kind in g10_types.REQUIRED_SHARED
                ]
            }
        )
    )
    assert main(["check", "--repo-root", str(tmp_path), source.name]) == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert "X1" not in out
    assert "need --targets; none were given" not in out
    assert handover_path(tmp_path).read_bytes() == stored.raw
