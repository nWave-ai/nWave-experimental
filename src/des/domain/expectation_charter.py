"""One canonical, source-bound expectation charter per selected value.

The charter is a five-section public artifact: Intent, Preconditions, Charter,
Expected observations (oracle), and an append-only Session log.  Its Intent
section embeds a deterministic source fingerprint over the persisted value's
own observation, scope identity and position, so a later reuse can detect a
drifted persisted value before it is silently reused.

Nothing here reads the filesystem or invokes a provider: this module owns only
the byte-exact canonical shape and its source fingerprint, so an application
producer can classify a namespace and construct or validate a member without a
second, drifting spelling of "what a charter looks like".
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date

from des.domain.document_scope import DocumentScope, Epic, Feature, Project, Slice


class ExpectationCharterInvalid(ValueError):
    """One canonical charter's bytes do not match the closed five-section shape."""


@dataclass(frozen=True, slots=True)
class ExpectationCharter:
    """One parsed canonical charter's complete typed facts."""

    value: int
    source_sha256: str
    intent: str
    public_start_recipe: str
    exploration: str
    positive_observations: tuple[str, ...]
    negative_observation: str
    session_log_rows: tuple[str, ...] = ()


def namespace_directory(scope: DocumentScope) -> str:
    """The repository-relative directory owning every direct value-N.md member."""
    if isinstance(scope, Project):
        return "docs/product/expectations/_project"
    if isinstance(scope, Epic):
        return f"docs/product/expectations/_epic/{scope.epic_id}"
    if isinstance(scope, Slice):
        return f"docs/product/expectations/_slice/{scope.feature_id}/{scope.slice_id}"
    if isinstance(scope, Feature):
        return f"docs/product/expectations/{scope.feature_id}"
    raise ValueError("an explicit document scope is required")


def member_path(scope: DocumentScope, value: int) -> str:
    """The canonical repository-relative path of one direct value member."""
    return f"{namespace_directory(scope)}/value-{value}.md"


_MEMBER_NAME = re.compile(r"\Avalue-([1-9][0-9]*)\.md\Z")


def member_value(name: str) -> int | None:
    """The canonical value position a direct entry name encodes, or ``None``."""
    match = _MEMBER_NAME.fullmatch(name)
    return int(match.group(1)) if match is not None else None


def _scope_fingerprint(scope: DocumentScope) -> dict[str, object]:
    if isinstance(scope, Project):
        return {"feature_id": None, "id": None, "kind": "project", "slice_id": None}
    if isinstance(scope, Epic):
        return {
            "feature_id": None,
            "id": scope.epic_id,
            "kind": "epic",
            "slice_id": None,
        }
    if isinstance(scope, Slice):
        return {
            "feature_id": scope.feature_id,
            "id": None,
            "kind": "slice",
            "slice_id": scope.slice_id,
        }
    if isinstance(scope, Feature):
        return {
            "feature_id": scope.feature_id,
            "id": None,
            "kind": "feature",
            "slice_id": None,
        }
    raise ValueError("an explicit document scope is required")


def source_fingerprint_sha256(
    observation: str, scope: DocumentScope, value: int
) -> str:
    """The deterministic SHA-256 binding one charter to its persisted source."""
    source = {
        "observation": observation,
        "scope": _scope_fingerprint(scope),
        "value": value,
    }
    encoded = json.dumps(
        source, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def canonical_bytes(charter: ExpectationCharter) -> bytes:
    """The complete, exact five-section canonical charter bytes."""
    positives = "".join(f"- {item}\n" for item in charter.positive_observations)
    rows = "".join(f"{row}\n" for row in charter.session_log_rows)
    text = (
        "## Intent\n\n"
        f"Value: {charter.value}\n"
        f"Source SHA-256: {charter.source_sha256}\n"
        f"{charter.intent}\n\n"
        "## Preconditions\n\n"
        f"{charter.public_start_recipe}\n\n"
        "## Charter\n\n"
        f"{charter.exploration}\n\n"
        "## Expected observations (oracle)\n\n"
        f"{positives}"
        f"- Negative: {charter.negative_observation}\n\n"
        "## Session log (append-only)\n\n"
        "| date | examiner | verdict | observations |\n"
        "|------|----------|---------|--------------|\n"
        f"{rows}"
    )
    return text.encode("utf-8")


_SESSION_ROW = re.compile(
    r"\A\| \d{4}-\d{2}-\d{2} \| [^|\n]+ \| "
    r"(?:ACCEPTED|REJECTED|INDETERMINATE) \| [^|\n]+ \|\Z"
)
_DOCUMENT = re.compile(
    r"\A## Intent\n\n"
    r"Value: (?P<value>\d+)\n"
    r"Source SHA-256: (?P<source>[0-9a-f]{64})\n"
    r"(?P<intent>.+?)\n\n"
    r"## Preconditions\n\n"
    r"(?P<recipe>.+?)\n\n"
    r"## Charter\n\n"
    r"(?P<exploration>.+?)\n\n"
    r"## Expected observations \(oracle\)\n\n"
    r"(?P<positives>.*?)"
    r"- Negative: (?P<negative>.+?)\n\n"
    r"## Session log \(append-only\)\n\n"
    r"\| date \| examiner \| verdict \| observations \|\n"
    r"\|------\|----------\|---------\|--------------\|\n"
    r"(?P<rows>(?:\|[^\n]*\n)*)\Z",
    re.DOTALL,
)


def parse_canonical(data: bytes) -> ExpectationCharter:
    """The typed facts of one canonical charter, or why its bytes are invalid."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ExpectationCharterInvalid(
            f"charter bytes are not UTF-8: {error}"
        ) from None
    match = _DOCUMENT.fullmatch(text)
    if match is None:
        raise ExpectationCharterInvalid(
            "charter bytes do not match the closed five-section canonical shape"
        )
    positive_text = match.group("positives")
    if int(match.group("value")) < 1:
        raise ExpectationCharterInvalid("value position must be positive")
    if not positive_text.startswith("- "):
        raise ExpectationCharterInvalid("positive observation bullets are missing")
    positives = tuple(
        item for item in positive_text[2:].removesuffix("\n").split("\n- ")
    )
    if any(not item.strip() for item in positives):
        raise ExpectationCharterInvalid("a positive observation bullet is blank")
    row_lines = [line for line in match.group("rows").splitlines() if line]
    for row in row_lines:
        if not _SESSION_ROW.fullmatch(row):
            raise ExpectationCharterInvalid(f"malformed session log row: {row!r}")
        cells = row[2:-2].split(" | ")
        if len(cells) != 4 or not cells[1].strip() or not cells[3].strip():
            raise ExpectationCharterInvalid(
                f"session log row has a blank cell: {row!r}"
            )
        try:
            date.fromisoformat(row[2:12])
        except ValueError:
            raise ExpectationCharterInvalid(
                f"session log row has an invalid date: {row!r}"
            ) from None
    for field in ("intent", "recipe", "exploration", "negative"):
        if not match.group(field).strip():
            raise ExpectationCharterInvalid(f"{field} must not be blank")
    charter = ExpectationCharter(
        value=int(match.group("value")),
        source_sha256=match.group("source"),
        intent=match.group("intent"),
        public_start_recipe=match.group("recipe"),
        exploration=match.group("exploration"),
        positive_observations=positives,
        negative_observation=match.group("negative"),
        session_log_rows=tuple(row_lines),
    )
    if canonical_bytes(charter) != data:
        raise ExpectationCharterInvalid("charter bytes are not canonical")
    return charter
