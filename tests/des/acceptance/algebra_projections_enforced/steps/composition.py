"""Composition root for the algebra-projections-enforced slice-01 ATs (Mandate-13).

Driving-port-only. The behaviour is driven through the REAL validate-feature-delta
gate — the ``des validate-feature-delta`` subcommand (Layer 3 subprocess:
``python -m des.cli.__main__ validate-feature-delta --require-registry-sections
<wave> --format=json <path>``) — over a real temp repo carrying a real
``feature-delta.md``. The only driven port is the real filesystem (tmp_path); the
wave-contract registry the check reads is the REAL ``nWave/waves/discuss.yaml``
in the repo (read-only), which is what makes the live-vs-hard-coded discrimination
a true observable.

Hermetic: the subprocess ``cwd`` is the tmp repo and a ``.git/`` marker is seeded
so the runtime-freshness gate AUTOSKIPS (dev-checkout) instead of refusing; the
real developer home / personal-hook path is never touched (the
``tests/meta/test_acceptance_hermeticity.py`` guard requires this).

active-RED scaffold (atdd_pure — NOT @skip). At HEAD the net-new production seam
this slice's DESIGN pins is ABSENT (verified 2026-06-22):

  * ``des validate-feature-delta`` does NOT accept ``--require-registry-sections``
    — invoked with that flag it prints its ``usage:`` banner and returns exit 1,
    emitting NO JSON ``{"verdict": ...}`` line;
  * the module functions ``read_wave_output_contract`` /
    ``classify_registry_sections`` raise an ``AssertionError`` RED-scaffold marker.

So every ``--require-registry-sections`` invocation produces no structured verdict
token -> the composition records ``UNRECOGNISED_INVOCATION`` and each ``Then``
turns that absence into a NAMED semantic ``AssertionError`` — never a collection /
import / setup error. The suite COLLECTS cleanly at HEAD (the module imported is
``des.cli.__main__`` via subprocess, always present) and every current-slice
scenario RED-fails for the right reason (missing functionality).

The check has a PURE-FUNCTION contract (DESIGN DA-2): it reads the feature-delta +
the registry and returns a verdict; it mutates NO file. ``capture_universe``
snapshots the feature-delta so the When-step state-delta guard (Mandate 8) proves
the read-only contract.

DELIVER-pinned assumptions (update HERE, not in the step bodies, if DELIVER picks
different surface shapes):

  A1 (flag): the wired surface is ``des validate-feature-delta
     --require-registry-sections <wave> --format=json <path>`` (DESIGN DA-6 /
     DD-A2). The JSON envelope carries a ``verdict`` field whose value is one of
     the closed token set (slice-01 pins ``accepted`` + ``undeclared-section``).
  A2 (diagnostic names the section): on an ``undeclared-section`` REJECT the
     emitted JSON ``detail`` field NAMES the offending section id verbatim (so the
     maintainer knows what to repair). The AT asserts the offending id is a
     substring of ``detail`` — a NAMED diagnostic, not a bare token.
  A3 (live registry): the check reads the REAL ``nWave/waves/<wave>.yaml``
     ``output_contract.ref_sections`` (the live registry), NOT the hard-coded
     ``LOCKED_REF_SECTIONS`` tuple. The LEGACY_TUPLE_ONLY + REGISTRY_ONLY shapes
     are the discriminators that fail on a tuple-reading implementation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types import DeltaShape, RegistrySectionVerdict, WaveId


# The validate-feature-delta gate's driving-port subcommand (A1).
_SUBCOMMAND_ID = "validate-feature-delta"

# A real, grep-findable feature-id the temp feature-delta self-identifies as.
_FEATURE_ID = "algebra-projections-enforced-fixture"

# A section id that is in NEITHER the discuss registry ref_sections NOR the legacy
# LOCKED_REF_SECTIONS tuple — a plainly undeclared section (UNDECLARED_SECTION).
_PLAINLY_UNDECLARED = "Totally Bogus Section"

# A section honoured by the legacy hard-coded LOCKED_REF_SECTIONS tuple
# (validate_feature_delta.py:555-560) but ABSENT from discuss.yaml ref_sections.
# A tuple-reading check passes it; a live-registry check REJECTS it (A3).
_LEGACY_TUPLE_ONLY_SECTION = "Reuse Analysis"

# A section the LIVE discuss registry declares (nWave/waves/discuss.yaml
# ref_sections) but the legacy 4-entry tuple omits. A direction-(a) live-registry
# check ACCEPTS it (it is declared); a tuple-whitelist would mishandle it (A3).
_REGISTRY_ONLY_SECTION = "Persona ID"

# The expected offending section id per rejecting shape (A2). The Then asserts the
# rejection diagnostic NAMES this id.
_OFFENDING_SECTION_BY_SHAPE: dict[DeltaShape, str] = {
    DeltaShape.UNDECLARED_SECTION: _PLAINLY_UNDECLARED,
    DeltaShape.LEGACY_TUPLE_ONLY: _LEGACY_TUPLE_ONLY_SECTION,
}


@dataclass
class _CheckObservable:
    """What the registry-section check emitted (or did not) for one invocation."""

    verdict: str | None
    detail: str | None
    recognised: bool
    raw: str


@dataclass
class RegistrySectionComposition:
    """Drives the registry-section check through its real validate-feature-delta port."""

    _shape: DeltaShape | None = field(default=None)
    _wave: WaveId | None = field(default=None)
    _repo_root: Path | None = field(default=None)
    _delta_path: Path | None = field(default=None)
    _observable: _CheckObservable | None = field(default=None)
    _universe_before: dict[str, object] | None = field(default=None)

    # =====================================================================
    # Given -- arm the feature-delta shape presented to the check
    # =====================================================================

    def given_delta_shape(self, shape: DeltaShape) -> None:
        """Arm which [REF] sections the presented feature-delta carries."""
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
        """The check returned EXACTLY the expected closed-set verdict (A1)."""
        observed = self._observed_verdict()
        assert observed == expected, (
            f"the registry-section check must return {expected.value!r} for this "
            f"feature-delta shape ({self._shape.value if self._shape else '?'}) "
            f"validated against the {self._wave!r} registry — got "
            f"{observed.value!r}. {self._diag()}"
        )

    def then_rejection_names_the_section(self) -> None:
        """The undeclared-section REJECT diagnostic NAMES the offending section (A2)."""
        assert self._shape is not None, (
            "a naming assertion requires an armed feature-delta shape."
        )
        offending = _OFFENDING_SECTION_BY_SHAPE[self._shape]
        detail = self._require_observable().detail
        assert detail is not None and offending in detail, (
            f"the registry-section rejection must NAME the offending section "
            f"{offending!r} in its diagnostic so the maintainer knows what to "
            f"repair — the emitted detail was {detail!r}. {self._diag()}"
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

    def _drive_check(self, repo_root: Path, wave: WaveId) -> _CheckObservable:
        """Run the REAL ``des validate-feature-delta`` EDGE in-process (A1).

        Drives the production ``des.cli.__main__.main`` dispatcher in-process via
        the shared ``run_cli_in_process`` driver (``cwd=repo_root``, stdout+stderr
        captured) — the in-process analogue of the former
        ``python -m des.cli.__main__ validate-feature-delta ...`` subprocess.

        At HEAD the ``--require-registry-sections`` flag is unknown, so the CLI
        prints its ``usage:`` banner and returns exit 1, emitting NO JSON envelope
        -> the observable carries ``verdict=None``, ``recognised=False``. The Then
        turns that into the named RED. GREEN once DELIVER ships the flag.
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
    # real temp-repo fixtures (the feature-delta the check inspects)
    # =====================================================================

    def _write_repo(self, tmp_path: Path) -> Path:
        """Materialise a real temp repo carrying the armed feature-delta shape."""
        assert self._shape is not None, (
            "a registry-section scenario must arm an explicit DeltaShape before "
            "the check runs."
        )
        feature_dir = tmp_path / "docs" / "feature" / _FEATURE_ID
        feature_dir.mkdir(parents=True, exist_ok=True)
        self._delta_path = feature_dir / "feature-delta.md"
        self._delta_path.write_text(self._render_feature_delta(), encoding="utf-8")
        # Env-parity: the gate subprocess runs with cwd=tmp_path (a manifest-less
        # synthetic workspace). Seed a `.git/` marker so the runtime-freshness gate
        # AUTOSKIPS (dev-checkout) instead of the customer-install REFUSAL (exit 78)
        # before the check's own logic runs. Environment SETUP, not
        # assertion-weakening. See tests/env_parity.py.
        seed_dev_checkout_marker(tmp_path)
        return tmp_path

    def _render_feature_delta(self) -> str:
        """Render a feature-delta carrying the [REF] sections the armed shape needs.

        Every shape uses ONLY discuss-registry-declared section ids EXCEPT the one
        section deliberately chosen to exercise the check:

        * ALL_DECLARED      -- three registry-declared sections (happy path).
        * UNDECLARED_SECTION -- the declared sections PLUS a plainly-undeclared
                               section (in neither registry nor tuple) -> REJECT.
        * LEGACY_TUPLE_ONLY -- the declared sections PLUS ``Reuse Analysis`` (in
                               the legacy tuple, absent from the discuss registry)
                               -> a live-registry check REJECTs (A3).
        * REGISTRY_ONLY     -- ONLY ``Persona ID`` (declared by the registry,
                               omitted by the legacy tuple) -> ACCEPT (A3).
        """
        sections = self._sections_for_shape()
        header = f"# Feature Delta: {_FEATURE_ID}\n\n"
        body = "\n\n".join(
            f"## Wave: DISCUSS / [REF] {sid}\n\nbody for {sid}." for sid in sections
        )
        return header + body + "\n"

    def _sections_for_shape(self) -> list[str]:
        """The list of [REF] section ids the armed shape's feature-delta carries.

        A module-level dispatch keeps this method a single typed lookup (no control
        flow that branches on business rules — the mapping IS the data).
        """
        return _SECTIONS_BY_SHAPE[self._shape]  # type: ignore[index]

    # =====================================================================
    # universe (Mandate 8 — port-exposed observable snapshot)
    # =====================================================================

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The check has a pure-function contract: it reads the feature-delta and MUST
        NOT mutate it. The universe is the feature-delta's existence and bytes —
        the state-delta guard proves the read-only contract.
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
        """Map the check output onto the user-observable verdict.

        Reads the structured ``verdict`` token (a MACHINE token, never free-text
        stdout). No token at all -> UNRECOGNISED_INVOCATION (the active-RED signal
        at HEAD). An off-contract token (a value not in the closed slice-01 set)
        raises rather than silently defaulting — a crafter emitting a wrong token
        fails loudly.
        """
        from .domain_types import VERDICT_TOKEN

        obs = self._require_observable()
        if obs.verdict is None:
            return RegistrySectionVerdict.UNRECOGNISED_INVOCATION
        if obs.verdict not in VERDICT_TOKEN:
            raise ValueError(
                f"the slice-01 registry-section check emitted an off-contract "
                f"verdict token {obs.verdict!r}; slice-01 pins one of "
                f"{sorted(VERDICT_TOKEN)}. {self._diag()}"
            )
        return VERDICT_TOKEN[obs.verdict]

    def _require_observable(self) -> _CheckObservable:
        assert self._observable is not None, (
            "the registry-section check driving port was never invoked — a When "
            "step must run the check before a Then reads its verdict."
        )
        return self._observable

    def _diag(self) -> str:
        obs = self._observable
        if obs is None:
            return "[no check observable captured]"
        if not obs.recognised:
            return (
                f"[the {_SUBCOMMAND_ID!r} --require-registry-sections check emitted "
                f"NO JSON verdict at HEAD — the flag is either unparsed (usage "
                f"banner) or dispatched to the RED scaffold (which raises the "
                f"RED-scaffold AssertionError before emitting a verdict); slice-01 "
                f"DELIVER ships the live-registry classifier to make it emit one] "
                f"raw={obs.raw.strip()[:280]!r}"
            )
        return (
            f"[verdict={obs.verdict!r} detail={obs.detail!r}] "
            f"raw={obs.raw.strip()[:280]!r}"
        )


