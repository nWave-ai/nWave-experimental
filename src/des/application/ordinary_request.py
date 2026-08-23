"""Pure application facts for `PrepareOrdinaryRequest` (ADR-SSOT-002 §4c/4d).

The deterministic `DeliveryId` projection and the lexical shape checks for
the fourteen-line Auto-root ATD dispatch body, and the six-line Auto-root
PO (value-only) dispatch envelope, live here once so `des.cli.
prepare_ordinary_request` / `des.cli.resolve_charters` (the producers) and
`des.adapters.drivers.hooks.pre_tool_use_handler` (the gate) cannot drift
apart. This is orchestration/application vocabulary (the ATD/PO prompt
envelopes), not domain vocabulary. Stdlib-only aside from one narrow,
explicit stdin byte read (no filesystem or network I/O, no path resolution).

SF friction report 2026-08-20, item 7: the PO envelope used to carry only
DELIVERY-ID/NAMESPACE/ROOT/VALUE-SEED -- a fresh `nw-product-owner`,
mandated to consume it verbatim and never infer, correctly refused
INDETERMINATE because the independently-resolved `EXAMINE=true` and
`Discover=Missing|Empty` facts its own Dispatch Boundary names were not
observable anywhere in its context. Root cannot hand-add them (the hook's
shape gate blocks any non-producer-emitted prompt) and PO cannot infer
them (source-blind, no re-verification tool). Representation fix, not a
new validator: the producer now carries both resolved facts IN the
envelope, so AUTHOR itself proves them -- EXAMINE/DISCOVER are
orchestration-state facts (already independently resolved before this
producer ever runs), not an architecture-authority anchor, so carrying
them does not reintroduce the contamination the four-line, value-only
shape was built to remove (2026-08-18, `6a02facc3`).
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


# Six named facts, in this exact order, the ONLY Auto-root PO dispatch
# envelope: value-only, no ARCHITECTURE-COVERED anchor (`nw-product-owner`
# disqualifies itself as charter author the moment its own context carries
# one -- ADR-SSOT-002 §2 authority typing, §4c single-author route). EXAMINE
# and DISCOVER are orchestration-state facts already independently resolved
# by `des resolve-charters` BEFORE this envelope is ever built (AUTHOR only
# exists when examine=true and Discover=Missing|Empty) -- carrying them here
# lets PO's own Dispatch Boundary preconditions be read directly from its
# context instead of trusted on faith with no observable evidence (SF
# friction report 2026-08-20, item 7). Emitted verbatim by `des
# resolve-charters` on `AUTHOR` so the root pastes it, never hand-composes
# it.
_PO_DELIVERY_ID_LINE_PREFIX = "DELIVERY-ID: "
_PO_NAMESPACE_LINE_PREFIX = "NAMESPACE: "
_PO_ROOT_LINE_PREFIX = "ROOT: "
_PO_EXAMINE_LINE_PREFIX = "EXAMINE: "
_PO_DISCOVER_LINE_PREFIX = "DISCOVER: "
_PO_VALUE_SEED_LINE_PREFIX = "VALUE-SEED: "
PO_ENVELOPE_LINE_PREFIXES = (
    _PO_DELIVERY_ID_LINE_PREFIX,
    _PO_NAMESPACE_LINE_PREFIX,
    _PO_ROOT_LINE_PREFIX,
    _PO_EXAMINE_LINE_PREFIX,
    _PO_DISCOVER_LINE_PREFIX,
    _PO_VALUE_SEED_LINE_PREFIX,
)
PO_ENVELOPE_LINE_COUNT = len(PO_ENVELOPE_LINE_PREFIXES)

#: The ONLY two `DISCOVER` values this envelope can ever carry --
#: `_resolve_charter_namespace` (`des.cli._charter_resolution`) maps
#: exactly `_Missing`/`_Empty` to `_Author`; `_Valid` resolves to REUSE and
#: `_Invalid` to BLOCK, neither of which ever reaches this envelope.
PO_ENVELOPE_DISCOVER_TOKENS = ("Missing", "Empty")


def build_po_envelope(
    *,
    delivery_id: str,
    namespace: str,
    root: str,
    examine: bool,
    discover: str,
    value_seed: str,
) -> str:
    """The exact six-line value-only Auto-root PO dispatch envelope,
    reusing the SAME VALUE-SEED JSON-string encoding
    `des prepare-ordinary-request` already uses for its own OUTCOME/
    VALUE-SEED lines -- one encoding rule, not a second template.

    `discover` must be one of `PO_ENVELOPE_DISCOVER_TOKENS` -- the caller
    passes the SAME resolved fact its own Resolve algebra already produced,
    never a re-derived or guessed value."""
    if discover not in PO_ENVELOPE_DISCOVER_TOKENS:
        raise ValueError(
            f"discover must be one of {PO_ENVELOPE_DISCOVER_TOKENS!r}, got {discover!r}"
        )
    value_seed_json = json.dumps(value_seed, ensure_ascii=False)
    return "\n".join(
        [
            f"{_PO_DELIVERY_ID_LINE_PREFIX}{delivery_id}",
            f"{_PO_NAMESPACE_LINE_PREFIX}{namespace}",
            f"{_PO_ROOT_LINE_PREFIX}{root}",
            f"{_PO_EXAMINE_LINE_PREFIX}{'true' if examine else 'false'}",
            f"{_PO_DISCOVER_LINE_PREFIX}{discover}",
            f"{_PO_VALUE_SEED_LINE_PREFIX}{value_seed_json}",
        ]
    )


def is_well_formed_po_envelope(prompt: str) -> bool:
    """Pure lexical check that `prompt` is exactly the six-line envelope
    `build_po_envelope` emits: the six facts, in that exact order, each
    non-empty, EXAMINE a boolean token, DISCOVER one of
    `PO_ENVELOPE_DISCOVER_TOKENS`, VALUE-SEED a well-formed non-empty JSON
    string literal -- and, defense in depth, no ARCHITECTURE-COVERED-shaped
    line anywhere (PO's own role logic disqualifies itself the instant one
    is present in its context, regardless of where it sits)."""
    lines = prompt.split("\n")
    if len(lines) != PO_ENVELOPE_LINE_COUNT:
        return False
    for line, prefix in zip(lines, PO_ENVELOPE_LINE_PREFIXES, strict=True):
        if not line.startswith(prefix) or len(line) <= len(prefix):
            return False
    examine_value = lines[3][len(_PO_EXAMINE_LINE_PREFIX) :]
    if examine_value not in ("true", "false"):
        return False
    discover_value = lines[4][len(_PO_DISCOVER_LINE_PREFIX) :]
    if discover_value not in PO_ENVELOPE_DISCOVER_TOKENS:
        return False
    value_seed_json = lines[-1][len(_PO_VALUE_SEED_LINE_PREFIX) :]
    try:
        decoded_value_seed = json.loads(value_seed_json)
    except json.JSONDecodeError:
        return False
    if not isinstance(decoded_value_seed, str) or not decoded_value_seed:
        return False
    return not any(prefix.rstrip() in prompt for prefix in ARCH_HEADER_PREFIXES)


# Eight named facts, in this exact order, the ONLY Auto-root PO charter-
# REVISION dispatch envelope (SF friction report 2026-08-20 follow-up: an
# existing, structurally valid namespace whose recipe a source-blind
# reviewer faulted VALUE-side had no PO-owned correction route -- `des
# resolve-charters` correctly returns REUSE, existence is not reviewed
# validity, and a hand-composed PO dispatch is correctly
# CHARTER-AUTHOR-DISQUALIFIED). `CHARTER-CURRENT` carries the existing
# charter's full text AS DATA from the producer, so the Write-only PO
# rewrites it applying `CITATION` without ever reading the destination --
# the charter is value-side authority, not source, so source-blindness is
# intact. Emitted verbatim by `des revise-charter-round`; the root pastes
# it, never hand-composes it.
PO_REVISION_ENVELOPE_DISCOVER_TOKEN = "ExistingNeedsRevision"
_PO_CHARTER_REVISION_ROUND_LINE_PREFIX = "CHARTER-REVISION-ROUND: "
_PO_CITATION_LINE_PREFIX = "CITATION: "
_PO_CHARTER_CURRENT_LINE_PREFIX = "CHARTER-CURRENT: "
PO_REVISION_ENVELOPE_LINE_PREFIXES = (
    _PO_DELIVERY_ID_LINE_PREFIX,
    _PO_NAMESPACE_LINE_PREFIX,
    _PO_ROOT_LINE_PREFIX,
    _PO_EXAMINE_LINE_PREFIX,
    _PO_DISCOVER_LINE_PREFIX,
    _PO_CHARTER_REVISION_ROUND_LINE_PREFIX,
    _PO_CITATION_LINE_PREFIX,
    _PO_CHARTER_CURRENT_LINE_PREFIX,
)
PO_REVISION_ENVELOPE_LINE_COUNT = len(PO_REVISION_ENVELOPE_LINE_PREFIXES)


def build_po_revision_envelope(
    *,
    delivery_id: str,
    namespace: str,
    root: str,
    charter_round: int,
    charter_round_bound: int,
    citation: str,
    charter_current: str,
) -> str:
    """The exact eight-line value-only Auto-root PO charter-revision
    dispatch envelope, reusing the SAME JSON-string encoding the ordinary
    envelope already uses for VALUE-SEED -- one encoding rule, not a second
    template. EXAMINE is fixed `true` and DISCOVER is fixed
    `ExistingNeedsRevision`: a revision only ever exists for an
    examine-true delivery whose namespace was already discovered valid."""
    if not (1 <= charter_round <= charter_round_bound):
        raise ValueError(
            f"charter_round must satisfy 1 <= n <= {charter_round_bound}, "
            f"got {charter_round}"
        )
    citation_json = json.dumps(citation, ensure_ascii=False)
    charter_current_json = json.dumps(charter_current, ensure_ascii=False)
    return "\n".join(
        [
            f"{_PO_DELIVERY_ID_LINE_PREFIX}{delivery_id}",
            f"{_PO_NAMESPACE_LINE_PREFIX}{namespace}",
            f"{_PO_ROOT_LINE_PREFIX}{root}",
            f"{_PO_EXAMINE_LINE_PREFIX}true",
            f"{_PO_DISCOVER_LINE_PREFIX}{PO_REVISION_ENVELOPE_DISCOVER_TOKEN}",
            f"{_PO_CHARTER_REVISION_ROUND_LINE_PREFIX}"
            f"{charter_round}/{charter_round_bound}",
            f"{_PO_CITATION_LINE_PREFIX}{citation_json}",
            f"{_PO_CHARTER_CURRENT_LINE_PREFIX}{charter_current_json}",
        ]
    )


def _is_well_formed_round_pair(value: str) -> bool:
    """`<n>/<N>`, both positive base-10 integers without sign, whitespace
    or leading zeros, `n <= N` -- lexical only. The BOUND `N` is never
    re-checked against the producer's own constant here: this only refuses
    a value the producer could never have emitted."""
    parts = value.split("/")
    if len(parts) != 2:
        return False
    n_text, bound_text = parts
    if not (n_text.isdigit() and bound_text.isdigit()):
        return False
    if n_text.lstrip("0") != n_text or bound_text.lstrip("0") != bound_text:
        return False
    return 1 <= int(n_text) <= int(bound_text)


def _is_non_empty_json_string_literal(text: str) -> bool:
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(decoded, str) and bool(decoded)


def is_well_formed_po_revision_envelope(prompt: str) -> bool:
    """Pure lexical check that `prompt` is exactly the eight-line envelope
    `build_po_revision_envelope` emits: the eight facts, in that exact
    order, each non-empty, EXAMINE exactly `true`, DISCOVER exactly
    `ExistingNeedsRevision`, CHARTER-REVISION-ROUND a well-formed `n/N`
    pair, CITATION and CHARTER-CURRENT well-formed non-empty JSON string
    literals -- and, defense in depth, no ARCHITECTURE-COVERED-shaped line
    anywhere (PO's own role logic disqualifies itself the instant one is
    present in its context, regardless of where it sits)."""
    lines = prompt.split("\n")
    if len(lines) != PO_REVISION_ENVELOPE_LINE_COUNT:
        return False
    for line, prefix in zip(lines, PO_REVISION_ENVELOPE_LINE_PREFIXES, strict=True):
        if not line.startswith(prefix) or len(line) <= len(prefix):
            return False
    if lines[3] != f"{_PO_EXAMINE_LINE_PREFIX}true":
        return False
    if lines[4] != f"{_PO_DISCOVER_LINE_PREFIX}{PO_REVISION_ENVELOPE_DISCOVER_TOKEN}":
        return False
    round_value = lines[5][len(_PO_CHARTER_REVISION_ROUND_LINE_PREFIX) :]
    if not _is_well_formed_round_pair(round_value):
        return False
    citation_json = lines[6][len(_PO_CITATION_LINE_PREFIX) :]
    charter_current_json = lines[7][len(_PO_CHARTER_CURRENT_LINE_PREFIX) :]
    if not _is_non_empty_json_string_literal(citation_json):
        return False
    if not _is_non_empty_json_string_literal(charter_current_json):
        return False
    return not any(prefix.rstrip() in prompt for prefix in ARCH_HEADER_PREFIXES)
