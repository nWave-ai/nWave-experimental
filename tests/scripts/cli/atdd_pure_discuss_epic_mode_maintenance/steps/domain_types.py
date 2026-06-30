"""Domain types for the discuss-epic-mode slice-05 maintenance slice.

Slice-05 value: a maintainer opening the epic-delta sees live progress -- feature
rows link ``docs/feature/{id}/`` when picked up and flip ``pending`` -> ``in-flight``
-> ``shipped`` -- and decides the next pickup from the plan, not from memory. The
"code" of this slice is SKILL / COMMAND text (DESIGN slice-02/04/05 text contracts)
-- there is NO ``src/des`` surface. DESIGN pins the linkage/status-flip contract
(LSC-1..LSC-6) as the AT-citable specification of what the epic-delta MAINTENANCE
procedure MUST do.

Every domain noun in the Gherkin is expressed once here as a typed enum or NewType
(Mandate-12 criterion 1). Step bodies and the composition service consume these
typed parameters -- no raw ``str`` where a domain enum exists.

S1 step-text uniqueness: the slice-02 sibling suite speaks "the maintainer runs the
epic-mode authoring on the epic" -- the ``--epic`` authoring act -- and "the
produced epic-delta". This suite speaks "the maintainer picks up the feature" /
"the maintainer finalizes the feature" -- the MAINTENANCE acts -- and "the row's
status" / "the row's link". The domain nouns differ, so the step phrases never
collide.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case epic identifier (e.g. "flow-v2-wave-migrations").
EpicId = NewType("EpicId", str)

# A kebab-case feature identifier naming one Feature Plan row (e.g. "design-wave-migration").
FeatureId = NewType("FeatureId", str)


class FeatureStatus(str, Enum):
    """The R2 closed Status-token set for a Feature Plan row (EDC-7 / LSC-5).

    The status moves FORWARD only (LSC-5 monotone): ``pending`` -> ``in-flight``
    -> ``shipped``. ``pending`` = authored, not yet started. ``in-flight`` = the
    feature's own DISCUSS has started (the row gains its ``docs/feature/{id}/``
    link at THIS flip, LSC-1). ``shipped`` = the feature has been finalized at
    feature-end (LSC-2).

    PENDING    -- authored row, the feature has not been picked up.
    IN_FLIGHT  -- the feature's DISCUSS has started; the row carries its
                  ``docs/feature/{id}/`` link (LSC-1).
    SHIPPED    -- the feature is finalized (LSC-2).
    """

    PENDING = "pending"
    IN_FLIGHT = "in-flight"
    SHIPPED = "shipped"


class MaintenanceAction(str, Enum):
    """A maintainer action on the epic-delta's Feature Plan (the LSC procedure).

    PICK_UP    -- start a feature's own DISCUSS: flip its row ``pending`` ->
                  ``in-flight`` AND add the ``docs/feature/{id}/`` link to the
                  Feature cell (LSC-1, one atomic edit).
    FINALIZE   -- finish a feature at feature-end: flip its row ``in-flight`` ->
                  ``shipped`` (LSC-2).
    """

    PICK_UP = "pick_up"
    FINALIZE = "finalize"


class MaintenanceVerdict(str, Enum):
    """Maintainer-observable verdict of an LSC maintenance action.

    The LSC procedure either applies the flip (forward-only, LSC-5) or rejects an
    illegal status token at the procedure level (LSC-6 -- the slice-01 validator
    does NOT validate Status cells, DC-1, so this rejection is the slice-05
    procedure's responsibility, NOT the keystone gate's).

    APPLIED            -- the flip was applied (forward-only); the row carries its
                          new status (and, on pick-up, its ``docs/feature/{id}/``
                          link).
    REJECTED_BAD_TOKEN -- an illegal status token (outside the R2 closed set, e.g.
                          ``done``) is rejected at the LSC procedure level (LSC-6).
    REJECTED_BACKWARD  -- a backward flip (e.g. ``shipped`` -> ``in-flight``) is
                          rejected; status moves forward only (LSC-5).
    MAINTENANCE_ABSENT -- the LSC maintenance procedure is undefined: no flip was
                          applied. On the current tip the procedure does not exist,
                          so every slice-05 invocation lands here -- the active-RED
                          missing-functionality signal, NOT a real verdict.
    """

    APPLIED = "applied"
    REJECTED_BAD_TOKEN = "rejected_bad_token"
    REJECTED_BACKWARD = "rejected_backward"
    MAINTENANCE_ABSENT = "maintenance_absent"


class GateOutVerdict(str, Enum):
    """Maintainer-observable verdict of the slice-01 keystone gate on a FLIPPED row.

    The keystone-gate-preservation leg (LSC-1/LSC-2 corollary): a status flip MUST
    NOT break the epic-delta's structural validity. The flipped epic-delta is
    re-validated through slice-01's REAL CLI ``des validate-feature-delta
    --require-feature-plan --format=json`` -- it must still return ``accepted``.

    ACCEPTED            -- the flipped epic-delta still clears the keystone gate
                           (exit 0, verdict ``accepted``). The flip preserved
                           validity.
    NOT_ACCEPTED        -- the flip broke structural validity (any non-``accepted``
                           verdict / exit != 0).
    EPIC_DELTA_ABSENT   -- the production-path epic-delta does not exist: the
                           maintenance procedure produced nothing. On the current
                           tip every invocation lands here -- the active-RED signal.
    """

    ACCEPTED = "accepted"
    NOT_ACCEPTED = "not_accepted"
    EPIC_DELTA_ABSENT = "epic_delta_absent"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step body a
# single typed lookup + a single composition call (Mandate-12 criterion 3: no
# control flow in step bodies).

FEATURE_STATUS_BY_PHRASE: dict[str, FeatureStatus] = {
    "pending": FeatureStatus.PENDING,
    "in-flight": FeatureStatus.IN_FLIGHT,
    "shipped": FeatureStatus.SHIPPED,
}

MAINTENANCE_ACTION_BY_PHRASE: dict[str, MaintenanceAction] = {
    "picks up": MaintenanceAction.PICK_UP,
    "finalizes": MaintenanceAction.FINALIZE,
}
