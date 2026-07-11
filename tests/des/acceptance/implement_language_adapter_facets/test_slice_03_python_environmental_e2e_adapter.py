"""Slice-03 AT: PythonEnvironmentalE2EAdapter's 3 methods genuinely implemented.

Feature `implement-language-adapter-facets`, slice-03 (feature-delta.md Slice
Plan row 3, components D3/D4/D5). Value statement: a contributor running
`verify-environmental-e2e --mode run` against a Python feature gets routed
through a REAL ``PythonEnvironmentalE2EAdapter`` -- not a silent
fall-through to the hardcoded body -- because:

  * ``build``/``install`` are PURE COMPOSITION (has-a, not is-a -- DDD-01)
    over the EXISTING, already-proven ``BuildDistArtifactBuilder`` /
    ``PipTargetInstaller`` adapters -- zero new build/install logic here;
  * ``run_against_installed`` genuinely runs pytest against a staged prefix
    and writes JUnit XML, sharing ONE implementation with
    ``verify_environmental_e2e.py``'s own fallback path via the extracted
    ``pytest_e2e_runner.run_pytest_against_installed`` helper (D3/D4, DDD-02)
    -- this AT drives it THROUGH the adapter method, not the helper module
    directly, since the adapter method IS the port surface under test.

Driving surface (Mandate 13 / composition-contract): ``EnvironmentalE2EPort``
is a DRIVEN port (Protocol) -- ``PythonEnvironmentalE2EAdapter`` ALREADY
EXISTS in production (shipped stub from the parent feature
`unified-language-adapter-registry` slice-04, ADR-ULAR-005), so this is a
driven-ADAPTER test: the adapter is instantiated and driven DIRECTLY (Mandate
6: every driven adapter earns >=1 `@real-io` scenario), exactly the same
shape slice-01's `PythonRobustnessDensityAdapter` AT used. This is NOT a
driving-port-boundary violation (Mandate 16): the port under test here IS the
driven port, which by definition is exercised via direct adapter
instantiation.

Delegation-target fakes (Contract Shapes table, D5 `build`/`install` rows --
"bounded-change ... asserted via a 'delegates-to' unit test (mock/spy on the
composed instance)"): scenarios 1/2/5/6 below `monkeypatch.setattr` the
COMPOSED CLASS's method (`BuildDistArtifactBuilder.build` /
`PipTargetInstaller.install`) rather than injecting a fake via a constructor
parameter -- DDD-01 specifies `PythonEnvironmentalE2EAdapter.__init__`
CONSTRUCTS its own `BuildDistArtifactBuilder()`/`PipTargetInstaller()`
internally (has-a composition, no DI seam declared), so class-level
monkeypatching is the only way to observe delegation without a real
multi-minute wheel build. The crafter's real ``build``/``install`` bodies
MUST:
  * call the composed instance's method with EXACTLY the arguments the
    adapter method received (no copying, no mutation, no re-derivation);
  * return EXACTLY the delegate's return value, unchanged;
  * NEVER catch and swallow ``ArtifactBuildError``/``StagedInstallError`` --
    propagate them verbatim (scenarios 5/6).

``run_against_installed`` (scenarios 3/4) is driven for REAL: a tiny,
hermetic pytest-against-staged-prefix subprocess (one trivial test file, no
real installed package needed since the fixture test imports nothing from
`prefix`) -- genuine I/O, no fork of an external interpreter beyond the one
`des` itself already spawns for this exact purpose in production
(`_run_e2e_against_installed` / the extracted `pytest_e2e_runner`).

Active-RED today: all 3 methods are pure ``raise NotImplementedError(...)``
stubs. Every scenario below imports ONLY already-shipped production classes
(safe: no collection-time ImportError) and calls the adapter method inside
the test body; the call raises ``NotImplementedError`` before any assertion
runs, which ``des verify-red-green`` classifies as a genuine SEMANTIC failure
(named testcase, errors during its own execution -- not during collection).
Never ``@skip``/``@pytest.mark.skip`` per ADR-GV-001 D6.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

import pytest

from des.adapters.driven.build.build_dist_artifact_builder import (
    BuildDistArtifactBuilder,
)
from des.adapters.driven.e2e.python_environmental_e2e_adapter import (
    PythonEnvironmentalE2EAdapter,
)
from des.adapters.driven.install.pip_target_installer import PipTargetInstaller
from des.ports.driven_ports.artifact_builder import ArtifactBuildError
from des.ports.driven_ports.staged_installer import InstalledTree, StagedInstallError


# --- fixtures ----------------------------------------------------------------


@pytest.fixture
def adapter() -> PythonEnvironmentalE2EAdapter:
    """The real, production-composed adapter under test -- no fake, no mock."""
    return PythonEnvironmentalE2EAdapter()


def _testsuite_from_junit(junit_path: Path) -> ElementTree.Element:
    """Parse a pytest-written JUnit XML file and return its `<testsuite>` node."""
    root = ElementTree.parse(junit_path).getroot()
    testsuite = root if root.tag == "testsuite" else root.find("testsuite")
    assert testsuite is not None, f"no <testsuite> element in {junit_path}"
    return testsuite


# --- positive: build/install genuinely delegate, not re-implement ------------


def test_build_delegates_to_build_dist_artifact_builder_and_returns_its_artifact(
    adapter: PythonEnvironmentalE2EAdapter,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`build` composes `BuildDistArtifactBuilder` -- never re-implements pip wheel."""
    feature_root = tmp_path / "feature-root"
    feature_root.mkdir()
    expected_artifact = tmp_path / "dist" / "widget-1.0.0-py3-none-any.whl"
    received_feature_roots: list[Path] = []

    def _fake_build(self: BuildDistArtifactBuilder, feature_root: Path) -> Path:
        received_feature_roots.append(feature_root)
        return expected_artifact

    monkeypatch.setattr(BuildDistArtifactBuilder, "build", _fake_build)

    result = adapter.build(feature_root)

    assert result == expected_artifact, (
        "PythonEnvironmentalE2EAdapter.build must return the COMPOSED "
        f"BuildDistArtifactBuilder's own return value unchanged. Got: {result!r}"
    )
    assert received_feature_roots == [feature_root], (
        "the composed BuildDistArtifactBuilder.build must be called exactly "
        "once, with the SAME feature_root the adapter method received -- "
        f"never re-derived or mutated. Got: {received_feature_roots!r}"
    )


