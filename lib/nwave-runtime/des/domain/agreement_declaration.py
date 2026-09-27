"""The closed v2 declaration of one executable agreement and ALL its consumers.

A declaration names a shared CONTRACT and the argv vectors that make it
executable: the producer that really builds an artifact, and EVERY consumer that
really reads it. Nothing here executes anything and nothing here reads source --
this module owns only the grammar, so a malformed declaration is refused BEFORE
any child is spawned.

THE GRAMMAR IS CLOSED. Exactly ``schema_version``, ``contract``, ``producer``
and ``consumers``; each party is exactly ``name`` and ``argv``. An unknown key is
refused rather than ignored: a silently dropped key is a declaration whose
reader and writer disagree about what was promised, which is the exact class of
drift an executable agreement exists to remove.

``consumers`` IS THE SINGLE SOURCE OF TRUTH for who consumes the contract. It
GREW IN PLACE out of v1's singular ``consumer`` -- same file, same module, same
subcommand -- rather than gaining a second list beside it, because two places
claiming who the parties are is the very drift this checker exists to kill. The
cardinality is "one or more", and a non-empty array is required: a declaration
with no consumer describes a contract nobody reads.

``schema_version`` BUMPS 1 -> 2 because the closed key set changed SHAPE. A
version number that silently means two shapes is the same drift in miniature, so
a stale v1 declaration is refused by VERSION with an accurate message rather than
by a confusing unknown-key error about ``consumer``.

CONSUMER NAMES ARE UNIQUE within one declaration. The red terminal names WHICH
consumer refused, and two identically named parties make that naming ambiguous at
exactly the moment it matters most.

EVERY ARGV MUST CARRY ``{artifact}`` -- the producer's and each consumer's. The
token is the only channel by which the artifact reaches a party, so a vector
without it describes a crossing that carries nothing -- and a green verdict over
a crossing that carried nothing is worse than no verdict at all. Refusing it
here, in the grammar, makes that hollow green unrepresentable instead of merely
unlikely.

A PARTY'S LANGUAGE IS NEVER DECLARED -- ONLY MEASURED. There is no key here for
it and there will not be one: the crossing reports the absolute executable that
really produced each verdict, and a declared language would be a second, unchecked
claim about a party that the executable itself already answers. That is also why
``schema_version`` STAYS 2 -- nothing new is declared, so every committed v2
declaration stays readable.

``consumers`` IS THE WHOLE MEASURED POPULATION, AND THE TERMINAL SAYS SO. A
crossing can only execute parties somebody declared, so an UNDECLARED reader of
the same contract is OUT OF REACH of every run driven from this file -- by
construction, not by omission. That limit is not left implicit and it is not a
later value: every terminal states it, naming this file as the one thing that
decides the population and naming the edit that widens it. There is no key here
for undeclared consumers and there will not be one -- a declaration listing who
it does not cover is a claim nobody can execute.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


#: The literal token both argvs must carry. The checker substitutes a
#: run-scoped path it owns for every occurrence, in both vectors.
ARTIFACT_TOKEN = "{artifact}"

#: The only declaration version this reader knows. Bumped from 1 when the
#: singular ``consumer`` grew into the plural ``consumers`` array.
SCHEMA_VERSION = 2

_ROOT_KEYS = frozenset({"schema_version", "contract", "producer", "consumers"})
_PARTY_KEYS = frozenset({"name", "argv"})


class InvalidDeclaration(ValueError):
    """A declaration that is not the closed v1 grammar.

    Carried as a value rather than a crash: the crossing turns it into an
    ``AgreementIndeterminate`` terminal, because an unreadable declaration
    proves nothing about the agreement either way.
    """


@dataclass(frozen=True)
class DeclaredParty:
    """One side of a declared agreement: who it is, and how to execute it."""

    name: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class AgreementDeclaration:
    """One contract, its real producer and EVERY consumer it declares.

    ``consumers`` is non-empty and carries the parties in DECLARATION ORDER,
    which is the order the crossing reaches them and the order it reports them,
    so an operator reading a terminal can line it up against the file by eye.
    """

    schema_version: int
    contract: str
    producer: DeclaredParty
    consumers: tuple[DeclaredParty, ...]


def declaration_from_bytes(raw: bytes) -> AgreementDeclaration:
    """Read a declaration from its STRICT UTF-8 bytes.

    Strict on purpose: a declaration that is only nearly UTF-8 is refused
    rather than repaired with replacement characters, because a repaired argv
    is a different argv from the declared one.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as undecodable:
        raise InvalidDeclaration(
            f"the declaration is not strict UTF-8: {undecodable}"
        ) from None
    return declaration_from_json_text(text)


