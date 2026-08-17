"""Regression AT -- ``des verify-doc-coherence``'s DEFAULT (repo-wide) scan
must NOT read ``docs/product/backlog.md``'s honestly-deferred work entries as
false claims about the current tree.

THE DEFECT (``src/des/cli/verify_doc_coherence.py``): the planning backlog is
a single FILE, ``docs/product/backlog.md``. ``_NOT_CURRENT_CLAIM_DOC_PREFIXES``
already exempts the forward-looking doc CLASSES around it (``docs/backlog/`` --
a directory, not this file -- plus ``docs/feature/``, ``docs/epic/``,
``docs/product/expectations/``, ``docs/product/architecture/``, ...) but not the
backlog file itself, whose entire genre is not-yet-true work: deferred slices,
untracked DISTILLs parked in other worktrees, paths a future feature will
create. ``_find_doc_files``'s default branch therefore collects it and
``_check_path_claims`` flags those honest descriptions.

Reproduced on this repo 2026-07-27 (causal-dispatch-envelope feature-end,
``des feature-end run`` precondition 2 -> ``DocCoherenceRefused``): 4 false
claims, all in ``docs/product/backlog.md``, all describing deliberately
deferred/untracked work the backlog text itself annotates as absent. Because
``feature_end_cycle_service`` invokes the gate with DEFAULT (repo-wide) scope,
this blocks ``des feature-end run`` for EVERY feature in the repo.

THE FIX (not implemented here -- production code untouched by this file): add
``docs/product/backlog.md`` to ``_NOT_CURRENT_CLAIM_DOC_PREFIXES``.

Fault injection is BIDIRECTIONAL in one repo shape, because the scoping fix
must be the FILE and not its folder: a deferred-work path in the backlog is
SKIPPED, while dead claims in ``README.md``, in ``docs/reference/`` and in a
SIBLING ``docs/product/`` doc are all still flagged. Exempting the whole
``docs/product/`` prefix would blind the gate to the product SSOT docs -- a
strictly worse failure than the one being fixed.

Driving surface (Mandate-13 driving-port-only, Layer 3 in-process default):
the REAL ``des.cli.verify_doc_coherence.main()`` CLI driver, captured via
``capsys`` -- mirrors the sibling regression ATs
``tests/bugs/des/test_verify_doc_coherence_skips_example_doc_classes.py`` and
``tests/des/unit/cli/test_doc_coherence_scope_current_claim_docs.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_doc_coherence import main as verify_doc_coherence_main


# Distinct dead paths per doc so every assertion names exactly one claim.
_BACKLOG_DEFERRED_PATH = "docs/feature/cpp-test-runner-adapter/"
_BACKLOG_DEFERRED_TEST_PATH = "tests/des/acceptance/cpp_test_runner_adapter/"
_README_DEAD_PATH = "src/readme_dead.py"
_REFERENCE_DEAD_PATH = "src/reference_gone.py"
_PRODUCT_SIBLING_DEAD_PATH = "src/vision_gone.py"


def _build_repo(tmp_path: Path) -> Path:
    """Given: a repo whose backlog honestly describes work deferred into
    another worktree (naming paths absent from THIS tree), alongside three
    docs that genuinely claim to describe the current tree and each lie.

    ``src/``, ``tests/`` and ``docs/`` exist so every planted path qualifies
    as a *checkable* claim (``_is_checkable_path_claim``'s example-tree guard
    skips spans whose top-level dir is absent); none of the specific files or
    directories named inside them exists, so each is a genuine dead claim.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("")

    (tmp_path / "README.md").write_text(
        f"# Demo Project\n\nThe entry point lives at `{_README_DEAD_PATH}`.\n"
    )

    product_dir = tmp_path / "docs" / "product"
    product_dir.mkdir(parents=True)
    # The backlog's deferred-work entry: accurate prose about work parked in
    # ANOTHER worktree. Deliberately free of the negation/future markers
    # `_NEGATED_LINE_RE` already exempts (NEW / MISSING / TODO / "not yet" /
    # "does not exist" / ...) -- otherwise the line would be skipped for a
    # reason unrelated to the fix under test and this AT would pass hollow.
    (product_dir / "backlog.md").write_text(
        "# Backlog\n\n"
        "### C++ test-runner adapter\n"
        "Status: DEFERRED (2026-07-22) -- DISTILL done, zero implementation.\n\n"
        "The `wt/feat-cpp-runner-adapter` worktree holds a complete DISTILL and "
        f"nothing else: `{_BACKLOG_DEFERRED_PATH}` and "
        f"`{_BACKLOG_DEFERRED_TEST_PATH}` are all UNTRACKED there, zero "
        "commits. Deferred rather than removed, because removing it discards "
        "an entire authored DISTILL.\n"
    )
    # A SIBLING product doc: same folder, but it describes the current tree.
    (product_dir / "vision.md").write_text(
        f"# Vision\n\nThe closed-loop entry point is `{_PRODUCT_SIBLING_DEAD_PATH}`.\n"
    )

    reference_dir = tmp_path / "docs" / "reference" / "commands"
    reference_dir.mkdir(parents=True)
    (reference_dir / "index.md").write_text(
        f"# Command Reference\n\nThe module lives at `{_REFERENCE_DEAD_PATH}`.\n"
    )

    return tmp_path


