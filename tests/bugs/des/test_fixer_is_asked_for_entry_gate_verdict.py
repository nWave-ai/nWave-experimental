# @feature-fix-fixer-emits-entry-gate-verdict
"""Regression AT -- the drain's entry gate has a CONSUMER and no PRODUCER.

RCA (fix-fixer-emits-entry-gate-verdict dispatch, confirmed 2026-07-22):
`des refactor` refuses to merge any drained item unless the fixer's own
stdout carries one of five literal tokens (`REFACTOR_SAFE`,
`MECHANICAL_RENAME_EXEMPT`, `CHARACTERIZE_FIRST`, `ABSTAINED`,
`MIKADO_ESCALATION`); absent one it records `EntryGateVerdictMissing`, tears
the worktree down and merges nothing
(`src/des/application/refactor_drain_service.py::_entry_gate_refusal`).

Those tokens exist ONLY in the enum that defines them
(`src/des/domain/refactor/entry_gate.py`), in that consumer, in docs, and in
TEST FIXTURES. NOTHING in the production path ever asks the fixer to emit
one: `DEFAULT_TEMPLATE_TEXT`
(`src/des/domain/refactor/prompt_template.py:27-34`) says only "Fix the
following tech-debt item" plus five item fields, and
`scripts/refactor_agent.py::_as_crafter` adds a role framing and a
behaviour-preservation instruction with no verdict clause. So the default
outcome of a REAL drain is a BLOCKED drain -- exactly the charter's reported
symptom ("nothing is ever merged"). The suite is green only because the
doubles were taught to echo the token (`tests/des/refactor/composition.py`
uses `sh -c "printf 'REFACTOR_SAFE\\n'"`) while production received no
equivalent change; ZERO tests exercise `scripts/refactor_agent.py`.

Second, subtler defect, also covered here: `classify_entry_gate` falls back
to a `\\b`-anchored regex over the WHOLE output, iterating the enum in
DECLARATION order with `REFACTOR_SAFE` declared FIRST, so
"I cannot certify this as REFACTOR_SAFE.\\nVerdict: CHARACTERIZE_FIRST\\n"
classifies as REFACTOR_SAFE -- it MERGES an item the fixer explicitly
REFUSED. Dormant today only because no token is ever emitted; asking the
fixer for a verdict ARMS it, since an LLM explaining why it will not certify
is the single most likely shape of a refusal.

Charter: docs/product/expectations/fix-fixer-emits-entry-gate-verdict/
a-maintainer-drains-tech-debt-and-only-the-real-fixes-land.md

Driving surfaces (Mandate 16, reuse-first -- no parallel harness):
  * Layer 3 composition -- `RefactorSwarmComposition.run_drain_one_item` /
    `run_drain_capturing_delivered_prompt` drive the REAL
    `RefactorDrainService.drain_one` with the REAL production adapters
    against a hermetic git repo (Pillar 3).
  * The real domain function `classify_entry_gate`, called directly, for the
    ambiguity/negation contract (a pure function -- its own port).
  * The REAL actuator `scripts/refactor_agent.py` in a subprocess against a
    stub headless CLI, for the boundary nobody covered.

RED-vs-guard status is stated per section below; sections C and the
preservation cases in D/E PASS today ON PURPOSE -- they are the guard that
must never regress.

covers: bug-observable (EXP-fix-fixer-emits-entry-gate-verdict-1)
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from des.domain.refactor.entry_gate import (
    ENTRY_GATE_VERDICT_MISSING,
    EntryGateVerdict,
    classify_entry_gate,
)
from tests.des.refactor.composition import (
    RefactorSwarmComposition,
    explanation_beside_token,
)
from tests.des.refactor.domain_types import EntryGateAgentVerdict


pytestmark = pytest.mark.acceptance


#: The only two verdicts that let an item through to merge
#: (`RefactorDrainService._entry_gate_refusal`). Every other outcome --
#: including "I could not tell" -- must refuse.
MERGE_PERMITTING = (
    EntryGateVerdict.REFACTOR_SAFE,
    EntryGateVerdict.MECHANICAL_RENAME_EXEMPT,
)

#: A token that is merely LISTED tells the fixer nothing about WHEN to choose
#: it. This many words of accompanying prose is the mechanical floor that
#: distinguishes an explained token from a bare enumeration.
_MIN_EXPLANATION_WORDS = 4

_ITEM_ID = "TD-001"


@pytest.fixture(scope="module")
def delivered_prompt(tmp_path_factory) -> str:
    """The exact text a REAL fixer receives from a REAL drain.

    Module-scoped because it costs one full drain (hermetic git repo,
    per-worktree venv, green-to-green run, merge-back) and every assertion in
    section A interrogates the SAME delivered artefact.
    """
    root = tmp_path_factory.mktemp("delivered-prompt")
    composition = RefactorSwarmComposition(root)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id=_ITEM_ID)
    return composition.run_drain_capturing_delivered_prompt()


# =========================================================================
# A -- THE ASK (the headline defect). RED today: the delivered prompt asks
#      for no verdict at all, so a real fixer has no way to know it is
#      expected to emit one.
# =========================================================================


def test_the_prompt_the_fixer_receives_asks_it_to_emit_an_entry_gate_verdict(
    delivered_prompt: str,
):
    """Given a real drain dispatches a fixer, When the fixer reads the prompt
    file the harness rendered for it, Then that prompt asks it to report an
    entry-gate verdict on its own output -- the drain cannot demand a token it
    never requested.

    CONTRACT_SHAPE: bounded-change
    """
    lowered = delivered_prompt.lower()

    assert "verdict" in lowered, (
        "the delivered prompt must ask the fixer for a VERDICT -- the drain "
        "refuses to merge without one, so a prompt that never mentions it "
        "guarantees every item is refused. Delivered prompt was:\n"
        f"{delivered_prompt}"
    )
    assert any(word in lowered for word in ("stdout", "print", "emit", "output")), (
        "the delivered prompt must tell the fixer WHERE to put the verdict "
        "(its own stdout is the only channel the harness reads, via "
        "AgentInvocationResult.stdout). Delivered prompt was:\n"
        f"{delivered_prompt}"
    )


@pytest.mark.parametrize(
    "verdict", list(EntryGateVerdict), ids=lambda verdict: verdict.value
)
def test_every_entry_gate_token_reaches_the_fixer_with_an_explanation_of_its_meaning(
    delivered_prompt: str, verdict: EntryGateVerdict
):
    """Given the drain classifies the fixer's output against a five-way closed
    set, When the fixer is asked for a verdict, Then every token in that set
    is offered to it WITH what it means -- so choosing one is a judgement
    about the item, not a ritual incantation copied off a list.

    Parametrised per token so a fix that documents four of five fails
    NAMING the one it dropped.

    CONTRACT_SHAPE: bounded-change
    """
    assert verdict.value in delivered_prompt, (
        f"the delivered prompt never mentions {verdict.value} -- a fixer "
        "cannot emit a token it was never offered, and the drain's closed "
        f"set is exactly {[member.value for member in EntryGateVerdict]}. "
        f"Delivered prompt was:\n{delivered_prompt}"
    )

    explanation = explanation_beside_token(delivered_prompt, verdict.value)
    assert len(explanation.split()) >= _MIN_EXPLANATION_WORDS, (
        f"{verdict.value} is listed but not EXPLAINED -- a bare token list "
        "makes the choice a ritual instead of a judgement, and the token a "
        "fixer picks decides whether real work merges or is thrown away. "
        f"Found only {explanation!r} beside it in:\n{delivered_prompt}"
    )


# =========================================================================
# B -- THE ASK SURVIVES A USER TEMPLATE. RED today. The prompt template is a
#      deliberately user-editable seam; the verdict protocol is NOT the
#      user's to delete, because deleting it silently blocks every drain.
# =========================================================================


_USER_TEMPLATE_WITHOUT_ANY_VERDICT_INSTRUCTION = (
    "Please fix this for me, briefly.\n\n"
    "Item: {item_id}\n"
    "Defect: {defect}\n"
    "Proposed solution: {proposed_solution}\n"
)


def test_a_user_authored_template_can_never_disarm_the_entry_gate_verdict_ask(
    tmp_path,
):
    """Given a maintainer has replaced `.nwave/refactor-agent-prompt.md` with
    their own wording that says nothing about verdicts, When a drain renders
    and delivers that template, Then the entry-gate protocol is STILL in the
    prompt the fixer receives -- the ask is harness-owned, not a default a
    template edit can silently remove and thereby block every future drain.

    The maintainer's own words must survive too: the protocol is ADDED to
    their template, never a replacement for it.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id=_ITEM_ID)
    composition.write_user_prompt_template(
        _USER_TEMPLATE_WITHOUT_ANY_VERDICT_INSTRUCTION
    )

    prompt = composition.run_drain_capturing_delivered_prompt()

    assert "Please fix this for me, briefly." in prompt, (
        "the maintainer's own template text must still be delivered -- the "
        f"verdict protocol is additive, never a replacement. Got:\n{prompt}"
    )
    missing = [
        member.value for member in EntryGateVerdict if member.value not in prompt
    ]
    assert not missing, (
        "a user-authored template that never mentions verdicts must NOT be "
        "able to disarm the ask: the harness owns it and appends it to every "
        f"delivered prompt. Missing tokens: {missing}. Got:\n{prompt}"
    )
    assert "verdict" in prompt.lower(), (
        "the delivered prompt must still ASK for a verdict even when the "
        f"user's template does not. Got:\n{prompt}"
    )


