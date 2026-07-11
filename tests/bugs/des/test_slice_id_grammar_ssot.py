"""Regression: five sites carry the PRE-fix `slice-NN` tag/row grammar.

DEFECT (fix-slice-id-grammar-drift-ssot, oracle in
``docs/feature/fix-slice-id-grammar-drift-ssot/feature-delta.md``): the
`slice-NN` identifier grammar was extended to accept a letter suffix
(`slice-04a`, `slice-05b` -- an `@coupled` split, accepted since #87) when the
old `@(slice-\\d+)\\b` silently failed to match it (friction #10, fixed
2026-06-26 LOCALLY in ``carpaccio_format.py:69-77`` and
``slice_id_trailer.py:19-25``). Five OTHER sites still carry the pre-fix
grammar and silently drop the suffix:

  * ``src/des/cli/run_contract_gate.py:133``               -- ``_SLICE_TAG_RE``
  * ``src/des/cli/verify_deliver_entry_contract.py:75``     -- ``_SLICE_ROW_ID``
  * ``src/des/cli/verify_deliver_entry_contract.py:78``     -- ``_SLICE_TAG``
  * ``src/des/application/feature_at_files.py:192``         -- ``_SLICE_SUBTAG_RE``
  * ``src/des/application/slice_at_completeness.py:47``     -- ``_SLICE_TAG_RE``

A feature using a letter-suffixed slice id has its ``@slice-04a``-tagged
scenarios / ``| slice-04a |`` plan rows SILENTLY INVISIBLE to the contract-gate
scope selector, the DELIVER-entry contract check, the feature-AT enumerator,
and the slice-AT completeness check -- the exact silent-failure class already
shipped and fixed once (#10), now drifted back open at five other loci.

Driving surface (Mandate 16): each site's own PUBLIC-BEHAVIOR consuming
function is driven directly (in-process, no subprocess) -- the private regex
itself is never asserted on in isolation except as a last-resort SSOT-identity
pin (test 6), per dispatch instruction. Fix locus (design, not yet landed):
``src/des/domain/slice_id_trailer.py`` exports ``SLICE_TAG_RE`` /
``SLICE_ROW_ID_RE``; the five sites (+ ``carpaccio_format.py`` itself, folded
back) import them instead of re-deriving.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.application import feature_at_files, slice_at_completeness
from des.cli import carpaccio_format, run_contract_gate
from des.cli.verify_deliver_entry_contract import (
    _authored_slice_tags,
    _slice_without_at_module,
)


_FEATURE_ID = "demo-feature"


def _write_feature_file(
    repo_root: Path, *, tag: str, rel: str = "tests/acceptance/demo.feature"
) -> Path:
    """A `.feature` file self-identifying with `@feature-{_FEATURE_ID}`, one
    scenario carrying `tag` (a bare `@slice-NN`-shaped or malformed tag)."""
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"@feature-{_FEATURE_ID}\n"
        "Feature: Demo\n\n"
        f"  {tag}\n"
        "  Scenario: A coupled-split scenario\n"
        "    Given a thing\n",
        encoding="utf-8",
    )
    return path


def _write_pytest_head_tagged_file(repo_root: Path, *, tag: str) -> Path:
    """A pytest file head-comment-tagged `@feature-{_FEATURE_ID}` + `tag`."""
    path = repo_root / "test_demo.py"
    path.write_text(
        f"# @feature-{_FEATURE_ID} {tag}\ndef test_something():\n    assert True\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# POSITIVE -- the bug: a letter-suffixed slice id must be matched exactly as
# a plain `slice-NN` id is (identically to the already-fixed carpaccio_format
# reference at line 77).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "surface_id,extract_tags",
    [
        pytest.param(
            "_slice_tags",
            lambda feature_file: run_contract_gate._slice_tags(feature_file),
            id="run_contract_gate._slice_tags",
        ),
        pytest.param(
            "_scenario_slice_index",
            lambda feature_file: set().union(
                *run_contract_gate._scenario_slice_index(feature_file).values()
            )
            if run_contract_gate._scenario_slice_index(feature_file)
            else set(),
            id="run_contract_gate._scenario_slice_index",
        ),
    ],
)
def test_run_contract_gate_extracts_letter_suffixed_slice_tag(
    tmp_path: Path, surface_id: str, extract_tags
) -> None:
    """POSITIVE (site 1, run_contract_gate.py:133): the contract gate's scope
    selector must resolve a `@slice-04a` scenario tag identically to a plain
    `@slice-04`, for BOTH consuming functions that read `_SLICE_TAG_RE`
    (`_slice_tags` -- the feature-scoped-mode intersection check, and
    `_scenario_slice_index` -- the shipped+entering narrowing map).

    ACTIVE-RED today: `_SLICE_TAG_RE = @(slice-\\d+)\\b` fails to match
    `@slice-04a` (the `\\b` between digit "4" and letter "a" is no boundary),
    so `slice-04a` is silently absent from the extracted tag set.

    # covers: R1
    """
    feature_file = _write_feature_file(tmp_path, tag="@slice-04a")

    tags = extract_tags(feature_file)

    assert "slice-04a" in tags, (
        f"[{surface_id}] a letter-suffixed @slice-04a scenario tag must be "
        f"extracted identically to @slice-NN (the already-fixed "
        f"carpaccio_format.py:77 grammar); got {tags!r} -- "
        "run_contract_gate._SLICE_TAG_RE still carries the pre-fix grammar "
        "(@(slice-\\d+)\\b), silently dropping the letter suffix"
    )


def test_verify_deliver_entry_contract_flags_missing_at_for_letter_suffixed_row(
    tmp_path: Path,
) -> None:
    """POSITIVE (site 2a, verify_deliver_entry_contract.py:75): `_SLICE_ROW_ID`
    must parse a `| slice-04a | ... |` Slice-Plan row identically to a plain
    `| slice-04 | ... |` row, so a genuinely-unbacked letter-suffixed slice is
    FLAGGED missing by `_slice_without_at_module` (never silently skipped).

    ACTIVE-RED today: `_SLICE_ROW_ID = ^\\|\\s*(slice-\\d+)\\s*\\|` requires
    `\\s*\\|` immediately after the digits, but the next character is the
    letter suffix -- the row fails to match AT ALL, so the loop silently
    SKIPS it instead of flagging it; `_slice_without_at_module` wrongly
    returns None (no gap detected) for a row that carries zero authored AT.

    # covers: R1
    """
    content = (
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        "| slice-04a | An @coupled split of slice-04 | pending | | |\n"
    )
    # No .feature authored anywhere under tmp_path -- slice-04a is genuinely
    # UNBACKED.

    unbacked = _slice_without_at_module(content, _FEATURE_ID, tmp_path)

    assert unbacked == "slice-04a", (
        f"a genuinely-unbacked slice-04a Slice-Plan row must be flagged "
        f"missing; got {unbacked!r} -- verify_deliver_entry_contract."
        "_SLICE_ROW_ID still carries the pre-fix grammar, silently skipping "
        "the letter-suffixed row instead of flagging it"
    )


def test_verify_deliver_entry_contract_recognizes_letter_suffixed_authored_tag(
    tmp_path: Path,
) -> None:
    """POSITIVE (site 2b, verify_deliver_entry_contract.py:78): `_SLICE_TAG`
    must extract a `@slice-04a` scenario tag from an authored `.feature`
    identically to `@slice-NN`, so `_authored_slice_tags` correctly counts a
    letter-suffixed slice as backed.

    ACTIVE-RED today: `_SLICE_TAG = @(slice-\\d+)\\b` fails to match
    `@slice-04a` for the same `\\b`-boundary reason as site 1; the authored
    tag set silently omits `slice-04a`.

    # covers: R1
    """
    _write_feature_file(tmp_path, tag="@slice-04a")

    authored = _authored_slice_tags(_FEATURE_ID, tmp_path)

    assert "slice-04a" in authored, (
        f"an authored @slice-04a scenario tag must be recognized identically "
        f"to @slice-NN; got {authored!r} -- verify_deliver_entry_contract."
        "_SLICE_TAG still carries the pre-fix grammar"
    )


def test_feature_at_files_resolves_letter_suffixed_pytest_sub_tag(
    tmp_path: Path,
) -> None:
    """POSITIVE (site 4, feature_at_files.py:192): the pytest-side head-comment
    `@slice-NN` sub-tag resolver must resolve `@slice-04a` identically to
    `@slice-NN`, so a pytest-authored AT for a letter-suffixed slice is not
    structurally invisible to the completeness oracle.

    ACTIVE-RED today: `_SLICE_SUBTAG_RE = @(slice-\\d+)\\b` fails to match
    `@slice-04a`; `resolve_test_file_attribution(...).slice_id` is silently
    `None` instead of `"slice-04a"`.

    # covers: R1
    """
    test_file = _write_pytest_head_tagged_file(tmp_path, tag="@slice-04a")

    attribution = feature_at_files.resolve_test_file_attribution(test_file)

    assert attribution.slice_id == "slice-04a", (
        f"a head-comment @slice-04a sub-tag must resolve identically to "
        f"@slice-NN; got slice_id={attribution.slice_id!r} -- "
        "feature_at_files._SLICE_SUBTAG_RE still carries the pre-fix grammar"
    )


def test_slice_at_completeness_finds_letter_suffixed_feature_file(
    tmp_path: Path,
) -> None:
    """POSITIVE (site 5, slice_at_completeness.py:47): the slice-commit
    completeness oracle must find a `.feature` scenario tagged `@slice-04a`
    when asked for `slice_id="slice-04a"`, identically to a plain slice id --
    otherwise a genuinely-delivered letter-suffixed AT is reported MISSING
    from the commit (a false-negative RCA Branch-A defect).

    ACTIVE-RED today: `_SLICE_TAG_RE = @(slice-\\d+)\\b` fails to match
    `@slice-04a`; `feature_files_for_slice` silently returns an empty list
    even though the AT file genuinely exists on disk.

    # covers: R1
    """
    _write_feature_file(tmp_path, tag="@slice-04a")

    matched = slice_at_completeness.feature_files_for_slice(
        tmp_path, "slice-04a", _FEATURE_ID
    )

    assert matched, (
        "a .feature scenario tagged @slice-04a must be resolved for "
        "slice_id='slice-04a'; got an empty result -- slice_at_completeness."
        "_SLICE_TAG_RE still carries the pre-fix grammar"
    )


# ---------------------------------------------------------------------------
# NEGATIVE (invariance pin) -- the fix must NOT loosen the grammar into
# matching a non-slice token. Green today, stays green after the fix.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize("bogus_tag", ["@slice-abc", "@notslice-04"])
def test_rejects_non_slice_tokens_across_all_five_drifted_surfaces(
    tmp_path: Path, bogus_tag: str
) -> None:
    """NEGATIVE (invariance pin): a non-slice token -- `@slice-abc` (no
    digits) or `@notslice-04` (wrong prefix, not immediately preceded by
    `@slice-`) -- must NEVER be matched by any of the five drifted surfaces,
    nor by the already-fixed `carpaccio_format` reference grammar. Pins that
    the letter-suffix fix widens the grammar by exactly one optional
    lowercase letter -- never into accepting an arbitrary suffix or a
    differently-prefixed token. Must stay green BOTH before and after the fix.
    """
    bare_token = bogus_tag.lstrip("@")

    feature_file = _write_feature_file(tmp_path, tag=bogus_tag)
    test_file = _write_pytest_head_tagged_file(tmp_path, tag=bogus_tag)
    content = (
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| {bare_token} | A malformed row | pending | | |\n"
    )

    # site 1 (run_contract_gate)
    assert bare_token not in run_contract_gate._slice_tags(feature_file)
    # site 2 (verify_deliver_entry_contract) -- a malformed row is never
    # RECOGNIZED as a slice row at all, so it is never flagged unbacked
    # (there is nothing valid to flag).
    assert _slice_without_at_module(content, _FEATURE_ID, tmp_path) != bare_token
    assert bare_token not in _authored_slice_tags(_FEATURE_ID, tmp_path)
    # site 4 (feature_at_files)
    attribution = feature_at_files.resolve_test_file_attribution(test_file)
    assert attribution.slice_id != bare_token
    # site 5 (slice_at_completeness)
    assert not slice_at_completeness.feature_files_for_slice(
        tmp_path, bare_token, _FEATURE_ID
    )
    # the already-fixed reference grammar (carpaccio_format.py:77) -- the
    # fix must match this pattern's negative space exactly, not exceed it.
    assert bare_token not in carpaccio_format._SLICE_TAG_RE.findall(f"{bogus_tag}\n")


# ---------------------------------------------------------------------------
# SSOT pin -- the one-locus witness. Deferred (function-body) import: an
# ImportError here must fail ONLY this test at call-time, never break
# collection of the whole file (RED-not-BROKEN discipline, ADR-025). No
# `pytest.importorskip` -- an honest hard fail IS the RED signal today (the
# SSOT export does not exist yet).
# ---------------------------------------------------------------------------


def test_five_drifted_modules_import_the_same_domain_ssot_pattern() -> None:
    """SSOT pin: after the fix there is ONE canonical `slice-NN` tag/row
    grammar, exported from the domain SSOT (`des.domain.slice_id_trailer`),
    and every one of the five drifted sites (plus `carpaccio_format.py`
    itself, folded back per the design) imports it rather than re-deriving
    its own copy.

    ACTIVE-RED today: `des.domain.slice_id_trailer` exports no
    `SLICE_TAG_RE` / `SLICE_ROW_ID_RE` at all -- the import below raises
    `ImportError`. This is an intentional HARD FAIL (no
    `pytest.importorskip`): the missing SSOT export IS the defect this test
    witnesses.
    """
    from des.domain.slice_id_trailer import SLICE_ROW_ID_RE, SLICE_TAG_RE

    assert carpaccio_format._SLICE_TAG_RE.pattern == SLICE_TAG_RE.pattern, (
        "carpaccio_format._SLICE_TAG_RE must be byte-identical to the domain "
        "SSOT SLICE_TAG_RE (fold-back per the design reference)"
    )
    assert run_contract_gate._SLICE_TAG_RE.pattern == SLICE_TAG_RE.pattern, (
        "run_contract_gate._SLICE_TAG_RE must import the domain SSOT pattern"
    )
    from des.cli import verify_deliver_entry_contract as _vdec

    assert _vdec._SLICE_TAG.pattern == SLICE_TAG_RE.pattern, (
        "verify_deliver_entry_contract._SLICE_TAG must import the domain "
        "SSOT SLICE_TAG_RE"
    )
    assert _vdec._SLICE_ROW_ID.pattern == SLICE_ROW_ID_RE.pattern, (
        "verify_deliver_entry_contract._SLICE_ROW_ID must import the domain "
        "SSOT SLICE_ROW_ID_RE"
    )
    assert feature_at_files._SLICE_SUBTAG_RE.pattern == SLICE_TAG_RE.pattern, (
        "feature_at_files._SLICE_SUBTAG_RE must import the domain SSOT SLICE_TAG_RE"
    )
    assert slice_at_completeness._SLICE_TAG_RE.pattern == SLICE_TAG_RE.pattern, (
        "slice_at_completeness._SLICE_TAG_RE must import the domain SSOT SLICE_TAG_RE"
    )
