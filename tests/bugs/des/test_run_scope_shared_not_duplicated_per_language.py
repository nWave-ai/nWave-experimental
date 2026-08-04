"""Regression AT -- feature-delta ``fix-runner-scope-discover-dedup``, slice-03.

RCA (measured this session, not re-derived here): ``run_go_scope`` /
``run_csharp_scope`` / ``run_java_scope`` / ``run_kotlin_scope`` /
``run_vitest_scope`` (``src/des/adapters/driven/runner/{go,csharp,java,
kotlin,vitest}_runner.py``) are IDENTICAL under AST-extract + full alpha-rename
+ unified-diff, normalizing exactly: the default binary name, the
``*_KNOWN_LOCATIONS`` tuple, the ``*_INSTALL_HINT`` string, the tool label
appearing in the timeout/kill error messages, and whether an ``env=`` kwarg is
passed to ``subprocess.run`` (go/java/csharp pass ``env_with_tool_dir(...)``;
kotlin/vitest do not). ``run_cargo_scope`` (``cargo_runner.py``) is DELIBERATELY
EXCLUDED and stays excluded: it carries its own exit-4/exit-94 empty-scope rows
the other five lack.

THE FIX (crafter's job -- zero ``src/`` edits authored by this AT): introduce
``des.adapters.driven.runner.scope_run`` (a narrow shared concern, matching the
package convention set by ``at_discovery.py`` / ``tool_discovery.py`` /
``runner_json.py``) hosting ONE ``run_declared_scope`` primitive with this
contract::

    def run_declared_scope(
        adapter: RunnerAdapter,
        target_root: Path,
        scoped_node_ids: tuple[str, ...],
        *,
        base_dir: Path,
        default_binary: str,
        known_locations: Sequence[str],
        install_hint: str,
        tool_label: str,
        env_builder: Callable[[str], dict[str, str]] | None = None,
    ) -> RunVerdict:

``base_dir`` is a REQUIRED keyword-only parameter (no default): kotlin's
``GRADLE_KNOWN_LOCATIONS`` carries the RELATIVE entry ``"."`` resolved against
``target_root`` via ``resolve_tool``'s own ``base_dir`` argument -- a shared
helper that DEFAULTS ``base_dir`` to ``None`` would silently revert gradlew
discovery to CWD-relative and produce a false INDETERMINATE (measured leak
risk). ``env_builder`` is OPTIONAL (default ``None``): when supplied, the
resolved binary's own path is passed to it and the returned dict becomes
``subprocess.run``'s ``env=``; when omitted, no ``env=`` kwarg is passed at all
(mirrors kotlin/vitest's CURRENT behaviour byte-for-byte). The 5
``run_*_scope`` functions become thin wrappers supplying ONLY their own
literal ``default_binary`` / ``known_locations`` / ``install_hint`` /
``tool_label`` / (optional) ``env_builder``, forwarding
``adapter``/``target_root``/``scoped_node_ids``/``base_dir=target_root``.

OUT OF SCOPE for this slice (untouched by this AT): ``run_cargo_scope``
(``cargo_runner.py`` -- its own exit-4/exit-94 rows); ``discover_*_ats`` /
``at_discovery.py`` (slice-01, already shipped); the 3 ``_env_with_*_dir``
helpers / ``tool_discovery.env_with_tool_dir`` (slice-02, already shipped);
``src/des/cli/at_review_verdict.py`` (slice-04).

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
every behavioral scenario drives the REAL, STABLE, EXISTING production entry
``RunnerAdapter(name=...).run(target_root, scoped_node_ids)`` dispatched
through ``GLOBAL_REGISTRY`` (``des.ports.test_runner_port`` /
``des.adapters.driven.runner.runner_registry``, both modules ALREADY EXIST --
as do all 5 per-language runner modules -- only the new shared module is
absent, so importing them at module top is P1-safe). No subprocess-fork of
pytest itself -- the per-language fixtures below plant a REAL, deterministic,
chmod+x fake binary and let the REAL production adapter shell it (the
production adapter's own job), never a child ``python -c`` probe.

RED-for-right-reason (per ``nw-distill-red-scaffolding`` P1-P4): the dedup-fact
test below probes the shared module's PRESENCE via ``importlib.util.find_spec``
BEFORE importing it, so today's failure is a genuine, message-carrying
``AssertionError`` (MISSING_FUNCTIONALITY), never a bare ``ModuleNotFoundError``
at collection. The wrapper-delegation structural check (section 2) is
CONTENT-based (greps the wrapper's OWN source for the shelling primitives it
must no longer contain) rather than SHAPE-based (e.g. "is a one-line
function") -- the slice-02 lesson: a shape-based check anchored to a site the
fix itself rewrites (the wrapper becoming a delegator) stops discriminating
the moment a byte-identical duplicate is silently reintroduced under a
different shape. A content-based check re-fires on the exact reintroduced
markers regardless of surrounding shape, at the SAME site the fix rewrites --
section 2b below DEMONSTRATES this on a synthetic function before ever
touching the real wrappers, so the discrimination is proven independent of
whether the crafter's future implementation happens to also change shape.
The per-language behavioral invariant tests (section 3) drive the
ALREADY-SHIPPED, ALREADY-GREEN production functions -- they must stay green
THROUGH the refactor (Critical Rule: pin the correct behaviour of
neighbouring/existing branches so a fix cannot pass by flattening 5 distinct
per-language error messages into one generic response).
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from des.adapters.driven.runner import (
    csharp_runner,
    go_runner,
    java_runner,
    kotlin_runner,
    vitest_runner,
)
from des.adapters.driven.runner.runner_registry import seed_runner_registry
from des.ports.test_runner_port import RunnerAdapter, RunnerAdapterUnavailable


if TYPE_CHECKING:
    from collections.abc import Callable


_SCOPE_RUN_MODULE = "des.adapters.driven.runner.scope_run"

_MISSING_SHARED_MODULE_MSG = (
    f"{_SCOPE_RUN_MODULE} must exist -- the ONE shared declared-scope-run "
    "primitive (run_declared_scope) that slice-03 of "
    "fix-runner-scope-discover-dedup introduces, hosting the logic today "
    "duplicated byte-identically across go_runner.py, csharp_runner.py, "
    "java_runner.py, kotlin_runner.py, and vitest_runner.py (matching the "
    "package convention set by at_discovery.py / tool_discovery.py) -- not "
    "yet implemented."
)

# The wrapper modules this slice must turn into thin delegators, keyed by the
# registry token RunnerAdapter.run dispatches on.
_WRAPPER_MODULES = {
    "go-test": go_runner,
    "gradle-test": kotlin_runner,
    "dotnet-test": csharp_runner,
    "maven-test": java_runner,
    "vitest": vitest_runner,
}

_WRAPPER_FN_NAME = {
    "go-test": "run_go_scope",
    "gradle-test": "run_kotlin_scope",
    "dotnet-test": "run_csharp_scope",
    "maven-test": "run_java_scope",
    "vitest": "run_vitest_scope",
}


# ===========================================================================
# 1. THE dedup fact itself: the shared module exists, exposes ONE
#    run_declared_scope, and base_dir/env_builder carry the contract shape
#    the leak-risk analysis requires.
# ===========================================================================


def test_run_scope_is_shared_not_duplicated_per_language() -> None:
    """The declared-scope-run body is ONE shared primitive, not 5 duplicated
    per-language copies.

    Active-RED at HEAD: ``scope_run.py`` does not exist yet, so ``find_spec``
    returns ``None`` and this fires a semantic ``AssertionError`` (never a
    collection-time ``ModuleNotFoundError``). GREEN once DELIVER lands the
    shared module AND turns the 5 wrappers into thin delegators (section 2).
    """
    spec = importlib.util.find_spec(_SCOPE_RUN_MODULE)
    assert spec is not None, _MISSING_SHARED_MODULE_MSG

    scope_run = importlib.import_module(_SCOPE_RUN_MODULE)
    assert hasattr(scope_run, "run_declared_scope"), (
        f"{_SCOPE_RUN_MODULE} must expose ONE shared run_declared_scope "
        "primitive that the 5 thin per-language wrappers call, supplying "
        "only their own default binary / known locations / install hint / "
        "tool label / optional env builder -- not yet implemented."
    )

    signature = inspect.signature(scope_run.run_declared_scope)
    for required_param in (
        "adapter",
        "target_root",
        "scoped_node_ids",
        "base_dir",
        "default_binary",
        "known_locations",
        "install_hint",
        "tool_label",
    ):
        assert required_param in signature.parameters, (
            f"{_SCOPE_RUN_MODULE}.run_declared_scope must accept "
            f"{required_param!r} -- got {list(signature.parameters)}."
        )

    base_dir_param = signature.parameters["base_dir"]
    assert base_dir_param.default is inspect.Parameter.empty, (
        "base_dir must be a REQUIRED parameter of run_declared_scope (no "
        "default) -- kotlin's GRADLE_KNOWN_LOCATIONS carries the relative "
        "entry '.' resolved against target_root via base_dir; a helper "
        "defaulting base_dir to None would silently revert gradlew "
        "discovery to CWD-relative and produce a false INDETERMINATE "
        f"(measured leak risk). Got default={base_dir_param.default!r}."
    )

    assert "env_builder" in signature.parameters, (
        f"{_SCOPE_RUN_MODULE}.run_declared_scope must accept an OPTIONAL "
        "env_builder parameter (go/java/csharp supply env_with_tool_dir; "
        "kotlin/vitest omit it, passing no env= kwarg to subprocess.run at "
        "all) -- not yet implemented."
    )
    env_builder_param = signature.parameters["env_builder"]
    assert env_builder_param.default is None, (
        "env_builder must default to None (kotlin/vitest never build one) "
        f"-- got default={env_builder_param.default!r}."
    )

    assert set(scope_run.__all__) == {"run_declared_scope"}, (
        f"{_SCOPE_RUN_MODULE}.__all__ must export EXACTLY run_declared_scope "
        f"-- got {sorted(scope_run.__all__)}."
    )


# ===========================================================================
# 2. Structural no-duplication: each wrapper's OWN source must no longer
#    contain the shelling primitives it used to re-implement.
# ===========================================================================

# The tell-tale markers of a re-implemented (not delegated) declared-scope-run
# body. Content-based (never shape-based, per the slice-02 lesson): a
# reintroduced duplicate re-fires this check regardless of how the
# surrounding function is otherwise reshaped.
_DUPLICATED_BODY_MARKERS = (
    "subprocess.run(",
    "TimeoutExpired",
    "_signal_kill_reason(",
    "resolve_tool(",
)


def _assert_delegates_to_shared_helper(
    fn: Callable[..., object], owner_label: str
) -> None:
    """Fail LOUD, naming ``owner_label``, if ``fn``'s own source still
    contains a declared-scope-run shelling primitive -- the exact signal
    that the dedup did not happen (or was reverted) at THIS site.
    """
    source = inspect.getsource(fn)
    for marker in _DUPLICATED_BODY_MARKERS:
        assert marker not in source, (
            f"{owner_label} still contains {marker!r} in its OWN source -- "
            f"it must delegate to {_SCOPE_RUN_MODULE}.run_declared_scope "
            "instead of re-implementing the declared-scope-run body "
            f"(fix-runner-scope-discover-dedup slice-03). A duplicate body "
            f"reintroduced into {owner_label} is exactly the regression "
            "this check exists to catch."
        )


def test_wrapper_delegation_check_discriminates_a_reintroduced_duplicate_body() -> None:
    """Self-test of the section-2 discriminator (proves it fires on content,
    not shape) -- independent of whether the real wrappers have been
    refactored yet.

    A synthetic function carrying the SAME shelling primitives the real
    wrappers used to contain, wrapped in an unrelated shape (a multi-line
    body, NOT the byte-identical original), must still be rejected by name.
    """

    def _reintroduced_duplicate(adapter: object, target_root: object) -> None:
        del adapter, target_root
        import subprocess

        try:
            subprocess.run(["true"], capture_output=True, text=True, timeout=1)
        except subprocess.TimeoutExpired:
            pass

    with pytest.raises(AssertionError, match="reintroduced_duplicate"):
        _assert_delegates_to_shared_helper(
            _reintroduced_duplicate,
            "des.adapters.driven.runner.<synthetic>.test_reintroduced_duplicate",
        )


@pytest.mark.parametrize(
    "runner_token", list(_WRAPPER_MODULES), ids=list(_WRAPPER_MODULES)
)
def test_language_wrapper_delegates_instead_of_reimplementing(
    runner_token: str,
) -> None:
    """Per-language isolation of the section-1 dedup fact -- an aggregate-only
    check could pass vacuously if only some wrappers were actually
    consolidated; this fires independently per module, naming the offender.

    Active-RED at HEAD: every wrapper still contains the full duplicated
    body, so this fails on ALL FIVE today (each with its own semantic
    AssertionError naming itself) -- the real, non-synthetic demonstration
    that the check discriminates the un-refactored state. GREEN once each
    wrapper is turned into a thin delegator.
    """
    module = _WRAPPER_MODULES[runner_token]
    fn = getattr(module, _WRAPPER_FN_NAME[runner_token])
    _assert_delegates_to_shared_helper(fn, f"{module.__name__}.{fn.__name__}")


# ===========================================================================
# 3. Leak-risk guards: the constants importable elsewhere must survive the
#    consolidation at their CURRENT names/modules (already GREEN today --
#    pins the neighbouring behaviour so the refactor cannot silently move
#    or rename an externally-imported symbol).
# ===========================================================================

_EXPECTED_EXTERNALLY_IMPORTED_CONSTANTS = (
    ("des.adapters.driven.runner.vitest_runner", "VITEST_KNOWN_LOCATIONS"),
    ("des.adapters.driven.runner.vitest_runner", "VITEST_INSTALL_HINT"),
    ("des.adapters.driven.runner.vitest_runner", "NPM_INSTALL_HINT"),
    ("des.adapters.driven.runner.cargo_runner", "CARGO_KNOWN_LOCATIONS"),
    ("des.adapters.driven.runner.cargo_runner", "CARGO_INSTALL_HINT"),
)


@pytest.mark.parametrize(
    "module_path,constant_name",
    _EXPECTED_EXTERNALLY_IMPORTED_CONSTANTS,
    ids=[
        f"{m.rsplit('.', 1)[-1]}.{c}"
        for m, c in _EXPECTED_EXTERNALLY_IMPORTED_CONSTANTS
    ],
)
def test_externally_imported_constant_stays_importable_at_its_current_name(
    module_path: str, constant_name: str
) -> None:
    """``e2e/vitest_e2e_runner.py``, ``contract_gate/vitest_contract_gate_
    adapter.py``, ``install/npm_install_staged_installer.py``, and
    ``runner_capability_probe.py`` all import these constants from their
    CURRENT module at their CURRENT name -- a consolidation that relocates
    or renames them breaks every one of those external readers.
    """
    module = importlib.import_module(module_path)
    assert hasattr(module, constant_name), (
        f"{constant_name} must stay importable from {module_path} at its "
        "CURRENT name after the scope_run consolidation -- relocating or "
        "renaming it breaks at least e2e/vitest_e2e_runner.py, "
        "contract_gate/vitest_contract_gate_adapter.py, "
        "install/npm_install_staged_installer.py, or "
        "runner_capability_probe.py."
    )


_EXPECTED_ALL = {
    "des.adapters.driven.runner.go_runner": {"GO_KNOWN_LOCATIONS", "run_go_scope"},
    "des.adapters.driven.runner.csharp_runner": {
        "DOTNET_KNOWN_LOCATIONS",
        "discover_csharp_ats",
        "run_csharp_scope",
    },
    "des.adapters.driven.runner.java_runner": {
        "JAVA_KNOWN_LOCATIONS",
        "discover_java_ats",
        "run_java_scope",
    },
    "des.adapters.driven.runner.kotlin_runner": {
        "GRADLE_KNOWN_LOCATIONS",
        "discover_kotlin_ats",
        "run_kotlin_scope",
    },
    "des.adapters.driven.runner.vitest_runner": {
        "VITEST_KNOWN_LOCATIONS",
        "run_vitest_scope",
    },
}


@pytest.mark.parametrize(
    "module_path,expected",
    list(_EXPECTED_ALL.items()),
    ids=list(_EXPECTED_ALL.keys()),
)
def test_runner_module_export_surface_stays_byte_identical_through_the_dedup(
    module_path: str, expected: set[str]
) -> None:
    module = importlib.import_module(module_path)
    assert set(module.__all__) == expected, (
        f"{module_path}.__all__ must stay byte-identical through the "
        f"scope_run consolidation -- expected {sorted(expected)}, got "
        f"{sorted(module.__all__)}. run_declared_scope is an implementation "
        "detail of the wrapper's body, never a re-export from a language "
        "module's own __all__."
    )


# ===========================================================================
# 4. Per-language behavioral invariants the dedup MUST NOT change (Critical
#    Rule: pin the correct behaviour of neighbouring branches). Every
#    scenario is parametrized over the 5 languages so a check that cannot
#    discriminate one language's own tool_label/remediation from another's
#    can never pass vacuously. Drives the REAL production driving port
#    (RunnerAdapter.run -> GLOBAL_REGISTRY dispatch) over a REAL, planted,
#    deterministic fake binary -- never a mock of the adapter itself.
# ===========================================================================


@dataclass(frozen=True)
class _LanguageRunFixture:
    runner_token: str
    binary_name: str
    declared_command: tuple[str, ...]
    own_hint_fragment: str
    tool_label: str
    known_locations_owner: object
    known_locations_attr: str


_LANGUAGE_RUN_FIXTURES = (
    _LanguageRunFixture(
        runner_token="go-test",
        binary_name="go",
        declared_command=("go", "test", "./..."),
        own_hint_fragment="go.dev",
        tool_label="go",
        known_locations_owner=go_runner,
        known_locations_attr="GO_KNOWN_LOCATIONS",
    ),
    _LanguageRunFixture(
        runner_token="gradle-test",
        binary_name="gradlew",
        declared_command=("gradlew", "test"),
        own_hint_fragment="gradle wrapper",
        tool_label="gradlew",
        known_locations_owner=kotlin_runner,
        known_locations_attr="GRADLE_KNOWN_LOCATIONS",
    ),
    _LanguageRunFixture(
        runner_token="dotnet-test",
        binary_name="dotnet",
        declared_command=("dotnet", "test"),
        own_hint_fragment="dotnet.microsoft.com",
        tool_label="dotnet",
        known_locations_owner=csharp_runner,
        known_locations_attr="DOTNET_KNOWN_LOCATIONS",
    ),
    _LanguageRunFixture(
        runner_token="maven-test",
        binary_name="mvn",
        declared_command=("mvn", "test"),
        own_hint_fragment="maven.apache.org",
        tool_label="mvn",
        known_locations_owner=java_runner,
        known_locations_attr="JAVA_KNOWN_LOCATIONS",
    ),
    _LanguageRunFixture(
        runner_token="vitest",
        binary_name="vitest",
        declared_command=("vitest", "run"),
        own_hint_fragment="npm install",
        tool_label="vitest",
        known_locations_owner=vitest_runner,
        known_locations_attr="VITEST_KNOWN_LOCATIONS",
    ),
)


def _plant_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _prepend_to_path(monkeypatch: pytest.MonkeyPatch, path_dir: Path) -> None:
    """Fake binary FIRST on PATH (shadows any real toolchain on this box) --
    but keeps the REAL system PATH tail so a script's own external commands
    (``sleep``) still resolve.
    """
    monkeypatch.setenv("PATH", f"{path_dir}{os.pathsep}{os.environ.get('PATH', '')}")


@pytest.fixture(autouse=True)
def _seeded_registry() -> None:
    seed_runner_registry()


@pytest.mark.parametrize(
    "fixture", _LANGUAGE_RUN_FIXTURES, ids=lambda f: f.runner_token
)
def test_exit_zero_is_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture: _LanguageRunFixture
) -> None:
    target_root = tmp_path / "target"
    target_root.mkdir()
    path_bin = tmp_path / "path-bin"
    path_bin.mkdir()
    _plant_executable(path_bin / fixture.binary_name, "#!/bin/sh\nexit 0\n")
    _prepend_to_path(monkeypatch, path_bin)

    adapter = RunnerAdapter(name=fixture.runner_token)
    verdict = adapter.run(target_root, fixture.declared_command)

    assert verdict.passed is True, (
        f"{fixture.runner_token}: exit 0 must map to RunVerdict(passed=True) "
        f"-- got passed={verdict.passed!r}."
    )
    assert verdict.runner == fixture.runner_token


@pytest.mark.parametrize(
    "fixture", _LANGUAGE_RUN_FIXTURES, ids=lambda f: f.runner_token
)
def test_any_non_zero_exit_is_fail_propagated_not_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture: _LanguageRunFixture
) -> None:
    target_root = tmp_path / "target"
    target_root.mkdir()
    path_bin = tmp_path / "path-bin"
    path_bin.mkdir()
    _plant_executable(path_bin / fixture.binary_name, "#!/bin/sh\nexit 7\n")
    _prepend_to_path(monkeypatch, path_bin)

    adapter = RunnerAdapter(name=fixture.runner_token)
    verdict = adapter.run(target_root, fixture.declared_command)

    assert verdict.passed is False, (
        f"{fixture.runner_token}: a non-zero exit must PROPAGATE to "
        f"RunVerdict(passed=False), never be softened into INDETERMINATE -- "
        f"got passed={verdict.passed!r}."
    )
    assert verdict.runner == fixture.runner_token


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "fixture", _LANGUAGE_RUN_FIXTURES, ids=lambda f: f.runner_token
)
def test_unresolvable_tool_refuses_loud_naming_own_remediation_never_anothers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture: _LanguageRunFixture
) -> None:
    """An unresolvable tool degrades LOUD to RunnerAdapterUnavailable naming
    THIS language's own remediation -- never a leaked/borrowed remediation
    from another language (the exact vacuous-pass the shared primitive could
    introduce if the per-language install_hint were lost in consolidation).
    """
    target_root = tmp_path / "target"
    target_root.mkdir()
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()
    monkeypatch.setenv("PATH", str(empty_path))
    monkeypatch.setattr(fixture.known_locations_owner, fixture.known_locations_attr, ())

    adapter = RunnerAdapter(name=fixture.runner_token)
    with pytest.raises(RunnerAdapterUnavailable) as excinfo:
        adapter.run(target_root, fixture.declared_command)

    message = str(excinfo.value)
    assert fixture.own_hint_fragment in message, (
        f"{fixture.runner_token}'s unresolvable-tool refusal must name ITS "
        f"OWN remediation fragment {fixture.own_hint_fragment!r} -- got "
        f"{message!r}."
    )
    for other in _LANGUAGE_RUN_FIXTURES:
        if other.runner_token == fixture.runner_token:
            continue
        assert other.own_hint_fragment not in message, (
            f"{fixture.runner_token}'s unresolvable-tool refusal must NEVER "
            f"name another language's remediation fragment "
            f"({other.own_hint_fragment!r}) -- got {message!r}. A borrowed "
            "remediation means the shared primitive lost the per-language "
            "install hint during consolidation."
        )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "fixture", _LANGUAGE_RUN_FIXTURES, ids=lambda f: f.runner_token
)
def test_timeout_refuses_loud_naming_the_tool_and_the_timeout_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture: _LanguageRunFixture
) -> None:
    """A hanging/deadlocking run degrades LOUD to RunnerAdapterUnavailable
    naming THIS tool and referencing NWAVE_GATE_RUN_TIMEOUT -- INDETERMINATE,
    never a silent unbounded hang.
    """
    target_root = tmp_path / "target"
    target_root.mkdir()
    path_bin = tmp_path / "path-bin"
    path_bin.mkdir()
    _plant_executable(path_bin / fixture.binary_name, "#!/bin/sh\nsleep 5\n")
    _prepend_to_path(monkeypatch, path_bin)
    monkeypatch.setenv("NWAVE_GATE_RUN_TIMEOUT", "0.2")

    adapter = RunnerAdapter(name=fixture.runner_token)
    with pytest.raises(RunnerAdapterUnavailable) as excinfo:
        adapter.run(target_root, fixture.declared_command)

    message = str(excinfo.value)
    assert fixture.tool_label in message, (
        f"{fixture.runner_token}'s timeout refusal must name its OWN tool "
        f"label {fixture.tool_label!r} -- got {message!r}."
    )
    assert "NWAVE_GATE_RUN_TIMEOUT" in message, (
        f"{fixture.runner_token}'s timeout refusal must reference "
        f"NWAVE_GATE_RUN_TIMEOUT -- got {message!r}."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "fixture", _LANGUAGE_RUN_FIXTURES, ids=lambda f: f.runner_token
)
def test_signal_kill_refuses_loud_naming_the_tool_and_the_os_never_a_test_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fixture: _LanguageRunFixture
) -> None:
    """A run killed by the host OS (OOM/SIGKILL) degrades LOUD to
    RunnerAdapterUnavailable naming THIS tool and that it was killed by the
    OS -- distinctly from an ordinary test failure (never RunVerdict(passed=
    False)).
    """
    target_root = tmp_path / "target"
    target_root.mkdir()
    path_bin = tmp_path / "path-bin"
    path_bin.mkdir()
    _plant_executable(path_bin / fixture.binary_name, "#!/bin/sh\nkill -9 $$\n")
    _prepend_to_path(monkeypatch, path_bin)

    adapter = RunnerAdapter(name=fixture.runner_token)
    with pytest.raises(RunnerAdapterUnavailable) as excinfo:
        adapter.run(target_root, fixture.declared_command)

    message = str(excinfo.value)
    assert fixture.tool_label in message, (
        f"{fixture.runner_token}'s signal-kill refusal must name its OWN "
        f"tool label {fixture.tool_label!r} -- got {message!r}."
    )
    assert "killed by the OS" in message, (
        f"{fixture.runner_token}'s signal-kill refusal must say it was "
        f"killed by the OS, distinctly from an ordinary test failure -- got "
        f"{message!r}."
    )
    assert "test failure" not in message or "not a" in message, (
        f"{fixture.runner_token}'s signal-kill refusal must be DISTINCT "
        f"from a test-failure verdict -- got {message!r}."
    )


# ===========================================================================
# 5. CRITICAL LEAK-RISK regression: kotlin's RELATIVE '.' known-location
#    entry must resolve against base_dir=target_root, never the process CWD.
#    All five wrappers pass base_dir=target_root; a shared helper defaulting
#    base_dir to None (or silently substituting Path.cwd()) would revert this
#    specific resolution to CWD-relative and produce a false INDETERMINATE.
# ===========================================================================


def test_kotlin_relative_known_location_resolves_against_target_root_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_root = tmp_path / "target"
    target_root.mkdir()
    # The fake gradlew lives ONLY at <target_root>/gradlew (the relative "."
    # entry in GRADLE_KNOWN_LOCATIONS resolved against base_dir=target_root)
    # -- NOT anywhere the process CWD would find it, and NOT on PATH.
    _plant_executable(target_root / "gradlew", "#!/bin/sh\nexit 0\n")
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()
    monkeypatch.setenv("PATH", str(empty_path))
    assert Path.cwd() != target_root, (
        "test precondition: the process CWD must differ from target_root "
        "for this regression to actually discriminate CWD-relative "
        "resolution from base_dir-relative resolution."
    )

    adapter = RunnerAdapter(name="gradle-test")
    verdict = adapter.run(target_root, ("gradlew", "test"))

    assert verdict.passed is True, (
        "the fake gradlew planted at <target_root>/gradlew must be "
        "resolved via GRADLE_KNOWN_LOCATIONS's relative '.' entry against "
        "base_dir=target_root -- a helper silently defaulting base_dir to "
        "None (or to Path.cwd()) would fail to find it here and raise "
        "RunnerAdapterUnavailable instead (a false INDETERMINATE), not "
        f"return RunVerdict(passed=True). Got passed={verdict.passed!r}."
    )


__all__: list[str] = []
