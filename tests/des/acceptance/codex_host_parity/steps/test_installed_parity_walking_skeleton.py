"""Step definitions -- the installed-parity walking skeleton (slice-01).

@feature-codex-host-parity
@slice-01

Driving surface (Mandate 13, Driving-Port-Only Boundary):

  * the single ``@walking_skeleton`` scenario exercises the ASSEMBLED SURFACE:
    the real producer mints a candidate, it is installed into a clean prefix,
    and the INSTALLED console script is executed from outside the checkout with
    a scrubbed environment. It never runs ``python -m des.cli`` from the source
    tree -- proving the checkout works is not this feature's claim;
  * every other scenario drives ``CodexParityJourneyPort.run`` IN-PROCESS
    through the production composition root's public re-export, with the five
    DESIGN ports supplied as independent external witnesses.

Every crossing is read from a STRUCTURED receipt (item, verdict, candidate id,
host composition id, external effect count) -- never matched out of prose, and
never satisfied by the mere absence of an error.

Step bodies delegate to :class:`InstalledParityJourney` -- the one service that
mints, installs, assembles the request and drives the port (Mandate-12
criterion 3).

RED-for-the-right-reason at tip: production mints no publishable candidate, so
the walking skeleton fails before any distribution is built; and
``CodexParityJourneyPort`` has no ``run``, so the in-process scenarios fail on
the promise rather than on an interpreter error. Classification recorded in
docs/feature/codex-host-parity/distill/red-classification-installed-parity.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_bdd import given, scenario, then, when

from .journey_requests import (
    CODEX_CROSSINGS,
    FOREIGN_CANDIDATE,
    NATIVE_LIFECYCLE_EVENT,
    ChainLink,
    CrossingReceipt,
    InstalledParityJourney,
    ObservedJourney,
    PublishedJourneyRun,
)


pytestmark = [pytest.mark.acceptance, pytest.mark.slice_01]

_FEATURE = "../installed-parity-walking-skeleton.feature"


@pytest.fixture()
def journey() -> InstalledParityJourney:
    """The one service every step of a scenario shares."""
    return InstalledParityJourney()


@pytest.fixture()
def walked() -> dict[str, object]:
    """What the user has observed so far in this scenario."""
    return {}


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@scenario(
    _FEATURE,
    "A Codex user installs one published candidate and completes the whole journey with it",
)
def test_a_codex_user_completes_the_whole_journey_on_one_published_candidate() -> None:
    """The feature's single walking skeleton, on the assembled surface."""
    # covers: R-S01-01
    # covers: R-S01-08
    # covers: R-S01-09
    # covers: R-S01-10
    ...


@scenario(
    _FEATURE,
    "The installed specialist follows its instructions and reads both its expertise and the project rule",
)
def test_the_installed_specialist_reads_its_expertise_and_the_project_rule() -> None:
    # covers: R-S01-02
    ...


@scenario(
    _FEATURE,
    "The specialist refuses work when the approval its role requires cannot be honoured, instead of quietly working without it",
)
def test_the_specialist_refuses_work_whose_approval_cannot_be_honoured() -> None:
    # covers: R-S01-03
    ...


@scenario(
    _FEATURE,
    "The workflow safeguard visibly stops a forbidden action and records it exactly once",
)
def test_the_workflow_safeguard_stops_a_forbidden_action_exactly_once() -> None:
    # covers: R-S01-04
    ...


@scenario(
    _FEATURE,
    "The operator arms one continued-work loop, ticks it once, sees it attested and stops it",
)
def test_the_operator_arms_ticks_attests_and_stops_one_continued_work_loop() -> None:
    # covers: R-S01-05
    ...


@scenario(
    _FEATURE,
    "A capability is never reported proved on work done for a different candidate or a different machine",
)
def test_a_capability_is_never_proved_on_another_candidates_work() -> None:
    # covers: R-S01-06
    # covers: R-S01-08
    ...


@scenario(
    _FEATURE,
    "Installing the candidate never changes what an existing Claude user already had",
)
def test_installing_the_candidate_never_changes_an_existing_claude_users_behaviour() -> (
    None
):
    # covers: R-S01-07
    ...


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------


