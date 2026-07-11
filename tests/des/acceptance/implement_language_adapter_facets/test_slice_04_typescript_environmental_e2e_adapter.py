"""Slice-04 AT: TypeScriptEnvironmentalE2EAdapter's 3 methods genuinely implemented.

Feature `implement-language-adapter-facets`, slice-04 (feature-delta.md Slice
Plan row 4, components D6/D7/D8/D9). Value statement: a contributor running
`verify-environmental-e2e --mode run` against a TypeScript feature gets
routed through a REAL ``TypeScriptEnvironmentalE2EAdapter`` -- not a silent
fall-through to the hardcoded body -- because:

  * ``build``/``install`` are PURE COMPOSITION (has-a, not is-a -- DDD-03,
    mirrors DDD-01) over 2 NEW ``ArtifactBuilder``/``StagedInstaller``
    implementations, ``NpmPackArtifactBuilder`` (D6) / ``NpmInstallStagedInstaller``
    (D7) -- zero build/install logic inline on the adapter itself;
  * ``run_against_installed`` genuinely runs vitest against a staged install
    and writes JUnit XML via the NEW ``vitest_e2e_runner.run_vitest_against_installed``
    helper (D8), the TS mirror of D3's Python `pytest_e2e_runner`.

Driving surface (Mandate 13 / composition-contract): ``EnvironmentalE2EPort``
is a DRIVEN port (Protocol) -- ``TypeScriptEnvironmentalE2EAdapter`` ALREADY
EXISTS in production (shipped stub from the parent feature
`unified-language-adapter-registry` slice-04, ADR-ULAR-005), so this is a
driven-ADAPTER test: the adapter (and, for scenario 3, its 2 NEW composed
adapters directly) is instantiated and driven DIRECTLY (Mandate 6: every
driven adapter earns >=1 `@real-io` scenario), exactly the same shape
slice-03's Python AT used. This is NOT a driving-port-boundary violation
(Mandate 16): the port under test here IS the driven port, which by
definition is exercised via direct adapter instantiation.

Delegation-target fakes (scenarios 1/2/6/7, mirrors slice-03 exactly):
`monkeypatch.setattr` the COMPOSED CLASS's method (`NpmPackArtifactBuilder.build`
/ `NpmInstallStagedInstaller.install`) rather than injecting a fake via a
constructor parameter -- DDD-03 specifies `TypeScriptEnvironmentalE2EAdapter.__init__`
CONSTRUCTS its own `NpmPackArtifactBuilder()`/`NpmInstallStagedInstaller()`
internally (has-a composition, no DI seam declared), so class-level
monkeypatching is the only way to observe delegation without a real npm
subprocess. The crafter's real ``build``/``install`` bodies MUST:
  * call the composed instance's method with EXACTLY the arguments the
    adapter method received (no copying, no mutation, no re-derivation);
  * return EXACTLY the delegate's return value, unchanged;
  * NEVER catch and swallow ``ArtifactBuildError``/``StagedInstallError`` --
    propagate them verbatim (scenarios 6/7).

TOOLCHAIN DECISION (documented, not guessed -- empirically probed before
authoring, per the Earned-Trust principle):

  * npm/node ARE installed in this dev sandbox (`npm --version` -> 11.6.2,
    `node --version` -> v24.12.0), but the sibling feature
    `vitest_test_runner_adapter`'s own composition root documents "a real
    Node / vitest toolchain (absent in CI)" -- i.e. this repo's CI is NOT
    guaranteed to have Node. Scenario 3 below therefore does NOT hard-require
    npm: it is marked `@pytest.mark.polyglot_smoke` and SKIPS with a named
    reason when `npm` is absent from PATH -- the EXACT existing, registered
    pattern this codebase already uses 5x (`tests/polyglot-pilot/test_*_smoke.py`,
    e.g. `test_typescript_smoke.py`: "if shutil.which('npx') is None or
    shutil.which('npm') is None: pytest.skip(...)"). This is NOT the
    ADR-GV-001 D6 "@skip disguises not-yet-implemented" anti-pattern -- it is
    an environment-capability-conditional skip, orthogonal to
    implementation-completeness, already sanctioned and precedented 5x in
    this exact codebase. Empirically verified BEFORE choosing this design:
    `npm pack --pack-destination <dir>` (dir must pre-exist) and
    `npm install --no-audit --no-fund --offline --prefix <dir> <tarball>`
    both complete with ZERO network access for a dependency-free fixture
    package (probed in this session's scratchpad; offline install succeeded,
    `added 1 package in 483ms`, rc=0) -- so when npm IS present the scenario
    is genuinely hermetic (no live registry call), never flaky.
  * vitest itself is NOT installed ANYWHERE reachable in this sandbox (no
    global package, no repo `node_modules/vitest`, no cached binary) and
    installing it would require a live registry call -- unlike npm/node
    which are pre-provisioned. Scenario 4/5 (`run_against_installed`)
    therefore use a FAKE, deterministic `vitest` executable -- the IDENTICAL
    technique `vitest_test_runner_adapter`'s composition root already
    established (`_plant_fake_vitest`: a real chmod+x POSIX shell script
    planted on a controlled child PATH, resolved via the SAME production
    `resolve_tool` scale the real `vitest_e2e_runner` (D8) must use per the
    Reuse Analysis row "vitest_e2e_runner.py (D8) ... reuse the SAME
    discovery scale"). This exercises the REAL D8 helper + its REAL
    subprocess invocation + its REAL `resolve_tool` wiring end-to-end,
    deterministically, without any live toolchain -- CI-portable by
    construction, matching the sibling feature's own precedent rather than
    inventing a new technique.
  * The fake vitest is CONTENT-DRIVEN (reads the `e2e_path` test file for a
    `// FAKE_VITEST_SCENARIO: FAIL` marker) rather than argv-scenario-driven,
    mirroring exactly how the REAL Python `run_pytest_against_installed`
    scenario (slice-03) is driven by a REAL passing/failing pytest file --
    the TS fake is the smallest substitute that preserves the same
    Given-shape (a staged e2e file that genuinely passes or fails) while
    being deterministic without a real vitest binary. The fake parses
    `--outputFile=<path>` from its own argv to know where to write JUnit --
    this pins the documented, load-bearing external CLI contract D8 MUST
    invoke real vitest with (`vitest run --reporter=junit --outputFile=<path>`),
    the ONLY mechanism by which a per-call-varying `junit_path` can reach a
    real vitest subprocess (no static `vitest.config.ts` reporter path is
    viable since `junit_path` varies per call) -- this is a genuine external
    contract, not incidental internal structure (Mandate 4/1 compliant).

Active-RED today: all 3 methods on `TypeScriptEnvironmentalE2EAdapter` are
pure `raise NotImplementedError(...)` stubs (confirmed by `Read`); D6/D7/D8
(`NpmPackArtifactBuilder`, `NpmInstallStagedInstaller`, `vitest_e2e_runner`)
do not exist on disk yet -- their absence is scaffolded below
(`__SCAFFOLD__` markers, `nw-distill-red-scaffolding` Mandate 7) so every
scenario fails with a semantic `AssertionError`/`NotImplementedError` raised
INSIDE the test body (never a collection-time `ImportError`). Every scenario
below imports ONLY already-shipped or freshly-scaffolded production classes
(safe: no collection-time ImportError) and calls the adapter/component method
inside the test body. Never `@skip`/`@pytest.mark.skip` for
not-yet-implemented per ADR-GV-001 D6 -- the ONE conditional skip in this
file (scenario 3) gates on TOOLCHAIN PRESENCE, not implementation status, and
is itself unconditionally exercised (never skipped) once npm is present.
"""