@pytest.fixture()
def backlog_repo(tmp_path: Path) -> Path:
    return _build_repo(tmp_path)


def _run_gate(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    exit_code = verify_doc_coherence_main(argv)
    captured = capsys.readouterr()
    return exit_code, captured.out + captured.err


def _refused_violations(combined: str) -> list[dict[str, object]]:
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
# ACTIVE-RED -- fails today (the default scan reads the backlog as a promise)
# ===========================================================================


def test_default_scan_skips_backlog_deferred_work_paths(
    backlog_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The DEFAULT (no ``--docs``) scan must NOT flag the backlog's
    deferred-work paths -- the backlog describes work parked elsewhere, never
    a promise about the current tree.

    RED today: ``_find_doc_files`` collects ``docs/product/backlog.md`` in the
    default branch, so both deferred paths ARE flagged -- and because
    feature-end calls the gate at exactly this scope, that refusal blocks
    every feature in the repo.
    """
    exit_code, combined = _run_gate(["--repo", str(backlog_repo)], capsys)

    pairs = _claim_doc_pairs(_refused_violations(combined))
    backlog_flagged = {
        claim for doc, claim in pairs if doc == "docs/product/backlog.md"
    }

    assert not backlog_flagged, (
        "the default scan must SKIP docs/product/backlog.md -- its entries "
        "describe deferred/planned work, not claims about the current tree; "
        f"exit_code={exit_code}, backlog claims flagged={backlog_flagged!r}"
    )


# ===========================================================================
# NEGATIVE / KEEP-THE-VALUE controls -- green BEFORE and AFTER the fix
# ===========================================================================


@pytest.mark.negative_at
def test_default_scan_still_flags_sibling_product_doc_dead_path(
    backlog_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exemption must be the FILE, not its folder: a sibling doc under
    ``docs/product/`` describes the current tree, and a dead path there is a
    real defect. Exempting the whole ``docs/product/`` prefix would blind the
    gate to the product SSOT docs -- worse than the bug being fixed.
    """
    exit_code, combined = _run_gate(["--repo", str(backlog_repo)], capsys)

    pairs = _claim_doc_pairs(_refused_violations(combined))
    sibling_flagged = ("docs/product/vision.md", _PRODUCT_SIBLING_DEAD_PATH) in pairs

    assert exit_code == 1 and sibling_flagged, (
        "a sibling docs/product/ doc lying about the current tree must still "
        f"be flagged -- exit_code={exit_code}, violations={pairs!r}"
    )


@pytest.mark.negative_at
def test_default_scan_still_flags_readme_and_reference_dead_paths(
    backlog_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """KEEP-the-value control: README* at repo root and ``docs/reference/``
    claim the current tree; their dead paths must stay caught.
    """
    exit_code, combined = _run_gate(["--repo", str(backlog_repo)], capsys)

    pairs = _claim_doc_pairs(_refused_violations(combined))

    assert exit_code == 1
    assert ("README.md", _README_DEAD_PATH) in pairs, (
        f"README* must always be scanned; violations={pairs!r}"
    )
    assert ("docs/reference/commands/index.md", _REFERENCE_DEAD_PATH) in pairs, (
        f"docs/reference/ must stay checked; violations={pairs!r}"
    )


@pytest.mark.negative_at
def test_explicit_docs_override_still_scans_the_backlog(
    backlog_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Non-regression control: the exemption is a DEFAULT-scope decision, never
    a permanent blindfold. An operator naming the backlog explicitly
    (``--docs docs/product/backlog.md``) still gets it scanned verbatim.
    """
    exit_code, combined = _run_gate(
        ["--repo", str(backlog_repo), "--docs", "docs/product/backlog.md"],
        capsys,
    )

    pairs = _claim_doc_pairs(_refused_violations(combined))
    backlog_flagged = {
        claim for doc, claim in pairs if doc == "docs/product/backlog.md"
    }

    assert exit_code == 1 and _BACKLOG_DEFERRED_PATH in backlog_flagged, (
        "an explicit --docs override must scan verbatim -- the backlog's dead "
        f"paths must still be flagged; exit_code={exit_code}, "
        f"violations={pairs!r}"
    )
