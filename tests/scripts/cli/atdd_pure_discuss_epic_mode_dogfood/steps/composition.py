"""Composition root for the discuss-epic-mode slice-06 dogfood acceptance slice.

Slice-06 value: the flow-v2 wave-migrations follow-on list (today living only in
conversation / flow-design ``§13 CHANGE-SET master``) becomes a validated,
repeatable epic-delta -- the FIRST real epic-mode run.

The REAL-artifact distinction (the central slice-06 decision)
=============================================================
Slices 02/04/05 witnessed the epic-delta / escalation / maintenance contracts
against a suite-local reference oracle producing into ``tmp_path`` (fully isolated,
synthetic). Slice-06 is the DOGFOOD: the deliverable IS the REAL artifact at the
production repository path ``docs/epic/flow-v2-wave-migrations/epic-delta.md``,
AUTHORED at DELIVER by the Luna PO agent following the epic-mode procedure
(slice-02 authoring prose + slice-04 escalation + slice-05 maintenance, all
exercised against this single real run).

A reference oracle CANNOT stand in here: the real artifact is the deliverable, not
a golden-file analogue of an LLM act. So this composition OBSERVES the real
repository path -- read-only. It NEVER writes the artifact (the producer is the
DELIVER-stage authoring procedure). Test isolation is preserved BY read-onlyness:
the ATs only read ``docs/epic/...`` under the real repo root and assert against the
parsed content; they perform zero filesystem mutation.

What these ATs PIN (mechanical, on the REAL artifact):
  - EDC structural shape + EDC-5 keystone + EDC-6 backward-only dependency order
    (DC-2: keystone/dep-order mechanical validation was DEFERRED to slice-06; THIS
    is its slice -- pinned here on the real artifact).
  - The gate-OUT seam (EDC-8): the REAL produced epic-delta validates ``accepted``
    through the slice-01 CLI ``des validate-feature-delta --require-feature-plan
    --format=json`` (``des.cli.validate_feature_delta.main``). The only mechanical
    ``src/des`` seam slice-06 drives -- slice-01's already-shipped surface.
  - §13-completeness (the dogfood's honesty): every one of the closed 7-item §13
    coverage universe maps to >= 1 Feature Plan row, OR is a documented exclusion in
    the artifact. Content-faithfulness as a closed-set semantic assertion, NOT a
    brittle byte-pin of the §13 prose.

Active-RED contract (atdd_pure)
===============================
Slice-06 has NO net-new ``src/des`` seam (DESIGN reuse table: zero CREATE_NEW code
modules; the entire feature is EXTEND + text + one dogfood artifact). The active-RED
is artifact-absence at the REAL production path: on the current tip
``docs/epic/flow-v2-wave-migrations/epic-delta.md`` does not exist (the dogfood run
has not happened), so every observation reads an ABSENT artifact ->
``EPIC_DELTA_ABSENT`` / missing structural pins -> semantic ``AssertionError``. The
composition imports cleanly (slice-01's CLI exists today), so RED is
missing-functionality, never a collection / import error. ``__SCAFFOLD__`` markers:
NONE (no new ``src/des`` seam to scaffold; the deliverable is an artifact + prose).

S3 dormant-seam reconciliation: slice-06 declares ZERO net-new ``src/des`` seams.
The only mechanical seam driven is slice-01's already-shipped CLI, reached through
its real ``main(argv)`` entry in the gate-OUT AT. No net-new seam can ship dormant
-- S3 = PASS by construction.

Layer 3 (subprocess/FS acceptance): the driving ports are (a) the REAL produced
epic-delta artifact (read-only filesystem/document observation) and (b) the real
slice-01 CLI for the gate-OUT leg. No PBT machinery (Mandate 9/11) -- the EDC + the
§13 coverage universe are finite, enumerable closed contract sets.
"""

from __future__ import annotations

import contextlib
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

