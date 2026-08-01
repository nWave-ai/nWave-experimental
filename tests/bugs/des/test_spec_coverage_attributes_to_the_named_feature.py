# @feature-fix-coverage-claim-names-a-feature
"""Regression: `des verify-spec-coverage` decides coverage on a global,
unqualified marker namespace -- ANY AT anywhere carrying `# covers: Rn` (or
the canonical `R-Sdd-dd` form) satisfies Rn for EVERY feature's checklist,
regardless of which feature that AT actually belongs to.

RCA (executed, not reasoned -- see the dispatching charter for the full
trace):

  * `src/des/cli/verify_spec_coverage.py:615` -- `covered |= ids_or_exit`
    unions per-file id-sets into one flat `set[str]`; the file's `path` is
    discarded, destroying provenance.
  * `src/des/cli/verify_spec_coverage.py:618` -- `req.req_id not in covered`
    is bare 1-tuple set membership -- the correct key is at minimum
    `(feature_id, req_id)`.
  * The canonical `R-Sdd-dd` id form does NOT fix this: it is a SLICE
    ordinal, not a feature name -- a foreign-tagged file carrying the exact
    canonical marker still satisfies a different feature's checklist.
  * `src/des/application/subagent_stop_service.py:121-247`
    (`spec_coverage_gate_stdout`) does NOT call `main()` -- it is a SECOND,
    already-drifted hand-rolled re-implementation of the SAME predicate
    (`covered |= ids_or_exit` at :210, `req.req_id not in covered` at :213),
    and it ALREADY swallows unparseable AT files (`continue` at :209) where
    locus 1 degrades LOUD. A faithful re-implementation of the buggy
    predicate already exists in this tree, so a value-only regression pin is
    insufficient by construction (team-lead constraint: "if a faithful
    re-implementation elsewhere would pass your AT, add the second axis").

Fix contract (three-set algebra, GDP-8 arity corollary):

    D = discover(at_dir)                          # what the operator scanned
    A = feature_tagged_test_files(repo, F)         # SSOT-attributed to F
        | feature_tag_files(repo, F)               # (Gherkin arm)
    S = D ∩ A                                      # coverage computed ONLY over S

  state                                              | verdict                | exit
  ----------------------------------------------------|-------------------------|-----
  no declared feature identity (checklist + no --feature-id) | SpecCoverageIndeterminate | 2
  A = ∅ (nothing on disk declares @feature-{F})       | SpecCoverageIndeterminate | 2
  S = ∅ but A ≠ ∅ (operator pointed at the wrong dir) | SpecCoverageWrongScope (NEW) | 2
  S ⊊ D (some scanned files are not this feature's)   | normal verdict + reports the ignored-file count | 0/1
  S ≠ ∅, every row covered                            | SpecCoverageVerified    | 0
  S ≠ ∅, ≥1 row uncovered                              | SpecCoverageRefused     | 1

This module authors the TEST only -- no production code here. Every scenario
below is written against the CONTRACT above; on today's (unfixed) code every
negative scenario observes the wrong verdict with a real, semantic
AssertionError -- never an import/collection error.

Scenario index (AXIS -> what it pins):
  AXIS 1 (behaviour, asserted at BOTH loci where the assertion shape allows):
    1/2  the deletion test, inverted (CLI / application)          -- sharpest proof
    3/4  foreign attribution refused (CLI / application)
    5/6  true positive preserved -- non-vacuity control (CLI / application)
    7    S ⊊ D visibility: ignored-file count reported (CLI)
    8    no-declared-identity is INDETERMINATE (CLI)
    9    A=∅ is INDETERMINATE, distinct fixture from #8 (CLI)
    10   wrong-scope: S=∅, A≠∅ (CLI)
    11/12 prose-decoy negative: line-anchored declaration only (CLI / application)
    13   canonical R-Sdd-dd form does not bypass attribution (CLI)
  AXIS 2 (architecture -- catches a faithful re-implementation, not just a value):
    14   neither locus hand-rolls its own `covered |= ...` set-union
    15   neither locus hand-rolls its own `req.req_id not in covered` predicate
    16   both loci resolve attribution through the feature_at_files SSOT
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from des.application.subagent_stop_service import spec_coverage_gate_stdout
from des.cli.verify_spec_coverage import main


# tests/bugs/des/<this file> -> parents[3] = repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]
_CLI_LOCUS = REPO_ROOT / "src" / "des" / "cli" / "verify_spec_coverage.py"
_APP_LOCUS = REPO_ROOT / "src" / "des" / "application" / "subagent_stop_service.py"


# ---------------------------------------------------------------------------
# Fixture helpers.
# ---------------------------------------------------------------------------


def _checklist_declared(path: Path, feature_id: str, rows: str) -> Path:
    """A checklist that declares its identity with a LINE-ANCHORED
    `@feature-{id}` tag, on its own line, inside the head window."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Requirement Checklist — {feature_id}\n\n@feature-{feature_id}\n\n{rows}",
        encoding="utf-8",
    )
    return path


