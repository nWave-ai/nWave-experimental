"""Composition root for the f-deliver-entry-contract-freeze ATs (Mandate-13).

Driving-port-only. The behaviour is driven through the REAL DELIVER-entry
contract-freeze gate -- the ``des verify-deliver-entry-contract`` subcommand
(Layer 3 subprocess: ``python -m des.cli.__main__ verify-deliver-entry-contract
--feature-id <id> --repo-root <tmp>``) -- over a real temp repo carrying a real
``feature-delta.md`` and real ``.feature`` AT modules. The observables are the
emitted §17 verdict (parsed from the gate's ``--format=json`` envelope) and the
``ContractFrozen`` record the REAL ``AtCompletionLedger`` carries afterwards.

active-RED scaffold (atdd_pure -- NOT @skip). At HEAD the net-new production
seams this feature's DESIGN pins are ABSENT (verified 2026-06-19):

  * ``src/des/cli/verify_deliver_entry_contract.py`` (the gate) does not exist;
  * the ``verify-deliver-entry-contract`` subcommand is NOT in the ``des``
    ``_REGISTRY`` -> argparse rejects it with "invalid choice";
  * ``AtCompletionLedger.append_contract_frozen`` / ``contract_frozen_event``
    do not exist -> no ``ContractFrozen`` record is ever written.

So a dispatch against the unregistered subcommand exits with argparse's
invalid-choice rejection (no verdict envelope), and the ledger carries no
``ContractFrozen`` record. Each driving-port invocation captures that absence as
an observable the ``Then`` turns into a NAMED semantic ``AssertionError`` -- never
a collection / import / setup error. The suite therefore COLLECTS cleanly at HEAD
and every current-slice scenario RED-fails for the right reason.

DELIVER-pinned assumptions (update HERE, not in the step bodies, if DELIVER picks
different surface shapes):

  A1 (subcommand id): the wired gate is ``des verify-deliver-entry-contract``,
     taking ``--feature-id <id> --repo-root <path> [--format=json]``. The JSON
     envelope carries a ``verdict`` field whose value is one of the §17 LOCKED
     FIVE (``src/des/domain/gate_outcome.py``).
  A2 (freeze record): on a structural PASS the gate appends a ``ContractFrozen``
     record to the ``AtCompletionLedger`` for the feature (the frozen baseline).
     This composition reads it back via the REAL ledger ``read_records`` API.
  A3 (locked sections): the named locked ``[REF]`` sections the gate requires
     present are the four DDD-1 sections (Architecture & Contract Tests /
     ADR Refs / Reuse Analysis / Slice Plan). The COMPLETE fixture renders all
     four; the MISSING_SECTION fixture drops one.
  A4 (slice<->AT binding): a planned ``slice-NN`` row binds to a ``.feature``
     carrying both the file-level ``@feature-{id}`` tag and a ``@slice-NN``
     scenario tag (``feature_at_files.feature_tag_files``). The COMPLETE fixture
     authors one such ``.feature``; the SLICE_WITHOUT_AT fixture omits it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types import ContractShape, FreezeVerdict, ManifestState, PostFreezeEdit


# The DELIVER-entry contract-freeze gate's driving-port subcommand (A1).
_SUBCOMMAND_ID = "verify-deliver-entry-contract"

# The ContractFrozen ledger event name (A2) the gate writes on a structural PASS.
_CONTRACT_FROZEN_EVENT = "ContractFrozen"

# Sentinel an absent / unrecognised gate records, so the Then names the missing
# behaviour rather than letting the absence escape as a non-semantic error.
_GATE_ABSENT = "__GATE_ABSENT__"

# A real, grep-findable feature-id the temp feature-delta self-identifies as.
_FEATURE_ID = "f-deliver-entry-contract-freeze-fixture"


@dataclass
class _GateObservable:
    """What the freeze gate emitted (or did not) for one driving-port invocation."""

    verdict: str | None
    recognised: bool
    raw: str


@dataclass
class ContractFreezeComposition:
    """Drives the DELIVER-entry contract-freeze gate through its real driving port."""

    _shape: ContractShape | None = field(default=None)
    _repo_root: Path | None = field(default=None)
    _observable: _GateObservable | None = field(default=None)

    # =====================================================================
    # Given -- arm the structural shape of the contract presented at DELIVER-IN
    # =====================================================================

    def given_contract_shape(self, shape: ContractShape) -> None:
        """Arm whether the presented contract is structurally complete / deficient."""
        self._shape = shape

    # =====================================================================
    # When -- drive the REAL freeze gate over a real temp repo
    # =====================================================================

    def when_the_freeze_gate_runs_at_deliver_entry(self, tmp_path: Path) -> None:
        """Write a real temp repo for the armed shape, then run the REAL gate (A1)."""
        self._repo_root = self._write_repo(tmp_path)
        self._observable = self._drive_gate(self._repo_root)

    # =====================================================================
    # Then -- observable readers (the §17 verdict + the ContractFrozen record)
    # =====================================================================

    def then_verdict_is(self, expected: FreezeVerdict) -> None:
        """The gate returned EXACTLY the expected §17 verdict (one of the LOCKED five)."""
        obs = self._require_observable()
        from .domain_types import LOCKED_VERDICTS

        assert obs.verdict in LOCKED_VERDICTS, (
            f"the DELIVER-entry contract-freeze gate must emit one of the §17 "
            f"LOCKED FIVE verdicts {sorted(LOCKED_VERDICTS)!r} (ADR-GV-001, no "
            f"sixth) -- it emitted verdict={obs.verdict!r}. {self._diag()}"
        )
        assert obs.verdict == expected.value, (
            f"the freeze gate must return {expected.value!r} for this contract "
            f"shape -- got {obs.verdict!r}. {self._diag()}"
        )

    def then_contract_is_frozen(self) -> None:
        """On a structural PASS, a ``ContractFrozen`` record is durably written (A2)."""
        assert self._repo_root is not None, (
            "the freeze gate must have run against a real repo before the "
            "ContractFrozen record can be read back."
        )
        frozen = self._read_contract_frozen_records(self._repo_root)
        assert len(frozen) == 1, (
            f"a structurally-complete contract at the first DELIVER gate-IN must "
            f"FREEZE the contract -- exactly one {_CONTRACT_FROZEN_EVENT!r} record "
            f"in the AtCompletionLedger (the frozen baseline; CT-1, feature-level "
            f"granularity per CT-7) -- but the ledger carries {len(frozen)} such "
            f"records. {self._diag()}"
        )

    def then_contract_is_not_frozen(self) -> None:
        """A REFUSED contract leaves NO ``ContractFrozen`` record (no false freeze)."""
        assert self._repo_root is not None, (
            "the freeze gate must have run against a real repo before the absence "
            "of a ContractFrozen record can be asserted."
        )
        frozen = self._read_contract_frozen_records(self._repo_root)
        assert len(frozen) == 0, (
            f"a structurally-incomplete OR unreadable contract must be REFUSED -- "
            f"no {_CONTRACT_FROZEN_EVENT!r} record may be written (a missing locked "
            f"section / a planned-slice-with-no-AT-module / an unreadable delta is "
            f"never a freeze) -- but the ledger carries {len(frozen)} such records. "
            f"{self._diag()}"
        )

    # =====================================================================
    # driving-port invocation (real subprocess -> sentinel on absence)
    # =====================================================================

    def _drive_gate(self, repo_root: Path) -> _GateObservable:
        """Run the REAL ``des verify-deliver-entry-contract`` EDGE in-process (A1).

        Drives the production ``des.cli.__main__.main`` dispatcher in-process via
        the shared ``run_cli_in_process`` driver (``cwd=repo_root``, stdout+stderr
        captured) -- the in-process analogue of the former
        ``python -m des.cli.__main__ verify-deliver-entry-contract ...`` subprocess.

        At HEAD the subcommand is unregistered, so argparse rejects it with an
        "invalid choice" usage error and emits NO verdict envelope -> the
        observable carries ``verdict=None``, ``recognised=False``. The Then turns
        that into the named RED. GREEN once DELIVER ships the gate + registers it.
        """
        _exit_code, stdout, stderr = run_cli_in_process(
            [
                _SUBCOMMAND_ID,
                "--feature-id",
                _FEATURE_ID,
                "--repo-root",
                str(repo_root),
                "--format=json",
            ],
            cwd=repo_root,
        )
        raw = f"{stdout}\n{stderr}"
        recognised = not (
            "invalid choice" in raw.lower() and _SUBCOMMAND_ID in raw.lower()
        )
        verdict = self._parse_verdict(stdout) if recognised else None
        return _GateObservable(verdict=verdict, recognised=recognised, raw=raw)

    @staticmethod
    def _parse_verdict(stdout: str) -> str | None:
        """Pull the ``verdict`` field out of the gate's JSON envelope (A1)."""
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            verdict = payload.get("verdict")
            return str(verdict) if verdict is not None else None
        return None

    def _read_contract_frozen_records(self, repo_root: Path) -> list[dict[str, object]]:
        """Read back ``ContractFrozen`` records from the REAL ledger (A2).

        At HEAD the gate never ran (unregistered) and the ledger has no
        ``ContractFrozen`` taxonomy, so this returns an empty list -- the PASS
        scenario's ``then_contract_is_frozen`` fires its named RED (0 != 1).
        """
        try:
            from des.adapters.driven.logging.at_completion_ledger import (
                AtCompletionLedger,
            )
        except (ImportError, ModuleNotFoundError):
            return []
        ledger = AtCompletionLedger(_FEATURE_ID, repo_root)
        try:
            records = list(ledger.read_records())
        except Exception:
            return []
        return [r for r in records if r.get("event") == _CONTRACT_FROZEN_EVENT]

    # =====================================================================
    # real temp-repo fixtures (the contract a DELIVER-entry presents)
    # =====================================================================

    def _write_repo(self, tmp_path: Path) -> Path:
        """Materialise a real temp repo carrying the armed contract shape."""
        assert self._shape is not None, (
            "a freeze scenario must arm an explicit ContractShape before the gate runs."
        )
        feature_dir = tmp_path / "docs" / "feature" / _FEATURE_ID
        feature_dir.mkdir(parents=True, exist_ok=True)
        delta = feature_dir / "feature-delta.md"
        if self._shape is ContractShape.UNREADABLE:
            # Undecodable bytes -- the gate cannot read the contract -> INDETERMINATE.
            delta.write_bytes(b"\xff\xfe\x00 not valid utf-8 \x80\x81")
        else:
            delta.write_text(self._render_feature_delta(), encoding="utf-8")
        if self._shape is not ContractShape.SLICE_WITHOUT_AT:
            self._write_slice_at_module(tmp_path)
        # Env-parity (F21/RCA-#68): the gate subprocess runs with cwd=tmp_path (a
        # manifest-less synthetic workspace). Seed a `.git/` marker so the runtime-
        # freshness gate AUTOSKIPS (dev-checkout) instead of the customer-install
        # REFUSAL (exit 78) before the gate's own logic runs. Environment SETUP, not
        # assertion-weakening; NOT a NWAVE_FRESHNESS=skip mask. See tests/env_parity.py.
        seed_dev_checkout_marker(tmp_path)
        return tmp_path

    def _render_feature_delta(self) -> str:
        """Render a feature-delta with the locked sections + a one-row Slice Plan.

        MISSING_SECTION drops the ``Reuse Analysis`` locked section; every other
        shape renders all four DDD-1 locked ``[REF]`` sections.
        """
        slice_plan = (
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|-------|-----------------|--------|------------|---------------|\n"
            "| slice-01 | A thin DELIVER-IN vertical. | pending | "
            "@walking-skeleton @driving_port | ~4 ATs. |\n"
        )
        arch_tests = (
            "## Wave: DESIGN / [REF] Architecture & Contract Tests\n\n"
            "| ID | Contract | SUT | Verdict | Consumed-by |\n"
            "|----|----------|-----|---------|-------------|\n"
            "| CT-1 | a contract is frozen | x::main | FAIL | DISTILL |\n"
        )
        adr_refs = "## Wave: DESIGN / [REF] ADR Refs\n\n- slice-01: ADR-FLOW-004\n"
        reuse = (
            "## Reuse Analysis\n\n"
            "| Existing Component | File | Overlap | Decision | Justification |\n"
            "|--------------------|------|---------|----------|---------------|\n"
            "| gate | x.py | none | CREATE_NEW | new gate. |\n"
        )
        sections = [arch_tests, adr_refs, slice_plan]
        if self._shape is not ContractShape.MISSING_SECTION:
            sections.append(reuse)
        header = f"# Feature Delta: {_FEATURE_ID}\n\n"
        return header + "\n".join(sections) + "\n"

    def _write_slice_at_module(self, tmp_path: Path) -> None:
        """Author a real ``.feature`` binding slice-01 to an AT (A4).

        The file carries the file-level ``@feature-{id}`` tag + a ``@slice-01``
        scenario tag, so ``feature_at_files.feature_tag_files`` resolves it as the
        planned slice's authored AT module.
        """
        at_dir = (
            tmp_path / "tests" / "des" / "acceptance" / _FEATURE_ID.replace("-", "_")
        )
        at_dir.mkdir(parents=True, exist_ok=True)
        feature_file = at_dir / "slice-01.feature"
        feature_file.write_text(
            f"@feature-{_FEATURE_ID}\n"
            "Feature: the slice-01 walking skeleton\n\n"
            "  @slice-01 @walking-skeleton\n"
            "  Scenario: the thin vertical is exercised\n"
            "    Given a structurally-complete contract\n"
            "    When the freeze gate runs\n"
            "    Then the contract is frozen\n",
            encoding="utf-8",
        )

    # =====================================================================
    # internal observable accessors
    # =====================================================================

    def _require_observable(self) -> _GateObservable:
        assert self._observable is not None, (
            "the freeze gate driving port was never invoked -- a When step must run "
            "the gate before a Then reads its verdict."
        )
        return self._observable

    def _diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "[no gate observable captured]"
        if not obs.recognised:
            return (
                f"[the {_SUBCOMMAND_ID!r} subcommand is UNREGISTERED at HEAD -- "
                f"argparse rejected it; the gate has not been shipped/wired yet] "
                f"raw={obs.raw.strip()[:240]!r}"
            )
        return f"[verdict={obs.verdict!r}] raw={obs.raw.strip()[:240]!r}"


