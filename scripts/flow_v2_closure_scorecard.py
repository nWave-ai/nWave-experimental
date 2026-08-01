#!/usr/bin/env python3
"""THE GOAL CONTRACT for the `flow-v2-wave-migrations` epic (Ale 2026-06-15).

THIS SCRIPT *IS* THE MEASUREMENT AND THE DEFINITION OF DONE. The score does not
depend on anyone's word — only on this committed code running deterministic,
fail-closed checks. Same code + same repo state -> same number. If a check
changes it is a reviewable git diff (the metric cannot drift silently).

REPRODUCIBILITY SCOPE (Ale 2026-06-20, after an independent audit swarm flagged
it): the attestation ledger this scorecard reads (`.nwave/telemetry/atdd-pure/
*.jsonl`) is INTENTIONALLY local runtime telemetry — `.gitignore`d, NOT committed
(telemetry/evidence stays out of the source tree). So this scorecard measures the
LOCAL machine's attestation state. A bare clone scores 0/N by design: it has not
run the gates yet. The contract is PROCESS-reproducible (re-run the gates on the
same code -> same verdicts -> same number), NOT bare-clone-STATE-reproducible. CI
re-derives the closure by re-running the gates, never by reading committed ledger
state. "Same repo state -> same number" therefore means: same code + same *local
attestation runs*.

UNIT OF MEASURE = the FEATURE, inside the EPIC (Ale 2026-06-15: "la slice e'
troppo fine, esclude il lavoro non ancora affettato"). Hierarchy:
    EPIC  ->  FEATURE (the unit that captures ALL known work, designed or not)
          ->  SLICE   (sub-unit; exists only after DESIGN)

A FEATURE is DONE iff (a) a `FeatureEnd` ledger record attests it, (b) every
ratified slice is attested (delivered >= planned_slices), AND (c) its wired_modules
all resolve. The FeatureEnd record alone is NOT sufficient: the M1 audit (2026-06-19)
found FeatureEnd records on features with 0/N or partial SliceCommitVerified (the
feature-end cycle's "all slices delivered" precondition was not, in practice, a
guarantee the scorecard could lean on). So the scorecard re-checks delivery itself:
  * undesigned feature  -> can never be DONE (no feature-end possible)  -> counts
    in the denominator from day one (nothing hidden; the denominator grows only
    if we DISCOVER new work, never shrinks to hide known work).
  * delivered-but-unattested feature -> NOT DONE until feature-end runs.
  * feature-end-but-slices-unattested (delivered < planned) -> NOT DONE (M1).
    If planned_slices was an over-count, correct planned_slices, never credit
    done-with-fewer.

EPIC DONE  <=>  every feature has a FeatureEnd record AND delivered>=planned AND wired.

Pure stdlib only (target-machine-independence). Fail-closed: unknown = NOT DONE.

Usage:
    python scripts/flow_v2_closure_scorecard.py
    python scripts/flow_v2_closure_scorecard.py --with-suite   # also runs pytest
"""

from __future__ import annotations

import argparse
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

from des.domain.repo_path_resolver import feature_delta_path  # noqa: E402
from des.domain.telemetry_paths import LedgerFamily  # noqa: E402
from des.domain.telemetry_paths import ledger_dir as _ledger_dir  # noqa: E402


REPO = Path(__file__).resolve().parents[1]
# The AT-completion ledger SSOT — the SAME directory the real done-gate reads
# (verify_deliver_integrity.py:182) and the writer emits to
# (at_completion_ledger.py:316). `.nwave/des/logs/` holds only audit logs, NOT
# the per-feature attestation records, so reading it could never detect a
# FeatureEnd (the iter-2 bug: scorecard reported 0/N regardless of reality).
LEDGER_DIR = _ledger_dir(REPO, LedgerFamily.ATDD_PURE)

