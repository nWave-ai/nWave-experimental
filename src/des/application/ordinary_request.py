"""Pure application facts for `PrepareOrdinaryRequest` (ADR-SSOT-002 §4c/4d).

The deterministic `DeliveryId` projection and the lexical shape checks for
the fourteen-line Auto-root ATD dispatch body, and the four-line Auto-root
PO (value-only) dispatch envelope, live here once so `des.cli.
prepare_ordinary_request` / `des.cli.resolve_charters` (the producers) and
`des.adapters.drivers.hooks.pre_tool_use_handler` (the gate) cannot drift
apart. This is orchestration/application vocabulary (the ATD/PO prompt
envelopes), not domain vocabulary. Stdlib-only aside from one narrow,
explicit stdin byte read (no filesystem or network I/O, no path resolution).
"""

from __future__ import annotations

import hashlib
import json
import sys


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


def read_value_seed_text() -> str | None:
    """Raw UTF-8 stdin bytes to EOF, decoded strictly. `None` on invalid or
    empty UTF-8 -- the caller reports the exact WHAT/WHY/HOW. Shared by
    every producer that consumes an immutable VALUE-SEED on stdin
    (`des prepare-ordinary-request`, `des resolve-charters`) so the one
    read/decode rule cannot drift between them."""
    raw = sys.stdin.buffer.read()
    if not raw:
        return None
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


# Four named facts, in this exact order, the ONLY Auto-root PO dispatch
# envelope: value-only, no ARCHITECTURE-COVERED anchor (`nw-product-owner`
# disqualifies itself as charter author the moment its own context carries
# one -- ADR-SSOT-002 §2 authority typing, §4c single-author route). Emitted
# verbatim by `des resolve-charters` on `AUTHOR` so the root pastes it,
# never hand-composes it.
_PO_DELIVERY_ID_LINE_PREFIX = "DELIVERY-ID: "
_PO_NAMESPACE_LINE_PREFIX = "NAMESPACE: "
_PO_ROOT_LINE_PREFIX = "ROOT: "
_PO_VALUE_SEED_LINE_PREFIX = "VALUE-SEED: "
PO_ENVELOPE_LINE_PREFIXES = (
    _PO_DELIVERY_ID_LINE_PREFIX,
    _PO_NAMESPACE_LINE_PREFIX,
    _PO_ROOT_LINE_PREFIX,
    _PO_VALUE_SEED_LINE_PREFIX,
)
PO_ENVELOPE_LINE_COUNT = len(PO_ENVELOPE_LINE_PREFIXES)


def build_po_envelope(
    *, delivery_id: str, namespace: str, root: str, value_seed: str
) -> str:
    """The exact four-line value-only Auto-root PO dispatch envelope,
    reusing the SAME VALUE-SEED JSON-string encoding
    `des prepare-ordinary-request` already uses for its own OUTCOME/
    VALUE-SEED lines -- one encoding rule, not a second template."""
    value_seed_json = json.dumps(value_seed, ensure_ascii=False)
    return "\n".join(
        [
            f"{_PO_DELIVERY_ID_LINE_PREFIX}{delivery_id}",
            f"{_PO_NAMESPACE_LINE_PREFIX}{namespace}",
            f"{_PO_ROOT_LINE_PREFIX}{root}",
            f"{_PO_VALUE_SEED_LINE_PREFIX}{value_seed_json}",
        ]
    )


def is_well_formed_po_envelope(prompt: str) -> bool:
    """Pure lexical check that `prompt` is exactly the four-line envelope
    `build_po_envelope` emits: the four facts, in that exact order, each
    non-empty, VALUE-SEED a well-formed non-empty JSON string literal --
    and, defense in depth, no ARCHITECTURE-COVERED-shaped line anywhere
    (PO's own role logic disqualifies itself the instant one is present in
    its context, regardless of where it sits)."""
    lines = prompt.split("\n")
    if len(lines) != PO_ENVELOPE_LINE_COUNT:
        return False
    for line, prefix in zip(lines, PO_ENVELOPE_LINE_PREFIXES, strict=True):
        if not line.startswith(prefix) or len(line) <= len(prefix):
            return False
    value_seed_json = lines[-1][len(_PO_VALUE_SEED_LINE_PREFIX) :]
    try:
        decoded_value_seed = json.loads(value_seed_json)
    except json.JSONDecodeError:
        return False
    if not isinstance(decoded_value_seed, str) or not decoded_value_seed:
        return False
    return not any(prefix.rstrip() in prompt for prefix in ARCH_HEADER_PREFIXES)
