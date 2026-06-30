"""Composition root for f-wave-contract-coherence slice-07 (epic-delta reconciliation).

DRIVING SURFACE (Mandate-13 driving-port-only -- shipped artifacts as production
reads them, no direct-domain business logic at the step boundary):

  * the SHIPPED epic-delta ``docs/epic/flow-v2-wave-migrations/epic-delta.md``
    parsed through the PRODUCTION feature-plan parser the validator uses
    (``validate_feature_delta._plan_table_rows`` + ``_FEATURE_PLAN_HEADING_RE`` +
    ``_parse_table_cells``) -- Layer 3 composition over the real read path, NOT a
    test-local markdown reader (AT-19 / AT-21 read #1);
  * the REAL ``des validate-feature-delta --require-feature-plan --format=json``
    subcommand invoked as a subprocess over the SHIPPED epic-delta -- Layer 3
    subprocess through the shipped ``des`` dispatcher (AT-20);
  * the REAL ``scripts/flow_v2_closure_scorecard.py`` ``FEATURES`` list sourced
    from the SHIPPED script via ``runpy.run_path`` with a NON-``__main__`` run name
    (loads the module-level ``FEATURES`` binding WITHOUT executing ``main()``, so the
    scorecard is READ, never run and never mutated -- it is the GOAL CONTRACT, Ale
    2026-06-15) -- AT-21 read #2.

Mandate-14 @real-io: real filesystem reads + a real OS subprocess. The fixtures set
up PRECONDITIONS (the shipped paths) only -- never the expected output (Critical Rule
7, no fixture theater): the feature-id sets and the verdict are the SUT's own
emissions over the shipped files, not values the test fabricated.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): slice-07 lands NO net-new code seam --
it is the LSC-1 epic-mode maintenance act (ADD the 8 missing Feature Plan rows to the
SHIPPED epic-delta so its inventory matches the scorecard). The "seam" each AT names
and drives is the SHIPPED epic-delta document + the SHIPPED feature-plan validator +
the SHIPPED scorecard; the observable effect is the reconciled inventory (count==live,
validator-accepts, set-equality). DELIVER makes these GREEN by editing the epic-delta
markdown (DATA), not by adding executable code.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the SHIPPED epic-delta Feature
Plan lists 6 of the 14 live features (8 missing), so AT-19 (count<live) and AT-21
(set mismatch) fire a semantic ``AssertionError`` naming the EXACT missing feature-ids,
and AT-20 fires because the accepted-AND-complete conjunction is not yet satisfied
(the validator accepts the structure, but the structure does not cover the live set).
Every failure is a business-fact mismatch, never a collection / import / setup error.
GREEN once DELIVER adds the missing rows to the epic-delta.
"""

from __future__ import annotations

import json
import runpy
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# tests/des/acceptance/f-wave-contract-coherence/acceptance/steps/<this file>
#   parents[6] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[6]

# The SHIPPED canonical epic-delta whose Feature Plan is the epic's feature
# inventory (LSC-4). slice-07 reconciles its Feature Plan to the live set.
_EPIC_DELTA = REPO_ROOT / "docs" / "epic" / "flow-v2-wave-migrations" / "epic-delta.md"

# The SHIPPED closure scorecard -- the GOAL CONTRACT (Ale 2026-06-15). Its
# FEATURES list declares the live feature set. READ here, NEVER executed/mutated.
_SCORECARD = REPO_ROOT / "scripts" / "flow_v2_closure_scorecard.py"

# The operator-visible feature-plan validator subcommand (the shipped gate).
_VALIDATOR_SUBCOMMAND = "validate-feature-delta"


def _epic_delta_feature_ids() -> tuple[str, ...]:
    """Read the epic-delta Feature Plan feature-ids via the PRODUCTION parser.

    Independent read #1 of the inventory: drives the SAME feature-plan table walk
    the validator uses (``validate_feature_delta._plan_table_rows`` with the
    ``_FEATURE_PLAN_HEADING_RE`` + ``_parse_table_cells``), so the AT exercises the
    real parse path, not a test-local markdown reader. The feature-id is column 1
    (``Feature``) of each data row, normalised (strip surrounding code-span
    backticks / bold markers a maintainer might add).

    Returns the ordered feature-ids, or an empty tuple when the epic-delta or its
    Feature Plan section is absent (the RED diagnostic distinguishes the two).
    """
    if not _EPIC_DELTA.is_file():
        return ()
    # mandate-13-ok: the production feature-plan parser the shipped validator uses,
    # invoked over the SHIPPED epic-delta -- not a test-local YAML/markdown reader.
    from des.cli import validate_feature_delta as vfd

    content = _EPIC_DELTA.read_text(encoding="utf-8")
    rows = vfd._plan_table_rows(content, vfd._FEATURE_PLAN_HEADING_RE)
    if not rows:
        return ()
    data_rows = [row for row in rows[1:] if not vfd._is_separator_row(row)]
    ids: list[str] = []
    for row in data_rows:
        cells = vfd._parse_table_cells(row)
        if not cells:
            continue
        ids.append(_normalise_feature_id(cells[0]))
    return tuple(ids)


