"""Regression: ``des commit-slice`` gates run BEFORE the commit lands (the
reorder), never after -- pending a ratified fix.

RCA: ``docs/feature/fix-precommit-fabricates-vacuous-scaffold/deliver/rca.md``
§4a. Feature-delta: ``docs/feature/fix-commit-slice-verify-before-commit/
feature-delta.md``. Mechanism decision: ``docs/product/architecture/
ADR-DES-001-commit-slice-shadow-commit-preflight-gate.md`` (a ``git
commit-tree`` shadow object, unreferenced, minted from the staged index with
the real HEAD as parent; E1+E2 run against the shadow BEFORE the real
``git commit`` -- never a commit-then-revert).

**The defect, as it stands today** (``commit_slice.py``): Step 2 lands the
real ``git commit``. Step 6 -- much later -- invokes ``verify_slice_commit_
completeness.main()`` (the fold-in: E1 completeness + E2 the feature-scoped
contract gate / behavioral attestation) and **discards its return value**.
Two lines later, ``main()`` unconditionally emits ``"verified": not args.
skip_verify`` -- a restatement of a CLI flag, never the fold-in's real exit
code. So a SINGLE invocation can print BOTH a real, gate-named
``SliceCommitRefused`` AND a ``SliceCommitted{"verified": true}`` -- exit 0,
the commit already landed at Step 2 (independent of the fold-in's verdict).

**This file pins the FIXED observable contract** (feature-delta ``[REF]
Observable`` + ADR-DES-001 CT1-CT4): a genuinely refusing gate -- whether the
E2 feature-scoped contract gate zero-collects, or a declared ``--at-kind
pytest-regression`` behavioral attestation genuinely fails -- must land NO
commit at all: no ``SliceCommitted`` event, non-zero exit, ``git rev-parse
HEAD`` unchanged, no ref moved (the shadow object, if minted, stays
unreferenced), no dangling half-committed state. A clearing gate must keep
committing exactly as it does today: HEAD advances by one commit, ``verified:
true`` reflects a REAL gate pass with a non-vacuous committed-scope digest,
and the AT-completion ledger records the slice as verified.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.commit_slice.main()`` CLI driver, captured via ``capsys``
-- the exact production entry every crafter commit goes through. No
monkeypatching: real git subprocesses, real staging/commit/digest/verify/
fold-in machinery underneath.

Fixture reuse (Test Reuse & Consolidation Analysis -- the feature-delta names
this exact reuse): ``_init_repo`` mirrors the EXACT proven-GREEN shape already
used in ``tests/des/integration/test_commit_slice.py``,
``test_commit_slice_refuses_disarmed_invocation.py``, and the pinned
RED-by-design AT ``test_commit_slice_verified_true_never_coexists_with_a_
refusal.py``. The "no feature-delta, no ``.feature`` file anywhere" E2
zero-collected reproduction, and the ``--at-kind pytest-regression
--regression-test-file`` behavioral-attestation reproduction (already-shipped
forwarding wiring, ``test_commit_slice_forwards_at_kind_to_verify_slice_
commit.py``), are both REUSED verbatim rather than hand-rolling a third
harness shape.

GIT SAFETY: every throwaway repo below is built with ``git -C <tmp_path>
...``-equivalent EXPLICIT-target invocations only (``subprocess.run(["git",
*args], cwd=root, ...)``) -- never a bare ``git config`` and never any git
write against the real project repo (the shared box the memory anchor warns
about).

THIS FILE IS TEST-ONLY. No production code is touched by this authoring pass.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main


_EMPTY_STRING_SHA256 = hashlib.sha256(b"").hexdigest()

_REGRESSION_FILE_REL = (
    "tests/bugs/fixture/test_commit_slice_gates_before_commit_fixture.py"
)


# ---------------------------------------------------------------------------
# Shared fixture builders (verbatim shape reused across the sibling files
# named in the module docstring -- no new harness invented).
# ---------------------------------------------------------------------------

from tests.des._helpers.commit_slice_git_template import (
    provision_commit_slice_repo,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    """Provision the git work-tree via the shared session-cached template.

    See ``tests.des._helpers.commit_slice_git_template`` -- the base repo
    (``git init`` + config + the "base: walking skeleton" commit, six real
    ``git`` subprocess spawns) is built ONCE per test process and cached;
    this call materializes an independent filesystem copy at ``root``, so
    no test's later mutations can leak into another test's repo.
    """
    provision_commit_slice_repo(root)


def _write_zero_collected_slice_new_at(root: Path) -> None:
    """A NEW (untracked) pytest test file, no feature-delta, no ``.feature``
    file anywhere -- the exact E2 zero-collected reproduction the pinned AT
    ``test_commit_slice_verified_true_never_coexists_with_a_refusal.py`` and
    two ``test_commit_slice.py`` tests already exercise: E1 clears (nothing
    declared missing), E2 (default gherkin) genuinely refuses
    ``zero-collected``.
    """
    (root / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )


def _write_regression_test(
    root: Path, feature_id: str, slice_id: str, *, passing: bool
) -> Path:
    """A real, pytest-collectible regression test file, head-tagged for the
    SAME ``feature_id``/``slice_id`` E1 discovers via ``# @feature-{id}`` /
    ``# @{slice-NN}`` head-comment tags -- doubles as both the E1 delivered-AT
    artifact and the E2 behavioral witness (verbatim shape from
    ``test_commit_slice_forwards_at_kind_to_verify_slice_commit.py``'s
    ``_write_regression_test``).
    """
    path = root / _REGRESSION_FILE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    if passing:
        body = "def test_the_slice_behaviour_holds():\n    assert 1 + 1 == 2\n"
    else:
        body = (
            "def test_the_slice_behaviour_is_broken():\n"
            "    assert 1 + 1 == 3, 'the slice behaviour does NOT hold'\n"
        )
    path.write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n{body}",
        encoding="utf-8",
    )
    return path


def _all_json_events(stdout: str) -> list[dict[str, object]]:
    """Every single-line JSON object on stdout, in emission order -- the
    contradiction this file pins is only observable by looking at every line
    the fold-in emitted, not just the final ``SliceCommitted``."""
    events: list[dict[str, object]] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            events.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return events


def _run_commit_slice(
    repo: Path,
    argv_tail: list[str],
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, list[dict[str, object]]]:
    """Drive the REAL ``des commit-slice`` CLI (``main()``) in-process,
    capturing every single-line JSON payload it emitted (in order)."""
    exit_code = commit_slice_main(["--repo", str(repo), *argv_tail])
    events = _all_json_events(capsys.readouterr().out)
    return exit_code, events


def _zero_collected_argv(feature_id: str) -> list[str]:
    return [
        "--feature-id",
        feature_id,
        "--all",
        "--message",
        "feat(slice): add the new slice behaviour\n\nSlice-Id: slice-01",
    ]


def _behavioral_argv(feature_id: str, slice_id: str, *, message: str) -> list[str]:
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
        _REGRESSION_FILE_REL,
    ]


# ===========================================================================
# 1. THE test -- a refusal binds: no commit lands at all, HEAD unchanged.
# ===========================================================================


@pytest.mark.negative_at
def test_a_genuinely_refusing_gate_lands_no_commit_head_unchanged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``--feature-id`` whose E2 leg genuinely refuses ``zero-collected``
    must land NO commit at all -- ``git rev-parse HEAD`` identical before and
    after the run, non-zero exit. A refusal that still commits (today's bug:
    the commit lands at Step 2, independent of the Step-6 fold-in's verdict)
    is the exact defect this feature pins closed (ADR-DES-001 CT1).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_zero_collected_slice_new_at(repo)
    head_before = _git(repo, "rev-parse", "HEAD").strip()

    exit_code, events = _run_commit_slice(
        repo,
        _zero_collected_argv("commit-slice-gates-before-commit-refusal-binds"),
        capsys,
    )

    head_after = _git(repo, "rev-parse", "HEAD").strip()
    refusal_events = [
        event
        for event in events
        if event.get("event") in ("SliceCommitRefused", "SliceCommitIndeterminate")
    ]

    assert refusal_events, (
        "reproduction precondition: the E2 leg must genuinely refuse "
        f"zero-collected for this fixture -- events={events!r}"
    )
    assert head_after == head_before, (
        "a genuinely refusing gate must land NO commit at all -- HEAD must "
        "stay exactly where it was pre-flight. A refusal that still commits "
        f"is the exact bug being closed. head_before={head_before!r} "
        f"head_after={head_after!r} exit_code={exit_code!r} events={events!r}"
    )
    assert exit_code != 0, (
        "a genuinely refusing gate must exit non-zero -- got "
        f"exit_code={exit_code!r} events={events!r}"
    )


# ===========================================================================
# 2. The durable invariant -- a refusal and verified:true can never coexist,
#    across BOTH refusal shapes (E2 zero-collected, E2 behavioral failure).
#    Absorbs the pinned RED-by-design AT
#    test_commit_slice_verified_true_never_coexists_with_a_refusal.py, per
#    slice-01's ratified, STRENGTHENED precondition.
# ===========================================================================


@pytest.mark.negative_at
@pytest.mark.parametrize("case", ["e2-zero-collected", "e2-behavioral-failure"])
def test_a_refusal_event_and_verified_true_never_coexist_in_one_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    """Across BOTH refusal shapes, a ``SliceCommitRefused``/
    ``SliceCommitIndeterminate`` event and a ``SliceCommitted{"verified":
    true}`` event must never coexist in one run -- they are contradictory
    reports of the SAME fold-in call. And a genuinely refusing run must write
    NO ``SliceCommitVerified`` ledger record for the refused slice.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = f"commit-slice-gates-before-commit-contradiction-{case}"
    slice_id = "slice-01"

    if case == "e2-zero-collected":
        _write_zero_collected_slice_new_at(repo)
        argv = _zero_collected_argv(feature_id)
    else:
        _write_regression_test(repo, feature_id, slice_id, passing=False)
        argv = _behavioral_argv(
            feature_id,
            slice_id,
            message="fix(slice): pytest-regression slice under test",
        )

    exit_code, events = _run_commit_slice(repo, argv, capsys)

    refusal_events = [
        event
        for event in events
        if event.get("event") in ("SliceCommitRefused", "SliceCommitIndeterminate")
    ]
    committed_events = [
        event for event in events if event.get("event") == "SliceCommitted"
    ]

    assert refusal_events, (
        f"reproduction precondition: a refusal event must fire for case "
        f"{case!r} -- exit_code={exit_code!r} events={events!r}"
    )

    if committed_events:
        committed = committed_events[-1]
        assert committed.get("verified") is not True, (
            "a SliceCommitRefused/SliceCommitIndeterminate event and a "
            "SliceCommitted{verified: true} event must NEVER coexist in one "
            f"run (case={case!r}) -- they are contradictory reports of the "
            f"SAME fold-in call. refusal_events={refusal_events!r} "
            f"committed={committed!r} all_events={events!r}"
        )

    verified = AtCompletionLedger(feature_id, repo).verified_slices()
    assert slice_id not in verified, (
        f"a genuinely refusing run (case={case!r}) must write NO "
        "SliceCommitVerified ledger record for the refused slice -- observed "
        f"verified_slices={sorted(verified)!r}"
    )