# =========================================================================
# C -- THE ANTI-UNCONDITIONAL GUARD. *** THE MOST IMPORTANT SECTION HERE. ***
#
# These two tests PASS TODAY, deliberately. They exist so that the fix for
# sections A/B can never be "simplified" into an unconditional emission of
# REFACTOR_SAFE -- in the prompt protocol, in `scripts/refactor_agent.py`,
# in the harness, or in `classify_entry_gate` itself. Any such shortcut
# turns the drain into a machine that merges whatever it is handed, which is
# strictly WORSE than today's defect: today the drain merges nothing and the
# repository stays intact; an unconditional verdict merges unreviewed work
# into a maintainer's branch while REPORTING that it was verified.
#
# WEAKENING, DELETING, OR MARKING THESE TESTS xfail DEFEATS THE ENTIRE GATE.
# If they start failing, the gate has been disarmed -- fix the production
# code, never the assertion. The charter's own oracle says it directly: "a
# drain that refuses everything and a drain that merges everything look
# IDENTICAL on a pile of good items"; these tests are what breaks that
# symmetry.
# =========================================================================


def test_a_fixer_emitting_no_verdict_at_all_is_never_merged_and_leaves_the_repo_untouched(
    tmp_path,
):
    """Given a fixer whose output carries NO entry-gate token whatsoever,
    When a full drain runs it end to end, Then the item is refused with the
    NAMED `EntryGateVerdictMissing` reason and every port-exposed observable
    -- pile file, paid file, worktree list, HEAD -- is EXACTLY as it was.

    Silence must never be read as consent. If a future change makes the
    verdict unconditional, this test fails, and that failure is the point.

    CONTRACT_SHAPE: unbounded-preservation
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id=_ITEM_ID)
    before = composition.capture_universe()

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_emitting_no_recognized_verdict()
    )
    after = composition.capture_universe()

    assert result.merged is False, (
        "an item whose fixer emitted no verdict must NEVER merge -- if this "
        "fails, the entry gate has been made unconditional and the drain now "
        "merges unreviewed work while reporting it as verified"
    )
    assert result.drained is False, (
        "an unverdicted item must never be REPORTED as drained -- what the "
        "command says must match what the repository shows"
    )
    assert result.merge_blocked_reason == ENTRY_GATE_VERDICT_MISSING, (
        "the refusal must NAME itself so a maintainer can tell 'I checked "
        "this and it is good' from 'I never managed to check this'; got "
        f"{result.merge_blocked_reason!r}"
    )
    assert composition.pile_contains(_ITEM_ID), (
        f"{_ITEM_ID} must stay in techdebt.md -- an item must never vanish "
        "from the pile without a corresponding commit"
    )
    assert not composition.paid_contains(_ITEM_ID), (
        f"{_ITEM_ID} must never be recorded in paidtechdebt.md without merging"
    )
    assert after == before, (
        "a refused item must leave NO residue in ANY port-exposed observable "
        "(pile file, paid file, git worktree list, HEAD). Changed names: "
        f"{sorted(name for name in before if before[name] != after.get(name))}"
    )


@pytest.mark.parametrize(
    "verdict",
    [
        EntryGateAgentVerdict.CHARACTERIZE_FIRST,
        EntryGateAgentVerdict.ABSTAINED,
        EntryGateAgentVerdict.MIKADO_ESCALATION,
    ],
    ids=lambda verdict: verdict.value,
)
def test_a_fixer_that_declines_to_certify_is_never_merged_and_never_reaches_paidtechdebt(
    tmp_path, verdict: EntryGateAgentVerdict
):
    """Given a fixer that emits a DECLINING verdict -- it wants the code
    characterized first, abstains outright, or escalates to Mikado -- When a
    full drain runs it end to end, Then its work is NOT merged and the item is
    NOT recorded as paid.

    The sibling of the test above: it proves the gate discriminates on the
    CONTENT of the verdict, not merely on a token being present. An
    unconditional REFACTOR_SAFE anywhere in the chain fails this too.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.prepare_clean_integration_branch()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id=_ITEM_ID)

    result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_emitting_verdict(verdict)
    )

    assert result.merged is False, (
        f"a fixer that answered {verdict.value} refused to certify its own "
        "work -- the drain must never merge over that refusal"
    )
    assert result.drained is False, (
        f"an item its own fixer answered {verdict.value} for must never be "
        "reported as drained"
    )
    assert not composition.paid_contains(_ITEM_ID), (
        f"{verdict.value} must never move the item to paidtechdebt.md"
    )
    assert composition.pile_contains(_ITEM_ID), (
        f"{verdict.value} must leave the item visible in techdebt.md for the "
        "maintainer, never silently consume it"
    )


