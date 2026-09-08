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

**2026-09-06 realignment**: ``TestRegenerationImpossibleDegradesLoud``
below no longer asserts a hard ``Failed`` for the executable-absent
sub-cause -- a later value (see
``tests/des/unit/cli/test_code_fact_graphify_non_answer_trace.py``) closed
that sub-cause differently: a bounded, honest ``graphify`` trace entry
naming the exact cause, with the fold still falling through to a real
answer from a lower tier, rather than a hard stop. The other two
sub-causes this same later value also names (index directory absent,
index present-but-unreadable) never reach a stale-graph regeneration
attempt at all, so they are out of this file's scope entirely.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from pathlib import Path

import pytest

from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.ports.code_fact_port import (
    CAPABILITY_ATOMS_IN_FILE,
    Answered,
    CapabilityDescriptor,
)


_FAKE_GRAPHIFY_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _deterministic_graphify_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """CI has no real ``graphify`` install (CLAUDE.md Portability rule keeps
    it optional); ``fixtures/graphify`` (POSIX) / ``fixtures/graphify.py``
    (Windows) is a repo-local, bounded stand-in implementing exactly the one
    subcommand the adapter shells out to (``update <root>``), so the
    synchronous-regeneration property this file falsifies is exercised
    deterministically in every environment instead of only on a box that
    happens to have the real binary installed. The
    ``test_graphify_absent_on_stale_graph_never_silently_answers`` test
    below still fully overrides ``PATH`` itself, which wins regardless.

    On POSIX ``shutil.which``/``execve`` resolve the extensionless,
    ``chmod +x``'d ``graphify`` shebang script directly. Windows has no
    kernel-level shebang mechanism and ``shutil.which`` there only matches
    ``PATHEXT`` extensions, so ``.PY`` is prepended to it -- that makes
    ``shutil.which("graphify")`` resolve ``graphify.py`` instead, exactly
    the pure-Python cross-platform pair ``GraphifyAdapter``'s own spawn
    construction (``executable.lower().endswith(".py")``) exists to launch
    via ``sys.executable``. No shell/batch/PowerShell shim -- forbidden by
    this repo's Portability rule."""
    if sys.platform == "win32":
        pathext = os.environ.get("PATHEXT", "")
        monkeypatch.setenv("PATHEXT", f".PY;{pathext}")
    else:
        fake = _FAKE_GRAPHIFY_DIR / "graphify"
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv(
        "PATH", f"{_FAKE_GRAPHIFY_DIR}{os.pathsep}{os.environ.get('PATH', '')}"
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


class TestPyExecutableIsLaunchedViaSysExecutable:
    """Cross-platform spawn-construction check (``graphify_code_fact_
    adapter.py:_run_graphify_update``: ``executable.lower().endswith(
    ".py")`` prepends ``sys.executable``). This suite's own POSIX/Windows
    fixture split above exercises the real shape end to end but only takes
    the ``.py`` branch on an actual Windows box; this test forces that
    resolution shape directly so the construction is asserted on whatever
    platform the suite actually runs on."""

    def test_a_resolved_py_executable_is_prepended_with_sys_executable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import subprocess

        from des.adapters.driven.codefact import graphify_code_fact_adapter as module

        root = _make_stale_fixture(tmp_path)
        fake_py = _FAKE_GRAPHIFY_DIR / "graphify.py"
        captured: dict[str, list[str]] = {}

        def _capture_spawn(argv, **kwargs):
            captured["argv"] = list(argv)
            return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

        monkeypatch.setattr(module.shutil, "which", lambda name: str(fake_py))
        monkeypatch.setattr(module, "spawn", _capture_spawn)

        chain = CodeFactChain(root=root)
        chain.resolve(_descriptor(), {"symbol": ""})

        assert captured.get("argv") == [
            sys.executable,
            str(fake_py),
            "update",
            str(root),
        ], (
            "a resolved '.py' graphify executable must be launched as "
            "[sys.executable, executable, 'update', root], got "
            f"{captured.get('argv')!r} instead -- otherwise the OS loader "
            "cannot run a bare '.py' file directly on either platform."
        )


class TestRegenerationImpossibleDegradesLoud:
    def test_graphify_absent_on_stale_graph_never_silently_answers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The third state, REALIGNED (this value, superseding the prior
        "must be Failed" claim this docstring itself used to defend):
        an unreachable regeneration must still surface a bounded, honest
        ``graphify`` trace entry naming the exact closed cause ("index
        present-but-stale with 'graphify' executable not on PATH") -- but
        the query itself is NOT hard-stopped over it. The fold falls
        through to whichever of ``AstAdapter``/``TextSearchAdapter`` alone
        would have answered this same request, and THAT answer -- with
        graphify's one non-answering entry prepended to its trace -- is
        what the port returns. Never a silent absence of any graphify
        trace entry, and never a phantom ``graphify``-attributed answer;
        but also never a hard ``Failed`` for this one sub-cause, since a
        real, honest, degraded-tier answer is strictly more useful to a
        caller than none at all, exactly as before this remedy existed --
        the difference this value adds is CALLING OUT the exact reason a
        precise answer WASN'T reached instead of the silence the module
        docstring above still, more broadly, argues against.
        """
        monkeypatch.setenv("PATH", str(tmp_path / "empty-path-no-graphify"))
        (tmp_path / "empty-path-no-graphify").mkdir()
        root = _make_stale_fixture(tmp_path)

        expected = CodeFactChain(root=root)._ast.resolve(_descriptor(), {"symbol": ""})
        if not isinstance(expected, Answered):
            expected = None  # AstAdapter itself declining is not this test's concern

        chain = CodeFactChain(root=root)
        resolution = chain.resolve(_descriptor(), {"symbol": ""})

        assert isinstance(resolution, Answered), (
            f"graphify is unreachable (PATH has no graphify) and the graph "
            f"is stale, yet the port did not answer at all: {resolution!r}. "
            "WHY: an unreachable regeneration must still let the fold fall "
            "through to whichever lower tier alone would have answered -- "
            "never a hard stop for THIS sub-cause."
        )
        graphify_entries = [e for e in resolution.trace if e.provider_id == "graphify"]
        assert len(graphify_entries) == 1, (
            f"expected exactly one graphify trace entry, got "
            f"{graphify_entries!r} in {resolution.trace!r}"
        )
        entry = graphify_entries[0]
        assert entry.event != "answered", (
            f"graphify did not really answer, yet its trace entry declares "
            f"event {entry.event!r} == 'answered': {entry!r}"
        )
        assert entry.detail == (
            "index present-but-stale with 'graphify' executable not on PATH"
        ), (
            f"expected the closed executable-missing phrase, got "
            f"{entry.detail!r} instead: {entry!r}"
        )
        if expected is not None:
            assert (resolution.provider_id, resolution.confidence) == (
                expected.provider_id,
                expected.confidence,
            ), (
                "the fallback answer must match whatever (self._ast, "
                f"self._floor) alone would produce: got "
                f"{(resolution.provider_id, resolution.confidence)!r}, "
                f"expected {(expected.provider_id, expected.confidence)!r}."
            )
