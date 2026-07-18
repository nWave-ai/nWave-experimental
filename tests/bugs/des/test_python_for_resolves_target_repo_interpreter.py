"""Regression test for defect #79 (target-machine-agnosticism, 5th layer).

``python_for()`` resolves its interpreter from the INSTALLED ``des`` location
-- ``_project_root()`` (``src/des/runtime/interpreter.py:84``) walks up from
``des.runtime.interpreter``'s OWN ``__file__``, never from the target repo
``des commit-slice`` / ``des verify-slice-commit`` is gating. On a beta
tester's consumer repo -- nWave installed globally, the project living in its
own ``.venv`` -- the resolved interpreter is wrong: it can even be the OUTER
interpreter running ``des`` itself (already pytest-capable, since ``des``
gates its OWN suite too), which then tries to collect the CONSUMER project's
tests and fails collection (exit 4) -> ``SliceCommitIndeterminate
gate_scope_interpreter_unavailable`` + a vacuous all-zero Gate-Scope.

Ground truth (verified by code-read, ``src/des/runtime/interpreter.py``):
  - ``python_for(capability)`` has no ``repo_root`` parameter today -- every
    caller (the E2 contract-gate adapter
    ``PythonContractGateAdapter.collect_scope``/``run_suite``, and the pytest
    run-facet ``pytest_runner.pytest_interpreter``) is stuck on whatever
    ``sys.executable`` / ``_uv_python()`` happens to resolve.
  - ``_uv_python()`` (:98) calls ``uv run --project <root>`` where ``<root>``
    comes from ``_project_root()`` -- always THIS repo's project root
    (anchored on ``Path(__file__)`` inside the installed ``des`` package),
    never the caller's target repo.
  - ``_has_capability`` (:143) only probes "can this interpreter import
    pytest" -- never "does this interpreter belong to the repo being
    gated" -- so a des-runtime interpreter that happens to have pytest wins
    rung-1 even though it owns none of the target project's dependencies.

Charter (the value-side oracle Vera examines against):
  docs/product/expectations/fix-python-for-target-interpreter/
  operator-gets-a-real-verdict-without-activating-their-venv.md

This file encodes the not-yet-existing ``repo_root=`` keyword the fix will
add to ``python_for``. Every assertion routes through
``_resolve_with_repo_root``, which turns TODAY's
``TypeError: unexpected keyword argument 'repo_root'`` into an explicit,
self-explaining ``pytest.fail`` -- RED for the diagnosed reason (the
parameter does not exist, so interpreter resolution cannot even be TOLD
which repo it is running against), never a bare collection/import error.
Once the fix lands (``repo_root: Path | None = None`` kwarg added,
VIRTUAL_ENV -> ``<repo_root>/.venv/bin/python`` -> existing ladder
resolution order, byte-identical dogfood path when ``repo_root`` names this
repo), the call succeeds and the behavioral assertions below take over.
"""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path
from typing import Any

import pytest

from des.cli import run_contract_gate
from des.runtime.interpreter import Capability, InterpreterUnavailable, python_for


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class _InterpreterResolutionRecorded(Exception):
    """Raised by the ``pytest_interpreter`` spy right after it records its
    call -- short-circuits the call site under test BEFORE any real
    subprocess/collection machinery runs. The D1 witnesses only need to know
    WHICH ``repo_root`` the interpreter-resolution boundary was told about;
    they never need a real pytest collection/run to complete.
    """


def _install_pytest_interpreter_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> list[Path | None]:
    """Replace ``run_contract_gate.pytest_interpreter`` with a spy that
    records the ``repo_root`` kwarg it was called with, then raises
    ``_InterpreterResolutionRecorded`` -- driving the call site under test
    exactly to (and not past) the interpreter-resolution boundary.
    """
    calls: list[Path | None] = []

    def _spy(repo_root: Path | None = None) -> str:
        calls.append(repo_root)
        raise _InterpreterResolutionRecorded()

    monkeypatch.setattr(run_contract_gate, "pytest_interpreter", _spy)
    return calls