# Wiring = a FIRING surface (the wave-contract registry gate-stacks + flavor
# gate-stacks + hooks). NOT the catalog (that is the registry of CLI subcommands,
# not a firing surface — counting it was the iter-1 bug). nWave/waves/*.yaml is
# the canonical wave-contract registry (ADR-FLOW-006 D6) — the SOLE gate-stack
# source the spine resolves; it is added here so a gate wired into the registry
# (not the dormant flavor block) is seen. The flavor-string-regex floor (`_term_
# wired`) over this surface is NOT enough for the gate-stack class — see
# `_live_resolved` + `_module_wired` (f-distill-wiring-to-registry DDD-7): a gate
# must LIVE-resolve, not merely appear as a string, or a dead block false-credits.
WIRING_FILES = [
    *sorted((REPO / "nWave" / "waves").glob("*.yaml")),
    *sorted((REPO / "nWave" / "flavors").glob("*.yaml")),
    *sorted(Path.home().glob(".claude/hooks/*.py")),
    *sorted((REPO / "scripts" / "hooks").glob("*.py")),
]

# The EPIC decomposed into FEATURES. `planned_slices` is the ratified slice count
# (None = not yet designed, so unsliceable — phase stays "to-design"). `dir` is
# the feature-delta directory (None for synthetic not-yet-created features).
# `wired_modules` lists des subcommands the feature must leave registered+wired
# for its feature-end to honestly pass.
FEATURES = [
    {
        # The keystone (epic feature #1) — CLOSED at feature-end 2026-06-14
        # (FeatureEnd record present). It was wrongly omitted from this list,
        # which both hid a real DONE and shrank the denominator; restored here
        # per the contract ("never hide known work" — DONE work included).
        "id": "f-design-wave-migration",
        "dir": "f-design-wave-migration",
        # 3->4 (audit 2026-06-20, swarm T2): the feature-delta `[REF] Slice Plan`
        # ratifies 4 slices (3 soft-gate + slice-04 removal-only @infrastructure,
        # which ships real @slice-04 .feature scenarios). planned_slices was an
        # UNDER-count that false-credited 3/3 DONE; corrected UPWARD (the honest
        # direction -- never down to hide work). All 4 are bundle-attested.
        "planned_slices": 4,
        "wired_modules": [],
    },
    {
        "id": "f-distill-wave-migration",
        "dir": "f-distill-wave-migration",
        "planned_slices": 3,
        "wired_modules": [],
    },
    {
        "id": "f-devops-wave-migration",
        "dir": "f-devops-wave-migration",
        "planned_slices": 3,
        "wired_modules": [],
    },
    {
        "id": "f-deliver-wave-migration",
        "dir": "f-deliver-wave-migration",
        "planned_slices": 3,
        "wired_modules": [],
    },
    {
        "id": "f-declarative-gate-composition",
        "dir": "f-declarative-gate-composition",
        "planned_slices": 1,
        "wired_modules": [],
    },
    {
        "id": "f-coherence-and-attestation",
        "dir": "f-coherence-and-attestation",
        "planned_slices": 6,
        # gate-g renamed -> gate-design-at-coherence by f-code-design-manifest-and
        # -gate-g slice-04 (DDD-5); all three now LIVE-resolve from the DISTILL
        # gate-out registry (f-distill-wiring-to-registry DDD-1/DDD-7), so this
        # row is honestly wired, not false-credited via the dormant flavor block.
        "wired_modules": ["gate-design-at-coherence", "self-attest", "test-runner"],
    },
    {
        "id": "fix-readiness-gate-reuse-first-invariant",
        "dir": "fix-readiness-gate-reuse-first-invariant",
        "planned_slices": 2,
        "wired_modules": [],
    },
    {
        "id": "fix-wave-bypass-recovery-truthful",
        "dir": "fix-wave-bypass-recovery-truthful",
        "planned_slices": 2,
        "wired_modules": [],
    },
    {
        "id": "f-nonbypassable-attestation",
        "_planned_slices_note": "5->6 2026-06-16: slice-05 split into 05a (guard verdicts) + 05b (skip-authorization) — 10 scenarios exceeded carpaccio ceiling 5 (AT-review HIGH); split preserves coverage",
        "dir": "f-nonbypassable-attestation",
        "planned_slices": 6,
        # audit 2026-06-19: delivers verify-wave-dispatch, wired live in the
        # atdd_pure flavor dispatch.pre surface (a flavor dispatch hook IS a firing
        # surface -> _term_wired floor, not a wave gate-out resolve_stack entry).
        "wired_modules": ["verify-wave-dispatch"],
    },
    # Designed 2026-06-15 (review Opus indep. APPROVED) — the former 2 synthetic
    # "to-design" entries became concrete features (#10 split into F1+F2), plus
    # §2B (f-spine-runs-tests) added by Ale. Denominator grew 10 -> 12 (honest:
    # designed/discovered work, never shrunk to hide). DELIVER sequences after #8.
    {
        "id": "f-design-devops-review-gate",
        "dir": "f-design-devops-review-gate",
        "planned_slices": 3,
        # audit 2026-06-19: delivers verify-design-review (design gate-out) +
        # verify-devops-review (devops gate-out); both LIVE-resolve. Empty would
        # credit wired trivially -- now genuinely checked.
        "wired_modules": ["verify-design-review", "verify-devops-review"],
    },
    {
        "id": "f-code-design-manifest-and-gate-g",
        "dir": "f-code-design-manifest-and-gate-g",
        "planned_slices": 4,
        # DDD-5: this feature renames + wires gate-g -> gate-design-at-coherence
        # into the DISTILL gate-out registry. The honest wiring check requires it
        # to LIVE-resolve there (not merely be catalogued) -- the M2 class the
        # audit hardened. Empty would credit modules_wired=all([])=True trivially.
        "wired_modules": ["gate-design-at-coherence"],
    },
    {
        "id": "f-deliver-entry-contract-freeze",
        "dir": "f-deliver-entry-contract-freeze",
        "planned_slices": 3,
        # audit 2026-06-19 FALSE-DONE EXPOSED: delivers verify-deliver-entry-contract
        # but it is catalogued + in `des --help` ONLY -- 0 occurrences in any wave /
        # flavor / hook (no deliver.yaml exists; not in atdd_pure dispatch.pre). The
        # gate never FIRES -> NOT honestly DONE until wired. (catalogued != wired.)
        "wired_modules": ["verify-deliver-entry-contract"],
    },
    {
        "id": "f-spine-runs-tests-not-git-hooks",
        "dir": "f-spine-runs-tests-not-git-hooks",
        "planned_slices": 4,
        # audit 2026-06-19 exposed FALSE-DONE: run-slice-ats was catalogued +
        # crafter-skill PROSE only, the hook script untracked + uninstalled.
        # REMEDIATED 2026-06-20 (swarm T4): the commit-msg hook is now committed +
        # wired into .pre-commit-config.yaml as an installed entry, and the wired
        # check gained `_hook_installed` (above) so file-presence alone no longer
        # credits -- the install manifest entry is now required. (catalogued != wired.)
        "wired_modules": ["run-slice-ats"],
    },
    # Designed 2026-06-17 (ADR-FLOW-006; review Opus iter-2 APPROVED). The
    # canonical wave-contract registry substrate (gates-ref/outputs-ref + the two
    # SSOTs: gate_stack + output_contract); DISCUSS is its worked example. Newly
    # DISCOVERED work -> denominator grows 13 -> 14 (never shrinks to hide known
    # work). DONE requires the coherence-check gate registered+wired.
    {
        "id": "f-wave-contract-coherence",
        "dir": "f-wave-contract-coherence",
        "planned_slices": 7,
        "wired_modules": ["verify-wave-contract-coherence"],
    },
    # DISCOVERED 2026-06-19 by the adversarial audit: the honest fix for the
    # f-coherence false-credit (M1 done-formula + M2 live-resolution + the genuine
    # wiring of self-attest + verify-test-runner into the registry, killing the
    # dormant flavor block). THIS is the feature that FORCES honest closure — it
    # hardens the very measure (M1/M2) and eats its own dogfood: its wired_modules
    # are the two gates it wired, so its DONE mechanically witnesses its deliverable
    # via the tightened _live_resolved. Newly discovered work -> denominator 14 -> 15
    # (never shrinks to hide known work). slice-01 SHIPPED+attested (cbf882696);
    # slice-02 reconciles the cross-feature AT-15 (f-wave) + coherence_codefact.
    {
        "id": "f-distill-wiring-to-registry",
        "dir": "f-distill-wiring-to-registry",
        "planned_slices": 2,
        "wired_modules": ["self-attest", "test-runner"],
    },
]


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=1800)
        return p.returncode, p.stdout + p.stderr
    except Exception:
        return 1, ""


