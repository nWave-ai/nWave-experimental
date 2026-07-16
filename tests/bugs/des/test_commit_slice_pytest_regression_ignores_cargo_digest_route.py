"""Regression: a ``--at-kind pytest-regression`` slice on a Rust-primary repo
must NOT route its Gate-Scope digest (or its verify leg) through cargo, and a
genuinely-missing ``--regression-test-file`` must surface a NAMED reason.

RCA (2 disjoint root causes sharing one commit-slice run, both CONFIRMED):

**Root Cause A (the primary blocker).** ``commit_slice.py`` Step 3 computes
the Gate-Scope digest UNCONDITIONALLY via
``_maybe_route_digest_through_runner(repo)`` -> ``resolve_runner(repo, None)``
(``run_contract_gate.py:2745-2767``, ``feature=None`` hardcoded). With
``feature=None``, ``resolve()`` (``test_runner_port.py:239-278``) scans
lockfiles at the repo ROOT only -- on a Rust-primary repo (``Cargo.toml`` at
root, no ``pyproject.toml``/``pytest.ini``) it picks "cargo-test"
UNCONDITIONALLY, regardless of the declared ``--at-kind``. When the slice
being committed is Python-only (a ``.py`` production file + a ``.py``
regression test, zero ``.rs`` touched) and the crate carries no ``#[test]``,
cargo's OWN enumerate facet reports an empty scope -> ``RunnerAdapterUnavailable``
-> the digest leg degrades LOUD -> ``SliceCommitIndeterminate`` (reason
``gate_scope_runner_unavailable``) -- never reaching ``SliceCommitVerified``,
even though the declared Python work is genuine and its own behavioral
attestation (``--regression-test-file``) passes cleanly. The feature-scoped
``runner.json`` escape hatch is structurally unreachable from this call (it
only special-cases ``feature is not None``).

FIX A (RCA-recommended, minimal, contained to ``commit_slice.py``): when
``args.at_kind == "pytest-regression"``, the digest/verify legs must NOT be
routed through the whole-tree runner seam -- a pytest-regression slice is
Python-specific by construction, so cargo is never the correct digest/verify
route for it. ``gherkin``-kind slices on the SAME cargo-resolved repo must
keep routing through cargo exactly as today (the "don't over-correct" pin,
scenario 2 below).

**Root Cause B (message-honesty gap).** ``_run_regression_gate``
(``verify_slice_commit_completeness.py:556-573``) returns
``(_GATE_INDETERMINATE_EXIT_CODE, None, None)`` for BOTH
``test_path.is_file() == False`` and ``InterpreterUnavailable`` -- collapsing
two distinct causes into one reason-less generic fallback: ledger
``reason == "pytest_regression_file_unrunnable"`` and the surfaced ``error``
text always reads "...could not be run on the committed tree (missing or
uncollectible)...", regardless of which of the two actually happened.

FIX B: ``_run_regression_gate`` must return a NAMED reason distinguishing the
two causes -- e.g. ``regression_test_file_missing_on_committed_tree`` for a
genuinely absent file -- so the honest ``SliceCommitIndeterminate`` record
names WHICH cause fired (the standing what/why/how mandate).

Charter: docs/product/expectations/fix-runner-resolves-per-scope-language/
verification-runs-the-runner-matching-the-committed-work.md

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process): the REAL
``des.cli.commit_slice.main()`` CLI driver -- the exact production entry
every crafter commit goes through (verbatim in-process + ``capsys`` shape
reused from ``tests/bugs/des/test_commit_slice_gates_run_before_commit.py``).
A FAKE, deterministic, chmod+x ``cargo`` script is prepended to ``PATH`` via
``monkeypatch`` (no real Rust toolchain required; pattern reused from
``tests/build/gate_scope_digest_runner_agnostic/acceptance/
test_gate_scope_digest_cargo.py``) -- ``resolve_tool``'s rung 1
(``shutil.which``) reads the live process ``PATH`` at call time, so this
works identically in-process.

GIT SAFETY: every git call below targets the DISPOSABLE ``tmp_path`` fixture
only (``cwd=root``, never a bare git config against the real project repo).

THIS FILE IS TEST-ONLY. No production code is touched by this authoring pass.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main


_GATE_SCOPE_TRAILER_RE = re.compile(r"^Gate-Scope:\s*([0-9a-f]{64})\s*$", re.MULTILINE)
_VACUOUS_DIGEST = hashlib.sha256(b"").hexdigest()

_FAKE_NEXTEST_BINARY = "polyglot_fixture"
_FAKE_NEXTEST_TESTS = ("digest::verifies_alpha", "digest::verifies_beta")
_EXPECTED_CARGO_NODE_IDS = tuple(
    f"{_FAKE_NEXTEST_BINARY}::{test}" for test in _FAKE_NEXTEST_TESTS
)


# ---------------------------------------------------------------------------
# expected-digest oracle (the documented public contract: sha256 of the
# sorted, newline-joined, deduplicated node-id set) -- computed locally
# (stdlib) so this AT never imports production internals in-process.
# ---------------------------------------------------------------------------


def _expected_gate_scope_digest(node_ids: tuple[str, ...]) -> str:
    joined = "\n".join(sorted(set(node_ids)))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# fixture builders (disposable git repos; every git write targets `root` only)
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_polyglot_fixture(root: Path) -> Path:
    """A Rust-primary repo (``Cargo.toml`` at root, ZERO committed
    ``#[test]``s) that also carries genuine, already-committed Python work.

    Root carries NO ``pyproject.toml``/``pytest.ini``/``package.json``/
    ``go.mod`` -- ``test_runner_port.resolve()`` therefore matches
    ``Cargo.toml`` as the SOLE recognized lockfile (the single-match fast
    path, no disambiguation needed) regardless of which language a given
    SLICE actually touches -- exactly the RCA's "picks cargo-test (Cargo.toml
    present)" symptom.
    """
    fixture = root / "repo"
    (fixture / "src").mkdir(parents=True)
    (fixture / "Cargo.toml").write_text(
        '[package]\nname = "polyglot_fixture"\nversion = "0.0.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    (fixture / "src" / "lib.rs").write_text(
        "pub fn answer() -> i32 { 42 }\n", encoding="utf-8"
    )
    (fixture / "scripts").mkdir()
    (fixture / "scripts" / "tool.py").write_text(
        "def greet() -> str:\n    return 'hi'\n", encoding="utf-8"
    )
    _git(fixture, "init", "-q")
    _git(fixture, "config", "user.email", "atdd@nwave.ai")
    _git(fixture, "config", "user.name", "atdd")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", "chore: polyglot fixture baseline")
    return fixture


def _init_plain_python_repo(root: Path) -> Path:
    """A plain, cargo-free repo -- isolates Root-Cause-B's message-honesty
    fix from Root-Cause-A's runner-routing fix (independent variables)."""
    fixture = root / "repo"
    fixture.mkdir(parents=True)
    (fixture / "README.md").write_text("# fixture\n", encoding="utf-8")
    _git(fixture, "init", "-q")
    _git(fixture, "config", "user.email", "atdd@nwave.ai")
    _git(fixture, "config", "user.name", "atdd")
    _git(fixture, "add", "-A")
    _git(fixture, "commit", "-q", "-m", "chore: plain fixture baseline")
    return fixture


