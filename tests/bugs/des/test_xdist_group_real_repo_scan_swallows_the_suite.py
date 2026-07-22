"""Regression AT -- the `real_repo_scan` xdist_group must not swallow the
majority of the full-suite wall-clock budget, the isolation it substitutes
for must stay wired, and its detector must not false-positive on ordinary
`cwd`-bookkeeping code that never touches the real repo.

CURRENT DETECTOR MECHANIC (`tests/conftest.py`, read live before editing this
docstring -- do not let these line numbers go stale again):

    `pytest_collection_modifyitems` (`tests/conftest.py:1664`) pins every
    collected item for which `_item_depends_on_real_repo()`
    (`tests/conftest.py:1599`) returns `True` onto
    `pytest.mark.xdist_group("real_repo_scan")` (the `add_marker` call at
    `tests/conftest.py:1748`). Under `--dist loadgroup` every member of a
    group runs on ONE worker, serialized.

    `_item_depends_on_real_repo()` / `_compute_item_depends_on_real_repo()`
    (`tests/conftest.py:1627`) walk an IMPORT-GRAPH CLOSURE: the item's own
    test module, the `conftest.py` chain pytest applies to it, and every
    local module transitively imported from those roots -- confined to the
    `tests/` tree (never following into `src/`, where a real subprocess
    `cwd=Path.cwd()` call is normal production behaviour, not a signal). This
    REPLACED an earlier directory-glob expansion (one matching
    `*composition*.py`/`*steps*/` sibling pinned its whole directory,
    ~8.3x over-pinning) -- see git history around commit range
    `d99b7ab9b`..`7cbcdbc16` for the migration. Import-reachability is the
    load-bearing property: a test can only touch the shared `.nwave` state
    through code it actually imports.

    The leaf-level test is `_file_drives_real_repo_cwd()`
    (`tests/conftest.py:1421`), a regex (`_REAL_REPO_CWD_RE`,
    `tests/conftest.py:1397-1408`) over SOURCE TEXT matching the `cwd=`
    keyword argument immediately followed by `REPO_ROOT` / `PROJECT_ROOT` /
    `_repo_root()` / `Path.cwd()` (optionally through `str(...)`).

    The marker exists for a REAL reason (commit 25bc00d35, 2026-06-21): tests
    that drive actual `des` CLI subprocesses with `cwd=<real repo>` share
    mutable `.nwave` state (`.nwave/wave-active/active.json`) across the
    subprocess boundary. Two such tests landing on the same xdist worker can
    collide on that shared on-disk state; serializing them was, and remains,
    correct -- the failure modes below are about the detector's PRECISION
    (over- and under-pinning), never about removing the safety measure
    itself.

WHAT THIS FILE GUARDS -- three parts, deliberately in ONE module so none
gets "fixed" in isolation from the others:

  (a) `test_real_repo_scan_group_does_not_dominate_collected_items` --
      the serialized lane must not silently swallow the majority of the
      suite. Deterministic observable: the FRACTION OF COLLECTED ITEMS
      pinned to the `real_repo_scan` xdist_group (never wall-clock seconds --
      machine-dependent and would itself become a source of flakiness). This
      mirrors exactly what `--dist loadgroup` schedules on: item membership,
      not file count or timing.

      THRESHOLD: 10% of collected items (`unit or integration or acceptance`
      selection). LIVE VALUE AT LAST VERIFICATION (2026-07-20, this bugfix's
      Phase 3a, re-run against the unmodified tree immediately before writing
      this docstring): 826 of 8117 items = 10.18% -- RED against the ceiling
      by a hair, reproduced live by this test on every run, never a
      hardcoded snapshot. The per-item cost-ratio rationale for the 10%
      figure (group items are markedly more expensive than non-group items
      because they spawn subprocesses instead of running in-memory) predates
      the import-graph-closure migration and has not been re-measured since
      -- treat it as the historical justification for WHY 10% and not a
      currently-reproduced number. Bringing the fraction back under ceiling
      is this bugfix's target: tightening `_REAL_REPO_CWD_RE` with a `\\b`
      word-boundary (see part (c)) removes 193 false-positive items,
      independently verified (RCA) to take the fraction to 633/8117 = 7.80%.

  (b) `test_pre_tool_use_service_does_not_honor_des_project_dir_override` --
      whatever bounds or shrinks the group must not silently drop the
      isolation it substitutes for. A change that shrinks the group without
      the underlying `.nwave` state being isolated per-test re-opens the
      EXACT order-dependent corruption 25bc00d35 fixed -- and the symptom is
      flakiness: false reds indistinguishable from real regressions, false
      greens that ship defects.

      NAME IS NOW A MISNOMER -- READ BEFORE "FIXING" IT: this test proves,
      behaviourally (through the real driving port
      `PreToolUseService.validate()`, real `WaveActiveFilesystemStore`, no
      fakes on the seam under test), that the per-test isolation mechanism
      `DES_PROJECT_DIR` / `resolve_nwave_root()` (DDD-14/DDD-15,
      `src/des/domain/nwave_root.py`) IS honoured by
      `PreToolUseService._read_active_wave()`
      (`src/des/application/pre_tool_use_service.py:543` calls
      `resolve_nwave_root()`, not a bare `Path.cwd()`). This was a genuine
      gap when this file was first authored (the docstring at the time
      described it as RED); it was closed by a separate bugfix that wired
      `DES_PROJECT_DIR` isolation into five Tier-1 `.nwave`-root call sites
      (confirmed live: `callers_of resolve_nwave_root` now returns 10
      production call sites, up from the original 2 test-only callers). The
      test now asserts `action == "allow"` and PASSES -- it is a REGRESSION
      GUARD holding that wiring in place, not a proof of an open gap. Do not
      "fix" it by flipping the assertion; if it ever goes red again, the
      isolation wiring regressed and that is the bug to chase.

  (c) `test_cwd_bookkeeping_idiom_does_not_pin_real_repo_scan_group` --
      the detector must not false-positive on the ordinary
      "save cwd, chdir into a hermetic tmp dir, restore after" bookkeeping
      idiom (`prev_cwd = Path.cwd()` / `original_cwd = Path.cwd()` /
      `previous_cwd = Path.cwd()`), which spawns no subprocess and never
      touches the real repo's shared `.nwave` state. `_REAL_REPO_CWD_RE`
      matches the LITERAL substring `cwd` immediately before `=` with no
      left-hand word boundary, so it matches the `cwd` inside `prev_cwd`
      followed by ` = Path.cwd(` -- the RHS `Path.cwd()` call itself
      satisfies one of the regex's own anchor alternatives, so the whole
      idiom self-matches. RCA (2026-07-20) found 43 files carrying this
      false-positive pattern, together responsible for 193 of the 826
      currently-pinned items. This test pins ONE representative case as an
      executable regression guard: RED today (falsely detected as
      real-repo-dependent), and must go GREEN once the detector gains a
      left-hand `\\b` word boundary -- without that fix ever weakening the
      TRUE-positive case (a companion assertion in the same test pins that a
      genuine `cwd=REPO_ROOT`-style call must still be detected).

Neither (a) nor (b) drives a `cwd=<real repo>` subprocess itself (test (a)
collects in-process via a nested `pytest.main()`; test (b) drives the real
filesystem adapter directly and only `chdir`s), and (c) calls the detector
function directly on synthetic source text with no subprocess anywhere --
this file legitimately does not match the detector it exercises, and is not
itself pinned to `real_repo_scan`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.application.pre_tool_use_service import PreToolUseService
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.wave_active import WaveActiveRecord, WaveProvenance
from des.ports.driven_ports.wave_active_store import WaveActiveReader
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput
from des.ports.driver_ports.validator_port import ValidationResult, ValidatorPort


# ---------------------------------------------------------------------------
# (a) speed regression -- the group must not dominate collected items.
# ---------------------------------------------------------------------------

# See module docstring "(a)" for the full derivation of this number from the
# RCA's measured ~26.9x per-item cost ratio between group and non-group items.
_REAL_REPO_SCAN_ITEM_FRACTION_CEILING = 0.10

_FULL_SUITE_MARKER_EXPR = "unit or integration or acceptance"


class _GroupFractionCollector:
    """In-process pytest plugin: counts items pinned to `real_repo_scan`.

    Runs via `pytest.main()` NESTED inside this test's own already-running
    pytest process -- no subprocess, no `cwd=` keyword argument anywhere in
    this call, so this collection pass is NOT itself a `cwd=<real repo>`
    subprocess the detector under test would match.
    """

    def __init__(self) -> None:
        self.total_items: int | None = None
        self.pinned_items: int | None = None

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.total_items = len(session.items)
        self.pinned_items = sum(
            1
            for item in session.items
            if any(
                marker.name == "xdist_group" and marker.args == ("real_repo_scan",)
                for marker in item.iter_markers()
            )
        )


def test_real_repo_scan_group_does_not_dominate_collected_items() -> None:
    """The `real_repo_scan` xdist_group must not exceed 10% of collected items.

    See the module docstring "(a)" for the threshold derivation. This
    re-collects the LIVE suite on every run (never a hardcoded snapshot), so
    it catches both "the group grew back" and "the total suite shrank enough
    that the same absolute group size is now proportionally worse."
    """
    collector = _GroupFractionCollector()
    exit_code = pytest.main(
        ["--collect-only", "-q", "-m", _FULL_SUITE_MARKER_EXPR],
        plugins=[collector],
    )
    assert collector.total_items is not None and collector.total_items > 0, (
        "nested collection produced no items (pytest.main exit_code="
        f"{exit_code!r}) -- cannot evaluate the real_repo_scan weight without "
        "a real collection pass; this is a harness failure, not the defect "
        "under test."
    )

    fraction = collector.pinned_items / collector.total_items

    assert fraction <= _REAL_REPO_SCAN_ITEM_FRACTION_CEILING, (
        f"'real_repo_scan' xdist_group holds {collector.pinned_items} of "
        f"{collector.total_items} collected items ({fraction:.1%}), above the "
        f"{_REAL_REPO_SCAN_ITEM_FRACTION_CEILING:.0%} ceiling. Under `--dist "
        "loadgroup` every member of this group runs on ONE worker, serialized "
        "-- `-n auto` cannot parallelize past this group's own wall time, "
        "which the RCA measured at 84.7% of total suite weight at the "
        "group's CURRENT (larger) size. See the module docstring '(a)' for "
        "the full threshold derivation (the RCA's measured ~26.9x per-item "
        "cost ratio between group and non-group items)."
    )


# ---------------------------------------------------------------------------
# (b) isolation-preservation guard -- whatever replaces the serialization
# must not silently drop the isolation it protects.
# ---------------------------------------------------------------------------


class _UnreachedValidator(ValidatorPort):
    """Classic prompt validator that must never be reached by this path.

    Both the S1 (no-wave, allow) and S2 (wave-active partial-context, block)
    branches under test resolve BEFORE Step 5's `validate_prompt` call
    (`pre_tool_use_service.py` lines ~184-260) -- reaching this is itself a
    sign the test built the wrong scenario, not a legitimate outcome.
    """

    def validate_prompt(self, prompt: str) -> ValidationResult:
        raise AssertionError(
            "classic prompt validation must not be reached by a markerless "
            "partial-context dispatch -- it resolves at S1/S2, before Step 5"
        )


@pytest.mark.negative_at
def test_pre_tool_use_service_does_not_honor_des_project_dir_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`PreToolUseService` must read the wave-active floor from an isolated
    per-test root when `DES_PROJECT_DIR` overrides it -- exactly the
    isolation `resolve_nwave_root()` (DDD-14/15) was built to provide.

    Setup: two real, empty tmp roots. `shared_cwd_root` stands in for the
    REAL repo checkout a `cwd=<real repo>` subprocess test runs against --
    ARMED with an active 'devops' wave floor (mirrors a live/stale floor a
    concurrent dispatch could leave behind). `isolated_root` stands in for
    the per-test tmp dir `DES_PROJECT_DIR` is meant to redirect state into --
    left UNARMED (no floor -> NoWaveActive -> no active wave).
    `DES_PROJECT_DIR` is set to `isolated_root`; the process `chdir`s to
    `shared_cwd_root` (mirrors `subprocess.run(..., cwd=<real repo>)`).

    A markerless-but-partial-context dispatch (`DES-STEP-ID` only, no
    `DES-WAVE`, no `DES-VALIDATION`) is BLOCKED (`WAVE_MARKER_BYPASS`) when
    the active wave is 'devops' (S2 branch), and ALLOWED when no wave is
    active (S1 branch) -- both confirmed by the sibling regression AT
    `test_wave_marker_allows_matching_wave_child_non_atdd_pure.py`
    (scenarios 1-2), which drives the identical composition.

    If `DES_PROJECT_DIR` were honoured, the service would read the UNARMED
    `isolated_root` floor and ALLOW. TODAY it reads the ARMED `shared_cwd_root`
    floor (via bare `Path.cwd()`, `pre_tool_use_service.py:508`) and BLOCKS --
    proving isolation is not wired into this call site. See the module
    docstring '(b)' for why this matters: it is the seam the `real_repo_scan`
    group's serialization currently substitutes for.
    """
    shared_cwd_root = tmp_path / "shared_repo_cwd"
    isolated_root = tmp_path / "isolated_des_project_dir"
    shared_cwd_root.mkdir()
    isolated_root.mkdir()

    store: WaveActiveReader = WaveActiveFilesystemStore()
    assert isinstance(store, WaveActiveFilesystemStore)
    store.arm(
        shared_cwd_root,
        WaveActiveRecord(
            wave="devops", provenance=WaveProvenance.COMMAND, entry_pending=False
        ),
    )
    # isolated_root deliberately left unarmed -- no floor -> NoWaveActive.

    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.chdir(shared_cwd_root)

    service = PreToolUseService(
        marker_parser=DesMarkerParser(),
        prompt_validator=_UnreachedValidator(),
        audit_writer=NullAuditLogWriter(),
        time_provider=SystemTimeProvider(),
        wave_active_reader=WaveActiveFilesystemStore(),
    )
    decision = service.validate(
        PreToolUseInput(
            prompt="<!-- DES-STEP-ID: 01-01 -->\nwork on something",
            subagent_type="child",
            wave_entering=False,
        )
    )

    assert decision.action == "allow", (
        "PreToolUseService._read_active_wave() must honour DES_PROJECT_DIR "
        "(the per-test isolation override) and read the UNARMED isolated "
        "root -- expected action='allow' (S1: no wave active). Observed "
        f"action={decision.action!r} reason={decision.reason!r}: the service "
        "read the ARMED shared cwd floor instead of the isolated root -- "
        "this means `_read_active_wave()` (pre_tool_use_service.py:543) has "
        "REGRESSED to a bare `Path.cwd()` instead of "
        "`resolve_nwave_root()` (it honoured DES_PROJECT_DIR when this test "
        "was last verified GREEN). Until this is re-fixed, the "
        "`real_repo_scan` xdist_group's SERIALIZATION is the ONLY thing "
        "preventing this exact order-dependent collision across xdist "
        "workers -- do not relax or remove that group without restoring "
        "this call site's isolation wiring first (see module docstring "
        "'(b)')."
    )


