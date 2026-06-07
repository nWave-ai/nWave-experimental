"""Composition root for des-spine-control-plane-ssot slice-04 (gate-composition SSOT).

Pillar 3 (App as in production): the SUT is the REAL `subagent.stop` lifecycle-
event driving port — `python -m des.adapters.drivers.hooks.claude_code_hook_adapter
subagent-stop` invoked exactly as Claude Code invokes it when a dispatched
atdd_pure crafter returns (a transcript-carrying `agent_transcript_path` payload
on stdin). The gate-composition SSOT behavior is observed via the hook's stdout
block-decision JSON + exit code, NEVER by importing the dispatcher or the if-ladder.

Mandate-13 (invariant 1+2): every service method drives the hook as a Layer-3
SUBPROCESS black-box — NEVER a direct
`from des.application.flavor_dispatcher import dispatch_lifecycle_event` +
function-boundary call, NEVER `from des.adapters.drivers.hooks.subagent_stop_handler
import _handle_feature_end_gate`. The dispatcher + handler are NEVER imported in
this composition; the AT observes only the hook subprocess's exit code + stdout
stream. This is the driving-port-only boundary: the gate that fires at
`subagent.stop` is read off the port's real behaviour, not an internal call.

Mandate-13 (invariant 5) — Python-only, git-free, cross-OS: the synthetic project
(config + feature-delta slice-plan + transcript) and the test flavor directories
are plain filesystem topology under tmp_path. No git, no shell tool. The
`subagent.stop` feature-end branch is reached by writing a synthetic atdd_pure
F_FINAL_REVIEW transcript with the public HTML-comment marker block
(`<!-- DES-MODE : atdd_pure -->` etc.) — the SAME format `/nw-deliver` renders.

Mandate-12 criterion 2/3: `GateCompositionFixture` is the single source of truth
for ALL business logic the step methods need. Step bodies in
`steps_slice_04_gate_composition.py` delegate here — each body is <=2 statements
ending in one `gate_composition_fixture.<method>(...)` call (or one assertion),
no control flow inline.

DISTILL-authored RED scaffold (ADR-025): `des ... subagent-stop` ALREADY EXISTS,
but slice-04's NEW behavior does NOT:
  * DDD-1 — the `subagent.stop` feature-end gate is hand-wired (the if-ladder at
    `subagent_stop_handler.py:1356` + the hardcoded `_REQUIRED_FEATURE_END_RECORDS`
    frozenset at `:820`). It NEVER reads the flavor YAML for `subagent.stop`.
  * The `NWAVE_FLAVORS_DIR` override seam (the overridable flavor-YAML SSOT)
    does NOT exist yet (grep-confirmed: zero `NWAVE_FLAVORS_DIR` in `src/des/`).
So with a test flavor pointed via `NWAVE_FLAVORS_DIR`:
  * AT-01 (EMPTY_REQUIRED_RECORDS) RED-fails — the boundary STILL blocks naming
    the six hardcoded records (the flavor's empty profile is ignored).
  * AT-02 (SENTINEL_REQUIRED_RECORD) RED-fails — the boundary blocks naming only
    the six hardcoded records; the YAML-declared sentinel record NEVER appears
    in `missing` (the flavor profile is ignored).
  * AT-03 (PRODUCTION) GREEN-passes today — with the shipped flavor (no override)
    the boundary blocks naming exactly the six records; this is the behavior-
    preservation regression pin (DEVOPS slice-04 deploy gate) that the routing
    must keep GREEN. Witnessed at DISTILL HEAD (the production six in `missing`).
All RED failures are MISSING_FUNCTIONALITY (the boundary reaches its block
assertion; the universe is correctly shaped) — NOT import/fixture/setup error
(Mandate-7 RED-vs-BROKEN preserved).

Layer 3 (subprocess against tmp_path): example-only (Mandate 9 v2 — @real-io
because the driven set includes a real filesystem adapter the hook reads config
+ feature-delta + transcript from). No PBT machinery. The feature-end block is
one explicit named example per flavor composition (Mandate 11).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .domain_types_slice_04 import (
    BLOCK_DECISION,
    FEATURE_END_BLOCK_EVENT,
    SENTINEL_REQUIRED_RECORD,
    BoundaryOutcome,
    BoundaryRun,
    FeatureEndProject,
    FlavorComposition,
)


_FEATURE_ID = "demo-gate-composition-feature"
_HOOK_MODULE = "des.adapters.drivers.hooks.claude_code_hook_adapter"
_SUBAGENT_STOP_ARG = "subagent-stop"


@dataclass
class GateCompositionFixture:
    """Composition-root service for des-spine-control-plane-ssot slice-04 ATs.

    Pillar 3: drives the SAME `subagent.stop` hook entry Claude Code invokes when
    a dispatched atdd_pure crafter returns, against a synthetic feature-end
    project under tmp_path. The gate-composition SSOT seam — "which required-
    records profile governs the `subagent.stop` feature-end boundary" — is
    expressed as a flavor directory the `NWAVE_FLAVORS_DIR` override points at
    (or NO override, for the production case). The AT observes the boundary's
    verdict via the hook's stdout block-decision JSON + exit code.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do typed lookup + one method call; nothing more.
    """

    _tmp_path: Path

    # --- project + flavor construction (the gate-composition seam) ----------

    def build_feature_end_project(
        self, *, flavor_composition: FlavorComposition
    ) -> FeatureEndProject:
        """Lay out a synthetic atdd_pure feature-end project under tmp_path. GIT-FREE.

        Every project has: a `.nwave/config.yaml` declaring atdd_pure; a feature-
        delta with a one-row `[REF] Slice Plan` whose only slice is `shipped`
        (the markdown fallback yields planned == shipped, so the feature-end gate
        reaches the missing-records branch); a synthetic F_FINAL_REVIEW transcript
        (the feature-end return marker block); and NO AT-completion ledger (so the
        feature-end cycle records are ABSENT — the boundary's missing-records
        block is reachable).

        `flavor_composition` selects which `subagent.stop` required-records
        profile governs: PRODUCTION → no `NWAVE_FLAVORS_DIR` override (the shipped
        flavor YAML); EMPTY/SENTINEL → a test flavor dir the override points at.
        """
        project_dir = self._tmp_path / flavor_composition.name.lower()
        feature_dir = project_dir / "docs" / "feature" / _FEATURE_ID
        feature_dir.mkdir(parents=True, exist_ok=True)
        self._write_atdd_pure_config(project_dir)
        self._write_shipped_slice_plan(feature_dir)
        transcript_path = self._write_feature_end_transcript(project_dir)
        flavors_dir = self._build_flavors_dir(flavor_composition)
        return FeatureEndProject(
            project_dir=str(project_dir),
            feature_id=_FEATURE_ID,
            transcript_path=str(transcript_path),
            flavor_composition=flavor_composition,
            flavors_dir=flavors_dir,
        )

    # --- the driving-port fire (real subagent-stop hook subprocess) ---------

    def run_subagent_stop(self, project: FeatureEndProject) -> BoundaryRun:
        """Fire the REAL `subagent.stop` hook entry on the feature-end project.

        Mandate-13 Layer-3 subprocess black-box: spawn the canonical hook by
        module-path with the `subagent-stop` arg and feed the synthetic
        F_FINAL_REVIEW transcript payload on stdin, exactly as Claude Code does.
        The dispatcher + handler are NEVER imported. The `subagent.stop` boundary's
        OBSERVABLE verdict is its stdout block-decision JSON: a feature-end return
        with the cycle records absent emits
        `{"decision":"block","event":"FeatureEndCycleIncomplete","missing":[...]}`.
        The `missing` list is the required-records-profile observable that
        discriminates a YAML-sourced profile (the slice-04 cure) from the
        hardcoded frozenset (today).

        `NWAVE_FLAVORS_DIR` points the gate-composition dispatcher at the test
        flavor dir (None for the production case). `NWAVE_FRESHNESS=skip` isolates
        the slice-01 install-freshness gate (DV-1) so its `stale` stderr chatter
        cannot confound the stdout block-JSON parse, AND so a `.git/`-adjacency
        autoskip cannot mask the verdict (RCA #68 P1-B). The skip masks slice-01's
        gate ONLY — it has no bearing on the gate-composition answer slice-04 asserts.
        """
        completed = subprocess.run(
            [sys.executable, "-m", _HOOK_MODULE, _SUBAGENT_STOP_ARG],
            input=self._hook_stdin(project),
            capture_output=True,
            text=True,
            env=self._spine_env(project),
            cwd=project.project_dir,
            timeout=120,
        )
        return self._classify_boundary_run(completed)

    # --- pure classifiers (SSOT for the observable-outcome derivation) ------

    @staticmethod
    def _classify_boundary_run(
        completed: subprocess.CompletedProcess[str],
    ) -> BoundaryRun:
        """Derive the port-exposed BoundaryRun from a completed hook subprocess.

        Parses the FIRST JSON line on stdout carrying a `decision`. A
        FeatureEndCycleIncomplete block yields BLOCKED_MISSING_RECORDS + the
        emitted `missing` set. The ABSENCE of a FeatureEndCycleIncomplete block
        (no block JSON, or a block from a different event) yields
        PROCEEDED_PAST_RECORDS. Anything malformed is UNEXPECTED so a verdict
        never passes for the wrong reason.
        """
        decision = GateCompositionFixture._first_decision_json(completed.stdout)
        block_event = decision.get("event") if decision else None
        missing = GateCompositionFixture._missing_from(decision)
        outcome = GateCompositionFixture._boundary_outcome(decision, block_event)
        return BoundaryRun(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            outcome=outcome,
            block_event=block_event,
            missing_records=missing,
        )

    @staticmethod
    def _first_decision_json(stdout: str) -> dict | None:
        """The first parseable JSON line on stdout carrying a `decision` key.

        Pure function — the hook emits its block decision as one JSON line on
        stdout. Returns None when no such line is present (no block emitted).
        """
        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "decision" in payload:
                return payload
        return None

    @staticmethod
    def _missing_from(decision: dict | None) -> frozenset[str]:
        """The emitted `missing` records set from a FeatureEndCycleIncomplete block.

        Empty frozenset when there is no block, no `missing` key, or the block is
        a different event. Pure function (SSOT for the required-records observable).
        """
        if decision is None or decision.get("event") != FEATURE_END_BLOCK_EVENT:
            return frozenset()
        raw = decision.get("missing")
        return frozenset(raw) if isinstance(raw, list) else frozenset()

    @staticmethod
    def _boundary_outcome(
        decision: dict | None, block_event: str | None
    ) -> BoundaryOutcome:
        """Map (decision, event) -> BoundaryOutcome. Pure decision table (SSOT)."""
        if decision is None:
            # No block JSON at all — the boundary did not block on missing records.
            return BoundaryOutcome.PROCEEDED_PAST_RECORDS
        if (
            decision.get("decision") == BLOCK_DECISION
            and block_event == FEATURE_END_BLOCK_EVENT
        ):
            return BoundaryOutcome.BLOCKED_MISSING_RECORDS
        if decision.get("decision") == BLOCK_DECISION:
            # A block from a LATER gate (e.g. the integrity gate), NOT the
            # missing-records block — the required-records check was passed.
            return BoundaryOutcome.PROCEEDED_PAST_RECORDS
        return BoundaryOutcome.UNEXPECTED

    # --- cross-flavor assertions (the discriminators) -----------------------

    @staticmethod
    def blocked_naming_exactly(run: BoundaryRun, expected: frozenset[str]) -> bool:
        """True iff the boundary blocked on missing records naming EXACTLY `expected`.

        SSOT for the AT-03 behavior-preservation check (production six) and the
        record-set-equality discriminators so the step body stays a thin delegate.
        """
        return (
            run.outcome is BoundaryOutcome.BLOCKED_MISSING_RECORDS
            and run.missing_records == expected
        )

    @staticmethod
    def proceeded_past_records(run: BoundaryRun) -> bool:
        """True iff the boundary did NOT block on the missing-records check (AT-01)."""
        return run.outcome is BoundaryOutcome.PROCEEDED_PAST_RECORDS

    @staticmethod
    def blocked_naming_sentinel(run: BoundaryRun) -> bool:
        """True iff the boundary blocked naming the YAML-declared sentinel (AT-02)."""
        return (
            run.outcome is BoundaryOutcome.BLOCKED_MISSING_RECORDS
            and SENTINEL_REQUIRED_RECORD in run.missing_records
        )

    # --- synthetic atdd_pure project artifacts (git-free filesystem) --------

    @staticmethod
    def _write_atdd_pure_config(project_dir: Path) -> None:
        """Write `.nwave/config.yaml` declaring the atdd_pure mode.

        The stdlib-only resolver parses a minimal two-level `workflow:`/`mode:`
        block (the DES bundle stays PyYAML-free). The feature-end gate's atdd_pure
        branch is reached via the transcript markers; this config keeps the
        downstream integrity gate (if ever reached) resolving atdd_pure too.
        """
        config_dir = project_dir / ".nwave"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "workflow:\n  mode: atdd_pure\n", encoding="utf-8"
        )

    @staticmethod
    def _write_shipped_slice_plan(feature_dir: Path) -> None:
        """Write a feature-delta whose one-row `[REF] Slice Plan` is `shipped`.

        The exact heading `## Wave: DISCUSS / [REF] Slice Plan` + a row whose
        third cell (Status) is `shipped` makes the markdown fallback yield
        planned == shipped (NO ledger written), so the feature-end gate sees "all
        planned slices shipped" and reaches the missing-records branch. GIT-FREE.
        """
        (feature_dir / "feature-delta.md").write_text(
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value | Status | Tags | Note |\n"
            "|---|---|---|---|---|\n"
            "| slice-01 | x | shipped | | |\n",
            encoding="utf-8",
        )

    @staticmethod
    def _write_feature_end_transcript(project_dir: Path) -> Path:
        """Write a synthetic F_FINAL_REVIEW transcript reaching the feature-end branch.

        The public HTML-comment marker block (the SAME format `/nw-deliver`
        renders) carries `DES-VALIDATION:required`, `DES-MODE:atdd_pure`,
        `DES-PHASE:F_FINAL_REVIEW`, the project id + slice + root markers. The
        hook's `extract_des_context_from_transcript` resolves the atdd_pure
        feature-end return from it. Mandate-13: this is the public marker contract
        (`docs/feature/single-entry-point/distill/des-marker-format.md`), NOT a
        production import — the transcript text is authored in-harness.
        """
        transcript = project_dir / "agent-transcript.jsonl"
        marker_block = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
            "<!-- DES-SLICE : slice-01 -->\n"
            "<!-- DES-PHASE : F_FINAL_REVIEW -->\n"
            f"<!-- DES-PROJECT-ROOT : {project_dir} -->\n"
        )
        entry = {"message": {"role": "user", "content": marker_block}}
        transcript.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        return transcript

    # --- test flavor directory construction (the NWAVE_FLAVORS_DIR target) ---

    def _build_flavors_dir(self, flavor_composition: FlavorComposition) -> str | None:
        """Materialise a test flavor dir for the override, or None for production.

        PRODUCTION → None (NO `NWAVE_FLAVORS_DIR`; the shipped
        `nWave/flavors/atdd_pure.yaml` governs — the behavior-preservation case).
        EMPTY_REQUIRED_RECORDS → an `atdd_pure.yaml` whose `subagent.stop`
        feature-end composition declares an EMPTY required-records profile.
        SENTINEL_REQUIRED_RECORD → an `atdd_pure.yaml` adding the sentinel record
        to the production profile.

        The flavor file is written in the same stdlib-only YAML subset the shipped
        flavor uses (`nWave/flavors/_schema.yaml`): top-level scalars + the
        `lifecycle_events` two-level mapping with gate-spec dicts + a
        `feature_end_required_records` string list under the `subagent.stop`
        composition (the new flavor-config field slice-04 introduces — the
        frozenset's YAML home).
        """
        if flavor_composition is FlavorComposition.PRODUCTION:
            return None
        flavors_dir = self._tmp_path / f"flavors-{flavor_composition.name.lower()}"
        flavors_dir.mkdir(parents=True, exist_ok=True)
        records = self._required_records_for(flavor_composition)
        (flavors_dir / "atdd_pure.yaml").write_text(
            self._render_flavor_yaml(records), encoding="utf-8"
        )
        return str(flavors_dir)

    @staticmethod
    def _required_records_for(flavor_composition: FlavorComposition) -> list[str]:
        """The required-records list a test flavor declares. Pure (SSOT)."""
        from .domain_types_slice_04 import PRODUCTION_REQUIRED_RECORDS

        if flavor_composition is FlavorComposition.EMPTY_REQUIRED_RECORDS:
            return []
        # SENTINEL: production six + the sentinel record.
        return sorted(PRODUCTION_REQUIRED_RECORDS | {SENTINEL_REQUIRED_RECORD})

    @staticmethod
    def _render_flavor_yaml(required_records: list[str]) -> str:
        """Render a minimal atdd_pure flavor file with a `subagent.stop` composition.

        Stays inside the flavor-file YAML subset: `flavor_id` scalar, the
        `lifecycle_events` mapping with a `subagent.stop` gate-spec list, and the
        `feature_end_required_records` string list (the new slice-04 config field
        — the frozenset's YAML home). Mirrors the shipped flavor's
        `verify-slice-commit` gate so the composition stays behavior-equivalent
        except for the required-records profile under test.
        """
        lines = [
            "flavor_id: atdd_pure",
            "",
            "lifecycle_events:",
            "  subagent.stop:",
            "    - gate_id: verify-slice-commit",
            "      args:",
            '        repo: "{repo_root}"',
            "        commit: HEAD",
            '        feature_id: "{feature_id}"',
            "      on_failure: warn",
            "      feature_end_required_records:",
        ]
        if required_records:
            lines.extend(f"        - {record}" for record in required_records)
        else:
            # An explicitly EMPTY list (the subset reader yields []). The trailing
            # key with no items expresses "demand no feature-end records".
            lines.append("        []")
        return "\n".join(lines) + "\n"

    # --- hook stdin + env (port-faithful invocation) ------------------------

    @staticmethod
    def _hook_stdin(project: FeatureEndProject) -> str:
        """The Claude Code subagent-stop payload on stdin (transcript + cwd)."""
        return json.dumps(
            {
                "agent_transcript_path": project.transcript_path,
                "cwd": project.project_dir,
                "agent_type": "nw-software-crafter",
                "agent_id": "slice-04-feature-end",
            }
        )

    @staticmethod
    def _spine_env(project: FeatureEndProject) -> dict[str, str]:
        """Env for the hook: inherit + isolate freshness + point the flavor dir.

        `NWAVE_FRESHNESS=skip` short-circuits the slice-01 install-freshness gate
        so the slice-04 gate-composition behavior is observed in isolation (DV-1)
        and a `.git/`-adjacency autoskip cannot mask the verdict (RCA #68 P1-B).
        `NWAVE_FLAVORS_DIR` points the gate-composition dispatcher at the test
        flavor dir (omitted for PRODUCTION → the shipped flavor governs). The
        red-classification run additionally sets `NWAVE_FRESHNESS=""` at the
        pytest level for env-parity (RCA #68 P1-B) — the per-subprocess skip here
        isolates slice-01's gate, never the slice-04 answer.
        """
        env = dict(os.environ)
        env["NWAVE_FRESHNESS"] = "skip"
        if project.flavors_dir is not None:
            env["NWAVE_FLAVORS_DIR"] = project.flavors_dir
        else:
            env.pop("NWAVE_FLAVORS_DIR", None)
        return env


__all__ = ["GateCompositionFixture"]
