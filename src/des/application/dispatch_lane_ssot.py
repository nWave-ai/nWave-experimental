"""dispatch_lane_ssot -- the ONE consulting locus that drift-checks `nWave/
dispatch/atdd_pure.yaml`'s `profiles.lane` block against the live
`des.domain.lane_profile.LANE_PROFILES` domain literal (feature
`des-dispatch-ssot-renderer`, Fase-1 code-layer, design: docs/feature/
des-dispatch-ssot-renderer/design/dispatch-ssot-design.md, Open Review
Point A resolved: the YAML is the SSOT, `LANE_PROFILES` stays a PURE
LITERAL -- D1/D2, no YAML I/O in the domain).

Mirrors the docgen `GENERATED:mode-descriptor` Layer-C agreement-leg
pattern (`scripts/docgen.py::check_registry_runtime_agreement` -- registry
says X, the running system says Y, name the disagreement, empty list =
fresh/in-sync). `LANE_PROFILES` is the projection's SOURCE OF TRUTH for
what "the running system says"; the YAML is the SSOT for what it OUGHT to
say.

DES-bundle-legal caveat: `nWave/dispatch/atdd_pure.yaml` uses flow-style
YAML (`sections: [A, B, ...]` wrapped across lines, `drop_sections: [X, Y]`)
that `des._internal.subset_parser` (the ONLY stdlib-only YAML reader legal
inside a bundled `des` module -- `import yaml` is forbidden here) does NOT
support. This module therefore carries a small, PURPOSE-BUILT reader scoped
to exactly the `profiles.full.sections` and `profiles.lane.*` shape this
file declares -- never a general YAML parser.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from des.application.atdd_pure_prompt_validator import ATDD_PURE_MANDATORY_SECTIONS
from des.domain.lane_profile import LANE_PROFILES


if TYPE_CHECKING:
    from pathlib import Path

_DISPATCH_YAML_PARTS = ("nWave", "dispatch", "atdd_pure.yaml")

# `profiles: full: sections: [...]` -- a flow-style list that may wrap across
# several lines before its closing `]`. DOTALL lets `.` cross newlines; the
# non-greedy body stops at the FIRST `]`, which is correct here because the
# section-id tokens never themselves contain brackets.
_FULL_SECTIONS_PATTERN = re.compile(
    r"full:\s*\n\s*sections:\s*\[(?P<body>.*?)\]", re.DOTALL
)


def _parse_flow_list(value_text: str) -> tuple[str, ...]:
    """Parse a single-line YAML flow list (``[a, b, c]`` or ``[]``) into a tuple."""
    stripped = value_text.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        raise ValueError(f"expected a flow-style YAML list, got {value_text!r}")
    inner = stripped[1:-1].strip()
    if not inner:
        return ()
    return tuple(item.strip() for item in inner.split(","))


def _read_full_sections(text: str) -> tuple[str, ...]:
    """Read `profiles.full.sections` -- the canonical ordered section set."""
    match = _FULL_SECTIONS_PATTERN.search(text)
    if match is None:
        raise ValueError("profiles.full.sections not found in the dispatch SSOT YAML")
    return _parse_flow_list(f"[{match.group('body')}]")


def _read_lane_drop_sections(text: str) -> dict[str, tuple[str, ...]]:
    """Read `profiles.lane.<lane_id>.drop_sections` for every lane row.

    Walks the indented block under the `lane:` header line-by-line: a line at
    the lane-row indent (one level deeper than `lane:`) starts a new lane id;
    a `drop_sections:` line at the field indent (one level deeper still)
    supplies that lane's dropped-section list. `drop_sections` is always
    authored on a single line in this SSOT (``[]`` or a short flow list), so
    no multi-line flow-list handling is needed here -- other multi-line
    fields (e.g. `skipped_invariants`) are simply skipped by the indent
    mismatch, since this reader only extracts what the drift-check compares.
    """
    lines = text.splitlines()
    lane_header_indent: int | None = None
    lane_header_idx: int | None = None
    for idx, line in enumerate(lines):
        if line.strip() == "lane:":
            lane_header_indent = len(line) - len(line.lstrip(" "))
            lane_header_idx = idx
            break
    if lane_header_idx is None or lane_header_indent is None:
        raise ValueError("profiles.lane block not found in the dispatch SSOT YAML")

    lanes: dict[str, tuple[str, ...]] = {}
    current_lane: str | None = None
    lane_row_indent: int | None = None
    idx = lane_header_idx + 1
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if stripped:
            indent = len(line) - len(line.lstrip(" "))
            if indent <= lane_header_indent:
                break
            if lane_row_indent is None:
                lane_row_indent = indent
            if indent == lane_row_indent:
                current_lane = stripped.rstrip(":")
            elif stripped.startswith("drop_sections:") and current_lane is not None:
                value_text = stripped.partition(":")[2].strip()
                lanes[current_lane] = _parse_flow_list(value_text)
        idx += 1
    return lanes


def check_lane_profile_drift(repo_root: Path) -> list[str]:
    """Project `nWave/dispatch/atdd_pure.yaml`'s `profiles.lane` block and
    compare it, lane-by-lane, against the live `des.domain.lane_profile.
    LANE_PROFILES` datum.

    Returns a list of stale-entry strings naming each disagreement -- an
    empty list means the two are fresh/in-sync. Contract: `-> list[str]`
    ALWAYS -- every hostile input (missing file, malformed YAML, a
    well-formed YAML missing the `profiles.lane` block) degrades LOUD to a
    single diagnostic entry naming the failure, never a raised exception.
    """
    yaml_path = repo_root.joinpath(*_DISPATCH_YAML_PARTS)

    try:
        text = yaml_path.read_text(encoding="utf-8")
    except OSError:
        return [f"dispatch SSOT YAML not found at expected path {yaml_path}"]

    try:
        full_sections = _read_full_sections(text)
    except ValueError:
        return [
            f"dispatch SSOT YAML at {yaml_path} is malformed/unparseable: "
            "could not locate a well-formed profiles.full.sections block"
        ]

    try:
        yaml_lane_drop_sections = _read_lane_drop_sections(text)
    except ValueError:
        return [f"dispatch SSOT YAML at {yaml_path} is missing its profiles.lane block"]

    yaml_lane_ids = set(yaml_lane_drop_sections)
    live_lane_ids = set(LANE_PROFILES)

    drift: list[str] = []

    full_sections_set = set(full_sections)
    mandatory_sections_set = set(ATDD_PURE_MANDATORY_SECTIONS)
    if full_sections_set != mandatory_sections_set:
        only_in_yaml = tuple(
            s for s in full_sections if s not in mandatory_sections_set
        )
        only_in_live = tuple(
            s for s in ATDD_PURE_MANDATORY_SECTIONS if s not in full_sections_set
        )
        drift.append(
            "ATDD_PURE_MANDATORY_SECTIONS and profiles.full.sections differ: "
            f"only-in-YAML={only_in_yaml!r} only-in-live={only_in_live!r}"
        )

    for lane_id in sorted(yaml_lane_ids - live_lane_ids):
        drift.append(
            f"lane {lane_id!r} present in the YAML SSOT but missing from LANE_PROFILES"
        )

    for lane_id in sorted(live_lane_ids - yaml_lane_ids):
        drift.append(
            f"lane {lane_id!r} present in LANE_PROFILES but missing from the YAML SSOT"
        )

    for lane_id in sorted(yaml_lane_ids & live_lane_ids):
        drop_sections = yaml_lane_drop_sections[lane_id]
        projected = tuple(s for s in full_sections if s not in drop_sections)
        live_sections = LANE_PROFILES[lane_id].required_sections
        if projected != live_sections:
            live_set = set(live_sections)
            projected_set = set(projected)
            only_in_yaml = tuple(s for s in projected if s not in live_set)
            only_in_live = tuple(s for s in live_sections if s not in projected_set)
            drift.append(
                f"lane {lane_id!r} required_sections differ: "
                f"only-in-YAML={only_in_yaml!r} only-in-live={only_in_live!r}"
            )

    return drift
