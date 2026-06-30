"""Domain types for slice-01 -- the MANIFEST-OPTIONAL walking-skeleton floor.

feature-end-ws-gate-manifest-optional (ADR-098, ratified 2026-06-24). Every domain
noun in the slice-01 Gherkin is expressed once here as a typed enum (Mandate-12
criterion 1). Step bodies and the composition service consume these typed
parameters; no raw ``str`` is passed where a domain enum exists.

Behaviour this slice specifies: when NO ``walking-skeleton.json`` manifest is
present, the floor COMPUTES applicability from the feature's git delta instead of
fail-closing (usage exit 2). This EXTENDS the delta-compute path the gate already
runs for the empty-``entry_points`` case (``walking_skeleton_gate.py:213-240``,
reusing ``_feature_ships_new_installable``) to the no-manifest case:

  - delta adds NO new installable root   -> NOT_APPLICABLE (the cycle proceeds);
  - delta ADDS a new installable root + no @walking-skeleton AT -> FAIL (the
    installer cannot dodge the floor by omitting the manifest);
  - the delta cannot be established      -> LOUD refuse-to-decide (the floor does
    NOT fall back to a silent NA or a usage exit 2).

A feature that ships a manifest is unchanged (the explicit-manifest path governs).

None of the no-manifest branch exists at HEAD -- ``_load_manifest`` raises a
``ValueError`` (mapped to usage exit 2) the moment the manifest file is absent
(``walking_skeleton_gate.py:108-110``). So AC-1/2/3 RED-fail for the right reason
(the floor fail-closes on absence); AC-4 (manifest present) is already green.
"""

from __future__ import annotations

from enum import Enum


class FeatureShape(str, Enum):
    """The staged feature whose manifest-optional WS-floor verdict is decided.

    MANIFEST_LESS_ADDS_NO_INSTALLABLE_ROOT
        -- NO ``walking-skeleton.json`` in the feature dir; a real git work-tree
           whose feature commit ADDS no new build-system file. The floor must
           DERIVE NOT_APPLICABLE from the git delta rather than fail-close on the
           absent manifest.

    MANIFEST_LESS_ADDS_NEW_INSTALLABLE_ROOT
        -- NO manifest; a real git work-tree whose feature commit ADDS a NEW
           ``pyproject.toml`` at a new root, and no @walking-skeleton AT. The floor
           must FAIL -- omitting the manifest cannot dodge the installer check.

    MANIFEST_LESS_NO_TRACKED_HISTORY
        -- NO manifest; the feature dir is NOT a git work-tree, so the delta cannot
           be computed. The floor degrades LOUD (refuse-to-decide) -- never a
           silent NA, never a usage fail-close on absence.

    MANIFEST_PRESENT_NOT_APPLICABLE
        -- a feature that DOES ship a ``walking-skeleton.json`` declaring
           ``walking_skeleton_applicable: false`` with a justified rationale. The
           explicit-manifest path is unchanged: NOT_APPLICABLE, exactly as today.
    """

    MANIFEST_LESS_ADDS_NO_INSTALLABLE_ROOT = "manifest_less_adds_no_installable_root"
    MANIFEST_LESS_ADDS_NEW_INSTALLABLE_ROOT = "manifest_less_adds_new_installable_root"
    MANIFEST_LESS_NO_TRACKED_HISTORY = "manifest_less_no_tracked_history"
    MANIFEST_PRESENT_NOT_APPLICABLE = "manifest_present_not_applicable"


class FloorVerdict(str, Enum):
    """The operator-observable verdict of one manifest-optional WS-floor run.

    NOT_APPLICABLE -- the feature's git delta adds no new installable root (or the
                      present manifest justifiably declares so); the floor honours
                      it and the cycle proceeds past the floor (exit 0).
    FAIL           -- the feature's git delta ADDS a new installable root with no
                      @walking-skeleton AT; the floor refuses (exit 1).
    INDETERMINATE  -- the delta could not be established; a LOUD refusal-to-decide.
    FAIL_CLOSED    -- the HEAD behaviour the no-manifest branch must REPLACE: the
                      floor rejected the run as a usage error (exit 2) because no
                      manifest was present. The slice-01 contract forbids this on
                      manifest absence; surfacing it as a distinct verdict makes
                      the RED name the real cause (got a usage fail-close) rather
                      than silently masking it as some other verdict.
    OTHER          -- any exit code outside the gate's verdict contract; surfaced
                      distinctly so a RED never masks a setup failure as a verdict.
    """

    NOT_APPLICABLE = "not_applicable"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"
    FAIL_CLOSED = "fail_closed"
    OTHER = "other"


class ReasonMarker(str, Enum):
    """A substring identifying WHICH cause a floor verdict reports.

    NOT_APPLICABLE_VERDICT
        -- the ``verdict`` token the gate prints when it honours a non-applicable
           feature (``GateVerdict.NOT_APPLICABLE``, ``gate_outcome.py:33``).
    FAIL_VERDICT
        -- the ``verdict`` token the gate prints when it refuses
           (``GateVerdict.FAIL``, ``gate_outcome.py:32``).
    GIT_UNAVAILABLE
        -- a token of the LOUD refuse-to-decide diagnostic naming the
           git-unavailability that prevented the delta from being computed.
    USAGE_FAIL_CLOSE
        -- the ``event`` token the gate prints when it fail-closes on an absent
           manifest at HEAD (``WalkingSkeletonGateUsageError``,
           ``walking_skeleton_gate.py:268``) -- the behaviour the no-manifest
           branch must REPLACE. The Then "does not fail-close" assertion keys on
           the ABSENCE of this token.
    """

    NOT_APPLICABLE_VERDICT = "not_applicable"
    FAIL_VERDICT = "fail"
    GIT_UNAVAILABLE = "git"
    USAGE_FAIL_CLOSE = "WalkingSkeletonGateUsageError"


__all__ = ["FeatureShape", "FloorVerdict", "ReasonMarker"]
