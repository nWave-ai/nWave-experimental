"""Falsifier: when the ``graphify`` tier does NOT answer, the answer the
port still returns THROUGH the fold (``ast``/``textsearch``) must carry
exactly one ``graphify`` trace entry naming which of the three closed
causes stopped it -- never a silent absence of any graphify trace entry
at all, and never a phantom answer where graphify pretended to look and
lied.

Driven through ``des.cli.code_fact.main(argv)`` in-process (the same
function every sibling CLI-tier oracle in this directory already drives),
so a real ``os.environ['PATH']`` change via ``monkeypatch.setenv`` is
observed by ``GraphifyAdapter``'s own ``shutil.which`` call in the SAME
process -- no subprocess boundary to lose the patched environment across.

Three independently ``tmp_path``-materialized roots, one per closed cause:

(a) no ``graphify-out`` anywhere under the root -- ``"index directory
    absent"``.
(b) a ``graphify-out`` produced by RUNNING the repo's own
    ``fixtures/graphify.py`` stand-in (the same producer
    ``test_code_fact_graphify_callers_of.py`` already uses), then made
    STALE by touching the seeded source file afterward, with ``PATH``
    stripped of that stand-in so ``shutil.which('graphify')`` resolves to
    nothing -- ``"index present-but-stale with 'graphify' executable not
    on PATH"``.
(c) a hand-written, deliberately unparseable ``graph.json``/
    ``manifest.json`` pair under ``graphify-out`` -- ``"index
    present-but-unreadable"``.

Each case asserts: exit 0, exactly one trace entry with
``provider_id == 'graphify'`` whose ``event`` is not ``'answered'`` and
whose ``detail`` equals that case's exact closed phrase, and a genuine
non-empty answer (``provider``/``confidence``/``payload`` all present and
sane) -- never hardcoding which of ``ast``/``textsearch`` must have
answered (an implementation detail of the fold this oracle does not own),
and never diffing against a second, separately-materialized control root
(each case stands on its own root and its own assertions).

Zero touches to ``src/``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from des.cli.code_fact import main


_FIXTURES_DIR = (
    Path(__file__).resolve().parents[1]
    / "adapters"
    / "driven"
    / "codefact"
    / "fixtures"
)
_GRAPHIFY_STAND_IN = _FIXTURES_DIR / "graphify.py"

assert _GRAPHIFY_STAND_IN.is_file(), (
    f"the `graphify update` stand-in was not found at {_GRAPHIFY_STAND_IN} -- "
    "this oracle produces its index by running that producer, and would "
    "otherwise fail for a path reason rather than a behavioural one."
)

_SOURCE = """\
def target():
    return 1


def helper():
    return 2
"""

_DETAIL_INDEX_ABSENT = "index directory absent"
_DETAIL_EXECUTABLE_MISSING = (
    "index present-but-stale with 'graphify' executable not on PATH"
)
_DETAIL_UNREADABLE = "index present-but-unreadable"


def _answer(root: Path, capsys: pytest.CaptureFixture[str]) -> dict:
    exit_code = main(["query.callers-of", "target", "--root", str(root)])
    stdout = capsys.readouterr().out
    assert exit_code == 0, (
        f"`des code-fact query.callers-of` over {root} exited {exit_code} "
        f"instead of answering: {stdout!r}"
    )
    return json.loads(stdout)


def _graphify_entries(payload: dict) -> list[dict]:
    return [e for e in payload["trace"] if e["provider_id"] == "graphify"]


def _assert_genuine_answer(payload: dict) -> None:
    assert payload.get("provider"), (
        f"no provider named on the answer envelope: {payload!r}"
    )
    assert payload.get("confidence"), (
        f"no confidence named on the answer envelope: {payload!r}"
    )
    assert payload.get("payload"), (
        f"the answer envelope carries no real payload: {payload!r} -- a "
        "genuine fallback answer must still carry real data, not an empty "
        "shell dressed as one."
    )


def _assert_single_non_answering_graphify_entry(
    payload: dict, *, expected_detail: str
) -> None:
    entries = _graphify_entries(payload)
    assert len(entries) == 1, (
        f"expected exactly one graphify trace entry, got {entries!r} in "
        f"{payload['trace']!r}"
    )
    entry = entries[0]
    assert entry["event"] != "answered", (
        f"graphify did not really answer this query, yet its trace entry "
        f"declares event {entry['event']!r} == 'answered': {entry!r}"
    )
    assert entry["detail"] == expected_detail, (
        f"graphify's non-answering trace entry names detail "
        f"{entry['detail']!r}, expected the closed phrase "
        f"{expected_detail!r} -- a caller reading this detail must see one "
        "of the exactly-three closed causes, not a paraphrase."
    )


class TestIndexDirectoryAbsent:
    def test_no_graphify_out_anywhere_names_index_directory_absent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "subject.py").write_text(_SOURCE, encoding="utf-8")

        payload = _answer(tmp_path, capsys)

        _assert_genuine_answer(payload)
        _assert_single_non_answering_graphify_entry(
            payload, expected_detail=_DETAIL_INDEX_ABSENT
        )


class TestExecutableMissingWhileStale:
    def test_stale_index_with_no_graphify_on_path_names_executable_missing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
    ) -> None:
        source = tmp_path / "subject.py"
        source.write_text(_SOURCE, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(_GRAPHIFY_STAND_IN), "update", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            "the `graphify update` stand-in failed to materialize an index "
            f"(exit {result.returncode}): {result.stderr or result.stdout!r} -- "
            "every assertion below would be meaningless without one."
        )
        time.sleep(0.01)
        source.write_text(
            "def target():\n    return 999\n\ndef helper():\n    return 2\n",
            encoding="utf-8",
        )
        empty_path_dir = tmp_path / "empty-path-no-graphify"
        empty_path_dir.mkdir()
        monkeypatch.setenv("PATH", str(empty_path_dir))

        payload = _answer(tmp_path, capsys)

        _assert_genuine_answer(payload)
        _assert_single_non_answering_graphify_entry(
            payload, expected_detail=_DETAIL_EXECUTABLE_MISSING
        )


class TestIndexPresentButUnreadable:
    def test_unparseable_graph_and_manifest_names_index_unreadable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "subject.py").write_text(_SOURCE, encoding="utf-8")
        out_dir = tmp_path / "graphify-out"
        out_dir.mkdir()
        (out_dir / "graph.json").write_text("{not valid json", encoding="utf-8")
        (out_dir / "manifest.json").write_text("{not valid json", encoding="utf-8")

        payload = _answer(tmp_path, capsys)

        _assert_genuine_answer(payload)
        _assert_single_non_answering_graphify_entry(
            payload, expected_detail=_DETAIL_UNREADABLE
        )
