"""des flavor-scaffold -- the PRODUCING tool for the mode 4-tuple (GDP-4/5).

Charter: ``docs/product/expectations/fix-flavor-scaffold-producing-tool/
des-flavor-scaffold-produces-a-valid-flavor.md``.
Regression AT: ``tests/bugs/des/test_flavor_scaffold_produces_valid_flavor.py``.

``mode-registry-completeness`` (``src/des/cli/mode_registry_completeness.py``)
refuses a half-declared workflow flavor but its HOW routed only to a MANUAL
repair -- an operator hand-assembling the 4-tuple against
``nWave/flavors/_schema.yaml`` by reading the schema + an existing flavor side
by side. This closes that GDP-4/5 gap: the HOW now invokes a PRODUCING TOOL.

``des flavor-scaffold --flavor-id <id> [--display-name <name>] [--repo <root>]
[--stdout]`` emits a flavor YAML skeleton carrying ALL NINE schema-required
fields (``nWave/flavors/_schema.yaml`` ``required:``) -- a superset of the
gate's six-field ``_REQUIRED_FIELDS`` -- so the scaffold passes BOTH the
mode-registry-completeness gate AND the schema. Each field is declared
EXACTLY ONCE. ``default`` is always ``false`` -- the scaffold never mints a
second registry default (the exactly-one-default invariant). Placeholder
values for the operator-specific parts (``selection``, ``skill_load_set``,
``descriptor``, ``deliver_phase_shape``, ``lifecycle_events``) are
minimal-but-structurally-valid so only the operator's own resolution of the
TODO markers remains.

Stdlib-only: the YAML is emitted as hand-formatted TEXT matching the shape
``des._internal.subset_parser`` reads back (the DES bundle hygiene contract
forbids PyYAML in the bundled ``des`` module) -- never built via a YAML
emitter library.

Exit codes: 0 = scaffold emitted (stdout or file) | 1 = unwritable target
path | 2 = invalid/empty ``--flavor-id`` (usage-shaped diagnostic).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# Mirrors `nWave/flavors/_schema.yaml` `flavor_id` pattern -- kebab/snake-case
# identifier. Validated here so a hostile/empty --flavor-id degrades LOUD
# (a clear diagnostic) instead of emitting a scaffold the schema would refuse.
_FLAVOR_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# An existing, real agent (nWave/agents/nw-software-crafter.md) and an
# existing, real gate (nWave/gates/health-check.yaml) so the emitted
# skeleton's placeholder skill_load_set / lifecycle_events entries are
# structurally AND referentially valid -- they pass mode-registry-
# completeness's agent-existence check and name a real gate_id, not a
# fabricated one the operator would have to discover is wrong.
_PLACEHOLDER_AGENT = "nw-software-crafter"
_PLACEHOLDER_GATE_ID = "health-check"


def _default_display_name(flavor_id: str) -> str:
    """Title-cased default display name derived from the flavor id."""
    return flavor_id.replace("_", " ").replace("-", " ").title()


def _render_flavor_yaml(flavor_id: str, display_name: str) -> str:
    """Render the 9-field flavor skeleton as hand-formatted YAML text.

    Field order + shapes mirror `nWave/flavors/atdd_pure.yaml` /
    `classic.yaml` so `des._internal.subset_parser` (the stdlib-only reader
    both the runtime and `mode-registry-completeness` use) parses it back
    identically to `yaml.safe_load`. Every schema-required field appears
    EXACTLY ONCE at column 0.
    """
    return (
        f"flavor_id: {flavor_id}\n"
        f"display_name: {display_name}\n"
        "description: |\n"
        f"  TODO: describe the {flavor_id} flavor's intent and trade-offs\n"
        "  (what it composes, how it differs from existing flavors).\n"
        "default: false\n"
        "selection: deterministic-config\n"
        "skill_load_set:\n"
        f"  {_PLACEHOLDER_AGENT}:\n"
        "    conditional: []\n"
        "    # TODO: list skills conditionally loaded when this flavor is\n"
        "    # active, or leave declared-empty if none.\n"
        "descriptor: >\n"
        f"  TODO: one-line human-readable descriptor for the {flavor_id}\n"
        "  flavor (projected into GENERATED:mode-descriptor regions).\n"
        'deliver_phase_shape: "TODO_PHASE -> TODO_PHASE"\n'
        "lifecycle_events:\n"
        "  session.init:\n"
        f"    - gate_id: {_PLACEHOLDER_GATE_ID}\n"
        "      on_failure: log\n"
        "  # TODO: add dispatch.pre / subagent.stop / commit.pre rows as\n"
        "  # this flavor's gate composition requires (see atdd_pure.yaml /\n"
        "  # classic.yaml for worked examples).\n"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des flavor-scaffold",
        description=(
            "Produce a structurally-complete workflow-flavor YAML skeleton "
            "(the 9 nWave/flavors/_schema.yaml required fields) -- the "
            "sanctioned PRODUCING tool for a new flavor, never a hand-"
            "assembled edit."
        ),
    )
    parser.add_argument(
        "--flavor-id",
        required=True,
        help="New flavor's id, e.g. `my_flavor` (pattern ^[a-z][a-z0-9_]*$).",
    )
    parser.add_argument(
        "--display-name",
        default=None,
        help="Human-readable display name (default: titled from --flavor-id).",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        help="Repo root to write nWave/flavors/<id>.yaml under (default: cwd).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the scaffold to stdout instead of writing a file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Emit a flavor scaffold; return the operator-visible exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    flavor_id: str = args.flavor_id
    if not _FLAVOR_ID_PATTERN.fullmatch(flavor_id):
        sys.stderr.write(
            f"flavor-scaffold: invalid --flavor-id {flavor_id!r}.\n"
            "Why: nWave/flavors/_schema.yaml requires flavor_id to match "
            "`^[a-z][a-z0-9_]*$` (lowercase, digits, underscores, starting "
            "with a letter).\n"
            "Fix: pass a --flavor-id like `my_flavor` or `atdd_lite`.\n"
        )
        return 2

    display_name = args.display_name or _default_display_name(flavor_id)
    yaml_text = _render_flavor_yaml(flavor_id, display_name)

    if args.stdout:
        sys.stdout.write(yaml_text)
        return 0

    repo_root = args.repo if args.repo is not None else Path.cwd()
    target_dir = repo_root / "nWave" / "flavors"
    target_path = target_dir / f"{flavor_id}.yaml"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path.write_text(yaml_text, encoding="utf-8")
    except OSError as exc:
        sys.stderr.write(
            f"flavor-scaffold: cannot write {target_path}.\n"
            f"Why: {exc}\n"
            "Fix: pass a writable --repo, or use --stdout and redirect the "
            "output yourself.\n"
        )
        return 1

    sys.stdout.write(f"flavor-scaffold: wrote {target_path}\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