# =========================================================================
# D -- AMBIGUITY AND NEGATION MUST NOT MERGE.
#      The negation cases are RED today (they classify as REFACTOR_SAFE, i.e.
#      they MERGE an item the fixer explicitly refused). The bare-line cases
#      are green-and-guarding: hardening the classifier must not over-correct
#      into refusing an unambiguous affirmative attestation.
# =========================================================================


@pytest.mark.parametrize(
    "agent_output",
    [
        pytest.param(
            "I cannot certify this as REFACTOR_SAFE.\nVerdict: CHARACTERIZE_FIRST\n",
            id="names-the-safe-token-to-decline-it-then-declines",
        ),
        pytest.param(
            "I cannot certify this as REFACTOR_SAFE.\n",
            id="bare-negation-of-the-safe-token-and-nothing-else",
        ),
        pytest.param(
            "Weighing REFACTOR_SAFE against ABSTAINED, I could not decide.\n",
            id="two-tokens-in-prose-no-bare-token-line",
        ),
        pytest.param(
            "This is not MECHANICAL_RENAME_EXEMPT, and it is not "
            "REFACTOR_SAFE either.\n",
            id="two-merge-permitting-tokens-both-negated",
        ),
        pytest.param(
            "Verdict: REFACTOR_SAFE is what I would emit if a test net "
            "existed, but none does, so CHARACTERIZE_FIRST.\n",
            id="conditional-safe-resolving-to-characterize-first",
        ),
        pytest.param(
            "MECHANICAL_RENAME_EXEMPT would apply to a pure rename; this was "
            "not one, so I ABSTAINED.\n",
            id="exempt-token-explained-then-abstained",
        ),
    ],
)
def test_ambiguous_or_negated_fixer_prose_is_never_classified_as_merge_permitting(
    agent_output: str,
):
    """Given a fixer explains, in prose, why it will NOT certify -- naming the
    merge-permitting token in the very sentence that declines it -- When the
    drain classifies that output, Then the result is never a merge-permitting
    verdict.

    A merge-permitting verdict is earned only by an unambiguous affirmative
    attestation. Ambiguity resolves to refusal (a declining verdict, or None
    -> `EntryGateVerdictMissing`), never to a merge: refusing an item that
    was fine costs a re-run, merging an item the fixer refused costs the
    maintainer's repository.

    An LLM explaining why it cannot certify is the single most likely shape
    of a real refusal, so this is the arming defect, not an exotic edge case.

    CONTRACT_SHAPE: bounded-change
    """
    classified = classify_entry_gate(agent_output)

    assert classified not in MERGE_PERMITTING, (
        "prose that DECLINES to certify must never be read as permission to "
        f"merge; classified {agent_output!r} as {classified!r}, which lets "
        "the item straight through the entry gate"
    )