def _plant_fake_cargo(bin_dir: Path, *, list_exit: int) -> None:
    """A REAL chmod+x fake ``cargo`` -- deterministic, no Rust toolchain
    needed (verbatim shape from ``test_gate_scope_digest_cargo.py``).

    ``list_exit``: ``0`` -> a well-formed 2-test ``nextest list`` (non-empty
    scope); ``4`` -> "no tests to run" (the adapter's own empty-scope ->
    ``RunnerAdapterUnavailable`` mapping). ``nextest run`` always reports
    GREEN -- the legs under test never need a red cargo run.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    if list_exit == 0:
        list_body = (
            f'  echo "{_FAKE_NEXTEST_BINARY}:"\n'
            + "".join(f'  echo "    {test}"\n' for test in _FAKE_NEXTEST_TESTS)
            + "  exit 0\n"
        )
    else:
        list_body = f'  echo "no tests to run" >&2\n  exit {list_exit}\n'
    script = (
        "#!/bin/sh\n"
        'if [ "$1" = "nextest" ] && [ "$2" = "list" ]; then\n'
        f"{list_body}"
        "fi\n"
        'echo "test result: ok. 2 passed; 0 failed"\n'
        "exit 0\n"
    )
    cargo = bin_dir / "cargo"
    cargo.write_text(script, encoding="utf-8")
    cargo.chmod(cargo.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_python_only_slice(fixture: Path, feature_id: str, slice_id: str) -> str:
    """A genuinely Python-only slice: a self-contained, TAGGED ``.py``
    regression test -- zero ``.rs`` files touched. Returns the repo-relative
    regression-test-file path."""
    rel_path = "scripts/test_widget.py"
    (fixture / rel_path).write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n"
        "def widget_total(count: int) -> int:\n    return count * 2\n\n\n"
        "def test_widget_total():\n    assert widget_total(3) == 6\n",
        encoding="utf-8",
    )
    return rel_path


def _write_rust_slice(fixture: Path) -> None:
    """A genuinely Rust-only slice addition (mirrors ``_init_cargo_fixture``'s
    slice content in ``test_gate_scope_digest_cargo.py``)."""
    (fixture / "tests").mkdir(parents=True, exist_ok=True)
    (fixture / "tests" / "gate_scope_at.rs").write_text(
        "#[test]\nfn verifies_alpha() { assert_eq!(1 + 1, 2); }\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# observables
# ---------------------------------------------------------------------------


def _json_events(*streams: str) -> list[dict[str, object]]:
    """Every single-line JSON object across the captured channels, in emission
    order. ``WholeTreeRunnerResolved`` is emitted on stderr (by design, so the
    pytest-path bare-digest stdout stays byte-identical) -- both channels must
    be scanned to observe it."""
    events: list[dict[str, object]] = []
    for stream in streams:
        for line in stream.splitlines():
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return events


def _run_commit_slice(
    repo: Path, argv_tail: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, list[dict[str, object]]]:
    """Drive the REAL ``des commit-slice`` CLI (``main()``) in-process,
    capturing every single-line JSON payload it emitted on EITHER channel."""
    exit_code = commit_slice_main(["--repo", str(repo), *argv_tail])
    captured = capsys.readouterr()
    events = _json_events(captured.out, captured.err)
    return exit_code, events


def _trailer_digest(fixture: Path) -> str | None:
    message = _git(fixture, "log", "-1", "--format=%B")
    match = _GATE_SCOPE_TRAILER_RE.search(message)
    return match.group(1) if match else None


def _diag(exit_code: int, events: list[dict[str, object]]) -> str:
    return f"\nexit_code={exit_code!r}\nevents={events!r}"


def _cargo_digest_routed(events: list[dict[str, object]]) -> bool:
    """Whether ANY leg of this run routed its whole-tree digest through
    cargo -- the precise signature of Root Cause A firing at all."""
    return any(
        event.get("event") == "WholeTreeRunnerResolved"
        and event.get("runner") == "cargo-test"
        and event.get("routed") is True
        for event in events
    )


def _behavioral_argv(
    feature_id: str, slice_id: str, regression_test_file: str, *, message: str
) -> list[str]:
    return [
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--all",
        "--message",
        message,
        "--at-kind",
        "pytest-regression",
        "--regression-test-file",
        regression_test_file,
    ]


# ===========================================================================
# Scenario 1 -- RED-today core (Fix A): the pytest-regression slice must
# reach SliceCommitVerified, never blocked by cargo's empty scope.
# ===========================================================================


def test_python_only_pytest_regression_slice_on_rust_primary_repo_seals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Python-only slice, declared ``--at-kind pytest-regression`` on a
    Rust-primary repo (``Cargo.toml`` at root, zero ``#[test]``s), must clear
    ``des commit-slice`` end-to-end -- ``SliceCommitted`` with
    ``verified: true`` and a real (non-vacuous) Gate-Scope digest -- because
    the runner it picks must match the LANGUAGE of the work actually
    committed, never the repo's OTHER language's lockfile.

    Active-RED at HEAD: Step 3's committed-scope digest is routed
    UNCONDITIONALLY through ``_maybe_route_digest_through_runner`` regardless
    of ``--at-kind`` -- cargo's OWN enumerate facet reports an empty scope on
    this crate (zero ``#[test]``s) -> ``RunnerAdapterUnavailable`` -> the
    digest degrades LOUD -> ``SliceCommitIndeterminate`` -- despite the
    declared Python regression test genuinely passing on the committed tree.
    """
    fake_bin = tmp_path / "fake-bin"
    _plant_fake_cargo(fake_bin, list_exit=4)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))
    fixture = _init_polyglot_fixture(tmp_path)
    feature_id = "fix-runner-resolves-per-scope-language-python-slice"
    slice_id = "slice-01"
    regression_test_file = _write_python_only_slice(fixture, feature_id, slice_id)

    exit_code, events = _run_commit_slice(
        fixture,
        _behavioral_argv(
            feature_id,
            slice_id,
            regression_test_file,
            message="feat(slice): land the python-only slice on a cargo-root repo",
        ),
        capsys,
    )

    committed = [e for e in events if e.get("event") == "SliceCommitted"]
    assert exit_code == 0 and committed and committed[-1].get("verified") is True, (
        "a Python-only --at-kind pytest-regression slice, declaring its own "
        ".py regression test, must clear des commit-slice end-to-end -- the "
        "runner picked for the Gate-Scope digest must match the DECLARED "
        "language of the slice, never the repo's OTHER (cargo) lockfile; at "
        "HEAD the digest leg routes through cargo unconditionally, cargo's "
        "own enumerate reports an empty scope on this crate, and the slice "
        "degrades to SliceCommitIndeterminate instead of sealing."
        + _diag(exit_code, events)
    )
    digest = committed[-1].get("gate_scope_digest") if committed else None
    assert (
        isinstance(digest, str) and len(digest) == 64 and digest != _VACUOUS_DIGEST
    ), (
        f"a sealed pytest-regression slice must carry a real, non-vacuous "
        f"64-hex Gate-Scope digest -- got {digest!r}." + _diag(exit_code, events)
    )
    verified = AtCompletionLedger(feature_id, fixture).verified_slices()
    assert slice_id in verified, (
        "a genuinely sealed Python-only pytest-regression slice on a "
        "cargo-root repo must earn a SliceCommitVerified ledger record -- "
        f"observed verified_slices={sorted(verified)!r}." + _diag(exit_code, events)
    )


