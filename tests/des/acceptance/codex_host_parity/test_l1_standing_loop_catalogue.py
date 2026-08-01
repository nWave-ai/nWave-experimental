"""Active-RED L1 contract for the standing-loop JSON catalogue.

@feature-codex-host-parity
@slice-l1

This module drives one future pure production boundary only:
``des.application.standing_loop_catalogue.StandingLoopCatalogue``.  The
dynamic import is intentional: until L1 supplies that boundary, each scenario
fails as an actionable assertion during test execution rather than failing at
collection or replacing production with a test-owned parser/renderer.

Closed refusal vocabulary pinned by this contract (ATD handoff item 3)::

    CATALOGUE_UNPARSABLE         catalogue bytes are not JSON at all
    SCHEMA_VERSION_UNSUPPORTED   discriminator is not the ratified v1 value
    SCHEMA_VALIDATION_FAILED     closed-schema breach: unknown field at ANY
                                 depth, invalid enum, or missing required fact
    V1_POPULATION_MISMATCH       ``loops`` is not exactly ten records
    V1_ORDER_MISMATCH            declared ``order`` values reordered or gapped
    V1_ID_TUPLE_MISMATCH         ordered ID tuple is not the ratified tuple
    LOOP_ID_UNKNOWN              lookup key is not one of the ten literal IDs
    MARKDOWN_STALE               marked block no longer projects the JSON
    MARKDOWN_BLOCK_ABSENT        marked block delimiters are missing
    MARKDOWN_BLOCK_REPEATED      a delimiter occurs more than once
    MARKDOWN_BLOCK_MISNESTED     END precedes BEGIN

Cross-record law precedence is part of the contract, because several mutations
break more than one law at once: population is decided first, then declared
order, then the ordered ID tuple.  The discriminator law precedes the closed
schema: a ``schema_version`` that is absent or blank is contracted to
``SCHEMA_VERSION_UNSUPPORTED``, never ``SCHEMA_VALIDATION_FAILED``.

Two contract statements this file makes explicit, because production must
satisfy them and the ATD does not spell them out:

* The generated row for a record NAMES its ratified ID.  The ATD lists the
  disclosure facts (title, purpose, cadence/effect/cost/isolation/stop) without
  requiring the ID in the block; this contract adds it, because a fact can only
  be bound to the record that owns it if the body carries a per-record anchor.
  Each of the ten literal IDs must appear exactly once, in ratified order.
* Each record declares a ``disclosure`` object carrying the seven facts named by
  the ATD, and every one of those values is projected VERBATIM into that
  record's section of the generated body.

Honesty notes -- assertions deliberately weaker than their heading suggests:

* ``test_l1_bootstrap_freezes_legacy_ordinal_and_title_evidence`` cannot pin the
  pre-migration Markdown BYTES.  The bootstrap is a one-time migration act and
  its source is the very file L1 turns into a generated disclosure, so reading
  that file at test time would be circular.  What holds the honesty instead is a
  frozen literal table (ID, legacy ordinal, discriminating keywords) plus an
  INJECTIVITY assertion -- each keyword set must match exactly one record -- so a
  shuffled, re-slugged, or invented bootstrap is still killed.
* ``test_l1_loader_reads_only_json_and_schema_never_markdown`` bounds its read
  universe to repo-relative NON-``.py`` reads outside ``.venv``.  Interpreter and
  import-machinery reads are outside that universe, so that leg alone cannot see
  a loader smuggling catalogue facts through an imported ``.py`` module.  What
  closes that route is behavioural, not observational: identity and order are
  pinned by the ordered tuple and the independently computed digest, and every
  DISCLOSED fact is pinned by the fact-change leg, which requires the looked-up
  record and the re-rendered section to carry the exact changed value.  A second
  catalogue in Python agrees with the JSON only until the JSON changes.
* Every non-string lookup key is contracted to ``LOOP_ID_UNKNOWN`` rather than a
  separate type refusal: the closed rule is "anything that is not one of the ten
  literal IDs is unknown", and a second code would add vocabulary the ATD does
  not declare.
* The v2 route is checked as a per-ID DISPOSITION SLOT, not as a mapping.  L1
  implements no v2 catalogue, so no mapping exists to verify: calling this leg a
  bijection check would claim a strength it cannot have.
* Record-level key names are frozen only where the ATD freezes them (``id``,
  ``order``, ``action_id``, ``trigger_id``, ``effect_class``, ``roles``,
  ``skills``, ``disclosure`` and the seven disclosure facts).  For the cadence,
  context and limits GROUPS the ATD names no literal keys, so the declared-fact
  sweep is seeded from what the SSOT declares at run time; a fact the SSOT never
  declares is outside this contract.
* Two ATD validator laws are NOT pinned here and remain open: "no duplicate role
  or skill within a record", and "coherent effect/isolation/budget
  combinations".  Emptiness of a declared role/skill value IS pinned.
"""

from __future__ import annotations

import builtins
import contextlib
import functools
import hashlib
import io
import json
import os
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


pytestmark = [pytest.mark.acceptance]


_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_CATALOGUE_PATH = (
    _PROJECT_ROOT
    / "nWave"
    / "data"
    / "orchestrator-affordance"
    / "standing-loops.v1.json"
)
_SCHEMA_PATH = (
    _PROJECT_ROOT / "nWave" / "schemas" / "standing-loop-catalogue.v1.schema.json"
)
_MARKDOWN_PATH = (
    _PROJECT_ROOT
    / "nWave"
    / "data"
    / "orchestrator-affordance"
    / "00-standing-loops.md"
)
_EXPECTED_SCHEMA_VERSION = "standing-loop-catalogue.v1"

# Frozen literal tuple -- never generated.  A comprehension would agree with any
# implementation that generates IDs the same way, including one that re-slugs
# them; only literals pin the ratified population.
_EXPECTED_LOOP_IDS = (
    "standing-loop-01",
    "standing-loop-02",
    "standing-loop-03",
    "standing-loop-04",
    "standing-loop-05",
    "standing-loop-06",
    "standing-loop-07",
    "standing-loop-08",
    "standing-loop-09",
    "standing-loop-10",
)

# Frozen bootstrap evidence: (ratified id, legacy ordinal, discriminating
# keywords).  Keywords must ALL appear in the record and must match exactly one
# record, which is what makes the legacy-to-v1 mapping injective under test.
_LEGACY_BOOTSTRAP: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("standing-loop-01", 1, ("cycle",)),
    ("standing-loop-02", 2, ("worktree",)),
    ("standing-loop-03", 3, ("parallel",)),
    ("standing-loop-04", 4, ("throughput",)),
    ("standing-loop-05", 5, ("failure",)),
    ("standing-loop-06", 6, ("source", "tech")),
    ("standing-loop-07", 7, ("drain", "tech")),
    ("standing-loop-08", 8, ("source", "bugfix")),
    ("standing-loop-09", 9, ("drain", "bugfix")),
    ("standing-loop-10", 10, ("design", "wave")),
)

# Title slugs of the ten REAL loops, literal.  These are the aliases a
# slug-regenerating implementation would produce; every one of them must be
# refused as an identity.
_LEGACY_TITLE_SLUGS = (
    "deliver-the-complete-epic-feature-slice-cycle",
    "reconcile-abandoned-worktrees",
    "find-parallel-work",
    "self-check-swarm-throughput",
    "require-what-why-how-failure-reports",
    "source-tech-debt",
    "drain-tech-debt",
    "source-the-bugfix-queue",
    "drain-the-bugfix-queue",
    "require-upstream-design-waves",
    "deliver-complete-cycle",
)