@pytest.mark.parametrize(
    "verdict", list(EntryGateVerdict), ids=lambda verdict: verdict.value
)
def test_a_bare_verdict_line_is_still_honoured_after_prose_naming_another_token(
    verdict: EntryGateVerdict,
):
    """Given a fixer discusses one token in prose and then states its actual
    verdict as a bare line, When the drain classifies that output, Then the
    BARE LINE wins.

    Green-and-guarding: this is the contract that stops the ambiguity fix
    above from over-correcting into a classifier that refuses everything --
    which would leave the maintainer with exactly today's symptom under a new
    name.

    CONTRACT_SHAPE: unbounded-preservation
    """
    other = next(member for member in EntryGateVerdict if member is not verdict)
    agent_output = (
        f"I considered {other.value} and could not reach it.\n{verdict.value}\n"
    )

    assert classify_entry_gate(agent_output) is verdict, (
        f"a bare {verdict.value} line is an unambiguous attestation and must "
        f"be honoured even when {other.value} was discussed above it; got "
        f"{classify_entry_gate(agent_output)!r}"
    )


_TOKEN_FREE_PROSE_LINES = (
    "I inspected the module and its callers.",
    "The change is small and local.",
    "I re-read the tests that cover this code.",
    "",
)

_AMBIGUOUS_PROSE_TEMPLATES = (
    "I cannot certify this as {first}, and I am unsure about {second}.",
    "Between {first} and {second} I could not decide.",
    "Neither {first} nor {second} applies cleanly here.",
    "{first} was my first instinct, but honestly {second} is closer.",
)


