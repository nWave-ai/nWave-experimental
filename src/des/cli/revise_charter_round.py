"""Bounded producer of the PO charter-revision dispatch envelope.

SF friction FAIL (2026-08-20 follow-up): an expectation-charter namespace
exists and is structurally valid (`des verify-charter-filled` PASSes -- it
judges the SHAPE, never the recipe's semantics), yet an independent
source-blind reviewer faults a real VALUE-side defect in the charter's
`PublicStartRecipe`. Every existing route dead-ends: a hand-composed PO
dispatch is correctly `CHARTER-AUTHOR-DISQUALIFIED` (no producer-generated
envelope), `des resolve-charters` correctly returns `REUSE` (existence is
not reviewed validity, and its algebra stays unchanged -- REUSE remains
right for the no-citation case), so the same `DeliveryId` has NO PO-owned
correction route. This module is that producer -- the exact sibling of
`revise_contract_round.py` (same durable per-`DeliveryId` counter, same
bound shape, same refusal contract), for the charter instead of the
contract.

Source-blindness stays intact BY CONSTRUCTION: the emitted envelope carries
`CHARTER-CURRENT` -- the existing charter's full text as a JSON string --
so the Write-only `nw-product-owner` receives the text FROM THE PRODUCER
and rewrites it applying `CITATION`, never reading the destination itself.
The charter is value-side authority, not source. The envelope NEVER carries
an architecture-authority anchor (that would disqualify PO on sight), and
this producer never deletes or mutates the charter -- it only reads it.

The durable, lock-protected per-`DeliveryId` counter mirrors
`revise_contract_round._reserve_next_round_locked` (itself the same
single-writer pattern `des commit` uses): `_reserve_next_round_locked` is
the ONLY route to a new round number and returns `None` (never a round
value) once the reservation would exceed the bound. Writes no file on
refusal (idempotent: retrying a refused call never corrupts or advances
the durable counter).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des._internal.delivery_contract_schema import (
    resolve_delivery_contract_schema_path,
)
from des._internal.json_schema_subset import JsonSchemaSubsetError
from des._internal.json_schema_subset import validate as _validate_contract_schema
from des.application.ordinary_request import (
    ARCH_HEADER_PREFIXES,
    build_po_revision_envelope,
)


try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover -- non-POSIX platform
    _HAS_FCNTL = False


_EXIT_BLOCKED = 2

# Same "one constant in the route" framing as `revise_contract_round.
# REVISE_ROUND_BOUND`, same value: bounds the PO redispatch loop on one
# DeliveryId without refusing the common, legitimate single-revision case.
CHARTER_REVISION_ROUND_BOUND = 3


def _blocked(*, what: str, why: str, how: str) -> int:
    print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
    return _EXIT_BLOCKED


class _RefusingArgumentParser(argparse.ArgumentParser):
    """Fail-closed argv parsing: one concise WHAT/WHY/HOW line on stderr,
    nonzero exit, nothing on stdout -- same contract as
    `revise_contract_round.py`'s own `_RefusingArgumentParser`."""

    def error(self, message: str) -> None:
        print(
            f"WHAT: {message} "
            "WHY: every argv fact must be an explicit, well-formed fixed "
            "token -- a missing or malformed flag cannot be silently "
            "defaulted or guessed. "
            "HOW: pass every required --flag; see "
            "`des revise-charter-round --help`.",
            file=sys.stderr,
        )
        raise SystemExit(_EXIT_BLOCKED)


