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
    # ADR-SSOT-002 Section 4b: the READ-ONLY projection of the owned state --
    # the exact Request, its ordered values, what each already carries, and the
    # canonical next step as DATA. It is the step an orchestrator invokes after
    # every terminal, and the base every other step is read against.
    _SubcommandRow("state", "des.cli.state", "main"),
    # The HUMAN layer of the same owned state (adr-ssot-document-model, "Feature
    # Brief -- The Human Layer"), rendered through the ONE nWave renderer. A
    # projection function and never a fourth store (ADR-BOARD-001): it writes
    # the page and nothing the delivery owns.
    _SubcommandRow("project", "des.cli.project", "main"),
    # ADR-SSOT-002 Section 4b: one Product Owner turn invoked ALONE. It records
    # the accepted decomposition as owned state and returns; it never converts
    # the role's local outcome into a verdict about the whole Request, which is
    # the defect measured at 06:21:39 in run 20260905T062139Z-38400.
    # F-DEVOPS-CONSTRAINTS-INTO-DISTILL: the OPTIONAL step upstream of `po`. It
    # writes operational CONSTRAINTS into a section of a tracked authority file
    # and proves the authority resolver can read them back, so the Product Owner
    # can decompose them into observable values. No NEXT line names it: a
    # project that deploys nothing is never handed this turn to refuse.
    _SubcommandRow("devops", "des.cli.devops", "main"),
    _SubcommandRow("evolution", "des.cli.evolution", "main"),
    _SubcommandRow("discuss", "des.cli.discuss", "main"),
    _SubcommandRow("distill", "des.cli.distill", "main"),
    _SubcommandRow("po", "des.cli.po", "main"),
    # ADR-SSOT-002 Section 4b: one architect turn for ONE value, invoked alone
    # and repeatable. A second call with `--finding -` carries the current typed
    # facts beside the finding and replaces them -- the correction the
    # orchestrator decides on, never an edge the software takes.
    _SubcommandRow("design", "des.cli.design", "main"),
    # ADR-SSOT-002 Section 4b: one value's oracle authored (or corrected),
    # MEASURED red, and independently judged -- one step, because between those
    # three the orchestrator has no move to make. A refusal carries the owner
    # the judge named as DATA and names both forms that could answer it.
    _SubcommandRow("oracle", "des.cli.oracle", "main"),
    # ADR-SSOT-002 Section 4b: one crafter turn for one value's batch. A refusing
    # turn's `blocked_by` word comes back as DATA on BLOCKED-BY -- the composed
    # run spends a window on the role it names, a lone step never does.
    _SubcommandRow("craft", "des.cli.craft", "main"),
    # The whole-Request candidate is built from its base and its declared native
    # evidence is captured once. Host-selected review and examination consume
    # the persisted observation separately. Nothing here moves a ref.
    _SubcommandRow("verify", "des.cli.verify", "main"),
    _SubcommandRow("prepare-role", "des.cli.prepare_role", "main"),
    _SubcommandRow("record-role-result", "des.cli.record_role_result", "main"),
    _SubcommandRow("invoke-role", "des.cli.invoke_role", "main"),
    # ADR-SSOT-002 Section 4b: the one compare-and-swap, the owned-index
    # reconciliation, and the closure of the graph. It buys no turn.
    _SubcommandRow("integrate", "des.cli.integrate", "main"),
    # ADR-SSOT-002 Section 4b: the first two invocable steps of the lane cycle
    # an orchestrator runs around the delivery steps -- opening a lane worktree
    # and integrating it back by fast-forward, then closing it. Both were hand-typed
    # Git before, and this repository's own standing instruction named two `des`
    # subcommands for them that the CLI does not carry.
    _SubcommandRow("lane", "des.cli.lane", "main"),
    # blast-radius-measured-tier slice-01 (GDP-1/5): the PRODUCING tool for the
    # measured S/M/L change-tier -- real files/lines measures over --paths,
    # boundary/consumer honestly not-yet-wired in slice-01 (explicit reasons
    # entry, never fabricated zeros).
    _SubcommandRow("blast-radius", "des.cli.blast_radius", "main"),
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
    # G2 slice 1 (ADR-AUM-001): the auto-update discovery+classification half
    # -- `des update --dry-run` reports every persisted artifact under
    # `.nwave/`, its declared version verbatim, kernel-readability, status
    # (InFlight/Completed/Indeterminate) and planned action
    # (Upcast/PreserveHistory/Indeterminate), writing nothing.
    _SubcommandRow("update", "des.cli.update", "main"),
    # The EXECUTABLE agreement crossing: run the declared producer for real,
    # carry the artifact it actually wrote to the ONE declared consumer, and
    # report that consumer's own exit code as acceptance. Nothing on this path
    # reads source, an import graph or a syntax tree, so a green verdict cannot
    # be produced by a crossing that carried nothing. This row is the whole
    # public surface of that value -- no second surface advertises it.
    _SubcommandRow("verify-agreement", "des.cli.verify_agreement", "main"),
)


#: The steps of one Request. Each may buy a role turn against a code tree the
#: operator selected implicitly, so each declares WHICH tree before it works --
#: the property the retired composed run carried and Section 11 sorts to the
#: model (see `des.cli._runtime_identity`). The read-only projections and the
#: analysis commands are excluded deliberately: they buy no turn, and hashing
#: the package on every `des code-fact` would charge ~60 ms to a query that
#: decides nothing.
_DECLARES_ITS_RUNTIME = frozenset(
    {"devops", "po", "design", "oracle", "craft", "verify", "integrate"}
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
    if row.name in _DECLARES_ITS_RUNTIME:
        # BEFORE the delegation, so a step killed before it reads its Request
        # still says which tree it was.
        from des.cli._runtime_identity import declare

        declare()
    module = importlib.import_module(row.module_path)
    subcommand_main = getattr(module, row.function_name)
    exit_code: int = subcommand_main(remaining)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
