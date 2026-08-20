"""des CLI dispatcher — single entry point for the nWave runtime.

Implements DDD-1..DDD-11 of fix-des-single-entry-point-consolidation feature.

The dispatcher is a pure-function fan-out over the subcommand registry.
Each row maps
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
import inspect
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class _SubcommandRow:
    """One public CLI command. This tuple is the single command registry."""

    name: str
    module_path: str
    function_name: str


# The subcommand registry is the dispatcher's single source of truth.
_REGISTRY: tuple[_SubcommandRow, ...] = (
    _SubcommandRow("health-check", "des.cli.health_check", "main"),
    # `des.cli.commit` (the `des-commit` entry point) was reachable only as a
    # legacy standalone script, never as `des commit` -- the same
    # implemented-not-wired class the anti-orphan guard below catches. It is a
    # real subcommand: it serialises the commit critical section under an
    # exclusive flock and builds the commit from a TEMPORARY index seeded with
    # HEAD plus only the owned paths, so a concurrent agent's staged work cannot
    # be swept in. That is the mitigation the shared-tree work-loss RCA asks for
    # (F-SHARED-TREE-EATS-UNCOMMITTED-WORK), so it must be reachable by name.
    _SubcommandRow(
        "commit",
        "des.cli.commit",
        "main",
    ),
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
    # The test runner is the executable boundary used by the thin delivery
    # contract.  Historical design-diff and self-attestation commands were
    # retired: acceptance obligations and independent observations carry the
    # quality evidence without a second mutable closure protocol.
    _SubcommandRow("verify-test-runner", "des.cli.run_tests", "main"),
    # Thin DeliveryContract handoff: validates one explicit locator and emits
    # only its immutable identity headers.
    _SubcommandRow("dispatch", "des.cli.dispatch", "main"),
    # ADR-SSOT-002 Section 4b: the read-only point-of-use projection of the
    # Discover/Resolve charter-namespace algebra over a raw --delivery-id
    # argv fact -- lets a producer route SKIP/AUTHOR/REUSE/BLOCK before
    # dispatch, without duplicating filesystem inference.
    _SubcommandRow("resolve-charters", "des.cli.resolve_charters", "main"),
    # ADR-SSOT-002 Section 4d: the point-of-use `PrepareOrdinaryRequest`
    # producer -- computes `SeededAuthority` for an ordinary Auto M/L request
    # and emits the exact fourteen-line Auto-root ATD dispatch body. Writes
    # no file; the dispatched acceptance designer still authors the one
    # DeliveryContract via `des dispatch`.
    _SubcommandRow(
        "prepare-ordinary-request", "des.cli.prepare_ordinary_request", "main"
    ),
    # Stable-design report 2026-08-19 §1.2: bounded producer of the
    # REVISE-CONTRACT/REVISE-ROUND/CITATION dispatch body -- refuses once a
    # DeliveryId's revision round would exceed the declared bound instead
    # of an unbounded ATD redispatch loop (Run 11's own incident: 4
    # sequential revisions on one DeliveryId). Writes only its own durable
    # per-DeliveryId round counter under `.nwave/des/revise-rounds/`.
    _SubcommandRow("revise-contract-round", "des.cli.revise_contract_round", "main"),
    # Produces one expectation charter in the DeliveryContract's delivery-id
    # namespace. Idempotent and loud on malformed ids or path ambiguity.
    _SubcommandRow("charter-scaffold", "des.cli.charter_scaffold", "main"),
    # blast-radius-measured-tier slice-01 (GDP-1/5): the PRODUCING tool for the
    # measured S/M/L change-tier -- real files/lines measures over --paths,
    # boundary/consumer honestly not-yet-wired in slice-01 (explicit reasons
    # entry, never fabricated zeros).
    _SubcommandRow("blast-radius", "des.cli.blast_radius", "main"),
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
    # Public vendor-neutral code-analysis projection.
    _SubcommandRow("code-fact", "des.cli.code_fact", "main"),
    _SubcommandRow(
        "validate-delivery-contract",
        "des.cli.validate_delivery_contract",
        "main",
    ),
    # parallel-work-cleans-up-after-merge-back slice-01 (D-2/D-3,
    # ADR-SWARM-002): the mechanical worktree-cleanup gate. ACT-by-default,
    # ties `git worktree remove` to a CONFIRMED merge-back (state-based via
    # `is_ancestor`); `--check-only` is the DONE-check backstop.
    _SubcommandRow(
        "verify-worktree-cleanup", "des.cli.verify_worktree_cleanup", "main"
    ),
    # sentinel-tool (nw-throughput SKILL.md "Throughput Sentinel"): the
    # versioned worktree-triage receipt, promoted from an unversioned
    # scratchpad script that produced three wrong readings in one afternoon
    # (each costing real work -- absence-from-silence liveness, no
    # declared-ownership axis, a name-normalization bug that made the fix
    # for the second defect unable to fire). Advisory only (GDP-6): never
    # removes, merges, dispatches, or authorizes -- reuses the existing
    # `sweep_worktrees`/`triage_worktree` production predicate for the
    # PID/lock/dirty/unmerged evidence and adds the two missing axes
    # (declared ownership, recent HEAD/index activity) on top.
    _SubcommandRow("sentinel", "des.cli.worktree_sentinel", "main"),
    # ADR-SSOT-002 Section 4/4b item 1: the point-of-use skeleton COMPILER --
    # mechanically derives targets/verification-scope/obligations from one
    # architecture brief's own citations, the same resolvers `des dispatch`'s
    # validators already use in CHECK mode, run here in GENERATE mode.
    # Semantic fields ATD alone can author land as the literal `<ATD: fill>`
    # placeholder (`des.domain.contract_placeholder_resolver`), which `des
    # dispatch`/`des validate-delivery-contract` both refuse until filled.
    _SubcommandRow("compile-contract", "des.cli.compile_contract", "main"),
    # Ale's construction-over-file correction (2026-08-20): the constructor
    # ATD calls, one value per call (--target/--field/stdin), to fill the
    # skeleton's own semantic placeholders in place. Sole writer of the
    # contract file after compile-contract; a mechanical field has no
    # --field choice naming it at all -- untouchable by construction.
    _SubcommandRow("fill-contract", "des.cli.fill_contract", "main"),
    # fix-shipped-regression-file-backfill: the historical regression-gap
    # backfill producer -- attests a SHIPPED slice's regression file
    # genuinely existed and passed at a real historical commit, recording a
    # RegressionFileHistoricalBackfill ledger record
    # `_shipped_and_entering_regression_files` reads back as its second
    # resolution tier.
    # des-saturated-scheduler slice-01 (DD-D1): the plan-only "what can run
    # now" query -- an artifact-level lane DAG, the READY cloud lanes, the one
    # ordered box lane, and blockers naming artifact + condition + action. It
    # never starts a process or agent; DD-D6's coherence check verifies the
    # projections against the one typed scheduling policy.
)


def _describe(row: _SubcommandRow) -> str:
    """Derive a one-line description for ``row`` from its module docstring.

    Reuses each subcommand module's own docstring first line as the
    canonical description (SSOT-safe: the description cannot drift out of
    sync with the module's real behavior the way a hand-duplicated string
    could). Only called when building the top-level ``des --help`` listing
    (see ``with_descriptions`` in ``_build_parser``) — never on normal
    subcommand dispatch, so this import cost is paid only for ``--help``
    invocations, not for every ``des`` call.

    Falls back to the bare subcommand name (today's behavior) if the module
    fails to import or carries no docstring — a broken/optional module must
    not take down the top-level ``--help`` listing for every OTHER
    subcommand.
    """
    try:
        module = importlib.import_module(row.module_path)
    except Exception:
        return row.name
    doc = inspect.getdoc(module)
    if not doc:
        return row.name
    first_line = doc.strip().splitlines()[0].strip()
    return first_line or row.name


def _build_parser(*, with_descriptions: bool = False) -> argparse.ArgumentParser:
    """Build the top-level parser with one subparser per registry row.

    Subparsers are registered with ``add_help=False`` so per-subcommand
    ``--help`` flows to the underlying module's argparse instead of being
    intercepted here (DDD-5). The dispatcher's own ``--help`` lists every
    registered subcommand name (DDD-4) together with a real one-line
    description (derived from the module docstring, see ``_describe``) when
    ``with_descriptions=True`` — the top-level-``--help``-only path. Normal
    subcommand dispatch builds with ``with_descriptions=False`` (the
    default) so it never pays the per-module import cost for a help string
    nobody renders on that invocation.
    """
    parser = argparse.ArgumentParser(
        prog="des",
        description="nWave deterministic execution system — single CLI entry point.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    for row in _REGISTRY:
        help_text = _describe(row) if with_descriptions else row.name
        subparsers.add_parser(row.name, add_help=False, help=help_text)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Dispatcher entry point — parse subcommand, delegate, passthrough exit.

    Parses the first positional argument as the subcommand name, resolves
    its registry row, lazily imports the module, and delegates the
    remaining ``argv`` to that module's ``main`` function. The subcommand's
    return value becomes this process's exit code unchanged (DDD-6).

    The top-level parser is built with real per-subcommand descriptions
    only when this invocation IS the top-level ``des --help``/``-h`` (no
    subcommand token consumed yet) — every other invocation (including
    ``des <sub> --help``, forwarded to the subcommand's own argparse
    unconsumed per DDD-5) builds the cheap, import-free parser.
    """
    raw_argv = sys.argv[1:] if argv is None else argv
    wants_top_level_help = bool(raw_argv) and raw_argv[0] in ("-h", "--help")
    parser = _build_parser(with_descriptions=wants_top_level_help)
    parsed, remaining = parser.parse_known_args(raw_argv)
    row = next(r for r in _REGISTRY if r.name == parsed.subcommand)
    module = importlib.import_module(row.module_path)
    subcommand_main = getattr(module, row.function_name)
    exit_code: int = subcommand_main(remaining)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
