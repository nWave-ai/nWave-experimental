"""Domain types for slice-03 -- the DELTA-AWARE WS-floor installability detection.

slice-03 of fix-feature-end-ws-gate-applicability (Ale-ratified option B-port,
2026-06-05). Every domain noun in the slice-03 Gherkin is expressed once here as
a typed enum (Mandate-12 criterion 1 -- the domain types module exists with
typed enums for every domain noun used in Gherkin). Step bodies and the
composition service consume these typed parameters; no raw ``str`` is passed
where a domain enum exists.

The behaviour this slice specifies (verified from the ratified DESIGN at HEAD
``c7a3375f6``, ``feature-delta.md`` slice-03 DDD-1..DDD-4): the walking-skeleton
floor's installability cross-check becomes DELTA-AWARE. The gate detects whether
THIS feature's git DELTA (``git diff --diff-filter=A --name-only base...HEAD`` --
files ADDED since the merge-base with ``base``) introduces a NEW installable root
(``pyproject.toml`` / ``setup.py`` / ``setup.cfg``), via a new ``FeatureDeltaPort``
+ ``GitFeatureDeltaAdapter`` that degrades LOUD (``GateVerdict.INDETERMINATE``,
exit 4) when git is absent / not a work-tree / the base ref is unresolvable.

The load-bearing divergence pair is (a) vs (b): IDENTICAL manifest declaration
(``walking_skeleton_applicable: false`` + the SAME non-empty rationale), IDENTICAL
ambient repo (root carries ``pyproject.toml`` on the baseline); the ONLY
difference is whether the feature's git DELTA ADDS a NEW build-system file at a
new root. (a) catches the lie mechanically; (b) grants NA to the exact
monorepo-internal shape slice-02 could not honour. (c) proves the degrade-LOUD
mandate on a non-git tree.

None of that exists at HEAD -- the gate keys installability on the ambient
``_detect_installable(feature_root)`` direct-children probe (``cli/
walking_skeleton_gate.py:108``), there is no ``FeatureDeltaPort``, no
``--delta-base-ref`` flag, and no ``GateVerdict.INDETERMINATE`` (exit 4). So the
slice-03 ATs RED-fail for the right reason (MISSING_FUNCTIONALITY): the gate
reads the ambient repo-root ``pyproject.toml`` as installable and FAILs the
honest monorepo-internal case (b), and has no INDETERMINATE producer for (c).
"""

from __future__ import annotations

from enum import Enum


class DeltaShape(str, Enum):
    """The shape of the staged feature's git DELTA whose WS-floor verdict is decided.

    Each value stages a REAL git work-tree (or, for the non-git case, a plain
    directory) so the divergence is keyed on the feature's actual added-paths set,
    not on a declared field. The work-tree has an initial ``master`` baseline
    commit and a feature-branch commit; the gate's delta probe runs
    ``git diff --diff-filter=A --name-only master...HEAD``.

    DELTA_ADDS_NEW_INSTALLABLE_ROOT
        -- the feature commit ADDS a NEW ``pyproject.toml`` at a NEW root that was
           absent on the baseline. The delta genuinely introduces an installable
           artifact. With ``walking_skeleton_applicable: false`` declared, the
           declaration is a LIE the gate must catch from the DELTA -> FAIL (exit
           1); the diagnostic names the detected added build-system path.

    DELTA_ADDS_NO_INSTALLABLE_ROOT
        -- a monorepo-internal feature commit (hook-only / gate-logic ``src/des``
           change, like THIS very feature). The ambient repo root HAS a
           ``pyproject.toml`` ON THE BASELINE, but the feature's delta ADDS no new
           build-system file. With the SAME ``walking_skeleton_applicable: false``
           + SAME rationale, the gate grants NOT_APPLICABLE (exit 0) -- the
           honest NA slice-02 could not grant for a monorepo-internal feature.

    NOT_A_GIT_WORK_TREE
        -- the staged feature dir is NOT a git work-tree (no ``.git/`` history).
           The delta cannot be computed; the gate degrades LOUD to INDETERMINATE
           (exit 4) -- never a silent NA, never a silent FAIL.
    """

    DELTA_ADDS_NEW_INSTALLABLE_ROOT = "delta_adds_new_installable_root"
    DELTA_ADDS_NO_INSTALLABLE_ROOT = "delta_adds_no_installable_root"
    NOT_A_GIT_WORK_TREE = "not_a_git_work_tree"


class FloorVerdict(str, Enum):
    """The operator-observable verdict of one delta-aware walking-skeleton-floor run.

    NOT_APPLICABLE -- the feature's git delta adds no new installable root; the
                      justified declaration is honoured (exit 0); the cycle
                      proceeds past the floor.
    FAIL           -- the feature's git delta ADDS a new installable root yet the
                      manifest declares not-applicable; the lie is caught from the
                      delta (exit 1).
    INDETERMINATE  -- the delta could not be established (git absent / not a
                      work-tree / base ref unresolvable); a LOUD refusal-to-decide
                      (exit 4); the cycle does NOT proceed.
    """

    NOT_APPLICABLE = "not_applicable"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class ReasonMarker(str, Enum):
    """A substring identifying WHICH cause a floor verdict reports.

    NOT_APPLICABLE_VERDICT
        -- the verdict token the gate emits in its stdout JSON when it honours a
           justified non-applicable declaration whose delta adds nothing installable
           (``GateVerdict.NOT_APPLICABLE``, ``gate_outcome.py:30``).
    FAIL_VERDICT
        -- the verdict token the gate emits when it refuses (``GateVerdict.FAIL``,
           ``gate_outcome.py:29``).
    INDETERMINATE_VERDICT
        -- the verdict token the gate emits when the delta is undecidable
           (``GateVerdict.INDETERMINATE``, DESIGN DDD-3 -- a NEW first-class
           verdict this slice introduces).
    ADDED_INSTALLABLE_PATH
        -- a token of the diagnostic naming the SPECIFIC delta-ADDED build-system
           path when a feature's delta introduces a new installable root yet
           declares not-applicable (DESIGN DDD-4 case (a)). Deliberately the
           NEW-ROOT path (``new_pkg/...``), NOT the bare ``pyproject.toml`` token
           the CURRENT ambient diagnostic already prints -- so the assertion
           RED-fails today (the gate names the ambient signatures generically, not
           the delta-added path) and only GREENs once the diagnostic is
           delta-sourced. Kept in sync with the staged added-path basename.
    GIT_UNAVAILABLE
        -- a token of the INDETERMINATE diagnostic naming the git-unavailability
           that prevented the delta from being computed (DESIGN DDD-3/case (c)).
    """

    NOT_APPLICABLE_VERDICT = "not_applicable"
    FAIL_VERDICT = "fail"
    INDETERMINATE_VERDICT = "indeterminate"
    ADDED_INSTALLABLE_PATH = "new_pkg"
    GIT_UNAVAILABLE = "git"


__all__ = ["DeltaShape", "FloorVerdict", "ReasonMarker"]
