# @feature-certified-capture
# @slice-01
# @contract-shape:pure-function

"""Public-port properties for the certified-capture value contract.

The external study harness imports only ``nwave_capture``.  The import is
deliberately lazy so the absent slice-01 package is reported as missing
functionality by an executable RED test rather than as a collection failure.
"""

from __future__ import annotations

import dataclasses
import importlib
import string
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import PurePosixPath
from types import ModuleType
from typing import Any, get_args
from uuid import UUID

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


pytestmark = pytest.mark.acceptance

_PUBLIC_NAMES = (
    "TaskCaseContractRef",
    "StudyRef",
    "RunRef",
    "PartitionRef",
    "RequestRef",
    "RepositoryRef",
    "UsageObservationMode",
    "UsageObservationSemantics",
    "RunManifest",
    "Complete",
    "Incomplete",
    "Indeterminate",
    "CaptureResult",
)
_IDENTIFIERS = st.text(
    alphabet=string.ascii_letters + string.digits + "-_:.", min_size=1
)
_DIGESTS = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)
_UTC_TIMESTAMPS = st.datetimes(
    min_value=datetime.min,
    max_value=datetime.max - timedelta(days=30),
    timezones=st.just(UTC),
)


def _capture_public_port() -> ModuleType:
    """Return the study-facing package root or fail as missing functionality."""
    modules_before_import = set(sys.modules)
    try:
        capture = importlib.import_module("nwave_capture")
    except ModuleNotFoundError as error:
        pytest.fail(
            "WHAT: the study-facing nwave_capture public port is absent. "
            "WHY: an external harness must construct certified-capture values "
            "without importing DES or checkout internals. HOW: add and package "
            "src/nwave_capture with the ratified root exports. "
            f"MISSING_FUNCTIONALITY: {error}"
        )

    missing = [name for name in _PUBLIC_NAMES if not hasattr(capture, name)]
    assert missing == [], (
        "WHAT: the public capture port omits ratified contract names. WHY: the "
        "external harness depends only on package-root values. HOW: re-export "
        f"the declared names from nwave_capture.__init__; missing={missing}"
    )
    exported_names = getattr(capture, "__all__", None)
    public_names = tuple(exported_names or ())
    original_name_counts = {name: public_names.count(name) for name in _PUBLIC_NAMES}
    assert all(count == 1 for count in original_name_counts.values()), (
        "WHAT: the package root removed or repeated an original slice-01 public "
        f"name; observed counts={original_name_counts}, root={public_names}. "
        "WHY: later certified-capture slices may extend the public root but existing "
        "study harnesses still require every original contract name exactly once. "
        "HOW: DELIVER must restore each of the 13 original names once; keep exact "
        "current-root membership enforcement in the latest-slice clean-wheel AT."
    )
    leaked = sorted(
        name
        for name in set(sys.modules) - modules_before_import
        if name == "des" or name.startswith(("des.", "src.des", "scripts", "tests"))
    )
    assert leaked == [], (
        "WHAT: importing the neutral public port loaded a prohibited runtime "
        f"module: {leaked}. WHY: the study contract must remain DES-neutral. "
        "HOW: keep nwave_capture imports restricted to the standard library."
    )
    return capture


def _valid_manifest(
    capture: ModuleType,
    *,
    identifier: str = "case-1",
    digest: str = "a" * 64,
    run_id: UUID = UUID("12345678-1234-5678-1234-567812345678"),
    attempt_no: int = 1,
    started_at: datetime = datetime(2026, 8, 5, tzinfo=UTC),
) -> Any:
    capture.TaskCaseContractRef(identifier, digest, digest, digest, digest)
    study = capture.StudyRef("study-1", digest, "current-des")
    run = capture.RunRef(run_id, attempt_no, study)
    root = capture.PartitionRef("root", run_id, "host-1", "host")
    semantics = capture.UsageObservationSemantics(
        "anthropic", "v1", capture.UsageObservationMode.CUMULATIVE_SNAPSHOT, "max-v1"
    )
    repository = capture.RepositoryRef(digest, digest, "f" * 40)
    return capture.RunManifest(
        "v1",
        run,
        digest,
        ("tokens",),
        (semantics,),
        root,
        started_at,
        started_at + timedelta(minutes=1),
        started_at + timedelta(minutes=6),
        PurePosixPath("/tmp/certified-capture"),
        digest,
        digest,
        digest,
        digest,
        "writer-v1",
        "metadata-only",
        started_at + timedelta(days=30),
        repository,
        ("anthropic:v1",),
        digest,
    )


