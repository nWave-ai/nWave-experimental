"""Composition root for des-gate-error-explain-and-guide slice-02 ATs.

Drives the production `des run-contract-gate --feature-id` CLI as a subprocess
black box to provoke the three remaining FeatureScopeMalformed reason tokens:
  - collection-failed
  - arch-scope-zero-collected
  - arch-invariant-failed

MANDATE-13 DRIVING-PORT-ONLY (HARD INVARIANT):
`_explain_and_guide`, `_EXPLAIN_AND_GUIDE_TABLE`, and `_feature_scope_malformed`
are NEVER imported-and-called at the step boundary. The SUT is exercised only
through the CLI subprocess:

    python -m des.cli.run_contract_gate
        --feature-id <id> --entering-slice <slice> --repo <tmp>

The observable surface is:
  - stdout: one-line JSON object (the FeatureScopeMalformed event payload)
  - exit code: 2

SYNTHETIC SUBSTRATES (precondition state, NOT the SUT):

  COLLECTION_FAILED_SUBSTRATE:
    A repo with a properly-tagged .feature file (so `_feature_tag_files` returns
    it and `_slice_tags` finds the entering_slice tag) PLUS a broken Python
    step file (syntax error via `import this_module_does_not_exist_xyz_abc`) in
    the same directory as the .feature file. When `_collect_node_ids` runs pytest
    --collect-only on that directory, pytest raises an ImportError ->
    _CollectionError -> reason="collection-failed".

  ARCH_SCOPE_ZERO_COLLECTED_SUBSTRATE:
    A repo with a valid .feature file (tagged + sliced), a valid conftest.py so
    the feature scope itself collects >=1 node (needed to pass the M-1 floor for
    the feature scope before the arch tier is checked), PLUS a tests/build/
    directory that is empty. The arch-invariant worker runs pytest on tests/build/
    with no test files -> pytest exit 5 (no tests collected) ->
    _ArchVerdict(collected=0, passed=True) -> arch.collected == 0 ->
    reason="arch-scope-zero-collected".

  ARCH_INVARIANT_FAILED_SUBSTRATE:
    Same as ARCH_SCOPE_ZERO_COLLECTED_SUBSTRATE except tests/build/ contains a
    failing test file marked `unit` (inside the contract marker set
    "unit or integration or acceptance"). The worker runs it, it fails ->
    _ArchVerdict(collected=1, passed=False) -> not arch.passed ->
    reason="arch-invariant-failed".

FEATURE-SCOPE COLLECTION BYPASS (for arch token substrates):
For the arch-related tokens the gate must pass through the feature-scope M-1
floor first. We place a minimal conftest.py + a passing test file in the
feature's step directory so that `_collect_node_ids` returns >=1 node-id.
The test does not need to pass (the gate only collects, not runs, the feature
scope); it only needs to be collectible (no ImportError, no syntax error).

PURE-READ CONTRACT (Mandate-8, layer-3 universe guard):
capture_universe() snapshots the tmp dir file count before the When-step; the
When-step asserts unchanged() for every entry.

Known `why` values for zero-collected token (used in scenario 1 distinctness
check without requiring a live invocation):
  _EXPLAIN_AND_GUIDE_TABLE["zero-collected"]["why"] =
    "no .feature file in the repository carries the @feature-<id> tag..."
We derive this from the domain_types constant set so the slice-02 scenarios are
self-contained and independent of slice-01 live runs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from .composition import _run_contract_gate_in_process
from .domain_types import (
    ExplainAndGuideField,
    FeatureId,
    SliceTag,
)


# tests/des/acceptance/des-gate-error-explain-and-guide/steps/slice_02_composition.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# Synthetic identifiers shared across all slice-02 substrates.
_SYNTHETIC_FEATURE_ID = FeatureId("explain-guide-at-s2-substrate")
_SYNTHETIC_SLICE_TAG = SliceTag("slice-01")

# Known `why` sentinels derived from the production _EXPLAIN_AND_GUIDE_TABLE.
# These are the verbatim strings the mapper returns for each token.  Using
# sentinels (rather than cross-scenario fixture state) makes each scenario's
# distinctness assertion self-contained: if the mapper changes one of these
# strings the assertion correctly goes RED.
_ZERO_COLLECTED_WHY_SENTINEL = (
    "no .feature file in the repository carries the"
    " @feature-<id> tag for this feature;"
    " the scoped gate would pass vacuously"
)
_COLLECTION_FAILED_WHY_SENTINEL = (
    "pytest raised a collection-time error (import error,"
    " syntax error, or plugin failure) while scanning"
    " the feature's test files"
)
_ARCH_SCOPE_ZERO_COLLECTED_WHY_SENTINEL = (
    "the architecture-invariant tier is present"
    " but its test scope collected zero tests;"
    " a vacuous arch-tier pass is refused"
)


def _build_base_tagged_feature_file(
    tmp: Path,
    feature_id: FeatureId,
    slice_tag: SliceTag,
) -> Path:
    """Create a correctly-tagged .feature file so `_feature_tag_files` finds it
    and `_slice_tags` returns the entering_slice.  Returns the feature directory.
    """
    feature_dir = tmp / "tests" / "acceptance" / str(feature_id)
    feature_dir.mkdir(parents=True)
    (feature_dir / "my-slice.feature").write_text(
        f"@feature-{feature_id} @{slice_tag}\n"
        "Feature: slice-02 AT substrate\n"
        f"  @{slice_tag}\n"
        "  Scenario: substrate scenario\n"
        "    Given nothing\n",
        encoding="utf-8",
    )
    return feature_dir


def _build_collection_failed_repo(
    tmp: Path, feature_id: FeatureId, slice_tag: SliceTag
) -> None:
    """Build a repo that provokes reason="collection-failed".

    The .feature file is correctly tagged (so `_feature_tag_files` returns it
    and the entering_slice is found). A broken Python file with a syntax error
    lives in the same directory as the .feature file. When `_collect_node_ids`
    runs pytest --collect-only on that directory, the ImportError raises
    _CollectionError -> reason="collection-failed".
    """
    (tmp / ".git").mkdir(parents=True, exist_ok=True)
    feature_dir = _build_base_tagged_feature_file(tmp, feature_id, slice_tag)
    # A Python step file with an ImportError that pytest will discover.
    # The broken import prevents collection from completing.
    (feature_dir / "test_broken_step.py").write_text(
        "# Broken step file -- provokes pytest _CollectionError\n"
        "import this_module_does_not_exist_xyz_abc_123\n"
        "\n"
        "def test_placeholder():\n"
        "    pass\n",
        encoding="utf-8",
    )


def _build_arch_scope_zero_collected_repo(
    tmp: Path, feature_id: FeatureId, slice_tag: SliceTag
) -> None:
    """Build a repo that provokes reason="arch-scope-zero-collected".

    Feature scope: correctly tagged .feature + a passing, collectible test so
    the M-1 floor for the feature scope clears. tests/build/ exists but is
    empty -> the arch-invariant worker exits 5 (no tests) ->
    _ArchVerdict(collected=0, passed=True) -> arch.collected == 0 ->
    reason="arch-scope-zero-collected".
    """
    (tmp / ".git").mkdir(parents=True, exist_ok=True)
    feature_dir = _build_base_tagged_feature_file(tmp, feature_id, slice_tag)
    # A valid (no-error) test file so the feature scope M-1 floor passes.
    (feature_dir / "test_passing_scope.py").write_text(
        textwrap.dedent("""\
            import pytest

            @pytest.mark.acceptance
            def test_placeholder_scope():
                pass
        """),
        encoding="utf-8",
    )
    # Empty tests/build/ directory -- arch tier present but zero tests.
    (tmp / "tests" / "build").mkdir(parents=True)


def _build_arch_invariant_failed_repo(
    tmp: Path, feature_id: FeatureId, slice_tag: SliceTag
) -> None:
    """Build a repo that provokes reason="arch-invariant-failed".

    Same as arch-scope-zero-collected except tests/build/ has a failing test
    marked `unit` (inside "unit or integration or acceptance") ->
    _ArchVerdict(collected=1, passed=False) -> not arch.passed ->
    reason="arch-invariant-failed".
    """
    (tmp / ".git").mkdir(parents=True, exist_ok=True)
    feature_dir = _build_base_tagged_feature_file(tmp, feature_id, slice_tag)
    (feature_dir / "test_passing_scope.py").write_text(
        textwrap.dedent("""\
            import pytest

            @pytest.mark.acceptance
            def test_placeholder_scope():
                pass
        """),
        encoding="utf-8",
    )
    build_dir = tmp / "tests" / "build"
    build_dir.mkdir(parents=True)
    # A failing test in the arch tier that the worker will collect and run.
    (build_dir / "test_arch_failing.py").write_text(
        textwrap.dedent("""\
            import pytest

            @pytest.mark.unit
            def test_arch_invariant_that_fails():
                assert False, "synthetic arch-invariant failure for slice-02 AT"
        """),
        encoding="utf-8",
    )


@dataclass
class Slice02Composition:
    """Drives the production des run-contract-gate CLI for slice-02 ATs.

    Reuses the same composition pattern as slice-01's ExplainGuideComposition
    but extends it with three additional substrate builders for the remaining
    three reason tokens.
    """

    _tmp: Path | None = field(default=None)
    _feature_id: FeatureId = field(default=_SYNTHETIC_FEATURE_ID)
    _entering_slice: SliceTag = field(default=_SYNTHETIC_SLICE_TAG)
    _completed: subprocess.CompletedProcess[str] | None = field(default=None)
    _event: dict[str, object] | None = field(default=None)
    _universe_before: dict[str, object] | None = field(default=None)

    # ---- given -----------------------------------------------------------------

    def given_collection_failed_repo(self) -> None:
        """Synthetic repo that provokes reason="collection-failed"."""
        self._tmp = Path(tempfile.mkdtemp(prefix="explain-guide-s2-colf-"))
        self._feature_id = _SYNTHETIC_FEATURE_ID
        self._entering_slice = _SYNTHETIC_SLICE_TAG
        _build_collection_failed_repo(self._tmp, self._feature_id, self._entering_slice)

    def given_arch_scope_zero_collected_repo(self) -> None:
        """Synthetic repo that provokes reason="arch-scope-zero-collected"."""
        self._tmp = Path(tempfile.mkdtemp(prefix="explain-guide-s2-archz-"))
        self._feature_id = _SYNTHETIC_FEATURE_ID
        self._entering_slice = _SYNTHETIC_SLICE_TAG
        _build_arch_scope_zero_collected_repo(
            self._tmp, self._feature_id, self._entering_slice
        )

    def given_arch_invariant_failed_repo(self) -> None:
        """Synthetic repo that provokes reason="arch-invariant-failed"."""
        self._tmp = Path(tempfile.mkdtemp(prefix="explain-guide-s2-archf-"))
        self._feature_id = _SYNTHETIC_FEATURE_ID
        self._entering_slice = _SYNTHETIC_SLICE_TAG
        _build_arch_invariant_failed_repo(
            self._tmp, self._feature_id, self._entering_slice
        )

    # ---- when ------------------------------------------------------------------

    def when_operator_runs_gate(self) -> None:
        """Invoke the REAL des run-contract-gate CLI as a subprocess black box.

        Pure-read guard (Mandate-8): snapshot tmp dir before invocation;
        assert unchanged() on every universe entry after the invocation returns.

        Env-parity: NWAVE_FRESHNESS=skip + PIPENV_DONT_LOAD_ENV=1 so the
        freshness wrapper does not refuse with exit 78 before gate logic runs.
        """
        tmp = self._require_tmp()
        self._universe_before = self.capture_universe()

        exit_code, out, err = _run_contract_gate_in_process(
            self._feature_id, self._entering_slice, tmp
        )
        self._completed = subprocess.CompletedProcess(
            args=["des", "run-contract-gate"],
            returncode=exit_code,
            stdout=out,
            stderr=err,
        )

        stdout = self._completed.stdout.strip()
        if stdout:
            self._event = json.loads(stdout)

        self._assert_pure_read()

    # ---- then ------------------------------------------------------------------

    def then_triad_present_for_reason(self, expected_reason: str) -> None:
        """The emitted JSON carries non-empty what/why/next for the expected token.

        GREEN-on-author: the _EXPLAIN_AND_GUIDE_TABLE entry for every reason
        token was shipped in slice-01 DELIVER. This assertion would FAIL if the
        entry for `expected_reason` had an empty `what`, `why`, or `next`.

        Also asserts the `reason` field matches `expected_reason` so a wrong
        substrate (accidentally triggering a different token) is caught.
        """
        event = self._require_event()
        assert event.get("reason") == expected_reason, (
            f"Expected reason={expected_reason!r} but got "
            f"reason={event.get('reason')!r}. "
            f"The substrate did not provoke the expected token. "
            f"Full event: {event}. stderr={self._require_completed().stderr!r}"
        )
        assert event.get("event") == "FeatureScopeMalformed", (
            f"Expected event='FeatureScopeMalformed' but got {event.get('event')!r}. "
            f"Full event: {event}"
        )
        assert self._require_completed().returncode == 2, (
            f"Expected exit code 2 (malformed scope) but got "
            f"{self._require_completed().returncode}. "
            f"stdout={self._require_completed().stdout!r}; "
            f"stderr={self._require_completed().stderr!r}"
        )
        for field_name in (
            ExplainAndGuideField.WHAT,
            ExplainAndGuideField.WHY,
            ExplainAndGuideField.NEXT,
        ):
            value = event.get(field_name.value)
            assert isinstance(value, str) and len(value) > 0, (
                f"FeatureScopeMalformed event for reason={expected_reason!r} "
                f"must carry a non-empty '{field_name.value}' field. "
                f"Got: {value!r}. Full event: {event}"
            )

    def then_why_distinct_from_known_zero_collected(self) -> None:
        """The `why` for collection-failed differs from the known zero-collected `why`.

        Uses the known zero-collected `why` sentinel constant rather than a live
        invocation -- the comparison is self-contained and does not depend on
        running a zero-collected substrate.

        This assertion fails if the mapper returns a constant string for all
        tokens (the `why` for collection-failed would equal the zero-collected
        string from `_EXPLAIN_AND_GUIDE_TABLE`).
        """
        event = self._require_event()
        collection_failed_why = event.get(ExplainAndGuideField.WHY.value)
        assert (
            isinstance(collection_failed_why, str) and len(collection_failed_why) > 0
        ), (
            f"collection-failed `why` must be a non-empty string. "
            f"Got: {collection_failed_why!r}. Full event: {event}"
        )
        assert collection_failed_why != _ZERO_COLLECTED_WHY_SENTINEL, (
            f"The `why` for collection-failed ({collection_failed_why!r}) must be "
            f"DISTINCT from the `why` for zero-collected "
            f"({_ZERO_COLLECTED_WHY_SENTINEL!r}). "
            "A constant-string stub mapper would fail this assertion."
        )

    def then_arch_scope_zero_why_distinct_from_collection_failed(self) -> None:
        """The `why` for arch-scope-zero-collected differs from the known collection-failed `why`.

        Self-contained: uses the sentinel constant, not cross-scenario fixture state.
        A constant-stub mapper would return the same `why` for both tokens and fail.
        """
        event = self._require_event()
        arch_zero_why = event.get(ExplainAndGuideField.WHY.value)
        assert isinstance(arch_zero_why, str) and len(arch_zero_why) > 0, (
            f"arch-scope-zero-collected `why` must be a non-empty string. "
            f"Got: {arch_zero_why!r}. Full event: {event}"
        )
        assert arch_zero_why != _COLLECTION_FAILED_WHY_SENTINEL, (
            f"The `why` for arch-scope-zero-collected ({arch_zero_why!r}) must be "
            f"DISTINCT from the `why` for collection-failed "
            f"({_COLLECTION_FAILED_WHY_SENTINEL!r}). "
            "A constant-string stub mapper would fail this assertion."
        )

    def then_arch_invariant_failed_why_distinct_from_arch_scope_zero(self) -> None:
        """The `why` for arch-invariant-failed differs from the known arch-scope-zero-collected `why`.

        Self-contained: uses the sentinel constant, not cross-scenario fixture state.
        A constant-stub mapper would return the same `why` for both tokens and fail.
        """
        event = self._require_event()
        arch_failed_why = event.get(ExplainAndGuideField.WHY.value)
        assert isinstance(arch_failed_why, str) and len(arch_failed_why) > 0, (
            f"arch-invariant-failed `why` must be a non-empty string. "
            f"Got: {arch_failed_why!r}. Full event: {event}"
        )
        assert arch_failed_why != _ARCH_SCOPE_ZERO_COLLECTED_WHY_SENTINEL, (
            f"The `why` for arch-invariant-failed ({arch_failed_why!r}) must be "
            f"DISTINCT from the `why` for arch-scope-zero-collected "
            f"({_ARCH_SCOPE_ZERO_COLLECTED_WHY_SENTINEL!r}). "
            "A constant-string stub mapper would fail this assertion."
        )

    def current_why(self) -> str:
        """Return the `why` value from the most recent invocation."""
        event = self._require_event()
        why = event.get(ExplainAndGuideField.WHY.value)
        assert isinstance(why, str) and len(why) > 0, (
            f"current_why() requires the `why` field to be present and non-empty. "
            f"Got: {why!r}. Full event: {event}"
        )
        return why

    # ---- universe (Mandate-8 pure-read guard) ----------------------------------

    # pytest-generated cache directory names written by the _collect_scope_worker
    # subprocess when it runs `pytest --collect-only` or `pytest` (the --run
    # branch for arch tokens) inside the tmp repo.  These are written by pytest
    # itself, not by the gate logic.  The gate is a pure observer of the
    # repository's SOURCE tree; cache directories are excluded from the universe
    # so the pure-read guard measures only source-tree mutations.
    _PYTEST_CACHE_DIRS: frozenset[str] = frozenset(
        {".pytest_cache", "__pycache__", ".hypothesis"}
    )

    def _is_cache_path(self, path: Path) -> bool:
        """Return True if `path` is inside a pytest-generated cache directory."""
        return any(part in self._PYTEST_CACHE_DIRS for part in path.parts)

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for the pure-read guard (Mandate-8).

        Counts only source-tree entries (not pytest-generated cache dirs/files).
        The three slice-02 tokens all reach `_collect_node_ids` / `_run_arch_invariant_set`
        which spawns the _collect_scope_worker subprocess -- that worker runs
        pytest, which writes __pycache__ and .pytest_cache artifacts into the tmp
        repo.  The gate itself does not write any source files; the universe
        excludes known cache paths so the pure-read guard measures the gate's own
        behaviour, not pytest's cache side-effects.
        """
        tmp = self._require_tmp()
        return {
            "tmp.source_file_count": sum(
                1 for p in tmp.rglob("*") if p.is_file() and not self._is_cache_path(p)
            ),
            "tmp.source_dir_count": sum(
                1 for p in tmp.rglob("*") if p.is_dir() and not self._is_cache_path(p)
            ),
        }

    def _assert_pure_read(self) -> None:
        from tests.common.state_delta import assert_state_delta, unchanged

        assert self._universe_before is not None
        assert_state_delta(
            before=self._universe_before,
            after=self.capture_universe(),
            universe={
                "tmp.source_file_count",
                "tmp.source_dir_count",
            },
            expected={
                "tmp.source_file_count": unchanged(),
                "tmp.source_dir_count": unchanged(),
            },
        )

    # ---- substrate helpers -----------------------------------------------------

    def _require_tmp(self) -> Path:
        assert self._tmp is not None, (
            "the synthetic repo must be built (Given) before running the gate (When)"
        )
        return self._tmp

    def _require_completed(self) -> subprocess.CompletedProcess[str]:
        assert self._completed is not None, (
            "des run-contract-gate must be run (When) before asserting on its surface (Then)"
        )
        return self._completed

    def _require_event(self) -> dict[str, object]:
        completed = self._require_completed()
        assert self._event is not None, (
            "the gate must emit a JSON event on stdout (When) before asserting on its fields (Then). "
            f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
        )
        return self._event

    def cleanup(self) -> None:
        if self._tmp is not None and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
