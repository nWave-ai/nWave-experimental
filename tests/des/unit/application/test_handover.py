"""Storage laws for the one restart graph."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

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
from des.domain.design_document import DesignDocument
from des.ports.driven_ports.task_invocation_port import (
    ApplicableADR,
    ApplicableImpactClosure,
    DesignFacts,
    DesignTarget,
    FactId,
    FactRecord,
    FactRef,
    ImpactItem,
    NotApplicable,
    PreNormalizedDesign,
    ReuseAnalysis,
    ReuseCandidate,
)
from tests.des._helpers.host_facts import design_manifest


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

    for raw in (forward, duplicate, old_design):
        parsed = read_handover(raw)
        assert isinstance(parsed, Blocked), raw
        assert parsed.what == "HandoverMalformed", raw
    restored = read_handover(typed_authority)
    assert isinstance(restored, StoredHandover)
    opaque = restored.values[0].authority
    assert isinstance(opaque, PreNormalizedDesign)
    assert opaque.raw == {"locator": "docs/a.md"}
    assert restored.raw == typed_authority
    assert "DesignFactsPreNormalized" in design_facts_defect(opaque)


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
    facts = _facts(
        constraints=(FactRef(FactId("Constraint")),),
        facts=(*_facts().facts, FactRecord(FactId("Constraint"), "constraint")),
    )
    canonical = json.loads(
        _canonical_bytes("deliver", (HandoverValue("A", (), facts),))
    )

    for malformed in (
        1,
        [1],
        [{"ref": ""}],
        [{"ref": " "}],
        [""],
        [" "],
        ["constraint", "constraint"],
    ):
        payload = json.loads(json.dumps(canonical))
        payload["values"][0]["authority"]["constraints"] = malformed
        raw = json.dumps(payload, separators=(",", ":")).encode()
        parsed = read_handover(raw)
        assert isinstance(parsed, Blocked), malformed
        assert parsed.what == "HandoverMalformed", malformed
    repeated_definition = json.loads(json.dumps(canonical))
    authority = repeated_definition["values"][0]["authority"]
    authority["facts"].append({"id": "ConstraintAgain", "text": "constraint"})
    authority["constraints"].append({"ref": "ConstraintAgain"})
    parsed = read_handover(
        json.dumps(repeated_definition, separators=(",", ":")).encode()
    )
    assert isinstance(parsed, Blocked)
    assert parsed.what == "HandoverMalformed"
    assert "DesignFactTextRepeated" in parsed.why

    legacy = json.loads(json.dumps(canonical))
    del legacy["values"][0]["authority"]["schema_version"]
    legacy["values"][0]["authority"]["obligations"] = ["constraint"]
    parsed_legacy = read_handover(json.dumps(legacy, separators=(",", ":")).encode())
    assert isinstance(parsed_legacy, StoredHandover)
    assert isinstance(parsed_legacy.values[0].authority, PreNormalizedDesign)
    assert parsed_legacy.values[0].authority.raw == legacy["values"][0]["authority"]
    assert "DesignFactsPreNormalized" in design_facts_defect(
        parsed_legacy.values[0].authority
    )


def test_reader_validates_raw_public_oracle_members_without_breaking_legacy_shape() -> (
    None
):
    facts = _facts()
    canonical = json.loads(
        _canonical_bytes("deliver", (HandoverValue("A", (), facts),))
    )

    # Malformed public_oracle values should be rejected
    for malformed in (
        1,  # not an object
        [],  # not an object
        {
            "observation": canonical["values"][0]["authority"]["public_oracle"][
                "observation"
            ]
        },
        {
            **canonical["values"][0]["authority"]["public_oracle"],
            "stimulus": {"ref": ""},
        },
        {
            **canonical["values"][0]["authority"]["public_oracle"],
            "stimulus": {"ref": " "},
        },
        {
            **canonical["values"][0]["authority"]["public_oracle"],
            "extra": "key",
        },
        {
            "observation": "obs",
            "stimulus": "stim",
            "expected": "exp",
            "falsifier": "fals",
        },
    ):
        payload = json.loads(json.dumps(canonical))
        payload["values"][0]["authority"]["public_oracle"] = malformed
        raw = json.dumps(payload, separators=(",", ":")).encode()
        parsed = read_handover(raw)
        assert isinstance(parsed, Blocked), malformed
        assert parsed.what == "HandoverMalformed", malformed

    # Pre-normalized absence is retained only as opaque, non-executable data.
    legacy = json.loads(json.dumps(canonical))
    del legacy["values"][0]["authority"]["public_oracle"]
    del legacy["values"][0]["authority"]["schema_version"]
    parsed_legacy = read_handover(json.dumps(legacy, separators=(",", ":")).encode())
    assert isinstance(parsed_legacy, StoredHandover)
    assert isinstance(parsed_legacy.values[0].authority, PreNormalizedDesign)
    assert parsed_legacy.values[0].authority.raw == legacy["values"][0]["authority"]
    assert "DesignFactsPreNormalized" in design_facts_defect(
        parsed_legacy.values[0].authority
    )

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
        base = _facts()
        return replace(
            base,
            targets=(DesignTarget(target, "EXTEND", base.targets[0].reason),),
            oracle=oracle,
            acceptance_supports=support,
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
    assert "oracle_verification_index" in parsed.why


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


@pytest.mark.parametrize("policy", (None, b"# custom policy\r\ncache/\r\n"))
def test_delivery_lock_ignores_only_runtime_and_preserves_nwave_policy(
    tmp_path, policy
) -> None:
    import subprocess

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    assert git("init").returncode == 0
    nwave = tmp_path / ".nwave"
    nwave.mkdir()
    config = nwave / "config.json"
    config_bytes = b'{"rigor":"custom"}\n'
    config.write_bytes(config_bytes)
    assert git("add", ".nwave/config.json").returncode == 0
    user_ignore = nwave / ".gitignore"
    if policy is not None:
        user_ignore.write_bytes(policy)

    lock = acquire_delivery_lock(tmp_path)
    try:
        assert not isinstance(lock, Blocked), lock
        runtime_ignore = nwave / "des/.gitignore"
        assert runtime_ignore.is_file()
        patterns = [
            line
            for line in runtime_ignore.read_text().splitlines()
            if line and not line.startswith("#")
        ]
        assert patterns == ["*"]
        assert (nwave / "des/commit.lock").is_file()
        ignored = git("check-ignore", "-v", ".nwave/des/commit.lock")
        assert ignored.returncode == 0, ignored.stderr
        assert ".nwave/des/.gitignore:" in ignored.stdout
        assert git("check-ignore", ".nwave/des/.gitignore").returncode == 0
        assert git("check-ignore", "--no-index", ".nwave/config.json").returncode == 1
        assert git("ls-files", "--", ".nwave/config.json").stdout.splitlines() == [
            ".nwave/config.json"
        ]
        assert config.read_bytes() == config_bytes
        if policy is None:
            assert not user_ignore.exists()
        else:
            assert user_ignore.read_bytes() == policy
    finally:
        if not isinstance(lock, Blocked):
            lock.release()


def test_delivery_lock_never_overwrites_existing_runtime_ignore(tmp_path) -> None:
    directory = tmp_path / ".nwave/des"
    directory.mkdir(parents=True)
    ignore = directory / ".gitignore"
    original = b"# retained runtime policy\r\n*\r\n"
    ignore.write_bytes(original)

    lock = acquire_delivery_lock(tmp_path)
    try:
        assert not isinstance(lock, Blocked), lock
        assert ignore.read_bytes() == original
        assert (directory / "commit.lock").is_file()
    finally:
        if not isinstance(lock, Blocked):
            lock.release()


def test_unavailable_runtime_ignore_storage_refuses_before_lock_or_state_change(
    tmp_path,
) -> None:
    import os
    import stat

    stored = create_handover(tmp_path, "deliver", (HandoverValue("A", (), None),))
    assert isinstance(stored, StoredHandover)
    directory = tmp_path / ".nwave/des"
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    original_mode = stat.S_IMODE(directory.stat().st_mode)
    assert os.geteuid() != 0, "permission refusal requires an unprivileged host"
    lock = None
    try:
        directory.chmod(0o555)
        assert not os.access(directory, os.W_OK), "storage must actually deny writes"

        lock = acquire_delivery_lock(tmp_path)

        assert isinstance(lock, Blocked), lock
        assert lock.what == "DeliveryLockUnavailable"
        assert str(directory / ".gitignore") in lock.why
        assert lock.how
        assert not (directory / "commit.lock").exists()
        assert not (directory / ".gitignore").exists()
        assert {path.name: path.read_bytes() for path in directory.iterdir()} == before
        assert handover_path(tmp_path).read_bytes() == stored.raw
    finally:
        if lock is not None and not isinstance(lock, Blocked):
            lock.release()
        directory.chmod(original_mode)


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
    base = DesignDocument.from_json(
        json.dumps(
            design_manifest(
                {
                    "targets": [{"path": "src/value.py", "decision": "EXTEND"}],
                    "paradigm": "object_oriented",
                    "decisions": ["reuse the existing boundary"],
                    "oracle": "tests/test_value.py",
                    "acceptance_supports": [],
                    "verification": [["python", "-m", "pytest"]],
                    "oracle_verification_index": 0,
                    "architectural_tests": {
                        "applicability": "not_applicable",
                        "reason": "The fixture has no structural boundary change.",
                    },
                    "contract_tests": {
                        "applicability": "not_applicable",
                        "reason": "The fixture changes no shared contract.",
                    },
                    "prefactoring": {
                        "applicability": "not_applicable",
                        "reason": "The fixture requires no preservation move.",
                    },
                    "agreement_analysis": {
                        "applicability": "not_applicable",
                        "reason": "The fixture has no affected agreement.",
                    },
                    "reuse_analysis": {"candidates": []},
                    "impact_closure": {
                        "applicability": "not_applicable",
                        "reason": "The fixture reaches no public surface, consumer or build metadata.",
                    },
                },
                "Expose value.",
                1,
            )
        )
    ).facts
    return replace(base, **overrides)


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
            DesignTarget("src/value.py", "EXTEND", _facts().targets[0].reason),
            DesignTarget("src/value.py", "CREATE_NEW", _facts().targets[0].reason),
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
        targets=(DesignTarget("src/value.py", decision, _facts().targets[0].reason),),
        acceptance_supports=("tests/support/helper.py", "src/value.py"),
    )

    defect = design_facts_defect(conflict)
    assert defect is not None
    assert "src/value.py" in defect and "helper.py" not in defect


def test_persisted_support_conflicts_are_opaque_and_refused_for_execution() -> None:
    """Old support bindings remain correctable, never executable compatibility."""
    from pathlib import Path

    from des.application.delivery_continuation import (
        DeliveryContinuationRunner,
        DeliveryOutcome,
    )

    for decision in ("EXTEND", "CREATE_NEW"):
        current = _facts(
            targets=(
                DesignTarget("src/value.py", decision, _facts().targets[0].reason),
            ),
            acceptance_supports=("src/value.py",),
        )
        assert design_facts_defect(current) is not None
        payload = json.loads(
            _canonical_bytes("deliver", (HandoverValue("A", (), current),))
        )
        del payload["values"][0]["authority"]["schema_version"]
        original = json.dumps(payload, separators=(",", ":")).encode()
        restored = read_handover(original)
        assert isinstance(restored, StoredHandover)
        assert restored.raw == original
        opaque = restored.values[0].authority
        assert isinstance(opaque, PreNormalizedDesign)
        assert opaque.raw == payload["values"][0]["authority"]
        refused = DeliveryContinuationRunner().derive_authority(Path(), opaque)
        assert isinstance(refused, DeliveryOutcome)
        assert refused.failure.what == "DesignFactsPreNormalized"
        assert "--replace-current" in refused.failure.how


def test_a_support_only_helper_beside_an_extended_target_is_valid() -> None:
    support_only = _facts(acceptance_supports=("tests/support/new_helper.py",))
    extended = _facts(
        targets=(DesignTarget("src/value.py", "EXTEND", _facts().targets[0].reason),),
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
            _facts(acceptance_supports=(prose,)),
        ),
    )

    parsed = read_handover(_canonical_bytes("deliver", values))

    assert isinstance(parsed, Blocked)
    assert parsed.what == "HandoverMalformed"
    assert "acceptance_supports[0]" in parsed.why
    assert prose in parsed.why


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
        facts=(
            *_facts().facts,
            *(
                FactRecord(FactId(identifier), text)
                for identifier, text in (
                    ("ReuseReason", "No existing renderer fits the contract."),
                    ("ImpactReason", "The target is rewritten."),
                    ("AdrContext", "context"),
                    ("AdrDecision", "decision"),
                    ("AdrAlternative", "alternative"),
                    ("AdrConsequence", "consequence"),
                    ("NoAdr", "The fixture needs no decision record."),
                    ("MigratedReason", "The target is migrated."),
                )
            ),
        ),
        reuse_analysis=ReuseAnalysis(
            (
                ReuseCandidate(
                    "Value.render",
                    "src/value.py:10",
                    "CREATE_NEW",
                    FactRef(FactId("ReuseReason")),
                ),
            )
        ),
        impact_closure=ApplicableImpactClosure(
            (
                ImpactItem(
                    "runtime",
                    "src/value.py",
                    "CHANGED",
                    FactRef(FactId("ImpactReason")),
                ),
            )
        ),
        adr=ApplicableADR(
            FactRef(FactId("AdrContext")),
            FactRef(FactId("AdrDecision")),
            (FactRef(FactId("AdrAlternative")),),
            (FactRef(FactId("AdrConsequence")),),
            "accepted",
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
        "adr": NotApplicable(FactRef(FactId("NoAdr"))),
        "impact_closure": ApplicableImpactClosure(
            (
                ImpactItem(
                    "runtime",
                    "src/value.py",
                    "MIGRATED",
                    FactRef(FactId("MigratedReason")),
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
    del canonical["values"][0]["authority"]["schema_version"]

    parsed = read_handover(json.dumps(canonical, separators=(",", ":")).encode())

    assert isinstance(parsed, StoredHandover)
    authority = parsed.values[0].authority
    assert isinstance(authority, PreNormalizedDesign)
    assert authority.raw == canonical["values"][0]["authority"]
    assert "DesignFactsPreNormalized" in design_facts_defect(authority)


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


@pytest.mark.parametrize(
    "required_instruction",
    [
        "Keep every scenario body visibly in domain-language typed steps: Given, "
        "exactly one When, Then for journeys; Arrange, exactly one Act, Assert for "
        "focused contract/property tests. Use fresh scenario-scoped context and "
        "reusable steps, never whole-scenario or scenario-kind-branching helpers.",
        "Drive every test through the declared public port: build the stimulus and "
        "read the result through that port, never by importing production modules, "
        "constructing production objects, calling below the port or patching internal "
        "state, in test bodies or in support files. The only exception is an "
        "obligation the DESIGN places at a declared contract or architecture locator: "
        "there, construct only the members that DESIGN names for it, in one "
        "composition-root helper in the support files, and keep test bodies calling "
        "that helper; never use this exception to observe a public-port obligation "
        "below the port.",
        "Test DESIGN-declared construction restrictions and error-code identities "
        "through their declared public contract surface: use the public port for "
        "emitted codes and observe accepted and refused inputs through the declared "
        "public port, using the injection seam where DESIGN declares one, in a "
        "contract test at the DESIGN-declared locator. Never mark these "
        "boundary obligations NOT TESTED. If no declared surface or locator can "
        "observe one, return `rejected` with `BLOCKED-BY design`, naming the obligation, "
        "the missing declaration and the DESIGN correction needed; do not import "
        "internals or invent a seam.",
        "Cover every DESIGN law with at least one Hypothesis @given property naming "
        "its exact id in the test name or docstring. For a finite domain, use "
        "st.sampled_from over the entire declared domain, including all alternatives "
        "and combinations, not a selected subset; retain tables for explicit examples, "
        "not as substitutes for the property. A full strategy domain is not evidence "
        "that every value was executed.",
        "For a DESIGN prohibition on retries, recovery or additional discovery, "
        "observe the declared dependency interaction per public invocation; "
        "unchanged final output or file bytes alone do not establish that prohibition.",
        "For a DESIGN obligation that excludes a claim or preserves an output field, "
        "assert the excluded claim's absence and the field's presence explicitly; "
        "a positive label or a nullable lookup is not that observation.",
        "Treat Hypothesis @example decorators and standalone finite examples as "
        "example-table cases: keep each explicit stimulus/assertion pair in one place "
        "across the primary oracle, finite tables and generated properties, retaining "
        "another occurrence only for a different assertion.",
        "Keep each concrete finite stimulus/assertion case once; when laws share it, "
        "one table observes it once and cites all applicable laws; each generative "
        "property adds only different cases or assertions.",
        "Retain and extend every DESIGN-declared EXTEND or retained test helper; "
        "replace one only with a specific reason in the diagnostic.",
    ],
)
def test_atd_oracle_prompt_preserves_authorization_and_return_schema(
    tmp_path, capsys, required_instruction
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
                "nw-acceptance-designer",
                "--value",
                "1",
                "--root-context",
                str(context),
            ]
        )
        == 0
    )
    prompt = capsys.readouterr().out
    assert prompt.count("jev_decide.py") == 1
    assert required_instruction in prompt, (
        f"WHAT: the rendered prompt lacks the required instruction {required_instruction!r}. "
        "WHY: acceptance authors must receive the complete declared instruction contract. "
        "HOW: correct the affected template clause without changing unrelated guidance."
    )
    assert "belong ONLY in the support files" not in prompt
    assert (
        "declared public constructor for accepted and refused inputs" not in prompt
    ), (
        "WHAT: the rendered prompt still directs accepted/refused inputs through a constructor. "
        "WHY: these observations belong at the declared public port and declared injection seam. "
        "HOW: replace the superseded constructor instruction with the public-port instruction."
    )
    return_section = prompt.split("## RETURN", 1)[1].split("## FROM THE ROOT", 1)[0]
    object_match = re.search(r"`(\{[^`]+\})`", return_section)
    assert object_match is not None
    # The displayed JSON schema uses quoted alternatives for enum values.
    example = re.sub(
        r'("(?:[^"\\]|\\.)*")(?:\s*\|\s*"(?:[^"\\]|\\.)*")+',
        r"\1",
        object_match.group(1),
    )
    assert set(json.loads(example)) == {"outcome", "diagnostic"}


@pytest.mark.parametrize(
    "required_instruction",
    [
        "Treat the design as binding: every decision, boundary, reuse decision, "
        "architectural test and contract test in `native_input.selected_authority`, "
        "and every law, construction claim and mapped symbol in "
        "`native_input.architect_projection`.",
        "Treat the tests as the specification: the public oracle is the outer loop; "
        "architectural and contract tests bind the structure.",
        "`object_oriented`: `nw-code-design-oo`. `functional`: `nw-code-design-fp`. "
        "`procedural`: preserve the imperative structure the DESIGN bound, with the "
        "universal rules of `nw-code-craftsmanship`.",
        "`object_oriented`, in the Refactoring Priority Premise order of "
        "`nw-code-design-oo`, until the changed code shows no smell of levels L1-L4; "
        "`functional`, in the refactoring order of `nw-code-design-fp`, preserving "
        "every declared law; `procedural`, readability, complexity and duplication only.",
        "When the paradigm is `object_oriented` and the bound targets or decisions "
        "place a decision about one object's data in an application service or script",
    ],
)
def test_craft_implementation_prompt_binds_design_tests_and_paradigm_rules(
    required_instruction,
):
    from des.application import architect_prompt

    spec = json.loads(
        (
            Path(__file__).parents[4]
            / "nWave/templates/architect-handoff/craft.impl-v3.spec.json"
        ).read_text(encoding="utf-8")
    )
    fixture = {
        field: ["supplied"] if kind == "list" else "supplied"
        for field, kind in spec["required"].items()
    }
    prompt, _ = architect_prompt.render(
        "craft.impl-v3", fixture, role_id="nw-software-crafter"
    )
    assert required_instruction in " ".join(prompt.split()), (
        f"WHAT: the crafter prompt lacks {required_instruction!r}. "
        "WHY: the crafter must receive the design, the tests and the paradigm rules "
        "as binding constraints, and refuse a design that forces an anemic model. "
        "HOW: restore the clause in craft.impl-v3.tmpl without changing unrelated lines."
    )


def test_architect_prompt_designs_for_the_crafter_paradigm_rules(tmp_path, capsys):
    from des.cli.handoff import main

    stored = create_handover(tmp_path, "deliver", (HandoverValue("A", (), _facts()),))
    assert isinstance(stored, StoredHandover)
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
    prompt = " ".join(capsys.readouterr().out.split())
    assert (
        "Never place a decision about one object's data in an application service "
        "or script: the crafter refuses a design that forces an anemic entity, an "
        "application transaction script or domain decisions in effectful code."
    ) in prompt, (
        "WHAT: the architect prompt does not carry the crafter's ownership rule. "
        "WHY: a design that places domain decisions in application services forces "
        "the crafter to write a transaction script or refuse. "
        "HOW: restore the domain-owners clause in design.architect-v9.tmpl."
    )


def test_role_invocation_passes_the_canonical_role_prompt_verbatim():
    guidance = " ".join(
        (Path(__file__).parents[4] / "nWave/skills/nw-role-invocation/SKILL.md")
        .read_text(encoding="utf-8")
        .split()
    )
    assert (
        "run `des handoff --repo-root ROOT prompt --role ROLE [--value N] "
        "--root-context FILE`"
        in guidance
        and "pass its stdout verbatim as the role's task" in guidance
        and "`--role nw-software-crafter` or `--role nw-functional-software-crafter`"
        in guidance
    ), (
        "WHAT: the host role-invocation guidance does not name the canonical prompt "
        "producer for the architect, acceptance designer and crafter. WHY: a host "
        "that composes its own crafter prompt never delivers the design handoff, "
        "the tests or the paradigm rules. HOW: restore the `des handoff ... prompt` "
        "paragraph in nw-role-invocation/SKILL.md."
    )


def test_atd_oracle_prompt_requires_review_without_repeating_finite_prefixes(
    tmp_path, capsys
):
    """The author receives the complete self-check before returning their oracle.

    @contract-shape: real-io
    """
    from des.cli.handoff import main

    handover = create_handover(tmp_path, "deliver", (HandoverValue("A", (), _facts()),))
    assert isinstance(handover, StoredHandover), (
        f"WHAT: the admitted handover was not stored; received {handover!r}. "
        "WHY: the author needs a valid handover to receive the instruction. "
        "HOW: persist the existing admitted facts through the handover entry point."
    )
    context = tmp_path / "root.txt"
    context.write_text("host context\n")
    result = main(
        [
            "--repo-root",
            str(tmp_path),
            "prompt",
            "--role",
            "nw-acceptance-designer",
            "--value",
            "1",
            "--root-context",
            str(context),
        ]
    )
    assert result == 0, (
        f"WHAT: prompt delivery returned {result!r}, expected successful exit 0. "
        "WHY: the author must receive the guidance through the public prompt entry. "
        "HOW: render and emit the prompt for the admitted handover and root context."
    )
    prompt = capsys.readouterr().out
    instruction = (
        "- Before returning, inspect your oracle: no property may repeat a finite "
        "case's stimulus-and-assertion sequence or prefix, even with new suffix "
        "assertions; add only generated domain or new assertions, and cite shared "
        "cases by reference to the owning table."
    )
    occurrences = prompt.count(instruction)
    assert occurrences == 1, (
        f"WHAT: the emitted prompt contains {occurrences} occurrences of the complete "
        f"self-check, expected exactly one: {instruction!r}. "
        "WHY: the author must receive the full finite-prefix self-check, including "
        "suffix coverage and owning-table references, without duplicate guidance. "
        "HOW: add the exact authorized instruction once to the template before RETURN."
    )
    task_position = prompt.find("## TASK (template)")
    instruction_position = prompt.find(instruction)
    return_position = prompt.find("## RETURN")
    assert 0 <= task_position < instruction_position < return_position, (
        f"WHAT: TASK, self-check and RETURN positions are {task_position}, "
        f"{instruction_position} and {return_position}, expected that order. "
        "WHY: the author must receive the self-check as task guidance before returning. "
        "HOW: place the instruction in TASK immediately before the blank line preceding RETURN."
    )


def test_atd_oracle_prompt_uses_consistent_obligation_line_shapes(tmp_path, capsys):
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
                "nw-acceptance-designer",
                "--value",
                "1",
                "--root-context",
                str(context),
            ]
        )
        == 0
    )
    prompt = capsys.readouterr().out
    return_section = prompt.split("## RETURN", 1)[1].split("## FROM THE ROOT", 1)[0]
    shape_pattern = r"`(O<n> \[[^`]*?)`"
    task_section = prompt.split("## RETURN", 1)[0]
    tested_shape = (
        "O<n> [<DESIGN id or name>]: stimulus <few words>; expected <few words>; "
        "user result <what the user can observe or accomplish, in plain words>; "
        "test <test file>::<test name>"
    )
    untested_shape = (
        "O<n> [<DESIGN id or name>]: NOT TESTED - <reason from the DESIGN>; "
        "owner: <owner the DESIGN declares, or none declared>"
    )
    expected_shapes = {tested_shape, untested_shape}
    untested_product_rule = (
        "Every permitted NOT TESTED O line about a product limit, guarantee or "
        "restriction states the plain-word user result; keep pipeline, provenance "
        "and model-bound facts separate, with no user result required."
    )
    for section in (task_section, return_section):
        shapes = re.findall(shape_pattern, section)
        assert set(shapes) == expected_shapes
        assert shapes.count(tested_shape) == 1
        assert section.count(untested_product_rule) == 1, (
            f"WHAT: a prompt section does not contain exactly one complete rule "
            f"{untested_product_rule!r}; actual section: {section!r}. "
            "WHY: TASK and RETURN must identically require plain user results for "
            "permitted untested product limits, guarantees and restrictions, not nonproduct facts. "
            "HOW: state the identical rule once in each section and preserve O-line shapes "
            "and the DESIGN permission and owner conditions."
        )


def test_native_architect_handoff_keeps_submission_host_owned_and_manifest_only(
    tmp_path, capsys
):
    import shlex

    import jsonschema

    from des.adapters.driven.task_invocation.model_envelope import (
        _schema_for,
        decode_model_run,
    )
    from des.cli.handoff import main
    from des.domain.design_document import DesignDocument, DesignDocumentInvalid
    from des.ports.driven_ports.task_invocation_port import ModelOutcome

    assert isinstance(
        create_handover(tmp_path, "deliver", (HandoverValue("A", (), _facts()),)),
        StoredHandover,
    )
    context = tmp_path / "root.txt"
    context.write_text("host context\n")
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
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
    commands = [
        shlex.split(line.removeprefix("- "))
        for line in submit.splitlines()
        if line.startswith("- des design ")
    ]
    assert commands == [
        ["des", "design", "--repo-root", str(tmp_path), "--shared", "--input", "-"],
        [
            "des",
            "design",
            "--repo-root",
            str(tmp_path),
            "--value",
            "1",
            "--input",
            "-",
        ],
    ]
    assert {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    } == before
    assert "Do not execute" in submit
    assert "BLOCKED-BY: <owner>" in submit

    from des.domain.design_document import normalized_wire

    manifest = {
        key: value
        for key, value in normalized_wire(_facts()).items()
        if key != "authority_locator" and value is not None
    }
    manifest["facts"][0]["text"] = "A"
    schema = jsonschema.Draft202012Validator(
        json.loads(_schema_for("nw-solution-architect"))
    )
    accepted = {"outcome": "accepted", "diagnostic": "", "manifest": manifest}
    schema.validate(accepted)
    assert (
        decode_model_run(accepted, role_id="nw-solution-architect").outcome
        is ModelOutcome.Accepted
    )
    document = DesignDocument.from_json(json.dumps(accepted["manifest"]))
    assert document.facts.purpose.ref == manifest["purpose"]["ref"]
    assert document.facts.facts[0].text == "A"
    with pytest.raises(DesignDocumentInvalid):
        DesignDocument.from_json(json.dumps(accepted))

    diagnostic = "BLOCKED-BY: design; formal checks are not authorized."
    for outcome in ("rejected", "indeterminate"):
        refusal = {"outcome": outcome, "diagnostic": diagnostic, "manifest": None}
        schema.validate(refusal)
        decoded = decode_model_run(refusal, role_id="nw-solution-architect")
        assert decoded.outcome.value == outcome
        assert decoded.diagnostic == diagnostic
        with pytest.raises(jsonschema.ValidationError):
            schema.validate({**refusal, "manifest": manifest})
    assert (
        "If you cannot execute a DESIGN-required verification or lack an authorization "
        "or input, return `rejected` through the caller's enforced schema with "
        "`BLOCKED-BY: <owner>` in `diagnostic`, naming the precise prerequisite "
        "(for example `formal checks not authorized` or `checker unavailable at <path>`). "
        "Use a typed blocker field only if that schema provides it; leave the refused "
        "design payload null, never put a candidate manifest in `diagnostic`, and "
        "never return `accepted`."
    ) in submit
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


def _detached_catalog(tmp_path):
    """Name actual schema-2 manifest bytes for detached rendering consumers."""
    import hashlib

    from des.domain.design_document import normalized_wire

    source = tmp_path / "catalog.design.json"
    source.write_text(
        json.dumps(
            {
                key: value
                for key, value in normalized_wire(_facts()).items()
                if key != "authority_locator" and value is not None
            }
        )
    )
    return [
        {"path": source.name, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    ]


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
    original = json.dumps(
        {"sections": [], "catalog": _detached_catalog(tmp_path)}
    ).encode()
    source.write_bytes(original)
    assert main(["summary", "--repo-root", str(tmp_path), source.name]) == 0
    out, err = capsys.readouterr()
    assert set(json.loads(out)["missing_shared"]) == set(g10_types.REQUIRED_SHARED)
    assert err == ""
    assert source.read_bytes() == original
    assert set(tmp_path.rglob("*")) == {source, tmp_path / "catalog.design.json"}


def test_detached_handoff_render_writes_only_the_requested_html_without_a_handover(
    tmp_path, capsys
):
    from des.cli.handoff import main

    source = tmp_path / "defective.g10.json"
    original = json.dumps(
        {"sections": [], "catalog": _detached_catalog(tmp_path)}
    ).encode()
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
    assert set(tmp_path.rglob("*")) == {source, page, tmp_path / "catalog.design.json"}


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
                "catalog": _detached_catalog(tmp_path),
                "sections": [
                    {
                        "kind": kind,
                        "scope": "shared",
                        "status": {
                            "tag": "not_applicable",
                            "reason": {"ref": _facts().purpose.ref},
                        },
                    }
                    for kind in g10_types.REQUIRED_SHARED
                ],
            }
        )
    )
    assert main(["check", "--repo-root", str(tmp_path), source.name]) == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert "X1" not in out
    assert "need --targets; none were given" not in out
    assert handover_path(tmp_path).read_bytes() == stored.raw


@pytest.mark.parametrize("command", ["summary", "render"])
def test_detached_text_consumer_refuses_missing_catalog_without_effects(
    tmp_path, capsys, command
):
    from des.cli.handoff import main

    source = tmp_path / "detached.g10.json"
    original = b'{"sections": []}\n'
    source.write_bytes(original)
    arguments = [command, "--repo-root", str(tmp_path), source.name]
    if command == "render":
        arguments.extend(["--html", "inspection.html"])
    assert main(arguments) == 1
    out, err = capsys.readouterr()
    assert "ArchitectHandoffCatalogUnavailable" in out + err
    assert "catalog" in (out + err).lower()
    assert source.read_bytes() == original
    assert set(tmp_path.rglob("*")) == {source}
