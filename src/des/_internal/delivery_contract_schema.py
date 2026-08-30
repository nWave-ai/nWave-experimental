"""Resolve the one shipped DeliveryContract schema across supported layouts."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from des._internal.json_schema_subset import JsonSchemaSubsetError, validate


_SCHEMA_NAME = "thin-delivery-contract.schema.json"


def resolve_delivery_contract_schema_path() -> Path:
    """Resolve the schema in Claude-install, checkout, or wheel layout.

    The installed runtime's packaged copy wins whenever it exists, whichever
    tree this module happens to execute from: `des compile-contract` under the
    installed shim and `des validate-delivery-contract` under a worktree
    venv's editable install must read THE SAME schema, or a stale checkout
    copy rejects a contract the producer legitimately emitted (version-skew
    incident 2026-08-20, `dropped-citations`). A checkout's own schema is a
    build source, never the runtime validation source; it remains the
    fallback only where no installed runtime exists (CI, bare checkouts).

    The Claude config dir follows the same two-branch rule the `des` shim
    inlines: a non-empty ``CLAUDE_CONFIG_DIR`` wins, else ``~/.claude``.

    The returned fallback preserves a deterministic diagnostic path when a
    broken distribution omitted the schema; callers still fail closed before
    trusting it.
    """
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "")
    claude_dir = Path(config_dir) if config_dir else Path.home() / ".claude"
    installed = claude_dir / "lib" / "nWave" / "schemas" / _SCHEMA_NAME
    if installed.is_file():
        return installed
    here = Path(__file__).resolve()
    candidates = (
        here.parents[3] / "nWave" / "schemas" / _SCHEMA_NAME,
        here.parents[2] / "nWave" / "nWave" / "schemas" / _SCHEMA_NAME,
    )
    return next((path for path in candidates if path.is_file()), candidates[0])


@dataclass(frozen=True, slots=True)
class SchemaUnreadable:
    """The shipped schema itself could not be read -- validity is
    UNDECIDABLE, never assumed (GDP-6: degrade LOUD)."""

    schema_path: Path
    error: str


@dataclass(frozen=True, slots=True)
class SchemaViolation:
    """One DeliveryContract constraint the instance violates, with the
    JSON-pointer-style ``path`` to the failing node and the schema keyword
    that fired -- enough for a caller to name WHICH authority cell
    produced the value, not merely that the JSON is invalid."""

    schema_path: Path
    message: str
    path: tuple[str | int, ...]
    validator: str

    @property
    def pointer(self) -> str:
        """The failing node as a readable JSON pointer (``/`` for the
        whole document)."""
        return "/" + "/".join(str(step) for step in self.path) if self.path else "/"


def delivery_contract_schema_violation(
    contract: object,
) -> SchemaUnreadable | SchemaViolation | None:
    """The ONE schema check every DeliveryContract producer and consumer
    runs -- never a copy.

    ``None`` means the instance satisfies the installed schema. Callers
    render their own WHAT/WHY/HOW from the returned finding, because the
    same violation means something different to a PRODUCER (an authority
    cell it transcribed is wrong) and to a CONSUMER (the contract it was
    handed cannot be trusted).

    GDP-0, 2026-08-22 (third occurrence of the class): ``des compile-
    contract`` used to WRITE its skeleton and leave validation to the
    downstream ``des dispatch`` / ``des validate-delivery-contract``
    consumer, so an authority cell naming a DIRECTORY where the schema
    admits only a FILE was transcribed verbatim into a contract no
    version of the schema has ever accepted. This function is the seam
    that lets the producer refuse instead.
    """
    schema_path = resolve_delivery_contract_schema_path()
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return SchemaUnreadable(schema_path=schema_path, error=str(exc))
    legacy_v13 = isinstance(contract, dict) and contract.get("schema-version") == "1.3"
    if legacy_v13:
        acceptance = contract.get("acceptance-tests")
        if isinstance(acceptance, dict) and "supporting-locators" in acceptance:
            return SchemaViolation(
                schema_path=schema_path,
                message="schema-version '1.3' cannot carry supporting-locators",
                path=("acceptance-tests", "supporting-locators"),
                validator="schema-version",
            )
        # Explicit compatibility adapter: schema 1.3 is the exact current
        # shape minus acceptance support. Validate a copy against 1.4 while
        # retaining the original bytes/version for closure/v1 identity.
        validation_candidate = {**contract, "schema-version": "1.4"}
    else:
        validation_candidate = contract
    try:
        validate(schema, validation_candidate)
    except JsonSchemaSubsetError as exc:
        return SchemaViolation(
            schema_path=schema_path,
            message=exc.message,
            path=tuple(exc.path),
            validator=exc.validator,
        )
    assert isinstance(validation_candidate, dict)
    acceptance = validation_candidate.get("acceptance-tests")
    assert isinstance(acceptance, dict)
    has_support = "supporting-locators" in acceptance
    if not legacy_v13 and not has_support:
        return SchemaViolation(
            schema_path=schema_path,
            message="schema-version '1.4' requires supporting-locators",
            path=("acceptance-tests",),
            validator="schema-version",
        )
    return None
