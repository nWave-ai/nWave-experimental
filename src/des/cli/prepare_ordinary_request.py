"""Pure producer of `SeededAuthority` for an ordinary Auto M/L request.

ADR-SSOT-002 Section 4c/4d: `PrepareOrdinaryRequest` turns the immutable
value seed, explicit M/L consent, the observed physical repository root/HEAD
and the already-resolved post-conditional-DESIGN semantic facts into the
exact fourteen-line Auto-root ATD dispatch body -- the same shape
`des.adapters.drivers.hooks.pre_tool_use_handler` validates. It computes only
deterministic projections (`DeliveryId`, `ContractLocator`, table-driven
`Budget`); every semantic decision (`delivery-route`, `examine`,
`independent-review`) is consumed as an explicit already-closed-rule-resolved
argv fact, never inferred, defaulted or guessed here.

Writes no file, mutates no repository state, and persists no value seed
anywhere -- its entire output is the envelope text on stdout. Non-persistent
and side-effect-free beyond the one `git` observation of the declared
`--repo-root`, and one read-only existence check of the DELIVERY-ID's own
`ContractLocator`: a second run for the SAME value seed, once ATD has
already written that contract, is `Blocked` naming the `nw-acceptance-
designer` REVISE-CONTRACT/CITATION revision path -- never a silent
re-derivation of a contract that already exists.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from des._internal.delivery_contract_schema import (
    resolve_delivery_contract_schema_path,
)
from des.application.ordinary_request import (
    BUDGET_TABLE,
    compute_delivery_id,
    contract_locator_for,
    is_valid_arch_header_line,
)


_EXIT_BLOCKED = 2

_BASE_REVISION_HEX_LEN_TO_TAG = {40: "git-sha1:", 64: "git-sha256:"}
_HEX_ALPHABET = frozenset("0123456789abcdef")


def _blocked(*, what: str, why: str, how: str) -> int:
    print(f"WHAT: {what} WHY: {why} HOW: {how}", file=sys.stderr)
    return _EXIT_BLOCKED


class _RefusingArgumentParser(argparse.ArgumentParser):
    """Fail-closed argv parsing: one concise WHAT/WHY/HOW line on stderr,
    nonzero exit, and nothing on stdout -- never argparse's default usage
    dump, which would violate the exact `Blocked` stderr-only contract."""

    def error(self, message: str) -> None:
        print(
            f"WHAT: {message} "
            "WHY: every argv fact must be an explicit, well-formed fixed "
            "token -- a missing or malformed flag cannot be silently "
            "defaulted or guessed. "
            "HOW: pass every required --flag with a value from its closed "
            "vocabulary; see `des prepare-ordinary-request --help`.",
            file=sys.stderr,
        )
        raise SystemExit(_EXIT_BLOCKED)


def _parser() -> argparse.ArgumentParser:
    parser = _RefusingArgumentParser(
        prog="des prepare-ordinary-request",
        description=(
            "Compute Prepared(SeededAuthority) for an ordinary Auto M/L "
            "request and emit the exact fourteen-line Auto-root ATD "
            "dispatch body on stdout."
        ),
    )
    parser.add_argument("--size", required=True, choices=("M", "L"))
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--architecture-authority", required=True)
    parser.add_argument(
        "--delivery-route", required=True, choices=("RED_TO_GREEN", "GREEN_TO_GREEN")
    )
    parser.add_argument("--examine", required=True, choices=("true", "false"))
    parser.add_argument(
        "--independent-review", required=True, choices=("true", "false")
    )
    parser.add_argument("--budget-token-limit", type=int, default=None)
    parser.add_argument("--budget-wall-clock-minutes", type=int, default=None)
    return parser


def _read_value_seed_text() -> str | None:
    """Raw UTF-8 stdin bytes to EOF, decoded strictly. `None` on invalid or
    empty UTF-8 -- the caller reports the exact WHAT/WHY/HOW."""
    raw = sys.stdin.buffer.read()
    if not raw:
        return None
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


def _resolved_repo_root(repo_root: Path) -> Path | None:
    try:
        real_stat = repo_root.lstat()
    except OSError:
        return None
    del real_stat
    if not repo_root.is_absolute() or not repo_root.is_dir() or repo_root.is_symlink():
        return None
    return repo_root.resolve()


def _git_output(repo_root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _observed_base_revision(repo_root: Path) -> str | None:
    head = _git_output(repo_root, "rev-parse", "HEAD")
    if not head:
        return None
    tag = _BASE_REVISION_HEX_LEN_TO_TAG.get(len(head))
    if tag is None or not set(head) <= _HEX_ALPHABET:
        return None
    return f"{tag}{head}"


def _positive_override(value: int | None, field: str) -> int | None | str:
    """`None` (no override), the positive int, or an error marker string."""
    if value is None:
        return None
    if value <= 0:
        return field
    return value


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_signal:
        code = exit_signal.code
        return code if isinstance(code, int) else _EXIT_BLOCKED

    value_seed = _read_value_seed_text()
    if value_seed is None:
        return _blocked(
            what="stdin carried no valid non-empty UTF-8 value seed",
            why="the value seed is the sole identity/outcome source and must "
            "never be paraphrased, defaulted or invented",
            how="pipe the exact UTF-8 value-seed bytes to stdin",
        )

    resolved_root = _resolved_repo_root(args.repo_root)
    if resolved_root is None:
        return _blocked(
            what=f"--repo-root {args.repo_root} is not an absolute real directory",
            why="the physical repository root must never be inferred",
            how="pass an existing absolute, non-symlink repository directory",
        )

    observed_toplevel = _git_output(resolved_root, "rev-parse", "--show-toplevel")
    if observed_toplevel is None:
        return _blocked(
            what=f"--repo-root {resolved_root} is not a readable git repository",
            why="Root/BaseRevision must be observed from a real repository, "
            "never guessed",
            how="pass the physical root of an existing git checkout",
        )
    if Path(observed_toplevel).resolve() != resolved_root:
        return _blocked(
            what=f"--repo-root {resolved_root} is not the observed git "
            f"toplevel ({observed_toplevel})",
            why="a mismatched root could silently source facts from the "
            "wrong repository",
            how="pass the exact `git rev-parse --show-toplevel` root",
        )

    base_revision = _observed_base_revision(resolved_root)
    if base_revision is None:
        return _blocked(
            what=f"HEAD could not be observed at {resolved_root}",
            why="BaseRevision must be the exact observed candidate SHA, never guessed",
            how="run from a repository with at least one commit checked out",
        )

    if not is_valid_arch_header_line(args.architecture_authority):
        return _blocked(
            what="--architecture-authority is not a well-formed "
            "ARCHITECTURE-COVERED <path>.md#<anchor> line",
            why="the architecture authority line is a deterministic upstream "
            "fact ATD must never infer or default",
            how="pass the architect's exact ARCHITECTURE-COVERED "
            "<repo-relative-path>.md#<anchor> line verbatim",
        )

    schema_path = resolve_delivery_contract_schema_path()
    if not schema_path.is_absolute() or not schema_path.is_file():
        return _blocked(
            what=f"the installed DeliveryContract schema is unavailable at {schema_path}",
            why="the producer must source CONTRACT-SCHEMA from its own installed "
            "runtime, never from a root-supplied path or host-wide search",
            how="repair or reinstall nWave so thin-delivery-contract.schema.json "
            "ships beside the runtime",
        )

    token_override = _positive_override(args.budget_token_limit, "--budget-token-limit")
    if isinstance(token_override, str):
        return _blocked(
            what=f"{token_override} must be a positive integer",
            why="Budget is an operating ceiling, never zero or negative",
            how=f"pass a positive integer for {token_override}, or omit it "
            "to use the size's table value",
        )
    minutes_override = _positive_override(
        args.budget_wall_clock_minutes, "--budget-wall-clock-minutes"
    )
    if isinstance(minutes_override, str):
        return _blocked(
            what=f"{minutes_override} must be a positive integer",
            why="Budget is an operating ceiling, never zero or negative",
            how=f"pass a positive integer for {minutes_override}, or omit it "
            "to use the size's table value",
        )

    table_tokens, table_minutes = BUDGET_TABLE[args.size]
    budget_token_limit = token_override if token_override is not None else table_tokens
    budget_wall_clock_minutes = (
        minutes_override if minutes_override is not None else table_minutes
    )

    delivery_id = compute_delivery_id(value_seed)
    contract_locator = contract_locator_for(delivery_id)

    if (resolved_root / contract_locator).exists():
        return _blocked(
            what=(
                f"a DeliveryContract already exists at {contract_locator} "
                f"for DeliveryId {delivery_id} -- this exact value seed "
                "already produced one"
            ),
            why=(
                "the value seed deterministically owns exactly one "
                "DeliveryId and one contract (ADR-SSOT-002 Section 4c/4d); "
                "a second prepare-ordinary-request run for the SAME seed "
                "would redispatch an already-produced contract instead of "
                "revising it, burning a full producer-to-crafter cycle on "
                "a request that already has one"
            ),
            how=(
                "a crafter INDETERMINATE citing this contract/oracle routes "
                "back to nw-acceptance-designer for a revision on the SAME "
                "DeliveryId -- dispatch it with the two-line body "
                f"`REVISE-CONTRACT: {contract_locator}` then `CITATION: "
                "<the crafter's cited defect, as a JSON string literal>`, "
                "never a new prepare-ordinary-request run"
            ),
        )

    outcome_and_seed_json = json.dumps(value_seed, ensure_ascii=False)

    body = "\n".join(
        [
            args.architecture_authority,
            "",
            f"CONTRACT-LOCATOR: {contract_locator}",
            f"CONTRACT-SCHEMA: {schema_path}",
            f"DELIVERY-ID: {delivery_id}",
            f"OUTCOME: {outcome_and_seed_json}",
            f"ROOT: {resolved_root}",
            f"BASE-REVISION: {base_revision}",
            f"DELIVERY-ROUTE: {args.delivery_route}",
            f"EXAMINE: {args.examine}",
            f"INDEPENDENT-REVIEW: {args.independent_review}",
            f"BUDGET-TOKEN-LIMIT: {budget_token_limit}",
            f"BUDGET-WALL-CLOCK-MINUTES: {budget_wall_clock_minutes}",
            f"VALUE-SEED: {outcome_and_seed_json}",
        ]
    )
    sys.stdout.write(body)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
