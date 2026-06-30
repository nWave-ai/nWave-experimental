"""Composition root for the algebra-projections-enforced slice-05 ATs (Mandate-13).

slice-05 = the fail-closed boundary of the registry-section check (DESIGN DA-5 /
DD-A5, the LAST slice). Driving-port-only: the behaviour is driven through the
REAL ``des validate-feature-delta`` subcommand (Layer 3 subprocess:
``python -m des.cli.__main__ validate-feature-delta --require-registry-sections
<wave> [--waves-dir <dir>] --format=json <path>``) over a real temp repo.

The boundary has FOUR cases (``domain_types_slice_05.BoundaryCase``):

  * UNKNOWN_WAVE      -- a non-canonical wave name (``bogus``) with no registry
                        entry. Tested against the REAL repo ``nWave/waves`` dir
                        (which carries no ``bogus.yaml``) — no repo mutation
                        needed; the wave is simply not a known wave.
  * UNREADABLE_GARBLED -- a KNOWN wave (``discuss``) whose ``<wave>.yaml`` exists
                        but is GARBLED (invalid bytes). Tested against a HERMETIC
                        tmp waves-dir carrying a garbled ``discuss.yaml`` — the
                        real repo registry is NEVER mutated.
  * UNREADABLE_ABSENT  -- a KNOWN wave (``discuss``) whose ``<wave>.yaml`` is
                        ABSENT. Tested against a hermetic EMPTY tmp waves-dir.
  * KNOWN_READABLE    -- a KNOWN wave (``discuss``) with the real readable
                        registry + an all-declared delta. The byte-stable
                        happy-path preservation witness.

Hermetic tmp waves-dir injection (the two UNREADABLE cases) requires the
driving surface to accept a ``--waves-dir <dir>`` override so the garbled/absent
registry can be exercised WITHOUT mutating the real repo ``nWave/waves`` (the
``tests/meta/test_acceptance_hermeticity.py`` guard forbids touching the real
developer tree). This is a TESTABILITY-DRIVEN DELIVER obligation for slice-05,
additive and mirroring the sibling ``verify-wave-contract-coherence --waves-dir``
flag (``verify_wave_contract_coherence.py:356``); it carries NO new gate-id
(DD-A2). See ``distill/red-classification.md`` slice-05 §"What DELIVER makes
GREEN".

active-RED scaffold (atdd_pure — NOT @skip). At HEAD the boundary verdict promotion
this slice's DESIGN pins is ABSENT (verified 2026-06-22 by direct probe):

  * UNKNOWN_WAVE / UNREADABLE_*: ``read_wave_output_contract`` returns ``None`` for
    BOTH an absent and a garbled registry, so the shell prints
    ``error: wave registry for '<wave>' is unreadable`` to stderr and returns
    exit 1 emitting NO JSON ``{"verdict": ...}`` line
    (``validate_feature_delta.py:1224-1231``). It (i) never distinguishes
    unknown-wave from unreadable-registry, and (ii) never emits a structured
    verdict token at all.
  * ``--waves-dir`` is not parsed at HEAD (the flag is unknown -> usage banner).

So every boundary invocation at HEAD produces no structured verdict token -> the
composition records ``UNRECOGNISED_INVOCATION`` and each ``Then`` turns that
absence into a NAMED semantic ``AssertionError`` — never a collection / import /
setup error. The suite COLLECTS cleanly at HEAD (the module imported is
``des.cli.__main__`` via subprocess, always present) and every current-slice
scenario RED-fails for the right reason (missing functionality).

The check has a PURE-FUNCTION contract on the happy path (DESIGN DA-2) and a
fail-closed boundary contract (DA-5): it reads the feature-delta + the registry
and returns a verdict; it mutates NO file. ``capture_universe`` snapshots the
feature-delta so the read-only contract is provable at the boundary too (Mandate
8).

DELIVER-pinned assumptions (update HERE, not in the step bodies, if DELIVER picks
different surface shapes):

  A1 (flag): the boundary surface is ``des validate-feature-delta
     --require-registry-sections <wave> [--waves-dir <dir>] --format=json <path>``.
     The JSON envelope carries a ``verdict`` field whose value is one of the
     closed boundary set (slice-05 pins ``unknown-wave`` + ``indeterminate``, and
     reuses ``accepted`` for the preservation witness).
  A2 (un-gameable): the boundary verdicts are NEVER ``accepted`` (no silent
     green) and NEVER a crash/stacktrace (no exit > 1 with a traceback). The AT
     asserts the exact closed-set token AND a clean (non-crash) process.
  A3 (waves-dir override): ``--waves-dir <dir>`` (additive, DD-A2; mirrors the
     coherence-gate sibling) lets the UNREADABLE_* cases point the check at a
     hermetic tmp registry dir so the real repo ``nWave/waves`` is never mutated.
     The UNKNOWN_WAVE case needs NO override (it uses the real repo dir, which has
     no ``bogus.yaml``).
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tests.env_parity import seed_dev_checkout_marker

from .domain_types_slice_05 import BoundaryCase, BoundaryVerdict, WaveId


# The validate-feature-delta gate's driving-port subcommand (A1).
_SUBCOMMAND_ID = "validate-feature-delta"

# A real, grep-findable feature-id the temp feature-delta self-identifies as.
_FEATURE_ID = "algebra-projections-enforced-slice05-fixture"

# A wave name that is NOT a canonical nWave wave and has no registry entry — the
# unknown-wave argument. (The canonical waves are DISCOVER/DIVERGE/DISCUSS/DESIGN/
# DEVOPS/DISTILL/DELIVER; `bogus` is none of them and `nWave/waves/bogus.yaml`
# does not exist.)
_UNKNOWN_WAVE = WaveId("bogus")

# A KNOWN wave whose registry the UNREADABLE_* cases corrupt / remove in a
# hermetic tmp waves-dir (the real repo registry is NEVER touched).
_KNOWN_WAVE = WaveId("discuss")

# Bytes that are not valid UTF-8 -> read_text(encoding="utf-8") raises
# UnicodeDecodeError -> read_wave_output_contract returns None (the garbled
# registry the INDETERMINATE boundary keys on).
_GARBLED_REGISTRY_BYTES = b"\xff\xfe output_contract: \x80\x81 ref_sections garbled"

# The repo's REAL waves dir (carries discuss.yaml etc.) — the anchor for the
# UNKNOWN_WAVE case (no bogus.yaml there) and the source the KNOWN_READABLE case
# reads. tests/des/acceptance/.../steps/<this> -> parents[5] = repo root.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_REAL_WAVES_DIR = _REPO_ROOT / "nWave" / "waves"


@dataclass
class _CheckObservable:
    """What the boundary check emitted (or did not) for one invocation."""

    verdict: str | None
    detail: str | None
    exit_code: int
    crashed: bool
    raw: str


@dataclass
class RegistrySectionBoundaryComposition:
    """Drives the registry-section check into its fail-closed boundary (slice-05)."""

    _case: BoundaryCase | None = field(default=None)
    _wave: WaveId | None = field(default=None)
    _repo_root: Path | None = field(default=None)
    _delta_path: Path | None = field(default=None)
    _waves_dir: Path | None = field(default=None)
    _observable: _CheckObservable | None = field(default=None)
    _universe_before: dict[str, object] | None = field(default=None)

    # =====================================================================
    # Given -- arm the fail-closed boundary case
    # =====================================================================

    def given_boundary_case(self, case: BoundaryCase) -> None:
        """Arm which fail-closed boundary the check is driven into."""
        self._case = case

    # =====================================================================
    # When -- drive the REAL check over a real temp repo at the boundary
    # =====================================================================

    def when_the_boundary_check_runs(self, tmp_path: Path) -> None:
        """Materialise the armed boundary (delta + waves-dir), run the REAL check."""
        self._repo_root = self._write_repo(tmp_path)
        self._waves_dir = self._waves_dir_for_case(tmp_path)
        self._wave = self._wave_for_case()
        self._universe_before = self.capture_universe()
        self._observable = self._drive_check(self._repo_root)

    # =====================================================================
    # Then -- observable readers (the closed boundary verdict + un-gameability)
    # =====================================================================

    def then_verdict_is(self, expected: BoundaryVerdict) -> None:
        """The boundary returned EXACTLY the expected closed-set verdict (A1)."""
        observed = self._observed_verdict()
        assert observed == expected, (
            f"the registry-section boundary must return {expected.value!r} for the "
            f"{self._case.value if self._case else '?'} case (wave "
            f"{self._wave!r}) — got {observed.value!r}. {self._diag()}"
        )

    def then_never_accepted(self) -> None:
        """Un-gameable: a boundary case is NEVER a silent green (A2)."""
        observed = self._observed_verdict()
        assert observed is not BoundaryVerdict.ACCEPTED, (
            f"the {self._case.value if self._case else '?'} boundary case must "
            f"NEVER collapse to 'accepted' — a missing/garbled/unknown registry is "
            f"never a silent green (DESIGN DA-5). {self._diag()}"
        )

    def then_did_not_crash(self) -> None:
        """Un-gameable: the boundary degrades cleanly, never a stacktrace (A2)."""
        obs = self._require_observable()
        assert not obs.crashed, (
            f"the registry-section boundary must degrade with a structured verdict, "
            f"NEVER crash with a stacktrace — the {self._case.value if self._case else '?'} "
            f"case raised an uncaught traceback. {self._diag()}"
        )

    def then_feature_delta_unchanged(self) -> None:
        """Pure-function contract: the check mutates no file (Mandate 8 / DA-2)."""
        from tests.common.state_delta import assert_state_delta, unchanged

        assert self._universe_before is not None, (
            "the check must have run (capturing the before-universe) before the "
            "read-only contract can be asserted."
        )
        assert_state_delta(
            before=self._universe_before,
            after=self.capture_universe(),
            universe={"feature_delta.exists", "feature_delta.bytes"},
            expected={
                "feature_delta.exists": unchanged(),
                "feature_delta.bytes": unchanged(),
            },
        )

    # =====================================================================
    # driving-port invocation (real subprocess -> sentinel on absence)
    # =====================================================================

    def _drive_check(self, repo_root: Path) -> _CheckObservable:
        """Run the REAL ``des validate-feature-delta`` subprocess at the boundary (A1).

        At HEAD the boundary emits NO JSON envelope (unknown/unreadable collapse to
        a stderr ``error: ... is unreadable`` + exit 1, and ``--waves-dir`` is
        unparsed), so the observable carries ``verdict=None`` -> the Then turns
        that into the named RED. GREEN once DELIVER ships the typed boundary
        verdicts + the ``--waves-dir`` override.
        """
        assert self._delta_path is not None, (
            "the feature-delta fixture must be written before the boundary check runs."
        )
        assert self._wave is not None and self._waves_dir is not None, (
            "the boundary case must arm a wave + waves-dir before the check runs."
        )
        argv = [
            sys.executable,
            "-m",
            "des.cli.__main__",
            _SUBCOMMAND_ID,
            "--require-registry-sections",
            str(self._wave),
            "--waves-dir",
            str(self._waves_dir),
            "--format=json",
            str(self._delta_path),
        ]
        completed = subprocess.run(
            argv,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        raw = f"{completed.stdout}\n{completed.stderr}"
        crashed = "Traceback (most recent call last)" in completed.stderr
        verdict, detail = self._parse_envelope(completed.stdout)
        return _CheckObservable(
            verdict=verdict,
            detail=detail,
            exit_code=completed.returncode,
            crashed=crashed,
            raw=raw,
        )

    @staticmethod
    def _parse_envelope(stdout: str) -> tuple[str | None, str | None]:
        """Pull the ``verdict`` + ``detail`` fields out of the JSON envelope (A1)."""
        for line in reversed(stdout.splitlines()):
            stripped = line.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "verdict" in payload:
                verdict = payload.get("verdict")
                detail = payload.get("detail")
                return (
                    str(verdict) if verdict is not None else None,
                    str(detail) if detail is not None else None,
                )
        return None, None

    # =====================================================================
    # real temp-repo + waves-dir fixtures (the boundary the check inspects)
    # =====================================================================

    def _write_repo(self, tmp_path: Path) -> Path:
        """Materialise a real temp repo carrying a fully-declared feature-delta.

        Every boundary case uses a VALID, all-declared feature-delta — the boundary
        being exercised is the WAVE/REGISTRY axis, not the delta-section axis (that
        is slice-01/03 turf). So the delta is held constant + valid and only the
        wave + waves-dir vary; a boundary verdict can therefore NEVER be blamed on
        the delta.
        """
        feature_dir = tmp_path / "docs" / "feature" / _FEATURE_ID
        feature_dir.mkdir(parents=True, exist_ok=True)
        self._delta_path = feature_dir / "feature-delta.md"
        self._delta_path.write_text(self._render_feature_delta(), encoding="utf-8")
        # Env-parity: seed a `.git/` marker so the runtime-freshness gate AUTOSKIPS
        # (dev-checkout) instead of the customer-install REFUSAL before the check's
        # own logic runs. Environment SETUP, not assertion-weakening.
        seed_dev_checkout_marker(tmp_path)
        return tmp_path

    @staticmethod
    def _render_feature_delta() -> str:
        """A valid feature-delta carrying three discuss-registry-declared sections.

        Held constant + valid across every boundary case (see ``_write_repo``).
        """
        sections = ["Locked Decisions", "Definition of Done", "Slice Plan"]
        header = f"# Feature Delta: {_FEATURE_ID}\n\n"
        body = "\n\n".join(
            f"## Wave: DISCUSS / [REF] {sid}\n\nbody for {sid}." for sid in sections
        )
        return header + body + "\n"

    def _waves_dir_for_case(self, tmp_path: Path) -> Path:
        """The waves-dir the armed boundary case points the check at.

        A module-level dispatch keeps this a single typed lookup (Mandate-12
        criterion 3 — the case→behaviour mapping is data; the per-case
        materialisation is a small typed helper, no business-rule branching in a
        step body).
        """
        builder = _WAVES_DIR_BUILDER_BY_CASE[self._require_case()]
        return builder(self, tmp_path)

    def _wave_for_case(self) -> WaveId:
        """The wave argument the armed boundary case passes to the check."""
        return _WAVE_BY_CASE[self._require_case()]

    def _build_real_waves_dir(self, _tmp_path: Path) -> Path:
        """UNKNOWN_WAVE / KNOWN_READABLE: use the REAL repo waves dir (read-only)."""
        return _REAL_WAVES_DIR

    def _build_garbled_waves_dir(self, tmp_path: Path) -> Path:
        """UNREADABLE_GARBLED: a hermetic tmp waves-dir with a garbled discuss.yaml."""
        waves = tmp_path / "garbled_waves"
        waves.mkdir(parents=True, exist_ok=True)
        (waves / f"{_KNOWN_WAVE}.yaml").write_bytes(_GARBLED_REGISTRY_BYTES)
        return waves

    def _build_absent_waves_dir(self, tmp_path: Path) -> Path:
        """UNREADABLE_ABSENT: a hermetic EMPTY tmp waves-dir (no discuss.yaml)."""
        waves = tmp_path / "empty_waves"
        waves.mkdir(parents=True, exist_ok=True)
        return waves

    # =====================================================================
    # universe (Mandate 8 — port-exposed observable snapshot)
    # =====================================================================

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8)."""
        path = self._delta_path
        return {
            "feature_delta.exists": path.exists() if path is not None else False,
            "feature_delta.bytes": (
                path.read_bytes() if path is not None and path.exists() else None
            ),
        }

    # =====================================================================
    # internal observable accessors
    # =====================================================================

    def _observed_verdict(self) -> BoundaryVerdict:
        """Map the check output onto the user-observable boundary verdict.

        Reads the structured ``verdict`` token (a MACHINE token, never free-text).
        No token at all -> UNRECOGNISED_INVOCATION (the active-RED signal at HEAD).
        An off-contract token (a value not in the closed slice-05 boundary set)
        raises rather than silently defaulting — a crafter emitting a wrong token
        fails loudly.
        """
        from .domain_types_slice_05 import BOUNDARY_VERDICT_TOKEN

        obs = self._require_observable()
        if obs.verdict is None:
            return BoundaryVerdict.UNRECOGNISED_INVOCATION
        if obs.verdict not in BOUNDARY_VERDICT_TOKEN:
            raise ValueError(
                f"the slice-05 boundary check emitted an off-contract verdict token "
                f"{obs.verdict!r}; slice-05 pins one of "
                f"{sorted(BOUNDARY_VERDICT_TOKEN)}. {self._diag()}"
            )
        return BOUNDARY_VERDICT_TOKEN[obs.verdict]

    def _require_observable(self) -> _CheckObservable:
        assert self._observable is not None, (
            "the boundary check driving port was never invoked — a When step must "
            "run the check before a Then reads its verdict."
        )
        return self._observable

    def _require_case(self) -> BoundaryCase:
        assert self._case is not None, (
            "a boundary scenario must arm an explicit BoundaryCase before the check "
            "runs."
        )
        return self._case

    def _diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "[no boundary observable captured]"
        return (
            f"[verdict={obs.verdict!r} detail={obs.detail!r} exit={obs.exit_code} "
            f"crashed={obs.crashed}] raw={obs.raw.strip()[:320]!r}"
        )


# Module-level dispatch (per-case wave + waves-dir builder). Keeping it data, not
# branching logic in the When body, satisfies Mandate-12 criterion 3.
_WAVE_BY_CASE: dict[BoundaryCase, WaveId] = {
    BoundaryCase.UNKNOWN_WAVE: _UNKNOWN_WAVE,
    BoundaryCase.UNREADABLE_GARBLED: _KNOWN_WAVE,
    BoundaryCase.UNREADABLE_ABSENT: _KNOWN_WAVE,
    BoundaryCase.KNOWN_READABLE: _KNOWN_WAVE,
}

_WAVES_DIR_BUILDER_BY_CASE = {
    BoundaryCase.UNKNOWN_WAVE: RegistrySectionBoundaryComposition._build_real_waves_dir,
    BoundaryCase.UNREADABLE_GARBLED: (
        RegistrySectionBoundaryComposition._build_garbled_waves_dir
    ),
    BoundaryCase.UNREADABLE_ABSENT: (
        RegistrySectionBoundaryComposition._build_absent_waves_dir
    ),
    BoundaryCase.KNOWN_READABLE: (
        RegistrySectionBoundaryComposition._build_real_waves_dir
    ),
}
