"""Regression: `des verify-slice-commit` WITHOUT `--feature-id` (an OPTIONAL
flag) emits `SliceCommitComplete` -- a PASS -- instead of INDETERMINATE (the
silent-false-green class #126).

RCA (verified LIVE by a sister nWave instance, confirmed here empirically
against current code): on a bare git repo (one committed file, no `.nwave`,
no ledger, zero `.feature` files anywhere) `des verify-slice-commit --repo
<r> --commit HEAD` WITHOUT `--feature-id` prints
``{"event": "SliceCommitComplete", ...}`` and exits 0. WITH `--feature-id` the
SAME repo/commit correctly reaches `SliceCommitRefused` (the E2 contract gate
has nothing to resolve). Cause: without `--feature-id`,
``_run_legacy_completeness`` (``src/des/cli/verify_slice_commit_completeness.py``)
computes E1 completeness via
``des.application.slice_at_completeness.missing_at_files`` ->
``feature_files_for_slice``, which -- with zero `.feature` files matching the
slice tag anywhere on the tree -- returns an EMPTY candidate list. An empty
candidate list yields an empty "missing" list (nothing to be missing FROM),
so ``_run_legacy_completeness`` (verify_slice_commit_completeness.py:753-776)
unconditionally emits ``SliceCommitComplete`` on ``deficient == {}`` --
"I verified everything" and "I had nothing to verify" collapse into the SAME
green output. This is the false-green a prior EXAMINE run hit (the examiner
had omitted `--feature-id`).

The fix (crafter's job, NOT this test's): when `--feature-id` is absent (or
present but no feature is resolvable), emit `SliceCommitIndeterminate` +
the dedicated INDETERMINATE exit code
(``verify_slice_commit_completeness._GATE_INDETERMINATE_EXIT_CODE``, 3) --
"you didn't tell me which feature to verify, so I verified NOTHING" -- never
a fabricated `SliceCommitComplete`. The E2/feature-scoped verification logic
(``_run_verify_then_record``) is untouched by this bug and by this test --
it already reaches its real verdict (confirmed by
``test_present_feature_id_is_never_downgraded_to_indeterminate`` below).

Driving surface: ``des.cli.verify_slice_commit_completeness.main(argv)``, the
CLI's real entry point (in-process, composition-root driving port), against a
REAL throwaway git repo built under ``tmp_path`` (real `git init`/`add`/
`commit`; LOCAL `git config user.email`/`user.name`, never `--global`). The
observable is the emitted JSON verdict + exit code -- never internals.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from des.cli import verify_slice_commit_completeness as _vscc
from des.cli.verify_slice_commit_completeness import (
    _GATE_INDETERMINATE_EXIT_CODE,
    main,
)


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _init_bare_slice_repo(repo: Path, *, slice_id: str = "slice-01") -> None:
    """Build a real, throwaway git repo carrying ONE commit with a valid
    `Slice-Id:` trailer -- and NOTHING else: no `.feature` files, no
    `.nwave/`, no ledger. The minimal fixture that reproduces the RCA:
    "verified nothing" and "verified everything" must not collapse.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", f"do the thing\n\nSlice-Id: {slice_id}")


