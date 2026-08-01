#!/usr/bin/env python3
"""THE GOAL CONTRACT (FIRST-CUT) for the ratified production-readiness roadmap
E1-E12 (`docs/product/roadmap.md`, Ale-ratified 2026-06-10).

THIS SCRIPT *IS* THE MEASUREMENT AND THE DEFINITION OF DONE for "implementa
tutte le fasi ricorsivamente" at EPIC granularity. Same committed code + same
local attestation state -> same number; a change to the measure is a reviewed
git diff (the metric cannot drift silently). Fail-closed: unknown = NOT DONE.

MODEL (per the objective-progress standing rule, 2026-06-15):
    ROADMAP -> EPIC (E1..E12) -> MEMBER
Each epic decomposes into MEMBERS of four kinds, each with a deterministic
predicate:

  * ("flow-v2-epic",)            -> delegates to scripts/flow_v2_closure_scorecard.py
                                    (the committed flow-v2 SSOT); DONE iff that
                                    scorecard reports every feature DONE.
  * ("beta", "<MEMBER-ID>")      -> delegates to scripts/beta_consolidation_scorecard.py;
                                    DONE iff that scorecard reports the member DONE.
  * ("ledger-feature", "<id>")   -> DONE iff a REAL feature-end record
                                    (FeatureEndReviewVerdict / EBatchRefactorCompleted
                                    as the EVENT TYPE, feature_id on the SAME record)
                                    exists in the local AT-completion ledger
                                    (.nwave/telemetry/atdd-pure/ -- intentionally
                                    local runtime telemetry, process-reproducible,
                                    NOT bare-clone-state-reproducible; same scope
                                    note as flow_v2_closure_scorecard.py).
  * ("friction-zero",)           -> DONE iff docs/product/backlog.md contains ZERO
                                    `### F-*` entries whose Status line says OPEN /
                                    INVESTIGATING (the dogfood-friction burn-down
                                    contract: every dogfood friction is a
                                    PRR-blocker; the count must reach 0).
  * ("to-design", "<id>")        -> ALWAYS NOT DONE. Known-but-undesigned work
                                    counted in the denominator from day one; the
                                    denominator grows only when we DISCOVER work,
                                    never shrinks to hide it.

EPIC DONE <=> every member DONE. E6 is NON-GATING (Ale 2026-06-10: acceleration
is milestone (b), outside the publish-gate sigma) -- reported, excluded from the
gating headline.

Pure stdlib. Usage:
    python scripts/roadmap_e1_e12_closure_scorecard.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


# Expose ``src/`` so ``des`` resolves under a bare ``python3`` (this script
# runs outside the uv venv as a ``language: system`` hook / ad-hoc tool).
# Guarded: ``src/`` exists only in the dev repo -- in an installed layout
# ``des`` is already importable and this is a no-op.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from des.domain.telemetry_paths import LedgerFamily  # noqa: E402
from des.domain.telemetry_paths import ledger_dir as _ledger_dir  # noqa: E402


REPO = Path(__file__).resolve().parents[1]
LEDGER_DIR = _ledger_dir(REPO, LedgerFamily.ATDD_PURE)
BACKLOG = REPO / "docs" / "product" / "backlog.md"

# ---------------------------------------------------------------------------
# The ratified epic inventory (roadmap.md section 1), decomposed into members.
# Member ids for ("to-design", ...) name the roadmap F-id (or the honest gap)
# so the row is traceable back to the plan SSOT.
# ---------------------------------------------------------------------------
EPICS = [
    {
        "id": "E1",
        "title": "Hook-side spine A->G enforcement (D1)",
        "gating": True,
        "members": [
            # wave-floor auto-close: the shipped hook-side keystone the beta
            # scorecard already measures mechanically.
            ("beta", "C4"),
            # roadmap F-id, not yet designed/attested as a sealed feature:
            ("to-design", "f-oss-mechanical-hmac-trailer-hook-derivation"),
            # the D1 48->~80 remainder: a non-Lyra user dispatches A->G hands-off.
            ("to-design", "f-hands-off-a-to-g-dispatch"),
        ],
    },
    {
        "id": "E2",
        "title": "flow-v2 manifest + gate-G (self-defending design<->AT) (D3)",
        "gating": True,
        "members": [
            # realized as this sealed flow-v2 feature (gate-design-at-coherence).
            ("ledger-feature", "f-code-design-manifest-and-gate-g"),
        ],
    },
    {
        "id": "E3",
        "title": "flow-v2 wave-migrations (DESIGN/DEVOPS/DISTILL/DELIVER) (D4)",
        "gating": True,
        "members": [("flow-v2-epic",)],
    },
    {
        "id": "E4",
        "title": "Language adapter plugin infrastructure (D8)",
        "gating": True,
        "members": [
            ("beta", "C12"),  # M42 layering fixed
            ("beta", "C13"),  # JS/TS (vitest) run-facet wired
            ("beta", "C14"),  # Go run-facet wired
            ("to-design", "f-language-adapter-e2-agnostic-routing"),
            ("to-design", "f-language-adapter-full-port-unification"),
        ],
    },
    {
        "id": "E5",
        "title": "Gate git-dependency removal (target-machine generality) (D3/D8)",
        "gating": True,
        "members": [
            # seams A+B closed 2026-06-08 pre-scorecard; the honest remaining
            # work per roadmap: seams C/D + commit_slice AD-37/38.
            ("to-design", "f-gate-git-seams-c-d-and-commit-slice-ad37-38"),
        ],
    },
    {
        "id": "E6",
        "title": "Acceleration proven (NON-GATING milestone (b))",
        "gating": False,
        "members": [
            ("to-design", "f-d6-exit-criterion-po-decision (PO-blocked)"),
            ("to-design", "f-atdd-pure-acceleration-pilot"),
        ],
    },
    {
        "id": "E7",
        "title": "Dogfood friction surface burn-down (D5)",
        "gating": True,
        "members": [("friction-zero",)],
    },
    {
        "id": "E8",
        "title": "Config-driven behaviour (D9)",
        "gating": True,
        "members": [("to-design", "f-config-driven-behaviour-audit-and-gate")],
    },
    {
        "id": "E9",
        "title": "Mechanical doc-structure consolidation (D10)",
        "gating": True,
        "members": [("to-design", "f-doc-structure-ssot-and-gate")],
    },
    {
        "id": "E10",
        "title": "Upstream-wave gate-PAIR coverage (D11)",
        "gating": True,
        "members": [
            # pair #2 (DESIGN->DISTILL, gate-G) is realized+wired by E2's sealed
            # feature -- counted THERE, not double-counted here. The remaining
            # three pairs are the honest open members:
            ("to-design", "f-gate-pair-discuss-to-distill"),
            ("to-design", "f-gate-pair-design-to-pbt-density"),
            ("to-design", "f-gate-pair-devops-to-env-matrix"),
        ],
    },
    {
        "id": "E11",
        "title": "Adoption / DX: epic-mode + caveman builder + Ferrari-UX",
        "gating": True,
        "members": [
            # ledger-checked: DONE only when sealed via the spine (fail-closed --
            # skill prose shipped without a feature-end seal does NOT credit).
            ("ledger-feature", "f-discuss-epic-mode"),
            ("ledger-feature", "f-agent-builder-caveman-native"),
            ("to-design", "f-ux-ferrari-as-utilitaria"),
        ],
    },
    {
        "id": "E12",
        "title": "Cross-OS / installer robustness (D1)",
        "gating": True,
        "members": [
            ("to-design", "f-installer-windows-logo-cp1252"),
            ("to-design", "f-rc-real-turn-smoke"),
        ],
    },
]

# ---------------------------------------------------------------------------
# Predicates (all fail-closed)
# ---------------------------------------------------------------------------


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1800)
        return p.returncode, p.stdout + p.stderr
    except Exception:
        return 1, ""


def _flow_v2_all_done() -> tuple[bool, str]:
    code, out = _run([sys.executable, "scripts/flow_v2_closure_scorecard.py"])
    m = re.search(r"EPIC:\s*(\d+)/(\d+)\s+features DONE", out)
    if code != 0 or not m:
        return False, "flow-v2 scorecard unreadable (fail-closed)"
    done, total = int(m.group(1)), int(m.group(2))
    return done == total and total > 0, f"flow-v2 {done}/{total}"


def _beta_member_status() -> dict[str, bool]:
    """Member-id -> DONE map parsed from the beta scorecard's own output."""
    code, out = _run([sys.executable, "scripts/beta_consolidation_scorecard.py"])
    if code != 0 and "EPIC MEMBERS" not in out:
        return {}
    status: dict[str, bool] = {}
    for line in out.splitlines():
        m = re.match(r"\s+([CWP]\d+)\s+\S+(?:-\S+)?\s+(DONE|OPEN)\s", line)
        if m:
            status[m.group(1)] = m.group(2) == "DONE"
    return status


