"""Feature `certification-legs-observe-real-execution`, slice-04 (DDD-CERT-5).

Value statement (feature-delta.md [REF] Slice Plan, slice-04): a crafter
committing a slice whose ``.nwave``-adjacent feature-scoped ``runner.json``
``test_command`` selector does not cover the entering slice's ``@slice-NN``
AT gets a refusal (``selector-gap``), never a silent ``FeatureScopeCleared``.
Folds backlog #99 (E2 selector-coverage gap) -- applies the pytest path's
existing M-8 tag-intersection floor (``_mode_feature_scoped``,
``run_contract_gate.py`` :2827-2868) to the cargo/runner.json path.

Found in ``src/des/cli/run_contract_gate.py::_maybe_route_through_cargo``
(:2393-2457) and ``_cargo_scope_command`` (:2344-2359): a present
``docs/feature/<feature_id>/runner.json`` ``test_command`` OVERRIDES the
convention-derived selector (``binary(/<snake_feature_id>/)``) WHOLESALE
(``read_runner_json``, ``des/adapters/driven/runner/runner_json.py`` --
the FEATURE-scoped override, distinct from the repo-level whole-tree
``.nwave/runner.json`` ``read_repo_runner_json`` consults).

TARGET-MACHINE-AGNOSTIC CONTRACT (this rework, 2026-07-14): the ORIGINAL
version of this AT pinned a dispatch-then-check design -- ``_maybe_route_
through_cargo`` ALWAYS calls ``resolution.run(command)`` (the real cargo
run-facet) FIRST, and only AFTER a passing cargo verdict does it consult
``_cargo_selector_covers_entering_slice`` (a PURELY STATIC, zero-cargo
question -- it reads ``.feature`` files via ``_feature_tag_files``/
``_slice_tags`` and string-checks the resolved command). That pinned design
is a genericity/agnosticism violation (nWave gates depend on Python ONLY;
a tool-bound step must sit behind a degrade-loud port, never gate a
pure-Python decision) AND a GDP-1 violation (intercept EARLY -- a real cargo
run is spent BEFORE the refusal that makes it moot). On a cargo-less
machine (CI/CD, a Python-only box) the selector-gap refusal was therefore
UNREACHABLE at runtime without monkeypatching the ``RunnerAdapter`` to fake
a PASS -- the ORIGINAL AT's own scaffolding was proof of the bug.

THE CORRECTED CONTRACT this AT now encodes: on a ``runner.json`` selector
that does NOT cover the entering slice, the gate refuses
(``selector-does-not-cover-entering-slice``, exit 3) **BEFORE dispatching
cargo at all** -- the cargo run-facet is NEVER invoked on the refusal path.
The static coverage check runs first (zero cargo needed); cargo is only
ever dispatched once coverage is already proven. This makes the refusal
reachable and verifiable on ANY box with only Python -- no cargo, no
``RunnerAdapter`` mock required to REACH the refusal path.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL ``des.cli.run_contract_gate.main(["--repo",
..., "--feature-id", ..., "--entering-slice", ...])`` CLI driver, run via
``run_cli_in_process`` -- the SAME in-process convention
``des_e2_contract_gate_degrade_loud``'s composition root uses for this exact
CLI. ``RunnerAdapter.run`` (the cargo run-facet's dispatch point, ``des/
ports/test_runner_port.py`` :92-123) is STILL replaced with a recording spy
in every scenario below -- but its role has changed. It no longer exists to
FORCE a passing verdict the refusal path depends on (the corrected contract
never reaches it on a refusal); it exists ONLY as hermetic test
instrumentation so:
  (a) the AT never depends on a real ``cargo`` binary being installed on
      this box (deterministic, target-machine-agnostic), and
  (b) the AT can OBSERVE dispatch count -- the positive proof that the
      refusal path never called it, and the covering/regression paths did.

Active-RED today (real assertion failures, never an import/collection
error): with production code UNCHANGED (dispatch-then-check order), a
non-covering ``runner.json`` selector still causes ``_maybe_route_through_
cargo`` to call ``resolution.run(command)`` FIRST -- the spy records ONE
call -- before the (already-correct) coverage check refuses at exit 3. The
new "the cargo run-facet must NEVER be dispatched on the refusal path"
assertion (``len(calls) == 0``) is therefore what fails today: the spy WAS
called once on the refusal path. This AT does NOT touch production code --
a crafter moves the static coverage check before the dispatch to GREEN it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process

from des.cli import run_contract_gate as gate_cli
from des.ports import test_runner_port
from des.ports.test_runner_port import RunVerdict


_FEATURE_ID = "fixture-cargo-selector-gap"
_ENTERING_SLICE = "slice-04"
_SNAKE_FEATURE_ID = _FEATURE_ID.replace("-", "_")

# ADR-GV-002-adjacent local pattern (feature-delta.md DDD-CERT-5, citing
# ``run_contract_gate.py`` :116's EXISTING ``_GATE_INDETERMINATE_EXIT_CODE``):
# the selector-gap refusal reuses this SAME local exit-3 value, never the
# generic malformed exit-2 every OTHER ``_feature_scope_malformed`` reason
# returns today.
_EXPECTED_SELECTOR_GAP_EXIT = 3
_CLEARED_EVENT = "FeatureScopeCleared"

# The convention-derived selector (``_cargo_scope_command``, zero-config, no
# ``runner.json``) targets ``binary(/<snake_feature_id>/)`` over the FULL
# snake feature-id. A ``runner.json`` override naming this SAME binary is the
# textbook covering case; an override naming something else entirely is the
# textbook gap this slice closes (#99).
_COVERING_SELECTOR = f"cargo nextest run -E binary(/{_SNAKE_FEATURE_ID}/)"
_NONCOVERING_SELECTORS = [
    "cargo nextest run -E binary(/completely_unrelated_crate/)",
    "cargo nextest run -E test(nonexistent_probe_that_never_matches)",
]
_NONCOVERING_IDS = ["unrelated-binary", "unrelated-test-filter"]


def _write_cargo_manifest(repo_root: Path) -> None:
    """A real, minimal Cargo target -- resolves the genuine ``cargo-test``
    ``RunnerAdapter`` via the filesystem lockfile scan (no mocked resolution)."""
    (repo_root / "Cargo.toml").write_text(
        '[package]\nname = "widget"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    src = repo_root / "src"
    src.mkdir(parents=True)
    (src / "main.rs").write_text("fn main() {}\n", encoding="utf-8")


def _write_entering_slice_feature_file(repo_root: Path) -> None:
    """A real ``.feature`` file self-identifying ``_FEATURE_ID`` (the
    ``@feature-`` tag ``_feature_tag_files`` resolves on) carrying the
    entering slice's ``@slice-04`` tag on its one scenario -- the AT
    ``_maybe_route_through_cargo`` must resolve (DDD-CERT-5) to determine
    whether a candidate cargo selector covers it, PURELY via filesystem
    read -- zero cargo involved. Placed under ``tests/`` so
    ``_walk_feature_files`` discovers it (not one of ``EXCLUDED_SEARCH_DIRS``).
    """
    feature_dir = repo_root / "tests" / "features" / _FEATURE_ID
    feature_dir.mkdir(parents=True)
    (feature_dir / f"{_FEATURE_ID}.feature").write_text(
        f"@feature-{_FEATURE_ID}\n"
        "Feature: fixture cargo selector coverage\n\n"
        f"  @{_ENTERING_SLICE}\n"
        "  Scenario: entering slice ships one scenario\n"
        "    Given the entering slice has exactly one scenario\n",
        encoding="utf-8",
    )


def _write_runner_json(repo_root: Path, test_command: str) -> None:
    """The FEATURE-scoped override ``read_runner_json`` reads (``docs/feature/
    <feature_id>/runner.json``) -- distinct from the repo-level whole-tree
    ``.nwave/runner.json`` ``read_repo_runner_json`` consults; ``_cargo_scope_
    command`` reads ONLY this feature-scoped file."""
    runner_json_dir = repo_root / "docs" / "feature" / _FEATURE_ID
    runner_json_dir.mkdir(parents=True, exist_ok=True)
    (runner_json_dir / "runner.json").write_text(
        json.dumps({"feature_id": _FEATURE_ID, "test_command": test_command}),
        encoding="utf-8",
    )


def _stage_fixture(repo_root: Path, test_command: str | None) -> None:
    repo_root.mkdir()
    _write_cargo_manifest(repo_root)
    _write_entering_slice_feature_file(repo_root)
    if test_command is not None:
        _write_runner_json(repo_root, test_command)


def _install_recording_cargo_spy(
    monkeypatch: pytest.MonkeyPatch, calls: list[tuple[Path, tuple[str, ...]]]
) -> None:
    """Replace ``RunnerAdapter.run`` with a recording spy that PASSES if
    called.

    Target-machine-agnostic hermetic instrumentation ONLY -- under the
    corrected contract the refusal path never reaches this spy at all (no
    real ``cargo`` binary, no mock, needed to REACH a non-covering
    refusal). It stays installed in every scenario so:
      (a) the AT is deterministic regardless of whether ``cargo`` is
          actually installed on this box, and
      (b) ``calls`` becomes the positive observable this AT asserts on --
          zero calls on the refusal path, exactly one call on a genuinely
          covering path.
    """

    def _spy_run(
        self: test_runner_port.RunnerAdapter,
        target_root: Path,
        scoped_node_ids: tuple[str, ...],
    ) -> RunVerdict:
        calls.append((target_root, scoped_node_ids))
        return RunVerdict(passed=True, runner=self.name)

    monkeypatch.setattr(test_runner_port.RunnerAdapter, "run", _spy_run)


def _drive_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    test_command: str | None,
) -> tuple[int, str, str, list[tuple[Path, tuple[str, ...]]]]:
    """Stage the fixture, drive the REAL ``des run-contract-gate`` CLI
    in-process (Layer 3 composition), and return
    ``(exit_code, stdout, stderr, cargo_run_calls)`` -- the command's real
    observables."""
    calls: list[tuple[Path, tuple[str, ...]]] = []
    _install_recording_cargo_spy(monkeypatch, calls)
    repo_root = tmp_path / "target-repo"
    _stage_fixture(repo_root, test_command)

    exit_code, stdout, stderr = run_cli_in_process(
        [
            "--repo",
            str(repo_root),
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            _ENTERING_SLICE,
        ],
        cwd=repo_root,
        main=gate_cli.main,
    )
    return exit_code, stdout, stderr, calls


def _events(stdout: str, stderr: str) -> list[dict[str, object]]:
    """Every single-line JSON event the gate emitted, across both channels."""
    records: list[dict[str, object]] = []
    for stream in (stdout, stderr):
        for line in stream.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
    return records


@pytest.mark.parametrize(
    "noncovering_selector", _NONCOVERING_SELECTORS, ids=_NONCOVERING_IDS
)
def test_runner_json_selector_gap_refuses_before_dispatching_cargo(
    noncovering_selector: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): a ``runner.json`` ``test_command`` that
    plainly does not cover the entering slice's ``@slice-04`` AT must refuse
    (exit 3, INDETERMINATE) -- and the coverage check is a PURELY STATIC,
    zero-cargo question, so the refusal must fire BEFORE the cargo run-facet
    is ever dispatched. A passing cargo run is never even attempted over
    the wrong scope; the cargo spy's call count must be ZERO on this path.
    Today ``_maybe_route_through_cargo`` dispatches cargo unconditionally
    before consulting coverage -- the spy IS called once -- so this is what
    fails.
    """
    exit_code, stdout, stderr, calls = _drive_gate(
        monkeypatch, tmp_path, test_command=noncovering_selector
    )
    events = _events(stdout, stderr)
    event_names = {str(event.get("event", "")) for event in events}

    assert exit_code == _EXPECTED_SELECTOR_GAP_EXIT, (
        f"a runner.json test_command ({noncovering_selector!r}) that does not "
        f"cover the entering slice {_ENTERING_SLICE!r}'s AT must refuse at "
        f"exit {_EXPECTED_SELECTOR_GAP_EXIT} (the local INDETERMINATE exit, "
        "DDD-CERT-5) -- a passing cargo run over the WRONG scope must never "
        f"be honored as coverage. Got exit {exit_code}, stdout={stdout!r}, "
        f"stderr={stderr!r}"
    )
    assert _CLEARED_EVENT not in event_names, (
        f"FeatureScopeCleared must NEVER be emitted while the runner.json "
        f"selector ({noncovering_selector!r}) does not exercise the entering "
        f"slice {_ENTERING_SLICE!r}'s AT -- got events: {events!r}"
    )
    combined = (json.dumps(events) + stdout + stderr).lower()
    assert "selector" in combined, (
        "the refusal must name the SELECTOR-coverage gap so a crafter knows "
        f"what to fix -- got: {combined!r}"
    )
    assert len(calls) == 0, (
        "selector coverage is a PURELY STATIC, zero-cargo question -- the "
        "cargo run-facet must NEVER be dispatched on the refusal path (this "
        "is what makes the refusal reachable/verifiable on a cargo-less, "
        f"Python-only box with no mock needed) -- got {len(calls)} call(s): "
        f"{calls!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "noncovering_selector", _NONCOVERING_SELECTORS, ids=_NONCOVERING_IDS
)
def test_runner_json_selector_gap_never_emits_feature_scope_cleared(
    noncovering_selector: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (anti-recurrence, active-RED today): given the SAME
    non-covering ``runner.json`` fixture, the gate must NEVER exit 0 and must
    NEVER emit ``FeatureScopeCleared`` -- a silent green over an unexercised
    entering-slice AT is exactly the #99 defect this slice closes. Today the
    gate DOES exactly that (by dispatching cargo, forcing a PASS via the
    recording spy, and only then refusing) -- these assertions are what fail
    while the fix is not yet moved before dispatch.
    """
    exit_code, stdout, stderr, _calls = _drive_gate(
        monkeypatch, tmp_path, test_command=noncovering_selector
    )
    events = _events(stdout, stderr)
    event_names = {str(event.get("event", "")) for event in events}

    assert exit_code != 0, (
        f"a non-covering runner.json selector ({noncovering_selector!r}) must "
        f"never exit 0: got exit {exit_code}, events={events!r}"
    )
    assert _CLEARED_EVENT not in event_names, (
        f"FeatureScopeCleared must never be emitted over a selector "
        f"({noncovering_selector!r}) that does not exercise the entering "
        f"slice {_ENTERING_SLICE!r}'s AT: {events!r}"
    )


def test_runner_json_selector_covering_entering_slice_still_clears_regression(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """REGRESSION-GUARD (COVERING control): a ``runner.json`` override naming
    the SAME binary the zero-config convention would derive (i.e. it
    genuinely covers the entering slice's feature) must still clear
    normally (exit 0, ``FeatureScopeCleared``) -- the fix must be scoped to
    the NON-covering case only, never to every ``runner.json`` override.
    Here the cargo run-facet legitimately DOES get dispatched (a covering
    selector genuinely routes to the runner), so the recording+PASS spy is
    legitimate scaffolding for this case -- unlike the refusal-path tests
    above. Already green today (pins the unchanged behaviour the fix must
    preserve).
    """
    exit_code, stdout, stderr, calls = _drive_gate(
        monkeypatch, tmp_path, test_command=_COVERING_SELECTOR
    )
    events = _events(stdout, stderr)
    event_names = {str(event.get("event", "")) for event in events}

    assert exit_code == 0, (
        f"a runner.json selector ({_COVERING_SELECTOR!r}) that DOES cover the "
        f"entering slice's own feature binary must still clear at exit 0: "
        f"got exit {exit_code}, events={events!r}"
    )
    assert _CLEARED_EVENT in event_names, (
        f"a covering runner.json override must still emit FeatureScopeCleared: "
        f"{events!r}"
    )
    assert len(calls) == 1, (
        f"the cargo run-facet must have been dispatched exactly once: {calls!r}"
    )


def test_zero_config_convention_selector_still_clears_regression(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """REGRESSION-GUARD (COVERING control): NO ``runner.json`` at all -- the
    zero-config, convention-derived selector (``binary(/<snake_feature_id>/)``)
    applies, which by construction covers the feature's own binary -- must
    still clear normally. The cargo run-facet legitimately gets dispatched
    here too (a genuinely covering, convention-derived selector). Pins the
    NORMAL, most-common zero-config path unchanged by this slice's fix.
    """
    exit_code, stdout, stderr, calls = _drive_gate(
        monkeypatch, tmp_path, test_command=None
    )
    events = _events(stdout, stderr)
    event_names = {str(event.get("event", "")) for event in events}

    assert exit_code == 0, (
        f"the zero-config convention-derived selector must still clear: got "
        f"exit {exit_code}, events={events!r}"
    )
    assert _CLEARED_EVENT in event_names, (
        f"the zero-config path must still emit FeatureScopeCleared: {events!r}"
    )
    assert len(calls) == 1, (
        f"the cargo run-facet must have been dispatched exactly once: {calls!r}"
    )
