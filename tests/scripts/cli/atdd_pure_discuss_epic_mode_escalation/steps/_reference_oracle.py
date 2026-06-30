"""Reference producer for the discuss-epic-mode slice-04 escalation slice.

A LABELED, deterministic stand-in for the LLM-mediated Phase 1.5 oversized-detection
escalation act. This is TEST-SUPPORT, NOT production code.

Slice-04's deliverable is PROSE: the Phase 1.5 escalation contract is LLM-mediated
skill / command text (DESIGN slice-02/04/05 text contracts: the slice's "code" is
SKILL / COMMAND text, there is NO ``src/des`` surface). The emitter of the
escalation message is the Luna PO agent during a discuss session, never a
``src/des`` function -- Phase 1.5 detection is a heuristic instruction to the
agent, with no validator / gate / structured-config detection surface on the tip
(verified 2026-06-11: nothing in ``src/des`` or ``scripts`` detects oversized
scope; ``carpaccio_slice_gate`` is a DELIVER-time slice-SIZE gate, a different
wave and concept).

These ATs verify the ESC contract (ESC-1..ESC-6) that the LLM-authored escalation
prose MUST satisfy. To witness that contract mechanically without a production
emitter, this module renders a deterministic ESC-conformant escalation message --
a GOLDEN-FILE ANALOGUE. It is the reference the ATs measure the contract against;
it makes no claim to be the production deliverable. Anti-fixture-theater is
inapplicable here precisely because the production deliverable is prose, not a
claimed ``src/des`` function.

This is NOT the presence-watcher anti-pattern. A presence-watcher greps the static
SKILL.md for the literal ``--epic`` -- it passes the instant the crafter types the
literal, testing no behaviour. Here the escalation message is a deterministic
FUNCTION of the fired-signal SET: which signals are named depends on which fired
(ESC-2), and a sub-threshold input produces NO message at all (ESC-6). The ATs
discriminate input -> output behaviour with right-sized vs oversized inputs and a
decline branch -- a golden-file analogue of an input-conditioned message, not a
static-text presence check.

Phase C resolution precedent (2026-06-11, Ruling B, slice-02): the deterministic
producer is suite-local test-support, NEVER a ``src/des`` module imported at the
composition boundary. Slice-04 follows that ruling by construction.

Contract shape (effect isolation): every function here is PURE (signal-set ->
message string, no I/O). The escalation contract has no side effect on the current
tip -- the message is emitted into the discuss transcript, an observation, not a
filesystem mutation. The decline branch (ESC-5) is likewise observable as "zero
epic artifacts", asserted on a real tmp_path tree by the composition.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain_types import EscalationDecision, OversizedSignal


#: ESC-1 trigger threshold: 2+ fired signals from the EXISTING Phase 1.5 closed
#: list mean the request is bigger than one feature (NO new heuristics).
ESCALATION_THRESHOLD = 2

#: ESC-3 the literal flag the escalation message MUST name (discoverability floor,
#: KPI-3). The message proposes epic-mode by naming THIS exact token.
EPIC_MODE_FLAG = "--epic"


@dataclass(frozen=True)
class EscalationMessage:
    """The Phase 1.5 escalation message (ESC-2/ESC-3/ESC-4).

    A structured view of the message the escalation emits when 2+ signals fire.
    The ATs read its typed fields rather than substring-matching free text, so the
    contract is pinned on MEANING (which signals named, the flag proposed, the
    confirmation options) not on incidental wording.

    fired_signals  -- the signals NAMED in the message (ESC-2 explain): exactly the
                      signals that fired, each by its human-readable description.
    proposes_epic_mode -- whether the message proposes epic-mode (ESC-3).
    names_epic_flag -- whether the message names the literal ``--epic`` (ESC-3,
                      KPI-3 discoverability floor).
    confirmation_options -- the closed options the message asks the user to choose
                      from (ESC-4): epic-mode vs continue feature-level. NEVER an
                      auto-switch.
    """

    fired_signals: tuple[OversizedSignal, ...]
    proposes_epic_mode: bool
    names_epic_flag: bool
    confirmation_options: tuple[EscalationDecision, ...]

    def render(self) -> str:
        """Render the escalation message as the maintainer-visible transcript text.

        The discoverability floor (KPI-3): the literal ``--epic`` appears in the
        rendered text AND each fired signal is named. The Luna PO agent authors the
        real wording during the discuss session; this reference guarantees the
        contract-bearing content is present and clear (D-caveman invariant: the
        escalation TEMPLATE stays clear and guiding).
        """
        signal_lines = "\n".join(f"  - {sig.value}" for sig in self.fired_signals)
        options = " / ".join(opt.value for opt in self.confirmation_options)
        return (
            "Your request looks bigger than one feature. These oversized signals "
            "fired:\n"
            f"{signal_lines}\n"
            f"Consider epic-mode -- run `/nw-discuss {EPIC_MODE_FLAG} <id>` to "
            "decompose it into independently-shippable features.\n"
            f"How would you like to proceed? ({options})"
        )


def detect_fired_signals(
    submitted_signals: tuple[OversizedSignal, ...],
) -> tuple[OversizedSignal, ...]:
    """The fired-signal set from a submitted request. Pure.

    The reference detection: a request firing a given set of oversized signals
    reports exactly those signals (de-duplicated, in the closed-list order). No
    new heuristics (ESC-1) -- the set is a subset of the EXISTING Phase 1.5 list.
    """
    return tuple(sig for sig in OversizedSignal if sig in submitted_signals)


def build_escalation(
    fired_signals: tuple[OversizedSignal, ...],
) -> EscalationMessage | None:
    """Build the escalation message for a fired-signal set. Pure.

    ESC-1: returns a message ONLY when 2+ signals fired; otherwise ``None`` (ESC-6
    guardrail -- a right-sized request gets zero escalation, zero new prompts).
    When it returns a message: the message NAMES each fired signal (ESC-2),
    proposes epic-mode naming ``--epic`` (ESC-3), and asks confirmation with the
    closed option set (ESC-4) -- never auto-switching.
    """
    if len(fired_signals) < ESCALATION_THRESHOLD:
        return None
    return EscalationMessage(
        fired_signals=fired_signals,
        proposes_epic_mode=True,
        names_epic_flag=True,
        confirmation_options=(
            EscalationDecision.SWITCH_TO_EPIC_MODE,
            EscalationDecision.CONTINUE_FEATURE,
        ),
    )
