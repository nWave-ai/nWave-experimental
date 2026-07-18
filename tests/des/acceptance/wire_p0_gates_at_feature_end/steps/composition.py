"""Composition root for the wire-p0-gates-at-feature-end acceptance suite.

Mandate-12 criterion 2/3 + Pillar 3: the SUT is wired through the PRODUCTION
use-case ``run_feature_end_cycle`` (``src/des/application/
feature_end_cycle_service.py``) -- the SAME function both ``des feature-end
run`` and the SubagentStop hook shim invoke (DDD-7). ALL business logic lives
in this module's service methods; step bodies in ``common_steps.py`` delegate
here and never inline business logic.

RED scaffold (Mandate 7 / ADR-025): every scenario reds for the RIGHT reason
-- ``run_feature_end_cycle`` does not yet invoke ``verify-fresh-clone`` /
``verify-execution-reach`` / ``verify-doc-coherence`` at all (evolution-plan
P0.1/P0.4/P0.5, "wiring into the feature-end stack = P2.2"), so every planted
defect below is reached but never checked and the cycle proceeds to a signed
``CycleSuccess`` -- the AT assertions fail because production behaviour is
absent, not because the test infrastructure is broken. No production code is
scaffolded here (L-5: the three gate CLIs are DONE); only the NEW leg inside
``run_feature_end_cycle`` is missing.

Fixture shapes below are REUSED verbatim (not re-derived) from the
already-authored unit-level oracles: ``tests/des/unit/application/
test_feature_end_cycle_{fresh_clone,execution_reach,doc_coherence}_gate.py``.
This acceptance layer is the driving-port witness ABOVE those unit pins, per
the feature-delta's ground-truth finding that reuse-first is the wiring
pattern, not reinvention.

Layer note: every scenario here is Layer 3 composition (Mandate-13) --
in-process call into the real application-service function, real git
repo / real Cobertura XML / real README on disk, sibling legs stubbed via
``monkeypatch`` so only the NEW leg under test can determine the cycle's
outcome (mirrors the unit oracles' ``_stub_non_*_legs`` pattern). Example-only
(Mandate 9/11), one scenario per gate. Every Then asserts via the single
port-exposed observable (Mandate 8 universe-bound): the ``CycleRefusal`` /
``CycleSuccess`` return value and its ``error`` string.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from des.application import feature_end_cycle_service as svc
from des.application.feature_end_cycle_service import (
    CycleRefusal,
    CycleSuccess,
    FullSuiteLegNotApplicable,
    FullSuiteLegRan,
    run_feature_end_cycle,
)
from des.runtime.interpreter import des_spawn


if TYPE_CHECKING:
    import pytest


_FRESH_CLONE_RECIPE = '{"steps": [{"name": "build", "cmd": ["python3", "main.py"]}]}\n'

_OVERSTATING_README = (
    "# Demo\n\n"
    "Run `npm run e2e:golden` to verify.\n\n"
    "The reconciler lives in `src/reconciler.ts`.\n"
)

_FEATURE_ID = "feat-wire-p0-gates-at-feature-end-acceptance"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")


def _cobertura(src_abs: Path, classes: str) -> str:
    return (
        '<?xml version="1.0" ?>\n'
        '<coverage version="7.0">\n'
        f"  <sources><source>{src_abs}</source></sources>\n"
        '  <packages><package name="."><classes>\n'
        f"{classes}"
        "  </classes></package></packages>\n"
        "</coverage>\n"
    )


def _cobertura_class(filename: str, hits: int, n_lines: int = 2) -> str:
    lines = "".join(
        f'      <line number="{i + 1}" hits="{hits}"/>\n' for i in range(n_lines)
    )
    return (
        f'    <class name="{filename}" filename="{filename}">'
        f"<methods/><lines>\n{lines}    </lines></class>\n"
    )


@dataclass
class FeatureEndP0GateComposition:
    """Production-composition root: drives ``run_feature_end_cycle``
    in-process with sibling legs stubbed and a real planted-defect fixture
    on disk for the leg under test."""

    tmp_path: Path
    monkeypatch: pytest.MonkeyPatch
    _repo_root: Path | None = field(default=None, init=False)
    _feature_dir: Path | None = field(default=None, init=False)
    result: CycleSuccess | CycleRefusal | None = field(default=None, init=False)

    # --- shared plumbing -----------------------------------------------------

    def _stub_sibling_legs(self) -> None:
        """Short-circuit every OTHER leg so only the leg under test can
        determine the cycle's outcome (mirrors the unit oracles'
        ``_stub_non_*_legs`` helper)."""
        self.monkeypatch.setattr(
            svc,
            "_run_walking_skeleton_gate",
            lambda *, repo_root, feature_dir: repo_root,
        )
        self.monkeypatch.setattr(
            svc,
            "_run_environmental_e2e_gate",
            lambda *, ledger, repo_root, feature_id, feature_dir, walking_skeleton: (
                None
            ),
        )
        self.monkeypatch.setattr(
            svc,
            "_run_coverage_map_verify_leg",
            lambda *, ledger, repo_root, feature_id, feature_dir: None,
        )
        self.monkeypatch.setattr(
            svc,
            "_run_full_suite_leg",
            lambda *, repo_root, feature_id=None: FullSuiteLegNotApplicable(
                "stubbed: no contract suite in this hermetic acceptance fixture"
            ),
        )

    def _seed_feature_dir(self, repo_root: Path) -> Path:
        """A minimal feature-dir with NO feature-delta.md (no Slice-Plan ->
        no undelivered-slice truncation refusal -- keeps the fixture focused
        on the leg under test alone)."""
        feature_dir = repo_root / "docs" / "feature" / _FEATURE_ID
        feature_dir.mkdir(parents=True)
        return feature_dir

    def _stage(self, repo_root: Path) -> None:
        self._stub_sibling_legs()
        self._repo_root = repo_root
        self._feature_dir = self._seed_feature_dir(repo_root)

    # NOTE: slice-01's fresh-clone Given/When/Then no longer route through
    # this in-process composition -- see ``FeatureEndRunCliComposition``
    # below, which drives the REAL `des feature-end run` CLI as a genuine
    # subprocess (the ONE @walking_skeleton per command,
    # `nw-distill-port-treatment-policy`). This class keeps ONLY slice-02/03
    # (still function-level, genuinely active-RED -- their legs are not yet
    # wired in `run_feature_end_cycle`).

    # --- Given: slice-02 execution-reach --------------------------------------

    def given_never_executed_production_file(self) -> None:
        """A shipped production file (``dead_scaffold.py``) shows ZERO hits
        in the feature's own coverage run -- the exact never-run scaffold
        class ``verify-execution-reach`` catches standalone."""
        repo_root = self.tmp_path / f"execution-reach-{uuid.uuid4().hex[:8]}"
        src = repo_root / "src"
        src.mkdir(parents=True)
        (src / "used.py").write_text("def greet():\n    return 'ok'\n")
        (src / "dead_scaffold.py").write_text(
            "def reconcile():\n    raise RuntimeError('x')\n"
        )
        xml = repo_root / "coverage.xml"
        xml.write_text(
            _cobertura(
                src,
                _cobertura_class("used.py", hits=3)
                + _cobertura_class("dead_scaffold.py", hits=0),
            )
        )
        self._stage(repo_root)

    # --- Given: slice-03 doc-coherence -----------------------------------------

    def given_docs_overstating_absent_code(self) -> None:
        """A README claims an npm script absent from ``package.json`` AND a
        file path absent from the tree -- the exact docs-overstate-the-code
        class ``verify-doc-coherence`` catches standalone."""
        repo_root = self.tmp_path / f"doc-coherence-{uuid.uuid4().hex[:8]}"
        repo_root.mkdir(parents=True)
        # .gitignore is the runtime-state boundary the real gate now derives
        # per-target (fix-doc-coherence-target-runtime-dir); unrelated to
        # this doc-overstatement scenario, so a plain entry suffices.
        (repo_root / ".gitignore").write_text("node_modules/\n")
        (repo_root / "README.md").write_text(_OVERSTATING_README)
        (repo_root / "src").mkdir()
        (repo_root / "src" / "index.ts").write_text("export {};\n")
        (repo_root / "package.json").write_text(
            json.dumps({"scripts": {"build": "tsc"}})
        )
        self._stage(repo_root)
        # A WARN outcome folds into leg_census.warned, NOT leg_census.ran
        # (only DocCoherenceLegRan does) -- force full-suite to a genuine
        # FullSuiteLegRan (overriding `_stub_sibling_legs`'s NotApplicable)
        # so leg_census.ran >= 1 and the cycle does not ALSO trip the
        # unrelated zero-observed-checks charter (leg_census.ran == 0 ->
        # CycleIndeterminate, ADR-GV-002 D1/D3, pinned elsewhere).
        self.monkeypatch.setattr(
            svc,
            "_run_full_suite_leg",
            lambda *, repo_root, feature_id=None: FullSuiteLegRan(0),
        )

    # --- When ------------------------------------------------------------------

    def when_feature_end_cycle_runs(self) -> None:
        assert self._repo_root is not None, "no fixture staged"
        assert self._feature_dir is not None, "no fixture staged"
        self.result = run_feature_end_cycle(
            repo_root=self._repo_root,
            feature_id=_FEATURE_ID,
            feature_dir=self._feature_dir,
            reviewer_agent_id="nw-software-crafter-reviewer",
            verdict="APPROVED",
        )

    # --- Then --------------------------------------------------------------------

    def then_cycle_is_refused(self) -> None:
        """Port-exposed observable: ``run_feature_end_cycle``'s return value."""
        assert isinstance(self.result, CycleRefusal), (
            "expected the feature-end cycle to refuse to sign the feature as "
            f"done; actual={self.result!r}"
        )

    def then_refusal_names_gate(self, gate_name: str) -> None:
        """Port-exposed observable: the ``CycleRefusal.error`` diagnostic
        string names the gate that produced it."""
        assert isinstance(self.result, CycleRefusal), (
            f"expected a refusal to inspect; actual={self.result!r}"
        )
        assert gate_name in self.result.error, (
            f"expected the refusal to name {gate_name!r}; "
            f"actual error={self.result.error!r}"
        )

    def then_no_feature_end_verdict_recorded(self) -> None:
        """Port-exposed observable: the AT-completion ledger JSONL carries
        no signed feature-end record (anti-theater: a refused cycle emits
        neither ``FeatureEndReviewVerdict`` nor ``EBatchRefactorCompleted``)."""
        assert self._repo_root is not None, "no fixture staged"
        ledger_path = (
            self._repo_root
            / ".nwave"
            / "telemetry"
            / "atdd-pure"
            / f"{_FEATURE_ID}.jsonl"
        )
        if not ledger_path.is_file():
            return
        text = ledger_path.read_text(encoding="utf-8")
        assert "FeatureEndReviewVerdict" not in text, (
            "a refused cycle must never emit a FeatureEndReviewVerdict record"
        )
        assert "EBatchRefactorCompleted" not in text, (
            "a refused cycle must never emit an EBatchRefactorCompleted record"
        )

    # --- Then: slice-03 warn-not-block (fix-doc-coherence-gate-warns-not-blocks) --

    def then_cycle_signs_as_done(self) -> None:
        """Port-exposed observable: doc-coherence violations must WARN, not
        hard-refuse -- the cycle proceeds to a signed ``CycleSuccess``."""
        assert isinstance(self.result, CycleSuccess), (
            "expected the feature-end cycle to WARN and still sign the "
            f"feature as done (advisory, not blocking); actual={self.result!r}"
        )

    def _ledger_records(self) -> list[dict]:
        assert self._repo_root is not None, "no fixture staged"
        ledger_path = (
            self._repo_root
            / ".nwave"
            / "telemetry"
            / "atdd-pure"
            / f"{_FEATURE_ID}.jsonl"
        )
        if not ledger_path.is_file():
            return []
        records: list[dict] = []
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        return records

    def _find_ledger_record(self, event: str) -> dict | None:
        matches = [r for r in self._ledger_records() if r.get("event") == event]
        return matches[-1] if matches else None

    def then_doc_coherence_warning_recorded(self) -> None:
        """Port-exposed observable: a distinct ``DocCoherenceWarned`` ledger
        record names the actual violation -- never swallowed into a bare
        boolean (charter negative oracle #1)."""
        warned_record = self._find_ledger_record("DocCoherenceWarned")
        assert warned_record is not None, (
            "expected a DocCoherenceWarned ledger record after a "
            f"doc-coherence violation; ledger={self._ledger_records()!r}"
        )
        serialized = json.dumps(warned_record)
        assert "e2e:golden" in serialized or "reconciler.ts" in serialized, (
            "the DocCoherenceWarned record must name the actual violation, "
            f"not swallow it into a bare boolean: {warned_record!r}"
        )

    def then_warning_never_reads_as_verified_clean(self) -> None:
        """Port-exposed observable: a warned completion must NEVER also
        carry a ``DocCoherenceVerified`` (clean-pass) record for the same
        run (charter negative oracle #2)."""
        assert self._find_ledger_record("DocCoherenceVerified") is None, (
            "a run completed WITH doc-coherence warnings must never ALSO "
            f"carry a DocCoherenceVerified (clean-pass) record: "
            f"{self._ledger_records()!r}"
        )


