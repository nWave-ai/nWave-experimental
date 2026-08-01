"""Active-RED steps for the saturated scheduler walking skeleton (slice-01).

Every oracle here binds a lane's reported state to the artifacts that exist or
are missing. Nothing asserts against a state the test itself declared, and no
step accepts an orchestrator's judgement in place of evidence.
"""

from __future__ import annotations

import re

from pytest_bdd import given, scenarios, then, when

from .composition import SaturatedSchedulerComposition
from .domain_types import CommandObservation, SchedulerRun
from .installed_candidate import InstalledCandidateComposition, InstalledSchedulerRun


scenarios("../saturated-scheduler.feature")


# The plan's own vocabulary: the artifact slice-02 consumes, and the artifact
# slice-04 awaits and no one has produced. The scheduler keys artifacts by a
# fuller path; the plan's declared name is the tail of it, and that is what an
# operator reads, so these oracles match on the declared name.
_ATTESTED_ARTIFACT = "acceptance-test.v1"
_MISSING_ARTIFACT = "verification-seal.v1"

# A blocker naming a slice instead of an artifact is the barrier this feature
# exists to remove.
_SLICE_ID = re.compile(r"slice-\d+")

# A snapshot is a value. A key naming an execution effect means DES did more
# than answer the question.
_EXECUTION_KEYS = {
    "started",
    "spawned",
    "executed",
    "process_id",
    "agent_id",
    "worktree",
}


# --- given ------------------------------------------------------------------


@given("a feature plan declaring independent work and one local operation")
def given_feature_plan(composition: SaturatedSchedulerComposition) -> None:
    composition.provision_feature_plan()


@given("no lane has produced any completion evidence yet")
def given_no_evidence(composition: SaturatedSchedulerComposition) -> None:
    composition.provision_empty_current_evidence()


@given(
    "the acceptance-test artifact is attested while its producing slice is unfinished"
)
def given_artifact_attested(composition: SaturatedSchedulerComposition) -> None:
    composition.attest_acceptance_test_artifact()


@given("the completion evidence is present but unreadable")
def given_unreadable_evidence(composition: SaturatedSchedulerComposition) -> None:
    composition.corrupt_current_evidence()


@given("the release-shaped candidate is installed once in a clean environment")
def given_installed_candidate(
    installed_composition: InstalledCandidateComposition,
) -> None:
    # The session fixture performs one assembly and one clean installation.
    assert installed_composition.venv_root.is_dir()


@given("a disposable project declares independent work and one local operation")
def given_disposable_project(
    installed_composition: InstalledCandidateComposition,
) -> None:
    installed_composition.provision_project()


# --- when -------------------------------------------------------------------


@when("the orchestrator asks DES what can run now twice")
def when_schedule_twice(
    composition: SaturatedSchedulerComposition, result_box: dict[str, object]
) -> None:
    result_box["schedule"] = composition.run_schedule_twice()


@when("the orchestrator asks DES what can run now")
def when_schedule_once(
    composition: SaturatedSchedulerComposition, result_box: dict[str, object]
) -> None:
    result_box["single"] = composition.run_schedule_once()


@when("the project asks the installed scheduler what can run now")
def when_installed_surface(
    installed_composition: InstalledCandidateComposition, result_box: dict[str, object]
) -> None:
    result_box["installed"] = installed_composition.invoke_public_surface()


# --- readers ----------------------------------------------------------------


def _installed_run(result_box: dict[str, object]) -> InstalledSchedulerRun:
    run = result_box["installed"]
    assert isinstance(run, InstalledSchedulerRun)
    return run


def _snapshot(result_box: dict[str, object]) -> dict[str, object]:
    run = result_box["schedule"]
    assert isinstance(run, SchedulerRun)
    return SaturatedSchedulerComposition.json_event(run.first)


def _single(result_box: dict[str, object]) -> CommandObservation:
    observation = result_box["single"]
    assert isinstance(observation, CommandObservation)
    return observation


def _lanes(snapshot: dict[str, object]) -> list[dict[str, object]]:
    nodes = snapshot["nodes"]
    assert isinstance(nodes, list)
    return nodes


# --- then: the installed candidate (walking skeleton) -----------------------


@then("the installed help offers the scheduling query")
def then_installed_help_offers_query(result_box: dict[str, object]) -> None:
    help_observation = _installed_run(result_box).help
    assert help_observation.exit_code == 0 and "schedule" in help_observation.stdout, (
        "WHAT: the installed des help surface never mentions the scheduling query; "
        "WHY: a route that exists only in the source checkout cannot be found by "
        "someone who installed the product; "
        "HOW: register the schedule route in the distributed dispatcher and its help."
    )