def _parser() -> argparse.ArgumentParser:
    parser = _RefusingArgumentParser(
        prog="des revise-charter-round",
        description=(
            "Bounded producer of the eight-line PO charter-revision "
            "dispatch envelope (DISCOVER: ExistingNeedsRevision) for a "
            "reviewer-cited VALUE-side charter defect -- refuses once the "
            "round would exceed the declared per-DeliveryId bound instead "
            "of emitting an unbounded PO redispatch loop."
        ),
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--delivery-id", required=True)
    parser.add_argument("--citation", required=True)
    return parser


def _delivery_id_schema_detail(delivery_id: str) -> str | None:
    """Non-None detail iff `delivery_id` fails the canonical shipped
    `$defs/id` schema -- the SAME gate `des resolve-charters` applies,
    because the namespace path is derived from this id and an unsafe id
    could escape the expectations root."""
    schema_path = resolve_delivery_contract_schema_path()
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        delivery_id_schema = schema["$defs"]["id"]
        if not isinstance(delivery_id_schema, dict):
            raise TypeError("$defs/id is not an object")
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return f"the DeliveryContract id schema cannot be read at {schema_path} ({exc})"
    try:
        _validate_contract_schema(delivery_id_schema, delivery_id)
    except JsonSchemaSubsetError as exc:
        return f"--delivery-id {delivery_id!r} is not schema-valid ({exc.message})"
    return None


def _round_state_dir(repo_root: Path) -> Path:
    return repo_root / ".nwave" / "des" / "charter-revision-rounds"


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
    """The ONLY route to a new round number -- returns `None` (never a
    round value, never a partial/best-effort number) the instant the
    reservation would exceed `bound`, and writes NOTHING on that path.
    Exclusive-locked (`fcntl.flock`, degrading to unlocked on a non-POSIX
    platform) so two concurrent revision requests for the SAME DeliveryId
    cannot both observe and claim the same round number."""
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
            why="the durable round counter's location and the charter "
            "namespace must never be inferred from the invoking cwd",
            how="pass an existing absolute repository directory",
        )

    delivery_id: str = args.delivery_id
    if detail := _delivery_id_schema_detail(delivery_id):
        return _blocked(
            what=detail,
            why="the charter namespace path is derived from delivery-id; "
            "an unsafe id could escape the expectations root",
            how="pass the exact schema-valid delivery-id already resolved "
            "for this delivery",
        )

    if not args.citation.strip():
        return _blocked(
            what="--citation is empty",
            why="a revision with no cited defect cannot direct the "
            "product owner's rewrite",
            how="pass the reviewer's exact cited value-side defect text",
        )

    namespace = repo_root / "docs" / "product" / "expectations" / delivery_id
    members = sorted(namespace.iterdir()) if namespace.is_dir() else []
    charter_path = namespace / "charter.md"
    if not members or not charter_path.is_file():
        return _blocked(
            what=f"the charter namespace {namespace} does not hold an "
            "existing charter at its deterministic member charter.md",
            why="revision is a rewrite of an EXISTING reviewed charter; a "
            "missing or empty namespace is the AUTHOR case, not the "
            "revision case",
            how=f"run `des resolve-charters --repo-root {repo_root} "
            f"--delivery-id {delivery_id} --examine true` and follow its "
            "AUTHOR envelope to author the charter first",
        )

    try:
        charter_current = charter_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _blocked(
            what=f"the existing charter {charter_path} cannot be read ({exc})",
            why="CHARTER-CURRENT must carry the exact existing charter "
            "text to the Write-only product owner",
            how="repair the unreadable charter file, then rerun this command",
        )

    contaminated = next(
        (
            prefix.rstrip()
            for prefix in ARCH_HEADER_PREFIXES
            if prefix.rstrip() in charter_current or prefix.rstrip() in args.citation
        ),
        None,
    )
    if contaminated is not None:
        return _blocked(
            what=f"the charter or citation carries an architecture-authority "
            f"anchor ({contaminated})",
            why="`nw-product-owner` disqualifies itself as charter author "
            "the instant its context carries an architecture-authority "
            "anchor -- this envelope must stay value-only",
            how="remove the architecture reference from the charter/citation "
            "text; architecture defects route to DISTILL via "
            "`des revise-contract-round`, never to the product owner",
        )

    next_round = _reserve_next_round_locked(
        repo_root, delivery_id, CHARTER_REVISION_ROUND_BOUND
    )
    if next_round is None:
        return _blocked(
            what=f"DeliveryId {delivery_id} has already used all "
            f"{CHARTER_REVISION_ROUND_BOUND} charter revision rounds",
            why="an unbounded PO revision loop on the same DeliveryId is "
            "the same incident class `revise-contract-round`'s bound "
            "already terminates (Run 11, 4 sequential revisions) -- the "
            "bound exists so a repeatedly-faulted charter terminates in "
            "an honest INDETERMINATE instead of compounding cost "
            "indefinitely",
            how="report a terminal result citing the exhausted charter "
            "revision budget -- verdict INDETERMINATE -- do not dispatch "
            "the product owner again for this DeliveryId; a human must "
            "resolve the recurring value-side defect",
        )

    namespace_rel = namespace.relative_to(repo_root).as_posix()
    sys.stdout.write(
        build_po_revision_envelope(
            delivery_id=delivery_id,
            namespace=namespace_rel,
            root=str(repo_root.resolve()),
            charter_round=next_round,
            charter_round_bound=CHARTER_REVISION_ROUND_BOUND,
            citation=args.citation,
            charter_current=charter_current,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
