"""Regression: `des verify-doc-coherence` false-flags legitimate doc content
in two classes (RCA, single production file
``src/des/cli/verify_doc_coherence.py``).

CLASS A -- runtime-dir hardcode (``_RUNTIME_STATE_TOP_LEVEL`` :127, consumed
in ``_is_checkable_path_claim`` :319): only ``.git``/``.nwave`` are exempt
runtime-state top-level dirs. A doc referencing a path under a top-level dir
the TARGET repo's OWN ``.gitignore`` lists (e.g. ``.tsunami/cache/x.json``
when ``.gitignore`` lists ``.tsunami/``) is flagged as a lie even though the
dir is legitimate gitignored runtime state, agnostic to its name.

CLASS B -- honest-absence punished (``_NEGATED_LINE_RE`` :132-137): a closed
6-group regex (NEW|CREATE_NEW|REJECTED|ABSENT|MISSING|TODO|TBD|
``Status: OPEN``|is/was deleted|do not exist|not yet) with ZERO Italian
coverage. A doc line that references a path AND on the SAME line honestly
annotates its absence ("since renamed to", "not created in this tree",
"planned path", "planned filename", "not a repo path", "removed; no longer
present", "non ancora creato") is flagged anyway.

Required fix (NOT implemented here -- this file authors the regression AT
only, no ``src/`` edit):
  - CLASS A: read the target repo's own ``.gitignore`` (pure Python, no
    ``git`` CLI, mirrors ``_load_npm_scripts``'s package.json read); a
    top-level dir it lists is exempt like ``.git``/``.nwave`` today. No
    ``.gitignore`` -> falls back to today's ``{.git,.nwave}``-only behavior,
    byte-identical. Unreadable ``.gitignore`` -> degrades LOUD (widens
    exemptions only), never silently passes a genuine unrelated lie.
  - CLASS B: extend the same-line honest-absence heuristic with the EN/IT
    phrasings above, WITHOUT blinding the gate to real lies (RCA
    peer-review caution: a bare "propose"/"proposed" word-boundary match
    would create false negatives -- scenario 6 below is the mechanical
    falsifier for that specific failure mode).

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.verify_doc_coherence.main()`` CLI driver, captured via
``capsys`` -- mirrors the established sibling regression pattern in
``tests/bugs/des/test_doc_coherence_unreadable_loud.py``.

Anchors (read, not modified): ``_RUNTIME_STATE_TOP_LEVEL`` (127),
``_NEGATED_LINE_RE`` (132-137, consumed in ``_scan_doc`` :467),
``_is_checkable_path_claim`` (303-324, runtime-state skip at 319),
``_check_path_claims`` (326-348), ``main()`` (494+).
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from des.cli.verify_doc_coherence import main as verify_doc_coherence_main


_DEGRADE_LOUD_KEYWORDS = (
    "unreadable",
    "cannot be read",
    "could not be read",
    "permission",
    "oserror",
    "os error",
    "indeterminate",
)


def _run_gate(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """Drive the REAL ``des verify-doc-coherence`` CLI (``main()``)
    in-process. Returns ``(exit_code, combined_stdout_stderr)``.
    """
    exit_code = verify_doc_coherence_main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out + captured.err


# ===========================================================================
# CLASS A -- positive ATs, active-RED today
# ===========================================================================


def test_gitignored_top_level_dir_reference_not_flagged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A doc referencing a path under a top-level dir the repo's OWN
    ``.gitignore`` lists (``.tmpstate/``) must NOT be flagged -- runtime
    state is agnostic to the dir's name, it need not be hardcoded ``.git``/
    ``.nwave``.

    RED today: ``.tmpstate`` is not in ``_RUNTIME_STATE_TOP_LEVEL`` and
    nothing reads ``.gitignore``, so ``.tmpstate/cache/x.json`` (dir exists,
    file does not) is flagged as a false path claim.
    """
    (tmp_path / ".gitignore").write_text(".tmpstate/\n")
    (tmp_path / ".tmpstate").mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "notes.md").write_text(
        "# Runtime Cache\n\n"
        "Cache entries are written to `.tmpstate/cache/x.json` at runtime.\n"
    )

    exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)

    assert exit_code == 0 and ".tmpstate/cache/x.json" not in combined, (
        "a path under a `.gitignore`-listed top-level dir must not be "
        f"flagged as a lie -- got exit_code={exit_code}, output={combined!r}"
    )


