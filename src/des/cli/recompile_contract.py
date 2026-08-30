"""Recompile one EXISTING DeliveryContract against the CURRENT authority.

``des recompile-contract`` is the producer-owned sanctioned overwrite path
``des compile-contract`` deliberately refuses: same flags, the SAME
derivation (``compile_delivery_contract``, the one function -- never a
copy) re-run against the architecture brief as it stands NOW, then a
preserve-fills merge (``des.application.recompile_contract``) that keeps
ATD's already-authored semantic fills wherever the target's identity
(path + decision) still holds. The existing oracle file is never touched
-- it is ATD's property; this CLI writes exactly one file, the contract.
"""

from __future__ import annotations

import json
from dataclasses import replace

from des.application.compile_contract import (
    Blocked,
    Compiled,
    compile_delivery_contract,
)
from des.application.ordinary_request import contract_locator_for
from des.application.recompile_contract import merge_preserve_fills
from des.cli.compile_contract import (
    _EXIT_BLOCKED,
    _blocked,
    _blocked_from,
    build_parser,
    refuse_schema_invalid_skeleton,
    resolve_inputs,
)


def _parser():
    return build_parser(
        prog="des recompile-contract",
        description=(
            "Re-derive an EXISTING DeliveryContract from the current "
            "architecture authority (the exact compile-contract "
            "derivation), overwriting it in place with a preserve-fills "
            "merge: targets present in both sets with an unchanged "
            "decision keep ATD's non-placeholder fills; new targets "
            "arrive as placeholders; removed targets drop; a same-path "
            "decision change resets that target's fills and is reported "
            "on stdout. Requires the contract to already exist -- "
            "authoring a first skeleton is des compile-contract's job."
        ),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_signal:
        code = exit_signal.code
        return code if isinstance(code, int) else _EXIT_BLOCKED

    inputs = resolve_inputs(args)
    if isinstance(inputs, int):
        return inputs

    contract_locator = contract_locator_for(inputs.delivery_id)
    destination = inputs.repo_root / contract_locator
    if not destination.is_file():
        return _blocked(
            what=f"no contract exists at {contract_locator}",
            why="recompile-contract re-derives an EXISTING contract in "
            "place, preserving ATD's fills -- with no contract there is "
            "nothing to preserve or overwrite",
            how="author the skeleton first: run des compile-contract with "
            "the same flags, then have ATD fill it via des fill-contract",
        )
    try:
        existing = json.loads(destination.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _blocked(
            what=f"the existing contract at {contract_locator} cannot be "
            f"read as JSON ({exc})",
            why="the preserve-fills merge reads ATD's fills from the "
            "current contract; an unreadable one cannot be merged",
            how="restore the file to valid JSON (e.g. git restore), or "
            "delete it and start over with des compile-contract",
        )

    # The existing contract is the record that a declared target was
    # grounded at the original compile -- possibly since authored as this
    # delivery's own in-flight product, which must not poison the
    # recompile. Same path+decision => exempt from re-grounding; new or
    # decision-changed rows are grounded fresh, exactly as at compile.
    existing_locator = (existing.get("acceptance-tests") or {}).get("locator")
    existing_scope = existing.get("verification-scope")
    budget = existing.get("budget") if isinstance(existing.get("budget"), dict) else {}
    applicability = (
        existing.get("applicability")
        if isinstance(existing.get("applicability"), dict)
        else {}
    )
    inputs = replace(
        inputs,
        delivery_route=existing.get("delivery-route", inputs.delivery_route),
        paradigm=existing.get("paradigm", inputs.paradigm),
        budget_token_limit=budget.get("token-limit", inputs.budget_token_limit),
        budget_wall_clock_minutes=budget.get(
            "wall-clock-minutes", inputs.budget_wall_clock_minutes
        ),
        examine=applicability.get("examine", inputs.examine),
        independent_review=applicability.get(
            "independent-review", inputs.independent_review
        ),
    )
    result = compile_delivery_contract(
        inputs,
        declared_in_existing_contract={
            path: plan["decision"]
            for path, plan in existing.get("targets", {}).items()
            if isinstance(plan, dict) and isinstance(plan.get("decision"), str)
        },
        existing_oracle_locator=(
            existing_locator if isinstance(existing_locator, str) else None
        ),
        existing_verification_scope=(
            existing_scope if isinstance(existing_scope, dict) else None
        ),
    )
    if isinstance(result, Blocked):
        # The ONE renderer, shared with des compile-contract -- never a
        # copy: the two producers refused in two different shapes before.
        return _blocked_from(result)
    assert isinstance(result, Compiled)

    summary = merge_preserve_fills(existing, result.contract)
    # The MERGED contract is what lands on disk, so it is the one
    # validated -- pre-write, through the same seam des compile-contract
    # and des validate-delivery-contract use (GDP-0, 2026-08-22). An
    # invalid recompile leaves the EXISTING contract untouched.
    refusal = refuse_schema_invalid_skeleton(
        summary.contract,
        architecture_authority=args.architecture_authority,
        producer="des recompile-contract",
    )
    if refusal is not None:
        return refusal
    destination.write_text(
        json.dumps(summary.contract, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"DELIVERY-CONTRACT-SKELETON: {contract_locator}")
    print(f"ORACLE-LOCATOR: {summary.contract['acceptance-tests']['locator']}")
    if result.oracle_reused:
        print("RECOMPILE-ORACLE: reused from existing contract")
    for change in summary.decision_changes:
        print(
            f"RECOMPILE-DECISION-CHANGED: {change.path} "
            f"{change.old_decision} -> {change.new_decision}"
        )
    print(
        f"RECOMPILE: kept {summary.kept_fills} fills, "
        f"new {summary.new_targets} targets, "
        f"dropped {summary.dropped_targets} targets"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
