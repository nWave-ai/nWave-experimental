"""Provider-neutral model-turn invocation for the owned delivery runner.

ADR-SSOT-002 section 13d.2, "evolve in place, do not delete and recreate": this
port was never wired and its production adapter was a ``NotImplementedError``
placeholder.  Its signature is replaced HERE rather than being deleted and
re-added under a new name -- deleting it would force edits to five re-export
sites and then re-add an equivalent abstraction, leaving one abstraction instead
of two nominal ones for strictly more churn.

Nothing provider-shaped crosses this boundary: no model, no effort level, no
permission mode, no output format, no argv.  Those are adapter-local settings.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


class ModelOutcome(str, Enum):
    """The complete provider-enforced semantic result of one turn."""

    Accepted = "accepted"
    Rejected = "rejected"
    Indeterminate = "indeterminate"


class MalformedModelEnvelope(ValueError):
    """The provider response cannot establish what semantic result occurred."""


#: The floor, in characters, under which a Product Owner observation is not a
#: statement about anything.  MEASURED on the population it constrains -- the
#: ACCEPTED Product Owner turns, the only ones that carry values.  Across every
#: recorded run of 2026-09-05 and 2026-09-06 the shortest real accepted
#: observation is 289 characters (run 20260905T235922Z-583383), so this floor
#: sits more than seven times below every real answer and refuses only what no
#: real turn has ever produced.  The incident it closes is run
#: 20260906T005839Z-648259 turn 06: `{"outcome":"accepted","diagnostic":"test",
#: "values":[{"observation":"a"}]}` -- one character, persisted, followed by
#: four paid turns.  It lives here, next to the value it describes, because the
#: provider schema and the runner both state it and two spellings of one number
#: would drift.
#:
#: The turn's DIAGNOSTIC carries no floor of its own beyond the one character
#: every role owes.  A first measurement read 82 as its minimum, but that came
#: from a sample that mixed non-accepting turns in; on accepted turns alone the
#: shortest real diagnostic is 41 characters
#: (`single-value-accepted-as-walking-skeleton`, run 20260906T014933Z-735633).
#: A 40-character floor there would have left ONE character of margin against a
#: real answer, which is a false positive waiting to happen, and the diagnostic
#: was never the byte that cost anything: the observation was.
MINIMUM_OBSERVATION_CHARACTERS = 40


@dataclass(frozen=True, slots=True)
class ProductValue:
    """One Product-Owner-only observable value from enforced provider IPC."""

    observation: str


class DefectOwner(str, Enum):
    """Who owns one non-accepting acceptance-review finding.

    The reviewer decides this; the software only routes on it.  Two members and
    not more, because exactly two roles can repair a rejected oracle set: the
    acceptance designer, who owns the oracle and its declared supports, and the
    architect of one value, who owns that value's targets, obligations and
    verification.  A third word would name a role no correction edge reaches.
    """

    Oracle = "oracle"
    Design = "design"


@dataclass(frozen=True, slots=True)
class ReviewDefect:
    """The reviewer's own closed routing word, plus the value it speaks about.

    ``value`` is the observation the defect is charged to, or ``None`` for a
    set-level defect belonging to no single value.  A ``Design`` defect without
    one names no architect, and its consumer refuses LOUD rather than choosing
    a value on the reviewer's behalf.
    """

    owner: DefectOwner
    value: str | None = None


class CraftBlocker(str, Enum):
    """Who can unblock one craft turn that could not drive its batch green.

    The crafter decides this; the software only routes on it.  Three members
    and not more.  Two of them name a role OTHER than the crafter that can
    still repair the batch: the acceptance designer, who owns the oracle and
    its declared supports, and the architect of the value, who owns its
    targets, obligations and verification.  The third is the honest "neither
    of them can" -- the crafter could not implement -- which is exactly what
    every craft refusal meant before this word existed, and is why the word
    exists rather than an absent field: a refusal has to say which of the three
    it is.
    """

    Oracle = "oracle"
    Design = "design"
    Product = "product"


@dataclass(frozen=True, slots=True)
class DesignTarget:
    path: str
    decision: str


@dataclass(frozen=True, slots=True)
class DesignFacts:
    """Provider-neutral, minimum semantic design consumed by the runner."""

    targets: tuple[DesignTarget, ...]
    paradigm: str
    decisions: tuple[str, ...]
    oracle: str
    acceptance_supports: tuple[str, ...]
    verification: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class ModelAccounting:
    """Provider-neutral paid-turn facts, or absent when not established."""

    total_cost_usd: float
    num_turns: int
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    session_id: str


@dataclass(frozen=True, slots=True)
class ModelRun:
    """One completed model turn, reported as data rather than an exception.

    ``outcome`` is constrained by the provider's structured-output schema.
    ``diagnostic`` is opaque evidence: callers must not parse or branch on
    model-authored prose.  A failed turn also carries its verbatim exit status
    and provider-neutral ``retry_safe`` fact.
    """

    outcome: ModelOutcome
    diagnostic: str
    exit_status: int
    retry_safe: bool
    product_values: tuple[ProductValue, ...] = ()
    accounting: ModelAccounting | None = None
    design_facts: DesignFacts | None = None
    review_defect: ReviewDefect | None = None
    craft_blocker: CraftBlocker | None = None


class TaskInvocationPort(ABC):
    """Port for invoking one sub-agent turn and observing its terminal."""

    @abstractmethod
    def invoke(
        self,
        *,
        role_id: str,
        prompt: str,
        cwd: Path,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
    ) -> ModelRun:
        """Run one turn of ``role_id`` over ``prompt`` with ``cwd`` as its root.

        ``role_id`` is derived by the caller from route and paradigm and is never
        CLI caller input, so no caller can alter the delivery route.

        ``max_product_values`` is the inclusive upper bound on ``product_values``
        for THIS call: the size of the replacement window the caller is
        correcting.  It is a provider-neutral cardinality, not a provider
        setting.  An adapter declares it to the provider AND enforces it on the
        answer, so a turn outside the window never reaches the caller and the
        caller keeps no cardinality precondition of its own.  ``None`` means the
        call declares no window.

        ``defect_values`` is the closed set of value observations a reviewer may
        charge a defect to on THIS call.  Like the window it is a
        provider-neutral fact of the call, not a provider setting, and for the
        same reason: an adapter declares it so the model is corrected inside its
        own turn, and re-states it on the answer so an envelope that never met
        that validator is still refused.  An empty tuple names no chargeable
        value.

        Returns:
            The completed :class:`ModelRun`.

        Raises:
            MalformedModelEnvelope: the provider response did not carry the
                enforced typed outcome.  This is indeterminate.
        """
