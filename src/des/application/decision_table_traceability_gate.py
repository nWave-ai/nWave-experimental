"""Decision-table <-> AT traceability gate (3 slices shipped).

WHY-NEW-FILE: src/des/application/decision_table_traceability_gate.py
  CLOSEST-EXISTING: src/des/application/walking_skeleton_feature_end_gate.py
  EXTENSION-COST: that gate models the feature-end terminal (slice-shipped +
    integrity), keyed on the AT-completion ledger; the traceability gate models
    a different boundary entirely -- the syntactic join of decision-table
    clause-IDs against `.feature` `# clause:` comments at DISTILL-exit, with a
    non-halting warn verdict. Folding clause<->AT join logic into the
    feature-end gate would couple two unrelated DISTILL/DELIVER concerns.
  PARALLEL-RATIONALE: the DESIGN-table (architecture.md sec.2, feature-delta
    Reuse Analysis) adjudicated this as a CREATE_NEW application-layer use case
    with its own contract shape (pure-function join over parsed inputs); it has
    an incompatible signature (clauses + clause->AT map -> warn result) and a
    distinct lifecycle (runs one concern earlier than the verdict-completeness
    check inside `_handle_distill_exit_gate`).

slice-01 (the SYNTACTIC join, ``evaluate``): a clause is provisionally
witnessed when its clause-ID appears in >=1 `.feature` `# clause:` comment; a
clause with zero such comments is UNWITNESSED and is warned-loud. This is the
DEGRADE path -- it is the verdict used when no behavioral witness port is
injected (``evaluate`` takes no port). It is NOT the final word once a witness
port is available (see slice-03 below).

slice-02 (ID->summary report + ledger record): the warning resolves each
clause-ID to its summary on one line (`<id> (<summary>): <token> ...`, see
`evaluate`) -- the DT-4 report contract, satisfied by slice-01 and
regression-pinned by slice-02. The ledger record of the verdict (DT-10) is
appended by the SubagentStop caller (`_run_decision_table_traceability_gate`),
not by this pure gate.

The gate is NON-HALTING by construction: it produces a warn/pass result. The
caller (the SubagentStop hook) emits the warning to stderr and ALLOWS -- it
never blocks on the traceability verdict (the OSS hooks-only invariant, DT-5).

slice-03 (behavioral witness core, ADR-001): for a NAME-MATCHED clause the
syntactic join is NOT the final witness -- a behavioral witness-check runs HERE.
``evaluate_with_witness`` upgrades each provisionally-witnessed clause (its ID
appears in a ``# clause:`` comment) to an EARNED verdict by running the injected
``ClauseWitnessPort`` differential: it perturbs an isolated copy of the target
into a WRONG RETURN and confirms the AT genuinely fails (and that the failure is
an ``AssertionError`` raised from the AT body, not an incidental error). A
clause whose AT does not genuinely assert its target's RETURN is DOWNGRADED to
``survived`` (the one-line "name a clause, assert nothing" evasion); a clause
whose ``# target:`` does not resolve is surfaced ``target-unresolved`` LOUD; an
AT that fails for a non-assertion reason is ``red-for-wrong-reason``. The
verdict logic stays pure (the ``ClauseWitnessPort`` is injected; the concrete
``PerturbationWitnessAdapter`` carries the isolated-copy perturbation and the
AssertionError-from-AT-body discrimination); only that adapter is language-bound.
Non-halting unchanged: behavioral downgrades only WARN.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.ports.clause_witness_port import ATRef, ClauseWitnessPort


# The unwitnessed-semantics token bound to every warned clause-ID. Sourced from
# the same vocabulary the ATs assert against (`ClauseVerdict.UNWITNESSED_NO_AT`)
# so a degenerate "echo every clause-ID" gate cannot satisfy the contract.
UNWITNESSED_NO_AT_TOKEN = "unwitnessed-no-at"

# slice-03 behavioral-downgrade tokens (ADR-001 evidence vocabulary). A
# name-matched clause whose AT does not genuinely witness it carries one of
# these, distinct from `unwitnessed-no-at` (which means NO AT at all).
SURVIVED_TOKEN = "survived"
TARGET_UNRESOLVED_TOKEN = "target-unresolved"

# A clause-ID is `DT-<digits>` or `DT-<WORD>` -- the immutable join key. The
# feature-delta's own table and the AT substrate both use `DT-ORPHAN` / `DT-WIT`
# in addition to numeric ids, so the id token is alphanumeric + hyphen.
_CLAUSE_ID = r"DT-[A-Za-z0-9-]+"

# The decision-table is the ONE GFM table whose header carries a `clause-ID`
# column. A data row is `| <clause-id> | <summary> | ... |` with >=4 cells.
_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_CLAUSE_ID_CELL = re.compile(rf"^({_CLAUSE_ID})$")

# A `.feature` clause carrier comment: `# clause: DT-N` (whitespace-tolerant).
_CLAUSE_COMMENT = re.compile(rf"^\s*#\s*clause:\s*({_CLAUSE_ID})\s*$")

# A co-located `# target: module::symbol` carrier (slice-03 target resolution).
_TARGET_COMMENT = re.compile(r"^\s*#\s*target:\s*(\S+::\S+)\s*$")

# A `Scenario:` header (the witnessing scenario the carrier comments precede).
_SCENARIO_LINE = re.compile(r"^\s*Scenario:\s*(.+?)\s*$")


@dataclass(frozen=True)
class Clause:
    """One decision-table row's identity (slice-01: id + summary only)."""

    clause_id: str
    summary: str


