"""Regression ATs — WS-2 (M2) of the feature-delta-doctor-and-ssot bugfix.

FR-11 traced a 7-sequential-rejection friction cascade: a contributor hits
one gate rejection, fixes it, resubmits, hits the NEXT gate's rejection, and
so on -- one-gap-at-a-time. `des feature-delta-doctor <path>` is the root
fix: a ONE-PASS, FILESYSTEM-ONLY generator that reads a feature-delta and
reports every structural gap at once (missing mandatory sections,
non-canonical Wave headings, malformed/unjustified Reuse Analysis rows),
each self-explaining what/why/how (STANDING every-failure-explains mandate).

Driving surface (P1-P4 in-process active-RED pattern, `nw-distill-red-
scaffolding`): the stable, always-present entry `des.cli.__main__` is driven
via subprocess (`python -m des.cli.__main__ feature-delta-doctor ...`) --
NEVER the not-yet-existing `des.cli.feature_delta_doctor` module. The
subcommand is absent from the `_SubcommandRow` registry today, so argparse's
OWN internal dispatch (a runtime call inside the child process, never a
collection-time import) rejects it with a clean `invalid choice` exit 2 --
not a traceback. Each test asserts on `returncode` FIRST (a plain, semantic
AssertionError) before ever parsing stdout as JSON, so a still-absent
subcommand fails for the right reason (MISSING_FUNCTIONALITY), never a
`json.JSONDecodeError`.

covers: R-M2
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from des.cli.validate_feature_delta import (
    LOCKED_REF_SECTIONS,
    VERDICT_MALFORMED_WAVE_HEADING,
    VERDICT_UNJUSTIFIED_CREATE_NEW,
    locked_sections_present,
)


# ---------------------------------------------------------------------------
# Fixtures — feature-delta content
# ---------------------------------------------------------------------------

#: Four INDEPENDENT, non-contradictory gaps in ONE feature-delta:
#: (1) a malformed Wave heading (`## Wave: DESIGN / Architecture` -- no
#:     `[TYPE]` token) -> VERDICT_MALFORMED_WAVE_HEADING;
#: (2)+(3) two of the four LOCKED_REF_SECTIONS absent ("Architecture &
#:     Contract Tests", "ADR Refs") -- Reuse Analysis and Slice Plan ARE
#:     present, so this is a genuine presence gap, not a duplicate of (4);
#: (4) the Reuse Analysis section IS present but carries an unjustified
#:     CREATE_NEW row (empty Justification) -> VERDICT_UNJUSTIFIED_CREATE_NEW.
#: Verified empirically against the production validators before authoring
#: this AT (locked_sections_present -> ["Architecture & Contract Tests",
#: "ADR Refs"]; validate_reuse_analysis_content -> unjustified-create-new;
#: validate_feature_delta_content -> 1 offender, missing schema prefix).
GAPPY_FEATURE_DELTA = (
    "## Wave: DESIGN / Architecture\n"
    "\n"
    "## Wave: DISCUSS / [REF] Slice Plan\n"
    "\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|---|---|---|---|---|\n"
    "| slice-01 | ships the walking skeleton | done |  | shipped |\n"
    "\n"
    "## Reuse Analysis\n"
    "\n"
    "| Existing Component | File | Overlap | Decision | Justification |\n"
    "|---|---|---|---|---|\n"
    "| SomeHelper | src/foo.py | none | CREATE_NEW |  |\n"
)

#: Zero-gap fixture: every LOCKED_REF_SECTIONS heading present and
#: well-formed, every Wave heading carries a valid `[TYPE]` token, the
#: Reuse Analysis section declares the DDD-9 `no-overlap` exemption marker
#: (an ACCEPTED verdict -- `no-overlap-declared` -- never a gap), AND a
#: well-formed `## Test Reuse & Consolidation Analysis` (sustainability)
#: section carrying the DDD-9 `methodology-exempt` marker. The sustainability
#: section is REQUIRED to be genuinely clean under the widened contract: the
#: doctor now mirrors `des verify-readiness-pre-dispatch`'s `sustainability`
#: invariant (`validate_sustainability_content` -> `methodology-exempt`,
#: an accepted verdict), so a delta lacking the section is no longer "clean".
#: Verified empirically: validate_feature_delta_content -> is_valid=True, zero
#: offenders; validate_reuse_analysis_content -> no-overlap-declared;
#: locked_sections_present -> []; validate_sustainability_content ->
#: methodology-exempt.
CLEAN_FEATURE_DELTA = (
    "## Wave: DESIGN / [REF] Architecture & Contract Tests\n"
    "\n"
    "Some architecture prose.\n"
    "\n"
    "## Wave: DESIGN / [REF] ADR Refs\n"
    "\n"
    "- ADR-001\n"
    "\n"
    "## Wave: DISCUSS / [REF] Slice Plan\n"
    "\n"
    "| Slice | Value statement | Status | Annotation | Justification |\n"
    "|---|---|---|---|---|\n"
    "| slice-01 | ships the walking skeleton | done |  | shipped |\n"
    "\n"
    "## Reuse Analysis\n"
    "\n"
    "Reuse-Analysis: no-overlap\n"
    "\n"
    "## Test Reuse & Consolidation Analysis\n"
    "\n"
    "Test-Reuse-Analysis: methodology-exempt\n"
)


# ---------------------------------------------------------------------------
# Driving-port helpers
# ---------------------------------------------------------------------------


def _doctor_argv(*args: str) -> list[str]:
    """Build the `python -m des.cli.__main__ feature-delta-doctor` argv.

    Drives the STABLE, always-present dispatcher module (never the absent
    `des.cli.feature_delta_doctor`) -- the P1 invariant of the in-process
    active-RED pattern, applied at the subprocess boundary so the absent
    subcommand surfaces as a clean argparse `invalid choice` (exit 2)
    inside the child, never a collection-time ImportError in this process.
    """
    return [sys.executable, "-m", "des.cli.__main__", "feature-delta-doctor", *args]


def _doctor_env() -> dict[str, str]:
    """Env with `src` on PYTHONPATH; freshness gate skipped.

    `NWAVE_FRESHNESS=skip` bypasses `des.runtime.freshness`'s OWN
    dev-checkout/installed-tree probe (a cross-cutting concern of the `des`
    dispatcher, unrelated to this AT's SUT) so its behaviour never
    confounds the feature-delta-doctor RED-classification -- in particular
    test_doctor_is_filesystem_only_no_git_dependency below deliberately
    runs with `cwd` pointed at a directory with no `.git`, which would
    otherwise engage the freshness probe's own (unrelated) filesystem
    checks.
    """
    project_root = Path(__file__).resolve().parents[4]
    env = dict(os.environ)
    src = str(project_root / "src")
    env["PYTHONPATH"] = (
        f"{src}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src
    )
    env["NWAVE_FRESHNESS"] = "skip"
    return env


def _run_doctor(
    target: Path, *extra_args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Invoke the doctor as a CLI subprocess and capture exit code + stdio."""
    return subprocess.run(
        _doctor_argv(str(target), *extra_args),
        capture_output=True,
        text=True,
        timeout=30,
        env=_doctor_env(),
        cwd=str(cwd) if cwd is not None else None,
    )


# ---------------------------------------------------------------------------
# (b1) all-gaps-in-one-pass
# ---------------------------------------------------------------------------


def test_doctor_lists_every_gap_in_one_invocation(tmp_path: Path) -> None:
    """`des feature-delta-doctor <path> --format=json` on a feature-delta
    carrying 4 independent gaps reports ALL of them in ONE JSON payload --
    never one-at-a-time -- each gap self-explaining what/why/how.

    FAILS TODAY: `feature-delta-doctor` is not a registered subcommand;
    the child process exits 2 (argparse `invalid choice`), not 1.
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(GAPPY_FEATURE_DELTA, encoding="utf-8")

    result = _run_doctor(target, "--format=json")

    assert result.returncode == 1, (
        "expected exit 1 (gaps found) once `des feature-delta-doctor` "
        f"exists; got {result.returncode}. stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    report = json.loads(result.stdout)
    gaps = report["gaps"]
    assert report["gap_count"] == len(gaps)
    assert len(gaps) >= 4, (
        f"expected >=4 distinct gaps (1 malformed heading + 2 missing "
        f"locked sections + 1 unjustified CREATE_NEW); got {len(gaps)}: {gaps}"
    )

    gap_ids = {gap["id"] for gap in gaps}
    assert VERDICT_MALFORMED_WAVE_HEADING in gap_ids
    assert VERDICT_UNJUSTIFIED_CREATE_NEW in gap_ids

    missing_sections = locked_sections_present(GAPPY_FEATURE_DELTA)
    assert missing_sections == ["Architecture & Contract Tests", "ADR Refs"]
    for section_name in missing_sections:
        assert any(section_name in gap.get("what", "") for gap in gaps), (
            f"expected a gap naming the missing locked section "
            f"{section_name!r} (one of {LOCKED_REF_SECTIONS}); gaps={gaps}"
        )

    # Every failure self-explains WHAT / WHY / HOW (STANDING mandate).
    for gap in gaps:
        assert gap.get("what"), f"gap missing 'what': {gap}"
        assert gap.get("why"), f"gap missing 'why': {gap}"
        assert gap.get("how"), f"gap missing 'how': {gap}"


# ---------------------------------------------------------------------------
# (b2) clean feature-delta -> zero gaps (no false positives)
# ---------------------------------------------------------------------------


def test_doctor_reports_zero_gaps_for_a_clean_feature_delta(tmp_path: Path) -> None:
    """A well-formed feature-delta (every locked section present, every Wave
    heading well-formed, Reuse Analysis exempted per DDD-9) reports ZERO
    gaps and exits 0 -- the guard against false positives.

    FAILS TODAY: `feature-delta-doctor` is not a registered subcommand;
    the child process exits 2, not 0.
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(CLEAN_FEATURE_DELTA, encoding="utf-8")

    result = _run_doctor(target, "--format=json")

    assert result.returncode == 0, (
        "expected exit 0 (zero gaps) on a well-formed feature-delta once "
        f"`des feature-delta-doctor` exists; got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    report = json.loads(result.stdout)
    assert report["gap_count"] == 0
    assert report["gaps"] == []


# ---------------------------------------------------------------------------
# (b3) filesystem-only -- no git dependency
# ---------------------------------------------------------------------------


def test_doctor_is_filesystem_only_no_git_dependency(tmp_path: Path) -> None:
    """CLAUDE.md agnosticism invariant (Python-only runtime): the doctor
    reads the feature-delta (+ declared slice-plan) via the filesystem
    ONLY -- it must run cleanly in a directory with NO `.git`, proving it
    never shells out to `git` (unlike `check_reuse_first_design.py`'s
    `git diff` detector, which is explicitly out of scope for the doctor's
    core).

    Runs the CLEAN fixture with `cwd` pointed AT `tmp_path` itself (which
    pytest guarantees is never a git repository) so a doctor that shelled
    out to `git` would fail here for a git-related reason, not the argparse
    `invalid choice` this test currently observes.

    FAILS TODAY: `feature-delta-doctor` is not a registered subcommand;
    the child process exits 2, not 0.
    """
    assert not (tmp_path / ".git").exists()  # tmp_path is never a git repo

    target = tmp_path / "feature-delta.md"
    target.write_text(CLEAN_FEATURE_DELTA, encoding="utf-8")

    result = _run_doctor(target, "--format=json", cwd=tmp_path)

    assert result.returncode == 0, (
        "feature-delta-doctor must run in a directory with no .git without "
        f"error (filesystem-only, no git dependency); got exit "
        f"{result.returncode}. stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    report = json.loads(result.stdout)
    assert report["gap_count"] == 0


# ---------------------------------------------------------------------------
# (b4) DEFECT 1 -- nonexistent path must NEVER surface a Python traceback
#
# Vera (examiner) flagged: `feature_delta_doctor.py:180` calls
# `Path(args.path).read_text(...)` uncaught -- a nonexistent path raises
# `FileNotFoundError` straight through `main()`, which the interpreter prints
# as a full "Traceback (most recent call last)" to stderr. This violates the
# STANDING every-failure-explains-what-why-how mandate: a traceback is the
# canonical anti-pattern the mandate exists to eliminate.
# ---------------------------------------------------------------------------


def test_doctor_nonexistent_path_never_shows_a_python_traceback(
    tmp_path: Path,
) -> None:
    """A nonexistent target path must produce a CLEAN, self-explaining error
    -- never an uncaught `FileNotFoundError` traceback.

    FAILS TODAY: `main()` calls `Path(args.path).read_text(...)` with no
    try/except; the interpreter prints "Traceback (most recent call last)"
    to stderr and exits 1 -- the exact same exit code the doctor uses for
    "gaps found", so a caller cannot even distinguish "the tool crashed"
    from "the tool ran and found gaps".
    """
    missing = tmp_path / "does" / "not" / "exist.md"
    assert not missing.exists()

    result = _run_doctor(missing, "--format=json")

    combined = result.stdout + result.stderr

    assert "Traceback (most recent call last)" not in combined, (
        "feature-delta-doctor must never leak a raw Python traceback for a "
        f"nonexistent path; got combined output:\n{combined}"
    )
    assert "FileNotFoundError" not in combined, (
        "feature-delta-doctor must surface a clean, self-explaining error "
        "for a nonexistent path -- never the raw exception class name; got "
        f"combined output:\n{combined}"
    )

    # A deliberate, distinguishable exit -- never the crash-default 1, which
    # is indistinguishable from the "gaps found" exit code.
    assert result.returncode not in (0, 1), (
        "expected a deliberate usage-class exit code (Vera suggested 2) "
        "distinct from 0 (no gaps) and 1 (gaps found), so a caller can "
        f"tell 'bad input' apart from 'ran and found gaps'; got "
        f"{result.returncode}. stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )

    # The error surface must self-explain WHAT failed (name the missing
    # path) -- either as a machine-readable JSON error object or, at
    # minimum, a clear one-line message naming the path.
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None

    if payload is not None:
        assert "error" in payload, (
            f"JSON error payload must self-explain via an 'error' field; got {payload}"
        )
        assert str(missing) in json.dumps(payload), (
            f"the error payload must name the missing path {str(missing)!r} "
            f"so the caller knows WHAT to fix; got {payload}"
        )
    else:
        assert str(missing) in combined, (
            "the clean error message must name the missing path "
            f"{str(missing)!r} so the caller knows WHAT to fix; got "
            f"combined output:\n{combined}"
        )


# ---------------------------------------------------------------------------
# (b5) DEFECT 2 -- the `why` field must explain the RULE, not restate `what`
#
# Vera (examiner) flagged: for the `unjustified-create-new` gap, `why` is
# set to the SAME `result.detail` string that is embedded verbatim inside
# `what` (`_reuse_analysis_gaps`: `what=f"...: {result.detail}"`,
# `why=result.detail`) -- `why` is a literal substring of `what`, so it adds
# zero new information. A self-explaining gap's `why` must explain the
# PRINCIPLE/rule rationale (reuse-first, reviewability, DDD-3's intent),
# not just restate the row-N condition already named in `what`.
# ---------------------------------------------------------------------------


#: Rationale vocabulary a genuinely explanatory `why` should draw on --
#: deliberately excludes words already present in the current buggy
#: `why` text ("CREATE_NEW", "Justification", "DDD-3", "row") so this
#: check cannot pass by accident on the unfixed code.
_RATIONALE_KEYWORDS = (
    "review",
    "reuse-first",
    "reuse first",
    "duplicat",
    "rationale",
    "principle",
    "accountab",
    "traceab",
)


def test_doctor_unjustified_create_new_why_explains_rationale_not_just_condition(
    tmp_path: Path,
) -> None:
    """The `unjustified-create-new` gap's `why` must explain the DDD-3
    reuse-first RULE -- not merely repeat the row-N condition `what` names.

    FAILS TODAY: `why` (`"row 1 is CREATE_NEW with an empty Justification
    (DDD-3)"`) is a literal substring of `what`
    (`"Reuse Analysis section is invalid: row 1 is CREATE_NEW with an "
    "empty Justification (DDD-3)"`) -- zero new information over `what`.
    """
    target = tmp_path / "feature-delta.md"
    target.write_text(GAPPY_FEATURE_DELTA, encoding="utf-8")

    result = _run_doctor(target, "--format=json")
    assert result.returncode == 1, (
        f"expected exit 1 (gaps found); got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    report = json.loads(result.stdout)

    create_new_gaps = [
        gap for gap in report["gaps"] if gap["id"] == VERDICT_UNJUSTIFIED_CREATE_NEW
    ]
    assert len(create_new_gaps) == 1, (
        f"expected exactly one {VERDICT_UNJUSTIFIED_CREATE_NEW!r} gap; "
        f"got {create_new_gaps}"
    )
    gap = create_new_gaps[0]

    assert gap["why"] != gap["what"], (
        f"'why' must differ from 'what'; both are {gap['why']!r}"
    )
    # Mechanizable proxy for "not redundant": today `why` is a verbatim
    # substring of `what` (same underlying `result.detail` reused twice) --
    # a genuinely explanatory `why` adds content `what` does not already
    # carry, so it should not be fully contained inside `what`.
    assert gap["why"] not in gap["what"], (
        "'why' must not be a verbatim substring of 'what' -- it must add "
        f"rule-rationale content 'what' does not already carry; "
        f"what={gap['what']!r} why={gap['why']!r}"
    )
    why_lower = gap["why"].lower()
    assert any(keyword in why_lower for keyword in _RATIONALE_KEYWORDS), (
        "'why' must reference the reuse-first / reviewability / DDD-3 "
        f"principle rationale (one of {_RATIONALE_KEYWORDS}), not just "
        f"restate the row condition; got why={gap['why']!r}"
    )
