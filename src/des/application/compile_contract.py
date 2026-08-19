"""Compile one DeliveryContract SKELETON from a DESIGN architecture brief's
own citations (ADR-SSOT-002 Section 4/4b item 1): ``des compile-contract``'s
pure core.

DISTILL "compiles value and architecture authority into a contract" (ADR
Section 4 preamble); today ATD hand-transcribes every mechanically-derivable
fact (target candidate/decision/declared-imports, verification-scope
commands, the acceptance locator, the schema-closed obligation vocabulary a
brief already bold-labels) and six ``des dispatch`` validators exist
specifically to catch ATD's transcription mistakes AFTER the fact. This
module removes the cause: every fact a validator already knows how to CHECK,
this module DERIVES the same way, by calling the identical resolver in
GENERATION mode instead of VALIDATION mode -- so a compiled skeleton passes
those validators by construction, not by luck.

What remains a ``PLACEHOLDER`` (see
``des.domain.contract_placeholder_resolver``) is exactly the set of fields
ADR-SSOT-002 Section 4's field-ownership table assigns to a SEMANTIC/
value-side authority this compiler is never given access to: ``outcome``
(value-side identity), each target's ``justification`` prose and its
``boundary.*`` sub-fields (DESIGN's own judgment, not a fact the brief's
citations alone determine). Two fields the schema type-constrains to a
closed enum (``paradigm``, ``contract-shape``) CANNOT represent an unfilled
placeholder at all without a schema change (out of this compiler's scope) --
they take an explicit, overridable default instead, documented at their own
call site below, never silently guessed as though derived.

The acceptance-oracle locator (``acceptance-tests.locator``) is a
CONVENTION this compiler decides, not an external input: root cannot obtain
that judgment call from ATD before ATD ever runs (ATD holds no ``Bash``,
and this producer runs before ATD's own dispatch), so the locator is
derived deterministically instead (``des.domain.oracle_locator_resolver``)
from the primary EXTEND target's own test-directory convention plus the
``delivery-id``. ATD then WRITES the oracle at that path -- it fills, it
never chooses. No discoverable test-directory convention is a construction
refusal (``Blocked``), never an invented directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.domain.architecture_brief_resolver import (
    declared_imports_for_target,
    extract_obligations,
    extract_target_citations,
)
from des.domain.base_revision_resolver import observed_base_revision
from des.domain.contract_placeholder_resolver import PLACEHOLDER
from des.domain.oracle_locator_resolver import resolve_oracle_locator
from des.domain.workspace_test_command_resolver import declared_whole_suite_command


if TYPE_CHECKING:
    from pathlib import Path


SCHEMA_VERSION = "1.2"

#: DESIGN owns ``targetPlan.contract-shape`` semantically, but the schema
#: constrains it to a closed enum -- an unfilled placeholder cannot validate
#: there the way ``justification``/``boundary.*`` (free ``nonEmptyText``)
#: can. ``bounded-change`` is the safe generic default for an EXTEND target
#: touching existing code; ATD corrects it per-target when a target is
#: actually ``pure-function`` or ``unbounded-preservation``.
DEFAULT_CONTRACT_SHAPE = "bounded-change"


@dataclass(frozen=True, slots=True)
class CompileContractInputs:
    """Every fact ``compile_delivery_contract`` needs, already resolved by
    its CLI caller (argv parsing, brief file reading) -- this dataclass
    itself performs no I/O."""

    repo_root: Path
    delivery_id: str
    brief_text: str
    delivery_route: str
    paradigm: str
    examine: bool
    budget_token_limit: int
    budget_wall_clock_minutes: int
    #: `applicability.independent-review` is a Seeded/orchestration fact
    #: (ADR-SSOT-002 Section 4c), not purely mechanical -- when the caller
    #: already holds the authoritative closed-rule value (root, before
    #: `des prepare-ordinary-request`), it MUST pass it here rather than
    #: let this compiler's own citation-only proxy (`ARCHITECTURE_BOUNDARY_
    #: CHANGE` in obligations) silently disagree with it. `None` (the
    #: default, for standalone/manual invocations with no better source)
    #: falls back to that proxy.
    independent_review: bool | None = None


@dataclass(frozen=True, slots=True)
class Compiled:
    """A schema-shaped skeleton, ready to be serialized verbatim."""

    contract: dict


@dataclass(frozen=True, slots=True)
class Blocked:
    """The compiler could not derive enough from the brief to proceed."""

    what: str
    why: str
    how: str


def _build_target_plan(
    repo_root: Path, target_path: str, citations: list[str], brief_text: str
) -> dict:
    decision = "EXTEND" if (repo_root / target_path).is_file() else "CREATE_NEW"
    return {
        "candidate": target_path,
        # `overlap` is the exact field `des dispatch`'s EXTEND-citation
        # validator searches -- every citation the brief carries for this
        # file is independently useful evidence, so all are kept.
        "overlap": "; ".join(citations),
        "decision": decision,
        "justification": PLACEHOLDER,
        "declared-imports": declared_imports_for_target(
            repo_root, target_path, brief_text
        ),
        "contract-shape": DEFAULT_CONTRACT_SHAPE,
        "boundary": {
            "failure-behavior": PLACEHOLDER,
            "substrate-lie": PLACEHOLDER,
            "substrate-probe": PLACEHOLDER,
            "double-blind-spot": PLACEHOLDER,
        },
    }


def _oracle_dotted_label(oracle_locator: str) -> str:
    stem = oracle_locator[:-3] if oracle_locator.endswith(".py") else oracle_locator
    return stem.replace("/", ".")


def _executable_for(repo_root: Path, head: str) -> dict:
    """A ``repository`` executable when ``head`` resolves under
    ``repo_root`` (a vendored venv interpreter, ``.venv/bin/python``, ...),
    else a ``toolchain`` executable resolved through the consumer's own
    ``PATH`` -- mirrors the same repository-vs-toolchain distinction
    ADR-SSOT-002 Section 4 already draws for ``verification-scope.commands``."""
    if (repo_root / head).is_file():
        return {"kind": "repository", "path": head}
    return {"kind": "toolchain", "name": head}


def _replace_last_non_flag_token(tokens: list[str], replacement: str) -> list[str]:
    """``tokens`` with its last non-``-``-prefixed entry swapped for
    ``replacement`` -- an index-based replacement (never value-equality
    based), so a coincidental duplicate earlier token is never mis-swapped."""
    for index in range(len(tokens) - 1, -1, -1):
        if not tokens[index].startswith("-"):
            return [*tokens[:index], replacement, *tokens[index + 1 :]]
    return [*tokens, replacement]


def _verification_commands(repo_root: Path, oracle_locator: str) -> list[dict]:
    """One command scoped to the oracle, plus the workspace's own declared
    whole-suite command when one exists (``workspace_test_command_resolver``)
    -- together they satisfy ``des dispatch``'s whole-suite-scope validator
    by construction. A workspace with no declared whole-suite convention
    falls back to a direct pytest invocation of the oracle locator, the
    shape this repo's own checked-in DeliveryContract fixtures already use."""
    declared = declared_whole_suite_command(repo_root)
    if not declared:
        return [
            {
                "executable": _executable_for(repo_root, ".venv/bin/python"),
                "arguments": ["-m", "pytest", "-q", oracle_locator],
            }
        ]
    head, *rest = declared
    executable = _executable_for(repo_root, head)
    whole_suite_command = {"executable": executable, "arguments": list(rest)}
    oracle_command = {
        "executable": executable,
        "arguments": _replace_last_non_flag_token(
            rest, _oracle_dotted_label(oracle_locator)
        ),
    }
    return [oracle_command, whole_suite_command]


