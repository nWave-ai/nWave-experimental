"""Falsifier: a stale graphify graph must trigger regeneration, not a silent
degrade to a lower-precision provider (P-SSOT-4 follow-up, measured
2026-08-24 against this box's real, shared ``graphify-out``).

Real, measured RED today (no fixture needed to observe it -- reproduced by
running ``uv run des code-fact query.callers-of diff_registry_names --root
.`` against the canonical repo tree while its graph was ~2 hours / 5+
commits stale): the port answered ``provider: ast``, ``confidence:
approx`` -- not ``graphify``/``binding-resolved``. A worse case measured in
this same session: ``query.atoms-in-file`` on a file newer than the graph
fell all the way to ``provider: textsearch``, ``confidence: noisy``,
returning 11,187 atoms from across the WHOLE repository, not the one file
asked about.

**This file's own existence is evidence of a second, sharper defect**: the
CURRENT contract for this fall-through is not merely unenforced -- it is
POSITIVELY CODIFIED as correct by an existing, currently-GREEN test:
``test_graphify_code_fact_adapter.py::TestPresentAndStale::
test_chain_falls_through_past_graphify_when_its_data_is_stale`` asserts
``resolution.provider_id == "textsearch"`` / ``confidence == "noisy"`` for
exactly this stale-graph condition, with a docstring explaining the
fall-through as intended behavior. Implementing the remedy this file
falsifies for will make THAT test's assertions wrong; reconciling it is the
crafter's job, not this oracle's -- named here so it is not missed.

**Architecture note for whoever implements this**: ``GraphifyAdapter``
today "never invokes the graphify tool itself ... zero runtime dependency
on graphify" (ADR-LA-001 D4/D10, this module's own docstring) --
CLAUDE.md's Portability section is the general form of this rule: "Where
tool data is genuinely needed it sits behind an optional driven-port
adapter that degrades LOUD (INDETERMINATE, never silent-pass) when the
tool is absent." A regenerate-on-stale remedy does not violate D4/D10 as
long as the regeneration attempt itself follows that SAME standing rule --
which is exactly this oracle's second property (see
``TestRegenerationImpossibleDegradesLoud`` below).

**Decision (Ale, 2026-08-24, relayed via team-lead): regeneration is
SYNCHRONOUS.** The choice is no longer open. On a stale graph the adapter
must regenerate and WAIT before answering -- a caller may block for tens of
seconds (this repo's own measured order of magnitude: an incremental
regen after ~15 commits took ~80s for AST extraction over 1,031 files;
declared here as the scale of wait a reader must accept, not a ceiling this
oracle enforces -- this fixture's single-file tree answers near-instantly
once a real remedy exists, so no timeout/sleep budget here depends on that
number). The first property below therefore asserts on the FIRST and ONLY
call, not a poll loop: a synchronous remedy either answers correctly on
that one call or it has not implemented the decided behavior.

A second file, ``test_graphify_concurrent_synchronous_regeneration_is_safe.py``,
covers the concurrency property the synchronous decision makes real
(multiple lanes on this box query the port at once) -- split out because it
exercises a materially different mechanism (real OS subprocesses, not this
file's single-process fixtures) and asserts a different, narrower claim.

Zero touches to ``src/des/adapters/driven/codefact/`` or any other
production path. This oracle is expected to stay RED until a crafter wires
the remedy.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.ports.code_fact_port import (
    CAPABILITY_ATOMS_IN_FILE,
    Answered,
    CapabilityDescriptor,
)


def _descriptor() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=CAPABILITY_ATOMS_IN_FILE,
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
    """Same fixture shape as ``test_graphify_code_fact_adapter.py``'s own
    ``_write_graphify_out`` -- kept as a local, independent copy rather than
    a cross-test import (test-local fixtures, not a shared production
    dependency)."""
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


def _make_stale_fixture(tmp_path: Path) -> Path:
    """A graphify-out whose recorded mtime for ``subject.py`` no longer
    matches the file's real, current mtime -- a REAL staleness condition
    (an actual mtime change, matching the sibling adapter test's own
    discipline), never a fabricated manifest mismatch."""
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
    return tmp_path


class TestSanityCheckThePredicateCanBothPassAndFail:
    """Per the mandate: verify this oracle's own logic against a state
    where the property ALREADY holds today, before trusting its red
    verdict on the stale case below -- the same discipline applied to the
    catalog-parity falsifier in this same follow-up
    (docs/analysis/2026-08-24-parita-proiezioni-verbi-des.md)."""

    def test_control_a_fresh_graph_already_answers_through_graphify_today(
        self, tmp_path: Path
    ) -> None:
        source = _seed_source(tmp_path)
        recorded_mtime = source.stat().st_mtime
        _write_graphify_out(
            tmp_path, source_relative="subject.py", recorded_mtime=recorded_mtime
        )
        chain = CodeFactChain(root=tmp_path)

        resolution = chain.resolve(_descriptor(), {"symbol": ""})

        assert isinstance(resolution, Answered)
        assert resolution.provider_id == "graphify", (
            "sanity check failed: a FRESH graph does not answer through "
            "graphify today either -- this oracle's predicate would be "
            "meaningless (always red regardless of the property), fix the "
            "fixture before trusting the stale-case assertions below"
        )
        assert resolution.confidence == "binding-resolved"


class TestStaleGraphMustRegenerateNotDegrade:
    def test_stale_graph_synchronously_regenerates_and_answers_through_graphify(
        self, tmp_path: Path
    ) -> None:
        """The happy path of the decided (synchronous) behavior: ONE call,
        no polling. RED today, by construction: nothing in the current
        adapter chain ever attempts regeneration, so this single call
        answers through whichever degraded provider the fold reaches
        (``ast``/``approx`` or ``textsearch``/``noisy``, both measured live
        on this box's real tree -- see module docstring), never
        ``graphify``."""
        root = _make_stale_fixture(tmp_path)

        chain = CodeFactChain(root=root)
        resolution = chain.resolve(_descriptor(), {"symbol": ""})

        got_provider = (
            resolution.provider_id if isinstance(resolution, Answered) else "none"
        )
        assert (
            isinstance(resolution, Answered)
            and resolution.provider_id == "graphify"
            and resolution.confidence == "binding-resolved"
        ), (
            f"a single synchronous call on a stale graph must regenerate "
            f"and answer through graphify -- got provider {got_provider!r} "
            "instead. WHY: a caller (an orchestrator, a gate) reads this "
            "as current fact when it is stale structural data or worse, "
            "an unscoped text match. HOW: the remedy is a real, running "
            "fix -- see docs/product/architecture/ADR-GCC-001-generated-"
            "command-catalog-index.md's sibling problem class and this "
            "repo's Portability rule (CLAUDE.md) for the degrade-LOUD-"
            "when-impossible shape the class below requires."
        )
        complete_trace = [
            e
            for e in resolution.trace
            if e.provider_id == "graphify" and e.scope == "complete"
        ]
        assert complete_trace, (
            "answered through graphify but its own trace entry does not "
            f"declare scope=='complete': {resolution.trace!r} -- a "
            "synchronous regen that only partially rebuilt the graph "
            "before answering is not the decided behavior either."
        )


class TestRegenerationImpossibleDegradesLoud:
    def test_graphify_absent_on_stale_graph_never_silently_answers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The third state -- with synchronous regeneration decided, this
        is MORE important than before, not less: a long, blocking wait
        that ends in a wrong answer is the worse of both worlds. Simulated
        by making the ``graphify`` executable itself unreachable -- a
        real, controlled precondition, not a mocked internal call whose
        name this role does not get to invent -- the port must degrade
        LOUD (``Failed``/an explicit indeterminate outcome), never
        silently ``Answered`` through a degraded provider dressed as
        current fact.

        RED today, unconditionally, regardless of whether a real
        ``graphify`` binary happens to be on this box's PATH: today's code
        never attempts regeneration at all, so it always answers
        ``Answered`` (degraded), never ``Failed`` for this reason -- the
        exact silent-``never_wired`` risk this test names explicitly.
        """
        monkeypatch.setenv("PATH", str(tmp_path / "empty-path-no-graphify"))
        (tmp_path / "empty-path-no-graphify").mkdir()
        root = _make_stale_fixture(tmp_path)

        chain = CodeFactChain(root=root)
        resolution = chain.resolve(_descriptor(), {"symbol": ""})

        assert not isinstance(resolution, Answered), (
            f"graphify is unreachable (PATH has no graphify) and the graph "
            f"is stale, yet the port still answered: {resolution!r}. WHY: "
            "an unreachable regeneration must degrade LOUD -- Failed or an "
            "explicit indeterminate outcome -- never a silent Answered "
            "built on a provider that could not honestly cover the query. "
            "HOW: the port's regeneration attempt must itself follow "
            "CLAUDE.md's Portability rule (\"degrades LOUD (INDETERMINATE, "
            'never silent-pass) when the tool is absent"), the same '
            "discipline every other optional-tool adapter in this repo "
            "already follows."
        )
