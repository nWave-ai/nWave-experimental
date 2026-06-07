"""Composition root for the dormant-seam gate escapes (slice-02).

The slice-02 value: a flagged dormant seam CLEARS two honest, never-silent ways:

  * escape (a) -- a real production call-site, INCLUDING the indirect attribute-
    call wiring form (``import module; module.symbol()``), not just the direct
    ``from module import symbol`` + bare-call form slice-01 already cleared. The
    deep binding-resolved precision (entry-point / registry) is slice-03; here the
    floor is "ONE indirect wiring form clears".
  * escape (b) -- a ``# dormant-ok: <F-id>`` owned-residue marker on the symbol.
    The symbol is OTHERWISE dormant (no call-site), but the marker clears the
    flag AND the clearing is RECORDED in the verdict surface naming the F-id (an
    auditable owned residue, never a silent suppression).

DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess): identical to
slice-01 -- the production ``des dormant-seam-gate`` composition-root CLI invoked
as a subprocess black box (``python -m des.cli.dormant_seam_gate``). The detector
``dormant_seam.detect`` and the marker-scan / call-site resolution are NEVER
imported-and-called at the step boundary; the SUT is exercised only through the
CLI subprocess. Observable surface: the single-line JSON verdict on stdout (now
carrying an ``escapes`` record for escape b), the loud human warning on stderr,
and the process exit code.

REUSE: the synthetic-repo builder is the slice-01 shape (a real tmp git repo with
a committed base, then net-new ADDED ``src/des/`` modules) -- copied here rather
than imported so slice-02 owns its own arrangements (the marker line, the
attribute-call caller) without coupling to slice-01's instance fields. The
``DormantSeamGateComposition`` import-and-extend was rejected: slice-02's marker
arrangement writes a DIFFERENT module body (the marker comment) and slice-02's
indirect caller writes a DIFFERENT caller body (attribute-call) -- distinct
substrate, same driving port.

RED-for-right-reason (verified empirically against shipped slice-01 production
2026-06-07):

  * MARKER case: slice-01 production IGNORES the ``# dormant-ok:`` marker -- the
    marked symbol is still flagged ``verdict: indeterminate`` and named in the
    warning, with NO escape record. The slice-02 Then-steps assert the symbol is
    CLEARED (not named, not flagged) AND that a record names the F-id -> both fail
    with a semantic AssertionError (the symbol is wrongly still named; no escape
    record exists). Correct RED: escape (b) is unimplemented.
  * INDIRECT case: slice-01 production resolves only the ``from X import name`` +
    bare-name call shape, so an attribute-call caller (``module.symbol()``) is NOT
    recognised as a call-site -> the symbol is wrongly flagged dormant. The
    slice-02 Then-step asserts the symbol is CLEARED -> fails with a semantic
    AssertionError. Correct RED: escape (a) indirect floor is unimplemented.

NON-VACUITY controls (the gate's discriminating power, not vacuously always-clear):

  * A ``# dormant-ok:`` marker on a NON-dormant symbol (one that HAS a call-site)
    must NOT spuriously emit an escape record -- the symbol was never flagged, so
    there is nothing to escape. (A marker is only meaningful on an otherwise-
    dormant symbol.)
  * A dormant symbol WITHOUT any marker and WITHOUT a call-site still warns
    (slice-01 contract, re-pinned here as the escape control pole) -- the escapes
    clear ONLY when their honest condition is present.

DRIVING-SURFACE AMBIGUITY FOR THE CRAFTER (DELIVER): the marker escape RECORD
shape is pinned by the AT as the OBSERVABLE contract (the cleared symbol is no
longer flagged AND a record in the verdict names BOTH the symbol and its F-id),
NOT the exact JSON key names. DESIGN D-4 proposes ``escapes: [{symbol,
escaped_via: "dormant-ok", f_id: <F-id>}]``; ``_escape_record_for`` accepts that
shape OR any record that carries the symbol + the F-id under a clearly-escape-
keyed field. If DELIVER chooses different key names, keep BOTH the symbol identity
and the F-id present + machine-findable in the verdict, and the human stderr line
must name them too (never-silent contract). The ``# dormant-ok: <F-id>`` marker
SYNTAX (a trailing line comment on the def, ``dormant-ok:`` then the F-id) is the
stable contract the gate line-scans (DESIGN D-4 mirrors the
``run_contract_gate._scan_gate_jobs`` narrow line-scan).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import CallSiteWiring, EmissionChannel, SeamEscape


# tests/des/acceptance/oss-dormant-seam-gate/steps/composition_slice_02.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# The production CLI module under test. slice-02 hardens the escapes ON it.
GATE_MODULE = "des.cli.dormant_seam_gate"

_FEATURE_ID = "probe-dormant-escapes-feat"
# The net-new effectful public symbol the synthetic delta adds. Public +
# effectful (its body performs an I/O write) so it is in the gate's effectful-
# symbol surface (D-3). OTHERWISE-dormant unless cleared by an escape.
_EFFECTFUL_SYMBOL = "stage_owned_residue"
_EFFECTFUL_MODULE_REL = "src/des/probe_escape_module.py"
_CALLER_MODULE_REL = "src/des/probe_escape_caller.py"

# The owned-residue F-id the marker names. Free-text (an unbounded domain, C6),
# anchored to a concrete realistic value here; the record must carry it verbatim.
_OWNED_RESIDUE_F_ID = "F-EXAMPLE-OWNED-RESIDUE"

# Tokens that bind a warning to the DORMANT verdict (slice-01 shape, reused so a
# warn-every-symbol gate cannot satisfy the assertion).
_DORMANT_MARKER_TOKENS: tuple[str, ...] = (
    "dormant-no-call-site",
    "dormant",
    "no production call-site",
    "no call-site",
    "no call site",
    "uncalled",
)

# A block / refuse on stdout is forbidden (KPI-2 guardrail, re-pinned for slice-02
# -- the escapes never introduce a halting path).
_BLOCK_TOKENS: tuple[str, ...] = ('"decision": "block"', '"decision":"block"', "refuse")


@dataclass
class DormantSeamEscapesComposition:
    """Drives the production dormant-seam-gate CLI for the slice-02 escape ATs."""

    _tmp: Path | None = field(default=None)
    _repo_root: Path | None = field(default=None)
    _feature_dir: Path | None = field(default=None)
    _base_ref: str | None = field(default=None)
    _completed: subprocess.CompletedProcess[str] | None = field(default=None)
    _emission_channel: EmissionChannel = field(default=EmissionChannel.STDERR)

    # ---- given ---------------------------------------------------------

    def given_dormant_seam_with_owned_residue_marker(self) -> None:
        """A dormant effectful symbol carrying a ``# dormant-ok: <F-id>`` marker.

        OTHERWISE dormant (no production call-site) -- the marker is the only
        thing that should clear it (escape b).
        """
        self._build_feature(wiring=CallSiteWiring.NONE, with_marker=True)

    def given_dormant_seam_wired_indirectly(self) -> None:
        """A dormant effectful symbol reached only by an indirect attribute call.

        A net-new caller does ``import module; module.symbol()`` (NOT the direct
        ``from module import symbol`` + bare-call form slice-01 cleared). This is
        the escape (a) indirect-wiring floor.
        """
        self._build_feature(wiring=CallSiteWiring.INDIRECT, with_marker=False)

    def given_wired_seam_with_owned_residue_marker(self) -> None:
        """A NON-dormant symbol (it has a call-site) that ALSO carries a marker.

        Non-vacuity control: the symbol is not dormant, so it was never flagged --
        the marker must NOT spuriously emit an escape record.
        """
        self._build_feature(wiring=CallSiteWiring.DIRECT, with_marker=True)

    def given_dormant_seam_without_any_escape(self) -> None:
        """A dormant effectful symbol with no call-site and no marker.

        Non-vacuity control pole: the escapes clear ONLY when present, so this
        symbol still warns (the slice-01 contract, re-pinned as the escape
        baseline).
        """
        self._build_feature(wiring=CallSiteWiring.NONE, with_marker=False)

    # ---- when ----------------------------------------------------------

    def when_developer_runs_the_gate(self) -> None:
        """Invoke the REAL dormant-seam-gate CLI as a subprocess black box."""
        self._run_gate()

    # ---- then ----------------------------------------------------------

    def then_marker_clears_the_seam(self) -> None:
        """escape (b): the marked dormant symbol is no longer flagged / named."""
        verdict = self._verdict()
        assert verdict.get("verdict") != "indeterminate" or not self._symbol_is_flagged(
            verdict, _EFFECTFUL_SYMBOL
        ), (
            f"the ``# dormant-ok: {_OWNED_RESIDUE_F_ID}`` marker must CLEAR the "
            f"otherwise-dormant seam {_EFFECTFUL_SYMBOL!r} -- it must no longer be "
            f"flagged dormant -- but the gate still flags it. {self._observed()}"
        )
        warning = self._warning_text()
        assert _EFFECTFUL_SYMBOL not in warning, (
            f"the marked seam {_EFFECTFUL_SYMBOL!r} must not be named in the loud "
            f"dormant-seam warning once the ``# dormant-ok`` marker clears it; the "
            f"gate still names it. {self._observed()}"
        )

    def then_clearing_is_recorded_with_owner(self) -> None:
        """escape (b): the clearing is RECORDED naming the symbol + its F-id.

        Never-silent contract -- the marker does not vanish the seam, it converts
        it into an AUDITABLE owned residue: the verdict surface carries an escape
        record naming BOTH the symbol and the owning F-id, and the loud stderr
        line names the F-id too.
        """
        record = self._escape_record_for(_EFFECTFUL_SYMBOL)
        flat = json.dumps(record)
        assert _OWNED_RESIDUE_F_ID in flat, (
            f"the escape record for {_EFFECTFUL_SYMBOL!r} must name the owning "
            f"F-id {_OWNED_RESIDUE_F_ID!r} (auditable owned residue, never a "
            f"silent suppression); record={record!r}. {self._observed()}"
        )
        assert SeamEscape.DORMANT_OK_MARKER.value in flat, (
            f"the escape record must mark the clearing as a "
            f"``{SeamEscape.DORMANT_OK_MARKER.value}`` escape (so a reader sees WHY "
            f"the seam was cleared); record={record!r}. {self._observed()}"
        )
        warning = self._warning_text()
        assert _OWNED_RESIDUE_F_ID in warning, (
            f"the loud stderr surface must also name the owning F-id "
            f"{_OWNED_RESIDUE_F_ID!r} when a seam is cleared by an owned-residue "
            f"marker (never-silent: the suppression is visible to the human). "
            f"{self._observed()}"
        )

    def then_indirect_call_site_clears_the_seam(self) -> None:
        """escape (a) floor: an indirect attribute-call wiring clears the seam."""
        verdict = self._verdict()
        assert not self._symbol_is_flagged(verdict, _EFFECTFUL_SYMBOL), (
            f"an indirect attribute-call wiring (``module.{_EFFECTFUL_SYMBOL}()``) "
            f"must count as a production call-site and CLEAR the seam (escape a "
            f"covers wiring, not just the direct from-import call), but the gate "
            f"still flags {_EFFECTFUL_SYMBOL!r} dormant. {self._observed()}"
        )
        warning = self._warning_text()
        assert _EFFECTFUL_SYMBOL not in warning, (
            f"the indirectly-wired seam {_EFFECTFUL_SYMBOL!r} must not be named in "
            f"the dormant-seam warning. {self._observed()}"
        )

    def then_no_escape_record_for_wired_seam(self) -> None:
        """Non-vacuity: a marker on a NON-dormant symbol emits NO escape record.

        The symbol has a real call-site, so it was never flagged -- there is
        nothing to escape, and a spurious escape record would be a false-positive
        suppression report.
        """
        record = self._optional_escape_record_for(_EFFECTFUL_SYMBOL)
        assert record is None, (
            f"a ``# dormant-ok`` marker on the NON-dormant (wired) symbol "
            f"{_EFFECTFUL_SYMBOL!r} must NOT emit an escape record -- the symbol "
            f"was never flagged, so there is nothing to escape; got record="
            f"{record!r}. {self._observed()}"
        )

    def then_unmarked_seam_still_warns(self) -> None:
        """Non-vacuity pole: a dormant seam with no escape still warns (slice-01)."""
        warning = self._warning_text()
        assert _EFFECTFUL_SYMBOL in warning, (
            f"a dormant seam with NO call-site and NO marker must still be named "
            f"in the loud warning -- the escapes clear only when present, they do "
            f"not vacuously silence every seam. {self._observed()}"
        )
        assert any(token in warning.lower() for token in _DORMANT_MARKER_TOKENS), (
            f"the unmarked dormant seam {_EFFECTFUL_SYMBOL!r} must stay bound to "
            f"the DORMANT verdict (one of {_DORMANT_MARKER_TOKENS!r}). "
            f"{self._observed()}"
        )

    def then_exits_zero(self) -> None:
        """Non-halting: every escape outcome stays exit 0 (KPI-2 guardrail)."""
        completed = self._require_completed()
        assert completed.returncode == 0, (
            "the gate must exit with code zero (non-halting) for every escape "
            f"outcome; got returncode={completed.returncode}. {self._observed()}"
        )
        assert not any(token in completed.stdout for token in _BLOCK_TOKENS), (
            "no escape outcome may emit a block / refuse decision on stdout "
            f"(KPI-2 guardrail). {self._observed()}"
        )

    # ---- assertion helpers ---------------------------------------------

    def _symbol_is_flagged(self, verdict: dict[str, object], symbol: str) -> bool:
        """True iff ``symbol`` appears in the verdict's flagged dormant-symbol set."""
        dormant = verdict.get("dormant_symbols")
        if not isinstance(dormant, list):
            return False
        for entry in dormant:
            if isinstance(entry, dict) and entry.get("symbol") == symbol:
                return True
            if entry == symbol:
                return True
        return False

    def _escape_record_for(self, symbol: str) -> dict[str, object] | list[object]:
        """The escape record naming ``symbol`` in the verdict, or AssertionError.

        RED-for-right-reason: slice-01 production carries NO ``escapes`` surface,
        so this raises a semantic AssertionError (the escape record is absent).
        """
        record = self._optional_escape_record_for(symbol)
        if record is None:
            raise AssertionError(
                f"the verdict carries no escape record naming {symbol!r} (the "
                f"``# dormant-ok`` owned-residue escape is unrecorded -- a silent "
                f"suppression, or unimplemented). {self._observed()}"
            )
        return record

    def _optional_escape_record_for(
        self, symbol: str
    ) -> dict[str, object] | list[object] | None:
        """The escape record naming ``symbol`` if present, else ``None``.

        Accepts the DESIGN D-4 shape (``escapes: [{symbol, escaped_via, f_id}]``)
        OR any record under a clearly-escape-keyed verdict field that names the
        symbol -- the OBSERVABLE contract is symbol + F-id present in an escape
        record, not the exact key names (crafter latitude).
        """
        verdict = self._verdict()
        for key, value in verdict.items():
            if "escape" not in key.lower():
                continue
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict) and entry.get("symbol") == symbol:
                        return entry
                    if isinstance(entry, str) and symbol in entry:
                        return [entry]
            elif isinstance(value, dict) and value.get("symbol") == symbol:
                return value
        return None

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

    def _build_feature(self, wiring: CallSiteWiring, with_marker: bool) -> None:
        """Build a real tmp git repo whose net-new delta carries the seam."""
        self._ensure_repo()
        self._write_effectful_module(with_marker=with_marker)
        if wiring is CallSiteWiring.DIRECT:
            self._write_direct_caller_module()
        elif wiring is CallSiteWiring.INDIRECT:
            self._write_indirect_caller_module()
        self._commit_all("add net-new dormant-seam-gate escape probe feature")

    def _ensure_repo(self) -> None:
        if self._repo_root is not None:
            return
        self._tmp = Path(tempfile.mkdtemp(prefix="dormant-seam-escapes-at-"))
        self._repo_root = self._tmp
        self._base_ref = "dormant-seam-escapes-base"
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

    def _write_effectful_module(self, with_marker: bool) -> None:
        """Add a net-new module with one effectful public symbol.

        When ``with_marker`` is set, the def carries a trailing ``# dormant-ok:
        <F-id>`` owned-residue comment (the escape-b marker syntax DESIGN D-4
        line-scans).
        """
        assert self._repo_root is not None
        marker = f"  # dormant-ok: {_OWNED_RESIDUE_F_ID}" if with_marker else ""
        module = self._repo_root / _EFFECTFUL_MODULE_REL
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(
            '"""Net-new probe module carrying one effectful public symbol."""\n'
            "from __future__ import annotations\n"
            "from pathlib import Path\n"
            "\n"
            f"def {_EFFECTFUL_SYMBOL}(target: str) -> None:{marker}\n"
            '    """Effectful: writes to the filesystem (an I/O side-effect)."""\n'
            '    Path(target).write_text("residue", encoding="utf-8")\n',
            encoding="utf-8",
        )

    def _write_direct_caller_module(self) -> None:
        """Add a net-new module that calls the symbol the DIRECT (slice-01) way."""
        assert self._repo_root is not None
        module = self._repo_root / _CALLER_MODULE_REL
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(
            '"""Net-new production module wiring the symbol directly."""\n'
            "from __future__ import annotations\n"
            f"from des.probe_escape_module import {_EFFECTFUL_SYMBOL}\n"
            "\n"
            "def run(target: str) -> None:\n"
            f"    {_EFFECTFUL_SYMBOL}(target)\n",
            encoding="utf-8",
        )

    def _write_indirect_caller_module(self) -> None:
        """Add a net-new module that calls via the INDIRECT attribute-call form.

        ``import module; module.symbol()`` -- the escape (a) wiring floor that
        slice-01's from-import-only resolution does NOT recognise.
        """
        assert self._repo_root is not None
        module = self._repo_root / _CALLER_MODULE_REL
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(
            '"""Net-new production module wiring the symbol indirectly."""\n'
            "from __future__ import annotations\n"
            "from des import probe_escape_module\n"
            "\n"
            "def run(target: str) -> None:\n"
            f"    probe_escape_module.{_EFFECTFUL_SYMBOL}(target)\n",
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
