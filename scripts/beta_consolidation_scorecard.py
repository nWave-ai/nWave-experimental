#!/usr/bin/env python3
"""GOAL CONTRACT for the `consolidation-for-wider-beta-testing` epic.

THIS SCRIPT *IS* THE MEASUREMENT of "is the spine consolidated enough to open a
WIDER (incl. non-Python) beta with sisters dogfooding". Same committed code +
same repo state -> same number. A member that flips is a reviewable git diff.

STATUS: FIRST-CUT, authored 2026-06-23 from the adversarial-review-corrected
beta-necessary set (R1 completeness + R2 correctness over docs/product/backlog.md)
+ the D8 `F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE` multi-language consolidation.
The member set + per-member predicates ARE the epic's working definition until
`/nw-discuss` epic-mode formalizes it (Ale ratifies the bar + member set).

UNIT = an epic MEMBER (a beta-blocker fix or a multi-lang-adapter realization). A
member is DONE iff its deterministic predicate holds over the committed repo.
Fail-closed: an unverifiable member is NOT DONE.

PREDICATE-HONESTY (lesson F-BETA-SCORECARD-PREDICATES-FILE-EXISTENCE-NOT-CORRECTNESS,
proven by the swarm that M6 passed a file-existence predicate while carrying a real
bug): each predicate here checks for the FIX'S CODE-SIGNATURE (a sentinel the fix
must introduce) PLUS, where one exists, the member's regression-AT file. This is a
SHALLOW structural proof. The DEEP proof is the member's AT GREEN under the full
suite -- run separately. A member flips to DONE only when its committed artifacts
carry the fix signature, never on assertion. Members measuring OPEN work read OPEN
until the fix lands (the scorecard is a gradient tracker, expected to start low).

Pure stdlib only (target-machine independence). No git, no external packages.

Usage:
    python scripts/beta_consolidation_scorecard.py
    python scripts/beta_consolidation_scorecard.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from _scorecard_fs_helpers import REPO
from _scorecard_fs_helpers import file_contains as _file_contains
from _scorecard_fs_helpers import file_exists as _file_exists

from des.domain.telemetry_paths import LedgerFamily
from des.domain.telemetry_paths import ledger_dir as _ledger_dir


if TYPE_CHECKING:
    from collections.abc import Callable


def _dir_has_children(rel: str, glob: str) -> bool:
    base = REPO / rel
    return base.is_dir() and any(base.glob(glob))


# Feature-end attestation (honest M3 check, mirrors flow_v2_closure_scorecard):
# a feature is DONE only when a REAL feature-end RECORD exists -- the event-type
# AND the feature_id on the SAME JSONL line (a prose mention can never credit;
# "slices delivered" is NOT done). Fail-closed on an unreadable ledger.
_LEDGER_DIR = _ledger_dir(REPO, LedgerFamily.ATDD_PURE)
_FEATURE_END_EVENTS = ("FeatureEndReviewVerdict", "EBatchRefactorCompleted")


def _has_feature_end_record(feature_id: str) -> bool:
    if not _LEDGER_DIR.exists():
        return False
    event_tokens = tuple(f'"event":"{e}"' for e in _FEATURE_END_EVENTS) + tuple(
        f'"event": "{e}"' for e in _FEATURE_END_EVENTS
    )
    fid_tokens = (f'"feature_id":"{feature_id}"', f'"feature_id": "{feature_id}"')
    for f in _LEDGER_DIR.rglob("*"):
        if not f.is_file():
            continue
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in txt.splitlines():
            if any(e in line for e in event_tokens) and any(
                t in line for t in fid_tokens
            ):
                return True
    return False


def _flow_v2_honestly_closed() -> bool:
    """W2 computed predicate (non-gameable, replaces the prose-grep on RESUME.md
    that the adversarial swarm 2026-06-29 refuted as theater). flow-v2 is honestly
    closed iff EVERY flow-v2 feature carries a FeatureEnd ledger record (a real
    seal whose FullSuiteLegRan-attested cycle ran) -- the SAME non-gameable
    mechanism P1/P2 use. The feature list is DELEGATED to
    flow_v2_closure_scorecard.FEATURES (the flow-v2 SSOT -- no duplication, no
    drift, resolves Ale's two-scorecard contradiction by making W2 read the
    flow-v2 SSOT instead of a disavowed prose string). Fail-closed on any error."""
    try:
        import importlib.util

        path = REPO / "scripts" / "flow_v2_closure_scorecard.py"
        spec = importlib.util.spec_from_file_location("_flow_v2_closure_for_w2", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        feats = [f["id"] for f in mod.FEATURES]
        return bool(feats) and all(_has_feature_end_record(fid) for fid in feats)
    except Exception:
        return False


def _sealed_and_reconciled(feature_id: str) -> bool:
    """Non-gameable done-predicate: a FeatureEnd seal AND no truncated slices.

    Closes the LEVEL-3 theater the adversarial swarm 2026-06-29 exposed: `des
    feature-end run` emits the FeatureEnd record WITHOUT running verify-integrity's
    truncation check, so a record-only predicate (`_has_feature_end_record`) is
    gameable by a theater-seal (the record says done; verify-integrity says the
    feature is TRUNCATED -- a Slice-Plan slice declared but never delivered).
    This requires BOTH the seal record AND that verify-integrity finds no
    undelivered slice (the un-gameable `.feature`/attested-prose oracle). Re-uses
    the verify-integrity truncation oracle directly (one SSOT, no drift).
    Fail-closed on any error."""
    if not _has_feature_end_record(feature_id):
        return False
    try:
        from des.cli.verify_deliver_integrity import _undelivered_slice_plan_slices

        return not _undelivered_slice_plan_slices(REPO, feature_id)
    except Exception:
        return False


def _corpus_migration_done() -> bool:
    """P2-specific NON-gameable predicate: the seal AND the REAL migration measure.

    The adversarial swarm 2026-06-30 proved `_sealed_and_reconciled` is gameable for
    a MIGRATION feature: reconciling-OUT the migration slices (slice-02/03) empties
    `_undelivered_slice_plan_slices`, so a single-slice (slice-01) seal passes the
    truncation oracle while the 140 forking ATs are NOT migrated. The seal/reconcile
    proxy never inspects the actual corpus. This predicate ALSO delegates to the
    project's own committed migration measure (`at_corpus_migration_scorecard`):
    PHASE-2 is DONE iff ZERO pure non-WS interpreter-forks remain. Fail-closed."""
    if not _sealed_and_reconciled("f-test-corpus-migration-in-process"):
        return False
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "_at_corpus_migration_scorecard",
            REPO / "scripts" / "at_corpus_migration_scorecard.py",
        )
        if spec is None or spec.loader is None:
            return False
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        scan = mod._scan()
        # PHASE-2 DONE iff zero pure non-WS interpreter-forks remain (the CONTRACT).
        return int(scan["pure_spawn"]) == 0
    except Exception:
        return False


@dataclass(frozen=True)
class Member:
    """One epic member + its deterministic DONE predicate + the fix signature."""

    mid: str
    title: str
    tier: str  # HARD | SHOULD | MULTILANG
    predicate: Callable[[], bool]
    done_signature: str  # what the predicate looks for (honest, reviewable)


# --- The consolidation-for-wider-beta-testing member set (first-cut) ----------
_MEMBERS: tuple[Member, ...] = (
    # ---- HARD must-fix (5): a beta-tester is blocked or silently corrupted ----
    Member(
        mid="C1",
        title="F-DES-E2-CONTRACT-GATE — E2 routed through TestRunnerPort, degrade-LOUD not hard-refuse (non-Python)",
        tier="HARD",
        # DONE (commit 2a6d2179b, 2026-06-23) via the full degrade-loud CHAIN, not
        # the removal of _emit_interpreter_unavailable (which legitimately stays for
        # the committed-scope path). STRONGER 3-part signature proving the chain:
        # (1) run_contract_gate emits the interpreter-unavailable INDETERMINATE event
        # (degrade-loud-and-proceed, not exit-2); (2) verify_slice_commit mints the
        # honest SliceCommitIndeterminate (never a fabricated SliceCommitVerified);
        # (3) the carpaccio in-order guard accepts that INDETERMINATE predecessor so
        # a non-Python slice chain progresses. Reviewed diff, not silent drift.
        predicate=lambda: (
            _file_contains(
                "src/des/cli/run_contract_gate.py",
                "interpreter-unavailable.indeterminate",
            )
            and _file_contains(
                "src/des/cli/verify_slice_commit_completeness.py",
                "SliceCommitIndeterminate",
            )
            and _file_contains(
                "src/des/adapters/drivers/hooks/carpaccio_intercept.py",
                "SliceCommitIndeterminate",
            )
        ),
        done_signature="interpreter-absence degrades LOUD to an INDETERMINATE event (not exit-2); verify_slice_commit mints honest SliceCommitIndeterminate (never fabricated SliceCommitVerified); carpaccio in-order guard accepts the INDETERMINATE predecessor",
    ),
    Member(
        mid="C2",
        title="F-DES-SUBPROCESS-PYTHONPATH-PROPAGATION — all gate subprocesses carry des on the path (no false-DONE)",
        tier="HARD",
        # DONE via CENTRALIZE (commit 3ff7e4d14, 2026-06-23): a des_spawn helper
        # applies python_for + des_subprocess_env BY CONSTRUCTION; the hot-path
        # carpaccio intercept routes through it; AND an enforcing arch-test bans
        # any inline des-module spawn. STRONGER than the original per-file
        # des_subprocess_env grep: the arch-test proves NO site can bypass (not
        # just that one file uses the env). Predicate updated (reviewed diff, not
        # silent drift) because the real fix centralizes rather than per-file.
        predicate=lambda: (
            _file_contains("src/des/runtime/interpreter.py", "def des_spawn")
            and _file_contains(
                "src/des/adapters/drivers/hooks/carpaccio_intercept.py", "des_spawn"
            )
            and _file_exists("tests/build/test_no_inline_des_module_spawn.py")
        ),
        done_signature="des_spawn centralizes every des-module spawn (python_for + des_subprocess_env by construction); carpaccio_intercept routes through it; enforcing arch-test test_no_inline_des_module_spawn bans inline des-module spawns",
    ),
    Member(
        mid="C3",
        title="F-CARPACCIO-FUTURE-SLICE-SCAFFOLD-BLOCKS-COMMIT — future-slice reds do not block slice-01..N-1 commit",
        tier="HARD",
        # DONE (commit a48496517, 2026-06-23) via the E2 collection-scope fix:
        # run_contract_gate narrows its collected node-ids to shipped+entering
        # @slice-NN tags + emits collected_slice_tags. STRONGER than the original
        # dir-existence check (file-existence != correctness, the known
        # anti-pattern): proves the narrowing helper + the AC-2 observable + the
        # regression AT. NOTE: RECLASSIFIED — the commit-stage whole-tree hook was
        # removed (.pre-commit-config.yaml:232) so the original commit-wedge is
        # stale on this branch; this is a Gate-Scope-correctness fix, demotion from
        # HARD pending Ale ratification (see backlog C3).
        predicate=lambda: (
            _file_contains(
                "src/des/cli/run_contract_gate.py", "_narrow_to_shipped_entering"
            )
            and _file_contains(
                "src/des/cli/run_contract_gate.py", "collected_slice_tags"
            )
            and _dir_has_children(
                "tests/des/acceptance/carpaccio_future_slice_scaffold", "*.feature"
            )
        ),
        done_signature="run_contract_gate narrows E2 collection to shipped+entering @slice-NN tags (excludes future scaffolds) + emits collected_slice_tags; regression AT present",
    ),
    Member(
        mid="C4",
        title="M6 F-SPINE-WAVE-FLOOR-AUTO-CLOSE — dual-aware ownership (platform-architect design+devops), devops floor closes",
        tier="HARD",
        # DONE when _maybe_close_owner_floor uses the dual-aware predicate (mirror
        # of _marker_is_on_spine), provable by the service no longer keying the
        # close solely on the single-valued WAVE_OWNERS.get, + a devops-floor AT.
        predicate=lambda: (
            _file_contains(
                "src/des/application/subagent_stop_service.py",
                "_PLATFORM_ARCHITECT_WAVES",
            )
            and _file_exists(
                "tests/des/acceptance/floor_auto_close_cross_wave/"
                "test_floor_auto_close_devops_wave.py"
            )
        ),
        done_signature="subagent_stop_service close uses _PLATFORM_ARCHITECT_WAVES (dual-aware) + a devops-wave close AT exists",
    ),
    Member(
        mid="C5",
        title="F-DES-FEATURE-ID-MARKER-DISTINCT — carpaccio feature-id is its own marker, not DES-PROJECT-ID overload",
        tier="HARD",
        predicate=lambda: _file_contains(
            "src/des/domain/des_marker_parser.py", "DES-FEATURE-ID"
        ),
        done_signature="a distinct DES-FEATURE-ID marker exists (DES-PROJECT-ID no longer overloaded as the carpaccio feature-id)",
    ),
    # C15 (F-DES-EXEMPT-AND-WAVE-CLEAR-SELF-AUTHORIZABLE) was briefly reconciled in
    # here as the 6th HARD, then RELOCATED to SF-tier per Ale's ruling 2026-06-24
    # (option C). RATIONALE: the un-mintable wave-clear grant requires keyed signing,
    # and in OSS key-holder == forger (the agent and the human share the machine), so
    # a keyed-HMAC grant is theater in OSS -- the OSS HMAC primitive was deliberately
    # demoted 2026-06-11 for exactly this reason. The un-mintable guarantee lives in
    # SF-tier, where the human/agent boundary is architecturally real. OSS keeps the
    # audit-logged wave-clear (who/why JSONL) WITHOUT the crypto guarantee; this is a
    # documented OSS residual, NOT an OSS scorecard member. Denominator returns 17->16.
    # See backlog F-DES-EXEMPT-AND-WAVE-CLEAR-SELF-AUTHORIZABLE (SF-relocated).
    # ---- SHOULD-fix (6): tester hits it, a workaround exists -----------------
    Member(
        mid="C6",
        title="F-FEATURE-END-RUN-ATDD-PURE-INCOMPATIBLE — des feature-end run works on an atdd_pure feature",
        tier="SHOULD",
        # DONE (commit e1a34da4a, 2026-06-24, ADR-098 ratified). TWO halves, both
        # proven: (1) env-bug — feature_end_cycle_service spawns gate subprocesses
        # via des_spawn (the C2 centralized helper that carries des on the path);
        # (2) WS-gate manifest-optional — _load_manifest returns None on absence
        # (no fail-close exit-2) and _delta_derived_feature_under_gate computes
        # applicability from the git-delta (the SAME un-gameable cross-check the
        # empty-entry_points branch uses, no duplicate logic) so an atdd_pure
        # (manifest-less) feature seals. STRONGER than the old des_subprocess_env
        # string-check: proves the WS-gate VALUE half + the regression ATs.
        predicate=lambda: (
            _file_contains(
                "src/des/application/feature_end_cycle_service.py", "des_spawn"
            )
            and _file_contains(
                "src/des/cli/walking_skeleton_gate.py",
                "_delta_derived_feature_under_gate",
            )
            and _file_contains(
                "src/des/cli/walking_skeleton_gate.py", "dict[str, object] | None"
            )
            and _dir_has_children(
                "tests/des/acceptance/ws_gate_manifest_optional", "*.feature"
            )
        ),
        done_signature="feature_end_cycle_service spawns via des_spawn (env) + WS-gate _load_manifest absent->None + _delta_derived_feature_under_gate computes applicability from the git-delta (manifest-optional, ADR-098); regression ATs present",
    ),
    Member(
        mid="C7",
        title="F-COHORT-GATE-PREAUTHORING-CHICKEN-EGG — Phase-0 cohort gate works on a fresh (pre-authoring) feature",
        tier="SHOULD",
        predicate=lambda: _file_contains(
            "scripts/cli/cohort_classifier.py", "Test Placement"
        ),
        done_signature="cohort_classifier counts candidate-ATs from the feature-delta [REF] Test Placement prose (pre-authoring)",
    ),
    Member(
        mid="C8",
        title="F-SUBAGENT-STOP-RESOLVER-FALSE-BLOCKS-QUOTED-MARKERS — fenced/quoted markers do not false-block a read-only return",
        tier="SHOULD",
        predicate=lambda: _file_contains(
            "src/des/adapters/drivers/hooks/subagent_stop_handler.py",
            "fenced",
        ),
        done_signature="subagent_stop_handler ignores markers inside fenced/quoted regions (or exempts read-only troubleshooter)",
    ),
    Member(
        mid="C9",
        title="F-COMMIT-SLICE-OMITS-SLICE-ID-TRAILER — commit-slice appends Slice-Id, or rejects a message lacking it",
        tier="SHOULD",
        predicate=lambda: _file_contains("src/des/cli/commit_slice.py", "Slice-Id"),
        done_signature="commit_slice appends a Slice-Id trailer (or refuses up-front) instead of letting verify-slice-commit fail downstream",
    ),
    Member(
        mid="C10",
        title="F-CARPACCIO-SLICE-PLAN-PARSER-BRITTLE — one parser, format-robust 3-col slice plan",
        tier="SHOULD",
        # DONE (commit 6593cfe12, 2026-06-23) via ONE shared tolerant parser.
        # STRONGER than the original file-existence check (file-existence !=
        # correctness): proves the shared tolerant parser EXISTS in carpaccio_format,
        # the hook DELEGATES to it (so CLI + hook share it by construction), AND the
        # regression AT exists. Reviewed diff (the AT landed at a different path than
        # the first-cut predicate guessed).
        predicate=lambda: (
            _file_contains("src/des/cli/carpaccio_format.py", "parse_slice_plan_rows")
            and _file_contains(
                "src/des/adapters/drivers/hooks/subagent_stop_handler.py",
                "parse_slice_plan_rows",
            )
            and _dir_has_children(
                "tests/des/acceptance/carpaccio_slice_plan_parser", "*.feature"
            )
        ),
        done_signature="ONE tolerant parse_slice_plan_rows in carpaccio_format (escaped-pipe + H2-H4 + col-tolerant); the hook delegates to it (CLI + hook share by construction); regression AT present",
    ),
    Member(
        mid="C11",
        title="F-CARPACCIO-DISTILL-DELIVER-HANDOFF-FRICTION — scenario discovery + verdict recording need no manual steps",
        tier="SHOULD",
        # DONE (commit b863389f0, 2026-06-24). STRONGER than a bare file-exists:
        # the predicate proves a NAMED closing AT for EACH of the 3 frictions —
        # AC-1 feature-tag discovery, AC-2 the per-scenario @slice-NN mandate
        # rejection, AC-3 the record-at-review-verdict -> check_at_review
        # round-trip. Empirical HEAD check (acceptance-designer) confirmed all 3
        # already closed in carpaccio_format._slice_scenarios + the verdict CLI,
        # so the ATs are live-green preservation guards locking the frictions shut.
        predicate=lambda: (
            _file_contains(
                "tests/des/acceptance/carpaccio_distill_deliver_handoff/"
                "test_handoff_no_manual_steps.py",
                "def test_ac1_feature_tag_discovery_finds_scenarios",
            )
            and _file_contains(
                "tests/des/acceptance/carpaccio_distill_deliver_handoff/"
                "test_handoff_no_manual_steps.py",
                "def test_ac2_missing_slice_tag_is_rejected",
            )
            and _file_contains(
                "tests/des/acceptance/carpaccio_distill_deliver_handoff/"
                "test_handoff_no_manual_steps.py",
                "def test_ac3_approved_verdict_round_trips",
            )
        ),
        done_signature="the 3 handoff frictions (file-tag discovery, slice-tag mandate, verdict round-trip) each have a NAMED closing AT (live-green preservation guards)",
    ),
    # ---- MULTILANG (D8): the language-adapter cohort, post-interface ----------
    Member(
        mid="C12",
        title="F-M42 — LanguageAdapterPlugin layering fixed (no src/des import from scripts/)",
        tier="MULTILANG",
        # DONE (already implemented; verified 2026-06-23): the file defines its
        # OWN ABC (class LanguageAdapterPlugin(ABC)), intentionally decoupled from
        # scripts.install.plugins.base.InstallationPlugin. The original predicate
        # `not contains "from scripts.install"` was DOCSTRING-NAIVE — it tripped on
        # the docstring's historical mention of the rejected M42 attempt, not a real
        # import (the file has ZERO scripts imports). STRONGER + docstring-immune
        # signature: the own-ABC class + no LINE-START scripts import. The no-import
        # is independently ENFORCED by the passing arch-test
        # tests/build/test_des_no_dev_root_imports.py (1 passed) + the
        # F_LANGUAGE_ADAPTER_PLUGIN_INFRASTRUCTURE AT suite (11 passed). Reviewed diff.
        predicate=lambda: (
            _file_exists("src/des/ports/language_adapter_plugin.py")
            and _file_contains(
                "src/des/ports/language_adapter_plugin.py",
                "class LanguageAdapterPlugin(ABC)",
            )
            and not _file_contains(
                "src/des/ports/language_adapter_plugin.py",
                "\nfrom scripts.",
            )
        ),
        done_signature="language_adapter_plugin.py defines its OWN ABC (class LanguageAdapterPlugin(ABC)), no line-start scripts import; no-dev-root-import arch-test + ABC AT suite pass; installed-package-safe",
    ),
    Member(
        mid="C13",
        title="Multi-lang TestRunner adapters — JS/TS run-facet adapter realized",
        tier="MULTILANG",
        # DEMOTED to OPEN 2026-06-24 by the adversarial theater-audit swarm
        # (catalogued != wired). The run-facet run_vitest_scope EXISTS + is correct
        # (resolve_tool + LOUD RunnerAdapterUnavailable), BUT it is NEVER REGISTERED
        # in the runner registry: seed_runner_registry (runner_registry.py:104-105)
        # registers only pytest + cargo-test; no nwave-lang-typescript entry-point.
        # So the PRODUCTION path RunnerAdapter("vitest").run() -> GLOBAL_REGISTRY
        # .lookup("vitest") -> None -> RunnerAdapterUnavailable, NEVER reaching
        # run_vitest_scope. The ATs drive run_vitest_scope DIRECTLY in a child
        # interpreter, bypassing the registry dispatch -> they prove the isolated
        # function, not the integrated wiring. My earlier predicate checked the
        # run-facet exists but NOT that it is wired -> a false DONE (the
        # objective-scorecard rule: DONE = built + WIRED, catalogued != wired). The
        # registration I scoped as a "follow-up" was load-bearing wiring, not
        # optional. Real-fix-signature now REQUIRES the run-facet wired into the
        # registry (+ resolve mapping). Needs a wiring DELIVER slice.
        predicate=lambda: (
            _file_contains(
                "src/des/adapters/driven/runner/vitest_runner.py",
                "def run_vitest_scope",
            )
            and _file_contains(
                "src/des/adapters/driven/runner/runner_registry.py", "run_vitest_scope"
            )
            and _dir_has_children(
                "tests/des/acceptance/vitest_test_runner_adapter", "*.feature"
            )
        ),
        done_signature="a JS/TS (vitest) run-facet run_vitest_scope exists AND is WIRED into the runner registry (production RunnerAdapter dispatch reaches it, not just the AT bypassing the registry); regression ATs present",
    ),
    Member(
        mid="C14",
        title="Multi-lang TestRunner adapters — Go run-facet adapter realized (cheapest, go test built-in)",
        tier="MULTILANG",
        # DEMOTED to OPEN 2026-06-24 by the adversarial theater-audit swarm
        # (catalogued != wired). Same defect as C13: run_go_scope EXISTS + is
        # correct, BUT is NEVER REGISTERED in seed_runner_registry (only pytest +
        # cargo-test are; no nwave-lang-go entry-point). PRODUCTION
        # RunnerAdapter("go-test").run() -> GLOBAL_REGISTRY.lookup("go-test") ->
        # None -> RunnerAdapterUnavailable, never reaching run_go_scope. The ATs
        # call run_go_scope directly in a child interpreter, bypassing the registry.
        # False DONE (built but not wired). Real-fix-signature now REQUIRES the
        # run-facet wired into the registry. Needs a wiring DELIVER slice.
        predicate=lambda: (
            _file_contains(
                "src/des/adapters/driven/runner/go_runner.py", "def run_go_scope"
            )
            and _file_contains(
                "src/des/adapters/driven/runner/runner_registry.py", "run_go_scope"
            )
            and _dir_has_children(
                "tests/des/acceptance/go_test_runner_adapter", "*.feature"
            )
        ),
        done_signature="a Go (go test) run-facet run_go_scope exists AND is WIRED into the runner registry (production RunnerAdapter dispatch reaches it, not just the AT bypassing the registry); regression ATs present",
    ),
    # ---- WAVE-REFACTOR: the flow-v2 wave-migration consolidation -------------
    # The wave-command/agent refactoring to declarative+lean form. DISTILL is the
    # SHIPPED precedent (f-distill-wave-migration); the consolidation extends it to
    # the remaining waves + the honest epic closure (Ale 2026-06-23: "includi nell
    # epic la feature di refactoring delle wave gia fatta per distill").
    Member(
        mid="W1",
        title="Wave-refactor — DISTILL wave-migration SHIPPED (the declarative+lean precedent)",
        tier="WAVE-REFACTOR",
        predicate=lambda: _sealed_and_reconciled("f-distill-wave-migration"),
        done_signature="f-distill-wave-migration feature-end-SEALED (FeatureEndReviewVerdict + EBatchRefactorCompleted in the ledger) — the lean-core+composed-modules wave precedent; non-gameable code-signature (was a _file_exists predicate-theater, refuted by the adversarial swarm 2026-06-29 + fixed)",
    ),
    Member(
        mid="W2",
        title="Wave-refactor — flow-v2 HONEST CLOSURE (all waves wired+fires+attested, not module+AT-green)",
        tier="WAVE-REFACTOR",
        predicate=_flow_v2_honestly_closed,
        done_signature="flow-v2-wave-migrations honestly closed — COMPUTED: every flow-v2 feature carries a FeatureEnd seal (delegates to flow_v2_closure_scorecard.FEATURES, the flow-v2 SSOT; non-gameable code-signature, was a hand-editable RESUME.md prose-grep refuted by the adversarial swarm 2026-06-29 + fixed; resolves the two-scorecard contradiction)",
    ),
    # ---- SLOW-AT CONSOLIDATION: a 2-phase plan (Ale 2026-06-26) --------------
    # Phase 1 = the producer+guard (migration-plan-1): subprocess-e2e reserved for
    # @walking_skeleton, every other AT defaults to the in-process port (6 levels,
    # enforced levers) -- "we improved the agent/workflow". Phase 2 = MIGRATE THE
    # EXISTING corpus (migration-plan-2-test-corpus): convert the 140 non-WS
    # acceptance tests that fork a subprocess to in-process -- "consolidate the
    # existing SLOW ATs". Phase 2 is gated on Phase 1 and was NOT started.
    #
    # P1 (Phase 1, at-in-process-port-default): 4/4 slices attested (3
    # SliceCommitVerified + 1 SliceProseDelivered, 90df3830c) -- the agent/
    # workflow improvement Ale considers done -- but the feature-end seal is
    # REFUSED by the full-suite-green precondition (the same pre-existing
    # oss_feature_end_emit_cli reds that block W2, ZERO from slice-04). DONE iff a
    # REAL feature-end seal -> shows OPEN-pending-seal (honest, seal not delivery).
    Member(
        mid="P1",
        title="Slow-AT consolidation PHASE 1 — in-process-port producer+guard (at-in-process-port-default): the agent/workflow improvement",
        tier="SLOW-AT",
        predicate=lambda: _sealed_and_reconciled("at-in-process-port-default"),
        done_signature="at-in-process-port-default feature-end-SEALED (EBatchRefactorCompleted + FeatureEndReviewVerdict in the ledger); 4/4 slices attested (90df3830c); the full-suite-green precondition was CLEARED (the pre-existing oss_feature_end_emit_cli reds fixed via e754b4d6c) -> seal proceeded -> DONE (predicate: _sealed_and_reconciled = feature-end record + verify-integrity-clean)",
    ),
    # P2 (Phase 2, migration-plan-2-test-corpus): the actual corpus migration of
    # the EXISTING slow ATs -- 140 non-@walking_skeleton acceptance tests that
    # fork sys.executable (381 spawn-sites total, 120/140 concentrated in
    # tests/des/acceptance). Status in the plan: "documento -- gated su Piano 1
    # DONE", F-id F-TEST-CORPUS-MIGRATION-IN-PROCESS to OPEN. NOT started ->
    # honestly OPEN. This is the phase Ale flagged as missing-from-the-epic.
    Member(
        mid="P2",
        title="Slow-AT consolidation PHASE 2 — migrate the EXISTING slow AT corpus to in-process (F-TEST-CORPUS-MIGRATION-IN-PROCESS): the 140 non-WS forking acceptance tests",
        tier="SLOW-AT",
        predicate=_corpus_migration_done,
        done_signature="the existing slow AT corpus migrated to in-process: PHASE-2 DONE iff the project classifier (at_corpus_migration_scorecard) reports ZERO pure non-WS interpreter-forks. NOT done as of 2026-06-30: the classifier reports 26 migrable spawn-sites remaining (19 pure + 3 mixed files). The seal + Model-B reconciliation (slice-02/03 RECONCILED-OUT) was a GAMEABLE proxy -- the adversarial swarm 2026-06-30 caught it as theater (the seal/reconcile predicate never inspected the actual corpus). Predicate hardened to delegate to the real migration measure.",
    ),
)


def _evaluate() -> list[tuple[Member, bool]]:
    rows: list[tuple[Member, bool]] = []
    for m in _MEMBERS:
        try:
            done = bool(m.predicate())
        except Exception:  # fail-closed: an erroring predicate is NOT DONE
            done = False
        rows.append((m, done))
    return rows


def _render_text(rows: list[tuple[Member, bool]]) -> str:
    done_n = sum(1 for _, d in rows if d)
    total = len(rows)
    pct = round(100 * done_n / total) if total else 0
    hard = [(m, d) for m, d in rows if m.tier == "HARD"]
    hard_done = sum(1 for _, d in hard if d)
    lines = [
        "=" * 80,
        "consolidation-for-wider-beta-testing -- GOAL CONTRACT (FIRST-CUT)",
        "  A member is DONE iff its deterministic committed-source predicate holds.",
        "  Predicates are SHALLOW structural proofs (fix-signature + regression AT);",
        "  the DEEP proof is the member's AT GREEN under the full suite (run separately).",
        "  WIDER-BETA GATE = all HARD members done + full-suite-green + adversarial-clean.",
        "=" * 80,
        f"  {'MEMBER':<5} {'TIER':<9} {'STATUS':<6} TITLE",
        "-" * 80,
    ]
    for m, d in rows:
        lines.append(f"  {m.mid:<5} {m.tier:<9} {'DONE' if d else 'OPEN':<6} {m.title}")
        lines.append(f"        signature: {m.done_signature}")
    lines.append("-" * 80)
    lines.append(
        f"  HARD blockers: {hard_done}/{len(hard)} done (ALL required for wider beta)"
    )
    lines.append(f"  EPIC MEMBERS:  {done_n}/{total} DONE = {pct}%")
    lines.append("  PRECONDITION full-suite-green + adversarial-clean: run separately")
    lines.append("=" * 80)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()
    rows = _evaluate()
    done_n = sum(1 for _, d in rows if d)
    total = len(rows)
    hard_open = sum(1 for m, d in rows if m.tier == "HARD" and not d)
    if args.json:
        print(
            json.dumps(
                {
                    "epic": "consolidation-for-wider-beta-testing",
                    "bar": "first-cut (Ale-ratify)",
                    "members_done": done_n,
                    "members_total": total,
                    "hard_blockers_open": hard_open,
                    "members": [
                        {
                            "id": m.mid,
                            "tier": m.tier,
                            "title": m.title,
                            "done": d,
                            "done_signature": m.done_signature,
                        }
                        for m, d in rows
                    ],
                }
            )
        )
    else:
        print(_render_text(rows))
    # Exit 0 = all HARD blockers done (wider-beta member-gate); 1 = HARD work remains.
    return 0 if hard_open == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
