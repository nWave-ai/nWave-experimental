"""Storage laws for the one restart graph."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

import pytest

from des.application.handover import (
    _HANDOVER_REPAIR,
    Blocked,
    HandoverValue,
    StoredHandover,
    _canonical_bytes,
    acquire_delivery_lock,
    create_handover,
    design_facts_defect,
    finalize_handover,
    handover_path,
    load_handover,
    read_handover,
    rewrite_handover,
    valid_design_facts,
)
from des.domain.architecture_brief_resolver import DESIGN_ORACLE_LOCATOR_PATTERN
from des.ports.driven_ports.task_invocation_port import DesignFacts, DesignTarget


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
        b'{"request":"deliver","values":['
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
        ("constraint",),
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
        )

    assert valid_design_facts(facts())
    assert not valid_design_facts(facts(target="../outside.py"))
    assert not valid_design_facts(facts(oracle="/tmp/oracle.py"))
    assert not valid_design_facts(facts(support=("../support.py",)))


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
    }
    fields.update(overrides)
    return DesignFacts(*fields.values())


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


def test_the_repair_a_rejection_names_is_the_path_the_software_uses(tmp_path) -> None:
    """The HOW must be executable, so the file it names must be the real one.

    `_DESIGN_FACTS_REPAIR` tells an operator to delete `.nwave/des/handover.json`
    to re-elicit DESIGN.  If that path ever diverged from what `handover_path`
    builds, the message would send them to delete nothing.
    """
    from des.application.delivery_continuation import _DESIGN_FACTS_REPAIR

    create_handover(tmp_path, "deliver", (HandoverValue("A", (), None),))
    named = _DESIGN_FACTS_REPAIR.split("delete ")[1].split(" ")[0]

    assert handover_path(tmp_path) == tmp_path / named
    assert handover_path(tmp_path).exists()

    handover_path(tmp_path).unlink()

    assert load_handover(tmp_path, "deliver") is None


def test_restoring_inadmissible_design_facts_names_the_field_and_the_repair() -> None:
    """The second consumer must not be the one place that still says nothing.

    `read_handover` is exactly why the guard was kept: it rebuilds design facts
    from bytes no provider validator ever saw.  Refusing them with "design
    facts are invalid" and "restore the handover" tells an operator neither
    which field is wrong nor what to run.
    """
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
    assert ".nwave/des/handover.json" in parsed.how


def test_the_handover_repair_names_the_file_the_software_writes(tmp_path) -> None:
    create_handover(tmp_path, "deliver", (HandoverValue("A", (), None),))
    named = _HANDOVER_REPAIR.split("delete ")[1].split(" ")[0]

    assert handover_path(tmp_path) == tmp_path / named
    assert handover_path(tmp_path).exists()


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
