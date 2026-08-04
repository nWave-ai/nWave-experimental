"""Regression: the ``_env_with_<tool>_dir`` PATH-prepending helper is
TRIPLICATED, byte-for-byte identical once local names are alpha-renamed away,
across the three "consolidating" runner adapters (RCA, fix-runner-helpers-
dedup, defect N4):

* ``src/des/adapters/driven/runner/java_runner.py``   -- ``_env_with_mvn_dir``
* ``src/des/adapters/driven/runner/csharp_runner.py``  -- ``_env_with_dotnet_dir``
* ``src/des/adapters/driven/runner/go_runner.py``      -- ``_env_with_go_dir``

Each copies ``os.environ``, takes ``Path(tool_path).parent``, and prepends it
to ``PATH`` (guarding the empty-PATH case). A params-only name normalizer
reports them as different (their param names -- ``mvn_path``/``dotnet_path``/
``go_path`` -- share almost no tokens); only a FULL alpha-rename (params AND
locals) reveals the identical shape.

EXCLUDED, on purpose: ``cargo_runner.py``'s ``_env_with_cargo_dir`` is a
genuine SUPERSET (it additionally sets ``CARGO_TARGET_DIR`` for warm
build-cache reuse, see ``test_cargo_digest_reuses_worktree_target_dir.py``)
and structurally differs even after alpha-renaming -- proven explicitly below
so the anti-regression assertion never accidentally recruits it.

Two axes pinned here:

1. BEHAVIOURAL (charter-serving, ``known-location-toolchain-finds-its-
   siblings.md``): for each of java/csharp/go, when the tool resolves from a
   known, off-PATH location, the child process the adapter shells reaches its
   own sibling executable -- driven through the REAL production seams
   (``run_java_scope``/``run_csharp_scope``/``run_go_scope``) with a planted
   fake tool + sibling on a controlled PATH, mirroring the fake-tool-planting
   technique in
   ``tests/des/acceptance/go_test_runner_adapter/steps/composition_slice_01_go_runner.py``.
   These are legitimately GREEN today (the three copies already do the right
   thing) -- they are the regression PIN that catches a future refactor
   breaking one runner silently while consolidating the other two.
2. STRUCTURAL (the anti-regression, RED today): the PATH-prepending body
   exists EXACTLY ONCE across the three consolidating runners plus
   ``tool_discovery.py``, decided on a full-alpha-rename + docstring-stripped
   AST normal form -- never on a name.
"""

from __future__ import annotations

import ast
import copy
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from des.adapters.driven.runner import (
    csharp_runner,
    go_runner,
    java_runner,
)
from des.adapters.driven.runner.tool_discovery import ToolResolution
from des.ports.test_runner_port import RunnerAdapter


_REPO_ROOT = Path(__file__).resolve().parents[3]
_RUNNER_DIR = _REPO_ROOT / "src" / "des" / "adapters" / "driven" / "runner"

_SIBLING_NAME = "sibling-tool"


# --- fixture builders: a REAL planted fake tool + sibling, no real toolchain ---


def _write_executable(path: Path, script: str) -> None:
    path.write_text(script, encoding="utf-8")
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _plant_fake_toolchain(tool_dir: Path, tool_name: str) -> Path:
    """A planted, off-PATH fake ``tool_name`` binary + a sibling it reaches for.

    The primary script never needs PATH to find its OWN interpreter (an
    absolute shebang) -- so it works even under the empty/absent-PATH edge.
    It reaches for ``sibling-tool`` by BARE NAME via ``subprocess.run``,
    exactly like a real dotnet reaching for its SDK resolver or a real maven
    reaching for a co-located JDK: that inner lookup depends entirely on the
    PATH the OUTER production call built for it. Exit code encodes the
    outcome (0 = sibling reached, 8 = sibling failed, 9 = sibling not found)
    so the observable ``RunVerdict.passed`` IS the sibling-reachability oracle.
    """
    tool_dir.mkdir(parents=True, exist_ok=True)
    shebang = f"#!{sys.executable}\n"
    primary = tool_dir / tool_name
    _write_executable(
        primary,
        shebang
        + (
            "import subprocess, sys\n"
            "try:\n"
            f"    result = subprocess.run([{_SIBLING_NAME!r}], capture_output=True)\n"
            "except FileNotFoundError:\n"
            "    sys.exit(9)\n"
            "sys.exit(0 if result.returncode == 0 else 8)\n"
        ),
    )
    _write_executable(tool_dir / _SIBLING_NAME, shebang + "import sys\nsys.exit(0)\n")
    return primary