def _normalise_feature_id(raw: str) -> str:
    """Strip a Feature cell down to the bare feature-id token.

    Tolerates a maintainer rendering the id as ``f-x``, ``**f-x**``, or ``f-x``
    in a code span -- the inventory join-key is the bare id, not its markup.
    """
    token = raw.strip()
    if token.startswith("**") and token.endswith("**") and len(token) >= 4:
        token = token[2:-2]
    return token.strip().strip("`").strip()


def _scorecard_feature_ids() -> tuple[str, ...]:
    """Read the live feature set from the SHIPPED scorecard FEATURES list.

    Independent read #2: sources the module-level ``FEATURES`` binding from the
    SHIPPED ``scripts/flow_v2_closure_scorecard.py`` via ``runpy.run_path`` with a
    NON-``__main__`` run name -- this loads the binding WITHOUT executing ``main()``
    (the ``if __name__ == "__main__"`` guard never fires), so the scorecard is READ,
    never run and never mutated. The scorecard is the GOAL CONTRACT (Ale 2026-06-15):
    this AT consumes it as an oracle, it does NOT edit it.

    Returns the ordered feature-ids the scorecard declares, or an empty tuple when
    the scorecard file is absent.
    """
    if not _SCORECARD.is_file():
        return ()
    namespace = runpy.run_path(str(_SCORECARD), run_name="__at_sourced__")
    features = namespace.get("FEATURES")
    if not isinstance(features, list):
        return ()
    ids: list[str] = []
    for entry in features:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str):
            ids.append(entry["id"])
    return tuple(ids)


