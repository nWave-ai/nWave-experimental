"""slice-05 composition root -- wave-dispatch guard (DDD-8/9, CT-8/9/10, AT-A7/A8).

RE-HOMED (orchestrator augment 2026-06-16): the production wave-dispatch guard is
PRODUCTION RUNTIME enforcement in the DES runtime -- a pure domain policy
(``src/des/domain/wave_dispatch_guard_policy.py``) + a thin ``des.cli`` gate
(``src/des/cli/verify_wave_dispatch.py``) MIRRORING ``verify_readiness_pre_dispatch.py``,
composed onto ``dispatch.pre``. NOT the hand-placed personal dispatch-guard hook
under the developer home dir (which has no repo source -- DDD-8). The pre-re-home
held composition drove that personal hook via a developer-home read -- non-hermetic,
which ``tests/meta/test_acceptance_hermeticity.py`` forbids in any COLLECTED
acceptance test. This re-homed composition drives the IN-TREE gate ``python -m
des.cli.verify_wave_dispatch`` HERMETICALLY (args + a tmp fixture prompt FILE, no
developer-home read anywhere).

DRIVING PORT (Mandate-13, Layer-3 subprocess): the gate's ``main()`` takes ARGS
(``--subagent-type`` / ``--prompt-path`` / ``--repo-root`` / ``--session-id``)
and projects its decision onto the process EXIT CODE (ALLOW=0 / BLOCK=1 /
malformed=2, §22.0 H-2) plus one JSON line on stdout. We invoke it as a real
subprocess (``python -m des.cli.verify_wave_dispatch`` with ``PYTHONPATH`` = repo
root) and read the exit code + the printed verdict/reason token -- the real
driving surface, no guard logic re-implemented in the step bodies.

DORMANT-SEAM (D11 / DDD-8): the net-new load-bearing seams are (a) the wave->owner
map + ``DISPATCH_GUARD_VOCABULARY`` in the new domain policy, and (b) the
``verify_wave_dispatch`` gate. At HEAD neither module exists, so the subprocess
exits non-zero on module-absence -- NEITHER the expected ALLOW (0) nor BLOCK (1).
The witnessing AT drives the gate through the real entry point and asserts the
exit-code observable effect, never a claim the map "exists".

DISTINCT-FIXTURE-PER-VERDICT: marker-absent / marker-present / platform-architect-
design / platform-architect-devops / reviewer / form-valid-witness / form-invalid-
witness / valid-pre-grant / expired-grant are GENUINELY different dispatch+witness+
grant states (different args + different on-disk prompt fixtures / witnesses /
grants), never one payload re-asserted.

ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD the policy + the gate do not exist,
so every scenario observes a module-absent non-zero exit -- semantic
AssertionErrors against the expected ALLOW/BLOCK verdict, never collection / import
/ setup errors (the AT imports nothing from the absent SUT; it shells out).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types_nonbypassable import GuardDecision


# tests/des/acceptance/f_nonbypassable_attestation/steps/<this file> when collected
#   parents[5] = REPO_ROOT (mirrors composition_nonbypassable.REPO_ROOT)
REPO_ROOT = Path(__file__).resolve().parents[5]

# The IN-TREE gate module the slice ships (DELIVER creates it). The AT drives it
# via `python -m des.cli.verify_wave_dispatch` -- the real shipped artifact at
# its runtime home (Mandate-13 protocol-driver contract). No ~/.claude path.
_GATE_MODULE = "des.cli.verify_wave_dispatch"

# The DDD-8 wave->owner map the gate's policy must recognize. Owners only;
# reviewers are deliberately excluded (§22.0 controls). The marker token is the
# `DES-WAVE:` value the owner's spine dispatch carries.
_WAVE_OWNER_MARKERS: dict[str, str] = {
    "nw-product-discoverer": "discover",
    "nw-diverger": "diverge",
    "nw-product-owner": "discuss",
    "nw-solution-architect": "design",
    # DESIGN has four authoring owners (feature-delta:114) -- ddd-architect + system-designer
    # are DESIGN wave-owners too (mirrors the policy WAVE_OWNERS map).
    "nw-ddd-architect": "design",
    "nw-system-designer": "design",
    "nw-acceptance-designer": "distill",
    # nw-platform-architect owns BOTH design (infra) + devops; either marker is on-spine.
    "nw-platform-architect": "design",
}

_PLATFORM_ARCHITECT = "nw-platform-architect"

# A representative reviewer subagent_type -- never in the map, always allowed (CT-9).
_REVIEWER_TYPE = "nw-solution-architect-reviewer"

_WAVE_SKIP_HEADING_TEMPLATE = "## Wave: {wave} / [REF] Wave Skipped"

_PROBE_FEATURE_ID = "probe"
_SESSION_ID = "sess-probe-0001"


@pytest.fixture
def guard() -> WaveDispatchGuardComposition:
    return WaveDispatchGuardComposition()


@dataclass
class WaveDispatchGuardComposition:
    """Drives the IN-TREE ``des.cli.verify_wave_dispatch`` gate via its ARGS protocol.

    DRIVING PORT (Mandate-13, Layer-3 subprocess): ``python -m des.cli.verify_wave_dispatch``
    with ``--subagent-type``/``--prompt-path``/``--repo-root``/``--session-id``.
    The prompt FILE (not stdin) keeps the AT hermetic. The observable is the exit
    code (ALLOW=0 / BLOCK=1) + the one JSON line on stdout.
    """

    _project_root: Path | None = None
    _exit_code: int | None = None
    _stdout: str = ""
    _subagent: str = ""
    _marker_wave: str | None = None
    _session_id: str = _SESSION_ID

    # ---- GIVEN: arm the dispatch + on-disk witness/grant state ----------------

    def use_project_root(self, root: Path) -> None:
        self._project_root = root
        (root / ".nwave" / "des").mkdir(parents=True, exist_ok=True)
        # Mark the tmp workspace as a developer checkout (empty `.git/`) so the
        # `des.cli` freshness gate (`assert_fresh_or_explain`) AUTOSKIPS instead of
        # fail-closed exit 78 ("no install manifest") on the manifest-less tmp tree,
        # BEFORE the wave-dispatch gate runs. Mirrors the sibling subprocess AT
        # pattern (tests/des/acceptance/readiness_reuse_invariant/conftest.py:376).
        # Harness wiring only -- changes neither the args nor any asserted observable.
        seed_dev_checkout_marker(root)

    def given_wave_owner(self, owner: object) -> None:
        """Arm a wave-OWNER dispatch (subagent_type from the DDD-8 map)."""
        self._subagent = getattr(owner, "value", str(owner))

    def given_platform_architect(self) -> None:
        """Arm the dual-ownership platform architect dispatch (DESIGN-infra + DEVOPS)."""
        self._subagent = _PLATFORM_ARCHITECT

    def given_reviewer(self) -> None:
        """Arm a reviewer dispatch (never in the map -> always allowed, CT-9)."""
        self._subagent = _REVIEWER_TYPE

    def given_no_des_wave_marker(self) -> None:
        self._marker_wave = None

    def given_matching_des_wave_marker(self) -> None:
        """Carry the DES-WAVE marker matching this owner's wave (on-spine, CT-9)."""
        self._marker_wave = _WAVE_OWNER_MARKERS.get(self._subagent)

    def given_wave_marker(self, wave: str) -> None:
        """Carry an explicit DES-WAVE marker token (CT-9 platform-architect variants)."""
        self._marker_wave = wave

    def write_wave_skip_witness(self, wave: str, rationale: str) -> None:
        """Write a `## Wave: <WAVE> / [REF] Wave Skipped` witness with the given body.

        rationale="" arms the FORM-INVALID case (heading present, empty rationale);
        a non-empty rationale arms the FORM-VALID case. The witness is plain
        markdown in the feature-delta (the generalized ``_wave_skip_witness_present``
        reads its FORM -- heading + non-empty body, DDD-9 / AT-A8).
        """
        assert self._project_root is not None
        heading = _WAVE_SKIP_HEADING_TEMPLATE.format(wave=wave)
        body = f"\n{rationale}\n" if rationale else "\n"
        path = (
            self._project_root
            / "docs"
            / "feature"
            / _PROBE_FEATURE_ID
            / "feature-delta.md"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"# Feature Delta: probe\n\n{heading}\n{body}\n## Wave: NEXT\n",
            encoding="utf-8",
        )

    def write_session_pre_grant(self, ttl_seconds: int) -> None:
        """Write a session-scoped pre-grant file (DDD-9 night-autonomy).

        ttl_seconds > 0  -> a non-expired grant (valid -> ALLOW).
        ttl_seconds <= 0 -> an already-expired grant (reads as ABSENT -> BLOCK).
        """
        assert self._project_root is not None
        grant = (
            self._project_root
            / ".nwave"
            / "des"
            / f"wave-skip-grant-{self._session_id}.json"
        )
        granted_at = time.time()
        grant.write_text(
            json.dumps(
                {
                    "session_id": self._session_id,
                    "granted_at": granted_at,
                    "ttl_seconds": ttl_seconds,
                    "expires_at": granted_at + ttl_seconds,
                    "authorized_by": "human",
                }
            ),
            encoding="utf-8",
        )

    # ---- WHEN: drive the IN-TREE gate (Layer-3 subprocess, hermetic) ----------

    def _write_prompt_fixture(self) -> Path:
        """Write the dispatch prompt to a tmp FILE the gate reads via --prompt-path.

        A FILE (not stdin) keeps the AT hermetic -- the gate reads the DES-WAVE
        marker + any wave-skip witness reference from the prompt text on disk.
        """
        assert self._project_root is not None
        prompt = ""
        if self._marker_wave is not None:
            prompt = f"<!-- DES-WAVE: {self._marker_wave} -->\nwork the wave"
        prompt_path = self._project_root / ".nwave" / "des" / "dispatch-prompt.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        return prompt_path

    def _run_gate(self, argv: list[str]) -> None:
        """Drive the in-tree ``verify_wave_dispatch`` gate IN-PROCESS with the args.

        The faithful in-process analogue of ``python -m des.cli.verify_wave_dispatch``
        (the module's ``__main__`` runs ``main()`` directly, not via the dispatcher):
        ``run_cli_in_process`` calls the same ``main(argv)``, chdir's to the work-tree,
        and captures stdout+stderr -- a missing required arg still surfaces as the
        argparse ``SystemExit(2)`` mapped onto exit 2. PYTHONPATH=REPO_ROOT is
        mirrored on ``os.environ`` (restored in finally) to match the old ``env=``.
        """
        assert self._project_root is not None
        from des.cli import verify_wave_dispatch

        prior_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = str(REPO_ROOT)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                argv, cwd=self._project_root, main=verify_wave_dispatch.main
            )
        finally:
            if prior_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = prior_pythonpath
        self._exit_code = exit_code
        self._stdout = stdout + stderr

    def when_agent_dispatched(self) -> None:
        """Drive the REAL in-tree gate over its ARGS protocol (Layer-3 subprocess)."""
        assert self._project_root is not None
        prompt_path = self._write_prompt_fixture()
        self._run_gate(
            [
                "--subagent-type",
                self._subagent,
                "--prompt-path",
                str(prompt_path),
                "--repo-root",
                str(self._project_root),
                "--session-id",
                self._session_id,
            ]
        )

    def when_dispatched_without_subagent_type(self) -> None:
        """Drive the gate OMITTING the required --subagent-type (CT MALFORMED).

        argparse fails on the missing required arg -> the gate exits 2 (§22.0 H-2
        malformed-input), distinct from BLOCK (1) and ALLOW (0). The prompt FILE is
        still written so the ONLY malformation is the absent required arg.
        """
        assert self._project_root is not None
        prompt_path = self._write_prompt_fixture()
        self._run_gate(
            [
                "--prompt-path",
                str(prompt_path),
                "--repo-root",
                str(self._project_root),
                "--session-id",
                self._session_id,
            ]
        )

    # ---- THEN: observable-surface readers -------------------------------------

    def _raw_exit(self) -> int:
        assert self._exit_code is not None, "must dispatch (When) before Then"
        return self._exit_code

    def _is(self, expected: GuardDecision) -> bool:
        """True iff the raw exit code EQUALS the expected verdict's code.

        Compares raw ints -- it does NOT coerce the exit through ``GuardDecision``.
        At HEAD the gate module is ABSENT, so the subprocess yields a non-{0,1}
        exit (the DES dispatcher's module-absent / freshness-autoskip projection);
        coercing that through the enum would raise ``ValueError`` (a wrong-RED:
        not a semantic AssertionError). Comparing raw ints lets the Then assertions
        fire a clean AssertionError naming the expected verdict (MISSING_FUNCTIONALITY).
        """
        return self._raw_exit() == expected.value

    def then_wave_owner_allowed_on_spine(self) -> None:
        """(CT-9/CT-10 ALLOW) a wave-owner is allowed AND the allow names WHY.

        DISCRIMINATING (anti-vacuous-pass): exit 0 alone cannot tell "allowed
        because the gate recognized the on-spine signal (marker / valid witness /
        valid grant)" apart from "allowed because the gate ignores every
        non-owner". The gate MUST emit a positive allow-trace naming the
        recognized signal on the wave-owner path, so the ALLOW is a recognized-on-
        spine decision, never silence. At HEAD the gate module is absent -> the
        subprocess exits non-zero (not 0) -> this RED-fails on the verdict.
        """
        assert self._is(GuardDecision.ALLOW), (
            "an on-spine / witnessed / pre-granted wave-owner dispatch must be "
            f"ALLOWED (exit 0); got exit {self._exit_code}. {self._gate_observed()}"
        )
        text = self._stdout.lower()
        assert "allow" in text and (
            "des-wave" in text
            or "on-spine" in text
            or "witness" in text
            or "pre-grant" in text
            or "grant" in text
        ), (
            "the wave-owner ALLOW must emit a positive allow-trace naming the "
            "recognized on-spine signal (the DES-WAVE marker / a form-valid skip "
            "witness / a valid session pre-grant) so an ALLOW is a RECOGNIZED "
            "decision, never a silent exemption. At HEAD the gate is absent. "
            f"{self._gate_observed()}"
        )

    def then_reviewer_always_allowed(self) -> None:
        """(CT-9) a reviewer dispatch is allowed (a standing cross-cutting invariant).

        Reviewers are §22.0 controls, NEVER in the wave->owner map -> always exit 0.
        This is the one legitimately-invariant ALLOW (a reviewer is never a wave-
        author; it need not name a reason). It is RED at HEAD because the gate
        module does not exist yet (subprocess exits non-zero); it goes GREEN once
        DELIVER ships the gate, which excludes reviewers from the map by design.
        """
        assert self._is(GuardDecision.ALLOW), (
            "a reviewer dispatch (a §22.0 control, never a wave-owner) must ALWAYS "
            f"be allowed (exit 0); got exit {self._exit_code}. {self._gate_observed()}"
        )

    def then_block_warns_and_asks(self) -> None:
        """(CT-8) the BLOCK carries the warn+ask reason (same strength as the crafter guard)."""
        assert self._is(GuardDecision.BLOCK), (
            "off-spine wave entry must BLOCK (exit 1), not silently allow nor crash "
            "malformed (exit 2); the gate's BLOCK is the wave-level silent-entry "
            f"hole DDD-8 closes. {self._gate_observed()}"
        )
        text = self._stdout.lower()
        assert "refus" in text or "block" in text, (
            "a BLOCK must print the verdict + the warn+ask reason a developer reads "
            f"(mirroring verify_readiness_pre_dispatch's refused report). {self._gate_observed()}"
        )

    def then_malformed_input_is_rejected(self) -> None:
        """(CT MALFORMED) a dispatch missing the required --subagent-type exits 2.

        argparse malformed-input is exit 2 (§22.0 H-2) -- a DISTINCT verdict from
        ALLOW (0) and BLOCK (1): the gate must not silently allow nor mis-classify a
        malformed invocation as an off-spine BLOCK. At HEAD the gate module is
        absent so the subprocess yields a non-2 exit -> a clean AssertionError
        (MISSING_FUNCTIONALITY); GREEN once DELIVER ships the gate with the readiness
        gate's argparse `required=True` shape.
        """
        assert self._is(GuardDecision.MALFORMED), (
            "a dispatch missing the required --subagent-type arg must be rejected as "
            f"MALFORMED (exit 2), distinct from ALLOW (0) / BLOCK (1); got exit "
            f"{self._exit_code}. {self._gate_observed()}"
        )

    def _gate_observed(self) -> str:
        return (
            f"exit={self._exit_code!r}; subagent={self._subagent!r}; "
            f"marker_wave={self._marker_wave!r}; root={self._project_root!r}; "
            f"stdout[:400]={self._stdout[:400]!r}"
        )