# =====================================================================
# slice-02 -- per-slice re-verify against the frozen baseline (CT-5 / CT-7)
# =====================================================================
#
# The freeze is feature-level (ADR-FLOW-002 D8): the FIRST DELIVER gate-IN writes
# the `ContractFrozen` baseline; EVERY subsequent per-slice gate-IN RE-VERIFIES the
# LIVE feature-delta against that baseline (OUT=IN re-earn) and never re-opens the
# ratification window. The one post-freeze mutation permitted is the status-flip
# "slice shipped" (D8 line 101); ANY other mutation is drift -> HALT.
#
# active-RED scaffold (atdd_pure -- NOT @skip). At HEAD the gate has NO re-verify
# behaviour (verified 2026-06-19): `evaluate_contract_freeze` runs the SAME
# structural check on every invocation and `main` writes a `ContractFrozen` record
# on EVERY PASS. So at HEAD:
#
#   * the freeze gate does NOT diff the live feature-delta against the frozen
#     baseline -> an EDITED_SECTION / ADDED_SLICE live delta that is still
#     structurally well-formed RE-PASSES (no drift HALT) -- the re-verify
#     scenarios' `then_verdict_is(FAIL)` fire their named RED (PASS != FAIL);
#   * a second well-formed invocation writes a SECOND `ContractFrozen` record ->
#     the feature-level-single-baseline scenario's `then_frozen_once` fires its
#     named RED (2 != 1).
#
# Each driving-port re-invocation captures these as observables the Then turns into
# a NAMED semantic AssertionError -- never a collection / import / setup error. The
# net-new production DELIVER ships (the re-verify diff + the single-baseline guard)
# turns them GREEN. The driving port + subprocess machinery is REUSED verbatim from
# `ContractFreezeComposition` (the gate is the same `des verify-deliver-entry-
# contract`; only the temp-repo lifecycle -- freeze-then-mutate-then-re-verify --
# differs).
#
# DELIVER-pinned assumptions (slice-02; update HERE, not in step bodies):
#   R1 (re-verify trigger): the SAME `des verify-deliver-entry-contract` subcommand
#      is re-invoked per slice; when a `ContractFrozen` baseline already exists for
#      the feature, the gate RE-VERIFIES instead of re-freezing.
#   R2 (drift verdict): a post-freeze mutation beyond the status-flip "slice
#      shipped" -> the §17 FAIL verdict (HALT, the confirmable-defect class).
#   R3 (single baseline): across re-verifies the ledger carries EXACTLY ONE
#      `ContractFrozen` record (feature-level granularity, CT-7); a status-flip /
#      unchanged re-verify re-earns the freeze, it does NOT mint a second baseline.


