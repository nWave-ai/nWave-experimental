"""Composition root for the algebra-projections-enforced slice-03 ATs (Mandate-13).

Driving-port-only. The behaviour is driven through the REAL validate-feature-delta
gate — the ``des validate-feature-delta`` subcommand (Layer 3 subprocess:
``python -m des.cli.__main__ validate-feature-delta --require-registry-sections
distill --format=json <path>``) — over a real temp repo carrying a real
``feature-delta.md`` of DISTILL ``[REF]`` sections. The only driven port is the
real filesystem (tmp_path); the wave-contract registry the check reads is the REAL
``nWave/waves/distill.yaml`` in the repo (read-only). The live read of distill.yaml
is what makes the "is the output_contract block present?" discrimination a true
observable.

active-RED scaffold (atdd_pure — NOT @skip). The slice-03 production change is a
DATA block, not code: ``nWave/waves/distill.yaml`` carries a ``gate_stack`` but NO
``output_contract`` block (verified grep-0, 2026-06-22). So at HEAD
``read_wave_output_contract("distill")`` returns a WaveOutputContract with
``ref_sections=()`` — an EMPTY contract. The ``--require-registry-sections`` flag
and the direction-(a) classifier are ALREADY shipped (slice-01), so the subprocess
emits a real JSON verdict — but with an empty distill contract:

  * an ALL_DISTILL_DECLARED delta -> every DISTILL section is "undeclared"
    -> verdict ``undeclared-section`` (RED; expected ``accepted`` post-DELIVER);
  * an UNDECLARED_DISTILL_SECTION delta -> the verdict names the FIRST DISTILL
    section, NOT the bogus one -> the naming assertion RED-fails;
  * a SINGLE_DISTILL_DECLARED delta -> the one declared section is "undeclared"
    -> verdict ``undeclared-section`` (RED; expected ``accepted`` post-DELIVER).

DELIVER A_GREEN adds the ``output_contract.ref_sections`` block (8 entries, DESIGN
Point 4) to distill.yaml — no production code — to turn these GREEN. The suite
COLLECTS cleanly at HEAD (the module imported is ``des.cli.__main__`` via
subprocess, always present) and every slice-03 scenario RED-fails for the right
reason (the missing distill contract block).

The check has a PURE-FUNCTION contract (DESIGN DA-2): it reads the feature-delta +
the registry and returns a verdict; it mutates NO file. ``capture_universe``
snapshots the feature-delta so the When-step state-delta guard (Mandate 8) proves
the read-only contract.

DELIVER-pinned assumptions (mirror slice-01 composition A1/A2/A3):

  A1 (flag): the wired surface is ``des validate-feature-delta
     --require-registry-sections distill --format=json <path>`` — ALREADY shipped
     (slice-01). The JSON envelope carries a ``verdict`` field whose value is one
     of the closed token set (slice-01/03 pin ``accepted`` + ``undeclared-section``).
  A2 (diagnostic names the section): on an ``undeclared-section`` REJECT the
     emitted JSON ``detail`` NAMES the offending section id verbatim. The AT
     asserts the plainly-undeclared id is a substring of ``detail``.
  A3 (live registry / the slice-03 production change): the check reads the REAL
     ``nWave/waves/distill.yaml output_contract.ref_sections`` (the live registry).
     At HEAD that block is ABSENT; DELIVER ADDS it (8 entries). The ALL_DISTILL_
     DECLARED + SINGLE_DISTILL_DECLARED shapes are the discriminators that fail on
     a distill.yaml with no output_contract block and pass once it is added.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types_slice_03 import (
    DISTILL_DECLARED_SECTIONS,
    PLAINLY_UNDECLARED_DISTILL_SECTION,
    DistillDeltaShape,
    RegistrySectionVerdict,
    WaveId,
)


# The validate-feature-delta gate's driving-port subcommand (A1).
_SUBCOMMAND_ID = "validate-feature-delta"

# A real, grep-findable feature-id the temp feature-delta self-identifies as.
_FEATURE_ID = "algebra-projections-enforced-slice03-fixture"

# The expected offending section id per rejecting shape (A2). The Then asserts the
# rejection diagnostic NAMES this id. Only UNDECLARED_DISTILL_SECTION rejects on a
# NAMED bogus section (the other RED shapes reject the FIRST declared section at
# HEAD, which is exactly the wrong-reason the contract block fixes).
_OFFENDING_SECTION_BY_SHAPE: dict[DistillDeltaShape, str] = {
    DistillDeltaShape.UNDECLARED_DISTILL_SECTION: PLAINLY_UNDECLARED_DISTILL_SECTION,
}

# Module-level dispatch (DISTILL feature-delta section composition per shape).
# Keeping it data, not branching logic in the service method, satisfies Mandate-12
# criterion 3 (no control flow encoding business rules in step / service bodies).
_SECTIONS_BY_SHAPE: dict[DistillDeltaShape, list[str]] = {
    # EXACTLY the 8 distill-declared sections (the happy path / walking skeleton).
    DistillDeltaShape.ALL_DISTILL_DECLARED: list(DISTILL_DECLARED_SECTIONS),
    # The 8 declared sections + one plainly-undeclared distill section.
    DistillDeltaShape.UNDECLARED_DISTILL_SECTION: [
        *DISTILL_DECLARED_SECTIONS,
        PLAINLY_UNDECLARED_DISTILL_SECTION,
    ],
    # ONLY one distill-declared section (declared once the block exists).
    DistillDeltaShape.SINGLE_DISTILL_DECLARED: [
        "Scenario List with Tags",
    ],
}


@dataclass
class _CheckObservable:
    """What the registry-section check emitted (or did not) for one invocation."""

    verdict: str | None
    detail: str | None
    recognised: bool
    raw: str


@dataclass
class DistillRegistrySectionComposition:
    """Drives the distill registry-section check through its real CLI port."""

    _shape: DistillDeltaShape | None = field(default=None)
    _wave: WaveId | None = field(default=None)
    _repo_root: Path | None = field(default=None)
    _delta_path: Path | None = field(default=None)
    _observable: _CheckObservable | None = field(default=None)
    _universe_before: dict[str, object] | None = field(default=None)

    # =====================================================================
    # Given -- arm the DISTILL feature-delta shape presented to the check
    # =====================================================================

    def given_distill_delta_shape(self, shape: DistillDeltaShape) -> None:
        """Arm which DISTILL [REF] sections the presented feature-delta carries."""
        self._shape = shape

    # =====================================================================
    # When -- drive the REAL check over a real temp repo
    # =====================================================================

    def when_the_check_runs_for_wave(self, wave: WaveId, tmp_path: Path) -> None:
        """Write a real temp repo for the armed shape, then run the REAL check (A1)."""
        self._wave = wave
        self._repo_root = self._write_repo(tmp_path)
        self._universe_before = self.capture_universe()
        self._observable = self._drive_check(self._repo_root, wave)

    # =====================================================================
    # Then -- observable readers (the structured verdict + the named diagnostic)
    # =====================================================================

    def then_verdict_is(self, expected: RegistrySectionVerdict) -> None:
        """The check returned EXACTLY the expected closed-set verdict (A1/A3)."""
        observed = self._observed_verdict()
        assert observed == expected, (
            f"the distill registry-section check must return {expected.value!r} for "
            f"this feature-delta shape ({self._shape.value if self._shape else '?'}) "
            f"validated against the {self._wave!r} registry — got "
            f"{observed.value!r}. This RED-fails until distill.yaml carries the "
            f"output_contract.ref_sections block (DESIGN Point 4). {self._diag()}"
        )

    def then_rejection_names_the_section(self) -> None:
        """The undeclared-section REJECT diagnostic NAMES the offending section (A2)."""
        assert self._shape is not None, (
            "a naming assertion requires an armed feature-delta shape."
        )
        offending = _OFFENDING_SECTION_BY_SHAPE[self._shape]
        detail = self._require_observable().detail
        assert detail is not None and offending in detail, (
            f"the distill registry-section rejection must NAME the offending section "
            f"{offending!r} in its diagnostic — but with no distill output_contract "
            f"block at HEAD the check names the FIRST declared section instead. The "
            f"emitted detail was {detail!r}. {self._diag()}"
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
    # driving-port invocation (real subprocess)
    # =====================================================================

    def _drive_check(self, repo_root: Path, wave: WaveId) -> _CheckObservable:
        """Run the REAL ``des validate-feature-delta`` EDGE in-process (A1/A3).

        The ``--require-registry-sections`` flag IS shipped (slice-01), so the CLI
        emits a JSON envelope. At HEAD distill.yaml carries NO output_contract block
        -> the distill contract is empty -> the verdict / named section is wrong for
        the DISTILL shapes. The Then turns that into the named RED. GREEN once
        DELIVER adds the output_contract.ref_sections block to distill.yaml.
        """
        assert self._delta_path is not None, (
            "the feature-delta fixture must be written before the check runs."
        )
        _exit_code, stdout, stderr = run_cli_in_process(
            [
                _SUBCOMMAND_ID,
                "--require-registry-sections",
                str(wave),
                "--format=json",
                str(self._delta_path),
            ],
            cwd=repo_root,
        )
        raw = f"{stdout}\n{stderr}"
        recognised = "usage:" not in stderr.lower()
        verdict, detail = self._parse_envelope(stdout)
        return _CheckObservable(
            verdict=verdict,
            detail=detail,
            recognised=recognised and verdict is not None,
            raw=raw,
        )

    @staticmethod
    def _parse_envelope(stdout: str) -> tuple[str | None, str | None]:
        """Pull the ``verdict`` + ``detail`` fields out of the JSON envelope (A1/A2)."""
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
    # real temp-repo fixtures (the DISTILL feature-delta the check inspects)
    # =====================================================================

    def _write_repo(self, tmp_path: Path) -> Path:
        """Materialise a real temp repo carrying the armed DISTILL feature-delta."""
        assert self._shape is not None, (
            "a distill registry-section scenario must arm an explicit "
            "DistillDeltaShape before the check runs."
        )
        feature_dir = tmp_path / "docs" / "feature" / _FEATURE_ID
        feature_dir.mkdir(parents=True, exist_ok=True)
        self._delta_path = feature_dir / "feature-delta.md"
        self._delta_path.write_text(self._render_feature_delta(), encoding="utf-8")
        # Env-parity: seed a `.git/` marker so the runtime-freshness gate AUTOSKIPS
        # (dev-checkout) instead of the customer-install REFUSAL before the check's
        # own logic runs. Environment SETUP, not assertion-weakening.
        seed_dev_checkout_marker(tmp_path)
        return tmp_path

    def _render_feature_delta(self) -> str:
        """Render a feature-delta carrying the DISTILL [REF] sections the shape needs."""
        sections = self._sections_for_shape()
        header = f"# Feature Delta: {_FEATURE_ID}\n\n"
        body = "\n\n".join(
            f"## Wave: DISTILL / [REF] {sid}\n\nbody for {sid}." for sid in sections
        )
        return header + body + "\n"

    def _sections_for_shape(self) -> list[str]:
        """The list of DISTILL [REF] section ids the armed shape carries (typed lookup)."""
        return _SECTIONS_BY_SHAPE[self._shape]  # type: ignore[index]

    # =====================================================================
    # universe (Mandate 8 — port-exposed observable snapshot)
    # =====================================================================

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The check has a pure-function contract: it reads the feature-delta and MUST
        NOT mutate it. The universe is the feature-delta's existence and bytes.
        """
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

    def _observed_verdict(self) -> RegistrySectionVerdict:
        """Map the check output onto the user-observable verdict (structured token)."""
        from .domain_types_slice_03 import VERDICT_TOKEN

        obs = self._require_observable()
        if obs.verdict is None:
            return RegistrySectionVerdict.UNRECOGNISED_INVOCATION
        if obs.verdict not in VERDICT_TOKEN:
            raise ValueError(
                f"the distill registry-section check emitted an off-contract verdict "
                f"token {obs.verdict!r}; slice-03 pins one of {sorted(VERDICT_TOKEN)}. "
                f"{self._diag()}"
            )
        return VERDICT_TOKEN[obs.verdict]

    def _require_observable(self) -> _CheckObservable:
        assert self._observable is not None, (
            "the distill registry-section check driving port was never invoked — a "
            "When step must run the check before a Then reads its verdict."
        )
        return self._observable

    def _diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "[no check observable captured]"
        return (
            f"[verdict={obs.verdict!r} detail={obs.detail!r}] "
            f"raw={obs.raw.strip()[:280]!r}"
        )
