"""Acceptance tests -- scoped per-slice BuildTier (DISTILL, slice-01).

Feature-delta: docs/feature/scoped-per-slice-build-tier/feature-delta.md
  Wave: DESIGN / [REF] Architecture & Contract + [REF] Slice Plan (slice-01)

ToC constraint-breaker: the ``des commit-slice`` BuildTier arch-invariant gate
(``build_tier_exit_verdict`` -> ``_run_arch_invariant_set`` in
``src/des/cli/run_contract_gate.py``) runs the WHOLE ``tests/build/**`` tree
(646 tests) for EVERY per-slice seal -- (1) a 3-10 min/seal tax on the box
seal lane, (2) JIT-poisoning: a future-slice active-RED AT (or unrelated
uncommitted drift) anywhere under ``tests/build/**`` fails the CURRENT
slice's seal. Wanted (batch-then-verify, mirrors feature-end refactoring): a
per-slice seal verifies THIS slice's own regression test + the LIGHT
always-on invariants; the heavy whole-tree run moves to the FEATURE-END floor
(``run_contract_gate --repo .``, unchanged, coverage preserved not lost).

Locus (Reuse Analysis EXTEND, not a new spawn site): ``build_tier_exit_verdict``
(the commit-slice Step-3 arch gate) resolves the scope it hands to the
EXISTING ``_run_arch_invariant_set(repo, arch_paths)`` seam -- unchanged
signature, only the caller's ``arch_paths`` computation gains a scope. The
feature-end whole-tree floor (``_mode_feature_scoped`` -> ``_arch_invariant_
paths`` + ``_run_arch_invariant_set``) is a SEPARATE call site this feature
never touches -- read-only preserved per the Reuse Analysis.

DESIGN PIN this AT establishes (necessary -- no prior slice fixed the scope
seam): ``build_tier_exit_verdict`` gains THREE new keyword-only parameters
(ADD-not-mutate, mirrors the C3 ``resource_readings``/``sleep_fn`` extension
-- existing callers, incl. today's zero-new-kwarg ``commit_slice.py`` call
site, are untouched):

    def build_tier_exit_verdict(
        repo: Path,
        *,
        output: OutputPort | None = None,
        resource_readings: Iterable[tuple[int, float]] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        regression_test_file: Path | None = None,
        light_invariant_paths: Sequence[Path] | None = None,
        full: bool = False,
    ) -> int:

  * ``regression_test_file`` -- the entering slice's declared regression test
    (commit-slice's existing ``--regression-test-file``). Given (and ``full``
    is not True) -> the per-slice tier is SCOPED.
  * ``light_invariant_paths`` -- the light always-on invariant set (fast
    structural checks: catalog-coherence, registry drift). ``None`` in scoped
    mode defaults to an internal ``_light_invariant_paths(repo)`` resolver
    (a DELIVER concern -- this AT set always injects the set explicitly so it
    never couples to a guessed filesystem convention).
  * ``full`` -- ``True`` forces the WHOLE ``tests/build/**`` tree (the
    feature-end / ``--full`` / CI path), overriding any scope. Default
    ``False``.

  Scope resolution: ``full=True`` OR neither of the two scope kwargs given ->
  whole tree (``_arch_invariant_paths(repo)``, UNCHANGED -- the existing
  ``tests/build``-presence N/A check at the top of the function stays keyed
  off this same whole-tree resolver, independent of what is actually RUN).
  Otherwise -> SCOPED: ``arch_paths = [regression_test_file,
  *light_invariant_paths]``, and a LOUD deferral event (naming "feature-end")
  is emitted BEFORE the run -- the whole-tree tier is deferred, never
  silently narrowed.

Active-RED scaffolding (hidden-signature-probe, ``nw-distill-red-scaffolding``
P1-P4 applied to a kwarg-extension rather than a new symbol, the SAME pattern
``test_resource_aware_build_tier.py`` (C3) established): the module imports
ONLY the STABLE, ALREADY-PRESENT names (``build_tier_exit_verdict``,
``_ArchVerdict``, the ``run_contract_gate`` module itself,
``des.testing.output_capture.CapturingOutput``) at module top -- nothing
absent is imported, collection is clean (never BROKEN). The missing
functionality is reached at RUNTIME inside ``_drive_gate`` -- calling
``build_tier_exit_verdict(repo, ..., regression_test_file=..., full=...)``
raises ``TypeError: ... got an unexpected keyword argument
'regression_test_file'`` at HEAD (verified empirically before authoring).
``_drive_gate`` catches exactly that ``TypeError`` shape and re-raises a
semantic ``AssertionError`` (MISSING_FUNCTIONALITY) -- every scoped-path test
RED-fails for the right reason, never a collection error. The backward-compat
test (no new kwargs) stays GREEN today by design (an invariant guard, not a
new-functionality pin).

Driving surface (Mandate-13 driving-port-only): every test drives the REAL
composition-root entry ``build_tier_exit_verdict(repo, ...)`` IN-PROCESS (a
direct call, no interpreter fork -- Layer 3 composition). The only faked
surfaces are the external/non-deterministic ports (Pillar 3): the heavy
arch-invariant runner (``_run_arch_invariant_set``, monkeypatched to a
recording stub -- the AT observes exactly what scope was selected without
ever spawning pytest, let alone the 646-test tree), the resource readings,
and the poll sleep. ``repo`` is a real ``tmp_path`` carrying a real
``tests/build`` directory with real files (real-IO for the reads
``_arch_invariant_paths`` / the scope resolver perform).

CONTRACT_SHAPE: bounded-change for every scenario -- ``build_tier_exit_verdict``
maps a bounded set of inputs (scope kwargs, resource readings, arch-run
outcome) to one of a closed set of verdicts, plus the bounded side-effect of
WHICH paths it hands to the arch-invariant runner.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from des.cli import run_contract_gate
from des.cli.run_contract_gate import _ArchVerdict, build_tier_exit_verdict
from des.testing.output_capture import CapturingOutput


# WHY -- a single fine reading (well above the 700 MiB / load1 design default)
# so tests NOT exercising the pre-launch window never trigger a wait as a side
# effect (mirrors the C3 precedent's ``_FINE_READING``).
_FINE_READING = (900, 1.0)

_MISSING_FUNCTIONALITY_MESSAGE = (
    "MISSING_FUNCTIONALITY: build_tier_exit_verdict(repo, ...) does not yet "
    "accept the regression_test_file=/light_invariant_paths=/full= keyword "
    "arguments (feature-delta slice-01, "
    "docs/feature/scoped-per-slice-build-tier/feature-delta.md "
    "[REF] Architecture & Contract). Extend its signature keyword-only "
    "(ADD-not-mutate -- existing callers, incl. today's zero-new-kwarg "
    "commit_slice.py call site, stay untouched): "
    "regression_test_file: Path | None = None (the entering slice's declared "
    "regression test; given + full is not True -> SCOPED run); "
    "light_invariant_paths: Sequence[Path] | None = None (the light "
    "always-on invariant set; None in scoped mode defaults to an internal "
    "_light_invariant_paths(repo) resolver); "
    "full: bool = False (True forces the WHOLE tests/build/** tree, "
    "overriding any scope -- the feature-end/--full/CI path). "
    "Scope resolution: full=True OR neither scope kwarg given -> whole tree "
    "(_arch_invariant_paths(repo), unchanged); otherwise -> arch_paths = "
    "[regression_test_file, *light_invariant_paths], with a LOUD event "
    "(naming 'feature-end') emitted BEFORE the run -- the whole-tree tier is "
    "deferred, never silently narrowed. "
    "Re-check with: uv run pytest "
    "tests/build/scoped_per_slice_build_tier/acceptance/"
    "test_scoped_build_tier.py -q"
)


@dataclass(frozen=True)
class _ScopedRun:
    """The observable outcome of driving ``build_tier_exit_verdict`` once."""

    exit_code: int
    events: list[dict[str, object]] = field(default_factory=list)
    sleep_calls: list[float] = field(default_factory=list)
    arch_paths_calls: list[list[Path]] = field(default_factory=list)

    def event_names(self) -> list[object]:
        return [event.get("event") for event in self.events]


@dataclass(frozen=True)
class _SliceScopeRepo:
    """A hermetic ``tests/build`` layout carrying a slice test + poison files."""

    root: Path
    regression_test_file: Path
    light_invariant_paths: list[Path]
    future_slice_at: Path


def _write_test(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


_PASSING_TEST = (
    "import pytest\npytestmark = pytest.mark.unit\n\n"
    "def test_behaviour():\n    assert True\n"
)

# A future-slice active-RED AT: on-disk, deliberately failing (impl missing) --
# the exact poison shape the feature-delta names ("a future-slice active-RED
# AT... fails the CURRENT slice's seal"). The scoped tier must never select it.
_FUTURE_SLICE_ACTIVE_RED_TEST = (
    "import pytest\npytestmark = pytest.mark.unit\n\n"
    "def test_future_slice_behaviour():\n"
    '    raise AssertionError("future-slice active-RED: not implemented yet")\n'
)


@pytest.fixture
def repo_with_slice_scope(tmp_path: Path) -> _SliceScopeRepo:
    """A repo carrying the entering slice's test + an unrelated poison AT."""
    build_dir = tmp_path / "tests" / "build"
    build_dir.mkdir(parents=True)
    (build_dir / "__init__.py").touch()

    regression_test_file = build_dir / "slice_01" / "test_regression.py"
    _write_test(regression_test_file, _PASSING_TEST)

    light_invariant = build_dir / "test_catalog_coherence.py"
    _write_test(light_invariant, _PASSING_TEST)

    future_slice_at = build_dir / "slice_02" / "test_future_slice_active_red.py"
    _write_test(future_slice_at, _FUTURE_SLICE_ACTIVE_RED_TEST)

    return _SliceScopeRepo(
        root=tmp_path,
        regression_test_file=regression_test_file,
        light_invariant_paths=[light_invariant],
        future_slice_at=future_slice_at,
    )


