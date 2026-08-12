#!/usr/bin/env python3
"""Spread of N identical headless runs: the noise floor a comparison must beat.

The instrument this file measures WITH is the mission's cost axis, so its own
failure modes matter more than its output. Two shape rules follow from the
defect it already had, and both are visible in the types below.

**One case per outcome, in the type.** Classifying a run is a THREE-outcome
operation -- usable, failed, unreadable -- and the first version expressed it as
a boolean split into two lists. That is N-1 outcomes in the type and the rest in
control flow, which is how a failed run became a data point: `if r[key]` treats a
legitimate 0 as absent, and `is_error` was rendered without gating anything. Fed
five FAILED runs (is_error true, every usage category 0) it would have dropped
each zeroed metric in silence and reported turns as max/min 1.00, CV 0% -- "the
noise floor is zero". A capture failure presented as a measurement, the same
defect repaired in `jsonl_audit_log_reader` earlier the same day.

**Computing is separate from rendering.** `spread` is total: it returns
`Indeterminate` rather than printing or raising, so the refusal is a value the
caller must handle and cannot skip past.
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from dataclasses import dataclass
from pathlib import Path


MIN_USABLE = 3
"""Below this a spread is not a spread. Attila's own benchmark rule."""

_TOKEN_FIELDS = ("in", "out", "cc", "cr")

# `modelUsage` (camelCase, Claude Code's own stream-json field) is nested-
# inclusive: it carries one entry per model actually invoked, including
# sub-agents the top-level `usage` block never sees. Reading top-level `usage`
# alone silently excludes every nested role's tokens -- the exact K4 defect
# (control 18,799,230 top-level vs 19,397,533 nested-inclusive; nWave
# 24,214,598 vs 32,822,225) that let a 1.2881x ratio PASS while the true
# 1.6921x ratio FAILed.
_MODEL_TOKEN_FIELDS = {
    "in": "inputTokens",
    "out": "outputTokens",
    "cc": "cacheCreationInputTokens",
    "cr": "cacheReadInputTokens",
}

TOP_LEVEL_ONLY = "top-level-only"
AGGREGATE_MODEL_USAGE = "aggregate-model-usage"


# --- outcomes: one case per outcome, none of them representable as another ---


@dataclass(frozen=True)
class Usable:
    """A run that genuinely executed. Every field is present, `0` means zero."""

    name: str
    session_id: str
    cost: float
    turns: int
    wall_s: float
    tokens: dict[str, int]
    token_scope: str
    """`AGGREGATE_MODEL_USAGE` when summed from `modelUsage`, else
    `TOP_LEVEL_ONLY`. Never call the latter a total: it is a scope, not a
    smaller total -- naming it a total is the exact false-PASS this exists to
    prevent from recurring."""


@dataclass(frozen=True)
class Failed:
    """A run that executed and did not work. NEVER a data point."""

    name: str
    reason: str


@dataclass(frozen=True)
class Unreadable:
    """An artifact that could not be parsed. Distinct from `Failed`: this one is
    a claim about the READER, and it may be hiding a usable run."""

    name: str
    error: str


@dataclass(frozen=True)
class Duplicate:
    """A second artifact carrying a `session_id` already seen.

    Exhibited by review 2026-08-06: a byte-identical copy of a run was folded in
    as an independent data point and shifted every statistic. The capture spec's
    own cardinality invariant is the rule being enforced here -- one run id
    belongs to exactly one attempt -- so a repeat is a COUNTING error, not data."""

    name: str
    session_id: str
    first_seen: str


RunOutcome = Usable | Failed | Unreadable | Duplicate


@dataclass(frozen=True)
class Spread:
    label: str
    lo: float
    median: float
    hi: float
    ratio: float
    cv_percent: float


@dataclass(frozen=True)
class Indeterminate:
    """Returned, not printed and not raised: the caller cannot skip past it."""

    label: str
    reason: str


SpreadOutcome = Spread | Indeterminate


# --- pure core ---------------------------------------------------------------


def _aggregate_model_usage(model_usage: dict) -> dict[str, int] | None:
    """Sum every model's four token categories. `None` means malformed --
    the caller fails closed to `Unreadable`, never falls back to top-level."""
    totals = dict.fromkeys(_TOKEN_FIELDS, 0)
    for record in model_usage.values():
        if not isinstance(record, dict):
            return None
        for key, field in _MODEL_TOKEN_FIELDS.items():
            value = record.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return None
            totals[key] += value
    return totals