@pytest.mark.negative_at
def test_no_gitignore_git_and_nwave_dirs_still_exempt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No ``.gitignore`` present -> falls back to today's ``.git``/
    ``.nwave`` exemption, byte-identical. Must stay green both BEFORE and
    AFTER the fix -- this is the preserved fallback behavior, not a new
    requirement.
    """
    (tmp_path / ".git").mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "notes.md").write_text(
        "# Internals\n\nState lives at `.git/HEAD` and `.nwave/state.json`.\n"
    )

    exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)

    assert exit_code == 0, (
        "`.git`/`.nwave` references must stay exempt with no `.gitignore` "
        f"present -- got exit_code={exit_code}, output={combined!r}"
    )
    assert ".git/HEAD" not in combined and ".nwave/state.json" not in combined, (
        f"no spurious violation for exempt runtime dirs -- output={combined!r}"
    )


# ===========================================================================
# CLASS B -- positive ATs, active-RED today
# ===========================================================================


_HONEST_ABSENCE_EN_PHRASINGS = [
    pytest.param(
        "See `docs/legacy-config.md`, since renamed to docs/new-config.md.",
        "docs/legacy-config.md",
        id="since-renamed-to",
    ),
    pytest.param(
        "The file `docs/upcoming-guide.md` is not created in this tree yet.",
        "docs/upcoming-guide.md",
        id="not-created-in-this-tree",
    ),
    pytest.param(
        "`docs/future-spec.md` is the planned path for this content.",
        "docs/future-spec.md",
        id="planned-path",
    ),
    pytest.param(
        "`docs/draft-notes.md` is the planned filename for the write-up.",
        "docs/draft-notes.md",
        id="planned-filename",
    ),
    pytest.param(
        "`docs/example-only.md` is not a repo path, just an illustration.",
        "docs/example-only.md",
        id="not-a-repo-path",
    ),
    pytest.param(
        "`docs/old-report.md` was removed; no longer present in the tree.",
        "docs/old-report.md",
        id="removed-no-longer-present",
    ),
]


@pytest.mark.parametrize("line, claim", _HONEST_ABSENCE_EN_PHRASINGS)
def test_honest_absence_annotation_en_not_flagged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], line: str, claim: str
) -> None:
    """A doc line carrying a path token AND a same-line EN honest-absence
    annotation must NOT be flagged.

    RED today: ``_NEGATED_LINE_RE`` has zero coverage for these EN
    phrasings, so the claim is flagged as a false path reference.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "notes.md").write_text(f"# Notes\n\n{line}\n")

    exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)

    assert exit_code == 0 and claim not in combined, (
        f"honest-absence line {line!r} must not be flagged -- got "
        f"exit_code={exit_code}, output={combined!r}"
    )


def test_honest_absence_annotation_it_not_flagged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A doc line carrying a path token AND a same-line IT honest-absence
    annotation ("non ancora creato") must NOT be flagged.

    RED today: ``_NEGATED_LINE_RE`` has ZERO Italian coverage.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "notes.md").write_text(
        "# Note\n\nVedi `docs/piano.md` (non ancora creato in questo tree).\n"
    )

    exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)

    assert exit_code == 0 and "docs/piano.md" not in combined, (
        "the IT honest-absence line ('non ancora creato') must not be "
        f"flagged -- got exit_code={exit_code}, output={combined!r}"
    )