_FEATURE_END_EVENTS = ("FeatureEndReviewVerdict", "EBatchRefactorCompleted")


def _has_feature_end_record(feature_id: str) -> bool:
    """Same honest event-type+feature_id-on-one-record check as flow_v2 (M3)."""
    if not LEDGER_DIR.exists():
        return False
    event_tokens = tuple(f'"event":"{e}"' for e in _FEATURE_END_EVENTS) + tuple(
        f'"event": "{e}"' for e in _FEATURE_END_EVENTS
    )
    fid_tokens = (f'"feature_id":"{feature_id}"', f'"feature_id": "{feature_id}"')
    for f in LEDGER_DIR.rglob("*"):
        if not f.is_file():
            continue
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line in txt.splitlines():
            if any(e in line for e in event_tokens) and any(
                t in line for t in fid_tokens
            ):
                return True
    return False


def _open_friction_count() -> int:
    """Count `### F-*` backlog entries whose Status is OPEN/INVESTIGATING.

    Fail-closed: unreadable backlog -> a large sentinel (never a silent zero).
    """
    try:
        text = BACKLOG.read_text(encoding="utf-8")
    except Exception:
        return 9999
    count = 0
    blocks = re.split(r"^### ", text, flags=re.M)
    for block in blocks[1:]:
        header = block.splitlines()[0] if block.splitlines() else ""
        if not header.startswith("F-"):
            continue
        m = re.search(r"^Status:\s*\*{0,2}([A-Z-]+)", block, flags=re.M)
        if m and m.group(1).rstrip("-") in ("OPEN", "INVESTIGATING", "CRITICAL"):
            count += 1
        elif m is None:
            count += 1  # fail-closed: no Status line -> counts as open
    return count


