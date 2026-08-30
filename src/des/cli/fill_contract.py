"""Fill semantic fields of an existing DeliveryContract skeleton.

``des fill-contract`` is the ONLY route to a filled DeliveryContract: ATD
passes one closed JSON batch for compiled skeletons; this CLI is the sole
writer of the contract file (single-writer discipline, mirroring ``des
compile-contract``'s own). A mechanical field (``declared-imports``,
``decision``, ``candidate``, ``verification-scope``, ``obligations``, ...)
has no batch entry naming it at all -- an attempt to fill one is an
argparse error at authoring time, never a runtime refusal to detect after
the fact. See ``des.application.fill_contract`` module docstring for the
full rationale (Ale's construction-over-file correction, 2026-08-20).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path

from des.application.compile_contract import Blocked as CompileBlocked
from des.application.fill_contract import (
    BatchBlocked,
    Blocked,
    Filled,
    fill_contract_batch,
)
from des.application.ordinary_request import contract_locator_for
from des.cli import compile_contract as compile_contract_cli
from des.domain.contract_placeholder_resolver import find_unfilled_placeholders


_EXIT_BLOCKED = 2
_DELIVERY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class _DuplicateJSONMember(ValueError):
    def __init__(self, member: str) -> None:
        self.member = member
        super().__init__(member)


def _reject_duplicate_json_members(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    members: dict[str, object] = {}
    for member, value in pairs:
        if member in members:
            raise _DuplicateJSONMember(member)
        members[member] = value
    return members


def _blocked(*, what: str, why: str, how: str) -> int:
    print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
    return _EXIT_BLOCKED


def _blocked_batch(problems: tuple[Blocked, ...]) -> int:
    converted = tuple(
        CompileBlocked(what=problem.what, why=problem.why, how=problem.how)
        for problem in problems
    )
    head, *also = converted
    return compile_contract_cli._blocked_from(
        CompileBlocked(
            what=head.what,
            why=head.why,
            how=head.how,
            also=tuple(also),
        )
    )


def _atomic_write_contract(destination: Path, contract: dict) -> None:
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(contract, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()


#: The one deterministic ephemeral batch-file carrier directory, derived
#: from --delivery-id alone. A provider-side Bash safety heuristic can
#: reject a heredoc whose body mixes a brace with a quote character (JSON
#: necessarily has both) before nWave ever sees the call; --batch-file
#: lets the same closed JSON array reach the identical atomic parser/
#: validator/publication path below through a file instead of a shell
#: argument or heredoc body, so the Bash command itself never carries JSON.
_BATCH_CARRIER_LOCATOR_DIR = ".des/fill-contract-carrier"


def _batch_carrier_locator_for(delivery_id: str) -> str:
    """The one admitted deterministic --batch-file carrier locator. There
    is no argv route to any other locator -- `_acquire_batch_carrier`
    computes this itself and never accepts a path from the caller."""
    return f"{_BATCH_CARRIER_LOCATOR_DIR}/{delivery_id}.json"


def _unlink_carrier_matching_identity(
    carrier: Path, locator: str, file_descriptor: int
) -> int | None:
    """Remove `carrier` only if BOTH: (a) the still-open descriptor's OWN
    inode, re-fstat'd right now, still has a positive link count -- an
    unlinked-then-recreated path can reuse the original inode number, so a
    positive link count is the only way to tell "still linked at this
    path" from "coincidentally same inode, already gone"; and (b) the
    CURRENT path identity (a fresh lstat
    on `carrier`) also matches that same dev/ino and is a regular file.
    Both checks must hold: the fd alone doesn't prove which path currently
    names it, and the path lstat alone is defeated by unlink-then-recreate
    inode reuse. Returns `None` on a clean removal, or an already-printed
    `_blocked()` exit code -- never unlinking a replacement, and never
    silently swallowing a removal failure (a carrier that cannot be proven
    gone must not have its bytes published). Does NOT close
    `file_descriptor` -- the caller owns the descriptor's lifetime and
    closes it exactly once."""
    try:
        refreshed = os.fstat(file_descriptor)
    except OSError as exc:
        return _blocked(
            what=f"the batch carrier at {locator} cannot be re-inspected "
            f"before removal ({exc})",
            why="the acquired descriptor's own identity must be provably "
            "readable immediately before removal is attempted",
            how="do not modify the carrier file while --batch-file is "
            "being read; retry the call",
        )
    if refreshed.st_nlink < 1:
        return _blocked(
            what=f"the batch carrier at {locator} was already unlinked or "
            "replaced (no positive link count on the acquired descriptor)",
            why="a descriptor with zero remaining links is no longer named "
            "by any path -- a subsequent unlink of THIS path would delete "
            "an unrelated file that happens to reuse the same inode number",
            how="do not modify the carrier file while --batch-file is "
            "being read; investigate the concurrent writer and retry",
        )
    try:
        current = carrier.lstat()
    except OSError as exc:
        return _blocked(
            what=f"the batch carrier at {locator} cannot be inspected "
            f"before removal ({exc})",
            why="the carrier's current on-disk identity must be provably "
            "the same file this call just read before it is removed",
            how="do not modify the carrier file while --batch-file is "
            "being read; retry the call",
        )
    if (
        current.st_dev != refreshed.st_dev
        or current.st_ino != refreshed.st_ino
        or not stat.S_ISREG(current.st_mode)
    ):
        return _blocked(
            what=f"the batch carrier at {locator} was replaced before it "
            "could be removed",
            why="a carrier whose current path identity differs from the "
            "identity just read is not the same file -- removing it would "
            "delete a replacement, not the carrier that was actually read",
            how="do not modify the carrier file while --batch-file is "
            "being read; investigate the concurrent writer and retry",
        )
    try:
        carrier.unlink()
    except OSError as exc:
        return _blocked(
            what=f"the batch carrier at {locator} could not be removed ({exc})",
            why="a carrier that cannot be proven removed after being read "
            "must not have its bytes published, to keep the carrier "
            "single-use",
            how="ensure the process has permission to remove the carrier "
            "file and retry",
        )
    return None


def _acquire_batch_carrier(repo_root: Path, delivery_id: str) -> str | int:
    """Acquire the deterministic --batch-file carrier through exactly one
    OS file descriptor: open it (refusing to follow a symlink where the
    platform supports that), prove the pre-open path identity equals the
    opened descriptor's own identity, read its bytes in one pass, decode
    them as UTF-8, then -- only after re-proving both a positive link
    count on the STILL-OPEN descriptor and that the current path identity
    still equals it -- remove it. The descriptor stays open across every
    read/decode outcome and is closed exactly once, after cleanup is
    attempted, so an unlink-then-recreate race can never be confused with
    the original file staying in place (a freed inode number can be
    reused by an unrelated new file the instant the original is gone). No
    later outcome (malformed JSON, batch validation failure, or a
    successful publish) can ever leave the carrier behind. Returns the
    carrier's decoded text, or an already-printed `_blocked()` exit code.
    An unsafe or replaced candidate is never read; a replacement is never
    unlinked; and a carrier whose cleanup could not be proven never has
    its bytes published.
    """
    locator = _batch_carrier_locator_for(delivery_id)
    carrier = repo_root / locator
    try:
        pre_open = carrier.lstat()
    except OSError as exc:
        return _blocked(
            what=f"no batch carrier exists at {locator} ({exc})",
            why="--batch-file reads the one deterministic carrier path "
            "derived from --delivery-id, never a path the caller supplies",
            how="write the batch JSON array to the exact deterministic "
            "carrier path and retry",
        )

    if carrier.is_symlink() or not stat.S_ISREG(pre_open.st_mode):
        return _blocked(
            what=f"the batch carrier at {locator} is not a regular file",
            why="a symlink, directory, or fifo is not a safe ephemeral "
            "carrier identity",
            how="write the batch JSON array as a plain regular file at "
            "the deterministic carrier path",
        )
    try:
        resolved_root = repo_root.resolve(strict=True)
        resolved_carrier = carrier.resolve(strict=True)
    except OSError as exc:
        return _blocked(
            what=f"the batch carrier at {locator} cannot be resolved ({exc})",
            why="the carrier's real path must be provably inside the real "
            "repository root",
            how="write the batch JSON array as a plain regular file at "
            "the deterministic carrier path",
        )
    if resolved_carrier != resolved_root / locator:
        return _blocked(
            what=f"the batch carrier at {locator} escapes the repository "
            "root or passes through a symlinked ancestor",
            why="an ancestor directory that is itself a symlink could "
            "redirect the carrier outside the repository root it "
            "lexically appears to be under",
            how="place the carrier directly inside the real repository "
            "root, with no symlinked ancestor directory",
        )

    open_flags = os.O_RDONLY
    # Windows/macOS fallback: O_NOFOLLOW is not always available, so the
    # mandatory lstat/fstat identity check below is the sole guarantee on
    # those platforms -- never a bare open-and-trust.
    open_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        file_descriptor = os.open(carrier, open_flags)
    except OSError as exc:
        return _blocked(
            what=f"the batch carrier at {locator} cannot be opened ({exc})",
            why="a safe ephemeral carrier must be openable by its exact "
            "observed identity, never a symlink or a vanished path",
            how="write the batch JSON array as a plain regular file at "
            "the deterministic carrier path",
        )
    # The descriptor is kept open across read, decode, AND cleanup below,
    # and is closed exactly once here, no matter which branch returns --
    # closing it any earlier would let the kernel recycle its inode number
    # before the pre-unlink identity re-check can run.
    try:
        try:
            opened = os.fstat(file_descriptor)
        except OSError as exc:
            return _blocked(
                what=f"the batch carrier at {locator} cannot be inspected "
                f"once opened ({exc})",
                why="a safe ephemeral carrier's open identity must be "
                "provably readable before its bytes are trusted",
                how="write the batch JSON array as a plain regular file at "
                "the deterministic carrier path",
            )
        if (
            pre_open.st_dev != opened.st_dev
            or pre_open.st_ino != opened.st_ino
            or not stat.S_ISREG(opened.st_mode)
        ):
            return _blocked(
                what=f"the batch carrier at {locator} is not a regular "
                "file, or was replaced between being observed and opened",
                why="a symlink, directory, fifo, or a candidate swapped in "
                "after the pre-open identity check is not a safe ephemeral "
                "carrier",
                how="write the batch JSON array as a plain regular file at "
                "the deterministic carrier path and retry without racing "
                "another writer",
            )
        try:
            payload_bytes = os.read(file_descriptor, opened.st_size + 1)
        except OSError as exc:
            cleanup = _unlink_carrier_matching_identity(
                carrier, locator, file_descriptor
            )
            if cleanup is not None:
                return cleanup
            return _blocked(
                what=f"the batch carrier at {locator} cannot be read ({exc})",
                why="the acquired carrier's bytes must be readable in one "
                "pass from its own open descriptor",
                how="write the batch JSON array as a plain regular file at "
                "the deterministic carrier path",
            )
        if len(payload_bytes) != opened.st_size:
            cleanup = _unlink_carrier_matching_identity(
                carrier, locator, file_descriptor
            )
            if cleanup is not None:
                return cleanup
            return _blocked(
                what=f"the batch carrier at {locator} returned "
                f"{len(payload_bytes)} bytes for a {opened.st_size}-byte "
                "acquired size",
                why="a short read is an incomplete acquisition -- publishing "
                "a truncated batch payload is not safe",
                how="write the batch JSON array as a plain regular file at "
                "the deterministic carrier path and retry without racing "
                "another writer",
            )

        try:
            payload_text = payload_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            cleanup = _unlink_carrier_matching_identity(
                carrier, locator, file_descriptor
            )
            if cleanup is not None:
                return cleanup
            return _blocked(
                what=f"the batch carrier at {locator} is not valid UTF-8 ({exc})",
                why="the batch payload must be readable as UTF-8 text",
                how="write the batch JSON array as UTF-8 encoded text at "
                "the deterministic carrier path",
            )

        cleanup = _unlink_carrier_matching_identity(carrier, locator, file_descriptor)
        if cleanup is not None:
            return cleanup
        return payload_text
    finally:
        os.close(file_descriptor)


class _RefusingArgumentParser(argparse.ArgumentParser):
    """Fail-closed argv parsing -- mirrors ``des compile-contract``'s own.
    An unrecognized write mode is one
    of these: a WHAT/WHY/HOW line, at authoring time, never a written
    byte."""

    def error(self, message: str) -> None:
        print(
            f"WHAT: {message} "
            "WHY: every argv fact must be an explicit, well-formed fixed "
            "token -- a missing or malformed flag cannot be silently "
            "defaulted or guessed, and only the compiler's own closed "
            "semantic values must arrive in one valid batch. "
            "HOW: pass every required --flag with a value from its own "
            "closed batch shape; see `des fill-contract --help`.",
            file=sys.stderr,
        )
        raise SystemExit(_EXIT_BLOCKED)


def _parser() -> argparse.ArgumentParser:
    parser = _RefusingArgumentParser(
        prog="des fill-contract",
        description=(
            "Fill semantic fields of a compiled DeliveryContract skeleton, "
            "or report which fields remain unfilled. The --batch JSON array "
            "arrives on stdin."
        ),
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--delivery-id", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--status",
        action="store_true",
        help="Report which fields remain unfilled without writing anything.",
    )
    mode.add_argument(
        "--batch",
        action="store_true",
        help="Fill a stdin JSON array of semantic field entries atomically.",
    )
    parser.add_argument(
        "--batch-file",
        action="store_true",
        help=(
            "With --batch, read the JSON array from the deterministic "
            f"carrier at {_BATCH_CARRIER_LOCATOR_DIR}/<delivery-id>.json "
            "instead of stdin -- the provider-safe transport for a Bash "
            "caller whose command line can never itself carry JSON."
        ),
    )
    return parser


def _report_status(contract: dict) -> None:
    remaining = find_unfilled_placeholders(contract)
    if remaining:
        print("CONTRACT-FILL-STATUS: INCOMPLETE")
        for field_path in remaining:
            print(f"UNFILLED: {field_path}")
    else:
        print("CONTRACT-FILL-STATUS: COMPLETE")


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_signal:
        code = exit_signal.code
        return code if isinstance(code, int) else _EXIT_BLOCKED

    if args.batch_file and not args.batch:
        return _blocked(
            what="--batch-file was given without --batch",
            why="--batch-file only selects the JSON transport for the "
            "atomic --batch write, not a mode of its own",
            how="pass --batch --batch-file together",
        )

    repo_root: Path = args.repo_root
    try:
        root_stat = repo_root.lstat()
    except OSError as exc:
        return _blocked(
            what=f"--repo-root cannot be read ({exc})",
            why="contract filling requires a real repository root",
            how="pass an existing absolute repository directory",
        )
    if (
        not repo_root.is_absolute()
        or not stat.S_ISDIR(root_stat.st_mode)
        or repo_root.is_symlink()
    ):
        return _blocked(
            what="--repo-root is not an absolute real directory",
            why="contract identity must not depend on the invoking cwd, and "
            "a symlink root makes it ambiguous",
            how="pass the absolute physical repository directory",
        )

    if not _DELIVERY_ID_RE.match(args.delivery_id):
        return _blocked(
            what=f"--delivery-id {args.delivery_id!r} is not schema-shaped",
            why="delivery-id must match thin-delivery-contract.schema.json's "
            "$defs/id pattern",
            how="pass the exact lowercase-kebab id `des compile-contract` already used",
        )

    contract_locator = contract_locator_for(args.delivery_id)
    destination = repo_root / contract_locator
    try:
        file_stat = destination.lstat()
    except OSError as exc:
        return _blocked(
            what=f"no contract exists at {contract_locator} ({exc})",
            why="fill-contract mutates an existing compiled skeleton, never "
            "invents one",
            how="run `des compile-contract` first",
        )
    if not stat.S_ISREG(file_stat.st_mode):
        return _blocked(
            what=f"the contract path {contract_locator} is not a regular file",
            why="a symlink, directory or fifo is not a stable contract identity",
            how="pass a locator resolving to a regular JSON file",
        )
    try:
        contract = json.loads(destination.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return _blocked(
            what=f"the contract at {contract_locator} cannot be read as JSON ({exc})",
            why="fill-contract requires a well-formed JSON object to mutate",
            how="fix the contract's encoding/JSON and rerun",
        )

    if args.status:
        _report_status(contract)
        return 0

    if args.batch:
        if args.batch_file:
            carrier_text = _acquire_batch_carrier(repo_root, args.delivery_id)
            if isinstance(carrier_text, int):
                return carrier_text
            raw_batch_text = carrier_text
        else:
            raw_batch_text = sys.stdin.read()
        try:
            payload = json.loads(
                raw_batch_text, object_pairs_hook=_reject_duplicate_json_members
            )
        except _DuplicateJSONMember as exc:
            return _blocked(
                what=(
                    "the --batch payload contains a duplicate JSON member "
                    f"name {exc.member!r}"
                ),
                why=(
                    "duplicate member names are ambiguous and must not be "
                    "silently reduced to the last value"
                ),
                how=(
                    "remove the duplicate member name and pass one field/value/"
                    "optional-target object per batch entry"
                ),
            )
        except json.JSONDecodeError as exc:
            return _blocked(
                what=f"the --batch payload is not valid JSON ({exc})",
                why="batch construction requires one JSON array",
                how="pass a JSON array of field/value/optional-target objects",
            )
        if not isinstance(payload, list):
            return _blocked(
                what="the --batch payload is not a JSON array",
                why="batch construction requires an ordered collection of entries",
                how="wrap the field/value/optional-target objects in one JSON array",
            )
        if not payload:
            return _blocked(
                what="the --batch JSON array is empty",
                why="an empty batch fills no semantic value",
                how="include at least one field/value entry",
            )
        batch_result = fill_contract_batch(contract, payload)
        if isinstance(batch_result, BatchBlocked):
            return _blocked_batch(batch_result.problems)
        assert isinstance(batch_result, Filled)
        _atomic_write_contract(destination, batch_result.contract)
        print(f"DELIVERY-CONTRACT-FILLED: BATCH ({len(payload)} entries)")
        _report_status(batch_result.contract)
        return 0

    return _blocked(
        what="no supported fill mode was selected",
        why="one atomic --batch is the sole write-capable contract publication route",
        how="pass --batch, or use --status for a read-only projection",
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