# ===========================================================================
# 3. verified is EARNED, not restated -- a genuine gate pass carries a
#    non-vacuous committed-scope digest, never the sha256 of the empty
#    string.
# ===========================================================================


def test_verified_true_reflects_a_genuine_gate_pass_with_a_non_vacuous_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """When the gates genuinely PASS, ``verified: true`` reflects the real
    gate verdict -- and the committed-scope digest is a real, non-vacuous
    64-hex fingerprint, never ``hashlib.sha256(b"").hexdigest()``.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "commit-slice-gates-before-commit-earned-verified"
    slice_id = "slice-01"
    _write_regression_test(repo, feature_id, slice_id, passing=True)

    exit_code, events = _run_commit_slice(
        repo,
        _behavioral_argv(
            feature_id,
            slice_id,
            message="fix(slice): pytest-regression fix verified behaviorally",
        ),
        capsys,
    )

    committed_events = [
        event for event in events if event.get("event") == "SliceCommitted"
    ]
    assert exit_code == 0 and committed_events, (
        "reproduction precondition: a genuinely PASSING gate must clear and "
        f"commit -- exit_code={exit_code!r} events={events!r}"
    )
    committed = committed_events[-1]

    assert committed.get("verified") is True, (
        f"a genuinely passing gate must earn verified: true. committed={committed!r}"
    )
    digest = committed.get("gate_scope_digest")
    assert isinstance(digest, str) and len(digest) == 64, (
        f"verified: true must carry a real 64-hex committed-scope digest -- "
        f"digest={digest!r} committed={committed!r}"
    )
    assert digest != _EMPTY_STRING_SHA256, (
        "verified: true must never carry the sha256 of the empty string -- "
        f"digest={digest!r} committed={committed!r}"
    )

    verified = AtCompletionLedger(feature_id, repo).verified_slices()
    assert slice_id in verified, (
        "a genuinely passing gate must earn a SliceCommitVerified ledger "
        f"record -- observed verified_slices={sorted(verified)!r}"
    )


# ===========================================================================
# 4. The positive control -- load-bearing: a clean slice STILL commits
#    normally. Prove YES before NO (a gate that refuses everything is worse
#    than the bug it replaces).
# ===========================================================================


def test_a_clean_slice_still_commits_normally_head_advances_by_exactly_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A clean slice (a genuinely passing gate, complete) commits normally:
    HEAD advances by exactly one commit, and the AT-completion ledger records
    the slice as verified. This must hold BEFORE and AFTER the reorder --
    the reorder must never turn a legitimate GREEN slice into a refusal.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "commit-slice-gates-before-commit-positive-control"
    slice_id = "slice-01"
    _write_regression_test(repo, feature_id, slice_id, passing=True)
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    count_before = int(_git(repo, "rev-list", "--count", "HEAD").strip())

    exit_code, events = _run_commit_slice(
        repo,
        _behavioral_argv(
            feature_id,
            slice_id,
            message="fix(slice): pytest-regression fix verified behaviorally",
        ),
        capsys,
    )

    head_after = _git(repo, "rev-parse", "HEAD").strip()
    count_after = int(_git(repo, "rev-list", "--count", "HEAD").strip())
    committed_events = [
        event for event in events if event.get("event") == "SliceCommitted"
    ]

    assert exit_code == 0 and committed_events, (
        f"a clean slice must commit -- exit_code={exit_code!r} events={events!r}"
    )
    assert head_after != head_before, (
        "a clean, gate-passing slice must actually advance HEAD -- "
        f"head_before={head_before!r} head_after={head_after!r}"
    )
    assert count_after == count_before + 1, (
        "a clean, gate-passing slice must land EXACTLY one new commit -- "
        f"count_before={count_before} count_after={count_after}"
    )

    verified = AtCompletionLedger(feature_id, repo).verified_slices()
    assert slice_id in verified, (
        "a clean, gate-passing slice must record SliceCommitVerified -- "
        f"observed verified_slices={sorted(verified)!r}"
    )


# ===========================================================================
# 5. No dangling state on refusal -- shared-box safety: a refused run must
#    touch NO ref (the shadow object, if minted, stays unreferenced) and
#    leave a clean working tree/index.
# ===========================================================================


@pytest.mark.negative_at
def test_a_refusal_leaves_no_dangling_ref_or_worktree_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A refused pre-flight gate must move NO ref at all -- ``git
    for-each-ref`` identical before and after -- and leave the index/working
    tree exactly as the OPERATOR left it pre-invocation. A ``git
    commit-tree`` shadow object writes only content-addressed objects, never
    a ref; a refusal that still moves the branch ref (today's bug: the
    commit lands at Step 2, unconditionally) is the exact ref-contention
    risk ADR-DES-001 rejects option (ii) over.

    NOTE on the invariant this asserts: the fixture's own new AT file
    (``tests/unit/test_slice_new.py``, written by
    ``_write_zero_collected_slice_new_at`` BEFORE the run) is the operator's
    own untracked work -- it is what commit-slice's own ``git add -A``
    staged and what the refusal's ``git reset`` correctly un-stages back to
    untracked (``commit_slice.py``'s own comment: "Any file the OPERATOR
    wrote before this invocation ... is content, never deleted by a
    refusal; only the STAGING commit-slice itself performed is undone.").
    So the invariant is ``status_after == status_before`` (the run is a
    no-op on the operator's pre-existing content), never ``status_after ==
    ""`` -- the latter would require DESTROYING the operator's own
    untracked file to pass, which an AT must never demand.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_zero_collected_slice_new_at(repo)
    refs_before = _git(repo, "for-each-ref").strip()
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    status_before = _git(repo, "status", "--porcelain").strip()

    exit_code, events = _run_commit_slice(
        repo,
        _zero_collected_argv("commit-slice-gates-before-commit-no-dangling"),
        capsys,
    )

    refs_after = _git(repo, "for-each-ref").strip()
    head_after = _git(repo, "rev-parse", "HEAD").strip()
    status_after = _git(repo, "status", "--porcelain").strip()
    refusal_events = [
        event
        for event in events
        if event.get("event") in ("SliceCommitRefused", "SliceCommitIndeterminate")
    ]

    assert refusal_events, (
        f"reproduction precondition: a refusal event must fire -- "
        f"exit_code={exit_code!r} events={events!r}"
    )
    assert refs_after == refs_before, (
        "a refused pre-flight gate must touch NO ref -- no branch ref may "
        "move, and any shadow commit-tree object stays unreferenced. "
        f"refs_before={refs_before!r} refs_after={refs_after!r}"
    )
    assert head_after == head_before, (
        "HEAD must not move on a genuine refusal -- "
        f"head_before={head_before!r} head_after={head_after!r}"
    )
    assert status_after == status_before, (
        "a refused pre-flight gate must leave the index/working tree "
        "EXACTLY as the operator left it pre-invocation -- commit-slice's "
        "own staging (`git add -A`) is undone by the refusal's `git "
        "reset`, but the operator's own untracked content is never "
        "touched, let alone destroyed. "
        f"status_before={status_before!r} status_after={status_after!r}"
    )


# ===========================================================================
# 6. ADR-DES-001 addendum Rule 3 (CT8) -- INDETERMINATE proceeds-honest at
#    the pre-flight, never a hard block; every OTHER non-zero code (a
#    genuine, runnable-but-failing E2 behavioral attestation) still refuses.
#    One parametrized test pins BOTH halves of the arch invariant CT8
#    declares: "commit_slice.main's pre-flight branches on exactly {0,
#    _GATE_INDETERMINATE_EXIT_CODE, other-non-zero} -- no fourth silently-
#    added case".
# ===========================================================================


def _indeterminate_regression_argv(
    feature_id: str, slice_id: str, *, message: str
) -> list[str]:
    """A declared ``--regression-test-file`` that is NEVER written to disk --
    the simplest, deterministic trigger for ``_run_regression_gate``'s
    ``_GATE_INDETERMINATE_EXIT_CODE`` (``verify_slice_commit_completeness.py``
    ``_run_regression_gate``'s ``if not test_path.is_file(): return
    _GATE_INDETERMINATE_EXIT_CODE``): a missing regression file is never
    trusted by presence alone, so E2 degrades LOUD INDETERMINATE rather than
    either a fabricated pass or a hard refusal. E1 clears vacuously for this
    fresh, never-before-seen feature_id (no `.feature`/tagged AT candidate
    exists anywhere on the tree, so nothing is "missing").
    """
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
        "tests/unit/test_never_written_regression_file.py",
    ]


@pytest.mark.parametrize("case", ["indeterminate-proceeds", "genuine-failure-refuses"])
def test_preflight_proceeds_on_indeterminate_but_refuses_on_genuine_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    """ADR-DES-001 addendum Rule 3 (CT8): a pre-flight outcome of
    ``_GATE_INDETERMINATE_EXIT_CODE`` (3) -- the gate's OWN documented
    "record honestly and PROCEED" contract -- must land the real commit, not
    reset the index and refuse. Today's blanket ``if preflight_exit_code !=
    0: refuse`` (``commit_slice.py:1526``) silently converts that contract
    into a hard block -- the exact defect this pins closed.

    The negative half is the SAME arch invariant read the other way: Rule 3
    narrows the proceed exemption to EXACTLY exit code 3 -- it must never
    widen into treating a genuine, runnable-but-failing E2 behavioral
    attestation (exit 1) as anything but a hard refusal. A real regression
    failure still lands NO commit at all, HEAD unchanged -- this parametrize
    case is the negative oracle for CT8's positive case above.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = f"commit-slice-gates-before-commit-preflight-branch-{case}"
    slice_id = "slice-01"

    if case == "indeterminate-proceeds":
        _write_zero_collected_slice_new_at(repo)  # real content to commit
        argv = _indeterminate_regression_argv(
            feature_id,
            slice_id,
            message="feat(slice): indeterminate preflight must still proceed",
        )
    else:
        _write_regression_test(repo, feature_id, slice_id, passing=False)
        argv = _behavioral_argv(
            feature_id,
            slice_id,
            message="fix(slice): genuine behavioral failure must still refuse",
        )

    head_before = _git(repo, "rev-parse", "HEAD").strip()
    exit_code, events = _run_commit_slice(repo, argv, capsys)
    head_after = _git(repo, "rev-parse", "HEAD").strip()

    indeterminate_events = [
        event for event in events if event.get("event") == "SliceCommitIndeterminate"
    ]
    refused_events = [
        event for event in events if event.get("event") == "SliceCommitRefused"
    ]
    ledger = AtCompletionLedger(feature_id, repo)

    if case == "indeterminate-proceeds":
        assert indeterminate_events, (
            "reproduction precondition: the declared --regression-test-file "
            f"must genuinely degrade INDETERMINATE -- events={events!r}"
        )
        assert not refused_events, (
            "an INDETERMINATE pre-flight outcome must NEVER be treated as a "
            f"hard refusal -- events={events!r}"
        )
        assert head_after != head_before, (
            "the gate's OWN documented 'record honestly and PROCEED' "
            "contract means the real commit must land even when the "
            "pre-flight degrades INDETERMINATE -- a hard block here is the "
            "exact defect ADR-DES-001 addendum Rule 3 closes. "
            f"head_before={head_before!r} head_after={head_after!r} "
            f"exit_code={exit_code!r} events={events!r}"
        )
        assert slice_id in ledger.indeterminate_slices(), (
            "an honest SliceCommitIndeterminate ledger record must be "
            f"written -- observed indeterminate_slices="
            f"{sorted(ledger.indeterminate_slices())!r}"
        )
        assert slice_id not in ledger.verified_slices(), (
            "an INDETERMINATE outcome must NEVER be recorded as a "
            "fabricated SliceCommitVerified -- observed verified_slices="
            f"{sorted(ledger.verified_slices())!r}"
        )
    else:
        assert refused_events, (
            "reproduction precondition: a genuinely failing regression file "
            f"must refuse -- exit_code={exit_code!r} events={events!r}"
        )
        assert not indeterminate_events, (
            "a genuine, runnable-but-failing E2 behavioral attestation must "
            "never be misclassified as INDETERMINATE -- Rule 3 narrows the "
            f"proceed exemption to exit code 3 ONLY. events={events!r}"
        )
        assert head_after == head_before, (
            "a genuine E2 behavioral failure must still land NO commit at "
            f"all -- head_before={head_before!r} head_after={head_after!r} "
            f"exit_code={exit_code!r} events={events!r}"
        )
        assert exit_code != 0, (
            f"a genuine E2 behavioral failure must exit non-zero -- got "
            f"exit_code={exit_code!r} events={events!r}"
        )
        assert slice_id not in ledger.verified_slices(), (
            "a genuinely refusing run must write NO SliceCommitVerified "
            f"ledger record -- observed verified_slices="
            f"{sorted(ledger.verified_slices())!r}"
        )


