"""Regression AT: a shared multi-slice pytest AT file must resolve EVERY
declared slice, not only the first one its head-comment block names.

RCA (verified twice independently). A shared acceptance file can declare
several slices in one head-comment block::

    # @feature-an-example-feature
    # @slice-02
    # @slice-03
    # @slice-04
    # @slice-05
    # @slice-06
    # @slice-07
    \"\"\"docstring...\"\"\"

``resolve_test_file_attribution`` (``des.application.feature_at_files``,
~lines 247-262) resolves ``slice_id`` via
``_SLICE_SUBTAG_RE.search(window)`` -- ``.search()`` returns only the FIRST
match, so a six-slice head window collapses to ``slice-02``. ``covers`` is
resolved via ``_COVERS_SUBTAG_RE.finditer(window)`` (plural, correct) --
that finditer/search asymmetry is the root cause. Downstream,
``des.application.slice_at_completeness.feature_files_for_slice`` does
``if attribution.slice_id == slice_id`` (line 213) -- every slice after the
first contributes zero AT candidates, and ``des check-slice-at-completeness``
reports the ``SliceAtCompletenessIndeterminate`` verdict (exit code 3) for a
slice that in fact has a real, committed AT.

This file pins the OBSERVABLE outcome -- which slices resolve to which
files via ``feature_files_for_slice``/``missing_at_files``, and the
completeness verdict itself -- rather than any particular new accessor
shape on ``TestFileAttribution``, so the fix (additive per the module's own
"ADD-not-mutate" discipline) retains design freedom.

Contract shape: bounded-change. Layer 6 unit/PBT composition (pure,
read-only filesystem functions for the ``feature_files_for_slice`` legs, no
git dependency; the ``missing_at_files`` leg uses a real temp git repo, same
convention as
``tests/des/acceptance/reverify_e1_via_scoped_wrapper/
test_slice_01_pure_function_scoping.py``). Located under
``tests/des/unit/application/`` -- NOT the Mandate-13-restricted
``tests/des/unit/(?:domain|cli)/*`` path (sibling precedent:
``test_feature_files_for_slice_pytest_discovery.py``,
``test_feature_files_for_slice_hardening_gaps.py``).

Active-RED (Mandate-7 / ADR-025): ``feature_files_for_slice`` and
``resolve_test_file_attribution`` are shipped, unscaffolded production code
-- the RED here is a genuine behavioral gap (semantic ``AssertionError`` on
the missing-recognition assertion), never an import/collection error.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from des.application.feature_at_files import resolve_test_file_attribution
from des.application.slice_at_completeness import (
    feature_files_for_slice,
    missing_at_files,
)


_FEATURE_ID = "fix-multi-slice-shared-at-file"
_OTHER_FEATURE_ID = "fix-other-feature-shares-slice-tag"

#: One shared pytest AT file declaring several slices in its head-comment block.
_SHARED_SLICE_IDS = (
    "slice-02",
    "slice-03",
    "slice-04",
    "slice-05",
    "slice-06",
    "slice-07",
)


def _write_shared_at_file(
    repo: Path,
    feature_id: str,
    slice_ids: tuple[str, ...],
    *,
    covers: tuple[str, ...] = (),
    filename: str = "test_shared_slices.py",
) -> Path:
    """A single pytest AT file head-tagged with MULTIPLE ``@slice-NN`` lines
    -- the exact real convention this defect reproduces, not a synthetic
    shape invented for the test.
    """
    target = repo / "tests" / feature_id / "acceptance" / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# @feature-{feature_id}"]
    lines += [f"# @{slice_id}" for slice_id in slice_ids]
    lines += [f"# @covers-{row}" for row in covers]
    header = "\n".join(lines) + "\n"
    body = (
        '"""docstring for the shared multi-slice AT file."""\n\n'
        "def test_something():\n    assert True\n"
    )
    target.write_text(header + body, encoding="utf-8")
    return target


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout


# ---------------------------------------------------------------------------
# 1. POSITIVE -- every declared slice resolves to the shared file, not only
#    the first-declared one.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slice_id", _SHARED_SLICE_IDS)
def test_shared_at_file_resolves_every_declared_slice(
    tmp_path: Path, slice_id: str
) -> None:
    shared = _write_shared_at_file(tmp_path, _FEATURE_ID, _SHARED_SLICE_IDS)

    found = feature_files_for_slice(tmp_path, slice_id, _FEATURE_ID)

    assert str(shared.relative_to(tmp_path)) in found, (
        f"a shared AT file head-tagged with {_SHARED_SLICE_IDS!r} must "
        f"resolve EVERY declared slice, including {slice_id!r} (not only "
        f"the first {_SHARED_SLICE_IDS[0]!r}); got found={found!r} for "
        f"slice_id={slice_id!r} -- resolve_test_file_attribution's "
        "slice_id resolution uses re.search (first match only), the exact "
        "asymmetry the plural 'covers' resolution (re.finditer) does not "
        "have"
    )


# ---------------------------------------------------------------------------
# 2. NEGATIVE -- a single-slice file keeps resolving to exactly its one
#    slice (no behaviour change for the already-correct common case).
# ---------------------------------------------------------------------------


def test_single_slice_file_still_resolves_to_its_one_slice(tmp_path: Path) -> None:
    single = _write_shared_at_file(
        tmp_path, _FEATURE_ID, ("slice-01",), filename="test_single_slice.py"
    )

    found = feature_files_for_slice(tmp_path, "slice-01", _FEATURE_ID)

    assert str(single.relative_to(tmp_path)) in found, (
        "a single-slice AT file must keep resolving to its one declared "
        f"slice after the multi-slice fix; got found={found!r}"
    )


# ---------------------------------------------------------------------------
# 3. NEGATIVE -- a slice no file declares still resolves to NOTHING (the
#    fix must not start over-matching / become permissive).
# ---------------------------------------------------------------------------


def test_slice_not_declared_by_any_file_resolves_to_nothing(tmp_path: Path) -> None:
    _write_shared_at_file(tmp_path, _FEATURE_ID, _SHARED_SLICE_IDS)

    found = feature_files_for_slice(tmp_path, "slice-99", _FEATURE_ID)

    assert found == [], (
        "a slice that no file declares must resolve to NOTHING -- the fix "
        f"must not start over-matching; got found={found!r}"
    )


# ---------------------------------------------------------------------------
# 4. NEGATIVE -- a @slice-NN tag belonging to a DIFFERENT feature's file
#    must not cross-bind into this feature's completeness check.
# ---------------------------------------------------------------------------


def test_slice_tag_from_different_feature_file_does_not_cross_bind(
    tmp_path: Path,
) -> None:
    _write_shared_at_file(
        tmp_path,
        _FEATURE_ID,
        ("slice-03", "slice-04"),
        filename="test_primary_shared.py",
    )
    other = _write_shared_at_file(
        tmp_path,
        _OTHER_FEATURE_ID,
        ("slice-02",),
        filename="test_other_feature.py",
    )

    found = feature_files_for_slice(tmp_path, "slice-02", _FEATURE_ID)

    assert str(other.relative_to(tmp_path)) not in found, (
        "a @slice-NN tag on a DIFFERENT feature's file must never "
        f"cross-bind into this feature's completeness check; got "
        f"found={found!r}"
    )
    assert found == [], (
        f"feature {_FEATURE_ID!r} declares no slice-02 file of its own; found={found!r}"
    )


# ---------------------------------------------------------------------------
# 5. NEGATIVE -- the `covers` tuple keeps its current, correct plural
#    behaviour untouched by the slice_id fix.
# ---------------------------------------------------------------------------


def test_covers_tuple_resolution_stays_plural_and_unaffected(tmp_path: Path) -> None:
    shared = _write_shared_at_file(
        tmp_path, _FEATURE_ID, _SHARED_SLICE_IDS, covers=("R1", "R2", "R3")
    )

    attribution = resolve_test_file_attribution(shared)

    assert attribution.covers == ("R1", "R2", "R3"), (
        "the covers tuple's plural resolution (re.finditer) must remain "
        f"unaffected by the slice_id fix; got covers={attribution.covers!r}"
    )


# ---------------------------------------------------------------------------
# 6. End-to-end -- the real user-visible symptom: `des
#    check-slice-at-completeness` (wrapping `missing_at_files`) must not
#    report the indeterminate verdict for a non-first slice of a shared
#    multi-slice AT file.
# ---------------------------------------------------------------------------


def test_shared_at_file_verdict_not_indeterminate_for_non_first_slice(
    tmp_path: Path,
) -> None:
    """This is the observable, user-facing defect
    (``SliceAtCompletenessIndeterminate``) -- pinned at the SAME module
    (``slice_at_completeness.missing_at_files``) the CLI wraps, not only at
    the lower-level resolver.
    """
    repo = tmp_path
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "commit", "--allow-empty", "-q", "-m", "chore: base")

    shared = _write_shared_at_file(repo, _FEATURE_ID, _SHARED_SLICE_IDS)
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        "feat: shared multi-slice AT\n\nSlice-Id: slice-02\n",
    )
    commit = _git(repo, "rev-parse", "HEAD").strip()

    # Farthest from the first-matched slice -- never accidentally green by
    # luck of ordering.
    non_first_slice = _SHARED_SLICE_IDS[-1]

    outcome = missing_at_files(repo, commit, non_first_slice, _FEATURE_ID)

    assert outcome.verifiable is True, (
        f"slice {non_first_slice!r} has a real, committed AT (the shared "
        f"file {shared.name!r}) -- `des check-slice-at-completeness` must "
        "not report SliceAtCompletenessIndeterminate for it; "
        f"outcome={outcome!r}"
    )
    assert outcome.missing == [], (
        f"the shared AT file is committed -- {non_first_slice!r} must not "
        f"be reported missing; outcome={outcome!r}"
    )
