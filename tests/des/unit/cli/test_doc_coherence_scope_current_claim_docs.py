"""Regression AT (#61, feature-delta:
``doc-coherence-scope-current-claim-docs``) -- ``des verify-doc-coherence``
DEFAULT scan (no ``--docs``) must SKIP structurally-not-current-tree-claim
doc classes (tutorials under ``docs/guides/tutorial-*/``, feature-deltas
under ``docs/feature/``, ...) while STILL flagging a real defect in
``docs/reference/`` and README* at repo root.

THE DEFECT (found in ``src/des/cli/verify_doc_coherence.py``
``_find_doc_files`` ~:174): the ``docs is None`` (default) branch collects
README* + ``docs/**/*.md`` unconditionally -- it does not distinguish a
forward-looking tutorial/feature-delta doc (which legitimately names paths
that do not yet exist in the tree) from a doc that claims to describe the
CURRENT tree. On this repo that produced 1559 false-positives, blocking
every feature's feature-end.

THE FIX (charter, NOT implemented here -- a crafter implements): add a
module-level ``_NOT_CURRENT_CLAIM_DOC_PREFIXES`` frozenset (``docs/feature/``,
``docs/analysis/``, ``docs/internal/``, ``docs/archive/``, ``docs/research/``,
``docs/evolution/``, ``docs/scenarios/``, ``docs/reports/``,
``docs/proposals/``, ``docs/adrs/``, ``docs/architecture/``,
``docs/product/architecture/``) PLUS a tutorial-subdir rule (any path segment
matching ``tutorial-*`` under ``docs/guides/``). Filter the ``docs is None``
branch's collected set to drop any doc under those prefixes/rule. An
EXPLICIT ``--docs`` stays byte-unchanged (operator override). README* at
repo root is ALWAYS scanned. The existing not-current-Status skip in
``_scan_doc`` (``_doc_declares_itself_not_current``) is a separate, orthogonal
filter -- untouched by this fix.

Driving surface (Mandate-16 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.verify_doc_coherence.main()`` CLI driver, captured via
``capsys`` -- mirrors the sibling regression ATs
``tests/des/unit/cli/test_verify_doc_coherence.py`` and
``tests/bugs/des/test_doc_coherence_unreadable_loud.py``.

Fixture repo (one ``src/`` dir so every dead path below is a CHECKABLE claim
per ``_is_checkable_path_claim``'s top-level-exists guard, and none of the
four planted paths actually exist under ``src/`` so each is a genuine dead
claim):

    README.md                                -> `src/readme_dead.py`   (KEEP flagging: always-scanned)
    docs/guides/tutorial-x/README.md          -> `src/calc.py`          (DROP: tutorial)
    docs/feature/f/feature-delta.md           -> `src/planned.py`       (DROP: feature-delta)
    docs/reference/commands/index.md          -> `src/gone.py`          (KEEP flagging: real defect)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_doc_coherence import main as verify_doc_coherence_main


def _build_scoped_doc_repo(repo: Path) -> None:
    """Given: a repo with one dead path claim per structurally-different doc
    class -- shared setup reused (chained narrative, Pillar 2) across every
    scenario below; only the ``When`` (the ``--docs`` argv) differs per test.
    """
    (repo / "src").mkdir()
    (repo / "src" / "__init__.py").write_text("")

    (repo / "README.md").write_text(
        "# Demo Project\n\nSee the entry point at `src/readme_dead.py` for details.\n"
    )

    tutorial_dir = repo / "docs" / "guides" / "tutorial-x"
    tutorial_dir.mkdir(parents=True)
    (tutorial_dir / "README.md").write_text(
        "# Tutorial: Build a Calculator\n\n"
        "Create a file `src/calc.py` and add your calculator logic there.\n"
    )

    feature_dir = repo / "docs" / "feature" / "f"
    feature_dir.mkdir(parents=True)
    (feature_dir / "feature-delta.md").write_text(
        "# Feature Delta\n\n"
        "This feature adds `src/planned.py` to implement the command.\n"
    )

    reference_dir = repo / "docs" / "reference" / "commands"
    reference_dir.mkdir(parents=True)
    (reference_dir / "index.md").write_text(
        "# Command Reference\n\nThe gone module lives at `src/gone.py`.\n"
    )


@pytest.fixture()
def scoped_doc_repo(tmp_path: Path) -> Path:
    _build_scoped_doc_repo(tmp_path)
    return tmp_path


def _run_gate(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    exit_code = verify_doc_coherence_main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out + captured.err


def _refused_violations(combined: str) -> list[dict[str, object]]:
    """The ``DocCoherenceRefused`` event's violations list, or [] when the
    scan found nothing to refuse."""
    for line in combined.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and "DocCoherenceRefused" in stripped:
            payload = json.loads(stripped)
            violations = payload.get("violations", [])
            assert isinstance(violations, list)
            return violations
    return []


def _claim_doc_pairs(violations: list[dict[str, object]]) -> set[tuple[str, str]]:
    return {(str(v["doc_file"]), str(v["claim"])) for v in violations}


# ===========================================================================
# ACTIVE-RED -- fail today (whole-tree scan flags forward-looking docs)
# ===========================================================================


def test_default_scan_skips_tutorial_dead_path(
    scoped_doc_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The DEFAULT (no ``--docs``) scan must NOT flag the tutorial's
    reader-example path ``src/calc.py`` -- a tutorial names paths the READER
    will create, not a claim about this repo's current tree.

    RED today: ``_find_doc_files`` collects ``docs/guides/tutorial-x/README.md``
    unconditionally in the default branch, so ``src/calc.py`` IS flagged --
    a false-positive of exactly the class this feature removes.
    """
    exit_code, combined = _run_gate(["--repo", str(scoped_doc_repo)], capsys)

    pairs = _claim_doc_pairs(_refused_violations(combined))
    tutorial_flagged = ("docs/guides/tutorial-x/README.md", "src/calc.py") in pairs

    assert not tutorial_flagged, (
        "the default scan must SKIP the tutorial doc's forward-looking "
        "example path -- it is not a claim about the current tree; "
        f"exit_code={exit_code}, violations={pairs!r}"
    )


