"""des CLI dispatcher — single entry point for the nWave runtime.

Implements DDD-1..DDD-11 of fix-des-single-entry-point-consolidation feature.

The dispatcher is a pure-function fan-out over the subcommand registry
(_REGISTRY below — the same SSOT mirrored in tests/des/acceptance/
single_entry_point/steps/domain_types.py:SUBCOMMAND_TABLE). Each row maps
the operator-visible kebab-case name to its importable module path. argparse
discovers subcommands from the registry; ``des --help`` advertises every
name without per-subcommand prose duplication (each module owns its own
help via per-subcommand ``des <sub> --help``).

Stdlib-only at import time (bundle-scan compliant per DDD-2). Subcommand
modules load via ``importlib.import_module`` only on dispatch — startup
cost stays constant regardless of registry size.

Exit-code passthrough is verbatim (DDD-6): whatever ``<sub>.main(argv[2:])``
returns becomes this process's exit code.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class _SubcommandRow:
    """One row of the dispatcher's subcommand registry."""

    name: str
    module_path: str
    function_name: str


# The subcommand registry — SSOT for the dispatcher. Mirrors
# tests/des/acceptance/single_entry_point/steps/domain_types.py SUBCOMMAND_TABLE
# (the executable test mirror). Filesystem-grounded against src/des/cli/*.py
# (excluding __init__.py and __main__.py) as of 2026-05-23.
_REGISTRY: tuple[_SubcommandRow, ...] = (
    _SubcommandRow("log-phase", "des.cli.log_phase", "main"),
    _SubcommandRow("init-log", "des.cli.init_log", "main"),
    _SubcommandRow("verify-integrity", "des.cli.verify_deliver_integrity", "main"),
    _SubcommandRow("roadmap", "des.cli.roadmap", "main"),
    _SubcommandRow("health-check", "des.cli.health_check", "main"),
    _SubcommandRow("verify-commit-trailers", "des.cli.verify_commit_trailers", "main"),
    _SubcommandRow(
        "verify-slice-commit",
        "des.cli.verify_slice_commit_completeness",
        "main",
    ),
    _SubcommandRow("walking-skeleton-gate", "des.cli.walking_skeleton_gate", "main"),
    _SubcommandRow(
        "walking-skeleton-done-gate",
        "des.cli.walking_skeleton_done_gate",
        "main",
    ),
    _SubcommandRow("carpaccio-slice-gate", "des.cli.carpaccio_slice_gate", "main"),
    _SubcommandRow("classify-features", "des.cli.classify_features", "main"),
    _SubcommandRow("convert-to-atdd-pure", "des.cli.convert_to_atdd_pure", "main"),
    _SubcommandRow("reverify-slice-commit", "des.cli.reverify_slice_commit", "main"),
    _SubcommandRow(
        "verify-environmental-e2e",
        "des.cli.verify_environmental_e2e",
        "main",
    ),
    _SubcommandRow("run-contract-gate", "des.cli.run_contract_gate", "main"),
    _SubcommandRow("commit-slice", "des.cli.commit_slice", "main"),
    _SubcommandRow("emit-feature-end", "des.cli.emit_feature_end", "main"),
    _SubcommandRow("feature-end", "des.cli.feature_end", "main"),
    _SubcommandRow(
        "check-slice-at-completeness",
        "des.cli.check_slice_at_completeness",
        "main",
    ),
    _SubcommandRow("doctor", "des.cli.doctor", "main"),
    _SubcommandRow(
        "verify-readiness-pre-dispatch",
        "des.cli.verify_readiness_pre_dispatch",
        "main",
    ),
    # f-nonbypassable-attestation slice-05 (DDD-8/9): the PRODUCTION RUNTIME
    # wave-dispatch guard gate -- a thin CLI over wave_dispatch_guard_policy,
    # composed onto dispatch.pre (atdd_pure.yaml) so a wave-owner dispatched
    # off-spine is BLOCKED (warn+ask), never silently allowed.
    _SubcommandRow(
        "verify-wave-dispatch",
        "des.cli.verify_wave_dispatch",
        "main",
    ),
    _SubcommandRow(
        "verify-slice-ledger-evidence",
        "des.cli.verify_slice_ledger_evidence",
        "main",
    ),
    _SubcommandRow(
        "validate-feature-delta",
        "des.cli.validate_feature_delta",
        "main",
    ),
    # feature-delta-section-schema (ADR-FLOW-007): the typed section-schema
    # algebra + 3 pure projections (gate-verify / wave-injection / output-
    # contract) realized as a `des` subcommand. RED scaffold authored by DISTILL.
    _SubcommandRow(
        "feature-delta-schema",
        "des.cli.feature_delta_schema",
        "main",
    ),
    # feature-delta-doctor-and-ssot slice-01 (WS-2 / M2, FR-11 root fix): the
    # one-pass structural gap aggregator over a feature-delta.md -- composes
    # the existing validate_feature_delta validators in ONE invocation so a
    # contributor sees every gap at once instead of one gate rejection at a
    # time. Filesystem-only (no git dependency).
    _SubcommandRow(
        "feature-delta-doctor",
        "des.cli.feature_delta_doctor",
        "main",
    ),
    # fix-flavor-scaffold-producing-tool slice-01 (GDP-4/5): the PRODUCING
    # tool for the mode 4-tuple -- emits a structurally-complete flavor YAML
    # skeleton (nWave/flavors/_schema.yaml's 9 required fields) so
    # mode-registry-completeness's HOW routes to a producing tool instead of
    # a manual hand-assembled edit.
    _SubcommandRow(
        "flavor-scaffold",
        "des.cli.flavor_scaffold",
        "main",
    ),
    _SubcommandRow(
        "record-discuss-review",
        "des.cli.discuss_review_verdict",
        "main",
    ),
    # f-declarative-gate-composition (OB-2): the DISCUSS PO-review CONSUMER veto
    # promoted to its own catalog gate_id so the declarative DISCUSS gate-out
    # stack is the readable 2-row list [validate-feature-delta,
    # verify-discuss-review]. Thin wrapper over DiscussReviewGate.evaluate.
    _SubcommandRow(
        "verify-discuss-review",
        "des.cli.verify_discuss_review",
        "main",
    ),
    _SubcommandRow(
        "record-at-review-verdict",
        "des.cli.at_review_verdict",
        "main",
    ),
    # mode-registry-single-locus slice-05: the two new mechanical guardrails
    # (Layer A + Layer B) that make the next mode shotgun-surgery structurally
    # impossible. Both are reachable as `des <gate-id>` subcommands and mirrored
    # 1:1 in nWave/gates/_catalog.yaml (+ per-gate files).
    # evolution-plan P0.1 (evidence-by-execution): the fresh-clone gate --
    # executes the target project's declared demo recipe in a fresh export of
    # the COMMITTED tree, so "works only on my machine / broken on fresh
    # clone" (the eval'd repo's npm-ci failure class) cannot reach done.
    _SubcommandRow("verify-fresh-clone", "des.cli.verify_fresh_clone", "main"),
    # evolution-plan P0.2: the RED->GREEN non-vacuity seal -- an AT that
    # passes without the implementation (never-red) cannot count as coverage;
    # a test edited between RED and GREEN voids its own evidence.
    _SubcommandRow("verify-red-green", "des.cli.verify_red_green", "main"),
    # evolution-plan P0.3: the negative-AT mandate -- a critical scope with
    # presence-only ATs is refused (weak assertions die to negative ATs).
    _SubcommandRow("verify-negative-at", "des.cli.verify_negative_at", "main"),
    # evolution-plan P1.3: the signal-driven refactor trigger -- detector
    # findings on the slice diff (incl. the SSOT-violation classes) ARE the
    # refactor's expectations; zero findings = no refactor pass runs; the
    # verdict declares which analysis arm ran (never a silent nobody-looked).
    _SubcommandRow(
        "verify-refactor-trigger",
        "des.cli.verify_refactor_trigger",
        "main",
    ),
    # evolution-plan P0.5: doc<->code coherence -- shipped docs claiming
    # absent scripts/files/modules are refused (docs cannot overstate code).
    _SubcommandRow(
        "verify-doc-coherence",
        "des.cli.verify_doc_coherence",
        "main",
    ),
    # evolution-plan P0.4: execution-reach -- a production file with ZERO
    # executions across the feature's verification cannot ship (binary
    # predicate over Cobertura XML, runner-agnostic; the never-run class).
    _SubcommandRow(
        "verify-execution-reach",
        "des.cli.verify_execution_reach",
        "main",
    ),
    # evolution-plan P3.2: the spec-coverage gate at DISTILL-exit -- every
    # requirement checklist row must be covered by >=1 AT (marker-discriminated),
    # or it is a visible red row; the six mandatory categories are called out;
    # missing/malformed checklist degrades LOUD (the eval's silent-absence class).
    _SubcommandRow(
        "verify-spec-coverage",
        "des.cli.verify_spec_coverage",
        "main",
    ),
    # evolution-plan P2.1/P1.2: the User-Examiner ("Vera") verdict PRODUCER --
    # appends a tamper-evident ExamineVerdict (charter-sealed) to the per-feature
    # examine ledger; the commit-slice examine gate is the consumer. This is the
    # execution-observation replacement for the code-reading C_REVIEWER_AUDIT.
    _SubcommandRow(
        "record-examine-verdict",
        "des.cli.record_examine_verdict",
        "main",
    ),
    _SubcommandRow("mode-locus-gate", "des.cli.mode_locus_gate", "main"),
    _SubcommandRow(
        "mode-registry-completeness",
        "des.cli.mode_registry_completeness",
        "main",
    ),
    # skill-normative-content-gate slice-01 (M-1 dormant-seam guard): the
    # maintainer-facing gate reached through the real `des` dispatcher.
    _SubcommandRow(
        "skill-normative-gate",
        "des.cli.skill_normative_gate",
        "main",
    ),
    # fix-wave-bypass-recovery-truthful slice-02: the sanctioned operator command
    # for clearing a stale wave-active floor (reuses WaveActiveWriter.clear via
    # WaveActivationService.clear_floor -- the floor's first CLI consumer, D11).
    _SubcommandRow("wave-clear", "des.cli.wave_clear", "main"),
    # f-coherence-and-attestation slice-06 (the gate-stack WIRING slice, JOB-028):
    # the three already-built feature modules are CONNECTED into the dispatcher so a
    # maintainer can REACH them and the closure scorecard sees the feature WIRED
    # (closing `catalogato ≠ cablato`). Each row is a THIN CLI driver over the
    # EXISTING slice-03/04/05 logic -- no domain re-implementation:
    #   gate-design-at-coherence -> des.cli.gate_g.main over evaluate_gate_g
    #                         (slice-03). f-code-design-manifest-and-gate-g slice-04
    #                         RENAMED the subcommand gate-g -> gate-design-at-coherence
    #                         (DDD-5: a GENERAL design<->AT coherence gate after the
    #                         slice-03 generalization, so the descriptive id). The
    #                         MODULE des.cli.gate_g is unchanged.
    #   self-attest        -> des.cli.self_attest.main over self_attest.classify
    #                         (slice-04, a new thin wrapper over the pure domain).
    #   verify-test-runner -> the EXISTING des.cli.run_tests.main (slice-05); only
    #                         the registry row + catalog mirror are net-new.
    _SubcommandRow("gate-design-at-coherence", "des.cli.gate_g", "main"),
    _SubcommandRow("self-attest", "des.cli.self_attest", "main"),
    _SubcommandRow("verify-test-runner", "des.cli.run_tests", "main"),
    # f-spine-runs-tests-not-git-hooks slice-01 (THE ACCELERATION, DDD-1/AT-A1):
    # the slice-scoped EXECUTOR that genuinely RUNS only the entering slice's
    # acceptance tests at commit (a real execution, not a collect-only walk) and
    # vetoes on a RED slice AT -- the commit-time test authority that supersedes
    # the whole-tree run-contract-gate per slice. Wiring this row is what makes
    # `run_slice_ats` reachable (no longer dead code).
    _SubcommandRow("run-slice-ats", "des.cli.run_slice_ats", "main"),
    # f-wave-contract-coherence slice-02: the git-free wave-contract coherence
    # gate -- verifies wave prose carries valid gates-ref/outputs-ref pointers,
    # restates nothing inline, and the referenced wave resolves in both SSOTs
    # (gate_stack + output_contract) with every gate_id resolving to the catalog.
    # Reuses the TextSearch-floor lexical scan (stdlib re) + the catalog gate_id
    # set; degrades LOUD to INDETERMINATE on an unreadable registry (ADR-FLOW-006
    # D7/D9 -- the five existing verdicts, no sixth).
    _SubcommandRow(
        "verify-wave-contract-coherence",
        "des.cli.verify_wave_contract_coherence",
        "main",
    ),
    # f-design-devops-review-gate slice-01: the per-wave review-verdict gate
    # carried to DESIGN (DISCUSS parity). record-design-review is the PRODUCER
    # (writes BOTH approved + needs-revision, O-4); verify-design-review is the
    # CONSUMER veto wired into nWave/waves/design.yaml gate-out. Both are thin
    # wrappers over the wave-parametric ReviewVerdictGate core (no new verdict
    # logic), mirroring the DISCUSS record/verify pair.
    _SubcommandRow(
        "record-design-review",
        "des.cli.design_review_verdict",
        "main",
    ),
    _SubcommandRow(
        "verify-design-review",
        "des.cli.verify_design_review",
        "main",
    ),
    # f-design-devops-review-gate slice-02: the SAME pair carried to DEVOPS
    # (the SSOT-reuse proof). record-devops-review is the PRODUCER (O-4 both
    # outcomes); verify-devops-review is the CONSUMER veto wired into
    # nWave/waves/devops.yaml gate-out. Both are thin wrappers over the SAME
    # wave-parametric ReviewVerdictGate core -- zero new verdict logic, only
    # the wave name changes.
    _SubcommandRow(
        "record-devops-review",
        "des.cli.devops_review_verdict",
        "main",
    ),
    _SubcommandRow(
        "verify-devops-review",
        "des.cli.verify_devops_review",
        "main",
    ),
    # f-deliver-entry-contract-freeze slice-01 (ADR-FLOW-004, DDD-1): the
    # DELIVER-entry contract-freeze gate. At the first DELIVER gate-IN it asserts
    # the contract is STRUCTURALLY complete (locked [REF] sections present + valid
    # Slice Plan + an authored AT module per planned slice) and writes ONE
    # ContractFrozen ledger record on PASS. Composes the EXISTING
    # validate_feature_delta checks in-process + the feature_tag_files AT-module
    # resolution; emits a §17 GateVerdict (PASS/FAIL/INDETERMINATE -- the five
    # existing verdicts, no sixth, no engine).
    _SubcommandRow(
        "verify-deliver-entry-contract",
        "des.cli.verify_deliver_entry_contract",
        "main",
    ),
    # f-attest-bundled-slice slice-01 (ADR-ABS-001): the sanctioned
    # bundle-delivered-slice attestation command, a SCAFFOLD reachable through
    # the real dispatcher. Built on reverify's SHARED precondition/gate/record
    # core (des.cli._reverify_core, extracted this slice from
    # reverify_slice_commit) -- no parallel attestation path. --reason is
    # MANDATORY (argparse required=True, the wave-clear precedent) so a missing
    # reason is the genuine usage error demanding a human GO. The A2 flow
    # (preconditions, gate composition, ledger record) lands in slices 02-04.
    _SubcommandRow(
        "attest-bundled-slice",
        "des.cli.attest_bundled_slice",
        "main",
    ),
    # des-dispatch-ssot-renderer Fase-2 (the GENERATOR): renders a gate-valid
    # atdd_pure dispatch prompt from nWave/dispatch/atdd_pure.yaml + vendors.yaml
    # + LANE_PROFILES, so the generator and AtddPurePromptValidator share ONE
    # source and cannot silently diverge.
    _SubcommandRow("dispatch", "des.cli.dispatch", "main"),
    # verify-catalog-coherence slice-01 (GDP-1/3/6): the FAST (<1s) explicit/
    # CI/feature-end check that this registry, nWave/gates/_catalog.yaml, and
    # the per-gate .yaml files stay 1:1 -- the same drift the build-tier
    # catalog suite catches only in a full run.
    _SubcommandRow(
        "verify-catalog-coherence",
        "des.cli.verify_catalog_coherence",
        "main",
    ),
    # check-contract-shape-declarations slice-01 (GDP-4/6): the PRODUCING tool
    # for Principle 11's three mechanical Contract-Shape checks (CONTRACT_SHAPE
    # docstring / acceptance Outcome-anchor / banned-regex name) over an
    # explicit caller-scoped --files list, git-free, stdlib-only.
    _SubcommandRow(
        "check-contract-shape",
        "des.cli.check_contract_shape_declarations",
        "main",
    ),
    # charter-scaffold slice-01 (GDP-1/5): the PRODUCING tool for expectation-
    # charter scaffolds -- generates a charter per OBSERVABLE Slice Plan row
    # (Intent pre-filled from the Value statement verbatim), idempotent,
    # degrade-LOUD on a missing/malformed feature-delta or absent Slice Plan.
    _SubcommandRow("charter-scaffold", "des.cli.charter_scaffold", "main"),
    # fix-record-review-verdict-ledger slice-01 (#45, WS-6): the general
    # reviewer-verdict PRODUCER -- ad-hoc reviewers (nw-agent-builder-reviewer
    # and other non-wave reviewers) had NO ledger, so a reviewer dying before
    # its final message lost the verdict with no recovery path. Mirrors
    # record-examine-verdict's ledger shape + at-review-verdict's reviewer/
    # slice/verdict fields.
    _SubcommandRow(
        "record-review-verdict",
        "des.cli.record_review_verdict",
        "main",
    ),
    # charter-scaffold slice-02 (the ENFORCEMENT half): the backstop gate that
    # verifies a scaffolded charter is genuinely FILLED (oracle with >=1
    # negative observation, real start recipe, no residual placeholders)
    # before an operator trusts it or lets it arm a downstream EXAMINE.
    _SubcommandRow(
        "verify-charter-filled",
        "des.cli.verify_charter_filled",
        "main",
    ),
    # codefact-similar-responsibility slice-01 (WS-9b, the reuse-first keystone):
    # the observable CLI over the ADDITIVE query.similar-responsibility CodeFactPort
    # capability -- shows the ranked EXISTING module-level symbols whose structural
    # fingerprint (name-token Jaccard + arity) overlaps a proposed new symbol, so an
    # operator sees the duplicate candidate {file:line} before writing a parallel
    # implementation. Advisory (always exits 0); degrades LOUD (absent) on an
    # unparseable/empty scope, never a fabricated empty candidate list.
    _SubcommandRow(
        "find-similar-responsibility",
        "des.cli.find_similar_responsibility",
        "main",
    ),
    # des-next-loop-projection slice-01 (F-56 generalization): read-only
    # advisory projection of the next legal atdd_pure DELIVER-loop step --
    # composes the Slice Plan + AT-completion ledger + phase order + gate/
    # wave registries, never a persisted loop-state snapshot (M1, no
    # sequencer/engine).
    _SubcommandRow(
        "next",
        "des.cli.next_step",
        "main",
    ),
    # examinable-gate-surface slice-01 (GDP-5): the PRODUCING tool for an
    # examiner-drivable certification-gate fixture -- builds a real repo with
    # a genuinely SHIPPED+attested slice, an entering slice, and a
    # deliberately-red work-ahead slice, each flippable red/green by editing
    # one line, so a source-blind examiner can reach and break the REAL
    # `des verify-slice-commit` gate without ever reading the gate's source.
    _SubcommandRow(
        "examine-fixture",
        "des.cli.examine_fixture",
        "main",
    ),
    # des-refactor-fixer-swarm slice-01 (ADR-SWARM-001): the fixer-harness CLI.
    # RED scaffold wiring authored by DISTILL -- `des.cli.refactor.main` raises
    # AssertionError (the drain loop is not yet implemented), so this row makes
    # the failure "drain not implemented" (MISSING_FUNCTIONALITY), never an
    # argparse `invalid choice` usage error, for the slice-01 walking-skeleton.
    _SubcommandRow("refactor", "des.cli.refactor", "main"),
)


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with one subparser per registry row.

    Subparsers are registered with ``add_help=False`` so per-subcommand
    ``--help`` flows to the underlying module's argparse instead of being
    intercepted here (DDD-5). The dispatcher's own ``--help`` lists every
    registered subcommand name (DDD-4).
    """
    parser = argparse.ArgumentParser(
        prog="des",
        description="nWave deterministic execution system — single CLI entry point.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    for row in _REGISTRY:
        subparsers.add_parser(row.name, add_help=False, help=row.name)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatcher entry point — parse subcommand, delegate, passthrough exit.

    Parses the first positional argument as the subcommand name, resolves
    its registry row, lazily imports the module, and delegates the
    remaining ``argv`` to that module's ``main`` function. The subcommand's
    return value becomes this process's exit code unchanged (DDD-6).
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    parser = _build_parser()
    parsed, remaining = parser.parse_known_args(raw_argv)
    row = next(r for r in _REGISTRY if r.name == parsed.subcommand)
    module = importlib.import_module(row.module_path)
    subcommand_main = getattr(module, row.function_name)
    exit_code: int = subcommand_main(remaining)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
