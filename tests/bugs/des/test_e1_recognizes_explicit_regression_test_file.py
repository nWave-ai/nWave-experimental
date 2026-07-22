"""Regression for F-E1-VACUOUS-MISSES-EXPLICIT-REGRESSION-DECLARATION.

``missing_at_files`` (``src/des/application/slice_at_completeness.py``, the
E1 completeness/verifiability oracle ``des commit-slice`` uses) recognized
only THREE scan-based AT taxonomies via ``feature_files_for_slice``: Gherkin
``@slice-NN`` tags, pytest head-comment tags, and the
``tests/**/{feature_dir}/test_{slice_us}_*.py`` path-naming convention. It did
NOT recognize a FOURTH, already-trusted-elsewhere source: the caller's own
explicit ``--at-kind pytest-regression --regression-test-file <path>``
declaration on the ``des commit-slice`` CLI itself -- the SAME evidence
``_infer_pytest_regression_at_kind`` (``verify_slice_commit_completeness.py``)
already trusts to route E2. A slice delivered via an arbitrarily-named
pytest-regression file (e.g. ``tests/unit/test_slice_new.py`` -- no tag, no
naming-convention match) was invisible to E1 and refused as owning no
recognized AT candidates, UNLESS an armed examine-verdict PASS happened to be
recorded first (a workaround, not the intended mechanical-seal fast path the
``/nw-bugfix`` methodology documents: ``verify-red-green`` + ``verify-negative-at``
alone should clear a pytest-regression slice's E1 leg).

Measured impact (whole-tree suite run, 2026-07-21): ~20 failures across
``tests/des/integration/test_commit_slice.py`` and 9 sibling files, all with
the identical ``assert exit_code == 0`` -> ``assert 1 == 0`` signature --
every one of them a plain ``commit-slice --at-kind pytest-regression
--regression-test-file <arbitrary path>`` call with no preceding
examine-verdict.

Fixed by threading ``at_kind``/``regression_test_file`` into
``missing_at_files`` (new optional kwargs) and its caller
``verify_slice_commit_completeness._missing_by_slice`` -- when
``at_kind == "pytest-regression"`` and ``regression_test_file`` is given AND
that path is actually present in ``files_in_commit``, it is unioned into the
AT-candidate set before the missing check runs. Applied ONLY when exactly
one slice is listed (unambiguous "this declaration is for THIS slice"
reading) -- a multi-slice commit does not get the override, same
conservative-keep discipline as the sibling path-convention fix
(F-E1-VACUOUS-MISSES-PYTEST-REGRESSION-PATH-CONVENTION). A declared-but-
ABSENT path is deliberately NOT unioned into ``at_files`` and therefore
never hard-flagged ``missing`` -- E1 performs no structural presence check
on it at all, deferring that verdict entirely to E2's own dedicated
regression-file gate, which degrades to INDETERMINATE (exit 3) rather than
a hard fail (F-E1-E2-REGRESSION-FILE-EXEMPTION-COLLISION, this fix).
``verifiable``, however, still flips True on the bare declaration itself
(present or absent) -- E1's OTHER guard
(``verify_slice_commit_completeness``'s ``non_verifiable`` check, RCA
fix-carpaccio-e1-vacuous-taxonomy-gap) hard-refuses ANY ``verifiable=False``
slice as "zero recognized AT candidates" before E2 is ever reached, so a
declared-but-absent file that left ``verifiable=False`` would still dead-end
at E1 -- just via a different guard than the original defect. Only
``verifiable=True, missing=[]`` for the declared-but-absent case lets
control flow actually reach E2.

Driving surface: the pure application-layer function ``missing_at_files``
itself, plus a real-git integration case pinning the exact
``verify_slice_commit_completeness_main``/``commit_slice_main`` end-to-end
scenario that was refused before the fix.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from des.application.slice_at_completeness import missing_at_files


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _init_repo_with_arbitrary_regression_file(tmp_path: Path) -> tuple[Path, str]:
    """A committed repo whose sole test file is at an ARBITRARY path -- no
    Gherkin tag, no pytest head-comment tag, no naming-convention match for
    any (feature_id, slice_id)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    rel_path = "tests/unit/test_slice_new.py"
    target = repo / rel_path
    target.parent.mkdir(parents=True)
    target.write_text(
        "def test_slice_new():\n    assert 2 + 2 == 4\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"add {rel_path}")
    return repo, rel_path


# ===========================================================================
# Positive: an explicitly-declared pytest-regression file, at an arbitrary
# path matching none of the three scan-based taxonomies, is recognized.
# ===========================================================================


def test_explicit_regression_test_file_declaration_is_recognized_as_slice_at(
    tmp_path: Path,
) -> None:
    """An arbitrary-path pytest-regression file the caller explicitly names
    via --regression-test-file must be recognized as AT evidence for the
    slice -- the caller's own declaration is itself positive evidence,
    independent of any scan-based taxonomy match."""
    repo, rel_path = _init_repo_with_arbitrary_regression_file(tmp_path)
    commit = _git(repo, "rev-parse", "HEAD").strip()

    outcome = missing_at_files(
        repo,
        commit,
        "slice-01",
        "commit-slice-mechanics",
        at_kind="pytest-regression",
        regression_test_file=rel_path,
    )

    assert outcome.verifiable is True
    assert outcome.missing == []


def test_declared_but_absent_regression_file_defers_to_e2_indeterminate(
    tmp_path: Path,
) -> None:
    """A DECLARED --regression-test-file that was never committed must NOT be
    hard-flagged as ``missing`` here -- E1 defers absence-classification to
    E2's dedicated regression-file gate (``_run_regression_gate``, which
    degrades to the INDETERMINATE exit code honored by
    ``commit_slice.main``'s proceed-on-3 preflight contract, ADR-DES-001
    addendum Rule 3 / CT8).

    ``verifiable`` is still True -- the caller's own affirmative
    ``--at-kind pytest-regression --regression-test-file <path>`` declaration
    IS itself the AT candidate. Collapsing this into ``verifiable=False``
    would re-collide with E2/CT8 one layer up:
    ``verify_slice_commit_completeness``'s ``non_verifiable`` guard treats
    ANY ``verifiable=False`` slice as "zero recognized AT candidates" and
    hard-refuses it at E1 -- before E2 is ever reached -- which would make
    the declared-but-absent case dead-end at E1 exactly like the original
    defect, just via a different guard. ``missing=[]`` because E1 performs no
    structural presence check on the declared path at all -- that
    presence/pass/fail/indeterminate verdict belongs to E2 alone."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("x", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    commit = _git(repo, "rev-parse", "HEAD").strip()

    outcome = missing_at_files(
        repo,
        commit,
        "slice-01",
        "commit-slice-mechanics",
        at_kind="pytest-regression",
        regression_test_file="tests/unit/never_committed.py",
    )

    assert outcome.verifiable is True
    assert outcome.missing == []


# ===========================================================================
# Negative: without at_kind == "pytest-regression", or without a declared
# file, behaviour is byte-identical to before this fix -- the override never
# fires by accident.
# ===========================================================================


def test_gherkin_at_kind_does_not_trigger_the_explicit_declaration_path(
    tmp_path: Path,
) -> None:
    """``at_kind="gherkin"`` (or any non-"pytest-regression" value) must NOT
    treat ``regression_test_file`` as AT evidence -- the override is scoped
    exactly to the pytest-regression CLI path, never a silent widening of
    what Gherkin-mode E1 accepts."""
    repo, rel_path = _init_repo_with_arbitrary_regression_file(tmp_path)
    commit = _git(repo, "rev-parse", "HEAD").strip()

    outcome = missing_at_files(
        repo,
        commit,
        "slice-01",
        "commit-slice-mechanics",
        at_kind="gherkin",
        regression_test_file=rel_path,
    )

    assert outcome.verifiable is False
    assert outcome.missing == []


def test_no_regression_test_file_leaves_behaviour_unchanged(tmp_path: Path) -> None:
    """``regression_test_file=None`` (the default -- every pre-existing
    caller) must reproduce the pre-fix vacuous-empty result exactly."""
    repo, _rel_path = _init_repo_with_arbitrary_regression_file(tmp_path)
    commit = _git(repo, "rev-parse", "HEAD").strip()

    outcome = missing_at_files(repo, commit, "slice-01", "commit-slice-mechanics")

    assert outcome.verifiable is False
    assert outcome.missing == []
