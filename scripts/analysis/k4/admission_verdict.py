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
    -- camp6's wall reads `1.2400x`, inside the `2.0x` bound, a PASS. Restricted
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

#: Ale, 2026-08-20 (`991609f79`): "monetary cost and processed tokens each at
#: <=1.5x and wall-clock at <=2.0x the comparable vibe control. No ratio
#: compensates for another." The last sentence is why the campaign verdict below
#: is conjunctive and never a weighted score.
COST_BOUND = 1.5
TOKEN_BOUND = 1.5
WALL_BOUND = 2.0
BOUNDS = {"cost": COST_BOUND, "tokens": TOKEN_BOUND, "wall": WALL_BOUND}

#: Priority order from the same decision: quality TOP, the two 1.5x resource
#: axes MID, speed LOW. It orders REMEDIATION EFFORT, not arithmetic -- a
#: conjunctive rule cannot be weighted, and weighting it would be the
#: compensation the decision forbids. Position inside this tuple is therefore
#: cosmetic; MEMBERSHIP is not, because `decide` iterates THIS tuple and an
#: axis missing from it is computed and never read.
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


DELIVERED = frozenset({Delivery.DELIVERED_REJECTED, Delivery.DELIVERED_ACCEPTED})

#: The two states in which an arm's delivery outcome was never ESTABLISHED at
#: all: the run produced no usable payload, or nothing scored the payload it
#: produced. `NO_DELIVERY` is deliberately not here -- an arm that ran and
#: delivered nothing WAS evaluated, and its gate failure is a finding.
UNEVALUATED = frozenset({Delivery.NOT_RUN, Delivery.UNSCORED})

RUBRIC_MAX = 2 * len(quality_rubric.CRITERIA_KEYS)

_NWAVE_ALIASES = frozenset({"nwave", "treatment", "b"})
_CONTROL_ALIASES = frozenset({"control", "vibe", "a"})


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
    rubric_total: int | None
    blocking: tuple[str, ...]


@dataclass(frozen=True)
class PairRecord:
    index: int
    nwave: ArmRun
    control: ArmRun

    @property
    def both_delivered(self) -> bool:
        return self.nwave.delivery in DELIVERED and self.control.delivery in DELIVERED


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
class QualityPair:
    pair: int
    nwave_total: int | None
    control_total: int | None
    delta: int | None
    nwave_blocking: int
    control_blocking: int
    pair_delivered: bool


@dataclass(frozen=True)
class QualityAxis:
    """Quality is NOT a ratio and has no threshold. See `quality_axis` below."""

    form: str
    gate: Status
    gate_detail: tuple[tuple[int, str], ...]
    ordering_delivered_only: tuple[QualityPair, ...]
    ordering_all_scored: tuple[QualityPair, ...]
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
    nwave_arm: str | None = None,
    control_arm: str | None = None,
    wall_source: str = "auto",
) -> tuple[PairRecord, ...]:
    """Every pair, every arm, one `ArmRun` each -- none dropped in silence."""
    paths = _payload_paths(campaign)
    stems = {stem for row in paths.values() for stem in row}
    roles = resolve_roles(stems, nwave=nwave_arm, control=control_arm)

    records: list[PairRecord] = []
    for index in sorted(paths):
        arms: dict[str, ArmRun] = {}
        for stem, path in sorted(paths[index].items()):
            role = roles.get(stem)
            if role is None:
                continue
            arms[role] = _read_arm(
                index, stem, role, path, verdicts, rubric, wall_source
            )
        if "nwave" in arms and "control" in arms:
            records.append(PairRecord(index, arms["nwave"], arms["control"]))
    return tuple(records)