def _checklist_undeclared(path: Path, rows: str) -> Path:
    """A checklist that declares NO feature identity at all."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Requirement Checklist — untagged\n\n{rows}", encoding="utf-8")
    return path


def _at_file(
    directory: Path,
    filename: str,
    feature_id: str,
    *covers: str,
    use_decorator: bool = False,
) -> Path:
    """A pytest-collectible AT file head-tagged `@feature-{feature_id}`,
    covering each id in *covers* -- via a body comment (default, the P3.2
    convention) or a `@pytest.mark.covers(...)` decorator."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    test_name = filename.removesuffix(".py").replace("-", "_")
    if use_decorator:
        assert covers, "decorator form needs >=1 covered id"
        ids = ", ".join(f'"{c}"' for c in covers)
        body = (
            f"# @feature-{feature_id}\n"
            "import pytest\n\n\n"
            f"@pytest.mark.covers({ids})\n"
            f"def test_{test_name}():\n"
            "    assert True\n"
        )
    else:
        comment_lines = "\n".join(f"    # covers: {c}" for c in covers) or "    pass"
        body = (
            f"# @feature-{feature_id}\n"
            f"def test_{test_name}():\n"
            f"{comment_lines}\n"
            "    assert True\n"
        )
    path.write_text(body, encoding="utf-8")
    return path


def _run_cli(
    capsys: pytest.CaptureFixture[str],
    checklist: Path,
    at_dirs: list[Path],
    repo: Path,
) -> tuple[int, dict | None]:
    argv: list[str] = ["--checklist", str(checklist)]
    for at_dir in at_dirs:
        argv += ["--at-dir", str(at_dir)]
    argv += ["--repo", str(repo)]
    exit_code = main(argv)
    event: dict | None = None
    for line in capsys.readouterr().out.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            event = json.loads(stripped)
            break
    return exit_code, event


def _ignored_count(event: dict) -> object:
    """Best-effort read of "how many scanned-but-non-attributed files were
    ignored" under any plausible key name the fix might choose -- the
    CONTRACT is that some such count is reported, not a specific spelling."""
    for key in (
        "ignored_non_attributed_files",
        "non_attributed_files_ignored",
        "ignored_foreign_files",
        "files_ignored_out_of_scope",
        "ignored_count",
    ):
        if key in event:
            return event[key]
    return None


# ---------------------------------------------------------------------------
# AXIS 1 -- scenarios 1/2: the deletion test, inverted (the sharpest proof).
# ---------------------------------------------------------------------------