_NON_CANONICAL_IDS = (
    "1",
    "01",
    "10",
    "0",
    "11",
    "Loop 1/10",
    "Loop 10/10",
    "loop 1/10",
    "standing_loop_01",
    "standing_loop_10",
    "loop-01",
    "loop-1",
    "loop-10",
    "standing-loop-1",
    "standing-loop-001",
    "standing-loop-0",
    "standing-loop-11",
    "standing-loop-99",
    "STANDING-LOOP-01",
    "Standing-Loop-01",
    " standing-loop-01",
    "standing-loop-01 ",
    "standing-loop-01\n",
    "",
    "   ",
)

_NON_STRING_KEYS: tuple[Any, ...] = (
    1,
    10,
    0,
    -1,
    1.0,
    True,
    None,
    ("standing-loop-01",),
    ["standing-loop-01"],
    {"id": "standing-loop-01"},
)

# No positional, ordinal, alias, slug or free-text accessor may exist: the only
# admitted identity API is exact lookup by one of the ten literal IDs.
_FORBIDDEN_ACCESSORS = (
    "lookup_by_position",
    "lookup_by_index",
    "lookup_by_order",
    "lookup_by_ordinal",
    "lookup_by_alias",
    "lookup_by_slug",
    "lookup_by_title",
    "lookup_by_name",
    "lookup",
    "index",
    "select_loop_at",
    "loop_at",
    "get_loop_at",
    "by_position",
    "by_index",
    "by_ordinal",
    "by_slug",
    "by_title",
    "by_alias",
    "resolve_alias",
    "find",
    "search",
    "__getitem__",
)

_REQUIRED_METHODS = (
    "load_and_validate",
    "lookup_by_id",
    "render_markdown_block",
    "write_markdown_block",
    "verify_markdown_block",
)

_BEGIN_PATTERN = re.compile(
    rb"<!-- standing-loop-catalogue:v1 BEGIN sha256=[0-9a-f]{64} -->"
)
_END_MARKER = b"<!-- standing-loop-catalogue:v1 END -->"
_DIGEST_PATTERN = re.compile(rb"sha256=([0-9a-f]{64})")

# The seven operator-facing facts the ATD names for the disclosure object.  Every
# one of them must be declared per record AND projected verbatim into that
# record's section of the generated block.
_REQUIRED_DISCLOSURE_FACTS = (
    "title",
    "purpose",
    "cadence",
    "effect",
    "cost",
    "isolation",
    "stop",
)

# ``<v1-id> -> <disposition>``: the explicit slot a v2 refusal must offer for
# each ratified ID.  Prose that merely lists the IDs gives the operator nowhere
# to record a decision.
_DISPOSITION_SLOT = r"\s*->\s*([^\s,;]+)"
_ANY_DISPOSITION_SLOT = re.compile(r"(standing-loop-\d+)" + _DISPOSITION_SLOT)

_FACT_CHANGE_SUFFIX = " (fact changed by AT-L1-04)"