# Module-level dispatch (feature-delta section composition per shape). Keeping it
# data, not branching logic in the service method, satisfies Mandate-12 criterion
# 3 (no control flow in step / service bodies that encodes business rules).
_SECTIONS_BY_SHAPE: dict[DeltaShape, list[str]] = {
    # Three registry-declared discuss sections (all in nWave/waves/discuss.yaml).
    DeltaShape.ALL_DECLARED: [
        "Locked Decisions",
        "Definition of Done",
        "Slice Plan",
    ],
    # Declared sections + one plainly-undeclared section (neither registry nor
    # tuple) -> the undeclared half of the cross-check.
    DeltaShape.UNDECLARED_SECTION: [
        "Locked Decisions",
        "Slice Plan",
        _PLAINLY_UNDECLARED,
    ],
    # Declared sections + Reuse Analysis (legacy tuple, NOT in the discuss
    # registry) -> a live-registry check REJECTs; a tuple-reader would pass.
    DeltaShape.LEGACY_TUPLE_ONLY: [
        "Locked Decisions",
        "Slice Plan",
        _LEGACY_TUPLE_ONLY_SECTION,
    ],
    # Only Persona ID (registry-declared, NOT in the legacy tuple) -> ACCEPT.
    DeltaShape.REGISTRY_ONLY: [
        _REGISTRY_ONLY_SECTION,
    ],
}
