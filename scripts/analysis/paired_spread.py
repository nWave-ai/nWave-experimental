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
from datetime import datetime
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

ROOT_PAYLOAD_ONLY = "root-payload-only"
TRANSCRIPT_ROOT_PLUS_SUBAGENTS = "transcript-root-plus-subagents"


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
    wall_scope: str
    """Always `ROOT_PAYLOAD_ONLY`: `wall_s` above is `duration_ms` from the root
    payload alone, and that duration ends the instant the ROOT process returns
    -- even while background agents it dispatched keep running. The exact K4
    gap this labels honestly: payload claimed 337s/78s while the root+subagent
    transcript spanned 1764s/1287s. `resolve_transcript_wall` below is the
    path-aware measurement that does not share this blind spot; nothing here
    falls back to it silently, and nothing there falls back to this one."""


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
        ROOT_PAYLOAD_ONLY,
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


# --- transcript-scoped wall measurement (path-aware) -------------------------


@dataclass(frozen=True)
class TranscriptWall:
    """Wall clock re-scoped to transcript evidence: the one root transcript the
    payload's `session_id` names, plus that transcript's own `subagents/*.jsonl`
    -- nothing else. `wall_s` is the span (latest - earliest) of every valid ISO
    timestamp parsed across them."""

    name: str
    session_id: str
    wall_s: float
    scope: str


@dataclass(frozen=True)
class TranscriptWallUnreadable:
    """Transcript evidence absent, ambiguous, or malformed. A refusal VALUE, same
    discipline as `Unreadable`/`Indeterminate`: the caller excludes this run from
    the wall-clock claim and never substitutes the payload duration for it."""

    name: str
    session_id: str
    reason: str


TranscriptWallOutcome = TranscriptWall | TranscriptWallUnreadable


