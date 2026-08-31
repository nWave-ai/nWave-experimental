"""Falsifier: concurrent synchronous regeneration must not corrupt the
shared graph and must not duplicate the regeneration work.

Split out from ``test_graphify_stale_graph_should_regenerate_not_degrade.py``
(see that file's module docstring) because the synchronous-regeneration
decision (Ale, 2026-08-24) makes this a REAL, everyday condition: five
lanes on this shared box can query ``des code-fact`` against the SAME
canonical ``graphify-out`` at the same moment, each in its OWN OS process
(``des`` is a fresh CLI invocation per call -- there is no shared
in-process state across lanes to synchronize with a plain Python lock).
This file therefore drives REAL, separate subprocesses against the same
fixture root, not threads in one process -- a Python-level lock would prove
nothing about cross-process safety, which is the actual shape of the risk.

Team-lead's framing, carried verbatim: "Non prescrivo il meccanismo -- lock,
attesa sul lavoro in corso, o altro: e' scelta di chi implementa. L'oracolo
deve pero' esprimere la proprieta', cosi' che un'implementazione che la
viola risulti rossa." Two properties, at two different strengths:

1. **Correctness under concurrency** (robust, no timing assumption): every
   one of N concurrent callers against the same stale graph must receive
   the SAME correct answer (``graphify``/``binding-resolved``/``complete``)
   -- never a torn read of a graph another process is mid-write on, never a
   wrong/degraded answer for one caller because another got there first.
2. **No duplicated regeneration work** (best-effort HEURISTIC, stated
   honestly as such): ``graph.json``'s mtime is sampled by a background
   watcher thread in THIS test process while the N subprocesses run. A
   coalescing implementation (lock / wait-on-in-progress / etc.) should
   produce at most a small, N-INDEPENDENT number of distinct write
   timestamps; an implementation where every process independently
   regenerates would tend toward N. This is a proxy, not a proof --
   sub-sampling-interval writes can be missed entirely, which is the safe
   failure direction (a real defect might slip past this specific
   assertion; it will not manufacture a false one). Property 1 above does
   not depend on this proxy at all.

Zero touches to ``src/des/adapters/driven/codefact/`` or any other
production path. Expected to stay RED until a crafter wires the remedy --
today nothing regenerates at all, so property 1 fails outright and
property 2's corruption/validity checks pass VACUOUSLY (nothing ever
writes to graph.json today, so there is nothing to corrupt yet); that
distinction is called out at each assertion site below, not glossed over.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


_FAKE_GRAPHIFY_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _deterministic_graphify_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same repo-local, bounded stand-in as the sibling stale-graph oracle
    (see that file's fixture docstring for the POSIX/Windows resolution
    split): makes the ``graphify`` executable this file's subprocess
    workers shell out to available deterministically in every environment,
    without a real graphify install as a CI dependency. ``monkeypatch.
    setenv`` mutates ``os.environ`` in place, so the worker subprocesses
    below (spawned with no explicit ``env=``, hence inheriting it) see the
    same ``PATH``/``PATHEXT``."""
    if sys.platform == "win32":
        pathext = os.environ.get("PATHEXT", "")
        monkeypatch.setenv("PATHEXT", f".PY;{pathext}")
    else:
        fake = _FAKE_GRAPHIFY_DIR / "graphify"
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv(
        "PATH", f"{_FAKE_GRAPHIFY_DIR}{os.pathsep}{os.environ.get('PATH', '')}"
    )


_CONCURRENT_CALLERS = 5
_WATCHER_POLL_SECONDS = 0.002

_WORKER_SCRIPT = """
import json, sys
from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.ports.code_fact_port import CAPABILITY_ATOMS_IN_FILE, Answered, CapabilityDescriptor

descriptor = CapabilityDescriptor(
    id=CAPABILITY_ATOMS_IN_FILE,
    stability="stable",
    contract_version="1.0.0",
    io_schema="code-fact.v1",
    providing_adapter="negotiated",
)
chain = CodeFactChain(root=sys.argv[1])
resolution = chain.resolve(descriptor, {"symbol": ""})
if isinstance(resolution, Answered):
    complete = any(
        e.provider_id == "graphify" and e.scope == "complete"
        for e in resolution.trace
    )
    print(json.dumps({
        "provider_id": resolution.provider_id,
        "confidence": resolution.confidence,
        "graphify_complete": complete,
    }))
else:
    print(json.dumps({"provider_id": None, "outcome_type": type(resolution).__name__}))
"""


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


def _is_valid_json_object(path: Path) -> bool:
    """A torn/partial write from a racing concurrent regeneration would
    fail to parse, or parse to something other than an object -- this is
    the corruption check. Never raises."""
    try:
        return isinstance(json.loads(path.read_text(encoding="utf-8")), dict)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False


class TestTheCorruptionCheckItselfIsNotVacuous:
    """Sanity check on THIS file's own detection logic (per the mandate,
    the same discipline used for the catalog-parity falsifier): prove
    ``_is_valid_json_object`` can actually observe a fault before trusting
    its all-clear verdict in the concurrency test below."""

    def test_control_a_hand_corrupted_file_is_detected(self, tmp_path: Path) -> None:
        corrupted = tmp_path / "graph.json"
        corrupted.write_text('{"nodes": [truncated mid-w', encoding="utf-8")
        assert _is_valid_json_object(corrupted) is False

    def test_control_a_well_formed_file_is_accepted(self, tmp_path: Path) -> None:
        fine = tmp_path / "graph.json"
        fine.write_text(json.dumps({"nodes": []}), encoding="utf-8")
        assert _is_valid_json_object(fine) is True