def _stub_resolution(
    monkeypatch: pytest.MonkeyPatch, module: object, primary: Path
) -> None:
    monkeypatch.setattr(
        module,
        "resolve_tool",
        lambda name, known_locations, **kwargs: ToolResolution(
            rung="known-location", path=str(primary)
        ),
    )


_CASES = [
    pytest.param(
        java_runner, java_runner.run_java_scope, "mvn", ("mvn", "test"), id="java"
    ),
    pytest.param(
        csharp_runner,
        csharp_runner.run_csharp_scope,
        "dotnet",
        ("dotnet", "test"),
        id="csharp",
    ),
    pytest.param(
        go_runner, go_runner.run_go_scope, "go", ("go", "test", "./..."), id="go"
    ),
]


# --- BEHAVIOURAL: reachable via the real seam (GREEN today -- regression pin) --


@pytest.mark.parametrize("module, run_scope, tool_name, command", _CASES)
def test_shelled_tool_reaches_sibling_when_resolved_off_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    module: object,
    run_scope: object,
    tool_name: str,
    command: tuple[str, ...],
) -> None:
    """The known-location-resolved tool must reach its own sibling: the
    charter's positive oracle, driven through the real production seam.
    """
    tool_dir = tmp_path / "toolhome" / "bin"
    primary = _plant_fake_toolchain(tool_dir, tool_name)
    target_root = tmp_path / "target"
    target_root.mkdir()
    _stub_resolution(monkeypatch, module, primary)
    adapter = RunnerAdapter(name=f"{tool_name}-test")

    verdict = run_scope(adapter, target_root, command)

    assert verdict.passed is True, (
        f"{tool_name}: the production env-with-tool-dir helper must let the "
        "shelled tool reach its own sibling on PATH via the real seam "
        f"({run_scope.__name__}); got passed=False (sibling unreachable through "
        "the production-applied env)"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("module, run_scope, tool_name, command", _CASES)
def test_sibling_tool_is_not_reachable_in_the_bare_inherited_environment(
    tmp_path: Path,
    module: object,
    run_scope: object,
    tool_name: str,
    command: tuple[str, ...],
) -> None:
    """The discriminating-pair CONTROL: the identical primary script, invoked
    with the bare (unmodified) inherited environment -- no ``tool_dir`` on
    PATH -- must NOT reach the sibling. Proves reachability in the prior test
    is earned by the production PATH-prepend, never incidental (e.g. an
    ambient PATH entry that happens to already contain the sibling).
    """
    del module, run_scope, command  # only the planted script + bare env matter here
    tool_dir = tmp_path / "toolhome" / "bin"
    primary = _plant_fake_toolchain(tool_dir, tool_name)

    bare_result = subprocess.run(
        [str(primary)], capture_output=True, env=dict(os.environ), check=False
    )

    assert bare_result.returncode != 0, (
        f"{tool_name}: the sibling must NOT be reachable under the bare "
        f"inherited environment (control); got returncode=0 -- either the "
        "discriminating pair is broken or tool_dir leaked onto PATH by accident"
    )


@pytest.mark.parametrize("module, run_scope, tool_name, command", _CASES)
def test_shelled_tool_reaches_sibling_when_inherited_path_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    module: object,
    run_scope: object,
    tool_name: str,
    command: tuple[str, ...],
) -> None:
    """The empty/absent-``PATH`` edge every one of the three copies guards
    explicitly (``existing = env.get("PATH", ""); env["PATH"] = dir + sep +
    existing if existing else dir``) -- with PATH entirely unset, the sibling
    must still be reachable (no leading/dangling ``os.pathsep``, no crash).
    """
    tool_dir = tmp_path / "toolhome" / "bin"
    primary = _plant_fake_toolchain(tool_dir, tool_name)
    target_root = tmp_path / "target"
    target_root.mkdir()
    _stub_resolution(monkeypatch, module, primary)
    monkeypatch.delenv("PATH", raising=False)
    adapter = RunnerAdapter(name=f"{tool_name}-test")

    verdict = run_scope(adapter, target_root, command)

    assert verdict.passed is True, (
        f"{tool_name}: with PATH entirely absent, the helper must still let "
        "the shelled tool reach its sibling (the empty-PATH guard each copy "
        f"carries); got passed=False from {run_scope.__name__}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("module, run_scope, tool_name, command", _CASES)
def test_real_process_environ_is_not_mutated_by_the_helper(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    module: object,
    run_scope: object,
    tool_name: str,
    command: tuple[str, ...],
) -> None:
    """The helper copies ``os.environ`` -- the real process environment (this
    test's own ``os.environ``) must be bit-for-bit unchanged after the call.
    """
    tool_dir = tmp_path / "toolhome" / "bin"
    primary = _plant_fake_toolchain(tool_dir, tool_name)
    target_root = tmp_path / "target"
    target_root.mkdir()
    _stub_resolution(monkeypatch, module, primary)
    adapter = RunnerAdapter(name=f"{tool_name}-test")
    snapshot = dict(os.environ)

    run_scope(adapter, target_root, command)

    assert dict(os.environ) == snapshot, (
        f"{tool_name}: the real process os.environ must not be mutated by "
        f"{run_scope.__name__}'s env-with-tool-dir helper"
    )


# --- STRUCTURAL: exactly-once anti-regression (RED today), on the PROPERTY ---


class _CollectAssignedNamesInOrder(ast.NodeVisitor):
    """Collects every ``arg`` and every Store-context ``Name`` id, in
    first-occurrence source order -- the rename universe for the alpha-rename
    normal form. Deliberately leaves Load-only names (``os``, ``Path``,
    ``dict``, attribute bases) untouched: those are the SHAPE the comparison
    must respect, not incidental local labels.
    """

    def __init__(self) -> None:
        self.order: list[str] = []
        self._seen: set[str] = set()

    def _record(self, name: str) -> None:
        if name not in self._seen:
            self._seen.add(name)
            self.order.append(name)

    def visit_arg(self, node: ast.arg) -> None:
        self._record(node.arg)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self._record(node.id)
        self.generic_visit(node)


class _RenameAssignedNames(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping

    def visit_arg(self, node: ast.arg) -> ast.arg:
        if node.arg in self._mapping:
            node.arg = self._mapping[node.arg]
        return node

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id in self._mapping:
            node.id = self._mapping[node.id]
        return node


def _strip_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[1:]
    return body


def _normal_form(func: ast.FunctionDef) -> tuple[str, ...]:
    """The full-alpha-rename (params AND locals), docstring-stripped AST
    normal form of ``func`` -- the PROPERTY the duplication assertion decides
    on. Every parameter and every locally-assigned name is renamed to a
    positional placeholder (``_V0``, ``_V1``, ...) in first-occurrence order,
    so two functions with identical shape but disjoint local-name vocabularies
    (``mvn_dir`` vs ``dotnet_dir`` vs ``go_dir``) normalize identically, while
    two functions with genuinely different bodies (e.g. one that ALSO sets
    ``CARGO_TARGET_DIR``) normalize differently.
    """
    func = copy.deepcopy(func)
    body = _strip_docstring(list(func.body))
    collector = _CollectAssignedNamesInOrder()
    collector.visit(func.args)
    for stmt in body:
        collector.visit(stmt)
    mapping = {name: f"_V{i}" for i, name in enumerate(collector.order)}
    renamer = _RenameAssignedNames(mapping)
    new_args = renamer.visit(copy.deepcopy(func.args))
    new_body = [renamer.visit(copy.deepcopy(stmt)) for stmt in body]
    return (ast.dump(new_args, annotate_fields=False),) + tuple(
        ast.dump(stmt, annotate_fields=False) for stmt in new_body
    )


# Scoped NARROWLY to the files this defect names -- never a repo-wide
# duplicate-body scanner (other lanes are concurrently fixing other
# duplications elsewhere; a general detector would false-positive on their
# in-flight work).
_SCAN_FILENAMES = (
    "java_runner.py",
    "csharp_runner.py",
    "go_runner.py",
    "cargo_runner.py",
    "tool_discovery.py",
)


def _top_level_functions(filename: str) -> list[tuple[str, ast.FunctionDef]]:
    path = _RUNNER_DIR / filename
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [(filename, node) for node in tree.body if isinstance(node, ast.FunctionDef)]


def _canonical_shape() -> tuple[str, ...]:
    """The canonical PATH-prepending normal form, anchored to the
    CONSOLIDATION HOME (``tool_discovery.env_with_tool_dir``) -- never to one
    of the three call-site delegators.

    Anchoring here (rather than e.g. ``java_runner._env_with_mvn_dir``) is
    load-bearing: by construction, ``tool_discovery.env_with_tool_dir`` is the
    ONE place the real PATH-prepend body is required to live post-fix, so the
    anchor cannot itself become a one-line delegator and go vacuous the way
    the prior anchor did (before the fix, ``_env_with_mvn_dir``'s OWN BODY was
    the PATH-prepend logic; after the fix its body is
    ``return env_with_tool_dir(mvn_path)`` -- a delegator shape that no longer
    matches a reintroduced PATH-prepend duplicate). Anchoring to the
    consolidation home instead of a call site means the reference normal form
    moves only if the shared helper itself is redefined -- never as a
    side-effect of a caller being refactored into a delegator.
    """
    for filename, func in _top_level_functions("tool_discovery.py"):
        if func.name == "env_with_tool_dir":
            return _normal_form(func)
    raise AssertionError("tool_discovery.py must define env_with_tool_dir")


def _find_cargo_env_helper() -> ast.FunctionDef:
    for _filename, func in _top_level_functions("cargo_runner.py"):
        if func.name == "_env_with_cargo_dir":
            return func
    raise AssertionError("cargo_runner.py must define _env_with_cargo_dir")


def test_path_prepending_body_exists_exactly_once_across_the_scoped_files() -> None:
    """The anti-regression: the PATH-prepending helper body (the canonical
    normal form pinned by the consolidation home,
    ``tool_discovery.env_with_tool_dir``) must exist EXACTLY ONCE across
    ``java_runner.py`` / ``csharp_runner.py`` / ``go_runner.py`` /
    ``tool_discovery.py`` -- decided on the alpha-renamed AST shape, never on
    a function name (the three call-site names share almost no tokens).

    GREEN today: the fix already consolidated the three copies into
    ``tool_discovery.env_with_tool_dir``, so this finds exactly ONE matching
    location (the consolidation home itself; the three call sites are now
    thin delegators with a different shape). Anchoring to the consolidation
    home (not a call site) is what keeps this a real detector: a future
    regression that reintroduces a fourth PATH-prepend copy anywhere in the
    scanned files raises the match count to 2 and fails here, naming both
    locations.
    """
    canonical = _canonical_shape()
    matches: list[str] = []
    for filename in _SCAN_FILENAMES:
        for source_filename, func in _top_level_functions(filename):
            if _normal_form(func) == canonical:
                matches.append(f"{source_filename}:{func.name}")

    assert len(matches) == 1, (
        "the PATH-prepending env-with-tool-dir body must exist EXACTLY ONCE "
        f"across {', '.join(_SCAN_FILENAMES)} (consolidated in "
        "tool_discovery.py); found "
        f"{len(matches)} structurally-identical (full-alpha-rename) copies: "
        f"{matches} -- consolidate into a single shared "
        "tool_discovery.env_with_tool_dir(tool_path) -> dict[str, str]"
    )


@pytest.mark.negative_at
def test_cargo_env_helper_is_not_a_structural_match_for_the_shared_normal_form() -> (
    None
):
    """Explicit exclusion proof: ``cargo_runner._env_with_cargo_dir`` is a
    genuine SUPERSET (it additionally resolves and injects
    ``CARGO_TARGET_DIR`` for warm build-cache reuse) and must NOT normalize to
    the same shape as java/csharp/go's PATH-prepending body -- guarding
    against the anti-regression test above ever demanding cargo's helper be
    folded into the shared consolidation too (it legitimately is NOT the same
    contract; it has its own dedicated regression test).
    """
    canonical = _canonical_shape()
    cargo_shape = _normal_form(_find_cargo_env_helper())

    assert cargo_shape != canonical, (
        "cargo_runner._env_with_cargo_dir unexpectedly normalizes identically "
        "to the shared java/csharp/go PATH-prepending shape -- it must stay "
        "excluded from this consolidation (it is a superset carrying "
        "CARGO_TARGET_DIR reuse logic); if this now matches, the normal-form "
        "comparison itself is broken (too weak to discriminate a real "
        "structural difference)"
    )
