"""The chat offer a completed wave may relay, built here and nowhere else.

The assistant supplies the named wave at entry; this module validates that
the name belongs to the installed wave set. The actual completion decision is
made by the conversation host at the end, from the wave's result. This pure
function maps (installed wave, resolved documentation preference) to a frozen
:class:`WaveEndOffer`; the CLI shell prints it.

The carrier is SPLIT, because the two audiences are different:

- ``chat_text`` is a short ordinary-language question for `ask` and `smart`;
  modes needing result-specific content have no entry-time chat payload.
- ``internal`` contains instructions for the assistant, not user-facing text.

Three representation choices carry obligations the acceptance oracle observes:

- :meth:`CompletedWave.of` validates an installed wave name at the CLI
  boundary. It does not certify that the wave has completed.
- :meth:`ChatOfferText.of` validates the template question against protocol
  labels and command tokens. Result-specific text written by the assistant at
  wave completion is governed by the installed skill instructions instead.
- The resolved behaviour is a CLOSED SUM, not a Boolean: ``Silent`` (no proactive
  chat, because the preference says so), ``Question`` (one optional,
  acceptance-gated question), ``Conditional`` (the same question, gated on the
  wave really having produced optional context), ``Unprompted`` (the deeper
  explanation is delivered directly, nothing to accept) and ``Named`` (the same
  gate as ``Conditional``, but the offer must name at most two topics the wave
  really produced). A Boolean could not tell any of these apart.
- Only the ``ask`` and ``smart`` branches own a relayable chat sentence.
  ``Unprompted`` and ``Named`` carry a directive on an internal row instead,
  because DES cannot author the substance of what a wave produced — and a topic
  name exists only AFTER the wave has a result, which wave entry cannot know.
  ``Silent`` renders ``WAVE-END-OFFER: none``.
- ``INTERNAL-ACCEPTANCE`` appears in every branch that offers a question,
  including conditional and named offers; it is absent for silence and direct
  expansion.

There is no acceptance token and no refusal token. Acceptance is a policy DES
states in ordinary language on an internal row: any affirmative reply in the
user's own language accepts the offer just made; silence or anything else
changes nothing.

Orthogonal to all of that, and TOTAL over every resolved preference, is the
``INTERNAL-ON-REQUEST`` row. The user's right to ask directly for more detail is
not an acceptance of an offer and not a proactive utterance, so it has ONE owner
here — a standing obligation emitted in every branch, ``always-skip`` included.
It is INTERNAL and carries no relayable payload: DES cannot author the substance
of what a wave produced, so a canned sentence would be a lie, and the resolved
preference confines only what the assistant raises on its own initiative.

Nothing here reads a file, an environment variable or a clock.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.domain.result import Failure, Result, Success


if TYPE_CHECKING:
    from des.domain.documentation_density import Density


#: The closed set of installed wave skills (``nWave/skills/nw-<name>``). A name
#: outside it is not a wave this product ships, so it can carry no offer.
INSTALLED_WAVES: tuple[str, ...] = (
    "discover",
    "diverge",
    "discuss",
    "design",
    "devops",
    "distill",
    "deliver",
)

#: The mode that owns the one acceptance-gated question.
_OFFERING_MODE = "ask"

#: The mode that owns proactive silence BY PREFERENCE, not by absent capability.
_SILENT_MODE = "always-skip"

#: The mode that owns the directly delivered explanation, with nothing to accept.
_UNPROMPTED_MODE = "always-expand"

#: The mode that owns the GATED question: offered if and only if the completed
#: wave really produced concrete optional context.
_CONDITIONAL_MODE = "smart"

#: The mode that owns the SAME gate as ``smart``, but whose offer must name at
#: most two topics the completed wave really produced.
_NAMED_MODE = "ask-intelligent"

#: The marker that prefixes the ONE unconditionally relayable row on stdout.
CHAT_MARKER = "WAVE-END-OFFER-CHAT"

#: The marker that prefixes the GATED relayable row. It is DISTINCT from
#: ``CHAT_MARKER`` by construction, not by convention: the shipped consumer rule
#: says «say in chat only the text after ``WAVE-END-OFFER-CHAT: ``», so reusing
#: that marker would make an unaware consumer relay the sentence ALWAYS — the
#: exact negation of a gated offer, and silently (GDP-6). A consumer that does
#: not know this marker relays nothing and degrades towards silence instead.
GATED_CHAT_MARKER = "WAVE-END-OFFER-CHAT-IF"

#: The CLOSED population of what counts as «concrete optional context». Every
#: member is optional BY CONSTRUCTION: the primary result of the wave — what it
#: decided — is deliberately absent, so it alone can never justify an offer.
OPTIONAL_CONTEXT_KINDS: tuple[str, ...] = (
    "an alternative the wave considered and set aside",
    "a trade-off the wave accepted, and what it costs",
    "a risk or an uncertainty the wave carries forward, and who owns it",
    "a constraint or an assumption that shaped the result",
    "a consequence the wave deferred to later work",
)

#: The prefix shared by every row addressed to the assistant alone.
INTERNAL_MARKER = "WAVE-END-OFFER-INTERNAL"

#: The CLOSED population of situations that are NOT the completion of the named
#: wave, and therefore carry no offer at all. An enumeration, never a Boolean
#: ``wave_complete`` flag: a flag states the positive branch and leaves the
#: silence branch without a producer, so the assistant would have to guess which
#: moments it covers. Each member names one moment the assistant can really
#: observe. The four step-terminal outcome words are quoted as WORDS and the
#: literal terminal row prefix is deliberately absent, so no consumer that reads
#: terminal rows by line prefix can mistake an instruction for a second outcome
#: row (GDP-8).
NON_COMPLETION_SITUATIONS: tuple[str, ...] = (
    "a single DES step that ended with the outcome word 'Success' - one "
    "successful 'des craft', or any other single step, completes a step and "
    "not the wave",
    "a single DES step that ended with the outcome word 'Refusal'",
    "a single DES step that ended with the outcome word 'Retry', and every "
    "re-run that follows it",
    "a single DES step that ended with the outcome word 'Indeterminate'",
    "any earlier turn - say nothing about expansion before your final response "
    "for this wave",
    "a wave that stops without completing, whether it was abandoned, blocked "
    "or handed back",
)

_PROTOCOL_LABEL = "WAVE-END-OFFER"
_CAPITAL_RUN = re.compile(r"[A-Z]{3,}")
_REPLY_IMPERATIVE = re.compile(r"\breply\s+[A-Z]{2,}")


@dataclass(frozen=True, slots=True)
class CompletedWave:
    """An installed wave name; completion itself is judged at the chat boundary."""

    name: str

    @staticmethod
    def of(name: str) -> Result[CompletedWave, str]:
        """Return the wave, or the WHY of refusing an uninstalled name."""
        if name not in INSTALLED_WAVES:
            return Failure(
                f"{name!r} is not an installed nWave wave; the installed waves "
                f"are {', '.join(INSTALLED_WAVES)}"
            )
        return Success(CompletedWave(name=name))


@dataclass(frozen=True, slots=True)
class ChatOfferText:
    """Validate a fixed relayable sentence for the `ask` and `smart` branches."""

    sentence: str

    @staticmethod
    def of(sentence: str) -> Result[ChatOfferText, str]:
        """Return the payload, or WHAT/WHY/HOW for a sentence that is not one."""
        shouted = _CAPITAL_RUN.findall(sentence)
        if shouted:
            return Failure(
                f"WHAT: the proposed chat sentence shouts {shouted!r}; WHY: a run "
                "of three or more capitals reads as a protocol label or a command "
                "token, not as conversation; HOW: write the sentence in ordinary "
                "sentence case."
            )
        if _PROTOCOL_LABEL in sentence:
            return Failure(
                f"WHAT: the proposed chat sentence contains {_PROTOCOL_LABEL!r}; "
                "WHY: protocol labels belong to the rows addressed to the "
                "assistant, never to the human; HOW: keep the label out of the "
                "relayable payload."
            )
        if _REPLY_IMPERATIVE.search(sentence):
            return Failure(
                "WHAT: the proposed chat sentence imposes an exact reply token; "
                "WHY: the human must be able to answer, or ignore, in ordinary "
                "language; HOW: ask a plain question and let DES state the "
                "acceptance policy on an internal row."
            )
        return Success(ChatOfferText(sentence=sentence))


@dataclass(frozen=True, slots=True)
class Silent:
    """No proactive chat at wave end, because the resolved preference says so.

    The silence IS the promised behaviour, so the label is ``none`` and the
    internal rows must attribute the silence to the preference rather than to a
    missing capability.
    """


@dataclass(frozen=True, slots=True)
class Question:
    """One optional, acceptance-gated question, carrying its relayable payload."""

    chat_text: str


@dataclass(frozen=True, slots=True)
class Unprompted:
    """The deeper explanation is delivered directly; there is nothing to accept.

    DES cannot author the substance of what a wave produced, so this behaviour
    carries no relayable sentence: the directive lives on an internal row and the
    assistant supplies the substance.
    """


@dataclass(frozen=True, slots=True)
class Conditional:
    """The same question, offered IF AND ONLY IF optional context really exists.

    A member of its own, never a Boolean flag on :class:`Question`: «offer
    always» and «offer only if» are two different observations for the user, and
    a flag on one member would conflate them. It carries the same relayable
    sentence — this value changes WHETHER the offer is said, not what it names —
    plus the closed vocabulary that decides the condition.
    """

    chat_text: str
    triggers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Named:
    """The gated offer whose question must NAME at most two produced topics.

    A member of its own, never a flag on :class:`Conditional`: «offer the
    explanation» and «offer it naming the two most useful topics» are two
    different observations for the user. It carries NO relayable sentence,
    because a topic name exists only AFTER the wave has a result and the
    preference is resolved once at entry, where no result exists yet. DES owns
    the naming RULE; the assistant owns the names.
    """

    triggers: tuple[str, ...]


#: The closed set of wave-end behaviours. A Boolean could not tell silence by
#: preference from a gated offer, nor either from a direct expansion or from an
#: offer that must name what the wave produced — so the carrier is this sum,
#: and the read site matches on it.
WaveEndBehaviour = Silent | Question | Conditional | Unprompted | Named


@dataclass(frozen=True, slots=True)
class WaveEndOffer:
    """The frozen offer: one resolved behaviour, and assistant-only rows."""

    wave: str
    expansion_prompt: str
    provenance: str
    behaviour: WaveEndBehaviour
    internal: tuple[str, ...]


def _chat_sentence(wave: CompletedWave) -> str:
    """The single question, naming the wave, its optionality and silence.

    One question a human answers naturally. It names the completed wave, says
    in plain words that it is optional and that silence changes nothing, and
    ends as a question — so refusing needs no token at all.
    """
    return (
        f"The {wave.name} wave is complete, and this is entirely optional - "
        "your silence changes nothing: would you like me to explain in more "
        "detail what it produced?"
    )


#: The acceptance policy, shared by every branch that actually puts a question.
#: Its presence on a terminal IS the property «an acceptance is required».
_ACCEPTANCE_ROW = (
    f"{INTERNAL_MARKER}-ACCEPTANCE: any affirmative answer in the user's own "
    "language accepts the deeper explanation you have just offered; no answer, "
    "or any other answer, changes nothing. Require no literal token and accept "
    "none as a condition."
)

#: The STANDING obligation, emitted in every branch, silence included. It owns
#: one question and one only — what a DIRECT request from the user for more
#: detail obliges — which is why the acceptance row above no longer mentions it
#: and the silent branch no longer permits it: three independent owners for one
#: rule is exactly how a promise drifts. It is INTERNAL with no relayable
#: payload, because the substance belongs to the wave's own result, which wave
#: entry cannot know, and it names no further command, because none exists.
_ON_REQUEST_ROW = (
    f"{INTERNAL_MARKER}-ON-REQUEST: if the user asks you directly, at any "
    "moment of this wave, for more detail about what it is doing or has done, "
    "answer at once and in substance, and take the substance of that answer "
    "from what this wave has really produced. The resolved preference on the "
    "mode row above governs only what you raise on your own initiative; it "
    "never suppresses, delays, defers or shortens a reply the user asked for - "
    f"{_SILENT_MODE!r} included. Any -WHEN or -NOT-NOW row, and any "
    "restatement of them in a wave skill, restricts proactive raising alone and "
    "never a reply to a direct request. That answer needs no acceptance and "
    "changes neither the accepted documents nor the DES execution; DES supplies "
    "no sentence and no command for it, so write it yourself from the wave's "
    "own result."
)


def _relayable(wave: CompletedWave) -> str:
    """The one product-owned sentence, valid by construction or not built at all."""
    payload = ChatOfferText.of(_chat_sentence(wave))
    if isinstance(payload, Failure):
        # A programming error, not a domain outcome: the sentence template and
        # the closed wave set are both owned here, so a refusal means this
        # module contradicts its own invariant. Crashing IS the right outcome.
        raise ValueError(payload.error)
    return payload.unwrap().sentence


def _silent(wave: CompletedWave) -> tuple[WaveEndBehaviour, tuple[str, ...]]:
    return Silent(), (
        f"{INTERNAL_MARKER}-NOTE: say nothing about expansion when this wave "
        f"ends. That silence follows the resolved preference {_SILENT_MODE!r} - "
        "it is not a missing capability, and there is no offer to make and "
        "nothing for the user to accept.",
    )


def _unprompted(wave: CompletedWave) -> tuple[WaveEndBehaviour, tuple[str, ...]]:
    return Unprompted(), (
        f"{INTERNAL_MARKER}-EXPAND: when the {wave.name} wave ends, explain "
        f"unprompted, in the language of the conversation, what the completed "
        f"{wave.name} wave produced. Ask no question, offer nothing and wait for "
        "no acceptance; DES supplies no sentence for this, so write the "
        "explanation yourself from the wave's own accepted documents.",
        f"{INTERNAL_MARKER}-NOTE: the explanation changes neither the accepted "
        "documents nor the DES execution.",
    )


def _question(wave: CompletedWave) -> tuple[WaveEndBehaviour, tuple[str, ...]]:
    return Question(chat_text=_relayable(wave)), (
        _ACCEPTANCE_ROW,
        f"{INTERNAL_MARKER}-NOTE: say the chat payload and nothing else about "
        "expansion; neither accepting nor ignoring it changes the accepted "
        "documents or the DES execution.",
    )


def _gate_rows(wave: CompletedWave) -> tuple[str, tuple[str, ...]]:
    """The ONE gate shared by every conditional branch: condition + vocabulary.

    The judgement is the assistant's — whether the completed wave really
    produced optional context is a semantic reading of the result, which DES
    never simulates and never authors. DES owns the bytes: the condition and
    the closed population it is decided against. Stating only the positive
    branch would leave the silence branch without a producer, and the silence
    is promised exactly as much as the offer.

    ``smart`` and ``ask-intelligent`` fire on exactly the same triggers, so the
    vocabulary has ONE owner here and is never enumerated a second time: a gate
    that drifted between the two modes would silently widen one of them.
    """
    triggers = tuple(
        f"{INTERNAL_MARKER}-TRIGGER: {kind}" for kind in OPTIONAL_CONTEXT_KINDS
    )
    condition = (
        f"{INTERNAL_MARKER}-CONDITION: make the offer only if the "
        f"{wave.name} wave you have just completed really produced concrete "
        "optional context, of one of the kinds enumerated on the trigger rows "
        "below; otherwise say nothing about expansion, and do not invent "
        "context in order to have something to offer. If you cannot tell, say "
        "nothing: a missed offer is the acceptable error here, a fabricated one "
        "is not."
    )
    return condition, triggers


def _conditional(wave: CompletedWave) -> tuple[WaveEndBehaviour, tuple[str, ...]]:
    """The gated branch: the shared gate, plus the one relayable sentence."""
    condition, triggers = _gate_rows(wave)
    return Conditional(chat_text=_relayable(wave), triggers=triggers), (
        condition,
        *triggers,
        _ACCEPTANCE_ROW,
        f"{INTERNAL_MARKER}-NOTE: when the condition holds, say the gated chat "
        "payload and nothing else about expansion; neither accepting nor "
        "ignoring it changes the accepted documents or the DES execution.",
    )


def _named(wave: CompletedWave) -> tuple[WaveEndBehaviour, tuple[str, ...]]:
    """The same gate as ``smart``, and the naming rule instead of a sentence.

    No relayable row at all — neither the unconditional nor the gated one. The
    names belong to the wave's result, which does not exist yet at entry, so
    DES supplies the rule and the assistant supplies the names. No placeholder
    stands in for a topic either: a placeholder is an invitation to invent one.
    """
    condition, triggers = _gate_rows(wave)
    naming = (
        f"{INTERNAL_MARKER}-NAMING: when the condition holds, write the offer "
        "yourself, as one short question in the language of the conversation. "
        "Name explicitly at most two specific topics — the two most useful to "
        "the user's next decision. Take every name from what the "
        f"{wave.name} wave has really produced, never a category label copied "
        "from the trigger rows. DES names no topic here, because a topic "
        "exists only after the wave has a result, which wave entry cannot "
        "know. Do not invent a topic and never name more than two; if only one "
        "such topic exists, name one; if none exists, say nothing about "
        "expansion. Say that the deeper explanation is optional and that "
        "silence changes nothing."
    )
    return Named(triggers=triggers), (
        condition,
        *triggers,
        naming,
        _ACCEPTANCE_ROW,
        f"{INTERNAL_MARKER}-NOTE: say that one question and nothing else about "
        "expansion; neither accepting nor ignoring it changes the accepted "
        "documents or the DES execution.",
    )


#: TOTAL dispatch over the five legal ``ExpansionPromptMode`` values — every one
#: now has a producer, so there is no fallback left to absorb a sixth member
#: silently. The lookup is read TOTALLY: the caller only ever passes a value the
#: closed configuration set already validated, so a ``KeyError`` here would be a
#: programming error, not a domain outcome.
_BRANCHES = {
    _SILENT_MODE: _silent,
    _UNPROMPTED_MODE: _unprompted,
    _OFFERING_MODE: _question,
    _CONDITIONAL_MODE: _conditional,
    _NAMED_MODE: _named,
}


def _scope_rows(wave: CompletedWave) -> tuple[str, ...]:
    """The moment an offer may be uttered, and the moments that are not it.

    Emitted only in the branches that can utter something. In ``Silent`` nothing
    is ever said about expansion, so a scope sentence would have no consumer at
    all (GDP-10, ``data:consumer-known-before-produced``) — the silence note
    already owns that branch.
    """
    when = (
        f"{INTERNAL_MARKER}-WHEN: say this only in your final response for the "
        f"{wave.name} wave, and only after that whole wave has really "
        "completed. Nowhere else, and never earlier."
    )
    return (
        when,
        *(
            f"{INTERNAL_MARKER}-NOT-NOW: {situation}"
            for situation in NON_COMPLETION_SITUATIONS
        ),
    )


def _resolved_once_row() -> str:
    """The preference lifecycle, stated in EVERY branch, silence included.

    Total where the scope rows are not: the rule «resolved here, once, and never
    read again» applies even where nothing will ever be said, because rereading
    the configuration at the end of a silent wave is exactly as wrong. It names
    the ``GLOBAL-CONFIG`` row the CLI already prints instead of carrying a path
    of its own, so the path string keeps one owner and this function stays free
    of I/O identifiers.
    """
    return (
        f"{INTERNAL_MARKER}-RESOLVED-ONCE: the preference on the mode row above "
        "was resolved here once, for this whole wave, from the configuration "
        "named on the GLOBAL-CONFIG row above. Do not read that configuration "
        "again, do not run des wave-entry again, and invoke no wave-end step: "
        "none exists."
    )


def build_offer(wave: CompletedWave, density: Density) -> WaveEndOffer:
    """Total: every resolved preference yields exactly one offer value.

    Each branch puts everything but the relayable payload on rows addressed to
    the assistant — the resolved mode with its cascade provenance, the
    natural-language acceptance policy where one applies, the gate where one
    applies, the no-effect note. The provenance is echoed there, and only there,
    because it is the one thing distinguishing a preference that was really read
    from a constant block.

    ``_ON_REQUEST_ROW`` is added HERE, beside ``_resolved_once_row``, rather than
    inside the branches: the user's standing right to ask directly is the same
    under every one of the five resolved preferences, so emitting it once at the
    single join point makes it TOTAL by construction and leaves no branch able to
    drift away from it.
    """
    mode_row = (
        f"{INTERNAL_MARKER}-MODE: {density.expansion_prompt} "
        f"(provenance: {density.provenance})"
    )
    behaviour, rows = _BRANCHES[density.expansion_prompt](wave)
    scope = () if isinstance(behaviour, Silent) else _scope_rows(wave)
    return WaveEndOffer(
        wave=wave.name,
        expansion_prompt=density.expansion_prompt,
        provenance=density.provenance,
        behaviour=behaviour,
        internal=(
            mode_row,
            *rows,
            *scope,
            _ON_REQUEST_ROW,
            _resolved_once_row(),
        ),
    )