from __future__ import annotations

import shutil
import stat
from pathlib import Path
from xml.etree import ElementTree

import pytest

from des.adapters.driven.build.npm_pack_artifact_builder import (
    NpmPackArtifactBuilder,
)
from des.adapters.driven.e2e.typescript_environmental_e2e_adapter import (
    TypeScriptEnvironmentalE2EAdapter,
)
from des.adapters.driven.install.npm_install_staged_installer import (
    NpmInstallStagedInstaller,
)
from des.ports.driven_ports.artifact_builder import ArtifactBuildError
from des.ports.driven_ports.staged_installer import InstalledTree, StagedInstallError


# --- fixtures ------------------------------------------------------------


@pytest.fixture
def adapter() -> TypeScriptEnvironmentalE2EAdapter:
    """The real, production-composed adapter under test -- no fake, no mock."""
    return TypeScriptEnvironmentalE2EAdapter()


def _testsuite_from_junit(junit_path: Path) -> ElementTree.Element:
    """Parse a JUnit XML file and return its `<testsuite>` node."""
    root = ElementTree.parse(junit_path).getroot()
    testsuite = root if root.tag == "testsuite" else root.find("testsuite")
    assert testsuite is not None, f"no <testsuite> element in {junit_path}"
    return testsuite


def _plant_fake_vitest(target: Path) -> None:
    """Write a REAL chmod+x fake ``vitest`` that reads its test file for a
    scenario marker and writes real JUnit XML at the CLI-declared
    ``--outputFile=<path>`` -- mirrors `vitest_test_runner_adapter`'s
    `_plant_fake_vitest` technique (a real POSIX shell script on a
    controlled PATH), content-driven instead of scenario-parameter-driven
    so it substitutes for a genuinely passing/failing vitest run.
    """
    script = r"""#!/bin/sh
OUT=""
TESTFILE=""
for a in "$@"; do
  case "$a" in
    --outputFile=*) OUT="${a#--outputFile=}" ;;
    *.test.ts) TESTFILE="$a" ;;
  esac
done
mkdir -p "$(dirname "$OUT")"
if grep -q "FAKE_VITEST_SCENARIO: FAIL" "$TESTFILE" 2>/dev/null; then
  cat > "$OUT" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
<testsuite name="fake" tests="1" failures="1" errors="0">
<testcase name="fake_test" classname="fake">
<failure message="intentional failure">simulated</failure>
</testcase>
</testsuite>
</testsuites>
XML
  exit 1
else
  cat > "$OUT" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
<testsuite name="fake" tests="1" failures="0" errors="0">
<testcase name="fake_test" classname="fake"/>
</testsuite>
</testsuites>
XML
  exit 0
fi
"""
    target.write_text(script, encoding="utf-8")
    mode = target.stat().st_mode
    target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


