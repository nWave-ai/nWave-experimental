"""Regression AT: the arch tier is selected by ASSERTION, not by directory LOCATION.

Bug (human report, verbatim): "arch tier selected by location not by
assertion: tests/build/ returned whole by _arch_invariant_paths, so an
undelivered feature's active-RED acceptance scaffold vetoes every slice
commit tree-wide".

`_arch_invariant_paths` (`src/des/cli/run_contract_gate.py:593`) returns the
ENTIRE `tests/build` directory. `tests/build/` also holds ~16 in-flight
FEATURE acceptance suites nested at `tests/build/<feature-slug>/acceptance/**`
alongside the genuine architecture-boundary scanners (`test_des_no_dev_root_
imports.py`, `test_no_inline_interpreter_spawn.py`, ...). The feature-scoped
leg of `des commit-slice` (`_mode_feature_scoped`) collects-AND-RUNS
EVERYTHING `_arch_invariant_paths` returns.

Measured scope of the veto (two concrete commits, both touching NOTHING under
`tests/build/`, one ATTESTED and one REFUSED): the red vetoes the
ATTESTATION of every GHERKIN (feature) slice, tree-wide, REGARDLESS of what
that slice touches -- a docs-only feature slice is refused just the same.
`pytest-regression` / `native-regression` bugfix slices are EXEMPT, because
`--at-kind pytest-regression` replaces the feature-scoped contract gate with
a behavioral attestation that never reaches the arch tier
(`verify_slice_commit_completeness.py:301-303`, `:1383-1390`). The defect is
therefore SHARPER than "everything is broken": the selection-by-location is
wrong in exactly the way that denies attestation to every unrelated FEATURE
slice on account of an unrelated feature's correct active-RED.

RCA (peer-verified): docs/feature/fix-arch-tier-selected-by-assertion/deliver/rca.md
Charter (value-side oracle): docs/product/expectations/fix-arch-tier-selected-by-assertion/
    a-developer-commits-a-clean-slice-without-being-blocked-by-anothers-known-failure.md

Three directions, ALL must hold simultaneously or the fix is unproven:
  A -- a genuine, flat, top-level `tests/build/` architecture invariant that
       FAILS at run-time must still REFUSE the slice (the tier must not
       become decorative -- a fix that simply returns an empty arch set would
       satisfy direction B alone and be indistinguishable from a working fix).
  B -- an undelivered feature's active-RED acceptance scaffold nested at
       `tests/build/<feature>/acceptance/**` must NOT veto an unrelated slice
       (the defect this AT is written to catch).
  C -- when the gate DOES refuse (GDP-3), the refusal must NAME the failing
       test/assertion -- not a fixed, generic string. `_ArchVerdict.
       failed_node_ids` (`run_contract_gate.py:585`) already carries this;
       `_mode_feature_scoped`'s refusal site (`:3389-3396`) never reads it
       into the emitted payload -- a wiring gap, not new machinery.

Driving port (Mandate-13, Layer-3 subprocess black-box): the real
`des run-contract-gate --feature-id <f> --entering-slice <s>` CLI, spawned as
a subprocess against SYNTHETIC `tmp_path` fixture repos -- NEVER this repo's
own, ever-changing `tests/build/` (that would couple this AT to other
features' in-flight red/green state and make it flaky by construction). No
production gate symbol (`_arch_invariant_paths`, `_mode_feature_scoped`,
`_ArchVerdict`) is imported.

Reuses the synthetic-flat-fixture technique of the shipped
`tests/des/acceptance/r3_gate_non_vacuity_build_tier/steps/composition_slice_01.py`
(`_write_clean_arch_tier` / `_write_broken_arch_tier`, lines 217/261/286/311)
rather than inventing a new fixture shape.

This AT does NOT touch, skip, or weaken any other feature's test -- in
particular `tests/build/gate_scope_digest_runner_agnostic/acceptance/
test_gate_scope_digest_cargo.py`, which is correctly RED and doing its job.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from des.runtime.interpreter import python_for


# EXIT-CODE-EXACT (verified-from-source, `_mode_feature_scoped`): 0 -> CLEARED
# (`FeatureScopeCleared`); 2 -> REFUSED (`FeatureScopeMalformed`, the
# non-vacuity floor OR the keystone `arch-invariant-failed`).
_GATE_CLEAR_EXIT = 0
_GATE_REFUSE_EXIT = 2

_FEATURE_SCOPE_CLEARED_EVENT = "FeatureScopeCleared"
_FEATURE_SCOPE_MALFORMED_EVENT = "FeatureScopeMalformed"
_ARCH_INVARIANT_FAILED_REASON = "arch-invariant-failed"

# The developer's own, unrelated feature id/slice (Developer A / B in the
# charter). Distinct from any real feature id in this repo -- the SUT never
# resolves this AT's own `.feature` file (plane separation).
_DEVELOPER_FEATURE_ID = "developer-clean-slice-probe"
_DEVELOPER_SLICE = "slice-01"

# The OTHER, undelivered feature whose scaffold must not colonize the arch
# tier -- filed as a feature-slug subdirectory of tests/build/, mirroring the
# RCA's real colonizing shape (e.g. gate_scope_digest_runner_agnostic).
_OTHER_UNDELIVERED_FEATURE_SLUG = "some_other_undelivered_feature"

_SUBPROCESS_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class GateRun:
    """The observable outcome of one `des run-contract-gate --feature-id` run."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def verdict_payload(self) -> dict[str, object]:
        """The single-line JSON verdict object on stdout.

        The SUT may emit a freshness-autoskip health line before the verdict
        (never after); this returns the LAST payload whose `event` is a known
        feature-scope verdict, ignoring health chatter -- same discipline as
        the shipped `r3_gate_non_vacuity_build_tier` composition root.
        """
        found: dict[str, object] = {}
        for line in self.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            event = payload.get("event")
            if event in (
                _FEATURE_SCOPE_CLEARED_EVENT,
                _FEATURE_SCOPE_MALFORMED_EVENT,
            ):
                found = payload
        return found


