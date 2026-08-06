"""SSOT for slice-commit AT completeness -- pure read-only computation.

Closes F-REVERIFY-E1-GLOBAL-SCOPE-COLLISION (PRR D2 blocker).

This module is the application-layer SSOT for the pure read-only functions that
compute the missing `.feature` AT files for a slice commit. DESIGN DDD-1 / DDD-9
promoted the functions out of ``des.cli.verify_slice_commit_completeness`` (the
F2-drift vector) into this layer so multiple CLI consumers can import a single
physical home -- ``verify_slice_commit_completeness`` then re-exports the
symbols (DDD-3 identity guarantee) and ``check_slice_at_completeness`` imports
them directly (DDD-2).

Contract shape: pure-function (return-only). Inputs: ``(repo, commit, slice_id,
feature_id)``. Outputs: ``AtCompletenessOutcome``. No filesystem mutation beyond
git's read cache. The driving-port wrapper (``des.cli.check_slice_at_completeness``)
inherits this read-only contract by construction (principle 12 effect-isolation
-- arch-test enforced via the no-``AtCompletionLedger``-import rule).

stdlib-only (per the DES-bundle contract). The intra-package imports are all
``feature_at_files`` resolvers: ``feature_tag_files`` (the application-layer
``@feature-{id}`` resolver for Gherkin ``.feature`` files, itself stdlib-only),
plus ``feature_tagged_test_files`` / ``resolve_test_file_attribution`` (the
pytest-side mirror, WTBD-168) added to close
F-FEATURE-END-COMPLETENESS-ORACLE-PYTEST-BLIND -- a slice delivered only by a
head-comment-tagged pytest AT file was invisible to this oracle.

``_regression_file_naming_components`` / ``canonical_regression_test_path`` /
``_regression_file_glob_candidates`` (moved here from
``des.cli.verify_slice_commit_completeness``, same DDD-1/DDD-9 promotion this
module's docstring already describes for ``feature_files_for_slice`` /
``missing_at_files`` -- fix-e1-pytest-regression-path-convention) are the
THIRD AT taxonomy ``feature_files_for_slice`` recognizes: a pytest-regression
file named by convention (``tests/**/{feature_dir}/test_{slice_us}_*.py``, no
``@feature-``/``@slice-NN`` head-comment tag required) is the same positive
evidence ``_infer_pytest_regression_at_kind``
(``verify_slice_commit_completeness.py``, RC1 Fix B) already trusts to route
E2 to the pytest-regression path -- E1's completeness/verifiability check now
recognizes the identical convention instead of reading it as taxonomy-blind
(F-E1-VACUOUS-MISSES-PYTEST-REGRESSION-PATH-CONVENTION).
``verify_slice_commit_completeness.py`` re-exports all three names unchanged
(``__all__``) so its 18 pre-existing callers keep importing from there.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_subprocess import git_text as _git
from des.application.feature_at_files import (
    feature_tag_files,
    feature_tagged_test_files,
    is_pytest_collectible,
    resolve_test_file_attribution,
)
from des.domain.slice_id_trailer import SLICE_TAG_RE


if TYPE_CHECKING:
    from pathlib import Path


#: Imported from the domain SSOT (fix-slice-id-grammar-drift-ssot) so a
#: letter-suffixed `@slice-04a` tag resolves identically to `@slice-NN`.
_SLICE_TAG_RE = SLICE_TAG_RE


def _regression_file_naming_components(
    feature_id: str, slice_id: str
) -> tuple[str, str]:
    """The two normalized components (``feature_dir``, ``slice_us``) the
    regression-file naming convention is built from -- hyphens replaced by
    underscores. Pure.

    SINGLE SOURCE for both ``_regression_file_glob_candidates`` below and
    ``canonical_regression_test_path`` (the seam a producer like
    ``des examine-fixture`` consumes to WRITE a new regression file this gate
    will later recognize) -- widening the naming convention into one shared
    private helper instead of letting a producer re-derive/guess it is what
    makes the produced fixture correct BY CONSTRUCTION (examinable-gate-
    surface feature, arch invariant: never re-declare this convention).
    """
    return feature_id.replace("-", "_"), slice_id.replace("-", "_")


def canonical_regression_test_path(
    feature_id: str,
    slice_id: str,
    *,
    parent: str = "fixture",
    suffix: str = "behaviour",
) -> str:
    """A repo-relative pytest-regression file path this gate's OWN naming
    convention (``_regression_file_glob_candidates``) resolves for
    ``slice_id``. Pure.

    The examinable-gate-surface feature's arch invariant: any producer that
    needs to WRITE a new regression file the gate will later recognize (e.g.
    ``des examine-fixture``) MUST derive its filename through this function,
    never by hand-matching the glob pattern below (a private implementation
    detail) -- a second copy of the convention would reintroduce the exact
    naming drift this feature exists to end. ``parent``/``suffix`` select
    WHERE under ``tests/**/{feature_dir}/`` and WHAT filename-tail the file
    gets; the returned path always satisfies ``test_{slice_us}_*.py`` for the
    SAME ``slice_us`` normalization ``_regression_file_glob_candidates``
    applies, so a file written at this path is guaranteed to resolve as
    exactly one candidate.
    """
    feature_dir, slice_us = _regression_file_naming_components(feature_id, slice_id)
    return f"tests/{parent}/{feature_dir}/test_{slice_us}_{suffix}.py"


def _regression_file_glob_candidates(
    repo: Path, feature_id: str, slice_id: str
) -> list[Path]:
    """Every file matching ``slice_id``'s regression-file naming convention.

    Glob ``tests/**/{feature_dir}/test_{slice_us}_*.py``, where
    ``feature_dir``/``slice_us`` are ``feature_id``/``slice_id`` with hyphens
    replaced by underscores (``_regression_file_naming_components``) -- the
    SAME convention this feature's own fixtures follow
    (``tests/fixture/{feature_id}/test_{slice_id}_*.py``) and the SAME shape
    already load-bearing on disk (e.g.
    ``tests/des/acceptance/{feature_id}/test_slice_NN_*.py``). Mirrors
    ``_slice_feature_dir``'s glob-and-match shape (``run_contract_gate.py``)
    keyed on filename prefix instead of a Gherkin ``@slice-NN`` tag -- the
    pytest-native equivalent. Zero or multiple matches are NEVER silently
    resolved by the caller (RC1 Fix B / RC2 Fix A conservative-keep).
    """
    feature_dir, slice_us = _regression_file_naming_components(feature_id, slice_id)
    return sorted(repo.glob(f"tests/**/{feature_dir}/test_{slice_us}_*.py"))


def feature_files_for_slice(
    repo: Path, slice_id: str, feature_id: str | None = None
) -> list[str]:
    """Return repo-relative paths of the AT files delivering the slice.

    Three discovery paths, UNIONed:

    1. Gherkin -- `.feature` files tagging the slice. A `.feature` file
       belongs to the slice when any of its scenarios carry the
       ``@slice-NN`` tag matching ``slice_id``. The working tree is walked,
       NOT just ``git ls-files`` -- an authored-but-never-committed AT file
       is untracked yet is exactly the RCA Branch-A defect this gate must
       catch. A file the slice authored on disk but kept out of every commit
       MUST be reported missing.

    2. pytest -- test files head-comment-tagged ``@feature-{feature_id}``
       (``feature_at_files.feature_tagged_test_files``, WTBD-168) whose
       ``@slice-NN`` sub-tag (``feature_at_files.resolve_test_file_attribution``)
       matches ``slice_id``. Closes
       F-FEATURE-END-COMPLETENESS-ORACLE-PYTEST-BLIND -- a slice delivered
       exclusively by a pytest AT was previously invisible to this oracle.
       Only active when ``feature_id`` is given: the ``@feature-{id}`` head
       tag is the discovery key, so a pytest file with no such tag never
       counts (no silent over-match; wall W5 -- ``@slice-NN`` alone is reused
       across features). ``feature_tagged_test_files`` itself applies no
       filename/extension restriction (any file's head window may match), so
       this loop additionally restricts matches to the pytest-collectible
       filename convention (``test_*.py`` / ``*_test.py``, see
       ``feature_at_files.is_pytest_collectible``) -- a doc, an ADR, or a
       non-test module that
       merely *mentions* the tag convention in its head must never count as a
       delivered AT (the un-gameable truncation guard).

    3. pytest-regression PATH CONVENTION -- a file matching
       ``_regression_file_glob_candidates``'s naming convention
       (``tests/**/{feature_dir}/test_{slice_us}_*.py``, no head-comment tag
       required) counts as a delivered AT for ``slice_id`` when EXACTLY ONE
       file matches. This is the SAME positive evidence
       ``_infer_pytest_regression_at_kind``
       (``des.cli.verify_slice_commit_completeness``, RC1 Fix B) already
       trusts to route E2 to the pytest-regression path -- closes
       F-E1-VACUOUS-MISSES-PYTEST-REGRESSION-PATH-CONVENTION, where E1 read a
       slice using this established convention as taxonomy-blind. Only
       active when ``feature_id`` is given (the convention is keyed on
       ``feature_dir``, mirroring taxonomy 2's wall-W5 scoping). Zero matches
       add no signal (conservative-keep, unchanged); >=2 matches add no
       signal either -- an ambiguous convention match is never silently
       resolved here, left for E2's own dedicated ambiguity refusal
       (``_infer_pytest_regression_at_kind``) to surface.

    The unioned candidate set is deduplicated before returning: a `.feature`
    file can legitimately be matched by BOTH paths (Gherkin tags precede
    ``Feature:`` within the pytest head-window scan too), and each delivered
    AT artifact must be reported EXACTLY ONCE.

    When ``feature_id`` is given the Gherkin candidate set is likewise scoped
    to that feature's `.feature` files via the ``@feature-{id}`` tag (the
    ``feature_at_files.feature_tag_files`` resolver) -- a ``@slice-NN`` tag
    is reused across features, so a global ``rglob`` would cross-bind another
    feature's slice file into this commit's completeness check (wall W5).
    """
    if feature_id is not None:
        candidates = feature_tag_files(repo, feature_id)
    else:
        candidates = [p for p in repo.rglob("*.feature") if ".git" not in p.parts]
    matched: list[str] = []
    for path in sorted(candidates):
        text = path.read_text(encoding="utf-8", errors="replace")
        if slice_id in _SLICE_TAG_RE.findall(text):
            matched.append(str(path.relative_to(repo)))
    if feature_id is not None:
        for test_path in feature_tagged_test_files(repo, feature_id):
            if not is_pytest_collectible(test_path):
                continue
            attribution = resolve_test_file_attribution(test_path)
            if slice_id in attribution.slice_ids:
                matched.append(str(test_path.relative_to(repo)))
        convention_candidates = _regression_file_glob_candidates(
            repo, feature_id, slice_id
        )
        if len(convention_candidates) == 1:
            matched.append(str(convention_candidates[0].relative_to(repo)))
    return sorted(set(matched))


def files_in_commit(repo: Path, commit: str) -> set[str]:
    """Return the set of repo-relative paths touched by ``commit``."""
    output = _git(repo, "show", "--name-only", "--pretty=format:", commit)
    return {line for line in output.splitlines() if line}


@dataclass(frozen=True)
class AtCompletenessOutcome:
    """E1 verdict for one (repo, commit, slice_id, feature_id) query.

    ``verifiable`` is False iff ``feature_files_for_slice`` matched ZERO AT
    candidates under EITHER taxonomy (Gherkin @slice-NN or pytest
    @feature-{id}/@slice-NN) -- "nothing was checked", distinct from
    ``missing == []`` meaning "everything checked, nothing missing". A
    consumer MUST treat ``verifiable is False`` as "cannot verify", never as
    a pass -- collapsing the two is exactly Bug #126 / the
    F-CARPACCIO-E1-VACUOUS-BLOCKS-PREDECESSOR-DISCRIMINATION defect class.
    """

    missing: list[str]
    verifiable: bool


def missing_at_files(
    repo: Path,
    commit: str,
    slice_id: str,
    feature_id: str | None = None,
    *,
    at_kind: str | None = None,
    regression_test_file: str | None = None,
    regression_test_files: tuple[str, ...] | None = None,
    historical_selection: bool = False,
) -> AtCompletenessOutcome:
    """Return `.feature` AT files for the slice that the commit fails to carry.

    A file is complete when it is present in this commit. A file already
    tracked before this commit AND unmodified by it is also complete -- the
    commit need not re-touch ATs delivered by an earlier slice commit. The
    incomplete case is the RCA Branch-A defect: an AT file the slice authored
    but never persisted into any commit.

    When ``feature_id`` is given the slice's `.feature` candidate set is
    scoped to that feature (wall W5 -- see ``feature_files_for_slice``).

    A FOURTH evidence source, additive to ``feature_files_for_slice``'s three
    scan-based taxonomies (fix-e1-explicit-regression-test-file): when
    ``at_kind == "pytest-regression"`` and ``regression_test_file`` is given
    AND that path is actually present in ``files_in_commit``, the CLI-declared
    path is itself positive AT evidence for this slice -- the caller's own
    affirmative declaration, exactly as ``_infer_pytest_regression_at_kind``
    (``verify_slice_commit_completeness``) already trusts it to route E2. A
    slice delivered via an arbitrarily-named pytest-regression file (no
    `.feature` tag, no head-comment tag, no naming-convention match) was
    previously invisible to E1 and refused as owning no recognized AT
    candidates -- the canonical `/nw-bugfix` mechanical-seal path
    (`verify-red-green` + `verify-negative-at`, no AT-review LLM dispatch)
    that only an armed examine-verdict PASS could route around.

    A DECLARED-but-ABSENT ``regression_test_file`` (named on the CLI but not
    actually present in this commit) is deliberately NOT unioned into
    ``at_files`` and therefore never hard-flagged as ``missing`` here --
    E1 (this function) collides with E2/CT8 if it does: E1 would hard-fail a
    case E2's own dedicated regression-file gate
    (``verify_slice_commit_completeness.py::_run_regression_gate``) already
    handles by degrading to ``_GATE_INDETERMINATE_EXIT_CODE`` (3), which
    ``commit_slice.main``'s preflight proceed-on-3 contract honors (ADR-DES-001
    addendum Rule 3 / CT8). This function's structural presence check defers
    entirely to E2 for that path -- it never marks it ``missing``.

    ``verifiable`` still flips True on the bare fact of the declaration
    itself (``at_kind == "pytest-regression"`` with a non-empty
    ``regression_test_file``), independent of whether the declared file is
    actually present in this commit. Collapsing "declared" into
    "verifiable=False, defer silently" would re-introduce the exact E1/E2
    collision this fix closes one layer up: ``verify_slice_commit_completeness
    ._run_verify_then_record``'s ``non_verifiable`` guard
    (RCA fix-carpaccio-e1-vacuous-taxonomy-gap) treats ANY
    ``verifiable=False`` slice as "zero recognized AT candidates" and hard-
    refuses it at E1, before E2 is ever reached -- so a declared-but-absent
    regression file would still never make it to E2's INDETERMINATE path.
    The caller's own affirmative ``--at-kind pytest-regression
    --regression-test-file <path>`` declaration IS the AT candidate (E1's
    job is only to say "something was declared for this slice", not to
    pre-empt E2's own presence/execution verdict) -- so ``verifiable=True,
    missing=[]`` for the declared-but-absent case, letting control flow
    reach E2, which is the sole authority on presence/pass/fail/indeterminate
    for that file.

    ``verifiable`` is False when zero AT candidates were found for this
    (slice_id, feature_id) at all AND no pytest-regression file was declared
    -- distinct from a genuine "verified everything, nothing missing" pass.
    See ``AtCompletenessOutcome``.

    ``historical_selection`` (ADR-002) is a FIFTH, mutually-exclusive
    evidence source keyed on an EXPLICIT, upstream-verified historical
    declaration (``--historical-declaration-id``): when ``True``, the
    working-tree scan (``feature_files_for_slice``) is never consulted and
    never unioned -- the E1-expected AT population comes SOLELY from
    ``regression_test_files``, the declaration's own canonical suite tuple.
    A declared member that is present-in-commit or tracked-before-commit is
    counted as positive evidence; a declared member that is neither is
    EXCLUDED from the population -- never added, therefore never appearing
    in ``missing`` -- mirroring, byte-for-byte, the ``declared_regression``
    carve-out above (same reasoning, one mechanism for both the single-file
    and the historical/aggregate evidence shape). ``verifiable`` is ``True``
    unconditionally on this path, mirroring ``declared_regression``'s own
    unconditional flip: the declaration's bare existence is all E1 decides
    here: whether a declared member is genuinely present, collectable, and
    green is E2's alone. ``historical_selection=False`` (the default) keeps
    every existing caller and path BYTE-IDENTICAL to pre-ADR-002 behavior.
    """
    if historical_selection:
        in_commit = files_in_commit(repo, commit)
        historical_at_files = [
            member
            for member in (regression_test_files or ())
            if member in in_commit or _tracked_before_commit(repo, commit, member)
        ]
        historical_missing = [
            rel_path
            for rel_path in historical_at_files
            if rel_path not in in_commit
            and not _tracked_before_commit(repo, commit, rel_path)
        ]
        return AtCompletenessOutcome(
            missing=sorted(historical_missing), verifiable=True
        )

    at_files = feature_files_for_slice(repo, slice_id, feature_id)
    in_commit = files_in_commit(repo, commit)
    declared_regression = at_kind == "pytest-regression" and bool(regression_test_file)
    if declared_regression and regression_test_file in in_commit:
        at_files = sorted({*at_files, regression_test_file})
    missing: list[str] = []
    for rel_path in at_files:
        if rel_path in in_commit:
            continue
        if _tracked_before_commit(repo, commit, rel_path):
            continue
        missing.append(rel_path)
    verifiable = bool(at_files) or declared_regression
    return AtCompletenessOutcome(missing=sorted(missing), verifiable=verifiable)


def _tracked_before_commit(repo: Path, commit: str, rel_path: str) -> bool:
    """True iff ``rel_path`` existed as a tracked file in ``commit``'s parent."""
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}~1:{rel_path}"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