@given(
    tokens=st.lists(
        st.sampled_from(list(EntryGateVerdict)),
        min_size=2,
        max_size=2,
        unique=True,
    ),
    preamble=st.lists(st.sampled_from(_TOKEN_FREE_PROSE_LINES), max_size=3),
    template=st.sampled_from(_AMBIGUOUS_PROSE_TEMPLATES),
)
@settings(max_examples=60, deadline=None)
def test_prose_weighing_two_verdict_tokens_is_never_merge_permitting(
    tokens: list[EntryGateVerdict], preamble: list[str], template: str
):
    """Property -- for ANY pair of distinct verdict tokens mentioned together
    in undecided prose, with no bare token line anywhere, the classification
    is never merge-permitting.

    Generated rather than enumerated because the defect is order-dependent:
    the classifier scans the enum in DECLARATION order, so which token wins
    depends on where each one sits in the enum, not on what the fixer meant.
    A handful of hand-picked examples would leave that dependence unprobed.

    CONTRACT_SHAPE: unbounded-preservation
    """
    first, second = tokens
    sentence = template.format(first=first.value, second=second.value)
    agent_output = "\n".join([*preamble, sentence]) + "\n"

    assert classify_entry_gate(agent_output) not in MERGE_PERMITTING, (
        "undecided prose naming two verdict tokens must never resolve to a "
        f"merge; {agent_output!r} classified as "
        f"{classify_entry_gate(agent_output)!r}"
    )


@given(
    verdict=st.sampled_from(list(EntryGateVerdict)),
    preamble=st.lists(st.sampled_from(_TOKEN_FREE_PROSE_LINES), max_size=4),
)
@settings(max_examples=40, deadline=None)
def test_a_bare_verdict_line_after_token_free_prose_is_always_honoured(
    verdict: EntryGateVerdict, preamble: list[str]
):
    """Property (preservation) -- for ANY verdict token, an output whose last
    line is exactly that token, preceded by prose mentioning no token at all,
    classifies as that token.

    The counterweight to the property above: a classifier hardened until it
    refuses even an unambiguous attestation has not fixed the drain, it has
    renamed the failure.

    CONTRACT_SHAPE: unbounded-preservation
    """
    agent_output = "\n".join([*preamble, verdict.value]) + "\n"

    assert classify_entry_gate(agent_output) is verdict, (
        f"an unambiguous bare {verdict.value} line must be honoured; "
        f"{agent_output!r} classified as {classify_entry_gate(agent_output)!r}"
    )