def _des_subcommands() -> set[str]:
    code, out = _run(["uv", "run", "python", "-m", "des", "--help"])
    if code != 0:
        return set()
    return {
        m.strip()
        for line in out.splitlines()
        for m in re.findall(r"^\s+([a-z][a-z0-9-]+)\b", line)
    }


def _term_wired(pattern: str) -> bool:
    rx = re.compile(pattern)
    for f in WIRING_FILES:
        try:
            if rx.search(f.read_text(encoding="utf-8", errors="ignore")):
                return True
        except Exception:
            continue
    return False


def _ledger_files() -> list[Path]:
    return (
        [f for f in LEDGER_DIR.rglob("*") if f.is_file()] if LEDGER_DIR.exists() else []
    )


def _ledger_has(*terms: str) -> bool:
    for f in _ledger_files():
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if all(t in txt for t in terms):
            return True
    return False


# The real feature-end attestation events. A feature is feature-end-attested iff
# ONE of these appears as the EVENT TYPE on a single ledger RECORD scoped to the
# feature_id -- never a prose substring.
_FEATURE_END_EVENTS = ("FeatureEndReviewVerdict", "EBatchRefactorCompleted")


def _has_feature_end_record(feature_id: str) -> bool:
    """True iff a REAL feature-end record exists for ``feature_id``.

    M3 (audit 2026-06-19): the prior check ``_ledger_has(fid, "FeatureEnd")``
    substring-matched the word "FeatureEnd" ANYWHERE in the feature's ledger
    corpus -- including a reviewer's ``findings_summary`` prose (e.g. "f-wave
    STAYS DONE ... FeatureEnd 63dc27bf intact"). That false-credited a feature
    DONE before its real feature-end ran (same class as M1/M2). The honest check
    matches the EVENT-TYPE field (``"event":"FeatureEndReviewVerdict"`` /
    ``EBatchRefactorCompleted``) together with the ``feature_id`` field on the
    SAME ledger RECORD (one JSONL line) -- a prose mention can no longer credit.
    Fail-closed: unreadable ledger -> not attested.
    """
    event_tokens = tuple(f'"event":"{e}"' for e in _FEATURE_END_EVENTS) + tuple(
        f'"event": "{e}"' for e in _FEATURE_END_EVENTS
    )
    fid_tokens = (f'"feature_id":"{feature_id}"', f'"feature_id": "{feature_id}"')
    for f in _ledger_files():
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


