"""Composition root for the discuss-epic-mode slice-02 acceptance slice.

Slice-02 value: a maintainer runs ``/nw-discuss --epic <id>`` and gets a
*validated* epic-delta instead of cutting features by hand.

Honest mechanical-vs-prompt boundary (the central slice-02 decision)
====================================================================
The epic-delta is AUTHORED by the Luna PO agent during an LLM-mediated discuss
session. That authoring act is PROMPT-SURFACE -- not mechanically testable. Per
the DESIGN slice-02/04/05 text contracts section: the "code" of this slice is
SKILL / COMMAND text; there is NO ``src/des`` surface; DESIGN pins the EDC as the
AT-citable contract.

What these ATs PIN (mechanical):
  - EDC structural shape of the PRODUCED epic-delta artifact (EDC-1..EDC-7):
    filesystem + document observation at the production path
    ``docs/epic/{id}/epic-delta.md`` -- the DESIGN-named driving port for
    slice-02 ATs ("artifact/filesystem observation: the epic-delta file content
    vs EDC").
  - The gate-OUT seam (EDC-8): the produced epic-delta validates ``accepted``
    through the REAL slice-01 CLI ``des validate-feature-delta
    --require-feature-plan --format=json`` (``des.cli.validate_feature_delta.main``).
    This is the only mechanical seam slice-02 drives, and it is slice-01's
    already-shipped surface (slice-02 depends on slice-01).
  - The fractal-JIT invariant (EDC-9): the run produces ONLY the epic-delta --
    zero ``docs/feature/{id}/`` workspaces.

What stays PROMPT-SURFACE (deliberately NOT an AT):
  - Discoverability ("skill Tier-1 surfaces ``--epic``"). A prose-grep AT would be
    the presence-watcher anti-pattern + Fixture Theater (passes the instant the
    crafter types the literal, testing no behaviour). Discoverability is verified
    by the Sentinel review of the landed skill text and lives mechanically in the
    slice-04 escalation contract (ESC-3), not here.

Active-RED contract (atdd_pure)
===============================
Slice-02 has NO net-new ``src/des`` validator seam (DESIGN reuse table: text-only;
DC-2 defers keystone/dep-order mechanical validation to slice-06). The active-RED
is therefore at the ARTIFACT layer, mirroring slice-01's "flag doesn't exist yet"
RED one level up: the EDC-conformant epic-delta the ``--epic`` authoring procedure
MUST produce does NOT exist at its production path on the current tip (the
authoring procedure is the slice-02 deliverable). Every EDC observation therefore
reads an ABSENT artifact -> ``EPIC_DELTA_ABSENT`` / missing structural pins ->
semantic ``AssertionError`` -- a deliberate missing-functionality RED, never a
collection / import error. DELIVER (slice-02) makes them GREEN by authoring the
``--epic`` procedure (skill/command text) AND producing a conformant epic-delta at
the production path.

S3 dormant-seam reconciliation: slice-02 declares ZERO net-new ``src/des`` seams
(DESIGN: "no ``src/des`` surface"). The only mechanical seam driven is slice-01's
already-shipped CLI, reached through its real ``main(argv)`` entry point in the
gate-OUT AT. No net-new seam can ship dormant -- S3 = PASS by construction.

Layer 3 (subprocess/FS acceptance): the driving ports are (a) the produced
epic-delta artifact (filesystem observation) and (b) the real slice-01 CLI for the
gate-OUT leg. No PBT machinery (Mandate 9/11) -- the EDC is a finite, enumerable
closed contract set.
"""

from __future__ import annotations

import contextlib
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

# The ONLY production import (S2 driving-port-only invariant): the slice-01
# validate-feature-delta CLI, already shipped (slice-02 depends on slice-01). It is
# the sole mechanical `src/des` seam slice-02 drives -- the gate-OUT leg (EDC-8).
# Phase C resolution (2026-06-11, Ruling B): the deterministic epic-delta emitter
# is NOT production code -- it is the suite-local reference producer
# (`_reference_oracle.py`), a golden-file analogue for the LLM-mediated `--epic`
# authoring. It is wired ONLY at GREEN (see `run_epic_mode_authoring` below).
from des.cli.validate_feature_delta import (
    main as validate_feature_delta_main,
)

from .domain_types import EpicDeltaVerdict, EpicId


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
class EpicDeltaObservation:
    """Read-only observation of the produced epic-delta artifact.

    ``exists`` is the production-path presence of ``epic-delta.md``. The rest are
    EDC structural observations parsed from its content; they are meaningful only
    when ``exists`` is True. On the current tip the artifact is absent (the
    ``--epic`` authoring procedure is undefined), so ``exists`` is False and the
    structural observations read their empty defaults -- the active-RED state.
    """

    exists: bool
    title_line: str = ""
    has_epic_jtbd_section: bool = False
    has_feature_plan_heading: bool = False
    feature_plan_columns: tuple[str, ...] = ()
    keystone_row_count: int = 0
    status_tokens_in_authored_rows: tuple[str, ...] = ()
    dependency_order_backward_only: bool = False


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
    def verdict(self) -> EpicDeltaVerdict:
        """Map the gate-OUT outcome onto the maintainer-observable verdict.

        Reads the STRUCTURED ``verdict`` token of the slice-01 CLI, never a
        free-text substring. When the production-path epic-delta is absent (the
        current tip), the gate cannot have accepted anything -> EPIC_DELTA_ABSENT,
        the active-RED signal.
        """
        if not self.epic_delta_exists:
            return EpicDeltaVerdict.EPIC_DELTA_ABSENT
        if self.exit_code == 0 and self._verdict_token == "accepted":
            return EpicDeltaVerdict.ACCEPTED
        return EpicDeltaVerdict.NOT_ACCEPTED


