"""Reference producer for the discuss-epic-mode slice-05 maintenance slice.

A LABELED, deterministic stand-in for the LLM-mediated epic-delta MAINTENANCE act
(picking up a feature, finalizing it, deciding the next pickup from the plan). This
is TEST-SUPPORT, NOT production code.

Slice-05's deliverable is PROSE: the linkage/status-flip procedure is LLM-mediated
skill / command text (DESIGN slice-02/04/05 text contracts: the slice's "code" is
SKILL / COMMAND text, there is NO ``src/des`` surface). The agent performing the
flip is the maintainer following the nw-discuss skill procedure during a discuss /
feature-end session, never a ``src/des`` function -- the maintenance is a heuristic
instruction to the agent, with no validator / gate / structured-config maintenance
surface on the tip (verified 2026-06-11: the slice-01 validator does NOT validate
Status cells -- DC-1; an illegal token like ``done`` validates ``accepted`` today).

These ATs verify the LSC contract (LSC-1..LSC-6) that the LLM-authored maintenance
prose MUST satisfy. To witness that contract mechanically without a production
maintainer, this module renders a deterministic LSC-conformant flip -- a GOLDEN-FILE
ANALOGUE. It is the reference the ATs measure the contract against; it makes no
claim to be the production deliverable. Anti-fixture-theater is inapplicable here
precisely because the production deliverable is prose, not a claimed ``src/des``
function.

This is NOT the presence-watcher anti-pattern. A presence-watcher greps the static
SKILL.md for the literal ``in-flight`` -- it passes the instant the crafter types
the literal, testing no behaviour. Here the flip is a deterministic FUNCTION of the
(current-status, action) pair: a pick-up of a ``pending`` row produces an
``in-flight`` row WITH its ``docs/feature/{id}/`` link (LSC-1); a finalize of an
``in-flight`` row produces a ``shipped`` row (LSC-2); a backward or illegal flip is
REJECTED (LSC-5/LSC-6). The ATs discriminate input -> output behaviour across the
forward path, the gate-preservation leg, the JIT invariant, and the rejection legs.

Phase C resolution precedent (2026-06-11, Ruling B, slice-02): the deterministic
producer is suite-local test-support, NEVER a ``src/des`` module imported at the
composition boundary. Slice-05 follows that ruling by construction.

The keystone-gate-preservation leg (LSC-1/LSC-2 corollary) is the genuine
mechanical seam: the FLIPPED epic-delta is re-validated through slice-01's REAL CLI
``des validate-feature-delta --require-feature-plan --format=json`` (driven by the
composition, NOT this module) -- it must still return ``accepted``. The flip-apply
itself (this module) is the reference producer; the gate that the flip must not
break is real ``src/des``.

Contract shape (effect isolation): the renderers here are PURE (plan -> markdown
string, no I/O); the only impure call is ``author_epic_delta`` / ``apply_pickup``
which write the rendered body to the production path. The split keeps the renderer
unable to reach the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from .domain_types import FeatureStatus, MaintenanceAction, MaintenanceVerdict


if TYPE_CHECKING:
    from pathlib import Path


#: EDC-3 epic-JTBD section heading (D2 grammar -- REF type token).
EPIC_JTBD_HEADING = "## Wave: DISCUSS / [REF] Epic Job & Intent"

#: EDC-4 / R1 Feature Plan heading (D2 grammar reused verbatim at epic granularity).
FEATURE_PLAN_HEADING = "## Wave: DISCUSS / [REF] Feature Plan"

#: EDC-4 fixed five-column header (mirrors the Slice Plan vocabulary).
FEATURE_PLAN_COLUMNS: tuple[str, ...] = (
    "Feature",
    "Value statement",
    "Status",
    "Annotation",
    "Justification",
)

#: EDC-5 keystone annotation token (Slice Plan vocabulary reused -- no new token).
KEYSTONE_ANNOTATION = "@walking-skeleton"

#: LSC-5 forward-only status order. A flip is legal iff it advances the row to the
#: NEXT token in this sequence (pending -> in-flight -> shipped). Any other target
#: (backward, skip-ahead, or off-set) is rejected.
_STATUS_ORDER: tuple[FeatureStatus, ...] = (
    FeatureStatus.PENDING,
    FeatureStatus.IN_FLIGHT,
    FeatureStatus.SHIPPED,
)

#: The action -> the source/target status pair it advances (LSC-1 pick-up,
#: LSC-2 finalize). The flip is applied ONLY when the row's current status equals
#: the action's source; otherwise it is a backward/illegal flip (LSC-5 rejection).
_ACTION_TRANSITION: dict[MaintenanceAction, tuple[FeatureStatus, FeatureStatus]] = {
    MaintenanceAction.PICK_UP: (FeatureStatus.PENDING, FeatureStatus.IN_FLIGHT),
    MaintenanceAction.FINALIZE: (FeatureStatus.IN_FLIGHT, FeatureStatus.SHIPPED),
}


@dataclass(frozen=True)
class FeaturePlanRow:
    """One row of the epic's Feature Plan (EDC-4).

    ``feature`` carries the feature name and, once picked up (LSC-1), its
    ``docs/feature/{id}/`` markdown link. ``status`` is an R2 token (LSC-5).
    """

    feature_id: str
    value_statement: str
    status: FeatureStatus
    annotation: str
    justification: str
    has_workspace_link: bool = False

    def feature_cell(self) -> str:
        """Render the Feature cell -- a plain name, or a link once picked up (LSC-1)."""
        if self.has_workspace_link:
            return f"[{self.feature_id}](docs/feature/{self.feature_id}/)"
        return self.feature_id

    def to_markdown(self) -> str:
        """Render the row as a GFM table line."""
        return (
            f"| {self.feature_cell()} | {self.value_statement} | {self.status.value} "
            f"| {self.annotation} | {self.justification} |"
        )


@dataclass(frozen=True)
class EpicDeltaPlan:
    """The authored content of an epic-delta with its Feature Plan rows.

    ``rows`` are in dependency order (row order = backward-only dependency order,
    EDC-6). The maintenance procedure flips individual row statuses in place.
    """

    epic_id: str
    job_statement: str
    rows: tuple[FeaturePlanRow, ...]


@dataclass(frozen=True)
class FlipResult:
    """Outcome of a maintenance flip on one Feature Plan row (the LSC verdict)."""

    verdict: MaintenanceVerdict
    plan: EpicDeltaPlan


def render_epic_delta(plan: EpicDeltaPlan) -> str:
    """Render an LSC/EDC-conformant epic-delta body from a plan. Pure function.

    No I/O. The rendered body carries the EDC-2 title, the EDC-3 epic-JTBD section,
    and the EDC-4 Feature Plan under the exact R1 heading with the five fixed
    columns -- so a flip that only changes a Status cell (and, on pick-up, adds a
    link to the Feature cell) leaves the structural shape intact and the document
    still clears slice-01's ``validate_feature_plan_content`` gate.
    """
    header = "| " + " | ".join(FEATURE_PLAN_COLUMNS) + " |"
    separator = "|" + "|".join("---" for _ in FEATURE_PLAN_COLUMNS) + "|"
    body_rows = "\n".join(row.to_markdown() for row in plan.rows)
    return (
        f"# Epic Delta: {plan.epic_id}\n"
        f"\n"
        f"{EPIC_JTBD_HEADING}\n"
        f"\n"
        f"{plan.job_statement}\n"
        f"\n"
        f"{FEATURE_PLAN_HEADING}\n"
        f"\n"
        f"{header}\n"
        f"{separator}\n"
        f"{body_rows}\n"
    )


def default_epic_plan(epic_id: str) -> EpicDeltaPlan:
    """A reference epic-delta plan, every row authored ``pending`` (EDC-7).

    The deterministic reference the maintenance procedure operates on: a keystone
    row (EDC-5) plus two follow-on rows in backward-only dependency order (EDC-6),
    all ``pending`` (an authored, not-yet-picked-up epic). The maintenance procedure
    flips individual rows as features are picked up and finalized.
    """
    keystone = FeaturePlanRow(
        feature_id="design-wave-migration",
        value_statement="Maintainer migrates the DESIGN wave to declarative composition",
        status=FeatureStatus.PENDING,
        annotation=KEYSTONE_ANNOTATION,
        justification="keystone vertical every later migration hangs on",
    )
    followers = (
        ("devops-wave-migration", "Maintainer migrates the DEVOPS wave"),
        ("distill-wave-migration", "Maintainer migrates the DISTILL wave"),
    )
    rows = (
        keystone,
        *(
            FeaturePlanRow(
                feature_id=feature_id,
                value_statement=value,
                status=FeatureStatus.PENDING,
                annotation="",
                justification="follow-on migration",
            )
            for feature_id, value in followers
        ),
    )
    return EpicDeltaPlan(
        epic_id=epic_id,
        job_statement=(
            "When my migration request spans every wave, I want the tool to "
            "decompose it into independently-shippable features, so I don't "
            "hand-cut the umbrella in conversation."
        ),
        rows=rows,
    )


def _row_index(plan: EpicDeltaPlan, feature_id: str) -> int:
    """The index of the row naming ``feature_id`` (the feature being maintained)."""
    for idx, row in enumerate(plan.rows):
        if row.feature_id == feature_id:
            return idx
    raise KeyError(feature_id)


def apply_flip(
    plan: EpicDeltaPlan, feature_id: str, action: MaintenanceAction
) -> FlipResult:
    """Apply a maintenance flip to one row. Pure (plan in -> plan + verdict out).

    LSC-1 (pick-up): ``pending`` -> ``in-flight`` AND add the
    ``docs/feature/{id}/`` link to the Feature cell -- one atomic edit.
    LSC-2 (finalize): ``in-flight`` -> ``shipped``.
    LSC-5 (forward-only): the flip is applied ONLY when the row's current status
    equals the action's source status; a backward or out-of-order flip is rejected
    (``REJECTED_BACKWARD``) and the plan is returned unchanged.
    """
    idx = _row_index(plan, feature_id)
    row = plan.rows[idx]
    source, target = _ACTION_TRANSITION[action]
    if row.status is not source:
        return FlipResult(verdict=MaintenanceVerdict.REJECTED_BACKWARD, plan=plan)
    flipped = replace(
        row,
        status=target,
        has_workspace_link=row.has_workspace_link
        or action is MaintenanceAction.PICK_UP,
    )
    new_rows = plan.rows[:idx] + (flipped,) + plan.rows[idx + 1 :]
    return FlipResult(
        verdict=MaintenanceVerdict.APPLIED,
        plan=replace(plan, rows=new_rows),
    )


def classify_status_token(token: str) -> MaintenanceVerdict:
    """Classify a candidate Status token at the LSC procedure level (LSC-6). Pure.

    The slice-01 validator does NOT validate Status cells (DC-1) -- an illegal
    token like ``done`` validates ``accepted`` through the keystone gate. LSC-6
    makes the maintenance procedure responsible for rejecting an off-set token.
    Returns ``REJECTED_BAD_TOKEN`` for any token outside the R2 closed set,
    ``APPLIED`` (well-formed) otherwise.
    """
    legal = {status.value for status in FeatureStatus}
    if token not in legal:
        return MaintenanceVerdict.REJECTED_BAD_TOKEN
    return MaintenanceVerdict.APPLIED


def seed_row_status(
    plan: EpicDeltaPlan, feature_id: str, status: FeatureStatus
) -> EpicDeltaPlan:
    """Advance one row to ``status`` by applying the legal forward flips. Pure.

    Establishes a STARTING state for a maintenance scenario (e.g. AT-2 needs a row
    already ``in-flight`` before a finalize). Applies pick-up / finalize in order
    until the row reaches ``status`` -- so the seeded row carries exactly the
    side effects those flips produce (LSC-1 adds the workspace link on the pick-up
    leg). ``PENDING`` is the authored default and needs no flip.
    """
    advanced = plan
    for action in (MaintenanceAction.PICK_UP, MaintenanceAction.FINALIZE):
        target_row = next(r for r in advanced.rows if r.feature_id == feature_id)
        if target_row.status is status:
            break
        advanced = apply_flip(advanced, feature_id, action).plan
    return advanced


def epic_delta_path(repo_dir: Path, epic_id: str) -> Path:
    """The production path of an epic's epic-delta (EDC-1)."""
    return repo_dir / "docs" / "epic" / epic_id / "epic-delta.md"


def author_epic_delta(repo_dir: Path, plan: EpicDeltaPlan) -> Path:
    """Author the epic-delta at its production path (EDC-1). Impure.

    Renders the plan (pure) and writes the body to ``docs/epic/{id}/epic-delta.md``
    under ``repo_dir``. Produces ONLY the epic-delta -- no ``docs/feature/{id}/``
    workspaces (LSC-3 fractal JIT: a ``pending`` row has no workspace). Returns the
    written path.
    """
    target = epic_delta_path(repo_dir, plan.epic_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_epic_delta(plan), encoding="utf-8")
    return target


def feature_workspace_path(repo_dir: Path, feature_id: str) -> Path:
    """The ``docs/feature/{id}/`` workspace path for a picked-up feature."""
    return repo_dir / "docs" / "feature" / feature_id