def classify(name: str, raw: str) -> RunOutcome:
    """Every input reaches exactly one outcome; none can be silently dropped."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return Unreadable(name, f"{type(exc).__name__}: {exc}"[:80])
    if not isinstance(payload, dict):
        return Unreadable(name, f"top level is {type(payload).__name__}, not an object")

    model_usage = payload.get("modelUsage")
    if model_usage is not None and not isinstance(model_usage, dict):
        return Unreadable(
            name, f"modelUsage is {type(model_usage).__name__}, not an object"
        )
    if isinstance(model_usage, dict) and model_usage:
        aggregated = _aggregate_model_usage(model_usage)
        if aggregated is None:
            return Unreadable(
                name,
                "modelUsage present but malformed: expected non-negative "
                "int inputTokens/outputTokens/cacheCreationInputTokens/"
                "cacheReadInputTokens per model",
            )
        tokens: dict[str, int | None] = aggregated
        token_scope = AGGREGATE_MODEL_USAGE
    else:
        usage = payload.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        tokens = {
            "in": usage.get("input_tokens"),
            "out": usage.get("output_tokens"),
            "cc": usage.get("cache_creation_input_tokens"),
            "cr": usage.get("cache_read_input_tokens"),
        }
        token_scope = TOP_LEVEL_ONLY

    cost = payload.get("total_cost_usd")
    turns = payload.get("num_turns")
    duration_ms = payload.get("duration_ms")

    if payload.get("is_error"):
        return Failed(name, "is_error set by the runtime")
    # `is None` throughout: a present 0 is data, an absent field is not.
    missing = [k for k, v in tokens.items() if v is None]
    if missing or cost is None or turns is None or duration_ms is None:
        return Unreadable(
            name, f"half-populated; missing {missing or ''} cost/turns/duration"
        )
    if not cost and not any(tokens.values()):
        return Failed(name, "zero cost AND zero tokens across every category")

    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return Unreadable(
            name, "no session_id: the run cannot be told apart from a copy of itself"
        )

    return Usable(
        name,
        session_id,
        float(cost),
        int(turns),
        duration_ms / 1000,
        {k: int(v) for k, v in tokens.items()},
        token_scope,
    )


def spread(label: str, values: list[float]) -> SpreadOutcome:
    """Total. Two refusals are values, not exceptions and not printed lines."""
    if len(values) < MIN_USABLE:
        return Indeterminate(
            label, f"only {len(values)} value(s), need >= {MIN_USABLE}"
        )
    lo, hi = min(values), max(values)
    if lo <= 0:
        # A ratio against zero is not a large number, it is an undefined one.
        return Indeterminate(label, f"minimum is {lo}; max/min is undefined")
    mean = st.mean(values)
    return Spread(
        label, lo, st.median(values), hi, hi / lo, st.pstdev(values) / mean * 100
    )


# --- imperative shell --------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--campaign",
        type=Path,
        default=Path.cwd(),
        help="campaign directory holding pair-*/ (default: the current directory)",
    )
    args = parser.parse_args(argv)
    # NOT `Path(__file__).parent`. This module lives in scripts/analysis/ and the
    # campaign it reads lives wherever the runner wrote it; rooting the scan at
    # the module's own directory found zero artifacts and reported a clean
    # refusal, which is the most convincing way to be wrong.
    base = args.campaign
    # rglob, because the runner writes beside the workspace it cd'd into. A glob
    # rooted here found nothing and would have reported "no runs" for a probe
    # that had in fact produced five artifacts.
    # Provenance: only artifacts of THE CURRENT campaign. `rglob` is deep and
    # timeless, so a usable leftover from a differently-configured earlier probe
    # was silently eligible to join this spread (exhibited by review). The
    # campaign is the newest `pair-*` generation; anything older is named and
    # excluded rather than quietly mixed in.
    candidates = sorted(base.rglob("*.json"))
    # `<arm>.setup.json` is a SETUP record, not a run: it carries an exit code
    # per step and no usage at all, so classifying it counted two perfectly
    # healthy files as `unreadable` on every campaign. An inflated unreadable
    # count is not harmless - it is the signal an operator is meant to react to,
    # and a counter that cries wolf on its own bookkeeping trains them not to.
    campaign = [
        p
        for p in candidates
        if p.parent.name.startswith("pair-") and not p.stem.endswith(".setup")
    ]
    stale = [p for p in candidates if p not in campaign]

    seen: dict[str, str] = {}
    outcomes: list[RunOutcome] = []
    for path in campaign:
        name = f"{path.parent.name}/{path.stem}"
        outcome = classify(name, path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(outcome, Usable):
            if outcome.session_id in seen:
                outcomes.append(
                    Duplicate(name, outcome.session_id, seen[outcome.session_id])
                )
                continue
            seen[outcome.session_id] = name
        outcomes.append(outcome)
    usable = [o for o in outcomes if isinstance(o, Usable)]
    failed = [o for o in outcomes if isinstance(o, Failed)]
    unreadable = [o for o in outcomes if isinstance(o, Unreadable)]
    duplicates = [o for o in outcomes if isinstance(o, Duplicate)]

    if stale:
        print(f"outside this campaign, EXCLUDED : {len(stale)}")
        for p in stale[:6]:
            print(f"     {p.relative_to(base)}")
    print(f"artifacts found : {len(outcomes)}")
    print(f"  usable        : {len(usable)}")
    print(f"  FAILED        : {len(failed)}")
    print(f"  unreadable    : {len(unreadable)}")
    print(f"  DUPLICATE     : {len(duplicates)}   (same session_id seen twice)")
    for o in failed:
        print(f"     excluded   {o.name}: {o.reason}")
    for o in unreadable:
        print(f"     unreadable {o.name}: {o.error}")
    for o in duplicates:
        print(
            f"     duplicate  {o.name}: session {o.session_id[:12]} already counted as {o.first_seen}"
        )

    if len(usable) < MIN_USABLE:
        print(
            f"\nREFUSING to report a spread: {len(usable)} usable run(s), need >= {MIN_USABLE}."
            "\nA noise floor computed from failed or missing runs is worse than no number,"
            "\nbecause it looks like one. Repair the probe, then re-run this.",
            file=sys.stderr,
        )
        return 1

    header = (
        f"{'run':16s}{'cost$':>9s}{'turns':>7s}{'wall_s':>9s}{'out_tok':>9s}"
        f"{'cache_rd':>11s}{'token scope':>23s}"
    )
    print("\n" + header + "\n" + "-" * len(header))
    for r in usable:
        print(
            f"{r.name:16s}{r.cost:9.4f}{r.turns:7d}{r.wall_s:9.1f}"
            f"{r.tokens['out']:9d}{r.tokens['cr']:11d}{r.token_scope:>23s}"
        )

    scopes = {r.token_scope for r in usable}
    if len(scopes) == 1:
        scope_note = scopes.pop()
    else:
        scope_note = (
            "MIXED — some runs top-level-only, some aggregate-model-usage; "
            "the token spreads below compare unlike scopes"
        )
    # Never call `top-level-only` a total: it excludes nested-role usage by
    # construction, which is the exact defect this file exists to prevent.
    print(f"\ntoken categories reflect scope: {scope_note}")

    series: list[tuple[str, list[float]]] = [
        ("cost USD", [r.cost for r in usable]),
        ("turns", [float(r.turns) for r in usable]),
        ("wall clock s", [r.wall_s for r in usable]),
    ] + [(f"{k} tok", [float(r.tokens[k]) for r in usable]) for k in _TOKEN_FIELDS]

    print(
        f"\n{'metric':16s}{'min':>12s}{'median':>12s}{'max':>12s}{'max/min':>10s}{'CV%':>8s}"
    )
    print("-" * 70)
    worst = 0.0
    for label, values in series:
        result = spread(label, values)
        match result:
            case Indeterminate(label=lab, reason=why):
                print(f"{lab:16s}{('INDETERMINATE — ' + why):>54s}")
            case Spread():
                worst = max(worst, result.ratio)
                print(
                    f"{result.label:16s}{result.lo:12.2f}{result.median:12.2f}"
                    f"{result.hi:12.2f}{result.ratio:10.2f}{result.cv_percent:8.1f}"
                )

    print(
        f"\nREAD THIS AS: across {len(usable)} runs the widest observed max/min is"
        f" {worst:.2f}x."
        "\nAn effect smaller than that is not distinguishable, at this sample size,"
        "\nfrom variance already observed. The range is a LOWER BOUND on the true"
        "\nnoise floor and likely understates it: the extremes of a few draws"
        "\nsystematically undersample the tails, so a later batch can vary wider."
        "\nIt is an observed range, never a confidence interval."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