def _parse_iso_timestamp(value: object) -> datetime | None:
    """Timezone-aware only -- no file mtime inference, no naive-datetime guess.
    A naive timestamp cannot be compared honestly against evidence pulled from a
    different file, so it is treated the same as an absent one."""
    if not isinstance(value, str) or not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _read_transcript_timestamps(path: Path) -> list[datetime] | None:
    """`None` when the file itself cannot be read, OR when any line is
    malformed JSON / not an object / carries a `timestamp` key that is present
    but invalid or naive -- each of those makes the whole transcript
    untrustworthy, not just the one line, so the caller fails the run closed
    rather than computing a span from whatever else happened to parse. A
    genuinely ABSENT `timestamp` key is not one of those cases: real transcript
    lines routinely omit it, so that line is skipped and reading continues."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    stamps: list[datetime] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(record, dict):
            return None
        if "timestamp" not in record:
            continue
        parsed = _parse_iso_timestamp(record["timestamp"])
        if parsed is None:
            return None
        stamps.append(parsed)
    return stamps


def resolve_transcript_wall(
    name: str, session_id: str, payload_path: Path
) -> TranscriptWallOutcome:
    """The path-aware measurement boundary `main` uses for the wall-clock claim.

    `Usable.wall_s` ends when the ROOT payload process returns even while
    background agents it dispatched keep running -- the exact K4 gap: payload
    duration 337s/78s against a root+subagent transcript span of 1764s/1287s.
    This locates the one root transcript under the workspace ADJACENT to the
    payload (`{workspace}/.claude-k4/projects/**/<session_id>.jsonl`, where
    `workspace` is `payload_path` with its `.json` suffix stripped -- the exact
    layout `paired_campaign.py` writes), adds only that transcript's own
    `subagents/*.jsonl`, and spans every valid ISO timestamp found across them.

    On any ambiguity -- no `.claude-k4` workspace, no matching root transcript,
    more than one, an unreadable file, or fewer than two valid timestamps -- this
    fails closed to `TranscriptWallUnreadable`. It never falls back to the
    payload duration: a silent fallback here is the exact false PASS/FAIL this
    function exists to prevent.
    """
    workspace = payload_path.parent / payload_path.stem
    projects_dir = workspace / ".claude-k4" / "projects"
    if not projects_dir.is_dir():
        return TranscriptWallUnreadable(
            name,
            session_id,
            f"no {projects_dir} -- no adjacent .claude-k4 workspace for this run",
        )
    matches = sorted(p for p in projects_dir.rglob("*.jsonl") if p.stem == session_id)
    if not matches:
        return TranscriptWallUnreadable(
            name,
            session_id,
            "no root transcript matching this session_id under projects/**",
        )
    if len(matches) > 1:
        return TranscriptWallUnreadable(
            name,
            session_id,
            f"{len(matches)} root transcripts matched this session_id, ambiguous: "
            + ", ".join(str(m) for m in matches[:4]),
        )
    root = matches[0]
    stamps = _read_transcript_timestamps(root)
    if stamps is None:
        return TranscriptWallUnreadable(name, session_id, f"could not read {root}")

    # Own subagents only: the directory that shares the root transcript's own
    # session-id stem, never a sibling session's -- that boundary is what keeps
    # an unrelated session in the same workspace from ever entering this span.
    subagents_dir = root.parent / root.stem / "subagents"
    if subagents_dir.is_dir():
        for sub_path in sorted(subagents_dir.glob("*.jsonl")):
            sub_stamps = _read_transcript_timestamps(sub_path)
            if sub_stamps is None:
                return TranscriptWallUnreadable(
                    name, session_id, f"could not read {sub_path}"
                )
            stamps.extend(sub_stamps)

    if len(stamps) < 2:
        return TranscriptWallUnreadable(
            name,
            session_id,
            f"only {len(stamps)} valid ISO timestamp(s) across root+subagents, "
            "need >= 2",
        )
    return TranscriptWall(
        name,
        session_id,
        (max(stamps) - min(stamps)).total_seconds(),
        TRANSCRIPT_ROOT_PLUS_SUBAGENTS,
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
    paths_by_name: dict[str, Path] = {}
    for path in campaign:
        name = f"{path.parent.name}/{path.stem}"
        paths_by_name[name] = path
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
        f"{'run':16s}{'cost$':>9s}{'turns':>7s}{'payload_s':>10s}{'out_tok':>9s}"
        f"{'cache_rd':>11s}{'token scope':>23s}"
    )
    print("\n" + header + "\n" + "-" * len(header))
    for r in usable:
        print(
            f"{r.name:16s}{r.cost:9.4f}{r.turns:7d}{r.wall_s:10.1f}"
            f"{r.tokens['out']:9d}{r.tokens['cr']:11d}{r.token_scope:>23s}"
        )
    # `payload_s` above, never `wall_s`: it is `ROOT_PAYLOAD_ONLY`, the exact
    # scope that ends when the root process returns even while its dispatched
    # agents keep running. The wall-clock CLAIM below never reads this column.
    print(
        "\n(payload_s is root-payload-only -- ends when the root process returns,"
        "\nnot when its dispatched agents finish. The wall clock s spread below"
        "\nis transcript-scoped, never this column.)"
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

    # The wall-clock CLAIM is resolved per run from transcript evidence, never
    # from the payload duration -- that fallback is the exact false PASS/FAIL
    # this module exists to prevent. A run without readable transcript evidence
    # is EXCLUDED from the wall spread and named here, not silently backfilled.
    wall_outcomes = [
        resolve_transcript_wall(r.name, r.session_id, paths_by_name[r.name])
        for r in usable
    ]
    wall_ok = [w for w in wall_outcomes if isinstance(w, TranscriptWall)]
    wall_bad = [w for w in wall_outcomes if isinstance(w, TranscriptWallUnreadable)]
    print(
        f"\nwall clock evidence : {len(wall_ok)} transcript-scoped, "
        f"{len(wall_bad)} indeterminate (excluded, never backfilled from payload)"
    )
    for w in wall_bad:
        print(f"     wall indeterminate {w.name}: {w.reason}")
    if wall_ok:
        print(f"wall clock reflects scope: {TRANSCRIPT_ROOT_PLUS_SUBAGENTS}")

    series: list[tuple[str, list[float]]] = [
        ("cost USD", [r.cost for r in usable]),
        ("turns", [float(r.turns) for r in usable]),
        ("wall clock s", [w.wall_s for w in wall_ok]),
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