def _slice_commits_verified(feature_id: str) -> int:
    """Count distinct slice-ids with a SliceCommitVerified record (fail-closed 0)."""
    slices: set[str] = set()
    for f in _ledger_files():
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line in txt.splitlines():
            if feature_id in line and "SliceCommitVerified" in line:
                slices.update(re.findall(r"slice-\d+[a-z]?", line))
    return len(slices)


def _live_resolved(wave: str, boundary: str, gate_id: str) -> bool | None:
    """True/False iff ``gate_id`` LIVE-resolves on the ``wave``/``boundary`` gate
    stack; ``None`` iff the wave-contract registry directory itself could not be
    verified (RCA fix-installed-waves-registry-silent-empty §6.3 "third
    consumer, do not miss it").

    The un-gameable wiring check (f-distill-wiring-to-registry DDD-7): drives the
    REAL in-tree spine resolver ``wave_gate_stack_dispatch.resolve_stack`` over the
    canonical wave-contract registry (``nWave/waves/<wave>.yaml``, the SOLE
    gate-stack source, ADR-FLOW-006 D6). A gate present only as a flavor / hook
    string but ABSENT from the resolved stack returns False -- so a dead flavor
    block can no longer false-credit a gate-stack module wired. Pure in-repo
    Python, no subprocess (consistent with target-machine-independence: the
    scorecard already shells ``des --help``; importing the in-tree resolver is the
    same in-repo mechanism). Fail-closed on a genuine import / resolve error ->
    False -- but an INDETERMINATE resolution (the registry directory could not be
    read at all) is NEVER collapsed into that SAME False: scoring "could not
    verify" as "not wired" would silently understate epic closure, the identical
    defect class this scorecard exists to catch, one layer out.
    """
    try:
        repo_src = REPO / "src"
        if str(repo_src) not in sys.path:
            sys.path.insert(0, str(repo_src))
        from des.application.wave_gate_stack_dispatch import resolve_stack

        result = resolve_stack(wave, boundary)
        if getattr(result, "indeterminate", None) is not None:
            return None
        rows = getattr(result, "rows", result)
        return any(str(r.get("gate_id")) == gate_id for r in rows)
    except Exception:
        return False


