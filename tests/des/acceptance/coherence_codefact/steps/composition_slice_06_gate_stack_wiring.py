"""Composition root for the f-coherence-and-attestation slice-06 ATs (gate-stack wiring).

Mandate-13 driving-port-only: each behaviour is driven through a REAL driving
surface — NO production module is imported-and-called at the step boundary for its
business logic; the step bodies (in ``test_slice_06_*``) delegate to these
composition methods (Mandate-12 — no logic in step bodies).

slice-06 (the WIRING slice, JOB-028) CONNECTS three already-built feature modules
into the gate-stack so a maintainer can REACH them and the closure scorecard sees
the feature WIRED (closing the ``catalogato ≠ cablato`` gap the scorecard reports:
``f-coherence-and-attestation  delivering 5/5  no UNWIRED``). The modules SHIP at
HEAD; slice-06 makes them FIRE:

  * slice-03 ``src/des/cli/gate_g.py`` (``evaluate_gate_g`` callable — NOT a
    registered ``des`` subcommand at HEAD; its own docstring line ~48 says so);
  * slice-04 ``src/des/domain/self_attest.py`` (``classify`` callable — pure
    domain, NO CLI module at HEAD);
  * slice-05 ``src/des/cli/run_tests.py`` (``main`` entry — a CLI module but NOT
    in the dispatcher ``_REGISTRY`` under any name at HEAD).

DRIVING SURFACES (Mandate-13, three witnessing axes):
  * REGISTRATION (AT-20/21/22) -> Layer 3 SUBPROCESS: the REAL ``des`` dispatcher
    (``des.cli.__main__.main``, invoked via its argv ``main`` entry the way an
    operator runs it). The observable is whether ``des --help`` advertises the
    subcommand + whether ``des <subcommand> --help`` resolves (exit 0) vs argparse
    invalid-choice (exit 2) — the same D-register seam pattern as
    oss-review-verdict-demotion slice-02. PLUS the 1:1 catalog mirror row in the
    SHIPPED ``nWave/gates/_catalog.yaml`` (read as a real artifact).
  * GATE-STACK REFERENCE (AT-23) -> the REAL shipped ``nWave/flavors/*.yaml``
    artifacts: the observable is whether the closure scorecard's EXACT
    ``_term_wired`` regex for each module matches ≥1 flavor surface (the literal
    ``catalogato ≠ cablato`` closure leg the goal-contract measures). Read from the
    shipped YAML, NEVER an inline test string (Mandate-13 prose-surface rule).
  * BEHAVIOURAL WIRING (AT-24/25/26) -> Layer 3 SUBPROCESS: the REAL ``des
    <subcommand>`` over a real ``tmp_path`` input; the observable is the §17
    GateVerdict-shaped result the driven subcommand emits — proving the thin CLI
    wrapper actually DRIVES the existing slice-03/04/05 domain logic (the wrapper
    is a thin driver; the domain is NOT re-implemented).

active-RED scaffold (atdd_pure -- NOT @skip): at HEAD all three subcommands are
ABSENT from the dispatcher ``_REGISTRY`` (verified: zero ``gate-g`` /
``self-attest`` / ``verify-test-runner`` rows), no module name is referenced in any
``nWave/flavors/*.yaml`` gate-stack, and ``self_attest.py`` has no CLI ``main``.
So:
  * REGISTRATION ATs: ``des <subcommand> --help`` hits argparse invalid-choice
    (SystemExit/exit 2) -> the dispatcher rejected an unregistered row -> the Then
    fires a NAMED semantic AssertionError (the subcommand is not registered).
  * REFERENCE AT: the scorecard ``_term_wired`` regex matches NO flavor surface ->
    the Then names the unwired module (the ``catalogato ≠ cablato`` failure).
  * BEHAVIOURAL ATs: the driven subcommand never resolves -> no verdict-shaped
    result -> the Then names the missing thin-driver wiring.
Each scenario RED-fails with a NAMED semantic AssertionError, never a collection /
import / setup error (the dispatcher import resolves; only the REGISTRY rows are
absent — a clean missing-functionality RED, the oss-review-verdict-demotion
slice-02 capture pattern).

DESIGN-CONTRACT ASSUMPTIONS flagged to DELIVER (state-here-so-DELIVER-matches —
the SEAM, never a line number):
  A1 (registration): DELIVER adds three ``_SubcommandRow`` rows to
     ``src/des/cli/__main__.py:_REGISTRY`` — ``gate-g`` -> a NEW thin CLI wrapper
     ``des.cli.gate_g`` ``main`` over the existing ``evaluate_gate_g``;
     ``self-attest`` -> a NEW thin CLI wrapper ``des.cli.self_attest`` ``main``
     over the existing ``des.domain.self_attest.classify``;
     ``verify-test-runner`` -> the EXISTING ``des.cli.run_tests`` ``main`` (already
     a CLI ``main``; only the registry row + a 1:1 catalog mirror are net-new).
     If DELIVER names the wrapper modules differently, the subprocess drive
     (``des <subcommand>``) is unchanged — the SEAM is the subcommand NAME, not the
     module path; update ``_catalog_module_for`` only if the catalog-mirror probe
     needs the exact module path.
  A2 (gate-stack reference): DELIVER references each subcommand in a
     ``nWave/flavors/*.yaml`` gate-stack — gate-G at the ``distill`` ``gate-out``
     stack (DISTILL gate-OUT #5, flow-v2-design §12); self-attest + the runner at
     whichever lifecycle_event / wave_gate_stack DESIGN places them. The witness is
     SURFACE-AGNOSTIC: it asks only whether the scorecard's ``_term_wired`` regex
     matches a flavor YAML (the EXACT closure leg), so ANY well-formed gate-stack
     placement greens it. If DESIGN places a module in a hook surface
     (``scripts/hooks/*.py``) instead of a flavor, the scorecard counts that too —
     but the slice plan + flow-v2-design §12 name the flavor gate-stack, so this AT
     keys on the flavor surface (update ``_FLAVOR_GLOB`` if DESIGN relocates).
  A3 (behavioural drive): each driven ``des <subcommand>`` emits a §17
     GateVerdict-shaped result — gate-G returns ``GateGEnvelope.verdict``;
     self-attest returns ``SelfAttestVerdict.verdict``; the runner emits a
     ``nwave.test_result.v1`` (a real run -> a verdict derivable from
     passed/failed) or a ``nwave.earned_verdict.v1`` ABSTAIN. This composition
     reads the verdict token from stdout / the emitted ``--out`` envelope; if
     DELIVER shapes the CLI output differently, update ``_read_driven_verdict``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .domain_types_slice_06_gate_stack_wiring import (
    LOCKED_GATE_VERDICTS,
    DrivenVerdict,
    GateStackReference,
    SubcommandRegistration,
    WiredModuleSpec,
)


# Repo root resolved relative to this composition file (tests/des/acceptance/
# coherence_codefact/steps/composition_slice_06...py -> parents[5]).
_REPO_ROOT: Path = Path(__file__).resolve().parents[5]

# The SHIPPED wiring surfaces the closure scorecard's `_term_wired` leg scans.
# MIRRORS the goal-contract scorecard's WIRING_FILES EXACTLY
# (scripts/flow_v2_closure_scorecard.py:63-67) — all FOUR firing surfaces, not
# only the flavor YAMLs: a module wired in `scripts/hooks/*.py`,
# `~/.claude/hooks/*.py`, OR the registry `nWave/waves/*.yaml` is ACCEPTED by the
# scorecard, so AT-23 MUST accept it too (a passing AT must ⟺ a passing scorecard
# leg — an AT stricter than the leg it witnesses is theater). Each glob is REAL,
# evaluated against the repo / HOME the scorecard reads. The reference AT reads
# these REAL artifacts, never an inline string (Mandate-13 prose-surface rule).
# Each entry is (glob_base, glob_pattern) — byte-for-byte the scorecard's four
# WIRING_FILES globs (the ~/.claude entry globs from HOME with the subpath IN the
# pattern, exactly as the scorecard does, so the matched file set is identical).
#
# f-distill-wiring-to-registry slice-02 (DDD-6/DDD-7, CT-8): `nWave/waves/*.yaml`
# (the LIVE-resolved registry, ADR-FLOW-006 D6) is ADDED here in lock-step with the
# scorecard tightening. slice-01 REMOVED the dormant `wave_gate_stacks.distill`
# flavor block (the former false-credit home of self-attest / verify-test-runner),
# so without scanning the registry this probe would go RED for those two gates —
# they now live in `nWave/waves/distill.yaml` gate-out. The probe and the scorecard
# WIRING_FILES are deliberate mirrors; they MUST change together (DDD-6).
_WIRING_GLOBS: tuple[tuple[Path, str], ...] = (
    (_REPO_ROOT / "nWave" / "flavors", "*.yaml"),
    (Path.home(), ".claude/hooks/*.py"),
    (_REPO_ROOT / "scripts" / "hooks", "*.py"),
    (_REPO_ROOT / "nWave" / "waves", "*.yaml"),
)

# The SHIPPED 1:1 registry-mirror catalog (registry<->catalog parity the
# single_entry_point arch test enforces).
_CATALOG_PATH: Path = _REPO_ROOT / "nWave" / "gates" / "_catalog.yaml"

# Sentinel an unregistered / un-driven subcommand records, so the Then can name
# the missing wiring instead of letting a SystemExit / empty result escape as a
# collection error.
_SEAM_ABSENT = "__SEAM_ABSENT__"

# argparse invalid-choice exit code (the dispatcher rejects an unregistered row).
_ARGPARSE_INVALID_CHOICE = 2


@dataclass
class GateStackWiringComposition:
    """Drives the slice-06 gate-stack-wiring seams through their REAL surfaces."""

    _spec: WiredModuleSpec | None = field(default=None)

    _registration: SubcommandRegistration | None = field(default=None)
    _reference: GateStackReference | None = field(default=None)
    _driven: DrivenVerdict | None = field(default=None)
    _seam_error: str | None = field(default=None)

    # =====================================================================
    # Given -- arm the module under wiring (the subcommand + the _term_wired regex)
    # =====================================================================

    def given_feature_module(self, spec: WiredModuleSpec) -> None:
        """Arm which already-built module slice-06 is wiring into the gate-stack."""
        self._spec = spec

    def given_unknown_subcommand(self, spec: WiredModuleSpec) -> None:
        """Arm an UNKNOWN subcommand name not in the gate-stack wiring set (AT-27).

        The closed-set robustness probe: the registration inspection (reused
        unchanged) must report this name NOT resolvable -- the dispatcher rejects
        it as an argparse invalid-choice. Proves the registration witness
        DISCRIMINATES (a resolver that accepted everything would pass the wiring
        ATs vacuously).
        """
        self._spec = spec

    # =====================================================================
    # When -- drive the REAL witnessing surfaces
    # =====================================================================

    def when_inspecting_subcommand_registration(self) -> None:
        """Probe whether ``des <subcommand>`` is a registered dispatcher row (AT-20/21/22)."""
        spec = self._require_spec()
        self._registration = self._probe_registration(spec)

    def when_inspecting_gate_stack_reference(self) -> None:
        """Probe whether the module is referenced in a flavor gate-stack (AT-23)."""
        spec = self._require_spec()
        self._reference = self._probe_gate_stack_reference(spec)

    def when_driving_the_subcommand(self, tmp_path: Path) -> None:
        """Drive the REAL ``des <subcommand>`` end-to-end (AT-24/25/26)."""
        spec = self._require_spec()
        self._driven = self._drive_subcommand(spec, tmp_path)

    # =====================================================================
    # Then -- observable readers
    # =====================================================================

    def then_subcommand_is_registered(self) -> None:
        """``des <subcommand>`` is a registered dispatcher row, advertised + resolvable (AT-20/21/22)."""
        reg = self._require_registration()
        spec = self._require_spec()
        assert reg.resolvable, (
            f"`des {spec.subcommand}` must be a REGISTERED subcommand (a "
            f"`_SubcommandRow` in src/des/cli/__main__.py:_REGISTRY, resolvable by "
            f"the real `des` dispatcher) -- the dispatcher rejected it as an invalid "
            f"choice (argparse exit {_ARGPARSE_INVALID_CHOICE}). At HEAD the "
            f"{spec.module.value} module ships (slice-03/04/05) but is NOT wired "
            f"into the dispatcher -- the `catalogato ≠ cablato` gap slice-06 closes. "
            f"{self._observed()}"
        )
        assert reg.advertised, (
            f"`des --help` must ADVERTISE the {spec.subcommand!r} subcommand (DDD-4 "
            f"-- the dispatcher lists every registered name) -- it was absent from "
            f"the help listing. {self._observed()}"
        )
        assert reg.in_catalog, (
            f"the gate catalog nWave/gates/_catalog.yaml must carry the 1:1 mirror "
            f"row for {spec.subcommand!r} (the registry<->catalog parity the "
            f"single_entry_point arch test enforces) -- the catalog row is absent. "
            f"{self._observed()}"
        )

    def then_subcommand_is_rejected_as_not_resolvable(self) -> None:
        """An unknown subcommand name is NOT resolvable -- the dispatcher rejects it (AT-27).

        The closed-set guardrail: the real `des` dispatcher rejects a name not in
        its `_REGISTRY` with an argparse invalid-choice (not resolvable). Proves
        the registration witness DISCRIMINATES -- a dispatcher that accepted any
        name would make AT-20/21/22 pass vacuously. GREEN at HEAD and after DELIVER.
        """
        reg = self._require_registration()
        spec = self._require_spec()
        assert not reg.resolvable, (
            f"an unknown subcommand name {spec.subcommand!r} (NOT in the dispatcher "
            f"_REGISTRY) must be REJECTED by the real `des` dispatcher as an "
            f"argparse invalid-choice (not resolvable) -- the dispatcher resolved "
            f"it, which would make the registration witness (AT-20/21/22) pass "
            f"vacuously for ANY name. {self._observed()}"
        )

    def then_module_is_referenced_in_a_gate_stack(self) -> None:
        """The module name is referenced in a flavor gate-stack -- the scorecard
        ``_term_wired`` leg passes (AT-23, the ``catalogato ≠ cablato`` closure)."""
        ref = self._require_reference()
        spec = self._require_spec()
        assert ref.term_wired, (
            f"the {spec.module.value} module must be REFERENCED in a "
            f"nWave/flavors/*.yaml gate-stack so the closure scorecard's "
            f"`_term_wired` leg (pattern {spec.term_pattern!r}) passes -- it is "
            f"referenced in NO flavor surface. This is the literal "
            f"`catalogato ≠ cablato` failure the scorecard reports "
            f"(`f-coherence-and-attestation delivering 5/5 no UNWIRED`): a built + "
            f"registered module that no FIRING surface references is NOT wired. "
            f"slice-06 must add a gate-stack reference (gate-G -> the `distill` "
            f"gate-out stack per flow-v2-design §12; self-attest + runner per "
            f"DESIGN). {self._observed()}"
        )

    def then_driving_emits_a_gate_verdict(self) -> None:
        """Driving ``des <subcommand>`` emits a §17 GateVerdict-shaped result --
        the thin CLI wrapper DRIVES the existing domain logic (AT-24/25/26)."""
        driven = self._require_driven()
        spec = self._require_spec()
        assert driven.drove_domain, (
            f"invoking `des {spec.subcommand}` must DRIVE the existing "
            f"{spec.module.value} domain logic (slice-03 evaluate_gate_g / slice-04 "
            f"self_attest.classify / slice-05 run_tests) and emit a §17 "
            f"GateVerdict-shaped result -- the subcommand produced no verdict-shaped "
            f"output (the thin CLI driver is unwired -- DELIVER must wire the wrapper "
            f"over the existing logic, NOT re-implement the domain). "
            f"{self._observed()}"
        )
        assert driven.verdict in LOCKED_GATE_VERDICTS, (
            f"`des {spec.subcommand}` must emit one of the §17 LOCKED FIVE verdict "
            f"tokens {sorted(LOCKED_GATE_VERDICTS)!r} (ADR-GV-001, no sixth -- C6) "
            f"-- got verdict={driven.verdict!r}. {self._observed()}"
        )

    # =====================================================================
    # driving-port probes (real subprocess / real shipped artifact)
    # =====================================================================

    def _probe_registration(self, spec: WiredModuleSpec) -> SubcommandRegistration:
        """Probe the REAL ``des`` dispatcher for the subcommand registration (A1).

        Layer 3 subprocess: runs ``des --help`` (advertised?) + ``des <subcommand>
        --help`` (resolvable, exit 0, vs argparse invalid-choice exit 2). The
        dispatcher is invoked the way an operator runs it (``python -m des``); at
        HEAD the unregistered row exits 2 -> resolvable=False -> the Then's named
        RED. Reads the shipped catalog for the 1:1 mirror row.
        """
        help_run = self._run_des(["--help"])
        if help_run is None:
            self._seam_error = _SEAM_ABSENT
            return SubcommandRegistration(
                advertised=False, resolvable=False, in_catalog=False
            )
        advertised = spec.subcommand in help_run.stdout
        sub_run = self._run_des([spec.subcommand, "--help"])
        resolvable = (
            sub_run is not None and sub_run.exit_code != _ARGPARSE_INVALID_CHOICE
        )
        in_catalog = self._catalog_has_gate_id(spec.subcommand)
        return SubcommandRegistration(
            advertised=advertised, resolvable=resolvable, in_catalog=in_catalog
        )

    def _probe_gate_stack_reference(self, spec: WiredModuleSpec) -> GateStackReference:
        """Probe ALL THREE shipped wiring surfaces for the module reference (A2, the closure leg).

        Mirrors the goal-contract scorecard's ``WIRING_FILES`` EXACTLY
        (scripts/flow_v2_closure_scorecard.py:50-54): scans the flavor YAMLs AND
        ``scripts/hooks/*.py`` AND ``~/.claude/hooks/*.py``, applying the EXACT
        scorecard ``_term_wired`` regex (spec.term_pattern) to each REAL artifact.
        A module referenced in ANY of the three surfaces is wired -- so a passing
        AT ⟺ a passing scorecard leg (an AT stricter than the leg would be theater
        -- the BLOCKER this mirroring closes). NEVER an inline test string
        (Mandate-13 prose-surface rule). At HEAD no surface references any module
        -> term_wired False -> the Then names the unwired module. The matched path
        (repo-relative when under the repo, else absolute) goes into
        ``referenced_in`` for the diagnostic.
        """
        rx = re.compile(spec.term_pattern)
        referenced_in: list[str] = []
        for base, pattern in _WIRING_GLOBS:
            if not base.exists():
                continue
            for surface in sorted(base.glob(pattern)):
                try:
                    text = surface.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if rx.search(text):
                    referenced_in.append(self._surface_label(surface))
        return GateStackReference(
            term_wired=bool(referenced_in),
            referenced_in=tuple(referenced_in),
        )

    @staticmethod
    def _surface_label(surface: Path) -> str:
        """A diagnostic label for a matched wiring surface (repo-relative if under the repo)."""
        try:
            return surface.relative_to(_REPO_ROOT).as_posix()
        except ValueError:
            return str(surface)

    def _drive_subcommand(self, spec: WiredModuleSpec, tmp_path: Path) -> DrivenVerdict:
        """Drive the REAL ``des <subcommand>`` end-to-end + read the §17 verdict (A3).

        Layer 3 subprocess: runs ``des <subcommand>`` over a real ``tmp_path``
        input shaped per the module, then reads the §17 GateVerdict-shaped result
        from stdout / the emitted ``--out`` envelope. At HEAD the unregistered row
        exits 2 (no verdict) -> drove_domain=False -> the Then names the missing
        thin-driver wiring.
        """
        argv, out_path = self._drive_argv_for(spec, tmp_path)
        run = self._run_des(argv)
        if run is None or run.exit_code == _ARGPARSE_INVALID_CHOICE:
            self._seam_error = _SEAM_ABSENT
            return DrivenVerdict(verdict=None, exit_code=None, drove_domain=False)
        verdict = self._read_driven_verdict(run.stdout, out_path)
        return DrivenVerdict(
            verdict=verdict,
            exit_code=run.exit_code,
            drove_domain=verdict is not None,
        )

    def _drive_argv_for(
        self, spec: WiredModuleSpec, tmp_path: Path
    ) -> tuple[list[str], Path | None]:
        """Build the ``des <subcommand>`` argv + the real tmp input per module (A3).

        Each module is driven over a CONTENT-DISTINCT real input so the driven
        verdict reflects the EXISTING domain logic, not a hard-coded template:
          * gate-design-at-coherence -> a real feature-root carrying a bijective
                         `[REF] Code-Design` + an AT module (drives evaluate_gate_g
                         -> PASS; subcommand renamed from gate-g by f-code-design
                         slice-04).
          * self-attest -> a real dual-source verdict record (drives classify).
          * verify-test-runner -> a real target dir + an --out path (drives
                         run_tests.main -> a real run / ABSTAIN envelope).
        DESIGN owns the precise CLI arg names; this composition passes the
        slice-03/04/05 module's known input shape. If DELIVER's wrapper takes
        different arg names, update this method (the SEAM, never a line number).
        """
        if spec.subcommand == "gate-design-at-coherence":
            feature_root = self._write_bijective_feature_root(tmp_path)
            return (
                [
                    "gate-design-at-coherence",
                    "--design-contract",
                    str(feature_root / "feature-delta.md"),
                    "--at-module",
                    str(feature_root / "tests" / "acceptance"),
                ],
                None,
            )
        if spec.subcommand == "self-attest":
            record_path = self._write_grounded_verdict_record(tmp_path)
            return (["self-attest", "--record", str(record_path)], None)
        # verify-test-runner: a real target dir + an --out envelope path.
        target = tmp_path / "target"
        (target / "tests").mkdir(parents=True, exist_ok=True)
        (target / "tests" / "test_smoke.py").write_text(
            "def test_smoke():\n    assert True\n", encoding="utf-8"
        )
        out_path = tmp_path / "result.json"
        return (
            [
                "verify-test-runner",
                "--target",
                str(target),
                "--out",
                str(out_path),
            ],
            out_path,
        )

    # =====================================================================
    # shipped-artifact readers + subprocess runner
    # =====================================================================

    def _run_des(self, args: list[str]) -> _DesRun | None:
        """Invoke the REAL ``des`` dispatcher IN-PROCESS (the operator's path).

        Drives the production ``des.cli.__main__:main`` EDGE directly — the same
        dispatcher ``python -m des <args>`` resolves to (``des.__main__`` delegates
        to it) — under ``cwd=_REPO_ROOT`` with captured output. ``catch_all=True``
        maps an unexpected dispatcher crash onto exit 1 with its traceback on the
        captured stderr, faithful to the non-zero exit a forked interpreter would
        have produced (the sentinel turns a setup error into the named RED, never a
        silent pass).
        """
        exit_code, stdout, stderr = run_cli_in_process(
            list(args),
            cwd=_REPO_ROOT,
            catch_all=True,
        )
        return _DesRun(exit_code=exit_code, stdout=stdout, stderr=stderr)

    def _catalog_has_gate_id(self, gate_id: str) -> bool:
        """True iff the shipped catalog carries a ``gate_id: <name>`` mirror row."""
        if not _CATALOG_PATH.is_file():
            return False
        text = _CATALOG_PATH.read_text(encoding="utf-8", errors="ignore")
        return (
            re.search(rf"^\s*-?\s*gate_id:\s*{re.escape(gate_id)}\s*$", text, re.M)
            is not None
        )

    @staticmethod
    def _read_driven_verdict(stdout: str, out_path: Path | None) -> str | None:
        """Read the §17 GateVerdict token from the driven subcommand's output (A3).

        Tries, in order: a JSON envelope on stdout carrying a ``verdict`` /
        ``status`` field; the emitted ``--out`` envelope (the runner port's
        ``nwave.test_result.v1`` / ``nwave.earned_verdict.v1``); a bare verdict
        token in stdout. Maps the runner's test-result/earned-verdict onto a §17
        token (a real run with failed==0 -> PASS; failed>0 -> FAIL; an ABSTAIN ->
        INDETERMINATE) so all three modules speak the LOCKED five.
        """
        token = GateStackWiringComposition._verdict_from_stdout(stdout)
        if token is not None:
            return token
        if out_path is not None and out_path.is_file():
            return GateStackWiringComposition._verdict_from_runner_envelope(out_path)
        return None

    @staticmethod
    def _verdict_from_stdout(stdout: str) -> str | None:
        """Read a verdict / status token from a JSON line on stdout, or a bare token."""
        for line in stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                token = payload.get("verdict") or payload.get("status")
                if isinstance(token, str):
                    return token.lower()
        # A bare verdict token printed alone (e.g. gate-G prints `pass`).
        for token in LOCKED_GATE_VERDICTS:
            if re.search(rf"\b{token}\b", stdout.lower()):
                return token
        return None

    @staticmethod
    def _verdict_from_runner_envelope(out_path: Path) -> str | None:
        """Map the runner port's emitted envelope onto a §17 verdict token.

        ``nwave.earned_verdict.v1`` ABSTAIN -> INDETERMINATE (the mechanism could
        not run); ``nwave.test_result.v1`` with failed==0 -> PASS, failed>0 ->
        FAIL. The runner DRIVES a real run (run_tests.main) -- this maps its honest
        emission onto the LOCKED five.
        """
        try:
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if payload.get("status") == "ABSTAIN":
            return "indeterminate"
        if payload.get("schema") == "nwave.test_result.v1":
            failed = payload.get("failed", 0)
            error = payload.get("error", 0)
            return "pass" if (failed == 0 and error == 0) else "fail"
        return None

    # =====================================================================
    # substrate plumbing -- real tmp inputs for the behavioural drive (A3)
    # =====================================================================

    @staticmethod
    def _write_bijective_feature_root(tmp_path: Path) -> Path:
        """A real feature-root with a bijective `[REF] Code-Design` ↔ AT pair.

        Drives the EXISTING evaluate_gate_g (slice-03) over real I/O -> PASS,
        proving the thin gate-G CLI wrapper drives the existing mechanical diff.
        """
        root = tmp_path / "gate_g_feature"
        (root / "tests" / "acceptance").mkdir(parents=True, exist_ok=True)
        (root / "feature-delta.md").write_text(
            "# feature-delta f-export-csv\n\n"
            "## Wave: DESIGN / [REF] Code-Design\n\n"
            "| ExampleTableRow | Input | Output |\n"
            "|-----------------|-------|--------|\n"
            "| full-dataset | <in> | <out> |\n"
            "| empty-dataset | <in> | <out> |\n",
            encoding="utf-8",
        )
        (root / "tests" / "acceptance" / "export_csv.feature").write_text(
            "Feature: Operator exports a CSV\n\n"
            "  Scenario: Operator exports the full-dataset case\n"
            "    Given the full-dataset dataset\n"
            "    When the operator exports a CSV\n"
            "    Then the full-dataset CSV is produced\n\n"
            "  Scenario: Operator exports the empty-dataset case\n"
            "    Given the empty-dataset dataset\n"
            "    When the operator exports a CSV\n"
            "    Then the empty-dataset CSV is produced\n",
            encoding="utf-8",
        )
        return root

    @staticmethod
    def _write_grounded_verdict_record(tmp_path: Path) -> Path:
        """A real dual-source verdict record (mechanical evidence + agreeing sources).

        Drives the EXISTING self_attest.classify (slice-04) -> PASS (a mechanical
        control found no objection), proving the thin self-attest CLI wrapper
        drives the existing classifier.
        """
        record_path = tmp_path / "verdict_record.json"
        record_path.write_text(
            json.dumps(
                {
                    "mechanical_verdict": "pass",
                    "llm_verdict": "pass",
                    "mechanical_evidence_ref": "gate-g:abc123",
                    "watchdog_timed_out": False,
                }
            ),
            encoding="utf-8",
        )
        return record_path

    # =====================================================================
    # diagnostics
    # =====================================================================

    def _require_spec(self) -> WiredModuleSpec:
        assert self._spec is not None, (
            "a slice-06 gate-stack-wiring scenario must arm an explicit feature "
            "module (gate-g / self-attest / verify-test-runner) -- got None."
        )
        return self._spec

    def _require_registration(self) -> SubcommandRegistration:
        if self._registration is None:
            raise AssertionError(
                "the slice-06 subcommand registration probe did not run -- the "
                "When step must drive the real `des` dispatcher first. "
                f"{self._observed()}"
            )
        return self._registration

    def _require_reference(self) -> GateStackReference:
        if self._reference is None:
            raise AssertionError(
                "the slice-06 gate-stack reference probe did not run -- the When "
                f"step must read the shipped flavor YAML first. {self._observed()}"
            )
        return self._reference

    def _require_driven(self) -> DrivenVerdict:
        if self._driven is None or self._seam_error == _SEAM_ABSENT:
            spec = self._spec.subcommand if self._spec is not None else "?"
            raise AssertionError(
                f"the slice-06 behavioural wiring (`des {spec}` DRIVES the existing "
                "slice-03/04/05 domain logic and emits a §17 GateVerdict-shaped "
                "result -- a thin CLI driver over evaluate_gate_g / "
                "self_attest.classify / run_tests, NOT a domain re-implementation) "
                "must exist -- the subcommand is ABSENT from the dispatcher "
                "_REGISTRY at HEAD (active-RED; DELIVER registers the row + ships "
                "the thin wrapper + references it in a flavor gate-stack). "
                f"{self._observed()}"
            )
        return self._driven

    def _observed(self) -> str:
        return (
            f"spec={self._spec!r}; registration={self._registration!r}; "
            f"reference={self._reference!r}; driven={self._driven!r}; "
            f"seam_error={self._seam_error!r}"
        )


@dataclass(frozen=True)
class _DesRun:
    """Observable outcome of one ``python -m des [args...]`` subprocess invocation.

    Universe-bound observable triple (Mandate 8, layer 3): exit_code / stdout /
    stderr -- the port-exposed names, never internal CompletedProcess attributes.
    """

    exit_code: int
    stdout: str
    stderr: str