def test_deletion_of_the_features_own_at_moves_the_verdict_off_pass_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 1 (CLI). Deleting checkout-flow's OWN AT for R1 must move the
    verdict off PASS -- even though a FOREIGN file (@feature-other-feature)
    still covers R1 in the same --at-dir. On unfixed code this assertion is
    RED: the foreign file's contribution silently absorbs the deletion, the
    exit code stays 0, and this test fails with a real value mismatch."""
    repo = tmp_path / "s1"
    at_dir = repo / "at"
    checklist = _checklist_declared(
        repo / "checklist.md",
        "checkout-flow",
        "| R1 | booking produces a confirmation | functional |\n"
        "| R2 | payment identity is verified | security |\n",
    )
    own_r1 = _at_file(at_dir, "test_own_r1.py", "checkout-flow", "R1")
    _at_file(at_dir, "test_own_r2.py", "checkout-flow", "R2")
    _at_file(at_dir, "test_foreign_decoy.py", "other-feature", "R1")

    exit_before, event_before = _run_cli(capsys, checklist, [at_dir], repo)
    assert exit_before == 0
    assert event_before is not None
    assert event_before["event"] == "SpecCoverageVerified"

    own_r1.unlink()  # delete checkout-flow's OWN AT for R1

    exit_after, event_after = _run_cli(capsys, checklist, [at_dir], repo)

    assert exit_after != 0, (
        "THE DELETION TEST, INVERTED: deleting checkout-flow's own AT for R1 "
        "must move the verdict off PASS even though a FOREIGN file "
        "(@feature-other-feature) still covers R1 in the same --at-dir "
        f"corpus. got exit {exit_after} "
        f"({event_after.get('event') if event_after else 'no event emitted'})"
    )
    assert event_after is not None
    assert exit_after == 1
    assert event_after["event"] == "SpecCoverageRefused"
    uncovered_ids = {row["id"] for row in event_after["uncovered"]}
    assert uncovered_ids == {"R1"}, (
        "R1 must be the ONLY uncovered row -- R2 stays covered by its own "
        f"attributed AT (test_own_r2.py); got {uncovered_ids!r}"
    )


def test_deletion_of_the_features_own_at_moves_the_verdict_off_pass_application(
    tmp_path: Path,
) -> None:
    """Scenario 2 (application locus). Same defect class pinned against
    `spec_coverage_gate_stdout` -- the ALREADY-DRIFTED faithful
    re-implementation the team-lead constraint warns about."""
    project_root = tmp_path
    feature_id = "checkout-flow-app"
    dist = project_root / "docs" / "feature" / feature_id / "distill"
    dist.mkdir(parents=True)
    (dist / "requirement-checklist.md").write_text(
        f"# Requirement Checklist — {feature_id}\n\n"
        f"@feature-{feature_id}\n\n"
        "| R1 | booking produces a confirmation | functional |\n"
        "| R2 | payment identity is verified | security |\n",
        encoding="utf-8",
    )
    tests_dir = project_root / "tests"
    own_r1 = _at_file(tests_dir, "test_own_r1.py", feature_id, "R1")
    _at_file(tests_dir, "test_own_r2.py", feature_id, "R2")
    _at_file(tests_dir, "test_foreign_decoy.py", "other-app-feature", "R1")

    code_before, raw_before = spec_coverage_gate_stdout(project_root, feature_id)
    verdict_before = json.loads(raw_before)
    assert code_before == 0
    assert verdict_before["verdict"] == "pass"

    own_r1.unlink()  # delete checkout-flow-app's OWN AT for R1

    code_after, raw_after = spec_coverage_gate_stdout(project_root, feature_id)
    verdict_after = json.loads(raw_after)

    assert code_after == 0  # advisory dispatch NEVER vetoes -- unaffected
    assert verdict_after["verdict"] != "pass", (
        "deleted checkout-flow-app's own AT for R1; a FOREIGN file tagged "
        "@feature-other-app-feature still covers R1 in the same tests/ "
        "corpus. Attribution must ignore the foreign file's contribution -- "
        f"deleting the feature's own AT must move the verdict off 'pass'. "
        f"got verdict={verdict_after!r}"
    )
    blob = json.dumps(verdict_after)
    assert "R1" in blob, (
        "R1 must be named as the now-uncovered requirement, not silently "
        f"absorbed by the foreign file's coverage; got {verdict_after!r}"
    )


# ---------------------------------------------------------------------------
# AXIS 1 -- scenarios 3/4: foreign attribution refused.
# ---------------------------------------------------------------------------


def test_foreign_tagged_at_does_not_cover_a_different_feature_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 3 (CLI). Checklist for 'alpha'; corpus contains ONLY a file
    head-tagged @feature-beta carrying 'covers: R1'. Must NOT report R1
    covered for alpha (A=∅ for alpha -> SpecCoverageIndeterminate)."""
    repo = tmp_path / "s3"
    at_dir = repo / "at"
    checklist = _checklist_declared(
        repo / "checklist.md", "alpha", "| R1 | alpha requirement | functional |\n"
    )
    _at_file(at_dir, "test_foreign.py", "beta", "R1")

    exit_code, event = _run_cli(capsys, checklist, [at_dir], repo)

    assert exit_code == 2, (
        "only a @feature-beta-tagged AT exists, carrying '# covers: R1' -- "
        "it must not be attributed to alpha (A=∅ for alpha). got exit "
        f"{exit_code} ({event.get('event') if event else 'no event emitted'})"
    )
    assert event is not None
    assert event["event"] == "SpecCoverageIndeterminate"


