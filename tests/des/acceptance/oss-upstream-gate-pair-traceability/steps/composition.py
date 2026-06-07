"""Composition root for the traceability gate walking skeleton (slice-01).

This is the *only* place the production system is wired for the slice-01 ATs.
It drives the production ``handle_subagent_stop`` SubagentStop hook end-to-end
through its real JSON stdin protocol **as a subprocess** (Mandate-13
driving-port-only, Layer 3/4 wiring_e2e), mirroring the shipped, proven
RED-for-right-reason exemplar
``tests/des/acceptance/oss-hook-side-phase-injection/steps/composition.py``.

INVOCATION (load-bearing): the hook module has NO ``__main__`` / ``main()``
block -- ``python -m des...subagent_stop_handler`` would import + define and
exit 0 reading nothing (a no-op that makes RED structurally indistinguishable
from a correct-gate RED). So we invoke via
``python -c "...; from ...subagent_stop_handler import handle_subagent_stop;
sys.exit(handle_subagent_stop())"`` exactly as the sibling does -- this genuinely
CALLS the hook over its real JSON stdin protocol. Still driving-port-only:
subprocess boundary, no in-process production import in the step module.

ROUTING (load-bearing): ``_resolve_des_context`` only routes to the atdd_pure
D_DISTILL gate when the agent transcript carries a ``DES-MODE:atdd_pure`` +
``D_DISTILL`` marker block. Absent the transcript the handler returns
allow/exit-0 and ``_handle_distill_exit_gate`` is never reached. So we seed a
real transcript carrying that marker block (markers point at the tmp repo +
feature-id) and pass its path as ``agent_transcript_path``. The traceability
gate, once DELIVER wires it, resolves ``repo = effective_cwd`` (from the
validated ``DES-PROJECT-ROOT`` marker) and ``feature_id = project_id`` (from
``DES-PROJECT-ID``), then reads our decision-table at
``{repo}/docs/feature/{feature_id}/feature-delta.md``.

HONEST SUBSTRATE (so DT-5's Gherkin sentences are literally asserted): the
orthogonal downstream verdict-completeness gate (architecture.md step 2) blocks
unless every PLANNED slice carries a signed ``ATReviewVerdict``. We seed one
signed verdict for the single planned slice (``slice-01``) as PRECONDITION
state, through the production ``AtCompletionLedger.append_review_verdict`` writer
-- exactly the sibling pattern. The downstream gate then ALLOWS, so the hook
emits NO ``{"decision":"block"}`` on stdout and exits 0. DT-5 can now assert
LITERALLY what its Gherkin promises -- "lets the feature proceed to DELIVER"
(``'"decision": "block"' not in stdout``) and "exits with code zero"
(``returncode == 0``). The seed is PRECONDITION substrate via the real writer,
NOT the SUT and NOT a DT-10 outcome assertion. The RED is still
gate-absent-right-reason: the traceability gate (warn-to-stderr) is unwired, so
the "unwitnessed clause named in loud stderr warning" assertion still fails --
while DT-5's proceed/exit-zero halves are now genuinely witnessed.

NO production module is imported here for the SUT -- the SUT is exercised only
via the hook subprocess. ``AtCompletionLedger`` is imported ONLY to seed the
precondition verdict record (substrate), the S2 tolerable-variant "seed
precondition state through the production writer" (sibling composition.py:44).
The ledger record is a slice-02 outcome concern, asserted there, not here.

State lives on the instance; every ``given_/when_/then_`` method mutates or reads
that state. Step functions in ``test_g_traceability_gate_slice_01.py`` are thin
delegations to these methods (Mandate-12: no business logic in step bodies).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# Precondition-substrate writer (NOT the SUT). Mirrors the sibling composition
# (oss-hook-side-phase-injection/steps/composition.py:44): seeds the signed
# ATReviewVerdict the DOWNSTREAM verdict-completeness gate reads so it ALLOWS,
# making DT-5's "proceed to DELIVER" / "exit zero" Gherkin literally assertable.
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

from .domain_types import ClauseVerdict, EmissionChannel


# tests/des/acceptance/oss-upstream-gate-pair-traceability/steps/composition.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]
HOOK_MODULE = "des.adapters.drivers.hooks.subagent_stop_handler"

# The orphan clause-ID the gate must surface as UNWITNESSED; the witnessed
# clause-ID it must stay silent about. Both ride in the tmp feature-delta table.
_UNWITNESSED_CLAUSE = "DT-ORPHAN"
_WITNESSED_CLAUSE = "DT-WIT"
_FEATURE_ID = "probe-traceability-feat"

# The single planned slice in the tmp feature-delta slice-plan. We seed a signed
# verdict for it so the downstream verdict-completeness gate ALLOWS (precondition
# substrate, not the SUT).
_PLANNED_SLICE = "slice-01"
_VERDICT_SIGNED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "slice_id",
    "verdict",
    "reviewer_agent_id",
    "at_ids",
    "at_content_hash",
    "timestamp",
)
_VERDICT_SCHEMA_VERSION = "1.0.0"
_SEED_SIGNING_KEY = b"traceability-slice-01-seed-key"

# slice-01 binds the unwitnessed clause-ID to the UNWITNESSED verdict, NOT to a
# bare substring echo: a degenerate gate that dumps every declared clause-id to
# stderr (zero join logic) must FAIL. The gate's loud warning for an unwitnessed
# clause must therefore carry one of these unwitnessed-semantics tokens adjacent
# to the clause-ID. (Slice-02's DT-4 tightens this to the full ID->summary
# format; slice-01 owns only the unwitnessed semantics.)
_UNWITNESSED_MARKER_TOKENS: tuple[str, ...] = (
    ClauseVerdict.UNWITNESSED_NO_AT.value,  # "unwitnessed-no-at"
    "unwitnessed",
    "no witnessing",
    "no witness",
    "not witnessed",
)


@dataclass
class TraceabilityGateComposition:
    """Drives the production SubagentStop hook for the traceability-gate ATs."""

    _tmp: Path | None = field(default=None)
    _project_root: Path | None = field(default=None)
    _transcript_path: Path | None = field(default=None)
    _completed: subprocess.CompletedProcess[str] | None = field(default=None)
    _emission_channel: EmissionChannel = field(default=EmissionChannel.STDERR)
    # slice-03 DT-8 tree-safety: before-snapshot of a real production source file
    # the witness-check perturbs (in a copy). Unused by slice-01/02; declared on
    # the base so the slice-03 subclass can set/read it as a dataclass field.
    _source_before: bytes | None = field(default=None)

    # ---- given ---------------------------------------------------------

    def given_clause_with_no_witnessing_test(self) -> None:
        """A decision-table with a single clause that no `.feature` witnesses."""
        self._ensure_project()
        self._write_decision_table([_UNWITNESSED_CLAUSE])
        self._write_feature_carrier(witnessed_clause_ids=[])
        self._seed_signed_verdict_for_planned_slice()

    def given_one_witnessed_and_one_unwitnessed_clause(self) -> None:
        """A decision-table with one witnessed + one unwitnessed clause.

        Shared two-clause substrate: DT-WIT carries a ``# clause: DT-WIT``
        comment in a seeded AT file (witnessed); DT-ORPHAN appears in no
        ``.feature`` comment (unwitnessed). The DT-3 pair (warn-unwitnessed +
        silent-witnessed) is jointly unsatisfiable by a warn-every-clause gate.
        """
        self._ensure_project()
        self._write_decision_table([_WITNESSED_CLAUSE, _UNWITNESSED_CLAUSE])
        self._write_feature_carrier(witnessed_clause_ids=[_WITNESSED_CLAUSE])
        self._seed_signed_verdict_for_planned_slice()

    # ---- when ----------------------------------------------------------

    def when_distill_exit_gate_evaluates(self) -> None:
        """Invoke the REAL ``handle_subagent_stop`` hook over its JSON protocol.

        Mirrors the sibling: ``python -c`` importing + CALLING the hook (the
        module has no ``__main__``), with a seeded atdd_pure D_DISTILL transcript
        so ``_resolve_des_context`` routes to the DISTILL-exit gate.
        """
        assert self._project_root is not None
        self._write_distill_return_transcript()
        hook_input = json.dumps(
            {
                "session_id": "traceability-slice-01-session",
                "hook_event_name": "SubagentStop",
                "agent_id": "acceptance-designer-1",
                "agent_type": "nw-acceptance-designer",
                "agent_transcript_path": str(self._transcript_path),
                "stop_hook_active": False,
                "cwd": str(self._project_root),
                "transcript_path": "/tmp/session.jsonl",
                "permission_mode": "default",
            }
        )
        runner = (
            "import sys; "
            f"sys.path.insert(0, {str(REPO_ROOT / 'src')!r}); "
            f"from {HOOK_MODULE} import handle_subagent_stop; "
            "sys.exit(handle_subagent_stop())"
        )
        self._completed = subprocess.run(
            [sys.executable, "-c", runner],
            input=hook_input,
            capture_output=True,
            text=True,
            cwd=str(self._project_root),
        )

    # ---- then ----------------------------------------------------------

    def then_names_unwitnessed_clause(self) -> None:
        """DT-1: the unwitnessed clause-ID is bound to the UNWITNESSED verdict.

        Stronger than a bare ``DT-ORPHAN in stderr`` echo: the warning must name
        the clause AND carry an unwitnessed-semantics token, so a warn-every-
        clause gate (no join) cannot satisfy it.
        """
        self._assert_clause_warned_as_unwitnessed(_UNWITNESSED_CLAUSE)

    def then_warns_about_unwitnessed_clause(self) -> None:
        """DT-3/DT-5: same unwitnessed-verdict binding as DT-1."""
        self._assert_clause_warned_as_unwitnessed(_UNWITNESSED_CLAUSE)

    def then_silent_about_witnessed_clause(self) -> None:
        """DT-3 negative pole: the witnessed clause-ID must NOT be warned."""
        warning = self._warning_text()
        assert _WITNESSED_CLAUSE not in warning, (
            f"the witnessed clause {_WITNESSED_CLAUSE!r} was wrongly named in the "
            f"traceability warning; only unwitnessed clauses should be surfaced. "
            f"{self._observed()}"
        )

    def then_lets_feature_proceed(self) -> None:
        """DT-5 "lets the feature proceed to DELIVER": warned AND no block (conjunction).

        Witnesses the CONJUNCTION "the traceability gate warned AND the hook still
        proceeded", so the half is non-vacuous w.r.t. slice-01's SUT. The
        warning-present sub-assert (reused from DT-1/DT-3) binds this step to the
        traceability gate actually running; a vacuous pass on the seeded substrate
        alone is impossible. At RED (gate absent -> no warning) it fails on the
        warning sub-assert, consistent with the other scenarios. At GREEN (gate
        wired, warn+ALLOW) the warning is present AND no block rides on stdout. A
        HALTING traceability gate (block on stdout) flips this RED on the no-block
        assert -- the half can no longer pass regardless of the gate's behaviour.
        The seeded verdict keeps the orthogonal downstream gate allowing so the
        no-block assertion is reachable at GREEN.
        """
        self._assert_clause_warned_as_unwitnessed(_UNWITNESSED_CLAUSE)
        completed = self._require_completed()
        assert '"decision": "block"' not in completed.stdout, (
            "the gate must let the feature proceed to DELIVER (no block decision "
            f"on stdout); a block was emitted. {self._observed()}"
        )

    def then_hook_exits_zero(self) -> None:
        """DT-5 "exits with code zero": warned AND returncode 0 (conjunction).

        Witnesses the CONJUNCTION "the traceability gate warned AND the hook
        returned exit 0", so the half is non-vacuous. The warning-present
        sub-assert binds exit-zero to the gate having run; without it, exit 0
        would pass on the seeded substrate even with the gate absent. At GREEN
        the warning is present AND the hook returns 0 (downstream allowing via the
        seeded verdict, traceability gate non-halting).
        """
        self._assert_clause_warned_as_unwitnessed(_UNWITNESSED_CLAUSE)
        completed = self._require_completed()
        assert completed.returncode == 0, (
            "the hook must exit with code zero (non-halting); got "
            f"returncode={completed.returncode}. {self._observed()}"
        )

    # ---- assertion helpers ---------------------------------------------

    def _assert_clause_warned_as_unwitnessed(self, clause_id: str) -> None:
        warning = self._warning_text()
        assert clause_id in warning, (
            "DISTILL-exit traceability gate did not name the unwitnessed clause "
            f"{clause_id!r} in its loud {self._emission_channel.value} warning. "
            f"{self._observed()}"
        )
        assert any(token in warning for token in _UNWITNESSED_MARKER_TOKENS), (
            f"the warning named {clause_id!r} but did not bind it to the "
            f"UNWITNESSED verdict (expected one of {_UNWITNESSED_MARKER_TOKENS!r} "
            "adjacent to the clause-ID); a warn-every-clause gate with no join "
            f"would echo the id without this semantics. {self._observed()}"
        )

    def _warning_text(self) -> str:
        """The loud-warning channel (stderr per the OSS hooks-only invariant)."""
        return self._require_completed().stderr

    def _observed(self) -> str:
        completed = self._require_completed()
        return (
            f"hook returncode={completed.returncode}; "
            f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
        )

    # ---- precondition plumbing (substrate, NOT the SUT) ----------------

    def _ensure_project(self) -> None:
        if self._project_root is not None:
            return
        self._tmp = Path(tempfile.mkdtemp(prefix="traceability-gate-at-"))
        self._project_root = self._tmp
        subprocess.run(["git", "init", "-q"], cwd=self._project_root, check=True)
        (self._project_root / "docs" / "feature" / _FEATURE_ID).mkdir(
            parents=True, exist_ok=True
        )

    def _seed_signed_verdict_for_planned_slice(self) -> None:
        """Seed a signed ATReviewVerdict for the one planned slice (substrate).

        Makes the DOWNSTREAM verdict-completeness gate ALLOW, so DT-5's
        proceed/exit-zero Gherkin is literally assertable. Routed through the
        production ``AtCompletionLedger.append_review_verdict`` writer (same as the
        sibling) -- precondition state, not the SUT, not a DT-10 outcome assertion.
        """
        assert self._project_root is not None
        ledger = AtCompletionLedger(_FEATURE_ID, self._project_root)
        ledger.append_review_verdict(
            slice_id=_PLANNED_SLICE,
            verdict_fields=self._signed_verdict_fields(_PLANNED_SLICE),
        )

    @staticmethod
    def _signed_verdict_fields(slice_id: str) -> dict[str, object]:
        record: dict[str, object] = {
            "schema_version": _VERDICT_SCHEMA_VERSION,
            "slice_id": slice_id,
            "verdict": "APPROVED",
            "reviewer_agent_id": "nw-acceptance-designer-reviewer",
            "at_ids": [f"{slice_id}-AT-1"],
            "at_content_hash": hashlib.sha256(slice_id.encode()).hexdigest(),
            "timestamp": "2026-05-31T00:00:00Z",
        }
        signed = {field: record[field] for field in _VERDICT_SIGNED_FIELDS}
        canonical = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()
        record["hmac_sha256"] = hmac.new(
            _SEED_SIGNING_KEY, canonical, hashlib.sha256
        ).hexdigest()
        record["findings_summary"] = "clean"
        return record

    def _write_decision_table(self, clause_ids: list[str]) -> None:
        assert self._project_root is not None
        delta = (
            self._project_root / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
        )
        rows = "\n".join(
            f"| {cid} | summary for {cid} | some condition | some outcome |"
            for cid in clause_ids
        )
        delta.write_text(
            "# Feature Delta -- probe-traceability-feat\n"
            "\n"
            "## This Feature's OWN Decision-Table\n"
            "\n"
            "| clause-ID | summary | condition / input | expected-outcome |\n"
            "|---|---|---|---|\n"
            f"{rows}\n"
            "\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n"
            "\n"
            "| slice    | description      | status  |\n"
            "|----------|------------------|---------|\n"
            "| slice-01 | walking skeleton | pending |\n",
            encoding="utf-8",
        )

    def _write_feature_carrier(self, witnessed_clause_ids: list[str]) -> None:
        """Author a `.feature` whose comments witness the given clause-IDs."""
        assert self._project_root is not None
        at_dir = self._project_root / "tests" / "acceptance" / _FEATURE_ID
        at_dir.mkdir(parents=True, exist_ok=True)
        scenarios = "\n".join(
            "\n".join(
                [
                    f"  # clause: {cid}",
                    "  # target: app.widget::accept",
                    f"  Scenario: behaviour witnessing {cid}",
                    "    Given a precondition",
                    "    When an action occurs",
                    "    Then an outcome holds",
                    "",
                ]
            )
            for cid in witnessed_clause_ids
        )
        (at_dir / "g-probe.feature").write_text(
            "Feature: Probe behaviour\n\n" + scenarios,
            encoding="utf-8",
        )

    def _write_distill_return_transcript(self) -> None:
        """Seed a transcript whose last block is an atdd_pure D_DISTILL return.

        Marker block carries DES-MODE:atdd_pure + DES-PHASE:D_DISTILL plus the
        DES-PROJECT-ID / DES-PROJECT-ROOT the gate resolves repo + feature_id
        from (mirrors the sibling's ``_marker_block``).
        """
        assert self._project_root is not None
        block = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            "<!-- DES-PHASE : D_DISTILL -->\n"
            "<!-- DES-SLICE : feature-end -->\n"
            f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self._project_root} -->\n"
        )
        line = json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": block},
                "uuid": "distill-return",
                "timestamp": "2026-05-31T00:00:00Z",
            }
        )
        self._transcript_path = self._project_root / "agent.jsonl"
        self._transcript_path.write_text(line + "\n", encoding="utf-8")

    def _require_completed(self) -> subprocess.CompletedProcess[str]:
        assert self._completed is not None, (
            "the DISTILL-exit gate must be evaluated (When) before asserting "
            "on its observable warning surface (Then)"
        )
        return self._completed
