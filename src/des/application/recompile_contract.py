"""Preserve-fills merge for ``des recompile-contract``: the pure policy
that folds ATD's already-authored semantic fills into a freshly recompiled
skeleton.

``des compile-contract`` refuses to overwrite an existing contract because
a blind overwrite silently discards ATD's fills -- which left NO sanctioned
producer-owned route when the architecture authority itself moves on after
ATD started filling (three DeliveryIds were abandoned to exactly this gap,
2026-08-21). This module is that route's core: the recompiled contract is
authoritative for every MECHANICAL fact (targets, decisions, obligations,
verification-scope, base-revision, ...), and the ONLY thing carried over
from the existing contract is what ATD alone authored -- the semantic fill
fields ``des.application.fill_contract`` names (``outcome``, each target's
``justification`` and ``boundary.*``) -- and only where the target's
identity still holds:

* a target present in both sets WITH the same decision keeps its
  non-placeholder fills;
* a target whose declared decision CHANGED is a different delivery fact --
  its fills are reset to placeholders and the change is surfaced loud
  (GDP-6), never silently carried;
* a new target arrives as compiled (placeholders); a removed target's
  fills are dropped with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from des.application.fill_contract import (
    CONTRACT_LEVEL_FIELDS,
    TARGET_LEVEL_FIELDS,
)
from des.domain.contract_placeholder_resolver import PLACEHOLDER


@dataclass(frozen=True, slots=True)
class DecisionChange:
    """One same-path target whose declared decision changed between the
    existing contract and the recompiled one -- surfaced loud, fills reset."""

    path: str
    old_decision: str
    new_decision: str


@dataclass(frozen=True, slots=True)
class MergeSummary:
    """The merged contract plus the counts the CLI's one RECOMPILE stdout
    line reports -- ``kept_fills`` counts individual preserved semantic
    fields (outcome included), ``new_targets`` counts genuinely-new paths
    AND decision-changed ones (their fills restart from placeholder)."""

    contract: dict
    kept_fills: int
    new_targets: int
    dropped_targets: int
    decision_changes: tuple[DecisionChange, ...]


def _read_dotted(plan: dict, dotted: str) -> object:
    head, _, rest = dotted.partition(".")
    if rest:
        return plan.get(head, {}).get(rest)
    return plan.get(head)


def _write_dotted(plan: dict, dotted: str, value: object) -> None:
    head, _, rest = dotted.partition(".")
    if rest:
        plan[head] = {**plan.get(head, {}), rest: value}
    else:
        plan[head] = value


def merge_preserve_fills(existing: dict, recompiled: dict) -> MergeSummary:
    """``recompiled`` with every still-valid semantic fill of ``existing``
    folded back in. Pure: neither input dict is mutated."""
    kept_fills = 0
    new_targets = 0
    decision_changes: list[DecisionChange] = []
    existing_targets = existing.get("targets", {})
    merged_targets: dict[str, dict] = {}
    for path, recompiled_plan in recompiled.get("targets", {}).items():
        existing_plan = existing_targets.get(path)
        if existing_plan is None:
            new_targets += 1
            merged_targets[path] = recompiled_plan
            continue
        if existing_plan.get("decision") != recompiled_plan.get("decision"):
            decision_changes.append(
                DecisionChange(
                    path=path,
                    old_decision=existing_plan.get("decision"),
                    new_decision=recompiled_plan.get("decision"),
                )
            )
            new_targets += 1
            merged_targets[path] = recompiled_plan
            continue
        plan = dict(recompiled_plan)
        for dotted in sorted(TARGET_LEVEL_FIELDS):
            filled = _read_dotted(existing_plan, dotted)
            if isinstance(filled, str) and filled != PLACEHOLDER:
                _write_dotted(plan, dotted, filled)
                kept_fills += 1
        merged_targets[path] = plan

    merged = {**recompiled, "targets": merged_targets}
    for field in sorted(CONTRACT_LEVEL_FIELDS):
        filled = existing.get(field)
        if isinstance(filled, str) and filled != PLACEHOLDER:
            merged[field] = filled
            kept_fills += 1

    dropped_targets = sum(1 for path in existing_targets if path not in merged_targets)
    return MergeSummary(
        contract=merged,
        kept_fills=kept_fills,
        new_targets=new_targets,
        dropped_targets=dropped_targets,
        decision_changes=tuple(decision_changes),
    )
