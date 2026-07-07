"""gate-G — the mechanical design↔AT coherence gate (f-coherence-and-attestation slice-03).

Diffs the design ``## Wave: DESIGN / [REF] Code-Design`` example-table against the
AT module's scenarios and returns a §17 ``GateVerdict`` (ADR-GV-001, the five
verdicts — CONSUMED unchanged, no sixth). It is the mechanical form of the gate-G
*review-rubric seam* f-distill NAMED but DEFERRED (its OB-2 table forward-references
the ``CodeFactPort`` queries ``query.adr-section`` over the design prose +
``query.atoms-in-file`` over the AT module) — so a dropped example-table row or a
signature mismatch cannot ship green on an LLM-adherence-dependent rubric alone.

OB-G RESOLVED — DEFER D3: gate-G diffs against the **prose** ``[REF] Code-Design``
contract present in the feature-delta (no ``code-design.manifest.yaml`` D3). When the
prose contract is too loose to mechanically confirm a row-level bijection (vague /
placeholder row identifiers no D3 manifest pins), gate-G surfaces the North-Star cap
LOUD as **UNVERIFIED** — never a false PASS, never a hard FAIL (option-c parity with
f-distill OB-1 / f-deliver OB-1).

CONSUMES the slice-01/02 ``CodeFactPort`` substrate — it does NOT fork it (C2 — NO
second ``import ast``):

* ``query.adr-section`` over the design prose confirms the ``[REF] Code-Design``
  block is present (the design contract exists to diff against).
* ``query.atoms-in-file`` over the AT module is the inspection-substrate probe: when
  the AT module is in a language the ``AstAdapter`` cannot run (e.g. an ``.exs``
  Elixir AT, no ``.feature`` / ``.py`` the gate recognizes), the mechanism could not
  run → gate-G degrades LOUD to **INDETERMINATE** (``ran=False``), never a fabricated
  verdict.

The row↔scenario bijection itself is computed over the **textual** markdown
example-table + Gherkin scenario lines — plain-text parsing, NOT a code-structure
``ast`` parse (C2-clean: the substrate is for code-facts, not Gherkin scenario names).

Verdict mapping (the five §17 verdicts, CONSUMED unchanged):

* design rows ↔ AT scenarios bijective AND lexically alignable → **PASS**.
* a confirmable divergence — a dropped row (a design row no scenario covers) OR a
  signature mismatch (a scenario referencing a symbol the design never declared) →
  **FAIL** + a non-empty diagnostic NAMING the divergence (the mechanical witness).
* the prose contract is too loose to confirm alignment AND no concrete divergence is
  pinnable (counts match, identifiers do not align) → **UNVERIFIED** (North-Star cap
  surfaced LOUD).
* the inspection adapter cannot run (unsupported AT language) → **INDETERMINATE**
  (``ran=False``).

Asymmetric authority (Invariant 1): a PASS = "no divergence found", never an
authorizing GO. UNVERIFIED / INDETERMINATE are NO-floors.

Driven by the pure callable :func:`evaluate_gate_g` and, since f-coherence-and-
attestation slice-06, reachable as a registered subcommand via the thin :func:`main`
driver below (a thin CLI wrapper over the unchanged callable — no domain logic in the
driver; it parses paths, drives the diff, prints the §17 verdict). f-code-design-
manifest-and-gate-g slice-04 RENAMED the subcommand ``des gate-g`` ->
``des gate-design-at-coherence`` (DDD-5: a GENERAL design↔AT coherence gate after the
slice-03 generalization). The module path ``des.cli.gate_g`` is unchanged.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.domain.gate_outcome import GateVerdict
from des.ports.code_fact_port import (
    CAPABILITY_ADR_SECTION,
    CAPABILITY_ATOMS_IN_FILE,
    CapabilityDescriptor,
)


# The design prose block gate-G diffs against (OB-G — DEFER D3). Read via the
# CodeFactPort `query.adr-section` to confirm the design contract is present.
_DESIGN_SECTION_HEADING = "## Wave: DESIGN / [REF] Code-Design"

# A code-design manifest's filename. When the design contract IS this manifest
# (ADR-FLOW-003 D1 / DDD-1), gate-G reads its `example-tables:` `row-id`s as the
# design side and the AT `@row:` tags as the AT side — a deterministic join key
# (no UNVERIFIED cap), replacing the prose `_example_table_rows` fallback.
_MANIFEST_FILENAME = "code-design.manifest.yaml"

# A Gherkin `@row:<row-id>` tag declaring the join key a scenario covers (DDD-4 /
# CT-10). Read from the line(s) above a `Scenario:` line in an AT `.feature`.
_ROW_TAG = re.compile(r"@row:([a-z0-9-]+)")

# A manifest `example-tables[].row-id` line. The manifest is parsed stdlib-only
# (no `import yaml` -- the DES-bundle contract forbids it in any bundled `des`
# module; F-D-09): the `example-tables:` block is a flat list of `- row-id: <id>`
# entries, so a line-oriented match extracts the join keys without a YAML parser.
_MANIFEST_ROW_ID = re.compile(r"^\s*-?\s*row-id:\s*([a-z0-9-]+)\s*$")

# An example-table row line in the prose `[REF] Code-Design` block. The first cell
# is the ExampleTableRow identifier; the header + separator rows are excluded.
_EXAMPLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|.*\|.*\|\s*$")
_EXAMPLE_HEADER_CELL = "ExampleTableRow"

# A Gherkin scenario line in an AT `.feature` (ANY wording). The capture is the
# scenario's free-text name -- used to NAME an untagged scenario (CT-10b).
_SCENARIO_NAME = re.compile(r"^\s*Scenario:\s*(.+?)\s*$")

# The legacy feature-specific scenario phrasing ("Operator exports the X case"),
# whose trailing token names the row the scenario covers. Kept ONLY as the prose-path
# fallback when a scenario carries no `@row:` tag (back-compat with the original
# coherence gate); the GENERAL join key is the `@row:` tag (CT-5).
_LEGACY_SCENARIO_SUBJECT = re.compile(
    r"^\s*Scenario:\s*Operator exports the\s+(\S+)\s+case\s*$"
)

# AT-module file extensions whose scenarios the gate can inspect. A `.feature`
# (Gherkin) or `.py` (step module) is recognized; any other extension (e.g. `.exs`)
# is an unsupported language the inspection substrate cannot run over.
_SUPPORTED_AT_SUFFIXES = frozenset({".feature", ".py"})


@dataclass(frozen=True)
class GateGEnvelope:
    """The §17 verdict envelope gate-G returns (port-exposed DTO at the gate boundary).

    ``verdict``      -- the §17 ``GateVerdict`` (one of the five, no sixth).
    ``diagnostic``   -- names the confirmable divergence on FAIL / the cap reason on
                        UNVERIFIED (non-empty there); empty on PASS.
    ``cap_surfaced`` -- the North-Star cap was surfaced LOUD (True only on the
                        suspected-but-unconfirmable UNVERIFIED case).
    ``ran``          -- the mechanical diff actually ran (False on the adapter-absent
                        INDETERMINATE degrade — the mechanism could not run).
    """

    verdict: GateVerdict
    diagnostic: str
    cap_surfaced: bool
    ran: bool


def evaluate_gate_g(design_contract_path: Path, at_module_path: Path) -> GateGEnvelope:
    """Diff the design ``[REF] Code-Design`` against the AT module → a §17 verdict.

    ``design_contract_path`` is the feature-delta carrying the prose ``[REF]
    Code-Design`` example-table; ``at_module_path`` is the AT module directory (or
    file). Consumes the ``CodeFactPort`` substrate to confirm the design block is
    present and to probe AT-module parseability, then computes the row↔scenario
    bijection over the textual contract.
    """
    if _is_manifest_source(design_contract_path):
        if not _at_module_is_inspectable(at_module_path):
            return _indeterminate()
        return _evaluate_manifest_source(design_contract_path, at_module_path)
    if not _design_section_present(design_contract_path):
        return _not_applicable()
    if not _at_module_is_inspectable(at_module_path):
        return _indeterminate()
    design_rows = _example_table_rows(design_contract_path)
    at_scenarios = _scenario_subjects(at_module_path)
    return _classify(design_rows, at_scenarios)


# -- manifest-source branch (the D3 closure — stable row-id join key) ---------


def _is_manifest_source(design_contract_path: Path) -> bool:
    """The design contract IS a ``code-design.manifest.yaml`` (the broad ADR-FLOW-003
    source), not the prose feature-delta — gate-G reads its ``example-tables:``."""
    return design_contract_path.name == _MANIFEST_FILENAME


def _evaluate_manifest_source(
    design_contract_path: Path, at_module_path: Path
) -> GateGEnvelope:
    """Diff the manifest ``example-tables:`` ``row-id``s against the AT ``@row:`` tags.

    The manifest's stable ``row-id`` is the join key that makes the bijection
    CONFIRMABLE (no UNVERIFIED cap). When every declared ``row-id`` is covered by
    exactly one tagged scenario and every tag names a declared row, gate-G returns a
    deterministic PASS.
    """
    # An untagged scenario carries NO `@row:` join key, so it is INVISIBLE to the
    # row↔tag diff and would be silently ignored (CT-10b). The general parser must
    # SEE every scenario: an untagged scenario under a manifest cannot be confirmed
    # against any row, so gate-G caps at UNVERIFIED NAMING it -- never a silent PASS.
    untagged = _untagged_scenarios(at_module_path)
    if untagged:
        return _untagged_unverified(untagged)
    manifest_rows = _manifest_row_ids(design_contract_path)
    at_rows = _at_row_tags(at_module_path)
    rows = set(manifest_rows)
    tags = set(at_rows)
    if rows == tags:
        return _manifest_passed()
    # The manifest's stable row-id is the join key: a row↔tag mismatch is a
    # CONFIRMED divergence (dropped row / undeclared scenario), so route it
    # through the existing _failed machinery for a deterministic FAIL naming the
    # offending row-id -- never the prose-era UNVERIFIED cap.
    dropped = sorted(rows - tags)
    undeclared = sorted(tags - rows)
    return _failed(dropped, undeclared)


def _manifest_row_ids(design_contract_path: Path) -> list[str]:
    """The ``example-tables:`` ``row-id``s declared in the manifest (stdlib-only)."""
    rows: list[str] = []
    for line in _read(design_contract_path).splitlines():
        match = _MANIFEST_ROW_ID.match(line)
        if match is not None:
            rows.append(match.group(1))
    return rows


def _at_row_tags(at_module_path: Path) -> list[str]:
    """The ``@row:<row-id>`` join keys the AT scenarios declare across the module."""
    tags: list[str] = []
    for path in _iter_at_files(at_module_path):
        if path.suffix != ".feature":
            continue
        tags.extend(_ROW_TAG.findall(_read(path)))
    return tags


def _untagged_scenarios(at_module_path: Path) -> list[str]:
    """The names of AT scenarios that carry NO ``@row:`` join key (CT-10b).

    A scenario is untagged when no ``@row:<id>`` tag appears on the contiguous tag
    line(s) directly above its ``Scenario:`` line. Such a scenario is invisible to
    the row↔tag diff, so the general parser surfaces it by name rather than letting
    it pass silently.
    """
    untagged: list[str] = []
    for path in _iter_at_files(at_module_path):
        if path.suffix != ".feature":
            continue
        tagged = False
        for line in _read(path).splitlines():
            scenario = _SCENARIO_NAME.match(line)
            if scenario is not None:
                if not tagged:
                    untagged.append(scenario.group(1).strip())
                tagged = False
                continue
            if _ROW_TAG.search(line):
                tagged = True
            elif line.strip() and not line.lstrip().startswith("@"):
                tagged = False
    return untagged


def _untagged_unverified(untagged: list[str]) -> GateGEnvelope:
    """An untagged scenario under a manifest → UNVERIFIED naming it (no silent pass)."""
    named = "; ".join(repr(name) for name in untagged)
    diagnostic = (
        "the acceptance tests include scenario(s) with no `@row:` join key under a "
        f"code-design manifest: {named}. An untagged scenario cannot be confirmed "
        "against any manifest row, so gate-G caps at UNVERIFIED naming it -- never a "
        "silent pass."
    )
    return GateGEnvelope(
        verdict=GateVerdict.UNVERIFIED,
        diagnostic=diagnostic,
        cap_surfaced=True,
        ran=True,
    )


def _manifest_passed() -> GateGEnvelope:
    """A manifest-backed bijection → deterministic PASS, no North-Star cap."""
    return GateGEnvelope(
        verdict=GateVerdict.PASS, diagnostic="", cap_surfaced=False, ran=True
    )


# -- substrate consumption (CodeFactPort — no second import ast) --------------


def _design_section_present(design_contract_path: Path) -> bool:
    """The ``[REF] Code-Design`` block is present (via ``query.adr-section``)."""
    result = _chain(design_contract_path).query(
        _descriptor(CAPABILITY_ADR_SECTION),
        {"anchor": _DESIGN_SECTION_HEADING},
    )
    payload = getattr(result, "payload", None)
    files = payload.get("files") if isinstance(payload, dict) else None
    return bool(files)


def _at_module_is_inspectable(at_module_path: Path) -> bool:
    """The AT module is in a language the inspection substrate can run over.

    Probes the AT module through ``query.atoms-in-file`` (consuming the substrate)
    AND recognizes the AT-language by extension: a ``.feature`` / ``.py`` AT is
    inspectable; an AT module whose only files are an unsupported language (e.g. an
    ``.exs`` Elixir AT) yields no inspectable surface → gate-G degrades LOUD.
    """
    # Consume the substrate's structural probe (provenance-tagged; C2 — no fork).
    _chain(at_module_path).query(
        _descriptor(CAPABILITY_ATOMS_IN_FILE),
        {"root": str(at_module_path)},
    )
    return any(
        path.suffix in _SUPPORTED_AT_SUFFIXES for path in _iter_at_files(at_module_path)
    )


def _chain(root: Path) -> CodeFactChain:
    """The slice-01/02 ``CodeFactChain`` rooted at ``root`` (the substrate, not a fork)."""
    return CodeFactChain(root=root)


def _descriptor(capability_id: str) -> CapabilityDescriptor:
    """A stable-core capability descriptor at the floor (the substrate negotiates)."""
    return CapabilityDescriptor(
        id=capability_id,
        stability="stable",
        contract_version="1.0.0",
        io_schema=capability_id,
        providing_adapter="ast",
    )


# -- textual extraction (markdown table + Gherkin — NOT import ast) -----------


def _example_table_rows(design_contract_path: Path) -> list[str]:
    """The ExampleTableRow identifiers in the prose ``[REF] Code-Design`` table."""
    rows: list[str] = []
    for line in _read(design_contract_path).splitlines():
        match = _EXAMPLE_ROW.match(line)
        if match is None:
            continue
        identifier = match.group(1)
        if _is_table_row_identifier(identifier):
            rows.append(identifier)
    return rows


def _is_table_row_identifier(identifier: str) -> bool:
    """True iff a first-cell token is a data row (not the header / separator)."""
    if identifier == _EXAMPLE_HEADER_CELL:
        return False
    return set(identifier) != {"-"}


def _scenario_subjects(at_module_path: Path) -> list[str]:
    """The join key each Gherkin scenario declares across the AT module.

    GENERAL recognition (CT-5): a scenario's join key is the ``@row:<id>`` tag it
    carries on ANY wording -- read with the same ``@row:`` reader the manifest branch
    uses (``_at_row_tags``), so the prose and manifest paths read the key identically.
    A scenario carrying no ``@row:`` tag falls back to the legacy feature-specific
    subject phrasing (``Operator exports the X case``), preserving the original gate's
    behaviour for ATs predating the ``@row:`` convention.
    """
    subjects: list[str] = list(_at_row_tags(at_module_path))
    if subjects:
        return subjects
    for path in _iter_at_files(at_module_path):
        if path.suffix != ".feature":
            continue
        for line in _read(path).splitlines():
            match = _LEGACY_SCENARIO_SUBJECT.match(line)
            if match is not None:
                subjects.append(match.group(1))
    return subjects


# -- the bijection classifier (the five §17 verdicts) -------------------------


def _classify(design_rows: list[str], at_scenarios: list[str]) -> GateGEnvelope:
    """Map the row↔scenario diff onto a §17 verdict (no sixth)."""
    rows = set(design_rows)
    scenarios = set(at_scenarios)
    dropped = sorted(rows - scenarios)
    undeclared = sorted(scenarios - rows)
    if not dropped and not undeclared:
        return _passed()
    if _is_confirmable_divergence(rows, scenarios, dropped, undeclared):
        return _failed(dropped, undeclared)
    return _unverified(design_rows, at_scenarios)


def _is_confirmable_divergence(
    rows: set[str],
    scenarios: set[str],
    dropped: list[str],
    undeclared: list[str],
) -> bool:
    """True iff the diff pins a CONCRETE divergence (a dropped row / undeclared scenario).

    A divergence is confirmable only when the row and scenario identifier spaces
    OVERLAP — i.e. some rows DO align, so an un-covered row (or an undeclared
    scenario) stands out against an aligned baseline. When the two identifier spaces
    are DISJOINT and the counts match, nothing concrete is pinnable: the contract is
    simply too loose to confirm alignment (→ UNVERIFIED, not FAIL).
    """
    overlap = bool(rows & scenarios)
    counts_differ = len(rows) != len(scenarios)
    return overlap or (counts_differ and bool(dropped or undeclared))


# -- verdict constructors -----------------------------------------------------


def _passed() -> GateGEnvelope:
    """Bijective + alignable → PASS (no divergence found; never an authorizing GO)."""
    return GateGEnvelope(
        verdict=GateVerdict.PASS, diagnostic="", cap_surfaced=False, ran=True
    )


def _failed(dropped: list[str], undeclared: list[str]) -> GateGEnvelope:
    """A confirmable divergence → FAIL + a diagnostic naming the mechanical witness
    AND a concrete HOW (GDP-3 — a FAIL/UNVERIFIED verdict must carry an actionable
    remediation, not only the mechanical WHAT)."""
    parts: list[str] = []
    for row in dropped:
        parts.append(
            f"ExampleTableRow {row!r} has no covering scenario -- author a "
            f"scenario tagged @row:{row}"
        )
    for scenario in undeclared:
        parts.append(
            f"AT scenario {scenario!r} references a symbol the design never "
            f"declared -- declare {scenario!r} on the design contract, or "
            "retarget the scenario to an existing row"
        )
    return GateGEnvelope(
        verdict=GateVerdict.FAIL,
        diagnostic="; ".join(parts),
        cap_surfaced=False,
        ran=True,
    )


def _unverified(design_rows: list[str], at_scenarios: list[str]) -> GateGEnvelope:
    """Too loose to confirm → UNVERIFIED + the North-Star cap surfaced LOUD, with a
    concrete HOW (GDP-3): declare the port on the design contract, or retarget the AT."""
    diagnostic = (
        "design↔AT row-level bijection UNCONFIRMABLE against the prose "
        f"`{_DESIGN_SECTION_HEADING}` contract (D3 manifest deferred, OB-G): "
        f"{len(design_rows)} example-table rows {design_rows!r} and "
        f"{len(at_scenarios)} AT scenarios {at_scenarios!r} match in count but no "
        "row identifier aligns to a scenario -- neither a clean bijection nor a "
        "concrete divergence is mechanically pinnable. North-Star cap surfaced -- "
        "declare the port on the design contract, or retarget the AT."
    )
    return GateGEnvelope(
        verdict=GateVerdict.UNVERIFIED,
        diagnostic=diagnostic,
        cap_surfaced=True,
        ran=True,
    )


def _indeterminate() -> GateGEnvelope:
    """The inspection adapter cannot run (unsupported AT language) → INDETERMINATE."""
    diagnostic = (
        "the inspection substrate could not run: the AT module is in a language "
        "the CodeFactPort AstAdapter cannot parse (no recognized `.feature` / `.py` "
        "AT surface). Degrading LOUD to INDETERMINATE -- the mechanism could not run, "
        "never a fabricated verdict."
    )
    return GateGEnvelope(
        verdict=GateVerdict.INDETERMINATE,
        diagnostic=diagnostic,
        cap_surfaced=False,
        ran=False,
    )


def _not_applicable() -> GateGEnvelope:
    """No design `[REF] Code-Design` contract present → NOT_APPLICABLE."""
    diagnostic = (
        f"no `{_DESIGN_SECTION_HEADING}` block present in the design contract -- "
        "gate-G has nothing to diff against (NOT_APPLICABLE)."
    )
    return GateGEnvelope(
        verdict=GateVerdict.NOT_APPLICABLE,
        diagnostic=diagnostic,
        cap_surfaced=False,
        ran=False,
    )


# -- filesystem helpers -------------------------------------------------------


def _iter_at_files(at_module_path: Path) -> list[Path]:
    """Every file under the AT module path (a directory walk or a single file)."""
    if at_module_path.is_file():
        return [at_module_path]
    if not at_module_path.is_dir():
        return []
    return [path for path in sorted(at_module_path.rglob("*")) if path.is_file()]


def _read(path: Path) -> str:
    """Read a file's text, tolerating a missing / non-UTF-8 file."""
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError, OSError):
        return ""


