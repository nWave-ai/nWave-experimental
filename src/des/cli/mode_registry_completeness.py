"""mode-registry-completeness — Layer-B guardrail (mode-registry-single-locus slice-05).

Analysis §3.2: the registry is the single, COMPLETE home for the mode 4-tuple.
This gate reads every flavor file under ``<root>/nWave/flavors/`` and refuses a
half-declared mode, NAMING the defect (the slice-01 fail-closed refusal contract
lifted to the registry level). Checks:

* every flavor declares the schema-required 4-tuple fields
  (``display_name``, ``default``, ``selection``, ``skill_load_set``,
  ``descriptor``, ``deliver_phase_shape``);
* every required field is declared EXACTLY ONCE per flavor — a duplicated
  top-level declaration is a shadowing ambiguity (a last-wins parser would
  silently prefer the appended copy over the authoritative first one: the
  duplicate-key bypass class the Layer-C agreement leg relies on THIS gate
  to refuse — the §3.4 orthogonality property);
* EXACTLY ONE flavor across the registry declares ``default: true``;
* every agent named in any flavor's ``skill_load_set`` has a spec under
  ``<root>/nWave/agents/``;
* no conflicting ``selection`` across flavors;
* a missing / unparsable flavor file is refused (never silently skipped).

Pure read (Mandate 8): the gate rewrites nothing. Stdlib-only (the flavor files
are parsed by the SSOT ``des._internal.subset_parser``, NEVER PyYAML — the DES
bundle hygiene contract). Git-free. Implemented as an argparse CLI:
argparse + a small dataclass + pure check functions + a thin ``main``.

Exit codes: 0 = registry complete | 1 = ``--root`` / flavors dir invalid
| 2 = at least one completeness defect (each named on stdout).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:  # only in annotations
    from pathlib import Path

from des._internal import subset_parser
from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.repo_path_resolver import resolve_repo_root


# The asset-facing 4-tuple fields every flavor MUST declare (analysis §2.2 /
# §3.2). Mirrors the `required` list in `nWave/flavors/_schema.yaml`; the schema
# refuses these structurally, the gate names them as an operator-actionable
# completeness defect.
_REQUIRED_FIELDS: tuple[str, ...] = (
    "display_name",
    "default",
    "selection",
    "skill_load_set",
    "descriptor",
    "deliver_phase_shape",
)


@dataclass(frozen=True)
class CompletenessDefect:
    """One way the registry is a half-declared mode, with the defect named."""

    flavor_id: str
    defect: str

    def render(self) -> str:
        return f"  {self.flavor_id}: {self.defect}"


def _repo_root(root_arg: str | None) -> Path:
    return resolve_repo_root(root_arg)


def _flavor_files(flavors_dir: Path) -> list[Path]:
    return sorted(p for p in flavors_dir.glob("*.yaml") if not p.name.startswith("_"))


def _missing_field_defects(
    flavor_id: str, doc: dict[str, object]
) -> list[CompletenessDefect]:
    return [
        CompletenessDefect(flavor_id, f"missing required mode field {field!r}")
        for field in _REQUIRED_FIELDS
        if field not in doc
    ]


def _top_level_declaration_count(raw_text: str, field: str) -> int:
    """How many times *field* is declared at column 0 in the raw flavor text."""
    return len(re.findall(rf"^{re.escape(field)}:", raw_text, flags=re.MULTILINE))


def _duplicate_declaration_defects(
    flavor_id: str, raw_text: str
) -> list[CompletenessDefect]:
    """Refuse a shadowed mode field: a required field declared 2+ times.

    A duplicated top-level declaration is ambiguous — a last-wins parser (the
    runtime's `subset_parser`, PyYAML) silently prefers the LAST copy while
    the authoritative declaration is the FIRST. An appended drifted duplicate
    would therefore steer the runtime away from the value the Layer-C
    agreement leg verified. This gate refuses the ambiguity fail-closed
    (the §3.4 one-layer-bypass-caught-by-another property).
    """
    return [
        CompletenessDefect(
            flavor_id,
            f"required mode field {field!r} declared "
            f"{_top_level_declaration_count(raw_text, field)} times — a "
            "shadowed (appended) declaration is ambiguous; declare each mode "
            "field exactly once",
        )
        for field in _REQUIRED_FIELDS
        if _top_level_declaration_count(raw_text, field) > 1
    ]


def _agent_existence_defects(
    flavor_id: str, doc: dict[str, object], existing_agents: frozenset[str]
) -> list[CompletenessDefect]:
    skill_load_set = doc.get("skill_load_set")
    if not isinstance(skill_load_set, dict):
        return []
    return [
        CompletenessDefect(
            flavor_id,
            f"skill_load_set directs agent {agent_id!r} that does not exist "
            "under nWave/agents/",
        )
        for agent_id in skill_load_set
        if agent_id not in existing_agents
    ]


def _default_count_defects(
    flavors: dict[str, dict[str, object]],
) -> list[CompletenessDefect]:
    defaulting = [
        flavor_id for flavor_id, doc in flavors.items() if doc.get("default") is True
    ]
    if len(defaulting) == 1:
        return []
    return [
        CompletenessDefect(
            ", ".join(sorted(flavors)),
            f"exactly one flavor must declare `default: true`; found "
            f"{len(defaulting)} ({sorted(defaulting)})",
        )
    ]


def _selection_conflict_defects(
    flavors: dict[str, dict[str, object]],
) -> list[CompletenessDefect]:
    selections = {
        doc.get("selection")
        for doc in flavors.values()
        if doc.get("selection") is not None
    }
    if len(selections) <= 1:
        return []
    return [
        CompletenessDefect(
            ", ".join(sorted(flavors)),
            f"conflicting `selection` across flavors: {sorted(map(str, selections))}",
        )
    ]


def _existing_agents(root: Path) -> frozenset[str]:
    agents_dir = root / "nWave" / "agents"
    if not agents_dir.is_dir():
        return frozenset()
    return frozenset(p.stem for p in agents_dir.glob("*.md"))


def check_registry_completeness(root: Path) -> list[CompletenessDefect]:
    """Pure check: every completeness defect across the flavor registry.

    A flavor file that cannot be parsed is itself a refused defect (never a
    silent skip — fail-closed).
    """
    flavors_dir = root / "nWave" / "flavors"
    existing_agents = _existing_agents(root)
    parsed: dict[str, dict[str, object]] = {}
    defects: list[CompletenessDefect] = []
    for path in _flavor_files(flavors_dir):
        try:
            raw_text = path.read_text(encoding="utf-8")
            doc = subset_parser.load_file(path)
        except (ValueError, OSError) as exc:
            defects.append(
                CompletenessDefect(path.stem, f"unparsable flavor file: {exc}")
            )
            continue
        parsed[path.stem] = doc
        defects.extend(_missing_field_defects(path.stem, doc))
        defects.extend(_duplicate_declaration_defects(path.stem, raw_text))
        defects.extend(_agent_existence_defects(path.stem, doc, existing_agents))
    defects.extend(_default_count_defects(parsed))
    defects.extend(_selection_conflict_defects(parsed))
    return defects


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mode-registry-completeness",
        description=(
            "Refuse a half-declared mode: every flavor declares the 4-tuple "
            "fields, exactly one default, every skill_load_set agent exists."
        ),
    )
    add_repo_root_argument(
        parser,
        "--root",
        default=None,
        help="Root of the asset tree to check (default: this repository).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = _repo_root(args.root)
    flavors_dir = root / "nWave" / "flavors"
    if not flavors_dir.is_dir():
        sys.stderr.write(
            f"mode-registry-completeness: no nWave/flavors/ under root {root}\n"
        )
        sys.stderr.write(
            "Fix: ensure nWave/flavors/ exists with *.yaml flavor files, or "
            "pass --root at the tree containing it.\n"
        )
        return 1
    if not _flavor_files(flavors_dir):
        sys.stderr.write(
            f"mode-registry-completeness: no flavor files under {flavors_dir}\n"
        )
        sys.stderr.write(
            "Fix: ensure nWave/flavors/ contains at least one *.yaml flavor "
            "file, or pass --root at the tree containing them.\n"
        )
        return 1
    defects = check_registry_completeness(root)
    if not defects:
        sys.stdout.write("mode-registry-completeness: the mode registry is complete.\n")
        return 0
    sys.stdout.write(
        f"mode-registry-completeness: {len(defects)} completeness defect(s) "
        "leave the registry a half-declared mode:\n"
    )
    for defect in defects:
        sys.stdout.write(defect.render() + "\n")
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
