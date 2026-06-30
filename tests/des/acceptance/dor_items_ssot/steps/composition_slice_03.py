"""Composition root for dor-items-ssot slice-03 (separate-hard-gate render).

slice-03 of dor-items-ssot (the FINAL behavioral slice): the DoR-validation skill
the reviewer ACTUALLY loads (``nWave/skills/nw-dor-validation/SKILL.md``) must
TELL the reviewer, at the point of enforcement, that **job-traceability is a
SEPARATE hard gate ABOVE the nine readiness items** -- NOT readiness item ten
(DISCUSS D-5 / DESIGN DDD-3). So the loaded enforcement path can no longer
confuse the ``job_id`` check for an enumerated readiness item (or skip it
alongside one).

TWO real artifacts, no test doubles (Pillar 3, Mandate 9/11 example-only):

  1. The reviewer-loaded skill itself -- ``nWave/skills/nw-dor-validation/SKILL.md``
     -- read from the REAL repository tree (the contract under test IS the shipped
     skill). The cross-artifact SUT, the SAME accepted shape slice-02 established.

  2. The canonical SSOT, driven through the PRODUCTION driving port -- the real
     ``scripts/cli/read_dor_items.py`` standalone reader invoked as a subprocess
     (Layer 3 subprocess, Mandate-13 driving-port-only; the SAME driving surface
     slices 01+02 established). Used ONLY by the coherence AT to prove the skill's
     separate-gate statement agrees with the SSOT's ``hard_gates`` key mechanically
     (render-not-drift, DESIGN DDD-4). The composition NEVER imports
     ``read_dor_items`` / its ``main`` and calls it at the step boundary (that
     would collapse the leg into a Layer-1 unit test, forbidden by Mandate-13 /
     S2): the only entry is the real subprocess.

WHY THIS RED-fails for the RIGHT reason (MISSING_FUNCTIONALITY, never BROKEN):
on the slice-02 GREEN baseline the skill enumerates the canonical nine but says
NOTHING about job-traceability -- it carries no "separate hard gate" statement at
all. The skill-view parser therefore reports
``states_job_traceability_is_separate_hard_gate=False`` and
``states_separate_gate_is_above_readiness_items=False``; each Then asserts the
GREEN-state opposite and fails with a semantic ``AssertionError``, never a
collection / import / setup error. The composition imports only test-local types
+ stdlib (``re`` / ``subprocess`` / ``json``), so the suite COLLECTS cleanly.

CRITICAL anti-trap (slice-02 carried the same): the GREEN skill statement MUST
NOT contain the literal ``nWave/data/`` -- ``validate_no_data_refs.py`` forbids
it in any framework ``.md``. slice-03's separate-gate statement names the gate by
its bare ``job-traceability`` token (and may cite the bare ``dor-items.yaml`` /
the standalone reader the skill already references). A GREEN that satisfies these
ATs passes ``validate_no_data_refs.py`` by construction: the parser asserts ONLY
the bare ``job-traceability`` token + the separate/above relationship, never the
forbidden prefix.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from scripts.cli import read_dor_items
from tests.common.in_process_cli import run_cli_in_process

# Reuse slice-02's checklist-section scoping so the readiness-item enumeration is
# parsed from exactly the same DoR-checklist section -- the single source of
# truth for "which section the nine live in".
from .composition_slice_02 import _checklist_section
from .domain_types import CanonicalReadinessSet, ReadinessItem
from .domain_types_slice_03 import (
    SEPARATE_HARD_GATE_TOKEN,
    JobTraceabilityGateView,
)


# THIS file lives at
# tests/des/acceptance/dor_items_ssot/steps/composition_slice_03.py -> 5 parents
# up is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# The reviewer-loaded skill -- the cross-artifact SUT.
_DOR_SKILL_RELPATH = Path("nWave") / "skills" / "nw-dor-validation" / "SKILL.md"

# "Separate hard gate" relationship phrasing the skill must state. The crafter is
# free to word the sentence (render-shape tolerance, mirroring slice-02): the
# contract is that the loaded skill says, in the same statement, BOTH that
# job-traceability is a "separate hard gate" AND that it sits "above" / is "not
# (one) of" the enumerated readiness items. Detected as: a line/paragraph that
# names the bare ``job-traceability`` token AND carries a "separate hard gate"
# phrase AND an "above the readiness items / not a readiness item" phrase.
_SEPARATE_HARD_GATE_RE = re.compile(r"separate\s+hard\s+gate", re.IGNORECASE)
_ABOVE_ITEMS_RE = re.compile(
    r"above\s+the\s+(?:nine\s+)?readiness\s+items"
    r"|above\s+the\s+(?:nine|9)\b"
    r"|not\s+(?:a|the\s+\w+|item\s+ten|readiness\s+item)\b",
    re.IGNORECASE,
)


class JobTraceabilityGateComposition:
    """Production composition root over the live nw-dor-validation skill asset.

    The asset is the shipped ``nWave/skills/nw-dor-validation/SKILL.md`` file
    itself -- slice-03's contract is that the reviewer-loaded skill copy TELLS the
    reviewer job-traceability is a separate hard gate ABOVE the nine (consistent
    with the SSOT's ``hard_gates`` key) without the forbidden ``nWave/data/``
    literal.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or _REPO_ROOT
        self._skill_path = self._repo_root / _DOR_SKILL_RELPATH

    # --- cross-artifact read surface (the loaded skill) ---------------------

    def read_job_traceability_stance(self) -> JobTraceabilityGateView:
        """Parse the shipped skill's stance on the job-traceability gate."""
        text = self._skill_text()
        return _parse_job_traceability_stance(text)

    def skill_bytes(self) -> bytes:
        """Raw shipped-skill bytes -- read-only universe snapshot (Mandate 8)."""
        return self._skill_path.read_bytes() if self._skill_path.is_file() else b""

    # --- coherence leg (the SSOT via the real driving port) -----------------

    def read_ssot_canonical_set(self) -> CanonicalReadinessSet:
        """Invoke the REAL ``scripts/cli/read_dor_items.py`` and parse its output.

        Layer 3 subprocess (Mandate-13): the coherence AT asks the production
        reader for the SSOT's separate ``hard_gates`` so it can assert the skill's
        separate-gate statement names the SAME gate the SSOT carries
        (render-not-drift). A non-zero result surfaces as the EMPTY set, never a
        raised setup error.
        """
        completed = self._run_reader(["--format", "json"])
        return _parse_ssot_set(completed.stdout, completed.returncode)

    # --- internals ----------------------------------------------------------

    def _skill_text(self) -> str:
        if not self._skill_path.is_file():
            return ""
        return self._skill_path.read_text(encoding="utf-8")

    def _run_reader(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        exit_code, stdout, stderr = run_cli_in_process(
            argv,
            cwd=self._repo_root,
            main=read_dor_items.main,
        )
        return subprocess.CompletedProcess(
            args=argv, returncode=exit_code, stdout=stdout, stderr=stderr
        )


# --- pure parsers -----------------------------------------------------------
# Each composition method is a single delegation (Mandate-12 criterion 3); the
# parsing logic is the single source of truth, kept out of step bodies.


def _separate_gate_block(text: str) -> str:
    """Return the text block(s) that mention the bare job-traceability token.

    The separate-gate statement may sit anywhere in the skill (a dedicated
    "Hard Gate(s)" sub-section, or a note under the checklist heading), and the
    relationship phrasing ("separate hard gate", "above the nine") may legitimately
    sit a few lines away from the bare ``job-traceability`` token within the same
    paragraph or sub-section. The block is therefore the markdown SECTION (``## ``
    heading to the next ``## ``) that contains the token, OR -- when the token is
    not under its own section -- a paragraph-sized window around the token. Empty
    string when the token is absent (today's RED state).
    """
    sections = _markdown_sections(text)
    keep: list[str] = [s for s in sections if SEPARATE_HARD_GATE_TOKEN in s]
    if keep:
        return "\n".join(keep)
    # Fallback: paragraph-sized window when the token is not under its own ``## ``
    # section (e.g. a note appended under the checklist heading).
    lines = text.splitlines()
    window: list[str] = []
    for idx, line in enumerate(lines):
        if SEPARATE_HARD_GATE_TOKEN in line:
            lo = max(0, idx - 5)
            hi = min(len(lines), idx + 6)
            window.extend(lines[lo:hi])
    return "\n".join(window)


def _markdown_sections(text: str) -> list[str]:
    """Split the skill text into ``## ``-delimited sections (heading -> next ``## ``)."""
    heading_re = re.compile(r"^##\s+.*$", re.MULTILINE)
    starts = [m.start() for m in heading_re.finditer(text)]
    if not starts:
        return [text]
    bounds = starts + [len(text)]
    return [text[bounds[i] : bounds[i + 1]] for i in range(len(starts))]


def _parse_job_traceability_stance(text: str) -> JobTraceabilityGateView:
    """Extract the slice-03 cross-artifact contract from the shipped skill text."""
    block = _separate_gate_block(text)
    names_gate = SEPARATE_HARD_GATE_TOKEN in block
    is_separate = names_gate and bool(_SEPARATE_HARD_GATE_RE.search(block))
    is_above = names_gate and bool(_ABOVE_ITEMS_RE.search(block))
    counted_among_items = _job_traceability_counted_among_items(text)
    return JobTraceabilityGateView(
        states_job_traceability_is_separate_hard_gate=is_separate,
        states_separate_gate_is_above_readiness_items=is_above,
        counts_job_traceability_among_readiness_items=counted_among_items,
    )


def _job_traceability_counted_among_items(text: str) -> bool:
    """Whether the bare job-traceability token appears in the readiness-item enum.

    The DoR-checklist section enumerates the nine readiness items. If the bare
    ``job-traceability`` token appears WITHIN that enumerated section it has been
    (wrongly) folded into the nine as item ten -- the exact D-5 anti-pattern. The
    separate-gate statement must live OUTSIDE the enumerated nine, so a correct
    GREEN keeps the token out of the readiness-item section.
    """
    section = _checklist_section(text)
    enumerated = _readiness_item_lines(section)
    return SEPARATE_HARD_GATE_TOKEN in enumerated


def _readiness_item_lines(section: str) -> str:
    """The enumerated readiness-item lines of the checklist section only.

    Restricts to the ``### Item N:`` / numbered-item enumeration lines so a
    separate "Hard Gates" note that happens to sit under the same ``## `` heading
    is NOT mistaken for an enumerated item. Falls back to the whole section when
    no per-item headings are present (numbered-list render shape).
    """
    item_heading_re = re.compile(r"^###\s+Item\s+\d+:", re.MULTILINE)
    matches = list(item_heading_re.finditer(section))
    if not matches:
        return section
    start = matches[0].start()
    return section[start:]


def _parse_ssot_set(stdout: str, returncode: int) -> CanonicalReadinessSet:
    """Parse the reader's JSON listing into the observable SSOT set.

    The reader may prefix non-JSON diagnostic lines (e.g. a freshness event)
    before the JSON object; scan for the single JSON object line so the coherence
    leg reads the ``hard_gates`` regardless of leading diagnostics.
    """
    if returncode != 0:
        return CanonicalReadinessSet(items=(), separate_hard_gates=())
    payload = _extract_json_object(stdout)
    if payload is None:
        return CanonicalReadinessSet(items=(), separate_hard_gates=())
    item_names = payload.get("items", []) if isinstance(payload, dict) else []
    hard_gates = payload.get("hard_gates", []) if isinstance(payload, dict) else []
    return CanonicalReadinessSet(
        items=tuple(ReadinessItem(name=str(name)) for name in item_names),
        separate_hard_gates=tuple(str(gate) for gate in hard_gates),
    )


def _extract_json_object(stdout: str) -> dict | None:
    """Return the first JSON object found in stdout (whole-string then per-line).

    Tolerates leading diagnostic lines the reader subprocess may emit before the
    JSON payload (Mandate-13 driving-port-only: we read what the real subprocess
    prints, we never reach into the reader).
    """
    for candidate in (stdout, *stdout.splitlines()):
        candidate = candidate.strip()
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(payload, dict) and "hard_gates" in payload:
            return payload
    return None


__all__ = [
    "JobTraceabilityGateComposition",
]