class _SysWithoutPytest:
    """A ``sys``-lookalike whose ``.modules`` view has ``"pytest"`` deleted --
    scoped to ``run_contract_gate``'s OWN module-global ``sys`` name only (via
    ``monkeypatch.setattr(run_contract_gate, "sys", ...)``), so the
    process-wide ``sys.modules`` singleton is never mutated. Every other
    attribute delegates to the real ``sys`` module unchanged.

    Simulates the production condition ``_resolve_arch_run_interpreter``
    documents in its own docstring: "this process is not itself running
    under pytest (e.g. a real ``des commit-slice`` CLI invocation)" -- the
    only way to reach its ``pytest_interpreter()`` fallback branch from
    inside a pytest-run test process.
    """

    def __getattr__(self, name: str) -> Any:
        return getattr(sys, name)

    @property
    def modules(self) -> dict[str, Any]:
        return {k: v for k, v in sys.modules.items() if k != "pytest"}


# venv.create + an offline `uv pip install` (cache-backed, no network hit --
# verified empirically to run in well under a second) is fast; the timeout is
# a generous bound against a wedged subprocess, not an expected duration.
_BUILD_TIMEOUT_SECONDS = 60


def _venv_python(venv_dir: Path) -> Path:
    """Path to the python executable inside a venv (mirrors the sibling
    convention in tests/build/test_python_for_under_pytestless_interpreter.py)."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _resolve_with_repo_root(capability: Capability | None, repo_root: Path) -> str:
    """Call ``python_for(capability, repo_root=repo_root)``.

    Wraps the call so TODAY's ``TypeError`` (the parameter does not exist --
    the diagnosed defect: interpreter resolution has no way to be told which
    repo it is targeting) surfaces as an explicit, named pytest FAILURE
    rather than an opaque call-signature ERROR -- RED for the reason under
    test, never a collection accident.
    """
    try:
        return python_for(capability, repo_root=repo_root)  # type: ignore[call-arg]
    except TypeError as exc:
        pytest.fail(
            "defect #79: python_for() does not accept repo_root= "
            f"({exc}) -- interpreter resolution has no way to target the "
            "repo being gated, so it falls back to whatever the INSTALLED "
            "des interpreter's own ladder resolves, regardless of which "
            "project `des commit-slice`/`des verify-slice-commit` is "
            "actually running against.",
            pytrace=False,
        )


@pytest.fixture(scope="module")
def consumer_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A hermetic beta-tester-style consumer repo: its own ``.venv``, its own
    trivial package, pytest installed ONLY inside that venv -- nWave/``des``
    is never installed there. Mirrors the charter's Precondition 1: "des
    installed globally/separately, NOT inside this .venv".

    Built with stdlib ``venv.create`` (no pip bundled -- ``with_pip=False``);
    ``pytest`` is then installed via ``uv pip install --python <venv>``,
    which resolves from uv's local wheel cache (offline-safe, sub-second) so
    the fixture never depends on live network access.

    Module-scoped: ONE venv build shared by every test in this file (mirrors
    the ``pytestless_python`` fixture convention in
    tests/build/test_python_for_under_pytestless_interpreter.py -- the
    filesystem-heavy build must not multiply per test function).
    """
    repo = tmp_path_factory.mktemp("consumer_repo")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "consumer-pkg"\nversion = "0.0.1"\n'
        'requires-python = ">=3.10"\n',
        encoding="utf-8",
    )
    pkg_dir = repo / "consumer_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_trivial.py").write_text(
        "def test_trivial():\n    assert True\n", encoding="utf-8"
    )

    venv_dir = repo / ".venv"
    venv.create(venv_dir, with_pip=False, clear=True)
    venv_python = _venv_python(venv_dir)
    assert venv_python.is_file(), f"venv python not created at {venv_python}"

    install = subprocess.run(
        ["uv", "pip", "install", "--python", str(venv_python), "pytest"],
        capture_output=True,
        text=True,
        timeout=_BUILD_TIMEOUT_SECONDS,
    )
    assert install.returncode == 0, (
        f"consumer venv pytest install failed:\n"
        f"stdout: {install.stdout}\nstderr: {install.stderr}"
    )
    # Fixture invariant: the consumer venv's pytest is genuinely reachable.
    probe = subprocess.run(
        [str(venv_python), "-c", "import pytest"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert probe.returncode == 0, (
        f"fixture invariant broken: consumer venv cannot import pytest "
        f"after install: {probe.stderr}"
    )
    return repo


# ---------------------------------------------------------------------------
# 1. Core RED — repo_root must steer resolution to the CONSUMER's own venv,
#    not the outer/des interpreter that happens to also be pytest-capable.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.negative_at
@pytest.mark.parametrize(
    "capability",
    ["pytest", None],
    ids=["pytest-capability-run-facet", "none-capability-e2-contract-gate-route"],
)
def test_python_for_resolves_consumer_venv_not_the_outer_interpreter(
    consumer_repo: Path, capability: Capability | None
) -> None:
    """``python_for(capability, repo_root=consumer_repo)`` must resolve THAT
    repo's own ``.venv`` interpreter -- not ``sys.executable`` (the outer
    process running THIS test suite, which is already pytest-capable and is
    exactly the wrong-interpreter trap: ``_has_capability`` only probes "can
    import pytest", never "belongs to this repo").

    Covers BOTH call sites the ground-truth RCA names: the ``"pytest"``
    capability (the run-facet, ``pytest_runner.pytest_interpreter``) and the
    ``None`` capability (the E2 contract-gate adapter route,
    ``PythonContractGateAdapter.collect_scope``/``run_suite``).
    """
    expected = str(_venv_python(consumer_repo / ".venv"))

    resolved = _resolve_with_repo_root(capability, consumer_repo)

    assert resolved == expected, (
        f"python_for({capability!r}, repo_root=consumer_repo) resolved "
        f"{resolved!r}, expected the consumer repo's own venv interpreter "
        f"{expected!r}."
    )
    # Negative (charter's sharpest oracle, GS-8): the wrong-interpreter
    # false-green must not happen -- the outer sys.executable must NOT win
    # just because it also happens to be pytest-capable.
    assert resolved != sys.executable, (
        "wrong-interpreter false-green: python_for must not fall back to "
        "the outer/des interpreter merely because it can import pytest -- "
        "that IS defect #79 (a des-runtime python wins rung-1 even though "
        "it does not own the target repo's dependencies)."
    )
    # Negative: must not silently reuse nwave-dev's OWN venv either (the
    # _uv_python()/_project_root() bug this defect is rooted in).
    assert not resolved.startswith(str(PROJECT_ROOT)), (
        "wrong-interpreter false-green: python_for must not resolve the "
        "nwave-dev repo's OWN .venv (the des-runtime venv) when repo_root "
        f"names a different repo ({consumer_repo}) -- a confident-looking "
        "wrong digest is worse than an honest refusal (charter negative "
        "oracle)."
    )


# ---------------------------------------------------------------------------
# 1.5. D1 BLOCKER — run_contract_gate.py's 3 unthreaded pytest_interpreter()
#      call sites (:446 _collect_scope_uncached, :634
#      _resolve_arch_run_interpreter, :1671 _run_contract_suite) sit on the
#      DEFAULT plain-consumer `des commit-slice` path -- no
#      `register_contract_gate("pytest")` facet exists, so a plain consumer
#      repo falls through to these. Section 1 above exercises `python_for`
#      directly and never reaches these sites; these witnesses close that
#      gap by spying on `run_contract_gate.pytest_interpreter` and asserting
#      it is called WITH `repo_root=<repo being gated>`.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_collect_scope_uncached_threads_repo_root_to_pytest_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """:446 -- ``_collect_scope_uncached`` (the ``gate_scope_digest``
    producer) must resolve its worker interpreter with
    ``repo_root=<repo being gated>``, not the installed des interpreter's
    own ladder. Today it calls ``pytest_interpreter()`` bare.
    """
    calls = _install_pytest_interpreter_spy(monkeypatch)

    with pytest.raises(_InterpreterResolutionRecorded):
        run_contract_gate._collect_scope_uncached(tmp_path)

    assert calls == [tmp_path], (
        "defect #79 site :446 (_collect_scope_uncached, the "
        "gate_scope_digest producer): pytest_interpreter() was called with "
        f"repo_root={calls!r}, expected [{tmp_path!r}] -- on a plain "
        "consumer repo this resolves the INSTALLED des interpreter instead "
        "of the target repo's own .venv, causing collection exit 4 -> "
        "SliceCommitIndeterminate/gate_scope_interpreter_unavailable."
    )


@pytest.mark.unit
def test_run_arch_invariant_set_threads_repo_root_to_pytest_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """:634 -- ``_resolve_arch_run_interpreter`` (reached from
    ``_run_arch_invariant_set``, the build-tier arch-invariant RUN) must
    resolve with ``repo_root=<repo being gated>`` on its
    ``pytest_interpreter()`` fallback branch. That branch only fires when
    the CALLING process is not itself running under pytest (per its own
    docstring) -- a real ``des commit-slice`` CLI invocation, never this
    test process -- so the "pytest"-in-``sys.modules`` short-circuit is
    faked OFF for ``run_contract_gate``'s own module-global ``sys`` only
    (the process-wide ``sys.modules`` singleton is untouched).
    """
    monkeypatch.setattr(run_contract_gate, "sys", _SysWithoutPytest())
    calls = _install_pytest_interpreter_spy(monkeypatch)

    with pytest.raises(_InterpreterResolutionRecorded):
        run_contract_gate._run_arch_invariant_set(tmp_path, [])

    assert calls == [tmp_path], (
        "defect #79 site :634 (_resolve_arch_run_interpreter, the "
        "build-tier arch-invariant RUN): pytest_interpreter() was called "
        f"with repo_root={calls!r}, expected [{tmp_path!r}] -- on a plain "
        "consumer repo this resolves the INSTALLED des interpreter, not "
        "the target repo's own .venv."
    )


@pytest.mark.unit
def test_run_contract_suite_threads_repo_root_to_pytest_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """:1671 -- ``_run_contract_suite`` (the verdict-driving full-suite RUN
    every plain consumer repo falls through to -- no
    ``register_contract_gate("pytest")`` facet exists by default) must
    resolve with ``repo_root=<repo being gated>``. Today it calls
    ``pytest_interpreter()`` bare, so ``passed = suite_code == 0`` is
    decided by the INSTALLED interpreter's collection of the CONSUMER
    repo -- exit 4, the exact ``SliceCommitIndeterminate``/Gate-Scope-0000
    symptom #79 claims fixed.
    """
    calls = _install_pytest_interpreter_spy(monkeypatch)

    with pytest.raises(_InterpreterResolutionRecorded):
        run_contract_gate._run_contract_suite(tmp_path)

    assert calls == [tmp_path], (
        "defect #79 site :1671 (_run_contract_suite, the verdict-driving "
        "full-suite RUN): pytest_interpreter() was called with "
        f"repo_root={calls!r}, expected [{tmp_path!r}] -- this is the "
        "DEFAULT path a plain consumer `des commit-slice` falls through to "
        "(no registered pytest ContractGatePort facet), so this is the "
        "sharpest reproduction of defect #79's claimed-fixed symptom."
    )


# ---------------------------------------------------------------------------
# 2. Guard — the already-working dogfood self-gate path must stay unchanged.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.parametrize(
    "capability",
    ["pytest", None],
    ids=["pytest-capability", "none-capability"],
)
def test_python_for_dogfood_path_unchanged_when_repo_root_is_nwave_dev(
    capability: Capability | None,
) -> None:
    """Guard: pointing ``repo_root`` at THIS repo (nwave-dev, the already-
    working self-gate case, charter Precondition 2) must resolve THIS
    repo's OWN dev-venv interpreter -- an ABSOLUTE, deterministic oracle,
    not an ambient baseline.

    D2 fix: the original guard compared against ``python_for(capability)``
    (no ``repo_root``) -- the AMBIENT rung-1 ``sys.executable``. That only
    equals the repo-scoped resolution when the TEST PROCESS itself happens
    to run under ``PROJECT_ROOT/.venv``. Under an INSTALLED interpreter
    (the exact target-machine-agnosticism scenario defect #79 is about)
    the two diverge on the SUCCESS case -- ``repo_root`` correctly
    overriding a stale ambient interpreter -- and the guard would fail for
    the wrong reason. The oracle is now ground-truth: the dev venv's own
    python path, independent of whatever interpreter runs this test.
    """
    expected = str(_venv_python(PROJECT_ROOT / ".venv"))

    resolved = _resolve_with_repo_root(capability, PROJECT_ROOT)

    assert resolved == expected, (
        f"repo_root=<nwave-dev root> resolved {resolved!r}, expected this "
        f"repo's own dev-venv interpreter {expected!r} -- the dogfood "
        "self-gate path must deterministically resolve PROJECT_ROOT/.venv, "
        "not whatever ambient interpreter happens to be running the test "
        "process."
    )


# ---------------------------------------------------------------------------
# 3. Negative — no-venv-anywhere must degrade LOUD, never a silent fallback.
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.negative_at
def test_python_for_refuses_silent_fallback_when_repo_root_has_no_venv_anywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No ``.venv`` under ``repo_root``, no ``VIRTUAL_ENV``, and every
    fallback-ladder rung forced incapable: ``python_for`` must raise
    ``InterpreterUnavailable`` -- NEVER silently return ``sys.executable``
    (the charter's sharpest negative oracle: an honest refusal beats a
    hollow ``0000...`` Gate-Scope). The message must name the checked path
    and reference the missing virtualenv, so the operator is told WHAT was
    checked and WHY it failed -- never a bare refusal (GDP-3). The existing
    ``des commit-slice`` catch of ``InterpreterUnavailable`` (sealing
    ``SliceCommitIndeterminate``/``gate_scope_interpreter_unavailable``)
    stays intact by construction: the exception TYPE is unchanged, only its
    trigger condition (repo-scoped, not global) is new.
    """
    empty_repo = tmp_path / "no_venv_anywhere"
    empty_repo.mkdir()
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    monkeypatch.setattr("des.runtime.interpreter._has_capability", lambda _i: False)
    monkeypatch.setattr("des.runtime.interpreter._uv_python", lambda: None)

    try:
        result: Any = python_for("pytest", repo_root=empty_repo)  # type: ignore[call-arg]
    except TypeError as exc:
        pytest.fail(
            "defect #79: python_for() does not accept repo_root= "
            f"({exc}) -- cannot exercise the no-venv-anywhere degrade-LOUD "
            "contract until the parameter exists.",
            pytrace=False,
        )
    except InterpreterUnavailable as exc:
        message = str(exc)
        assert str(empty_repo) in message, (
            "InterpreterUnavailable must name the checked repo_root path "
            f"({empty_repo}) so the operator knows WHAT was checked: "
            f"{message!r}"
        )
        assert "venv" in message.lower(), (
            "InterpreterUnavailable must reference the missing virtualenv "
            f"so the operator knows WHY it failed: {message!r}"
        )
        return

    pytest.fail(
        "python_for() must raise InterpreterUnavailable when repo_root has "
        f"no venv anywhere and every ladder rung is incapable -- instead it "
        f"silently returned {result!r} (the exact wrong-interpreter "
        "false-green the charter forbids)."
    )