def _valid_public_records(capture: ModuleType) -> dict[str, Any]:
    """Literal valid records keyed by their public package-root names."""
    manifest = _valid_manifest(capture)
    digest = "a" * 64
    root = manifest.root_partition
    return {
        "TaskCaseContractRef": capture.TaskCaseContractRef(
            "case-1", digest, digest, digest, digest
        ),
        "StudyRef": manifest.run.study,
        "RunRef": manifest.run,
        "PartitionRef": root,
        "RequestRef": capture.RequestRef("anthropic", "request-1", root, "claude"),
        "RepositoryRef": manifest.repository,
        "UsageObservationSemantics": manifest.usage_observation_semantics[0],
        "RunManifest": manifest,
        "Complete": capture.Complete(digest),
        "Incomplete": capture.Incomplete(("writer-refused",)),
        "Indeterminate": capture.Indeterminate(("unknown-provenance",)),
    }


_WRONG_TYPE_CASES = (
    ("TaskCaseContractRef", "task_case_id", 0),
    ("TaskCaseContractRef", "task_spec_digest", 0),
    ("TaskCaseContractRef", "initial_state_digest", 0),
    ("TaskCaseContractRef", "environment_contract_digest", 0),
    ("TaskCaseContractRef", "quality_evaluation_plan_digest", 0),
    ("StudyRef", "study_id", 0),
    ("StudyRef", "task_case_contract_digest", 0),
    ("StudyRef", "comparator_id", 0),
    ("RunRef", "run_id", "not-a-uuid"),
    ("RunRef", "attempt_no", True),
    ("RunRef", "study", "not-a-study"),
    ("PartitionRef", "partition_id", 0),
    ("PartitionRef", "run_id", "not-a-uuid"),
    ("PartitionRef", "actor_id", 0),
    ("PartitionRef", "actor_kind", 0),
    ("PartitionRef", "parent_partition_id", 0),
    ("RequestRef", "provider_namespace", 0),
    ("RequestRef", "request_id", 0),
    ("RequestRef", "partition", "not-a-partition"),
    ("RequestRef", "model", 0),
    ("RepositoryRef", "repo_id", 0),
    ("RepositoryRef", "worktree_id", 0),
    ("RepositoryRef", "base_commit_sha", 0),
    ("RepositoryRef", "observed_head_sha", 0),
    ("UsageObservationSemantics", "provider_namespace", 0),
    ("UsageObservationSemantics", "schema_version", 0),
    ("UsageObservationSemantics", "mode", "delta"),
    ("UsageObservationSemantics", "reducer_id_and_version", 0),
    ("RunManifest", "capture_schema_version", 0),
    ("RunManifest", "run", "not-a-run"),
    ("RunManifest", "task_case_contract_digest", 0),
    ("RunManifest", "metric_vocabulary", ["tokens"]),
    ("RunManifest", "metric_vocabulary", (0,)),
    ("RunManifest", "usage_observation_semantics", []),
    ("RunManifest", "usage_observation_semantics", ("not-semantics",)),
    ("RunManifest", "root_partition", "not-a-partition"),
    ("RunManifest", "interval_start", "not-a-datetime"),
    ("RunManifest", "interval_end", "not-a-datetime"),
    ("RunManifest", "reconciliation_deadline", "not-a-datetime"),
    ("RunManifest", "canonical_capture_root", "/relative/string"),
    ("RunManifest", "runtime_digest", 0),
    ("RunManifest", "hook_digest", 0),
    ("RunManifest", "executable_digest", 0),
    ("RunManifest", "config_digest", 0),
    ("RunManifest", "primary_writer_version", 0),
    ("RunManifest", "retention_target", 0),
    ("RunManifest", "retention_deadline", "not-a-datetime"),
    ("RunManifest", "repository", "not-a-repository"),
    ("RunManifest", "provider_namespace_versions", ["anthropic:v1"]),
    ("RunManifest", "provider_namespace_versions", (0,)),
    ("RunManifest", "manifest_digest", 0),
    ("Complete", "certificate_digest", 0),
    ("Incomplete", "known_failures", ["writer-refused"]),
    ("Incomplete", "known_failures", (0,)),
    ("Indeterminate", "unknowns", ["unknown-provenance"]),
    ("Indeterminate", "unknowns", (0,)),
)