def test_default_scan_skips_feature_delta_dead_path(
    scoped_doc_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The DEFAULT scan must NOT flag a feature-delta's PLANNED path
    ``src/planned.py`` -- a feature-delta names paths a future slice will
    create, not a claim about the current tree.

    RED today: the default branch scans ``docs/feature/**/*.md``
    unconditionally, so ``src/planned.py`` IS flagged -- a false-positive.
    """
    exit_code, combined = _run_gate(["--repo", str(scoped_doc_repo)], capsys)

    pairs = _claim_doc_pairs(_refused_violations(combined))
    feature_delta_flagged = (
        "docs/feature/f/feature-delta.md",
        "src/planned.py",
    ) in pairs

    assert not feature_delta_flagged, (
        "the default scan must SKIP the feature-delta's planned path -- it "
        "is not a claim about the current tree; "
        f"exit_code={exit_code}, violations={pairs!r}"
    )


# ===========================================================================
# NEGATIVE / KEEP-THE-VALUE controls -- must stay green BEFORE and AFTER the
# fix (the scope-narrowing must not eat the gate's real catching power, and
# must not touch the explicit-override / README-always-scanned contracts).
# ===========================================================================


@pytest.mark.negative_at
def test_default_scan_still_flags_reference_doc_dead_path(
    scoped_doc_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """KEEP-the-value control: ``docs/reference/`` is auto-generated FROM the
    code -- a dead path there is a REAL defect and must stay caught by the
    default scan, both before and after the scope-narrowing fix.
    """
    exit_code, combined = _run_gate(["--repo", str(scoped_doc_repo)], capsys)

    pairs = _claim_doc_pairs(_refused_violations(combined))
    reference_flagged = (
        "docs/reference/commands/index.md",
        "src/gone.py",
    ) in pairs

    assert exit_code == 1 and reference_flagged, (
        "a docs/reference/ doc lying about the current code is a real "
        "defect and must still be flagged by the default scan -- got "
        f"exit_code={exit_code}, violations={pairs!r}"
    )


@pytest.mark.negative_at
def test_explicit_docs_override_still_scans_tutorial_not_skipped(
    scoped_doc_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Non-regression control: an EXPLICIT ``--docs docs/guides/tutorial-x``
    is the operator's choice of scope and stays byte-unchanged -- the
    tutorial's dead path is still scanned and flagged verbatim, it is NOT
    silently skipped just because it lives under a tutorial-* subdir.
    """
    exit_code, combined = _run_gate(
        ["--repo", str(scoped_doc_repo), "--docs", "docs/guides/tutorial-x"],
        capsys,
    )

    pairs = _claim_doc_pairs(_refused_violations(combined))
    tutorial_flagged = ("docs/guides/tutorial-x/README.md", "src/calc.py") in pairs

    assert exit_code == 1 and tutorial_flagged, (
        "an explicit --docs override must scan verbatim -- the tutorial's "
        "dead path must still be flagged, not silently skipped, when the "
        f"operator names it directly; exit_code={exit_code}, "
        f"violations={pairs!r}"
    )


@pytest.mark.negative_at
def test_readme_dead_path_not_skipped_by_default(
    scoped_doc_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Non-regression control: README* at repo root is ALWAYS scanned -- a
    top-level claim about the actual repo, never exempted by the
    not-current-tree-claim scoping.
    """
    exit_code, combined = _run_gate(["--repo", str(scoped_doc_repo)], capsys)

    pairs = _claim_doc_pairs(_refused_violations(combined))
    readme_flagged = ("README.md", "src/readme_dead.py") in pairs

    assert exit_code == 1 and readme_flagged, (
        "README* at repo root must always be scanned -- its dead path claim "
        f"must not be skipped by default; exit_code={exit_code}, "
        f"violations={pairs!r}"
    )