def _parse_cycle_event(stdout: str) -> tuple[str | None, str | None]:
    """Parse the ``des feature-end run`` subprocess's OWN structured payload.

    The CLI shim (``des/cli/feature_end.py`` ``_run_cycle`` -> ``_emit``)
    prints exactly one single-line JSON object per invocation on stdout --
    ``FeatureEndCycleRefused`` or ``FeatureEndCycleComplete``. Returns
    ``(event, error)``; ``error`` is populated only for a refusal. Scanning
    reversed (last line first) mirrors ``_walking_skeleton_verdict`` above and
    is robust to any other diagnostic line a sibling gate leg might have
    printed earlier in the same stream.
    """
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        event = payload.get("event")
        if event in ("FeatureEndCycleRefused", "FeatureEndCycleComplete"):
            error = payload.get("error")
            return event, (error if isinstance(error, str) else None)
    return None, None


@dataclass(frozen=True)
class CliCycleResult:
    """Port-exposed observable of ONE ``des feature-end run`` subprocess call.

    Universe entries (Mandate 8) are the command's OWN observable surface --
    the process exit code and the structured JSON event/\u200berror its ``_emit``
    prints -- never the in-process ``CycleRefusal``/``CycleSuccess`` struct
    (this composition never imports ``run_feature_end_cycle``'s return type;
    the process boundary is the SUT here, not the Python function).
    """

    exit_code: int
    event: str | None
    error: str | None


