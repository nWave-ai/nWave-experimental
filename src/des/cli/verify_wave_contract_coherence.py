"""verify-wave-contract-coherence — the git-free wave-contract coherence gate.

f-wave-contract-coherence slice-02 (ADR-FLOW-006 D7, brief §5). Holds the
no-inline-restatement rule for wave prose: a wave's command/skill prose POINTS at
its canonical wave-contract registry entry (``nWave/waves/<wave>.yaml``) via
``gates-ref`` / ``outputs-ref`` markers instead of RESTATING the gate stack /
[REF]-section list inline. The drift surface (a config fact copied into prose)
becomes a mechanical veto instead of an LLM-adherence hope.

The gate reads two real on-disk artifacts — the wave PROSE (markdown) and the
wave-contract REGISTRY (``<waves-dir>/<wave>.yaml``) — and emits a §17
``GateVerdict`` token on JSON-stdout (ADR-GV-001, the five existing verdicts; NO
sixth, NO engine, per ADR-FLOW-006 D7/D9). Slice-02 produces three of the five:

* **PASS** — the prose carries valid ``gates-ref`` + ``outputs-ref`` pointers,
  restates nothing inline, the referenced wave resolves in BOTH SSOTs
  (``gate_stack`` AND ``output_contract``), and every ``gate_id`` resolves to the
  catalog.
* **FAIL** — a pointer is missing, the prose restates a bare catalog ``gate_id``
  inline, the registry is incomplete (missing an SSOT), or a ``gate_id`` is an
  orphan (not in the catalog). The diagnostic NAMES the offender.
* **INDETERMINATE** — the registry the gate must read is unreadable (absent /
  undecodable). Degrade-LOUD (Invariant 2): a refusal-to-decide, never a silent
  green. The diagnostic NAMES the unreadable registry's wave.

Target-machine agnostic (Invariant 4): stdlib ``re`` + a narrow line-oriented YAML
scan only — NO git, NO ``grep`` binary, NO AST, NO ``import yaml`` (the DES bundle
scan forbids it in any bundled ``des`` module; F-D-09). The catalog ``gate_id``
set the inline scan and the orphan check both use is read from
``nWave/gates/_catalog.yaml`` by the same narrow line scan. Runs on any Python
3.10+ target.

Reachable as the registered ``des verify-wave-contract-coherence`` subcommand via
the thin :func:`main` driver below; the verdict, not the process exit code,
carries the gate outcome (asymmetric authority — a PASS is "no objection found").
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from des.domain.gate_outcome import GateVerdict


# src/des/cli/<this file> -> parents[3] = REPO_ROOT
_REPO_ROOT = Path(__file__).resolve().parents[3]

# The shipped gate catalog — the SSOT for the catalog gate_id set. A bare gate_id
# token from this set appearing in wave prose is the duplication drift surface the
# inline scan vetoes; a gate_id in a registry gate_stack absent from this set is an
# orphan. Read by the same narrow stdlib line scan (no import yaml).
_CATALOG_PATH = _REPO_ROOT / "nWave" / "gates" / "_catalog.yaml"

# The two HTML-comment pointer markers wave prose carries (brief §4). Each names
# the wave whose registry entry the prose points at.
_GATES_REF = re.compile(r"<!--\s*gates-ref:\s*([A-Za-z0-9_-]+)\s*-->")
_OUTPUTS_REF = re.compile(r"<!--\s*outputs-ref:\s*([A-Za-z0-9_-]+)\s*-->")

# A ``gate_id: <id>`` line in a registry gate_stack / the catalog gates list.
_GATE_ID_LINE = re.compile(r"^\s*-?\s*gate_id:\s*([A-Za-z0-9_-]+)\s*$")

# A markdown list item (``- body`` / ``* body``) — used to recognise a gate-stack
# enumeration written as a bullet list of bare catalog gate_ids (ADR-003 D1 shape 2).
_MARKDOWN_LIST_ITEM = re.compile(r"^\s*[-*]\s+(.+?)\s*$")

# A backtick-code span (`` `...` ``) — Shape 2's genuine-enumeration signal
# (F-COHERENCE-GATE-PRECISION). A wave's gate-stack re-enumerated inline is always
# written as backtick-code (the registry's `gate_id` values pasted as code, e.g.
# "runs `a` then `b`"); a common-English-word catalog gate_id (`dispatch`,
# `feature-end`, ...) used as ordinary running-prose vocabulary is bare, unbackticked
# text. Restricting the Shape-2 tally to backtick-wrapped occurrences keeps the
# command-form (`des <gate-id>`) and artifact-noun (`roadmap.json`) exclusions intact
# (they still apply inside a span) while removing the command/common-word collision.
_BACKTICK_SPAN = re.compile(r"`([^`]+)`")

# A top-level YAML key (zero-indent ``key:``) — used to detect the presence of the
# two SSOT blocks (``gate_stack`` / ``output_contract``) in a registry file.
_TOP_LEVEL_KEY = re.compile(r"^([A-Za-z0-9_-]+):\s*$")


@dataclass(frozen=True)
class CoherenceOutcome:
    """The §17 verdict envelope the coherence-check emits (the gate boundary DTO).

    ``verdict``    — the §17 ``GateVerdict`` (one of the five, no sixth).
    ``diagnostic`` — names the offender on FAIL / the unreadable registry on
                     INDETERMINATE; empty on PASS.
    """

    verdict: GateVerdict
    diagnostic: str


def evaluate_coherence(
    wave: str,
    prose_path: Path,
    waves_dir: Path,
    catalog_path: Path = _CATALOG_PATH,
) -> CoherenceOutcome:
    """Evaluate the coherence-check for ``wave`` over its prose + registry.

    ``catalog_path`` isolates the catalog gate_id read (default: the live repo
    catalog, today's behavior) -- mirrors the ``waves_dir`` isolation already in
    place for the registry read.

    The check order is load-bearing: the registry-readable probe runs FIRST so an
    unreadable registry degrades LOUD to INDETERMINATE before any prose verdict;
    then the pointer + inline-restatement + both-SSOTs + catalog-resolution checks
    project onto PASS / FAIL.
    """
    registry_path = waves_dir / f"{wave}.yaml"
    registry_text = _read(registry_path)
    if registry_text is None:
        return _indeterminate(wave, registry_path)

    prose_text = _read(prose_path) or ""

    pointer_failure = _missing_pointer(prose_text, wave)
    if pointer_failure is not None:
        return _failed(pointer_failure)

    catalog_gate_ids = _catalog_gate_ids(catalog_path)

    restatement = _inline_restatement(prose_text, catalog_gate_ids)
    if restatement is not None:
        return _failed(
            f"wave prose restates the bare catalog gate_id {restatement!r} inline "
            f"(the duplication drift surface) -- point at the registry via "
            f"`gates-ref: {wave}` instead of enumerating gate_ids in prose."
        )

    ssot_failure = _missing_ssot(registry_text, wave)
    if ssot_failure is not None:
        return _failed(ssot_failure)

    orphan = _orphan_gate_id(registry_text, catalog_gate_ids)
    if orphan is not None:
        return _failed(
            f"the registry gate_stack for wave {wave!r} names gate_id {orphan!r} "
            f"which does not resolve to the gate catalog (orphan gate_id)."
        )

    return CoherenceOutcome(verdict=GateVerdict.PASS, diagnostic="")


# -- check primitives ---------------------------------------------------------


def _missing_pointer(prose_text: str, wave: str) -> str | None:
    """A diagnostic naming a missing/mismatched pointer, or None when both resolve.

    The prose must carry BOTH a ``gates-ref`` and an ``outputs-ref`` marker, and
    each must name the wave under check (a pointer at a different wave is a
    mismatch, not a valid pointer).
    """
    gates_ref = _GATES_REF.search(prose_text)
    outputs_ref = _OUTPUTS_REF.search(prose_text)
    if gates_ref is None or gates_ref.group(1) != wave:
        return (
            f"wave prose is missing a valid `gates-ref: {wave}` pointer -- the prose "
            f"must POINT at the registry, not restate the gate stack inline."
        )
    if outputs_ref is None or outputs_ref.group(1) != wave:
        return (
            f"wave prose is missing a valid `outputs-ref: {wave}` pointer -- the "
            f"prose must POINT at the registry, not restate the output contract."
        )
    return None


def _inline_restatement(
    prose_text: str, catalog_gate_ids: frozenset[str]
) -> str | None:
    """The first gate_id of a *structured gate-stack enumeration* restated in the
    prose, or None (ADR-003 D1 — enumeration, not command/artifact mention).

    The clause flags only the duplication drift surface: a wave's gate stack
    re-enumerated inline (the registry block pasted into prose). It does NOT flag a
    catalog gate_id that merely appears as a token in running prose — a ``des
    <gate-id>`` command being invoked, a single mention, or the ``roadmap`` artifact
    noun. The pointer markers themselves are stripped first (a ``gates-ref: discuss``
    marker is the cure, not a restatement).

    A *structured gate-stack enumeration* is recognised by ANY of three shapes:

    1. a ``gate_id: <id>`` YAML-list line — the registry block pasted verbatim into
       prose (reuses :data:`_GATE_ID_LINE`, the module constant at the top);
    2. a single line naming >=2 DISTINCT bare catalog gate_ids — the inline-sentence
       stack restatement (``the gate-out stack runs `a` then `b```);
    3. a run of >=2 consecutive markdown-list items, each a bare catalog gate_id —
       the bullet-list re-enumeration of ``gate_stack``.

    A *bare* token is the retained word-boundary token scan (ADR-003 D2 ADD-not-mutate:
    the boundary scan is RETAINED as the per-candidate inner test, narrowed in
    application scope) EXCLUDING the two mention forms ADR-003 D1 keeps PASSing: a
    ``des <gate-id>`` invocation (the gate_id is preceded by ``des ``) and an artifact
    file-name stem (the gate_id is followed by ``.``, e.g. ``roadmap.json``). Pure
    ``re`` only (TextSearch floor, ADR-LA-001 tier-3 — NEVER the ``grep`` binary).
    """
    scanned = _GATES_REF.sub("", prose_text)
    scanned = _OUTPUTS_REF.sub("", scanned)
    lines = scanned.splitlines()

    # Shape 1 — a `gate_id: <id>` YAML-list line (registry block pasted into prose).
    for line in lines:
        yaml_line = _GATE_ID_LINE.match(line)
        if yaml_line is not None and yaml_line.group(1) in catalog_gate_ids:
            return yaml_line.group(1)

    # Shape 2 — a single line naming >=2 distinct bare catalog gate_ids, restricted to
    # backtick-code occurrences (the genuine-enumeration signal; see _BACKTICK_SPAN).
    for line in lines:
        distinct = _distinct_bare_gate_ids(line, catalog_gate_ids)
        if len(distinct) >= 2:
            return distinct[0]

    # Shape 3 — a run of >=2 consecutive bare-gate_id markdown-list items.
    run: list[str] = []
    for line in lines:
        item = _MARKDOWN_LIST_ITEM.match(line)
        body = item.group(1).strip().strip("`").strip() if item is not None else ""
        if body in catalog_gate_ids:
            run.append(body)
            if len(run) >= 2:
                return run[0]
        else:
            run = []
    return None


def _distinct_bare_gate_ids(line: str, catalog_gate_ids: frozenset[str]) -> list[str]:
    """The distinct catalog gate_ids appearing as bare tokens on ``line``, in order.

    A token counts ONLY when it sits inside a backtick-code span (F-COHERENCE-GATE-
    PRECISION) -- the genuine-enumeration signal (see :data:`_BACKTICK_SPAN`). A
    common-word catalog gate_id (``dispatch``, ``feature-end``, ...) mentioned as
    ordinary running prose is never backticked and so never tallies here -- only the
    registry's re-enumerated ``gate_id`` values, pasted as code, are. Within a span, a
    token is bare when the retained word-boundary scan matches AND it is neither a
    ``des <gate-id>`` invocation (``des `` immediately before) nor an artifact stem
    (``.`` immediately after) — the two mention forms ADR-003 D1 keeps PASSing.
    """
    found: dict[str, int] = {}
    for span in _BACKTICK_SPAN.finditer(line):
        span_text = span.group(1)
        span_start = span.start(1)
        for gate_id in catalog_gate_ids:
            for match in re.finditer(
                rf"(?<![\w-]){re.escape(gate_id)}(?![\w-])", span_text
            ):
                local_start = match.start()
                absolute_start = span_start + local_start
                if line[max(0, absolute_start - 4) : absolute_start] == "des ":
                    continue
                if match.end() < len(span_text) and span_text[match.end()] == ".":
                    continue
                found.setdefault(gate_id, absolute_start)
                break
    return [gate_id for gate_id, _ in sorted(found.items(), key=lambda kv: kv[1])]


def _missing_ssot(registry_text: str, wave: str) -> str | None:
    """A diagnostic when the registry lacks an SSOT block, or None when both present.

    The referenced wave must resolve in BOTH SSOTs: the registry file carries a
    top-level ``gate_stack`` key AND a top-level ``output_contract`` key.
    """
    top_keys = {
        match.group(1)
        for line in registry_text.splitlines()
        if (match := _TOP_LEVEL_KEY.match(line)) is not None
    }
    missing = [key for key in ("gate_stack", "output_contract") if key not in top_keys]
    if missing:
        return (
            f"the wave-contract registry for wave {wave!r} is incomplete -- the "
            f"referenced wave must resolve in BOTH SSOTs; missing: "
            f"{', '.join(missing)}."
        )
    return None


def _orphan_gate_id(registry_text: str, catalog_gate_ids: frozenset[str]) -> str | None:
    """The first registry gate_id absent from the catalog, or None when all resolve."""
    for line in registry_text.splitlines():
        match = _GATE_ID_LINE.match(line)
        if match is not None and match.group(1) not in catalog_gate_ids:
            return match.group(1)
    return None


def _catalog_gate_ids(catalog_path: Path = _CATALOG_PATH) -> frozenset[str]:
    """The catalog gate_id set, read by the narrow stdlib line scan (no import yaml).

    ``catalog_path`` defaults to the live repo catalog (today's behavior) --
    override to isolate the read from the live repo file (mirrors the
    ``waves_dir`` override on the registry read).
    """
    text = _read(catalog_path) or ""
    return frozenset(
        match.group(1)
        for line in text.splitlines()
        if (match := _GATE_ID_LINE.match(line)) is not None
    )


# -- verdict constructors -----------------------------------------------------


def _failed(diagnostic: str) -> CoherenceOutcome:
    """A FAIL outcome naming the offender (a confirmable coherence defect)."""
    return CoherenceOutcome(verdict=GateVerdict.FAIL, diagnostic=diagnostic)


def _indeterminate(wave: str, registry_path: Path) -> CoherenceOutcome:
    """An INDETERMINATE outcome — the registry is unreadable (degrade-LOUD)."""
    diagnostic = (
        f"the wave-contract registry for wave {wave!r} is unreadable "
        f"({registry_path}) -- the gate must read it to resolve the pointer and "
        f"cannot. Degrading LOUD to INDETERMINATE (Invariant 2): a refusal-to-decide, "
        f"never a silent green."
    )
    return CoherenceOutcome(verdict=GateVerdict.INDETERMINATE, diagnostic=diagnostic)


# -- filesystem helper --------------------------------------------------------


def _read(path: Path) -> str | None:
    """Read a file's text, or None when it is absent / undecodable (the unreadable
    case the INDETERMINATE degrade keys on). Any other OSError (resource-class:
    EMFILE, ENOMEM, EAGAIN...) propagates loudly with its real errno -- it must
    never be swallowed into a fabricated content-drift verdict (GDP-6)."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError):
        return None


# -- thin CLI driver (the registered `des verify-wave-contract-coherence`) -----


def main(argv: list[str] | None = None) -> int:
    """Drive the coherence-check over a wave's prose + registry → print the verdict.

    Emits one JSON line ``{"verdict": <token>, "diagnostic": <str>}`` on stdout (the
    verdict token is the §17 ``GateVerdict.value``). The exit code carries the
    outcome (0 PASS, 1 FAIL, 4 INDETERMINATE) but the verdict token is the
    observable contract.
    """
    args = _build_parser().parse_args(argv)
    outcome = evaluate_coherence(
        args.wave, args.prose, args.waves_dir, args.catalog_path
    )
    print(
        json.dumps({"verdict": outcome.verdict.value, "diagnostic": outcome.diagnostic})
    )
    return _EXIT_BY_VERDICT.get(outcome.verdict, 1)


_EXIT_BY_VERDICT: dict[GateVerdict, int] = {
    GateVerdict.PASS: 0,
    GateVerdict.FAIL: 1,
    GateVerdict.INDETERMINATE: 4,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des verify-wave-contract-coherence",
        description=(
            "Git-free wave-contract coherence gate: verify the wave prose carries "
            "valid gates-ref + outputs-ref pointers, restates nothing inline, and "
            "the referenced wave resolves in both SSOTs; emit a §17 GateVerdict."
        ),
    )
    parser.add_argument(
        "--wave",
        required=True,
        help="The wave id under check (e.g. `discuss`).",
    )
    parser.add_argument(
        "--prose",
        required=True,
        type=Path,
        help="The wave prose (markdown) to scan for pointers + inline restatement.",
    )
    parser.add_argument(
        "--waves-dir",
        required=True,
        type=Path,
        help="The directory holding the wave-contract registry files (<wave>.yaml).",
    )
    parser.add_argument(
        "--catalog-path",
        required=False,
        type=Path,
        default=_CATALOG_PATH,
        help=(
            "The gate catalog file to read the gate_id set from "
            "(default: the live repo catalog, nWave/gates/_catalog.yaml)."
        ),
    )
    return parser


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main())