_DIGEST_FIELDS = (
    ("TaskCaseContractRef", "task_spec_digest"),
    ("TaskCaseContractRef", "initial_state_digest"),
    ("TaskCaseContractRef", "environment_contract_digest"),
    ("TaskCaseContractRef", "quality_evaluation_plan_digest"),
    ("StudyRef", "task_case_contract_digest"),
    ("RepositoryRef", "repo_id"),
    ("RepositoryRef", "worktree_id"),
    ("RunManifest", "task_case_contract_digest"),
    ("RunManifest", "runtime_digest"),
    ("RunManifest", "hook_digest"),
    ("RunManifest", "executable_digest"),
    ("RunManifest", "config_digest"),
    ("RunManifest", "manifest_digest"),
    ("Complete", "certificate_digest"),
)
_INVALID_DIGESTS = ("A" * 64, "a" * 63, "g" * 64)

_TRIMMED_STRING_FIELDS = (
    ("TaskCaseContractRef", "task_case_id"),
    ("StudyRef", "study_id"),
    ("StudyRef", "comparator_id"),
    ("PartitionRef", "partition_id"),
    ("PartitionRef", "actor_id"),
    ("PartitionRef", "actor_kind"),
    ("PartitionRef", "parent_partition_id"),
    ("RequestRef", "provider_namespace"),
    ("RequestRef", "request_id"),
    ("RequestRef", "model"),
    ("RepositoryRef", "base_commit_sha"),
    ("RepositoryRef", "observed_head_sha"),
    ("UsageObservationSemantics", "provider_namespace"),
    ("UsageObservationSemantics", "schema_version"),
    ("UsageObservationSemantics", "reducer_id_and_version"),
    ("RunManifest", "capture_schema_version"),
    ("RunManifest", "primary_writer_version"),
    ("RunManifest", "retention_target"),
)
_TRIMMED_TUPLE_MEMBER_FIELDS = (
    ("RunManifest", "metric_vocabulary"),
    ("RunManifest", "provider_namespace_versions"),
    ("Incomplete", "known_failures"),
    ("Indeterminate", "unknowns"),
)
_INVALID_TRIMMED_STRINGS = ("", " ", " padded ")

_INVALID_VALUE_CASES = (
    (
        ("RunRef", "attempt_no", 0),
        ("RunManifest", "canonical_capture_root", PurePosixPath("relative/root")),
    )
    + tuple(
        (record, field, invalid)
        for record, field in _DIGEST_FIELDS
        for invalid in _INVALID_DIGESTS
    )
    + tuple(
        (record, field, invalid)
        for record, field in _TRIMMED_STRING_FIELDS
        for invalid in _INVALID_TRIMMED_STRINGS
    )
    + tuple(
        (record, field, (invalid,))
        for record, field in _TRIMMED_TUPLE_MEMBER_FIELDS
        for invalid in _INVALID_TRIMMED_STRINGS
    )
)

_SPECIAL_INVALID_CASES = (
    "interval_start_naive",
    "interval_start_non_utc",
    "interval_end_naive",
    "interval_end_non_utc",
    "reconciliation_deadline_naive",
    "reconciliation_deadline_non_utc",
    "retention_deadline_naive",
    "retention_deadline_non_utc",
    "start_not_before_end",
    "end_after_reconciliation",
    "reconciliation_after_retention",
    "study_digest_mismatch",
    "root_run_mismatch",
    "root_has_parent",
    "duplicate_provider_namespace",
)