@then("two installed reads return the same lane snapshot under one policy identity")
def then_installed_reads_agree(result_box: dict[str, object]) -> None:
    run = _installed_run(result_box)
    first = InstalledCandidateComposition.event(run.first)
    second = InstalledCandidateComposition.event(run.second)
    assert run.first.exit_code == run.second.exit_code == 0
    assert first == second and first["policy_digest"], (
        "WHAT: two identical reads of an unchanged project disagreed, or carried "
        "no policy identity; "
        "WHY: an orchestrator cannot act on an answer that changes when nothing "
        "changed; "
        "HOW: derive the snapshot deterministically and stamp it with the "
        "scheduling policy digest."
    )


@then(
    "the installed snapshot marks every unblocked cloud lane ready and orders one box lane"
)
def then_installed_snapshot_is_saturated(result_box: dict[str, object]) -> None:
    snapshot = InstalledCandidateComposition.event(_installed_run(result_box).first)
    ready_cloud = snapshot["ready_cloud"]
    assert isinstance(ready_cloud, list) and ready_cloud, (
        "WHAT: the installed scheduler reported no ready cloud lane although the "
        "project declares independent work with nothing to wait for; "
        "WHY: a ready lane that is not reported ready is exactly the idle-capacity "
        "error this feature exists to remove; "
        "HOW: mark every lane whose prerequisites are all satisfied as READY."
    )
    assert all(lane["state"] == "READY" for lane in ready_cloud)
    assert len(snapshot["active_box"]) + len(snapshot["admitted_box"]) <= 1, (
        "WHAT: the installed scheduler admitted more than one local operation; "
        "WHY: the box is one shared lane and over-admitting it is what the "
        "orchestrator asked DES to prevent; "
        "HOW: admit at most one box artifact and queue the rest with a reason."
    )


@then(
    "the installed scheduler records no execution and leaves the disposable project unchanged"
)
def then_installed_scheduler_is_query_only(
    installed_composition: InstalledCandidateComposition,
    result_box: dict[str, object],
) -> None:
    run = _installed_run(result_box)
    snapshot = InstalledCandidateComposition.event(run.first)
    assert run.before == run.after, (
        "WHAT: asking what can run now changed the disposable project; "
        "WHY: a query must not mutate its subject, least of all the evidence its "
        "own answer rests on; "
        "HOW: keep every schedule adapter read-only."
    )
    assert run.answering_module_path.startswith(str(installed_composition.venv_root)), (
        "WHAT: the code that answered does not live inside the installed "
        f"candidate — it resolved to {run.answering_module_path!r}; "
        "WHY: an answer borrowed from the source checkout proves nothing about "
        "what a user who installed the product actually receives; "
        "HOW: ship the scheduler inside the release-shaped candidate."
    )
    assert snapshot["execution_mode"] == "plan-only" and not _EXECUTION_KEYS & set(
        snapshot
    ), (
        "WHAT: the installed snapshot claims DES started something; "
        "WHY: DES answers the question and the orchestrator's own agent tooling "
        "dispatches under hooks; "
        "HOW: return lanes and reasons only, with no execution boundary."
    )


# --- then: the deterministic artifact-level snapshot ------------------------


@then("both snapshots carry the same lanes in the same order under one policy identity")
def then_snapshot_is_deterministic(result_box: dict[str, object]) -> None:
    run = result_box["schedule"]
    assert isinstance(run, SchedulerRun)
    first = SaturatedSchedulerComposition.json_event(run.first)
    second = SaturatedSchedulerComposition.json_event(run.second)
    assert (
        first["nodes"] == second["nodes"]
        and first["admitted_box"] == second["admitted_box"]
    ), (
        "WHAT: two reads of the same plan and the same evidence produced different "
        "lanes or a different order; "
        "WHY: an orchestrator that reruns the query must not receive a different "
        "instruction; "
        "HOW: sort lanes by policy artifact rank and artifact key."
    )
    assert (
        first["policy_digest"] == second["policy_digest"] and first["policy_digest"]
    ), (
        "WHAT: the snapshot carries no stable policy identity; "
        "WHY: later work consumes this snapshot and must know which policy "
        "produced it; "
        "HOW: stamp every snapshot with the scheduling policy digest."
    )


@then("every dependency edge names the consumed artifact and the condition it awaits")
def then_edges_are_artifact_level(result_box: dict[str, object]) -> None:
    edges = _snapshot(result_box)["edges"]
    assert isinstance(edges, list) and edges, (
        "WHAT: the snapshot declares no dependency edge although the plan declares "
        "one lane consuming another lane's artifact; "
        "WHY: without edges the orchestrator is back to guessing what waits on what; "
        "HOW: build one edge per declared artifact consumption."
    )
    assert all(
        {"to", "consumed_artifact", "required_condition"} <= set(edge) for edge in edges
    ), (
        "WHAT: a dependency edge omits one of its two ends or the condition it "
        "awaits; "
        "WHY: an edge that names only a slice turns an input contract into a "
        "finish-the-slice barrier and hides independently runnable work; "
        "HOW: name the dependent artifact, the consumed artifact, and the required "
        "condition on every edge."
    )


