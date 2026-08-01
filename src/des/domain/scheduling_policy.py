"""Typed, deterministic policy and read-only plan builder for ``des schedule``.

The policy is the scheduling SSOT.  It deliberately describes resource
classification and rendered projections only; it has no execution, process, or
agent-invocation dependency.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Mapping


CLOUD_REASONING = "CLOUD_REASONING"
BOX_OPERATION = "BOX_OPERATION"
_ARTIFACT_RANK = {
    "acceptance-test": 0,
    "red-seal": 1,
    "green-implementation": 2,
    "vera-verdict": 3,
    "verification-seal": 4,
    "commit-attestation": 5,
}
_ARTIFACTS = tuple(_ARTIFACT_RANK)
_SLICE_ROW = re.compile(r"^\|\s*(slice-[^|\s]+)\s*\|", re.MULTILINE)
_SLICE_ROW_BODY = re.compile(r"^\|\s*(slice-[^|\s]+)\s*\|(?P<body>.*)$", re.MULTILINE)
_CONSUMED_ARTIFACT = re.compile(
    r"consumes artifact:\s*([^|.]+(?:\.[^|\s]+)?)", re.IGNORECASE
)


@dataclass(frozen=True)
class ArtifactRule:
    """The resource and predecessor rule for one durable artifact kind."""

    resource_class: str
    predecessor: str | None
    required_condition: str


@dataclass(frozen=True)
class SchedulingPolicy:
    """The sole machine-readable source for scheduler vocabulary and rules."""

    version: str
    artifact_rules: Mapping[str, ArtifactRule]
    bugfix_stage_resource: Mapping[str, str]
    projection_names: tuple[str, ...]
    marker_name: str
    default_cloud_capacity: int
    supported_platforms: tuple[str, ...]

    def digest(self) -> str:
        """Return a stable digest that every projection may carry."""
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


SCHEDULING_POLICY = SchedulingPolicy(
    version="1",
    artifact_rules={
        "acceptance-test": ArtifactRule(
            CLOUD_REASONING, None, "slice plan declares the artifact"
        ),
        "red-seal": ArtifactRule(
            BOX_OPERATION, "acceptance-test", "RedObserved evidence"
        ),
        "green-implementation": ArtifactRule(
            CLOUD_REASONING, "red-seal", "red seal is DONE"
        ),
        "vera-verdict": ArtifactRule(
            CLOUD_REASONING, "green-implementation", "green evidence is DONE"
        ),
        "verification-seal": ArtifactRule(
            BOX_OPERATION, "vera-verdict", "Vera verdict is DONE"
        ),
        "commit-attestation": ArtifactRule(
            BOX_OPERATION, "verification-seal", "verification seal is DONE"
        ),
    },
    bugfix_stage_resource={
        "rca": CLOUD_REASONING,
        "charter-authoring": CLOUD_REASONING,
        "at-authoring": CLOUD_REASONING,
        "crafter-green": CLOUD_REASONING,
        "vera-examine": CLOUD_REASONING,
        "red-seal": BOX_OPERATION,
        "verification-seal": BOX_OPERATION,
        "commit-slice": BOX_OPERATION,
        "merge": BOX_OPERATION,
    },
    projection_names=(
        "cli_help",
        "session_start",
        "skills",
        "runtime",
        "gate_message",
        "command_catalog",
    ),
    marker_name="DES-SCHEDULE-ARTIFACT",
    default_cloud_capacity=3,
    supported_platforms=("linux", "macos", "windows"),
)


def bugfix_box_lane_stages(
    policy: SchedulingPolicy = SCHEDULING_POLICY,
) -> frozenset[str]:
    """Project actual shared operations from the single scheduling policy."""
    return frozenset(
        stage
        for stage, resource in policy.bugfix_stage_resource.items()
        if resource == BOX_OPERATION
    )


def policy_projections(
    policy: SchedulingPolicy = SCHEDULING_POLICY,
) -> dict[str, dict[str, str]]:
    """Render bounded projection identities from policy, never from documents."""
    digest = policy.digest()
    return {
        name: {"policy_digest": digest, "policy_version": policy.version}
        for name in policy.projection_names
    }


def feature_slices(feature_delta: str) -> tuple[str, ...]:
    """Read ordered slice identifiers from a feature plan without mutating it."""
    slices = tuple(dict.fromkeys(_SLICE_ROW.findall(feature_delta)))
    if not slices:
        raise ValueError("no Slice Plan rows named slice-* were found")
    return slices


def declared_slice_dependencies(feature_delta: str) -> Mapping[str, str]:
    """Return only explicit feature-plan artifact dependencies, by slice."""
    dependencies: dict[str, str] = {}
    for match in _SLICE_ROW_BODY.finditer(feature_delta):
        consumed = _CONSUMED_ARTIFACT.search(match.group("body"))
        if consumed:
            dependencies[match.group(1)] = consumed.group(1)
    return dependencies


def artifact_key(feature_id: str, slice_id: str, kind: str) -> str:
    return f"feature/{feature_id}/slice/{slice_id}/artifact/{kind}"


def declared_artifact_kind(declared_dependency: str) -> str:
    """Strip a declared artifact's version suffix (``acceptance-test.v1`` -> ``acceptance-test``)."""
    return declared_dependency.rsplit(".", 1)[0]