def test_foreign_tagged_at_does_not_cover_a_different_feature_application(
    tmp_path: Path,
) -> None:
    """Scenario 4 (application locus) -- same shape as scenario 3."""
    project_root = tmp_path
    feature_id = "alpha-app"
    dist = project_root / "docs" / "feature" / feature_id / "distill"
    dist.mkdir(parents=True)
    (dist / "requirement-checklist.md").write_text(
        f"# Requirement Checklist — {feature_id}\n\n"
        f"@feature-{feature_id}\n\n"
        "| R1 | alpha requirement | functional |\n",
        encoding="utf-8",
    )
    tests_dir = project_root / "tests"
    _at_file(tests_dir, "test_foreign.py", "beta-app", "R1")

    code, raw = spec_coverage_gate_stdout(project_root, feature_id)
    verdict = json.loads(raw)

    assert code == 0
    assert verdict["verdict"] != "pass", (
        "only a @feature-beta-app-tagged AT exists in the corpus, carrying "
        f"'# covers: R1' -- it must not be attributed to alpha-app. got "
        f"verdict={verdict!r}"
    )


# ---------------------------------------------------------------------------
# AXIS 1 -- scenarios 5/6: true positive preserved (non-vacuity control).
#
# Pairs against EVERY negative above and below: a gate that refuses
# everything would satisfy every negative scenario in this file too. These
# controls prove the fix does not become a blanket refusal.
# ---------------------------------------------------------------------------