@dataclass
class ContractReVerifyComposition:
    """Drives the freeze-then-re-verify lifecycle through the real freeze gate.

    Re-uses ``ContractFreezeComposition`` for the freeze (first gate-IN) and for the
    subprocess driving port; this dataclass only owns the freeze-then-mutate-then-
    re-verify temp-repo lifecycle the slice-02 scenarios need.
    """

    _edit: PostFreezeEdit | None = field(default=None)
    _repo_root: Path | None = field(default=None)
    _freeze: ContractFreezeComposition = field(
        default_factory=ContractFreezeComposition
    )
    _reverify_obs: _GateObservable | None = field(default=None)

    # --- Given: a feature already frozen at the first DELIVER gate-IN ---------

    def given_a_frozen_contract(self, tmp_path: Path) -> None:
        """Freeze a structurally-complete contract once (the frozen baseline)."""
        self._freeze.given_contract_shape(ContractShape.COMPLETE)
        self._freeze.when_the_freeze_gate_runs_at_deliver_entry(tmp_path)
        self._repo_root = tmp_path

    # --- Given: how the live feature-delta diverges from the baseline ---------

    def given_post_freeze_edit(self, edit: PostFreezeEdit) -> None:
        """Arm how the LIVE feature-delta differs from the frozen baseline."""
        self._edit = edit

    # --- When: the per-slice gate-IN re-verifies the live delta ---------------

    def when_the_per_slice_gate_reverifies(self) -> None:
        """Mutate the live feature-delta per the armed edit, then re-run the gate."""
        self._apply_live_edit(self._require_repo())
        self._reverify_obs = self._freeze._drive_gate(self._require_repo())

    # --- Then: the re-verify verdict + the single-baseline invariant ----------

    def then_reverify_verdict_is(self, expected: FreezeVerdict) -> None:
        """The re-verify returned EXACTLY the expected §17 verdict (drift -> FAIL)."""
        obs = self._require_reverify()
        from .domain_types import LOCKED_VERDICTS

        assert obs.verdict in LOCKED_VERDICTS, (
            f"the per-slice re-verify must emit one of the §17 LOCKED FIVE verdicts "
            f"{sorted(LOCKED_VERDICTS)!r} (ADR-GV-001, no sixth) -- it emitted "
            f"verdict={obs.verdict!r}. {self._diag()}"
        )
        assert obs.verdict == expected.value, (
            f"a per-slice re-verify of a {self._edit.value if self._edit else '?'!r} "
            f"live feature-delta against the frozen baseline must return "
            f"{expected.value!r} (status-flip/unchanged re-earn the freeze -> PASS; "
            f"any other post-freeze mutation is drift -> HALT/FAIL, ADR-FLOW-002 D8) "
            f"-- got {obs.verdict!r}. {self._diag()}"
        )

    def then_frozen_exactly_once(self) -> None:
        """Across re-verifies, EXACTLY ONE ``ContractFrozen`` baseline exists (CT-7).

        Feature-level freeze granularity: the first gate-IN writes the single
        baseline; a status-flip / unchanged re-verify re-earns the freeze without
        minting a second baseline (never re-opening the ratification window).
        """
        frozen = self._freeze._read_contract_frozen_records(self._require_repo())
        assert len(frozen) == 1, (
            f"the freeze is feature-level (ADR-FLOW-002 D8 / CT-7): exactly ONE "
            f"'ContractFrozen' baseline may exist across ALL per-slice re-verifies "
            f"-- a re-verify RE-EARNS the freeze, it does NOT mint a second baseline "
            f"-- but the ledger carries {len(frozen)} such records. {self._diag()}"
        )

    # --- live-delta mutation (the per-slice edit applied after freeze) --------

    def _apply_live_edit(self, repo_root: Path) -> None:
        """Rewrite the live feature-delta per the armed PostFreezeEdit.

        Every drift variant kept STRUCTURALLY WELL-FORMED on purpose: the live
        delta still passes the slice-01 structural check (locked sections present,
        valid Slice Plan, an AT module per planned slice). So the ONLY thing that
        can REFUSE it is the per-slice drift-detection against the frozen baseline
        -- the net-new slice-02 behaviour. This is what keeps the drift scenarios
        a genuine RED rather than tautologically re-passing the structural check.
        """
        delta = repo_root / "docs" / "feature" / _FEATURE_ID / "feature-delta.md"
        baseline = delta.read_text(encoding="utf-8")
        if self._edit is PostFreezeEdit.ADDED_SLICE:
            # The added slice-02 row must itself be backed by an AT module, so the
            # structural AT-module-per-slice check still PASSES -- only the
            # drift-detection (a row added after freeze) may refuse it.
            self._freeze._write_slice_at_module(self._require_repo())
            self._add_second_slice_at_module(self._require_repo())
        delta.write_text(self._mutate(baseline), encoding="utf-8")

    def _add_second_slice_at_module(self, repo_root: Path) -> None:
        """Author a real ``.feature`` binding slice-02 to an AT (keeps ADDED_SLICE
        structurally well-formed -- the added row is AT-backed)."""
        at_dir = (
            repo_root / "tests" / "des" / "acceptance" / _FEATURE_ID.replace("-", "_")
        )
        at_dir.mkdir(parents=True, exist_ok=True)
        (at_dir / "slice-02.feature").write_text(
            f"@feature-{_FEATURE_ID}\n"
            "Feature: the slice-02 row smuggled in after freeze\n\n"
            "  @slice-02 @driving_port\n"
            "  Scenario: an AT-backed row added post-freeze\n"
            "    Given a structurally-complete contract\n"
            "    When the freeze gate runs\n"
            "    Then the contract is frozen\n",
            encoding="utf-8",
        )

    def _mutate(self, baseline: str) -> str:
        """Project the frozen baseline text onto the armed live variant."""
        if self._edit is PostFreezeEdit.UNCHANGED:
            return baseline
        if self._edit is PostFreezeEdit.STATUS_FLIP:
            # The ONE permitted post-freeze mutation (D8 line 101): a Slice-Plan
            # row status -> "shipped". Structurally well-formed; must re-PASS.
            return baseline.replace("| pending |", "| shipped |", 1)
        if self._edit is PostFreezeEdit.EDITED_SECTION:
            # A locked [REF] section body rewritten after freeze (a value statement
            # changed) -- structurally well-formed but a drift -> must HALT.
            return baseline.replace(
                "A thin DELIVER-IN vertical.",
                "A WHOLLY DIFFERENT post-freeze value statement.",
                1,
            )
        if self._edit is PostFreezeEdit.ADDED_SLICE:
            # A Slice-Plan row ADDED after freeze (the ratification window cannot
            # re-open per-slice) -- structurally well-formed (the added slice-02 row
            # is AT-backed, see _apply_live_edit) but a drift -> must HALT.
            return baseline.replace(
                "@walking-skeleton @driving_port | ~4 ATs. |\n",
                "@walking-skeleton @driving_port | ~4 ATs. |\n"
                "| slice-02 | A row smuggled in after freeze. | pending | "
                "@driving_port | ~2 ATs. |\n",
                1,
            )
        raise AssertionError(  # pragma: no cover - exhaustive enum guard
            f"unhandled PostFreezeEdit {self._edit!r}"
        )

    # --- internal accessors --------------------------------------------------

    def _require_repo(self) -> Path:
        assert self._repo_root is not None, (
            "a re-verify scenario must FREEZE the contract (first gate-IN) before "
            "a per-slice gate-IN can re-verify against the baseline."
        )
        return self._repo_root

    def _require_reverify(self) -> _GateObservable:
        assert self._reverify_obs is not None, (
            "the per-slice re-verify driving port was never invoked -- a When step "
            "must re-run the gate before a Then reads its re-verify verdict."
        )
        return self._reverify_obs

    def _diag(self) -> str:
        obs = self._reverify_obs
        if obs is None:
            return "[no re-verify observable captured]"
        if not obs.recognised:
            return (
                f"[the {_SUBCOMMAND_ID!r} subcommand is UNREGISTERED at HEAD] "
                f"raw={obs.raw.strip()[:240]!r}"
            )
        return f"[re-verify verdict={obs.verdict!r}] raw={obs.raw.strip()[:240]!r}"


