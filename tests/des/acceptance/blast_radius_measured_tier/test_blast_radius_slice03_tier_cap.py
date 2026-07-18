"""Acceptance tests -- `des commit-slice --tier {S,M,L}` (DISTILL, slice-03).

Feature-delta: docs/feature/blast-radius-measured-tier/feature-delta.md
  ([REF] Slice Plan slice-03 row, [REF] Architecture & Contract Tests --
  `des commit-slice --tier {S,M,L}` -- the tier-cap consumer).

Slice-03 value (Slice Plan): `des commit-slice --tier {S,M,L}` refuses --
BEFORE any commit lands, exit 1, `BlastRadiusTierExceeded` naming what/why/how
-- when the measured blast radius of the declared `--path` scope exceeds the
declared tier; omitting `--tier` is byte-identical to today.

TEST-PYRAMID CONSTRAINT (Ale-ratified 2026-07-18, F-V5): the feature's ONE
`@walking_skeleton` subprocess-E2E is ALREADY SPENT on slice-01. This module
authors ZERO new subprocess/E2E scenarios -- every scenario drives the REAL
`des.cli.commit_slice.main(argv)` composition-root driving port IN-PROCESS,
against a hermetic tmp git fixture repo built by `tests.des.integration.
test_commit_slice._init_repo` (Test Reuse & Consolidation Analysis: EXTEND,
no new fixture-repo builder).

MINIMAL-BOOKKEEPING PATH (answering the dispatch's "watch out" -- how a bare
fixture reaches the pre-flight tier check at all): `commit-slice` normally
requires project bookkeeping (an AT-completion ledger, an examine verdict) to
reach its commit path. Every scenario below uses the SAME minimal-bookkeeping
shape `test_commit_slice.py`'s OWN happy-path tests already establish and
prove reaches a genuine `SliceCommitted` (see e.g.
`test_commit_slice_verifies_clean_with_new_untracked_at`): `--at-kind
pytest-regression --regression-test-file <a real, passing, newly-added test
file>`, NO charter directory (so the examine-verdict gate stays UNARMED, a
no-op), and NO pre-existing AT-completion ledger (so the E1/E2 pre-flight
gate the tier cap shares its chokepoint with clears on an empty ledger, the
SAME way it already does for every pre-existing `commit-slice` caller that
never set one up). This is not a fabricated shortcut: it is the SAME fixture
shape the shipped test suite already uses to prove a REAL commit lands.

Contract under test (DOES NOT EXIST YET at slice-02 HEAD -- active-RED by
design): `src/des/cli/commit_slice.py::main(argv)` extended with an OPTIONAL
`--tier {S,M,L}` flag. Today `--tier` is an UNRECOGNIZED argument, so every
scenario below that passes it observes argparse's OWN "unrecognized
arguments" `SystemExit(2)` -- folded by `_invoke_commit_slice` into the SAME
`(exit_code, payload, stderr)` shape a post-implementation call produces
(mirrors `_run_commit_slice_with_at_kind` in
`tests/bugs/des/test_commit_slice_forwards_at_kind_to_verify_slice_commit.py`),
so every assertion below is a genuine semantic comparison against the
slice-03 contract, never a crash masquerading as a failing test.

===========================================================================
DISTILL-PINNED CONTRACT ADDITIONS (unspecified by the feature-delta -- DISTILL's
own design decisions, since `--tier` does not exist yet to reverse-engineer;
DELIVER matches these, or raises the discrepancy back to DISTILL/DESIGN if it
disagrees):
===========================================================================

DT1 -- the `BlastRadiusTierExceeded` refusal payload carries STRUCTURED
      `declared_tier` / `measured_tier` string keys (each one of "S"/"M"/"L"),
      IN ADDITION TO the free-text `what`/`why`/`how` prose the feature-delta
      names. A single-letter substring scan of prose ("S" or "M" or "L"
      appearing somewhere in a sentence) is not a discriminating signal --
      the letters are common English substrings -- so this module asserts
      against the STRUCTURED fields, mirroring the module's own established
      convention elsewhere (`ExamineVerdictMissing` carries structured
      `feature_id`/`slice_id` alongside its prose).
DT2 -- the tier-cap measures the declared scope EXACTLY as
      `des blast-radius --paths <scope>` would (the SAME `measure_blast_radius`
      orchestration, the SAME closed S/M/L decision table shipped in
      slice-02) -- it does not invent a parallel, simplified escalation rule.
      This is what makes obligation (f) (indeterminate-never-silently-passes)
      a CONSEQUENCE of reuse rather than a new mechanism: an unparseable
      touched file already degrades `consumer_counts` to `null`, which
      `classify_tier` already escalates to L (GDP-6, shipped, unchanged).
DT3 -- an INVALID `--tier` value is refused BEFORE any git mutation (exit 2)
      and is distinguishable from today's "the flag does not exist at all"
      failure: the refusal names the offending value AND the word
      "unrecognized" (argparse's own wording for a wholly-unknown flag) is
      ABSENT from the combined output -- a recognized flag rejecting a bad
      VALUE speaks differently than an unrecognized flag.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.des.integration.test_commit_slice import _git, _init_repo


_FEATURE_ID = "blast-radius-tier-cap"

# Canonical default thresholds (feature-delta "Canonical default thresholds"
# table, unchanged since slice-01/02) -- the fixture scopes below are sized
# relative to these.
SMALL_MAX_LINES = 10


def _message(subject: str) -> str:
    return f"test(slice): {subject}"


def _invoke_commit_slice(argv: list[str], capsys) -> tuple[int, dict[str, object], str]:
    """Drive the REAL `des commit-slice` CLI (`main()`) in-process.

    Folds an argparse-level `SystemExit` into the SAME `(exit_code, payload,
    stderr)` shape a post-implementation call produces, so a raw `SystemExit`
    never escapes a test unexplained (P3/P4 active-RED discipline).

    ALSO folds an UNCAUGHT non-`SystemExit` exception escaping `main()` --
    which is itself a contract VIOLATION, never a legitimate outcome: every
    `des` gate surface owes a structured refusal, so an escaping exception is
    the defect under test (blocker D3), not a test-harness accident. Folding
    it (exit 70, the conventional software-error code -- distinct from every
    code `main()` itself returns, so it can never be mistaken for a real
    verdict) renders the traceback into `stderr` so the asserting test fails
    SEMANTICALLY on "a structured refusal was owed and a crash arrived
    instead", rather than erroring out with a bare traceback that proves the
    same thing far less legibly. Nothing is weakened: a test that wants a
    clean run still asserts `exit_code == 0`, which 70 fails.

    Returns the parsed LAST single-line JSON stdout payload (or `{}` when
    nothing was ever emitted) plus the captured stderr.
    """
    import traceback

    from des.cli.commit_slice import main as commit_slice_main

    folded_traceback = ""
    try:
        exit_code = commit_slice_main(argv)
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 2
    except Exception:
        # An escaping exception IS the defect under test; re-raising would
        # surface it as a bare error instead of the semantic assertion
        # failure it deserves.
        exit_code = 70
        folded_traceback = traceback.format_exc()
    captured = capsys.readouterr()
    json_lines = [
        line for line in captured.out.splitlines() if line.strip().startswith("{")
    ]
    payload: dict[str, object] = json.loads(json_lines[-1]) if json_lines else {}
    return exit_code, payload, captured.err + folded_traceback


def _commit_slice_argv(
    repo: Path,
    paths: list[str],
    regression_test_file: str,
    subject: str,
    tier: str | None = None,
    use_all: bool = False,
) -> list[str]:
    argv = [
        "--repo",
        str(repo),
        "--feature-id",
        _FEATURE_ID,
        "--slice-id",
        "slice-01",
        "--at-kind",
        "pytest-regression",
        "--regression-test-file",
        regression_test_file,
        "--message",
        _message(subject),
    ]
    if use_all:
        argv.append("--all")
    else:
        for path in paths:
            argv.extend(["--path", path])
    if tier is not None:
        argv.extend(["--tier", tier])
    return argv


# --- fixture scope builders (each returns (declared --path list, the
# regression test file among them)) ----------------------------------------


def _scope_small(repo: Path) -> tuple[list[str], str]:
    """A genuinely S-measured scope: 1 file, well under 10 lines, no
    boundary crossing, zero external callers."""
    rel = "tests/unit/test_slice_tier_small.py"
    (repo / rel).write_text(
        "def test_slice_tier_small():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )
    return [rel], rel


def _scope_lines_exceed(repo: Path) -> tuple[list[str], str]:
    """A 1-file scope whose LINE COUNT alone exceeds `small_max_lines` (10)
    -- measures M (files/boundary/consumers all otherwise small)."""
    rel = "tests/unit/test_slice_tier_lines.py"
    body = "\n".join(f"    value_{i} = {i}" for i in range(SMALL_MAX_LINES + 2))
    (repo / rel).write_text(
        f"def test_slice_tier_lines():\n{body}\n    assert value_0 == 0\n",
        encoding="utf-8",
    )
    return [rel], rel


def _scope_boundary(repo: Path) -> tuple[list[str], str]:
    """A boundary-glob scope (`**/ports/**`) -- ALWAYS L regardless of size."""
    boundary_rel = "src/ports/thing.py"
    boundary_path = repo / boundary_rel
    boundary_path.parent.mkdir(parents=True, exist_ok=True)
    boundary_path.write_text("x = 1\n", encoding="utf-8")
    test_rel = "tests/unit/test_slice_tier_boundary.py"
    (repo / test_rel).write_text(
        "def test_slice_tier_boundary():\n    assert True\n", encoding="utf-8"
    )
    return [boundary_rel, test_rel], test_rel


def _scope_indeterminate(repo: Path) -> tuple[list[str], str]:
    """A scope carrying an UNPARSEABLE `.py` file (genuine syntax error) --
    its `consumer_counts` entry degrades to `null`, which `classify_tier`
    already escalates to L (DT2) -- the honest-INDETERMINATE-is-never-a-
    silent-pass witness."""
    broken_rel = "broken.py"
    (repo / broken_rel).write_text("def broken(:\n    pass\n", encoding="utf-8")
    test_rel = "tests/unit/test_slice_tier_indeterminate.py"
    (repo / test_rel).write_text(
        "def test_slice_tier_indeterminate():\n    assert True\n", encoding="utf-8"
    )
    return [broken_rel, test_rel], test_rel


def _scope_medium_consumers(repo: Path) -> tuple[list[str], str]:
    """A genuinely M-measured scope: 2 files, comfortably under 10 lines
    combined, no boundary crossing, but a touched symbol with 6 external
    callers -- strictly between `small_max_consumers` (3) and
    `large_min_consumers` (10), i.e. squarely inside the M band (mirrors
    slice-02's `_seed_producer_with_callers` pattern: the callers are
    committed separately, only the producer + the regression test file are
    the DECLARED scope, so `files`/`lines_changed` stay small while
    `consumer_counts` is a REAL cross-repo measurement)."""
    producer_rel = "producer_mid.py"
    producer_path = repo / producer_rel
    producer_path.write_text("def helper_mid():\n    return 1\n", encoding="utf-8")
    for i in range(6):
        (repo / f"caller_mid_{i}.py").write_text(
            f"from producer_mid import helper_mid\n\n\n"
            f"def use_mid_{i}():\n    return helper_mid()\n",
            encoding="utf-8",
        )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed medium-consumer producer + callers")
    with producer_path.open("a", encoding="utf-8") as handle:
        handle.write("# touched\n")
    test_rel = "tests/unit/test_slice_tier_medium.py"
    (repo / test_rel).write_text(
        "def test_slice_tier_medium():\n    assert True\n", encoding="utf-8"
    )
    return [producer_rel, test_rel], test_rel


# --- (a) declared S + genuinely S-measured scope: proceeds normally -------


def test_declared_tier_s_with_genuinely_small_scope_commits_normally(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: a

    A --tier S declaration over a scope that GENUINELY measures S (1 file, a
    handful of lines, no boundary crossing, zero consumers) commits
    normally -- the cap never blocks honest small work.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    paths, regression_file = _scope_small(repo)

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo, paths, regression_file, "add small tier-s coverage", tier="S"
        ),
        capsys,
    )

    assert exit_code == 0, f"expected a clean commit, got payload={payload!r}"
    assert payload.get("event") == "SliceCommitted"


# --- (b)+(c) declared S refused when measured M or L; refusal self-explains --


_ABOVE_SMALL_CASES = [
    pytest.param("lines_exceed", _scope_lines_exceed, "M", "line", id="lines_exceed"),
    pytest.param("boundary", _scope_boundary, "L", "boundary", id="boundary"),
]


@pytest.mark.parametrize(
    "scope_kind,scope_builder,expected_measured_tier,expected_why_substring",
    _ABOVE_SMALL_CASES,
)
def test_declared_tier_s_refused_when_measured_scope_exceeds_it(
    tmp_path: Path,
    capsys,
    scope_kind: str,
    scope_builder,
    expected_measured_tier: str,
    expected_why_substring: str,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b, c

    A --tier S declaration over a scope that measures M (lines alone) or L
    (a boundary crossing) is REFUSED before any commit lands (exit 1,
    BlastRadiusTierExceeded) -- nothing lands (HEAD unchanged, nothing left
    staged) -- and the refusal is self-explaining (GDP-3): it names the
    measured tier, the declared tier (DT1), the driving measure/reason, and
    a HOW that interpolates the REAL repo + the ACTUAL declared paths (never
    a placeholder) plus a concrete remediation.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    paths, regression_file = scope_builder(repo)

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo,
            paths,
            regression_file,
            f"add {scope_kind} scope declared too small",
            tier="S",
        ),
        capsys,
    )

    assert exit_code == 1, f"expected a refusal, got payload={payload!r}"
    assert payload.get("event") == "BlastRadiusTierExceeded"
    assert payload.get("declared_tier") == "S"
    assert payload.get("measured_tier") == expected_measured_tier

    # (b) nothing committed, nothing left half-staged.
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before, (
        "a refused tier-cap commit must land NOTHING -- HEAD must stay "
        "exactly where it was before the invocation"
    )
    staged = _git(repo, "diff", "--cached", "--name-only").strip()
    assert staged == "", (
        f"a refusal must leave the working tree UNSTAGED, not half-staged -- "
        f"found staged paths: {staged!r}"
    )

    # (c) self-explaining: non-empty what/why, HOW interpolates the REAL
    # repo + declared paths (never a placeholder) and names a remediation.
    what = str(payload.get("what", ""))
    why = str(payload.get("why", ""))
    how = str(payload.get("how", ""))
    assert what, "the WHAT must be non-empty"
    assert expected_why_substring in why.lower(), (
        f"the WHY must name the driving measure ({expected_why_substring!r}), "
        f"not a bare tier letter -- got why={why!r}"
    )
    assert "blast-radius" in how
    assert "--repo" in how
    assert str(repo) in how, (
        "the HOW must interpolate the REAL repo path, never a placeholder"
    )
    for path in paths:
        assert path in how, f"the HOW must interpolate the declared path {path!r}"
    assert any(
        word in how.lower() for word in ("split", "smaller", "--tier", "slice")
    ), (
        "the HOW must name a concrete remediation (accept the real tier or split the slice)"
    )


def test_declared_tier_m_refused_when_measured_scope_is_boundary_large(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b

    A --tier M declaration is ALSO refused once the measured scope is L (a
    boundary crossing) -- the cap is not merely a strict-S special case, it
    enforces the FULL S < M < L ordering at every declared level below the
    ceiling.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    paths, regression_file = _scope_boundary(repo)

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo, paths, regression_file, "add boundary scope declared m", tier="M"
        ),
        capsys,
    )

    assert exit_code == 1, f"expected a refusal, got payload={payload!r}"
    assert payload.get("event") == "BlastRadiusTierExceeded"
    assert payload.get("declared_tier") == "M"
    assert payload.get("measured_tier") == "L"
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before
    assert _git(repo, "diff", "--cached", "--name-only").strip() == ""


def test_declared_tier_m_with_genuinely_medium_scope_commits_normally(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b -- the M-M boundary (HIGH review finding): every OTHER tier
    boundary in this module is witnessed (S-S, S-M, S-L, M-L, L-M, L-L) EXCEPT
    a --tier M declaration over a scope that GENUINELY measures M -- without
    this witness a `>` vs `>=` inversion in the declared-vs-measured
    comparison could ship silently (a strict `>` comparison would also let
    this scope through, masking the bug the other boundary tests cannot see).
    A --tier M declaration over a scope that measures M (2 files, well under
    10 lines combined, no boundary crossing, a touched symbol with 6 callers
    -- strictly inside the M band) commits normally.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    paths, regression_file = _scope_medium_consumers(repo)

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo, paths, regression_file, "add medium tier-m coverage", tier="M"
        ),
        capsys,
    )

    assert exit_code == 0, f"expected a clean commit, got payload={payload!r}"
    assert payload.get("event") == "SliceCommitted"


# --- (d) --tier omitted: byte-identical to today ---------------------------


def test_tier_omitted_stays_byte_identical_to_today(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: d -- the no-regression witness

    Omitting --tier entirely over a scope that WOULD be L-tier (a boundary
    crossing) still commits normally -- proving the cap is opt-in by
    construction and never runs unconditionally. This is the discriminating
    counterpart to the refusal tests above: the SAME scope that gets refused
    under a declared --tier S/M commits cleanly with --tier omitted.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    paths, regression_file = _scope_boundary(repo)

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo, paths, regression_file, "add boundary scope no tier declared"
        ),
        capsys,
    )

    assert exit_code == 0, (
        f"omitting --tier must be byte-identical to today (no cap applied), "
        f"got payload={payload!r}"
    )
    assert payload.get("event") == "SliceCommitted"


# --- (e) declared L: never refused regardless of measured scope ------------


_UP_TO_L_CASES = [
    pytest.param("lines_exceed", _scope_lines_exceed, id="lines_exceed"),
    pytest.param("boundary", _scope_boundary, id="boundary"),
]


@pytest.mark.parametrize("scope_kind,scope_builder", _UP_TO_L_CASES)
def test_declared_tier_l_never_refused_regardless_of_measured_scope(
    tmp_path: Path, capsys, scope_kind: str, scope_builder
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: e

    A --tier L declaration NEVER refuses, regardless of whether the measured
    scope is M (lines alone) or L (a boundary crossing) -- L is the ceiling,
    nothing measured exceeds it.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    paths, regression_file = scope_builder(repo)

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo, paths, regression_file, f"add {scope_kind} scope declared l", tier="L"
        ),
        capsys,
    )

    assert exit_code == 0, f"L is the ceiling -- nothing exceeds it, got {payload!r}"
    assert payload.get("event") == "SliceCommitted"


# --- (f) NEGATIVE: an indeterminate measurement is NEVER silently trusted --


def test_indeterminate_measurement_is_never_silently_trusted(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: f -- MANDATORY NEGATIVE, the one that matters most

    A scope carrying a genuinely UNPARSEABLE `.py` file cannot be reliably
    measured -- its `consumer_counts` entry degrades to `null` (never a
    fabricated 0), which the SHIPPED `classify_tier` already escalates to L
    (DT2, GDP-6: unknown blast radius is the worst case, never silently
    smaller). Declared --tier M (a GENEROUS, non-strict declaration) is
    STILL refused: an enforcement that quietly disappears exactly when
    measurement is hard is not an enforcement.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    paths, regression_file = _scope_indeterminate(repo)

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo, paths, regression_file, "add unparseable scope declared m", tier="M"
        ),
        capsys,
    )

    assert exit_code == 1, (
        "a genuinely unmeasurable (unparseable-file) scope must NEVER pass "
        f"silently on the operator's word, got payload={payload!r}"
    )
    assert payload.get("event") == "BlastRadiusTierExceeded"
    assert payload.get("declared_tier") == "M"
    assert payload.get("measured_tier") == "L", (
        "an unparseable touched file degrades its consumer_counts entry to "
        "null, which classify_tier escalates to L -- the tier cap must "
        "inherit this escalation, never invent a smaller verdict"
    )
    why = str(payload.get("why", "")).lower()
    assert any(
        token in why for token in ("pars", "indeterminate", "null", "broken.py")
    ), (
        f"the WHY must name the indeterminate cause, not a bare tier letter -- got {why!r}"
    )
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before
    assert _git(repo, "diff", "--cached", "--name-only").strip() == ""


# --- (D3) the cap also applies to the resolved --all staged set ------------


def test_all_flag_scope_also_enforces_the_tier_cap(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b -- DT-adjacent: the feature-delta names TWO declared-scope
    shapes ("the declared --path list, OR the resolved --all staged set");
    this pins that --all is measured too, not only an explicit --path list.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    _scope_boundary(repo)  # writes the files on disk; --all discovers them
    regression_file = "tests/unit/test_slice_tier_boundary.py"

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo,
            [],
            regression_file,
            "add boundary scope via --all",
            tier="S",
            use_all=True,
        ),
        capsys,
    )

    assert exit_code == 1, (
        f"expected the cap to also apply under --all, got {payload!r}"
    )
    assert payload.get("event") == "BlastRadiusTierExceeded"
    assert payload.get("measured_tier") == "L"
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before
    assert _git(repo, "diff", "--cached", "--name-only").strip() == ""


def test_all_flag_scope_with_genuinely_small_scope_commits_normally(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b -- the --all HAPPY PATH (MEDIUM review finding): the sibling
    test above (`test_all_flag_scope_also_enforces_the_tier_cap`) only proves
    --all is measured under a REFUSING scenario -- this pins the --all HAPPY
    PATH: a genuinely S-measured scope (1 file, well under 10 lines) staged
    via --all with --tier S commits cleanly. Also guards against the
    implementation measuring the WRONG scope under --all (the already-staged
    paths at invocation time, which would be empty here, instead of the
    resolved --all staged set the declared scope actually is).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _paths, regression_file = _scope_small(repo)

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo,
            [],
            regression_file,
            "add small tier-s coverage via --all",
            tier="S",
            use_all=True,
        ),
        capsys,
    )

    assert exit_code == 0, f"expected a clean commit, got payload={payload!r}"
    assert payload.get("event") == "SliceCommitted"


def test_deleted_path_in_the_tier_scope_refuses_structurally_never_crashes(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b, g -- MANDATORY NEGATIVE (feature-end deep-review BLOCKER D3)

    Declaring `--tier` over a scope naming a DELETED path must produce a
    structured, self-explaining refusal (GDP-3 what/why/how) and must leave
    the index CLEAN -- never a raw traceback with a dangling staged deletion.

    WHY THE 49-AT CORPUS MISSED THIS: no AT in the corpus ever seeds a
    DELETED path in any scope -- the "D" leg of CRUD is absent from every
    fixture (the same root cause as the D2 blocker in the slice-02 module).

    THE DEFECT: `commit_slice.py` imports only `BlastRadiusVerdict` and
    `measure_blast_radius` -- it catches NEITHER `BlastRadiusInputRejected`
    NOR `BlastRadiusConfigRejected`, unlike `des blast-radius`'s own CLI which
    catches both and maps each to a structured exit-2 payload. A deleted
    `--path` reaches `_resolve_scope`'s existence check, which raises
    `BlastRadiusInputRejected` -- uncaught, so it escapes `main()` as a raw
    traceback. Worse, the escape happens AFTER `_stage()` has already staged
    the deletion and BEFORE the refusal path's `git_run(repo, "reset")`
    cleanup, so the staged deletion is left dangling in the operator's index.

    Both halves matter and neither implies the other: a structured refusal
    that forgot the reset would still corrupt the index, and a reset without
    a structured refusal would still hand the operator a traceback.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    doomed_rel = "doomed_module.py"
    (repo / doomed_rel).write_text("def doomed():\n    return 1\n", encoding="utf-8")
    regression_file = "tests/unit/test_slice_tier_deleted.py"
    (repo / regression_file).write_text(
        "def test_slice_tier_deleted():\n    assert True\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed the module this slice deletes")
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    (repo / doomed_rel).unlink()

    exit_code, payload, stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo,
            [doomed_rel, regression_file],
            regression_file,
            "delete the doomed module",
            tier="S",
        ),
        capsys,
    )

    # A structured refusal, never a traceback escaping main().
    assert exit_code in (1, 2), (
        f"a deleted path in the --tier scope must produce a structured "
        f"refusal, got exit={exit_code}, payload={payload!r}"
    )
    assert payload, (
        "the refusal must emit a machine-readable JSON payload -- today the "
        "uncaught BlastRadiusInputRejected escapes main() as a raw traceback, "
        "so NO payload is ever emitted"
    )
    assert "Traceback" not in stderr, (
        f"a declared-scope input problem is a REFUSAL, not a crash -- an "
        f"uncaught exception is never a self-explaining failure surface "
        f"(GDP-3), got stderr={stderr!r}"
    )
    assert doomed_rel in json.dumps(payload), (
        "the refusal must NAME the offending path (GDP-3 what), not merely "
        "report that something went wrong"
    )

    # The index is left CLEAN: the cleanup the refusal path performs today is
    # skipped entirely when the exception escapes before reaching it.
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before, (
        "nothing may land -- HEAD must stay exactly where it was"
    )
    staged = _git(repo, "diff", "--cached", "--name-only").strip()
    assert staged == "", (
        f"a refusal must unstage what commit-slice itself staged -- today the "
        f"exception escapes BEFORE the `git reset` cleanup line, leaving the "
        f"staged deletion dangling in the operator's index: {staged!r}"
    )


# --- (D7) the escape hatch is the CLASS of exception, not two members ------


def test_any_escaping_measurement_exception_becomes_a_structured_refusal(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b, g -- MANDATORY NEGATIVE (feature-end re-review BLOCKER D7)

    ANY exception escaping the tier measurement must become a structured,
    self-explaining refusal with a CLEAN index -- not merely the two types
    the D3 fix happened to name.

    THE CLASS, NOT THE INSTANCE: `_check_blast_radius_tier` wraps
    `measure_blast_radius()` in a try/except for exactly
    `BlastRadiusInputRejected` and `BlastRadiusConfigRejected`. Every OTHER
    failure inside `measure_blast_radius` / `_resolve_scope` -- a failing
    `git diff`, an unparseable git object, a filesystem/permission error --
    escapes uncaught, crashes `main()` with a raw traceback, and skips the
    caller's `git_run(repo, "reset")` cleanup, leaving staged content
    dangling.

    WHY THIS AT EXISTS SEPARATELY FROM D3: the D3 AT pinned ONE member of
    the class (the deleted path), so the fix that followed it caught ONE
    member's exception type -- the AT shaped the fix to its own narrowness.
    This AT pins the CLASS: the tier cap sits on the pre-commit chokepoint,
    so its failure surface must be total. Whatever goes wrong inside the
    measurement, the operator gets a refusal they can read and an index they
    can trust.

    `RuntimeError` here is an ARBITRARY representative of "an exception that
    is neither caught type". DELIVER must NOT satisfy this AT by adding
    `RuntimeError` to the except tuple -- that repeats the exact
    instance-not-class mistake. The correct fix is a total handler mapping
    any unexpected failure to a structured refusal, degrading LOUD.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    paths, regression_file = _scope_small(repo)

    def _explode(*_args, **_kwargs):
        raise RuntimeError("git diff failed: unparseable object 4b825dc")

    monkeypatch.setattr("des.cli.commit_slice.measure_blast_radius", _explode)

    exit_code, payload, stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo,
            paths,
            regression_file,
            "add scope whose measurement explodes",
            tier="S",
        ),
        capsys,
    )

    assert exit_code in (1, 2), (
        f"ANY escaping measurement exception must become a structured refusal, "
        f"not a crash -- got exit={exit_code}, payload={payload!r}"
    )
    assert payload, (
        "the refusal must emit a machine-readable JSON payload -- an "
        "unexpected exception type currently escapes main() uncaught, so NO "
        "payload is ever emitted"
    )
    assert "Traceback" not in stderr, (
        f"an unexpected measurement failure is a REFUSAL, not a crash: the "
        f"operator gets a message they can act on (GDP-3), never a stack "
        f"trace. Got stderr={stderr!r}"
    )
    for field in ("what", "why", "how"):
        assert payload.get(field), (
            f"the refusal must be self-explaining (GDP-3) -- missing/empty "
            f"{field!r} in {payload!r}"
        )

    assert _git(repo, "rev-parse", "HEAD").strip() == head_before, (
        "nothing may land when the measurement fails -- HEAD must not move"
    )
    staged = _git(repo, "diff", "--cached", "--name-only").strip()
    assert staged == "", (
        f"an escaping measurement exception must still leave the index CLEAN "
        f"-- today the crash skips the reset cleanup and leaves the staged "
        f"content dangling: {staged!r}"
    )


# --- (D8) a refusal must not discard the operator's own staging ------------


def test_all_refusal_preserves_the_operators_pre_existing_staging(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b -- MANDATORY NEGATIVE (feature-end re-review HIGH D8)

    A tier-cap refusal under `--all` must NOT silently discard staging the
    operator curated BEFORE invoking: content staged before the invocation
    is still staged after the refusal.

    THE DEFECT: on refusal the code runs `git_run(repo, "reset")`, which
    unstages the ENTIRE index unconditionally. Under `--all` the
    extraneous-staged-content guard is deliberately exempted ("the operator
    explicitly asked for everything"), so anything already staged -- curated
    `git add -p` hunks for unrelated work -- is swept in by `git add -A` and
    then silently unstaged by the refusal. The module's own comment claims
    "only the STAGING commit-slice itself performed is undone"; under
    `--all` that is not true.

    WHY STRICT: no bytes are destroyed on disk, but staging INTENT is real
    work -- a curated partial-hunk index can represent substantial effort
    and is NOT reconstructible from the working tree. This lands amid an
    investigation into a shared working tree silently eating uncommitted
    work (8 forensic occurrences), so a refusal path that discards someone's
    index without naming it is that same class, introduced by the fix for
    the previous defect.

    ACCEPTABLE ALTERNATIVE IF PRESERVATION PROVES INFEASIBLE: the refusal
    payload NAMES what it is about to unstage, so the loss is visible and
    hand-recoverable rather than silent. That is strictly worse than
    preserving, which is why this AT asserts preservation -- the weaker
    route should have to be argued for explicitly, never defaulted into.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    head_before = _git(repo, "rev-parse", "HEAD").strip()

    # The operator's OWN curated staging, unrelated to this slice, staged
    # BEFORE commit-slice is invoked.
    unrelated_rel = "operator_work_in_progress.py"
    (repo / unrelated_rel).write_text(
        "def unrelated_wip():\n    return 'curated by the operator'\n",
        encoding="utf-8",
    )
    _git(repo, "add", unrelated_rel)
    staged_before = set(
        _git(repo, "diff", "--cached", "--name-only").strip().splitlines()
    )
    assert unrelated_rel in staged_before, "fixture precondition: the WIP is staged"

    # A boundary scope measures L, so --tier S refuses.
    _scope_boundary(repo)
    regression_file = "tests/unit/test_slice_tier_boundary.py"

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo,
            [],
            regression_file,
            "add boundary scope via --all over curated staging",
            tier="S",
            use_all=True,
        ),
        capsys,
    )

    assert exit_code == 1, f"expected the tier cap to refuse, got {payload!r}"
    assert payload.get("event") == "BlastRadiusTierExceeded"
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before

    staged_after = set(
        _git(repo, "diff", "--cached", "--name-only").strip().splitlines()
    )
    assert unrelated_rel in staged_after, (
        f"the operator staged {unrelated_rel!r} BEFORE invoking commit-slice; "
        f"a --tier refusal must not silently discard it. Today the refusal "
        f"runs an unconditional `git reset`, which under --all unstages the "
        f"operator's curated index alongside what commit-slice itself staged "
        f"-- staging intent is real work, not reconstructible from the "
        f"working tree. Staged after the refusal: {sorted(staged_after)}"
    )


def _commit_unrelated_file(repo: Path, rel: str, body: str) -> None:
    """Commit an unrelated file so the operator can later stage a DELETION or
    a RENAME of it (both need a committed baseline to exist at all)."""
    (repo / rel).write_text(body, encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", f"seed unrelated {rel}")


def _staged_name_status(repo: Path) -> list[str]:
    """`git diff --cached --name-status` lines -- unlike `--name-only` this
    preserves the STATUS letter (D/R/M), so a deletion or rename staged by
    the operator is distinguishable from an ordinary modification."""
    return [
        line
        for line in _git(repo, "diff", "--cached", "--name-status").strip().splitlines()
        if line.strip()
    ]


def test_all_refusal_preserves_a_pre_staged_deletion(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b -- CHARACTERIZATION AT (expected GREEN on authoring, by
    design -- see below). Closes a FIXTURE-COVERAGE gap, not a behaviour gap.

    An operator's pre-staged DELETION survives a `--all` tier-cap refusal:
    still staged as a deletion afterwards, and the file is NOT resurrected
    on disk.

    WHY THIS AT EXISTS -- AND WHY IT IS GREEN, NOT RED: the D8 fix
    (`_reset_preserving_pre_existing_staging`, unstaging only the delta via
    `git reset -- <paths>`) is covered today ONLY by a fixture that stages an
    ORDINARY MODIFIED file. A deep reviewer raised the concern that
    `git reset -- <path>` would destroy a staged deletion's intent. That
    concern was MEASURED and is FALSE:

        rm doomed.py; git add -A      -> staged: "D doomed.py"
        git reset -- doomed.py
           git diff --cached          -> empty
           git status --porcelain     -> " D doomed.py"  (deletion intact,
                                                          merely unstaged)
           ls doomed.py               -> No such file    (NOT recreated)

    `git reset -- <path>` makes the index entry match HEAD (i.e. "unstaged")
    and never touches the working tree. Additionally `_staged_paths` is
    `git diff --cached --name-only`, which LISTS deletions -- so a pre-staged
    deletion is inside the snapshot and falls out of the delta by
    construction.

    So the behaviour is already right. The DEFECT was that the AT suite could
    not TELL right from wrong here: every fixture staged only ordinary files,
    so a correct implementation and the one the reviewer feared would both
    have passed. An AT that passes because of how its fixture is built is a
    coincidence, not a proof. This AT is therefore a CHARACTERIZATION test --
    it pins behaviour that is correct today but was structurally unprotected.
    A future refactor that "simplifies" the delta-reset back into a blanket
    `git reset`, or that filters deletions out of the snapshot, now breaks
    HERE instead of silently in an operator's working tree.

    NOT A FAILED REGRESSION TEST: if this is green the moment it is authored,
    that is the intended and correct outcome -- do not read it as a no-op.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    unrelated_rel = "operator_deleted_file.py"
    _commit_unrelated_file(
        repo, unrelated_rel, "def doomed_by_the_operator():\n    return 1\n"
    )
    head_before = _git(repo, "rev-parse", "HEAD").strip()

    # The operator's OWN staged DELETION, before commit-slice is invoked.
    _git(repo, "rm", "-q", unrelated_rel)
    assert any(
        line.startswith("D") and unrelated_rel in line
        for line in _staged_name_status(repo)
    ), "fixture precondition: the deletion is staged"

    # A boundary scope measures L, so --tier S refuses.
    _scope_boundary(repo)
    regression_file = "tests/unit/test_slice_tier_boundary.py"

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo,
            [],
            regression_file,
            "add boundary scope via --all over a staged deletion",
            tier="S",
            use_all=True,
        ),
        capsys,
    )

    assert exit_code == 1, f"expected the tier cap to refuse, got {payload!r}"
    assert payload.get("event") == "BlastRadiusTierExceeded"
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before

    staged_after = _staged_name_status(repo)
    assert any(
        line.startswith("D") and unrelated_rel in line for line in staged_after
    ), (
        f"the operator staged a DELETION of {unrelated_rel!r} before invoking; "
        f"a --tier refusal must preserve it as a STAGED deletion, not merely "
        f"leave some entry behind. Staged after the refusal: {staged_after}"
    )
    assert not (repo / unrelated_rel).exists(), (
        f"a refusal must never RESURRECT a file the operator deleted -- "
        f"{unrelated_rel!r} reappeared on disk, which would silently undo "
        f"the operator's deletion intent in the working tree"
    )


def test_all_refusal_preserves_a_pre_staged_rename(tmp_path: Path, capsys) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b -- CHARACTERIZATION AT (expected GREEN on authoring, by
    design -- same class as the staged-deletion AT above).

    An operator's pre-staged RENAME survives a `--all` tier-cap refusal:
    both sides stay staged (the old path's removal AND the new path's
    addition), and the working tree still shows the renamed file at its new
    location only.

    WHY: a rename is the index shape most likely to be silently half-undone
    by a partial reset -- it occupies TWO index entries that must move
    together. Unstaging one side and not the other would leave the operator
    with an incoherent index that neither `git status` nor any assertion in
    the pre-existing suite would have flagged, because every fixture staged
    exactly one ordinary file. Like the deletion AT, this pins behaviour that
    is correct today but structurally unprotected: the suite could not
    distinguish a correct delta-reset from one that mangles multi-entry index
    shapes.

    NOT A FAILED REGRESSION TEST: green on authoring is the intended outcome.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    old_rel = "operator_old_name.py"
    new_rel = "operator_new_name.py"
    _commit_unrelated_file(
        repo, old_rel, "def renamed_by_the_operator():\n    return 1\n"
    )
    head_before = _git(repo, "rev-parse", "HEAD").strip()

    # The operator's OWN staged RENAME, before commit-slice is invoked.
    _git(repo, "mv", old_rel, new_rel)
    assert _staged_name_status(repo), "fixture precondition: the rename is staged"

    _scope_boundary(repo)
    regression_file = "tests/unit/test_slice_tier_boundary.py"

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo,
            [],
            regression_file,
            "add boundary scope via --all over a staged rename",
            tier="S",
            use_all=True,
        ),
        capsys,
    )

    assert exit_code == 1, f"expected the tier cap to refuse, got {payload!r}"
    assert payload.get("event") == "BlastRadiusTierExceeded"
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before

    # Both sides of the rename must still be staged. git may record this as
    # a single `R` entry naming both paths, or as a `D old` + `A new` pair --
    # either encoding is fine, but BOTH paths must appear.
    staged_after = _staged_name_status(repo)
    staged_blob = "\n".join(staged_after)
    assert old_rel in staged_blob, (
        f"the OLD side of the operator's staged rename was dropped -- a "
        f"refusal must not half-undo a rename, leaving an incoherent index. "
        f"Staged after the refusal: {staged_after}"
    )
    assert new_rel in staged_blob, (
        f"the NEW side of the operator's staged rename was dropped -- a "
        f"refusal must not half-undo a rename. Staged after the refusal: "
        f"{staged_after}"
    )
    assert (repo / new_rel).exists(), "the renamed file must remain on disk"
    assert not (repo / old_rel).exists(), (
        "a refusal must not resurrect the pre-rename path in the working tree"
    )


# --- (D10) the PREFLIGHT refusal path still resets unconditionally ---------


def test_preflight_refusal_preserves_the_operators_pre_existing_staging(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: b, g -- MANDATORY NEGATIVE (deep-review D10)

    The PREFLIGHT gate's refusal path must preserve the operator's
    pre-existing staging, exactly as the tier-cap refusal path now does.

    THE DEFECT -- D8's class, left alive in the SECOND path: the tier-cap
    refusal was fixed to unstage only the delta
    (`_reset_preserving_pre_existing_staging`), but the preflight gate's
    refusal path still calls a bare, unconditional `git_run(repo, "reset")`.
    Under `--all` that empties the operator's entire index -- curated
    `git add -p` hunks for unrelated work included. The comment directly
    above that call asserts "only the STAGING commit-slice itself performed
    is undone", which under `--all` is exactly as untrue as it was in the
    tier-cap path before D8. Two refusal paths, one already corrected, the
    other still carrying the original defect and a comment claiming
    otherwise.

    WHY IT MATTERS MORE HERE: the preflight gate refuses on ordinary E1/E2
    failures -- a far more frequent path than a tier-cap breach. The most
    common refusal is the one silently eating the most staging.

    ANTI-GAMING CONSTRAINT (read before fixing): the fix is to call the SAME
    `_reset_preserving_pre_existing_staging(repo, pre_stage_snapshot)` this
    module already has. It is NOT satisfied by wrapping the reset in
    `if not args.all:` -- that would skip the cleanup wholesale under
    `--all`, leaving staged everything commit-slice ITSELF added, which is
    the opposite defect (a refusal must leave no half-staged slice content).
    Both properties must hold at once: the operator's prior staging survives
    AND this invocation's own staging is undone. The delta reset is the only
    shape that satisfies both.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    head_before = _git(repo, "rev-parse", "HEAD").strip()

    # The operator's OWN curated staging on a file this slice never declares.
    unrelated_rel = "operator_work_in_progress.py"
    (repo / unrelated_rel).write_text(
        "def unrelated_wip():\n    return 'curated by the operator'\n",
        encoding="utf-8",
    )
    _git(repo, "add", unrelated_rel)
    assert unrelated_rel in _git(repo, "diff", "--cached", "--name-only"), (
        "fixture precondition: the operator's WIP is staged"
    )

    _paths, regression_file = _scope_small(repo)

    # Force the PREFLIGHT gate to refuse (a genuine E1/E2-style non-zero that
    # is NOT the indeterminate code 3, so it takes the reset+refuse branch --
    # the `return preflight_exit_code` after the unconditional reset). No
    # --tier is declared, so the tier-cap path is not involved at all: this
    # isolates the SECOND refusal path.
    def _refuse(*_args, **_kwargs):
        return 1, {}

    monkeypatch.setattr(
        "des.cli.verify_slice_commit_completeness._run_verify_checks", _refuse
    )

    exit_code, payload, _stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo,
            [],
            regression_file,
            "add small scope refused by the preflight gate",
            use_all=True,
        ),
        capsys,
    )

    assert exit_code == 1, (
        f"expected the preflight gate to refuse (exit 1), got exit={exit_code}, "
        f"payload={payload!r}"
    )
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before, (
        "a preflight refusal lands no commit -- HEAD must not move"
    )

    staged_after = set(
        _git(repo, "diff", "--cached", "--name-only").strip().splitlines()
    )
    assert unrelated_rel in staged_after, (
        f"the operator staged {unrelated_rel!r} BEFORE invoking commit-slice; "
        f"the PREFLIGHT refusal path must preserve it, exactly as the "
        f"tier-cap path was fixed to (D8). Today it runs an unconditional "
        f"`git reset`, emptying the operator's whole index under --all. "
        f"Staged after the refusal: {sorted(staged_after)}"
    )


# --- (g) NEGATIVE: an invalid --tier value is a clear usage error ----------


def test_invalid_tier_value_is_a_clear_usage_error_never_silently_ignored(
    tmp_path: Path, capsys
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch

    # covers: g -- MANDATORY NEGATIVE

    A --tier value outside {S,M,L} is a clear usage error (exit 2), not
    silently ignored: a silently-ignored bad value would be INDISTINGUISHABLE
    from omitting --tier entirely, which the byte-identical-omission witness
    above proves lets an L-measured scope commit cleanly. This test uses the
    SAME boundary (L-measuring) scope and proves the OPPOSITE: nothing
    commits, and the failure is a value-rejection (DT3), not merely "the
    flag does not exist" (today's pre-implementation failure mode).

    Also asserts GIT STATE (MEDIUM review finding): the exit-code + output
    assertions alone would still pass an implementation that validated
    --tier AFTER already landing a commit -- the sibling refusal tests
    (b-f) all pin HEAD-unchanged + nothing-staged, and this is exactly what
    makes "before any commit lands" (the feature-delta's own words) an
    ENFORCED property here too, not merely a stated one.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    head_before = _git(repo, "rev-parse", "HEAD").strip()
    paths, regression_file = _scope_boundary(repo)

    exit_code, payload, stderr = _invoke_commit_slice(
        _commit_slice_argv(
            repo, paths, regression_file, "add boundary scope bogus tier", tier="BOGUS"
        ),
        capsys,
    )

    assert exit_code == 2, (
        f"an invalid --tier value must be a clear usage error (exit 2), got "
        f"exit={exit_code}, payload={payload!r}"
    )
    combined = (json.dumps(payload) + stderr).lower()
    assert "tier" in combined, "the rejection must name the --tier flag"
    assert "bogus" in combined, "the rejection must name the offending value"
    assert "unrecognized" not in combined, (
        "today (pre-implementation) an unknown --tier flag dies as "
        "'unrecognized arguments' -- once --tier is a REAL, validated flag "
        "an invalid VALUE must be reported as a value-rejection (DT3), not "
        "merely an unrecognized argument"
    )

    # Never silently ignored: a silently-ignored --tier would be
    # indistinguishable from omitting it, which would let this L-measuring
    # scope commit cleanly (see the byte-identical-omission witness above).
    assert payload.get("event") != "SliceCommitted"

    # GIT STATE (the "before any commit lands" enforcement witness -- mirrors
    # the sibling refusal tests b-f): a validation-after-commit implementation
    # would still pass every assertion above; only these two catch it.
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before, (
        "an invalid --tier value must be rejected BEFORE any git mutation -- "
        "HEAD must stay exactly where it was before the invocation"
    )
    assert _git(repo, "diff", "--cached", "--name-only").strip() == "", (
        "an invalid --tier value must leave the working tree UNSTAGED, not "
        "half-staged by a validation step that ran after staging"
    )
    assert _git(repo, "rev-parse", "HEAD").strip() == head_before