def _drive_gate(
    repo: Path,
    *,
    regression_test_file: Path | None,
    light_invariant_paths: Sequence[Path] | None,
    full: bool,
    resource_readings: Iterable[tuple[int, float]],
    arch_verdict: _ArchVerdict,
    monkeypatch: pytest.MonkeyPatch,
) -> _ScopedRun:
    """Drive the REAL ``build_tier_exit_verdict(repo, ...)`` composition root.

    Fakes exactly the external/non-deterministic ports (Pillar 3): the
    arch-invariant runner (``_run_arch_invariant_set``, monkeypatched to a
    recording stub -- never a real pytest spawn, let alone the 646-test
    tree), the resource readings, and the poll sleep. Everything else is the
    real gate logic. Records every ``arch_paths`` the runner was asked to
    target -- the observable this AT set pins.
    """
    output = CapturingOutput()
    arch_calls: list[list[Path]] = []

    def _fake_run_arch_invariant_set(
        repo_arg: Path, arch_paths: list[Path]
    ) -> _ArchVerdict:
        arch_calls.append(list(arch_paths))
        return arch_verdict

    monkeypatch.setattr(
        run_contract_gate, "_run_arch_invariant_set", _fake_run_arch_invariant_set
    )
    sleep_calls: list[float] = []
    try:
        exit_code = build_tier_exit_verdict(
            repo,
            output=output,
            resource_readings=iter(resource_readings),
            sleep_fn=sleep_calls.append,
            regression_test_file=regression_test_file,
            light_invariant_paths=light_invariant_paths,
            full=full,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        raise AssertionError(_MISSING_FUNCTIONALITY_MESSAGE) from exc
    events = [json.loads(line) for line in output.lines]
    return _ScopedRun(
        exit_code=exit_code,
        events=events,
        sleep_calls=sleep_calls,
        arch_paths_calls=arch_calls,
    )


# ---------------------------------------------------------------------------
# T1 -- the scoped run targets ONLY the entering slice's regression test + the
# light always-on invariants, never the whole tests/build tree.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def _covers_whole_tier(selected: set[Path], whole_tree: Path) -> tuple[set, set]:
    """Return (uncovered, outside) for a whole-tree selection.

    The whole-tree contract is the tier's COVERAGE, not its argv SHAPE. Since
    da64aba54 the resolver hands back the tier's filtered MEMBERS rather than
    the bare directory, so that a feature-slug-nested acceptance scaffold can be
    pruned. Pinning the single-directory form would forbid that fix; pinning
    coverage-and-confinement does not, and the confinement leg is STRONGER than
    the equality it replaces -- `== {whole_tree}` could not tell a widening to
    the repo root from a legitimate member list.
    """
    tier_files = {
        path
        for path in whole_tree.rglob("test_*.py")
        if "__pycache__" not in path.parts
    }
    uncovered = {
        path
        for path in tier_files
        if not any(path == s or path.is_relative_to(s) for s in selected)
    }
    outside = {
        path
        for path in selected
        if path != whole_tree and not path.is_relative_to(whole_tree)
    }
    return uncovered, outside


def test_scoped_run_selects_only_slice_test_and_light_invariants_not_whole_tree(
    monkeypatch: pytest.MonkeyPatch, repo_with_slice_scope: _SliceScopeRepo
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract ("it runs (a)
    the entering slice's declared regression test file(s) + (b) a LIGHT
    always-on invariant set... NOT the full tests/build/**").
    """
    run = _drive_gate(
        repo_with_slice_scope.root,
        regression_test_file=repo_with_slice_scope.regression_test_file,
        light_invariant_paths=repo_with_slice_scope.light_invariant_paths,
        full=False,
        resource_readings=[_FINE_READING],
        arch_verdict=_ArchVerdict(collected=2, passed=True, failed_node_ids=()),
        monkeypatch=monkeypatch,
    )

    assert run.arch_paths_calls, (
        "the scoped tier must invoke the arch-invariant runner exactly once"
    )
    selected = {Path(p) for p in run.arch_paths_calls[-1]}
    expected = {
        repo_with_slice_scope.regression_test_file,
        *repo_with_slice_scope.light_invariant_paths,
    }
    assert selected == expected, (
        f"the scoped per-slice tier must target ONLY the entering slice's "
        f"regression test + the light always-on invariants -- expected "
        f"{expected}, got {selected}"
    )
    whole_tree = repo_with_slice_scope.root / "tests" / "build"
    assert whole_tree not in selected, (
        f"the scoped tier must NEVER pass the bare whole-tree tests/build "
        f"directory as its target (that would re-collect 600+ tests) -- got "
        f"{selected}"
    )
    assert repo_with_slice_scope.future_slice_at not in selected, (
        f"the scoped tier must not sweep in the unrelated future-slice AT "
        f"{repo_with_slice_scope.future_slice_at} -- got {selected}"
    )
    assert run.exit_code == 0, f"expected exit 0 -- got {run.exit_code}"


# ---------------------------------------------------------------------------
# T2 (negative_at) -- a future-slice active-RED AT elsewhere under
# tests/build/** must NEVER fail the current scoped seal (poison dissolved).
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_scoped_seal_does_not_fail_on_unrelated_future_slice_at(
    monkeypatch: pytest.MonkeyPatch, repo_with_slice_scope: _SliceScopeRepo
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Negative AT (GS-8): ``repo_with_slice_scope`` plants a genuinely-failing
    future-slice AT ON DISK (simulating an active-RED scenario of a slice not
    yet entered). Because the scoped tier never selects it (T1), it must
    never surface through the current seal's verdict.

    Outcome anchor: feature-delta Summary ("Poison dissolved: because the
    per-slice tier no longer sweeps unrelated tests/build/** files, a
    future-slice active-RED AT... no longer fails the current seal").
    """
    run = _drive_gate(
        repo_with_slice_scope.root,
        regression_test_file=repo_with_slice_scope.regression_test_file,
        light_invariant_paths=repo_with_slice_scope.light_invariant_paths,
        full=False,
        resource_readings=[_FINE_READING],
        arch_verdict=_ArchVerdict(collected=2, passed=True, failed_node_ids=()),
        monkeypatch=monkeypatch,
    )

    assert run.exit_code == 0, (
        f"a future-slice active-RED AT elsewhere under tests/build/** must "
        f"NEVER fail the current scoped seal -- got exit {run.exit_code}, "
        f"events={run.events}"
    )
    assert "BuildTierRefused" not in run.event_names(), (
        f"the future-slice AT's on-disk failure must never surface through "
        f"the BuildTierRefused lane once the scoped tier stops selecting it "
        f"-- got events={run.events}"
    )


# ---------------------------------------------------------------------------
# T3 -- the scoped seal LOUDLY logs that the whole-tree tier is deferred to
# feature-end -- never silently narrowed.
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_scoped_seal_logs_loud_deferral_of_whole_tree_run_to_feature_end(
    monkeypatch: pytest.MonkeyPatch, repo_with_slice_scope: _SliceScopeRepo
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract ("a
    deliberate, LOUD trade: log at the per-slice seal that the whole-tree
    tier is deferred to feature-end (never silently narrowed)").
    """
    run = _drive_gate(
        repo_with_slice_scope.root,
        regression_test_file=repo_with_slice_scope.regression_test_file,
        light_invariant_paths=repo_with_slice_scope.light_invariant_paths,
        full=False,
        resource_readings=[_FINE_READING],
        arch_verdict=_ArchVerdict(collected=2, passed=True, failed_node_ids=()),
        monkeypatch=monkeypatch,
    )

    deferral_events = [
        event
        for event in run.events
        if "defer" in str(event.get("event", "")).lower()
        or "defer" in json.dumps(event).lower()
    ]
    assert deferral_events, (
        f"the scoped seal must LOUDLY log that the whole-tree tests/build/** "
        f"tier is deferred (never silently narrowed) -- got "
        f"events={run.events}"
    )
    blob = json.dumps(deferral_events[0]).lower()
    assert "feature-end" in blob, (
        f"the deferral record must name feature-end as where the whole-tree "
        f"run moves to -- got {deferral_events[0]}"
    )


# ---------------------------------------------------------------------------
# T4 -- full=True forces the WHOLE tests/build tree, overriding any scope --
# the feature-end / --full / CI floor stays byte-for-byte unchanged.
# CONTRACT_SHAPE: bounded-change (invariant guard)
# ---------------------------------------------------------------------------


def test_full_mode_still_selects_whole_tree_overriding_any_scope(
    monkeypatch: pytest.MonkeyPatch, repo_with_slice_scope: _SliceScopeRepo
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta Summary + [REF] Architecture & Contract
    ("Backward-compatible + additive: the scoped path is the new per-slice
    default; the whole-tree invocation (feature-end / --full / CI) is
    unchanged byte-for-byte.").
    """
    run = _drive_gate(
        repo_with_slice_scope.root,
        regression_test_file=repo_with_slice_scope.regression_test_file,
        light_invariant_paths=repo_with_slice_scope.light_invariant_paths,
        full=True,
        resource_readings=[_FINE_READING],
        arch_verdict=_ArchVerdict(collected=40, passed=True, failed_node_ids=()),
        monkeypatch=monkeypatch,
    )

    assert run.arch_paths_calls, (
        "the whole-tree run must invoke the arch-invariant runner exactly once"
    )
    selected = {Path(p) for p in run.arch_paths_calls[-1]}
    whole_tree = repo_with_slice_scope.root / "tests" / "build"
    uncovered, outside = _covers_whole_tier(selected, whole_tree)
    assert not uncovered, (
        "full=True must select the WHOLE tests/build tier, overriding any "
        f"regression_test_file/light_invariant_paths scope -- uncovered="
        f"{uncovered}, selected={selected}"
    )
    assert not outside, (
        "full=True must stay CONFINED to the tests/build tier -- it must never "
        f"widen beyond {whole_tree}; outside={outside}, selected={selected}"
    )
    assert run.exit_code == 0, f"expected exit 0 -- got {run.exit_code}"


# ---------------------------------------------------------------------------
# T5 -- a caller passing NONE of the new keywords (today's commit_slice.py
# shape) sees the SAME whole-tree selection as before this feature -- zero
# behaviour change (byte-for-byte backward compat). This test is GREEN today
# by design: it exercises only the ALREADY-EXISTING signature.
# CONTRACT_SHAPE: bounded-change (invariant guard)
# ---------------------------------------------------------------------------


def test_default_call_with_no_new_kwargs_preserves_whole_tree_selection(
    monkeypatch: pytest.MonkeyPatch, repo_with_slice_scope: _SliceScopeRepo
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta Reuse Analysis ("Add a per-slice scope
    selector; the whole-tree path is retained for feature-end/--full. A
    second runner would fork the seal path.") -- a caller adopting none of
    the new keywords must see zero drift.
    """
    output = CapturingOutput()
    arch_calls: list[list[Path]] = []

    def _fake_run_arch_invariant_set(
        repo_arg: Path, arch_paths: list[Path]
    ) -> _ArchVerdict:
        arch_calls.append(list(arch_paths))
        return _ArchVerdict(collected=40, passed=True, failed_node_ids=())

    monkeypatch.setattr(
        run_contract_gate, "_run_arch_invariant_set", _fake_run_arch_invariant_set
    )

    exit_code = build_tier_exit_verdict(
        repo_with_slice_scope.root,
        output=output,
        resource_readings=iter([_FINE_READING]),
        sleep_fn=lambda _seconds: None,
    )

    assert exit_code == 0, f"expected exit 0 -- got {exit_code}"
    assert arch_calls, "the default call must still invoke the arch-invariant runner"
    whole_tree = repo_with_slice_scope.root / "tests" / "build"
    default_selected = {Path(p) for p in arch_calls[-1]}
    uncovered, outside = _covers_whole_tier(default_selected, whole_tree)
    assert not uncovered and not outside, (
        "a caller using none of the new scope kwargs must still see the WHOLE "
        f"tier, confined to it -- uncovered={uncovered}, outside={outside}, "
        f"got {arch_calls[-1]}"
    )


# ---------------------------------------------------------------------------
# T6 -- C3 composition: the pre-launch resource-aware window still gates the
# SCOPED run (window-then-scoped-run).
# CONTRACT_SHAPE: bounded-change
# ---------------------------------------------------------------------------


def test_resource_window_gates_the_scoped_run_before_launch(
    monkeypatch: pytest.MonkeyPatch, repo_with_slice_scope: _SliceScopeRepo
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: feature-delta [REF] Architecture & Contract ("C3's
    resource-aware window (build_tier_exit_verdict resource_readings/
    sleep_fn kwargs, committed 47b3fd716) is preserved and composes with the
    scoping (window-then-scoped-run).").
    """
    readings = [(500, 5.0), (500, 5.0), (900, 1.0)]  # two below, then healthy
    run = _drive_gate(
        repo_with_slice_scope.root,
        regression_test_file=repo_with_slice_scope.regression_test_file,
        light_invariant_paths=repo_with_slice_scope.light_invariant_paths,
        full=False,
        resource_readings=readings,
        arch_verdict=_ArchVerdict(collected=2, passed=True, failed_node_ids=()),
        monkeypatch=monkeypatch,
    )

    assert len(run.sleep_calls) >= 2, (
        f"two below-threshold readings must still trigger the C3 wait-and-"
        f"poll loop BEFORE the scoped run launches -- expected >= 2 sleep "
        f"call(s), got {len(run.sleep_calls)}"
    )
    assert len(run.arch_paths_calls) == 1, (
        f"the scoped run must launch exactly once, AFTER the resource window "
        f"opens -- got {len(run.arch_paths_calls)} call(s)"
    )
    selected = {Path(p) for p in run.arch_paths_calls[0]}
    expected = {
        repo_with_slice_scope.regression_test_file,
        *repo_with_slice_scope.light_invariant_paths,
    }
    assert selected == expected, (
        f"the post-window run must still be the SCOPED selection, not the "
        f"whole tree -- expected {expected}, got {selected}"
    )
    assert run.exit_code == 0, f"expected exit 0 -- got {run.exit_code}"
