#!/usr/bin/env python3
"""Check docs/reference/ freshness; fail loudly on stale.

Usage:
    python scripts/hooks/check_documentation_freshness.py          # local hook
    python scripts/hooks/check_documentation_freshness.py --check  # CI (alias)

Exit codes:
    0 - Documentation is fresh
    1 - Pipeline error or docs are stale

Local and CI behavior are identical: stale state fails the push with a clear
remediation message. The previous "silent regenerate + git commit --amend"
local mode was removed because it composed unsafely with write_pages's prior
shutil.rmtree-based regeneration — silently deleting hand-authored files in
docs/reference/ from the pushed commit. See
docs/analysis/rca-pre-push-hook-untracked-deletion-2026-05-06.md.
"""

import importlib.util
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent.parent

# Make the `des` package importable when this hook runs as a standalone
# subprocess (pre-commit does not put `src/` on `sys.path`). Same
# self-bootstrap recipe as scripts/hooks/verify_slice_ledger_record.py.
# `des.application.dispatch_lane_ssot` is stdlib-only (re + dataclasses via
# des.domain.lane_profile) -- no PyYAML dependency, so importing it here
# does NOT reintroduce the bare-python3-without-venv hazard `_load_docgen`
# guards against below.
_SRC_DIR = _ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from des.application.dispatch_lane_ssot import check_lane_profile_drift  # noqa: E402


def _load_docgen():
    """Load ``scripts/docgen.py`` by path, deferred until actually needed.

    Importing THIS module must stay side-effect-free of docgen: docgen
    imports PyYAML (a venv-only dependency) at module level, and this
    script runs as a pre-commit `language: system` hook under a bare
    python3 with no venv guaranteed. Loading docgen eagerly at module scope
    would crash the load of this file before ``main()`` ever runs.
    """
    spec = importlib.util.spec_from_file_location(
        "docgen", _ROOT / "scripts" / "docgen.py"
    )
    docgen = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    # Register BEFORE exec_module (canonical importlib recipe): @dataclass under
    # `from __future__ import annotations` resolves string annotations via
    # sys.modules[cls.__module__] — unregistered, dataclasses raises AttributeError.
    sys.modules["docgen"] = docgen
    try:
        spec.loader.exec_module(docgen)  # type: ignore[union-attr]
    except ModuleNotFoundError as exc:
        print(
            f"ERROR: docgen dependency unavailable under this interpreter ({exc}); "
            "run via `uv run` or install pyyaml.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    return docgen


def main() -> int:
    output_dir = _ROOT / "docs" / "reference"
    docgen = _load_docgen()

    try:
        pages = docgen.run_pipeline(_ROOT, output_dir)
    except Exception as e:
        print(f"ERROR: docgen pipeline failed: {e}", file=sys.stderr)
        return 1

    stale = docgen.check_pages(pages, output_dir)

    # registry<->runtime agreement leg (mode-registry-single-locus slice-05,
    # F-DOCGEN-PHASE-VOCAB-COMPARATOR-ALIAS-BLIND prevention): `--check` already
    # runs this via the CLI entry point, but this pre-push hook re-implements
    # `--check`'s file-staleness half by hand and had NOT been carrying the
    # registry-agreement half -- so a phase-vocab rename (the velocity-v2
    # EXAMINE/COMMIT rename that shipped uncaught) could pass this gate. Wired
    # here so a future rename is caught mechanically at push time, not only
    # when an operator remembers to run `docgen.py --check` by hand.
    disagreements = docgen.check_registry_runtime_agreement(_ROOT)

    # dispatch-lane SSOT drift leg (dispatch-lane-ssot-drift-check-never-
    # invoked-outside-its-own-test): check_lane_profile_drift is the ONLY
    # consulting locus that projects nWave/dispatch/atdd_pure.yaml's
    # profiles.lane block against the live des.domain.lane_profile.
    # LANE_PROFILES literal and names any disagreement -- before this, it was
    # invoked ONLY by its own unit test, so a real YAML<->literal drift would
    # ship silently. Wired here, the sibling agreement-leg it explicitly
    # models itself on (registry<->runtime agreement, above).
    lane_drift = check_lane_profile_drift(_ROOT)

    # GENERATED-region freshness leg (declared-facts-reachable-recorded
    # slice-04, DD-11): every GENERATED-marker-carrying asset (agents,
    # commands and skills) must byte-match a
    # fresh re-render -- alongside the existing 3 legs above.
    asset_paths = docgen.scan(_ROOT)
    generated_projections = docgen.project_generated_regions(_ROOT, asset_paths)
    generated_stale = docgen.check_generated_regions(_ROOT, generated_projections)

    if not stale and not disagreements and not lane_drift and not generated_stale:
        print("✓ docs/reference/ is up to date")
        return 0

    if stale:
        print(
            f"ERROR: docs/reference/ has {len(stale)} stale files: {', '.join(stale)}",
            file=sys.stderr,
        )
        print("Run the following to bring docs/reference/ up to date:", file=sys.stderr)
        print("  python scripts/docgen.py", file=sys.stderr)
        print("  git add docs/reference/", file=sys.stderr)
        print("  git commit --amend --no-edit  # or a fresh commit", file=sys.stderr)

    if disagreements:
        print(
            f"ERROR: registry<->runtime agreement failed ({len(disagreements)}):",
            file=sys.stderr,
        )
        for disagreement in disagreements:
            print(f"  {disagreement}", file=sys.stderr)
        print(
            "Fix the drifted registry field (nWave/flavors/*.yaml) or the "
            "runtime source it disagrees with, then retry.",
            file=sys.stderr,
        )

    if lane_drift:
        print(
            f"ERROR: dispatch-lane SSOT drift detected ({len(lane_drift)}):",
            file=sys.stderr,
        )
        for entry in lane_drift:
            print(f"  {entry}", file=sys.stderr)
        print(
            "Reconcile nWave/dispatch/atdd_pure.yaml's profiles.lane block "
            "against src/des/domain/lane_profile.py::LANE_PROFILES, then retry.",
            file=sys.stderr,
        )

    if generated_stale:
        print(
            f"ERROR: {len(generated_stale)} GENERATED region(s) are stale:",
            file=sys.stderr,
        )
        for entry in generated_stale:
            print(f"  {entry}", file=sys.stderr)
        print(
            "Run the following to re-render every GENERATED region:",
            file=sys.stderr,
        )
        print("  python scripts/docgen.py", file=sys.stderr)

    print("Then retry your push.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