# =====================================================================
# slice-03 -- the code-design-manifest validity fold (CT-4 / KPI-3)
# =====================================================================
#
# DESIGN is optional (ADR-FLOW-002 D2): a feature MAY ship a
# `code-design.manifest.yaml`. slice-03 FOLDS that manifest's VALIDITY into the
# DELIVER-entry structural-completeness check (ADR-FLOW-004 DDD-1 step 3 / DDD-5):
#
#   * manifest PRESENT + VALID   -> the fold CONTRIBUTES; a structurally-complete
#                                   contract still freezes (PASS);
#   * manifest PRESENT + INVALID -> the freeze gate FAILs, the diagnostic naming
#                                   the manifest defect (stale sut / bad schema);
#   * manifest ABSENT            -> NO re-block on manifest grounds (the
#                                   DESIGN-absent soft-gate already advised
#                                   upstream, ADR-FLOW-002 D5a) -> PASS.
#
# active-RED scaffold (atdd_pure -- NOT @skip). At HEAD the gate has NO manifest
# fold (verified 2026-06-19: zero "manifest" references in
# `src/des/cli/verify_deliver_entry_contract.py`). So at HEAD:
#
#   * an INVALID manifest is IGNORED -> the otherwise-structurally-complete
#     contract RE-PASSES (no manifest FAIL) -> the INVALID example's
#     `then_verdict_is(FAIL)` fires its named RED (PASS != FAIL). This is the
#     genuine active-RED that forces DELIVER to ship the fold.
#   * the VALID + ABSENT examples PASS at HEAD too (the manifest is ignored), so
#     they are the CONTROL arms: after the fold lands they must STILL pass (the
#     fold must not re-block a valid or a consciously-absent manifest). They keep
#     the Outline honest -- a fold that blanket-FAILed any manifest-bearing
#     feature would red the VALID arm.
#
# F-D-09 (forbidden-import-roots): the manifest validator genuinely lives under
# `scripts/cli/**`, so the production gate invokes it as a SUBPROCESS
# (`python -m scripts.cli.validate_component_manifest`), NEVER `from scripts.*
# import`. This AT does not import it either -- it only WRITES the manifest fixture
# and lets the REAL freeze-gate driving port fold it.
#
# Mandate-13 (driving-port-only): the SUT is driven through the SAME real
# `des verify-deliver-entry-contract` Layer-3 subprocess as slice-01/02; only the
# fixture (a manifest written alongside the feature-delta) differs. The driving
# port + subprocess machinery is REUSED verbatim from `ContractFreezeComposition`.
#
# DELIVER-pinned assumptions (slice-03; update HERE, not in the step bodies):
#   M1 (manifest filename): a code-design manifest ships at
#      `docs/feature/<id>/code-design.manifest.yaml` (gate_g.py:80
#      `_MANIFEST_FILENAME`). The freeze gate folds it WHEN that file is present.
#   M2 (validity mechanism): the gate validates the manifest via
#      `validate_component_manifest` (subprocess) -- exit 0 valid, exit 1 stale
#      sut symbol, exit 2 schema-invalid. exit != 0 -> the fold FAILs the freeze.
#   M3 (absence is not a block): no manifest file -> the fold is N/A; the contract
#      freezes on its other halves (DESIGN optional, D5a).