# ===========================================================================
# Scenario 2 -- pin: don't over-correct. A genuinely Rust (gherkin-kind)
# slice on the SAME repo shape must still route through cargo for its
# digest -- the fix must not make every slice resolve to pytest.
# ===========================================================================


def test_rust_slice_on_the_same_repo_shape_still_routes_through_cargo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A genuinely Rust slice (default ``--at-kind gherkin``, no
    ``--regression-test-file``) on the SAME Rust-primary repo shape must
    STILL resolve its Gate-Scope digest via cargo's own enumerate facet --
    the fix scoped to ``--at-kind pytest-regression`` must never widen into
    treating every cargo-root commit as pytest-native. This is the pinned
    regression guard: it must stay GREEN before AND after Fix A lands.
    """
    fake_bin = tmp_path / "fake-bin"
    _plant_fake_cargo(fake_bin, list_exit=0)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))
    fixture = _init_polyglot_fixture(tmp_path)
    _write_rust_slice(fixture)

    exit_code, events = _run_commit_slice(
        fixture,
        [
            "--feature-id",
            "fix-runner-resolves-per-scope-language-rust-slice",
            "--slice-id",
            "slice-01",
            "--all",
            "--message",
            "feat(slice): land the rust slice on the same cargo-root repo",
        ],
        capsys,
    )

    committed = [e for e in events if e.get("event") == "SliceCommitted"]
    assert exit_code == 0 and committed and committed[-1].get("verified") is True, (
        "a genuinely Rust (gherkin-kind) slice on a cargo-root repo must "
        "still clear des commit-slice -- the fix must be scoped to "
        "--at-kind pytest-regression, never widened to every cargo-root "
        "commit." + _diag(exit_code, events)
    )
    expected = _expected_gate_scope_digest(_EXPECTED_CARGO_NODE_IDS)
    trailer = _trailer_digest(fixture)
    assert trailer == expected, (
        "a Rust slice's Gate-Scope trailer must still be the CARGO-derived "
        f"digest (sha256 of the sorted node-id set {sorted(_EXPECTED_CARGO_NODE_IDS)}, "
        f"expected {expected}) -- never coerced through a pytest-native "
        f"digest just because a pytest-regression carve-out now exists; got "
        f"{trailer!r}." + _diag(exit_code, events)
    )
    assert _cargo_digest_routed(events), (
        "a Rust (gherkin-kind) slice must still show its digest ROUTED "
        "through cargo (WholeTreeRunnerResolved{runner: 'cargo-test', "
        "routed: true}) -- its absence would mean the fix over-corrected "
        "into skipping cargo routing for every slice, not just "
        "pytest-regression ones." + _diag(exit_code, events)
    )


# ===========================================================================
# Scenario 3 -- honest N/A, not blocking (negative): the python-only
# pytest-regression slice must NEVER show cargo interference anywhere in the
# run -- no routing attempt, no cargo-empty-scope Indeterminate reason.
# ===========================================================================


@pytest.mark.negative_at
def test_python_only_pytest_regression_slice_never_routes_through_cargo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Python-only ``--at-kind pytest-regression`` slice must NEVER show
    ANY leg of the run routing through cargo -- no
    ``WholeTreeRunnerResolved{runner: "cargo-test", routed: true}`` event
    anywhere, and no ``SliceCommitIndeterminate`` record carrying the
    cargo-runner-unavailable reason. The repo's OTHER language (cargo) is
    simply N/A to this slice -- it must never surface as a blocking
    condition, distinguishable from the (also honest, but different)
    positive-seal outcome scenario 1 pins.

    Active-RED at HEAD: the digest leg unconditionally resolves and routes
    through cargo (`WholeTreeRunnerResolved{runner: "cargo-test", routed:
    true}` fires) BEFORE cargo's own empty-scope enumerate degrades the run
    -- exactly the interference this test forbids.
    """
    fake_bin = tmp_path / "fake-bin"
    _plant_fake_cargo(fake_bin, list_exit=4)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))
    fixture = _init_polyglot_fixture(tmp_path)
    feature_id = "fix-runner-resolves-per-scope-language-honest-na"
    slice_id = "slice-01"
    regression_test_file = _write_python_only_slice(fixture, feature_id, slice_id)

    exit_code, events = _run_commit_slice(
        fixture,
        _behavioral_argv(
            feature_id,
            slice_id,
            regression_test_file,
            message="feat(slice): the repo's cargo side must be honest N/A here",
        ),
        capsys,
    )

    assert not _cargo_digest_routed(events), (
        "a Python-only pytest-regression slice must NEVER show its digest "
        "routed through cargo (WholeTreeRunnerResolved{runner: 'cargo-test', "
        "routed: true}) -- the repo's cargo side is simply not applicable to "
        "this slice's declared language, never a blocking route."
        + _diag(exit_code, events)
    )
    cargo_blocked = any(
        event.get("event") == "SliceCommitIndeterminate"
        and event.get("reason") == "gate_scope_runner_unavailable"
        for event in events
    )
    ledger_records = AtCompletionLedger(feature_id, fixture).read_records(
        slice_id=slice_id, event_type="SliceCommitIndeterminate"
    )
    cargo_blocked = cargo_blocked or any(
        record.get("reason") == "gate_scope_runner_unavailable"
        for record in ledger_records
    )
    assert not cargo_blocked, (
        "a Python-only pytest-regression slice must never mint a "
        "SliceCommitIndeterminate whose reason names the cargo runner as "
        "unavailable -- an empty CARGO scope is not this slice's business. "
        f"ledger_records={ledger_records!r}" + _diag(exit_code, events)
    )


