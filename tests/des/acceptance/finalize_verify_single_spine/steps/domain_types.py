"""Domain types for the f-finalize-verify-single-spine slice-01 acceptance set.

Every domain noun used in the Gherkin is expressed once here as a typed enum
or NewType (Mandate-12 criterion 1). Step bodies and the composition service
consume these typed parameters -- no raw `str` where a domain enum exists.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


class WorkflowMode(str, Enum):
    """The finalize mode resolved from .nwave/config.yaml:workflow.mode.

    CLASSIC    -- an EXPLICIT `workflow.mode: classic`. TODAY this is the ONLY
                  directory routed to the classic roadmap/execution-log
                  cross-reference; after the REDUCE the dispatch is gone and
                  even this directory runs the single atdd_pure body.
    ATDD_PURE  -- an explicit `workflow.mode: atdd_pure` (the surviving spine).
    UNSET      -- no `workflow.mode` key / no config file. `resolve_workflow_mode`
                  ALREADY resolves this to atdd_pure (DDD-7), so an unconfigured
                  directory is already on the single spine today.
    """

    CLASSIC = "classic"
    ATDD_PURE = "atdd_pure"
    UNSET = "unset"


class ClassicProjectShape(str, Enum):
    """The classic (roadmap-based) deliver-project shape under verification.

    COMPLETE_TRACES -- roadmap.json + execution-log.json with every TDD phase
                       recorded -> the classic cross-reference yields verified
                       (exit 0) TODAY. This is the shape that makes the
                       "still asks for the classic finalize leg" scenario RED
                       now: the classic leg returns "complete DES traces"
                       instead of the atdd_pure missing-ledger verdict.
    """

    COMPLETE_TRACES = "complete_traces"


class IntegrityVerdict(str, Enum):
    """The user-observable verdict of one des verify-integrity invocation.

    Maps onto the preserved 0/1/2 exit-code contract.
    """

    VERIFIED = "verified"  # exit 0
    VIOLATION = "violation"  # exit 1
    USAGE_ERROR = "usage_error"  # exit 2
    CANNOT_EVALUATE = "cannot_evaluate"  # exit 4 (LOUD INDETERMINATE)


# A kebab-case feature identifier (e.g. "finalize-spine-demo").
FeatureId = NewType("FeatureId", str)