@dataclass(frozen=True)
class _ClauseVerdict:
    """One clause's behavioral verdict for report rendering (slice-03, internal).

    ``checked`` is True iff the behavioral differential actually ran for this
    clause (a runnable name-matched AT existed). ``witnessed`` is the earned
    verdict. ``evidence`` is the ADR-001 token; ``detail`` is the human gloss.
    """

    clause_id: str
    summary: str
    witnessed: bool
    checked: bool
    evidence: str
    detail: str


@dataclass(frozen=True)
class DecisionTableTraceabilityResult:
    """The non-halting verdict of the syntactic join (slice-01).

    ``verdict`` is ``"warn"`` when >=1 clause is unwitnessed, else ``"pass"``.
    ``warning`` is the loud message naming each unwitnessed clause-ID adjacent to
    the unwitnessed-semantics token; empty when every clause is witnessed.
    """

    verdict: str
    unwitnessed_clause_ids: tuple[str, ...]
    warning: str


class DecisionTableParser:
    """Parse the feature-delta's decision-table into ``Clause`` rows (pure)."""

    def parse(self, feature_delta_text: str) -> list[Clause]:
        clauses: list[Clause] = []
        seen: set[str] = set()
        for line in feature_delta_text.splitlines():
            row = _TABLE_ROW.match(line)
            if row is None:
                continue
            cells = [cell.strip() for cell in row.group(1).split("|")]
            if len(cells) < 4:
                continue
            if _CLAUSE_ID_CELL.match(cells[0]) is None:
                continue
            clause_id = cells[0]
            if clause_id in seen:
                continue
            seen.add(clause_id)
            clauses.append(Clause(clause_id=clause_id, summary=cells[1]))
        return clauses