class TestConcurrentSynchronousRegenerationIsSafe:
    def test_all_concurrent_callers_get_a_correct_answer_and_the_graph_is_not_corrupted(
        self, tmp_path: Path
    ) -> None:
        """Property 1 (robust) + the corruption half of property 2. RED
        today: nothing regenerates, so no process reaches a correct
        graphify answer -- every one of the N results below will show a
        degraded provider instead. The JSON-validity assertions pass
        VACUOUSLY today (no writer exists yet to corrupt anything); they
        become a REAL check only once a remedy starts writing under
        concurrent load, which is exactly why this file exists ahead of
        that remedy, not after it."""
        root = _make_stale_fixture(tmp_path)

        procs = [
            subprocess.Popen(
                [sys.executable, "-c", _WORKER_SCRIPT, str(root)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(_CONCURRENT_CALLERS)
        ]
        results = []
        for proc in procs:
            stdout, stderr = proc.communicate(timeout=120)
            assert proc.returncode == 0, (
                f"worker subprocess crashed (exit {proc.returncode}): {stderr}"
            )
            results.append(json.loads(stdout.strip().splitlines()[-1]))

        wrong = [r for r in results if r.get("provider_id") != "graphify"]
        assert not wrong, (
            f"{len(wrong)}/{_CONCURRENT_CALLERS} concurrent callers on the "
            f"SAME stale graph did not get a graphify answer: {wrong!r}. "
            "WHY: concurrent access to a stale graph must never let one "
            "caller see a degraded or torn answer while another triggers "
            "regeneration. HOW: the regeneration path must serialize or "
            "share in-flight work across processes querying the same "
            "graphify-out (a cross-process lock or an in-progress marker "
            "file, per team-lead's framing -- the mechanism is not "
            "prescribed here)."
        )
        incomplete = [r for r in results if not r.get("graphify_complete")]
        assert not incomplete, (
            f"{len(incomplete)}/{_CONCURRENT_CALLERS} concurrent callers "
            f"got provider=graphify but scope != 'complete': {incomplete!r}"
        )

        graph_path = root / "graphify-out" / "graph.json"
        manifest_path = root / "graphify-out" / "manifest.json"
        assert _is_valid_json_object(graph_path), (
            f"{graph_path} is not valid JSON after {_CONCURRENT_CALLERS} "
            "concurrent regenerations -- a torn/interleaved write from two "
            "racing regenerations corrupted the shared graph."
        )
        assert _is_valid_json_object(manifest_path), (
            f"{manifest_path} is not valid JSON after "
            f"{_CONCURRENT_CALLERS} concurrent regenerations."
        )

    def test_regeneration_work_does_not_obviously_multiply_with_concurrent_callers(
        self, tmp_path: Path
    ) -> None:
        """Property 2, the heuristic half (module docstring: a proxy, not
        a proof). Watches graph.json's mtime while N callers race; asserts
        the observed distinct-write count stays small and does not scale
        with N. GREEN today, but VACUOUSLY and for an uninteresting reason
        -- verified by running it: nothing ever writes to graph.json today
        (no regeneration attempt exists at all), so 1 distinct mtime is
        observed regardless of N, satisfying the assertion without this
        property having been exercised at all. Recorded here explicitly so
        a future reader does not mistake THIS test's pass for the fix
        being correct -- property 1 above is the one that actually
        discriminates today (and stays the authoritative one always: this
        heuristic can be satisfied by an implementation that never
        regenerates at all, exactly as it is right now)."""
        root = _make_stale_fixture(tmp_path)
        graph_path = root / "graphify-out" / "graph.json"

        observed_mtimes: set[float] = {graph_path.stat().st_mtime_ns}
        stop = threading.Event()

        def _watch() -> None:
            while not stop.is_set():
                try:
                    observed_mtimes.add(graph_path.stat().st_mtime_ns)
                except OSError:
                    pass
                time.sleep(_WATCHER_POLL_SECONDS)

        watcher = threading.Thread(target=_watch, daemon=True)
        watcher.start()
        try:
            procs = [
                subprocess.Popen(
                    [sys.executable, "-c", _WORKER_SCRIPT, str(root)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for _ in range(_CONCURRENT_CALLERS)
            ]
            for proc in procs:
                proc.communicate(timeout=120)
        finally:
            stop.set()
            watcher.join(timeout=5)

        distinct_writes = len(observed_mtimes)
        assert distinct_writes < _CONCURRENT_CALLERS, (
            f"observed {distinct_writes} distinct graph.json mtimes across "
            f"{_CONCURRENT_CALLERS} concurrent callers -- consistent with "
            "each process independently regenerating instead of "
            "coalescing. WHY: duplicated regeneration wastes exactly the "
            "~80s-scale work (this repo's own measured order of magnitude "
            "for an incremental regen) once for every concurrent caller "
            "instead of once total. HOW: share or serialize in-flight "
            "regeneration across processes querying the same graphify-out "
            "(mechanism not prescribed)."
        )
