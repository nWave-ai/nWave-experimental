"""Regression -- the pytest-regression E2 leg of `des verify-slice-commit` /
`des commit-slice` must scope its per-slice check to {shipped} UNION
{entering}, and must never silently misroute a pytest-regression-authored
feature into the gherkin scope resolver.

RCA: `docs/feature/fix-contract-gate-slice-scope/deliver/rca.md`.
Charter: `docs/product/expectations/fix-contract-gate-slice-scope/
a-finished-slice-gets-certified-without-its-work-ahead-tests-counted-
against-it.md`.

The bug was ORIGINALLY reported as "the per-slice contract gate runs the
whole feature suite and trips on a future slice's RED work-ahead ATs". The
RCA DISPROVED that headline story -- a correctly-invoked pytest-regression
call cannot even SEE a future slice's tests. This file pins the THREE root
causes the RCA actually established, NOT the disproved story:

RC1 (`src/des/cli/verify_slice_commit_completeness.py` `_build_parser`
default + `_run_verify_then_record`, `run_contract_gate.py:2849-2856`) --
`--at-kind` defaults to `"gherkin"` with NO feature-layout introspection. A
feature authored with pytest-regression ATs, invoked without the explicit
flags, is unconditionally routed into `_mode_feature_scoped`, which demands
`.feature` files the feature was never designed to have, and REFUSES
`zero-collected` -- for a reason that has nothing to do with the operator's
code. The E2 refusal payload also does not thread the child gate's own
self-explaining `reason` through (a bare `contract_gate_exit_code: 2`).

RC2 (`verify_slice_commit_completeness.py:466-523`, `_run_regression_gate`)
-- THE HEADLINE DEFECT. Even when `--at-kind pytest-regression` IS supplied,
the E2 leg runs ONLY the entering slice's single declared regression file.
There is no pytest equivalent of `run_contract_gate._narrow_to_shipped_
entering`. A SHIPPED slice that has gone RED is never re-checked at all --
a FALSE-GREEN: the gate certifies the entering slice while blind to every
slice already delivered.

RC3 (why no existing code closes RC1+RC2) -- the ledger-based resolver that
WOULD answer "which slices are shipped" already exists
(`verify_deliver_integrity._slice_commit_verified_slices`, imported into
`commit_slice.py:84-87`) but is never consulted from this E2 leg. Not
independently pinned by its own AT here -- RC1 and RC2's fixtures below are
the observable proof that the missing wiring matters; RC3 is the "why", not
a separate behaviour.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL `des.cli.verify_slice_commit_completeness.main()` CLI driver,
captured via `capsys` -- mirrors every sibling regression AT in this
directory (e.g. `test_slice_commit_refused_names_how.py`,
`tests/des/acceptance/test_attest_legacy_commit_slice_id_override.py`). No
monkeypatching of the E2 gate: the pytest-regression leg's real subprocess
spawn (`des_spawn("pytest", ...)`) is exercised for real (the proven,
already-GREEN pattern in
`test_attest_legacy_commit_slice_id_override.py::
test_legacy_trailer_path_is_unchanged_without_the_override_flag`), so the
false-green this file pins is observed on the real execution path, not
faked via a mock.

Fixtures: real tmp git repos (own local `user.name`/`user.email`, git-safety
rule #48). Regression test files double as the E1 delivered-AT artifact
(pytest head-comment-tag convention `# @feature-{id}` / `# @{slice-NN}`) and
the E2 behavioral witness, mirroring the proven sibling fixture shape.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import verify_slice_commit_completeness as vscc


_FEATURE_RC2_HEADLINE = "fix-contract-gate-slice-scope-rc2-headline"
_FEATURE_RC2_CLEAN = "fix-contract-gate-slice-scope-rc2-clean"
_FEATURE_RC2_ENTERING_BROKEN = "fix-contract-gate-slice-scope-rc2-entering-broken"
_FEATURE_RC1_MISROUTE = "fix-contract-gate-slice-scope-rc1-misroute"
_FEATURE_RC1_GHERKIN_UNCHANGED = "fix-contract-gate-slice-scope-rc1-gherkin-unchanged"


# ---------------------------------------------------------------------------
# Shared fixture builders
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` (raises on non-zero), return stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _git_init(repo: Path) -> None:
    """Isolated tmp repo with its OWN local git config (rule #48) -- the real
    project repo's `user.name`/`user.email` are never read or touched.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "atdd@nwave.ai")
    _git(repo, "config", "user.name", "atdd")


def _write_regression_test(
    repo: Path, feature_id: str, slice_id: str, suffix: str, *, passing: bool
) -> Path:
    """A real, pytest-collectible regression test, head-tagged for E1
    discovery (`# @feature-{id}` / `# @{slice-NN}`) -- doubles as the E1
    delivered-AT artifact and the E2 behavioral witness (mirrors
    `test_attest_legacy_commit_slice_id_override.py::_write_regression_test`).
    """
    rel_dir = Path("tests") / "fixture" / feature_id.replace("-", "_")
    path = repo / rel_dir / f"test_{slice_id.replace('-', '_')}_{suffix}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    name = f"test_{slice_id.replace('-', '_')}_{suffix}_behaviour"
    if passing:
        body = f"def {name}():\n    assert 1 + 1 == 2\n"
    else:
        body = (
            f"def {name}():\n"
            f"    assert 1 + 1 == 3, "
            f"'deliberately broken for the {slice_id} regression fixture'\n"
        )
    path.write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n{body}",
        encoding="utf-8",
    )
    return path