# --- synthetic fixture builders (filesystem only, no git) ------------------


def _write_pyproject(root: Path) -> None:
    """The minimal pytest config so collection over the synthetic repo works."""
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nmarkers = ["unit", "integration", "acceptance"]\n'
    )


def _write_clean_developer_scope(root: Path) -> None:
    """The developer's OWN slice: a clean `.feature` + a passing test.

    Filed entirely outside `tests/build/` -- an unrelated slice, per the
    charter's Developer A: "no architecture-boundary involvement at all".
    """
    scope = root / "tests" / "developer_clean_slice_probe" / "acceptance"
    scope.mkdir(parents=True, exist_ok=True)
    (scope / "clean.feature").write_text(
        f"@feature-{_DEVELOPER_FEATURE_ID}\n"
        "Feature: developer's unrelated clean slice\n"
        f"  @{_DEVELOPER_SLICE}\n"
        "  Scenario: a clean, unrelated scenario\n"
        "    Given a precondition\n"
        "    When an action occurs\n"
        "    Then an outcome is observed\n"
    )
    (scope / "test_clean.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.acceptance\n"
        "def test_developer_clean_slice_scenario():\n"
        "    assert True\n"
    )


def _write_flat_architecture_invariant(root: Path, *, passing: bool) -> Path:
    """A GENUINE architecture-boundary test at the FLAT top level of
    `tests/build/` -- never nested under any `<feature-slug>/acceptance/`
    subdirectory. Mirrors the real `test_des_no_dev_root_imports.py` shape:
    collects cleanly (imports only `pytest`), asserts at run-time (Form A,
    the scans-not-imports AST-gate class).

    Returns the file's path so callers can assert the refusal NAMES it.
    """
    build = root / "tests" / "build"
    build.mkdir(parents=True, exist_ok=True)
    path = build / "test_arch_forbidden_dev_root_import_boundary.py"
    assertion = (
        "assert True"
        if passing
        else (
            "assert False, "
            "'forbidden dev-root import in src/des: src/des/badmod/leaky.py:1 scripts'"
        )
    )
    path.write_text(
        "import pytest\n\n"
        "@pytest.mark.unit\n"
        "def test_des_has_no_forbidden_dev_root_imports():\n"
        f"    {assertion}\n"
    )
    return path


def _write_nested_undelivered_feature_scaffold(root: Path) -> Path:
    """An UNDELIVERED feature's correctly-active-RED acceptance scaffold,
    nested at `tests/build/<feature-slug>/acceptance/**` -- the RCA-confirmed
    colonizing shape (e.g.
    `tests/build/gate_scope_digest_runner_agnostic/acceptance/test_gate_scope_digest_cargo.py`).

    This RED is CORRECT, method-working-as-designed behaviour, not a defect
    to silence -- the companion test proves it stays RED and untouched.
    """
    scaffold = root / "tests" / "build" / _OTHER_UNDELIVERED_FEATURE_SLUG / "acceptance"
    scaffold.mkdir(parents=True, exist_ok=True)
    path = scaffold / "test_still_undelivered_feature.py"
    path.write_text(
        "import pytest\n\n"
        "@pytest.mark.acceptance\n"
        "def test_undelivered_feature_scenario_not_yet_implemented():\n"
        "    assert False, 'active-RED scaffold: feature not yet implemented'\n"
    )
    return path