# ===========================================================================
# 7. ADR-DES-001 addendum Rule 2 (attribution) -- the negative half: a slice
#    cleared by a REAL behavioral attestation (a passing
#    --regression-test-file, not the E2-vacuous examine carve-out) must NEVER
#    carry attested_via: "examine-verdict" -- that value is reserved
#    exclusively for the examine-verdict carve-out (Rule 1), never a blanket
#    restatement applied to every clear. The positive half (an
#    examine-cleared slice DOES carry it) is pinned in
#    test_commit_slice_examine_gate.py, alongside the carve-out's own CT7
#    pin -- same ledger substrate, same attested_via field, no duplicate
#    fixture harness.
# ===========================================================================


def test_verified_record_attested_via_is_never_examine_verdict_on_a_normal_regression_cleared_slice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A slice cleared by a genuinely passing ``--regression-test-file``
    behavioral attestation must never carry ``attested_via:
    "examine-verdict"`` on its ``SliceCommitVerified`` ledger record --
    that provenance value is reserved for the E2-vacuous examine carve-out
    (Rule 1) alone. A future implementation that over-applies the carve-out
    label to every clear (instead of only the examine-cleared one) would
    silently mislabel the evidence source -- exactly the "blanket
    restatement" Rule 2 forbids.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "commit-slice-gates-before-commit-attribution-negative"
    slice_id = "slice-01"
    _write_regression_test(repo, feature_id, slice_id, passing=True)

    exit_code, events = _run_commit_slice(
        repo,
        _behavioral_argv(
            feature_id,
            slice_id,
            message="fix(slice): a normally-cleared slice must not be "
            "mislabeled examine-verdict",
        ),
        capsys,
    )

    assert exit_code == 0, (
        "reproduction precondition: a genuinely passing regression file "
        f"must clear and commit -- exit_code={exit_code!r} events={events!r}"
    )

    verified_records = AtCompletionLedger(feature_id, repo).read_records(
        slice_id=slice_id, event_type="SliceCommitVerified"
    )
    assert verified_records, (
        "reproduction precondition: a SliceCommitVerified ledger record "
        "must exist for the normally-cleared slice"
    )
    attested_via = verified_records[-1].get("attested_via")
    assert attested_via != "examine-verdict", (
        "attested_via: 'examine-verdict' is reserved for the examine-"
        "verdict carve-out (Rule 1) -- a slice cleared by a real "
        "behavioral attestation must never carry it. observed record="
        f"{verified_records[-1]!r}"
    )
