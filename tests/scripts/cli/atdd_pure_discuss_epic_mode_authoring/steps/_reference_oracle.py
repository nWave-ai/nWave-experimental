"""Reference producer for the discuss-epic-mode slice-02 acceptance slice.

A LABELED, deterministic stand-in for the LLM-mediated ``/nw-discuss --epic <id>``
authoring act. This is TEST-SUPPORT, NOT production code.

Slice-02's deliverable is PROSE: the ``--epic`` authoring procedure is
LLM-mediated skill / command text (DESIGN slice-02/04/05 text contracts: the
slice's "code" is SKILL / COMMAND text, there is NO ``src/des`` surface). The
producer of the epic-delta is the Luna PO agent during a discuss session, never a
``src/des`` function.

These ATs verify the EDC contract (EDC-1..EDC-9) that the LLM-authored prose MUST
satisfy. To witness that contract mechanically without a production producer, this
module renders a deterministic EDC-conformant epic-delta — a GOLDEN-FILE ANALOGUE.
It is the reference the ATs measure the contract against; it makes no claim to be
the production deliverable. Anti-fixture-theater is inapplicable here precisely
because the production deliverable is prose, not a claimed ``src/des`` function.

Phase C resolution (2026-06-11, Ruling B): this emitter was previously mis-placed
as a ``src/des/application`` production module and imported at the composition
boundary — a S2 driving-port violation + a CREATE_NEW ``src/des/**`` module
forbidden by the ratified Reuse Analysis. It is RE-HOMED here, verbatim, as the
suite-local reference producer.

Contract shape (effect isolation): ``render_epic_delta`` is a pure function
(EpicDeltaPlan -> str, no I/O); ``author_epic_delta`` is the only impure call (it
writes the rendered body to the production path). The split keeps the renderer
unable to reach the filesystem.

The rendered body satisfies the EDC contract DESIGN pinned (EDC-1..EDC-9) and
clears slice-01's ``validate_feature_plan_content`` gate (EDC-8): a well-formed
``# Epic Delta`` title, an epic-JTBD section under a D2-conformant heading, and a
Feature Plan under the exact R1 heading carrying the five fixed columns with at
least one value-bearing keystone row.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


#: EDC-3 epic-JTBD section heading (D2 grammar — REF type token).
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

#: EDC-5 keystone annotation token (Slice Plan vocabulary reused — no new token).
KEYSTONE_ANNOTATION = "@walking-skeleton"


@dataclass(frozen=True)
class FeaturePlanRow:
    """One row of the epic's Feature Plan (EDC-4).

    Mirrors the five fixed columns. ``annotation`` carries the keystone token
    (EDC-5) on exactly one row and any backward-only ``depends-on {feature}``
    reference (EDC-6); ``status`` is an R2 token, ``pending`` for an authored row
    (EDC-7).
    """

    feature: str
    value_statement: str
    status: str
    annotation: str
    justification: str

    def to_markdown(self) -> str:
        """Render the row as a GFM table line."""
        return (
            f"| {self.feature} | {self.value_statement} | {self.status} "
            f"| {self.annotation} | {self.justification} |"
        )


@dataclass(frozen=True)
class EpicDeltaPlan:
    """The authored content of an epic-delta (EDC-2/EDC-3/EDC-4 inputs).

    ``epic_id`` is a kebab-case identifier; ``job_statement`` is the epic-JTBD
    When-I-want-so-that line; ``rows`` are the Feature Plan rows in dependency
    order (row order = backward-only dependency order, EDC-6).
    """

    epic_id: str
    job_statement: str
    rows: tuple[FeaturePlanRow, ...]


def render_epic_delta(plan: EpicDeltaPlan) -> str:
    """Render an EDC-conformant epic-delta body from a plan. Pure function.

    No I/O. The rendered body carries the EDC-2 title, the EDC-3 epic-JTBD
    section, and the EDC-4 Feature Plan under the exact R1 heading with the five
    fixed columns — so it clears slice-01's ``validate_feature_plan_content`` gate
    (EDC-8) whenever ``plan.rows`` carries at least one value-bearing row.
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


def epic_delta_path(repo_dir: Path, epic_id: str) -> Path:
    """The production path of an epic's epic-delta (EDC-1)."""
    return repo_dir / "docs" / "epic" / epic_id / "epic-delta.md"


def default_flow_v2_plan() -> EpicDeltaPlan:
    """The reference epic-delta plan for the flow-v2-wave-migrations dogfood epic.

    The deterministic reference the ``--epic flow-v2-wave-migrations`` authoring
    is measured against. Mirrors the §13 follow-on list as Feature Plan rows in
    backward-only dependency order (EDC-6), with the DESIGN-wave migration as the
    single keystone (EDC-5) and authored rows ``pending`` (EDC-7). The Luna PO
    agent authors the real value statements and justifications during the discuss
    session; this reference guarantees the structural shape clears the gate
    (EDC-8).
    """
    keystone = FeaturePlanRow(
        feature="DESIGN-wave migration",
        value_statement="Maintainer migrates the DESIGN wave to declarative composition",
        status="pending",
        annotation=KEYSTONE_ANNOTATION,
        justification="keystone vertical every later migration hangs on",
    )
    followers = (
        ("DEVOPS-wave migration", "Maintainer migrates the DEVOPS wave"),
        ("DISTILL-wave migration", "Maintainer migrates the DISTILL wave"),
        ("DELIVER-wave migration", "Maintainer migrates the DELIVER wave"),
        ("declarative extraction", "Wave->gate composition extracted declaratively"),
        ("manifest", "Manifest + gate-G track produced"),
        ("self-attest", "Self-attest verdict layer wired"),
    )
    rows = (
        keystone,
        *(
            FeaturePlanRow(
                feature=feature,
                value_statement=value,
                status="pending",
                annotation="",
                justification="follow-on migration",
            )
            for feature, value in followers
        ),
    )
    return EpicDeltaPlan(
        epic_id="flow-v2-wave-migrations",
        job_statement=(
            "When my flow-v2 migration request spans every wave, I want the tool "
            "to decompose it into independently-shippable features, so I don't "
            "hand-cut the umbrella in conversation."
        ),
        rows=rows,
    )


def author_epic_delta(repo_dir: Path, plan: EpicDeltaPlan) -> Path:
    """Author the reference epic-delta at its production path (EDC-1). Impure.

    The only side-effecting call: renders the plan (pure) and writes the body to
    ``docs/epic/{id}/epic-delta.md`` under ``repo_dir``, creating the epic
    directory if needed. Produces ONLY the epic-delta — no ``docs/feature/{id}/``
    workspaces (EDC-9 fractal JIT). Returns the written path.
    """
    target = epic_delta_path(repo_dir, plan.epic_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_epic_delta(plan), encoding="utf-8")
    return target
