"""Regression -- ``des commit-slice`` must REFUSE a slice commit whose
``--feature-id`` is omitted, naming the gates it would otherwise have
skipped -- never silently land a "quiet unattested commit".

RCA: ``docs/feature/fix-precommit-fabricates-vacuous-scaffold/deliver/rca.md``
§4a. Feature-delta: ``docs/feature/fix-precommit-fabricates-vacuous-scaffold/
feature-delta.md``.

This file pins Vector 2 ONLY (slice-02 of the Slice Plan). Slice-01 (the
``des run-slice-ats`` pytest-blindness fix) is a SEPARATE slice, pinned by
``tests/bugs/des/test_run_slice_ats_sees_pytest_ats.py`` -- deliberately kept
apart: this half re-arms E1/E2/E3 on paths where they have been silently
skipped, so its blast radius (a surge of previously-hidden, genuine
failures) must be attributable to THIS slice alone.

The defect: ``--feature-id`` is OPTIONAL on ``des commit-slice``
(``commit_slice.py`` ``_build_parser``, ``default=None``), and **all four**
downstream gates are guarded behind ``if args.feature_id is not None``
(``commit_slice.py:1172, 1209, 1273, 1300``): (a) the E3 examine-verdict
gate, (b) the honest ``SliceCommitIndeterminate`` mint, (c) the Step-6
fold-in (E1 completeness + E2 feature-scoped contract gate +
``SliceCommitVerified`` record), (d) the feature-end-pending notice. The
canonical crafter skill's ONE documented invocation
(``nWave/skills/nw-crafter-discipline-atdd-pure/SKILL.md:130-140``) omits
``--feature-id`` -- so every commit made through the DOCUMENTED path
silently disarms all four.

Contract (C4, feature-delta ``[REF] Architecture & Contract Tests``): a
``commit-slice`` invocation without the feature identity REFUSES and NAMES
the four gates it would have skipped; it never downgrades to a quiet
unattested commit. Arch invariant: no gate in ``commit-slice`` may be
conditional on an OPTIONAL argument -- an optional flag must never be able
to disarm a gate.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.commit_slice.main()`` CLI driver, captured via
``capsys`` -- the exact production entry every crafter commit goes through.
No monkeypatching: real git subprocesses, real staging/commit/digest/verify
machinery underneath.

Fixtures: reuse the EXACT proven-GREEN shapes already in this directory
(Test Reuse & Consolidation Analysis) rather than inventing a fourth
harness:
  * ``_init_repo`` -- the pytest-collectible git work-tree from
    ``tests/des/integration/test_commit_slice.py`` / mirrored verbatim in
    ``tests/bugs/des/test_commit_slice_writes_verified_record.py``.
  * The AT-EXEMPT ``@prefactoring`` lane (same file, same precedent) --
    the cheapest reliable way to make a ``--feature-id``-armed invocation's
    E1+E2+E3 genuinely clear, so the anti-overcorrection control below
    proves the NEW guard leaves the armed path untouched without needing a
    real feature-scoped pytest suite.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.commit_slice import main as commit_slice_main


_ARMED_FEATURE_ID = "fix-precommit-vacuous-scaffold-armed-control"
_PREDECESSOR = "slice-01"
_ENTERING = "slice-02"


# ---------------------------------------------------------------------------
# Shared fixture builders (mirrors test_commit_slice_writes_verified_record.py
# / tests/des/integration/test_commit_slice.py -- Test Reuse row).
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


def _last_json_event(stdout: str) -> dict[str, object]:
    json_lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    assert json_lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    return json.loads(json_lines[-1])


def _write_feature_delta_with_prefactoring_entering_slice(
    repo: Path, feature_id: str
) -> None:
    """A minimal feature-delta carrying the ``[REF] Slice Plan`` table --
    mirrors ``test_commit_slice_writes_verified_record.py``'s builder
    verbatim: ``_PREDECESSOR`` is an ordinary AT-bearing row, ``_ENTERING``
    is annotated ``@prefactoring`` (EXEMPT) -- the cheapest reliable way to
    make an armed invocation's E1+E2+E3 genuinely clear.
    """
    delta_dir = repo / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {_PREDECESSOR} | the predecessor slice ships a real scenario | "
        "pending | | a real AT-bearing slice |\n"
        f"| {_ENTERING} | a behavior-preserving refactor introduces the seam | "
        "pending | @prefactoring | a green-to-green prefactoring |\n",
        encoding="utf-8",
    )


def _commit_predecessor_with_at(repo: Path, feature_id: str) -> None:
    """Commit ``_PREDECESSOR`` with a real ``@slice-01``-tagged ``.feature``
    file (raw git -- not under test here)."""
    feat_dir = repo / "tests" / "acceptance" / feature_id.replace("-", "_")
    feat_dir.mkdir(parents=True, exist_ok=True)
    (feat_dir / f"{_PREDECESSOR}.feature").write_text(
        f"@feature-{feature_id}\n"
        "Feature: the predecessor slice's behaviour\n\n"
        f"  @{_PREDECESSOR}\n"
        "  Scenario: the predecessor delivers its observable outcome\n"
        "    Given a precondition\n"
        "    When the action happens\n"
        "    Then the outcome holds\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"feat(slice): predecessor behaviour\n\nSlice-Id: {_PREDECESSOR}",
    )


def _mark_predecessor_verified(repo: Path, feature_id: str) -> None:
    AtCompletionLedger(feature_id, repo).append_gate_event(
        event="SliceCommitVerified", slice_id=_PREDECESSOR
    )


def _author_entering_slice_production_change(repo: Path) -> None:
    """The ``_ENTERING`` slice's behavior-preserving production-only change
    -- no new ``.feature`` file, mirroring the real 0-AT prefactoring shape.
    """
    prod_file = repo / "src" / "app" / "module.py"
    prod_file.parent.mkdir(parents=True, exist_ok=True)
    prod_file.write_text(
        "def helper() -> str:\n    return 'refactored, same behaviour'\n",
        encoding="utf-8",
    )


# ===========================================================================
# THE NEGATIVE AT ON THE CLASS -- item C4: a disarmed invocation must NEVER
# quietly commit. Active-RED today: the four gates below are guarded behind
# `if args.feature_id is not None`, so omitting the flag lands the commit
# anyway and emits `SliceCommitted`, exit 0.
# ===========================================================================


@pytest.mark.negative_at
def test_missing_feature_id_never_commits_it_refuses_naming_the_disarmed_gates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``des commit-slice`` invoked WITHOUT ``--feature-id`` -- the
    documented canonical crafter invocation -- must REFUSE (non-zero exit),
    land NO commit at all, and NAME (in its refusal payload) at least
    several of the four gates it would otherwise have silently skipped:
    the E3 examine-verdict gate, the E1 completeness / SliceCommitIndeterminate
    honesty mint, the E2 feature-scoped contract gate / SliceCommitVerified
    record, and the feature-end-pending notice.

    RED for the right reason today: NONE of the four gates gate the commit
    itself -- they are each individually skipped
    (``if args.feature_id is not None``), so the commit lands normally and
    ``main()`` returns 0 with ``event: SliceCommitted`` -- a real semantic
    mismatch against the expected refusal, not a crash or collection error.

    SPEED (2026-07-20): the ``args.feature_id is None`` guard fires at the
    very top of ``main()``, and its refusal builder
    (``_missing_feature_id_refusal`` -> ``active_feature_id`` /
    ``_ledger_stems``) only ever does pure filesystem reads
    (``Path.is_dir()`` / ``Path.glob()``, both False/empty for a nonexistent
    ``repo``) -- no ``git`` call happens anywhere on this path. No real git
    repo is provisioned; ``repo`` is never created on disk, so
    ``not repo.exists()`` is a strictly STRONGER "no mutation" proof than a
    real-git HEAD-unchanged check.
    """
    repo = tmp_path / "repo"

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--slice-id",
            "slice-01",
            "--message",
            "feat(slice): a commit that forgot --feature-id",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code != 0, (
        "an invocation missing --feature-id -- the documented canonical "
        "crafter path -- must REFUSE, never land a commit while silently "
        f"disarming four gates. got exit_code={exit_code!r} event={event!r}"
    )
    assert event.get("event") != "SliceCommitted", (
        "a missing-feature-id invocation must never reach a SliceCommitted "
        f"outcome -- that IS the quiet unattested commit this fix exists to "
        f"close. event={event!r}"
    )

    assert not repo.exists(), (
        "the refusal must happen BEFORE any git mutation -- no placeholder "
        f"commit may land, and no repo directory should ever be created. "
        f"repo={repo!r}"
    )

    haystack = json.dumps(event).lower()
    gate_categories_named = sum(
        1
        for markers in (
            ("examine",),
            ("completeness", "indeterminate"),
            ("contract gate", "slicecommitverified", "e2"),
            ("feature-end", "feature_end"),
        )
        if any(marker in haystack for marker in markers)
    )
    assert gate_categories_named >= 3, (
        "the refusal must NAME the gates it would have skipped (examine-"
        "verdict, E1 completeness/indeterminate-mint, E2 contract-gate/"
        "SliceCommitVerified, feature-end-pending notice) -- not a bare, "
        f"unexplained refusal. event={event!r}"
    )