# ---------------------------------------------------------------------------
# (c) detector-precision guard -- the cwd-bookkeeping idiom must not
# false-positive into the real_repo_scan pin.
# ---------------------------------------------------------------------------

_CWD_BOOKKEEPING_SNIPPET = """
from pathlib import Path


def some_test_helper():
    {var} = Path.cwd()
    try:
        os.chdir(tmp_path)
        do_work()
    finally:
        os.chdir({var})
"""

_GENUINE_REAL_REPO_SUBPROCESS_SNIPPET = """
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def some_test():
    subprocess.run(["des", "status"], cwd=REPO_ROOT, check=True)
"""


@pytest.mark.parametrize(
    "var",
    ["prev_cwd", "original_cwd", "previous_cwd"],
)
def test_cwd_bookkeeping_idiom_does_not_pin_real_repo_scan_group(
    tmp_path: Path, var: str
) -> None:
    """The `real_repo_scan` detector must not false-positive on the ordinary
    save-cwd/chdir/restore bookkeeping idiom -- see module docstring '(c)'.

    Drives the SAME function `pytest_collection_modifyitems`
    (`tests/conftest.py:1664`) calls at its pin site
    (`tests/conftest.py:1747-1748`) -- `_item_depends_on_real_repo()` --
    directly on a synthetic source file containing ONLY the bookkeeping
    idiom (no subprocess `cwd=` call anywhere). If this returns `True`, the
    collection hook pins the item; the assertion below proves it must not.
    """
    import tests.conftest as suite_conftest

    probe_file = tmp_path / f"probe_{var}.py"
    probe_file.write_text(_CWD_BOOKKEEPING_SNIPPET.format(var=var), encoding="utf-8")

    assert suite_conftest._item_depends_on_real_repo(probe_file) is False, (
        f"a file containing only `{var} = Path.cwd()` bookkeeping (save cwd "
        "before chdir-ing into a hermetic tmp dir, restore after) was "
        "detected as driving a `cwd=<real repo>` subprocess and would be "
        "pinned to xdist_group('real_repo_scan'). `_REAL_REPO_CWD_RE` "
        f"(tests/conftest.py:1397-1408) matched the `cwd` inside `{var}` "
        "followed by ` = Path.cwd(` -- the RHS `Path.cwd()` call satisfies "
        "the regex's own `Path.cwd()` anchor alternative, so the idiom "
        "self-matches. Fix: add a left-hand `\\b` word boundary before the "
        "`cwd` literal in `_REAL_REPO_CWD_RE` so it only matches when `cwd` "
        "is a keyword-argument NAME, not a substring of a longer identifier."
    )


def test_genuine_real_repo_subprocess_call_still_pins_real_repo_scan_group(
    tmp_path: Path,
) -> None:
    """Companion to the false-positive guard above -- the fix for (c) must
    not overcorrect into a false NEGATIVE. A genuine
    `subprocess.run(..., cwd=REPO_ROOT)` call must still be detected and
    pinned; this is the exact defect class the group exists to serialize
    (see module docstring's "The marker exists for a REAL reason" section).
    """
    import tests.conftest as suite_conftest

    probe_file = tmp_path / "probe_genuine_subprocess.py"
    probe_file.write_text(_GENUINE_REAL_REPO_SUBPROCESS_SNIPPET, encoding="utf-8")

    assert suite_conftest._item_depends_on_real_repo(probe_file) is True, (
        "a file containing a genuine `subprocess.run(..., cwd=REPO_ROOT)` "
        "call was NOT detected as driving a `cwd=<real repo>` subprocess "
        "and would NOT be pinned to xdist_group('real_repo_scan') -- this "
        "would silently drop the isolation the group exists to provide "
        "(see the '25bc00d35' rationale in the module docstring)."
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