def test_genuine_own_attribution_still_passes_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 5 (CLI) -- NON-VACUITY CONTROL."""
    repo = tmp_path / "s5"
    at_dir = repo / "at"
    checklist = _checklist_declared(
        repo / "checklist.md",
        "gamma",
        "| R1 | gamma requirement one | functional |\n"
        "| R2 | gamma requirement two | security |\n",
    )
    _at_file(at_dir, "test_own.py", "gamma", "R1", "R2")

    exit_code, event = _run_cli(capsys, checklist, [at_dir], repo)

    assert exit_code == 0, (
        "a genuinely own-attributed, fully-covering AT must still PASS -- "
        f"the fix must not become a blanket refusal. got exit {exit_code} "
        f"({event.get('event') if event else 'no event emitted'})"
    )
    assert event is not None
    assert event["event"] == "SpecCoverageVerified"


def test_genuine_own_attribution_still_passes_application(tmp_path: Path) -> None:
    """Scenario 6 (application locus) -- NON-VACUITY CONTROL."""
    project_root = tmp_path
    feature_id = "gamma-app"
    dist = project_root / "docs" / "feature" / feature_id / "distill"
    dist.mkdir(parents=True)
    (dist / "requirement-checklist.md").write_text(
        f"# Requirement Checklist — {feature_id}\n\n"
        f"@feature-{feature_id}\n\n"
        "| R1 | gamma requirement one | functional |\n"
        "| R2 | gamma requirement two | security |\n",
        encoding="utf-8",
    )
    tests_dir = project_root / "tests"
    _at_file(tests_dir, "test_own.py", feature_id, "R1", "R2")

    code, raw = spec_coverage_gate_stdout(project_root, feature_id)
    verdict = json.loads(raw)

    assert code == 0
    assert verdict["verdict"] == "pass", (
        "a genuinely own-attributed, fully-covering AT must still PASS -- "
        f"the fix must not become a blanket refusal. got verdict={verdict!r}"
    )


# ---------------------------------------------------------------------------
# AXIS 1 -- scenario 7: S ⊊ D visibility.
# ---------------------------------------------------------------------------


def test_non_attributed_files_in_at_dir_are_reported_ignored_not_silently_dropped_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 7 (CLI). --at-dir scans 2 files but only 1 is attributed to
    'delta'; the coverage verdict is unaffected (already true today -- the
    foreign file covers nothing) but the fix must ALSO report the count of
    non-attributed files it ignored (S ⊊ D). Today's code reports no such
    count -- this is the semantic gap this scenario pins."""
    repo = tmp_path / "s7"
    at_dir = repo / "at"
    checklist = _checklist_declared(
        repo / "checklist.md", "delta", "| R1 | delta requirement | functional |\n"
    )
    _at_file(at_dir, "test_own.py", "delta", "R1")
    _at_file(at_dir, "test_foreign.py", "zeta")

    exit_code, event = _run_cli(capsys, checklist, [at_dir], repo)

    assert exit_code == 0
    assert event is not None
    ignored = _ignored_count(event)
    assert ignored == 1, (
        "--at-dir scanned 2 files but only 1 (test_own.py) is attributed to "
        "'delta'; the verdict must report the count of non-attributed files "
        f"it ignored (S ⊊ D). got no such count in the event ({event!r})"
    )


# ---------------------------------------------------------------------------
# AXIS 1 -- scenarios 8/9/10: the three arity states, each individually
# observable, none collapsing into each other or into PASS.
# ---------------------------------------------------------------------------


def test_no_declared_feature_identity_is_indeterminate_not_a_silent_pass_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 8 (CLI). Checklist declares NO feature identity at all (no
    --feature-id equivalent either). Regardless of whatever coverage happens
    to be found in --at-dir, the verdict must be INDETERMINATE (exit 2),
    never a computed pass/refuse -- there is no F to attribute against."""
    repo = tmp_path / "s8"
    at_dir = repo / "at"
    checklist = _checklist_undeclared(
        repo / "checklist.md", "| R1 | some requirement | functional |\n"
    )
    _at_file(at_dir, "test_x.py", "whatever-feature", "R1")

    exit_code, event = _run_cli(capsys, checklist, [at_dir], repo)

    assert exit_code == 2, (
        "the checklist declares no feature identity and no --feature-id was "
        "passed -- the gate has no F to attribute against and must degrade "
        f"INDETERMINATE regardless of any coverage found. got exit "
        f"{exit_code} ({event.get('event') if event else 'no event emitted'})"
    )


def test_empty_attribution_is_indeterminate_distinct_from_no_declared_identity_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 9 (CLI). Checklist DOES declare 'eta', but ZERO files on
    disk declare @feature-eta anywhere -- a DISTINCT state from scenario 8
    (identity is declared, attribution is simply empty)."""
    repo = tmp_path / "s9"
    at_dir = repo / "at"
    checklist = _checklist_declared(
        repo / "checklist.md", "eta", "| R1 | eta requirement | functional |\n"
    )
    _at_file(at_dir, "test_x.py", "theta", "R1")  # zero eta-tagged files exist

    exit_code, event = _run_cli(capsys, checklist, [at_dir], repo)

    assert exit_code == 2, (
        "the checklist declares 'eta' but no file anywhere under --repo "
        "declares @feature-eta -- A=∅ must degrade INDETERMINATE. got exit "
        f"{exit_code} ({event.get('event') if event else 'no event emitted'})"
    )


