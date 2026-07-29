#!/usr/bin/env python3
"""GOAL CONTRACT (FIRST-CUT, autonomous) for the `atdd-pure-beta-readiness` epic.

THIS SCRIPT *IS* THE MEASUREMENT of "is ATDD-pure ready for beta on the experimental
repo". The score depends only on this committed code running deterministic,
fail-closed checks over the repo state -- never on anyone's word. Same code + same
repo state -> same number. A member that changes is a reviewable git diff.

STATUS: FIRST-CUT, authored autonomously (Lyra-DEV, 2026-06-23 night protocol) from
docs/analysis/beta-readiness-epic-triage-2026-06-23.md at the MINIMAL beta-bar
(the reversible flagged default; Ale ratifies the bar + member set). The member set
and per-member predicates ARE the epic's working definition until /nw-discuss
epic-mode formalizes it. Nothing is hidden: every known member is in the denominator
from day one; OPEN members count against the score honestly (the score is not gamed
by omitting un-done work).

UNIT = an epic MEMBER (a ToC item or a prioritized friction). A member is DONE iff
its deterministic predicate holds over the committed repo. Fail-closed: an
unverifiable member is NOT DONE.

Pure stdlib only (target-machine independence). No git, no external packages -- the
predicates read the source tree via pathlib + substring checks.

Usage:
    python scripts/beta_readiness_scorecard.py
    python scripts/beta_readiness_scorecard.py --json
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from _scorecard_fs_helpers import REPO
from _scorecard_fs_helpers import file_contains as _file_contains
from _scorecard_fs_helpers import file_exists as _file_exists


if TYPE_CHECKING:
    from collections.abc import Callable


def _dir_has_children(rel: str, glob: str) -> bool:
    base = REPO / rel
    return base.is_dir() and any(base.glob(glob))


def _symbol_referenced_in_code(rel: str, symbol: str) -> bool:
    """True iff `symbol` appears in the file's CODE (not comments/strings).

    Fail-closed behavior proof (#2 hardening, 2026-06-29): parses the file with
    stdlib `ast` and looks for `symbol` as a real Name / Attribute / function
    or class definition. A comment or string literal mentioning `symbol` is NOT
    an AST node of that kind, so this fails-closed if the behavior is deleted
    while a documenting comment is left behind -- the presence-proxy hole the
    epic-end swarm caught. Portable: stdlib only (no tsunami/MCP), so the
    scorecard stays deterministic + target-machine-independent. Unreadable /
    unparseable file -> False (fail-closed).
    """
    path = REPO / rel
    if not path.is_file():
        return False
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == symbol:
            return True
        if isinstance(node, ast.Attribute) and node.attr == symbol:
            return True
        if (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
            and node.name == symbol
        ):
            return True
    return False


@dataclass(frozen=True)
class Member:
    """One epic member + its deterministic DONE predicate."""

    mid: str
    title: str
    toc_or_friction: str
    predicate: Callable[[], bool]
    note: str = ""


# --- The MINIMAL beta-bar member set (first-cut; Ale ratifies) ---------------
# DONE predicates are conjunctions of committed-source facts. They are intentionally
# SHALLOW structural proofs (a shipped fix left a test + the production change); the
# DEEP proof is the full-suite-green gate, run separately. A member flips to DONE only
# when its committed artifacts are present -- never on assertion.
_MEMBERS: tuple[Member, ...] = (
    Member(
        mid="M1",
        title="sustainable-test-suite test-base (nw-distill lean reconciliation + d4)",
        toc_or_friction="friction (this-session) + JOB-026 walking-skeleton",
        predicate=lambda: (
            _dir_has_children("nWave/skills", "nw-distill-*/SKILL.md")
            and _file_contains(
                "src/des/application/skill_normative_gate_service.py",
                "_resolve_assets",
            )
        ),
        note="gate resolves skill corpus (monolith U sub-skills); shipped 77c9242a5",
    ),
    Member(
        mid="M2",
        title="wave-floor mode-aware routing (atdd_pure exempt from classic bypass)",
        toc_or_friction="friction (tsunami/nwave-sf, 4x) -- R3-adjacent dispatch honesty",
        predicate=lambda: (
            _file_exists(
                "tests/des/acceptance/wave_floor_atdd_pure_mode_exemption/"
                "test_atdd_pure_floor_exemption.py"
            )
            and _symbol_referenced_in_code(
                "src/des/application/pre_tool_use_service.py",
                "classify_atdd_pure_dispatch",
            )
        ),
        note="shipped 0748107b6; catch-22 atdd_pure-crafter closed",
    ),
    Member(
        mid="M3",
        title="R3 gate non-vacuity slice-02 (LOUD-on-absent-arch-scope floor)",
        toc_or_friction="ToC #1 (binding constraint)",
        predicate=lambda: (
            _file_exists(
                "tests/des/acceptance/r3_gate_non_vacuity_build_tier/"
                "slice-02-arch-scope-non-vacuity.feature"
            )
            and _file_exists(
                "tests/des/acceptance/r3_gate_non_vacuity_build_tier/"
                "steps/domain_types_slice_02.py"
            )
        ),
        note="DONE -- R3 slice-01/02/03 all delivered + green (12/12 verified 2026-06-23); ToC #1 'slice-02 remains' was stale (2026-06-04, 19d old)",
    ),
    Member(
        mid="M4",
        title="verify-wave-dispatch <-> PreToolUse exemption SSOT reconcile",
        toc_or_friction="friction (tsunami Q-10/11) -- highest ACTIVE friction",
        predicate=lambda: _file_exists(
            "tests/des/acceptance/wave_dispatch_exemption_ssot/"
            "test_verify_wave_dispatch_at3_canonical.py"
        ),  # DESIGN-RESOLVED (Ale 2026-06-23: AT-3-BLOCK canonical, no bypass reopen)
        note="DESIGN-RESOLVED (Ale 2026-06-23: AT-3-BLOCK canonical -- verify-wave-dispatch aligned to AT-3 BLOCK verdict, no security reopen); impl via spine /nw-bugfix (RCA done, direction ratified). Flips DONE when regression AT lands",
    ),
    Member(
        mid="M5",
        title="feature-end WS-gate computed applicability (no fail-close sans @walking-skeleton)",
        toc_or_friction="friction (nwave-sf cross-tree) -- feature-end honesty",
        predicate=lambda: (
            _symbol_referenced_in_code(
                "src/des/cli/walking_skeleton_gate.py",
                "_feature_under_gate",
            )
            and _file_exists(
                "tests/des/unit/cli/test_ws_gate_computed_applicability.py"
            )
        ),
        note="shipped: _feature_under_gate computes applicability from the delta on the no-AT path (RCA via /nw-bugfix)",
    ),
    Member(
        mid="M6",
        title="floor auto-close cross-wave (supersede-on-new-wave)",
        toc_or_friction="friction (tsunami Q-10) -- I4-governed",
        predicate=lambda: (
            _file_contains(
                "src/des/application/subagent_stop_service.py",
                "_maybe_close_owner_floor",
            )
            and _file_exists(
                "tests/des/acceptance/floor_auto_close_cross_wave/"
                "test_floor_auto_close_cross_wave.py"
            )
        ),  # DONE -- impl seam present in production + AT shipped (Ale Option A)
        note="shipped 2026-06-23 (Ale opzione A): _maybe_close_owner_floor chains WaveActiveFilesystemStore.clear() on the wave-only attested gate-OUT PASS IFF WAVE_OWNERS[subagent_type]==active wave (terminal/owner only); additive, I3/I4 untouched, in-wave persist by construction. slice c28522d34, SliceCommitVerified + Gate-Scope verified, C_REVIEWER_AUDIT APPROVED (genuine terminal/owner gate, binding-resolved). 6/6 scoped ATs + invariant guards 126/126",
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
    lines = [
        "=" * 78,
        "atdd-pure-beta-readiness -- GOAL CONTRACT (FIRST-CUT, minimal bar)",
        "  A member is DONE iff its deterministic committed-source predicate holds.",
        "  FULL beta-readiness ALSO requires: full-suite-green + experimental release",
        "  (outward, human-gated). This scorecard measures the member work only.",
        "=" * 78,
        f"  {'MEMBER':<6} {'STATUS':<6} TITLE",
        "-" * 78,
    ]
    for m, d in rows:
        lines.append(f"  {m.mid:<6} {'DONE' if d else 'OPEN':<6} {m.title}")
        lines.append(f"         [{m.toc_or_friction}] {m.note}")
    lines.append("-" * 78)
    lines.append(f"  EPIC MEMBERS: {done_n}/{total} DONE = {pct}%")
    lines.append(
        "  PRECONDITION full-suite-green: run separately (deliberate, pgrep-first)"
    )
    lines.append("=" * 78)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()
    rows = _evaluate()
    done_n = sum(1 for _, d in rows if d)
    total = len(rows)
    if args.json:
        print(
            json.dumps(
                {
                    "epic": "atdd-pure-beta-readiness",
                    "bar": "minimal (first-cut, Ale-ratify)",
                    "members_done": done_n,
                    "members_total": total,
                    "members": [
                        {"id": m.mid, "title": m.title, "done": d, "note": m.note}
                        for m, d in rows
                    ],
                }
            )
        )
    else:
        print(_render_text(rows))
    # Exit 0 = all members done; 1 = work remains (fail-closed default).
    return 0 if done_n == total else 1


if __name__ == "__main__":
    sys.exit(main())