def _write_feature_file(repo: Path, feature_id: str, slice_id: str) -> Path:
    """A real, tagged `.feature` file -- the gherkin AT layout RC1's negative
    control proves is NEVER rerouted to the pytest-regression attestation.
    """
    path = repo / "tests" / "acceptance" / f"{feature_id.replace('-', '_')}.feature"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"@feature-{feature_id}\n"
        "Feature: fixture gherkin feature\n\n"
        f"  @{slice_id}\n"
        "  Scenario: fixture scenario\n"
        "    Given a fixture precondition\n"
        "    When the fixture action occurs\n"
        "    Then the fixture outcome holds\n",
        encoding="utf-8",
    )
    return path


def _commit_with_trailer(repo: Path, slice_id: str, subject: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"{subject}\n\nSlice-Id: {slice_id}")


def _run_verify_slice_commit(
    repo: Path,
    feature_id: str,
    capsys: pytest.CaptureFixture[str],
    *,
    at_kind: str | None = None,
    regression_test_file: str | None = None,
) -> tuple[int, dict[str, object]]:
    """Drive the REAL `des verify-slice-commit` CLI (`main()`) in-process
    (Layer 3 composition -- no interpreter fork for the EDGE itself; the E2
    leg's OWN subprocess spawns for real underneath), capturing its
    single-line JSON payload via `capsys`.
    """
    argv = ["--repo", str(repo), "--commit", "HEAD", "--feature-id", feature_id]
    if at_kind is not None:
        argv += ["--at-kind", at_kind]
    if regression_test_file is not None:
        argv += ["--regression-test-file", regression_test_file]
    exit_code = vscc.main(argv)
    stdout = capsys.readouterr().out
    json_lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    payload: dict[str, object] = json.loads(json_lines[-1]) if json_lines else {}
    return exit_code, payload


# ===========================================================================
# RC2 -- THE HEADLINE DEFECT: a shipped slice going RED must refuse the
# commit. Today it doesn't -- a FALSE-GREEN. Active-RED today.
# ===========================================================================


