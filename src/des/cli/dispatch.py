"""Validate one DeliveryContract and emit its thin DELIVER handoff.

The command owns no workflow state.  It validates an explicit repository-root
relative locator, resolves the independent EXAMINE/charter precondition, and
prints only the immutable contract identity consumed by ``nw-deliver``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from pathlib import Path

from des._internal.delivery_contract_schema import (
    resolve_delivery_contract_schema_path,
)
from des._internal.json_schema_subset import JsonSchemaSubsetError
from des._internal.json_schema_subset import validate as _validate_contract_schema
from des.cli._charter_resolution import (
    _assert_never,
    _Author,
    _Block,
    _discover_charter_namespace,
    _resolve_charter_namespace,
    _Reuse,
    _Skip,
)
from des.cli._declared_import_refusal import (
    all_missing_declared_imports as _all_missing_declared_imports,
)
from des.cli._declared_import_refusal import (
    unresolved_declared_import_how as _unresolved_declared_import_how,
)
from des.cli._oracle_structure_refusal import (
    all_oracle_structure_findings as _all_oracle_structure_findings,
)
from des.cli._verification_command_refusal import (
    all_missing_verification_paths as _all_missing_verification_paths,
)
from des.cli._verification_command_refusal import (
    missing_verification_path_finding as _missing_verification_path_finding,
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


#: A repository-relative file paired with a line number, e.g.
#: `hc/api/models.py:1149` -- the shape DESIGN's own architecture authority
#: cites for an exact insertion point. Extension-agnostic (not `.py`-only):
#: an EXTEND target's insertion point can equally be a non-Python file (a
#: schema, a config) -- the K4/healthchecks arm and this repo's own
#: DeliveryContracts both go through `des dispatch`.
_FILE_LINE_CITATION_RE = re.compile(r"[\w/.-]+\.\w+:\d+")


def _extend_targets_missing_citation(contract: dict) -> list[tuple[str, str, str]]:
    """Every `decision: EXTEND` target (`$defs/targetPlan`,
    thin-delivery-contract.schema.json) whose `overlap`/`justification`
    text carries zero file:line-shaped citation.

    GDP-8 second axis on "lossless contract projection": DESIGN's
    architecture authority names an exact insertion point for every EXTEND
    target it declares; a contract target that extends existing code but
    cites none lost that fact projecting from authority into the contract,
    leaving the crafter to relocate the insertion point itself instead of
    reading it verbatim. `CREATE_NEW` targets are exempt -- there is no
    existing insertion point to cite.
    """
    findings: list[tuple[str, str, str]] = []
    for target_path, target_plan in contract["targets"].items():
        if target_plan.get("decision") != "EXTEND":
            continue
        overlap = str(target_plan.get("overlap", ""))
        justification = str(target_plan.get("justification", ""))
        if _FILE_LINE_CITATION_RE.search(overlap) or _FILE_LINE_CITATION_RE.search(
            justification
        ):
            continue
        findings.append(
            (
                f"the contract carries no insertion point for {target_path!r}",
                "DESIGN's architecture authority cites an exact insertion "
                "point for an EXTEND target; a DeliveryContract must project "
                "it losslessly, not drop it on the way from authority to "
                "contract",
                f"cite the exact file:line insertion point (e.g. "
                f"'hc/api/models.py:1149') DESIGN named for {target_path!r} "
                "in this target's own overlap or justification field",
            )
        )
    return findings


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

    try:
        contract_bytes = candidate.read_bytes()
    except OSError as exc:
        _handoff_refusal(
            what=f"the contract cannot be read ({exc})",
            why="DELIVER requires readable contract bytes",
            how="fix the file permissions and rerun des dispatch",
        )
        return None
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

    schema_path = resolve_delivery_contract_schema_path()
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _handoff_refusal(
            what=f"the DeliveryContract schema cannot be read at {schema_path} ({exc})",
            why="contract validity cannot be established without its schema",
            how="reinstall nWave with its schemas",
        )
        return None
    try:
        _validate_contract_schema(schema, contract)
    except JsonSchemaSubsetError as exc:
        _handoff_refusal(
            what=f"the contract fails the thin-delivery-contract schema ({exc.message})",
            why="DELIVER cannot trust a schema-invalid contract",
            how=f"fix the contract to satisfy nWave/schemas/{schema_path.name}",
        )
        return None
    return contract, path_str, contract_bytes


def _oracle_path_finding(repo_root: Path, locator: str) -> tuple[str, str, str] | None:
    """Pure check: `(what, why, how)` for the first reason `locator` cannot
    be trusted as an oracle path, or `None` when it is safe to read.

    Extracted from `_resolve_oracle` so `main()`'s batched defect
    aggregation (Run 5, K4 matrix) can collect this as ONE finding among
    possibly several, while `_resolve_oracle` itself keeps printing and
    returning immediately, unchanged, for `validate_delivery_contract.py`'s
    own single-defect caller.
    """
    unsafe_reason = _unsafe_delivery_contract_path_reason(locator)
    if unsafe_reason is not None:
        return (
            unsafe_reason.replace(
                "--delivery-contract PATH", "acceptance-tests locator"
            ),
            "an unsafe oracle locator could escape the repository boundary",
            "pass a repository-relative acceptance-tests locator without an "
            "absolute prefix, traversal, backslash, drive letter or glob token",
        )

    candidate = repo_root / locator
    try:
        resolved_root = repo_root.resolve()
        resolved_candidate = candidate.resolve()
    except OSError as exc:
        return (
            f"oracle path resolution failed ({exc})",
            "path safety cannot be established",
            "pass an accessible acceptance-tests locator below --repo-root",
        )
    if not resolved_candidate.is_relative_to(resolved_root):
        return (
            f"the oracle path {candidate} escapes --repo-root",
            "the resolved path does not belong to the declared repository",
            "pass an acceptance-tests locator below --repo-root",
        )

    try:
        file_stat = candidate.lstat()
    except OSError:
        return (
            f"the oracle file does not exist at {candidate}",
            "DELIVER requires a real acceptance-tests oracle",
            "pass an existing repository-relative acceptance-tests locator",
        )
    if not stat.S_ISREG(file_stat.st_mode):
        return (
            f"the oracle path {candidate} is not a regular file",
            "a symlink, directory or fifo is not a stable oracle identity",
            "pass a regular acceptance-tests file",
        )
    return None


def _resolve_oracle(repo_root: Path, locator: str) -> bytes | None:
    """Load one safe, regular acceptance-tests oracle or refuse WHAT/WHY/HOW."""
    finding = _oracle_path_finding(repo_root, locator)
    if finding is not None:
        what, why, how = finding
        _handoff_refusal(what=what, why=why, how=how)
        return None

    candidate = repo_root / locator
    try:
        return candidate.read_bytes()
    except OSError as exc:
        _handoff_refusal(
            what=f"the oracle cannot be read ({exc})",
            why="DELIVER requires readable oracle bytes",
            how="fix the file permissions and rerun des dispatch",
        )
        return None


def closure_digest(contract_bytes: bytes, oracle_bytes: bytes) -> str:
    """Compute the shared nwave delivery-closure digest over contract + oracle bytes."""
    return hashlib.sha256(
        b"nwave/delivery-closure/v1"
        + len(contract_bytes).to_bytes(8, "big")
        + contract_bytes
        + len(oracle_bytes).to_bytes(8, "big")
        + oracle_bytes
    ).hexdigest()


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
    # find -- every missing declared-import across every target, every
    # EXTEND target missing a lossless insertion-point citation, plus the
    # one oracle-path/self-reference problem -- into ONE batched refusal
    # below, instead of returning on the first and forcing a fresh dispatch
    # cycle per defect. An OSError during oracle path resolution stays an
    # immediate return: a filesystem anomaly, not a contract content defect
    # an ATD REVISE can fix by editing the contract.
    findings: list[tuple[str, str, str]] = [*_extend_targets_missing_citation(contract)]
    for target_path, reference in _all_missing_declared_imports(repo_root, contract):
        findings.append(
            (
                f"target {target_path!r} declares import {reference!r}, "
                "which does not resolve to a base-tree module or symbol",
                "a DeliveryContract citing an invented symbol reintroduces "
                "ATD-invented substrate (K4 failure-to-design matrix row 12)",
                _unresolved_declared_import_how(repo_root, contract, reference),
            )
        )
    for path in _all_missing_verification_paths(repo_root, contract):
        findings.append(_missing_verification_path_finding(path))
    findings.extend(_all_oracle_structure_findings(repo_root, contract))

    oracle_locator = str(contract["acceptance-tests"]["locator"])
    oracle_unsafe_reason = _unsafe_delivery_contract_path_reason(oracle_locator)
    self_reference_finding: tuple[str, str, str] | None = None
    if oracle_unsafe_reason is None:
        try:
            resolved_contract_path = (repo_root / locator).resolve()
            resolved_oracle_candidate = (repo_root / oracle_locator).resolve()
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

    digest = closure_digest(contract_bytes, oracle_bytes)
    print(f"THIN-DELIVERY-CONTRACT: {locator}")
    print(f"THIN-DELIVERY-CONTRACT-DIGEST: sha256:{digest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