def main() -> int:
    beta = _beta_member_status()
    flow_ok, flow_detail = _flow_v2_all_done()
    friction_open = _open_friction_count()

    print("=" * 78)
    print("roadmap E1-E12 -- GOAL CONTRACT (FIRST-CUT)")
    print("  An epic is DONE iff every member's deterministic predicate holds.")
    print("  to-design members ALWAYS count open (denominator never hides work).")
    print("  Fail-closed: unknown/unreadable = NOT DONE.")
    print("=" * 78)

    epics_done = 0
    gating_total = 0
    members_done = 0
    members_total = 0

    for epic in EPICS:
        rows: list[tuple[str, bool, str]] = []
        for member in epic["members"]:
            kind = member[0]
            if kind == "flow-v2-epic":
                ok, detail = flow_ok, flow_detail
                label = "flow-v2 epic (delegated scorecard)"
            elif kind == "beta":
                mid = member[1]
                ok = beta.get(mid, False)
                detail = f"beta member {mid}" + ("" if mid in beta else " UNPARSED")
                label = f"beta:{mid}"
            elif kind == "ledger-feature":
                fid = member[1]
                ok = _has_feature_end_record(fid)
                detail = "feature-end record" + ("" if ok else " ABSENT")
                label = fid
            elif kind == "friction-zero":
                ok = friction_open == 0
                detail = f"open frictions = {friction_open} (target 0)"
                label = "dogfood-friction-surface == 0"
            elif kind == "to-design":
                ok = False
                detail = "not yet designed/sealed"
                label = member[1]
            else:  # unknown member kind: fail-closed
                ok, detail, label = False, "unknown member kind", str(member)
            rows.append((label, ok, detail))

        epic_done = all(ok for _, ok, _ in rows)
        if epic["gating"]:
            gating_total += 1
            if epic_done:
                epics_done += 1
        members_total += len(rows)
        members_done += sum(1 for _, ok, _ in rows if ok)

        gate_tag = "" if epic["gating"] else "  [NON-GATING]"
        print(
            f"\n  {epic['id']:4s} {'DONE' if epic_done else 'OPEN':4s}"
            f"  {epic['title']}{gate_tag}"
        )
        for label, ok, detail in rows:
            print(f"        [{'x' if ok else ' '}] {label}  -- {detail}")

    print("-" * 78)
    print(f"  GATING EPICS: {epics_done}/{gating_total} DONE")
    print(f"  MEMBERS (all epics incl. non-gating): {members_done}/{members_total}")
    print("  PRECONDITION full-suite-green: run separately (pytest whole tree)")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
