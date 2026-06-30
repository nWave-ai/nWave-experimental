"""Domain types for the discuss-epic-mode slice-04 escalation slice.

Slice-04 value: a user who has never heard of epic-mode discovers it exactly at
the moment of need -- Phase 1.5 oversized-detection EXPLAINS which signals fired,
proposes epic-mode (naming ``--epic``), and ASKS confirmation; a silent giant plan
can no longer happen. The "code" of this slice is SKILL / COMMAND text (DESIGN
slice-02/04/05 text contracts) -- there is NO ``src/des`` surface. DESIGN pins the
ESC contract (ESC-1..ESC-6) as the AT-citable specification of what the Phase 1.5
escalation message MUST satisfy.

Every domain noun in the Gherkin is expressed once here as a typed enum or NewType
(Mandate-12 criterion 1). Step bodies and the composition service consume these
typed parameters -- no raw ``str`` where a domain enum exists.

S1 step-text uniqueness: the slice-02 sibling suite speaks "the maintainer runs
the epic-mode authoring on the epic" -- the ``--epic`` authoring act -- and "the
produced epic-delta". This suite speaks "the maintainer submits a request firing
{n} oversized signals" -- the Phase 1.5 detection act -- and "the escalation
message". The domain nouns differ, so the step phrases never collide.
"""

from __future__ import annotations

from enum import Enum


class OversizedSignal(str, Enum):
    """The EXISTING Phase 1.5 closed signal list (ESC-1 -- NO new heuristics).

    Mirrors the heuristics already in ``nWave/skills/nw-discuss/SKILL.md``
    Phase 1.5 (Scope Assessment): the five oversized signals, any 2+ of which mean
    the request is bigger than one feature. The escalation contract NAMES each
    fired signal (ESC-2 explain) -- so the signal is a first-class typed noun, not
    a free-text string.

    MANY_USER_STORIES        -- >10 user stories.
    MANY_BOUNDED_CONTEXTS    -- >3 bounded contexts or modules.
    MANY_INTEGRATION_POINTS  -- the walking skeleton requires >5 integration points.
    LONG_EFFORT              -- estimated effort >2 weeks.
    MANY_INDEPENDENT_OUTCOMES -- multiple independent user outcomes that could ship
                                separately.
    """

    MANY_USER_STORIES = "more than 10 user stories"
    MANY_BOUNDED_CONTEXTS = "more than 3 bounded contexts or modules"
    MANY_INTEGRATION_POINTS = "walking skeleton requires more than 5 integration points"
    LONG_EFFORT = "estimated effort over 2 weeks"
    MANY_INDEPENDENT_OUTCOMES = (
        "multiple independent user outcomes that could ship separately"
    )


class EscalationDecision(str, Enum):
    """The user's response to the escalation's confirmation ask (ESC-4/ESC-5).

    The escalation ASKS confirmation with closed options (ESC-4); the user decides
    (the tool NEVER auto-switches -- §22.0-coherent). The two closed responses:

    SWITCH_TO_EPIC_MODE  -- the user confirms epic-mode; the run authors an
                            epic-delta (slice-02's ``--epic`` procedure).
    CONTINUE_FEATURE      -- the user declines; standard feature-level DISCUSS
                            continues, zero epic artifacts (ESC-5).
    """

    SWITCH_TO_EPIC_MODE = "switch_to_epic_mode"
    CONTINUE_FEATURE = "continue_feature"


class EscalationOutcome(str, Enum):
    """Maintainer-observable outcome of the Phase 1.5 detection (the ESC verdict).

    The escalation is a FUNCTION of the fired-signal set: 2+ signals -> an
    escalation message is emitted (ESC-1 trigger); fewer -> none (ESC-6 guardrail).
    This is the maintainer-observable verdict the slice-04 ATs read.

    ESCALATED              -- 2+ signals fired: the escalation message was emitted,
                              naming the fired signals (ESC-2), proposing epic-mode
                              and naming ``--epic`` (ESC-3), asking confirmation
                              (ESC-4). The happy path -- AT-1.
    NO_ESCALATION          -- fewer than 2 signals fired (right-sized input): zero
                              escalation, zero new prompts (ESC-6 guardrail). AT-3.
    EPIC_MODE_CONFIRMED    -- 2+ signals fired AND the user chose
                              SWITCH_TO_EPIC_MODE: the run proceeds to epic-mode.
    FEATURE_LEVEL_CONTINUED -- 2+ signals fired AND the user chose CONTINUE_FEATURE:
                              standard feature-level DISCUSS continues, zero epic
                              artifacts (ESC-5). AT-2.
    ESCALATION_ABSENT      -- the Phase 1.5 escalation contract is undefined: no
                              detection wiring produced any outcome. On the current
                              tip the escalation procedure does not exist, so every
                              slice-04 invocation lands here -- the active-RED
                              missing-functionality signal, NOT a real outcome.
    """

    ESCALATED = "escalated"
    NO_ESCALATION = "no_escalation"
    EPIC_MODE_CONFIRMED = "epic_mode_confirmed"
    FEATURE_LEVEL_CONTINUED = "feature_level_continued"
    ESCALATION_ABSENT = "escalation_absent"


# Gherkin-phrase -> typed-value lookups. Module-level dicts keep each step body a
# single typed lookup + a single composition call (Mandate-12 criterion 3: no
# control flow in step bodies).

ESCALATION_DECISION_BY_PHRASE: dict[str, EscalationDecision] = {
    "epic-mode": EscalationDecision.SWITCH_TO_EPIC_MODE,
    "continue feature-level": EscalationDecision.CONTINUE_FEATURE,
}
