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

EXTENSION (fix-contract-gate-python-scope-agnostic, Q-169 RCA:
docs/analysis/root-cause-analysis-contract-gate-python-marker-agnostic.md):
the tests above exercise ONLY `_collect_node_ids` (the raw seam) and
`_mode_print_digest` (one debug surface) -- the RCA's own "backwards-chain
validation" found FOUR production call sites that share the identical
unset-markers call shape but were never covered: the default-`at_kind`
produce leg (`commit_slice._committed_scope_digest_or_degrade_reason` ->
`_committed_scope_digest_quiet`), `_mode_verify_gate_scope`, `_mode_run_suite`,
and `_mode_feature_scoped` (the M-1 non-vacuity floor). The tests below drive
those four sites directly, through REAL throwaway git repos (real `git
init`/`add`/`commit`; LOCAL `git config user.email`/`user.name`, never
`--global` -- mirrors
`tests/bugs/des/test_verify_slice_commit_requires_feature_id.py`), since the
committed-scope machinery (`GitCommittedScopeAdapter`) requires a resolvable
commit.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from des.cli import commit_slice
from des.cli.run_contract_gate import (
    _collect_node_ids,
    _committed_scope_digest_quiet,
    _CommittedScopeDigest,
    _mode_feature_scoped,
    _mode_print_digest,
    _mode_run_suite,
    _mode_verify_gate_scope,
)


# sha256("") -- the canonical "empty scope" digest (RCA evidence #3).
_EMPTY_SCOPE_DIGEST = hashlib.sha256(b"").hexdigest()


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


def _write_unmarked_tests_with_one_failure(
    tests_dir: Path, passing_names: list[str], failing_name: str
) -> None:
    """A plain, marker-less module where every test passes EXCEPT one -- a
    genuine regression the gate must never swallow into a false GREEN.
    """
    passing_body = "\n\n\n".join(
        f"def {name}():\n    assert True" for name in passing_names
    )
    failing_body = (
        f"def {failing_name}():\n"
        "    assert False, 'deliberate regression-fixture failure'"
    )
    (tests_dir / "test_unmarked_with_failure.py").write_text(
        passing_body + "\n\n\n" + failing_body + "\n", encoding="utf-8"
    )


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