# The ONLY production import (S2 driving-port-only invariant): the slice-01
# validate-feature-delta CLI, already shipped (slice-06 depends on slice-01). It is
# the sole mechanical `src/des` seam slice-06 drives -- the gate-OUT leg (EDC-8).
# There is NO reference oracle in this suite: the REAL artifact is the deliverable
# (authored at DELIVER), not a golden-file analogue. The composition only OBSERVES
# the real production path, read-only.
from des.cli.validate_feature_delta import (
    main as validate_feature_delta_main,
)

from .domain_types import (
    DOGFOOD_EPIC_ID,
    SECTION_13_ITEM_KEYWORDS,
    DogfoodVerdict,
    EpicId,
    Section13Item,
)


# The R1 Feature Plan heading (exact form, reused verbatim from DESIGN R1).
_FEATURE_PLAN_HEADING = "## Wave: DISCUSS / [REF] Feature Plan"
# The EDC-3 epic-JTBD section heading.
_EPIC_JTBD_HEADING = "## Wave: DISCUSS / [REF] Epic Job & Intent"
# EDC-4 fixed five-column header (mirrors the Slice Plan vocabulary).
_FEATURE_PLAN_COLUMNS = (
    "Feature",
    "Value statement",
    "Status",
    "Annotation",
    "Justification",
)
# EDC-5 keystone annotation token (Slice Plan vocabulary REUSED -- no new token).
_KEYSTONE_ANNOTATION = "@walking-skeleton"
# EDC-7 / R2 closed Status token set; authored rows start `pending`.
_STATUS_TOKENS = frozenset({"pending", "in-flight", "shipped"})


@dataclass(frozen=True)
class DogfoodObservation:
    """Read-only observation of the REAL flow-v2-wave-migrations epic-delta.

    ``exists`` is the production-path presence of ``epic-delta.md`` under the real
    repository root. The rest are EDC structural observations parsed from its
    content; they are meaningful only when ``exists`` is True. On the current tip
    the dogfood run has not happened, so ``exists`` is False and the structural
    observations read their empty defaults -- the active-RED state.

    ``covered_items`` / ``uncovered_items`` partition the closed 7-item §13 coverage
    universe by whether each item's keyword set is present in any Feature Plan row
    OR named in the artifact's documented-exclusions set (slice-06 dogfood
    completeness contract). On an absent artifact every item is uncovered.
    """

    exists: bool
    title_line: str = ""
    has_epic_jtbd_section: bool = False
    has_feature_plan_heading: bool = False
    feature_plan_columns: tuple[str, ...] = ()
    keystone_row_count: int = 0
    status_tokens_in_authored_rows: tuple[str, ...] = ()
    dependency_order_backward_only: bool = False
    covered_items: frozenset[Section13Item] = field(default_factory=frozenset)
    uncovered_items: frozenset[Section13Item] = field(
        default_factory=lambda: frozenset(Section13Item)
    )


@dataclass
class GateOutResult:
    """Observable outcome of the slice-01 gate-OUT validation (EDC-8)."""

    epic_delta_exists: bool
    exit_code: int
    output: str

    @property
    def _verdict_token(self) -> str | None:
        """The ``verdict`` field of the single JSON object the slice-01 CLI emits."""
        import json

        for line in self.output.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            with contextlib.suppress(json.JSONDecodeError):
                obj = json.loads(stripped)
                if isinstance(obj, dict) and "verdict" in obj:
                    return str(obj["verdict"])
        return None

    @property
    def verdict(self) -> DogfoodVerdict:
        """Map the gate-OUT outcome onto the maintainer-observable verdict.

        Reads the STRUCTURED ``verdict`` token of the slice-01 CLI, never a
        free-text substring. When the production-path epic-delta is absent (the
        current tip), the gate cannot have accepted anything -> EPIC_DELTA_ABSENT,
        the active-RED signal.
        """
        if not self.epic_delta_exists:
            return DogfoodVerdict.EPIC_DELTA_ABSENT
        if self.exit_code == 0 and self._verdict_token == "accepted":
            return DogfoodVerdict.ACCEPTED
        return DogfoodVerdict.NOT_ACCEPTED


