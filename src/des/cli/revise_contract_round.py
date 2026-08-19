"""Bounded producer of the ATD contract-revision dispatch body.

Stable-design report 2026-08-19 §1.2 (`~/nwave-formal/2026-08-19-gates/
report/2026-08-19-stable-design.md`): nothing today bounds how many times
ATD can be redispatched via `REVISE-CONTRACT` on the same `DeliveryId` --
root hand-types the two-line revision body directly (per `nw-auto/SKILL.md`
"Route boundaries"), and `tla/AutoRoute.tla`'s own `MaxRevise` bound
carries an explicit comment admitting it is a TLC-exploration-only device
with no source-code analogue. Run 11's own evidence: 4 separate ATD
revisions in one delivery (FK field name, PUT scope, verification scope,
PUT support -- residuality/stressors.md STR-09).

`agda/StableDesign.agda` §2 models the target as an intrinsic, fully
type-checkable construction -- unlike §1.1 (terminal-by-construction
subagent results), this needs NO external platform fact:

    data ReviseRound (bound : Nat) : Nat -> Set where
      first         : ReviseRound bound 0
      attemptRevise : ReviseRound bound n → (suc n ≤ bound) → ReviseRound bound (suc n)

A caller holding `ReviseRound bound n` at `n = bound` has no `suc n ≤ bound`
evidence to offer -- there is no well-typed route to round `bound+1`. This
module is that construction's Python-side realization: `_reserve_next_round
_locked` is the ONLY route to a new round number, and it returns `None`
(never a round value) once the reservation would exceed the bound --
mirroring `attemptRevise`'s missing evidence exactly, not merely
approximating a ceiling with a re-checkable counter.

The durable, lock-protected per-`DeliveryId` counter uses the SAME
single-writer pattern `des commit` already uses for a different resource
(`commit.py:124-134`, `fcntl.flock` + a scoped temporary index) -- portable
per this repo's ADR-PLAT-001 (`_HAS_FCNTL` degrades to unlocked-but-still-
durable on a platform without `fcntl`, never a hard failure).

The bound (`REVISE_ROUND_BOUND = 3`) lives HERE, in the producer -- never
in a hook. `pre_tool_use_handler._evaluate_auto_root_atd_body` only checks
the ENVELOPE's own lexical shape (`REVISE-ROUND: n/N` is a well-formed
`n/N` pair), never re-derives or re-enforces the bound itself; enforcing
the SAME bound in two places would be exactly the "three checks on one
artefact" pattern GDP-0 names as the alarm to redesign the producer, not
the gate.

Writes no file on refusal (idempotent: retrying a refused call never
corrupts or advances the durable counter). Mirrors `prepare_ordinary_
request.py`'s own `_blocked`/`_RefusingArgumentParser`/argv-fact-explicit
conventions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover -- non-POSIX platform
    _HAS_FCNTL = False


_EXIT_BLOCKED = 2

# "One constant in the route" (team-lead's own framing). Run 11's real
# incident is exactly ONE OVER a bound of 3 (4 sequential revisions) -- the
# smallest bound that would have caught it without also refusing the
# common, legitimate single-revision case.
REVISE_ROUND_BOUND = 3


def _blocked(*, what: str, why: str, how: str) -> int:
    print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
    return _EXIT_BLOCKED


class _RefusingArgumentParser(argparse.ArgumentParser):
    """Fail-closed argv parsing: one concise WHAT/WHY/HOW line on stderr,
    nonzero exit, nothing on stdout -- same contract as `prepare_ordinary_
    request.py`'s own `_RefusingArgumentParser`."""

    def error(self, message: str) -> None:
        print(
            f"WHAT: {message} "
            "WHY: every argv fact must be an explicit, well-formed fixed "
            "token -- a missing or malformed flag cannot be silently "
            "defaulted or guessed. "
            "HOW: pass every required --flag; see "
            "`des revise-contract-round --help`.",
            file=sys.stderr,
        )
        raise SystemExit(_EXIT_BLOCKED)


