"""Regression for F-E1-VACUOUS-MISSES-PYTEST-REGRESSION-PATH-CONVENTION.

``feature_files_for_slice`` (``src/des/application/slice_at_completeness.py``,
the E1 completeness/verifiability oracle used by ``des commit-slice``)
recognized only two AT taxonomies for a slice: (1) Gherkin ``.feature`` files
tagged ``@slice-NN``, and (2) pytest files head-comment-tagged
``@feature-{id}``/``@slice-NN``. It did NOT recognize the THIRD,
already-established taxonomy: the pytest-regression PATH-NAMING convention
``des/cli/verify_slice_commit_completeness.py::_infer_pytest_regression_at_kind``
already trusts elsewhere in the same gate -- a file at
``tests/**/{feature_dir}/test_{slice_us}_*.py`` (feature_id/slice_id with
hyphens replaced by underscores), with NO head-comment tag required. A slice
using ONLY this path convention read as taxonomy-blind to E1
(``verifiable=False``) even though it is a legitimate, established AT.

Fixed by extending ``feature_files_for_slice``: when ``feature_id`` is given,
after the existing Gherkin + pytest-tag matching, it now ALSO calls
``_regression_file_glob_candidates`` and -- if EXACTLY ONE file matches --
adds it to the matched set. Zero matches add no signal (unchanged); 2+
matches (ambiguous) also add no signal, deliberately left for E2's own
dedicated ambiguity refusal (``_infer_pytest_regression_at_kind``) to
surface -- E1 never silently resolves an ambiguous convention match.

Driving surface (Mandate-13 driving-port-only): the pure application-layer
function ``feature_files_for_slice`` itself -- no git repo required (it is a
filesystem-only computation; only ``missing_at_files``/``files_in_commit``
need a real git commit). The regression-file path is derived through
``canonical_regression_test_path`` -- the SAME producer seam a real caller
(e.g. ``des examine-fixture``) uses -- never hand-constructed, so the test
stays coupled to the actual naming convention instead of a private guess.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.application.slice_at_completeness import (
    canonical_regression_test_path,
    feature_files_for_slice,
)


_FEATURE_ID = "e1-pytest-regression-path-convention-pos"
_SLICE_ID = "slice-01"

_AMBIGUOUS_FEATURE_ID = "e1-pytest-regression-path-convention-ambiguous"
_AMBIGUOUS_SLICE_ID = "slice-01"


def _write_untagged_regression_file(repo: Path, rel_path: str) -> None:
    """A pytest-regression file with NO ``@feature-``/``@slice-NN`` head-comment
    tag -- the taxonomy under test relies purely on the file's PATH, not any
    tag, to be recognized."""
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "def test_trivially_passes():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )


# ===========================================================================
# Positive: exactly one convention-matching file is recognized as the slice's
# AT, with no head-comment tag at all.
# ===========================================================================


def test_single_convention_matching_file_is_recognized_as_slice_at(
    tmp_path: Path,
) -> None:
    """A lone file at the path ``canonical_regression_test_path`` resolves
    for (``_FEATURE_ID``, ``_SLICE_ID``), carrying NO ``@feature-``/
    ``@slice-NN`` tag, must be recognized by ``feature_files_for_slice`` as
    an AT delivering the slice -- the path-naming convention alone is
    sufficient positive evidence (taxonomy 3)."""
    repo = tmp_path / "repo"
    rel_path = canonical_regression_test_path(_FEATURE_ID, _SLICE_ID)
    _write_untagged_regression_file(repo, rel_path)

    matched = feature_files_for_slice(repo, _SLICE_ID, _FEATURE_ID)

    assert rel_path in matched, (
        f"expected the untagged pytest-regression file at the canonical "
        f"path-convention location {rel_path!r} to be recognized as an AT "
        f"for slice {_SLICE_ID!r} of feature {_FEATURE_ID!r} -- "
        f"feature_files_for_slice must trust the path-naming convention "
        f"(taxonomy 3) exactly as _infer_pytest_regression_at_kind already "
        f"does elsewhere in the same gate. observed matched={matched!r}"
    )


# ===========================================================================
# Negative: an AMBIGUOUS convention match (2+ files) must never be silently
# resolved here -- E1 adds no signal, left for E2's dedicated refusal.
# ===========================================================================


@pytest.mark.negative_at
def test_ambiguous_convention_match_adds_no_signal(tmp_path: Path) -> None:
    """Two files BOTH matching the slice's path-naming convention (differing
    only by the ``suffix`` component ``canonical_regression_test_path``
    exposes) must NOT be silently resolved by ``feature_files_for_slice`` --
    neither is added as recognized AT evidence via taxonomy 3. This proves
    the fix does not overreach: an ambiguous match is left for E2's own
    dedicated ambiguity refusal (``_infer_pytest_regression_at_kind``) to
    surface, never picked-one-silently here."""
    repo = tmp_path / "repo"
    first_path = canonical_regression_test_path(
        _AMBIGUOUS_FEATURE_ID, _AMBIGUOUS_SLICE_ID, suffix="behaviour"
    )
    second_path = canonical_regression_test_path(
        _AMBIGUOUS_FEATURE_ID, _AMBIGUOUS_SLICE_ID, suffix="other"
    )
    _write_untagged_regression_file(repo, first_path)
    _write_untagged_regression_file(repo, second_path)

    matched = feature_files_for_slice(repo, _AMBIGUOUS_SLICE_ID, _AMBIGUOUS_FEATURE_ID)

    assert first_path not in matched and second_path not in matched, (
        f"expected NEITHER ambiguous convention-matching file to be "
        f"silently resolved as slice AT evidence via taxonomy 3 -- an "
        f"ambiguous path-convention match (2+ candidates) must add no "
        f"signal here, left for E2's dedicated ambiguity refusal to "
        f"surface. observed matched={matched!r}, "
        f"candidates=[{first_path!r}, {second_path!r}]"
    )
