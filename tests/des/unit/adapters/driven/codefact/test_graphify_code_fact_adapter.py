"""``GraphifyAdapter`` — the optional precise CodeFact tier (ADR-LA-001 D4/LA1-L7).

Covers the three residual-stress cells this new provider realizes:
absent ⇒ not in the chain's provider tuple at all (never a phantom tier);
present + fresh (the manifest's recorded mtime for the touched file matches
its current mtime) ⇒ a real ``binding-resolved`` answer, never inflated
past the manifest's own declared confidence (LA1-L6); present + stale (the
file was modified since the graph was materialized) ⇒ the witness check
fails the query with the closed D3 cause ``provider-error``, and the chain
falls through to the next covering provider (``AstAdapter``, ``approx``) —
never a stale structural claim served as current fact.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from des.adapters.driven.codefact.ast_code_fact_adapter import AstAdapter
from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.adapters.driven.codefact.graphify_code_fact_adapter import GraphifyAdapter
from des.ports.code_fact_port import (
    CAPABILITY_ATOMS_IN_FILE,
    CAPABILITY_CALLERS_OF,
    CAPABILITY_NEVER_WIRED,
    Answered,
    CapabilityDescriptor,
    Failed,
)


def _descriptor(capability_id: str) -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=capability_id,
        stability="stable",
        contract_version="1.0.0",
        io_schema="code-fact.v1",
        providing_adapter="negotiated",
    )


def _seed_source(tmp_path: Path) -> Path:
    source = tmp_path / "subject.py"
    source.write_text(
        "def target():\n    return 1\n\ndef helper():\n    return 2\n",
        encoding="utf-8",
    )
    return source


def _write_graphify_out(
    tmp_path: Path, *, source_relative: str, recorded_mtime: float
) -> None:
    out_dir = tmp_path / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "subject_target",
                        "label": "target",
                        "source_file": source_relative,
                        "source_location": "L1",
                        "file_type": "code",
                    },
                    {
                        "id": "subject_helper",
                        "label": "helper",
                        "source_file": source_relative,
                        "source_location": "L4",
                        "file_type": "code",
                    },
                    {
                        "id": "external_thing",
                        "label": "external",
                        "source_file": "",
                        "source_location": "",
                        "file_type": "code",
                    },
                ],
                "edges": [],
                "hyperedges": [],
                "input_tokens": 0,
                "output_tokens": 0,
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                source_relative: {
                    "ast_hash": "deadbeef",
                    "mtime": recorded_mtime,
                    "semantic_hash": "deadbeef",
                }
            }
        ),
        encoding="utf-8",
    )


class TestAbsentGraphifyOut:
    def test_has_data_is_false_with_no_graphify_out_directory(
        self, tmp_path: Path
    ) -> None:
        _seed_source(tmp_path)
        adapter = GraphifyAdapter(root=tmp_path)
        assert adapter.has_data is False

    def test_manifest_is_empty_when_absent(self, tmp_path: Path) -> None:
        _seed_source(tmp_path)
        adapter = GraphifyAdapter(root=tmp_path)
        assert adapter.manifest() == ()

    def test_chain_excludes_it_and_resolves_identically_to_today(
        self, tmp_path: Path
    ) -> None:
        """Regression: with no graphify-out present, the chain must
        behave EXACTLY as it did before this adapter existed --
        AstAdapter answers callers-of at `approx`."""
        _seed_source(tmp_path)
        chain = CodeFactChain(root=tmp_path)

        assert "graphify" not in [p.provider_id for p in chain._providers]

        resolution = chain.resolve(
            _descriptor(CAPABILITY_CALLERS_OF), {"symbol": "target"}
        )
        assert isinstance(resolution, Answered)
        assert resolution.provider_id == "ast"
        assert resolution.confidence == "approx"


class TestPresentAndFresh:
    def test_resolve_answers_binding_resolved_for_atoms_in_file(
        self, tmp_path: Path
    ) -> None:
        source = _seed_source(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out(
            tmp_path, source_relative="subject.py", recorded_mtime=recorded_mtime
        )
        adapter = GraphifyAdapter(root=tmp_path)
        assert adapter.has_data is True

        outcome = adapter.resolve(_descriptor(CAPABILITY_ATOMS_IN_FILE), {"symbol": ""})

        assert isinstance(outcome, Answered)
        assert outcome.confidence == "binding-resolved"
        assert outcome.payload.payload["atoms"] == ["helper", "target"]

    def test_chain_wires_graphify_first_and_answers_through_it(
        self, tmp_path: Path
    ) -> None:
        source = _seed_source(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out(
            tmp_path, source_relative="subject.py", recorded_mtime=recorded_mtime
        )
        chain = CodeFactChain(root=tmp_path)

        assert chain._providers[0].provider_id == "graphify"

        resolution = chain.resolve(
            _descriptor(CAPABILITY_ATOMS_IN_FILE), {"symbol": ""}
        )
        assert isinstance(resolution, Answered)
        assert resolution.provider_id == "graphify"
        assert resolution.confidence == "binding-resolved"

    def test_confidence_never_inflates_past_manifest_declared_value(
        self, tmp_path: Path
    ) -> None:
        """LA1-L6: the fold must report EXACTLY the manifest-declared
        confidence, never higher."""
        source = _seed_source(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out(
            tmp_path, source_relative="subject.py", recorded_mtime=recorded_mtime
        )
        adapter = GraphifyAdapter(root=tmp_path)
        manifest_entry = adapter.manifest()[0]

        outcome = adapter.resolve(_descriptor(CAPABILITY_ATOMS_IN_FILE), {"symbol": ""})

        assert isinstance(outcome, Answered)
        assert outcome.confidence == manifest_entry.confidence == "binding-resolved"


class TestPresentAndStale:
    def test_resolve_fails_with_provider_error_when_file_touched_since_capture(
        self, tmp_path: Path
    ) -> None:
        source = _seed_source(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out(
            tmp_path, source_relative="subject.py", recorded_mtime=recorded_mtime
        )
        # Touch the file AFTER the graph claims to have captured it --
        # a real mtime change, not a fabricated manifest mismatch.
        time.sleep(0.01)
        source.write_text(
            "def target():\n    return 999\n\ndef helper():\n    return 2\n",
            encoding="utf-8",
        )

        adapter = GraphifyAdapter(root=tmp_path)
        outcome = adapter.resolve(_descriptor(CAPABILITY_ATOMS_IN_FILE), {"symbol": ""})

        assert isinstance(outcome, Failed)
        assert outcome.cause == "provider-error"

    def test_chain_falls_through_past_graphify_when_its_data_is_stale(
        self, tmp_path: Path
    ) -> None:
        """The fold's own D5 fall-through: a Failed graphify answer never
        blocks the chain. It falls through to ``textsearch`` (noisy), not
        ``ast``: AstAdapter's own pre-existing, unmodified scope-purity
        check (``_request_is_python_scoped``) declines a subject-free
        query -- such as ``atoms-in-file`` -- the moment the queried root
        contains ANY non-``.py`` file, and ``graphify-out/{graph,
        manifest}.json`` (this adapter's own materialized data, sitting
        under the same queried root by convention) are exactly such
        files. The stale graphify failure is still preserved in the
        trace, never silently dropped."""
        source = _seed_source(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out(
            tmp_path, source_relative="subject.py", recorded_mtime=recorded_mtime
        )
        time.sleep(0.01)
        source.write_text(
            "def target():\n    return 999\n\ndef helper():\n    return 2\n",
            encoding="utf-8",
        )

        chain = CodeFactChain(root=tmp_path)
        resolution = chain.resolve(
            _descriptor(CAPABILITY_ATOMS_IN_FILE), {"symbol": ""}
        )

        assert isinstance(resolution, Answered)
        assert resolution.provider_id == "textsearch"
        assert resolution.confidence == "noisy"
        failed_entries = [e for e in resolution.trace if e.event.startswith("failed:")]
        assert len(failed_entries) >= 1
        graphify_failure = [e for e in failed_entries if e.provider_id == "graphify"]
        assert len(graphify_failure) == 1
        assert graphify_failure[0].event == "failed:provider-error"


def _seed_source_with_caller(tmp_path: Path) -> Path:
    source = tmp_path / "subject.py"
    source.write_text(
        "def target():\n    return 1\n\n\ndef caller():\n    return target()\n",
        encoding="utf-8",
    )
    return source


def _write_graphify_out_with_calls(
    tmp_path: Path,
    *,
    source_relative: str,
    recorded_mtime: float,
    edges: list[dict[str, object]],
) -> None:
    out_dir = tmp_path / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "mod_target",
                        "label": "target",
                        "source_file": source_relative,
                        "source_location": "L1",
                        "file_type": "code",
                    },
                    {
                        "id": "mod_caller",
                        "label": "caller",
                        "source_file": source_relative,
                        "source_location": "L5",
                        "file_type": "code",
                    },
                ],
                "edges": edges,
                "hyperedges": [],
                "input_tokens": 0,
                "output_tokens": 0,
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                source_relative: {
                    "ast_hash": "deadbeef",
                    "mtime": recorded_mtime,
                    "semantic_hash": "deadbeef",
                }
            }
        ),
        encoding="utf-8",
    )


def _extracted_calls_edge(source_relative: str) -> dict[str, object]:
    return {
        "source": "mod_caller",
        "target": "mod_target",
        "relation": "calls",
        "confidence": "EXTRACTED",
        "source_file": source_relative,
        "source_location": "L6",
        "weight": 1.0,
        "context": "call",
        "_origin": "ast",
    }


class TestCallersOfAndNeverWired:
    """Slice 2: query.callers-of / query.never-wired, backed by `calls`
    edges at confidence == EXTRACTED only (module docstring: LA1-L6
    no-inflation excludes INFERRED `calls` and every `indirect_call`)."""

    def test_callers_of_answers_binding_resolved_from_extracted_calls_edge(
        self, tmp_path: Path
    ) -> None:
        source = _seed_source_with_caller(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out_with_calls(
            tmp_path,
            source_relative="subject.py",
            recorded_mtime=recorded_mtime,
            edges=[_extracted_calls_edge("subject.py")],
        )
        adapter = GraphifyAdapter(root=tmp_path)

        outcome = adapter.resolve(
            _descriptor(CAPABILITY_CALLERS_OF), {"symbol": "target"}
        )

        assert isinstance(outcome, Answered)
        assert outcome.confidence == "binding-resolved"
        assert outcome.payload.payload["sites"] == [f"{tmp_path / 'subject.py'}:6"]

    def test_never_wired_is_false_when_a_calls_edge_exists(
        self, tmp_path: Path
    ) -> None:
        source = _seed_source_with_caller(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out_with_calls(
            tmp_path,
            source_relative="subject.py",
            recorded_mtime=recorded_mtime,
            edges=[_extracted_calls_edge("subject.py")],
        )
        adapter = GraphifyAdapter(root=tmp_path)

        outcome = adapter.resolve(
            _descriptor(CAPABILITY_NEVER_WIRED), {"symbol": "target"}
        )

        assert isinstance(outcome, Answered)
        assert outcome.payload.payload["never_wired"] is False
        assert outcome.payload.payload["call_sites"] == [f"{tmp_path / 'subject.py'}:6"]

    def test_never_wired_is_true_when_no_calls_edge_exists_for_symbol(
        self, tmp_path: Path
    ) -> None:
        source = _seed_source_with_caller(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out_with_calls(
            tmp_path,
            source_relative="subject.py",
            recorded_mtime=recorded_mtime,
            edges=[],
        )
        adapter = GraphifyAdapter(root=tmp_path)

        outcome = adapter.resolve(
            _descriptor(CAPABILITY_NEVER_WIRED), {"symbol": "target"}
        )

        assert isinstance(outcome, Answered)
        assert outcome.payload.payload["never_wired"] is True
        assert outcome.payload.payload["call_sites"] == []

    def test_inferred_calls_and_indirect_call_edges_are_excluded_no_inflation(
        self, tmp_path: Path
    ) -> None:
        """LA1-L6: an INFERRED `calls` edge or an `indirect_call` edge (100%
        INFERRED in every sampled real graph) must never count as a real
        call site -- only EXTRACTED `calls` may."""
        source = _seed_source_with_caller(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out_with_calls(
            tmp_path,
            source_relative="subject.py",
            recorded_mtime=recorded_mtime,
            edges=[
                {
                    "source": "mod_caller",
                    "target": "mod_target",
                    "relation": "calls",
                    "confidence": "INFERRED",
                    "source_file": "subject.py",
                    "source_location": "L6",
                    "weight": 0.8,
                    "context": "call",
                    "_origin": "ast",
                },
                {
                    "source": "mod_caller",
                    "target": "mod_target",
                    "relation": "indirect_call",
                    "confidence": "INFERRED",
                    "source_file": "subject.py",
                    "source_location": "L6",
                    "weight": 1.0,
                    "context": "argument",
                    "_origin": "ast",
                },
            ],
        )
        adapter = GraphifyAdapter(root=tmp_path)

        outcome = adapter.resolve(
            _descriptor(CAPABILITY_NEVER_WIRED), {"symbol": "target"}
        )

        assert isinstance(outcome, Answered)
        assert outcome.payload.payload["never_wired"] is True
        assert outcome.payload.payload["call_sites"] == []

    def test_chain_wires_graphify_first_for_callers_of(self, tmp_path: Path) -> None:
        source = _seed_source_with_caller(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out_with_calls(
            tmp_path,
            source_relative="subject.py",
            recorded_mtime=recorded_mtime,
            edges=[_extracted_calls_edge("subject.py")],
        )
        chain = CodeFactChain(root=tmp_path)

        resolution = chain.resolve(
            _descriptor(CAPABILITY_CALLERS_OF), {"symbol": "target"}
        )

        assert isinstance(resolution, Answered)
        assert resolution.provider_id == "graphify"
        assert resolution.confidence == "binding-resolved"

    def test_resolve_fails_when_a_live_file_is_missing_from_the_manifest(
        self, tmp_path: Path
    ) -> None:
        """Whole-tree completeness: a NEW Python file the graph never
        scanned must never let a `never-wired` claim go through -- a real
        caller could be sitting in exactly that file."""
        source = _seed_source_with_caller(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out_with_calls(
            tmp_path,
            source_relative="subject.py",
            recorded_mtime=recorded_mtime,
            edges=[_extracted_calls_edge("subject.py")],
        )
        (tmp_path / "unscanned.py").write_text(
            "def other():\n    return 1\n", encoding="utf-8"
        )
        adapter = GraphifyAdapter(root=tmp_path)

        outcome = adapter.resolve(
            _descriptor(CAPABILITY_NEVER_WIRED), {"symbol": "target"}
        )

        assert isinstance(outcome, Failed)
        assert outcome.cause == "provider-error"


class TestMalformedGraphifyOut:
    def test_unreadable_json_is_treated_as_absent(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "graphify-out"
        out_dir.mkdir()
        (out_dir / "graph.json").write_text("not json{{{", encoding="utf-8")
        (out_dir / "manifest.json").write_text("{}", encoding="utf-8")

        adapter = GraphifyAdapter(root=tmp_path)
        assert adapter.has_data is False

    def test_provider_implements_the_same_manifest_resolve_shape_as_ast(
        self, tmp_path: Path
    ) -> None:
        """LA1-L2: fold-dispatchable through the identical uniform
        protocol -- no special-casing anywhere in the fold."""
        graphify_adapter = GraphifyAdapter(root=tmp_path)
        ast_adapter = AstAdapter(root=tmp_path)
        assert hasattr(graphify_adapter, "manifest")
        assert hasattr(graphify_adapter, "resolve")
        assert hasattr(graphify_adapter, "provider_id")
        assert callable(graphify_adapter.manifest)
        assert callable(graphify_adapter.resolve)
        assert type(graphify_adapter.manifest()) is type(ast_adapter.manifest())
