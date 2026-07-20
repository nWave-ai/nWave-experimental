"""Domain types -- des-refactor-fixer-swarm slice-01 acceptance set (Mandate 12).

Typed enums for the Given-side arrangements the slice-01 composition needs.
Step/composition methods consume these typed parameters, never a raw ``str``
(Mandate 12 criterion 2).
"""

from __future__ import annotations

from enum import Enum


class IntegrationTreeState(str, Enum):
    """The integration branch's tree state a merge-back attempt observes (D4/D5)."""

    CLEAN = "clean"
    DIRTY = "dirty"


class DrainOutcome(str, Enum):
    """Whether the agent's work on an item ultimately merges (pile-move gate)."""

    SUCCEEDS = "succeeds"
    FAILS_GREEN_TO_GREEN = "fails_green_to_green"


class DispatchMode(str, Enum):
    """The DES-MODE value a dispatch prompt may carry (slice-03, D8).

    The `.value` is the literal token the DES-MODE marker carries; ABSENT is a
    sentinel meaning "no DES-MODE marker line at all". Step/composition helpers
    consume this typed parameter, never a raw ``str`` (Mandate-12 criterion 2).
    """

    REFACTOR = "refactor"  # the fixer-swarm dispatch mode (slice-03)
    FIND = "find"  # the finder-swarm dispatch mode (slice-03)
    ATDD_PURE = "atdd_pure"  # the already-shipped carpaccio dispatch mode
    ORCHESTRATOR = "orchestrator"  # a classic orchestrator dispatch
    ABSENT = "absent"  # sentinel: no DES-MODE marker at all


class RecognitionVerdict(str, Enum):
    """The user-observable verdict a mode classifier returns (slice-03, D8).

    Mirrors ``classify_atdd_pure_dispatch``'s three-way vocabulary. A well-formed
    fixer/finder dispatch is VALID (spine-recognized); any other/absent mode is
    ABSENT; DEFECTIVE is the malformed-marker verdict a well-formed fixer/finder
    dispatch must NEVER receive.
    """

    ABSENT = "absent"
    VALID = "valid"
    DEFECTIVE = "defective"


class EntryGateAgentVerdict(str, Enum):
    """The verdict token a slice-04 stand-in agent emits on stdout -- the
    Given-side arrangement for entry-gate acceptance tests (Mandate 12,
    des-refactor-fixer-swarm slice-04). Mirrors
    ``des.domain.refactor.entry_gate.EntryGateVerdict``'s 5-way closed set
    verbatim so a Given-side typo cannot silently drift from the production
    enum's token spelling.
    """

    REFACTOR_SAFE = "REFACTOR_SAFE"
    CHARACTERIZE_FIRST = "CHARACTERIZE_FIRST"
    ABSTAINED = "ABSTAINED"
    MECHANICAL_RENAME_EXEMPT = "MECHANICAL_RENAME_EXEMPT"
    MIKADO_ESCALATION = "MIKADO_ESCALATION"


class DeclaredParadigm(str, Enum):
    """The recognized closed set of declared-paradigm lens tokens a pile item
    may carry (D10, slice-05). These are the ONLY two values
    ``select_paradigm_lens`` may proceed on; any other parsed token is
    unrecognized and dispatch must refuse before the worktree/agent
    invocation (AT-9). Values match the literal tokens already established by
    this feature's own pile grammar precedent (``composition.py``'s
    ``_DEFAULT_PARADIGM``, ``des/cli/refactor.py``'s grammar example, and this
    repo's own ``CLAUDE.md`` "## Development Paradigm" convention) -- never
    the ``oop``/``fp`` abbreviation pair used by an unrelated CLI knob
    (``nw-design --paradigm=[auto|oop|fp]``)."""

    OBJECT_ORIENTED = "object-oriented"
    FUNCTIONAL = "functional"
