"""Pure application facts for `PrepareOrdinaryRequest` (ADR-SSOT-002 §4c/4d).

The deterministic `DeliveryId` projection and the lexical shape checks for
the fourteen-line Auto-root ATD dispatch body live here once so
`des.cli.prepare_ordinary_request` (the producer) and
`des.adapters.drivers.hooks.pre_tool_use_handler` (the gate) cannot drift
apart. This is orchestration/application vocabulary (the ATD prompt
envelope), not domain vocabulary. Stdlib-only; no filesystem or network I/O.
"""

from __future__ import annotations

import hashlib


# Twelve named facts, in this exact order, after the architecture header line
# and one blank line.
ATD_BODY_LINE_COUNT = 14

DELIVERY_ID_PREFIX = "auto-"
DELIVERY_ID_HEX_LEN = 16

BUDGET_TABLE: dict[str, tuple[int, int]] = {
    "M": (2_000_000, 30),
    "L": (4_000_000, 60),
}


def compute_delivery_id(value_seed: str) -> str:
    """`auto-` + the first 16 lowercase hex chars of SHA-256(UTF-8 seed).

    No paraphrase, trim or normalization of `value_seed` before hashing --
    the same seed byte-for-byte always yields the same id.
    """
    digest = hashlib.sha256(value_seed.encode("utf-8")).hexdigest()
    return f"{DELIVERY_ID_PREFIX}{digest[:DELIVERY_ID_HEX_LEN]}"


def contract_locator_for(delivery_id: str) -> str:
    """The one admitted deterministic authoring-time locator projection."""
    return f"docs/delivery-contracts/{delivery_id}.json"


def is_lexical_repo_relative_locator(
    locator: str, *, suffix: str, reject_leading_whitespace: bool = False
) -> bool:
    """Lexical repo-relative locator check (no I/O): rejects absolute path,
    `..` traversal, empty segment, wrong suffix."""
    if not locator or not locator.endswith(suffix):
        return False
    if reject_leading_whitespace and (locator[0].isspace() or locator[0] == "\ufeff"):
        return False
    if locator.startswith(("/", "~")) or ":" in locator:
        return False
    return all(part not in ("", "..") for part in locator.split("/"))


def is_lexical_repo_relative_json_locator(locator: str) -> bool:
    """Lexical repo-relative `.json` locator check -- no filesystem I/O."""
    return is_lexical_repo_relative_locator(locator, suffix=".json")


def is_lexical_repo_relative_md_locator(locator: str) -> bool:
    """Lexical repo-relative `.md` locator check, plus BOM/leading-whitespace
    reject since this locator sits at prompt byte zero."""
    return is_lexical_repo_relative_locator(
        locator, suffix=".md", reject_leading_whitespace=True
    )


def is_lexical_markdown_anchor(anchor: str) -> bool:
    """Accept a lowercase Markdown fragment without shell-significant syntax.

    GitHub heading fragments preserve underscores and non-ASCII letters.
    """
    return (
        bool(anchor)
        and anchor == anchor.lower()
        and all(character.isalnum() or character in "-_" for character in anchor)
    )


_ARCH_HEADER_COVERED_PREFIX = "ARCHITECTURE-COVERED: "
ARCH_HEADER_PREFIXES = (_ARCH_HEADER_COVERED_PREFIX,)


def is_valid_arch_header_line(line: str) -> bool:
    """Pure lexical check that `line` is a well-formed
    ARCHITECTURE-COVERED `<path>.md#<anchor>` line -- shape only,
    never reads/parses the referenced doc."""
    matched_prefix = next(
        (prefix for prefix in ARCH_HEADER_PREFIXES if line.startswith(prefix)),
        None,
    )
    if matched_prefix is None:
        return False
    reference = line[len(matched_prefix) :]
    path, separator, anchor = reference.partition("#")
    if not separator:
        return False
    if not is_lexical_repo_relative_md_locator(path):
        return False
    return is_lexical_markdown_anchor(anchor)
