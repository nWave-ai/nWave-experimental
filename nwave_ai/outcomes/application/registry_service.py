"""RegistryService — orchestrates registry reads/writes with id uniqueness
and JSON Schema validation.

Driving port: register / load. Drives the RegistryReader and
RegistryWriter driven ports. Validates every outcome against the packaged
JSON Schema (``nwave_ai/outcomes/schema.json``) before persistence
(fail-fast on malformed entries — protects the registry contract).

The schema is a PACKAGE RESOURCE, loaded via ``importlib.resources``: it
travels with ``nwave_ai`` into every install. It must never be resolved by
walking out of the package (``__file__.parents[n] / "docs" / ...``) — in an
install that lands in site-packages, where no ``docs/`` tree exists, and
``register`` dies unable to validate (nWave-ai/nWave#63).
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import TYPE_CHECKING, Any

from jsonschema import Draft7Validator, SchemaError
from jsonschema import ValidationError as JsonSchemaValidationError

from nwave_ai.outcomes.domain.outcome import Outcome  # noqa: TC001  # used at runtime
from nwave_ai.outcomes.domain.serialization import outcome_to_dict
from nwave_ai.outcomes.ports.registry_io import (  # noqa: TC001  # runtime DI
    RegistryReader,
    RegistryWriter,
)


if TYPE_CHECKING:
    from nwave_ai.outcomes.application.collision_detector import CollisionReport


_SCHEMA_PACKAGE = "nwave_ai.outcomes"
_SCHEMA_RESOURCE = "schema.json"
_SCHEMA_LABEL = "nwave_ai/outcomes/schema.json"


class DuplicateOutcomeIdError(Exception):
    """Raised when register is called with an id already present.

    Message format: ``duplicate outcome id: <id>`` — stable contract for
    CLI stderr matching (AC-1.b: /duplicate.*OUT-1/).
    """


class InvalidOutcomeError(Exception):
    """Raised when an outcome WAS checked against the schema and failed."""


class SchemaUnavailableError(Exception):
    """Raised when the outcome could NOT be checked at all.

    Distinct from `InvalidOutcomeError` on purpose: that one means "checked,
    and it failed"; this one means "the schema resource was unreadable,
    unparseable, or not a valid draft-07 schema, so nothing was checked". A
    damaged install must never be able to masquerade as a bad outcome — nor an
    unchecked outcome as a validated one.
    """


class UnknownOutcomeIdError(Exception):
    """Raised when a collision check is requested for an id not in registry."""


def load_schema() -> dict[str, Any]:
    """Return the outcomes JSON Schema, read from the packaged resource.

    Every rejection here means the same thing to the caller: nothing can be
    checked. That includes a schema that is *technically* well-formed but
    vacuous — draft-07 permits a boolean schema, and `Draft7Validator(True)`
    accepts EVERYTHING. A validator that passes everything is not a validator;
    it is "cannot check" wearing the face of "checked and fine", which is the
    one outcome this module exists to make impossible. So the schema must be a
    JSON object, and that is asserted, not assumed.

    Raises:
        SchemaUnavailableError: the resource is missing/unreadable, is not
            valid JSON, is not a JSON object, or is not a valid draft-07 schema.
    """
    try:
        raw = (files(_SCHEMA_PACKAGE) / _SCHEMA_RESOURCE).read_text(encoding="utf-8")
        schema = json.loads(raw)
        Draft7Validator.check_schema(schema)
    except (OSError, ModuleNotFoundError, json.JSONDecodeError, SchemaError) as err:
        raise SchemaUnavailableError(
            f"the outcomes schema resource ({_SCHEMA_LABEL}) could not be read: {err}"
        ) from err
    if not isinstance(schema, dict):
        raise SchemaUnavailableError(
            f"the outcomes schema resource ({_SCHEMA_LABEL}) is not a JSON object "
            f"(got {type(schema).__name__}), so it cannot constrain anything"
        )
    return schema


@lru_cache(maxsize=1)
def _load_validator() -> Draft7Validator:
    return Draft7Validator(load_schema())


class RegistryService:
    """Application service — register a new outcome, load all outcomes."""

    def __init__(
        self,
        reader: RegistryReader,
        writer: RegistryWriter,
    ) -> None:
        self._reader = reader
        self._writer = writer

    def register(self, outcome: Outcome) -> None:
        """Append `outcome` after JSON Schema validation and id-uniqueness check.

        Validation runs BEFORE the write, and every failure path raises before
        `append_outcome` is reached: nothing is ever persisted while the caller
        is told all is well.

        Raises:
            SchemaUnavailableError: when the outcome could not be checked at
                all (schema resource unreadable) — nothing is written.
            InvalidOutcomeError: when the outcome was checked and failed.
            DuplicateOutcomeIdError: when the id is already present.
        """
        self._validate_against_schema(outcome)
        self._guard_unique_id(outcome)
        self._writer.append_outcome(outcome)

    def load(self) -> tuple[Outcome, ...]:
        """Return an immutable snapshot of all registered outcomes."""
        return self._reader.read_outcomes()

    def collision_check_for_id(self, outcome_id: str) -> CollisionReport:
        """Run a collision check for `outcome_id` excluding itself from the
        snapshot, so an outcome cannot collide with its own registry entry.

        Drives US-3 aggregate scan over feature-delta.md.

        Raises:
            UnknownOutcomeIdError: when `outcome_id` is not in the registry.
        """
        # Local import keeps the module-level dependency graph minimal and
        # avoids a circular import risk if collision_detector ever imports
        # back from registry_service.
        from nwave_ai.outcomes.application.collision_detector import (
            CollisionDetector,
            TargetShape,
        )

        snapshot = self._reader.read_outcomes()
        target = self._find_outcome(snapshot, outcome_id)
        others = tuple(o for o in snapshot if o.id != outcome_id)
        detector = CollisionDetector()
        return detector.check(
            target=TargetShape(
                input_shape=target.inputs[0].shape if target.inputs else "",
                output_shape=target.output.shape,
                keywords=target.keywords,
            ),
            snapshot=others,
        )

    def _validate_against_schema(self, outcome: Outcome) -> None:
        """Check `outcome` against the schema.

        Only a genuine validation failure is translated. `SchemaUnavailableError`
        from the loader is deliberately NOT caught: "I could not check this"
        must reach the caller as itself, never be flattened into "I checked it
        and it is invalid".
        """
        try:
            _load_validator().validate(outcome_to_dict(outcome))
        except JsonSchemaValidationError as err:
            raise InvalidOutcomeError(
                f"outcome {outcome.id} fails schema: {err.message}"
            ) from err

    def _guard_unique_id(self, outcome: Outcome) -> None:
        existing_ids = tuple(o.id for o in self._reader.read_outcomes())
        if outcome.id in existing_ids:
            raise DuplicateOutcomeIdError(f"duplicate outcome id: {outcome.id}")

    def _find_outcome(self, snapshot: tuple[Outcome, ...], outcome_id: str) -> Outcome:
        for outcome in snapshot:
            if outcome.id == outcome_id:
                return outcome
        raise UnknownOutcomeIdError(f"unknown outcome id: {outcome_id}")