@dataclass(frozen=True)
class _ValidatorRun:
    """The observable boundary DTO of one feature-plan validator subprocess run."""

    verdict: str | None
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class EpicDeltaReconciliationComposition:
    """Drives the SHIPPED epic-delta / scorecard / validator for slice-07 ATs."""

    _epic_ids: tuple[str, ...] | None = field(default=None)
    _scorecard_ids: tuple[str, ...] | None = field(default=None)
    _read: bool = field(default=False)
    _validator: _ValidatorRun | None = field(default=None)

    # ---- given --------------------------------------------------------------

    def given_shipped_epic_delta_and_scorecard(self) -> None:
        """Arm the SUT to read the SHIPPED epic-delta + scorecard from the repo.

        PRECONDITION only -- the shipped artifacts ARE the contract under test; no
        expected output is fabricated. At HEAD both files exist but the epic-delta
        Feature Plan is short of the live set (the inventory RED).
        """
        # Nothing to stage beyond pointing at the shipped paths -- the documents
        # themselves carry the inventory the ATs reconcile.

    # ---- when ---------------------------------------------------------------

    def when_epic_delta_feature_plan_is_read(self) -> None:
        """Read the epic-delta Feature Plan feature-ids via the production parser."""
        self._read = True
        self._epic_ids = _epic_delta_feature_ids()
        self._scorecard_ids = _scorecard_feature_ids()

    def when_validator_runs_over_epic_delta(self) -> None:
        """Invoke the REAL des validate-feature-delta --require-feature-plan subprocess.

        Drives the shipped ``des`` dispatcher over the SHIPPED epic-delta, capturing
        the JSON verdict. Also reads both inventories so the Then can assert the
        accepted-AND-complete conjunction (accepted = non-regression guard; complete =
        the RED clause).
        """
        self._read = True
        self._epic_ids = _epic_delta_feature_ids()
        self._scorecard_ids = _scorecard_feature_ids()
        argv = [
            sys.executable,
            "-m",
            "des",
            _VALIDATOR_SUBCOMMAND,
            "--require-feature-plan",
            "--format=json",
            str(_EPIC_DELTA),
        ]
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
            cwd=str(REPO_ROOT),
        )
        self._validator = _ValidatorRun(
            verdict=_parse_verdict(completed.stdout),
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )

    def when_both_id_sets_are_read(self) -> None:
        """Read BOTH the epic-delta and scorecard feature-id sets (AT-21)."""
        self._read = True
        self._epic_ids = _epic_delta_feature_ids()
        self._scorecard_ids = _scorecard_feature_ids()

    # ---- then: AT-19 (every live feature is listed) --------------------------

    def then_epic_delta_lists_every_live_feature(self) -> None:
        """Every scorecard feature-id appears as an epic-delta Feature Plan row.

        Seam-named oracle: the live set (scorecard FEATURES) must be a SUBSET of the
        epic-delta Feature Plan inventory -- no live feature missing. RED at HEAD: the
        epic-delta lists 6 of 14, so 8 are missing; the AssertionError names the EXACT
        missing ids so DELIVER knows precisely which rows to ADD.
        """
        epic_ids, scorecard_ids = self._require_read()
        assert scorecard_ids, (
            "the scorecard FEATURES list must be sourced from the shipped "
            f"{_SCORECARD} (the live feature set / GOAL CONTRACT) -- it read EMPTY. "
            f"{self._observed()}"
        )
        missing = [fid for fid in scorecard_ids if fid not in set(epic_ids)]
        assert not missing, (
            "the epic-delta Feature Plan must list EVERY feature in the live set "
            f"(LSC-4: the epic-delta is the canonical feature inventory, {_EPIC_DELTA}); "
            f"{len(missing)} live feature(s) are MISSING and must be ADDED as Feature "
            f"Plan rows by DELIVER: {missing}. {self._observed()}"
        )

    # ---- then: AT-20 (validator accepts a complete plan) ---------------------

    def then_validator_accepts_complete_feature_plan(self) -> None:
        """The validator ACCEPTS the epic-delta AND the plan covers the live set.

        Two clauses, both required:
          (1) non-regression guard -- the feature-plan validator must emit the
              ``accepted`` verdict over the SHIPPED epic-delta (the reconciled
              epic-delta must stay structurally valid after the rows are added);
          (2) RED clause -- the accepted plan must COVER the live set (every scorecard
              feature is a row). At HEAD the validator already emits ``accepted`` for
              the 6-row structure, so clause (1) holds; clause (2) FAILS because the
              structure does not yet cover the 14 live features. The conjunction makes
              this AT active-RED today and a regression guard once GREEN -- it can
              never pass on a still-incomplete-but-structurally-valid epic-delta.
        """
        epic_ids, scorecard_ids = self._require_read()
        assert self._validator is not None, (
            "the feature-plan validator must run (When) before asserting (Then)"
        )
        inv = self._validator
        assert inv.verdict == "accepted", (
            "the feature-plan validator (des validate-feature-delta "
            "--require-feature-plan) must ACCEPT the epic-delta -- the reconciled "
            f"epic-delta must stay structurally valid; it emitted {inv.verdict!r}. "
            f"{self._observed()}"
        )
        assert scorecard_ids, (
            "the scorecard FEATURES list (live set) must read non-empty from "
            f"{_SCORECARD}. {self._observed()}"
        )
        missing = [fid for fid in scorecard_ids if fid not in set(epic_ids)]
        assert not missing, (
            "the validator-accepted epic-delta Feature Plan must COVER every live "
            f"feature -- {len(missing)} are still missing, so the accepted plan is "
            f"INCOMPLETE: {missing}. DELIVER must ADD these rows (the validator stays "
            f"accepted; the coverage clause is what is RED today). {self._observed()}"
        )

    # ---- then: AT-21 (no drift -- the two id sets are equal) -----------------

    def then_epic_delta_id_set_equals_scorecard_id_set(self) -> None:
        """The epic-delta and scorecard feature-id SETS are equal -- no drift.

        Two INDEPENDENT reads (production feature-plan parser over the epic-delta vs
        the scorecard FEATURES binding) must yield the SAME set -- in BOTH directions:
        no live feature missing from the inventory, no stale phantom row absent from
        the live set. RED at HEAD: the sets differ by the 8 features absent from the
        epic-delta; the AssertionError names both diffs.
        """
        epic_ids, scorecard_ids = self._require_read()
        assert scorecard_ids, (
            "the scorecard FEATURES list (live set) must read non-empty from "
            f"{_SCORECARD}. {self._observed()}"
        )
        epic_set, scorecard_set = set(epic_ids), set(scorecard_ids)
        missing_from_epic = sorted(scorecard_set - epic_set)
        stale_in_epic = sorted(epic_set - scorecard_set)
        assert epic_set == scorecard_set, (
            "the epic-delta Feature Plan feature-id set must EQUAL the scorecard "
            "FEATURES feature-id set (LSC-4: no inventory drift). "
            f"missing from the epic-delta (must be ADDED): {missing_from_epic}; "
            f"stale rows in the epic-delta (must be REMOVED): {stale_in_epic}. "
            f"{self._observed()}"
        )

    # ---- helpers ------------------------------------------------------------

    def _require_read(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        assert self._read, "the inventories must be read (When) before asserting (Then)"
        epic = self._epic_ids if self._epic_ids is not None else ()
        scorecard = self._scorecard_ids if self._scorecard_ids is not None else ()
        return epic, scorecard

    def _observed(self) -> str:
        return (
            f"epic_delta={_EPIC_DELTA} (exists={_EPIC_DELTA.is_file()}); "
            f"scorecard={_SCORECARD} (exists={_SCORECARD.is_file()}); "
            f"epic_ids={self._epic_ids!r}; scorecard_ids={self._scorecard_ids!r}; "
            f"validator_verdict="
            f"{self._validator.verdict if self._validator else None!r}"
        )


def _parse_verdict(stdout: str) -> str | None:
    """Parse the ``verdict`` token from the validator's JSON-stdout line.

    Tolerates the dev-checkout freshness banner line preceding the JSON object.
    Returns None when no JSON line carries a verdict.
    """
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            verdict = payload.get("verdict")
            return verdict if isinstance(verdict, str) else None
    return None