class ClauseIdFeatureParser:
    """Parse ``# clause: DT-N`` carrier comments from ``.feature`` text (pure)."""

    def witnessed_clause_ids(self, feature_texts: list[str]) -> set[str]:
        witnessed: set[str] = set()
        for text in feature_texts:
            for line in text.splitlines():
                comment = _CLAUSE_COMMENT.match(line)
                if comment is not None:
                    witnessed.add(comment.group(1))
        return witnessed

    def clause_targets(
        self, feature_files: list[tuple[str, str]]
    ) -> dict[str, list[ATRef]]:
        """Map each clause-ID to its claimed witnessing ATs (slice-03).

        ``feature_files`` is a list of ``(at_module_path, feature_text)`` pairs:
        the path of the executable AT module the witness-check runs (relative to
        the repo) co-located with the carrier ``.feature`` text. Each
        ``# clause:`` comment with a co-located ``# target:`` and a following
        ``Scenario:`` produces one ``ATRef``. A clause comment without a
        parseable ``# target:`` produces an ``ATRef`` with an empty target so
        the gate surfaces it ``target-unresolved`` (never a soft skip, DT-12).
        """
        from des.ports.clause_witness_port import ATRef

        targets: dict[str, list[ATRef]] = {}
        for at_path, text in feature_files:
            pending_clause: str | None = None
            pending_target: str | None = None
            for line in text.splitlines():
                clause = _CLAUSE_COMMENT.match(line)
                if clause is not None:
                    pending_clause = clause.group(1)
                    pending_target = None
                    continue
                target = _TARGET_COMMENT.match(line)
                if target is not None:
                    pending_target = target.group(1)
                    continue
                scenario = _SCENARIO_LINE.match(line)
                if scenario is not None and pending_clause is not None:
                    ref = ATRef(
                        scenario=scenario.group(1),
                        target=pending_target or "",
                        at_path=at_path,
                    )
                    targets.setdefault(pending_clause, []).append(ref)
                    pending_clause = None
                    pending_target = None
        return targets


