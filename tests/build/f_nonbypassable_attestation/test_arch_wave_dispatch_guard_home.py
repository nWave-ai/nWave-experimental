"""AT-A7b (slice-05, DDD-8 REGRESSION GUARD): the wave-dispatch guard production
logic lives in the DES runtime (`src/des/**`) and is composed onto `dispatch.pre`
in atdd_pure.yaml -- and there is NO production guard counterpart under `scripts/`.

RE-HOMED (orchestrator augment 2026-06-16): the production wave-dispatch guard is
PRODUCTION RUNTIME enforcement in the DES runtime, NOT a `scripts/`-resident or
hand-placed personal hook (the `des_crafter_dispatch_guard.py` has no repo source --
DDD-8). This arch test reads REPO paths + the flavor YAML as DATA -- no subprocess,
no behavioral execution, no developer-home read.

NOT TAUTOLOGICAL -- a REGRESSION GUARD. It fails LOUD on the EXACT two ways the
re-home could silently regress:
  (a) a future change re-lands the guard policy under `scripts/hooks/` (the
      pre-re-home shape) -- leg 4 catches it (the scripts/ counterpart reappears);
  (b) a future change deletes the `verify-wave-dispatch` row from the
      `dispatch.pre` composition in atdd_pure.yaml (un-wiring the gate) -- leg 3
      catches it (the YAML row vanishes).
Both are real regressions a green-elsewhere suite would otherwise ship silently
(the authored-but-unwired / re-homed-then-reverted class slice-04 + this feature
exist to kill). Recognized as an arch test (`test_arch_` prefix under
`tests/build/`) per the AT-completeness S2 tolerable-variant rule (it introspects
structure; it does not exercise behavior).

ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD neither `src/des/cli/verify_wave_dispatch.py`
nor `src/des/domain/wave_dispatch_guard_policy.py` exists, and atdd_pure.yaml carries
no `verify-wave-dispatch` row. Legs 1/2/3 RED-fail with semantic AssertionErrors on
the absent artifacts; leg 4 (no scripts/ counterpart) is GREEN at HEAD and STAYS
GREEN (the regression-guard direction) -- so the file as a whole is RED until DELIVER
ships the runtime guard + wires it.
"""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]  # parents[3] = REPO_ROOT
_GATE_PATH = _REPO_ROOT / "src" / "des" / "cli" / "verify_wave_dispatch.py"
_POLICY_PATH = _REPO_ROOT / "src" / "des" / "domain" / "wave_dispatch_guard_policy.py"
_FLAVOR_PATH = _REPO_ROOT / "nWave" / "flavors" / "atdd_pure.yaml"
_SCRIPTS_HOOKS_DIR = _REPO_ROOT / "scripts" / "hooks"

_DISPATCH_PRE_GATE_ID = "verify-wave-dispatch"


def test_wave_dispatch_gate_lives_in_des_runtime() -> None:
    """AT-A7b leg 1: the `des.cli` gate module ships in the DES runtime (DDD-8)."""
    assert _GATE_PATH.is_file(), (
        "the wave-dispatch guard gate must ship as PRODUCTION RUNTIME code at "
        f"{_GATE_PATH.relative_to(_REPO_ROOT)} (NOT a scripts/-resident or "
        "hand-placed personal hook -- DDD-8); at HEAD it does not exist. GREEN once "
        "DELIVER ships the in-tree gate."
    )


def test_wave_dispatch_policy_lives_in_des_runtime() -> None:
    """AT-A7b leg 2: the pure domain policy ships in the DES runtime (DDD-8)."""
    assert _POLICY_PATH.is_file(), (
        "the wave-dispatch guard policy must ship as PRODUCTION RUNTIME code at "
        f"{_POLICY_PATH.relative_to(_REPO_ROOT)} (a pure domain policy holding the "
        "wave->owner map + DISPATCH_GUARD_VOCABULARY + skip-witness FORM check); at "
        "HEAD it does not exist. GREEN once DELIVER ships the policy."
    )


def test_wave_dispatch_gate_is_composed_on_dispatch_pre() -> None:
    """AT-A7b leg 3: the gate is wired onto `dispatch.pre` in atdd_pure.yaml.

    Reads the flavor YAML as TEXT (DATA) and asserts the `verify-wave-dispatch`
    gate-id appears in the dispatch.pre composition. A future change that deletes
    the row (un-wiring the gate) fails here LOUD -- the re-homed gate must stay
    WIRED, not just exist.
    """
    assert _FLAVOR_PATH.is_file(), (
        f"the atdd_pure flavor must exist at {_FLAVOR_PATH.relative_to(_REPO_ROOT)}"
    )
    text = _FLAVOR_PATH.read_text(encoding="utf-8")
    assert _DISPATCH_PRE_GATE_ID in text, (
        f"the {_DISPATCH_PRE_GATE_ID!r} gate must be composed onto the dispatch.pre "
        f"lifecycle event in {_FLAVOR_PATH.relative_to(_REPO_ROOT)} so the in-tree "
        "guard auto-fires on every Agent/Task dispatch the intercept sees (DDD-8); "
        "at HEAD no such row exists. GREEN once DELIVER adds the dispatch.pre row. "
        "(Regression guard: deleting this row un-wires the gate and re-fails here.)"
    )


def test_no_scripts_resident_wave_dispatch_guard_counterpart() -> None:
    """AT-A7b leg 4: NO production guard counterpart under scripts/hooks/.

    REGRESSION-GUARD direction (GREEN at HEAD, must STAY GREEN): a future change
    re-landing the guard policy under scripts/ (the pre-re-home shape DDD-8
    supersedes) reappears here and fails LOUD. `scripts/` is dev-only; the
    production guard ships exclusively in the DES runtime.
    """
    if not _SCRIPTS_HOOKS_DIR.is_dir():
        return  # no scripts/hooks dir -> trivially no counterpart
    counterparts = [
        p for p in _SCRIPTS_HOOKS_DIR.rglob("*.py") if "wave_dispatch" in p.name
    ]
    assert not counterparts, (
        "the wave-dispatch guard production logic MUST live in src/des/** ONLY -- "
        "NO production guard counterpart may ship under scripts/hooks/ (DDD-8: "
        "scripts/ is dev-only, the guard ships to users via the DES runtime). "
        f"Found scripts/-resident counterpart(s): "
        f"{[str(p.relative_to(_REPO_ROOT)) for p in counterparts]}."
    )