@then(
    "exactly one box lane is admitted and every remaining box operation is queued with its reason"
)
def then_one_box_lane(result_box: dict[str, object]) -> None:
    snapshot = _snapshot(result_box)
    admitted = len(snapshot["active_box"]) + len(snapshot["admitted_box"])
    assert admitted <= 1, (
        "WHAT: more than one local operation was admitted at once; "
        "WHY: the box is the one genuinely scarce resource here; "
        "HOW: admit at most one box artifact per snapshot."
    )
    assert all(
        entry["reason"] in {"box-occupied", "higher-priority-ready-artifact"}
        for entry in snapshot["deferred_box"]
    ), (
        "WHAT: box work was withheld without saying why; "
        "WHY: an unexplained queue is indistinguishable from work that was lost; "
        "HOW: give every deferred box entry one of the policy's declared reasons."
    )


@then(
    "every blocked lane names its missing artifact, its awaited condition, and its next action"
)
def then_blockers_are_actionable(result_box: dict[str, object]) -> None:
    blockers = _snapshot(result_box)["blockers"]
    assert isinstance(blockers, list) and blockers, (
        "WHAT: no lane is reported blocked although the plan declares a lane "
        "awaiting an artifact nobody has produced; "
        "WHY: a blocker DES does not name is one the orchestrator must rediscover "
        "by hand; "
        "HOW: report every unsatisfied prerequisite as a named blocker."
    )
    assert all(
        {"missing_artifact", "required_condition", "next_action"} <= set(blocker)
        for blocker in blockers
    ), (
        "WHAT: a blocked lane lacks its missing artifact, its awaited condition, or "
        "its next action; "
        "WHY: a blocker without a reason reads exactly like silence, and silence is "
        "what an orchestrator misreads as a block; "
        "HOW: emit the missing artifact, the condition, and the recovery action."
    )


@then("the snapshot needs no host scheduler on Linux macOS or Windows")
def then_snapshot_is_portable(result_box: dict[str, object]) -> None:
    snapshot = _snapshot(result_box)
    assert (
        set(snapshot["supported_platforms"]) == {"linux", "macos", "windows"}
        and snapshot["requires_host_scheduler"] is False
    ), (
        "WHAT: the snapshot does not promise the same answer on every supported "
        "host without a daemon; "
        "WHY: DES is an on-demand cross-platform command; "
        "HOW: derive the snapshot from plan and evidence only — no cron, no Task "
        "Scheduler, no launch agent, no process-table probe."
    )


@then(
    "the snapshot records no execution and leaves the plan and the evidence unchanged"
)
def then_snapshot_is_query_only(
    composition: SaturatedSchedulerComposition, result_box: dict[str, object]
) -> None:
    run = result_box["schedule"]
    assert isinstance(run, SchedulerRun)
    snapshot = SaturatedSchedulerComposition.json_event(run.first)
    assert snapshot["execution_mode"] == "plan-only" and not _EXECUTION_KEYS & set(
        snapshot
    ), (
        "WHAT: the snapshot claims an execution side effect; "
        "WHY: DES answers the question; the orchestrator dispatches under hooks; "
        "HOW: return lanes and reasons only."
    )
    assert composition.workspace_is_unchanged(run), (
        "WHAT: asking what can run now changed the plan or the evidence bytes; "
        "WHY: evidence is the authority over lane state, so a query that edits it "
        "corrupts the only thing the answer rests on; "
        "HOW: keep every schedule adapter read-only."
    )


# --- then: artifact-granular readiness --------------------------------------


@then("the lane consuming the attested artifact is ready")
def then_consumer_lane_is_ready(result_box: dict[str, object]) -> None:
    snapshot = SaturatedSchedulerComposition.json_event(_single(result_box))
    dependents = {
        edge["to"]
        for edge in snapshot["edges"]
        if str(edge.get("consumed_artifact", "")).endswith(_ATTESTED_ARTIFACT)
    }
    assert dependents, (
        "WHAT: no lane is reported as consuming the attested artifact; "
        f"WHY: the plan declares a lane consuming {_ATTESTED_ARTIFACT} and that "
        "lane must appear before its readiness can be judged; "
        "HOW: build one edge per declared artifact consumption."
    )
    consumers = [
        lane for lane in _lanes(snapshot) if lane.get("artifact_key") in dependents
    ]
    assert consumers and all(lane["state"] == "READY" for lane in consumers), (
        "WHAT: a lane whose only input is already attested was not reported READY; "
        "WHY: readiness attaches to the consumed artifact, not to the completion of "
        "the slice that produced it — treating a slice boundary as a barrier is the "
        "idle-capacity defect this feature removes; "
        "HOW: mark a lane READY as soon as every artifact it consumes is attested."
    )


