"""Composition root for the dormant-seam gate walking skeleton (slice-01).

This is the *only* place the production system is wired for the slice-01 ATs.
It drives the production ``des dormant-seam-gate`` composition-root CLI end-to-end
as a subprocess black box (Mandate-13 driving-port-only, Layer 3 subprocess),
mirroring the shipped CLI-gate shape ``des.cli.walking_skeleton_gate`` and the
proven subprocess driving-port pattern of the sibling suite
``tests/des/acceptance/oss-upstream-gate-pair-traceability/steps/composition.py``.

DRIVING PORT (load-bearing): the detector ``dormant_seam.detect(...)`` and the
``ChangedSymbolPort`` are NEVER imported-and-called at the step boundary -- the
SUT is exercised only through the CLI subprocess. The CLI is invoked as
``python -m des.cli.dormant_seam_gate --feature-dir <dir> --repo-root <repo>
--delta-base-ref <ref>`` against a real synthetic git repo. The observable
surface is the single-line JSON ``DormantSeamVerdict`` on stdout, the loud human
warning on stderr, and the process exit code -- nothing else.

SYNTHETIC SUBSTRATE (precondition state, NOT the SUT): a real tmp git repo with
a committed base, then a net-new ADDED module under ``src/des/`` carrying one
effectful public symbol. The net-new delta is computed by the production
``ChangedSymbolPort`` adapter behind git (D-2), so the test seeds the delta as
real git history (a base commit + the added file). Two arrangements:

  * DORMANT: the added effectful symbol has NO production call-site (it is
    referenced only by its own module / tests) -> the gate must fire the loud
    INDETERMINATE warning naming it, non-halting (exit 0).
  * WIRED: the same effectful symbol shape, but a second net-new production
    module under ``src/des/`` calls it -> the gate must stay clean (non-vacuity
    control). The call-site module is itself in the delta so slice-01's
    net-new-delta scoping (slice-04) is not exercised; both files are added.

RED-for-right-reason: ``des.cli.dormant_seam_gate`` does not exist yet, so the
subprocess prints no JSON verdict; ``_verdict()`` raises a semantic
``AssertionError`` (no parseable verdict on stdout), and the Then-steps fail for
the RIGHT reason -- the CLI cannot produce the dormant-seam verdict. At GREEN
(CLI + detector + port wired) the verdict is parseable and the assertions bind.

State lives on the instance; every ``given_/when_/then_`` method mutates or reads
that state. Step functions in ``test_slice_01_dormant_seam_walking_skeleton.py``
are thin delegations to these methods (Mandate-12: no business logic in step
bodies).

DRIVING-SURFACE AMBIGUITY FOR THE CRAFTER (DELIVER): the exact CLI argv +
manifest contract is mirrored from ``des.cli.walking_skeleton_gate`` here
(``--feature-dir`` / ``--repo-root`` / ``--delta-base-ref``). If DELIVER chooses
a different CLI surface (e.g. a ``dormant-seam.json`` manifest, or a
``--changed-symbols`` flag), update ``_run_gate`` accordingly -- the contract the
ATs pin is the OBSERVABLE verdict (named seam + non-halting exit 0), not the
exact flag names. The ``feature-id`` + ``effectful-symbol`` constants and the
synthetic-repo shape are stable; only the argv plumbing is the crafter's choice.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from des.cli import dormant_seam_gate
from tests.common.in_process_cli import run_cli_in_process

from .domain_types import CallSiteWiring, EmissionChannel, SeamVerdict


_FEATURE_ID = "probe-dormant-seam-feat"
# The net-new effectful public symbol the synthetic delta adds. Public
# (non-`_`-prefixed) and effectful (its body performs an I/O write) so it is in
# the gate's effectful-symbol surface (D-3).
_EFFECTFUL_SYMBOL = "absorb_ready_refs"
_EFFECTFUL_MODULE_REL = "src/des/probe_dormant_module.py"
_CALLER_MODULE_REL = "src/des/probe_caller_module.py"

# slice-01 binds the dormant verdict to a NAMED seam plus a dormant-semantics
# token, so a degenerate gate that echoes every net-new symbol (no call-site
# join) cannot satisfy the assertion. The loud warning for a dormant seam must
# carry one of these tokens adjacent to the symbol identity.
_DORMANT_MARKER_TOKENS: tuple[str, ...] = (
    SeamVerdict.DORMANT_NO_CALL_SITE.value,  # "dormant-no-call-site"
    "dormant",
    "no production call-site",
    "no call-site",
    "no call site",
    "uncalled",
)

# The dormant-seam INDETERMINATE warning is non-halting -> exit 0. A block /
# refuse on stdout is forbidden (KPI-2 guardrail).
_BLOCK_TOKENS: tuple[str, ...] = ('"decision": "block"', '"decision":"block"', "refuse")


@dataclass
class DormantSeamGateComposition:
    """Drives the production dormant-seam-gate CLI for the slice-01 ATs."""

    _tmp: Path | None = field(default=None)
    _repo_root: Path | None = field(default=None)
    _feature_dir: Path | None = field(default=None)
    _base_ref: str | None = field(default=None)
    _wiring: CallSiteWiring = field(default=CallSiteWiring.NONE)
    _completed: subprocess.CompletedProcess[str] | None = field(default=None)
    _emission_channel: EmissionChannel = field(default=EmissionChannel.STDERR)

    # ---- given ---------------------------------------------------------

    def given_dormant_net_new_effectful_symbol(self) -> None:
        """A net-new effectful public symbol with NO production call-site."""
        self._wiring = CallSiteWiring.NONE
        self._build_synthetic_feature(wiring=CallSiteWiring.NONE)

    def given_wired_net_new_effectful_symbol(self) -> None:
        """A net-new effectful public symbol that production code calls."""
        self._wiring = CallSiteWiring.DIRECT
        self._build_synthetic_feature(wiring=CallSiteWiring.DIRECT)

    # ---- when ----------------------------------------------------------

    def when_developer_runs_the_gate(self) -> None:
        """Invoke the REAL dormant-seam-gate CLI as a subprocess black box."""
        self._run_gate()

    # ---- then ----------------------------------------------------------

    def then_names_dormant_seam(self) -> None:
        """The dormant seam is named in the loud warning, bound to dormant semantics."""
        self._assert_seam_warned_as_dormant(_EFFECTFUL_SYMBOL)

    def then_silent_about_wired_seam(self) -> None:
        """Non-vacuity: a wired seam is NOT warned (the warning is call-site-bound)."""
        warning = self._warning_text()
        assert _EFFECTFUL_SYMBOL not in warning, (
            f"the wired seam {_EFFECTFUL_SYMBOL!r} was wrongly named in the "
            f"dormant-seam warning; a symbol WITH a production call-site must "
            f"stay silent (the warning is not vacuously always-on). "
            f"{self._observed()}"
        )

    def then_lets_wave_proceed(self) -> None:
        """Non-halting: the gate warned AND emitted no block (conjunction)."""
        self._assert_seam_warned_as_dormant(_EFFECTFUL_SYMBOL)
        completed = self._require_completed()
        assert not any(token in completed.stdout for token in _BLOCK_TOKENS), (
            "the gate must let the wave proceed (no block / refuse decision on "
            f"stdout); a block was emitted. {self._observed()}"
        )

    def then_exits_zero(self) -> None:
        """Non-halting: the dormant-seam INDETERMINATE warning stays exit 0."""
        completed = self._require_completed()
        assert completed.returncode == 0, (
            "the gate must exit with code zero (non-halting) on a dormant-seam "
            f"warning; got returncode={completed.returncode}. {self._observed()}"
        )

    def then_indeterminate_warns_without_refusing(self) -> None:
        """The verdict is INDETERMINATE (warn) AND non-halting (no block)."""
        verdict = self._verdict()
        assert verdict.get("verdict") == "indeterminate", (
            "the gate must report an INDETERMINATE verdict for a dormant seam "
            f"(the warn-loud non-halting verdict); got verdict="
            f"{verdict.get('verdict')!r}. {self._observed()}"
        )
        completed = self._require_completed()
        assert not any(token in completed.stdout for token in _BLOCK_TOKENS), (
            "the INDETERMINATE verdict must warn WITHOUT refusing the wave (no "
            f"block / refuse on stdout). {self._observed()}"
        )

    # ---- assertion helpers ---------------------------------------------

    def _assert_seam_warned_as_dormant(self, symbol: str) -> None:
        warning = self._warning_text()
        assert symbol in warning, (
            "the dormant-seam gate did not name the dormant seam "
            f"{symbol!r} in its loud {self._emission_channel.value} warning. "
            f"{self._observed()}"
        )
        assert any(token in warning.lower() for token in _DORMANT_MARKER_TOKENS), (
            f"the warning named {symbol!r} but did not bind it to the DORMANT "
            f"verdict (expected one of {_DORMANT_MARKER_TOKENS!r} adjacent to "
            "the symbol identity); a warn-every-net-new-symbol gate with no "
            f"call-site join would echo the name without this semantics. "
            f"{self._observed()}"
        )

    def _verdict(self) -> dict[str, object]:
        """Parse the single-line JSON DormantSeamVerdict from stdout.

        Raises a semantic AssertionError (RED-for-right-reason) when the CLI is
        absent / produced no parseable verdict line.
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
            f"on stdout (the CLI is absent or emitted no verdict). {self._observed()}"
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

    def _build_synthetic_feature(self, wiring: CallSiteWiring) -> None:
        """Build a real tmp git repo whose net-new delta carries the seam.

        A base commit (empty `src/des/`), then the net-new ADDED effectful module
        (and, when `wiring=DIRECT`, an added caller module). The net-new delta is
        the git diff base...HEAD, which the production `ChangedSymbolPort` adapter
        reads behind git (D-2) -- the test seeds it as real history.
        """
        self._ensure_repo()
        assert self._repo_root is not None
        self._write_effectful_module()
        if wiring is CallSiteWiring.DIRECT:
            self._write_caller_module()
        self._commit_all("add net-new dormant-seam-gate probe feature")

    def _ensure_repo(self) -> None:
        if self._repo_root is not None:
            return
        self._tmp = Path(tempfile.mkdtemp(prefix="dormant-seam-gate-at-"))
        self._repo_root = self._tmp
        self._base_ref = "dormant-seam-base"
        subprocess.run(["git", "init", "-q"], cwd=self._repo_root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "at@example.com"],
            cwd=self._repo_root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "at"], cwd=self._repo_root, check=True
        )
        # Base commit: an empty `src/des/` so the seam module is a true net-new
        # ADD relative to the base ref (the net-new-delta scope, D-3).
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
            ["git", "branch", self._base_ref],
            cwd=self._repo_root,
            check=True,
        )

    def _write_effectful_module(self) -> None:
        """Add a net-new module with one effectful public symbol."""
        assert self._repo_root is not None
        module = self._repo_root / _EFFECTFUL_MODULE_REL
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(
            '"""Net-new probe module carrying one effectful public symbol."""\n'
            "from __future__ import annotations\n"
            "from pathlib import Path\n"
            "\n"
            f"def {_EFFECTFUL_SYMBOL}(target: str) -> None:\n"
            '    """Effectful: writes to the filesystem (an I/O side-effect)."""\n'
            '    Path(target).write_text("absorbed", encoding="utf-8")\n',
            encoding="utf-8",
        )

    def _write_caller_module(self) -> None:
        """Add a net-new production module that calls the effectful symbol."""
        assert self._repo_root is not None
        module = self._repo_root / _CALLER_MODULE_REL
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text(
            '"""Net-new production module wiring the effectful symbol."""\n'
            "from __future__ import annotations\n"
            f"from des.probe_dormant_module import {_EFFECTFUL_SYMBOL}\n"
            "\n"
            "def run(target: str) -> None:\n"
            f"    {_EFFECTFUL_SYMBOL}(target)\n",
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
        """Run `python -m des.cli.dormant_seam_gate` as a subprocess black box.

        Env-parity: a clean subprocess env with `NWAVE_FRESHNESS=""` +
        `PIPENV_DONT_LOAD_ENV=1` so the freshness auto-skip / dotenv do not mask
        the gate verdict; `src` on PYTHONPATH so the importable `des.cli` module
        resolves the same way the kebab dispatcher would. The detector / port are
        NOT imported here -- only the subprocess boundary is crossed.
        """
        assert self._repo_root is not None
        assert self._feature_dir is not None
        assert self._base_ref is not None
        argv = [
            "--feature-dir",
            str(self._feature_dir),
            "--repo-root",
            str(self._repo_root),
            "--delta-base-ref",
            self._base_ref,
        ]
        # NWAVE_FRESHNESS="" + PIPENV_DONT_LOAD_ENV=1 so the freshness auto-skip /
        # dotenv do not mask the gate verdict (env-parity). Set on os.environ
        # around the in-process call, restored in `finally` -- shared-process safe.
        prior = {
            key: os.environ.get(key)
            for key in ("NWAVE_FRESHNESS", "PIPENV_DONT_LOAD_ENV")
        }
        os.environ["NWAVE_FRESHNESS"] = ""
        os.environ["PIPENV_DONT_LOAD_ENV"] = "1"
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                argv, cwd=str(self._repo_root), main=dormant_seam_gate.main
            )
        finally:
            for key, value in prior.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        self._completed = subprocess.CompletedProcess(argv, exit_code, stdout, stderr)

    def _require_completed(self) -> subprocess.CompletedProcess[str]:
        assert self._completed is not None, (
            "the dormant-seam gate must be run (When) before asserting on its "
            "observable verdict surface (Then)"
        )
        return self._completed
