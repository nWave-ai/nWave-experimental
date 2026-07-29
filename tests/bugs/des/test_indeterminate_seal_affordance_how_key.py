"""Regression (GDP-3): two ``SliceCommitIndeterminate`` emission sites and the
``CarpaccioSliceOutOfOrder`` refusal carry no ``how`` key -- the operator sees
WHAT degraded and WHY, never HOW to recover.

RCA: ``docs/feature/fix-indeterminate-seal-affordance/deliver/rca.md``
(peer-reviewed 8.4/10). Charter: ``docs/product/expectations/
fix-indeterminate-seal-affordance/
operator-finds-the-seal-recovery-path-without-reading-help.md``.

Two sites mint ``SliceCommitIndeterminate`` with no ``"how"`` key:

  * Site A -- ``_record_indeterminate_outcome``
    (``verify_slice_commit_completeness.py:1589-1625``), fired when the E2
    contract gate / pytest-regression runner returns
    ``_GATE_INDETERMINATE_EXIT_CODE`` (interpreter/runner unresolvable).
  * Site B -- the Step-3 committed-scope-digest degrade
    (``commit_slice.py:1681-1694``), fired when
    ``_committed_scope_digest_or_degrade_reason`` cannot pin a digest.

A third site -- the carpaccio out-of-order refusal
(``carpaccio_intercept.py:568-575``, rendered to the operator by
``pre_tool_use_handler._atdd_pure_intercept_block``) -- also carries no
``"how"`` key.

CRITICAL PRECISION this file pins (RCA Q3, correcting the alpha-challenge's
FALSE premise): the examine-verdict carve-out
(``check_examine_verdict``/``_examine_gate_armed``, ``commit_slice.py:
506-720``) applies ONLY to a genuinely-EMPTY AT scope (E2 reason
``zero-collected``/``empty-intersection``) -- it is a DIFFERENT branch of
``_run_verify_checks`` than the ``_GATE_INDETERMINATE_EXIT_CODE`` branch Site
A/B fire from, and the INDETERMINATE branch RETURNS before the carve-out is
ever consulted (``verify_slice_commit_completeness.py:1354-1379`` vs
``1405-1432``). So a correct fix's ``how`` text must NEVER claim that
re-running seals an interpreter/runner-unavailable INDETERMINATE via the
recorded examine-verdict -- that is a FALSE HOW the codebase's own
Printed-Remediation Rule (``commit_slice.py:41-88``) forbids. It MAY mention
the examine-verdict escape when clearly CONDITIONED on a genuinely-empty AT
scope (a different, honest reading of the same text).

Driving surface (Mandate-13/16 driving-port-only, Layer 3 in-process): the
REAL ``des.cli.commit_slice.main()`` CLI driver (Site A/B, mirroring
``tests/bugs/des/test_commit_slice_gates_run_before_commit.py``'s proven
fixture shape) and the REAL U1 carpaccio intercept driving port
(``intercept_atdd_pure_dispatch`` + ``pre_tool_use_handler.
_atdd_pure_intercept_block``, mirroring ``tests/des/acceptance/
fix-slicecommitverified-emission/steps/composition.py``'s proven shape).

GIT SAFETY: every repo below is a disposable ``tmp_path`` fixture, built with
explicit-target ``["git", *args], cwd=root`` invocations only -- never a bare
``git config`` and never any write against the real project repo.

THIS FILE IS TEST-ONLY. No production code is touched by this authoring pass.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks import carpaccio_intercept
from des.adapters.drivers.hooks.pre_tool_use_handler import _atdd_pure_intercept_block
from des.cli import commit_slice as commit_slice_module
from des.cli import record_examine_verdict as record_examine_verdict_module
from des.cli.commit_slice import main as commit_slice_main
from tests.charter_fixtures import filled_charter


# ---------------------------------------------------------------------------
# The honesty oracle -- test-only, pins RCA Q3's corrected finding.
# ---------------------------------------------------------------------------

_EXAMINE_MENTION_TOKENS = ("examine-verdict", "examine verdict", "examine pass")
_CONDITIONAL_QUALIFIERS = (
    "genuinely empty",
    "zero-collected",
    "empty-intersection",
    "no examine-verdict escape",
    "no direct examine-verdict escape",
    "does not have an examine-verdict escape",
    "has no examine-verdict escape",
)


def _mentions_examine_verdict(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in _EXAMINE_MENTION_TOKENS)


def _how_is_honest_about_examine_verdict(text: str) -> bool:
    """False iff ``text`` mentions the examine-verdict escape hatch WITHOUT
    conditioning it on a genuinely-empty AT scope.

    This is the headline correctness oracle: an interpreter/runner-unavailable
    INDETERMINATE (Site A/B, the ONLY class these two sites ever emit) has NO
    examine-verdict escape (RCA Q3) -- only a genuinely-empty AT scope
    (a DIFFERENT E2 branch, never reached from Site A/B) does. A ``how`` text
    that mentions the escape hatch without conditioning it on that genuinely-
    empty-scope precondition is an unconditional (false) promise.
    """
    if not _mentions_examine_verdict(text):
        return True
    lowered = text.lower()
    return any(qualifier in lowered for qualifier in _CONDITIONAL_QUALIFIERS)


# ---------------------------------------------------------------------------
# Shared fixture builders (verbatim shape reused from
# tests/bugs/des/test_commit_slice_gates_run_before_commit.py).
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo(root: Path) -> None:
    """A real pytest-collectible git work-tree."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "atdd@nwave.ai")
    _git(root, "config", "user.name", "atdd")
    tests_dir = root / "tests" / "unit"
    tests_dir.mkdir(parents=True)
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (root / "conftest.py").write_text(
        "import pytest\n\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.unit)\n",
        encoding="utf-8",
    )
    (root / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n"
        "    unit: unit tests\n"
        "    integration: integration tests\n"
        "    acceptance: acceptance tests\n",
        encoding="utf-8",
    )
    (tests_dir / "test_base.py").write_text(
        "def test_base():\n    assert True\n", encoding="utf-8"
    )
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