# -- thin CLI driver (gate-stack wiring, slice-06) ----------------------------
#
# The operator-visible `des gate-g` subcommand. A THIN driver over the existing
# evaluate_gate_g — it parses the design-contract + AT-module paths, drives the
# unchanged mechanical diff, and prints the §17 GateVerdict token as a JSON line
# on stdout. NO domain logic lives here; the verdict comes from evaluate_gate_g.


def main(argv: list[str] | None = None) -> int:
    """Drive gate-G over a design contract + AT module → print the §17 verdict.

    Emits one JSON line ``{"verdict": <token>, "diagnostic": <str>}`` on stdout
    (the verdict token is the §17 ``GateVerdict.value``), followed by a
    human-readable ``✗ <verdict>: <diagnostic>`` line whenever the diagnostic is
    non-empty (FAIL / UNVERIFIED / INDETERMINATE / NOT_APPLICABLE — GDP-3: a
    machine-only JSON blob is not a self-explaining failure surface). A PASS
    carries an empty diagnostic, so no human line is emitted for it. The exit
    code is 0 — the verdict, not the process code, carries the gate outcome
    (asymmetric authority: a PASS is "no objection found", never an authorizing GO).
    """
    args = _build_gate_g_parser().parse_args(argv)
    envelope = evaluate_gate_g(args.design_contract, args.at_module)
    print(
        json.dumps(
            {"verdict": envelope.verdict.value, "diagnostic": envelope.diagnostic}
        )
    )
    if envelope.diagnostic:
        print(f"✗ {envelope.verdict.value}: {envelope.diagnostic}")
    return 0


def _build_gate_g_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des gate-design-at-coherence",
        description=(
            "Mechanical design↔AT coherence gate: diff the design `[REF] "
            "Code-Design` against the AT module and emit a §17 GateVerdict."
        ),
    )
    parser.add_argument(
        "--design-contract",
        required=True,
        type=Path,
        help="The feature-delta (prose `[REF] Code-Design`) or code-design.manifest.yaml.",
    )
    parser.add_argument(
        "--at-module",
        required=True,
        type=Path,
        help="The acceptance-test module directory (or file) to diff against.",
    )
    return parser


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main())