def test_wrong_scope_when_attributed_at_exists_outside_at_dir_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 10 (CLI). 'iota' has a genuinely attributed AT on disk, but
    it lives OUTSIDE the scanned --at-dir -- the operator pointed at the
    wrong corpus. S = D∩A is empty though A is non-empty: this is the
    WRONG-SCOPE state (contract table row 3), distinct from a genuine
    refusal (which requires S non-empty with an uncovered row)."""
    repo = tmp_path / "s10"
    at_dir = repo / "at"
    elsewhere = repo / "elsewhere"
    checklist = _checklist_declared(
        repo / "checklist.md", "iota", "| R1 | iota requirement | functional |\n"
    )
    _at_file(at_dir, "test_foreign.py", "kappa")  # inside --at-dir, wrong feature
    _at_file(elsewhere, "test_iota_own.py", "iota", "R1")  # outside --at-dir

    exit_code, event = _run_cli(capsys, checklist, [at_dir], repo)

    assert exit_code == 2, (
        f"iota's own attributed AT exists under {elsewhere}, outside the "
        f"scanned --at-dir {at_dir}; S=D∩A is empty though A is non-empty -- "
        "this is the WRONG-SCOPE state, not a genuine refusal. got exit "
        f"{exit_code} ({event.get('event') if event else 'no event emitted'})"
    )


# ---------------------------------------------------------------------------
# AXIS 1 -- scenarios 11/12: prose-decoy negative (line-anchored, not
# substring). Traps the exact false-positive shape already present in-tree:
# docs/feature/carpaccio-pytest-at-comment-tag-binding/distill/
# requirement-checklist.md:9 mentions '@feature-' inside R1's prose.
# ---------------------------------------------------------------------------


def test_prose_mention_of_feature_tag_does_not_self_declare_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 11 (CLI). '@feature-decoy-target' appears only inside R1's
    requirement PROSE (in backticks, within the head window), never on its
    own dedicated line. A bare substring match would let the checklist
    self-declare from prose -- the same defect class
    feature_at_files.is_pytest_collectible was written to prevent. The AT
    genuinely exists and genuinely covers R1, so if the checklist WERE
    properly declared this would PASS; it must not, because it never
    declared."""
    repo = tmp_path / "s11"
    at_dir = repo / "at"
    checklist = repo / "checklist.md"
    checklist.parent.mkdir(parents=True, exist_ok=True)
    checklist.write_text(
        "# Requirement Checklist — decoy-target\n\n"
        "| R1 | a file whose head carries a `@feature-decoy-target` "
        "comment-tag is bound | functional |\n",
        encoding="utf-8",
    )
    _at_file(at_dir, "test_own.py", "decoy-target", "R1")

    exit_code, event = _run_cli(capsys, checklist, [at_dir], repo)

    assert exit_code == 2, (
        "'@feature-decoy-target' appears only inside R1's requirement "
        "prose, never on its own dedicated line -- a bare substring match "
        "would wrongly self-declare identity from prose. got exit "
        f"{exit_code} ({event.get('event') if event else 'no event emitted'})"
    )


def test_prose_mention_of_feature_tag_does_not_self_declare_application(
    tmp_path: Path,
) -> None:
    """Scenario 12 (application locus) -- same trap as scenario 11."""
    project_root = tmp_path
    feature_id = "decoy-target-app"
    dist = project_root / "docs" / "feature" / feature_id / "distill"
    dist.mkdir(parents=True)
    (dist / "requirement-checklist.md").write_text(
        "# Requirement Checklist — decoy-target-app\n\n"
        "| R1 | a file whose head carries a `@feature-decoy-target-app` "
        "comment-tag is bound | functional |\n",
        encoding="utf-8",
    )
    tests_dir = project_root / "tests"
    _at_file(tests_dir, "test_own.py", feature_id, "R1")

    code, raw = spec_coverage_gate_stdout(project_root, feature_id)
    verdict = json.loads(raw)

    assert code == 0
    assert verdict["verdict"] != "pass", (
        "'@feature-decoy-target-app' appears only inside R1's requirement "
        "prose, never on its own dedicated line -- a bare substring match "
        f"would wrongly self-declare identity from prose. got verdict="
        f"{verdict!r}"
    )