# The code-design manifest filename the freeze gate folds (M1, gate_g.py:80).
_MANIFEST_FILENAME = "code-design.manifest.yaml"

# A real, grep-findable sut symbol for the VALID manifest fixture: a production
# symbol that genuinely exists in the cited file in the REAL repo (the manifest
# validator's `_ground_sut` resolves sut paths against the real repo root, not the
# temp --repo-root). Keeping it real keeps the VALID fixture a true exit-0.
_VALID_SUT = "src/des/cli/verify_deliver_entry_contract.py::evaluate_contract_freeze"
# A stale sut symbol for the INVALID manifest fixture: a name that is NOT present
# in its cited file -> the validator exits 1 (ManifestStale).
_STALE_SUT = (
    "src/des/cli/verify_deliver_entry_contract.py::__no_such_symbol_exists_anywhere__"
)


@dataclass
class ManifestFoldComposition:
    """Drives the manifest-validity fold through the real freeze gate (slice-03).

    Re-uses ``ContractFreezeComposition`` for the structurally-complete contract
    and the subprocess driving port; this dataclass only owns writing the
    ``code-design.manifest.yaml`` fixture in the armed validity state.
    """

    _manifest: ManifestState | None = field(default=None)
    _repo_root: Path | None = field(default=None)
    _freeze: ContractFreezeComposition = field(
        default_factory=ContractFreezeComposition
    )
    _observable: _GateObservable | None = field(default=None)

    # --- Given: a structurally-complete contract that ships a manifest --------

    def given_manifest_state(self, manifest: ManifestState) -> None:
        """Arm whether the shipped code-design manifest is valid / invalid / absent."""
        self._manifest = manifest

    # --- When: the freeze gate folds the manifest at the first gate-IN --------

    def when_the_freeze_gate_folds_the_manifest(self, tmp_path: Path) -> None:
        """Write a complete contract + the armed manifest, then run the REAL gate.

        The contract is otherwise structurally COMPLETE (so the ONLY thing that
        can refuse it is the manifest-validity fold -- the net-new slice-03
        behaviour), keeping the INVALID example a genuine RED rather than
        tautologically failing the slice-01 structural check.
        """
        self._repo_root = self._write_contract_with_manifest(tmp_path)
        self._observable = self._freeze._drive_gate(self._repo_root)

    # --- Then: the §17 verdict the fold projects ------------------------------

    def then_verdict_is(self, expected: FreezeVerdict) -> None:
        """The freeze gate returned EXACTLY the expected §17 verdict for the fold."""
        obs = self._require_observable()
        from .domain_types import LOCKED_VERDICTS

        assert obs.verdict in LOCKED_VERDICTS, (
            f"the manifest-fold freeze gate must emit one of the §17 LOCKED FIVE "
            f"verdicts {sorted(LOCKED_VERDICTS)!r} (ADR-GV-001, no sixth) -- it "
            f"emitted verdict={obs.verdict!r}. {self._diag()}"
        )
        assert obs.verdict == expected.value, (
            f"folding a {self._manifest.value if self._manifest else '?'!r} "
            f"code-design manifest into the DELIVER-entry structural check must "
            f"return {expected.value!r} (a VALID manifest contributes to PASS; an "
            f"INVALID manifest -- stale sut or bad schema -- FAILs the freeze; an "
            f"ABSENT manifest does NOT re-block since DESIGN is optional, "
            f"ADR-FLOW-004 DDD-5) -- got {obs.verdict!r}. {self._diag()}"
        )

    # --- real temp-repo fixture (complete contract + the manifest) ------------

    def _write_contract_with_manifest(self, tmp_path: Path) -> Path:
        """A structurally-complete contract PLUS the armed manifest fixture (M1)."""
        self._freeze.given_contract_shape(ContractShape.COMPLETE)
        repo_root = self._freeze._write_repo(tmp_path)
        self._write_manifest(repo_root)
        return repo_root

    def _write_manifest(self, repo_root: Path) -> None:
        """Materialise (or omit) ``code-design.manifest.yaml`` per the armed state."""
        assert self._manifest is not None, (
            "a manifest-fold scenario must arm an explicit ManifestState before "
            "the freeze gate runs."
        )
        if self._manifest is ManifestState.ABSENT:
            return
        feature_dir = repo_root / "docs" / "feature" / _FEATURE_ID
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / _MANIFEST_FILENAME).write_text(
            self._render_manifest(), encoding="utf-8"
        )

    def _render_manifest(self) -> str:
        """Render a code-design manifest in the armed validity state (M2).

        VALID renders a schema-valid manifest whose sut symbol is grep-findable
        (validator exit 0). INVALID renders the same schema with a STALE sut symbol
        (validator exit 1) -- a deliberately confirmable manifest defect the fold
        must surface as a freeze FAIL.
        """
        sut = _STALE_SUT if self._manifest is ManifestState.INVALID else _VALID_SUT
        return (
            'schema-version: "1.0"\n'
            f"feature-id: {_FEATURE_ID}\n"
            "unbounded-input-domains:\n"
            "  - id: feature-id\n"
            f'    sut: "{sut}"\n'
            '    domain: "the feature id string the gate is run for"\n'
            '    why-unbounded: "any kebab feature id is accepted at the gate"\n'
            "    canonical-category: C5\n"
            "    declared-at: design\n"
        )

    # --- internal accessors ---------------------------------------------------

    def _require_observable(self) -> _GateObservable:
        assert self._observable is not None, (
            "the manifest-fold freeze gate driving port was never invoked -- a When "
            "step must run the gate before a Then reads its verdict."
        )
        return self._observable

    def _diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "[no manifest-fold observable captured]"
        if not obs.recognised:
            return (
                f"[the {_SUBCOMMAND_ID!r} subcommand is UNREGISTERED at HEAD] "
                f"raw={obs.raw.strip()[:240]!r}"
            )
        return f"[manifest-fold verdict={obs.verdict!r}] raw={obs.raw.strip()[:240]!r}"