def declaration_from_json_text(text: str) -> AgreementDeclaration:
    """Read and validate one declaration from its JSON text."""
    try:
        document = json.loads(text)
    except ValueError as malformed:
        raise InvalidDeclaration(f"the declaration is not JSON: {malformed}") from None
    return declaration_from_object(document)


def declaration_from_object(document: object) -> AgreementDeclaration:
    """Validate an already-parsed declaration object against the closed v1 grammar."""
    if not isinstance(document, dict):
        raise InvalidDeclaration(
            f"a declaration is one JSON object, got {_kind(document)}"
        )
    # THE VERSION IS READ FIRST, BEFORE the closed key set. A stale v1 file
    # carries the singular `consumer`, and checking keys first would refuse it
    # with an unknown-key error that sends the operator hunting a typo. The
    # version says what actually happened: the shape changed.
    if "schema_version" not in document:
        raise InvalidDeclaration(
            "declaration is missing required key(s): ['schema_version']"
        )

    version = document["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise InvalidDeclaration(
            f"schema_version must be the integer {SCHEMA_VERSION}, got {_kind(version)}"
        )
    if version != SCHEMA_VERSION:
        raise InvalidDeclaration(
            f"unsupported declaration schema_version {version!r}; "
            f"this reader knows only {SCHEMA_VERSION}"
        )

    _require_exact_keys(document, _ROOT_KEYS, "declaration")

    contract = document["contract"]
    if not isinstance(contract, str) or not contract.strip():
        raise InvalidDeclaration("contract must be a non-empty string")

    return AgreementDeclaration(
        schema_version=version,
        contract=contract,
        producer=_party(document["producer"], "producer"),
        consumers=_consumers(document["consumers"]),
    )


def _consumers(value: object) -> tuple[DeclaredParty, ...]:
    """Validate the non-empty, uniquely named ``consumers`` array.

    Emptiness is refused because a contract nobody reads is not an agreement,
    and duplicate names are refused because the red terminal's whole job is to
    say WHICH consumer refused.
    """
    if not isinstance(value, list) or not value:
        raise InvalidDeclaration(
            "consumers must be a non-empty array of declared consumers: a "
            "contract with no declared consumer crosses to nobody"
        )

    consumers = tuple(
        _party(entry, f"consumers[{position}]") for position, entry in enumerate(value)
    )

    seen: set[str] = set()
    for consumer in consumers:
        if consumer.name in seen:
            raise InvalidDeclaration(
                f"consumer names must be unique within one declaration; "
                f"{consumer.name!r} is declared more than once, which would make "
                f"a refusal ambiguous about which consumer refused"
            )
        seen.add(consumer.name)
    return consumers


def substitute_artifact(argv: tuple[str, ...], artifact_path: str) -> tuple[str, ...]:
    """Replace every ``{artifact}`` occurrence with the checker-owned path.

    Substitution happens in BOTH vectors from the SAME path, which is what makes
    the crossing a crossing: the bytes the consumer reads are the bytes the
    producer wrote, not a re-derivation of them.
    """
    return tuple(part.replace(ARTIFACT_TOKEN, artifact_path) for part in argv)


def _party(value: object, role: str) -> DeclaredParty:
    if not isinstance(value, dict):
        raise InvalidDeclaration(f"{role} must be an object, got {_kind(value)}")
    _require_exact_keys(value, _PARTY_KEYS, role)

    name = value["name"]
    if not isinstance(name, str) or not name.strip():
        raise InvalidDeclaration(f"{role}.name must be a non-empty string")

    argv = value["argv"]
    if not isinstance(argv, list) or not argv:
        raise InvalidDeclaration(f"{role}.argv must be a non-empty array")
    for part in argv:
        if not isinstance(part, str) or not part:
            raise InvalidDeclaration(
                f"every {role}.argv element must be a non-empty string"
            )
    if not any(ARTIFACT_TOKEN in part for part in argv):
        raise InvalidDeclaration(
            f"{role}.argv must carry the {ARTIFACT_TOKEN} token at least once: "
            f"without it the {role} is never handed the artifact, so the "
            f"crossing would carry nothing"
        )
    return DeclaredParty(name=name, argv=tuple(argv))


def _require_exact_keys(
    document: dict[str, object], allowed: frozenset[str], what: str
) -> None:
    present = set(document)
    missing = sorted(allowed - present)
    if missing:
        raise InvalidDeclaration(f"{what} is missing required key(s): {missing}")
    unknown = sorted(present - allowed)
    if unknown:
        raise InvalidDeclaration(f"{what} carries unknown key(s): {unknown}")


def _kind(value: object) -> str:
    return type(value).__name__


__all__ = [
    "ARTIFACT_TOKEN",
    "SCHEMA_VERSION",
    "AgreementDeclaration",
    "DeclaredParty",
    "InvalidDeclaration",
    "declaration_from_bytes",
    "declaration_from_json_text",
    "declaration_from_object",
    "substitute_artifact",
]