# The gate-stack-class wired modules (DDD-7): for these, "wired" demands LIVE
# resolution on the DISTILL gate-out stack, not merely a WIRING_FILES string
# match. Each value is the gate_id as it resolves in nWave/waves/distill.yaml.
# Hook-wired modules (a hook IS a firing surface) legitimately stay on the
# `_term_wired` floor and are NOT listed here.
_GATE_STACK_LIVE_RESOLVED = {
    "gate-design-at-coherence": ("distill", "gate-out", "gate-design-at-coherence"),
    "self-attest": ("distill", "gate-out", "self-attest"),
    "test-runner": ("distill", "gate-out", "verify-test-runner"),
    # f-design-devops-review-gate's two gates live-resolve on their own wave
    # gate-out stacks (audit 2026-06-19): a WIRING_FILES string alone would not
    # prove they FIRE -- the un-gameable check is resolve_stack membership.
    "verify-design-review": ("design", "gate-out", "verify-design-review"),
    "verify-devops-review": ("devops", "gate-out", "verify-devops-review"),
}

# Hook-class modules whose firing surface is an INSTALLED git hook, not a wave
# gate-stack. The honest signal is the `.pre-commit-config.yaml` ENTRY that
# installs the hook -- NOT the mere presence of the hook .py file in
# scripts/hooks/ (audit 2026-06-20, swarm T4 FALSE-DONE: an untracked,
# uninstalled hook file false-credited `_term_wired` via the scripts/hooks glob).
# Value = the hook-script basename the install manifest must reference as an entry.
_HOOK_INSTALLED = {
    "run-slice-ats": "run_slice_ats_precommit",
}


def _hook_installed(token: str) -> bool:
    """True iff `.pre-commit-config.yaml` installs a hook whose entry names `token`.

    Reads the install manifest and requires an `entry:` line referencing the hook
    script basename -- a comment mentioning the subcommand (or the hook .py file
    merely existing on disk) does NOT count. Fail-closed on read error.
    """
    cfg = REPO / ".pre-commit-config.yaml"
    try:
        for line in cfg.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("entry:") and token in stripped:
                return True
    except Exception:
        return False
    return False


