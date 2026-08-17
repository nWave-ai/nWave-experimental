"""Unit test: RegistryService — register persists, raises on duplicate id;
load returns immutable snapshot.

Driving port: RegistryService application service. Uses a real
YamlRegistryAdapter against tmp_path (Strategy C — adapter is local I/O,
real adapter cheaper than fake here per nw-tdd-methodology Mandate 6).
"""

from __future__ import annotations

from pathlib import Path  # used in fixture bodies via tmp_path

import pytest
from nwave_ai.outcomes.adapters.yaml_registry import YamlRegistryAdapter
from nwave_ai.outcomes.application.registry_service import (
    DuplicateOutcomeIdError,
    RegistryService,
)
from nwave_ai.outcomes.domain.outcome import InputShape, Outcome, OutputShape


def _make_outcome(id_: str = "OUT-A") -> Outcome:
    return Outcome(
        id=id_,
        kind="specification",
        summary="Test outcome",
        feature="outcomes-registry",
        inputs=(InputShape(shape="FeatureDeltaModel"),),
        output=OutputShape(shape="tuple[Violation, ...]"),
        keywords=("k1", "k2"),
        artifact="path/to/artifact.py",
        related=(),
        superseded_by=None,
    )


def _make_service(tmp_path: Path) -> RegistryService:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text('schema_version: "0.1"\noutcomes: []\n', encoding="utf-8")
    adapter = YamlRegistryAdapter(registry_path)
    return RegistryService(reader=adapter, writer=adapter)


def test_register_persists_outcome_and_load_returns_immutable_snapshot(
    tmp_path: Path,
) -> None:
    service = _make_service(tmp_path)
    outcome = _make_outcome("OUT-A")

    service.register(outcome)
    snapshot = service.load()

    # Immutable snapshot — collection is a tuple.
    assert isinstance(snapshot, tuple)
    ids = tuple(o.id for o in snapshot)
    assert ids == ("OUT-A",)


def test_register_raises_on_duplicate_id(tmp_path: Path) -> None:
    service = _make_service(tmp_path)
    service.register(_make_outcome("OUT-A"))

    with pytest.raises(DuplicateOutcomeIdError):
        service.register(_make_outcome("OUT-A"))


def test_register_rejects_entry_failing_json_schema(tmp_path: Path) -> None:
    """Registry MUST validate entries against the JSON Schema before persistence.

    A malformed id (lowercase, not matching ^OUT-[A-Z0-9-]+$) must be rejected
    fail-fast — never persisted to disk.
    """
    from nwave_ai.outcomes.application.registry_service import (
        InvalidOutcomeError,
    )

    service = _make_service(tmp_path)
    bad = Outcome(
        id="out-1",  # lowercase — fails pattern ^OUT-[A-Z0-9-]+$
        kind="specification",
        summary="bad id",
        feature="outcomes-registry",
        inputs=(InputShape(shape="X"),),
        output=OutputShape(shape="Y"),
        keywords=("k1",),
        artifact="path.py",
        related=(),
        superseded_by=None,
    )

    with pytest.raises(InvalidOutcomeError):
        service.register(bad)

    # Invalid entry must NOT be persisted.
    snapshot = service.load()
    assert snapshot == ()