@dataclass
class EpicModeAuthoringComposition:
    """Composition root for the slice-02 epic-mode authoring slice.

    ``repo_dir`` is a real tmp_path acting as the repository root. The
    ``--epic <id>`` run is expected to produce ``docs/epic/{id}/epic-delta.md``
    (EDC-1). This composition observes that production-path artifact: its EDC
    structural shape, its gate-OUT verdict via the real slice-01 CLI, and the
    fractal-JIT invariant on the feature workspace tree.
    """

    repo_dir: Path
    epic_id: EpicId = field(default=EpicId("flow-v2-wave-migrations"))

    # --- paths ---------------------------------------------------------------

    @property
    def _epic_dir(self) -> Path:
        return self.repo_dir / "docs" / "epic" / self.epic_id

    @property
    def epic_delta_path(self) -> Path:
        return self._epic_dir / "epic-delta.md"

    @property
    def _feature_workspace_root(self) -> Path:
        return self.repo_dir / "docs" / "feature"

    # --- Given: a maintainer with a multi-feature epic -----------------------

    def open_epic(self, epic_id: EpicId) -> None:
        """Establish the epic identity + repository skeleton for the run."""
        self.epic_id = epic_id
        self.repo_dir.mkdir(parents=True, exist_ok=True)

    # --- When: the maintainer runs the --epic authoring ----------------------

    def run_epic_mode_authoring(self) -> None:
        """Run the ``/nw-discuss --epic <id>`` authoring procedure.

        PROMPT-SURFACE boundary: the authoring is the Luna PO agent filling in the
        epic-JTBD + Feature Plan rows during an LLM-mediated discuss session. The
        slice-02 deliverable is PROSE (DESIGN slice-02/04/05 text contracts: the
        slice's "code" is SKILL / COMMAND text, there is NO ``src/des`` surface).

        DESIGNATED GREEN WIRING POINT (atdd_pure, Phase C resolution 2026-06-11):
        on the current tip this is a documented NO-OP -- it imports nothing from
        the suite-local reference oracle yet, so the ``--epic`` run produces no
        epic-delta. Every downstream EDC observation therefore reads an ABSENT
        artifact -> ``EPIC_DELTA_ABSENT`` / missing structural pins -> semantic
        ``AssertionError`` (artifact-absence active-RED).

        DELIVER (slice-02) makes the ATs GREEN at THIS exact seam by (i) wiring the
        suite-local reference producer here:
        ``from ._reference_oracle import author_epic_delta, default_flow_v2_plan``
        then ``author_epic_delta(self.repo_dir, default_flow_v2_plan())`` -- a
        golden-file analogue, NOT a ``src/des`` import -- AND (ii) authoring the
        prose deliverable (``--epic`` section in ``nWave/skills/nw-discuss/SKILL.md``
        + ``nWave/tasks/nw/discuss.md``). Filling this Sentinel-approved no-op seam
        is NOT a Driving-Port-Only-Boundary violation; importing ``src/des``
        application code was.
        """
        # GREEN wiring (slice-02): the suite-local reference producer stands in for
        # the LLM-mediated `--epic` authoring (a golden-file analogue, NOT a src/des
        # import). It renders an EDC-conformant epic-delta at the production path and
        # produces ONLY that artifact (EDC-9 fractal JIT -- no feature workspaces).
        from ._reference_oracle import author_epic_delta, default_flow_v2_plan

        author_epic_delta(self.repo_dir, default_flow_v2_plan())

    # --- observations: EDC contract on the produced artifact -----------------

    def observe_epic_delta(self) -> EpicDeltaObservation:
        """Observe the produced epic-delta against the EDC structural contract."""
        if not self.epic_delta_path.exists():
            return EpicDeltaObservation(exists=False)
        content = self.epic_delta_path.read_text(encoding="utf-8")
        rows = _feature_plan_rows(content)
        return EpicDeltaObservation(
            exists=True,
            title_line=_first_line(content),
            has_epic_jtbd_section=_EPIC_JTBD_HEADING in content,
            has_feature_plan_heading=_FEATURE_PLAN_HEADING in content,
            feature_plan_columns=_feature_plan_header(content),
            keystone_row_count=_keystone_row_count(rows),
            status_tokens_in_authored_rows=_status_tokens(rows),
            dependency_order_backward_only=_dependency_order_backward_only(rows),
        )

    def validate_gate_out(self) -> GateOutResult:
        """Validate the produced epic-delta via the REAL slice-01 CLI (EDC-8).

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

    def count_feature_workspaces(self) -> int:
        """Count ``docs/feature/{id}/`` workspaces produced by the run (EDC-9).

        Fractal JIT: an ``--epic`` run produces ONLY the epic-delta. A non-zero
        count means the run eagerly created feature workspaces upfront -- a D-jit
        violation.
        """
        root = self._feature_workspace_root
        if not root.exists():
            return 0
        return sum(1 for child in root.iterdir() if child.is_dir())

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        Slice-02 mutates no repository state via a validator -- the only
        observable is the produced-artifact surface: the epic-delta's existence
        and the feature-workspace count. The When-step gate-OUT validation is the
        slice-01 pure-function read (no mutation), so both are asserted unchanged
        by the validation step; AT-3 asserts the JIT count directly.
        """
        return {
            "epic_delta.exists": self.epic_delta_path.exists(),
            "feature_workspaces.count": self.count_feature_workspaces(),
        }


# --- EDC parsing helpers ----------------------------------------------------
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