def test_shipped_slice_gone_red_refuses_the_entering_slice_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """slice-01 is already SHIPPED (a `SliceCommitVerified` ledger record
    exists for it) but its regression test is now RED on the committed tree.
    slice-02 (the entering slice) is green. The commit must be REFUSED --
    the gate must re-check every shipped+entering regression file, not only
    the entering slice's own declared file.

    RED for the right reason today: `_run_regression_gate`
    (`verify_slice_commit_completeness.py:466-523`) runs EXACTLY the
    declared `--regression-test-file` (slice-02's) and never so much as
    globs for slice-01's file -- so today this clears (exit 0,
    `SliceCommitVerified`), a real, semantic false-green, not a crash or
    collection error.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    feature_id = _FEATURE_RC2_HEADLINE
    _write_regression_test(repo, feature_id, "slice-01", "shipped", passing=False)
    entering_file = _write_regression_test(
        repo, feature_id, "slice-02", "entering", passing=True
    )
    _commit_with_trailer(repo, "slice-02", "feat(slice): entering slice behaviour")
    AtCompletionLedger(feature_id, repo).append_gate_event(
        event="SliceCommitVerified", slice_id="slice-01"
    )

    exit_code, payload = _run_verify_slice_commit(
        repo,
        feature_id,
        capsys,
        at_kind="pytest-regression",
        regression_test_file=str(entering_file.relative_to(repo)),
    )

    assert exit_code != 0, (
        "a SHIPPED slice (slice-01) whose regression test has gone RED must "
        "REFUSE the commit even though the entering slice (slice-02) is "
        "green -- today this E2 leg never re-checks any shipped slice at "
        f"all, so it FALSE-GREENs. got exit_code={exit_code!r} "
        f"payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitRefused", (
        f"expected a SliceCommitRefused verdict -- payload={payload!r}"
    )

    haystack = json.dumps(payload)
    assert "slice-01" in haystack, (
        "the refusal must name the BROKEN SHIPPED slice (slice-01), not "
        f"just the entering slice -- payload={payload!r}"
    )

    verified = AtCompletionLedger(feature_id, repo).verified_slices()
    assert "slice-02" not in verified, (
        "the entering slice must never earn a fabricated SliceCommitVerified "
        f"while a shipped sibling slice is red -- verified={sorted(verified)!r}"
    )


# ===========================================================================
# RC2 -- fault-injection / positive controls (green now AND after the fix)
# ===========================================================================


@pytest.mark.negative_at
def test_all_shipped_and_entering_slices_green_still_verifies_with_a_future_slice_invisible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Positive control (item 4a) + over-correction guard (item 3, the
    original disproved deadlock): a genuinely clean commit (shipped slice-01
    green, entering slice-02 green) must still VERIFY -- the fix must not
    make everything refuse. A work-ahead slice-03, authored per the
    pipelining mandate and deliberately RED, is neither shipped nor
    entering: it must stay structurally INVISIBLE to this gate. Pulling it
    in would recreate the very deadlock this fix exists to avoid.

    Green both BEFORE the fix (today's narrower "entering-file-only" scope
    trivially never sees slice-03 either) and AFTER (the fix's shipped-set
    resolver is keyed on the ledger, never a blind directory sweep).
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    feature_id = _FEATURE_RC2_CLEAN
    _write_regression_test(repo, feature_id, "slice-01", "shipped", passing=True)
    entering_file = _write_regression_test(
        repo, feature_id, "slice-02", "entering", passing=True
    )
    _write_regression_test(repo, feature_id, "slice-03", "future", passing=False)
    _commit_with_trailer(repo, "slice-02", "feat(slice): entering slice behaviour")
    AtCompletionLedger(feature_id, repo).append_gate_event(
        event="SliceCommitVerified", slice_id="slice-01"
    )

    exit_code, payload = _run_verify_slice_commit(
        repo,
        feature_id,
        capsys,
        at_kind="pytest-regression",
        regression_test_file=str(entering_file.relative_to(repo)),
    )

    assert exit_code == 0, (
        "a genuinely clean commit (shipped slice-01 green, entering slice-02 "
        "green) must still VERIFY -- the fix must not make everything "
        f"refuse. got exit_code={exit_code!r} payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", payload

    haystack = json.dumps(payload)
    assert "slice-03" not in haystack, (
        "a work-ahead slice that is neither shipped nor entering must stay "
        "structurally invisible to this gate, even though it is "
        "deliberately RED on disk -- pulling it in would recreate the "
        f"original (disproved) deadlock. payload={payload!r}"
    )


@pytest.mark.negative_at
def test_broken_entering_slice_still_refuses_even_with_a_green_shipped_slice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Positive control (item 4b): a genuinely broken ENTERING slice must
    still be REFUSED regardless of the fix -- the fix must not make
    everything pass. Already true today (the entering file IS what's run);
    must remain true after the fix widens the scope to shipped+entering.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    feature_id = _FEATURE_RC2_ENTERING_BROKEN
    _write_regression_test(repo, feature_id, "slice-01", "shipped", passing=True)
    entering_file = _write_regression_test(
        repo, feature_id, "slice-02", "entering", passing=False
    )
    _commit_with_trailer(repo, "slice-02", "feat(slice): entering slice behaviour")
    AtCompletionLedger(feature_id, repo).append_gate_event(
        event="SliceCommitVerified", slice_id="slice-01"
    )

    exit_code, payload = _run_verify_slice_commit(
        repo,
        feature_id,
        capsys,
        at_kind="pytest-regression",
        regression_test_file=str(entering_file.relative_to(repo)),
    )

    assert exit_code != 0, (
        "a genuinely broken ENTERING slice must still be REFUSED -- the fix "
        f"must not make everything pass. got exit_code={exit_code!r} "
        f"payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitRefused", payload

    verified = AtCompletionLedger(feature_id, repo).verified_slices()
    assert "slice-02" not in verified, (
        "a broken entering slice must never earn SliceCommitVerified -- "
        f"verified={sorted(verified)!r}"
    )


# ===========================================================================
# RC1 -- no silent misroute. Active-RED today.
# ===========================================================================


def test_pytest_regression_feature_without_at_kind_flag_is_not_silently_misrouted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A feature authored entirely with pytest-regression ATs (zero
    `.feature` files) invoked WITHOUT `--at-kind`/`--regression-test-file`
    (the caller "forgot" the flag -- exactly the original RCA reproduction)
    must NOT be silently refused for a reason unrelated to the operator's
    code. Either it introspects the feature's layout and routes correctly
    to the pytest-regression leg, OR it refuses with a self-explaining
    message naming the mismatch (this feature has no `.feature` files /
    pass `--at-kind pytest-regression`). It must NOT refuse with a bare
    `contract_gate_exit_code: 2` that names neither.

    RED for the right reason today: `--at-kind` defaults to `"gherkin"`
    with no feature-layout introspection
    (`verify_slice_commit_completeness.py` `_build_parser` default), so this
    call is routed into `run_contract_gate._mode_feature_scoped`, which
    resolves ZERO `.feature` files and refuses `zero-collected`
    (`run_contract_gate.py:2849-2856`) -- and the E2 refusal payload
    (`verify_slice_commit_completeness.py:986-1006`) surfaces only a bare
    `contract_gate_exit_code: 2`, threading NONE of the child gate's own
    `reason`/`what`/`why`.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    feature_id = _FEATURE_RC1_MISROUTE
    _write_regression_test(repo, feature_id, "slice-01", "only", passing=True)
    _commit_with_trailer(
        repo, "slice-01", "feat(slice): pytest-regression-only feature"
    )

    exit_code, payload = _run_verify_slice_commit(repo, feature_id, capsys)

    if exit_code == 0:
        assert payload.get("event") == "SliceCommitVerified", (
            "an auto-routed, cleared pytest-regression-only feature must "
            f"emit SliceCommitVerified -- payload={payload!r}"
        )
        return

    haystack = json.dumps(payload).lower()
    self_explains = any(
        marker in haystack
        for marker in (
            "pytest-regression",
            "at-kind",
            "at_kind",
            "no .feature",
            "zero-collected",
            "reason",
        )
    )
    assert self_explains, (
        "a pytest-regression-only feature invoked WITHOUT --at-kind must not "
        "be silently routed into the gherkin scope resolver and refused for "
        "a reason unrelated to the operator's code (RC1) -- today it "
        "refuses with a BARE contract_gate_exit_code=2, naming neither the "
        "at-kind mismatch nor the child gate's own zero-collected reason: "
        f"payload={payload!r}"
    )


# ===========================================================================
# RC1 -- negative control: gherkin stays byte-unchanged when .feature files
# genuinely exist. Green now AND after the fix.
# ===========================================================================


@pytest.mark.negative_at
def test_gherkin_feature_without_at_kind_flag_is_never_rerouted_to_pytest_regression(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A feature that legitimately HAS `.feature` files, invoked without
    `--at-kind`, must never be silently rerouted to the pytest-regression
    attestation path -- gherkin stays the explicit default whenever
    `.feature` files exist (the fix must only ever route TOWARD
    pytest-regression when NO `.feature` files resolve). Green both BEFORE
    and AFTER the fix -- this scenario is untouched by either fix.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    feature_id = _FEATURE_RC1_GHERKIN_UNCHANGED
    _write_feature_file(repo, feature_id, "slice-01")
    _commit_with_trailer(repo, "slice-01", "feat(slice): gherkin-authored feature")

    _exit_code, payload = _run_verify_slice_commit(repo, feature_id, capsys)

    assert "regression_test_file" not in payload, (
        "a feature that legitimately has .feature files must never be "
        "rerouted to the pytest-regression attestation path just because "
        f"--at-kind was omitted -- payload={payload!r}"
    )
    assert payload.get("attested_via") != "slice-id-override", payload
    # exit_code/event shape is deliberately UNASSERTED here -- an unbound
    # `.feature` collection outcome (zero-collected / collection-failed /
    # a genuine pass) is not this control's concern; only "never rerouted
    # to pytest-regression" is.


# ===========================================================================
# THE EXAMINER'S DEFECT -- the refusal testifies, the consent does not.
# leg_census lesson (`certification-legs-observe-real-execution`) at the
# per-slice altitude: "An attestation that does not exhibit what it
# observed is indistinguishable from an attestation over nothing."
#
# Do NOT design the payload's shape -- these probes only demand the
# executed regression-file path(s) appear SOMEWHERE in the serialized
# payload (mirroring the existing `haystack = json.dumps(payload)`
# substring-membership idiom above), never a specific field name.
# ===========================================================================


_FEATURE_VERIFIED_EXHIBITS_SCOPE = "fix-contract-gate-slice-scope-verified-exhibits"


def _executed_scope_mentions(payload: dict[str, object]) -> set[str]:
    """Every ``tests/**/*.py``-shaped path substring anywhere in the payload.

    Outcome-shaped probe: the crafter is free to choose ANY field name or
    structure to exhibit what it executed -- this only demands the executed
    regression-file path(s) surface SOMEWHERE in the serialized payload.
    """
    haystack = json.dumps(payload)
    return set(re.findall(r"tests/[\w./-]+?\.py", haystack))


def test_verified_payload_names_the_regression_files_it_actually_ran(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The PASS payload must EXHIBIT what it ran (the examiner's finding).

    A genuinely clean commit (shipped slice-01 green, entering slice-02
    green) must emit a `SliceCommitVerified` payload that NAMES the
    regression file(s) it actually executed for {shipped}∪{entering} --
    not merely `slice_ids`.

    RED for the right reason today: the success payload
    (`verify_slice_commit_completeness.py:1326-1334`) carries only
    `event`/`slice_ids`/`commit`/`commit_sha` -- neither the shipped
    slice's file nor the entering slice's file appears anywhere in the
    serialized payload, so "I cannot tell whether the gate really ran my
    slice's tests, or skipped everything" (the examiner's own words).
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    feature_id = _FEATURE_VERIFIED_EXHIBITS_SCOPE + "-names-what-it-ran"
    shipped_file = _write_regression_test(
        repo, feature_id, "slice-01", "shipped", passing=True
    )
    entering_file = _write_regression_test(
        repo, feature_id, "slice-02", "entering", passing=True
    )
    _commit_with_trailer(repo, "slice-02", "feat(slice): entering slice behaviour")
    AtCompletionLedger(feature_id, repo).append_gate_event(
        event="SliceCommitVerified", slice_id="slice-01"
    )

    exit_code, payload = _run_verify_slice_commit(
        repo,
        feature_id,
        capsys,
        at_kind="pytest-regression",
        regression_test_file=str(entering_file.relative_to(repo)),
    )

    assert exit_code == 0, (
        f"sanity: expected a clean verify -- exit_code={exit_code!r} "
        f"payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", payload

    executed = _executed_scope_mentions(payload)
    shipped_rel = str(shipped_file.relative_to(repo))
    entering_rel = str(entering_file.relative_to(repo))
    assert shipped_rel in executed and entering_rel in executed, (
        "a successful SliceCommitVerified must EXHIBIT the regression "
        "test file(s) it actually executed for {shipped}∪{entering} -- "
        "today's payload names only slice_ids, never the files it ran. "
        f"expected_files=[{shipped_rel!r}, {entering_rel!r}] "
        f"executed_scope_found={sorted(executed)!r} payload={payload!r}"
    )


@pytest.mark.negative_at
def test_verified_never_carries_an_empty_executed_scope(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The durable invariant: verified ⇒ non-empty exhibited executed-scope.

    The leg_census lesson at the per-slice altitude -- a `SliceCommitVerified`
    must NEVER be emitted while having run nothing observable. Even the
    minimal single-slice case (no shipped siblings, just the entering
    slice) must exhibit the file it ran; the gate must not be able to
    certify over an empty executed-scope.
    """
    repo = tmp_path / "repo"
    _git_init(repo)
    feature_id = _FEATURE_VERIFIED_EXHIBITS_SCOPE + "-never-empty"
    entering_file = _write_regression_test(
        repo, feature_id, "slice-01", "only", passing=True
    )
    _commit_with_trailer(repo, "slice-01", "feat(slice): only slice behaviour")

    exit_code, payload = _run_verify_slice_commit(
        repo,
        feature_id,
        capsys,
        at_kind="pytest-regression",
        regression_test_file=str(entering_file.relative_to(repo)),
    )

    assert exit_code == 0, (
        f"sanity: expected a clean verify -- exit_code={exit_code!r} "
        f"payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitVerified", payload

    executed = _executed_scope_mentions(payload)
    assert executed, (
        "verified ⇒ the exhibited executed-scope must be non-empty -- a "
        "SliceCommitVerified with zero observable executed-files is, "
        "epistemically, the SAME SHAPE as a verdict issued over nothing "
        f"observed. payload={payload!r}"
    )


def test_verified_payload_testifies_as_much_as_the_refusal_payload_does(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Symmetry: the refusal already testifies -- the consent must too.

    Two sibling commits, same feature shape (shipped slice-01 green,
    entering slice-02): one clean (expect `SliceCommitVerified`), one with
    the entering slice broken (expect `SliceCommitRefused`, which already
    names `regression_test_file`). A reader must be able to answer "what
    did you actually check?" from EITHER verdict, without asking anyone --
    the charter's own oracle row.
    """
    clean_repo = tmp_path / "clean_repo"
    _git_init(clean_repo)
    clean_feature = _FEATURE_VERIFIED_EXHIBITS_SCOPE + "-symmetry-clean"
    _write_regression_test(
        clean_repo, clean_feature, "slice-01", "shipped", passing=True
    )
    clean_entering = _write_regression_test(
        clean_repo, clean_feature, "slice-02", "entering", passing=True
    )
    _commit_with_trailer(
        clean_repo, "slice-02", "feat(slice): entering slice behaviour"
    )
    AtCompletionLedger(clean_feature, clean_repo).append_gate_event(
        event="SliceCommitVerified", slice_id="slice-01"
    )
    _, verified_payload = _run_verify_slice_commit(
        clean_repo,
        clean_feature,
        capsys,
        at_kind="pytest-regression",
        regression_test_file=str(clean_entering.relative_to(clean_repo)),
    )

    broken_repo = tmp_path / "broken_repo"
    _git_init(broken_repo)
    broken_feature = _FEATURE_VERIFIED_EXHIBITS_SCOPE + "-symmetry-broken"
    _write_regression_test(
        broken_repo, broken_feature, "slice-01", "shipped", passing=True
    )
    broken_entering = _write_regression_test(
        broken_repo, broken_feature, "slice-02", "entering", passing=False
    )
    _commit_with_trailer(
        broken_repo, "slice-02", "feat(slice): entering slice behaviour"
    )
    AtCompletionLedger(broken_feature, broken_repo).append_gate_event(
        event="SliceCommitVerified", slice_id="slice-01"
    )
    _, refused_payload = _run_verify_slice_commit(
        broken_repo,
        broken_feature,
        capsys,
        at_kind="pytest-regression",
        regression_test_file=str(broken_entering.relative_to(broken_repo)),
    )

    assert refused_payload.get("event") == "SliceCommitRefused", refused_payload
    assert verified_payload.get("event") == "SliceCommitVerified", verified_payload

    refused_scope = _executed_scope_mentions(refused_payload)
    verified_scope = _executed_scope_mentions(verified_payload)
    assert refused_scope, (
        f"sanity: the refusal already testifies -- payload={refused_payload!r}"
    )
    assert verified_scope, (
        "the CONSENT must testify at least as much as the refusal does -- a "
        "reader must be able to answer 'what did you actually check?' from "
        "EITHER verdict, without asking anyone. Today the PASS payload "
        f"names nothing it ran. refused_scope={sorted(refused_scope)!r} "
        f"verified_scope={sorted(verified_scope)!r} "
        f"verified_payload={verified_payload!r}"
    )


# ===========================================================================
# THE TRAP THAT VOID'D TWO INDEPENDENT EXAMS -- a refusal that names an
# UNRELATED cause is worse than one that says nothing: it sends the
# operator hunting a phantom in their own innocent code.
#
# --repo points at a repo that has NEVER HEARD OF the named --feature-id
# (no .feature files, no regression files, no footprint at all) -- the
# overwhelmingly natural way to trigger this is `--repo .` from inside a
# repo where the feature lives only in a throwaway fixture elsewhere.
#
# RCA (confirmed by reading the real code paths, not guessed): E1
# (`missing_at_files` -> `feature_files_for_slice`) vacuously reports
# "nothing missing" when the feature owns ZERO `.feature` candidates in
# this repo -- E1 always clears here. E2 (`_run_contract_gate`,
# verify_slice_commit_completeness.py:454-469) spawns
# `run_contract_gate --feature-id` as a subprocess, and that CHILD gate
# already emits a genuinely self-explaining `FeatureScopeMalformed`
# (`reason: "zero-collected"`, `error: "no .feature file resolves under
# feature id '<id>' -- the scoped contract gate would pass vacuously"`,
# run_contract_gate.py:2849-2856) -- naming the feature-id and the real
# cause. But `_run_contract_gate` captures the child's stdout/stderr and
# THROWS IT AWAY, keeping only the bare exit code
# (`completed.returncode`). The E2 refusal this CLI then emits
# (verify_slice_commit_completeness.py:1279-1298) is the generic,
# reason-less template "slice {slice_id} failed the feature-scoped
# contract gate (exit {contract_code})" -- it names the CONTRACT GATE, not
# the feature's absence from this repo.
# ===========================================================================


_FEATURE_WRONG_REPO = "fix-contract-gate-slice-scope-wrong-repo"


def _repo_with_slice_trailer_and_no_feature_footprint(repo: Path) -> None:
    """A real repo carrying ONE commit with a valid ``Slice-Id:`` trailer and
    NOTHING else -- no `.feature` files, no regression test files, no
    footprint whatsoever for any feature-id. The everyday mistake: `--repo
    .` pointed at a repository that has never heard of the feature-id the
    operator names.
    """
    _git_init(repo)
    (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
    _commit_with_trailer(repo, "slice-01", "chore: placeholder commit")


def test_feature_id_absent_from_repo_is_named_as_such(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The everyday mistake this fix exists for: `--repo` points at a
    repository that has never heard of the named `--feature-id` (no
    `.feature` files, no regression files, no footprint at all). The
    refusal must NAME that: this repository has no feature `<id>` -- WHAT
    is wrong (the feature-id), WHY (it resolves nowhere under this repo),
    and (implicitly) HOW to fix it -- point `--repo` at the repository that
    owns the feature.

    RED for the right reason today: `_run_contract_gate`
    (`verify_slice_commit_completeness.py:454-469`) captures the child E2
    gate's stdout/stderr and DISCARDS it, keeping only the bare exit code
    -- even though the child (`run_contract_gate._mode_feature_scoped`)
    already emits a self-explaining `zero-collected` reason naming the
    feature-id ("no .feature file resolves under feature id ..."). Today's
    E2 refusal never threads it through -- it says only "failed the
    feature-scoped contract gate (exit N)", testifying about the CONTRACT
    GATE, never about the feature never having existed in this repo.

    This exact misdirection void'd TWO independent examinations on
    2026-07-13: both examiners ran `--repo .` with a `--feature-id` that
    existed only in their throwaway fixture, chased the wrong culprit, and
    returned FAIL on a product that works.
    """
    repo = tmp_path / "repo"
    _repo_with_slice_trailer_and_no_feature_footprint(repo)
    feature_id = _FEATURE_WRONG_REPO + "-does-not-exist-here"

    exit_code, payload = _run_verify_slice_commit(repo, feature_id, capsys)

    assert exit_code != 0, (
        "a --feature-id absent from this repo must refuse, not verify -- "
        f"exit_code={exit_code!r} payload={payload!r}"
    )

    haystack = json.dumps(payload).lower()
    names_feature = feature_id.lower() in haystack
    names_absence = any(
        phrase in haystack
        for phrase in (
            "no .feature file resolves",
            "no such feature",
            "does not exist",
            "not found",
            "resolves under feature id",
            "owns no",
            "unknown feature",
        )
    )
    assert names_feature and names_absence, (
        "the refusal must NAME the real cause -- this repository has no "
        f"feature {feature_id!r} -- WHAT is wrong (the feature-id), WHY "
        "(it resolves nowhere under this repo). Today's refusal only says "
        "the contract gate 'failed' (exit N), naming neither the "
        "feature-id nor its absence from this repo -- an operator chasing "
        f"this message investigates the wrong thing. payload={payload!r}"
    )


@pytest.mark.negative_at
def test_feature_id_absent_from_repo_refusal_never_blames_an_unrelated_cause(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE AT (the durable one): the gate must NEVER refuse a
    wrong-`--repo` invocation by naming a cause unrelated to the real one.
    A refusal that points at the wrong culprit is WORSE than one that says
    nothing -- it costs the operator an investigation into their own
    innocent code. This exact misdirection void'd TWO independent
    examinations on 2026-07-13.

    Pin the durable invariant, not the message text: the refusal must not
    collapse into the generic, reason-less "failed the feature-scoped
    contract gate (exit N)" template -- that bare shape is
    indistinguishable from a dozen OTHER, genuinely unrelated E2 failure
    modes (a really-broken slice, an arch-invariant break, a collection
    failure), so a reader cannot tell "wrong repo" from "my code is
    broken" and is sent chasing a phantom in code that is actually fine.
    """
    repo = tmp_path / "repo"
    _repo_with_slice_trailer_and_no_feature_footprint(repo)
    feature_id = _FEATURE_WRONG_REPO + "-never-blames-unrelated-cause"

    exit_code, payload = _run_verify_slice_commit(repo, feature_id, capsys)
    assert exit_code != 0, f"sanity: expected a refusal -- payload={payload!r}"

    error = str(payload.get("error", ""))
    generic_unexplained_template = re.fullmatch(
        r"slice [\w-]+ failed the feature-scoped contract gate \(exit \d+\)",
        error,
    )
    assert generic_unexplained_template is None, (
        "the refusal must never collapse into the bare, reason-less "
        "template that names neither the feature-id nor why E2 actually "
        f"failed -- its stated cause must MATCH the actual cause (the "
        f"feature-id resolves to zero footprint in this repo). got "
        f"error={error!r} payload={payload!r}"
    )