def _module_wired(subs: set[str], module: str) -> bool | None:
    sub = {
        "gate-design-at-coherence": "gate-design-at-coherence",
        "self-attest": "self-attest",
        "test-runner": "verify-test-runner",
    }.get(module, module)
    patt = {
        "gate-design-at-coherence": r"gate.?design.?at.?coherence",
        "self-attest": r"self.?attest|self_attest",
        "test-runner": r"test.?runner|test_runner",
    }.get(module, re.escape(module))
    if not ((sub in subs) and _term_wired(patt)):
        return False
    # Gate-stack class (DDD-7): AND a LIVE-resolution check so a dormant flavor /
    # hook string cannot false-credit.
    live = _GATE_STACK_LIVE_RESOLVED.get(module)
    if live is not None:
        return _live_resolved(*live)
    # Hook class (audit 2026-06-20, swarm T4): AND an install check so a hook .py
    # file present on disk but NOT wired into .pre-commit-config.yaml cannot
    # false-credit (catalogued != wired, one layer below the gate-stack class).
    hook_token = _HOOK_INSTALLED.get(module)
    if hook_token is not None:
        return _hook_installed(hook_token)
    return True


def assess(feat: dict, subs: set[str]) -> dict:
    fid = feat["id"]
    designed = bool(feat["dir"]) and feature_delta_path(REPO, feat["dir"]).exists()
    feature_end = _has_feature_end_record(fid)
    delivered = _slice_commits_verified(fid)
    modules_wired = all(_module_wired(subs, m) for m in feat["wired_modules"])
    # M1 (audit 2026-06-19): DONE requires EVERY ratified slice attested
    # (delivered >= planned). The prior formula credited DONE on a FeatureEnd
    # record alone, ignoring `delivered` — so a feature with 0/N or partial
    # SliceCommitVerified was falsely DONE (the docstring contract: "no
    # SliceCommitVerified -> NOT done"). If `planned_slices` was an over-count,
    # the honest fix is to correct planned_slices, not to credit done-with-fewer.
    fully_delivered = (
        feat["planned_slices"] is not None and delivered >= feat["planned_slices"]
    )

    if not designed and feat["planned_slices"] is None:
        phase = "to-design"
    elif feature_end and modules_wired and fully_delivered:
        phase = "DONE"
    elif delivered > 0:
        phase = "delivering"
    elif designed:
        phase = "designed"
    else:
        phase = "to-design"

    done = bool(feature_end and modules_wired and fully_delivered)
    return {
        "id": fid,
        "phase": phase,
        "delivered": delivered,
        "planned": feat["planned_slices"],
        "feature_end": feature_end,
        "modules_wired": modules_wired if feat["wired_modules"] else None,
        "done": done,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--with-suite", action="store_true", help="also run pytest (slow)")
    args = ap.parse_args()

    subs = _des_subcommands()
    rows = [assess(f, subs) for f in FEATURES]
    done = sum(1 for r in rows if r["done"])
    total = len(rows)

    print("=" * 78)
    print("flow-v2-wave-migrations — GOAL CONTRACT (EPIC -> FEATURE -> SLICE)")
    print("  A feature is DONE iff FeatureEnd record AND delivered>=planned AND wired")
    print("  (which requires: all slices delivered + suite green + modules wired).")
    print("=" * 78)
    print(f"  {'FEATURE':<52}{'PHASE':<12}{'SLICES':<8}DONE")
    print("-" * 78)
    for r in rows:
        sl = f"{r['delivered']}/{r['planned']}" if r["planned"] is not None else "—/?"
        wire = (
            ""
            if r["modules_wired"] is None
            else (" wired" if r["modules_wired"] else " UNWIRED")
        )
        print(
            f"  {r['id']:<52}{r['phase']:<12}{sl:<8}{'YES' if r['done'] else 'no'}{wire}"
        )
    print("-" * 78)
    pct = round(100 * done / total) if total else 0
    print(f"  EPIC: {done}/{total} features DONE = {pct}%")

    # Global precondition (not a feature): the full suite must be green.
    if args.with_suite:
        code, _ = _run(["uv", "run", "python", "-m", "pytest", "tests/", "-q"])
        print(f"  PRECONDITION full-suite-green: {'PASS' if code == 0 else 'FAIL'}")
    else:
        print("  PRECONDITION full-suite-green: (run with --with-suite)")
    print("=" * 78)
    return 0 if done == total else 1


if __name__ == "__main__":
    sys.exit(main())
