"""Regression: `des verify-doc-coherence` must NOT flag EXAMPLE paths in
forward-looking doc classes (docs/requirements/ and siblings) as false
claims -- it must keep flagging real lies in PROMISE docs (README, guides).

RCA (grounded in ``src/des/cli/verify_doc_coherence.py``):

    - Lines 150-169: ``_NOT_CURRENT_CLAIM_DOC_PREFIXES`` is the frozenset of
      repo-relative doc-class prefixes the DEFAULT scan (``--docs`` omitted)
      DROPS -- because they are structurally not claims about the current
      tree (``docs/feature/``, ``docs/analysis/``, ``docs/proposals/``,
      ``docs/adrs/``, ``docs/product/expectations/``, ...).
    - ``_is_not_current_claim_doc`` (~:172) does
      ``rel_posix.startswith(prefix)`` over that set; called from
      ``_find_doc_files`` (~:232) to filter the default scan.
    - THE DEFECT: ``docs/requirements/`` (and forward-looking siblings
      ``docs/backlog/``, ``docs/rfc/``, ``docs/spike/``, ``docs/decisions/``)
      are NOT in the set, even though they are the SAME structural class as
      ``docs/proposals/`` / ``docs/feature/`` already exempted -- so the
      default scan scans ``docs/requirements/`` and flags its fictional
      illustrative paths (e.g. ``src/auth/login.py``) as false claims. On a
      real repo this produced 151 false-claims, 140 of them fictional
      example paths under ``docs/requirements/``.

The intended fix (NOT implemented here, production code untouched): add
``docs/requirements/`` (+ siblings) to ``_NOT_CURRENT_CLAIM_DOC_PREFIXES``.

Fault-injection is BIDIRECTIONAL in one repo shape: a fictional path in
``docs/requirements/`` (forward-looking, example) must be SKIPPED; a
fictional path in ``README.md`` (promise doc) must STILL be flagged -- the
fix must not blind the gate to real lies in promise docs.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.verify_doc_coherence.main()`` CLI driver, captured via
``capsys`` -- mirrors the sibling regression AT
``tests/bugs/des/test_doc_coherence_unreadable_loud.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli.verify_doc_coherence import main as verify_doc_coherence_main


# Distinct fictional paths per doc, so each assertion is unambiguous about
# which doc's claim it is checking.
_REQUIREMENTS_FAKE_PATH = "src/auth/login.py"
_README_FAKE_PATH = "tests/does_not_exist_yet.py"


def _build_repo(tmp_path: Path) -> Path:
    """A repo with BOTH a forward-looking requirements doc (illustrative
    example path) and a README promise doc (a real, checkable lie).

    ``src/`` and ``tests/`` top-level dirs must exist in the tree for their
    paths to qualify as *checkable* claims at all (the example-tree guard in
    ``_is_checkable_path_claim`` skips paths whose top-level dir is absent)
    -- but the specific files named inside those dirs (``src/auth/login.py``,
    ``tests/does_not_exist_yet.py``) do NOT exist, so both are genuinely
    false claims of "this file exists in the tree" if actually checked.
    """
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "placeholder.py").write_text(
        "# real file, unrelated to the claimed path\n", encoding="utf-8"
    )
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "placeholder_test.py").write_text(
        "# real file, unrelated to the claimed path\n", encoding="utf-8"
    )

    requirements_dir = repo / "docs" / "requirements"
    requirements_dir.mkdir(parents=True)
    (requirements_dir / "backlog.md").write_text(
        "## Login feature backlog\n\n"
        f"Example module layout for the login flow: `{_REQUIREMENTS_FAKE_PATH}`.\n",
        encoding="utf-8",
    )

    (repo / "README.md").write_text(
        f"# Project\n\nRun the client-side entry point at `{_README_FAKE_PATH}`.\n",
        encoding="utf-8",
    )
    return repo


def _run_gate(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    """Drive the REAL ``des verify-doc-coherence`` CLI (``main()``)
    in-process, default scan (no ``--docs``). Returns
    ``(exit_code, combined_stdout_stderr)``.
    """
    exit_code = verify_doc_coherence_main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out + captured.err


# ===========================================================================
# POSITIVE AT -- active-RED today
# ===========================================================================


def test_requirements_example_path_is_not_flagged_as_false_claim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``docs/requirements/`` is a forward-looking, example-bearing doc class
    -- the same structural class as ``docs/proposals/`` / ``docs/feature/``,
    already exempted from the default scan. The default scan must skip it
    and never flag its illustrative paths as claims about the current tree.

    RED today: ``docs/requirements/`` is absent from
    ``_NOT_CURRENT_CLAIM_DOC_PREFIXES``, so the default scan includes
    ``docs/requirements/backlog.md`` and flags ``src/auth/login.py`` as a
    false claim -- a semantic ``AssertionError`` below, not a crash.
    """
    repo = _build_repo(tmp_path)

    exit_code, combined = _run_gate(["--repo", str(repo)], capsys)

    requirements_doc_named = "docs/requirements/backlog.md" in combined
    requirements_fake_path_named = _REQUIREMENTS_FAKE_PATH in combined

    assert not requirements_doc_named and not requirements_fake_path_named, (
        "docs/requirements/ is a forward-looking example doc class (same "
        "structural class as docs/proposals/ / docs/feature/, already "
        "exempted from the default scan) -- its illustrative "
        f"`{_REQUIREMENTS_FAKE_PATH}` path must NOT be reported as a false "
        "claim. Got requirements_doc_named="
        f"{requirements_doc_named}, requirements_fake_path_named="
        f"{requirements_fake_path_named}, exit_code={exit_code}, "
        f"output={combined!r}"
    )


# ===========================================================================
# NEGATIVE AT -- control, must STAY green before AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_readme_promise_with_fake_path_is_still_flagged(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``README.md`` is a PROMISE doc -- a fictional path named there is a
    real lie about the current tree and MUST still be flagged as a false
    claim. Proves the fix (exempting docs/requirements/) does not blind the
    gate to genuine lies in promise docs -- no over-correction.

    Must stay GREEN both before and after the production fix: the README
    violation is orthogonal to the requirements-doc exemption.
    """
    repo = _build_repo(tmp_path)

    exit_code, combined = _run_gate(["--repo", str(repo)], capsys)

    readme_named = "README.md" in combined
    readme_fake_path_named = _README_FAKE_PATH in combined

    assert exit_code != 0 and readme_named and readme_fake_path_named, (
        "README.md is a promise doc -- its fictional "
        f"`{_README_FAKE_PATH}` path must still be reported as a false "
        f"claim (exit != 0). Got exit_code={exit_code}, readme_named="
        f"{readme_named}, readme_fake_path_named={readme_fake_path_named}, "
        f"output={combined!r}"
    )