@given(
    identifier=_IDENTIFIERS,
    digest=_DIGESTS,
    run_id=st.uuids(),
    attempt_no=st.integers(min_value=1),
    started_at=_UTC_TIMESTAMPS,
)
@settings(max_examples=40, deadline=None)
def test_external_harness_constructs_immutable_coherent_capture_manifest(
    identifier: str,
    digest: str,
    run_id: UUID,
    attempt_no: int,
    started_at: datetime,
) -> None:
    """All valid unbounded identities yield a frozen, coherent public manifest.

    CONTRACT_SHAPE: pure-function
    Outcome anchor: DISCUSS Elevator Pitch — A clean installed nwave_capture wheel exposes public contracts, manifest, and result values that an external harness can construct without importing DES.
    # domain: certified-capture-public-identifiers
    # covers: R2
    # covers: R3
    # covers: R4
    # covers: R8
    """
    capture = _capture_public_port()
    manifest = _valid_manifest(
        capture,
        identifier=identifier,
        digest=digest,
        run_id=run_id,
        attempt_no=attempt_no,
        started_at=started_at,
    )
    mode_members = {
        name: member.value
        for name, member in capture.UsageObservationMode.__members__.items()
    }
    child = capture.PartitionRef("child", run_id, "agent-1", "agent", "root")
    observed_repository = dataclasses.replace(
        manifest.repository, observed_head_sha="f" * 40
    )
    semantics_by_mode = tuple(
        capture.UsageObservationSemantics("provider", "v1", mode, "reducer-v1")
        for mode in capture.UsageObservationMode
    )
    end_equal_reconciliation = dataclasses.replace(
        manifest, interval_end=manifest.reconciliation_deadline
    )
    reconciliation_equal_retention = dataclasses.replace(
        manifest, reconciliation_deadline=manifest.retention_deadline
    )

    assert manifest.run.run_id == run_id, (
        "WHAT: a valid public manifest did not preserve its run identity. WHY: "
        "the harness joins all capture evidence by that identity. HOW: retain "
        "the provided RunRef unchanged in RunManifest."
    )
    assert manifest.run.attempt_no == attempt_no, (
        "WHAT: a positive attempt number was not preserved. WHY: retries greater "
        "than one are valid run identities. HOW: accept every int greater than zero."
    )
    assert child.parent_partition_id == "root" and child.run_id == run_id, (
        "WHAT: a valid child partition lost its parent or run. WHY: admitted child "
        "identity is structural. HOW: retain a trimmed non-empty parent on the same run."
    )
    assert observed_repository.observed_head_sha == "f" * 40, (
        "WHAT: a supplied observed repository head was rejected or changed. WHY: the "
        "optional head is valid when supplied as a trimmed string. HOW: preserve it."
    )
    assert tuple(value.mode for value in semantics_by_mode) == tuple(
        capture.UsageObservationMode
    ), (
        "WHAT: a declared usage mode could not construct observation semantics. WHY: "
        "CUMULATIVE_SNAPSHOT, DELTA, and OTHER are all valid. HOW: accept each enum arm."
    )
    assert end_equal_reconciliation.interval_end == (
        end_equal_reconciliation.reconciliation_deadline
    ), (
        "WHAT: equality between interval end and reconciliation deadline was "
        "rejected or changed. WHY: the ratified order allows this boundary. HOW: "
        "enforce interval_end <= reconciliation_deadline, not a strict inequality."
    )
    assert reconciliation_equal_retention.reconciliation_deadline == (
        reconciliation_equal_retention.retention_deadline
    ), (
        "WHAT: equality between reconciliation and retention deadlines was rejected "
        "or changed. WHY: the ratified order allows this boundary. HOW: enforce "
        "reconciliation_deadline <= retention_deadline, not a strict inequality."
    )
    assert (
        dataclasses.is_dataclass(manifest) and manifest.__dataclass_params__.frozen
    ), (
        "WHAT: a public manifest is mutable. WHY: study evidence must not change "
        "after construction. HOW: implement every public value as a frozen dataclass."
    )
    assert mode_members == {
        "CUMULATIVE_SNAPSHOT": "cumulative_snapshot",
        "DELTA": "delta",
        "OTHER": "other",
    }, (
        "WHAT: UsageObservationMode differs from the ratified three values. WHY: "
        "providers require a closed, stable observation vocabulary. HOW: expose "
        "exactly CUMULATIVE_SNAPSHOT, DELTA, and OTHER with their declared values."
    )
    assert get_args(capture.CaptureResult) == (
        capture.Complete,
        capture.Incomplete,
        capture.Indeterminate,
    ), (
        "WHAT: CaptureResult is not the exact closed three-arm public union. WHY: "
        "a fourth or missing arm makes certification outcomes ambiguous. HOW: define "
        "CaptureResult as Complete | Incomplete | Indeterminate in that order."
    )
    assert manifest.repository.observed_head_sha is None, (
        "WHAT: RepositoryRef did not default observed_head_sha to None. WHY: the "
        "optional observed head must remain absent unless the harness supplies it. "
        "HOW: retain the ratified None default on the frozen public record."
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.capture_schema_version = "rewritten"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("record_name", "field_name"),
    (
        ("RunManifest", "metric_vocabulary"),
        ("RunManifest", "usage_observation_semantics"),
        ("RunManifest", "provider_namespace_versions"),
        ("Incomplete", "known_failures"),
        ("Indeterminate", "unknowns"),
    ),
)
@pytest.mark.parametrize(
    ("cardinality", "expected_length"), (("zero", 0), ("one", 1), ("many", 2))
)
def test_external_harness_preserves_zero_one_many_cardinality_rules(
    record_name: str, field_name: str, cardinality: str, expected_length: int
) -> None:
    """Public tuple surfaces reject zero and preserve one or many values.

    CONTRACT_SHAPE: pure-function
    Outcome anchor: DISCUSS Elevator Pitch — A clean installed nwave_capture wheel exposes public contracts, manifest, and result values that an external harness can construct without importing DES.
    # covers: R4
    # covers: R5
    """
    capture = _capture_public_port()
    records = _valid_public_records(capture)
    manifest = records["RunManifest"]
    values_by_surface = {
        ("RunManifest", "metric_vocabulary"): ("tokens", "duration"),
        ("RunManifest", "usage_observation_semantics"): (
            manifest.usage_observation_semantics[0],
            capture.UsageObservationSemantics(
                "openai", "v1", capture.UsageObservationMode.DELTA, "sum-v1"
            ),
        ),
        ("RunManifest", "provider_namespace_versions"): (
            "anthropic:v1",
            "openai:v1",
        ),
        ("Incomplete", "known_failures"): ("writer-refused", "missing-terminal"),
        ("Indeterminate", "unknowns"): ("unknown-provenance", "unknown-runtime"),
    }
    values = values_by_surface[(record_name, field_name)][:expected_length]

    if cardinality == "zero":
        with pytest.raises(ValueError):
            dataclasses.replace(records[record_name], **{field_name: values})
        return

    constructed = dataclasses.replace(records[record_name], **{field_name: values})
    assert getattr(constructed, field_name) == values
    assert len(getattr(constructed, field_name)) == expected_length