def _write_new_at(root: Path) -> None:
    """A NEW (untracked) pytest test file -- real content to stage/commit."""
    (root / "tests" / "unit" / "test_slice_new.py").write_text(
        "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )


_REGRESSION_FILE_REL = "tests/unit/test_regression_fixture.py"


def _write_regression_test(root: Path, feature_id: str, slice_id: str) -> Path:
    """A real, pytest-collectible, GENUINELY PASSING regression test file,
    head-tagged for E1 completeness (verbatim shape reused from the sibling
    ``test_commit_slice_gates_run_before_commit.py``)."""
    path = root / _REGRESSION_FILE_REL
    path.write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n"
        "def test_the_slice_behaviour_holds():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    return path


def _indeterminate_regression_argv(
    feature_id: str, slice_id: str, *, message: str
) -> list[str]:
    """A declared ``--regression-test-file`` that is NEVER written to disk --
    the deterministic trigger for Site A's ``_record_indeterminate_outcome``
    (verbatim shape reused from ``test_commit_slice_gates_run_before_commit.
    py``'s ``_indeterminate_regression_argv``)."""
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


def _json_events(stdout: str) -> list[dict[str, object]]:
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
    repo: Path, argv_tail: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, list[dict[str, object]]]:
    exit_code = commit_slice_main(["--repo", str(repo), *argv_tail])
    events = _json_events(capsys.readouterr().out)
    return exit_code, events


def _diag(exit_code: int, events: list[dict[str, object]]) -> str:
    return f"\nexit_code={exit_code!r}\nevents={events!r}"


# ---------------------------------------------------------------------------
# Site A -- verify_slice_commit_completeness._record_indeterminate_outcome
# ---------------------------------------------------------------------------


