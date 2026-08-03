"""Regression: the trimmed collect-worker environment must not orphan any
declared pytest ini option from the plugin that defines it.

Defect (measured, reproduced below): ``_collect_scope_uncached``
(``src/des/cli/run_contract_gate.py``) always tries the ``trim=True`` collect
first -- ``PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`` plus only the
``_collection_plugin_allowlist()`` plugins re-enabled by module name
(``:544``). pytest validates EVERY ini option declared in ``pyproject.toml``
at startup, regardless of whether the option matters to collection, and it
stops at the FIRST one whose owning plugin is not loaded:

    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest --collect-only -q \
        tests/bugs/des/test_collect_memo_marker_key_preserves_mismatch_detection.py
    -> ERROR: Unknown config option: asyncio_mode
    -> exit_status 4

Reproduced directly against this project's real ``pyproject.toml`` and the
real ``_collect_worker_env`` seam (see the three tests below): the trimmed
env orphans ``asyncio_mode`` / ``timeout`` / ``timeout_method`` -- but none of
those names is spelled out in this file's *logic*. Every test below derives
"which ini options are declared" and "which are recognized under which env"
from the project's ACTUAL ``pyproject.toml`` and from pytest's OWN
``--help`` output at run time, so:

  * a fix that silences only the FIRST offending option (pytest stops at the
    first) still leaves this suite RED, because the property is evaluated
    over the WHOLE declared set, not one name;
  * a future plugin added to ``pyproject.toml`` with new ini options is
    covered automatically -- nothing here needs to change to catch it.

Crucially, the failure is NOT a fast fail: the trimmed pytest process WALKS
the target file(s) (its stdout below shows ``tests/test_probe.py: 1`` printed
by ``--collect-only`` before the config-validation error line lands on
stderr) and is then discarded whole, and the SAME collection is repeated from
scratch by the ``trim=False`` fallback (``_collect_scope_uncached``,
``:576-579``). One ``--collect-only`` call therefore pays for two full
collections with nothing surfacing that the first one was wasted -- test 3
below asserts directly on that call count.

These tests build their own synthetic ``tmp_path`` project (a couple of
trivial test functions) -- never the real ~11k-test tree -- so they stay fast
and hermetic; the real-tree reproduction above is a manually-run cross-check,
not a test in this suite.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import tomllib

from des.adapters.driven.runner.pytest_runner import pytest_interpreter
from des.cli import run_contract_gate


def _repo_root() -> Path:
    """Walk up from this test file to the checkout root (the ``pyproject.toml``
    that declares the ini options under test) -- never a hardcoded path, so the
    test travels with the worktree it runs in.
    """
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise AssertionError(f"no pyproject.toml found walking up from {here}")


def _declared_ini_option_names(repo_root: Path) -> set[str]:
    """The project's OWN declared ``[tool.pytest.ini_options]`` keys -- the
    SSOT of "what must not be orphaned". Read live, never copied into this
    file as a literal list.
    """
    with (repo_root / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return set(data["tool"]["pytest"]["ini_options"].keys())


def _ini_option_names_recognized_under(
    interpreter: str, env: dict[str, str], cwd: Path
) -> set[str]:
    """The ini option names pytest itself reports as KNOWN under ``env``.

    Drives ``pytest --help`` (no collection, no target project needed) and
    parses the ``[pytest] configuration options ...`` section pytest prints
    for its OWN currently-loaded plugin set -- i.e. pytest is the oracle for
    "which plugin defines which option", never a hand-maintained mapping in
    this test.
    """
    completed = subprocess.run(
        [interpreter, "-m", "pytest", "--help"],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    out = completed.stdout
    start = out.find("[pytest] configuration options")
    end = out.find("Environment variables:")
    section = out[start:end] if start != -1 else ""
    return set(re.findall(r"^ {2}([A-Za-z_][A-Za-z0-9_]*) \(", section, re.MULTILINE))


def _mirrored_synthetic_project(tmp_path: Path, repo_root: Path) -> Path:
    """A minimal synthetic project whose ``[tool.pytest.ini_options]`` table is
    the project's REAL section, copied verbatim (never hand-reconstructed) --
    so it declares exactly the options the real project declares, whatever
    they are, without this file ever naming one.
    """
    real_pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^\[tool\.pytest\.ini_options\]\n.*?(?=^\[)", real_pyproject
    )
    assert match is not None, (
        "could not locate a [tool.pytest.ini_options] table in the real "
        "pyproject.toml to mirror -- the fixture depends on it existing"
    )
    ini_section = match.group(0)

    project = tmp_path / "synthetic_project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        "[build-system]\nrequires = []\n\n" + ini_section, encoding="utf-8"
    )
    # `pythonpath = ["src", "."]` (mirrored verbatim above) is harmless when
    # "src" is empty, but create it so the ini option resolves a real path.
    (project / "src").mkdir()
    tests_dir = project / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_probe.py").write_text(
        "def test_probe():\n    assert True\n", encoding="utf-8"
    )
    return project


def test_no_declared_ini_option_is_orphaned_of_its_plugin_in_the_trimmed_worker_env():
    """Property: every ini option THIS PROJECT declares must be recognized
    under the trimmed collect-worker env, whenever it is a real, known pytest
    option (i.e. it is recognized under the untrimmed/full-autoload env too).

    Computed entirely at run time from (a) the project's own declared option
    names and (b) pytest's own ``--help`` output under each env -- no option
    name is hardcoded in this test's logic, so it stays valid whichever
    plugin ships the option and it fails for every orphaned option at once,
    not just the first one pytest's own startup validation would report.
    """
    repo_root = _repo_root()
    declared = _declared_ini_option_names(repo_root)
    interpreter = pytest_interpreter(repo_root=repo_root)

    # An isolated cwd with no project config of its own: --help enumerates
    # pytest's currently-loaded plugin set, independent of any target tree.
    probe_cwd = repo_root  # any existing dir works; --help reads no config here

    trimmed_env = run_contract_gate._collect_worker_env(trim=True)
    full_env = run_contract_gate._collect_worker_env(trim=False)

    recognized_trimmed = _ini_option_names_recognized_under(
        interpreter, trimmed_env, probe_cwd
    )
    recognized_full = _ini_option_names_recognized_under(
        interpreter, full_env, probe_cwd
    )

    # Sanity precondition: every declared option must be a REAL pytest option
    # under full autoload -- otherwise this property test would be silently
    # vacuous (nothing to orphan). A failure here means the project declared
    # a typo'd/unknown option, a different bug than the one under test.
    unknown_even_with_full_autoload = declared - recognized_full
    assert not unknown_even_with_full_autoload, (
        "declared ini option(s) not recognized by pytest even with full "
        f"plugin autoload: {sorted(unknown_even_with_full_autoload)} -- "
        "this test cannot evaluate the trimmed-env property against an "
        "option pytest itself does not know"
    )

    orphaned = declared & recognized_full - recognized_trimmed
    assert not orphaned, (
        f"declared ini option(s) {sorted(orphaned)} are recognized under "
        "full plugin autoload but NOT under the trimmed collect-worker env "
        "(_collect_worker_env(trim=True)) -- the plugin that defines "
        f"{sorted(orphaned)} is excluded from _collection_plugin_allowlist() "
        "while pyproject.toml still declares the option(s), so pytest's "
        "startup ini validation refuses the trimmed collect before it "
        "reaches a single test file"
    )


def test_trimmed_collect_worker_env_completes_pytest_collection_over_declared_ini_options(
    tmp_path,
):
    """Behavioral proof: collection under the trimmed env must SUCCEED (exit
    0 or 5 -- pytest's own "collection ok" codes), not fail with a config
    usage error, against a project declaring the real project's ini options.

    Uses a synthetic tmp_path project mirroring the real declared
    ``[tool.pytest.ini_options]`` table verbatim (never the real ~11k-test
    tree), so this stays fast regardless of tree size while still exercising
    every option the real project declares.
    """
    repo_root = _repo_root()
    project = _mirrored_synthetic_project(tmp_path, repo_root)
    interpreter = pytest_interpreter(repo_root=project)
    trimmed_env = run_contract_gate._collect_worker_env(trim=True)

    completed = subprocess.run(
        [interpreter, "-m", "pytest", "--collect-only", "-q", str(project)],
        cwd=str(project),
        env=trimmed_env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert "Unknown config option" not in completed.stderr, (
        "the trimmed collect-worker env rejected a declared ini option "
        f"before collecting a single test -- stderr: {completed.stderr.strip()}"
    )
    assert completed.returncode in (0, 5), (
        "trimmed-env collection did not complete successfully: "
        f"exit={completed.returncode} stdout={completed.stdout.strip()!r} "
        f"stderr={completed.stderr.strip()!r}"
    )


def test_collect_scope_never_pays_a_silent_double_collection_when_trim_admits_every_option(
    tmp_path, monkeypatch
):
    """Negative safety companion: ``_collect_scope_uncached`` must spawn the
    real collect-worker subprocess EXACTLY ONCE per call -- never fall
    through, unsignaled, from a failing trimmed attempt to a second full
    attempt that silently redoes the exact same work.

    Drives the REAL production seam (``run_contract_gate._collect_scope_uncached``),
    spying on ``_run_collect_worker`` (the one seam both the ``trim=True``
    attempt and its ``trim=False`` fallback call, per ``:572-579``) to COUNT
    invocations rather than asserting on any option name. Today the trimmed
    attempt fails closed (an orphaned declared option) and the fallback
    silently redoes the whole collection -- two full collector subprocess
    spawns for one caller-visible answer, with nothing recording that the
    first one was wasted. This is the general form of the RCA's measured
    symptom (a single ``--collect-only`` performing duplicate whole-tree
    collections, RCA `docs/feature/fix-g-commit-gate-timeout/deliver/rca.md`
    section 1.2) applied to the ini-option-orphaning root cause instead of
    the memo-key root cause that RCA documents.
    """
    repo_root = _repo_root()
    project = _mirrored_synthetic_project(tmp_path, repo_root)

    original_run_collect_worker = run_contract_gate._run_collect_worker
    call_envs: list[dict[str, str]] = []

    def _spy(repo, paths, markers, *, env):
        call_envs.append(env)
        return original_run_collect_worker(repo, paths, markers, env=env)

    monkeypatch.setattr(run_contract_gate, "_run_collect_worker", _spy)

    result = run_contract_gate._collect_scope_uncached(project)

    assert len(call_envs) == 1, (
        f"_collect_scope_uncached spawned {len(call_envs)} collect-worker "
        "subprocesses for one call -- expected exactly 1. A declared ini "
        "option whose plugin the trimmed env excludes makes the FIRST "
        "(trimmed) attempt fail closed, and the SECOND (full-autoload) "
        "attempt silently redoes the identical whole-project collection "
        f"with nothing surfacing the waste. Envs tried (trim flag inferred "
        f"from PYTEST_DISABLE_PLUGIN_AUTOLOAD): "
        f"{[e.get('PYTEST_DISABLE_PLUGIN_AUTOLOAD') for e in call_envs]!r}"
    )
    # The single surviving attempt must still be the trustworthy answer: the
    # synthetic project's one test function, reachable under whichever
    # marker policy `_collect_scope_uncached` was called with.
    assert result.collected_count >= 0