@dataclass
class FeatureEndRunCliComposition:
    """Production-wired composition root for slice-01's ONE
    ``@walking_skeleton`` scenario -- the single subprocess-e2e AT per command
    that proves the ``des feature-end run`` CLI is wired end-to-end
    (``nw-distill-port-treatment-policy``: "subprocess-e2e reserved for
    @walking_skeleton"; canonical exemplar
    ``tests/des/acceptance/oss_feature_end_emit_cli/steps/
    composition_slice_04.py``'s ``FeatureEndCoverageMapComposition``).

    Unlike ``FeatureEndP0GateComposition`` (in-process call into
    ``run_feature_end_cycle`` with sibling legs monkeypatched), this
    composition forks a REAL child interpreter through the production
    ``des_spawn`` boundary (``des.runtime.interpreter.des_spawn`` -- the SAME
    primitive ``feature_end_cycle_service._dispatch`` uses for every gate
    leg) -- driving the argparse-level CLI edge (``des/cli/feature_end.py``
    ``main`` -> ``_run_cycle``), not the bare use-case function. A
    monkeypatch on THIS process's ``feature_end_cycle_service`` module has NO
    effect on a forked child, so NOTHING is stubbed: every sibling leg
    (walking-skeleton, env-e2e, coverage-map, full-suite) must reach its OWN
    real NOT_APPLICABLE verdict against the minimal fixture below. Verified
    empirically -- a feature-dir carrying no ``feature-delta.md`` / no
    walking-skeleton manifest / coverage-map-adoption-inactive naturally
    routes every sibling leg to NA, so the cycle reaches the fresh-clone leg
    unassisted, exactly as the hermetic subprocess run below reproduces.
    """

    tmp_path: Path
    _repo_root: Path | None = field(default=None, init=False)
    _feature_dir: Path | None = field(default=None, init=False)
    result: CliCycleResult | None = field(default=None, init=False)

    def given_fresh_clone_broken_build(self) -> None:
        """A committed tree whose declared build step depends on an
        UNTRACKED file -- the exact works-only-on-my-machine class
        ``verify-fresh-clone`` catches standalone (byte-identical fixture
        shape to ``FeatureEndP0GateComposition.given_fresh_clone_broken_build``,
        reused rather than re-derived)."""
        repo_root = self.tmp_path / f"fresh-clone-cli-{uuid.uuid4().hex[:8]}"
        _init_repo(repo_root)
        (repo_root / "main.py").write_text("import helper\nprint(helper.GREETING)\n")
        (repo_root / "helper.py").write_text('GREETING = "ok"\n')
        (repo_root / ".nwave").mkdir()
        (repo_root / ".nwave" / "demo-recipe.json").write_text(_FRESH_CLONE_RECIPE)
        _git(repo_root, "add", "main.py", ".nwave/demo-recipe.json")  # NOT helper.py
        _git(repo_root, "commit", "-qm", "planted: depends on untracked helper")
        self._repo_root = repo_root
        feature_dir = repo_root / "docs" / "feature" / _FEATURE_ID
        feature_dir.mkdir(parents=True)
        self._feature_dir = feature_dir

    def when_feature_end_cycle_runs(self) -> None:
        """Fork the REAL ``des feature-end run`` CLI -- ``python -m
        des.cli.__main__ feature-end run ...`` via ``des_spawn`` (the SAME
        spawn boundary production dispatches every gate leg through), a
        genuine process boundary, not an in-process call."""
        assert self._repo_root is not None, "no fixture staged"
        assert self._feature_dir is not None, "no fixture staged"
        completed = des_spawn(
            None,
            "des.cli.__main__",
            "feature-end",
            "run",
            "--repo",
            str(self._repo_root),
            "--feature-id",
            _FEATURE_ID,
            "--feature-dir",
            str(self._feature_dir),
            "--reviewer-agent-id",
            "nw-software-crafter-reviewer",
            "--verdict",
            "APPROVED",
            capture_output=True,
            text=True,
            cwd=str(self._repo_root),
        )
        event, error = _parse_cycle_event(completed.stdout)
        self.result = CliCycleResult(
            exit_code=completed.returncode, event=event, error=error
        )

    def then_cycle_is_refused(self) -> None:
        """Port-exposed observable: the subprocess's exit code + its own
        ``FeatureEndCycleRefused`` JSON event -- never a bare non-zero exit
        (that would also match an unrelated dispatcher/usage error)."""
        assert self.result is not None, "no cycle run"
        assert self.result.event == "FeatureEndCycleRefused", (
            "expected `des feature-end run` to emit a FeatureEndCycleRefused "
            f"event and exit non-zero; actual exit_code={self.result.exit_code} "
            f"event={self.result.event!r}"
        )
        assert self.result.exit_code != 0, (
            "a FeatureEndCycleRefused event must carry a non-zero exit code; "
            f"actual exit_code={self.result.exit_code}"
        )

    def then_refusal_names_gate(self, gate_name: str) -> None:
        """Port-exposed observable: the refusal's own ``error`` diagnostic
        string names the gate that produced it."""
        assert self.result is not None and self.result.error is not None, (
            f"expected a refusal diagnostic to inspect; actual={self.result!r}"
        )
        assert gate_name in self.result.error, (
            f"expected the refusal to name {gate_name!r}; "
            f"actual error={self.result.error!r}"
        )

    def then_no_feature_end_verdict_recorded(self) -> None:
        """Port-exposed observable: the AT-completion ledger JSONL carries no
        signed feature-end record for a refused cycle."""
        assert self._repo_root is not None, "no fixture staged"
        ledger_path = (
            self._repo_root
            / ".nwave"
            / "telemetry"
            / "atdd-pure"
            / f"{_FEATURE_ID}.jsonl"
        )
        if not ledger_path.is_file():
            return
        text = ledger_path.read_text(encoding="utf-8")
        assert "FeatureEndReviewVerdict" not in text, (
            "a refused cycle must never emit a FeatureEndReviewVerdict record"
        )
        assert "EBatchRefactorCompleted" not in text, (
            "a refused cycle must never emit an EBatchRefactorCompleted record"
        )
