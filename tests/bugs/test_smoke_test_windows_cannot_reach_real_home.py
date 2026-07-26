"""Regression: the Windows smoke test must not be able to touch the real home
directory, and must refuse outright when run anywhere but Windows.

RCA (already diagnosed by the charter, this file does not re-derive it):
``tests/e2e/smoke_test_windows.py`` is a plain script whose entire body runs
at import time. On any platform it points ``nwave-ai install`` at
``Path.home()`` -- the *real* Claude configuration -- and overwrites
``~/.nwave/global-config.json`` down to a single ``attribution`` key. The
only thing that ever stopped this was a ``skipif`` on a *different* file
(``tests/e2e/test_windows_smoke.py``); nothing in the script itself declined.
Full charter:
``docs/product/expectations/F-FLOW-V2-EPIC-HONEST-CLOSURE/
running-the-windows-smoke-test-installs-nwave-into-the-developers-real-claude-and-overwrites-the.md``

Two properties, per the charter's oracle:

P1 -- the refusal lives in the file that carries the hazard: asked to run on
      a non-Windows platform, ``smoke_test_windows.py`` declines, explains,
      and ends before any effect.
P2 -- the script cannot reach the real home *at all*, even on Windows. Its
      installation target is a throwaway directory. This is the property
      that matters -- it removes the whole class, not one instance of it.

THE SEAM (this file names it; a separate GREEN dispatch implements it):
``tests/e2e/smoke_guard.py``, importable with ZERO side effects:

    - ``require_windows(platform: str) -> str | None``
          Pure. Returns a human-readable refusal message naming the given
          platform and stating the script only runs on Windows, for any
          ``platform != "win32"``. Returns ``None`` for ``"win32"``.
    - ``sandbox_home(root: Path) -> Path``
          Pure, no I/O. Returns the throwaway home the script must install
          into, derived from the caller-supplied ``root`` -- never from
          ``Path.home()``.

ABSOLUTE PROHIBITION: this file NEVER imports or runs
``tests/e2e/smoke_test_windows.py`` (its body executes on import -- that IS
the defect) and NEVER runs ``tests/e2e/test_windows_smoke.py``. Every
assertion below reaches its verdict either by calling the seam directly, or
by reading ``smoke_test_windows.py`` as source text / AST -- never by
executing it.

THIS FILE IS TEST-ONLY. No production code, including the seam module named
above, is touched by this authoring pass -- that is a separate GREEN
dispatch's job.

Active-RED today: ``tests/e2e/smoke_guard.py`` does not exist yet. The
behavioural tests below import it LOCALLY (inside each test body, not at
module level) so a missing module fails only those individual tests with
``ModuleNotFoundError`` rather than collection-erroring the whole file --
the structural checks below need no such import and fail with a genuine
``AssertionError`` against the CURRENT, unfixed source of
``smoke_test_windows.py`` (it calls no guard, and it still builds paths from
``Path.home()``).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from hypothesis import example, given
from hypothesis import strategies as st


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SMOKE_SCRIPT = _REPO_ROOT / "tests" / "e2e" / "smoke_test_windows.py"

# Measured directly from the CURRENT (unfixed) source -- ten `test(...)`
# assertion call sites reachable at module-import time. A fix must not drop
# below this: a script that refuses everywhere, or that quietly stopped
# checking anything, must fail the "still smoke-tests" guard below.
_CURRENT_ASSERTION_CALL_COUNT = 10

_NAMED_NON_WINDOWS_PLATFORMS = ["linux", "darwin", "cygwin", "aix", "freebsd8"]

_EFFECT_CALL_NAMES = {
    "run",
    "mkdir",
    "write_text",
    "rmtree",
    "copytree",
    "unlink",
    "remove",
    "Popen",
    "system",
}


def _read_source() -> str:
    return _SMOKE_SCRIPT.read_text(encoding="utf-8")


def _parse_module() -> ast.Module:
    return ast.parse(_read_source(), filename=str(_SMOKE_SCRIPT))


def _module_level_calls(tree: ast.Module) -> list[ast.Call]:
    """Calls that execute at import time -- skip nested def/class bodies.

    A guard or an effect that is only *defined* inside a function or class
    does not run merely because the module is imported; only statements
    reachable by straight-line execution of the module body count.
    """
    calls: list[ast.Call] = []

    class _Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        def visit_Call(self, node: ast.Call) -> None:
            calls.append(node)
            self.generic_visit(node)

    _Visitor().visit(tree)
    return calls


def _call_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


# ---------------------------------------------------------------------------
# P2 -- the script cannot reach the real home at all (the property that
# matters most -- primary regression name per the dispatch contract).
# ---------------------------------------------------------------------------


def test_smoke_test_windows_cannot_reach_real_home() -> None:
    """No path in the script is built from the real home, on any platform.

    Read as source text (never imported/executed): the fix must remove
    every ``Path.home()``, ``expanduser``, and literal ``"~"`` home
    construction, on BOTH surfaces the charter names -- the ``~/.claude``
    install target and the ``~/.nwave/global-config.json`` rewrite -- since
    today's script derives both from a single ``home = Path.home()`` call.
    """
    source = _read_source()
    violations = []
    if "Path.home()" in source:
        violations.append("Path.home()")
    if "expanduser" in source:
        violations.append("expanduser")
    if re.search(r"""["']~["']""", source) or re.search(r"""["']~/""", source):
        violations.append('literal "~" home construction')

    assert not violations, (
        "smoke_test_windows.py still builds a path from the real home via: "
        f"{', '.join(violations)}. Its installation target must be a "
        "throwaway sandbox (see tests/e2e/smoke_guard.py:sandbox_home), "
        "never the developer's real home -- this covers both the "
        "~/.claude install target and the ~/.nwave/global-config.json "
        "rewrite, since both derive from the same home reference today."
    )


# ---------------------------------------------------------------------------
# P1 -- the guard, exercised directly, refuses off Windows and allows
# Windows. Behavioural: calls the seam, never the subject script.
# ---------------------------------------------------------------------------

_PLATFORM_TEXT = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu"), max_codepoint=0x7A),
    min_size=1,
    max_size=24,
).filter(lambda platform: platform != "win32")


@given(platform=_PLATFORM_TEXT)
@example(platform="linux")
@example(platform="darwin")
def test_require_windows_refuses_every_non_windows_platform(platform: str) -> None:
    """The guard, exercised directly, refuses off Windows and says why.

    A reader who has never seen this defect must understand from the
    message alone why the script stopped -- assert on MEANING (the
    platform is named, Windows is named as the only supported platform),
    not on one exact wording.
    """
    from tests.e2e.smoke_guard import require_windows

    message = require_windows(platform)

    assert message is not None, f"require_windows({platform!r}) must refuse"
    assert platform in message, (
        f"the refusal message does not name the offending platform "
        f"{platform!r}: {message!r}"
    )
    assert "indows" in message, (
        f"the refusal message must say the script only runs on Windows: {message!r}"
    )


@pytest.mark.parametrize("platform", _NAMED_NON_WINDOWS_PLATFORMS)
def test_require_windows_refuses_named_platforms(platform: str) -> None:
    """Pinned canonical cases for the property above -- readable, no shrink."""
    from tests.e2e.smoke_guard import require_windows

    assert require_windows(platform) is not None


def test_require_windows_allows_the_windows_platform() -> None:
    """Negative example, mandatory -- proves this is a guard, not a mute button."""
    from tests.e2e.smoke_guard import require_windows

    assert require_windows("win32") is None


# ---------------------------------------------------------------------------
# P2 continued -- the sandbox helper never resolves under the real home.
# ---------------------------------------------------------------------------

_ROOT_SEGMENT = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")),
    min_size=1,
    max_size=12,
)


@given(segment=_ROOT_SEGMENT)
def test_sandbox_home_never_resolves_under_the_real_home(
    tmp_path_factory: pytest.TempPathFactory, segment: str
) -> None:
    """The install target is a throwaway dir, never the caller's real home.

    ``sandbox = None, skip the install`` must not be able to pass this: the
    helper has to return a genuine, usable path, derived from the
    caller-supplied root -- never from ``Path.home()``.
    """
    from tests.e2e.smoke_guard import sandbox_home

    root = tmp_path_factory.mktemp("sandbox-root") / segment
    home = sandbox_home(root)

    assert home is not None, "sandbox_home must return a usable path"
    assert home != Path.home()
    assert Path.home() not in home.parents, (
        f"sandbox_home({root!r}) resolved to {home!r}, which is nested "
        "under the real home -- it must be derived from the caller's root."
    )


# ---------------------------------------------------------------------------
# Wiring -- the guard must be CALLED, and called before every side effect.
# Structural: reads smoke_test_windows.py as text/AST, never imports it.
# ---------------------------------------------------------------------------


def test_the_platform_guard_is_called_not_merely_defined() -> None:
    """A defined-but-uncalled guard is a dormant seam -- must read as failure."""
    source = _read_source()
    assert "require_windows(" in source, (
        "smoke_test_windows.py never calls require_windows(...) -- a guard "
        "defined elsewhere and never invoked here refuses nothing."
    )


def test_the_platform_guard_runs_before_any_side_effect() -> None:
    """P1 -- the refusal precedes venv creation, pip, and every mkdir/write."""
    tree = _parse_module()
    calls = _module_level_calls(tree)

    guard_calls = [c for c in calls if _call_name(c) == "require_windows"]
    effect_calls = [c for c in calls if _call_name(c) in _EFFECT_CALL_NAMES]

    assert guard_calls, (
        "require_windows(...) is never called at module level in "
        "smoke_test_windows.py -- see "
        "test_the_platform_guard_is_called_not_merely_defined for the "
        "direct symptom."
    )
    assert effect_calls, (
        "no known side-effecting call was found in smoke_test_windows.py "
        "-- update _EFFECT_CALL_NAMES if the script's shape changed."
    )

    guard_line = min(call.lineno for call in guard_calls)
    first_effect_line = min(call.lineno for call in effect_calls)

    assert guard_line < first_effect_line, (
        f"the platform guard is called at line {guard_line}, but a "
        f"side-effecting call already happened at line {first_effect_line} "
        "-- the refusal must run before anything with an effect."
    )


# ---------------------------------------------------------------------------
# Negative example, mandatory -- the smoke test must still smoke-test.
# ---------------------------------------------------------------------------


def test_the_smoke_script_still_performs_its_full_assertion_suite() -> None:
    """A fix must not hollow out the script's coverage.

    Counts ``test(...)`` call sites reachable at module-import time. A fix
    that refuses everywhere (including Windows) or that quietly stops
    installing/checking anything must fail this.
    """
    tree = _parse_module()
    calls = _module_level_calls(tree)
    assertion_calls = [c for c in calls if _call_name(c) == "test"]

    assert len(assertion_calls) >= _CURRENT_ASSERTION_CALL_COUNT, (
        f"smoke_test_windows.py now records only {len(assertion_calls)} "
        f"test(...) assertions, down from the measured baseline of "
        f"{_CURRENT_ASSERTION_CALL_COUNT} -- a fix that hollows out the "
        "smoke test's coverage is not acceptable; it must still create a "
        "venv, install nwave-ai, run the installer, and verify agents, "
        "skills and the git-attribution commit."
    )