@dataclass
class DogfoodComposition:
    """Composition root for the slice-06 dogfood slice.

    ``repo_dir`` is the REAL repository root (located from this module's path), NOT a
    tmp_path. The dogfood deliverable is ``docs/epic/flow-v2-wave-migrations/
    epic-delta.md`` produced at DELIVER by the epic-mode authoring procedure. This
    composition OBSERVES that production-path artifact read-only: its EDC structural
    shape, its keystone + dependency order (DC-2), its gate-OUT verdict via the real
    slice-01 CLI, and the §13 coverage-universe completeness. It performs ZERO
    filesystem mutation -- the producer is the DELIVER-stage procedure, never the
    test.
    """

    repo_dir: Path
    epic_id: EpicId = field(default=DOGFOOD_EPIC_ID)

    # --- paths (REAL production path under the real repo root) ----------------

    @property
    def _epic_dir(self) -> Path:
        return self.repo_dir / "docs" / "epic" / self.epic_id

    @property
    def epic_delta_path(self) -> Path:
        return self._epic_dir / "epic-delta.md"

    # --- observations: the dogfood contract on the REAL produced artifact -----

    def observe_dogfood_epic_delta(self) -> DogfoodObservation:
        """Observe the REAL produced epic-delta against the dogfood contract.

        Read-only: the artifact is the DELIVER-stage deliverable; this never writes
        it. On the current tip it is absent -> the active-RED missing-functionality
        observation.
        """
        if not self.epic_delta_path.exists():
            return DogfoodObservation(exists=False)
        content = self.epic_delta_path.read_text(encoding="utf-8")
        rows = _feature_plan_rows(content)
        covered = _covered_section13_items(content, rows)
        return DogfoodObservation(
            exists=True,
            title_line=_first_line(content),
            has_epic_jtbd_section=_EPIC_JTBD_HEADING in content,
            has_feature_plan_heading=_FEATURE_PLAN_HEADING in content,
            feature_plan_columns=_feature_plan_header(content),
            keystone_row_count=_keystone_row_count(rows),
            status_tokens_in_authored_rows=_status_tokens(rows),
            dependency_order_backward_only=_dependency_order_backward_only(rows),
            covered_items=covered,
            uncovered_items=frozenset(Section13Item) - covered,
        )

    def validate_gate_out(self) -> GateOutResult:
        """Validate the REAL produced epic-delta via the slice-01 CLI (EDC-8).

        Drives ``des validate-feature-delta --require-feature-plan --format=json
        <epic-delta>`` -- slice-01's already-shipped driving port -- through its
        real ``main(argv)`` entry. When the artifact is absent (current tip), the
        gate cannot accept it -> EPIC_DELTA_ABSENT.
        """
        if not self.epic_delta_path.exists():
            return GateOutResult(epic_delta_exists=False, exit_code=1, output="")
        argv = [
            "--require-feature-plan",
            "--format=json",
            str(self.epic_delta_path),
        ]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = validate_feature_delta_main(argv)
        return GateOutResult(
            epic_delta_exists=True, exit_code=exit_code, output=buffer.getvalue()
        )


# --- repo-root resolution ---------------------------------------------------
# The real repository root, located from this module's path. Slice-06 observes the
# REAL production path, so the repo root is the actual checkout, never a tmp_path.


def real_repo_root() -> Path:
    """The real repository root (5 levels up from this module file).

    .../tests/scripts/cli/atdd_pure_discuss_epic_mode_dogfood/steps/composition.py
       ^repo  ^tests ^scripts ^cli ^suite           ^steps           ^this file
    """
    return Path(__file__).resolve().parents[5]


# --- EDC + §13 parsing helpers ----------------------------------------------
# Pure functions over the epic-delta content. Kept module-level so step + service
# bodies stay delegations, never inline logic (Mandate-12 criterion 3).