# --- positive: build/install genuinely delegate, not re-implement --------


def test_build_delegates_to_npm_pack_artifact_builder_and_returns_its_artifact(
    adapter: TypeScriptEnvironmentalE2EAdapter,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`build` composes `NpmPackArtifactBuilder` -- never re-implements npm pack."""
    feature_root = tmp_path / "feature-root"
    feature_root.mkdir()
    expected_artifact = tmp_path / "dist" / "widget-1.0.0.tgz"
    received_feature_roots: list[Path] = []

    def _fake_build(self: NpmPackArtifactBuilder, feature_root: Path) -> Path:
        received_feature_roots.append(feature_root)
        return expected_artifact

    monkeypatch.setattr(NpmPackArtifactBuilder, "build", _fake_build)

    result = adapter.build(feature_root)

    assert result == expected_artifact, (
        "TypeScriptEnvironmentalE2EAdapter.build must return the COMPOSED "
        f"NpmPackArtifactBuilder's own return value unchanged. Got: {result!r}"
    )
    assert received_feature_roots == [feature_root], (
        "the composed NpmPackArtifactBuilder.build must be called exactly "
        "once, with the SAME feature_root the adapter method received -- "
        f"never re-derived or mutated. Got: {received_feature_roots!r}"
    )


def test_install_delegates_to_npm_install_staged_installer_and_returns_its_installed_tree(
    adapter: TypeScriptEnvironmentalE2EAdapter,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`install` composes `NpmInstallStagedInstaller` -- never re-implements npm install."""
    artifact = tmp_path / "dist" / "widget-1.0.0.tgz"
    prefix = tmp_path / "prefix"
    expected_tree = InstalledTree(prefix=prefix, python_path=prefix)
    received_calls: list[tuple[Path, Path]] = []

    def _fake_install(
        self: NpmInstallStagedInstaller, artifact: Path, prefix: Path
    ) -> InstalledTree:
        received_calls.append((artifact, prefix))
        return expected_tree

    monkeypatch.setattr(NpmInstallStagedInstaller, "install", _fake_install)

    result = adapter.install(artifact, prefix)

    assert result == expected_tree, (
        "TypeScriptEnvironmentalE2EAdapter.install must return the COMPOSED "
        f"NpmInstallStagedInstaller's own InstalledTree unchanged. Got: {result!r}"
    )
    assert received_calls == [(artifact, prefix)], (
        "the composed NpmInstallStagedInstaller.install must be called "
        "exactly once, with the SAME (artifact, prefix) the adapter method "
        f"received -- never re-derived or mutated. Got: {received_calls!r}"
    )


# --- positive (@real-io, toolchain-conditional): D6/D7 genuine npm round-trip


@pytest.mark.polyglot_smoke
@pytest.mark.slow
def test_npm_pack_artifact_builder_and_npm_install_staged_installer_round_trip_with_real_npm(
    tmp_path: Path,
) -> None:
    """A real `npm pack` tarball is genuinely staged by a real offline `npm install`.

    Drives D6 (`NpmPackArtifactBuilder`) and D7 (`NpmInstallStagedInstaller`)
    DIRECTLY (not through the composing adapter -- these 2 components have no
    other test coverage anywhere in the codebase; Mandate 6 requires >=1
    `@real-io` scenario per driven adapter). SKIPS with a named reason when
    npm is absent from PATH -- mirrors `tests/polyglot-pilot/test_typescript_smoke.py`
    verbatim (the registered `polyglot_smoke` marker's existing convention).
    """
    if shutil.which("npm") is None:
        pytest.skip("npm not on PATH -- polyglot smoke deferred (D6/D7 real-io)")

    feature_root = tmp_path / "feature-root"
    feature_root.mkdir()
    (feature_root / "package.json").write_text(
        '{\n  "name": "nwave-fixture-pkg",\n  "version": "1.0.0",\n'
        '  "main": "index.js"\n}\n',
        encoding="utf-8",
    )
    (feature_root / "index.js").write_text("module.exports = 42;\n", encoding="utf-8")
    prefix = tmp_path / "prefix"

    artifact = NpmPackArtifactBuilder().build(feature_root)

    assert artifact.is_file() and artifact.suffix == ".tgz", (
        "NpmPackArtifactBuilder.build must produce a real .tgz artifact via "
        f"a genuine `npm pack` subprocess. Got: {artifact!r}"
    )

    installed = NpmInstallStagedInstaller().install(artifact, prefix)

    installed_pkg_json = (
        installed.prefix / "node_modules" / "nwave-fixture-pkg" / "package.json"
    )
    assert installed_pkg_json.is_file(), (
        "NpmInstallStagedInstaller.install must genuinely stage the packed "
        f"tarball into prefix/node_modules/<pkg-name>/ via a real (offline) "
        f"`npm install --prefix` subprocess. Expected file: {installed_pkg_json!r}"
    )
    assert installed.prefix == prefix, (
        "the returned InstalledTree.prefix must be the SAME prefix passed "
        f"in, never re-derived. Got: {installed.prefix!r}"
    )


# --- positive/negative: run_against_installed genuinely runs vitest ------


def test_run_against_installed_runs_vitest_against_the_staged_prefix_and_writes_junit_xml(
    adapter: TypeScriptEnvironmentalE2EAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A trivially-passing staged e2e vitest file produces a real JUnit XML reporting PASS."""
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    junit_path = tmp_path / "results" / "junit.xml"
    e2e_path = tmp_path / "e2e" / "trivial_pass.test.ts"
    e2e_path.parent.mkdir(parents=True, exist_ok=True)
    e2e_path.write_text(
        "// FAKE_VITEST_SCENARIO: PASS\n"
        "test('trivial pass', () => { expect(true).toBe(true); });\n",
        encoding="utf-8",
    )

    path_bin = tmp_path / "path-bin"
    path_bin.mkdir()
    _plant_fake_vitest(path_bin / "vitest")
    monkeypatch.setenv("PATH", str(path_bin))

    adapter.run_against_installed(e2e_path, prefix, junit_path, work_dir)

    assert junit_path.is_file(), (
        "run_against_installed must write a real JUnit XML file at "
        f"junit_path ({junit_path}) -- wrapping vitest_e2e_runner "
        "(D8) invoking `vitest run --reporter=junit --outputFile=<junit_path>`."
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
    adapter: TypeScriptEnvironmentalE2EAdapter,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A genuinely-failing staged vitest test must surface as a JUnit failure, not a silent pass."""
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    junit_path = tmp_path / "results" / "junit.xml"
    e2e_path = tmp_path / "e2e" / "trivial_fail.test.ts"
    e2e_path.parent.mkdir(parents=True, exist_ok=True)
    e2e_path.write_text(
        "// FAKE_VITEST_SCENARIO: FAIL\n"
        "test('trivial fail', () => { expect(true).toBe(false); });\n",
        encoding="utf-8",
    )

    path_bin = tmp_path / "path-bin"
    path_bin.mkdir()
    _plant_fake_vitest(path_bin / "vitest")
    monkeypatch.setenv("PATH", str(path_bin))

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


# --- negative: build/install must never swallow the delegate's error -----


@pytest.mark.negative_at
def test_build_never_swallows_artifact_build_error_from_the_delegate(
    adapter: TypeScriptEnvironmentalE2EAdapter,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A build failure in the composed NpmPackArtifactBuilder MUST propagate."""

    def _raising_build(self: NpmPackArtifactBuilder, feature_root: Path) -> Path:
        raise ArtifactBuildError("simulated npm pack failure")

    monkeypatch.setattr(NpmPackArtifactBuilder, "build", _raising_build)

    with pytest.raises(ArtifactBuildError):
        adapter.build(tmp_path / "feature-root")


@pytest.mark.negative_at
def test_install_never_swallows_staged_install_error_from_the_delegate(
    adapter: TypeScriptEnvironmentalE2EAdapter,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An install failure in the composed NpmInstallStagedInstaller MUST propagate."""

    def _raising_install(
        self: NpmInstallStagedInstaller, artifact: Path, prefix: Path
    ) -> InstalledTree:
        raise StagedInstallError("simulated npm install failure")

    monkeypatch.setattr(NpmInstallStagedInstaller, "install", _raising_install)

    with pytest.raises(StagedInstallError):
        adapter.install(tmp_path / "artifact.tgz", tmp_path / "prefix")