def test_site_a_indeterminate_outcome_carries_an_honest_how_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE AT (active-RED today): a declared ``--regression-test-file``
    that never exists on the committed tree degrades Site A's honest
    ``SliceCommitIndeterminate`` -- the emitted payload must carry a
    non-empty ``how`` key, and that ``how`` must never falsely claim
    examine-verdict sealing (RCA Q3's corrected finding).

    FAILS today: ``_record_indeterminate_outcome``
    (``verify_slice_commit_completeness.py:1617-1624``) emits
    ``event``/``slice_ids``/``commit``/``error`` only -- no ``how`` key at
    all -- a semantic AssertionError, not a collection/import error.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_new_at(repo)
    feature_id = "fix-indeterminate-seal-affordance-site-a"
    slice_id = "slice-01"

    exit_code, events = _run_commit_slice(
        repo,
        _indeterminate_regression_argv(
            feature_id,
            slice_id,
            message="feat(slice): declare a regression file that is never written",
        ),
        capsys,
    )

    indeterminate = [e for e in events if e.get("event") == "SliceCommitIndeterminate"]
    assert indeterminate, (
        "reproduction precondition: a declared --regression-test-file that "
        "is never written must degrade Site A INDETERMINATE -- "
        f"{_diag(exit_code, events)}"
    )
    how = indeterminate[0].get("how")
    assert isinstance(how, str) and how.strip(), (
        "Site A's SliceCommitIndeterminate payload must carry a non-empty "
        f"'how' key -- got how={how!r} payload={indeterminate[0]!r}"
        f"{_diag(exit_code, events)}"
    )
    assert _how_is_honest_about_examine_verdict(how), (
        "Site A's 'how' text mentions the examine-verdict escape hatch "
        "WITHOUT conditioning it on a genuinely-empty AT scope -- a FALSE "
        "HOW: an interpreter/runner-unavailable INDETERMINATE (the ONLY "
        "class Site A ever emits) has NO examine-verdict escape (RCA Q3). "
        f"how={how!r}"
    )


# ---------------------------------------------------------------------------
# Site B -- commit_slice.py Step-3 committed-scope-digest degrade
# ---------------------------------------------------------------------------


def test_site_b_step3_digest_degrade_carries_an_honest_how_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """POSITIVE AT (active-RED today): a genuinely CLEARING preflight (E1+E2+E3
    pass) whose Step-3 committed-scope digest cannot be pinned (interpreter/
    runner unavailable) must degrade Site B's honest
    ``SliceCommitIndeterminate`` -- same 'how'-key + honesty requirements as
    Site A.

    The digest computation is monkeypatched to degrade deterministically
    (mirrors the codebase's own documented "compatibility normalization" for
    stubbing this exact seam, ``verify_slice_commit_completeness.py:
    1332-1338``) -- no attempt to fabricate a real interpreter-unavailable
    environment.

    FAILS today: the Step-3 degrade emit (``commit_slice.py:1681-1694``)
    carries no ``how`` key -- a semantic AssertionError, not a collection
    error.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_id = "fix-indeterminate-seal-affordance-site-b"
    slice_id = "slice-01"
    _write_regression_test(repo, feature_id, slice_id)

    def _fake_degrade(_repo: Path, _at_kind: str | None = None) -> tuple[None, str]:
        return None, "gate_scope_interpreter_unavailable"

    monkeypatch.setattr(
        commit_slice_module,
        "_committed_scope_digest_or_degrade_reason",
        _fake_degrade,
    )

    exit_code, events = _run_commit_slice(
        repo,
        _behavioral_argv(
            feature_id,
            slice_id,
            message="fix(slice): a genuinely clearing slice whose digest cannot pin",
        ),
        capsys,
    )

    indeterminate = [e for e in events if e.get("event") == "SliceCommitIndeterminate"]
    assert indeterminate, (
        "reproduction precondition: a monkeypatched digest degrade must "
        f"fire Site B INDETERMINATE -- {_diag(exit_code, events)}"
    )
    how = indeterminate[0].get("how")
    assert isinstance(how, str) and how.strip(), (
        "Site B's SliceCommitIndeterminate payload must carry a non-empty "
        f"'how' key -- got how={how!r} payload={indeterminate[0]!r}"
        f"{_diag(exit_code, events)}"
    )
    assert _how_is_honest_about_examine_verdict(how), (
        "Site B's 'how' text mentions the examine-verdict escape hatch "
        "WITHOUT conditioning it on a genuinely-empty AT scope -- a FALSE "
        f"HOW (RCA Q3). how={how!r}"
    )


# ---------------------------------------------------------------------------
# CarpaccioSliceOutOfOrder -- carpaccio_intercept._carpaccio_order_block,
# rendered by pre_tool_use_handler._atdd_pure_intercept_block.
# ---------------------------------------------------------------------------


def _dispatch_prompt(slice_id: str) -> str:
    """A valid atdd_pure A_GREEN_ATS dispatch prompt entering ``slice_id``
    (verbatim marker shape reused from ``tests/des/acceptance/
    fix-slicecommitverified-emission/steps/composition.py``)."""
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        f"<!-- DES-SLICE : {slice_id} -->\n"
        "\natdd_pure dispatch body.\n"
    )


def test_carpaccio_out_of_order_refusal_carries_an_how_key_naming_commit_slice(
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): a successor slice dispatched with its
    predecessor entirely uncommitted (no commit on disk carries the
    predecessor's ``Slice-Id:`` trailer -- the backfill cannot recover
    anything) must be blocked ``CarpaccioSliceOutOfOrder`` carrying a
    non-empty ``how`` key naming the ``des commit-slice`` recovery path for
    the named predecessor.

    Driving surface: the REAL U1 intercept (``intercept_atdd_pure_dispatch``)
    composed with the REAL operator-facing renderer
    (``pre_tool_use_handler._atdd_pure_intercept_block``) -- the exact two
    production functions that together produce what the operator sees.

    FAILS today: ``_atdd_pure_intercept_block`` renders only
    ``decision``/``event``/``reason`` (``pre_tool_use_handler.py:72-78``) --
    no ``how`` key at all -- a semantic AssertionError, not a collection
    error.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "atdd@nwave.ai")
    _git(repo, "config", "user.name", "atdd")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: seed (no predecessor Slice-Id anywhere)")
    feature_id = "fix-indeterminate-seal-affordance-carpaccio-order"

    decision = carpaccio_intercept.intercept_atdd_pure_dispatch(
        prompt=_dispatch_prompt("slice-02"),
        feature_id=feature_id,
        project_root=repo,
        carpaccio_runner=lambda _f, _s: (
            0,
            json.dumps({"event": "SliceCleared", "slice_id": _s}),
        ),
        readiness_runner=lambda _f, _s: (0, ""),
    )

    assert decision.is_block and decision.event == "CarpaccioSliceOutOfOrder", (
        "reproduction precondition: entering slice-02 with NO predecessor "
        f"commit on disk must block CarpaccioSliceOutOfOrder -- got {decision!r}"
    )

    payload = _atdd_pure_intercept_block(decision)
    how = payload.get("how")
    assert isinstance(how, str) and how.strip(), (
        "the CarpaccioSliceOutOfOrder refusal the operator sees must carry a "
        f"non-empty 'how' key -- got payload={payload!r}"
    )
    assert "des commit-slice" in how, (
        f"the 'how' must name the des commit-slice recovery path -- got how={how!r}"
    )
    assert "slice-01" in how, (
        "the 'how' must name the out-of-order predecessor (slice-01) -- "
        f"got how={how!r}"
    )


# ---------------------------------------------------------------------------
# Control / regression pin -- RCA Q3's corrected finding, behavioral proof:
# an armed examine gate with a fresh PASS on record does NOT rescue an
# interpreter/runner-unavailable INDETERMINATE. This must be green NOW
# (unaffected by the how-key fix) and stay green after it lands.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_examine_verdict_pass_does_not_rescue_an_interpreter_unavailable_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE AT (control, must be GREEN already -- pins RCA Q3): even with
    the examine gate ARMED (a charter exists) and a fresh PASS ExamineVerdict
    recorded for the SAME entering slice, a persisting interpreter/runner-
    unavailable degrade (a declared --regression-test-file that never
    exists) still mints SliceCommitIndeterminate -- NEVER a
    SliceCommitVerified, and NEVER ``attested_via: "examine-verdict"``. The
    carve-out is scoped to a genuinely-empty AT scope (zero-collected /
    empty-intersection), a DIFFERENT E2 branch the INDETERMINATE return
    never reaches (verify_slice_commit_completeness.py:1354-1379 returns
    before 1405-1432 is ever consulted).

    This is the direct behavioral falsification of the alpha-challenge's
    premise that INDETERMINATE seals via examine-verdict on re-run.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_new_at(repo)
    feature_id = "fix-indeterminate-seal-affordance-no-rescue"
    slice_id = "slice-01"

    charter_dir = repo / "docs" / "product" / "expectations" / feature_id
    charter_dir.mkdir(parents=True)
    charter_path = charter_dir / "intent.md"
    charter_path.write_text(filled_charter("Charter body."), encoding="utf-8")

    record_exit = record_examine_verdict_module.main(
        [
            "--repo",
            str(repo),
            "--feature-id",
            feature_id,
            "--slice",
            slice_id,
            "--charter",
            f"docs/product/expectations/{feature_id}/intent.md",
            "--verdict",
            "PASS",
            "--observations",
            "walked the charter end to end, all observations held",
            "--examiner",
            "nw-user-examiner",
        ]
    )
    assert record_exit == 0, "reproduction precondition: the PASS verdict must record"

    exit_code, events = _run_commit_slice(
        repo,
        _indeterminate_regression_argv(
            feature_id,
            slice_id,
            message="feat(slice): armed examine PASS must not rescue an "
            "interpreter-unavailable degrade",
        ),
        capsys,
    )

    indeterminate = [e for e in events if e.get("event") == "SliceCommitIndeterminate"]
    assert indeterminate, (
        "reproduction precondition: the missing regression file must still "
        f"degrade INDETERMINATE even with an armed PASS on record -- "
        f"{_diag(exit_code, events)}"
    )

    ledger = AtCompletionLedger(feature_id, repo)
    assert slice_id in ledger.indeterminate_slices(), (
        "an honest SliceCommitIndeterminate ledger record must be written "
        f"-- observed indeterminate_slices={sorted(ledger.indeterminate_slices())!r}"
    )
    assert slice_id not in ledger.verified_slices(), (
        "an armed examine PASS must NEVER rescue an interpreter/runner-"
        "unavailable INDETERMINATE into a fabricated SliceCommitVerified -- "
        f"observed verified_slices={sorted(ledger.verified_slices())!r}"
        f"{_diag(exit_code, events)}"
    )
    verified_events = [e for e in events if e.get("event") == "SliceCommitVerified"]
    attested_via_values = {e.get("attested_via") for e in verified_events}
    assert "examine-verdict" not in attested_via_values, (
        "no emitted event may carry attested_via: 'examine-verdict' for this "
        f"slice -- the carve-out never fires on this branch. events={events!r}"
    )


# ---------------------------------------------------------------------------
# Oracle self-test -- documents that a PROPERLY CONDITIONED examine-verdict
# mention (the empty-AT-scope case) is permitted, never flagged dishonest.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "how_text, expected_honest",
    [
        (
            "fix the interpreter/runner resolution and re-run `des "
            "commit-slice` -- this degrade has no examine-verdict escape.",
            True,
        ),
        (
            "this degrade has no direct examine-verdict escape -- the "
            "carve-out only fires on a genuinely empty AT scope "
            "(zero-collected/empty-intersection); fix the interpreter/"
            "runner and re-run, OR record a PASS examine-verdict first if "
            "this slice's scope is genuinely empty by design, then re-run "
            "`des commit-slice`.",
            True,
        ),
        (
            "just re-run `des commit-slice` -- it will seal via the "
            "recorded examine-verdict.",
            False,
        ),
        (
            "re-run and the examine-verdict on record will let this commit seal.",
            False,
        ),
        (
            "fix the interpreter/runner resolution on this machine and "
            "re-run `des commit-slice`.",
            True,
        ),
    ],
)
def test_how_honesty_oracle_permits_conditioned_mention_rejects_bare_promise(
    how_text: str, expected_honest: bool
) -> None:
    """The empty-AT-scope case's how MAY mention the examine path -- a
    'how' text is honest whenever it either never mentions examine-verdict
    at all, or mentions it CONDITIONED on a genuinely-empty AT scope. It is
    dishonest (a false promise) only when it claims examine-verdict sealing
    UNCONDITIONALLY -- the exact false premise RCA Q3 corrected.
    """
    assert _how_is_honest_about_examine_verdict(how_text) is expected_honest, (
        f"oracle mismatch for how_text={how_text!r}: "
        f"expected honest={expected_honest!r}"
    )