class DecisionTableTraceabilityGate:
    """Join decision-table clauses against witnessing ATs (slice-01, syntactic).

    Pure derivation: given the parsed clauses and the set of clause-IDs carried
    by ``.feature`` comments, every clause whose id is NOT in the witnessed set
    is UNWITNESSED and warned-loud. Non-halting: the result is a verdict value,
    never a block.
    """

    def evaluate(
        self, clauses: list[Clause], witnessed_clause_ids: set[str]
    ) -> DecisionTableTraceabilityResult:
        unwitnessed = [c for c in clauses if c.clause_id not in witnessed_clause_ids]
        if not unwitnessed:
            return DecisionTableTraceabilityResult(
                verdict="pass", unwitnessed_clause_ids=(), warning=""
            )
        report_lines = [
            f"  - {c.clause_id} ({c.summary}): {UNWITNESSED_NO_AT_TOKEN} "
            "(no witnessing acceptance test)"
            for c in unwitnessed
        ]
        warning = (
            "DECISION-TABLE TRACEABILITY WARNING (non-halting): the following "
            "decision-table clause(s) have no witnessing acceptance test "
            f"({UNWITNESSED_NO_AT_TOKEN}):\n" + "\n".join(report_lines)
        )
        return DecisionTableTraceabilityResult(
            verdict="warn",
            unwitnessed_clause_ids=tuple(c.clause_id for c in unwitnessed),
            warning=warning,
        )

    def evaluate_with_witness(
        self,
        clauses: list[Clause],
        witnessed_clause_ids: set[str],
        clause_targets: dict[str, list[ATRef]],
        witness_port: ClauseWitnessPort,
    ) -> DecisionTableTraceabilityResult:
        """Behavioral witness-aware verdict (slice-03, ADR-001 differential).

        Each clause carrying a runnable name-matched AT is upgraded from the
        syntactic ``witnessed-by-name`` to an EARNED behavioral verdict via the
        injected ``witness_port``: ``witnessed`` (the AT genuinely asserts its
        target's RETURN) / ``survived`` (executes but does not assert) /
        ``target-unresolved`` (``# target:`` does not resolve) /
        ``red-for-wrong-reason``. A clause with no AT at all is the slice-01
        ``unwitnessed-no-at``.

        REPORT SHAPE (the DT-7a / DT-8 reconciliation): when >=1 clause is
        DOWNGRADED the warning names only the downgraded clauses (a genuinely
        witnessed clause stays out of the warning -- DT-7a). When EVERY checked
        clause is genuinely witnessed the gate emits a positive
        "all clauses witnessed" report that names each witnessed clause adjacent
        to the ``witnessed`` token -- the clean-pass observable that proves the
        differential actually RAN (DT-8 tree-safety binds its byte-identity
        assertion to this proof-of-run, so a no-op gate cannot pass DT-8
        trivially). Both report shapes are loud + non-halting.

        Pure over the injected port: the verdict logic is code, the language-
        bound perturbation lives behind the port. Non-halting unchanged.
        """
        verdicts = [
            self._clause_behavioral_verdict(
                clause, witnessed_clause_ids, clause_targets, witness_port
            )
            for clause in clauses
        ]
        downgraded = [v for v in verdicts if not v.witnessed]
        if downgraded:
            return self._warn_result(
                downgraded,
                "the following decision-table clause(s) are not genuinely "
                "witnessed by an acceptance test:",
            )
        witnessed = [v for v in verdicts if v.checked]
        if witnessed:
            # Clean pass: every checked clause is genuinely witnessed. Emit the
            # positive report (proof the behavioral differential ran -- DT-8).
            return self._warn_result(
                witnessed,
                "every decision-table clause is genuinely witnessed by an "
                "acceptance test:",
            )
        # No clause was behaviorally checked and none downgraded -> nothing to
        # report (mirrors slice-01/02: name-matched-only carriers stay silent).
        return DecisionTableTraceabilityResult(
            verdict="pass", unwitnessed_clause_ids=(), warning=""
        )

    def _warn_result(
        self, verdicts: list[_ClauseVerdict], header: str
    ) -> DecisionTableTraceabilityResult:
        report_lines = [
            f"  - {v.clause_id} ({v.summary}): {v.evidence} ({v.detail})"
            for v in verdicts
        ]
        warning = (
            "DECISION-TABLE TRACEABILITY WARNING (non-halting): "
            f"{header}\n" + "\n".join(report_lines)
        )
        return DecisionTableTraceabilityResult(
            verdict="warn",
            unwitnessed_clause_ids=tuple(v.clause_id for v in verdicts),
            warning=warning,
        )

    def _clause_behavioral_verdict(
        self,
        clause: Clause,
        witnessed_clause_ids: set[str],
        clause_targets: dict[str, list[ATRef]],
        witness_port: ClauseWitnessPort,
    ) -> _ClauseVerdict:
        """The per-clause behavioral verdict value (slice-03)."""
        if clause.clause_id not in witnessed_clause_ids:
            return _ClauseVerdict(
                clause_id=clause.clause_id,
                summary=clause.summary,
                witnessed=False,
                checked=False,
                evidence=UNWITNESSED_NO_AT_TOKEN,
                detail="no witnessing acceptance test",
            )
        at_refs = clause_targets.get(clause.clause_id, [])
        if not at_refs:
            # Name-matched but no RUNNABLE witnessing AT module: fall back to the
            # slice-01 syntactic verdict (witnessed-by-name). There is no AT to
            # run the differential against, so the gate does NOT downgrade and
            # does NOT count it as a behaviorally-checked witness -- it stays out
            # of both report shapes (slice-01/02 silence preserved).
            return _ClauseVerdict(
                clause_id=clause.clause_id,
                summary=clause.summary,
                witnessed=True,
                checked=False,
                evidence="witnessed-by-name",
                detail="name-matched (no runnable AT to behaviorally check)",
            )
        report = witness_port.witness(clause.clause_id, at_refs)
        if report.witnessed:
            return _ClauseVerdict(
                clause_id=clause.clause_id,
                summary=clause.summary,
                witnessed=True,
                checked=True,
                evidence=report.evidence,
                detail="acceptance test genuinely witnesses this clause",
            )
        return _ClauseVerdict(
            clause_id=clause.clause_id,
            summary=clause.summary,
            witnessed=False,
            checked=True,
            evidence=report.evidence,
            detail="acceptance test does not genuinely witness this clause",
        )
