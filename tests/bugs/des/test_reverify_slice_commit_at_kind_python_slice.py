"""Regression: `des reverify-slice-commit` mis-routes a Python-only slice to
cargo and hangs silently on a Rust-primary repo.

RCA: docs/feature/fix-reverify-slice-commit-at-kind/deliver/rca.md

Two independent root causes, both pinned here.

BRANCH A -- coverage gap (wrong runner resolved):
    ``reverify_slice_commit.py`` ``_build_parser()`` (:82-105) defines only
    ``--repo --feature-id --slice-id --commit`` -- no ``--at-kind``, so the
    command cannot be told the committed slice is Python. The child argv
    falls through to ``run_contract_gate._mode_run_suite(repo)`` (:1892),
    which has NO ``at_kind`` param (unlike ``_mode_verify_gate_scope``) --
    ``_maybe_route_through_runner_whole_tree(repo)`` (:1920) resolves the
    runner from a pure ROOT-LOCKFILE scan (``resolve_runner(repo, None)``,
    feature/at_kind-blind), so a Python-only slice inside a Rust-primary repo
    (root ``Cargo.toml`` present) mis-routes through cargo.

BRANCH B -- silent unbounded hang (systemic, not reverify-local):
    ``cargo_runner.py`` ``run_cargo_scope`` (:108) and ``list_cargo_scope``
    (:181) shell ``subprocess.run(...)`` with NO ``timeout=``.
    ``_reverify_core._run_gate`` (:336-355) spawns the gate child via
    ``des_spawn`` with no ``timeout=`` either (defense-in-depth). The
    ``WholeTreeRunnerResolved`` preamble event
    (``run_contract_gate._emit_whole_tree_resolved``, :2674-2696) carries only
    ``{event, runner, routed, digest_degraded}`` -- no ``what``/``why``/``how``
    (unlike the sibling ``BuildTierResourceWait``/``BuildTierRefused`` events),
    so a blocked reverify surfaces no reason.

CI-SAFE / NEVER invokes real cargo: cargo resolution is stubbed
(``cargo_runner.resolve_tool``) and every cargo-bound ``subprocess.run`` call
is CAPTURED rather than executed -- mirrors
``tests/bugs/des/test_cargo_digest_reuses_worktree_target_dir.py``. No real
``cargo``/``nextest`` is ever spawned by this file.

Driving surface (Mandate-13 driving-port-only): the RCA names the exact
production seams under regression (``reverify_slice_commit._build_parser``,
``run_contract_gate._mode_run_suite``/``_emit_whole_tree_resolved``,
``cargo_runner.run_cargo_scope``/``list_cargo_scope``,
``_reverify_core._run_gate``) -- these ARE the composition-root entry points
the fix touches (RCA "Minimal fix" section), mirroring the established
adapter-direct precedent (``test_cargo_digest_reuses_worktree_target_dir.py``,
``test_cargo_scope_nomatch_is_indeterminate.py``): the seams under regression
are private, un-exercisable through a stable public signature the fix has not
chosen yet, so the AT drives them at their own module boundary rather than
coupling to an unmade CLI/E2E signature.

Fail-for-right-reason discipline (per the authoring brief): every assertion
below fails today for a REAL business reason -- a routing/verdict/payload
mismatch -- never an argparse-unrecognized-flag crash, never a TypeError from
an unsupported kwarg, never an import/collection error. Where the RCA's fix
adds a new optional param (``at_kind`` on ``_mode_run_suite``), this file
calls it through a TypeError-tolerant helper (``_invoke_mode_run_suite``) so
the SAME assertion is RED today (param absent -> old behaviour observed) and
GREEN once the crafter adds the param per the RCA's own signature choice.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from des.adapters.driven.runner import cargo_runner
from des.adapters.driven.runner.tool_discovery import ToolResolution
from des.cli import _reverify_core, reverify_slice_commit, run_contract_gate
from des.ports.test_runner_port import RunnerAdapter


_ADAPTER = RunnerAdapter(name="cargo-test")
_SCOPED_COMMAND = ("cargo", "nextest", "run", "--test", "ws_driver")
# Non-empty nextest-list-shaped stdout so the list facet does not itself raise
# an (unrelated) empty-scope INDETERMINATE -- see `cargo_runner._parse_nextest_list`.
# FLAT shape (matches the golden fixture in
# tests/des/unit/adapters/driven/runner/test_cargo_nextest_flat_list_parse.py):
# a single non-indented ``<binary-id> <test-path>`` line, space-separated, no
# trailing ``:`` header, no indent -- the REAL `cargo nextest list` output
# shape the current parser contracts for. The prior grouped/indented literal
# (``"ws_driver:\n    it_works\n"``) parsed to ZERO identities under the flat
# parser, masking the timeout=/TimeoutExpired assertion below it ever ran.
_LIST_STDOUT = "ws_driver it_works\n"


# --- fixture builders: plain filesystem, NO git required for these seams ---


def _rust_primary_repo_with_python_only_slice(tmp_path: Path) -> Path:
    """A Rust-primary target root (root ``Cargo.toml``, no pyproject.toml /
    pytest.ini / package.json / go.mod) whose committed slice is otherwise
    Python-only (``scripts/`` + ``tests/scripts/`` + ``docs/``, no ``.rs``) --
    the RCA Observable fixture shape verbatim.

    ``resolve_runner(repo, None)`` (whole-tree, feature/at_kind-BLIND) matches
    exactly ONE lockfile row (``Cargo.toml``) and fast-paths to
    ``RunnerAdapter("cargo-test")`` regardless of which files the slice under
    reverify actually touches -- the RCA Branch A defect.
    """
    repo = tmp_path / "rust-primary-repo"
    repo.mkdir()
    (repo / "Cargo.toml").write_text('[package]\nname = "primary"\nversion = "0.1.0"\n')
    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "hello.py").write_text("def hello() -> str:\n    return 'hi'\n")
    tests_scripts_dir = repo / "tests" / "scripts"
    tests_scripts_dir.mkdir(parents=True)
    (tests_scripts_dir / "test_hello.py").write_text(
        "from scripts.hello import hello\n\n\ndef test_hello() -> None:\n"
        "    assert hello() == 'hi'\n"
    )
    docs_dir = repo / "docs"
    docs_dir.mkdir()
    (docs_dir / "notes.md").write_text("# notes\n")
    return repo


# --- stubs: cargo resolution + captured (never-executed) cargo subprocess ---


def _stub_cargo_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    """cargo "resolves" to a fake path -- no real cargo binary is touched."""
    monkeypatch.setattr(
        cargo_runner,
        "resolve_tool",
        lambda name, known_locations: ToolResolution(
            rung="on-path", path="/fake/cargo"
        ),
    )


def _stub_cargo_call_captured(
    monkeypatch: pytest.MonkeyPatch,
    captured_argv: list[list[str]],
    *,
    cargo_returncode: int = 0,
    cargo_stdout: str = _LIST_STDOUT,
) -> None:
    """Capture every cargo-bound ``subprocess.run`` call -- NEVER execute it.

    Non-cargo argv (e.g. a ``git`` probe some seam might issue) is routed to
    the REAL ``subprocess.run`` unchanged, mirroring
    ``test_cargo_digest_reuses_worktree_target_dir.py``'s ``_stub_cargo_call``.
    """
    real_run = subprocess.run

    def _fake(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if argv and Path(argv[0]).name == "git":
            return real_run(argv, **kwargs)
        captured_argv.append(list(argv))
        return subprocess.CompletedProcess(
            args=argv, returncode=cargo_returncode, stdout=cargo_stdout, stderr=""
        )

    monkeypatch.setattr(subprocess, "run", _fake)


def _invoke_mode_run_suite(repo: Path, *, at_kind: str) -> int:
    """Call ``_mode_run_suite`` with ``at_kind`` if the fix has added the
    param; fall back to the pre-fix ``(repo)``-only signature so THIS test
    RUNS and asserts on the ROUTING OUTCOME (a real business assertion)
    rather than crashing on an unsupported kwarg (the "not a TypeError"
    fail-for-right-reason discipline).
    """
    try:
        return run_contract_gate._mode_run_suite(repo, at_kind=at_kind)  # type: ignore[call-arg]
    except TypeError as exc:
        if "at_kind" not in str(exc):
            raise
        return run_contract_gate._mode_run_suite(repo)


# --- BRANCH A -- coverage gap: --at-kind absent, cargo mis-route ------------


def test_reverify_slice_commit_accepts_at_kind_pytest_regression() -> None:
    """`des reverify-slice-commit` must accept ``--at-kind pytest-regression``.

    RCA Branch A item 1: ``_build_parser()`` (reverify_slice_commit.py:82-105)
    defines only ``--repo --feature-id --slice-id --commit`` today. Rather
    than let argparse's own "unrecognized arguments" crash (`SystemExit`) be
    the observed failure, this test CATCHES it and converts the absence into
    an explicit, business-framed assertion failure naming the missing flag --
    the "not an argparse-unrecognized-flag crash" discipline.
    """
    parser = reverify_slice_commit._build_parser()
    argv = [
        "--repo",
        "/does/not/need/to/exist/for/parsing",
        "--feature-id",
        "fix-reverify-slice-commit-at-kind",
        "--slice-id",
        "slice-01",
        "--commit",
        "HEAD",
        "--at-kind",
        "pytest-regression",
    ]
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        pytest.fail(
            f"des reverify-slice-commit rejected --at-kind pytest-regression "
            f"(argparse exit {exc.code}) -- _build_parser() carries no "
            "--at-kind coverage yet (RCA Branch A item 1); the command "
            "cannot be told a committed slice is Python"
        )
    assert getattr(args, "at_kind", None) == "pytest-regression", (
        "--at-kind pytest-regression was accepted by the parser but did not "
        f"bind to args.at_kind -- got {getattr(args, 'at_kind', '<absent>')!r}"
    )


def test_pytest_regression_slice_reverify_skips_cargo_whole_tree_route(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """NEGATIVE: a Python-only slice reverify (``at_kind == "pytest-regression"``)
    must NEVER route the whole-tree contract gate through cargo, even when the
    repo root resolves cargo (RCA Branch A items 2-3, the routing/verdict
    assertion the authoring brief calls for).

    Active-RED at HEAD: ``_mode_run_suite``/``_maybe_route_through_runner_whole_tree``
    ignore ``at_kind`` entirely (the RCA-cited coverage gap) -- the fallback
    leg of ``_invoke_mode_run_suite`` calls the pre-fix ``(repo)``-only
    signature, which resolves the runner from a pure root-lockfile scan and
    mis-routes through cargo REGARDLESS of the slice's actual language. cargo
    is never actually executed (stubbed resolution + captured subprocess) --
    only ATTEMPTED-invocation is observed.
    """
    repo = _rust_primary_repo_with_python_only_slice(tmp_path)
    captured_argv: list[list[str]] = []
    _stub_cargo_resolved(monkeypatch)
    _stub_cargo_call_captured(monkeypatch, captured_argv)

    _invoke_mode_run_suite(repo, at_kind="pytest-regression")

    assert not captured_argv, (
        "a pytest-regression (Python-only) slice reverify must NOT route the "
        "whole-tree contract gate through cargo (RCA Branch A) -- the wrong "
        f"behaviour WAS produced: cargo was invoked with {captured_argv!r}"
    )


# --- BRANCH B -- silence: unbounded subprocess + no surfaced reason --------


@pytest.mark.parametrize(
    ("facet_name", "invoke"),
    [
        (
            "run_cargo_scope",
            lambda repo: cargo_runner.run_cargo_scope(_ADAPTER, repo, _SCOPED_COMMAND),
        ),
        (
            "list_cargo_scope",
            lambda repo: cargo_runner.list_cargo_scope(_ADAPTER, repo),
        ),
    ],
)
def test_cargo_runner_subprocess_is_time_bounded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    facet_name: str,
    invoke: Any,
) -> None:
    """The cargo runner subprocess MUST be time-bounded (RCA Branch B item
    b.1) -- both ``run_cargo_scope`` (:108) and ``list_cargo_scope`` (:181)
    shell ``subprocess.run(...)`` with no ``timeout=`` today, which is how a
    blocked reverify hangs SILENTLY (observed at 240s and 900s, empty output).

    Active-RED at HEAD: neither facet passes ``timeout=`` to ``subprocess.run``.
    """
    captured: dict[str, Any] = {}

    def _fake(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout=_LIST_STDOUT, stderr=""
        )

    _stub_cargo_resolved(monkeypatch)
    monkeypatch.setattr(subprocess, "run", _fake)

    invoke(tmp_path)

    assert captured["kwargs"].get("timeout") is not None, (
        f"cargo_runner.{facet_name}'s subprocess.run call must carry a "
        f"timeout= bound (RCA Branch B item b.1) -- got kwargs "
        f"{sorted(captured['kwargs'])}, no 'timeout' key present"
    )


def test_reverify_gate_child_spawn_is_time_bounded_defense_in_depth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``_reverify_core._run_gate``'s ``des_spawn`` child must ALSO carry a
    ``timeout=`` bound, defense-in-depth (RCA Branch B item b.2) -- distinct
    from the cargo-runner-level bound above: this is the boundary
    ``_reverify_core._compose_gates`` shells E1/E2 through, and a blocked
    grandchild (cargo, unbounded) currently hangs the whole reverify command
    with the child's stdout/stderr silently DISCARDED (``_run_gate`` keeps
    only ``.returncode``).

    Active-RED at HEAD: ``_run_gate`` calls ``des_spawn(None, *args, cwd=repo,
    capture_output=True, text=True)`` -- no ``timeout=`` kwarg. No real
    subprocess is spawned: ``des_spawn`` itself is monkeypatched.
    """
    captured: dict[str, Any] = {}

    def _fake_des_spawn(
        capability: object, *args: str, **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=list(args), returncode=0)

    monkeypatch.setattr(_reverify_core, "des_spawn", _fake_des_spawn)

    _reverify_core._run_gate(
        tmp_path, "des.cli.run_contract_gate", "--repo", str(tmp_path)
    )

    assert captured["kwargs"].get("timeout") is not None, (
        "_reverify_core._run_gate must bound its des_spawn child with a "
        "timeout= (RCA Branch B item b.2, defense-in-depth) -- got kwargs "
        f"{sorted(captured['kwargs'])}, no 'timeout' key present"
    )