# --- driving port: the real `des run-contract-gate` CLI subprocess ---------


def _run_gate(repo: Path, *, feature_id: str, entering_slice: str) -> GateRun:
    """Drive the REAL `des run-contract-gate --feature-id` CLI.

    Layer-3 subprocess black-box (driving-port-only boundary, Mandate-13):
    spawns the real CLI by module and observes ONLY its stdout / stderr /
    exit code. No production gate symbol is imported. Byte-identical
    invocation shape to the shipped `r3_gate_non_vacuity_build_tier` AT
    suite's `run_feature_scoped_gate` (env-parity: `NWAVE_FRESHNESS=""` +
    `PIPENV_DONT_LOAD_ENV=1` so no `.env` freshness mask can fabricate the
    verdict).
    """
    env = dict(os.environ)
    env["NWAVE_FRESHNESS"] = ""
    env["PIPENV_DONT_LOAD_ENV"] = "1"
    completed = subprocess.run(
        [
            python_for(None),
            "-m",
            "des.cli.run_contract_gate",
            "--repo",
            str(repo),
            "--feature-id",
            feature_id,
            "--entering-slice",
            entering_slice,
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )
    return GateRun(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _run_pytest_directly(repo: Path, target: Path) -> subprocess.CompletedProcess[str]:
    """Developer C's control (charter): re-inspect a specific test file
    directly, bypassing the gate entirely, to confirm its RED/GREEN status
    is unaffected by any other developer's gate run -- the pain must have
    moved off the innocent developer, never be erased from the guilty
    scaffold.
    """
    env = dict(os.environ)
    env["NWAVE_FRESHNESS"] = ""
    env["PIPENV_DONT_LOAD_ENV"] = "1"
    return subprocess.run(
        [python_for(None), "-m", "pytest", str(target), "-q", "--no-header"],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


# ---------------------------------------------------------------------------
# Direction A -- a genuine architecture invariant must still refuse the slice.
# ---------------------------------------------------------------------------


def test_genuine_architecture_invariant_still_refuses_the_slice(
    tmp_path: Path,
) -> None:
    """A REAL, run-time-failing top-level `tests/build/` invariant must still
    REFUSE the commit. Proves the fix narrows the LOCATION glob without
    switching off arch enforcement -- a fix that simply returned an empty arch
    set would satisfy Direction B alone and be indistinguishable from a
    working fix; this direction makes that outcome DETECTABLE.
    """
    _write_pyproject(tmp_path)
    _write_clean_developer_scope(tmp_path)
    _write_flat_architecture_invariant(tmp_path, passing=False)

    run = _run_gate(
        tmp_path, feature_id=_DEVELOPER_FEATURE_ID, entering_slice=_DEVELOPER_SLICE
    )

    assert run.exit_code == _GATE_REFUSE_EXIT, (
        "a genuine, run-time-failing architecture invariant at the flat top "
        "level of tests/build/ must refuse the slice (a decorative arch tier "
        f"is a regression); got exit {run.exit_code}, "
        f"stdout={run.stdout!r}, stderr={run.stderr!r}"
    )
    payload = run.verdict_payload
    assert payload.get("event") == _FEATURE_SCOPE_MALFORMED_EVENT
    assert payload.get("reason") == _ARCH_INVARIANT_FAILED_REASON


# ---------------------------------------------------------------------------
# Direction B -- an unrelated feature's active-RED scaffold must NOT veto.
# ---------------------------------------------------------------------------


def test_unrelated_feature_scaffold_no_longer_vetoes_clean_slice(
    tmp_path: Path,
) -> None:
    """The defect under fix. A DIFFERENT, undelivered feature's correctly
    active-RED acceptance scaffold, nested at
    `tests/build/<feature-slug>/acceptance/**`, must not veto a developer's
    slice that touches neither that feature nor any real architecture
    invariant.

    RED against current code: `_arch_invariant_paths` returns the WHOLE
    `tests/build` directory, so the feature-scoped leg's collect-AND-RUN
    sweeps in the nested scaffold, it fails, and the gate wrongly refuses
    (exit 2) instead of clearing (exit 0).
    """
    _write_pyproject(tmp_path)
    _write_clean_developer_scope(tmp_path)
    _write_flat_architecture_invariant(tmp_path, passing=True)
    scaffold_path = _write_nested_undelivered_feature_scaffold(tmp_path)

    run = _run_gate(
        tmp_path, feature_id=_DEVELOPER_FEATURE_ID, entering_slice=_DEVELOPER_SLICE
    )

    assert run.exit_code == _GATE_CLEAR_EXIT, (
        "an unrelated feature's active-RED acceptance scaffold nested under "
        "tests/build/<feature>/acceptance/** must not veto a clean, "
        f"unrelated slice; got exit {run.exit_code} (refused) instead of 0 "
        f"(cleared) -- location alone must never be sufficient grounds for "
        f"refusal. stdout={run.stdout!r}"
    )
    payload = run.verdict_payload
    assert payload.get("event") == _FEATURE_SCOPE_CLEARED_EVENT

    # Negative (charter): the scaffold itself must remain untouched -- still
    # collected, still genuinely RED -- after the developer's commit clears.
    # The pain must have moved OFF the innocent developer, not been silenced,
    # skipped, or erased from the guilty scaffold.
    control = _run_pytest_directly(tmp_path, scaffold_path)
    assert control.returncode != 0, (
        "the unrelated feature's scaffold must still FAIL when re-inspected "
        "directly -- it must never be silently skipped/passed/deleted as a "
        f"side effect of clearing the developer's slice; got exit "
        f"{control.returncode}, stdout={control.stdout!r}"
    )
    assert "test_undelivered_feature_scenario_not_yet_implemented" in control.stdout


# ---------------------------------------------------------------------------
# Direction C -- when the gate DOES refuse, it must name WHICH test broke.
# ---------------------------------------------------------------------------


def test_refusal_names_the_failing_invariant_not_a_generic_string(
    tmp_path: Path,
) -> None:
    """GDP-3: the refusal must be self-explaining -- WHAT failed (which test)
    and enough about its location for a developer to tell whether it is
    their own change or somebody else's known-failing work -- not merely
    THAT something failed under tests/build/**.

    `_ArchVerdict.failed_node_ids` (`run_contract_gate.py:585`) already
    carries the failing node-id(s); the defect is that
    `_mode_feature_scoped`'s refusal site (`:3389-3396`) never reads them
    into the emitted `FeatureScopeMalformed` payload -- a wiring gap, not new
    machinery.
    """
    _write_pyproject(tmp_path)
    _write_clean_developer_scope(tmp_path)
    arch_path = _write_flat_architecture_invariant(tmp_path, passing=False)

    run = _run_gate(
        tmp_path, feature_id=_DEVELOPER_FEATURE_ID, entering_slice=_DEVELOPER_SLICE
    )
    assert run.exit_code == _GATE_REFUSE_EXIT
    payload = run.verdict_payload

    # Negative: the OLD fixed refusal string, alone, does not name a specific
    # test -- a demanding tester reading only `error` cannot tell WHICH
    # assertion broke without opening a source file. This assertion
    # documents exactly what "not self-explaining" means here; if a future
    # fix instead makes the generic string carry the test name, that is also
    # an acceptable route to GDP-3 -- adjust this oracle, do not delete it.
    generic_error = str(payload.get("error", ""))
    assert arch_path.name not in generic_error, (
        "the fixed generic refusal string alone must not be treated as "
        "sufficient to name the failing test -- if it now names the file, "
        "confirm `failed_node_ids` below is redundant-but-present rather "
        "than silently dropping the structured signal"
    )

    # The proving assertion: `failed_node_ids` must be present, non-empty,
    # and must name the ACTUAL broken assertion's file -- not the whole
    # tests/build/ directory, not a bare exit code.
    failed_node_ids = payload.get("failed_node_ids")
    assert failed_node_ids, (
        "a refusal caused by a run-time architecture-invariant failure must "
        "name WHICH node-id(s) failed via `failed_node_ids` on the "
        "FeatureScopeMalformed payload -- `_ArchVerdict.failed_node_ids` "
        f"already carries this at the call site, it is simply not wired into "
        f"the emitted payload. Got payload={payload!r}"
    )
    assert any(arch_path.name in str(node_id) for node_id in failed_node_ids), (
        "the named node-id(s) must point at the ACTUAL failing architecture "
        f"test ({arch_path.name!r}), not a generic placeholder or an "
        f"unrelated node-id -- failed_node_ids={failed_node_ids!r}"
    )
