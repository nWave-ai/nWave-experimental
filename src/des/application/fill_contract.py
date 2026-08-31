"""Fill exactly one semantic field of an existing DeliveryContract skeleton
(`des fill-contract`'s pure core).

Ale's correction (2026-08-20) supersedes an earlier fill-FILE design: a
separate intermediate JSON file is itself a representable WRONG state --
unparsable JSON, a stray/mechanical key, a malformed nesting -- exactly the
class of defect certainty-by-construction exists to make unrepresentable,
not merely re-validate after the fact. Construction is the only route: ATD
never authors any contract-shaped artifact at all. It passes semantic values
to this constructor as one closed batch; the CLI is the sole writer of the contract file, and a
mechanical field (`declared-imports`, `decision`, `candidate`,
`verification-scope`, `obligations`, ...) has no batch entry naming
it at all -- untouchable by construction, not merely rejected at runtime.

This module is a pure function: no I/O, no argv parsing. `des.cli.
fill_contract` reads the contract file, calls this, and writes the result
back -- the SAME producer discipline `des.application.compile_contract`
already established (derive/validate here, I/O only at the CLI edge).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from des.application.ordinary_request import DELIVERY_ID_PREFIX
from des.domain.contract_placeholder_resolver import PLACEHOLDER


#: The one contract-level semantic field -- no `--target` may accompany it.
CONTRACT_LEVEL_FIELDS = frozenset({"outcome"})

#: Every target-level semantic field -- `--target` is required and must
#: name a target this contract already declares. Dotted `boundary.*` names
#: are the literal batch field names, split on first `.` at fill time.
TARGET_LEVEL_FIELDS = frozenset(
    {
        "justification",
        "boundary.failure-behavior",
        "boundary.substrate-lie",
        "boundary.substrate-probe",
        "boundary.double-blind-spot",
    }
)

#: THE closed field vocabulary this constructor can ever fill -- exactly
#: the semantic fields `des compile-contract` could not derive
#: (`des.domain.contract_placeholder_resolver`'s own tracked set). Every
#: OTHER contract field is mechanical and has no batch entry naming
#: it -- `des.cli.fill_contract`'s own argparse `choices=` is this exact
#: frozenset, sorted, so an attempt to fill one is an argparse error at
#: authoring time, never a runtime refusal this module has to detect.
ALL_FIELDS = CONTRACT_LEVEL_FIELDS | TARGET_LEVEL_FIELDS


@dataclass(frozen=True, slots=True)
class FillContractInputs:
    """Every fact `fill_contract_field` needs, already parsed by its CLI
    caller (argv parsing, contract JSON reading, stdin value reading) --
    this dataclass itself performs no I/O."""

    contract: dict
    field: str
    value: str
    target: str | None = None


@dataclass(frozen=True, slots=True)
class Filled:
    """The contract with exactly one field replaced -- every other field
    byte-identical to the input."""

    contract: dict


@dataclass(frozen=True, slots=True)
class Blocked:
    """The fill call cannot be honored as given."""

    what: str
    why: str
    how: str


@dataclass(frozen=True, slots=True)
class BatchBlocked:
    """Every independently detectable refusal in one batch."""

    problems: tuple[Blocked, ...]


def fill_contract_batch(contract: dict, entries: list[object]) -> Filled | BatchBlocked:
    """Validate every batch entry before publishing one composed contract."""
    problems: list[Blocked] = []
    validated: list[FillContractInputs] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            problems.append(
                Blocked(
                    what=f"batch entry {index} is not a JSON object",
                    why="each entry must name exactly one semantic field and value",
                    how="pass an object with field, value, and optional target keys",
                )
            )
            continue
        unknown = sorted(set(entry) - {"field", "value", "target"})
        field = entry.get("field")
        value = entry.get("value")
        target = entry.get("target")
        target_was_supplied = "target" in entry
        if (
            unknown
            or not isinstance(field, str)
            or not isinstance(value, str)
            or (target_was_supplied and not isinstance(target, str))
        ):
            problems.append(
                Blocked(
                    what=f"batch entry {index} has a malformed shape",
                    why=(
                        "field and value must be strings, target must be a string "
                        "when present, and no other keys are accepted"
                    ),
                    how="pass only field, value, and optional target keys",
                )
            )
            continue
        inputs = FillContractInputs(
            contract=contract, field=field, value=value, target=target
        )
        result = fill_contract_field(inputs)
        if isinstance(result, Blocked):
            problems.append(result)
        else:
            validated.append(inputs)
    if problems:
        return BatchBlocked(problems=tuple(problems))

    composed = copy.deepcopy(contract)
    for inputs in validated:
        result = fill_contract_field(
            FillContractInputs(
                contract=composed,
                field=inputs.field,
                value=inputs.value,
                target=inputs.target,
            )
        )
        assert isinstance(result, Filled)
        composed = result.contract
    return Filled(contract=composed)


def fill_contract_field(inputs: FillContractInputs) -> Filled | Blocked:
    """Replace exactly one semantic field's placeholder (or prior value)
    with `inputs.value`.

    A total function even against a field/target combination argparse's
    own closed choices should already have rejected -- this pure core
    never trusts the caller blindly, the same discipline
    `des.application.compile_contract`'s own `Blocked` branches apply.
    """
    field = inputs.field
    if field in CONTRACT_LEVEL_FIELDS:
        if inputs.target is not None:
            return Blocked(
                what=f"--target {inputs.target!r} was given for contract-level "
                f"field {field!r}",
                why=f"{field!r} lives at the contract's own top level, never "
                "inside a target",
                how="omit --target for this field",
            )
        if field == "outcome" and str(
            inputs.contract.get("delivery-id", "")
        ).startswith(DELIVERY_ID_PREFIX):
            return Blocked(
                what=f"'outcome' was given for auto delivery-id "
                f"{inputs.contract.get('delivery-id')!r}",
                why="an auto contract's outcome is the piped VALUE-SEED "
                "des compile-contract already wrote -- ATD does not author it",
                how="omit the 'outcome' entry from the batch; des "
                "compile-contract/recompile-contract own this field for "
                "an auto delivery-id",
            )
    elif field in TARGET_LEVEL_FIELDS:
        if inputs.target is None:
            return Blocked(
                what=f"--target is required for target-level field {field!r}",
                why="a target-level field must name which target it fills -- "
                "never inferred",
                how="pass --target <the exact target path this contract "
                "already declares>",
            )
        if inputs.target not in inputs.contract.get("targets", {}):
            return Blocked(
                what=f"--target {inputs.target!r} is not a target this "
                "contract declares",
                why="a fill can only address a target the compiler already "
                "listed, never invent one",
                how=f"pass one of {sorted(inputs.contract.get('targets', {}))}",
            )
    else:
        return Blocked(
            what=f"{field!r} is not a field this constructor can fill",
            why="only the compiler's own closed semantic-field vocabulary "
            "is addressable -- every mechanical field has no batch "
            "choice naming it at all",
            how=f"pass one of {sorted(ALL_FIELDS)}",
        )

    value = inputs.value.strip()
    if not value:
        return Blocked(
            what=f"the value for {field!r} is empty or whitespace-only",
            why="a fill must supply real prose, never a blank",
            how="pass the real value on stdin between the heredoc markers",
        )
    if value == PLACEHOLDER:
        return Blocked(
            what=f"the value for {field!r} is still the literal placeholder "
            f"{PLACEHOLDER!r}",
            why="a fill must replace the placeholder with real prose, never repeat it",
            how="pass the real authored value, not the compiler's own "
            "placeholder token",
        )

    contract = copy.deepcopy(inputs.contract)
    if field == "outcome":
        contract["outcome"] = value
    elif field == "justification":
        assert inputs.target is not None
        contract["targets"][inputs.target]["justification"] = value
    else:
        assert inputs.target is not None
        _, boundary_field = field.split(".", 1)
        contract["targets"][inputs.target]["boundary"][boundary_field] = value
    return Filled(contract=contract)
