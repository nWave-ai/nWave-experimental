"""Validate one DeliveryContract and emit its thin DELIVER handoff.

The command owns no workflow state.  It validates an explicit repository-root
relative locator, resolves the independent EXAMINE/charter precondition, and
prints only the immutable contract identity consumed by ``nw-deliver``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os  # noqa: F401 - the os module is this command's filesystem seam
import re
import stat
import sys
from pathlib import Path

from des._internal.delivery_contract_schema import (
    SchemaUnreadable,
    SchemaViolation,
    delivery_contract_schema_violation,
)
from des.adapters.driven.filesystem.real_filesystem import RealFileSystem
from des.application.ordinary_request import (
    DELIVERY_ID_PREFIX,
    compute_delivery_id,
    contract_locator_for,
)
from des.cli._charter_resolution import (
    _assert_never,
    _Author,
    _Block,
    _discover_charter_namespace,
    _resolve_charter_namespace,
    _Reuse,
    _Skip,
)
from des.cli._oracle_red_reason_refusal import (
    oracle_red_reason_check as _oracle_red_reason_check,
)
from des.cli._placeholder_refusal import (
    all_unfilled_placeholder_findings as _all_unfilled_placeholder_findings,
)
from des.domain.oracle_locator_resolver import (
    oracle_citation_file_part as _oracle_file_part,
)
from des.ports.driven_ports.filesystem_port import (
    FileSystemPort,
    RegularFileSnapshot,
    SnapshotRefusal,
)


_EXIT_USAGE_ERROR = 2
_GLOB_PATTERN = re.compile(r"[*?\[\]]")


def _handoff_refusal(*, what: str, why: str, how: str) -> int:
    """Emit one actionable refusal and no success-shaped output."""
    print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
    return _EXIT_USAGE_ERROR


def _batched_contract_defects_refusal(findings: list[tuple[str, str, str]]) -> int:
    """One refusal naming every collected `(what, why, how)` defect.

    Run 5 (K4 matrix): `des dispatch` rejected the same contract three
    times in sequence, one defect per REVISE cycle (invented import ->
    self-referential import -> non-regular-file oracle path), each costing
    a full ATD REVISE round (~236s + up to 676K cache-read tokens on the
    third). GDP-3/5: the validator must report every defect it can find in
    one pass, so one REVISE fixes all of them.

    A single-item batch reduces to exactly `_handoff_refusal`'s own
    single-defect message, byte for byte -- every EXISTING single-defect
    test keeps matching. Exit code is `_EXIT_USAGE_ERROR` either way.
    """
    if len(findings) == 1:
        what, why, how = findings[0]
        return _handoff_refusal(what=what, why=why, how=how)
    lines = [f"WHAT: this DeliveryContract has {len(findings)} defects:"]
    for index, (what, why, how) in enumerate(findings, start=1):
        lines.append(f"  {index}. {what}")
        lines.append(f"     WHY: {why}")
        lines.append(f"     HOW: {how}")
    print("\n".join(lines), file=sys.stderr)
    return _EXIT_USAGE_ERROR


def _unsafe_delivery_contract_path_reason(path_str: str) -> str | None:
    """Return why a raw locator is unsafe, before any filesystem access."""
    if not path_str.strip():
        return "the --delivery-contract PATH is empty or whitespace-only"
    if path_str != path_str.strip():
        return f"the --delivery-contract PATH {path_str!r} has surrounding whitespace"
    if path_str.startswith("/"):
        return f"the --delivery-contract PATH {path_str!r} is absolute"
    if re.match(r"^[A-Za-z]:", path_str):
        return f"the --delivery-contract PATH {path_str!r} has a drive letter"
    if "\\" in path_str:
        return f"the --delivery-contract PATH {path_str!r} contains a backslash"
    if ".." in path_str.split("/"):
        return f"the --delivery-contract PATH {path_str!r} contains traversal"
    if _GLOB_PATTERN.search(path_str):
        return f"the --delivery-contract PATH {path_str!r} contains a glob token"
    return None


def _load_delivery_contract(
    repo_root: Path, path_str: str
) -> tuple[dict, str, bytes] | None:
    """Load one safe, regular, schema-valid contract or refuse WHAT/WHY/HOW."""
    unsafe_reason = _unsafe_delivery_contract_path_reason(path_str)
    if unsafe_reason is not None:
        _handoff_refusal(
            what=unsafe_reason,
            why="an unsafe locator could escape the repository boundary",
            how=(
                "pass a repository-relative path without an absolute prefix, "
                "traversal, backslash, drive letter or glob token"
            ),
        )
        return None

    candidate = repo_root / path_str
    try:
        resolved_root = repo_root.resolve()
        resolved_candidate = candidate.resolve()
    except OSError as exc:
        _handoff_refusal(
            what=f"contract path resolution failed ({exc})",
            why="path safety cannot be established",
            how="pass an accessible locator below --repo-root",
        )
        return None
    if not resolved_candidate.is_relative_to(resolved_root):
        _handoff_refusal(
            what=f"the contract path {candidate} escapes --repo-root",
            why="the resolved path does not belong to the declared repository",
            how="pass a locator below --repo-root",
        )
        return None

    try:
        file_stat = candidate.lstat()
    except OSError:
        _handoff_refusal(
            what=f"the contract file does not exist at {candidate}",
            why="DELIVER requires a real immutable DeliveryContract",
            how="pass an existing repository-relative JSON file",
        )
        return None
    if not stat.S_ISREG(file_stat.st_mode):
        _handoff_refusal(
            what=f"the contract path {candidate} is not a regular file",
            why="a symlink, directory or fifo is not a stable contract identity",
            how="pass a regular JSON file",
        )
        return None

    # The contract is a closure member like any other: it is acquired through
    # the validated no-follow capability, never through an ordinary reread.
    acquired = RealFileSystem().acquire_regular_snapshot(candidate, role="contract")
    if isinstance(acquired, SnapshotRefusal):
        _handoff_refusal(what=acquired.what, why=acquired.why, how=acquired.how)
        return None
    contract_bytes = acquired.content
    try:
        contract = json.loads(contract_bytes.decode("utf-8"))
    except UnicodeDecodeError as exc:
        _handoff_refusal(
            what=f"the contract is not valid UTF-8 ({exc})",
            why="a malformed contract cannot be trusted",
            how="fix the encoding and rerun des dispatch",
        )
        return None
    except json.JSONDecodeError as exc:
        _handoff_refusal(
            what=f"the contract is not valid JSON ({exc})",
            why="a malformed contract cannot be trusted",
            how="fix the JSON and rerun des dispatch",
        )
        return None

    # The ONE schema check, shared with des compile-contract's own
    # PRE-WRITE producer refusal -- never a copy (GDP-0, 2026-08-22).
    finding = delivery_contract_schema_violation(contract)
    if isinstance(finding, SchemaUnreadable):
        _handoff_refusal(
            what="the DeliveryContract schema cannot be read at "
            f"{finding.schema_path} ({finding.error})",
            why="contract validity cannot be established without its schema",
            how="reinstall nWave with its schemas",
        )
        return None
    if isinstance(finding, SchemaViolation):
        _handoff_refusal(
            what="the contract fails the thin-delivery-contract schema "
            f"({finding.message})",
            why="DELIVER cannot trust a schema-invalid contract",
            how=f"fix the contract to satisfy nWave/schemas/{finding.schema_path.name}",
        )
        return None
    supporting_locators = contract["acceptance-tests"].get("supporting-locators", [])
    if supporting_locators != sorted(supporting_locators):
        _handoff_refusal(
            what="acceptance-tests.supporting-locators are not lexicographically ordered",
            why="delivery-closure/v2 binds durable support order and consumers never normalise authority",
            how="recompile the contract from lexicographically ordered Acceptance support locator declarations",
        )
        return None
    return contract, path_str, contract_bytes


def _auto_contract_boundary_findings(
    contract: dict, locator: str
) -> list[tuple[str, str, str]]:
    """The two untrusted-file boundary checks for an `auto-` DeliveryId:
    an `auto-` id is a self-asserted claim about the VALUE-SEED that
    produced it, so DELIVER must not trust a contract moved off its own
    canonical locator, nor one whose `outcome` no longer hashes to its own
    `delivery-id`. A nominal (non-auto) contract carries neither claim and
    is untouched by this check."""
    delivery_id = str(contract.get("delivery-id", ""))
    if not delivery_id.startswith(DELIVERY_ID_PREFIX):
        return []
    findings: list[tuple[str, str, str]] = []
    canonical_locator = contract_locator_for(delivery_id)
    if locator != canonical_locator:
        findings.append(
            (
                f"the auto delivery-id {delivery_id!r} contract was dispatched "
                f"from {locator!r}, not its canonical locator {canonical_locator!r}",
                "an auto delivery-id owns exactly one deterministic authoring "
                "locator -- a contract found elsewhere could be a copy or a "
                "stale duplicate never re-validated against that locator",
                f"dispatch the contract at its canonical locator {canonical_locator!r}",
            )
        )
    outcome = contract.get("outcome")
    if isinstance(outcome, str) and compute_delivery_id(outcome) != delivery_id:
        findings.append(
            (
                f"the contract's outcome does not hash to its own auto "
                f"delivery-id {delivery_id!r}",
                "an auto delivery-id is a deterministic function of its own "
                "VALUE-SEED outcome -- a mismatch means the outcome was "
                "altered after compilation",
                "recompile the contract from the original VALUE-SEED with "
                "des compile-contract, never hand-edit outcome",
            )
        )
    return findings


def _regular_closure_path_finding(
    repo_root: Path, locator: str, *, role: str
) -> tuple[str, str, str] | None:
    """Shared containment/lstat/regular-file laws for closure members."""
    unsafe_reason = _unsafe_delivery_contract_path_reason(locator)
    if unsafe_reason is not None:
        noun = (
            "acceptance-tests locator"
            if role == "oracle"
            else "acceptance support locator"
        )
        return (
            unsafe_reason.replace("--delivery-contract PATH", noun),
            f"an unsafe {role} locator could escape the repository boundary",
            f"pass a repository-relative {role} locator without unsafe path syntax",
        )
    candidate = repo_root / locator
    try:
        resolved_root = repo_root.resolve()
        resolved_candidate = candidate.resolve()
    except OSError as exc:
        return (
            f"{role} path resolution failed ({exc})",
            "path safety cannot be established",
            f"pass an accessible {role} locator below --repo-root",
        )
    if not resolved_candidate.is_relative_to(resolved_root):
        return (
            f"the {role} path {candidate} escapes --repo-root",
            "the resolved path does not belong to the declared repository",
            f"pass a {role} locator below --repo-root",
        )
    try:
        file_stat = candidate.lstat()
    except OSError:
        return (
            f"the {role} file does not exist at {candidate}",
            f"delivery closure requires a real {role} file",
            f"pass an existing repository-relative {role} locator",
        )
    if not stat.S_ISREG(file_stat.st_mode):
        return (
            f"the {role} path {candidate} is not a regular file",
            f"a symlink, directory or fifo is not a stable {role} identity",
            f"pass a regular {role} file",
        )
    return None


def _oracle_path_finding(repo_root: Path, locator: str) -> tuple[str, str, str] | None:
    """Pure check: `(what, why, how)` for the first reason `locator` cannot
    be trusted as an oracle path, or `None` when it is safe to read.

    Extracted from `_resolve_oracle` so `main()`'s batched defect
    aggregation (Run 5, K4 matrix) can collect this as ONE finding among
    possibly several, while `_resolve_oracle` itself keeps printing and
    returning immediately, unchanged, for `validate_delivery_contract.py`'s
    own single-defect caller.

    A `::Selector` suffix on the locator is oracle IDENTITY, never a path
    segment: every disk check here runs on the FILE part alone.
    """
    return _regular_closure_path_finding(
        repo_root, _oracle_file_part(locator), role="oracle"
    )


def _acquire_closure_member(
    repo_root: Path, locator: str, *, role: str, filesystem: FileSystemPort
) -> RegularFileSnapshot | None:
    """Acquire one validated closure member snapshot, or refuse WHAT/WHY/HOW.

    The same-descriptor algorithm itself lives on the real filesystem
    adapter: this CLI holds no second copy of it, so a CLI reader and an
    adapter reader can no longer agree on the same unsafe sequence.
    """
    finding = _regular_closure_path_finding(repo_root, locator, role=role)
    if finding is not None:
        what, why, how = finding
        _handoff_refusal(what=what, why=why, how=how)
        return None
    outcome = filesystem.acquire_regular_snapshot(repo_root / locator, role=role)
    if isinstance(outcome, SnapshotRefusal):
        _handoff_refusal(what=outcome.what, why=outcome.why, how=outcome.how)
        return None
    return outcome


def _read_regular_file_no_follow(
    repo_root: Path,
    locator: str,
    *,
    role: str,
    filesystem: FileSystemPort | None = None,
) -> bytes | None:
    """Return the acquired bytes of one closure member, or refuse."""
    snapshot = _acquire_closure_member(
        repo_root, locator, role=role, filesystem=filesystem or RealFileSystem()
    )
    if snapshot is None:
        return None
    return snapshot.content


def _resolve_oracle(repo_root: Path, locator: str) -> bytes | None:
    """Load one safe, regular acceptance-tests oracle or refuse WHAT/WHY/HOW."""
    return _read_regular_file_no_follow(
        repo_root, _oracle_file_part(locator), role="oracle"
    )


def _support_path_finding(repo_root: Path, locator: str) -> tuple[str, str, str] | None:
    """Pure no-follow regular-file check for one acceptance support."""
    return _regular_closure_path_finding(repo_root, locator, role="support")


def _resolve_supporting_files(
    repo_root: Path, locators: list[str]
) -> tuple[tuple[str, bytes], ...] | None:
    """Read ordered support identities and bytes, refusing on first defect."""
    resolved: list[tuple[str, bytes]] = []
    for locator in locators:
        finding = _support_path_finding(repo_root, locator)
        if finding is not None:
            what, why, how = finding
            _handoff_refusal(what=what, why=why, how=how)
            return None
        content = _read_regular_file_no_follow(repo_root, locator, role="support")
        if content is None:
            return None
        resolved.append((locator, content))
    return tuple(resolved)


def _closure_v2_frame(label: bytes, payload: bytes) -> bytes:
    """Length-frame one typed closure/v2 field without ambiguous joins."""
    return (
        len(label).to_bytes(8, "big")
        + label
        + len(payload).to_bytes(8, "big")
        + payload
    )


def closure_digest(
    contract_bytes: bytes,
    oracle_bytes: bytes,
    *,
    oracle_locator: str | None = None,
    supporting_files: tuple[tuple[str, bytes], ...] = (),
) -> str:
    """Compute legacy closure/v1 or support-aware closure/v2 honestly."""
    if not supporting_files:
        # Exact compatibility contract for schema 1.3. Do not label these
        # bytes as v2: old candidates retain the identical digest.
        return hashlib.sha256(
            b"nwave/delivery-closure/v1"
            + len(contract_bytes).to_bytes(8, "big")
            + contract_bytes
            + len(oracle_bytes).to_bytes(8, "big")
            + oracle_bytes
        ).hexdigest()
    if oracle_locator is None:
        raise ValueError("closure/v2 requires the primary oracle locator identity")
    framed = [
        b"nwave/delivery-closure/v2",
        _closure_v2_frame(b"contract-bytes", contract_bytes),
        _closure_v2_frame(b"primary-locator", oracle_locator.encode("utf-8")),
        _closure_v2_frame(b"primary-bytes", oracle_bytes),
        _closure_v2_frame(b"support-count", len(supporting_files).to_bytes(8, "big")),
    ]
    for locator, content in supporting_files:
        framed.append(_closure_v2_frame(b"support-locator", locator.encode("utf-8")))
        framed.append(_closure_v2_frame(b"support-bytes", content))
    return hashlib.sha256(b"".join(framed)).hexdigest()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des dispatch",
        description=(
            "Validate one immutable DeliveryContract and emit its thin DELIVER "
            "handoff. PATH is relative to --repo-root."
        ),
    )
    parser.add_argument(
        "--repo-root",
        required=True,
        type=Path,
        help="Absolute repository root used to resolve the contract locator.",
    )
    parser.add_argument(
        "--delivery-contract",
        required=True,
        help="DeliveryContract JSON path relative to --repo-root.",
    )
    parser.add_argument(
        "--diagnostics",
        action="store_true",
        help="Emit informational validation diagnostics on stderr.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Validate one contract and emit exactly two identity headers."""
    args = _build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    repo_root: Path = args.repo_root
    if not repo_root.is_absolute():
        return _handoff_refusal(
            what="--repo-root is relative",
            why="contract identity must not depend on the invoking cwd",
            how="pass the absolute physical repository root",
        )
    try:
        root_stat = repo_root.lstat()
    except OSError as exc:
        return _handoff_refusal(
            what=f"--repo-root cannot be read ({exc})",
            why="contract resolution requires a real repository root",
            how="pass an existing absolute repository directory",
        )
    if not stat.S_ISDIR(root_stat.st_mode) or repo_root.is_symlink():
        return _handoff_refusal(
            what="--repo-root is not a real directory",
            why="a symlink or non-directory makes contract identity ambiguous",
            how="pass the absolute physical repository directory",
        )

    loaded = _load_delivery_contract(repo_root, args.delivery_contract)
    if loaded is None:
        return _EXIT_USAGE_ERROR
    contract, locator, contract_bytes = loaded

    # Run 5 (K4 matrix): collect EVERY contract-content defect this pass can
    # find -- the unfilled-placeholder and oracle-path/self-reference
    # problems -- into ONE batched refusal below, instead of returning on
    # the first and forcing a fresh dispatch cycle per defect. An OSError
    # during oracle path resolution stays an immediate return: a
    # filesystem anomaly, not a contract content defect an ATD REVISE can
    # fix by re-filling. Ale's construction-over-file correction
    # (2026-08-20, "the contract has one writer -- `des fill-contract` is
    # the constructor", Agda vacuity report ~/nwave-formal/
    # 2026-08-19-gates/report/2026-08-19-gate-analysis.md): the three
    # checks this list used to run here -- EXTEND-target citation,
    # declared-imports resolution, verification-scope path existence --
    # are DELETED, not merely reordered. `des fill-contract` has no
    # batch entry naming a mechanical field at all, so a contract
    # that reaches this point already has them correct by construction;
    # re-checking here would be pure duplicated cost for zero additional
    # evidence (GDP-10).
    findings: list[tuple[str, str, str]] = [
        *_all_unfilled_placeholder_findings(contract),
        *_auto_contract_boundary_findings(contract, locator),
    ]
    oracle_locator = str(contract["acceptance-tests"]["locator"])
    oracle_file = _oracle_file_part(oracle_locator)
    oracle_unsafe_reason = _unsafe_delivery_contract_path_reason(oracle_file)
    self_reference_finding: tuple[str, str, str] | None = None
    if oracle_unsafe_reason is None:
        try:
            resolved_contract_path = (repo_root / locator).resolve()
            resolved_oracle_candidate = (repo_root / oracle_file).resolve()
        except OSError as exc:
            return _handoff_refusal(
                what=f"oracle path resolution failed ({exc})",
                why="path safety cannot be established",
                how="pass an accessible acceptance-tests locator below --repo-root",
            )
        if resolved_oracle_candidate == resolved_contract_path:
            self_reference_finding = (
                f"the acceptance-tests locator {oracle_locator!r} resolves "
                f"to the same physical path as --delivery-contract {locator!r}",
                "ContractLocator and OracleLocator are distinct nominal "
                "roles; a self-referencing oracle could never be "
                "independently validated",
                "point acceptance-tests.locator at a distinct oracle file",
            )
    if self_reference_finding is not None:
        findings.append(self_reference_finding)
    else:
        oracle_path_finding = _oracle_path_finding(repo_root, oracle_locator)
        if oracle_path_finding is not None:
            findings.append(oracle_path_finding)

    if findings:
        return _batched_contract_defects_refusal(findings)

    support_locators = list(contract["acceptance-tests"].get("supporting-locators", []))
    supporting_files = _resolve_supporting_files(repo_root, support_locators)
    if supporting_files is None:
        return _EXIT_USAGE_ERROR

    # K4 Run 13: only after every cheaper STATIC check already passed --
    # no reason to spend a real bounded subprocess proving an oracle's RED
    # reason when a static defect would refuse this contract anyway.
    red_reason_findings, red_reason_notes = _oracle_red_reason_check(
        repo_root, contract
    )
    findings.extend(red_reason_findings)
    if findings:
        return _batched_contract_defects_refusal(findings)

    oracle_bytes = _resolve_oracle(repo_root, oracle_locator)
    if oracle_bytes is None:
        return _EXIT_USAGE_ERROR

    examine = bool(contract["applicability"]["examine"])
    delivery_id = str(contract["delivery-id"])
    discovered = (
        _discover_charter_namespace(repo_root, delivery_id) if examine else None
    )
    resolution = _resolve_charter_namespace(examine=examine, discovered=discovered)
    if isinstance(resolution, _Author):
        return _handoff_refusal(
            what=(
                "the expectation-charter namespace "
                f"docs/product/expectations/{delivery_id}/ is missing or empty"
            ),
            why="applicability.examine=true requires a valid charter before DELIVER",
            how="author the charter from value-side evidence, then rerun des dispatch",
        )
    if isinstance(resolution, _Block):
        return _handoff_refusal(
            what=resolution.what,
            why=resolution.why,
            how=resolution.how,
        )
    if not isinstance(resolution, (_Reuse, _Skip)):
        _assert_never(resolution)

    if args.diagnostics:
        for note in red_reason_notes:
            if "INDETERMINATE" not in note:
                note = f"INDETERMINATE: {note}"
            print(note, file=sys.stderr)
    # The CLI is a value-only handoff. Construction belongs to PreToolUse,
    # where the foreground Agent/result provenance is available.
    # The published identity is the identity of the bytes this run VALIDATED.
    # Rereading a locator here would digest a different observation of a
    # possibly different file, silently unbinding validation from publication.
    admitted_digest = closure_digest(
        contract_bytes,
        oracle_bytes,
        oracle_locator=oracle_locator,
        supporting_files=supporting_files,
    )
    print(f"THIN-DELIVERY-CONTRACT: {locator}")
    print(f"THIN-DELIVERY-CONTRACT-DIGEST: sha256:{admitted_digest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
