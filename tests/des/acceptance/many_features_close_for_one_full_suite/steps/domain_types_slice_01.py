"""DISTILL-interim wire contract for `des feature-end run-batch` (slice-01).

No production code exists yet (`run-batch` is not yet a registered
`feature-end` verb; `src/des/application/feature_end_batch_service.py` is a
RED scaffold per DESIGN D-D3). Per feature-delta `Wave: DESIGN / [REF]
Driving Ports`, the CLI emits JSON-lines: ZERO or more per-member lines
(reusing the EXISTING `FeatureEndCycleComplete` / `FeatureEndCycleRefused` /
`FeatureEndCycleIndeterminate` payload shapes verbatim, verb `"run-batch"`),
followed by exactly ONE terminal batch-level line:

    {"event": "FeatureEndBatchManifestRefused", "verb": "run-batch",
     "error": <WHAT+WHY+HOW>}
    # -- OR, on a valid manifest whose shared full-suite leg is RED --
    {"event": "FeatureEndBatchRefused", "verb": "run-batch", "error": ...,
     "failing_tests": [...], "failing_count": N, "junit_artifact": <path>}
    # -- OR, on a valid manifest whose shared full-suite leg is
    # PASS/NOT_APPLICABLE (member lines already printed, in manifest order) --
    {"event": "FeatureEndBatchComplete", "verb": "run-batch",
     "members": N, "succeeded": x, "refused": y, "indeterminate": z}

`BatchRunOutcome` is the PORT-EXPOSED observable this slice's step bodies
assert on (Mandate 8 Universe) -- independently re-derived from REAL
filesystem state (the persisted JUnit artifact COUNT under
`.nwave/telemetry/feature-end/`) and the REAL AT-completion ledger JSONL
wherever possible, not solely from the not-yet-existing payload, so the RED
reason is genuine business behaviour missing, never a parsing artifact of an
absent module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SuiteStatePhrase(Enum):
    """The 2 fixture states the shared `Given` step selects between
    (typed-parameter lookup, Mandate-12 criterion 2 -- never a raw string
    dispatch)."""

    GREEN = "green"
    GENUINELY_RED = "genuinely red"


PHRASE_BY_TEXT: dict[str, SuiteStatePhrase] = {
    phrase.value: phrase for phrase in SuiteStatePhrase
}


@dataclass(frozen=True)
class BatchRunOutcome:
    """Port-exposed observable outcome of one `feature-end run-batch` call.

    Every field is re-derivable from a REAL filesystem/ledger read,
    independent of whether the not-yet-existing CLI ever produces a
    parseable payload -- the RED reason stays "wrong behaviour", never "no
    JSON to parse".
    """

    exit_code: int
    batch_event: str | None
    member_count: int
    member_success_count: int
    member_refused_count: int
    junit_artifact_count: int
    total_feature_end_records: int
    failing_tests_named: bool
    refusal_error_text: str