def _first_line(content: str) -> str:
    return content.splitlines()[0] if content.splitlines() else ""


def _gfm_cells(line: str) -> tuple[str, ...]:
    """Split a GFM table row into trimmed cell texts."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return ()
    return tuple(cell.strip() for cell in stripped.strip("|").split("|"))


def _feature_plan_table_lines(content: str) -> list[str]:
    """The contiguous GFM table lines following the Feature Plan heading."""
    lines = content.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == _FEATURE_PLAN_HEADING:
            in_section = True
            continue
        if in_section and line.strip().startswith("|"):
            out.append(line)
        elif in_section and out:
            break
    return out


def _feature_plan_header(content: str) -> tuple[str, ...]:
    table = _feature_plan_table_lines(content)
    return _gfm_cells(table[0]) if table else ()


def _feature_plan_rows(content: str) -> list[tuple[str, ...]]:
    """Data rows (header + separator dropped) of the Feature Plan table."""
    table = _feature_plan_table_lines(content)
    if len(table) < 3:
        return []
    return [_gfm_cells(line) for line in table[2:]]


def _keystone_row_count(rows: list[tuple[str, ...]]) -> int:
    """Rows whose Annotation cell (index 3) carries the keystone token (EDC-5)."""
    return sum(
        1 for cells in rows if len(cells) >= 4 and _KEYSTONE_ANNOTATION in cells[3]
    )


def _status_tokens(rows: list[tuple[str, ...]]) -> tuple[str, ...]:
    """Status cell (index 2) of each authored row (EDC-7)."""
    return tuple(cells[2] for cells in rows if len(cells) >= 3)


def _dependency_order_backward_only(rows: list[tuple[str, ...]]) -> bool:
    """Backward-only dependency order = row order (EDC-6).

    Explicit ``depends-on {feature-id}`` annotations may only reference a feature
    named in an EARLIER row (row K depends only on rows < K). A reference to a
    later or unknown feature is a forward/dangling dependency = violation.
    """
    names_so_far: list[str] = []
    depends_on = re.compile(r"depends-on\s+([A-Za-z0-9-]+)")
    for cells in rows:
        if len(cells) < 4:
            return False
        feature_name = cells[0].strip()
        annotation = cells[3]
        for match in depends_on.finditer(annotation):
            if match.group(1) not in names_so_far:
                return False
        names_so_far.append(feature_name)
    return True


def _documented_exclusions(content: str) -> str:
    """The artifact's documented-exclusions text region, lowercased.

    The slice-06 dogfood completeness contract allows a §13 item to be covered EITHER
    by a Feature Plan row OR by a named exclusion (merge-if-identical-except-scale is
    named in a row's Justification; an Out-of-Scope section may explicitly exclude an
    item). The whole document (lowercased) is the search corpus for the exclusion
    leg -- a deliberately permissive faithfulness check, not a brittle byte-pin.
    """
    return content.lower()


def _covered_section13_items(
    content: str, rows: list[tuple[str, ...]]
) -> frozenset[Section13Item]:
    """Closed 7-item §13 coverage universe items covered by the produced artifact.

    An item is covered when at least one of its keyword phrases (case-insensitive)
    appears in any Feature Plan ROW's joined text (Feature + Value statement +
    Justification cells) OR in the artifact's documented-exclusions corpus. This is
    content-faithfulness as a closed-set semantic assertion -- the §13 source list
    can be re-worded, the contract is that all 7 categories are represented.
    """
    row_corpus = " ".join(" ".join(cells) for cells in rows).lower()
    exclusion_corpus = _documented_exclusions(content)
    covered: set[Section13Item] = set()
    for item, keywords in SECTION_13_ITEM_KEYWORDS.items():
        if any(kw in row_corpus or kw in exclusion_corpus for kw in keywords):
            covered.add(item)
    return frozenset(covered)