class _PoisonedRead(BaseException):
    """Raised when production reads a path the contract forbids it to read.

    Derives from ``BaseException`` on purpose: a loader wrapping its work in a
    broad ``except Exception`` must not be able to swallow the poison and turn a
    forbidden Markdown read into an ordinary refusal.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(str(path))
        self.path = path


def _require_artifacts() -> None:
    """Assert the canonical L1 artifacts, never synthesize substitutes in tests."""
    missing = [
        str(path.relative_to(_PROJECT_ROOT))
        for path in (_CATALOGUE_PATH, _SCHEMA_PATH, _MARKDOWN_PATH)
        if not path.is_file()
    ]
    assert not missing, (
        "WHAT: the L1 catalogue contract artifacts are absent. "
        "WHY: acceptance cannot validate a JSON SSOT, schema, and generated disclosure "
        "that have not been produced. "
        "HOW: create only the canonical standing-loops.v1.json and "
        "standing-loop-catalogue.v1.schema.json, then render the marked Markdown block; "
        f"missing={missing}"
    )


def _catalogue_service() -> Any:
    """Load the sole future boundary lazily so absence is an active RED assertion."""
    import importlib

    try:
        module = importlib.import_module("des.application.standing_loop_catalogue")
    except ModuleNotFoundError as error:
        pytest.fail(
            "WHAT: L1 has no production StandingLoopCatalogue boundary. "
            "WHY: tests must validate one JSON-only loader/validator/renderer rather "
            "than invent a test parser or consume Markdown. "
            "HOW: add des.application.standing_loop_catalogue.StandingLoopCatalogue "
            "with load_and_validate, lookup_by_id, render_markdown_block, "
            "write_markdown_block, and verify_markdown_block. "
            f"import_error={error}"
        )

    service_type = getattr(module, "StandingLoopCatalogue", None)
    assert callable(service_type), (
        "WHAT: the L1 production module lacks StandingLoopCatalogue. "
        "WHY: AT-L1 must drive one named pure boundary. "
        "HOW: expose StandingLoopCatalogue from des.application.standing_loop_catalogue."
    )
    service = service_type()
    absent = [
        name for name in _REQUIRED_METHODS if not callable(getattr(service, name, None))
    ]
    assert not absent, (
        "WHAT: the L1 catalogue boundary is incomplete. "
        "WHY: validation, exact-ID lookup, render, write, and stale verification are "
        "one acceptance contract. "
        "HOW: implement the missing methods without adding Markdown loading, aliases, "
        f"or positional lookup; missing_methods={absent}"
    )
    return service


def _canonical_digest(document: object) -> str:
    """Recompute the contract digest independently of production.

    Lowercase sha256 over UTF-8 canonical JSON: recursive key sort, compact
    separators, ``ensure_ascii=False``.  Computing it here is what stops a
    constant-digest implementation from agreeing with itself.
    """
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _catalogue_document() -> Any:
    return json.loads(_CATALOGUE_PATH.read_text(encoding="utf-8"))


def _validated() -> tuple[Any, Any]:
    _require_artifacts()
    service = _catalogue_service()
    validated = service.load_and_validate(_CATALOGUE_PATH, _SCHEMA_PATH)
    assert getattr(validated, "schema_version", None) == _EXPECTED_SCHEMA_VERSION, (
        "WHAT: the validated catalogue does not declare the ratified v1 discriminator. "
        "WHY: v1 is a closed contract and L2 binds to it by name. "
        f"HOW: expose schema_version={_EXPECTED_SCHEMA_VERSION!r} on the validated "
        f"catalogue; got={getattr(validated, 'schema_version', None)!r}"
    )
    assert tuple(getattr(validated, "loop_ids", ())) == _EXPECTED_LOOP_IDS, (
        "WHAT: the validated catalogue does not expose the ratified ordered ID tuple. "
        "WHY: v1 identity is the exact ordered tuple, not a cardinality or a set. "
        f"HOW: return loop_ids={_EXPECTED_LOOP_IDS}; "
        f"got={tuple(getattr(validated, 'loop_ids', ()))}"
    )
    digest = getattr(validated, "digest", None)
    assert isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), (
        "WHAT: the validated catalogue has no canonical SHA-256 digest. "
        "WHY: L2 must bind the JSON population actually validated by L1. "
        f"HOW: expose the lowercase canonical JSON digest; got={digest!r}"
    )
    return service, validated


@functools.lru_cache(maxsize=1)
def _cached_validated() -> tuple[Any, Any]:
    """Load once for property-based runs; exceptions are never cached by lru_cache."""
    return _validated()


def _write_document(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _refusal(action: Callable[[], object]) -> Exception:
    """Require a typed loud refusal instead of accepting a silent fallback."""
    try:
        action()
    except Exception as error:  # the contract accepts one typed refusal family
        code = getattr(error, "code", None)
        assert isinstance(code, str) and code, (
            "WHAT: L1 refused without a typed code. "
            "WHY: schema, identity, and stale-disclosure failures need distinct "
            "remediation. "
            "HOW: raise the closed catalogue refusal type with its non-empty code. "
            f"error_type={type(error).__name__} error={error}"
        )
        return error
    pytest.fail(
        "WHAT: L1 accepted an invalid catalogue/disclosure input. "
        "WHY: v1 is a closed, exact population contract. "
        "HOW: reject the input before rendering or runtime consumption."
    )


def _refusal_code(action: Callable[[], object]) -> str:
    return str(_refusal(action).code)


def _refusal_text(error: Exception) -> str:
    remediation = getattr(error, "remediation", None)
    parts = [str(error)]
    if isinstance(remediation, str):
        parts.append(remediation)
    return " ".join(parts)


@contextlib.contextmanager
def _observed_reads(poisoned: tuple[Path, ...] = ()) -> Iterator[list[Path]]:
    """Record every filesystem read and explode on a forbidden one.

    Patches ``builtins.open``, ``io.open`` and ``os.open``: ``pathlib`` read
    helpers funnel through those, so this covers the routes production can use
    without the test knowing which one it picked.
    """
    opened: list[Path] = []
    forbidden = {path.resolve() for path in poisoned}
    real_builtins_open = builtins.open
    real_io_open = io.open
    real_os_open = os.open

    def _record(target: Any) -> None:
        if isinstance(target, int):
            return
        try:
            resolved = Path(os.fsdecode(target)).resolve()
        except (TypeError, ValueError):
            return
        opened.append(resolved)
        if resolved in forbidden:
            raise _PoisonedRead(resolved)

    def _watched_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        _record(file)
        return real_builtins_open(file, *args, **kwargs)

    def _watched_os_open(path: Any, *args: Any, **kwargs: Any) -> Any:
        _record(path)
        return real_os_open(path, *args, **kwargs)

    builtins.open = _watched_open  # type: ignore[assignment]
    io.open = _watched_open  # type: ignore[assignment]
    os.open = _watched_os_open  # type: ignore[assignment]
    try:
        yield opened
    finally:
        builtins.open = real_builtins_open  # type: ignore[assignment]
        io.open = real_io_open  # type: ignore[assignment]
        os.open = real_os_open  # type: ignore[assignment]


def _data_reads(opened: list[Path]) -> set[str]:
    """Universe of the read assertion: repo-relative, non-interpreter reads."""
    universe: set[str] = set()
    for path in opened:
        try:
            relative = path.relative_to(_PROJECT_ROOT)
        except ValueError:
            continue
        if path.suffix in {".py", ".pyc", ".pth", ".pyi"}:
            continue
        if {".venv", "__pycache__", ".git"} & set(relative.parts):
            continue
        universe.add(relative.as_posix())
    return universe


def _marked_region(document: bytes) -> tuple[bytes, bytes, bytes]:
    """Split only renderer delimiters; never reconstruct loop data from Markdown."""
    begin = _BEGIN_PATTERN.search(document)
    assert begin is not None, "Generated block must begin with the v1 digest marker."
    end_start = document.find(_END_MARKER, begin.end())
    assert end_start >= 0, "Generated block must end with the v1 end marker."
    end = end_start + len(_END_MARKER)
    assert _BEGIN_PATTERN.search(document, begin.end()) is None, (
        "Generated block marker repeats."
    )
    assert document.find(_END_MARKER, end) < 0, "Generated block end marker repeats."
    return document[: begin.start()], document[begin.start() : end], document[end:]


def _marker_digest(document: bytes) -> str:
    match = _DIGEST_PATTERN.search(document)
    assert match is not None, (
        "WHAT: the generated block carries no sha256 marker. "
        "WHY: the disclosure must seal the exact JSON population it projects. "
        "HOW: emit <!-- standing-loop-catalogue:v1 BEGIN sha256=<64 hex> -->."
    )
    return match.group(1).decode("ascii")


def _rendered_bytes(service: Any, validated: Any) -> bytes:
    rendered = service.render_markdown_block(validated)
    return rendered.encode("utf-8") if isinstance(rendered, str) else bytes(rendered)


def _block_body(block: bytes) -> bytes:
    """Block content with both delimiters stripped -- the part a digest cannot fake."""
    begin = _BEGIN_PATTERN.search(block)
    assert begin is not None
    return block[begin.end() : len(block) - len(_END_MARKER)]


# --------------------------------------------------------------------------
# Markdown tamper vectors
# --------------------------------------------------------------------------


def _tamper_digest_marker(document: bytes) -> bytes:
    match = _BEGIN_PATTERN.search(document)
    assert match is not None
    marker = match.group(0)
    digest = _DIGEST_PATTERN.search(marker)
    assert digest is not None
    original = digest.group(1)
    flipped = (b"1" if original[:1] == b"0" else b"0") + original[1:]
    return (
        document[: match.start()]
        + marker.replace(original, flipped, 1)
        + document[match.end() :]
    )


def _tamper_block_body(document: bytes) -> bytes:
    """Change the disclosed text while leaving the sealed marker byte-identical."""
    prefix, block, suffix = _marked_region(document)
    begin = _BEGIN_PATTERN.search(block)
    assert begin is not None
    injected = (
        block[: begin.end()] + b"\nTAMPERED DISCLOSURE LINE\n" + block[begin.end() :]
    )
    return prefix + injected + suffix


def _remove_block_markers(document: bytes) -> bytes:
    prefix, block, suffix = _marked_region(document)
    return prefix + _block_body(block) + suffix


def _remove_begin_marker(document: bytes) -> bytes:
    """Only the opening delimiter is gone: the END marker still stands alone."""
    prefix, block, suffix = _marked_region(document)
    return prefix + _block_body(block) + _END_MARKER + suffix


def _remove_end_marker(document: bytes) -> bytes:
    """Only the closing delimiter is gone: a verifier may run the block to EOF."""
    prefix, block, suffix = _marked_region(document)
    begin = _BEGIN_PATTERN.search(block)
    assert begin is not None
    return prefix + begin.group(0) + _block_body(block) + suffix


def _repeat_begin_marker(document: bytes) -> bytes:
    prefix, block, suffix = _marked_region(document)
    begin = _BEGIN_PATTERN.search(block)
    assert begin is not None
    marker = begin.group(0)
    return (
        prefix + block[: begin.end()] + b"\n" + marker + block[begin.end() :] + suffix
    )


def _repeat_end_marker(document: bytes) -> bytes:
    prefix, block, suffix = _marked_region(document)
    return prefix + block + b"\n" + _END_MARKER + suffix


def _nest_block(document: bytes) -> bytes:
    prefix, block, suffix = _marked_region(document)
    begin = _BEGIN_PATTERN.search(block)
    assert begin is not None
    nested = begin.group(0) + b"\nnested disclosure\n" + _END_MARKER
    return (
        prefix + block[: begin.end()] + b"\n" + nested + block[begin.end() :] + suffix
    )


def _swap_block_markers(document: bytes) -> bytes:
    prefix, block, suffix = _marked_region(document)
    begin = _BEGIN_PATTERN.search(block)
    assert begin is not None
    return prefix + _END_MARKER + _block_body(block) + begin.group(0) + suffix


_MARKDOWN_TAMPERS: tuple[tuple[str, Callable[[bytes], bytes], str], ...] = (
    ("sealed digest flipped", _tamper_digest_marker, "MARKDOWN_STALE"),
    ("body edited under an intact marker", _tamper_block_body, "MARKDOWN_STALE"),
    ("delimiters deleted", _remove_block_markers, "MARKDOWN_BLOCK_ABSENT"),
    ("begin marker deleted only", _remove_begin_marker, "MARKDOWN_BLOCK_ABSENT"),
    ("end marker deleted only", _remove_end_marker, "MARKDOWN_BLOCK_ABSENT"),
    ("begin marker repeated", _repeat_begin_marker, "MARKDOWN_BLOCK_REPEATED"),
    ("end marker repeated", _repeat_end_marker, "MARKDOWN_BLOCK_REPEATED"),
    ("block nested inside itself", _nest_block, "MARKDOWN_BLOCK_REPEATED"),
    ("end precedes begin", _swap_block_markers, "MARKDOWN_BLOCK_MISNESTED"),
)


# --------------------------------------------------------------------------
# JSON mutation vectors
# --------------------------------------------------------------------------


def _clone(document: Any) -> Any:
    return json.loads(json.dumps(document))


def _mutate_zero_loops(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"] = []
    return mutated


def _mutate_one_loop(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"] = mutated["loops"][:1]
    return mutated


def _mutate_nine_loops(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"] = mutated["loops"][:-1]
    return mutated


def _mutate_eleven_loops(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"].append(_clone(mutated["loops"][-1]))
    return mutated


def _mutate_duplicate_id(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"][1]["id"] = mutated["loops"][0]["id"]
    return mutated


def _mutate_changed_id(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"][0]["id"] = "standing-loop-99"
    return mutated


def _mutate_alias_id(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"][0]["id"] = "loop-01"
    return mutated


def _mutate_slug_regenerated_ids(document: Any) -> Any:
    mutated = _clone(document)
    for index, loop in enumerate(mutated["loops"]):
        loop["id"] = _LEGACY_TITLE_SLUGS[index]
    return mutated


def _mutate_reordered_loops(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"][0], mutated["loops"][1] = (
        mutated["loops"][1],
        mutated["loops"][0],
    )
    return mutated


def _mutate_gapped_order(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"][-1]["order"] = 11
    return mutated


def _mutate_v2_version(document: Any) -> Any:
    mutated = _clone(document)
    mutated["schema_version"] = "standing-loop-catalogue.v2"
    return mutated


def _mutate_unknown_root_field(document: Any) -> Any:
    mutated = _clone(document)
    mutated["compatibility_aliases"] = ["loop-1"]
    return mutated


def _mutate_unknown_loop_field(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"][0]["compatibility_alias"] = "loop-1"
    return mutated


def _mutate_missing_required_id(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"][0].pop("id", None)
    return mutated


def _mutate_missing_required_order(document: Any) -> Any:
    mutated = _clone(document)
    mutated["loops"][0].pop("order", None)
    return mutated


def _set_first_key(node: Any, key: str, value: Any) -> bool:
    if isinstance(node, dict):
        if key in node:
            node[key] = value
            return True
        return any(_set_first_key(child, key, value) for child in node.values())
    if isinstance(node, list):
        return any(_set_first_key(child, key, value) for child in node)
    return False


def _mutate_invalid_enum(document: Any) -> Any:
    mutated = _clone(document)
    found = _set_first_key(mutated["loops"][0], "effect_class", "read_write")
    assert found, (
        "WHAT: no effect_class field exists on a loop record. "
        "WHY: effect_class is a declared closed enum of the v1 contract. "
        "HOW: declare effect_class as exactly read_only, cloud_write, or box_write."
    )
    return mutated


_JSON_MUTATIONS: tuple[tuple[str, Callable[[Any], Any], str], ...] = (
    ("zero loops", _mutate_zero_loops, "V1_POPULATION_MISMATCH"),
    ("one loop", _mutate_one_loop, "V1_POPULATION_MISMATCH"),
    ("nine loops", _mutate_nine_loops, "V1_POPULATION_MISMATCH"),
    ("eleven loops", _mutate_eleven_loops, "V1_POPULATION_MISMATCH"),
    ("reordered records", _mutate_reordered_loops, "V1_ORDER_MISMATCH"),
    ("gapped declared order", _mutate_gapped_order, "V1_ORDER_MISMATCH"),
    ("duplicate id", _mutate_duplicate_id, "V1_ID_TUPLE_MISMATCH"),
    ("changed id", _mutate_changed_id, "V1_ID_TUPLE_MISMATCH"),
    ("compatibility alias id", _mutate_alias_id, "V1_ID_TUPLE_MISMATCH"),
    ("slug-regenerated ids", _mutate_slug_regenerated_ids, "V1_ID_TUPLE_MISMATCH"),
    ("v2 discriminator", _mutate_v2_version, "SCHEMA_VERSION_UNSUPPORTED"),
    ("unknown root field", _mutate_unknown_root_field, "SCHEMA_VALIDATION_FAILED"),
    ("unknown nested field", _mutate_unknown_loop_field, "SCHEMA_VALIDATION_FAILED"),
    ("invalid enum", _mutate_invalid_enum, "SCHEMA_VALIDATION_FAILED"),
    ("missing required id", _mutate_missing_required_id, "SCHEMA_VALIDATION_FAILED"),
    (
        "missing required order",
        _mutate_missing_required_order,
        "SCHEMA_VALIDATION_FAILED",
    ),
)


def _object_paths(node: Any, prefix: tuple[Any, ...] = ()) -> Iterator[tuple[Any, ...]]:
    if isinstance(node, dict):
        yield prefix
        for key, value in node.items():
            yield from _object_paths(value, prefix + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _object_paths(value, prefix + (index,))


def _node_at(document: Any, path: tuple[Any, ...]) -> Any:
    node = document
    for step in path:
        node = node[step]
    return node


def _record_id(record: Any) -> Any:
    if isinstance(record, dict):
        return record.get("id")
    return getattr(record, "id", None)


def _record_order(record: Any) -> Any:
    if isinstance(record, dict):
        return record.get("order")
    return getattr(record, "order", None)


def _record_text(record: Any) -> str:
    """Flatten every string leaf of a record for keyword-evidence matching."""
    chunks: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            chunks.append(node)
        elif isinstance(node, dict):
            for key, value in node.items():
                chunks.append(str(key))
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)

    _walk(record)
    return " ".join(chunks).lower()


def _field(node: Any, name: str) -> Any:
    """Read a declared fact whether the record is a mapping or a typed object."""
    if isinstance(node, dict):
        return node.get(name)
    return getattr(node, name, None)


def _disclosure_fact(record: Any, fact: str) -> Any:
    disclosure = _field(record, "disclosure")
    if disclosure is None:
        return None
    return _field(disclosure, fact)


def _change_a_disclosure_fact(record: Any) -> tuple[str, str] | None:
    """Append a marker to one declared disclosure fact; return (fact, new value).

    The exact new value is returned because "the body changed" is not an oracle:
    a renderer that only re-seals a digest line changes the body too.
    """
    disclosure = record.get("disclosure") if isinstance(record, dict) else None
    if not isinstance(disclosure, dict):
        return None
    for fact in _REQUIRED_DISCLOSURE_FACTS:
        current = disclosure.get(fact)
        if isinstance(current, str):
            disclosure[fact] = current + _FACT_CHANGE_SUFFIX
            return fact, disclosure[fact]
    return None


def _decoded_block_body(service: Any, validated: Any) -> str:
    return _block_body(_rendered_bytes(service, validated)).decode("utf-8")


def _record_sections(body: str) -> dict[str, str]:
    """Split the generated body into one section per ratified ID.

    Anchoring on the literal IDs is what binds a disclosed fact to the record
    that owns it: a body-wide keyword search accepts a record whose row was
    dropped as long as the words survive somewhere else in the block.
    """
    starts: list[tuple[str, int]] = []
    for loop_id in _EXPECTED_LOOP_IDS:
        found = [match.start() for match in re.finditer(re.escape(loop_id), body)]
        assert len(found) == 1, (
            f"WHAT: {loop_id!r} occurs {len(found)} times in the generated body. "
            "WHY: the disclosure must name every ratified loop exactly once; a dropped "
            "row still seals a valid digest and verifies against itself, so only the "
            "operator loses the loop, and a repeated one makes the owning record of a "
            "fact ambiguous. "
            f"HOW: emit exactly one row naming {loop_id!r}; offsets={found}"
        )
        starts.append((loop_id, found[0]))

    ordered = sorted(starts, key=lambda item: item[1])
    disclosed_order = [loop_id for loop_id, _offset in ordered]
    assert disclosed_order == list(_EXPECTED_LOOP_IDS), (
        "WHAT: the generated body discloses the ratified IDs in another order. "
        "WHY: the disclosure projects the sealed v1 order; a reordered block tells the "
        "operator a different sequence from the one the catalogue declares. "
        f"HOW: render records in ratified order; got={disclosed_order}"
    )

    sections: dict[str, str] = {}
    for index, (loop_id, start) in enumerate(ordered):
        stop = ordered[index + 1][1] if index + 1 < len(ordered) else len(body)
        sections[loop_id] = body[start:stop]
    return sections


def _required_fact_paths(document: Any) -> list[tuple[Any, ...]]:
    """Every fact the SSOT declares on the root and on one loop record.

    Seeded from the document because the ATD names the field GROUPS but fixes
    literal key names only for part of them; inventing the rest would author a
    contract the design never ratified.  String array ITEMS are included so the
    ATD's "no empty role/skill value" law has a seed.
    """
    paths: list[tuple[Any, ...]] = []
    for prefix in [()] + list(_object_paths(document["loops"][0], ("loops", 0))):
        node = _node_at(document, prefix)
        for key, value in node.items():
            paths.append(prefix + (key,))
            if (
                isinstance(value, list)
                and value
                and all(isinstance(item, str) for item in value)
            ):
                paths.append(prefix + (key, 0))
    return paths


# --------------------------------------------------------------------------
# AT-L1-01 / AT-L1-03 -- ratified population, tuple, and bootstrap evidence
# --------------------------------------------------------------------------


def test_l1_catalogue_v1_is_closed_and_pins_the_ratified_tuple() -> None:
    """AT-L1-01: only the canonical JSON validates to the ten sealed IDs."""
    service, validated = _validated()

    assert validated.schema_version == _EXPECTED_SCHEMA_VERSION
    assert tuple(validated.loop_ids) == _EXPECTED_LOOP_IDS
    assert len(validated.loop_ids) == 10
    assert len(set(validated.loop_ids)) == 10

    expected_digest = _canonical_digest(_catalogue_document())
    assert validated.digest == expected_digest, (
        "WHAT: the exposed digest is not the canonical digest of the SSOT bytes. "
        "WHY: a digest computed by any other rule cannot bind L2 to the validated "
        "population, and a constant digest would agree with itself forever. "
        "HOW: emit lowercase sha256 over UTF-8 canonical JSON (recursive key sort, "
        f"compact separators, ensure_ascii=False); expected={expected_digest} "
        f"got={validated.digest}"
    )

    records = [
        service.lookup_by_id(validated, loop_id) for loop_id in _EXPECTED_LOOP_IDS
    ]
    assert all(record is not None for record in records), (
        "WHAT: an exact ratified ID did not resolve. "
        "WHY: the ten literal IDs are the only admitted identity API. "
        "HOW: resolve every id in the ratified tuple by exact match."
    )
    assert len({id(record) for record in records}) == 10, (
        "WHAT: exact-ID lookup is not injective across the ten ratified IDs. "
        "WHY: two IDs resolving to one record would collapse the sealed population. "
        "HOW: return the distinct record declared for each id."
    )
    returned_ids = [_record_id(record) for record in records]
    assert returned_ids == list(_EXPECTED_LOOP_IDS), (
        "WHAT: exact-ID lookup returned a record whose own id is not the key asked "
        "for. "
        "WHY: a lookup that resolves to a different (or copied) record silently "
        "re-points every downstream consumer at the wrong loop. "
        f"HOW: return the record declared with that exact id; got={returned_ids}"
    )


def test_l1_bootstrap_freezes_legacy_ordinal_and_title_evidence() -> None:
    """AT-L1-03: the one-time bootstrap maps frozen legacy evidence to exact IDs.

    Honesty note: the pre-migration Markdown bytes are NOT re-read here (the
    bootstrap source is the same file L1 turns into a generated disclosure, so
    reading it would be circular).  The frozen literal table below plus the
    injectivity assertion is what holds the honesty: a shuffled, re-slugged, or
    invented bootstrap still fails.
    """
    service, validated = _validated()

    texts = {
        loop_id: _record_text(service.lookup_by_id(validated, loop_id))
        for loop_id in _EXPECTED_LOOP_IDS
    }

    for loop_id, legacy_ordinal, keywords in _LEGACY_BOOTSTRAP:
        declared_order = _record_order(service.lookup_by_id(validated, loop_id))
        assert declared_order == legacy_ordinal, (
            "WHAT: a ratified ID does not carry its frozen legacy ordinal. "
            "WHY: the bootstrap is a one-time migration of the sealed legacy order; "
            "a runtime re-derivation would let the order drift. "
            f"HOW: declare order={legacy_ordinal} on {loop_id}; got={declared_order!r}"
        )

        matches = {
            other_id
            for other_id, text in texts.items()
            if all(keyword in text for keyword in keywords)
        }
        assert matches == {loop_id}, (
            "WHAT: the frozen legacy title evidence does not bind to exactly one "
            "ratified ID. "
            "WHY: the legacy-to-v1 mapping must be total and injective; a shuffled or "
            "invented bootstrap would otherwise pass unnoticed. "
            f"HOW: keep the disclosure of {loop_id} carrying {keywords} and no other "
            f"record carrying all of them; matched={sorted(matches)}"
        )


# --------------------------------------------------------------------------
# AT-L1-07 -- JSON is the sole authority
# --------------------------------------------------------------------------


def test_l1_loader_reads_only_json_and_schema_never_markdown() -> None:
    """AT-L1-07: validation reads the SSOT and its schema, and nothing else.

    Two independent legs: an observed-read universe (what was opened) and a
    poisoned canonical Markdown path (what happens if it is opened anyway).  The
    universe leg alone would be satisfied by a loader that reads the Markdown via
    a route the watcher misses; the poison leg alone would be satisfied by a
    loader that reads a Markdown copy.  Together they pin the authority.
    """
    _require_artifacts()
    service = _catalogue_service()

    with _observed_reads() as opened:
        validated = service.load_and_validate(_CATALOGUE_PATH, _SCHEMA_PATH)

    universe = _data_reads(opened)
    expected = {
        _CATALOGUE_PATH.relative_to(_PROJECT_ROOT).as_posix(),
        _SCHEMA_PATH.relative_to(_PROJECT_ROOT).as_posix(),
    }
    assert universe == expected, (
        "WHAT: load_and_validate read repository data beyond the JSON SSOT and its "
        "schema. "
        "WHY: Markdown (or any other repo artifact) must never be a catalogue "
        "authority; a loader that also parses the disclosure would keep passing a "
        "test that only mutates a Markdown copy. "
        f"HOW: read only {sorted(expected)}; "
        f"extra={sorted(universe - expected)} missing={sorted(expected - universe)}"
    )

    try:
        with _observed_reads(poisoned=(_MARKDOWN_PATH,)):
            poisoned_validated = service.load_and_validate(
                _CATALOGUE_PATH, _SCHEMA_PATH
            )
    except _PoisonedRead as poisoned:
        pytest.fail(
            "WHAT: load_and_validate opened the canonical Markdown disclosure. "
            "WHY: the disclosure is a generated output, never a runtime input. "
            "HOW: derive every loop fact from standing-loops.v1.json plus its schema; "
            f"forbidden_read={poisoned.path}"
        )

    assert tuple(poisoned_validated.loop_ids) == _EXPECTED_LOOP_IDS
    assert poisoned_validated.digest == validated.digest


@pytest.mark.negative_at
def test_l1_markdown_mutation_is_not_a_catalogue_authority(tmp_path: Path) -> None:
    """AT-L1-07: Markdown mutation cannot change JSON catalogue identity or digest."""
    service, before = _validated()
    markdown_copy = tmp_path / "00-standing-loops.md"
    markdown_copy.write_bytes(_MARKDOWN_PATH.read_bytes())
    service.write_markdown_block(markdown_copy, before)
    generated = markdown_copy.read_bytes()
    markdown_copy.write_bytes(_tamper_digest_marker(generated))

    after = service.load_and_validate(_CATALOGUE_PATH, _SCHEMA_PATH)
    assert tuple(after.loop_ids) == _EXPECTED_LOOP_IDS
    assert after.digest == before.digest
    assert after.digest == _canonical_digest(_catalogue_document())
    assert (
        _refusal_code(lambda: service.verify_markdown_block(markdown_copy, after))
        == "MARKDOWN_STALE"
    )


# --------------------------------------------------------------------------
# AT-L1-02 / AT-L1-03 -- closed schema and closed v1 population
# --------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("label", "mutate", "expected_code"),
    [pytest.param(*row, id=row[0]) for row in _JSON_MUTATIONS],
)
def test_l1_refuses_every_v1_schema_and_population_mutation(
    label: str,
    mutate: Callable[[Any], Any],
    expected_code: str,
    tmp_path: Path,
) -> None:
    """AT-L1-02/03: each closed-contract breach refuses with its own typed code."""
    service, _validated_catalogue = _validated()
    mutated_path = tmp_path / "mutated.json"
    _write_document(mutated_path, mutate(_catalogue_document()))

    actual = _refusal_code(
        lambda: service.load_and_validate(mutated_path, _SCHEMA_PATH)
    )
    assert actual == expected_code, (
        f"WHAT: the {label!r} mutation refused with {actual!r}. "
        "WHY: population, declared order, identity tuple, and schema breaches need "
        "distinct remediation; one merged code hides which law broke. "
        f"HOW: refuse {label!r} with {expected_code!r} (law precedence: population, "
        "then declared order, then ID tuple)."
    )


@pytest.mark.negative_at
def test_l1_refuses_a_catalogue_that_is_not_json_at_all(tmp_path: Path) -> None:
    """AT-L1-02: unparsable bytes refuse before any schema or render work."""
    service, _validated_catalogue = _validated()
    broken = tmp_path / "not-json.json"
    broken.write_text("{ this is not json,", encoding="utf-8")

    assert (
        _refusal_code(lambda: service.load_and_validate(broken, _SCHEMA_PATH))
        == "CATALOGUE_UNPARSABLE"
    )


@pytest.mark.negative_at
def test_l1_refuses_an_unknown_field_at_every_object_depth(tmp_path: Path) -> None:
    """AT-L1-02: closure is enforced at every nested object, not only at the root.

    The paths are walked from the real document at run time (they cannot be
    parametrized at collection time without assuming a shape the SSOT has not
    published yet), and every offending path is reported in one message.
    """
    service, _validated_catalogue = _validated()
    document = _catalogue_document()
    paths = [()] + list(_object_paths(document["loops"][0], ("loops", 0)))

    accepted: list[str] = []
    wrong_code: list[str] = []
    for path in paths:
        mutated = _clone(document)
        _node_at(mutated, path)["__at_l1_unknown__"] = "extension"
        mutated_path = tmp_path / ("unknown-" + "-".join(map(str, path)) + ".json")
        _write_document(mutated_path, mutated)
        try:
            service.load_and_validate(mutated_path, _SCHEMA_PATH)
        except Exception as error:
            if getattr(error, "code", None) != "SCHEMA_VALIDATION_FAILED":
                wrong_code.append(f"{path}->{getattr(error, 'code', None)!r}")
            continue
        accepted.append(str(path))

    assert not accepted and not wrong_code, (
        "WHAT: an unknown extension field was tolerated (or mis-typed) at some object "
        "depth. "
        "WHY: v1 is closed at root AND at every nested object; an extension accepted "
        "deep in a record is the smuggling route a root-only check leaves open. "
        "HOW: set additionalProperties=false on every object in the v1 schema and "
        f"refuse with SCHEMA_VALIDATION_FAILED; accepted={accepted} "
        f"wrong_code={wrong_code}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("blank", [False, True], ids=["deleted", "blanked"])
def test_l1_refuses_every_declared_fact_deleted_or_blanked(
    blank: bool,
    tmp_path: Path,
) -> None:
    """AT-L1-02: removing or emptying ANY declared fact is a closed-schema breach.

    Missing-required coverage that stops at ``id`` and ``order`` leaves a schema
    free to declare the cadence, action, capability, semantic, limit and
    disclosure facts optional -- a catalogue could then validate with no cadence,
    no effect class and no disclosure at all.  Every fact the SSOT declares is
    seeded here, at every object depth, in both directions: deleted, and present
    but empty (the ATD's "no empty role/skill/action/trigger/disclosure value"
    law).

    Two declared limits: deleting a string ARRAY ITEM is skipped, because a
    shorter role list is a population question this contract does not decide;
    and a fact the SSOT never declares cannot be swept at all -- the frozen
    disclosure-fact tuple is what stops the disclosed surface from shrinking.
    """
    service, _validated_catalogue = _validated()
    document = _catalogue_document()

    accepted: list[str] = []
    wrong_code: list[str] = []
    for path in _required_fact_paths(document):
        if isinstance(path[-1], int) and not blank:
            continue
        expected = (
            "SCHEMA_VERSION_UNSUPPORTED"
            if path == ("schema_version",)
            else "SCHEMA_VALIDATION_FAILED"
        )
        mutated = _clone(document)
        parent = _node_at(mutated, path[:-1])
        if blank:
            parent[path[-1]] = ""
        else:
            parent.pop(path[-1])
        mutated_path = tmp_path / ("fact-" + "-".join(map(str, path)) + ".json")
        _write_document(mutated_path, mutated)

        try:
            service.load_and_validate(mutated_path, _SCHEMA_PATH)
        except Exception as error:
            code = getattr(error, "code", None)
            if code != expected:
                wrong_code.append(f"{path}->{code!r} (expected {expected})")
            continue
        accepted.append(str(path))

    assert not accepted and not wrong_code, (
        "WHAT: a declared v1 fact could be removed or emptied without the contracted "
        "refusal. "
        "WHY: a required-fact check that only guards id and order lets a catalogue ship "
        "with no cadence, no effect class, no budgets or no disclosure, and the "
        "renderer would then project a record the operator cannot act on. "
        "HOW: declare every fact required (and non-empty) at every object depth in the "
        "v1 schema, refuse with SCHEMA_VALIDATION_FAILED, and keep the discriminator "
        f"law ahead of it; accepted={accepted} wrong_code={wrong_code}"
    )


@pytest.mark.negative_at
def test_l1_refuses_a_document_reconstructed_from_markdown_evidence(
    tmp_path: Path,
) -> None:
    """AT-L1-03: a catalogue rebuilt from disclosure prose is not a v1 catalogue."""
    service, _validated_catalogue = _validated()
    markdown_derived = {
        "schema_version": _EXPECTED_SCHEMA_VERSION,
        "loops": [
            {"id": slug, "order": index + 1}
            for index, slug in enumerate(_LEGACY_TITLE_SLUGS[:10])
        ],
    }
    derived_path = tmp_path / "markdown-derived.json"
    _write_document(derived_path, markdown_derived)

    assert (
        _refusal_code(lambda: service.load_and_validate(derived_path, _SCHEMA_PATH))
        == "SCHEMA_VALIDATION_FAILED"
    )


@pytest.mark.negative_at
def test_l1_v1_mutation_refusal_opens_a_disposition_slot_for_every_v1_id(
    tmp_path: Path,
) -> None:
    """AT-L1-03: the v2 route offers an explicit disposition slot per ratified ID.

    This is NOT a bijection check and does not claim to be one: L1 implements no
    v2 catalogue, so there is no mapping to verify.  What is verifiable is the
    SHAPE of the honest narration -- the refusal names v2 and carries an explicit
    ``<v1-id> -> <disposition>`` slot for exactly the ten ratified IDs, in
    ratified order.  Prose that merely mentions v2 and lists the ID strings reads
    like a plan while leaving the operator nowhere to record a decision, and a
    remediation covering nine IDs silently drops the tenth loop.
    """
    service, _validated_catalogue = _validated()
    mutated_path = tmp_path / "changed-id.json"
    _write_document(mutated_path, _mutate_changed_id(_catalogue_document()))

    error = _refusal(lambda: service.load_and_validate(mutated_path, _SCHEMA_PATH))
    text = _refusal_text(error).lower()
    assert "v2" in text, (
        "WHAT: the v1 identity refusal does not route the operator to v2. "
        "WHY: a population/order/ID change is a versioned migration, never a v1 edit. "
        f"HOW: name the v2 catalogue in the remediation; remediation={text!r}"
    )

    without_slot = [
        loop_id
        for loop_id in _EXPECTED_LOOP_IDS
        if re.search(re.escape(loop_id) + _DISPOSITION_SLOT, text) is None
    ]
    assert not without_slot, (
        "WHAT: the v2 remediation gives some v1 IDs no explicit disposition slot. "
        "WHY: naming an ID in prose states that it exists, not what becomes of it; a "
        "loop with no disposition slot is a loop nobody has to decide about, which is "
        "exactly how a standing loop disappears across a version bump. "
        "HOW: enumerate every v1 id as '<id> -> <disposition>' in the remediation; "
        f"without_slot={without_slot} remediation={text!r}"
    )

    slotted = [loop_id for loop_id, _token in _ANY_DISPOSITION_SLOT.findall(text)]
    assert slotted == list(_EXPECTED_LOOP_IDS), (
        "WHAT: the disposition slots are not exactly the ten ratified IDs in ratified "
        "order. "
        "WHY: an extra or reordered slot means the remediation is describing a "
        "population other than the sealed v1 one. "
        f"HOW: emit one slot per ratified id, in ratified order; got={slotted}"
    )


# --------------------------------------------------------------------------
# Identity API -- only the ten literal IDs
# --------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize("candidate", _NON_CANONICAL_IDS + _LEGACY_TITLE_SLUGS)
def test_l1_lookup_refuses_every_non_literal_identity(candidate: str) -> None:
    """AT-L1-03: ordinals, aliases, slugs and formatting variants are not identities."""
    service, validated = _validated()

    assert candidate not in _EXPECTED_LOOP_IDS
    actual = _refusal_code(lambda: service.lookup_by_id(validated, candidate))
    assert actual == "LOOP_ID_UNKNOWN", (
        f"WHAT: lookup of {candidate!r} refused with {actual!r}. "
        "WHY: the only admitted identities are the ten literal ratified IDs; an "
        "alias, ordinal, or slug accepted here reintroduces the identity drift v1 "
        "was sealed to prevent. "
        "HOW: refuse every non-literal key with LOOP_ID_UNKNOWN."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "candidate", [pytest.param(key, id=repr(key)) for key in _NON_STRING_KEYS]
)
def test_l1_lookup_refuses_every_non_string_identity(candidate: Any) -> None:
    """AT-L1-03: an integer or ordinal object is not a positional selector."""
    service, validated = _validated()

    actual = _refusal_code(lambda: service.lookup_by_id(validated, candidate))
    assert actual == "LOOP_ID_UNKNOWN", (
        f"WHAT: lookup of {candidate!r} refused with {actual!r}. "
        "WHY: accepting an integer key is positional selection wearing the name of "
        "an ID lookup. "
        "HOW: refuse every key that is not one of the ten literal IDs with "
        "LOOP_ID_UNKNOWN."
    )


@settings(max_examples=40, deadline=None)
@given(candidate=st.text(max_size=32))
def test_l1_lookup_admits_no_identity_outside_the_literal_tuple(candidate: str) -> None:
    """AT-L1-03 (@property): the admitted identity set is exactly the ten IDs."""
    service, validated = _cached_validated()

    if candidate in _EXPECTED_LOOP_IDS:
        assert service.lookup_by_id(validated, candidate) is not None
        return
    assert (
        _refusal_code(lambda: service.lookup_by_id(validated, candidate))
        == "LOOP_ID_UNKNOWN"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("accessor", _FORBIDDEN_ACCESSORS)
def test_l1_exposes_no_positional_or_alias_accessor(accessor: str) -> None:
    """AT-L1-03: v1 loop order is sealed metadata, not a runtime selection API."""
    service, _validated_catalogue = _validated()

    assert not hasattr(service, accessor), (
        f"WHAT: L1 exposes {accessor!r}. "
        "WHY: positional, ordinal, alias, slug and free-text selection all bypass the "
        "sealed identity tuple, and any one of them makes the tuple decorative. "
        f"HOW: remove {accessor!r} and require exact JSON-derived loop IDs."
    )


# --------------------------------------------------------------------------
# AT-L1-04 / AT-L1-05 / AT-L1-06 -- render, seal, projection, stale
# --------------------------------------------------------------------------


def test_l1_generated_marker_seals_the_independently_computed_digest() -> None:
    """AT-L1-04: the marker digest is the JSON digest, computed outside production."""
    service, validated = _validated()

    expected = _canonical_digest(_catalogue_document())
    rendered = _rendered_bytes(service, validated)
    sealed = _marker_digest(rendered)

    assert sealed == expected, (
        "WHAT: the rendered block seals a digest that is not the canonical JSON "
        "digest. "
        "WHY: writer and renderer are one service, so a constant (or self-derived) "
        "digest would verify against itself forever; the test computes it separately "
        "precisely to break that circle. "
        f"HOW: seal the canonical digest of standing-loops.v1.json; "
        f"expected={expected} sealed={sealed}"
    )
    assert sealed == validated.digest


def test_l1_generated_block_binds_every_disclosed_fact_to_its_own_record() -> None:
    """AT-L1-05: each record's seven disclosure facts appear verbatim in its section.

    A keyword search over the whole body is not an oracle for this: a renderer
    that drops a record's row keeps passing while its words survive in a footer,
    a heading or another record, and a renderer that prints only titles satisfies
    every keyword the bootstrap table names.  So the body is split into per-record
    sections anchored on the literal IDs, and each declared fact must be found in
    the section of the record that declares it -- swapping two purposes, dropping
    the cadence line, or summarising a record away all fail.
    """
    service, validated = _validated()
    body = _decoded_block_body(service, validated)
    sections = _record_sections(body)

    undeclared: list[str] = []
    unprojected: list[str] = []
    for loop_id in _EXPECTED_LOOP_IDS:
        record = service.lookup_by_id(validated, loop_id)
        for fact in _REQUIRED_DISCLOSURE_FACTS:
            value = _disclosure_fact(record, fact)
            if not isinstance(value, str) or not value.strip():
                undeclared.append(f"{loop_id}.{fact}={value!r}")
                continue
            if value not in sections[loop_id]:
                unprojected.append(f"{loop_id}.{fact}={value!r}")

    assert not undeclared, (
        "WHAT: a record does not declare every mandatory disclosure fact. "
        "WHY: the ATD names title, purpose, cadence, effect, cost, isolation and stop "
        "as the operator-facing facts; a record missing one cannot be acted on, and a "
        "renderer cannot project what the SSOT never declared. "
        f"HOW: declare all of {_REQUIRED_DISCLOSURE_FACTS} on every loop record; "
        f"undeclared={undeclared}"
    )
    assert not unprojected, (
        "WHAT: a declared disclosure fact is absent from its own record's section of "
        "the generated block. "
        "WHY: the block is the only thing the operator reads; a fact held in the JSON "
        "but never printed -- or printed under a different loop -- is a fact the "
        "operator acts on wrongly while every digest and stale check stays green. "
        f"HOW: project every declared disclosure fact verbatim into the row of the "
        f"record that declares it; unprojected={unprojected}"
    )


def test_l1_generated_block_parity_is_idempotent_and_byte_exact(
    tmp_path: Path,
) -> None:
    """AT-L1-05: only the marked block changes and rewriting is a no-op."""
    service, validated = _validated()
    markdown_copy = tmp_path / "00-standing-loops.md"
    markdown_copy.write_bytes(_MARKDOWN_PATH.read_bytes())
    before = markdown_copy.read_bytes()

    service.write_markdown_block(markdown_copy, validated)
    after = markdown_copy.read_bytes()
    before_prefix, _before_block, before_suffix = _marked_region(before)
    after_prefix, after_block, after_suffix = _marked_region(after)
    assert after_prefix == before_prefix
    assert after_suffix == before_suffix
    assert after_block == _rendered_bytes(service, validated)
    service.verify_markdown_block(markdown_copy, validated)

    service.write_markdown_block(markdown_copy, validated)
    assert markdown_copy.read_bytes() == after


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("label", "tamper", "expected_code"),
    [pytest.param(*row, id=row[0]) for row in _MARKDOWN_TAMPERS],
)
def test_l1_stale_and_malformed_disclosure_refuse_with_typed_codes(
    label: str,
    tamper: Callable[[bytes], bytes],
    expected_code: str,
    tmp_path: Path,
) -> None:
    """AT-L1-06: a stale seal, an edited body, and broken markers are distinct."""
    service, validated = _validated()
    markdown_copy = tmp_path / "00-standing-loops.md"
    markdown_copy.write_bytes(_MARKDOWN_PATH.read_bytes())
    service.write_markdown_block(markdown_copy, validated)
    generated = markdown_copy.read_bytes()

    markdown_copy.write_bytes(tamper(generated))
    actual = _refusal_code(
        lambda: service.verify_markdown_block(markdown_copy, validated)
    )
    assert actual == expected_code, (
        f"WHAT: the {label!r} disclosure refused with {actual!r}. "
        "WHY: a verifier that only inspects the marker cannot see an edited body, and "
        "a verifier that merges structure with staleness cannot tell an operator "
        "which repair to make. "
        f"HOW: refuse {label!r} with {expected_code!r}."
    )


@pytest.mark.negative_at
def test_l1_json_fact_change_makes_the_disclosure_stale_and_rerender_differs(
    tmp_path: Path,
) -> None:
    """AT-L1-04/05/06: the full unrendered -> current -> stale -> current cycle."""
    service, validated = _validated()
    markdown_copy = tmp_path / "00-standing-loops.md"
    markdown_copy.write_bytes(_MARKDOWN_PATH.read_bytes())
    service.write_markdown_block(markdown_copy, validated)
    first_render = _rendered_bytes(service, validated)
    service.verify_markdown_block(markdown_copy, validated)

    changed_document = _clone(_catalogue_document())
    changed_record_id = changed_document["loops"][0]["id"]
    change = _change_a_disclosure_fact(changed_document["loops"][0])
    assert change is not None, (
        "WHAT: no declared disclosure fact was found on a loop record. "
        f"WHY: the renderer prints the declared disclosure facts "
        f"({_REQUIRED_DISCLOSURE_FACTS}); without one, a valid fact change cannot be "
        "exercised. "
        "HOW: declare a disclosure object with those facts on every loop record."
    )
    changed_fact, changed_value = change
    changed_path = tmp_path / "changed-fact.json"
    _write_document(changed_path, changed_document)

    changed = service.load_and_validate(changed_path, _SCHEMA_PATH)
    assert tuple(changed.loop_ids) == _EXPECTED_LOOP_IDS
    expected_changed_digest = _canonical_digest(changed_document)
    assert changed.digest == expected_changed_digest
    assert changed.digest != validated.digest, (
        "WHAT: a changed catalogue fact produced the same digest. "
        "WHY: a digest insensitive to content cannot detect a stale disclosure. "
        f"HOW: digest the full canonical document; changed_field={changed_fact!r}"
    )

    served = _disclosure_fact(
        service.lookup_by_id(changed, changed_record_id), changed_fact
    )
    assert served == changed_value, (
        "WHAT: the looked-up record does not carry the exact changed disclosure fact. "
        "WHY: a loader that serves facts from a SECOND catalogue -- a Python constant "
        "module, a frozen table, an in-process cache -- agrees with the JSON right up "
        "to the moment the JSON changes, and the read-universe leg cannot see it "
        "because imported .py reads are outside that universe. "
        f"HOW: derive every served fact from the validated JSON document; "
        f"expected={changed_value!r} got={served!r}"
    )

    assert (
        _refusal_code(lambda: service.verify_markdown_block(markdown_copy, changed))
        == "MARKDOWN_STALE"
    )

    second_render = _rendered_bytes(service, changed)
    assert second_render != first_render
    second_body = _block_body(second_render).decode("utf-8")
    assert changed_value in _record_sections(second_body)[changed_record_id], (
        "WHAT: the re-rendered section of the changed record does not carry the exact "
        "changed value. "
        "WHY: 'the body differs' is not an oracle -- re-sealing a digest line differs "
        "too; only the exact new value proves the operator is shown the fact that "
        f"actually changed. "
        f"HOW: project the changed {changed_fact!r} fact verbatim into the row of "
        f"{changed_record_id!r}; expected={changed_value!r}"
    )

    service.write_markdown_block(markdown_copy, changed)
    service.verify_markdown_block(markdown_copy, changed)
    assert _marked_region(markdown_copy.read_bytes())[1] == second_render