def test_whole_tree_resolved_event_surfaces_what_why_how(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A blocked reverify must SURFACE A REASON, never an empty-output hang
    (RCA Branch B item b.4) -- ``_emit_whole_tree_resolved`` (:2674-2696) is
    the preamble event a routed whole-tree run always emits BEFORE any
    run/digest leg, so it is the earliest, always-present seam to carry the
    routing REASON into the terminal payload. The sibling events
    ``BuildTierResourceWait``/``BuildTierRefused`` already carry
    ``what``/``why``/``how`` keys -- this event does not yet.

    Active-RED at HEAD: the emitted ``WholeTreeRunnerResolved`` JSON carries
    only ``{event, runner, routed, digest_degraded}`` -- no ``what``, no
    ``why``, no ``how``.
    """
    run_contract_gate._emit_whole_tree_resolved(
        "cargo-test", routed=True, digest_degraded=True
    )

    stderr_lines = [
        line for line in capsys.readouterr().err.strip().splitlines() if line
    ]
    assert stderr_lines, "_emit_whole_tree_resolved must emit a JSON line to stderr"
    payload = json.loads(stderr_lines[-1])
    missing = sorted(key for key in ("what", "why", "how") if key not in payload)
    assert not missing, (
        "WholeTreeRunnerResolved must surface what/why/how the whole-tree run "
        f"was routed through {payload.get('runner')!r} (RCA Branch B item "
        f"b.4, matching BuildTierResourceWait/BuildTierRefused) -- missing "
        f"keys {missing!r} in payload {payload!r}"
    )


# --- non-goal guard: verify_fresh_clone.py stays untouched by this fix -----


@pytest.mark.negative_at
def test_verify_fresh_clone_gate_does_not_import_reverify_or_cargo_runner() -> None:
    """``verify_fresh_clone.py`` is a structurally SEPARATE true-scratch gate
    -- the RCA's explicit Non-goal is that this fix must not weaken it.
    Guard: it carries no import of ``reverify_slice_commit`` / ``_reverify_core``
    / ``cargo_runner`` today AND must not gain one.

    Passes TODAY -- must keep passing after the fix.
    """
    import des.cli.verify_fresh_clone as verify_fresh_clone_module

    source = Path(verify_fresh_clone_module.__file__).read_text(encoding="utf-8")

    forbidden = ("reverify_slice_commit", "_reverify_core", "cargo_runner")
    present = [name for name in forbidden if name in source]
    assert not present, (
        "verify_fresh_clone.py must stay structurally independent of the "
        f"reverify machinery this fix touches -- found references to {present!r}"
    )
