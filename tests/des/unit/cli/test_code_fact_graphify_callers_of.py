"""Falsifier: `des code-fact query.callers-of SYMBOL --root .`, over a
checkout whose graphify index was JUST produced by `graphify update`, must
answer `provider: graphify` / `confidence: binding-resolved` with the REAL
`file:line` call sites of every EXTRACTED `calls` edge targeting the symbol
-- and must answer a VERIFIED empty site set (never a defaulted one) for a
genuinely uncalled in-root symbol.

Driven through `des.cli.code_fact.main(argv)` in-process: the same function
the `des code-fact` console script reaches, so no parallel entrypoint is
introduced.

Discipline of this oracle:

* The index is produced by RUNNING the repo's `graphify update` stand-in
  (`tests/des/unit/adapters/driven/codefact/fixtures/graphify.py`, the only
  producer available -- CI installs no real graphify, per this repo's
  Portability rule) as a real subprocess over a self-materialized temporary
  root. Nothing here hand-writes a `graph.json`.
* The expected call-site LINE is derived from the seeded module SOURCE, not
  from the generated graph, so producer and expectation cannot drift into
  agreement.
* `app.py` also IMPORTS the queried symbol. An `imports` edge naming the
  same target therefore exists in the graph, which is what makes the
  consumer's `calls`-only relation filtering observable rather than merely
  asserted.
* The empty answer is only trustworthy because it is reached AFTER the
  adapter's whole-tree freshness gate -- so it is asserted together with
  `fault_count == 0` / `scope == "complete"` on graphify's own trace entry.

Zero touches to `src/`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from des.cli.code_fact import main


_GRAPHIFY_STAND_IN = (
    Path(__file__).resolve().parents[1]
    / "adapters"
    / "driven"
    / "codefact"
    / "fixtures"
    / "graphify.py"
)

assert _GRAPHIFY_STAND_IN.is_file(), (
    f"the `graphify update` stand-in was not found at {_GRAPHIFY_STAND_IN} -- "
    "this oracle produces its index by running that producer, and would "
    "otherwise fail for a path reason rather than a behavioural one."
)

_LIB_SOURCE = """\
def target():
    return 1


def lonely():
    return 2
"""

_APP_SOURCE = """\
from lib import target


def run():
    return target()
"""


def _line_of(source: str, needle: str) -> int:
    """The 1-based line number of ``needle`` in the SEEDED SOURCE -- the
    expectation's only origin (never the generated graph)."""
    for offset, line in enumerate(source.splitlines(), start=1):
        if needle in line:
            return offset
    raise AssertionError(f"{needle!r} is not in the seeded source")


@pytest.fixture()
def indexed_root(tmp_path: Path) -> Path:
    """A temporary root whose graphify index was JUST produced by a real
    ``graphify update`` run over it."""
    (tmp_path / "lib.py").write_text(_LIB_SOURCE, encoding="utf-8")
    (tmp_path / "app.py").write_text(_APP_SOURCE, encoding="utf-8")
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
    return tmp_path


def _answer(root: Path, symbol: str, capsys: pytest.CaptureFixture[str]) -> dict:
    exit_code = main(["query.callers-of", symbol, "--root", str(root)])
    stdout = capsys.readouterr().out
    assert exit_code == 0, (
        f"`des code-fact query.callers-of {symbol}` over a freshly indexed "
        f"root exited {exit_code} instead of answering: {stdout!r}"
    )
    return json.loads(stdout)


def _graphify_trace(payload: dict) -> dict:
    entries = [e for e in payload["trace"] if e["provider_id"] == "graphify"]
    assert entries, (
        "graphify contributed NO trace entry to this answer: "
        f"{payload['trace']!r} -- it did not even attempt the query."
    )
    return entries[-1]


class TestCallersOfOverAFreshlyProducedIndex:
    def test_real_call_sites_are_answered_at_binding_resolved(
        self, indexed_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        expected_line = _line_of(_APP_SOURCE, "return target()")

        payload = _answer(indexed_root, "target", capsys)

        assert (payload["provider"], payload["confidence"]) == (
            "graphify",
            "binding-resolved",
        ), (
            "a root whose index was just produced by `graphify update` must "
            f"be answered by the precise tier, got {payload['provider']!r}/"
            f"{payload['confidence']!r} -- a degraded provider's answer read "
            "as binding-resolved fact is the silent-degrade class this "
            "capability exists to close."
        )
        sites = payload["payload"]["sites"]
        assert len(sites) == 1, (
            f"expected exactly one call site of `target`, got {sites!r}"
        )
        site_path, _, site_line = sites[0].rpartition(":")
        assert Path(site_path).resolve() == (indexed_root / "app.py").resolve(), (
            f"the answered call site names {site_path!r}, not the file that "
            "really calls `target`."
        )
        assert site_line == str(expected_line), (
            f"the answered call site is at line {site_line!r}, but the SEEDED "
            f"SOURCE calls `target` at line {expected_line} -- the reported "
            "line must be the real one, not the definition's or the import's."
        )

    def test_the_import_of_the_same_symbol_is_not_reported_as_a_call_site(
        self, indexed_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`app.py` imports `target` AND calls it; the graph carries both an
        `imports` and a `calls` edge naming the same target node. Only the
        `calls` edge is a call site."""
        import_line = _line_of(_APP_SOURCE, "from lib import target")

        payload = _answer(indexed_root, "target", capsys)

        reported_lines = {
            site.rpartition(":")[2] for site in payload["payload"]["sites"]
        }
        assert str(import_line) not in reported_lines, (
            f"line {import_line} (the IMPORT of `target`) is reported as a "
            f"call site: {payload['payload']['sites']!r} -- an `imports` edge "
            "is not a call, and counting it inflates a wiring claim."
        )

    def test_an_uncalled_symbol_answers_a_verified_empty_site_set(
        self, indexed_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`lonely` is defined in-root and called nowhere. The honest answer
        is an empty site set that is still `binding-resolved` and still
        `complete` -- verified absence, not a default."""
        payload = _answer(indexed_root, "lonely", capsys)

        assert (payload["provider"], payload["confidence"]) == (
            "graphify",
            "binding-resolved",
        ), (
            "an uncalled symbol must still be answered by the precise tier "
            f"({payload['provider']!r}/{payload['confidence']!r} instead) -- "
            "otherwise 'no callers' is indistinguishable from 'nobody who "
            "could see callers looked'."
        )
        assert payload["payload"]["sites"] == [], (
            f"`lonely` is called nowhere in the seeded root, yet sites "
            f"{payload['payload']['sites']!r} were reported."
        )
        entry = _graphify_trace(payload)
        assert (entry["scope"], entry["fault_count"]) == ("complete", 0), (
            f"the empty answer's own trace declares scope {entry['scope']!r} "
            f"and fault_count {entry['fault_count']!r} -- an empty site set "
            "may only be read as a real absence when the whole tree was "
            "observed without fault."
        )