# ===========================================================================
# NEGATIVE ATs -- mechanical falsifiers, must stay green BEFORE and AFTER
# the fix (guard against the fix blinding the gate to real lies)
# ===========================================================================


@pytest.mark.negative_at
def test_real_missing_path_claim_still_flagged_no_gitignore_no_annotation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A genuine false path claim (no gitignore coverage, no absence
    annotation, path does not exist) must STILL be flagged. Already true
    today AND must remain true after the fix -- the fix must not widen
    suppression beyond gitignore-coverage + precise honest-absence.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "present.py").write_text("# real file\n")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "readme.md").write_text(
        "# Module\n\nSee `src/nonexistent.py` for the implementation.\n"
    )

    exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)

    assert exit_code == 1 and "src/nonexistent.py" in combined, (
        "a real missing-path claim with no gitignore coverage and no "
        f"absence annotation must still be flagged -- got "
        f"exit_code={exit_code}, output={combined!r}"
    )


@pytest.mark.negative_at
def test_bare_propose_word_does_not_suppress_a_real_missing_path_claim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CRITICAL guard (RCA peer-review finding): a sentence merely
    CONTAINING the word "propose"/"proposed" -- not as a path-adjacent
    absence annotation -- must NOT suppress a genuine missing-path claim.
    The honest-absence heuristic must be path-adjacent/precise, never a
    bare word-boundary match on "propose". Already true today (the word
    isn't in ``_NEGATED_LINE_RE`` at all) AND must remain true after the
    fix adds the EN/IT phrasings -- this is the falsifier that the fix
    doesn't over-suppress.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "present.py").write_text("# real file\n")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "readme.md").write_text(
        "# Proposal\n\n"
        "We propose adding a new module at `src/newmod.py` for this "
        "feature.\n"
    )

    exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)

    assert exit_code == 1 and "src/newmod.py" in combined, (
        "a sentence containing 'propose' must not blanket-suppress a real "
        f"missing-path claim -- got exit_code={exit_code}, "
        f"output={combined!r}"
    )


def test_unreadable_gitignore_degrades_loud_and_still_catches_real_lie(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Agnosticism/degrade-LOUD guard: an unreadable ``.gitignore`` (e.g.
    permission-denied) must not silently widen exemptions or silently pass
    an unrelated genuine lie -- the gate must (1) still flag the unrelated
    real missing-path claim, AND (2) announce the ``.gitignore`` could not
    be read (a visible degrade-LOUD signal), consistent with the standing
    what/why/how rule and the sibling ``DocCoherenceDocUnreadable`` pattern
    already used for unreadable docs.

    RED today: nothing reads ``.gitignore`` at all, so no visible signal
    ever names it -- the real-lie half already passes today (unrelated to
    this defect), so this fails specifically on the missing degrade-LOUD
    announcement, not on the real-lie detection.
    """
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(".tmpstate/\n")
    gitignore.chmod(0o000)
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "present.py").write_text("# real file\n")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "readme.md").write_text(
        "# Module\n\nSee `src/reallymissing.py` for the implementation.\n"
    )

    try:
        exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)

        combined_lower = combined.lower()
        real_lie_still_caught = exit_code == 1 and "src/reallymissing.py" in combined
        mentions_gitignore = "gitignore" in combined_lower
        degrade_signal = any(
            keyword in combined_lower for keyword in _DEGRADE_LOUD_KEYWORDS
        )

        assert real_lie_still_caught and mentions_gitignore and degrade_signal, (
            "an unreadable .gitignore must degrade LOUD (name the file, "
            "signal indeterminate/unreadable) while still catching the "
            f"unrelated real lie -- got exit_code={exit_code}, "
            f"real_lie_still_caught={real_lie_still_caught}, "
            f"mentions_gitignore={mentions_gitignore}, "
            f"degrade_signal={degrade_signal}, output={combined!r}"
        )
    finally:
        # Restore readability so tmp_path teardown can remove the file.
        gitignore.chmod(stat.S_IRUSR | stat.S_IWUSR)
