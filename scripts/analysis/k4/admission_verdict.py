#!/usr/bin/env python3
"""The K4 admission verdict, COMPUTED from archived evidence instead of typed.

Why this file exists, stated as the defect rather than as a principle. Until it
existed, no code in this repository computed the nWave/control ratio on any
axis, compared one against a bound, or even carried the bounds as constants:
`paired_spread.py` measures DISPERSION INSIDE one set of identical runs, which
is the noise floor a comparison must beat, never the comparison itself. So every
admission verdict -- including camp6's, the one that cost $43.32 and 1h51m --
was arithmetic performed by hand and transcribed into prose. A transcription
error in that chain is invisible: nothing recomputes it, and the prose reads
exactly the same whether the number is right or wrong.

This module is the recomputation. It reads a campaign archive
(`campaign_archive.py`), reuses the existing scorers rather than reimplementing
them -- `paired_spread.classify` for the per-run payload, `paired_spread.
resolve_transcript_wall` for the path-aware wall, `paired_quality_join.join` for
the run/verdict binding, `blind_review.validate_verdict_shape` +
`quality_rubric.CRITERIA_KEYS` for the rubric -- and emits ONE verdict.

Two traps are handled in the type rather than in a footnote, because both were
seen to change the SIGN of camp6's verdict:

(a) A pair whose nWave arm produced no delivery yields no ratio at all. Summed
    together with the delivering pair -- which is what the hand computation does
    -- camp6's wall reads `1.2400x`, inside the `1.5x` bound, a PASS. Restricted
    to the pairs where both arms actually delivered it reads `2.8100x`, a breach.
    `Delivery` therefore separates NOT-DELIVERED from DELIVERED-BADLY, and the
    two are never summed: a rejected delivery did the work and its cost counts,
    an absent one cannot be counted at all.

(b) One valid pair is an anecdote. `Status.INDETERMINATE` and
    `Verdict.INDETERMINATE` are first-class outcomes that reach the aggregate
    AND the process exit code (2), so "PASS*" with a footnote stops being
    representable. The asymmetry is deliberate and stated: an insufficient
    sample cannot MANUFACTURE an admission, and it cannot ERASE an observed
    breach either -- admission is the claim being established, so it needs the
    evidence and its refutation does not.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from scripts.analysis import blind_review, paired_spread
from scripts.analysis.k4 import quality_rubric


# --- the bounds, which were nowhere in code before this line ----------------

#: ADR-SSOT-002 §1: monetary cost, processed tokens, and wall-clock are each
#: <=1.5x the comparable vibe control. No ratio compensates for another. The
#: 2026-08-20 commit (`991609f79`) is historical lineage only. The rule is
#: conjunctive and never a weighted score.
COST_BOUND = 1.5
TOKEN_BOUND = 1.5
WALL_BOUND = 1.5
BOUNDS = {"cost": COST_BOUND, "tokens": TOKEN_BOUND, "wall": WALL_BOUND}

#: Priority order: quality TOP, then the three equally bounded 1.5x resource
#: axes (cost, tokens, wall-clock). It orders REMEDIATION EFFORT, not arithmetic
#: -- a conjunctive rule cannot be weighted, and weighting it would be the
#: compensation the decision forbids. Position inside this tuple is therefore
#: cosmetic; MEMBERSHIP is not, because `decide` iterates THIS tuple and an axis
#: missing from it is computed and never read.
#:
#: `cost` was absent here until 2026-08-23 while `COST_BOUND` had defined it
#: since the bounds landed -- a bound with no reader. Measured on
#: `preflight-20260823-rex` pair-1: cost 2.14x against tokens 1.32x, because
#: the arms used different model mixes and different cache shares (63% more
#: cost per million tokens). So the omission was hiding a REAL 1.5x breach
#: behind a within-bound token ratio, not a hypothetical one.
#: `test_every_bound_has_a_priority_entry` is the structural guard that keeps
#: this set and `BOUNDS` in step.
PRIORITY = ("quality", "cost", "tokens", "wall")

#: Reused, not re-invented: `paired_spread.MIN_USABLE` is this repository's
#: existing "below this a spread is not a spread" rule. A campaign with fewer
#: valid PAIRS than that is under the same rule -- one point is an anecdote.
MIN_VALID_PAIRS = paired_spread.MIN_USABLE


class Status(str, Enum):
    WITHIN = "WITHIN"
    BREACH = "BREACH"
    INDETERMINATE = "INDETERMINATE"


class Verdict(str, Enum):
    ADMIT = "ADMIT"
    NOT_ADMITTED = "NOT_ADMITTED"
    INDETERMINATE = "INDETERMINATE"


class Delivery(str, Enum):
    """Five outcomes, and NOT-DELIVERED is not one of the delivered ones.

    camp6 is the anchor: two pairs of three saw the nWave arm produce no
    delivery at all. A ratio computed on such a pair is not a favourable ratio,
    it is a division by an absence -- p1 cost 0.44x measures an abort.
    """

    NOT_RUN = "NOT_RUN"
    NO_DELIVERY = "NO_DELIVERY"
    DELIVERED_REJECTED = "DELIVERED_REJECTED"
    DELIVERED_ACCEPTED = "DELIVERED_ACCEPTED"
    UNSCORED = "UNSCORED"


#: The two states in which an arm's delivery outcome was never ESTABLISHED at
#: all: the run produced no usable payload, or nothing scored the payload it
#: produced. `NO_DELIVERY` is deliberately not here -- an arm that ran and
#: delivered nothing WAS evaluated, and its gate failure is a finding.
UNEVALUATED = frozenset({Delivery.NOT_RUN, Delivery.UNSCORED})

_NWAVE_ALIASES = frozenset({"nwave", "treatment", "b"})
_CONTROL_ALIASES = frozenset({"control", "vibe", "a"})

# K4's Maintenance Windows subject has every Section 1a item required or
# applicable. The sealed rubric has no persisted applicability projection, so
# this is deliberately local to this subject rather than pretending it is a
# general rule for every future campaign.
_K4_MAINTENANCE_REQUIRED_ITEMS = frozenset(quality_rubric.SECTION_1A_ITEMS)
_K4_MAINTENANCE_REQUIRED_CRITERIA = frozenset(
    key
    for key, criterion in quality_rubric.CRITERIA_BY_KEY.items()
    if _K4_MAINTENANCE_REQUIRED_ITEMS.intersection(criterion.section_1a)
)


class ArmResolutionError(RuntimeError):
    """Which stem is the nWave arm is never guessed: swapping the two inverts
    every ratio in the report and the report still looks well-formed."""


@dataclass(frozen=True)
class ArmRun:
    pair: int
    stem: str
    role: str
    session_id: str | None
    delivery: Delivery
    delivery_reason: str
    cost: float | None
    tokens: int | None
    token_scope: str | None
    wall_s: float | None
    wall_source: str | None
    rubric_scores: tuple[tuple[str, int, str], ...] | None
    blocking: tuple[str, ...]


@dataclass(frozen=True)
class PairRecord:
    index: int
    nwave: ArmRun
    control: ArmRun

    @property
    def both_accepted(self) -> bool:
        return (
            self.nwave.delivery is Delivery.DELIVERED_ACCEPTED
            and self.control.delivery is Delivery.DELIVERED_ACCEPTED
        )


@dataclass(frozen=True)
class PairRatio:
    pair: int
    ratio: float | None
    reason: str | None
    source: str | None


@dataclass(frozen=True)
class RatioAxis:
    axis: str
    bound: float
    per_pair: tuple[PairRatio, ...]
    counted: tuple[int, ...]
    excluded: tuple[tuple[int, str], ...]
    ratio: float | None
    status: Status
    notes: tuple[str, ...]


@dataclass(frozen=True)
class QualityCriterionPair:
    pair: int
    criterion: str
    dimension: str
    nwave_score: int | None
    control_score: int | None
    delta: int | None
    status: Status
    nwave_evidence: str | None
    control_evidence: str | None


@dataclass(frozen=True)
class QualityAxis:
    """Quality is NOT a ratio and has no threshold. See `quality_axis` below."""

    form: str
    gate: Status
    gate_detail: tuple[tuple[int, str], ...]
    criteria: tuple[QualityCriterionPair, ...]
    ordering: Status
    blocking: Status
    reported: tuple[tuple[int, str, str], ...]
    status: Status


@dataclass(frozen=True)
class Admission:
    verdict: Verdict
    pairs: tuple[PairRecord, ...]
    axes: dict[str, RatioAxis]
    quality: QualityAxis
    valid_pairs: int
    reasons: tuple[str, ...]


# --- reading the archive -----------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ArmSelection:
    """Which payload stem is which arm, and where wall-clock is read from.

    Keyword-only, deliberately: `nwave_arm` and `control_arm` carry the same
    type, so a positional pair constructs cleanly with the two swapped, and a
    swap inverts every ratio in the report while leaving the report perfectly
    well-formed. `ArmResolutionError` refuses the UNRESOLVABLE case, an ambiguous
    alias it cannot map; an explicitly inverted pair is accepted without
    complaint, which is exactly why the keyword-only form is worth having here.
    """

    nwave_arm: str | None = None
    control_arm: str | None = None
    wall_source: str = "auto"


#: The selection that names nothing: both roles are resolved from the payload
#: stems, and the wall measurement is whatever `auto` resolves to. Bound here
#: rather than constructed in the signature, so the default every caller gets
#: is one named value.
DEFAULT_ARM_SELECTION = ArmSelection()


@dataclass(frozen=True, kw_only=True)
class ArmReadInputs:
    """What one arm read consults, identical for every arm in a campaign.

    `read_campaign` builds exactly one of these, so the loop below varies only
    WHICH arm is read. It carries the caller's `ArmSelection` rather than a copy
    of `wall_source`, so that value exists in exactly one place and the two
    records cannot disagree about it. Keyword-only because `verdicts` and `rubric` carry the
    same type: transposed positionally they construct without error, and the
    result is every delivery UNSCORED and every rubric score absent. That run
    still ENDS loudly, at `_nothing_was_ever_evaluated`, so the transposition
    costs a confusing INDETERMINATE rather than a plausible-looking report.

    The guard reaches this record only. `read_campaign` still takes the same two
    dicts as adjacent positional parameters, and every one of its callers passes
    them positionally, nine of them by unpacking a tuple where the order is not
    visible at the call site. Closing that seam is a separate change.
    """

    verdicts: dict[str, dict]
    rubric: dict[str, dict]
    selection: ArmSelection


def resolve_roles(
    stems: set[str], *, nwave: str | None = None, control: str | None = None
) -> dict[str, str]:
    """Map payload stem -> role, refusing rather than guessing."""
    if nwave and control:
        return {nwave: "nwave", control: "control"}
    found_n = sorted(s for s in stems if s.lower() in _NWAVE_ALIASES)
    found_c = sorted(s for s in stems if s.lower() in _CONTROL_ALIASES)
    if len(found_n) != 1 or len(found_c) != 1:
        raise ArmResolutionError(
            "WHAT: cannot tell which arm is nWave and which is the control.\n"
            f"WHY:  payload stems {sorted(stems)} matched nWave {found_n} and "
            "control {found_c}; swapping the two inverts every ratio in this\n"
            "      report while leaving the report perfectly well-formed.\n"
            "HOW:  pass --nwave-arm and --control-arm explicitly.\n".replace(
                "{found_c}", str(found_c)
            )
        )
    return {found_n[0]: "nwave", found_c[0]: "control"}


def _payload_paths(campaign: Path) -> dict[int, dict[str, Path]]:
    out: dict[int, dict[str, Path]] = {}
    for path in sorted(campaign.glob("pair-*/*.json")):
        if path.stem.endswith(".setup") or "." in path.stem:
            continue
        try:
            index = int(path.parent.name.split("-", 1)[1])
        except (IndexError, ValueError):
            continue
        out.setdefault(index, {})[path.stem] = path
    return out


def _resolve_delivery(usable: bool, verdict: dict | None) -> tuple[Delivery, str]:
    if not usable:
        return Delivery.NOT_RUN, "no usable run payload"
    if verdict is None:
        return Delivery.UNSCORED, "no verdict record carries this session"
    if "delivered" not in verdict:
        return (
            Delivery.UNSCORED,
            "verdict has no `delivered` field; delivery is never inferred "
            "from the presence of an `accepted` field",
        )
    if not verdict["delivered"]:
        return Delivery.NO_DELIVERY, str(verdict.get("evidence", "<none stated>"))
    if "accepted" not in verdict:
        return Delivery.UNSCORED, "delivered, but no `accepted` field"
    if verdict["accepted"]:
        return Delivery.DELIVERED_ACCEPTED, str(
            verdict.get("evidence", "<none stated>")
        )
    return Delivery.DELIVERED_REJECTED, str(verdict.get("evidence", "<none stated>"))


def read_campaign(
    campaign: Path,
    verdicts: dict[str, dict],
    rubric: dict[str, dict],
    *,
    selection: ArmSelection = DEFAULT_ARM_SELECTION,
) -> tuple[PairRecord, ...]:
    """Every pair, every arm, one `ArmRun` each -- none dropped in silence."""
    paths = _payload_paths(campaign)
    stems = {stem for row in paths.values() for stem in row}
    roles = resolve_roles(
        stems, nwave=selection.nwave_arm, control=selection.control_arm
    )
    inputs = ArmReadInputs(verdicts=verdicts, rubric=rubric, selection=selection)

    records: list[PairRecord] = []
    for index in sorted(paths):
        arms: dict[str, ArmRun] = {}
        for stem, path in sorted(paths[index].items()):
            role = roles.get(stem)
            if role is None:
                continue
            arms[role] = _read_arm(index, stem, role, path, inputs)
        if "nwave" in arms and "control" in arms:
            records.append(PairRecord(index, arms["nwave"], arms["control"]))
    return tuple(records)


def _read_arm(
    index: int,
    stem: str,
    role: str,
    path: Path,
    inputs: ArmReadInputs,
) -> ArmRun:
    outcome = paired_spread.classify(
        f"pair-{index}/{stem}", path.read_text(errors="replace")
    )
    if not isinstance(outcome, paired_spread.Usable):
        reason = getattr(outcome, "reason", None) or getattr(outcome, "error", "")
        delivery, why = _resolve_delivery(False, None)
        return ArmRun(
            index,
            stem,
            role,
            None,
            delivery,
            f"{why}: {reason}",
            None,
            None,
            None,
            None,
            None,
            None,
            (),
        )

    wall_s: float | None = outcome.wall_s
    source = paired_spread.ROOT_PAYLOAD_ONLY
    if inputs.selection.wall_source in ("auto", "transcript"):
        resolved = paired_spread.resolve_transcript_wall(
            outcome.name, outcome.session_id, path
        )
        if isinstance(resolved, paired_spread.TranscriptWall):
            wall_s, source = resolved.wall_s, resolved.scope
        elif inputs.selection.wall_source == "transcript":
            wall_s, source = None, None

    verdict = inputs.verdicts.get(outcome.session_id)
    delivery, why = _resolve_delivery(True, verdict)
    scored = inputs.rubric.get(outcome.session_id)
    blocking = tuple(scored.get("blocking_quality_findings", ())) if scored else ()
    criteria = scored.get("criteria") if isinstance(scored, dict) else None
    scores: tuple[tuple[str, int, str], ...] | None = None
    if isinstance(criteria, dict) and set(criteria) == quality_rubric.CRITERIA_KEYS:
        rows: list[tuple[str, int, str]] = []
        for key in sorted(quality_rubric.CRITERIA_KEYS, key=int):
            entry = criteria[key]
            if (
                not isinstance(entry, dict)
                or type(entry.get("score")) is not int
                or not 0 <= entry["score"] <= 2
            ):
                break
            evidence = entry.get("evidence")
            if not isinstance(evidence, str) or not evidence.strip():
                break
            rows.append((key, entry["score"], evidence))
        else:
            scores = tuple(rows)

    return ArmRun(
        index,
        stem,
        role,
        outcome.session_id,
        delivery,
        why,
        outcome.cost,
        sum(outcome.tokens.values()),
        outcome.token_scope,
        wall_s,
        source,
        scores,
        blocking,
    )


# --- the axes ----------------------------------------------------------------


def _axis_values(run: ArmRun, axis: str) -> tuple[float | None, str | None]:
    if axis == "cost":
        return run.cost, None
    if axis == "tokens":
        if run.token_scope != paired_spread.AGGREGATE_MODEL_USAGE:
            return None, (
                f"token scope is {run.token_scope}, not nested-inclusive; the "
                "top-level-only scope is what let a 1.2881x ratio PASS while "
                "the true ratio was 1.6921x"
            )
        return (float(run.tokens) if run.tokens is not None else None), None
    if axis == "wall":
        return run.wall_s, (None if run.wall_s is not None else "no wall measurement")
    raise KeyError(axis)


def ratio_axis(axis: str, pairs: tuple[PairRecord, ...]) -> RatioAxis:
    """One ratio per axis, over the pairs where a ratio EXISTS.

    A pair enters the denominator only when both arms delivered. That is trap
    (a) in one line, and it is worth 1.24x versus 2.81x on camp6's wall.
    """
    bound = BOUNDS[axis]
    per_pair: list[PairRatio] = []
    counted: list[int] = []
    excluded: list[tuple[int, str]] = []
    n_sum = 0.0
    c_sum = 0.0
    notes: list[str] = []

    for pair in pairs:
        if not pair.both_accepted:
            why = (
                f"nWave {pair.nwave.delivery.value} / control "
                f"{pair.control.delivery.value} -- both outcomes must be accepted; "
                "favourable ratio, it is a division by an absence"
            )
            per_pair.append(PairRatio(pair.index, None, why, None))
            excluded.append((pair.index, why))
            continue
        n_val, n_why = _axis_values(pair.nwave, axis)
        c_val, c_why = _axis_values(pair.control, axis)
        if n_val is None or c_val is None:
            why = n_why or c_why or "missing measurement"
            per_pair.append(PairRatio(pair.index, None, why, None))
            excluded.append((pair.index, why))
            continue
        if c_val <= 0:
            why = f"control {axis} is {c_val}; the ratio is undefined, not large"
            per_pair.append(PairRatio(pair.index, None, why, None))
            excluded.append((pair.index, why))
            continue
        if axis == "wall" and pair.nwave.wall_source != pair.control.wall_source:
            why = (
                f"wall sources differ ({pair.nwave.wall_source} vs "
                f"{pair.control.wall_source}); those are two different quantities"
            )
            per_pair.append(PairRatio(pair.index, None, why, None))
            excluded.append((pair.index, why))
            continue
        source = pair.nwave.wall_source if axis == "wall" else None
        per_pair.append(PairRatio(pair.index, n_val / c_val, None, source))
        counted.append(pair.index)
        n_sum += n_val
        c_sum += c_val

    if not counted:
        return RatioAxis(
            axis,
            bound,
            tuple(per_pair),
            (),
            tuple(excluded),
            None,
            Status.INDETERMINATE,
            ("no pair carries a computable ratio",),
        )
    ratio = n_sum / c_sum
    if ratio > bound:
        # A breach observed on the only evidence there is refutes the claim.
        # Sample insufficiency is a reason not to GRANT admission, never a
        # reason to unsee a measured overrun.
        status = Status.BREACH
    elif len(counted) < MIN_VALID_PAIRS:
        status = Status.INDETERMINATE
        notes.append(
            f"{len(counted)} valid pair(s), need >= {MIN_VALID_PAIRS}: "
            f"{ratio:.4f}x is inside the {bound}x bound but one point is an "
            "anecdote, not a measure"
        )
    else:
        status = Status.WITHIN
    return RatioAxis(
        axis,
        bound,
        tuple(per_pair),
        tuple(counted),
        tuple(excluded),
        ratio,
        status,
        tuple(notes),
    )


def quality_axis(pairs: tuple[PairRecord, ...]) -> QualityAxis:
    """Conjoin paired criterion observations; rubric totals are never read."""
    gate_detail: list[tuple[int, str]] = []
    criteria_rows: list[QualityCriterionPair] = []
    reported: list[tuple[int, str, str]] = []
    comparison_states: list[Status] = []
    blocking_basis: list[PairRecord] = []

    for pair in pairs:
        if pair.nwave.delivery is not Delivery.DELIVERED_ACCEPTED:
            gate_detail.append((pair.index, pair.nwave.delivery.value))
        if pair.control.delivery is not Delivery.DELIVERED_ACCEPTED:
            gate_detail.append((pair.index, f"control {pair.control.delivery.value}"))
        if pair.nwave.rubric_scores is None or pair.control.rubric_scores is None:
            for key in sorted(quality_rubric.CRITERIA_KEYS, key=int):
                criterion = quality_rubric.CRITERIA_BY_KEY[key]
                criteria_rows.append(
                    QualityCriterionPair(
                        pair.index,
                        key,
                        criterion.dimension,
                        None,
                        None,
                        None,
                        Status.INDETERMINATE,
                        None,
                        None,
                    )
                )
                comparison_states.append(Status.INDETERMINATE)
        else:
            n_scores = {
                key: (score, evidence)
                for key, score, evidence in pair.nwave.rubric_scores
            }
            c_scores = {
                key: (score, evidence)
                for key, score, evidence in pair.control.rubric_scores
            }
            for key in sorted(quality_rubric.CRITERIA_KEYS, key=int):
                criterion = quality_rubric.CRITERIA_BY_KEY[key]
                n_score, n_evidence = n_scores[key]
                c_score, c_evidence = c_scores[key]
                if n_score < c_score or (
                    key in _K4_MAINTENANCE_REQUIRED_CRITERIA and n_score == 0
                ):
                    state = Status.BREACH
                else:
                    state = Status.WITHIN
                criteria_rows.append(
                    QualityCriterionPair(
                        pair.index,
                        key,
                        criterion.dimension,
                        n_score,
                        c_score,
                        n_score - c_score,
                        state,
                        n_evidence,
                        c_evidence,
                    )
                )
                comparison_states.append(state)
        blocking_basis.append(pair)
        for text in pair.nwave.blocking:
            reported.append((pair.index, "nwave", text))
        for text in pair.control.blocking:
            reported.append((pair.index, "control", text))

    gate = Status.BREACH if gate_detail else Status.WITHIN
    if not comparison_states:
        ordering = Status.INDETERMINATE
    elif Status.BREACH in comparison_states:
        ordering = Status.BREACH
    elif Status.INDETERMINATE in comparison_states:
        ordering = Status.INDETERMINATE
    else:
        ordering = Status.WITHIN
    blocking = (
        Status.BREACH
        if any(pair.nwave.blocking for pair in blocking_basis)
        else Status.WITHIN
    )
    status = (
        Status.BREACH
        if Status.BREACH in (gate, ordering, blocking)
        else (
            Status.INDETERMINATE
            if Status.INDETERMINATE in (gate, ordering, blocking)
            else Status.WITHIN
        )
    )
    return QualityAxis(
        "GATE (accepted) + per-criterion paired non-inferiority + REPORTED "
        "JUDGMENT (blocking findings, quoted never scored) -- never a total",
        gate,
        tuple(gate_detail),
        tuple(criteria_rows),
        ordering,
        blocking,
        tuple(reported),
        status,
    )


def _nothing_was_ever_evaluated(pairs: tuple[PairRecord, ...]) -> bool:
    """True when no arm of this campaign carries an ESTABLISHED delivery
    outcome -- every one is NOT_RUN or UNSCORED.

    camp7 is the anchor: one pair, both arms ran and produced payloads, and
    neither acceptance record carried a `delivered` field, so both resolved
    UNSCORED. The quality gate then read BREACH for the single reason that
    nothing had scored them, and the campaign came out NOT_ADMITTED -- a flat
    refusal of the nWave arm off a campaign in which no comparison was ever
    computed. An absence of evaluation is the third state, never the negative
    one.

    Deliberately NOT generalised past this: it is checked only where zero pairs
    are valid, and only when EVERY arm is unevaluated. camp6 (one valid pair,
    wall 2.81x) must keep refusing, and so must a campaign whose arms ran and
    delivered nothing -- insufficient sample never erases an observed breach.
    """
    return bool(pairs) and all(
        run.delivery in UNEVALUATED
        for pair in pairs
        for run in (pair.nwave, pair.control)
    )


def decide(pairs: tuple[PairRecord, ...]) -> Admission:
    """Conjunctive and three-valued. No axis compensates for another (`991609f79`),
    so there is nothing to weight and the priority order only sorts the reasons."""
    axes = {axis: ratio_axis(axis, pairs) for axis in BOUNDS}
    quality = quality_axis(pairs)
    valid = sum(1 for p in pairs if p.both_accepted)
    unevaluated = valid == 0 and _nothing_was_ever_evaluated(pairs)

    breaches: list[str] = []
    unknowns: list[str] = []
    for name in PRIORITY:
        axis_status = quality.status if name == "quality" else axes[name].status
        detail = (
            f"gate={quality.gate.value} ordering={quality.ordering.value} "
            f"blocking={quality.blocking.value}"
            if name == "quality"
            else "; ".join(
                (
                    *(
                        ()
                        if axes[name].ratio is None
                        else (
                            f"{axes[name].ratio:.4f}x vs {axes[name].bound}x on "
                            f"pair(s) {list(axes[name].counted)}",
                        )
                    ),
                    *axes[name].notes,
                )
            )
            or "no computable ratio"
        )
        if axis_status is Status.BREACH and not unevaluated:
            breaches.append(f"{name}: BREACH ({detail})")
        elif axis_status is Status.BREACH:
            unknowns.append(
                f"{name}: INDETERMINATE ({detail}) -- not a breach: no arm of "
                "this campaign carries an established delivery outcome, so "
                "this axis was never evaluated"
            )
        elif axis_status is Status.INDETERMINATE:
            unknowns.append(f"{name}: INDETERMINATE ({detail})")

    if breaches:
        return Admission(
            Verdict.NOT_ADMITTED, pairs, axes, quality, valid, tuple(breaches)
        )
    if valid < MIN_VALID_PAIRS:
        unknowns.insert(
            0,
            f"sample: {valid} pair(s) where both arms delivered, need >= "
            f"{MIN_VALID_PAIRS}; an admission cannot be granted off an anecdote",
        )
    if unknowns:
        return Admission(
            Verdict.INDETERMINATE, pairs, axes, quality, valid, tuple(unknowns)
        )
    return Admission(Verdict.ADMIT, pairs, axes, quality, valid, ())


# --- imperative shell --------------------------------------------------------


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def render(result: Admission) -> str:
    lines: list[str] = []
    lines.append(f"pairs                : {len(result.pairs)}")
    lines.append(f"valid (both delivered): {result.valid_pairs}")
    lines.append("")
    lines.append(f"{'pair':>5}  {'nWave':<20} {'control':<20}")
    for pair in result.pairs:
        lines.append(
            f"{pair.index:>5}  {pair.nwave.delivery.value:<20} "
            f"{pair.control.delivery.value:<20}"
        )
    lines.append("")
    lines.append(f"{'axis':<8}{'bound':>7}{'ratio':>10}  {'status':<14} counted")
    for name in ("cost", "tokens", "wall"):
        axis = result.axes[name]
        shown = "n/a" if axis.ratio is None else f"{axis.ratio:.4f}x"
        lines.append(
            f"{name:<8}{axis.bound:>6.1f}x{shown:>10}  {axis.status.value:<14}"
            f"{list(axis.counted)}"
        )
        for item in axis.per_pair:
            if item.ratio is None:
                lines.append(f"    pair {item.pair}: EXCLUDED - {item.reason}")
    lines.append("")
    lines.append(f"quality form         : {result.quality.form}")
    lines.append(f"quality gate         : {result.quality.gate.value}")
    for index, state in result.quality.gate_detail:
        lines.append(f"    pair {index}: nWave arm {state}")
    lines.append(f"quality criteria     : {result.quality.ordering.value}")
    for row in result.quality.criteria:
        delta = "n/a" if row.delta is None else f"{row.delta:+d}"
        lines.append(
            f"    pair {row.pair} criterion {row.criterion} ({row.dimension}): "
            f"nWave {row.nwave_score} vs control {row.control_score}, "
            f"delta {delta}, {row.status.value}; evidence: "
            f"nWave={row.nwave_evidence!r}, control={row.control_evidence!r}"
        )
    lines.append(
        f"quality blocking     : {result.quality.blocking.value}"
        "   (every finding below is QUOTED, "
        "never scored)"
    )
    for index, arm, text in result.quality.reported:
        lines.append(f"    pair {index} {arm}: {text}")
    lines.append("")
    lines.append(f"VERDICT: {result.verdict.value}")
    for reason in result.reasons:
        lines.append(f"    {reason}")
    return "\n".join(lines)


_EXIT = {Verdict.ADMIT: 0, Verdict.NOT_ADMITTED: 1, Verdict.INDETERMINATE: 2}


#: The one word that identifies the treatment among an arm's setup steps. The
#: install console script is `nwave-ai` whatever venv it was installed into, so
#: the check below reads the NAME and never an absolute path a campaign root
#: renders differently on every machine.
_TREATMENT_INSTALLER = "nwave-ai"


def _arms_are_a_pair(campaign: Path, nwave_arm: str | None, control_arm: str | None):
    """(the arms are a valid pair, why not) read from a finished campaign.

    WHAT CHANGED AND WHY. This gate used to require the treatment's timed argv
    to be an exact `des dispatch` vector. ADR-SSOT-002 Section 4b retires that
    command as an orchestrator: what ships is an LLM that invokes the steps one
    at a time, so a harness pinned to the composer would admit only campaigns
    measuring a thing nobody runs.

    The property that actually makes a K4 verdict meaningful is SYMMETRY, and it
    is checked here directly rather than inferred from a vector:

    1. both arms declare the SAME timed invocation, so the pair differs in the
       treatment and not in how the two were launched. Anything else makes the
       comparison uninterpretable no matter what the numbers say;
    2. the treatment arm declares the nWave install among its setup steps, and
       the control arm does not. Without this the campaign is vanilla against
       vanilla, reported as nWave against vanilla -- the exact silent-wrong
       `probe_engagement` refuses before a campaign starts, checked again here
       against what the campaign actually recorded.

    Both are read off `campaign.json`, which is what the run wrote, never what a
    preflight intended. Nothing here imports the preflight, so this gate still
    reads a finished campaign directory on its own.
    """
    try:
        document = json.loads((campaign / "campaign.json").read_text(encoding="utf-8"))
        arms = document["arms"]
        treatment = arms[nwave_arm or "nwave"]
        control = arms[control_arm or "control"]
        treatment_argv = list(treatment["argv"])
        control_argv = list(control["argv"])
        treatment_setup = [list(step) for step in treatment.get("setup", ())]
        control_setup = [list(step) for step in control.get("setup", ())]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return False, f"campaign.json does not declare two readable arms ({exc})"

    if treatment_argv != control_argv:
        return False, (
            "the two arms declare DIFFERENT timed invocations, so the pair "
            f"measures the launcher and not the treatment: treatment "
            f"{treatment_argv}, control {control_argv}"
        )

    def installs_nwave(setup):
        return any(Path(step[0]).name == _TREATMENT_INSTALLER for step in setup if step)

    if not installs_nwave(treatment_setup):
        return False, (
            f"the treatment arm's setup never runs `{_TREATMENT_INSTALLER}`, so "
            "nWave was never installed and this campaign is vanilla against "
            "vanilla"
        )
    if installs_nwave(control_setup):
        return False, (
            f"the CONTROL arm's setup runs `{_TREATMENT_INSTALLER}`, so both "
            "arms carry the treatment and the comparison has no control"
        )
    return True, ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--verdicts", required=True, type=Path)
    parser.add_argument("--rubric", type=Path)
    parser.add_argument("--nwave-arm")
    parser.add_argument("--control-arm")
    parser.add_argument(
        "--wall-source", choices=("auto", "transcript", "payload"), default="auto"
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    paired, why_not = _arms_are_a_pair(args.campaign, args.nwave_arm, args.control_arm)
    if not paired:
        message = why_not
        if args.json:
            print(
                json.dumps(
                    {"verdict": Verdict.INDETERMINATE.value, "reasons": [message]}
                )
            )
        else:
            print(f"VERDICT: {Verdict.INDETERMINATE.value}\n    {message}")
        return 2

    verdicts = _load_json(args.verdicts)
    rubric = _load_json(args.rubric) if args.rubric else {}
    if rubric:
        problems = blind_review.validate_verdict_shape(rubric)
        if problems:
            sys.stderr.write(
                "WHAT: the rubric file contains malformed verdicts.\n"
                + "".join(f"      - {p}\n" for p in problems)
                + "WHY:  a total the reviewer cannot add up is not a quality\n"
                "      judgement this instrument may carry.\n"
                "HOW:  fix the verdict JSON, then rerun.\n"
            )
            return 2

    try:
        pairs = read_campaign(
            args.campaign,
            verdicts,
            rubric,
            selection=ArmSelection(
                nwave_arm=args.nwave_arm,
                control_arm=args.control_arm,
                wall_source=args.wall_source,
            ),
        )
    except ArmResolutionError as exc:
        sys.stderr.write(str(exc))
        return 2

    result = decide(pairs)
    if args.json:
        print(json.dumps(_as_dict(result), indent=1))
    else:
        print(render(result))
    return _EXIT[result.verdict]


def _as_dict(result: Admission) -> dict:
    return {
        "verdict": result.verdict.value,
        "pairs": len(result.pairs),
        "valid_pairs": result.valid_pairs,
        "reasons": list(result.reasons),
        # Each arm's delivery outcome, as DATA. It was already stated inside
        # every excluded pair's prose reason, so a reader who needed it had to
        # decode a sentence -- and a consumer that decodes a sentence breaks
        # when the sentence is reworded. Named here once, from the same `pairs`
        # the axes were computed from, so a caller can decide on the outcome
        # (`UNEVALUATED` means the chain produced no evidence; anything else
        # means it produced a finding) instead of on wording.
        "deliveries": [
            {
                "pair": pair.index,
                "nwave": pair.nwave.delivery.value,
                "control": pair.control.delivery.value,
            }
            for pair in result.pairs
        ],
        "axes": {
            name: {
                "bound": axis.bound,
                "ratio": axis.ratio,
                "status": axis.status.value,
                "counted_pairs": list(axis.counted),
                "excluded_pairs": [{"pair": i, "reason": r} for i, r in axis.excluded],
                "per_pair": [
                    {"pair": p.pair, "ratio": p.ratio, "reason": p.reason}
                    for p in axis.per_pair
                ],
            }
            for name, axis in result.axes.items()
        },
        "quality": {
            "form": result.quality.form,
            "gate": result.quality.gate.value,
            "ordering": result.quality.ordering.value,
            "blocking": result.quality.blocking.value,
            "status": result.quality.status.value,
            "per_criterion": [
                {
                    "pair": r.pair,
                    "criterion": r.criterion,
                    "dimension": r.dimension,
                    "nwave_score": r.nwave_score,
                    "control_score": r.control_score,
                    "delta": r.delta,
                    "status": r.status.value,
                    "nwave_evidence": r.nwave_evidence,
                    "control_evidence": r.control_evidence,
                }
                for r in result.quality.criteria
            ],
            "reported_findings": [
                {"pair": i, "arm": a, "finding": t}
                for i, a, t in result.quality.reported
            ],
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