def _parser() -> argparse.ArgumentParser:
    parser = _RefusingArgumentParser(
        prog="des revise-contract-round",
        description=(
            "Bounded producer of the REVISE-CONTRACT/REVISE-ROUND/CITATION "
            "dispatch body for an ATD contract revision -- refuses once the "
            "round would exceed the declared per-DeliveryId bound instead "
            "of emitting an unbounded redispatch loop."
        ),
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--contract-locator", required=True)
    parser.add_argument("--citation", required=True)
    return parser


def _round_state_dir(repo_root: Path) -> Path:
    return repo_root / ".nwave" / "des" / "revise-rounds"


def _delivery_id_from_locator(locator: str) -> str | None:
    """The `<delivery-id>` stem of a `docs/delivery-contracts/<delivery-id>
    .json`-shaped locator -- the round counter's own key, derived from the
    SAME locator the crafter cited, never a freshly-invented identity."""
    name = Path(locator).name
    if not name.endswith(".json") or name == ".json":
        return None
    return name[: -len(".json")]


def _read_current_round(state_path: Path) -> int:
    if not state_path.is_file():
        return 0
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    round_value = data.get("round") if isinstance(data, dict) else None
    return round_value if isinstance(round_value, int) and round_value >= 0 else 0


def _write_round(state_path: Path, round_value: int) -> None:
    state_path.write_text(json.dumps({"round": round_value}), encoding="utf-8")


def _reserve_next_round_locked(
    repo_root: Path, delivery_id: str, bound: int
) -> int | None:
    """The ONLY route to a new round number -- mirrors `attemptRevise`'s
    missing-evidence shape exactly: returns `None` (never a round value,
    never a partial/best-effort number) the instant the reservation would
    exceed `bound`, and writes NOTHING on that path. Exclusive-locked
    (`fcntl.flock`, degrading to unlocked on a non-POSIX platform) so two
    concurrent revision requests for the SAME DeliveryId cannot both
    observe and claim the same round number."""
    state_dir = _round_state_dir(repo_root)
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{delivery_id}.json"
    lock_path = state_dir / f"{delivery_id}.lock"
    with open(lock_path, "w", encoding="utf-8") as lock_handle:
        if _HAS_FCNTL:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            current = _read_current_round(state_path)
            next_round = current + 1
            if next_round > bound:
                return None
            _write_round(state_path, next_round)
            return next_round
        finally:
            if _HAS_FCNTL:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_signal:
        code = exit_signal.code
        return code if isinstance(code, int) else _EXIT_BLOCKED

    repo_root: Path = args.repo_root
    if not repo_root.is_absolute() or not repo_root.is_dir():
        return _blocked(
            what=f"--repo-root {repo_root} is not an absolute real directory",
            why="the durable round counter's location must never be inferred",
            how="pass an existing absolute repository directory",
        )

    delivery_id = _delivery_id_from_locator(args.contract_locator)
    if delivery_id is None:
        return _blocked(
            what=f"--contract-locator {args.contract_locator!r} has no "
            "well-formed <delivery-id>.json basename",
            why="the round counter is keyed by DeliveryId, derived from the "
            "SAME locator the crafter cited -- never a fresh identity",
            how="pass the exact CONTRACT-LOCATOR already produced for this DeliveryId",
        )

    if not args.citation.strip():
        return _blocked(
            what="--citation is empty",
            why="a revision with no cited defect cannot direct ATD's fix",
            how="pass the crafter's exact cited defect text",
        )

    next_round = _reserve_next_round_locked(repo_root, delivery_id, REVISE_ROUND_BOUND)
    if next_round is None:
        return _blocked(
            what=f"DeliveryId {delivery_id} has already used all "
            f"{REVISE_ROUND_BOUND} revision rounds",
            why="an unbounded REVISE-CONTRACT loop on the same DeliveryId "
            "is exactly Run 11's own incident (4 sequential revisions, "
            "residuality/stressors.md STR-09) -- the bound exists so a "
            "repeatedly-wrong contract terminates in an honest "
            "INDETERMINATE instead of compounding cost indefinitely",
            how="report a terminal result citing the exhausted revision "
            "budget -- verdict INDETERMINATE -- do not dispatch ATD again "
            "for this DeliveryId; a human must resolve the recurring defect",
        )

    citation_json = json.dumps(args.citation, ensure_ascii=False)
    body = "\n".join(
        [
            f"REVISE-CONTRACT: {args.contract_locator}",
            f"REVISE-ROUND: {next_round}/{REVISE_ROUND_BOUND}",
            f"CITATION: {citation_json}",
        ]
    )
    sys.stdout.write(body)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