def _run_git(repo: Path, *args: str) -> str:
    """Run a real `git` subprocess scoped to `repo`; raise on non-zero exit."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _init_git_repo(repo: Path) -> None:
    """A real, throwaway git repo with LOCAL (never `--global`) identity."""
    repo.mkdir(parents=True, exist_ok=True)
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")


def _git_commit_all(repo: Path, message: str) -> None:
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-q", "-m", message)


def _last_json_event_on_stdout(stdout_text: str) -> dict[str, object]:
    """Parse the LAST single-line JSON object `_mode_*` printed on stdout.

    The `_mode_*` functions may also print a human-readable summary line
    (`print_human_summary`) alongside the machine-readable event -- this
    skips any non-JSON line rather than assuming the JSON event is the only
    line printed.
    """
    events: list[dict[str, object]] = []
    for line in stdout_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    assert events, f"expected at least one JSON event on stdout, got: {stdout_text!r}"
    return events[-1]


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


# ---------------------------------------------------------------------------
# EXTENSION -- the four RCA-named, previously-uncovered production call sites
# (Q-169: docs/analysis/root-cause-analysis-contract-gate-python-marker-
# agnostic.md). Each test below drives a REAL git-committed foreign repo
# through the ACTUAL default-`at_kind` seam a normal `des commit-slice` /
# `des run-contract-gate` invocation exercises -- not the raw `_collect_scope`
# function these sites internally share.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_default_at_kind_produce_leg_seals_real_digest_on_marker_less_repo(
    tmp_path: Path,
) -> None:
    """Constraint 1 (POSITIVE, RED today): the default-`at_kind` PRODUCE leg
    (`commit_slice._committed_scope_digest_or_degrade_reason`, which is the
    exact function `des commit-slice` calls for a normal `gherkin` slice --
    core: `_committed_scope_digest_quiet`) must seal a REAL, non-empty digest
    reflecting a marker-less repo's genuine N passing tests, never the vacuous
    `sha256("")` seal (RCA evidence #2: `_CommittedScopeDigest(digest=sha256(
    ""), node_id_count=0)` minted for a repo with 3 real passing tests).
    """
    project_dir = tmp_path / "marker_less_committed_repo"
    function_names = ["test_one", "test_two", "test_three"]
    tests_dir = _provision_project(project_dir)
    _write_unmarked_tests(tests_dir, function_names)
    _init_git_repo(project_dir)
    _git_commit_all(project_dir, "seed the marker-less contract suite")

    result = _committed_scope_digest_quiet(project_dir, "HEAD")

    assert isinstance(result, _CommittedScopeDigest), (
        "expected a real _CommittedScopeDigest for a marker-less repo with "
        f"{len(function_names)} real passing tests -- got a refusal/"
        f"indeterminate instead: {result!r}"
    )
    assert result.node_id_count == len(function_names), (
        "the default-at_kind produce leg (_committed_scope_digest_quiet, the "
        "core of commit_slice._committed_scope_digest_or_degrade_reason) "
        f"silently reported node_id_count={result.node_id_count} for a "
        f"marker-less repo with {len(function_names)} real passing tests -- "
        "the vacuous-digest bug (docs/analysis/root-cause-analysis-contract-"
        "gate-python-marker-agnostic.md, evidence #2)"
    )
    assert result.digest != _EMPTY_SCOPE_DIGEST, (
        f"the produce leg sealed the VACUOUS sha256('') digest "
        f"({_EMPTY_SCOPE_DIGEST}) for a repo with {len(function_names)} real "
        "passing tests -- a vacuous seal masquerading as a real one"
    )

    digest_or_reason = commit_slice._committed_scope_digest_or_degrade_reason(
        project_dir, at_kind=None
    )
    assert digest_or_reason == (result.digest, None), (
        "commit_slice._committed_scope_digest_or_degrade_reason (the ACTUAL "
        "function `des commit-slice` calls for the default at_kind) must "
        f"mint the SAME real digest as the underlying seam -- got "
        f"{digest_or_reason!r}, expected ({result.digest!r}, None)"
    )


@pytest.mark.unit
def test_verify_gate_scope_default_at_kind_re_derives_real_digest_not_vacuous(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Constraint 1 (RED today), RCA branch B: `_mode_verify_gate_scope`
    (default `at_kind`) must RE-DERIVE the SAME real, marker-agnostic digest a
    correctly-fixed produce leg would have stamped as the commit's
    `Gate-Scope:` trailer -- not a freshly-recomputed VACUOUS digest that
    falsely reports the already-correct trailer as `mismatch`.

    The commit's trailer is seeded with the marker-AGNOSTIC digest (what the
    fixed produce leg is expected to seal) via `git commit --amend` -- the
    tree content (and therefore every collected node-id) is unchanged by the
    amend, only the commit message/SHA. Today's unfixed verify leg
    (`_committed_scope_digest_value(repo, commit, _MARKERS_UNSET)`) still
    collects the marker-FILTERED (vacuous) scope, so it disagrees with the
    real trailer -- a false `GateScopeUnverified`/`mismatch` on an honestly
    correct commit.
    """
    project_dir = tmp_path / "marker_less_verify_repo"
    function_names = ["test_alpha", "test_beta"]
    tests_dir = _provision_project(project_dir)
    _write_unmarked_tests(tests_dir, function_names)
    _init_git_repo(project_dir)
    _git_commit_all(project_dir, "seed the marker-less contract suite")

    agnostic_result = _committed_scope_digest_quiet(project_dir, "HEAD", markers=None)
    assert isinstance(agnostic_result, _CommittedScopeDigest), (
        f"premise check: the marker-agnostic collect must succeed; got {agnostic_result!r}"
    )
    assert agnostic_result.node_id_count == len(function_names), (
        "premise check: the marker-agnostic collect must find both real "
        f"tests; got node_id_count={agnostic_result.node_id_count}"
    )

    _run_git(
        project_dir,
        "commit",
        "--amend",
        "-q",
        "-m",
        f"seed the marker-less contract suite\n\nGate-Scope: {agnostic_result.digest}",
    )

    exit_code = _mode_verify_gate_scope(project_dir, "HEAD", at_kind=None)
    captured = capsys.readouterr()
    event = _last_json_event_on_stdout(captured.out)

    assert exit_code == 0 and event.get("event") == "GateScopeVerified", (
        "_mode_verify_gate_scope (default at_kind) failed to re-derive the "
        "REAL marker-agnostic digest already carried by the commit's "
        f"Gate-Scope: trailer -- got exit {exit_code}, event {event!r}. "
        "This is RCA branch B: the produce and verify legs share the "
        "identical unset-markers call shape, so once the produce leg is "
        "fixed to stamp a real digest, the verify leg must agree with it, "
        "not recompute a vacuous one and falsely report a mismatch."
    )


@pytest.mark.unit
def test_feature_scoped_m1_floor_clears_marker_less_populated_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Constraint 1 (RED today) + constraint 5, RCA branch C:
    `_mode_feature_scoped` (the M-1 non-vacuity floor `des commit-slice`
    invokes via `--feature-id`) must NOT falsely refuse a feature scope that
    is marker-less but GENUINELY populated with one real, collectible,
    passing scenario.

    Today `_collect_node_ids(repo, paths=scope_dirs)` (no `markers` kwarg,
    hence marker-FILTERED) collects ZERO for this unmarked step module, so
    the M-1 floor refuses `FeatureScopeMalformed reason="zero-collected"` on
    a healthy slice -- the false refusal RCA branch C names.

    This also covers constraint 5 (the examine-gate carve-out at
    `verify_slice_commit_completeness.py:1406-1470`, which treats EXACTLY
    the reasons `"zero-collected"`/`"empty-intersection"` as "genuinely
    nothing to test" and lets an ARMED charter's PASS bypass E2 for them): a
    populated-but-unmarked scope must never surface either of those two
    reason values, or a real, unattested slice would silently ride the
    zero-AT carve-out meant for prose-only slices.
    """
    feature_id = "marker-less-feature-scope-probe"
    entering_slice = "slice-01"
    project_dir = tmp_path / "feature_scoped_marker_less_repo"
    project_dir.mkdir(parents=True)
    scope_dir = project_dir / "tests" / "acceptance" / feature_id.replace("-", "_")
    scope_dir.mkdir(parents=True)
    (scope_dir / "__init__.py").write_text("", encoding="utf-8")
    (scope_dir / "probe.feature").write_text(
        f"@feature-{feature_id}\n"
        f"Feature: The {feature_id} feature has a real, marker-less AT\n\n"
        f"  @{entering_slice}\n"
        "  Scenario: A marker-less scenario is genuinely collectible\n"
        "    Given the scenario carries no unit/integration/acceptance marker\n"
        "    When the feature-scoped contract gate collects the scope\n"
        "    Then the scenario is found\n",
        encoding="utf-8",
    )
    (scope_dir / "test_probe.py").write_text(
        "from __future__ import annotations\n\n"
        "from pytest_bdd import given, scenarios, then, when\n\n\n"
        "# Deliberately NO `pytestmark = pytest.mark.*` -- unmarked, real, passing.\n"
        'scenarios("probe.feature")\n\n\n'
        '@given("the scenario carries no unit/integration/acceptance marker")\n'
        "def _given() -> None:\n    pass\n\n\n"
        '@when("the feature-scoped contract gate collects the scope")\n'
        "def _when() -> None:\n    pass\n\n\n"
        '@then("the scenario is found")\n'
        "def _then() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    exit_code = _mode_feature_scoped(project_dir, feature_id, entering_slice)
    captured = capsys.readouterr()
    event = _last_json_event_on_stdout(captured.out)

    assert event.get("reason") not in {"zero-collected", "empty-intersection"}, (
        "the feature-scoped M-1 floor conflated an unmarked-but-populated "
        "scope with a genuinely-empty one -- the examine-gate carve-out at "
        "verify_slice_commit_completeness.py:1406-1470 treats EXACTLY "
        "these two reasons as 'nothing to test', so a real populated-but-"
        f"unmarked slice would silently bypass E2 through it; got: {event!r}"
    )
    assert exit_code == 0 and event.get("event") == "FeatureScopeCleared", (
        "_mode_feature_scoped (the --feature-id M-1 floor `des commit-slice` "
        "invokes) falsely refused a marker-less-but-real feature scope -- "
        f"got exit {exit_code}, event {event!r} (RCA branch C: "
        "docs/analysis/root-cause-analysis-contract-gate-python-marker-"
        "agnostic.md)"
    )
    assert event.get("collected_node_ids") == 1, (
        f"expected exactly 1 real collected node-id -- got {event!r}"
    )


@pytest.mark.unit
def test_committed_scope_digest_quiet_genuinely_empty_scope_stays_honest(
    tmp_path: Path,
) -> None:
    """Constraint 2 (NEGATIVE, honest-empty): a genuinely-empty COMMITTED
    scope (zero test files at all, zero under BOTH the marker-filtered and
    the marker-agnostic collect) must stay the honest empty digest at the
    default-at_kind produce leg -- the marker-mismatch fallback must never
    fabricate a nonzero count where there is nothing to fall back to.

    Distinct call site from `test_genuinely_empty_scope_never_fabricates_a_
    nonzero_count` above (which pins `_mode_print_digest`): this pins the
    SAME invariant at `_committed_scope_digest_quiet` and
    `commit_slice._committed_scope_digest_or_degrade_reason`, two of the
    four RCA-named uncovered sites.
    """
    project_dir = tmp_path / "genuinely_empty_committed_repo"
    _provision_project(project_dir)  # tests/ package, ZERO test files
    _init_git_repo(project_dir)
    _git_commit_all(project_dir, "seed an empty contract suite")

    result = _committed_scope_digest_quiet(project_dir, "HEAD")

    assert isinstance(result, _CommittedScopeDigest), (
        f"premise check: an empty-but-resolvable commit must still succeed "
        f"(not INDETERMINATE/refused); got {result!r}"
    )
    assert result.node_id_count == 0 and result.digest == _EMPTY_SCOPE_DIGEST, (
        "a genuinely-empty scope (zero test files, zero tests under BOTH the "
        "marker-filtered and marker-agnostic collect) must stay the honest "
        f"empty digest ({_EMPTY_SCOPE_DIGEST}) -- the marker-mismatch "
        "fallback must NEVER fabricate a nonzero count for a truly empty "
        f"scope; got {result!r}"
    )

    digest_or_reason = commit_slice._committed_scope_digest_or_degrade_reason(
        project_dir, at_kind=None
    )
    assert digest_or_reason == (_EMPTY_SCOPE_DIGEST, None), (
        "commit_slice's default-at_kind produce leg must mint the SAME "
        f"honest empty digest for a genuinely-empty scope -- got "
        f"{digest_or_reason!r}"
    )


@pytest.mark.unit
def test_feature_scoped_m1_floor_still_refuses_genuinely_empty_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Constraint 2 (NEGATIVE, honest-empty), second site: a feature scope
    with a tagged `.feature` file but NO bound step module at all (zero
    collectible node-ids under BOTH the marker-filtered and the
    marker-agnostic collect) must stay refused `"zero-collected"` at the M-1
    floor -- the marker-mismatch fix must never fabricate a non-vacuous
    clear here, distinguishing "genuinely nothing to collect" from
    "unmarked-but-populated" (the previous test).
    """
    feature_id = "genuinely-empty-feature-scope-probe"
    entering_slice = "slice-01"
    project_dir = tmp_path / "feature_scoped_genuinely_empty_repo"
    project_dir.mkdir(parents=True)
    scope_dir = project_dir / "tests" / "acceptance" / feature_id.replace("-", "_")
    scope_dir.mkdir(parents=True)
    (scope_dir / "__init__.py").write_text("", encoding="utf-8")
    (scope_dir / "probe.feature").write_text(
        f"@feature-{feature_id}\n"
        f"Feature: The {feature_id} feature declares a scenario with no "
        "bound step module\n\n"
        f"  @{entering_slice}\n"
        "  Scenario: A scenario nobody ever binds to a step module\n"
        "    Given nothing\n"
        "    When nothing happens\n"
        "    Then nothing is collectible\n",
        encoding="utf-8",
    )
    # Deliberately NO test_*.py step module bound to probe.feature -- zero
    # collectible node-ids under BOTH the marker-filtered and the
    # marker-agnostic collect (the genuinely-empty case).

    exit_code = _mode_feature_scoped(project_dir, feature_id, entering_slice)
    captured = capsys.readouterr()
    event = _last_json_event_on_stdout(captured.out)

    assert exit_code == 2 and event.get("reason") == "zero-collected", (
        "a genuinely-empty feature scope (no bound step module at all, zero "
        "collectible node-ids under BOTH filters) must stay refused "
        "'zero-collected' -- the marker-mismatch fix must never fabricate a "
        f"non-vacuous clear here; got exit {exit_code}, event {event!r}"
    )


@pytest.mark.unit
def test_committed_scope_digest_and_verify_stay_unchanged_for_marked_repo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Constraint 3 (NEGATIVE, no-op on marked): an already-marked repo
    (mirrors nwave-dev's own conftest auto-marker convention) must be
    UNCHANGED at the produce AND verify legs -- same real digest, same
    verified outcome -- no regression, no double-collect surprise, at the
    TWO previously-uncovered sites (not merely at the raw `_collect_node_ids`
    level `test_marked_repo_filtered_and_agnostic_collect_stay_unchanged`
    already pins).
    """
    project_dir = tmp_path / "marked_committed_repo"
    function_names = ["test_one", "test_two", "test_three", "test_four"]
    tests_dir = _provision_project(project_dir)
    _write_marked_tests(tests_dir, function_names)
    _init_git_repo(project_dir)
    _git_commit_all(project_dir, "seed the marked contract suite")

    result = _committed_scope_digest_quiet(project_dir, "HEAD")
    assert isinstance(result, _CommittedScopeDigest), (
        f"premise check: a fully-marked repo's produce leg must succeed; got {result!r}"
    )
    assert result.node_id_count == len(function_names), (
        f"a fully-marked repo must collect all {len(function_names)} tests "
        f"at the produce leg; got node_id_count={result.node_id_count}"
    )

    _run_git(
        project_dir,
        "commit",
        "--amend",
        "-q",
        "-m",
        f"seed the marked contract suite\n\nGate-Scope: {result.digest}",
    )

    exit_code = _mode_verify_gate_scope(project_dir, "HEAD", at_kind=None)
    captured = capsys.readouterr()
    event = _last_json_event_on_stdout(captured.out)

    assert exit_code == 0 and event.get("event") == "GateScopeVerified", (
        "a fully-marked repo (mirrors nwave-dev's own convention) must "
        "verify UNCHANGED at the default-at_kind verify leg -- the "
        f"target-agnosticism fix must not regress it; got exit {exit_code}, "
        f"event {event!r}"
    )


@pytest.mark.unit
def test_mode_run_suite_default_at_kind_never_reports_passed_true_for_failing_slice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Constraint 4 (NEGATIVE, fail-not-swallowed): `_mode_run_suite`
    (default `at_kind`, the whole-tree RUN leg `des run-contract-gate`
    exercises) must NEVER report `passed: true` for a marker-less repo that
    carries a genuinely FAILING test.

    The target-agnosticism fix corrects the DIGEST leg (making its
    `gate_scope_digest` real instead of vacuous) -- it must never leak into
    fabricating a PASSING run verdict for a slice that actually fails. This
    guards the exact seam the fix touches (`_committed_scope_digest_quiet`,
    consulted by `_mode_run_suite` for its trailer) against a careless
    implementation that couples digest correctness to run correctness.
    """
    project_dir = tmp_path / "marker_less_failing_repo"
    tests_dir = _provision_project(project_dir)
    _write_unmarked_tests_with_one_failure(
        tests_dir, ["test_one_passes", "test_two_passes"], "test_three_fails"
    )
    _init_git_repo(project_dir)
    _git_commit_all(project_dir, "seed a marker-less suite with a real failure")

    exit_code = _mode_run_suite(project_dir, at_kind=None)
    captured = capsys.readouterr()
    event = _last_json_event_on_stdout(captured.out)

    assert event.get("passed") is not True and exit_code != 0, (
        "the default-at_kind whole-tree suite-run must NEVER report "
        "passed=True (a vacuous, false-GREEN seal) for a marker-less repo "
        f"that carries a genuinely FAILING test -- got exit {exit_code}, "
        f"event {event!r}. The marker-agnostic fallback fixes the DIGEST "
        "leg only (docs/analysis/root-cause-analysis-contract-gate-python-"
        "marker-agnostic.md); it must never leak into fabricating a passing "
        "run verdict."
    )
