"""Domain types for the oss-review-verdict-demotion S2 acceptance slice.

Mandate-12 criterion 1: every domain noun used in the S2 Gherkin is expressed
once here as a typed enum / NewType. Step bodies and the composition service
consume these typed parameters -- no raw ``str`` where a domain enum exists.

S2 demotes the PRODUCER (``record_at_review_verdict``): it writes an APPROVED
verdict record carrying the content-seal + reviewer identity but NO
``hmac_sha256`` field, it resolves NO signing key (key absence is a non-event),
and it is discoverable through the ``des`` dispatcher as
``des record-at-review-verdict`` (D-register). The post-demotion producer
vocabulary therefore has NO signing-key noun -- the record-presence fields are
the whole contract.

S1's ``domain_types.py`` already owns ``FeatureId`` / ``SliceId`` for the
neighbour gate slice; this S2-suffixed module owns the producer-side nouns so
the two slice modules never collide on a type name (single-source per slice).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-review-verdict-demotion").
FeatureId = NewType("FeatureId", str)

# A ``slice-NN`` slice identifier (e.g. "slice-02").
SliceId = NewType("SliceId", str)


class ProducerEntryPoint(str, Enum):
    """The driving surface through which the operator records a verdict.

    The S2 contract pins BOTH the direct producer entry and the dispatcher
    entry as one coupled "keyless AND discoverable" surface (D-register).

    DIRECT      -- the producer invoked at its own argv entry
                   (``des.cli.at_review_verdict.main``). The pre-D-register
                   invocation shape; the keyless write contract is pinned here.
    DISPATCHER  -- the producer reached through the ``des`` single entry point
                   (``des record-at-review-verdict ...`` ->
                   ``des.cli.__main__.main``). The D-register seam: the producer
                   is discoverable as a first-class subcommand, symmetric with
                   the already-registered ``record-discuss-review``.
    """

    DIRECT = "direct"
    DISPATCHER = "dispatcher"


class ProducerOutcome(str, Enum):
    """User-observable outcome of one verdict-recording invocation.

    Maps onto the producer's exit-code + ledger-write contract.

    RECORDED  -- the producer exited successfully (exit 0) AND appended exactly
                 one ATReviewVerdict record for the entering slice.
    """

    RECORDED = "recorded"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step body
# a single typed lookup + a single composition call (Mandate-12 criterion 3:
# no control flow in step bodies).

ENTRY_POINT_BY_PHRASE: dict[str, ProducerEntryPoint] = {
    "the at-review-verdict producer directly": ProducerEntryPoint.DIRECT,
    "the discoverable des record-at-review-verdict subcommand": (
        ProducerEntryPoint.DISPATCHER
    ),
}