@pytest.mark.parametrize(
    ("record_name", "field_name", "wrong_value"), _WRONG_TYPE_CASES
)
def test_external_harness_rejects_wrong_runtime_types(
    record_name: str, field_name: str, wrong_value: Any
) -> None:
    """Wrong runtime types are TypeError, never a later ambiguous failure.

    CONTRACT_SHAPE: pure-function
    Outcome anchor: DISCUSS Elevator Pitch — A clean installed nwave_capture wheel exposes public contracts, manifest, and result values that an external harness can construct without importing DES.
    # covers: R5
    """
    capture = _capture_public_port()
    records = _valid_public_records(capture)

    with pytest.raises(TypeError):
        dataclasses.replace(records[record_name], **{field_name: wrong_value})


@pytest.mark.parametrize(
    ("record_name", "field_name", "invalid_value", "case"),
    tuple((record, field, value, None) for record, field, value in _INVALID_VALUE_CASES)
    + tuple(("RunManifest", "", None, case) for case in _SPECIAL_INVALID_CASES),
)
def test_external_harness_rejects_typed_invalid_capture_values(
    record_name: str, field_name: str, invalid_value: Any, case: str | None
) -> None:
    """Typed invalid values are rejected with ValueError at the public port.

    CONTRACT_SHAPE: pure-function
    Outcome anchor: DISCUSS Elevator Pitch — A clean installed nwave_capture wheel exposes public contracts, manifest, and result values that an external harness can construct without importing DES.
    # covers: R5
    """
    capture = _capture_public_port()
    records = _valid_public_records(capture)
    manifest = records["RunManifest"]
    non_utc = timezone(timedelta(hours=1))

    with pytest.raises(ValueError):
        if case is None:
            dataclasses.replace(records[record_name], **{field_name: invalid_value})
        elif case == "interval_start_naive":
            dataclasses.replace(
                manifest, interval_start=manifest.interval_start.replace(tzinfo=None)
            )
        elif case == "interval_start_non_utc":
            dataclasses.replace(
                manifest, interval_start=manifest.interval_start.astimezone(non_utc)
            )
        elif case == "interval_end_naive":
            dataclasses.replace(
                manifest, interval_end=manifest.interval_end.replace(tzinfo=None)
            )
        elif case == "interval_end_non_utc":
            dataclasses.replace(
                manifest, interval_end=manifest.interval_end.astimezone(non_utc)
            )
        elif case == "reconciliation_deadline_naive":
            dataclasses.replace(
                manifest,
                reconciliation_deadline=manifest.reconciliation_deadline.replace(
                    tzinfo=None
                ),
            )
        elif case == "reconciliation_deadline_non_utc":
            dataclasses.replace(
                manifest,
                reconciliation_deadline=manifest.reconciliation_deadline.astimezone(
                    non_utc
                ),
            )
        elif case == "retention_deadline_naive":
            dataclasses.replace(
                manifest,
                retention_deadline=manifest.retention_deadline.replace(tzinfo=None),
            )
        elif case == "retention_deadline_non_utc":
            dataclasses.replace(
                manifest,
                retention_deadline=manifest.retention_deadline.astimezone(non_utc),
            )
        elif case == "start_not_before_end":
            dataclasses.replace(manifest, interval_end=manifest.interval_start)
        elif case == "end_after_reconciliation":
            dataclasses.replace(
                manifest,
                interval_end=manifest.reconciliation_deadline + timedelta(seconds=1),
            )
        elif case == "reconciliation_after_retention":
            dataclasses.replace(
                manifest,
                reconciliation_deadline=manifest.retention_deadline
                + timedelta(seconds=1),
            )
        elif case == "study_digest_mismatch":
            dataclasses.replace(manifest, task_case_contract_digest="b" * 64)
        elif case == "root_run_mismatch":
            other_run = UUID("87654321-4321-8765-4321-876543218765")
            root = capture.PartitionRef("root", other_run, "host-1", "host")
            dataclasses.replace(manifest, root_partition=root)
        elif case == "root_has_parent":
            root = dataclasses.replace(
                manifest.root_partition, parent_partition_id="parent"
            )
            dataclasses.replace(manifest, root_partition=root)
        elif case == "duplicate_provider_namespace":
            other = capture.UsageObservationSemantics(
                "anthropic", "v2", capture.UsageObservationMode.DELTA, "sum-v2"
            )
            dataclasses.replace(
                manifest,
                usage_observation_semantics=(
                    manifest.usage_observation_semantics[0],
                    other,
                ),
            )
