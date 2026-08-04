"""verify-dispatch-ref-coherence — the git-free dispatch-ref coherence gate.

f-dispatch-template-ssot-reconciliation slice-04. Holds the no-inline-
restatement rule for skill prose against the dispatch SSOT
(``nWave/dispatch/atdd_pure.yaml``): a skill's prose POINTS at its dispatch
mode/lane via a ``dispatch-ref: mode=<mode> lane=<lane>`` anchor instead of
RESTATING the dispatch section bodies inline. The concept is reused from
``des verify-wave-contract-coherence`` (f-wave-contract-coherence slice-02) --
pointer + registry + no-inline-restatement, git-free, target-agnostic -- NOT
its list-diff algorithm (design Decision 5): the dispatch registry declares
``{mode, lane}`` names, not an enumerable gate-stack list to diff prose
against.

The gate reads two real on-disk artifacts -- the skill PROSE (markdown) and
the dispatch REGISTRY (``nWave/dispatch/atdd_pure.yaml``) -- and emits a §17
``GateVerdict`` token on JSON-stdout (ADR-GV-001, the five existing verdicts;
no sixth, no engine). This slice produces three of the five:

* **PASS** -- the prose carries a valid ``dispatch-ref`` pointer whose
  ``mode``/``lane`` both resolve in the registry, and restates nothing inline.
* **FAIL** -- the pointer is missing, the pointed-at mode or lane does not
  resolve, or the prose inline-restates dispatch section bodies (>=2
  CONSECUTIVE canonical section-id bullet items). The diagnostic NAMES the
  offender and points to ``des dispatch`` as the producing tool -- never a
  manual repair.
* **INDETERMINATE** -- the target skill file is missing/unreadable. Degrade-
  LOUD (Invariant 2): a refusal-to-decide, never a silent pass. The
  diagnostic NAMES the unreadable skill file.

Target-machine agnostic: stdlib ``re`` + a narrow line-oriented YAML scan
only -- NO git, NO ``grep`` binary, NO AST, NO ``import yaml`` (the DES bundle
scan forbids it in any bundled ``des`` module; F-D-09). Runs on any Python
3.10+ target.

This gate is ADDITIVE (slice-04 scope): it is NOT wired against the real
``nWave/skills/nw-execute/SKILL.md`` and is NOT part of any always-on gate
stack yet -- a later slice's scope.

Reachable as the registered ``des verify-dispatch-ref-coherence`` subcommand
via the thin :func:`main` driver below; the verdict, not the process exit
code, carries the gate outcome (asymmetric authority -- a PASS is "no
objection found").
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

# The shipped dispatch SSOT for atdd_pure mode -- the default registry the
# gate resolves mode/lane against when ``--dispatch-yaml`` is not supplied.
_DISPATCH_YAML = _REPO_ROOT / "nWave" / "dispatch" / "atdd_pure.yaml"

# The single HTML-comment anchor pair a skill's prose carries: ``mode``
# resolves against the registry's top-level ``mode:`` key, ``lane`` against a
# ``profiles.lane.<lane>:`` entry in the same registry.
_DISPATCH_REF = re.compile(
    r"<!--\s*dispatch-ref:\s*mode=([A-Za-z0-9_-]+)\s+lane=([A-Za-z0-9_-]+)\s*-->"
)

# The registry's top-level ``mode: <value>`` line.
_TOP_LEVEL_MODE = re.compile(r"^mode:\s*(\S+)\s*$")

# The registry's ``  lane:`` block-start line (nested under ``profiles:``) --
# used to scope the lane-name scan to its immediate children only.
_LANE_BLOCK_START = re.compile(r"^(\s*)lane:\s*$")

# A YAML mapping key on its own line (``<key>:``), used both to walk the
# ``profiles.lane.*`` block and to read the ``sections:`` list's ``- id: <id>``
# entries.
_INDENTED_KEY = re.compile(r"^(\s*)([A-Za-z0-9_-]+):\s*$")
_SECTION_ID_LINE = re.compile(r"^\s*-\s*id:\s*([A-Za-z0-9_-]+)\s*$")

# A markdown list item (``- body`` / ``* body``) -- the bullet-list
# re-enumeration shape (reused concept from ``verify_wave_contract_coherence``
# Shape 3): a run of >=2 consecutive bare canonical section-id bullets is the
# dispatch section list pasted into prose instead of pointed-at.
_MARKDOWN_LIST_ITEM = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


@dataclass(frozen=True)
class DispatchRefCoherenceOutcome:
    """The §17 verdict envelope the dispatch-ref coherence check emits.

    ``verdict``    -- the §17 ``GateVerdict`` (one of the five, no sixth).
    ``diagnostic`` -- names the offender on FAIL / the unreadable skill file on
                     INDETERMINATE; empty on PASS.
    """

    verdict: GateVerdict
    diagnostic: str


def evaluate_dispatch_ref_coherence(
    skill_path: Path, dispatch_yaml_path: Path = _DISPATCH_YAML
) -> DispatchRefCoherenceOutcome:
    """Evaluate the dispatch-ref coherence-check for ``skill_path``.

    The check order is load-bearing: the skill-readable probe runs FIRST so
    an unreadable/missing skill file degrades LOUD to INDETERMINATE before
    any FAIL/PASS verdict; then the registry-readable probe (also degrading
    LOUD); then the pointer + mode/lane-resolution + inline-restatement
    checks project onto PASS / FAIL.
    """
    prose_text = _read(skill_path)
    if prose_text is None:
        return _indeterminate(skill_path)

    registry_text = _read(dispatch_yaml_path)
    if registry_text is None:
        return _indeterminate(dispatch_yaml_path)

    pointer = _DISPATCH_REF.search(prose_text)
    if pointer is None:
        return _failed(
            "skill prose is missing a valid `dispatch-ref: mode=<mode> "
            "lane=<lane>` pointer -- the prose must POINT at the dispatch SSOT "
            f"({dispatch_yaml_path}), not omit it. Run `des dispatch` to "
            "generate a dispatch carrying the anchor and paste it in."
        )
    mode_value, lane_value = pointer.group(1), pointer.group(2)

    registry_mode = _registry_mode(registry_text)
    if mode_value != registry_mode:
        return _failed(
            f"the dispatch-ref pointer names mode {mode_value!r} which does not "
            f"resolve against the registry's top-level `mode:` key "
            f"({registry_mode!r}) in {dispatch_yaml_path}. Run `des dispatch` "
            "to regenerate a valid anchor naming a real mode."
        )

    lane_names = _lane_names(registry_text)
    if lane_value not in lane_names:
        return _failed(
            f"the dispatch-ref pointer names lane {lane_value!r} which does not "
            f"resolve against any `profiles.lane.*` entry in {dispatch_yaml_path}. "
            "Run `des dispatch` to regenerate a valid anchor naming a real lane."
        )

    section_ids = _canonical_section_ids(registry_text)
    restated = _inline_restatement(prose_text, section_ids)
    if restated is not None:
        return _failed(
            f"skill prose inline-restates the dispatch section body {restated!r} "
            "(the duplication drift surface) -- point at the dispatch SSOT via "
            f"`dispatch-ref: mode={mode_value} lane={lane_value}` instead of "
            "enumerating section ids inline. Run `des dispatch` to regenerate "
            "the pointer-only prose."
        )

    return DispatchRefCoherenceOutcome(verdict=GateVerdict.PASS, diagnostic="")


# -- check primitives ---------------------------------------------------------


def _registry_mode(registry_text: str) -> str | None:
    """The registry's top-level ``mode:`` value, or None when absent."""
    for line in registry_text.splitlines():
        match = _TOP_LEVEL_MODE.match(line)
        if match is not None:
            return match.group(1)
    return None


