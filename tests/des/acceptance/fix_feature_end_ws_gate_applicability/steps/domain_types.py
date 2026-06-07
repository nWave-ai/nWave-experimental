"""Domain types for slice-01 -- the feature-end gate's truthful refusal reason.

slice-01 of fix-feature-end-ws-gate-applicability (the walking-skeleton slice).
Every domain noun in the slice-01 Gherkin is expressed once here as a typed enum
or NewType; step bodies and the composition service consume these typed
parameters (Mandate-12 criterion 1 -- the domain types module exists with typed
enums for every domain noun used in Gherkin).

The defect this slice fixes (verified from source,
``feature_end_cycle_service.py:292`` ``_gate_diagnostic``): when the feature-end
cycle runs a gate as a subprocess on a developer checkout, the runtime freshness
gate prints a ``des.runtime.freshness.autoskipped`` notice to standard error.
``_gate_diagnostic`` selects the refusal reason as ``stderr or stdout`` -- so the
freshness notice SHADOWS the gate's real reason (which the gate prints to
standard output). The operator is handed the freshness notice instead of the
real cause. slice-01 makes the cycle FILTER the ``des.runtime.*`` runtime notices
out before it selects the reason, so the REAL reason surfaces.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier the feature-end cycle is scoped to.
FeatureId = NewType("FeatureId", str)


class StagedFeature(str, Enum):
    """The shape of the staged feature the walking-skeleton floor checks.

    Each value stages a feature directory whose walking-skeleton floor refuses
    for a DISTINCT, REAL reason -- so a single filter that surfaces the real
    reason is proven to surface DIFFERENT real reasons (anti-over-filtering),
    not one hard-coded string.

    NO_MANIFEST       -- the floor has no ``walking-skeleton.json`` manifest to
                         check; the floor's real reason names the missing
                         manifest.
    MANIFEST_NO_ROOT  -- the manifest is present but omits its ``feature_root``;
                         the floor's real reason names the missing feature root.
    """

    NO_MANIFEST = "no_manifest"
    MANIFEST_NO_ROOT = "manifest_missing_feature_root"


class CycleOutcome(str, Enum):
    """The operator-observable verdict of one feature-end cycle run.

    CERTIFIED -- the cycle certified the feature-end done (exit zero).
    REFUSED   -- the cycle refused to certify the feature-end done (non-zero
                 exit); a gate failed and the cycle reports its reason.
    """

    CERTIFIED = "certified"
    REFUSED = "refused"


class ReasonMarker(str, Enum):
    """A substring that identifies WHICH reason a refusal reports.

    Used to assert the reported refusal reason carries the REAL gate reason and
    NOT the runtime freshness notice -- the whole point of the slice.

    MISSING_MANIFEST     -- token of the floor's missing-manifest reason
                            (``walking_skeleton_gate.py:96`` usage error).
    MISSING_FEATURE_ROOT -- token of the floor's missing-feature-root reason
                            (``walking_skeleton_gate.py:112`` usage error).
    RUNTIME_FRESHNESS     -- the runtime freshness-notice event prefix
                            (``freshness.py:223``); the noise that must NOT be
                            the reported reason.
    """

    MISSING_MANIFEST = "walking-skeleton.json"
    MISSING_FEATURE_ROOT = "feature_root"
    RUNTIME_FRESHNESS = "des.runtime.freshness"
