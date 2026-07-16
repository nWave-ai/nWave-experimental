"""Regression -- contract-gate collector must be marker-target-agnostic.

RCA: docs/feature/fix-collector-marker-filter-target-agnostic/deliver/rca.md

`_collect_node_ids` / `_collect_scope` default to the marker-FILTERED collect
(`-m "unit or integration or acceptance"`, `run_contract_gate.py:129
_FULL_SUITE_MARKER`). nwave-dev's own conftest auto-marker stamps every item
with those markers, so nwave-dev's whole suite matches the filter. A FOREIGN
target repo whose tests carry NO unit/integration/acceptance marker collects
ZERO under the filter while an unfiltered (`markers=None`) collect finds every
test -- and today the gate silently reports that filtered zero as the
"genuinely collected zero" verdict (`_mode_print_digest`'s `GateScopeDigest`
event, `node_id_count: 0`), refusing a GREEN slice on a healthy foreign repo.

Two defects pinned here:
  1. target-agnosticism -- filtered-zero-but-agnostic-nonzero must not be
     silently reported as a genuine zero (fallback OR degrade-LOUD naming the
     marker mismatch).
  2. the vacuous-scope refusal for a GENUINELY-empty scope (zero under BOTH
     filters) must stay intact -- the fix must never fabricate a nonzero
     count for a truly empty scope.

Drives the real production seams in-process: `_collect_node_ids` (the
canonical collection function, `run_contract_gate.py:219`) and
`_mode_print_digest` (the `des run-contract-gate --collect-only
--print-digest` CLI entry's implementation, `run_contract_gate.py:1544`).
Hermetic tmp-repo fixtures only -- no real cargo, no network. The worker
spawned by `_collect_scope` resolves its own pytest-capable interpreter via
`pytest_interpreter()` (the SAME interpreter this test suite runs under, i.e.
`.venv/bin/python3` in this repo) -- no interpreter is hardcoded here.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from des.cli.run_contract_gate import _collect_node_ids, _mode_print_digest


_PYPROJECT_SOURCE = textwrap.dedent(
    """\
    [tool.pytest.ini_options]
    testpaths = ["tests"]
    """
)


def _write_unmarked_tests(tests_dir: Path, function_names: list[str]) -> None:
    """A plain test module -- no `@pytest.mark.*` decorations at all."""
    body = "\n\n\n".join(f"def {name}():\n    assert True" for name in function_names)
    (tests_dir / "test_unmarked.py").write_text(body + "\n", encoding="utf-8")


def _write_marked_tests(tests_dir: Path, function_names: list[str]) -> None:
    """Mirrors nwave-dev's own conftest auto-marker convention: every test IS marked."""
    body = "\n\n\n".join(
        f"@pytest.mark.unit\ndef {name}():\n    assert True" for name in function_names
    )
    (tests_dir / "test_marked.py").write_text(
        "import pytest\n\n\n" + body + "\n", encoding="utf-8"
    )


def _provision_project(project_dir: Path) -> Path:
    """Provision the shared skeleton (pyproject.toml + empty tests/ package)."""
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "pyproject.toml").write_text(_PYPROJECT_SOURCE, encoding="utf-8")
    tests_dir = project_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    return tests_dir


def _gate_scope_digest_event(stderr_text: str) -> dict[str, object]:
    """Parse the `GateScopeDigest` JSON event line from `_mode_print_digest`'s stderr."""
    for line in stderr_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if payload.get("event") == "GateScopeDigest":
            return payload
    raise AssertionError(
        f"no GateScopeDigest event found in _mode_print_digest stderr: {stderr_text!r}"
    )


