"""Fault-observation behavior -- ``resolve()``'s per-query trace (ADR-LA-001 D5).

Proves, for both floor tiers, that ``resolve()`` reports the EXACT fault
count and a deterministic, capped-ordered exemplar tuple observed during the
one traversal that also computes the payload -- and that the payload itself
is identical to the legacy :meth:`query` envelope (the GREEN_TO_GREEN thin
edge convention). A cached fault must still be counted on a later query
WITHOUT a second read/parse; this is proven behaviorally (an observable
sentinel -- repairing the faulting file on disk after the first call -- would
leak into the payload/exemplars if a second read/parse ever happened), never
by asserting a private call count.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.driven.codefact.ast_code_fact_adapter import AstAdapter
from des.adapters.driven.codefact.text_search_code_fact_adapter import (
    TextSearchAdapter,
)
from des.ports.code_fact_port import (
    CAPABILITY_ATOMS_IN_FILE,
    TRACE_EXEMPLARS_MAX,
    Answered,
    CapabilityDescriptor,
)


_INVALID_PYTHON_SYNTAX = "this is not valid python syntax $$$\n"
_INVALID_UTF8_BYTES = b"\xff\xfe\xfa not valid utf-8"


def _descriptor(capability_id: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=capability_id,
        stability="stable",
        contract_version="1.0.0",
        io_schema="code-fact.v1",
        providing_adapter="negotiated",
    )


def test_ast_resolve_reports_exact_fault_count_and_capped_exemplars_matching_query_payload(
    tmp_path: Path,
) -> None:
    fault_count = TRACE_EXEMPLARS_MAX + 2
    fault_paths = []
    for index in range(fault_count):
        source_file = tmp_path / f"fault_{index}.py"
        source_file.write_text(_INVALID_PYTHON_SYNTAX, encoding="utf-8")
        fault_paths.append(str(source_file))
    (tmp_path / "valid_module.py").write_text(
        "def gamma():\n    return 1\n", encoding="utf-8"
    )
    descriptor = _descriptor(CAPABILITY_ATOMS_IN_FILE)
    adapter = AstAdapter(root=tmp_path)

    outcome = adapter.resolve(descriptor, {})
    legacy_payload = adapter.query(descriptor, {})

    assert isinstance(outcome, Answered)
    trace_entry = outcome.trace[0]
    assert trace_entry.fault_count == fault_count
    assert len(trace_entry.exemplars) == TRACE_EXEMPLARS_MAX
    assert trace_entry.exemplars == tuple(fault_paths[:TRACE_EXEMPLARS_MAX])
    assert outcome.payload == legacy_payload
    assert outcome.payload.payload == {"atoms": ["gamma"], "unparseable": False}


def test_text_search_resolve_reports_exact_fault_count_and_capped_exemplars_matching_query_payload(
    tmp_path: Path,
) -> None:
    fault_count = TRACE_EXEMPLARS_MAX + 2
    fault_paths = []
    for index in range(fault_count):
        source_file = tmp_path / f"fault_{index}.bin"
        source_file.write_bytes(_INVALID_UTF8_BYTES)
        fault_paths.append(str(source_file))
    (tmp_path / "valid_module.py").write_text(
        "def gamma():\n    return 1\n", encoding="utf-8"
    )
    descriptor = _descriptor(CAPABILITY_ATOMS_IN_FILE)
    adapter = TextSearchAdapter(root=tmp_path)

    outcome = adapter.resolve(descriptor, {})
    legacy_payload = adapter.query(descriptor, {})

    assert isinstance(outcome, Answered)
    trace_entry = outcome.trace[0]
    assert trace_entry.fault_count == fault_count
    assert len(trace_entry.exemplars) == TRACE_EXEMPLARS_MAX
    assert trace_entry.exemplars == tuple(fault_paths[:TRACE_EXEMPLARS_MAX])
    assert outcome.payload == legacy_payload
    assert outcome.payload.payload == {"atoms": ["gamma"]}


def test_ast_cached_parse_fault_is_counted_once_without_a_second_parse(
    tmp_path: Path,
) -> None:
    """A file that faulted on the traversal that first parsed it must still
    report that fault on a later query WITHOUT a second read/parse. Proven
    behaviorally: the file is repaired (rewritten to valid Python defining a
    NEW atom) on disk after the first call -- if a second parse ever
    happened, the new atom would leak into the second payload and the fault
    would disappear. Neither happens."""
    broken_file = tmp_path / "broken.py"
    broken_file.write_text(_INVALID_PYTHON_SYNTAX, encoding="utf-8")
    (tmp_path / "ok.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    descriptor = _descriptor(CAPABILITY_ATOMS_IN_FILE)
    adapter = AstAdapter(root=tmp_path)

    first = adapter.resolve(descriptor, {})
    assert isinstance(first, Answered)
    assert first.trace[0].fault_count == 1
    assert first.trace[0].exemplars == (str(broken_file),)
    assert first.payload.payload == {"atoms": ["alpha"], "unparseable": False}

    broken_file.write_text("def beta():\n    return 2\n", encoding="utf-8")

    second = adapter.resolve(descriptor, {})
    assert isinstance(second, Answered)
    assert second.trace[0].fault_count == 1
    assert second.trace[0].exemplars == (str(broken_file),)
    assert second.payload.payload == {"atoms": ["alpha"], "unparseable": False}


def test_text_search_cached_read_fault_is_counted_once_without_a_second_read(
    tmp_path: Path,
) -> None:
    """The text-search analogue: a file that faulted on the traversal that
    first read it must still report that fault on a later query WITHOUT a
    second read. Proven behaviorally: the file is repaired (rewritten to
    valid UTF-8 text defining a NEW atom) on disk after the first call -- if
    a second read ever happened, the new atom would leak into the second
    payload and the fault would disappear. Neither happens."""
    broken_file = tmp_path / "broken.bin"
    broken_file.write_bytes(_INVALID_UTF8_BYTES)
    (tmp_path / "ok.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    descriptor = _descriptor(CAPABILITY_ATOMS_IN_FILE)
    adapter = TextSearchAdapter(root=tmp_path)

    first = adapter.resolve(descriptor, {})
    assert isinstance(first, Answered)
    assert first.trace[0].fault_count == 1
    assert first.trace[0].exemplars == (str(broken_file),)
    assert first.payload.payload == {"atoms": ["alpha"]}

    broken_file.write_text("def beta():\n    return 2\n", encoding="utf-8")

    second = adapter.resolve(descriptor, {})
    assert isinstance(second, Answered)
    assert second.trace[0].fault_count == 1
    assert second.trace[0].exemplars == (str(broken_file),)
    assert second.payload.payload == {"atoms": ["alpha"]}
