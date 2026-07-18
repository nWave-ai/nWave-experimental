"""Regression (GDP-6 word/behaviour mismatch): `des verify-doc-coherence`
must never label a NON-fatal outcome with the word reserved for its FATAL
verdict.

RCA: ``docs/feature/fix-unreadable-gitignore-exit-propagation/deliver/
rca.md``.

Found in ``src/des/cli/verify_doc_coherence.py``
``_load_gitignore_top_level_dirs`` (~:278-323). The genuine fatal verdict
helper ``_indeterminate`` (~:228-238) prints ``"⚠ INDETERMINATE — ..."`` and
returns ``_EXIT_INDETERMINATE`` (``= 2``, :48) -- a BLOCKING outcome. But the
present-but-unreadable-``.gitignore`` branch (~:299-321) prints the SAME
``"⚠ INDETERMINATE"`` label while returning ``frozenset()`` and NOT exiting
2 -- by design this is non-fatal ("Only affects the exemption set; checks
continue."). Same word, opposite outcome: an operator reading
"INDETERMINATE" reasonably expects a blocking indeterminate verdict, but the
run proceeds and PASSes when the docs are otherwise coherent.

Fix direction (RCA, NOT implemented here): change the unreadable-.gitignore
human print to a non-fatal WARNING label so the word matches the
non-fatal-continue behaviour, WITHOUT touching the exit code (must stay
non-fatal, GDP-8 foreign-target tolerance) and WITHOUT touching the genuine
fatal ``_indeterminate`` path (exit 2 for a real blocking indeterminate,
e.g. no doc files found at all).

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.verify_doc_coherence.main()`` CLI driver, captured via
``capsys`` -- mirrors the sibling regression AT
``tests/bugs/des/test_doc_coherence_unreadable_loud.py``.

OSError trigger: mirrors the sibling AT's empirically-confirmed technique --
a real file ``chmod``'d to ``0o000`` passes ``Path.is_file()`` (permission
bits do not affect that check) while ``read_text()`` raises
``PermissionError`` (an ``OSError`` subclass) on this (non-root) machine.
Applied here to ``.gitignore`` rather than a scanned doc.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from des.cli.verify_doc_coherence import main as verify_doc_coherence_main


def _run_gate(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """Drive the REAL ``des verify-doc-coherence`` CLI (``main()``)
    in-process. Returns ``(exit_code, combined_stdout_stderr)``.
    """
    exit_code = verify_doc_coherence_main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out + captured.err


# ===========================================================================
# POSITIVE AT -- active-RED today
# ===========================================================================


def test_unreadable_gitignore_warns_not_indeterminate_and_still_continues(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repo whose ``.gitignore`` is present but unreadable, and whose docs
    are otherwise coherent, must:

    1. NOT print the word "INDETERMINATE" for the unreadable-.gitignore
       notice -- that label is reserved for the tool's FATAL, blocking
       verdict (exit 2); this case is explicitly non-fatal.
    2. STILL continue and exit normally (0) -- non-fatal, not a blocking
       indeterminate.
    3. STILL tell the operator the .gitignore was unreadable -- the notice
       is not silenced, only re-labeled.

    RED today: line ~320-321 prints ``f"⚠ INDETERMINATE — {what}. Only
    affects the exemption set; checks continue."`` -- the word
    "INDETERMINATE" IS present even though the outcome is non-fatal. So
    assertion (1) fails with a semantic ``AssertionError`` today -- not a
    crash -- RED for the right reason.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "readme.md").write_text(
        "# Coherent Doc\n\nEverything documented here is true of the tree.\n"
    )
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("build/\n")
    gitignore.chmod(0o000)

    try:
        exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)
        combined_lower = combined.lower()

        names_gitignore_unreadable = (
            ".gitignore" in combined_lower and "could not be read" in combined_lower
        )

        assert "indeterminate" not in combined_lower, (
            "an unreadable .gitignore is explicitly NON-fatal (checks "
            "continue, exit code is unaffected by it) -- the word "
            "'INDETERMINATE' is reserved for the tool's FATAL, blocking "
            f"verdict and must not label this notice; output={combined!r}"
        )
        assert exit_code == 0, (
            "an unreadable .gitignore must not block the run -- with an "
            f"otherwise-coherent doc tree the exit code must stay 0 "
            f"(non-fatal); got exit_code={exit_code}, output={combined!r}"
        )
        assert names_gitignore_unreadable, (
            "the operator must still be told the .gitignore was "
            f"unreadable -- the notice must not be silenced; "
            f"output={combined!r}"
        )
    finally:
        # Restore readability so tmp_path teardown can remove the file.
        gitignore.chmod(stat.S_IRUSR | stat.S_IWUSR)


def test_broken_symlink_gitignore_warns_and_names_it_not_silently_dropped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A repo whose ``.gitignore`` is a BROKEN SYMLINK (points at a
    nonexistent target) and whose docs are otherwise coherent must still
    tell the operator the .gitignore could not be read -- a non-fatal
    WARNING that NAMES the .gitignore -- while continuing and exiting 0.

    Today ``_load_gitignore_top_level_dirs`` guards on
    ``gitignore.is_file()`` (~:299). ``Path.is_file()`` FOLLOWS symlinks and
    returns ``False`` for a broken symlink, so a present-but-unresolvable
    .gitignore silently takes the "absent" branch (returns ``frozenset()``,
    emits NO event, prints NO notice). That is INCONSISTENT with the
    permission-denied case (which warns) and violates the charter's "must
    not silently drop mention of the unreadable .gitignore".

    RED today: the ``.gitignore`` symlink exists but nothing in the output
    mentions it or signals it was unreadable -- the assertion below fails
    with a semantic ``AssertionError`` on the silent drop (no ⚠ line, no
    DocCoherenceGitignoreUnreadable event for the broken-symlink case) --
    not a crash -- RED for the right reason.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "readme.md").write_text(
        "# Coherent Doc\n\nEverything documented here is true of the tree.\n"
    )
    gitignore = tmp_path / ".gitignore"
    gitignore.symlink_to("/nonexistent/target")

    exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)
    combined_lower = combined.lower()

    names_gitignore_unreadable = (
        ".gitignore" in combined_lower and "could not be read" in combined_lower
    )

    assert names_gitignore_unreadable, (
        "a broken-symlink .gitignore must NOT be silently dropped -- like "
        "the permission-denied case, the operator must still be told the "
        ".gitignore could not be read (a non-fatal ⚠ WARNING naming it); "
        f"output={combined!r}"
    )
    assert "indeterminate" not in combined_lower, (
        "the broken-symlink .gitignore notice is NON-fatal -- it must use "
        "the WARNING label, never the FATAL-reserved word 'INDETERMINATE'; "
        f"output={combined!r}"
    )
    assert exit_code == 0, (
        "a broken-symlink .gitignore must not block the run -- with an "
        f"otherwise-coherent doc tree the exit code must stay 0 (non-fatal); "
        f"got exit_code={exit_code}, output={combined!r}"
    )


# ===========================================================================
# NEGATIVE AT -- control, must stay green BEFORE and AFTER the fix
# ===========================================================================


@pytest.mark.negative_at
def test_genuine_fatal_indeterminate_is_never_downgraded_by_the_gitignore_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The GENUINE fatal INDETERMINATE path (a real blocking indeterminate
    verdict, exit 2) must STILL say "INDETERMINATE" -- the fix must not
    downgrade it while re-labeling the unreadable-.gitignore case.

    Trigger: a repo with no doc files at all (no README*, no docs/) drives
    the real fatal ``_indeterminate(what="no doc files found ...")`` path
    (``main()`` ~:621-627), independent of, and unrelated to, the
    .gitignore-unreadable branch under regression above.

    Wrong outcome this pins against: the fix broadening its label change to
    the fatal helper too (silently swallowing the genuine blocking verdict
    behind a softer word) -- that wrong outcome is asserted NOT produced.
    Green today (control) and must remain green after the fix.
    """
    exit_code, combined = _run_gate(["--repo", str(tmp_path)], capsys)

    assert exit_code == 2, (
        "a repo with zero doc files must hit the genuine fatal "
        f"indeterminate verdict (exit 2); got exit_code={exit_code}, "
        f"output={combined!r}"
    )
    assert "INDETERMINATE" in combined, (
        "the genuine fatal indeterminate verdict must still say "
        f"'INDETERMINATE' -- the gitignore-label fix must not downgrade "
        f"the real blocking path; output={combined!r}"
    )