def _lane_names(registry_text: str) -> frozenset[str]:
    """The ``profiles.lane.*`` child key names (the resolvable lane set).

    A narrow indentation-scoped scan: find the ``lane:`` block-start line,
    then collect keys at exactly its immediate child indentation until a
    dedent (a non-blank, non-comment line at or above the ``lane:`` line's
    own indentation) ends the block.
    """
    lines = registry_text.splitlines()
    lane_indent: int | None = None
    child_indent: int | None = None
    names: set[str] = set()
    for line in lines:
        if lane_indent is None:
            match = _LANE_BLOCK_START.match(line)
            if match is not None:
                lane_indent = len(match.group(1))
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= lane_indent:
            break
        if child_indent is None:
            child_indent = indent
        if indent == child_indent:
            key_match = _INDENTED_KEY.match(line)
            if key_match is not None:
                names.add(key_match.group(2))
    return frozenset(names)


def _canonical_section_ids(registry_text: str) -> frozenset[str]:
    """The registry's canonical ``sections:`` id set (``- id: <ID>`` lines)."""
    return frozenset(
        match.group(1)
        for line in registry_text.splitlines()
        if (match := _SECTION_ID_LINE.match(line)) is not None
    )


def _inline_restatement(prose_text: str, section_ids: frozenset[str]) -> str | None:
    """The first section id of a run of >=2 consecutive bare bullet-list
    restatements, or None (a single passing mention is explicitly NOT a
    restatement -- AT-4b, the near-miss boundary).

    Reused concept from ``verify_wave_contract_coherence`` Shape 3 (a run of
    consecutive bare-id markdown-list items) -- NOT its list-diff algorithm
    (design Decision 5).
    """
    scanned = _DISPATCH_REF.sub("", prose_text)
    run: list[str] = []
    for line in scanned.splitlines():
        item = _MARKDOWN_LIST_ITEM.match(line)
        body = item.group(1).strip().strip("`").strip() if item is not None else ""
        if body in section_ids:
            run.append(body)
            if len(run) >= 2:
                return run[0]
        else:
            run = []
    return None


