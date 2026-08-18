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

Run 6 (K4 matrix): the resolver ALSO accepted a false-reject regression --
a bare name genuinely bound at the top of the target's OWN file (e.g.
`CronSim`, imported via `from cronsim import CronSim` in that exact
`hc/api/models.py`) is a real base-tree reference, not an invented one, even
though it never resolves as a dotted module path (there is no file literally
named `CronSim.py`, and `cronsim` itself is never vendored into the tree for
`resolve_declared_import` to walk into). `is_name_bound_in_target_file`
checks the target's own file first; `resolve_declared_import`'s dotted
resolution runs second, unchanged, so a genuinely invented DOTTED reference
(Run 4's `cronsim.CronSim`) still rejects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.domain.declared_import_resolver import (
    is_name_bound_in_target_file,
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
            if is_name_bound_in_target_file(repo_root, target_path, reference):
                continue
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
        "declared-imports accepts either a bare name bound at the top of "
        "the TARGET's own file (an import alias or a module-level "
        "definition), or a dotted base-tree module/symbol path -- cite one "
        "of those forms, or if this delivery creates it, document that in "
        "the creating target's own justification field instead of "
        "declared-imports"
    )