# ===========================================================================
# Scenario 4 -- Fix B named reasons (negative): a genuinely MISSING declared
# --regression-test-file must surface a NAMED reason, not the reason-less
# generic fallback that collapses it with the interpreter-unavailable case.
# ===========================================================================


@pytest.mark.negative_at
def test_missing_regression_test_file_surfaces_a_named_reason_not_the_generic_fallback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When the declared ``--regression-test-file`` genuinely does NOT exist
    on the committed tree, the honest ``SliceCommitIndeterminate`` record
    must name the cause as ``regression_test_file_missing_on_committed_tree``
    -- distinguishable from an interpreter-unavailable degrade -- never the
    single reason-less generic fallback both causes collapse into today
    (ledger ``reason == "pytest_regression_file_unrunnable"``, surfaced
    ``error`` text "...(missing or uncollectible)...").

    Isolated from Root Cause A: a plain, cargo-free repo, so this pins Fix B
    independently of the runner-routing defect.

    Active-RED at HEAD: ``_run_regression_gate`` returns ``(exit, None,
    None)`` for BOTH a missing file and ``InterpreterUnavailable`` -- the
    caller then falls back to the SAME generic literal for both, so the
    surfaced record never distinguishes which cause actually fired.
    """
    repo = _init_plain_python_repo(tmp_path)
    feature_id = "fix-runner-resolves-per-scope-language-missing-file"
    slice_id = "slice-01"
    (repo / "src").mkdir()
    (repo / "src" / "thing.py").write_text(
        "def thing() -> int:\n    return 1\n", encoding="utf-8"
    )

    exit_code, events = _run_commit_slice(
        repo,
        _behavioral_argv(
            feature_id,
            slice_id,
            "src/test_never_written_regression.py",
            message="feat(slice): declare a regression file that is never written",
        ),
        capsys,
    )

    indeterminate = [e for e in events if e.get("event") == "SliceCommitIndeterminate"]
    assert indeterminate, (
        "reproduction precondition: a declared --regression-test-file that "
        f"is never written must degrade INDETERMINATE -- events={events!r}"
        + _diag(exit_code, events)
    )

    ledger_records = AtCompletionLedger(feature_id, repo).read_records(
        slice_id=slice_id, event_type="SliceCommitIndeterminate"
    )
    assert ledger_records, (
        "reproduction precondition: a SliceCommitIndeterminate ledger record "
        "must be minted for the missing-file degrade." + _diag(exit_code, events)
    )
    reason = ledger_records[-1].get("reason")
    assert reason == "regression_test_file_missing_on_committed_tree", (
        "a genuinely MISSING --regression-test-file must surface a NAMED "
        "reason distinguishing it from an interpreter-unavailable degrade -- "
        f"got reason={reason!r}. Today's generic reason-less fallback is "
        "'pytest_regression_file_unrunnable', which collapses BOTH the "
        "missing-file and interpreter-unavailable causes into one "
        f"indistinguishable literal. ledger_record={ledger_records[-1]!r}"
        + _diag(exit_code, events)
    )

    error_text = str(indeterminate[-1].get("error", ""))
    assert "missing or uncollectible" not in error_text, (
        "the surfaced error text must no longer use the reason-less generic "
        "phrase that collapses the missing-file and interpreter-unavailable "
        f"causes into one literal -- got error={error_text!r}."
        + _diag(exit_code, events)
    )