def compile_delivery_contract(
    inputs: CompileContractInputs,
) -> Compiled | Blocked:
    """Derive a schema-shaped DeliveryContract skeleton from ``inputs``.

    ``Blocked`` only when a fact this compiler could never safely guess is
    genuinely absent (no observable HEAD, no file:line citation, no
    schema-closed obligation token) -- never a partial or best-effort
    contract in that case.
    """
    base_revision = observed_base_revision(inputs.repo_root)
    if base_revision is None:
        return Blocked(
            what=f"HEAD could not be observed at {inputs.repo_root}",
            why="repository.base-revision must be the exact observed "
            "candidate SHA, never guessed",
            how="run from a repository with at least one commit checked out",
        )

    citations = extract_target_citations(inputs.brief_text)
    if not citations:
        return Blocked(
            what="the architecture brief carries no file:line citation",
            why="targets are derived exclusively from DESIGN's own cited "
            "insertion points; a brief with none gives this compiler "
            "nothing to build a target from",
            how="cite at least one exact file:line insertion point in the "
            "architecture brief, or author the contract's targets by hand "
            "for a brief this compiler cannot parse",
        )
    targets = {
        target_path: _build_target_plan(
            inputs.repo_root, target_path, citation_list, inputs.brief_text
        )
        for target_path, citation_list in citations.items()
    }

    # The primary EXTEND target is the first citation the brief makes --
    # `extract_target_citations` preserves first-appearance order.
    primary_target = next(iter(citations))
    oracle_locator = resolve_oracle_locator(
        inputs.repo_root, primary_target, inputs.delivery_id
    )
    if oracle_locator is None:
        return Blocked(
            what="no test-directory convention is discoverable for "
            f"{primary_target!r} (no sibling tests/ and no repository-root "
            "tests/)",
            why="the acceptance-oracle locator is a convention this "
            "compiler decides, never a guessed or invented directory",
            how="create the project's test directory (a sibling tests/ "
            f"next to {primary_target!r}, or a top-level tests/), or "
            "declare the project's test-directory convention in the "
            "workspace fragment",
        )

    obligations = extract_obligations(inputs.brief_text)
    if not obligations:
        return Blocked(
            what="the architecture brief bold-labels no schema-closed obligation token",
            why="obligations select the algebra/certainty/PBT/reuse/"
            "architecture-drift lenses downstream; this compiler only ever "
            "copies a token the brief already states, never invents one",
            how="have DESIGN label each numbered obligation with its exact "
            "schema token (e.g. '**REUSE_CANDIDATE**'), or author "
            "'obligations' by hand",
        )

    # ADR-SSOT-002 Section 4c closed rule: independent review resolves true
    # when obligations include an architecture-boundary change -- used only
    # when the caller has no already-resolved Seeded value of its own.
    independent_review = (
        inputs.independent_review
        if inputs.independent_review is not None
        else "ARCHITECTURE_BOUNDARY_CHANGE" in obligations
    )

    contract = {
        "schema-version": SCHEMA_VERSION,
        "delivery-id": inputs.delivery_id,
        "repository": {"worktree": ".", "base-revision": base_revision},
        "outcome": PLACEHOLDER,
        "targets": targets,
        "paradigm": inputs.paradigm,
        "delivery-route": inputs.delivery_route,
        "obligations": obligations,
        "acceptance-tests": {"locator": oracle_locator},
        "verification-scope": {
            "commands": _verification_commands(inputs.repo_root, oracle_locator)
        },
        "applicability": {
            "independent-review": independent_review,
            "examine": inputs.examine,
        },
        "budget": {
            "token-limit": inputs.budget_token_limit,
            "wall-clock-minutes": inputs.budget_wall_clock_minutes,
        },
    }
    return Compiled(contract=contract)
