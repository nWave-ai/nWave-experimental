"""validate_ssot_propagation — back-propagation contract validator (R3).

Per Recommendation 3 (lean-wave doc audit, 2026-04-28). When a PR modifies
`docs/feature/{id}/feature-delta.md`, the lean-wave contract requires that
the relevant SSOT artifact under `docs/product/` is also modified in the
same diff (DESIGN, DEVOPS, DISTILL, DELIVER waves all back-propagate to
SSOT — see each wave skill's "SSOT updates" subsection).

CLI contract:
- `git diff --name-only <ref> | python validate_ssot_propagation.py`
  Reads modified-paths on stdin (one per line) and validates the SSOT
  propagation contract.
- Exit 0 always during the soft-rollout window (warnings only). Promote
  to exit 1 after one stable release by dropping `--soft`.
- Exit 2 on usage error.

Architecture (functional split):
- Pure core: `validate_ssot_propagation(modified_paths)` accepts a flat
  list of paths and returns a `PropagationResult`. No I/O.
- CLI shell: `main(argv)` reads stdin, delegates to the pure core, prints
  diagnostics, returns the exit code.
"""

from __future__ import annotations

import sys
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Domain types — pure data carriers
# ---------------------------------------------------------------------------


#: Marker prefix identifying a feature-delta.md file under docs/feature/.
FEATURE_DELTA_PREFIX: str = "docs/feature/"
FEATURE_DELTA_SUFFIX: str = "/feature-delta.md"

#: Marker prefix identifying any SSOT path. A modification anywhere under
#: `docs/product/` is treated as a back-propagation signal.
SSOT_PREFIX: str = "docs/product/"


class PropagationWarning(NamedTuple):
    """A feature-delta.md whose modification was not paired with SSOT writes."""

    feature_id: str
    feature_delta_path: str
    expected_ssot_paths: tuple[str, ...]


class PropagationResult(NamedTuple):
    """Outcome of evaluating a diff against the back-propagation contract."""

    has_warnings: bool
    warnings: list[PropagationWarning]
    feature_delta_count: int
    ssot_modified: bool


# ---------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------


def _extract_feature_id(path: str) -> str | None:
    """Return the feature-id slug for a feature-delta.md path, else None."""
    if not path.startswith(FEATURE_DELTA_PREFIX):
        return None
    if not path.endswith(FEATURE_DELTA_SUFFIX):
        return None
    return path[len(FEATURE_DELTA_PREFIX) : -len(FEATURE_DELTA_SUFFIX)]


def _expected_ssot_paths_for(feature_id: str) -> tuple[str, ...]:
    """Return the canonical SSOT paths a feature might reasonably write to.

    These are advisory — a single feature seldom touches all of them. The
    list documents the contract in failure messages so authors know where
    SSOT writes belong (per the "SSOT updates" subsection of each wave
    skill, post-Recommendation 1).
    """
    del (
        feature_id
    )  # currently per-feature paths aren't custom; reserved for future use.
    return (
        "docs/product/architecture/brief.md",
        "docs/product/architecture/adr-*.md",
        "docs/product/jobs.yaml",
        "docs/product/journeys/{name}.yaml",
        "docs/product/personas/{name}.yaml",
        "docs/product/kpi-contracts.yaml",
    )


def validate_ssot_propagation(modified_paths: list[str]) -> PropagationResult:
    """Validate that feature-delta modifications are paired with SSOT writes.

    Pure function. Walks the diff once; counts feature-delta modifications;
    counts SSOT modifications. If at least one feature-delta changed and
    NO SSOT path changed, emits a warning per modified feature.

    Args:
        modified_paths: list of forward-slash-relative paths from the PR
            diff (typically `git diff --name-only origin/master`).

    Returns:
        PropagationResult with `has_warnings` true iff the contract is
        violated.
    """
    feature_deltas: list[tuple[str, str]] = []  # (feature_id, path)
    ssot_modified = False

    for path in modified_paths:
        normalized = path.strip().replace("\\", "/")
        if not normalized:
            continue
        if normalized.startswith(SSOT_PREFIX):
            ssot_modified = True
            continue
        feature_id = _extract_feature_id(normalized)
        if feature_id is not None:
            feature_deltas.append((feature_id, normalized))

    warnings: list[PropagationWarning] = []
    if feature_deltas and not ssot_modified:
        for feature_id, delta_path in feature_deltas:
            warnings.append(
                PropagationWarning(
                    feature_id=feature_id,
                    feature_delta_path=delta_path,
                    expected_ssot_paths=_expected_ssot_paths_for(feature_id),
                )
            )

    return PropagationResult(
        has_warnings=bool(warnings),
        warnings=warnings,
        feature_delta_count=len(feature_deltas),
        ssot_modified=ssot_modified,
    )


# ---------------------------------------------------------------------------
# CLI shell
# ---------------------------------------------------------------------------


def _format_warnings(result: PropagationResult) -> str:
    lines = [
        f"SSOT back-propagation WARNING: {len(result.warnings)} "
        f"feature-delta.md modification(s) without paired SSOT writes.",
        "",
    ]
    for warn in result.warnings:
        lines.append(f"  feature: {warn.feature_id}")
        lines.append(f"    delta:    {warn.feature_delta_path}")
        lines.append("    expected SSOT writes (one or more of):")
        for path in warn.expected_ssot_paths:
            lines.append(f"      - {path}")
    lines.append("")
    lines.append(
        "Per Recommendation 3: DESIGN, DEVOPS, DISTILL, DELIVER waves "
        "MUST back-propagate to docs/product/. Open the relevant wave "
        "skill's `Outputs > SSOT updates` subsection for the contract."
    )
    return "\n".join(lines)


def _format_clean(result: PropagationResult) -> str:
    if result.feature_delta_count == 0:
        return "validate_ssot_propagation: no feature-delta.md changes in diff."
    return (
        f"validate_ssot_propagation: {result.feature_delta_count} "
        "feature-delta.md modification(s) paired with SSOT writes (clean)."
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry: reads diff paths from stdin, returns exit code.

    Args:
        argv: optional argument list. Recognised: `--soft` (always exit 0
            even on warnings). Default behaviour also exits 0 during the
            rollout window — promote to strict mode by removing this
            default after one stable release.

    Returns:
        0 on clean diff or under `--soft`. Reserved 1 for future strict
        mode. 2 on usage error.
    """
    args = sys.argv[1:] if argv is None else argv
    strict = "--strict" in args

    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    paths = [line for line in raw.splitlines() if line.strip()]

    result = validate_ssot_propagation(paths)
    if not result.has_warnings:
        print(_format_clean(result))
        return 0

    print(_format_warnings(result), file=sys.stderr)
    return 1 if strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