@then(
    "the lane awaiting the still-missing artifact is blocked by that artifact by name"
)
def then_awaiting_lane_is_blocked_by_name(result_box: dict[str, object]) -> None:
    snapshot = SaturatedSchedulerComposition.json_event(_single(result_box))
    blockers = [
        blocker
        for blocker in snapshot["blockers"]
        if str(blocker.get("missing_artifact", "")).endswith(_MISSING_ARTIFACT)
    ]
    assert blockers, (
        "WHAT: the lane awaiting an unproduced artifact is not blocked by that "
        f"artifact's name ({_MISSING_ARTIFACT}); "
        "WHY: a blocker named by slice rather than by artifact cannot tell the "
        "orchestrator what to produce next; "
        "HOW: name the missing artifact itself on the blocker."
    )


@then("no lane is held back merely because a producing slice is unfinished")
def then_no_slice_barrier(result_box: dict[str, object]) -> None:
    snapshot = SaturatedSchedulerComposition.json_event(_single(result_box))
    slice_shaped = [
        blocker
        for blocker in snapshot["blockers"]
        if _SLICE_ID.fullmatch(str(blocker.get("missing_artifact", "")))
    ]
    assert not slice_shaped, (
        "WHAT: a lane is blocked by a slice identifier instead of by a missing "
        "artifact; "
        "WHY: only a missing artifact may hold a lane back — a slice boundary is an "
        "input contract, never a synchronisation barrier, and treating it as one "
        "leaves ready lanes idle; "
        f"HOW: block a lane only on a named artifact. Offending blockers: "
        f"{slice_shaped!r}."
    )


# --- then: unreadable evidence is incapacity, never readiness ---------------


@then("DES refuses with an evidence-indeterminate verdict naming the unreadable input")
def then_refusal_is_indeterminate(result_box: dict[str, object]) -> None:
    observation = _single(result_box)
    event = SaturatedSchedulerComposition.json_event(observation)
    assert (
        observation.exit_code == 3 and event["event"] == "ScheduleEvidenceIndeterminate"
    ), (
        "WHAT: unreadable evidence did not produce the evidence-indeterminate "
        "refusal; "
        "WHY: an input DES cannot read is an incapacity to answer, and reporting "
        "anything else would present a guess as an answer; "
        "HOW: exit 3 with ScheduleEvidenceIndeterminate when evidence cannot be read."
    )
    assert "atdd-pure-events" in str(event.get("unreadable_input", "")), (
        "WHAT: the refusal does not name which input it could not read; "
        "WHY: an unnamed bad input leaves the operator searching; "
        "HOW: name the exact unreadable path in the refusal."
    )


@then(
    "the refusal states what failed, why it matters, and which existing tool repairs it"
)
def then_refusal_explains_itself(result_box: dict[str, object]) -> None:
    event = SaturatedSchedulerComposition.json_event(_single(result_box))
    assert {"WHAT", "WHY", "HOW"} <= set(event), (
        "WHAT: the refusal omits its WHAT, WHY, or HOW; "
        "WHY: a refusal an operator cannot act on costs the same as a silent "
        "failure; "
        "HOW: render all three fields from the shared diagnostic renderer."
    )
    how = str(event["HOW"])
    assert "des " in how, (
        "WHAT: the repair instruction names no existing command to run; "
        "WHY: telling an operator to fix a corrupt ledger by hand invites a second "
        "corruption; "
        f"HOW: name the existing doctor/integrity command. Received: {how!r}."
    )


@then("no lane is reported ready and nothing is executed")
def then_refusal_fabricates_no_readiness(result_box: dict[str, object]) -> None:
    event = SaturatedSchedulerComposition.json_event(_single(result_box))
    assert not event.get("ready_cloud") and not event.get("admitted_box"), (
        "WHAT: DES reported ready work while admitting it could not read the "
        "evidence; "
        "WHY: absent evidence is never readiness — a fabricated READY sends an "
        "orchestrator to redo work that may already exist; "
        "HOW: report no lane as ready when the evidence is indeterminate."
    )
    assert not _EXECUTION_KEYS & set(event), (
        "WHAT: the refusal claims an execution effect; "
        "WHY: DES never starts anything, least of all while refusing; "
        "HOW: return the refusal as a value."
    )
