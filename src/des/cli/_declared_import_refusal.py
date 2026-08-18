"""Shared declared-imports refusal: the single WHAT/WHY/HOW `des dispatch`
and `des validate-delivery-contract` both print (DRY -- one message, no
drifting second copy across the two point-of-use verification call sites
ADR-SSOT-002 Section 4a item 9 names).

K4 failure-to-design matrix row 12 + Run 4 defects A/B
(``docs/analysis/2026-08-05-des-simplification-evidence-backed-roadmap.md``):
an ATD-authored ``declared-imports`` entry can cite a symbol absent from the
base tree entirely (defect A, e.g. an un-vendored third-party package), or a
symbol the SAME contract's own target is the one creating (defect B,
self-reference) -- both were previously caught only at the crafter's own
BASELINE `des validate-delivery-contract` call, after a full crafter dispatch
was already spent. `des dispatch` is the documented early gate (called by
root immediately after `CONTRACT_READY`, before any crafter subagent starts
-- `nWave/skills/nw-distill/SKILL.md` "that one call only validates,
resolves and hashes the contract"); wiring this same check there catches
both defect classes before that cost is spent, without reversing the
separately-documented, ADR-anchored rule that DISTILL/the acceptance
designer itself never calls `des validate-delivery-contract` (that call
stays exclusively `des dispatch`'s and the crafter's own BASELINE
point-of-use verification).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.domain.declared_import_resolver import (
    resolve_declared_import,
    unresolved_declared_import_owner,
)


if TYPE_CHECKING:
    from pathlib import Path


def all_missing_declared_imports(
    repo_root: Path, contract: dict
) -> list[tuple[str, str]]:
    """Every `(target_path, reference)` absent from the base tree, across
    ALL targets -- not only the first.

    Run 5 (K4 matrix): `des dispatch` rejected the same contract three
    times in sequence, one defect per REVISE cycle, because only the FIRST
    missing declared-import was ever reported. Reporting every one lets a
    single ATD REVISE round fix them all instead of costing one full
    dispatch/REVISE cycle per defect.
    """
    missing: list[tuple[str, str]] = []
    for target_path, target_plan in contract["targets"].items():
        for reference in target_plan.get("declared-imports", []):
            if not resolve_declared_import(repo_root, reference):
                missing.append((target_path, reference))
    return missing


def first_missing_declared_import(
    repo_root: Path, contract: dict
) -> tuple[str, str] | None:
    """Return the first `(target_path, reference)` absent from the base tree."""
    return next(iter(all_missing_declared_imports(repo_root, contract)), None)


def unresolved_declared_import_how(
    repo_root: Path, contract: dict, reference: str
) -> str:
    """Run 4 defect A vs B: name exactly why `reference` is unresolved.

    A `creating target` from `unresolved_declared_import_owner` that is
    ALSO one of this SAME contract's own `targets` keys is a self-reference
    (defect B: the delivery cites, as already-existing, a symbol its own
    target is the one creating) -- name that target and its `justification`
    field explicitly. Otherwise the module is absent from the base tree
    entirely (defect A, e.g. an un-vendored third-party package) -- the
    schema has no dedicated "creates" field (thin-delivery-contract.schema.json
    `$defs.targetPlan`), so the generic guidance points at the same existing
    `justification` field a creating target already carries, never a new one.
    """
    base_revision = str(contract["repository"]["base-revision"])
    owner = unresolved_declared_import_owner(repo_root, reference)
    if owner is not None and owner in contract["targets"]:
        return (
            f"'{reference}' is not present at base revision {base_revision} "
            f"because this delivery's own target {owner!r} is the one that "
            "creates it -- remove it from declared-imports (reuse-only) and "
            f"document the cross-target dependency in {owner!r}'s own "
            "justification instead"
        )
    return (
        f"'{reference}' is not present at base revision {base_revision}: "
        "cite only existing base-tree symbols, or if this delivery creates "
        "it, document that in the creating target's own justification "
        "field instead of declared-imports"
    )
