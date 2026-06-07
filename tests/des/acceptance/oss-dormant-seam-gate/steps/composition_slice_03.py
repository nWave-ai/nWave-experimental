"""Composition root for the dormant-seam gate binding-resolved precision (slice-03).

The slice-03 value: the gate resolves BINDINGS, not names, so it produces ZERO
false-positives on dispatched symbols and ZERO false-negatives on name-collisions
(KPI-3 guardrails).

  * binding-resolved CLEAR (no false-positive): a net-new effectful symbol wired
    ONLY by an entry-point / registry registration -- the canonical OSS anchor, a
    ``[project.entry-points."nwave.lang.adapter"]`` registration in a net-new
    ``pyproject.toml`` pointing at the symbol -- has NO direct/attribute source
    call-site BY DESIGN. The gate must resolve the entry-point registration INTO
    the call-site set (D6/D-3, mirroring the real ``discovery.py`` resolve-and-
    probe seam that reads the ``nwave.lang.adapter`` group), so the dispatched
    symbol is NOT false-flagged dormant.
  * module-qualified identity (no false-negative): two distinct ``main`` symbols
    in different net-new modules -- one reached by a production call-site, one not
    -- are distinct identities. The call to the WIRED ``main`` must NOT count as a
    call-site for the DORMANT ``main``; only the dormant one is flagged, by
    module-qualified identity, not the bare name ``main``.

DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess): identical to
slice-01/02 -- the production ``des dormant-seam-gate`` composition-root CLI
invoked as a subprocess black box (``python -m des.cli.dormant_seam_gate``). The
detector ``dormant_seam.detect``, the entry-point resolution, and the discovery
resolve-and-probe seam are NEVER imported-and-called at the step boundary; the SUT
is exercised only through the CLI subprocess. Observable surface: the single-line
JSON verdict on stdout, the loud human warning on stderr, the process exit code.

ANCHOR REALISM (DISCUSS D3 / DESIGN D-3 / R6): the entry-point registration models
the REAL form ``discovery.py`` resolves -- a pyproject
``[project.entry-points."nwave.lang.adapter"]`` table whose value is a
``module.path:Symbol`` reference (exactly the repo's own
``_conformance_fixture = "scripts...:ConformanceFixtureLanguageAdapter"`` shape).
This proves the ACTUAL false-positive class (an entry-point-dispatched symbol with
no source call-site), not a synthetic stand-in.

REUSE: the synthetic-repo builder is the slice-01/02 shape (a real tmp git repo
with a committed base, then net-new ADDED ``src/des/`` modules) -- the proven
substrate, extended here to ALSO add a net-new ``pyproject.toml`` carrying the
entry-point group (the registry registration the gate must resolve). Copied rather
than imported so slice-03 owns its own arrangements (the pyproject table, the two
``main`` defs) without coupling to slice-01/02 instance fields.

RED-for-right-reason (verified against shipped slice-02 production 2026-06-07):

  * ENTRY-POINT case: slice-02 production resolves ONLY source call-sites (the
    direct ``from X import name`` + bare-call and the indirect ``import module;
    module.symbol()`` attribute-call shapes). It does NOT parse the pyproject
    ``[project.entry-points."nwave.lang.adapter"]`` table, so an entry-point-only
    registered symbol has NO resolved call-site -> it is wrongly flagged dormant
    (``verdict: indeterminate``, named in the warning). The slice-03 Then-step
    asserts the symbol is CLEARED (not flagged, not named) -> fails with a
    semantic AssertionError. Correct RED: entry-point binding-resolution is
    unimplemented.
  * COLLISION case: slice-02 production already keys call-sites on module-
    qualified identity, so the name-collision MAY already pass -- but the
    paired assertion (the WIRED ``main`` clears AND the DORMANT ``main`` is still
    flagged) is pinned here as the no-false-negation control regardless. If
    slice-02 already distinguishes them, this scenario is GREEN-on-arrival and
    documents the invariant; the gate must keep distinguishing them once entry-
    point resolution lands (a regression guard for slice-03's resolution change).

NON-VACUITY controls (the resolution's discriminating power, not vacuously
always-clear):

  * A net-new effectful symbol that is NEITHER source-called NOR entry-point-
    registered (a genuinely dormant symbol) STILL warns -- the entry-point
    resolution clears ONLY when a real registration is present, it does not
    vacuously silence every symbol. (KPI-1 recall control: the gate that clears
    on entry-point registration must still FIRE on the genuinely-dormant control,
    else the clear is the always-on bug.)
  * In the collision fixture the DORMANT same-named symbol still warns -- the
    presence of a WIRED namesake does NOT vacuously clear it.

DRIVING-SURFACE / ENTRY-POINT-RESOLUTION-CONTRACT AMBIGUITY FOR THE CRAFTER
(DELIVER -- see also the DISTILL handoff note): the production CLI parses SOURCE
files in the net-new delta (it does NOT read ``importlib.metadata.entry_points``,
which reads INSTALLED package metadata, not the synthetic tmp repo). slice-03
therefore models the entry-point registration as a net-new ``pyproject.toml``
source file carrying ``[project.entry-points."nwave.lang.adapter"]`` -> the gate
must line-scan / parse that table, map each ``module.path:Symbol`` value to the
symbol's module-qualified identity, and add it to the resolved call-site set
BEFORE the detector runs (mirroring R6's resolve-and-probe shape on SOURCE rather
than installed metadata). The OBSERVABLE contract the AT pins is: an entry-point-
registered symbol CLEARS (not flagged, not named, exit 0); the EXACT parse
mechanism (a narrow ``[project.entry-points."nwave.lang.adapter"]`` line-scan, the
stdlib ``subset_parser``, or a tomllib read) is the crafter's choice. The pyproject
table SYNTAX (``module.path:Symbol`` under the ``nwave.lang.adapter`` group) is the
stable contract -- the value's module + the trailing ``:Symbol`` join to the
symbol's identity (``module.path.Symbol``-shaped; here the registered target is a
FUNCTION, so the value is ``des.probe_dispatch_module:dispatch_lang_adapter`` and
the joined identity is ``des.probe_dispatch_module.dispatch_lang_adapter``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import EmissionChannel


# tests/des/acceptance/oss-dormant-seam-gate/steps/composition_slice_03.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# The production CLI module under test. slice-03 hardens the binding-resolution ON it.
GATE_MODULE = "des.cli.dormant_seam_gate"

_FEATURE_ID = "probe-dormant-precision-feat"

# The net-new effectful public symbol wired ONLY by the entry-point registration
# (no source call-site by design). Public + effectful (its body performs an I/O
# write) so it is in the gate's effectful-symbol surface (D-3).
_DISPATCH_SYMBOL = "dispatch_lang_adapter"
_DISPATCH_MODULE_REL = "src/des/probe_dispatch_module.py"
_DISPATCH_MODULE_DOTTED = "des.probe_dispatch_module"

# The real entry-point group the production discovery.py resolves (anchor realism).
_ENTRY_POINT_GROUP = "nwave.lang.adapter"
# The registration NAME under that group (arbitrary; the real repo uses
# ``_conformance_fixture``). The VALUE is the ``module:Symbol`` reference the gate
# must resolve into the call-site set.
_ENTRY_POINT_NAME = "probe_lang_adapter"
_ENTRY_POINT_VALUE = f"{_DISPATCH_MODULE_DOTTED}:{_DISPATCH_SYMBOL}"

# Name-collision fixture: two distinct ``main`` symbols in different modules, one
# wired by a source call-site, one dormant. Module-qualified identity must keep
# them distinct (no false-negation: the call to the wired ``main`` is not a
# call-site for the dormant ``main``).
_COLLIDING_NAME = "main"
_WIRED_MAIN_MODULE_REL = "src/des/probe_collision_wired.py"
_WIRED_MAIN_MODULE_DOTTED = "des.probe_collision_wired"
_DORMANT_MAIN_MODULE_REL = "src/des/probe_collision_dormant.py"
_COLLISION_CALLER_MODULE_REL = "src/des/probe_collision_caller.py"

# Genuinely-dormant control symbol (neither source-called nor entry-point-
# registered) -- the KPI-1 recall control: the resolution must still FIRE on it.
_GENUINE_DORMANT_SYMBOL = "stage_unregistered_residue"
_GENUINE_DORMANT_MODULE_REL = "src/des/probe_unregistered_module.py"

# Tokens binding a warning to the DORMANT verdict (slice-01/02 shape reused).
_DORMANT_MARKER_TOKENS: tuple[str, ...] = (
    "dormant-no-call-site",
    "dormant",
    "no production call-site",
    "no call-site",
    "no call site",
    "uncalled",
)

# A block / refuse on stdout is forbidden (KPI-2 guardrail, re-pinned for slice-03).
_BLOCK_TOKENS: tuple[str, ...] = ('"decision": "block"', '"decision":"block"', "refuse")


@dataclass
class DormantSeamPrecisionComposition:
    """Drives the production dormant-seam-gate CLI for the slice-03 precision ATs."""

    _tmp: Path | None = field(default=None)
    _repo_root: Path | None = field(default=None)
    _feature_dir: Path | None = field(default=None)
    _base_ref: str | None = field(default=None)
    _completed: subprocess.CompletedProcess[str] | None = field(default=None)
    _emission_channel: EmissionChannel = field(default=EmissionChannel.STDERR)

    # ---- given ---------------------------------------------------------

    def given_entry_point_dispatched_seam(self) -> None:
        """An effectful symbol wired ONLY by a ``nwave.lang.adapter`` registration.

        No source call-site reaches it; the only wiring is the pyproject
        entry-point group. The gate must resolve the registration into a call-site
        so the symbol is NOT false-flagged dormant (KPI-3, binding-resolved).
        """
        self._build_entry_point_feature()

    def given_name_collision_one_wired_one_dormant(self) -> None:
        """Two same-named ``main`` symbols: one source-called, one not.

        Module-qualified identity must keep them distinct -- the call to the wired
        ``main`` is not a call-site for the dormant ``main`` (no false-negation).
        """
        self._build_name_collision_feature()

    def given_genuinely_dormant_unregistered_seam(self) -> None:
        """An effectful symbol with NO source call-site and NO entry-point registration.

        KPI-1 recall control: the binding-resolution clears ONLY on a real
        registration, so this genuinely-dormant symbol must STILL be flagged (the
        clear is not vacuously always-on).
        """
        self._build_unregistered_feature()

    # ---- when ----------------------------------------------------------

    def when_developer_runs_the_gate(self) -> None:
        """Invoke the REAL dormant-seam-gate CLI as a subprocess black box."""
        self._run_gate()

    # ---- then ----------------------------------------------------------

    def then_entry_point_seam_cleared(self) -> None:
        """The entry-point-dispatched seam is NOT flagged / named (no false-positive)."""
        verdict = self._verdict()
        assert not self._symbol_is_flagged(verdict, _DISPATCH_SYMBOL), (
            f"an entry-point-registered symbol ({_ENTRY_POINT_GROUP} -> "
            f"{_ENTRY_POINT_VALUE!r}) with no source call-site must be resolved as "
            f"WIRED -- the gate must read the pyproject entry-point group and add "
            f"the registration to the call-site set -- but it still flags "
            f"{_DISPATCH_SYMBOL!r} dormant (a false-positive on a dispatched "
            f"symbol). {self._observed()}"
        )
        warning = self._warning_text()
        assert _DISPATCH_SYMBOL not in warning, (
            f"the entry-point-dispatched seam {_DISPATCH_SYMBOL!r} must not be "
            f"named in the loud dormant-seam warning (it is wired by the registry, "
            f"not dormant). {self._observed()}"
        )

    def then_dormant_namesake_flagged_wired_namesake_cleared(self) -> None:
        """No false-negation: the dormant ``main`` is flagged, the wired one is not.

        Module-qualified identity keeps the two same-named symbols distinct: the
        call to the wired ``main`` does NOT cover the dormant ``main``.
        """
        verdict = self._verdict()
        dormant_identity = f"des.probe_collision_dormant.{_COLLIDING_NAME}"
        wired_identity = f"{_WIRED_MAIN_MODULE_DOTTED}.{_COLLIDING_NAME}"
        assert self._identity_is_flagged(verdict, dormant_identity), (
            f"the DORMANT same-named symbol {dormant_identity!r} must be flagged -- "
            f"the production call-site reaching its namesake {wired_identity!r} must "
            f"NOT count as a call-site for it (module-qualified identity, not the "
            f"bare name {_COLLIDING_NAME!r}); a name-match gate would false-NEGATE "
            f"it. {self._observed()}"
        )
        assert not self._identity_is_flagged(verdict, wired_identity), (
            f"the WIRED same-named symbol {wired_identity!r} must clear (it has a "
            f"real production call-site); the gate wrongly flags it. "
            f"{self._observed()}"
        )

    def then_dormant_namesake_named_in_warning(self) -> None:
        """The dormant ``main`` is named in the loud warning, bound to dormant semantics."""
        warning = self._warning_text()
        assert _COLLIDING_NAME in warning, (
            f"the dormant same-named symbol {_COLLIDING_NAME!r} must be named in "
            f"the loud warning (it is genuinely dormant). {self._observed()}"
        )
        assert any(token in warning.lower() for token in _DORMANT_MARKER_TOKENS), (
            f"the dormant {_COLLIDING_NAME!r} must stay bound to the DORMANT "
            f"verdict (one of {_DORMANT_MARKER_TOKENS!r}). {self._observed()}"
        )

    def then_unregistered_seam_still_warns(self) -> None:
        """KPI-1 control: a genuinely-dormant unregistered symbol still warns."""
        verdict = self._verdict()
        assert self._symbol_is_flagged(verdict, _GENUINE_DORMANT_SYMBOL), (
            f"a net-new effectful symbol with NO source call-site and NO entry-"
            f"point registration must STILL be flagged dormant -- the binding-"
            f"resolution clears ONLY on a real registration, it does not vacuously "
            f"silence every symbol (KPI-1 recall control). {self._observed()}"
        )
        warning = self._warning_text()
        assert _GENUINE_DORMANT_SYMBOL in warning, (
            f"the genuinely-dormant unregistered seam {_GENUINE_DORMANT_SYMBOL!r} "
            f"must be named in the loud warning. {self._observed()}"
        )

    def then_exits_zero(self) -> None:
        """Non-halting: every precision outcome stays exit 0 (KPI-2 guardrail)."""
        completed = self._require_completed()
        assert completed.returncode == 0, (
            "the gate must exit with code zero (non-halting) for every precision "
            f"outcome; got returncode={completed.returncode}. {self._observed()}"
        )
        assert not any(token in completed.stdout for token in _BLOCK_TOKENS), (
            "no precision outcome may emit a block / refuse decision on stdout "
            f"(KPI-2 guardrail). {self._observed()}"
        )

    # ---- assertion helpers ---------------------------------------------

    def _symbol_is_flagged(self, verdict: dict[str, object], symbol: str) -> bool:
        """True iff the bare ``symbol`` name appears in the flagged dormant set."""
        for entry in self._dormant_entries(verdict):
            if isinstance(entry, dict) and entry.get("symbol") == symbol:
                return True
            if entry == symbol:
                return True
        return False

    def _identity_is_flagged(self, verdict: dict[str, object], identity: str) -> bool:
        """True iff the module-qualified ``identity`` is in the flagged dormant set.

        Matches on the resolved ``identity`` field (the module-qualified join key),
        NOT the bare name -- the precise check the name-collision control needs.
        """
        for entry in self._dormant_entries(verdict):
            if isinstance(entry, dict) and entry.get("identity") == identity:
                return True
            if entry == identity:
                return True
        return False

    def _dormant_entries(self, verdict: dict[str, object]) -> list[object]:
        dormant = verdict.get("dormant_symbols")
        return dormant if isinstance(dormant, list) else []

    def _verdict(self) -> dict[str, object]:
        """Parse the single-line JSON DormantSeamVerdict from stdout.

        Raises a semantic AssertionError (RED-for-right-reason) when no parseable
        verdict line exists.
        """
        completed = self._require_completed()
        for line in reversed(completed.stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "verdict" in payload:
                return payload
        raise AssertionError(
            "the dormant-seam gate produced no parseable single-line JSON verdict "
            f"on stdout. {self._observed()}"
        )

    def _warning_text(self) -> str:
        """The loud-warning channel (stderr per the OSS hooks-only invariant)."""
        return self._require_completed().stderr

    def _observed(self) -> str:
        completed = self._require_completed()
        return (
            f"gate returncode={completed.returncode}; "
            f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) ----------

    def _build_entry_point_feature(self) -> None:
        """net-new delta: an effectful symbol + a pyproject entry-point registration.

        The symbol module is added with NO source call-site; a net-new
        ``pyproject.toml`` registers it under the ``nwave.lang.adapter`` group --
        the only wiring. The gate must resolve the registration into a call-site.
        """
        self._ensure_repo()
        self._write_module(
            rel=_DISPATCH_MODULE_REL,
            symbol=_DISPATCH_SYMBOL,
            payload="dispatched",
        )
        self._write_entry_point_pyproject()
        self._commit_all("add net-new entry-point-dispatched seam")

    def _build_name_collision_feature(self) -> None:
        """net-new delta: two same-named ``main`` symbols, one wired, one dormant."""
        self._ensure_repo()
        self._write_module(
            rel=_WIRED_MAIN_MODULE_REL,
            symbol=_COLLIDING_NAME,
            payload="wired-main",
        )
        self._write_module(
            rel=_DORMANT_MAIN_MODULE_REL,
            symbol=_COLLIDING_NAME,
            payload="dormant-main",
        )
        self._write_collision_caller()
        self._commit_all("add net-new name-collision seams (one wired, one dormant)")

    def _build_unregistered_feature(self) -> None:
        """net-new delta: an effectful symbol with neither call-site nor registration."""
        self._ensure_repo()
        self._write_module(
            rel=_GENUINE_DORMANT_MODULE_REL,
            symbol=_GENUINE_DORMANT_SYMBOL,
            payload="unregistered",
        )
        self._commit_all("add net-new genuinely-dormant unregistered seam")

    def _ensure_repo(self) -> None:
        if self._repo_root is not None:
            return
        self._tmp = Path(tempfile.mkdtemp(prefix="dormant-seam-precision-at-"))
        self._repo_root = self._tmp
        self._base_ref = "dormant-seam-precision-base"
        subprocess.run(["git", "init", "-q"], cwd=self._repo_root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "at@example.com"],
            cwd=self._repo_root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "at"], cwd=self._repo_root, check=True
        )
        (self._repo_root / "src" / "des").mkdir(parents=True, exist_ok=True)
        (self._repo_root / "src" / "des" / "__init__.py").write_text(
            "", encoding="utf-8"
        )
        self._feature_dir = self._repo_root / "docs" / "feature" / _FEATURE_ID
        self._feature_dir.mkdir(parents=True, exist_ok=True)
        (self._feature_dir / "feature-delta.md").write_text(
            f"# Feature Delta -- {_FEATURE_ID}\n", encoding="utf-8"
        )
        self._commit_all("base: empty src/des before the net-new seam")
        subprocess.run(
            ["git", "branch", self._base_ref], cwd=self._repo_root, check=True
        )

    def _write_module(self, rel: str, symbol: str, payload: str) -> None:
        """Add a net-new module defining one effectful public ``symbol``."""
        assert self._repo_root is not None
        module = self._repo_root / rel
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(
            '"""Net-new probe module carrying one effectful public symbol."""\n'
            "from __future__ import annotations\n"
            "from pathlib import Path\n"
            "\n"
            f"def {symbol}(target: str) -> None:\n"
            '    """Effectful: writes to the filesystem (an I/O side-effect)."""\n'
            f'    Path(target).write_text("{payload}", encoding="utf-8")\n',
            encoding="utf-8",
        )

    def _write_entry_point_pyproject(self) -> None:
        """Add a net-new ``pyproject.toml`` registering the symbol under the group.

        Anchor realism: the ``[project.entry-points."nwave.lang.adapter"]`` table
        with a ``module:Symbol`` value -- exactly the form the real
        ``discovery.py`` resolve-and-probe seam reads (and the repo's own
        ``_conformance_fixture`` registration shape). This is the registry wiring
        the gate must resolve INTO the call-site set.
        """
        assert self._repo_root is not None
        pyproject = self._repo_root / "pyproject.toml"
        pyproject.write_text(
            "[project]\n"
            'name = "probe-dormant-precision"\n'
            'version = "0.0.0"\n'
            "\n"
            f'[project.entry-points."{_ENTRY_POINT_GROUP}"]\n'
            f'{_ENTRY_POINT_NAME} = "{_ENTRY_POINT_VALUE}"\n',
            encoding="utf-8",
        )

    def _write_collision_caller(self) -> None:
        """Add a net-new module that calls ONLY the wired ``main`` (direct wiring).

        The dormant ``main`` (in a different module) is NOT called -- so a
        module-qualified gate must keep it flagged while clearing the wired one.
        """
        assert self._repo_root is not None
        module = self._repo_root / _COLLISION_CALLER_MODULE_REL
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(
            '"""Net-new production module wiring ONLY the wired-namesake main."""\n'
            "from __future__ import annotations\n"
            f"from {_WIRED_MAIN_MODULE_DOTTED} import {_COLLIDING_NAME}\n"
            "\n"
            "def run(target: str) -> None:\n"
            f"    {_COLLIDING_NAME}(target)\n",
            encoding="utf-8",
        )

    def _commit_all(self, message: str) -> None:
        assert self._repo_root is not None
        subprocess.run(["git", "add", "-A"], cwd=self._repo_root, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", message, "--allow-empty"],
            cwd=self._repo_root,
            check=True,
        )

    def _run_gate(self) -> None:
        """Run `python -m des.cli.dormant_seam_gate` as a subprocess black box."""
        assert self._repo_root is not None
        assert self._feature_dir is not None
        assert self._base_ref is not None
        env = dict(os.environ)
        env["NWAVE_FRESHNESS"] = ""
        env["PIPENV_DONT_LOAD_ENV"] = "1"
        env["PYTHONPATH"] = (
            str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        )
        self._completed = subprocess.run(
            [
                sys.executable,
                "-m",
                GATE_MODULE,
                "--feature-dir",
                str(self._feature_dir),
                "--repo-root",
                str(self._repo_root),
                "--delta-base-ref",
                self._base_ref,
            ],
            capture_output=True,
            text=True,
            cwd=str(self._repo_root),
            env=env,
        )

    def _require_completed(self) -> subprocess.CompletedProcess[str]:
        assert self._completed is not None, (
            "the dormant-seam gate must be run (When) before asserting on its "
            "observable verdict surface (Then)"
        )
        return self._completed
