"""Step definitions: the slice-04 path-genericity ATs driven IN-PROCESS.

at-in-process-port-default slice-04 (DISCUSS slice-04 Metà-B, the generic-to-target-
machine mandate applied to the AXIS-B levers' scan roots: DISCOVER the target's source
+ tests directories instead of assuming nWave's ``tests/`` + ``src/des``; degrade LOUD
when the layout cannot be resolved). DESIGN DDD-4 (pure resolvers) + DDD-9 (git-free,
degrade-LOUD) on the PATH axis.

Layer 3 (in-process composition acceptance). Example-only, no PBT machinery (Mandate
9/11): each scenario pins a single closed observable (the resolved roots / the
degrade-LOUD reason). The sad path (unresolvable layout) is enumerated explicitly
(Mandate 11), never PBT-generated.

The levers are driven through the REAL gate ``main(argv)`` entry IN-PROCESS (a direct
call --- NO ``subprocess.run([sys.executable, ...])`` fork). This honours THIS feature's
own Locked Decision (subprocess reserved for @walking_skeleton); none of these scenarios
is @walking_skeleton, so none forks.

Step bodies delegate to ``PathGenericityComposition``; no inline business logic
(Mandate-12 criterion 3) --- each body is a typed accessor plus a composition call.

active-RED scaffold (atdd_pure --- NOT @skip). At HEAD ``axis_b_levers.py`` HARDCODES
``_TESTS`` / ``_SRC_DES`` and exposes no layout-discovery surface (no ``--source-dir`` /
``--tests-dir`` argv, no pyproject-testpaths / .nwave resolution), so the levers scan the
host nWave layout, never the target's ``spec/`` / ``lib/``. So every observable assertion
RED-fails for the right reason (no resolved-roots record / host-layout fallback / no
degrade-LOUD reason). DELIVER ships the path-discovery to turn these GREEN. Collection
imports ONLY the stable ``main`` entry (present) --- the absent resolver names appear
nowhere at module top, so the suite COLLECTS cleanly (DESIGN P1).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_04 import PathGenericityComposition
from .domain_types_slice_04 import LayoutResolution


scenarios("../slice-04-path-genericity.feature")


@pytest.fixture
def layout() -> PathGenericityComposition:
    """Production-wired composition root driving the real readiness gate in-process."""
    return PathGenericityComposition()


# --- Given --------------------------------------------------------------------


@given(
    parsers.parse(
        'a target project whose tests live in "{tests_dir}" and whose source '
        'lives in "{source_dir}"'
    )
)
def given_non_standard_layout(
    layout: PathGenericityComposition,
    tmp_path: Path,
    tests_dir: str,
    source_dir: str,
) -> None:
    layout.given_non_standard_layout(tmp_path, tests_dir, source_dir)


@given(
    "the target project declares its layout with explicit source and tests arguments"
)
def given_declared_via_args(layout: PathGenericityComposition) -> None:
    layout.given_declared_via_explicit_args()


@given("the target project declares its tests root in pyproject testpaths")
def given_declared_via_testpaths(layout: PathGenericityComposition) -> None:
    layout.given_declared_via_pyproject_testpaths()


@given("a target project with no conventional layout and no layout configuration")
def given_unresolvable(layout: PathGenericityComposition, tmp_path: Path) -> None:
    layout.given_unresolvable_layout(tmp_path)


# --- When: drive the REAL readiness gate IN-PROCESS ---------------------------


@when(
    "the maintainer drives the readiness levers against the target project in-process"
)
def when_drive_levers(layout: PathGenericityComposition) -> None:
    layout.drive_levers()


# --- Then: happy path -- discovery resolves the non-standard roots -------------


@then(
    parsers.parse(
        'the levers resolve the target tests root to its "{tests_dir}" directory'
    )
)
def then_resolve_tests_root(layout: PathGenericityComposition, tests_dir: str) -> None:
    obs = layout.observable()
    assert obs.resolved_tests_root and tests_dir in obs.resolved_tests_root, (
        "the levers must RESOLVE the target's tests root to its "
        f"`{tests_dir}/` directory (not assume nWave's `tests/`) --- but at HEAD "
        "`axis_b_levers.py` hardcodes `_TESTS = _REPO_ROOT / 'tests'` and the gate "
        "emits no `layout` record, so no resolved tests root is surfaced. "
        f"{layout.diag()}"
    )


@then(
    parsers.parse(
        'the levers resolve the target source root to its "{source_dir}" directory'
    )
)
def then_resolve_source_root(
    layout: PathGenericityComposition, source_dir: str
) -> None:
    obs = layout.observable()
    assert obs.resolved_source_root and source_dir in obs.resolved_source_root, (
        "the levers must RESOLVE the target's source root to its "
        f"`{source_dir}/` directory (not assume nWave's `src/des`) --- but at HEAD "
        "`axis_b_levers.py` hardcodes `_SRC_DES = _REPO_ROOT / 'src' / 'des'` and the "
        "gate emits no `layout` record, so no resolved source root is surfaced. "
        f"{layout.diag()}"
    )


@then("the levers scan the target project layout, not the host nwave layout")
def then_scan_target_not_host(layout: PathGenericityComposition) -> None:
    obs = layout.observable()
    assert (
        obs.resolution is LayoutResolution.RESOLVED and not obs.scanned_host_layout
    ), (
        "the levers must scan the TARGET project's resolved roots, not fall back to "
        "the host nWave `tests/` / `src/des` (the hardcoded-globals defect) --- but at "
        "HEAD the levers read the module-level `_TESTS` / `_SRC_DES`, so they scan the "
        f"host layout regardless of the target. {layout.diag()}"
    )


# --- Then: shared -- in-process, no fork --------------------------------------


@then("the levers drove the gate without forking an interpreter")
def then_no_fork(layout: PathGenericityComposition) -> None:
    obs = layout.observable()
    assert not obs.forked_interpreter, (
        "the levers must drive the gate `main(argv)` IN-PROCESS with no interpreter "
        "fork (this feature's own dog food) --- a forked observable means the AT "
        f"regressed to subprocess-e2e. {layout.diag()}"
    )


# --- Then: sad path -- degrade LOUD when the layout cannot be resolved ----------


@then("the levers report the layout as not resolvable with a named reason")
def then_not_resolvable_named_reason(layout: PathGenericityComposition) -> None:
    obs = layout.observable()
    assert (
        obs.resolution is LayoutResolution.NOT_RESOLVABLE and obs.not_resolvable_reason
    ), (
        "the levers must DEGRADE LOUD when the target layout cannot be resolved "
        "(NOT_APPLICABLE / INDETERMINATE with a NAMED reason) --- but at HEAD "
        "`axis_b_levers.py` has no discovery surface, so it silently scans the host "
        "globals and emits no `not-resolvable` reason. "
        f"{layout.diag()}"
    )


@then("the levers do not raise a false pass on a wrong or empty directory")
def then_no_false_pass(layout: PathGenericityComposition) -> None:
    obs = layout.observable()
    assert obs.resolution is not LayoutResolution.RESOLVED, (
        "the levers must NEVER report `resolved` on a wrong/empty directory when the "
        "target layout cannot be resolved (a false-PASS hides the genericity defect) "
        "--- but at HEAD the hardcoded globals make every run scan the host layout, "
        f"which a naive check could read as a (wrong) pass. {layout.diag()}"
    )


@then("the levers do not crash on the unresolvable layout")
def then_no_crash(layout: PathGenericityComposition) -> None:
    obs = layout.observable()
    assert not obs.crashed, (
        "the levers must NOT crash on a layout that is not nWave's (degrade-LOUD, a "
        "verdict not an unhandled exception) --- but at HEAD scanning an absent "
        "`tests/` / `src/des` on a bare target can raise instead of returning a "
        f"named NOT_APPLICABLE. {layout.diag()}"
    )