@given("the team has published one nWave candidate for Codex users")
def the_team_has_published_one_candidate(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    walked["published"] = journey.will_publish_through_the_real_producer()


@given("a Codex user has installed that same published candidate")
def a_codex_user_has_installed_that_candidate(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    walked["published"] = journey.publish_candidate()


@given("the installed specialist has been asked to do its work")
def the_installed_specialist_has_been_asked_to_work(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    a_codex_user_has_installed_that_candidate(journey, walked)
    journey.exercise(
        ChainLink.SPECIALIST_FOLLOWS_INSTRUCTIONS,
        ChainLink.SPECIALIST_READS_ITS_EXPERTISE,
        ChainLink.SPECIALIST_READS_PROJECT_RULE,
    )


@given("the specialist's role requires approval before it acts")
def the_specialists_role_requires_approval(journey: InstalledParityJourney) -> None:
    journey.exercise(ChainLink.APPROVAL_IS_ENFORCED_OR_REFUSED)


@given("the specialist's approval requirement has been honoured")
def the_specialists_approval_requirement_has_been_honoured(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    the_installed_specialist_has_been_asked_to_work(journey, walked)
    journey.exercise(ChainLink.APPROVAL_IS_ENFORCED_OR_REFUSED)


@given("the workflow safeguard has reacted for this user")
def the_workflow_safeguard_has_reacted(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    the_specialists_approval_requirement_has_been_honoured(journey, walked)
    journey.exercise(ChainLink.SAFEGUARD_REACTS)


@given("the operator's continued work has been attested on the installed candidate")
def the_operators_continued_work_has_been_attested(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    the_workflow_safeguard_has_reacted(journey, walked)
    journey.exercise(ChainLink.LOOP_TICK_IS_ATTESTED)


@given(
    "an existing Claude user already has their own safeguards and specialists on this machine"
)
def an_existing_claude_user_is_already_set_up(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    walked["published"] = journey.publish_candidate()
    journey.exercise(ChainLink.CLAUDE_USER_IS_UNCHANGED)


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------


@when(
    "a Codex user installs that published candidate on a clean machine and works through the whole journey"
)
def the_user_installs_and_walks_the_whole_journey(
    journey: InstalledParityJourney, walked: dict[str, object], tmp_path: Path
) -> None:
    journey.exercise(*ChainLink)
    walked["invocation"] = journey.publish_install_and_walk(tmp_path)


@when("the user asks the installed specialist to do its work")
def the_user_asks_the_specialist_to_work(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    journey.exercise(
        ChainLink.SPECIALIST_FOLLOWS_INSTRUCTIONS,
        ChainLink.SPECIALIST_READS_ITS_EXPERTISE,
        ChainLink.SPECIALIST_READS_PROJECT_RULE,
    )
    walked["run"] = journey.run()


@when("this machine cannot honour that approval requirement")
def this_machine_cannot_honour_the_approval_requirement(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    journey.approval_cannot_be_honoured()
    walked["run"] = journey.run()


@when("the user attempts an action the workflow safeguard forbids")
def the_user_attempts_a_forbidden_action(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    journey.exercise(ChainLink.SAFEGUARD_REACTS)
    walked["run"] = journey.run()


@when(
    "the operator arms one continued-work loop, ticks it once, stops it and then tries to tick it again"
)
def the_operator_arms_ticks_stops_and_reticks(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    journey.ticks_again_after_stopping()
    walked["run"] = journey.run()


@when(
    "a capability offers work that was done for a different candidate or on a different machine"
)
def a_capability_offers_work_from_another_machine(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    journey.borrowed_from_another_machine(ChainLink.SAFEGUARD_REACTS)
    walked["run"] = journey.run()


@when("that same published candidate is installed for Codex on the same machine")
def the_same_candidate_is_installed_beside_claude(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    walked["run"] = journey.run()


# ---------------------------------------------------------------------------
# Then -- walking skeleton (the assembled surface)
# ---------------------------------------------------------------------------


def _observed(walked: dict[str, object]) -> ObservedJourney:
    return walked["invocation"]  # type: ignore[return-value]


def _reported_crossings(observed: ObservedJourney) -> tuple[CrossingReceipt, ...]:
    """Read the report ONLY for the identity binding it is entitled to carry.

    A receipt may bind a candidate to a host composition -- that is its job. It
    is never the oracle of an effect it itself declares; those are measured on
    the clean machine by the five observations above.
    """
    try:
        payload = json.loads(observed.invocation.stdout or "{}")
    except json.JSONDecodeError:
        return ()
    return tuple(
        CrossingReceipt.read(record) for record in payload.get("crossings", ())
    )


@then(
    "the specialist's answer quotes the expertise and the project rule that were really installed"
)
def the_specialists_answer_quotes_installed_material(walked: dict[str, object]) -> None:
    """(a) Correlated to material this test read off the installed prefix.

    Discrimination is MEASURED, not hoped for: each token must occur in exactly
    ONE installed file, so quoting it cannot be done by echoing a header shared
    across the tree. The project-rule nonce was invented by this test before
    the journey ran, so quoting it requires having read the durable rule.
    """
    observed = _observed(walked)
    generic = [
        f"{name} token occurs in {count} installed files"
        for name, count in (
            ("installed role", observed.role_token_file_count),
            ("installed skill", observed.skill_token_file_count),
        )
        if count != 1
    ]
    assert not generic, (
        f"WHAT: {generic}. WHY: a token that appears in many installed files "
        "cannot distinguish a specialist that read ITS role and ITS skill from "
        "one echoing boilerplate, so quoting it would prove nothing. HOW: give "
        "each installed role and skill a marker unique to that file."
    )
    unquoted = [
        name
        for name, token in (
            ("installed role", observed.role_token),
            ("installed skill", observed.skill_token),
            ("project rule", observed.project_rule_nonce),
        )
        if not observed.specialist_quoted(token)
    ]
    assert not unquoted, (
        f"WHAT: the specialist's answer did not quote: {unquoted}. WHY: a "
        "specialist that cannot show the expertise and the project rule it was "
        "given has not read them, and a report claiming otherwise is the "
        "producer vouching for itself. HOW: install the role, skill and durable "
        "rule so the specialist reads them and its answer reflects their "
        f"content. Answer: {observed.specialist_output.strip()[:300]!r}"
    )


@then("the specialist did the one thing its installed role declares it must do")
def the_specialist_did_what_its_role_declares(walked: dict[str, object]) -> None:
    """(a2) Following instructions, judged by an effect the ROLE declared.

    The obligation is read out of the installed role itself, so the producer
    cannot choose the bar it is measured against, and the effect is looked for
    on disk -- an answer that merely claims obedience satisfies nothing.
    """
    observed = _observed(walked)
    assert observed.declared_obligation, (
        "WHAT: the role this journey runs declares no observable obligation. WHY: "
        "'follows its instructions' judged on prose is judged on the answer's "
        "self-description; without a declared, checkable obligation the claim "
        "is untestable. HOW: have the installed role declare the effect its "
        "work must leave, so obedience is a fact on the machine."
    )
    assert observed.obligation_effect_carries_nonce, (
        f"WHAT: the role declares it must produce '{observed.declared_obligation}' "
        "carrying this project's rule, and after the specialist ran it was "
        "absent or did not carry it. WHY: a specialist that answers without "
        "doing what its own role requires has not followed its instructions, "
        "however well it describes itself. HOW: make the installed role's "
        "instructions actually govern what the specialist does."
    )


@then(
    "the action that needed approval leaves its mark only when the approval was granted"
)
def the_guarded_action_leaves_its_mark_only_when_approved(
    walked: dict[str, object],
) -> None:
    """(b) The approval the ROLE declares, taken away at its real source."""
    observed = _observed(walked)
    assert observed.role_files_declaring == 1, (
        f"WHAT: {observed.role_files_declaring} role files in the HOST's own "
        "agents directory carry the exact identity of the role this journey "
        "runs. WHY: with none, nothing was withheld and the refusal proves "
        "nothing; with several the bar is ambiguous; and a file elsewhere in "
        "the candidate whose name merely resembles the role is not the role the "
        "host selects -- judging obedience against it would measure a stranger. "
        "HOW: install exactly one host role file for the selected role, "
        "declaring its obligation, its approval and its effect."
    )
    assert observed.declared_approval, (
        "WHAT: the selected role declares no approval requirement, so nothing "
        "was actually withheld in the second leg. WHY: a policy dimension the "
        "test invents is a test of the test; only a requirement the role itself "
        "declares can be enforced or refused on the user's behalf. HOW: render "
        "the role's approval requirement into the installed material."
    )
    assert observed.policy_decoy_planted, (
        "WHAT: no decoy policy was on the machine while the guarded action ran. "
        "WHY: 'a document the host never resolves cannot grant anything' is a "
        "claim about our own code until something shaped like policy, carrying "
        "the grant, is actually sitting there being ignored. HOW: plant the "
        "decoy before the action, so its silence is observed rather than "
        "assumed."
    )
    assert observed.granting_authority_is_the_host_policy, (
        "WHAT: the approval was not granted by a document the HOST reads as its "
        "policy. WHY: a grant is not settled by being written down somewhere "
        "identifiable -- the role's own statement of what it requires is a "
        "precise file and a precise field, and it still has no title to grant "
        "anything. Only the surface the host consults when it decides what may "
        "happen can concede it. HOW: grant the approval in the host's own "
        "policy, and leave the role's file to declare the requirement."
    )
    assert observed.machine_grants_of_the_approval == 1, (
        f"WHAT: {observed.machine_grants_of_the_approval} fields of the HOST's "
        f"own policy grant '{observed.declared_approval}'. WHY: zero means "
        "the second leg withheld nothing, so the refusal proves nothing; more "
        "than one means the withdrawal was partial and the action may have been "
        "refused for another reason. The role's own statement of what it "
        "REQUIRES is not one of these -- a requirement that satisfies itself is "
        "no authority at all. HOW: let the machine's policy grant the named "
        "approval in exactly one field."
    )
    assert observed.guarded_effect_with_approval, (
        "WHAT: the approved action left no mark on the machine. WHY: an "
        "approval that permits nothing observable is not enforcement, it is "
        "decoration. HOW: let the granted approval carry the action through to "
        "its real effect."
    )
    assert not observed.guarded_effect_without_approval, (
        "WHAT: the action ran and left its mark even though the machine no "
        "longer granted the approval its role requires. WHY: this is the silent "
        "downgrade the feature forbids -- work proceeding under an allowance "
        "nobody could honour. HOW: refuse before the effect."
    )
    assert observed.refused_approval_exit != 0, (
        "WHAT: the unapprovable action exited "
        f"{observed.refused_approval_exit}, reporting success. WHY: a refusal "
        "the user cannot detect from the outside is indistinguishable from "
        "having worked. HOW: exit non-zero when the approval cannot be honoured."
    )
    assert (
        observed.refused_approval_remedy
        and observed.declared_approval in observed.refused_approval_remedy
    ), (
        "WHAT: the refusal did not carry a structured what/why/how naming the "
        f"approval '{observed.declared_approval}'. WHY: a user told only that "
        "something failed cannot tell which policy their machine is missing nor "
        "how to restore it, and free prose that happens to mention a word is "
        "not guidance a user or a tool can act on. HOW: refuse with a "
        "structured diagnostic whose three parts are all present and name the "
        f"approval. Shown: {observed.refused_approval_remedy.strip()[:300]!r}"
    )


@then("the safeguard reacts to the native event and leaves exactly one mark")
def the_safeguard_reacts_natively_and_leaves_one_mark(
    walked: dict[str, object],
) -> None:
    """(c) The REAL host attempts the action; the test only measures after.

    Declaring the hook in the native format proves CONFIGURATION. The host
    calling it proves ACTIVATION. The forbidden action failing to happen
    proves ENFORCEMENT. This asserts the last two, on a machine inspected once
    the real boot is over -- no receipt takes part in it.
    """
    observed = _observed(walked)
    decoy = observed.native_decoy_in_the_candidate
    assert decoy.is_file() and observed.native_decoy_is_executable, (
        f"WHAT: no runnable stand-in host was planted at {decoy} before the "
        "boot. WHY: the rule that the judge comes from the machine is only "
        "worth the case that would break it; with nothing to be wrongly "
        "preferred, every claim below about where the host came from is a claim "
        "about an absence, and an absence agrees with anything. HOW: plant the "
        "decoy inside the candidate's own bin before resolving the host."
    )
    prefix = observed.prefix.resolve()
    resolved = observed.native_host_binary
    assert prefix != resolved and prefix not in resolved.parents, (
        f"WHAT: the host that judged this run is {resolved}, inside the "
        f"candidate's own install {prefix} -- where this test had just planted a "
        "working stand-in that announces a supported version and answers the "
        "protocol. WHY: a candidate that supplies its own judge does not "
        "fabricate one piece of evidence, it fabricates the judge: version, "
        "transcript, tool outcome and the very absence of the forbidden effect "
        "would all be the producer marking its own work, and the run would be "
        "coherent theatre. HOW: resolve the host from the machine's own path, "
        "with everything under the candidate removed, and let the candidate "
        "supply only what the host is asked to find."
    )
    assert not observed.native_decoy_was_invoked, (
        f"WHAT: the stand-in host at {decoy} was executed during this run. WHY: "
        "the resolved binary being outside the candidate is not enough if the "
        "candidate's copy still runs by another route -- a name looked up again "
        "on the child's path, or a re-exec -- and whatever it answered would "
        "have entered this scenario's evidence unremarked. HOW: invoke the "
        "machine's host by its absolute path and keep the candidate's bin out "
        "of any lookup that could resolve a host."
    )
    assert NATIVE_LIFECYCLE_EVENT in observed.native_registration_events, (
        f"WHAT: the install registered nWave for "
        f"{sorted(observed.native_registration_events) or 'no events at all'}, "
        f"not {NATIVE_LIFECYCLE_EVENT}. WHY: a safeguard the host never calls "
        "protects nobody -- only a native lifecycle registration puts it in the "
        "path of the user's real actions. HOW: register the safeguard for the "
        "event the host raises before a tool runs."
    )
    assert observed.native_host_exit == 0, (
        f"WHAT: the host itself exited {observed.native_host_exit} instead of "
        "running to completion. WHY: a boot that fell over never got as far as "
        "attempting the action, so nothing it did or did not do says anything "
        "about the safeguard. HOW: let the host complete its turn. Host said: "
        f"{observed.native_transcript.strip()[-400:]!r}"
    )
    assert observed.native_tool_call_reported_back, (
        "WHAT: the host never reported back what became of the tool call it was "
        f"given for '{observed.native_tool_the_host_offered}'. WHY: without that "
        "outcome the boot is indistinguishable from one where the action was "
        "never attempted, and an unattempted action is trivially harmless -- "
        "which would make the whole observation vacuous. HOW: let the host "
        "carry the call through to its outcome."
    )
    assert observed.native_reaction_log is not None, (
        "WHAT: the registered hook command does not name the log it records "
        "into. WHY: without it, a reaction could only be recognised by a record "
        "SAYING it is one -- and any file under this machine's home can say "
        "that, so a stranger's writing would stand in for the hook the host "
        "actually called. HOW: have the registration name the log its own "
        "handler writes."
    )
    assert observed.native_marks_before == 0, (
        f"WHAT: {observed.native_marks_before} safeguard reactions to this event "
        "already existed before the host ran. WHY: a count that was never zero "
        "cannot attribute anything to the event; the record could predate it "
        "entirely. HOW: write a reaction only when reacting."
    )
    assert len(observed.native_reactions) == 1, (
        f"WHAT: after {observed.native_host_version} really attempted a "
        "forbidden action through its own "
        f"'{observed.native_tool_the_host_offered}' tool, the safeguard left "
        f"{len(observed.native_reactions)} reactions in the log its "
        "registration names, naming this "
        f"event ('{observed.native_event_nonce}'), not one. WHY: zero means the "
        "host never called the safeguard -- the registration was configuration "
        "nobody activated, which is exactly the gap between a declared hook and "
        "a protected user; more than one double-counts a single reaction. A "
        "record elsewhere would not do, however well typed: the host persists "
        "its own session and rollout, so a stray object under this home could "
        "otherwise supply the only occurrence and enforcement would be credited "
        "to somebody else's writing. HOW: match the tool the host actually "
        "offers "
        "and record ONE reaction that says it is a safeguard reaction and names "
        "the event, the lifecycle event, the tool and the candidate. "
        f"Host said: {observed.native_transcript.strip()[-400:]!r}"
    )
    reaction = observed.native_reactions[0] if observed.native_reactions else {}
    assert str(reaction.get("record_id", "")) in observed.native_tool_outcome, (
        "WHAT: the host's own account of what became of the tool call does not "
        f"quote the reaction {reaction.get('record_id')!r} the registered hook "
        f"recorded. Host reported: {observed.native_tool_outcome[:300]!r}. WHY: "
        "without that, the action could have been stopped by a sandbox or by "
        "some other policy while the hook did nothing -- the effect would be "
        "absent and a matching record would still be there, and nothing would "
        "show the REGISTERED hook is what refused. Only the host quoting the "
        "hook's own answer ties the two together. HOW: have the safeguard "
        "refuse the call with its reaction identity, so the host reports it."
    )
    assert not observed.native_forbidden_effect_happened, (
        "WHAT: the forbidden action the host attempted left its effect on the "
        "machine anyway. WHY: a safeguard that is called and then lets the "
        "action through is enforcement in appearance only -- the user is told "
        "they are protected while the thing they feared happened. HOW: refuse "
        "the action to the host, so the effect never occurs."
    )


@then(
    "the loop's work is still there after its process ended, and a tick after the stop is turned away"
)
def the_loops_work_is_durable_and_the_stop_holds(walked: dict[str, object]) -> None:
    """(d) One loop, bound by the id its arming returned, across processes."""
    observed = _observed(walked)
    assert observed.loop_id, (
        "WHAT: arming the loop returned no identity for it. WHY: without one, "
        "every later step is an unbound claim -- a tick, an attestation and a "
        "stop could each belong to a different loop and the sequence would "
        "still look complete. HOW: return the armed loop's id."
    )
    failed = {
        step: code for step, code in observed.loop_step_exits.items() if code != 0
    }
    assert not failed, (
        f"WHAT: {failed} did not succeed. WHY: an attestation counted after a "
        "step that actually failed credits the operator with continued work "
        "that never happened. HOW: let arm, tick and stop each succeed before "
        "their result is read."
    )
    before = observed.loop_records_before_the_tick
    after = observed.loop_records_after_the_tick
    kinds_before = InstalledParityJourney.kinds_in(before)
    kinds_after = InstalledParityJourney.kinds_in(after)
    assert not kinds_before.get("tick") and not kinds_before.get("attestation"), (
        f"WHAT: before the tick ran, loop '{observed.loop_id}' already had "
        f"{kinds_before}. WHY: arming writes durable state of its own, so a "
        "count taken only afterwards credits the tick with work the arming did. "
        "Only a baseline of none makes what follows attributable to the tick. "
        "HOW: record ticks and attestations only when they happen."
    )
    assert InstalledParityJourney.attests_the_tick(after), (
        f"WHAT: nothing in {sorted(kinds_after)} attests the tick that ran -- no "
        "attestation names the tick's own record. WHY: two well-formed objects "
        "written side by side satisfy every shape check and attest no work at "
        "all; an attestation that does not say WHICH occurrence it stands for "
        "cannot be told from a fabricated pair. HOW: have the attestation carry "
        "the record identity of the tick it attests."
    )
    assert kinds_after.get("tick") == 1 and kinds_after.get("attestation") == 1, (
        f"WHAT: the tick left {kinds_after} for loop '{observed.loop_id}', not "
        "exactly one tick and one attestation. WHY: none means the operator's "
        "continued work has no memory across processes; more than one means a "
        "single tick was counted twice; and anything that merely MENTIONS the "
        "loop is not a typed occurrence -- the arming state mentions it too. "
        "HOW: write one typed tick record and one typed attestation, each "
        "naming the loop and carrying its own record identity."
    )
    assert observed.retick_exit != 0, (
        f"WHAT: a tick attempted after the stop exited {observed.retick_exit}, "
        "reporting success. WHY: a stopped loop that still ticks makes Stop a "
        "suggestion, and the operator can no longer tell stopped work from "
        "running work. HOW: refuse any tick claimed on a stopped generation."
    )
    assert observed.loop_records_after_the_retick == after, (
        "WHAT: the stop and the refused tick did not leave loop "
        f"'{observed.loop_id}' with the same records byte-for-byte. Lost or "
        f"changed: {sorted(set(after) - set(observed.loop_records_after_the_retick))}; "
        f"added: {sorted(set(observed.loop_records_after_the_retick) - set(after))}. "
        "WHY: counting how many records survive cannot tell conservation from "
        "replacement -- a stop that rewrites, substitutes or corrupts the "
        "attestation while leaving one tick and one attestation behind reads as "
        "untouched, and the operator would recover work that is no longer the "
        "work that was done. HOW: leave the exact records the tick wrote, and "
        "add nothing for a tick that was turned away."
    )


@then("the Claude user's own files are byte-for-byte what they were before the install")
def the_claude_users_files_are_unchanged(walked: dict[str, object]) -> None:
    """(e) Digested by this test on both sides of the install."""
    observed = _observed(walked)
    assert observed.claude_digest_before, (
        "WHAT: there was no Claude surface on the machine before the install, "
        "so preservation was never actually put at risk. WHY: a preservation "
        "claim measured against an empty tree is vacuous. HOW: plant the "
        "existing user's files before installing."
    )
    assert observed.claude_digest_before == observed.claude_digest_after, (
        "WHAT: the Claude user's tree changed across the Codex install "
        f"({observed.claude_digest_before[:16]} -> "
        f"{observed.claude_digest_after[:16]}). WHY: Claude preservation is a "
        "floor of this slice; an existing user must not pay for someone else's "
        "Codex install. HOW: touch only nWave-owned material."
    )


@then(
    "every capability the user exercised carries the same candidate and the same machine"
)
def every_capability_carries_the_same_identity(walked: dict[str, object]) -> None:
    """One tuple across the whole chain, read structurally.

    A per-crossing receipt that quotes its own candidate and machine cannot be
    satisfied by a report that names the candidate once in a header: that
    binding is what a green-but-wrong assembly breaks first.
    """
    observed = _observed(walked)
    reported = _reported_crossings(observed)
    expected = observed.minted.candidate
    assert (
        observed.claimed_distribution_digest == observed.measured_distribution_digest
    ), (
        f"WHAT: the candidate claims its distribution digests to "
        f"{observed.claimed_distribution_digest!r}, and the artifact on disk "
        f"weighs {observed.measured_distribution_digest!r}. WHY: the bytes are "
        "the only authority for what a candidate is; a producer that both "
        "builds the artifact and reports its digest is attesting its own "
        "capability, and nothing on the machine could contradict it. HOW: "
        "report the digest of the distribution actually built."
    )
    assert (
        observed.other_measured_distribution_digest
        != observed.measured_distribution_digest
    ), (
        "WHAT: two candidates published from different material weighed the "
        f"same ({observed.measured_distribution_digest[:16]}). WHY: if the "
        "second build is not a different artifact, comparing their identities "
        "shows nothing -- the pair has to be materially different before it can "
        "tell anything apart. HOW: build the second candidate from the material "
        "it was given."
    )
    assert (
        observed.other_claimed_distribution_digest
        == observed.other_measured_distribution_digest
    ), (
        f"WHAT: the second candidate claims "
        f"{observed.other_claimed_distribution_digest!r} and weighs "
        f"{observed.other_measured_distribution_digest!r}. WHY: each candidate "
        "answers to its OWN bytes; a second artifact reporting a digest that is "
        "not its own is the same self-attestation as the first, one build "
        "further along. HOW: report the digest of what was built."
    )
    assert observed.other_candidate != expected, (
        f"WHAT: two materially different candidates were both published as "
        f"{expected!r}. WHY: two real builds sharing one identity means a "
        "rebuild can change what a user installs while every receipt still "
        "quotes the same candidate -- and a mint that distinguishes fabricated "
        "inputs can still fail here, which is the case the product actually "
        "meets. HOW: mint each candidate from its own artifact."
    )
    assert (
        observed.other_candidate == observed.identity_from_the_other_measured_bytes
    ), (
        f"WHAT: the second candidate was published as "
        f"{observed.other_candidate!r} while its own bytes mint "
        f"{observed.identity_from_the_other_measured_bytes!r}. WHY: each "
        "identity must follow the artifact it belongs to, not just differ from "
        "its neighbour -- two distinct constants would satisfy difference alone. "
        "HOW: mint the second identity from the second distribution."
    )
    assert expected == observed.identity_from_the_measured_bytes, (
        f"WHAT: the producer published {expected!r}, but the bytes this test "
        f"weighed mint {observed.identity_from_the_measured_bytes!r}. WHY: an "
        "identity that does not follow the artifact's own bytes cannot be held "
        "to account by anything outside the producer -- checking one producer "
        "surface against another is still the producer vouching for itself, and "
        "a constant published identity survives it. HOW: mint the published "
        "identity from the distribution that was built."
    )
    assert expected == observed.reported_candidate, (
        f"WHAT: the producer minted {expected!r}, and the installed candidate "
        f"calls itself {observed.reported_candidate!r}. WHY: two independent "
        "sources -- what the build returned and what the artifact says once "
        "installed -- must agree, or the thing on the user's machine is not the "
        "thing that was minted. HOW: carry the minted identity into the "
        "installed artifact."
    )
    declared = tuple(sorted(link.value for link in CODEX_CROSSINGS))
    reported_items = tuple(sorted(receipt.item for receipt in reported))
    assert reported_items == declared, (
        f"WHAT: the journey reported {list(reported_items)}, not exactly "
        f"{list(declared)}. WHY: a missing crossing is a capability the user "
        "was promised and never got, an extra one is evidence nobody asked "
        "for, and a REPEATED one is the same capability counted twice -- "
        "compared as a set all three hide, because a set cannot tell one walk "
        "of the chain from three. HOW: emit exactly one receipt per declared "
        "crossing."
    )
    strangers = sorted(
        receipt.item
        for receipt in reported
        if receipt.identity != (expected, observed.reported_composition)
    )
    assert not strangers, (
        f"WHAT: crossings that do not carry "
        f"({expected}, {observed.reported_composition}): {strangers}. WHY: a "
        "capability the report does not tie to this exact candidate and machine "
        "could have been proved elsewhere and presented as this user's -- the "
        "borrowed evidence this slice exists to prevent. HOW: stamp every "
        "crossing receipt with the candidate and host composition the journey "
        "ran on."
    )
    assert (
        observed.reported_composition
        and observed.reported_composition == observed.reported_composition_on_second_run
    ), (
        f"WHAT: two runs on the same machine named it "
        f"{observed.reported_composition!r} and "
        f"{observed.reported_composition_on_second_run!r}. WHY: a machine "
        "identity that changes between runs cannot bind evidence to a host at "
        "all -- every capability would be proved on a machine that no longer "
        "exists. HOW: derive the host composition from the machine, so it is "
        "the same whenever the machine is."
    )


@then(
    "the journey the user ran came from the installed candidate and borrowed nothing from the source tree"
)
def the_journey_came_from_the_installed_candidate(walked: dict[str, object]) -> None:
    """Decide on the PROPERTY: where the executing code lives, not what it claims.

    The clean process reports its own executable, the module that served the
    journey and its import roots; each is then resolved through symlinks and
    required to exist under the prefix, and the prefix is separately proved
    self-sufficient -- real package files, no content naming the checkout, no
    ``.pth`` pointing outside. The decoy planted in the user's own site
    directory closes the last door: if the candidate honoured user or global
    site-packages, it would have left its mark.
    """
    observed = _observed(walked)
    strays = observed.ran_from_the_clean_prefix()
    assert not strays, (
        f"WHAT: the journey attributed its own code to {list(strays)}, outside "
        f"the clean prefix {observed.prefix}. WHY: executing the developer's "
        "checkout proves the source tree works and says nothing about the "
        "artifact a user receives. HOW: install the minted candidate and "
        "execute the console script that install produced."
    )
    assert observed.real_package_files > 0, (
        "WHAT: the prefix carries no real package files of its own. WHY: an "
        "install whose code lives elsewhere is a pointer, not an artifact -- it "
        "cannot be what a user receives. HOW: install the candidate's own files "
        "into the prefix."
    )
    borrowed = observed.borrowed_from_the_checkout()
    assert not borrowed, (
        f"WHAT: the installed candidate reaches outside itself: {list(borrowed)}. "
        "WHY: source-tree, developer-HOME and global-install material cannot "
        "satisfy assembled-candidate evidence -- an editable install or a "
        "redirecting path file makes the checkout the real code while the "
        "prefix takes the credit. HOW: install real files and run with a "
        "scrubbed environment and no path back to the checkout."
    )
    assert observed.decoy_package_planted, (
        "WHAT: the decoy package was not on the machine while the candidate "
        "ran. WHY: an absent marker proves nothing about a decoy that was never "
        "there -- the scenario would be asserting that a package which does not "
        "exist was not imported. HOW: plant the decoy in the user's own site "
        "directory before the journey runs."
    )
    assert not observed.decoy_marker_present, (
        "WHAT: the installed candidate imported the decoy package planted in "
        "this user's own site directory. WHY: a candidate that accepts user or "
        "global site-packages can be served by material it never shipped, so "
        "nothing it then proves belongs to the artifact. HOW: refuse user and "
        "global site-packages and resolve only within the install."
    )


@then(
    "the candidate the user installed carries none of the material nWave keeps private"
)
def the_candidate_carries_no_private_material(walked: dict[str, object]) -> None:
    """Independent oracle: the catalogue's PATHS against the real inventory.

    Private entries are mapped to the paths they would occupy -- an agent
    document, a skill package directory, a governance folder -- and matched
    component-wise against everything the install really produced, including
    what the artifact's own record claims. And absence is only counted beside
    presence: a candidate that ships nothing is not a clean one.
    """
    observed = _observed(walked)
    assert observed.private_paths, (
        "WHAT: the catalogue named nothing private, so this scenario would pass "
        "on any candidate whatsoever. WHY: an exclusion oracle with an empty "
        "exclusion set is not an oracle. HOW: read the catalogue that flags "
        "private material."
    )
    assert observed.public_paths_installed > 0, (
        "WHAT: the candidate installed no public specialist at all. WHY: an "
        "install that ships nothing satisfies every exclusion trivially, so "
        "'carries nothing private' would be true of an empty box the user "
        "cannot use. HOW: ship the public material the candidate promises."
    )
    assert not observed.unrecorded_installed, (
        f"WHAT: the install put material on the machine that its own manifest "
        f"never records: {list(observed.unrecorded_installed[:8])}. WHY: an "
        "exclusion is only as good as the inventory it is measured against, and "
        "material that arrived without the manifest accounting for it is "
        "exactly where private content sits unnoticed. HOW: record every path "
        "the install produces."
    )
    assert not observed.phantom_recorded, (
        f"WHAT: the manifest records entries with nothing behind them: "
        f"{list(observed.phantom_recorded[:8])}. WHY: a manifest describing an "
        "install that did not happen makes the inventory agree with itself "
        "rather than with the machine -- and an entry written in another "
        "notation would answer for a file that was never placed. HOW: install "
        "every recorded path, and record it in the form it is installed under."
    )
    leaked = observed.leaked_private_paths()
    assert not leaked, (
        f"WHAT: the installed candidate carries private material: {list(leaked)}. "
        "WHY: a public candidate that ships private agents, private skills or "
        "governance material is not the artifact the user was promised, and "
        "absence has to be a property of the artifact rather than a habit of "
        f"the build. HOW: exclude every catalogue-private path "
        f"({len(observed.private_paths)} of them) from the published candidate."
    )


# ---------------------------------------------------------------------------
# Then -- in-process journey observations
# ---------------------------------------------------------------------------


def _run(walked: dict[str, object]) -> PublishedJourneyRun:
    return walked["run"]  # type: ignore[return-value]


def _assert_crossing(
    run: PublishedJourneyRun,
    journey: InstalledParityJourney,
    link: ChainLink,
    *,
    verdict: str,
) -> CrossingReceipt:
    """A crossing counts only with the right verdict AND the right identity."""
    assert run.crossing_items() == journey.declared_items(), (
        f"WHAT: the journey reported {list(run.crossing_items())} for a request "
        f"that asked for {list(journey.declared_items())}. WHY: a missing "
        "crossing is a capability the user was promised and never got, an extra "
        "one is evidence nobody asked for, and a repeated one is one capability "
        "counted twice -- exactly what comparing sets instead of multisets "
        "hides. HOW: emit exactly one receipt per declared crossing."
    )
    receipt = run.crossing(link)
    assert receipt is not None, (
        f"WHAT: the journey reported no receipt for '{link.value}'. WHY: the "
        "user was promised that capability on the candidate they installed, "
        "and a capability with no receipt is not a proved one -- silence is "
        "not success. HOW: emit one structured receipt per declared crossing. "
        f"Reported: {[item.item for item in run.crossings()]}"
    )
    assert receipt.verdict == verdict, (
        f"WHAT: '{link.value}' came back {receipt.verdict!r}, not {verdict!r}. "
        "WHY: this scenario is satisfied by a positive observation, never by "
        "the absence of an error. HOW: record the verdict the journey actually "
        "observed for that crossing."
    )
    assert receipt.identity == journey.identity.as_pair(), (
        f"WHAT: '{link.value}' quotes {receipt.identity}, not "
        f"{journey.identity.as_pair()}. WHY: evidence from another candidate "
        "or machine cannot advance this user's journey. HOW: stamp the receipt "
        "with the tuple the journey ran on."
    )
    return receipt


@then("the specialist follows the instructions it was installed with")
def the_specialist_follows_its_instructions(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    _assert_crossing(
        _run(walked),
        journey,
        ChainLink.SPECIALIST_FOLLOWS_INSTRUCTIONS,
        verdict="PROVED",
    )


@then("the specialist reads the expertise that was installed alongside it")
def the_specialist_reads_its_expertise(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    _assert_crossing(
        _run(walked),
        journey,
        ChainLink.SPECIALIST_READS_ITS_EXPERTISE,
        verdict="PROVED",
    )


@then("the specialist reads the rule the project keeps for everyone who works in it")
def the_specialist_reads_the_project_rule(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    _assert_crossing(
        _run(walked), journey, ChainLink.SPECIALIST_READS_PROJECT_RULE, verdict="PROVED"
    )


@then(
    "the user is told what could not be approved, why it matters and how to remedy it"
)
def the_user_is_told_what_why_and_how(walked: dict[str, object]) -> None:
    run = _run(walked)
    assert run.outcome() == "REFUSED" and run.remedy_text().strip(), (
        "WHAT: work whose approval could not be honoured was not refused with "
        f"a remedy (outcome {run.outcome()!r}). WHY: a user who is never told "
        "which approval failed cannot tell a working install from a silently "
        "downgraded one. HOW: refuse the journey and name the approval, why it "
        f"matters and how to obtain it. Shown: {run.remedy_text()!r}"
    )


@then("no work is credited as having run under that approval requirement")
def no_work_is_credited_under_that_approval_requirement(
    walked: dict[str, object],
) -> None:
    receipt = _run(walked).crossing(ChainLink.APPROVAL_IS_ENFORCED_OR_REFUSED)
    assert receipt is not None and receipt.verdict == "REFUSED", (
        "WHAT: the approval crossing came back "
        f"{receipt.verdict if receipt else 'with no receipt at all'}, not a "
        "recorded refusal. WHY: an unenforced approval that is neither proved "
        "nor visibly refused is the silent downgrade this feature forbids -- "
        "and an absent receipt hides it just as effectively. HOW: record the "
        "refusal explicitly for that crossing."
    )


@then("the user sees the action stopped rather than completed")
def the_user_sees_the_action_stopped(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    _assert_crossing(
        _run(walked), journey, ChainLink.SAFEGUARD_REACTS, verdict="PROVED"
    )


@then("the safeguard's effect on this user's machine happened exactly once")
def the_safeguards_effect_happened_exactly_once(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    """Exactly-once is the property; at-least-once would pass a duplicate."""
    receipt = _assert_crossing(
        _run(walked), journey, ChainLink.SAFEGUARD_REACTS, verdict="PROVED"
    )
    assert receipt.external_effect_count == 1, (
        "WHAT: the safeguard's external effect happened "
        f"{receipt.external_effect_count} times, not once. WHY: two effects "
        "double-count one reaction and zero credits enforcement that never "
        "happened; only exactly-once means the safeguard did its job. HOW: "
        "correlate the reaction to a single external effect for this machine."
    )


@then("the operator sees a durable attestation for the tick that ran")
def the_operator_sees_a_durable_attestation(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    _assert_crossing(
        _run(walked), journey, ChainLink.LOOP_TICK_IS_ATTESTED, verdict="PROVED"
    )


@then("the tick attempted after the stop is refused")
def the_tick_after_the_stop_is_refused(walked: dict[str, object]) -> None:
    run = _run(walked)
    assert str(run.observable("retick_outcome")) == "REFUSED", (
        "WHAT: the tick attempted after the stop came back "
        f"{run.observable('retick_outcome')!r}, not a refusal. WHY: a stopped "
        "loop that still ticks makes Stop a suggestion rather than a "
        "guarantee, and the operator can no longer tell stopped work from "
        "running work. HOW: refuse any tick claimed on a stopped generation."
    )


@then("the user is told that capability was not proved here")
def the_user_is_told_the_capability_was_not_proved(walked: dict[str, object]) -> None:
    receipt = _run(walked).crossing(ChainLink.SAFEGUARD_REACTS)
    assert receipt is None or receipt.verdict != "PROVED", (
        "WHAT: a capability was reported PROVED on work done for a different "
        "candidate and a different machine. WHY: this is evidence laundering "
        "-- the user would be told their install works because someone else's "
        "did. HOW: reject any observation whose candidate and machine are not "
        f"the ones under test. Reported: {receipt}"
    )


@then("the whole journey is refused rather than completed on borrowed work")
def the_whole_journey_is_refused_on_borrowed_work(walked: dict[str, object]) -> None:
    run = _run(walked)
    borrowed = sorted(
        receipt.item
        for receipt in run.crossings()
        if receipt.identity[0] == FOREIGN_CANDIDATE
    )
    assert run.outcome() != "COMPLETED" and not borrowed, (
        f"WHAT: the journey reported {run.outcome()!r} while carrying "
        f"crossings from another candidate ({borrowed}). WHY: a completed "
        "journey is the claim the user relies on, and it must never rest on a "
        "tuple that was not the one installed. HOW: refuse the journey when "
        "any observation quotes another candidate or machine."
    )


@then(
    "the Claude user's safeguards and specialists are the same after the install as before it"
)
def the_claude_users_surface_is_unchanged(walked: dict[str, object]) -> None:
    """Before and after, both observed by production -- neither asserted here."""
    run = _run(walked)
    before = run.claude_surface_before()
    after = run.claude_surface_after()
    assert before and after and before == after, (
        "WHAT: the Claude user's surface changed across the install "
        f"({before!r} -> {after!r}). WHY: Claude preservation is a floor of "
        "this slice, so an existing user must not pay for a Codex install; an "
        "unobserved before or after hides exactly that regression. HOW: "
        "observe the Claude surface on both sides of the deployment and leave "
        "it byte-identical."
    )


@then("only the material nWave owns has changed")
def only_nwave_owned_material_has_changed(
    journey: InstalledParityJourney, walked: dict[str, object]
) -> None:
    run = _run(walked)
    _assert_crossing(run, journey, ChainLink.CLAUDE_USER_IS_UNCHANGED, verdict="PROVED")
    assert run.owned_material(), (
        "WHAT: the install reported no nWave-owned material at all. WHY: an "
        "install that preserves everything by changing nothing preserves "
        "foreign content trivially and delivers nothing -- the preservation "
        "claim is only meaningful alongside a real owned change. HOW: report "
        "the material nWave owns after the install."
    )