# -- verdict constructors -----------------------------------------------------


def _failed(diagnostic: str) -> DispatchRefCoherenceOutcome:
    """A FAIL outcome naming the offender (a confirmable coherence defect)."""
    return DispatchRefCoherenceOutcome(verdict=GateVerdict.FAIL, diagnostic=diagnostic)


def _indeterminate(unreadable_path: Path) -> DispatchRefCoherenceOutcome:
    """An INDETERMINATE outcome -- a target artifact is unreadable (degrade-LOUD)."""
    diagnostic = (
        f"the dispatch-ref coherence gate must read {unreadable_path} and cannot "
        "-- it is missing or unreadable. Degrading LOUD to INDETERMINATE "
        "(Invariant 2): a refusal-to-decide, never a silent pass."
    )
    return DispatchRefCoherenceOutcome(
        verdict=GateVerdict.INDETERMINATE, diagnostic=diagnostic
    )


# -- filesystem helper --------------------------------------------------------


def _read(path: Path) -> str | None:
    """Read a file's text, or None when it is absent / undecodable (the
    unreadable case the INDETERMINATE degrade keys on). Any other OSError
    (resource-class: EMFILE, ENOMEM, EAGAIN...) propagates loudly with its
    real errno -- it must never be swallowed into a fabricated content-drift
    verdict (GDP-6)."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError):
        return None


# -- thin CLI driver (the registered `des verify-dispatch-ref-coherence`) -----


def main(argv: list[str] | None = None) -> int:
    """Drive the coherence-check over a skill's prose + the dispatch registry
    -> print the verdict.

    Emits one JSON line ``{"verdict": <token>, "diagnostic": <str>}`` on
    stdout (the verdict token is the §17 ``GateVerdict.value``). The exit
    code carries the outcome (0 PASS, 1 FAIL, 4 INDETERMINATE) but the
    verdict token is the observable contract.
    """
    args = _build_parser().parse_args(argv)
    outcome = evaluate_dispatch_ref_coherence(args.skill, args.dispatch_yaml)
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
        prog="des verify-dispatch-ref-coherence",
        description=(
            "Git-free dispatch-ref coherence gate: verify a skill's prose "
            "carries a valid `dispatch-ref: mode=<mode> lane=<lane>` pointer "
            "resolving in the dispatch SSOT, restates nothing inline, and "
            "emit a §17 GateVerdict."
        ),
    )
    parser.add_argument(
        "--skill",
        required=True,
        type=Path,
        help="The skill prose (markdown) to scan for the dispatch-ref pointer.",
    )
    parser.add_argument(
        "--dispatch-yaml",
        required=False,
        type=Path,
        default=_DISPATCH_YAML,
        help=(
            "The dispatch SSOT registry to resolve mode/lane against "
            "(default: nWave/dispatch/atdd_pure.yaml)."
        ),
    )
    return parser


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main())