def test_install_delegates_to_pip_target_installer_and_returns_its_installed_tree(
    adapter: PythonEnvironmentalE2EAdapter,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`install` composes `PipTargetInstaller` -- never re-implements pip install."""
    artifact = tmp_path / "dist" / "widget-1.0.0-py3-none-any.whl"
    prefix = tmp_path / "prefix"
    expected_tree = InstalledTree(prefix=prefix, python_path=prefix)
    received_calls: list[tuple[Path, Path]] = []

    def _fake_install(
        self: PipTargetInstaller, artifact: Path, prefix: Path
    ) -> InstalledTree:
        received_calls.append((artifact, prefix))
        return expected_tree

    monkeypatch.setattr(PipTargetInstaller, "install", _fake_install)

    result = adapter.install(artifact, prefix)

    assert result == expected_tree, (
        "PythonEnvironmentalE2EAdapter.install must return the COMPOSED "
        f"PipTargetInstaller's own InstalledTree unchanged. Got: {result!r}"
    )
    assert received_calls == [(artifact, prefix)], (
        "the composed PipTargetInstaller.install must be called exactly "
        "once, with the SAME (artifact, prefix) the adapter method received "
        f"-- never re-derived or mutated. Got: {received_calls!r}"
    )


# --- positive: run_against_installed genuinely runs pytest + writes JUnit ----


def test_run_against_installed_runs_pytest_against_the_staged_prefix_and_writes_junit_xml(
    adapter: PythonEnvironmentalE2EAdapter, tmp_path: Path
) -> None:
    """A trivially-passing staged e2e test produces a real JUnit XML reporting PASS."""
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    junit_path = tmp_path / "results" / "junit.xml"
    e2e_path = tmp_path / "e2e" / "test_trivial_pass.py"
    e2e_path.parent.mkdir(parents=True, exist_ok=True)
    e2e_path.write_text(
        "def test_trivial_pass() -> None:\n    assert True\n", encoding="utf-8"
    )

    adapter.run_against_installed(e2e_path, prefix, junit_path, work_dir)

    assert junit_path.is_file(), (
        "run_against_installed must write a real JUnit XML file at "
        f"junit_path ({junit_path}) -- wrapping pytest_e2e_runner "
        "(D3) verbatim, per DDD-02."
    )
    testsuite = _testsuite_from_junit(junit_path)
    assert int(testsuite.attrib.get("tests", "0")) == 1, (
        "the JUnit XML must report exactly the 1 collected staged test. "
        f"Got attrib: {testsuite.attrib!r}"
    )
    assert int(testsuite.attrib.get("failures", "0")) == 0, (
        "a genuinely-passing staged test must report zero failures. "
        f"Got attrib: {testsuite.attrib!r}"
    )
    assert int(testsuite.attrib.get("errors", "0")) == 0, (
        "a genuinely-passing staged test must report zero errors. "
        f"Got attrib: {testsuite.attrib!r}"
    )


@pytest.mark.negative_at
def test_run_against_installed_never_reports_a_false_pass_when_the_staged_test_fails(
    adapter: PythonEnvironmentalE2EAdapter, tmp_path: Path
) -> None:
    """A genuinely-failing staged test must surface as a JUnit failure, not a silent pass."""
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    junit_path = tmp_path / "results" / "junit.xml"
    e2e_path = tmp_path / "e2e" / "test_trivial_fail.py"
    e2e_path.parent.mkdir(parents=True, exist_ok=True)
    e2e_path.write_text(
        "def test_trivial_fail() -> None:\n"
        '    assert False, "intentional failure -- proves the runner reports it honestly"\n',
        encoding="utf-8",
    )

    adapter.run_against_installed(e2e_path, prefix, junit_path, work_dir)

    assert junit_path.is_file(), (
        "run_against_installed must write JUnit XML even when the staged "
        f"test fails -- junit_path ({junit_path}) must still exist."
    )
    testsuite = _testsuite_from_junit(junit_path)
    reported_failures = int(testsuite.attrib.get("failures", "0")) + int(
        testsuite.attrib.get("errors", "0")
    )
    assert reported_failures >= 1, (
        "a staged test that genuinely fails MUST be reported as a "
        "failure/error in the written JUnit XML -- run_against_installed "
        "must NEVER report a false pass (no silent-green). "
        f"Got attrib: {testsuite.attrib!r}"
    )


# --- negative: build/install must never swallow the delegate's error ---------


@pytest.mark.negative_at
def test_build_never_swallows_artifact_build_error_from_the_delegate(
    adapter: PythonEnvironmentalE2EAdapter,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A build failure in the composed BuildDistArtifactBuilder MUST propagate."""

    def _raising_build(self: BuildDistArtifactBuilder, feature_root: Path) -> Path:
        raise ArtifactBuildError("simulated build failure")

    monkeypatch.setattr(BuildDistArtifactBuilder, "build", _raising_build)

    with pytest.raises(ArtifactBuildError):
        adapter.build(tmp_path / "feature-root")


@pytest.mark.negative_at
def test_install_never_swallows_staged_install_error_from_the_delegate(
    adapter: PythonEnvironmentalE2EAdapter,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An install failure in the composed PipTargetInstaller MUST propagate."""

    def _raising_install(
        self: PipTargetInstaller, artifact: Path, prefix: Path
    ) -> InstalledTree:
        raise StagedInstallError("simulated install failure")

    monkeypatch.setattr(PipTargetInstaller, "install", _raising_install)

    with pytest.raises(StagedInstallError):
        adapter.install(tmp_path / "artifact.whl", tmp_path / "prefix")