# ---------------------------------------------------------------------------
# AXIS 1 -- scenario 13: canonical R-Sdd-dd form does not bypass attribution.
# ---------------------------------------------------------------------------


def test_canonical_hierarchical_id_does_not_bypass_attribution_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Scenario 13 (CLI). A checklist for 'lambda-feat' with a canonical
    R-S01-03 row; the ONLY carrier of that exact marker is a file tagged
    @feature-mu-feat. R-Sdd-dd is a SLICE ordinal, not a feature namespace
    -- the canonical form must be refused for lambda-feat too."""
    repo = tmp_path / "s13"
    at_dir = repo / "at"
    checklist = _checklist_declared(
        repo / "checklist.md",
        "lambda-feat",
        "| R-S01-03 | lambda requirement | functional |\n",
    )
    _at_file(at_dir, "test_foreign.py", "mu-feat", "R-S01-03", use_decorator=True)

    exit_code, event = _run_cli(capsys, checklist, [at_dir], repo)

    assert exit_code == 2, (
        "the ONLY carrier of the exact canonical marker "
        '@pytest.mark.covers("R-S01-03") is tagged @feature-mu-feat, not '
        "@feature-lambda-feat -- the canonical id form does not namespace "
        f"the marker to a feature. got exit {exit_code} "
        f"({event.get('event') if event else 'no event emitted'})"
    )


# ---------------------------------------------------------------------------
# AXIS 2 -- architecture. A faithful re-implementation of the buggy
# predicate would pass EVERY value assertion above if it independently
# re-derives the same globally-unqualified aggregation -- locus 2 already
# does exactly that. These tests pin the STRUCTURE: one shared decision
# core, attribution resolved through the existing feature_at_files SSOT,
# neither entry-point module hand-rolling its own aggregation/membership
# predicate.
#
# Precedent this guards against (already in-tree): src/des/cli/
# carpaccio_format.py hand-joins a telemetry path instead of going through
# its own module's SSOT -- the correct VALUE reached by the wrong ROUTE.
# ---------------------------------------------------------------------------


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _bitor_aggregation_lines(
    tree: ast.Module, target_name: str = "covered"
) -> list[int]:
    """Every ``<target_name> |= ...`` AugAssign line -- a hand-rolled
    set-union aggregation, the exact shape both loci independently carry
    today (verify_spec_coverage.py:615, subagent_stop_service.py:210)."""
    lines = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AugAssign)
            and isinstance(node.op, ast.BitOr)
            and isinstance(node.target, ast.Name)
            and node.target.id == target_name
        ):
            lines.append(node.lineno)
    return lines


def _not_in_membership_lines(
    tree: ast.Module, attr_name: str = "req_id", set_name: str = "covered"
) -> list[int]:
    """Every ``<obj>.<attr_name> not in <set_name>`` Compare -- the
    hand-rolled 1-tuple coverage-membership predicate both loci
    independently carry today (verify_spec_coverage.py:618,
    subagent_stop_service.py:213)."""
    lines = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.NotIn):
            continue
        left = node.left
        comparator = node.comparators[0]
        if (
            isinstance(left, ast.Attribute)
            and left.attr == attr_name
            and isinstance(comparator, ast.Name)
            and comparator.id == set_name
        ):
            lines.append(node.lineno)
    return lines


def _imports_feature_at_files(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and "feature_at_files" in node.module
        ):
            return True
        if isinstance(node, ast.Import) and any(
            "feature_at_files" in alias.name for alias in node.names
        ):
            return True
    return False


def test_neither_locus_hand_rolls_its_own_coverage_set_union() -> None:
    """Scenario 14. A faithful re-implementation elsewhere would pass every
    AXIS-1 value assertion above if it independently re-derives the SAME
    buggy union. Locus 2 does exactly that TODAY (`covered |= ids_or_exit`,
    subagent_stop_service.py:210) -- independently of locus 1's OWN copy
    (verify_spec_coverage.py:615). The fix must delegate this aggregation to
    ONE shared decision core; neither entry-point module should carry its
    own `covered |= ...` AugAssign."""
    cli_lines = _bitor_aggregation_lines(_parse(_CLI_LOCUS))
    app_lines = _bitor_aggregation_lines(_parse(_APP_LOCUS))

    assert not cli_lines, (
        f"WHAT: {_CLI_LOCUS} hand-rolls its own 'covered |= ...' "
        f"aggregation at line(s) {cli_lines}. WHY: this is the exact shape "
        "that drifted independently in locus 2 -- two hand-rolled copies of "
        "the same predicate is how the two loci already disagree. HOW: "
        "extract the aggregation into one shared decision-core function "
        "both loci call."
    )
    assert not app_lines, (
        f"WHAT: {_APP_LOCUS} hand-rolls its own 'covered |= ...' "
        f"aggregation at line(s) {app_lines} (spec_coverage_gate_stdout), "
        "independently of verify_spec_coverage.py's own copy. WHY: this is "
        "the ALREADY-DRIFTED faithful re-implementation the team lead's "
        "constraint warns against -- locus 2 already swallows unparseable "
        "AT files where locus 1 degrades LOUD. HOW: delegate to the same "
        "shared decision core locus 1 uses."
    )


def test_neither_locus_hand_rolls_its_own_uncovered_membership_predicate() -> None:
    """Scenario 15. Mirrors the aggregation check for the membership
    predicate: `req.req_id not in covered` -- present identically in both
    verify_spec_coverage.py:618 and subagent_stop_service.py:213 today. A
    1-tuple set-membership test is exactly the bug (no feature identity in
    the key) -- pinning its ABSENCE from both entry-point modules forces
    the fix through a shared, feature-scoped decision core rather than a
    second local patch."""
    cli_lines = _not_in_membership_lines(_parse(_CLI_LOCUS))
    app_lines = _not_in_membership_lines(_parse(_APP_LOCUS))

    assert not cli_lines, (
        f"WHAT: {_CLI_LOCUS} tests coverage via bare 'req.req_id not in "
        f"covered' at line(s) {cli_lines} -- a 1-tuple membership test with "
        "no feature identity in the key. WHY/HOW: see the shared "
        "decision-core requirement in this module's docstring."
    )
    assert not app_lines, (
        f"WHAT: {_APP_LOCUS} tests coverage via bare 'req.req_id not in "
        f"covered' at line(s) {app_lines} -- the SAME bare predicate, "
        "independently re-implemented. WHY/HOW: see the shared "
        "decision-core requirement in this module's docstring."
    )


def test_both_loci_resolve_attribution_through_the_feature_at_files_ssot() -> None:
    """Scenario 16. Attribution (the `A` set) must be resolved by REUSING
    `des.application.feature_at_files` (`feature_tagged_test_files` /
    `feature_tag_files`) -- the existing 11-call-site SSOT for the
    `@feature-{id}` head-tag idiom -- never a private re-scan. Neither
    locus imports it today."""
    cli_tree = _parse(_CLI_LOCUS)
    app_tree = _parse(_APP_LOCUS)

    assert _imports_feature_at_files(cli_tree), (
        f"WHAT: {_CLI_LOCUS} does not import "
        "des.application.feature_at_files. WHY: attribution (the A set) "
        "must be resolved through that SSOT, never a private "
        "'@feature-{id}' re-scan. HOW: import feature_tagged_test_files / "
        "feature_tag_files from des.application.feature_at_files and "
        "resolve A through it."
    )
    assert _imports_feature_at_files(app_tree), (
        f"WHAT: {_APP_LOCUS} does not import "
        "des.application.feature_at_files. WHY/HOW: same as above -- "
        "locus 2 must resolve attribution through the SAME SSOT locus 1 "
        "uses, not a second private implementation."
    )


if __name__ == "__main__":
    import sys

    raise SystemExit(pytest.main([__file__, "-v", *sys.argv[1:]]))
