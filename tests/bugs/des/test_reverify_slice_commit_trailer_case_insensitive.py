"""Regression: `des reverify-slice-commit` trailer match is case-sensitive
and misreports the cause when it fails.

Measured 2026-07-27 (Vera probe, shard drain/defects-a): a commit carrying
`Slice-Id: slice-01` (lowercase) is recognized, while `Slice-Id: Slice-02`
(mixed-case VALUE) is refused with `--slice-id 'slice-02' is not in the
commit's trailer set []` -- the reported set is empty even though the commit
DOES carry the trailer, because ``extract_slice_ids``' shared regex
(``des.domain.slice_id_trailer._SLICE_ID_TRAILER_RE``) requires the trailer
value to already be lowercase `slice-NN` form. The operator reads "this is
not a slice commit" and goes looking for a missing trailer that is, in fact,
present.

Fix locus: ``des.cli._reverify_core._trailer_slice_ids_case_insensitive`` --
a LOCAL (not shared-regex-touching) case-insensitive companion used only by
P2 in ``_preconditions``. The shared ``extract_slice_ids``/
``_SLICE_ID_TRAILER_RE`` consumed by the other gates is untouched by design
(wide blast radius; see the docstring on the fix helper).

Two layers:
  1. Unit -- the pure helper directly (fast, no git).
  2. Regression -- ``_preconditions`` against a REAL throwaway git repo,
     proving a mixed-case `Slice-Id:` trailer no longer collapses into the
     misleading "not in the commit's trailer set []" refusal (P2 passes;
     the run proceeds to a LATER precondition instead).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from des.cli._reverify_core import (
    _preconditions,
    _trailer_slice_ids_case_insensitive,
)


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _init_repo_with_commit(repo: Path, commit_message: str) -> str:
    """Build a real, throwaway git repo with one commit; return its SHA."""
    repo.mkdir(parents=True, exist_ok=True)
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("placeholder\n", encoding="utf-8")
    _run_git(repo, "add", "README.md")
    _run_git(repo, "commit", "-q", "-m", commit_message)
    return _run_git(repo, "rev-parse", "HEAD").strip()


class TestTrailerSliceIdsCaseInsensitiveUnit:
    """Unit: the pure P2 helper recognizes mixed-case trailer VALUES."""

    def test_mixed_case_value_is_recognized_and_normalized(self) -> None:
        found = _trailer_slice_ids_case_insensitive(
            "do the thing\n\nSlice-Id: Slice-02"
        )
        assert found == ["slice-02"]

    def test_uppercase_label_and_value_are_recognized(self) -> None:
        found = _trailer_slice_ids_case_insensitive(
            "do the thing\n\nSLICE-ID: SLICE-03"
        )
        assert found == ["slice-03"]

    def test_lowercase_canonical_trailer_still_recognized(self) -> None:
        found = _trailer_slice_ids_case_insensitive(
            "do the thing\n\nSlice-Id: slice-01"
        )
        assert found == ["slice-01"]

    def test_no_trailer_line_returns_empty(self) -> None:
        found = _trailer_slice_ids_case_insensitive("do the thing with no trailer")
        assert found == []

    def test_duplicate_trailers_collapse_preserving_first_order(self) -> None:
        found = _trailer_slice_ids_case_insensitive(
            "batch\n\nSlice-Id: slice-01\nSlice-Id: Slice-01\nStep-Id: slice-02"
        )
        assert found == ["slice-01", "slice-02"]


class TestReverifyPreconditionsCaseInsensitiveTrailerMatch:
    """Regression: P2 no longer refuses a mixed-case trailer as absent."""

    def test_mixed_case_trailer_passes_p2_reaches_later_precondition(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        commit = _init_repo_with_commit(repo, "do the thing\n\nSlice-Id: Slice-01")

        refusal = _preconditions(repo, "some-feature", "slice-01", commit)

        assert refusal is not None, (
            "expected SOME refusal (no .feature AT in this throwaway repo -- "
            "P4), but the run must get PAST P2 first"
        )
        error = refusal.get("error", "")
        assert "trailer set" not in error, (
            "BUG: a mixed-case Slice-Id trailer must not be refused as "
            f"'not in the commit's trailer set' -- got: {error!r}"
        )
        assert "carries no @slice-01" in error, (
            f"expected the run to fail LATER at P4 (no AT file) -- got: {error!r}"
        )

    def test_lowercase_trailer_still_passes_p2_unaffected(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        commit = _init_repo_with_commit(repo, "do the thing\n\nSlice-Id: slice-01")

        refusal = _preconditions(repo, "some-feature", "slice-01", commit)

        assert refusal is not None
        assert "trailer set" not in refusal.get("error", "")

    def test_absent_trailer_still_refused_at_p2(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        commit = _init_repo_with_commit(repo, "do the thing, no trailer at all")

        refusal = _preconditions(repo, "some-feature", "slice-01", commit)

        assert refusal is not None
        assert "trailer set" in refusal.get("error", ""), (
            "a genuinely trailer-less commit must still be refused at P2 -- "
            f"got: {refusal!r}"
        )
