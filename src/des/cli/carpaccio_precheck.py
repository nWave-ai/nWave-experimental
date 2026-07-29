"""Designer-facing carpaccio format PRE-CHECK -- read-only, collect-ALL (B).

A DISTILL author runs this BEFORE recording the AT-review verdict to learn every
format violation the mid-spine ``carpaccio-slice-gate`` would later raise -- in
ONE pass (collect-ALL), so the author fixes them all in a single round trip.

WHY-NEW-FILE: src/des/cli/carpaccio_precheck.py
  CLOSEST-EXISTING: src/des/cli/carpaccio_slice_gate.py
  EXTENSION-COST: the gate is the ENFORCING boundary (assertion-5 record-presence,
    exit 44/45, ledger read) with a frozen machine contract hooks/CI depend on;
    overloading it with an advisory ``--precheck`` mode muddies that contract.
  PARALLEL-RATIONALE: Principle 12 read/write driving-port split -- the advisory
    surface MUST NOT expose the enforcing path (no ledger write, no verdict
    record). It is a separate driving port with a different lifecycle (designer
    runs it pre-verdict, the gate runs mid-spine post-verdict). Both REUSE the
    SAME predicates from ``carpaccio_format`` (ADR-001 single-SSOT, NO second
    parser); only the orchestration differs (collect-ALL vs the gate's fail-fast).

Architecture (Ale 2026-05-24 nwave-dev topology): stdlib-only, FLAT under
``src/des/cli/``, glob-shipped. NO sequencer / NO engine coupling. Invoked
MODULE-DIRECT against the ``des.cli.carpaccio_precheck`` module, NOT as a ``des``
dispatcher subcommand -- the dispatcher ``_REGISTRY`` is parity-pinned to the gate
catalog (F-DES-AT-REVIEW-VERDICT-SUBCOMMAND-SURFACE defers the subcommand
ergonomics). Per the runtime-emit invariant (tests/regression/
test_no_module_form_in_runtime_emit.py) the ``python -m`` invocation form is NOT
spelled literally in this source.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING

from des.application.feature_at_files import (
    feature_tagged_test_files,
    is_pytest_collectible,
)
from des.cli.carpaccio_format import (
    GateError,
    Scenario,
    SlicePlan,
    SlicePlanRow,
    _config_slice_max,
    _feature_tag_files,
    _legacy_acceptance_dir,
    parse_scenarios,
    parse_slice_plan,
    read_feature_files,
)
from des.cli.human_surface import Verdict, print_human_summary
from des.domain.repo_path_resolver import (
    feature_delta_path as _feature_delta_path,
)
from des.domain.repo_path_resolver import (
    resolve_repo_root as _repo_root,
)


if TYPE_CHECKING:
    from pathlib import Path


def collect_violations(repo: Path, feature_id: str) -> list[str]:
    """Run every format predicate over the feature, collecting ALL violations.

    Collect-ALL (NOT fail-fast): the gate raises ``GateError`` on the first
    violation; the pre-check reports every violation in one pass so the author
    fixes them all before a single round trip. Returns an ordered list of
    human-readable diagnostic lines; empty when the feature is clean.
    """
    violations: list[str] = []
    violations.extend(_check_binding(repo, feature_id))
    violations.extend(_check_slice_plan_and_scenarios(repo, feature_id))
    return violations


def _check_binding(repo: Path, feature_id: str) -> list[str]:
    """Report when no AT module is bound to the feature (friction #1).

    AT-kind agnostic (agnostic-at-discovery-ssot-repair, gap 4): a Gherkin
    ``.feature`` file is one binding source; a head-comment-tagged pytest AT
    (``feature_tagged_test_files`` + ``is_pytest_collectible`` -- the SAME
    resolvers ADR-AAD-001 and gap 1 of this repair already trust) is another.
    A feature delivered exclusively via pytest must not be told to author a
    ``.feature`` file it was never designed to have.
    """
    if _feature_tag_files(repo, feature_id):
        return []
    if any(
        is_pytest_collectible(path)
        for path in feature_tagged_test_files(repo, feature_id)
    ):
        return []
    legacy_dir = _legacy_acceptance_dir(repo, feature_id)
    underscore_id = feature_id.replace("-", "_")
    return [
        f"no scenario file is bound to the feature {feature_id!r}: add the "
        f"file-level binding tag @feature-{feature_id} before the Feature: header "
        f"of at least one .feature file, or place it under the legacy directory "
        f"{legacy_dir}. Watch the hyphen-versus-underscore legacy directory: the "
        f"binding tag uses the hyphenated id (@feature-{feature_id}) while a "
        f"directory named {underscore_id!r} (underscore) is NOT auto-bound."
    ]


def _check_slice_plan_and_scenarios(repo: Path, feature_id: str) -> list[str]:
    """Report slice-plan + scenario format violations (ceiling, tags, escapes)."""
    scenarios = parse_scenarios(_read_precheck_feature_texts(repo, feature_id))
    try:
        plan = parse_slice_plan(_read_feature_delta(repo, feature_id))
    except GateError as plan_error:
        return [f"slice-plan: {plan_error.payload.get('error', plan_error)}"]
    violations: list[str] = []
    violations.extend(_check_tag_mismatch(plan, scenarios))
    violations.extend(_check_ceilings(repo, plan, scenarios))
    return violations


def _read_precheck_feature_texts(repo: Path, feature_id: str) -> list[str]:
    """Read the feature's ``.feature`` texts for collect-ALL format analysis.

    Collect-ALL discipline: a MISSING binding tag must not suppress the OTHER
    defect diagnostics (tag mismatch, over-ceiling). The gate's binding
    resolution (``read_feature_files``) only sees files that already carry the
    ``@feature-{id}`` tag or live under the legacy directory; an un-bound file
    would yield zero scenarios and silently hide its tag/ceiling defects. So when
    binding resolves no files, fall back to scanning the feature's conventional
    acceptance directories directly -- the format predicates still run on the
    authored content the author is fixing. Both paths feed the SAME
    ``carpaccio_format.parse_scenarios`` predicate (ADR-001, no second parser).
    """
    bound = read_feature_files(repo, feature_id)
    if bound:
        return bound
    return [
        path.read_text(encoding="utf-8", errors="replace")
        for path in _feature_scoped_feature_files(repo, feature_id)
    ]


def _feature_scoped_feature_files(repo: Path, feature_id: str) -> list[Path]:
    """Find ``.feature`` files under the feature's conventional acceptance dirs."""
    candidate_dirs = (
        repo / "tests" / "des" / "acceptance" / feature_id,
        _legacy_acceptance_dir(repo, feature_id),
    )
    matched: set[Path] = set()
    for directory in candidate_dirs:
        if directory.is_dir():
            # gherkin-scope: REPAIRED-as-one-arm (agnostic-at-discovery-ssot-
            # repair gap 4, ed2bb451c) -- ONE arm of the OR `_check_binding`
            # composes with the pytest arm.
            matched.update(directory.rglob("*.feature"))
    return sorted(matched)


def _read_feature_delta(repo: Path, feature_id: str) -> str:
    path = _feature_delta_path(repo, feature_id)
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _check_tag_mismatch(plan: SlicePlan, scenarios: list[Scenario]) -> list[str]:
    """Report scenarios whose @slice-NN tag has no matching slice-plan row."""
    plan_ids = {row.slice_id for row in plan.rows}
    violations: list[str] = []
    for tag in sorted({tag for s in scenarios for tag in s.slice_tags}):
        if tag not in plan_ids:
            violations.append(
                f"slice-tag mismatch: a scenario carries @{tag} with no matching "
                f"slice-plan row -- add a {tag} row to the slice plan or re-tag the "
                f"scenario"
            )
    return violations


def _check_ceilings(
    repo: Path, plan: SlicePlan, scenarios: list[Scenario]
) -> list[str]:
    """Report each over-ceiling slice + whether the coupled escape is satisfied."""
    slice_max = _config_slice_max(repo)
    violations: list[str] = []
    for row in plan.rows:
        members = [s for s in scenarios if row.slice_id in s.slice_tags]
        if len(members) <= slice_max:
            continue
        violations.append(_describe_over_ceiling(row, members, slice_max))
    return violations


def _describe_over_ceiling(
    row: SlicePlanRow, members: list[Scenario], slice_max: int
) -> str:
    """Describe an over-ceiling slice, naming the coupled-escape state."""
    at_count = len(members)
    all_coupled = bool(members) and all(s.has_coupled_tag for s in members)
    escape_satisfied = all_coupled and bool(row.justification)
    if escape_satisfied:
        return (
            f"slice {row.slice_id} has {at_count} ATs over the carpaccio ceiling of "
            f"{slice_max}, but the coupled escape is satisfied (every scenario "
            f"carries @coupled and the slice-plan row records a justification) -- "
            f"the gate will accept it"
        )
    return (
        f"slice {row.slice_id} has {at_count} ATs over the carpaccio ceiling of "
        f"{slice_max} and lacks the coupled escape -- the gate will refuse it. "
        f"Note @walking-skeleton / @infrastructure do NOT lift the ceiling; only "
        f"the coupled escape (every scenario @coupled + a recorded justification) "
        f"does. Re-slice into thinner verticals or apply the coupled escape."
    )


def _emit(feature_id: str, violations: list[str]) -> int:
    """Emit the machine JSON event + human summary; return the advisory exit code.

    Read-only courtesy surface: exit 0 when clean, non-zero (advisory) when
    violations are found. The pre-check NEVER records a verdict and NEVER writes
    to the ledger -- it only reads and reports.
    """
    if not violations:
        print(
            json.dumps(
                {
                    "event": "CarpaccioPrecheckClean",
                    "feature_id": feature_id,
                    "violation_count": 0,
                }
            )
        )
        print_human_summary(
            Verdict.PASS,
            f"carpaccio pre-check found no format violations for {feature_id}",
        )
        return 0
    print(
        json.dumps(
            {
                "event": "CarpaccioPrecheckViolations",
                "feature_id": feature_id,
                "violation_count": len(violations),
                "violations": violations,
            }
        )
    )
    for line in violations:
        print(f"  - {line}", file=sys.stderr)
    print_human_summary(
        Verdict.DEGRADED,
        f"carpaccio pre-check found {len(violations)} format violation(s) for "
        f"{feature_id} -- advisory, fix before recording the verdict",
    )
    return 3


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="carpaccio-precheck",
        description=(
            "Read-only carpaccio format pre-check: report every format violation "
            "the carpaccio-slice-gate would later raise, in one pass."
        ),
    )
    parser.add_argument("--feature-id", required=True)
    parser.add_argument("--repo-root", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo = _repo_root(args.repo_root)
    violations = collect_violations(repo, args.feature_id)
    return _emit(args.feature_id, violations)


if __name__ == "__main__":
    raise SystemExit(main())