def _read_arm(
    index: int,
    stem: str,
    role: str,
    path: Path,
    verdicts: dict[str, dict],
    rubric: dict[str, dict],
    wall_source: str,
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
    if wall_source in ("auto", "transcript"):
        resolved = paired_spread.resolve_transcript_wall(
            outcome.name, outcome.session_id, path
        )
        if isinstance(resolved, paired_spread.TranscriptWall):
            wall_s, source = resolved.wall_s, resolved.scope
        elif wall_source == "transcript":
            wall_s, source = None, None

    verdict = verdicts.get(outcome.session_id)
    delivery, why = _resolve_delivery(True, verdict)
    scored = rubric.get(outcome.session_id)
    total = scored.get("total") if isinstance(scored, dict) else None
    blocking = tuple(scored.get("blocking_quality_findings", ())) if scored else ()

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
        total if isinstance(total, int) else None,
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
        if not pair.both_delivered:
            why = (
                f"nWave {pair.nwave.delivery.value} / control "
                f"{pair.control.delivery.value} -- NOT DELIVERED is not a "
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
    """Quality has THREE forms and none of them is a threshold ratio.

    1. GATE, machine-decidable: the nWave arm must have DELIVERED and been
       ACCEPTED. Binary, owned by `run_acceptance.py`'s `examine()`, carried
       here by reference exactly as `paired_quality_join` carries it.
    2. ORDERING, machine-computable but NOT a ratio: the mission text is
       "non-inferior enterprise quality", and the tree already scores it that
       way ("Rubric control 9/24, nWave 18/24, non-inferior"). The rubric total
       is a sum of 17 judgments each 0..2 -- an interval-less count with no
       meaningful zero, so a QUOTIENT of two totals denotes nothing. The
       comparable quantity is the SIGN of the difference.
    3. REPORTED JUDGMENT, which code must not decide: the reviewer's
       `blocking_quality_findings` strings. They are reproduced verbatim and
       never scored; the only mechanical reading taken from them is again an
       ORDERING (does nWave carry more blockers than the control).
    """
    gate_detail: list[tuple[int, str]] = []
    delivered_rows: list[QualityPair] = []
    all_rows: list[QualityPair] = []
    reported: list[tuple[int, str, str]] = []

    for pair in pairs:
        if pair.nwave.delivery is not Delivery.DELIVERED_ACCEPTED:
            gate_detail.append((pair.index, pair.nwave.delivery.value))
        n, c = pair.nwave.rubric_total, pair.control.rubric_total
        row = QualityPair(
            pair.index,
            n,
            c,
            (n - c) if (n is not None and c is not None) else None,
            len(pair.nwave.blocking),
            len(pair.control.blocking),
            pair.both_delivered,
        )
        if n is not None and c is not None:
            all_rows.append(row)
            if pair.both_delivered:
                delivered_rows.append(row)
        for text in pair.nwave.blocking:
            reported.append((pair.index, "nwave", text))
        for text in pair.control.blocking:
            reported.append((pair.index, "control", text))

    gate = Status.BREACH if gate_detail else Status.WITHIN
    basis = delivered_rows or all_rows
    if not basis:
        ordering = Status.INDETERMINATE
    elif all(row.delta is not None and row.delta >= 0 for row in basis):
        ordering = Status.WITHIN
    else:
        ordering = Status.BREACH
    blocking = (
        Status.BREACH
        if any(row.nwave_blocking > row.control_blocking for row in basis)
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
        "GATE (accepted) + ORDERING (non-inferior delta) + REPORTED JUDGMENT "
        "(blocking findings, quoted never scored) -- never a ratio, no threshold",
        gate,
        tuple(gate_detail),
        tuple(delivered_rows),
        tuple(all_rows),
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
    valid = sum(1 for p in pairs if p.both_delivered)
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
    lines.append(f"quality ordering     : {result.quality.ordering.value}")
    for row in result.quality.ordering_all_scored:
        mark = "" if row.pair_delivered else "   (pair NOT delivered)"
        lines.append(
            f"    pair {row.pair}: nWave {row.nwave_total}/{RUBRIC_MAX} vs control "
            f"{row.control_total}/{RUBRIC_MAX}, delta {row.delta:+d}{mark}"
        )
    basis = [row.pair for row in result.quality.ordering_delivered_only] or [
        row.pair for row in result.quality.ordering_all_scored
    ]
    lines.append(
        f"quality blocking     : {result.quality.blocking.value}"
        f"   (compared on pair(s) {basis}; every finding below is QUOTED, "
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
            nwave_arm=args.nwave_arm,
            control_arm=args.control_arm,
            wall_source=args.wall_source,
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
            "per_pair": [
                {
                    "pair": r.pair,
                    "nwave_total": r.nwave_total,
                    "control_total": r.control_total,
                    "delta": r.delta,
                    "rubric_max": RUBRIC_MAX,
                    "pair_delivered": r.pair_delivered,
                }
                for r in result.quality.ordering_all_scored
            ],
            "reported_findings": [
                {"pair": i, "arm": a, "finding": t}
                for i, a, t in result.quality.reported
            ],
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