def build_schedule_plan(
    feature_id: str,
    feature_delta: str,
    *,
    cloud_capacity: int | None = None,
    attested_slice_ids: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """Build a deterministic plan from feature-plan bytes and attested evidence.

    ``attested_slice_ids`` names every slice with at least one completion-ledger
    record for this feature -- the caller's evidence read, kept out of this pure
    calculation (SD-1). Per DD-D2 a lane consuming a declared cross-slice
    artifact is READY as soon as that artifact is attested, never merely
    because its producing slice finished. The plan's own producing slice is the
    first row of the Slice Plan; a generic ledger record for it attests only
    the weakest (``acceptance-test``) artifact kind -- never a stronger claim a
    caller did not actually record (no fabricated readiness).
    """
    policy = SCHEDULING_POLICY
    capacity = (
        policy.default_cloud_capacity if cloud_capacity is None else cloud_capacity
    )
    if capacity < 1:
        raise ValueError("cloud capacity must be a positive integer")
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, str]] = []
    blockers: list[dict[str, str]] = []
    ready_cloud: list[dict[str, str]] = []
    ready_box: list[dict[str, str]] = []
    dependencies = declared_slice_dependencies(feature_delta)
    slices = feature_slices(feature_delta)
    producing_slice_id = slices[0]
    producing_slice_attested = producing_slice_id in attested_slice_ids
    for slice_index, slice_id in enumerate(slices):
        for kind in _ARTIFACTS:
            rule = policy.artifact_rules[kind]
            key = artifact_key(feature_id, slice_id, kind)
            predecessor = rule.predecessor
            declared_dependency = (
                dependencies.get(slice_id) if predecessor is None else None
            )
            if predecessor is None and declared_dependency is None:
                state = "READY"
            elif predecessor is None and declared_dependency is not None:
                # A cross-slice declared consumption: keyed to the named
                # artifact actually consumed, never to the producing slice's
                # overall completion (DD-D2).
                predecessor_key = (
                    f"feature/{feature_id}/declared-artifact/{declared_dependency}"
                )
                required_condition = "declared consumed artifact is DONE"
                edges.append(
                    {
                        "from": predecessor_key,
                        "to": key,
                        "consumed_artifact": predecessor_key,
                        "required_condition": required_condition,
                    }
                )
                attested = (
                    producing_slice_attested
                    and declared_artifact_kind(declared_dependency) == "acceptance-test"
                )
                if attested:
                    state = "READY"
                else:
                    state = "BLOCKED"
                    blockers.append(
                        {
                            "artifact_key": key,
                            "missing_artifact": predecessor_key,
                            "required_condition": required_condition,
                            "next_action": "record the required artifact evidence, then rerun des schedule",
                        }
                    )
            else:
                state = "BLOCKED"
                predecessor_key = artifact_key(
                    feature_id,
                    slice_id,
                    predecessor,  # type: ignore[arg-type]
                )
                required_condition = rule.required_condition
                edges.append(
                    {
                        "from": predecessor_key,
                        "to": key,
                        "consumed_artifact": predecessor_key,
                        "required_condition": required_condition,
                    }
                )
                blockers.append(
                    {
                        "artifact_key": key,
                        "missing_artifact": predecessor_key,
                        "required_condition": required_condition,
                        "next_action": "record the required artifact evidence, then rerun des schedule",
                    }
                )
            node = {
                "artifact_key": key,
                "slice_id": slice_id,
                "artifact_kind": kind,
                "resource_class": rule.resource_class,
                "state": state,
                "sort_key": [slice_index, _ARTIFACT_RANK[kind], key],
            }
            nodes.append(node)
            if state == "READY":
                lane = {
                    "artifact_key": key,
                    "state": state,
                    "resource_class": rule.resource_class,
                }
                (
                    ready_cloud if rule.resource_class == CLOUD_REASONING else ready_box
                ).append(lane)
    nodes.sort(key=lambda item: item["sort_key"])
    ready_cloud.sort(key=lambda item: item["artifact_key"])
    admitted_cloud = ready_cloud[:capacity]
    deferred_cloud = [
        {**entry, "reason": "cloud-capacity"} for entry in ready_cloud[capacity:]
    ]
    descriptors = [
        _descriptor(entry["artifact_key"], policy) for entry in admitted_cloud
    ]
    plan: dict[str, object] = {
        "event": "SchedulePlanProduced",
        "policy_version": policy.version,
        "policy_digest": policy.digest(),
        "execution_mode": "plan-only",
        "requires_host_scheduler": False,
        "supported_platforms": list(policy.supported_platforms),
        "nodes": nodes,
        "edges": edges,
        "ready_cloud": ready_cloud,
        "admitted_cloud": admitted_cloud,
        "active_cloud": [],
        "ready_box": ready_box,
        "active_box": [],
        "admitted_box": [],
        "deferred_box": [],
        "deferred_cloud": deferred_cloud,
        "blockers": blockers,
        "admitted_descriptors": descriptors,
        "policy_projections": policy_projections(policy),
        "bugfix_resource_classes": dict(policy.bugfix_stage_resource),
        "running_observation": "unavailable",
    }
    # Deferral is already visible in `deferred_cloud`, but a structure the reader
    # must decode is not a warning: the plan knowing is not the plan SAYING. The
    # diagnostic therefore rides the DEFAULT report, not only the --consumer gate.
    diagnostic = unused_parallelism_diagnostic(plan)
    plan["diagnostics"] = [] if diagnostic is None else [diagnostic]
    return plan