def _last_json_event(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    """Parse the LAST single-line JSON event `main()` printed on stdout.

    ``main()`` may also print a one-off runtime-freshness notice ahead of the
    real verdict (``des.runtime.freshness.autoskipped``) -- the verdict is
    always the LAST JSON line on stdout, mirroring the established pattern in
    ``test_verify_slice_commit_trailer_value_message.py``.
    """
    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert lines, f"expected at least one JSON line on stdout, got: {captured.out!r}"
    return json.loads(lines[-1])


class TestVerifySliceCommitRequiresFeatureId:
    """RED-CONFIRMED regression: a missing `--feature-id` must never emit a
    `SliceCommitComplete` PASS -- it verified nothing, so it must say so.
    """

    def test_missing_feature_id_is_indeterminate_not_complete(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """POSITIVE (the bug, RED today): a bare repo with zero `.feature`
        files anywhere and NO `--feature-id` must emit
        `SliceCommitIndeterminate` (exit
        `_GATE_INDETERMINATE_EXIT_CODE` == 3) -- NEVER the false-green
        `SliceCommitComplete` (exit 0) that today's code emits, because E1
        completeness vacuously reports "nothing missing" when it found ZERO
        `.feature` candidates to check in the first place.
        """
        repo = tmp_path / "repo"
        _init_bare_slice_repo(repo)

        # Confirm the fixture is honest: no `.feature` AT file exists
        # anywhere on this throwaway tree -- the gate has literally nothing
        # to verify E1 completeness against.
        assert not list(repo.rglob("*.feature")), (
            "fixture setup broken: a .feature file exists on the throwaway "
            "tree -- this test requires a repo with ZERO .feature files"
        )

        exit_code = main(["--repo", str(repo), "--commit", "HEAD"])

        event = _last_json_event(capsys)
        assert event.get("event") != "SliceCommitComplete", (
            "BUG: a slice commit verified with NO --feature-id must never "
            f"emit the false-green SliceCommitComplete -- got: {event!r}"
        )
        assert event.get("event") == "SliceCommitIndeterminate", (
            "a missing --feature-id must produce an honest "
            f"SliceCommitIndeterminate verdict -- got: {event!r}"
        )
        assert exit_code == _GATE_INDETERMINATE_EXIT_CODE, (
            "a missing --feature-id must exit with the dedicated "
            f"INDETERMINATE exit code ({_GATE_INDETERMINATE_EXIT_CODE}) -- "
            f"got exit {exit_code}, event {event!r}"
        )
        error = str(event.get("error", "")).lower()
        assert "feature" in error, (
            "the emitted reason must explain that no feature was specified "
            f"or resolvable to verify against -- got: {event.get('error')!r}"
        )

    def test_present_feature_id_is_never_downgraded_to_indeterminate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """NEGATIVE AT (`_never_`): the fix must NOT overcorrect. The SAME
        bare repo/commit, but WITH `--feature-id` supplied, must still reach
        its OWN real verdict (here: `SliceCommitRefused` -- a nonexistent
        feature owns zero recognized AT candidates, so E1's taxonomy-blind
        guard refuses it, per RCA fix-carpaccio-e1-vacuous-taxonomy-gap --
        see the sibling
        `TestRunVerifyChecksAtomicPathTaxonomyBlindGuard.test_taxonomy_blind_non_exempt_slice_refuses_before_reaching_e2`,
        the identical fixture shape) -- it must NOT be forced into the
        missing-feature-id `SliceCommitIndeterminate` path (Bug #126's
        DISTINCT legacy-completeness codepath, `_run_legacy_completeness`,
        never entered when `--feature-id` is present). Pins that only the
        MISSING-`--feature-id` case enters that INDETERMINATE codepath -- a
        PRESENT-but-unresolvable `--feature-id` reaches the atomic
        verify-then-record gate's own refusal instead.
        """
        repo = tmp_path / "repo"
        _init_bare_slice_repo(repo)

        exit_code = main(
            [
                "--repo",
                str(repo),
                "--commit",
                "HEAD",
                "--feature-id",
                "some-nonexistent-feature",
            ]
        )

        event = _last_json_event(capsys)
        assert event.get("event") == "SliceCommitRefused", (
            "a present --feature-id must reach its OWN real verdict "
            f"(SliceCommitRefused) -- got: {event!r}"
        )
        assert event.get("refused_half") == "E1", (
            "a nonexistent feature owns zero recognized AT candidates, so "
            "the refusal must come from E1's taxonomy-blind guard -- got: "
            f"{event!r}"
        )
        assert exit_code == 1, (
            f"a present --feature-id refusal must exit 1 -- got {exit_code}"
        )
        # The distinguishing property: this must NOT be the missing-
        # feature-id INDETERMINATE outcome.
        assert event.get("event") != "SliceCommitIndeterminate", (
            "BUG-OVERCORRECTION: a present --feature-id must never be "
            f"downgraded to the missing-feature-id INDETERMINATE path -- "
            f"got: {event!r}"
        )
        assert exit_code != _GATE_INDETERMINATE_EXIT_CODE

    def test_missing_feature_id_indeterminate_distinct_from_malformed_input(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Boundary regression guard: the NEW missing-`--feature-id`
        INDETERMINATE exit code must stay distinct from the PRE-EXISTING
        malformed-input exit code (2, e.g. no `Slice-Id:` trailer at all) --
        the fix must add a third distinguishable outcome, not collapse two
        already-different meanings ("no trailer" vs "no feature to verify
        against") into the same exit code.
        """
        repo = tmp_path / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        _run_git(repo, "init", "-q")
        _run_git(repo, "config", "user.email", "test@example.com")
        _run_git(repo, "config", "user.name", "Test")
        (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
        _run_git(repo, "add", "README.md")
        _run_git(repo, "commit", "-q", "-m", "no trailer at all here")

        malformed_exit = main(["--repo", str(repo), "--commit", "HEAD"])
        malformed_event = _last_json_event(capsys)
        assert malformed_event.get("event") == "MalformedInput"
        assert malformed_exit == 2

        repo2 = tmp_path / "repo2"
        _init_bare_slice_repo(repo2)
        indeterminate_exit = main(["--repo", str(repo2), "--commit", "HEAD"])
        indeterminate_event = _last_json_event(capsys)

        assert indeterminate_exit != malformed_exit, (
            "the missing-feature-id INDETERMINATE exit code must be "
            f"distinct from the malformed-input exit code ({malformed_exit}) "
            f"-- got the same code for both: {indeterminate_event!r}"
        )
        assert indeterminate_event.get("event") != "MalformedInput"


def _write_prefactoring_exempt_slice_plan(
    repo: Path, feature_id: str, slice_id: str
) -> None:
    """A minimal feature-delta `[REF] Slice Plan` declaring ``slice_id``
    `@prefactoring` (``AtRequirement.EXEMPT``) -- the SAME precedent shape
    ``tests/bugs/des/test_commit_slice_writes_verified_record.py`` and
    ``tests/des/cli/f_prefactoring_dispatch_clears_honestly/
    test_bugfix_exit_gate_honors_prefactoring_lane.py`` build, read by
    `_is_at_exempt_lane` (`verify_slice_commit_completeness.py:428-446`) via
    `parse_slice_plan` + `_lane_profile_for_slice`.
    """
    delta_dir = repo / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {slice_id} | a behavior-preserving refactor introduces the seam | "
        "pending | @prefactoring | a green-to-green prefactoring, genuinely "
        "zero AT by design |\n",
        encoding="utf-8",
    )


def _run_verify_checks_namespace(
    repo: Path,
    feature_id: str,
    *,
    commit: str = "HEAD",
    at_kind: str = "gherkin",
    regression_test_file: str | None = None,
    slice_id: str | None = None,
) -> argparse.Namespace:
    """The `argparse.Namespace` shape `_build_parser().parse_args(...)`
    would produce for the atomic `--feature-id`-present CLI path -- built
    directly (no real argv parse) so `_run_verify_checks` can be driven in
    isolation from `main()`'s HEAD-race + dispatch wiring.
    """
    return argparse.Namespace(
        repo=str(repo),
        commit=commit,
        feature_id=feature_id,
        expected_head=None,
        scope_feature_id=None,
        at_kind=at_kind,
        regression_test_file=regression_test_file,
        slice_id=slice_id,
    )


class TestRunVerifyChecksAtomicPathTaxonomyBlindGuard:
    """RCA fix-carpaccio-e1-vacuous-taxonomy-gap: the atomic `--feature-id`-
    present path (`_run_verify_checks`, feeding `des commit-slice` / `des
    verify-slice-commit --feature-id`) is named by the RCA as the MOST
    load-bearing UNGUARDED consumer of `missing_at_files` -- unlike its
    sibling `_run_legacy_completeness` (Bug #126, already fixed), this path
    has NO guard at all for the vacuous-empty case: `deficient == {}`
    (whether genuinely verified-complete OR taxonomy-blind with zero
    candidates) falls straight through to E2 as if genuinely verified.
    """

    def test_taxonomy_blind_non_exempt_slice_refuses_before_reaching_e2(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """RED: a slice whose AT layout matches NEITHER the .feature nor the
        pytest-tagged taxonomy (zero candidates anywhere), carrying NO
        `@prefactoring` exemption, must be REFUSED at E1 -- `_run_verify_
        checks` must never even invoke E2 (`_run_contract_gate`) for it.
        Today E1's `deficient` dict is vacuously empty (nothing to check,
        not nothing missing), so the atomic gate falls straight through to
        E2 unguarded.
        """
        repo = tmp_path / "repo"
        _init_bare_slice_repo(repo, slice_id="slice-01")
        # No feature-delta at all -- `_is_at_exempt_lane` fails closed to
        # False (not exempt), matching the RCA's non-exempt negative case.

        e2_calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

        def _record_and_fail_e2(*args: object, **kwargs: object) -> tuple[int, None]:
            e2_calls.append((args, kwargs))
            return 99, None

        monkeypatch.setattr(_vscc, "_run_contract_gate", _record_and_fail_e2)

        args = _run_verify_checks_namespace(repo, "taxonomy-blind-nonexempt-feature")
        exit_code, verified_context = _vscc._run_verify_checks(repo, args)

        captured = capsys.readouterr()
        json_lines = [
            ln for ln in captured.out.splitlines() if ln.strip().startswith("{")
        ]
        event = json.loads(json_lines[-1]) if json_lines else {}

        assert not e2_calls, (
            "BUG: E1 vacuously cleared (zero AT candidates found, not zero "
            "missing) for a taxonomy-blind, non-exempt slice, so "
            "_run_verify_checks fell through to E2 -- _run_contract_gate "
            f"was invoked: calls={e2_calls!r}"
        )
        assert verified_context is None, (
            f"a taxonomy-blind, non-exempt slice must never earn a "
            f"_VerifiedSliceContext -- got {verified_context!r}"
        )
        assert exit_code == 1, (
            f"a taxonomy-blind, non-exempt slice must be REFUSED (exit 1) "
            f"at E1 -- got exit_code={exit_code!r}, event={event!r}"
        )
        assert event.get("event") == "SliceCommitRefused", event
        assert event.get("refused_half") == "E1", (
            "the refusal must be attributed to E1 (zero AT candidates "
            f"found), not E2 -- got: {event!r}"
        )

    def test_prefactoring_exempt_taxonomy_blind_slice_still_clears(
        self, tmp_path: Path
    ) -> None:
        """NON-REGRESSION (the RCA's single highest-risk edge, "Legitimate-
        Zero-AT Non-Regression Note"): a slice DECLARED `@prefactoring`
        (`AtRequirement.EXEMPT`) in the feature-delta's `[REF] Slice Plan`
        is ALSO taxonomy-blind (zero AT candidates by design) -- it must
        STILL clear `_run_verify_checks`, exactly as it does today. The
        fix's new non-verifiable refusal MUST be gated on
        `not _is_at_exempt_lane(...)`, or this legitimate lane regresses
        into a false refusal. Must stay GREEN both BEFORE and AFTER the fix.
        """
        repo = tmp_path / "repo"
        feature_id = "taxonomy-blind-exempt-feature"
        slice_id = "slice-02"
        _init_bare_slice_repo(repo, slice_id=slice_id)
        _write_prefactoring_exempt_slice_plan(repo, feature_id, slice_id)

        args = _run_verify_checks_namespace(repo, feature_id)
        exit_code, verified_context = _vscc._run_verify_checks(repo, args)

        assert exit_code == 0, (
            "a genuinely zero-AT, @prefactoring-exempt slice must clear "
            f"_run_verify_checks (exit 0) -- got exit_code={exit_code!r}, "
            f"verified_context={verified_context!r}"
        )
        assert verified_context is not None, (
            "expected a _VerifiedSliceContext for the exempt lane's clear "
            "verdict -- got None (refused/indeterminate instead)"
        )
        assert verified_context.feature_id == feature_id
        assert verified_context.slice_ids == [slice_id]