# =========================================================================
# E -- THE BOUNDARY NOBODY WROTE: `scripts/refactor_agent.py`.
#      Zero tests exercised the real actuator before this file. E1/E2 are
#      green-and-guarding -- they pin the fd-inheritance transport (the
#      actuator's `subprocess.run` deliberately has NO `capture_output`, so
#      the fixer's stdout is inherited straight through); a future
#      `capture_output=True` would silently swallow every verdict and
#      resurrect this exact bug. E3 is RED today.
# =========================================================================


@pytest.mark.parametrize(
    "verdict", list(EntryGateVerdict), ids=lambda verdict: verdict.value
)
def test_a_verdict_printed_by_the_fixer_reaches_the_classifier_through_the_actuator(
    tmp_path, verdict: EntryGateVerdict
):
    """Given the real actuator drives a headless fixer that prints a verdict
    token, When the actuator returns, Then that token is on the actuator's own
    stdout and the drain's classifier reads it back unchanged.

    This is the ONLY test that exercises `scripts/refactor_agent.py`, and the
    only one that would have caught the original defect end to end. The stub
    CLI needs no `claude` on PATH and makes no network call.

    CONTRACT_SHAPE: unbounded-preservation
    """
    composition = RefactorSwarmComposition(tmp_path)
    stub = composition.stub_fixer_cli_that_prints(f"{verdict.value}\n")

    result = composition.run_refactor_actuator(
        prompt_text="Fix the duplicated helper in two modules.", cli=stub
    )

    assert result.exit_code == 0, (
        "the actuator must exit 0 when the fixer succeeds; got "
        f"{result.exit_code} with stderr={result.stderr!r}"
    )
    assert classify_entry_gate(result.stdout) is verdict, (
        "the fixer's verdict must survive the actuator's stdout unchanged -- "
        "the actuator deliberately does NOT capture the fixer's output so it "
        "is inherited straight through to the harness. Got stdout="
        f"{result.stdout!r}"
    )


def test_actuator_output_carrying_only_prose_is_never_read_as_a_merge_permitting_verdict(
    tmp_path,
):
    """Negative twin -- Given the real actuator drives a fixer that reports
    only free-form prose, When the actuator returns, Then the drain's
    classifier finds no verdict and the item can only be refused.

    Guards the transport in the other direction: a chain that manufactured a
    verdict the fixer never emitted would pass the test above and fail this
    one.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    stub = composition.stub_fixer_cli_that_prints(
        "I had a look at the duplicated helper and tidied it up a bit.\n"
    )

    result = composition.run_refactor_actuator(
        prompt_text="Fix the duplicated helper in two modules.", cli=stub
    )

    assert classify_entry_gate(result.stdout) not in MERGE_PERMITTING, (
        "a fixer that never attested anything must never yield a "
        f"merge-permitting verdict; stdout={result.stdout!r} classified as "
        f"{classify_entry_gate(result.stdout)!r}"
    )


def test_the_verdict_ask_is_never_dropped_by_the_actuators_own_crafter_framing(
    tmp_path, delivered_prompt: str
):
    """Given the prompt file a REAL drain rendered for a REAL fixer, When the
    real actuator wraps it in its crafter framing and dispatches it, Then
    every entry-gate token still reaches the headless fixer.

    The last link in the chain: template -> rendered prompt file -> actuator
    framing -> the fixer's own prompt. A verdict protocol that is added at
    render time and then truncated here would be just as invisible to the
    fixer as no protocol at all.

    CONTRACT_SHAPE: bounded-change
    """
    composition = RefactorSwarmComposition(tmp_path)
    stub = composition.stub_fixer_cli_that_prints("REFACTOR_SAFE\n")

    composition.run_refactor_actuator(prompt_text=delivered_prompt, cli=stub)
    received = composition.text_the_headless_cli_received()

    missing = [
        member.value for member in EntryGateVerdict if member.value not in received
    ]
    assert not missing, (
        "the actuator must deliver the entry-gate ask through to the fixer "
        f"untruncated; these tokens never arrived: {missing}. The fixer "
        f"received:\n{received}"
    )