def _descriptor(key: str, policy: SchedulingPolicy) -> dict[str, str]:
    digest = sha256(f"{policy.digest()}:{key}".encode()).hexdigest()
    return {
        "schema_version": "1",
        "artifact_key": key,
        "resource_class": CLOUD_REASONING,
        "preconditions_digest": "sha256:" + digest,
        "prompt": (
            f"{policy.marker_name}\n"
            f"Read-only scheduling descriptor for {key}.\n"
            "Use the native-agent dispatch prompt, then rerun des schedule or explicitly defer."
        ),
    }


def unused_parallelism_diagnostic(plan: Mapping[str, object]) -> dict[str, str] | None:
    """Return the policy-rendered consumer refusal, or ``None`` when saturated.

    The predicate keys on READY cloud work existing at all, not on capacity
    arithmetic: with no observation feed installed, `active_cloud` is always
    empty, so DES cannot tell an ADMITTED lane from a DISPATCHED one. Severity
    reports that honestly rather than presenting a guess as a measurement.
    """
    ready = plan.get("ready_cloud", [])
    admitted = plan.get("admitted_cloud", [])
    if not isinstance(ready, list) or not isinstance(admitted, list) or not ready:
        return None
    observed = plan.get("running_observation")
    descriptors = plan.get("admitted_descriptors", [])
    prompt_names = ", ".join(
        str(descriptor.get("artifact_key", ""))
        for descriptor in descriptors
        if isinstance(descriptor, dict)
    )
    return {
        "code": "UNUSED_PARALLELISM",
        "severity": "ADVISORY" if observed == "unavailable" else "BLOCKING",
        "WHAT": "READY cloud artifacts remain before a controlled box action.",
        "WHY": "Serializing reasoning wastes ownership-safe cloud capacity while the single box lane remains protected.",
        "HOW": (
            f"Use generated {SCHEDULING_POLICY.marker_name} prompts for {prompt_names}; "
            "then rerun des schedule or explicitly defer the ready cloud work."
        ),
    }