# ===========================================================================
# THE ANTI-OVERCORRECTION CONTROL -- an armed invocation (--feature-id
# given) must be UNAFFECTED by the new guard. Green both BEFORE and AFTER
# the fix (only the absent-flag path changes).
# ===========================================================================


@pytest.mark.negative_at
def test_feature_id_given_invocation_is_never_refused_by_the_new_guard(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``--feature-id``-armed invocation must commit exactly as it does
    today -- the new missing-flag refusal must never reach the armed path.
    Reuses the proven AT-EXEMPT ``@prefactoring`` lane (the cheapest way to
    make E1+E2+E3 genuinely clear) so this control is fully self-contained.

    Green both BEFORE the fix (the armed path already works) and AFTER (the
    fix only adds a refusal for the ABSENT-flag case).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_feature_delta_with_prefactoring_entering_slice(repo, _ARMED_FEATURE_ID)
    _commit_predecessor_with_at(repo, _ARMED_FEATURE_ID)
    _mark_predecessor_verified(repo, _ARMED_FEATURE_ID)
    _author_entering_slice_production_change(repo)

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            _ARMED_FEATURE_ID,
            "--slice-id",
            _ENTERING,
            "--message",
            "refactor(slice): behavior-preserving seam introduces the exemption",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code == 0, (
        "a --feature-id-armed invocation must commit and verify exactly as "
        f"it does today -- the new guard must never refuse it. got "
        f"exit_code={exit_code!r} event={event!r}"
    )
    assert event.get("event") == "SliceCommitted", event
    assert event.get("verified") is True, event


# ===========================================================================
# THE EMPTY-STRING CLASS -- item AT-1: "present but meaningless" IS "absent",
# for EVERY identity-bearing flag (--feature-id, --slice-id, --repo). Found
# by the same independent examiner (2026-07-14): ``--feature-id ""`` walked
# straight past the (then) ``is not None`` guard, scoped every gate to a
# feature literally named ``""``, and landed
# ``SliceCommitted{verified: true}`` with a ``Gate-Scope`` digest that was
# the sha256 of the EMPTY STRING -- exit 0, commit landed.
#
# The fix (``commit_slice.py:_meaningful_or_absent``) collapses any blank or
# whitespace-only value to ``None`` at the parse boundary, for all three
# identity-bearing flags. These tests pin the CLASS ("a value that cannot
# name a real thing is the same as no value"), not the three known
# spellings -- ``_MEANINGLESS_SPELLINGS`` is parametrized so the next
# spelling of nothing (a tab, a newline, an all-whitespace value) is caught
# by the SAME assertion rather than needing a bespoke test written after the
# fact.
# ===========================================================================


_MEANINGLESS_SPELLINGS = (
    "",
    "   ",
    "\t",
    "\n",
    " \t\n ",
)


@pytest.mark.negative_at
@pytest.mark.parametrize("meaningless_feature_id", _MEANINGLESS_SPELLINGS, ids=repr)
def test_feature_id_class_of_meaningless_spellings_is_treated_as_absent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    meaningless_feature_id: str,
) -> None:
    """``--feature-id`` spelled as any blank/whitespace-only value must be
    treated EXACTLY as an omitted ``--feature-id``: REFUSE
    (``CommitRefusedMissingFeatureId``, non-zero exit), and land NO commit
    at all. A refusal that still commits is not a refusal.

    GREEN today: ``_meaningful_or_absent`` (the ``argparse type=``
    normalizer) collapses every spelling in ``_MEANINGLESS_SPELLINGS`` to
    ``None`` at the parse boundary, so the ``args.feature_id is None`` guard
    (sound only because of that normalization) fires for all of them, not
    only for a truly-omitted flag.

    SPEED (2026-07-20): same pure-classification shape as
    ``test_missing_feature_id_never_commits_it_refuses_naming_the_disarmed_gates``
    above -- no real git repo is provisioned, see that test's docstring.
    """
    repo = tmp_path / "repo"

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            meaningless_feature_id,
            "--slice-id",
            "slice-01",
            "--message",
            "feat(slice): a commit whose --feature-id spells nothing",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code != 0, (
        f"--feature-id={meaningless_feature_id!r} (a value that cannot name "
        "a real feature) must REFUSE exactly as an omitted --feature-id "
        f"does. got exit_code={exit_code!r} event={event!r}"
    )
    assert event.get("event") != "SliceCommitted", (
        "a present-but-meaningless --feature-id must never reach a "
        f"SliceCommitted outcome. event={event!r}"
    )

    assert not repo.exists(), (
        "the refusal must happen BEFORE any git mutation -- no placeholder "
        f"commit may land, and no repo directory should ever be created. "
        f"repo={repo!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("meaningless_slice_id", _MEANINGLESS_SPELLINGS, ids=repr)
def test_slice_id_class_of_meaningless_spellings_never_stamps_an_empty_trailer(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    meaningless_slice_id: str,
) -> None:
    """``--slice-id`` spelled as any blank/whitespace-only value, with a
    ``--message`` that carries NO ``Slice-Id:`` trailer of its own, must be
    treated as an OMITTED ``--slice-id`` -- refused up-front
    (``MalformedInput: missing Slice-Id``) BEFORE any staging/commit -- and
    must never stamp a blank/whitespace ``Slice-Id:`` trailer onto a
    landed commit.

    SPEED (2026-07-20): ``extract_slice_ids`` is a pure regex scan of the
    message string, and the ``args.slice_id is None`` refusal it feeds fires
    before any staging/commit call -- no ``git`` call happens on this path.
    No real git repo is provisioned; ``repo`` is never created on disk, so
    ``not repo.exists()`` proves both "no commit landed" and "no blank
    Slice-Id: trailer was ever stamped" (there is no commit at all).
    """
    repo = tmp_path / "repo"

    exit_code = commit_slice_main(
        [
            "--repo",
            str(repo),
            "--all",
            "--feature-id",
            "meaningless-slice-id-control",
            "--slice-id",
            meaningless_slice_id,
            "--message",
            "feat(slice): a commit whose --slice-id spells nothing",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code != 0, (
        f"--slice-id={meaningless_slice_id!r} (a value that cannot name a "
        "real slice) with no Slice-Id: trailer already in --message must "
        f"REFUSE exactly as an omitted --slice-id does. got "
        f"exit_code={exit_code!r} event={event!r}"
    )
    assert event.get("event") != "SliceCommitted", (
        "a present-but-meaningless --slice-id must never reach a "
        f"SliceCommitted outcome. event={event!r}"
    )

    assert not repo.exists(), (
        "the refusal must happen BEFORE any git mutation -- no commit "
        "carrying a blank/whitespace Slice-Id: trailer may land, and no "
        f"repo directory should ever be created. repo={repo!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("meaningless_repo", _MEANINGLESS_SPELLINGS, ids=repr)
def test_repo_class_of_meaningless_spellings_never_resolves_to_caller_cwd(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    meaningless_repo: str,
) -> None:
    """``--repo`` spelled as any blank/whitespace-only value must REFUSE
    (``MalformedInput``, non-zero exit) -- never silently resolve to ``.``
    and commit into whatever directory the calling process happens to be
    standing in. The aim-at-the-wrong-repository trap, arriving through a
    different door than the ``<placeholder>`` trap it shares a root cause
    with (both are "a value that LOOKS like it names something, and does
    not").

    The caller's cwd is a REAL git repo with a real untracked change staged
    for ``--all`` to pick up: if ``--repo`` ever silently fell back to
    resolving against ``.``, this control would show a genuine commit
    landing in it -- not merely an absence of evidence.
    """
    caller_cwd = tmp_path / "caller_cwd_is_a_real_repo"
    _init_repo(caller_cwd)
    (caller_cwd / "src" / "app").mkdir(parents=True, exist_ok=True)
    (caller_cwd / "src" / "app" / "module.py").write_text(
        "def helper() -> str:\n    return 'would be picked up by --all'\n",
        encoding="utf-8",
    )
    head_before = _git(caller_cwd, "rev-parse", "HEAD").strip()
    monkeypatch.chdir(caller_cwd)

    exit_code = commit_slice_main(
        [
            "--repo",
            meaningless_repo,
            "--all",
            "--feature-id",
            "repo-empty-control",
            "--slice-id",
            "slice-01",
            "--message",
            "feat(slice): a commit whose --repo spells nothing",
        ]
    )
    event = _last_json_event(capsys.readouterr().out)

    assert exit_code != 0, (
        f"--repo={meaningless_repo!r} (a value that cannot name a real "
        f"repository) must REFUSE. got exit_code={exit_code!r} event={event!r}"
    )
    assert event.get("event") != "SliceCommitted", (
        f"a present-but-meaningless --repo must never reach a "
        f"SliceCommitted outcome. event={event!r}"
    )

    head_after = _git(caller_cwd, "rev-parse", "HEAD").strip()
    assert head_after == head_before, (
        "a blank/whitespace --repo must never silently resolve to '.' and "
        "commit into the caller's current directory. "
        f"head_before={head_before!r} head_after={head_after!r}"
    )