@pytest.mark.unit
def test_foreign_repo_marker_mismatch_is_not_reported_as_genuinely_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The diagnosed defect: an unmarked-but-populated repo must not read as zero.

    Given a hermetic foreign repo with 3 passing tests and NO
    unit/integration/acceptance marker (no conftest auto-marker, no
    `@pytest.mark.*` decorations -- the alpha-challenge shape the RCA
    diagnosed), the marker-FILTERED collect (today's default) is 0 while the
    marker-agnostic collect finds all 3. The contract-gate's `--collect-only
    --print-digest` surface must not silently report that filtered zero as
    the genuine scope: it must either fall back to the agnostic count, or
    degrade-LOUD naming the marker mismatch. Today it does neither -- this
    assertion is RED for the diagnosed reason.
    """
    project_dir = tmp_path / "foreign_unmarked_repo"
    function_names = ["test_alpha", "test_beta", "test_gamma"]
    tests_dir = _provision_project(project_dir)
    _write_unmarked_tests(tests_dir, function_names)

    filtered_node_ids = _collect_node_ids(project_dir)
    agnostic_node_ids = _collect_node_ids(project_dir, markers=None)

    # Premise: pytest genuinely finds the 3 unmarked tests unfiltered, while
    # the marker filter excludes every one of them (the root-cause fact).
    assert len(agnostic_node_ids) == len(function_names), (
        f"premise check: marker-agnostic collect should find all "
        f"{len(function_names)} unmarked tests; got {len(agnostic_node_ids)}: "
        f"{agnostic_node_ids!r}"
    )
    assert filtered_node_ids == [], (
        "premise check: the marker-FILTERED collect must exclude every "
        f"unmarked test on this foreign repo; got {filtered_node_ids!r}"
    )

    exit_code = _mode_print_digest(project_dir)
    captured = capsys.readouterr()
    event = _gate_scope_digest_event(captured.err)
    combined_output = (captured.out + captured.err).lower()
    marker_mismatch_named = "marker" in combined_output

    assert event["node_id_count"] != 0 or marker_mismatch_named, (
        "contract-gate collector silently reported "
        f"node_id_count={event['node_id_count']} (exit {exit_code}) for a "
        f"foreign repo with {len(agnostic_node_ids)} marker-agnostic tests "
        "and NO unit/integration/acceptance marker -- expected either a "
        "fallback to the marker-agnostic scope, or a degrade-LOUD message "
        "naming the marker mismatch; got neither (the false 'genuinely "
        "zero' bug -- "
        "docs/feature/fix-collector-marker-filter-target-agnostic/deliver/"
        "rca.md)"
    )


def _write_partial_marked_tests(
    tests_dir: Path, marked_names: list[str], unmarked_names: list[str]
) -> None:
    """A foreign module where ONLY `marked_names` carry a marker; the rest are bare."""
    marked_body = "\n\n\n".join(
        f"@pytest.mark.unit\ndef {name}():\n    assert True" for name in marked_names
    )
    unmarked_body = "\n\n\n".join(
        f"def {name}():\n    assert True" for name in unmarked_names
    )
    (tests_dir / "test_partial.py").write_text(
        "import pytest\n\n\n" + marked_body + "\n\n\n" + unmarked_body + "\n",
        encoding="utf-8",
    )


@pytest.mark.unit
def test_partial_marking_silent_subset_is_not_reported_without_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The Vera-surfaced case: filtered<agnostic (a SUBSET) must not scope silently.

    Vera's examine FAILed the filtered==0 fallback on a case it never covered:
    a foreign repo where SOME (not all) tests carry a marker. Here 1 of 3
    tests is marked unit; the other 2 are bare. The marker-FILTERED collect
    returns 1 (>0), so the "filtered==0 fallback" never triggers -- the gate
    silently scopes to the 1 marked test and reports node_id_count=1 with NO
    explanation, and the user's other 2 tests VANISH from the contract scope.

    Pin: when filtered < agnostic (some tests excluded by the marker filter,
    not merely all), the gate must NOT silently report the subset -- it must
    emit a marker_mismatch warning NAMING the excluded count (2) and how to
    include them. Today no warning fires on the partial case -- this assertion
    is RED for the diagnosed reason (a silent subset, not a false zero).
    """
    project_dir = tmp_path / "foreign_partial_marked_repo"
    marked_names = ["test_marked_one"]
    unmarked_names = ["test_bare_two", "test_bare_three"]
    tests_dir = _provision_project(project_dir)
    _write_partial_marked_tests(tests_dir, marked_names, unmarked_names)

    filtered_node_ids = _collect_node_ids(project_dir)
    agnostic_node_ids = _collect_node_ids(project_dir, markers=None)

    # Premise: the marker filter yields a strict, non-empty SUBSET -- the
    # 1 marked test survives, the 2 bare tests are excluded (the root-cause
    # fact that makes the filtered==0 fallback structurally blind to this case).
    assert len(filtered_node_ids) == len(marked_names), (
        f"premise check: exactly the {len(marked_names)} marked test(s) must "
        f"survive the marker filter; got {filtered_node_ids!r}"
    )
    assert len(agnostic_node_ids) == len(marked_names) + len(unmarked_names), (
        "premise check: the marker-agnostic collect must find ALL "
        f"{len(marked_names) + len(unmarked_names)} tests; got "
        f"{agnostic_node_ids!r}"
    )
    assert 0 < len(filtered_node_ids) < len(agnostic_node_ids), (
        "premise check: this is the strict-SUBSET case (0 < filtered < "
        f"agnostic); got filtered={filtered_node_ids!r} "
        f"agnostic={agnostic_node_ids!r}"
    )

    _mode_print_digest(project_dir)
    captured = capsys.readouterr()
    combined_output = (captured.out + captured.err).lower()
    excluded_count = len(agnostic_node_ids) - len(filtered_node_ids)
    marker_mismatch_named = "marker" in combined_output
    excluded_count_named = str(excluded_count) in combined_output

    assert marker_mismatch_named and excluded_count_named, (
        "contract-gate collector silently scoped to the "
        f"{len(filtered_node_ids)}-test marked SUBSET, dropping "
        f"{excluded_count} unmarked test(s) with NO explanation -- expected a "
        "degrade-LOUD marker_mismatch warning NAMING the excluded count "
        f"({excluded_count}) and how to include them; got neither "
        f"(marker-named={marker_mismatch_named}, "
        f"excluded-count-named={excluded_count_named}). The silent-subset bug "
        "-- docs/feature/fix-collector-marker-filter-target-agnostic/deliver/"
        "rca.md"
    )


@pytest.mark.unit
def test_genuinely_empty_scope_never_fabricates_a_nonzero_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Negative AT: a truly-empty scope must stay refused, never vacuously pass.

    Zero test files exist at all -- collected_count is 0 under BOTH the
    marker-filtered AND the marker-agnostic collect. The fix for the
    target-agnosticism defect (falling back to the agnostic count on a
    filtered-zero) must NOT fabricate a nonzero count here: there is nothing
    to fall back to, so the honest zero-collected refusal must survive.
    """
    project_dir = tmp_path / "genuinely_empty_repo"
    _provision_project(project_dir)  # tests/ package with zero test files

    filtered_node_ids = _collect_node_ids(project_dir)
    agnostic_node_ids = _collect_node_ids(project_dir, markers=None)

    assert filtered_node_ids == [] and agnostic_node_ids == [], (
        "premise check: a repo with zero test files must collect zero under "
        f"BOTH filters; got filtered={filtered_node_ids!r} "
        f"agnostic={agnostic_node_ids!r}"
    )

    _mode_print_digest(project_dir)
    captured = capsys.readouterr()
    event = _gate_scope_digest_event(captured.err)

    assert event["node_id_count"] == 0, (
        "a GENUINELY-empty scope (zero tests under both the marker-filtered "
        "and the marker-agnostic collect) must report node_id_count == 0 -- "
        "the marker-mismatch fallback must never fabricate a nonzero count "
        f"for a truly empty scope; got {event['node_id_count']}"
    )


@pytest.mark.unit
def test_marked_repo_filtered_and_agnostic_collect_stay_unchanged(
    tmp_path: Path,
) -> None:
    """No-regression pin: a repo whose tests ARE marked collects identically.

    Mirrors nwave-dev's own conftest auto-marker convention (every item
    stamped with unit/integration/acceptance). Filtered and agnostic collect
    must find the SAME scope -- the target-agnosticism fix must not change
    nwave-dev's own (already-marked) behaviour.
    """
    project_dir = tmp_path / "marked_repo_mirrors_nwave_dev"
    function_names = ["test_one", "test_two", "test_three", "test_four"]
    tests_dir = _provision_project(project_dir)
    _write_marked_tests(tests_dir, function_names)

    filtered_node_ids = _collect_node_ids(project_dir)
    agnostic_node_ids = _collect_node_ids(project_dir, markers=None)

    assert len(filtered_node_ids) == len(function_names), (
        f"a fully-marked repo must collect all {len(function_names)} tests "
        f"under the marker filter; got {filtered_node_ids!r}"
    )
    assert set(filtered_node_ids) == set(agnostic_node_ids), (
        "a repo whose tests ARE marked must collect the IDENTICAL scope "
        f"under both filters (no regression); filtered={filtered_node_ids!r} "
        f"agnostic={agnostic_node_ids!r}"
    )
