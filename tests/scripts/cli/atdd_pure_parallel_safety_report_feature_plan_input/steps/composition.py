"""Composition root for the parallel-safety-report / Feature-Plan-input
acceptance slice (slice-02).

`docs/feature/parallel-by-default-feature-plan/feature-delta.md` D-6/D-7 /
slice-02 (Mandate-12, Pillar 3). Wires the PRODUCTION `parallel-safety-report`
CLI entry point (``des.cli.parallel_safety_report.main``) against a real
tmp_path git repository + an epic-delta fixture. Business logic lives here as
the single source of truth; step bodies delegate to
``ParallelSafetyReportFeaturePlanComposition`` methods and never inline logic.

Driving-Port-Only Boundary (SSOT: nw-test-design-mandates): every scenario
drives the REAL CLI surface DESIGN names for slice-02 -- `des
parallel-safety-report --epic-delta <path> --repo <path> --scope
<id>=<paths> [--timeout <s>]` -- via ``main(argv)`` (Layer 3 subprocess/FS
acceptance, in-process per `nw-distill-port-treatment-policy`'s inverted
driving default; the underlying `des blast-radius` measurement is still a
REAL, unfaked subprocess via ``SubprocessBlastRadiusAdapter``, D-6, so the
MEASURED-SAFE/DRIFT/UNMEASURED scenarios are genuinely `@real-io`).

Structured-outcome contract (pins the slice-02 CLI's machine output -- the
contract the crafter MUST implement, not a guess). `--epic-delta` selects
`read_declared_parallel_feature_ids` over `read_declared_parallel_slice_ids`
and the "Feature Plan row" rejection noun (DESIGN DC/DD); every other flag,
the in-process `run_parallel_safety_report(...)` API, and the emitted
`ParallelSafetyReport` JSON event are BYTE-IDENTICAL to the `--feature-delta`
path (D-6, CT-7).

Active-RED note (atdd_pure, brand-new-flag shape). `--epic-delta` does not
exist as a registered argparse flag on the current tip (only
`--feature-delta`, `required=True`) -- EVERY scenario below is RED today:
argparse raises `SystemExit(2)` on the unrecognized/missing flag before any
JSON event is ever printed, which `main`'s own P3 handler converts to the
plain int `2` -- `ReportResult.outcome` then reads `UNRECOGNISED_INVOCATION`
(no structured event at all), never matching the DESIGN'd expectation. Unlike
the sibling `atdd_pure_validate_feature_delta_feature_dependency_
justification` suite (an INCREMENTAL classification arm on an
already-shipped flag), this is a brand-new-flag slice -- every scenario is
individually RED until `--epic-delta` + `read_declared_parallel_feature_ids`
ship (mirrors row-3's OWN slice-01 walking-skeleton suite, which the DESIGN
[REF] Component Decomposition / Reuse Analysis both name as the precedent
this slice generalizes).
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Production driving port -- the parallel-safety-report CLI. `--feature-delta`
# already exists (row 3); slice-02 of THIS feature EXTENDS it with the
# mutually-exclusive `--epic-delta` alternate.
from des.cli.parallel_safety_report import main as parallel_safety_report_main

from .domain_types import (
    EpicId,
    FeatureId,
    InputSourceCase,
    MeasurementFixture,
    ReportOutcome,
)


# The closed outcome token set this composition can observe -- see
# `domain_types.ReportOutcome` docstring for the mapping rationale.
_OUTCOME_BY_VERDICT_TOKEN: dict[str, ReportOutcome] = {
    "MEASURED-SAFE": ReportOutcome.MEASURED_SAFE,
    "DRIFT": ReportOutcome.DRIFT,
    "UNMEASURED": ReportOutcome.UNMEASURED,
}

# The fixed three-row Feature Plan every scenario's Background provisions:
# feature-a + feature-b declared-parallel (no `depends-on`), feature-c
# declared-serial (`depends-on feature-b`, with a why) -- mirrors row-3's own
# `_PLAN_ROWS` shape one granularity up.
_FEATURE_PLAN_ROWS = (
    "| feature-a | Maintainer ships the checkout-guest-express capability. "
    "| pending | @walking_skeleton | Thinnest end-to-end vertical over the "
    "declared plan. |\n"
    "| feature-b | Maintainer ships the order-summary-redesign capability. "
    "| pending |  | Second declared-parallel row read from the same plan. |\n"
    "| feature-c | Maintainer extends the report with a degraded branch. "
    "| pending | depends-on feature-b | Depends on feature-b: consumes a "
    "type feature-b introduces. |"
)

# Per-`MeasurementFixture`: the tracked repo files + the `--scope` path
# binding for feature-a/feature-b + the forced-timeout flag. Module-level
# dispatch keeps `provision_repository_fixture`/`run_measurement_report` a
# single typed lookup (Mandate-12 criterion 3: no control flow in service
# method bodies).
_REPO_FILES_BY_FIXTURE: dict[MeasurementFixture, dict[str, str]] = {
    MeasurementFixture.DISJOINT: {
        "checkout/guest_session.py": "def guest():\n    return 1\n",
        "orders/summary_view.py": "def summary():\n    return 2\n",
    },
    MeasurementFixture.OVERLAPPING: {
        "shared/index_schema.py": "def schema():\n    return 1\n",
        "search/alpha.py": "def alpha():\n    return 2\n",
        "search/beta.py": "def beta():\n    return 3\n",
    },
    MeasurementFixture.TIMED_OUT: {
        "des/config.py": "def config():\n    return 1\n",
        "orders/summary_view.py": "def summary():\n    return 2\n",
    },
}

_SCOPE_PATHS_BY_FIXTURE: dict[MeasurementFixture, tuple[str, str]] = {
    MeasurementFixture.DISJOINT: (
        "checkout/guest_session.py",
        "orders/summary_view.py",
    ),
    MeasurementFixture.OVERLAPPING: (
        "shared/index_schema.py,search/alpha.py",
        "shared/index_schema.py,search/beta.py",
    ),
    MeasurementFixture.TIMED_OUT: ("des/config.py", "orders/summary_view.py"),
}

#: The file named as un-measurable in the TIMED_OUT fixture's expected
#: `unmeasured.paths` (feature-a's scope, the first of the pair).
_TIMED_OUT_UNMEASURABLE_FILE = "des/config.py"

#: A trivially small wall-clock budget -- forces the real `des blast-radius`
#: subprocess past its budget regardless of file size (mirrors row-3's own
#: slice-02 characterization AT).
_FORCED_TIMEOUT_S = 0.001


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


@dataclass
class ReportResult:
    """Observable outcome of one `parallel-safety-report` CLI invocation.

    Reads BOTH the `ParallelSafetyReport` and `ParallelSafetyInputRejected`
    JSON event shapes into one typed surface so a Then-step never needs to
    know which event fired -- only the `outcome` token + the raw payload for
    detail assertions (GDP-3: naming what/why).
    """

    exit_code: int
    output: str

    @property
    def _payload(self) -> dict[str, object] | None:
        for line in self.output.splitlines():
            stripped = line.strip()
            if not (stripped.startswith("{") and stripped.endswith("}")):
                continue
            with contextlib.suppress(json.JSONDecodeError):
                obj = json.loads(stripped)
                if isinstance(obj, dict) and "event" in obj:
                    return obj
        return None

    @property
    def outcome(self) -> ReportOutcome:
        """Map the CLI's structured event+verdict onto the typed outcome.

        No structured event at all -> UNRECOGNISED_INVOCATION (the current-tip
        argparse-usage-error behaviour before `--epic-delta` ships). An
        off-contract verdict token -> ValueError, failing loudly rather than
        silently misclassifying.
        """
        obj = self._payload
        if obj is None:
            return ReportOutcome.UNRECOGNISED_INVOCATION
        event = str(obj.get("event"))
        if event == "ParallelSafetyInputRejected":
            return ReportOutcome.INPUT_REJECTED
        if event == "ParallelSafetyReport":
            token = str(obj["verdict"])
            if token not in _OUTCOME_BY_VERDICT_TOKEN:
                raise ValueError(
                    f"parallel-safety-report emitted an off-contract verdict "
                    f"token {token!r}; expected one of "
                    f"{sorted(_OUTCOME_BY_VERDICT_TOKEN)}"
                )
            return _OUTCOME_BY_VERDICT_TOKEN[token]
        return ReportOutcome.UNRECOGNISED_INVOCATION

    @property
    def payload(self) -> dict[str, object]:
        """The full parsed JSON payload -- for detail/shape assertions."""
        obj = self._payload
        assert obj is not None, (
            f"expected a structured JSON event on stdout, got: {self.output!r}"
        )
        return obj


@dataclass
class ParallelSafetyReportFeaturePlanComposition:
    """Production-wired composition root for the slice-02 acceptance slice.

    ``repo_dir`` is a real tmp_path directory acting as the repository root
    (git-initialized by `provision_repository_fixture`). ``active_path``
    tracks the epic-delta doc so `capture_universe` always targets the
    fixture the current scenario actually built.
    """

    repo_dir: Path
    epic_id: EpicId = field(default=EpicId("swarm-parallel-delivery"))
    active_path: Path = field(init=False, default=None)  # type: ignore[assignment]
    _scope_paths: dict[FeatureId, str] = field(init=False, default_factory=dict)

    # --- paths -----------------------------------------------------------

    @property
    def _epic_delta_path(self) -> Path:
        return self.repo_dir / "docs" / "epic" / self.epic_id / "epic-delta.md"

    @property
    def _decoy_feature_delta_path(self) -> Path:
        """A well-formed but irrelevant feature-delta -- used ONLY by CT-8's
        "both sources supplied" scenario to supply a syntactically-valid
        second input path."""
        return self.repo_dir / "feature-delta.md"

    # --- Given: repo -------------------------------------------------------

    def create_epic(self, epic_id: EpicId) -> None:
        """Create the epic directory skeleton (also the repo root).

        Seeds `_scope_paths` with PLACEHOLDER paths for all three fixture
        feature-ids -- `provision_repository_fixture` later OVERRIDES
        feature-a/feature-b with real, measured paths; scenarios that reject
        BEFORE any measurement (CT-9) never call it, so the placeholders
        (which need not exist on disk -- the rejection fires at scope-id
        validation, before any file is read) are all such a scenario needs.
        """
        self.epic_id = epic_id
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        self._epic_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self._scope_paths = {
            FeatureId("feature-a"): "alpha.py",
            FeatureId("feature-b"): "beta.py",
            FeatureId("feature-c"): "gamma.py",
        }

    # --- Given: fixtures ---------------------------------------------------

    def provision_feature_plan(self) -> None:
        """Write an epic-delta whose Feature Plan declares the fixed
        three-row fixture (feature-a + feature-b parallel, feature-c
        declared-serial on feature-b)."""
        body = (
            "# Epic Delta: parallel-safety-report-feature-plan-input fixture\n\n"
            "## Wave: DISCUSS / [REF] Feature Plan\n\n"
            "| Feature | Value statement | Status | Annotation | Justification |\n"
            "|---------|-----------------|--------|------------|---------------|\n"
            f"{_FEATURE_PLAN_ROWS}\n"
        )
        self._epic_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self._epic_delta_path.write_text(body, encoding="utf-8")
        self.active_path = self._epic_delta_path

    def provision_repository_fixture(self, fixture: MeasurementFixture) -> None:
        """A real git work-tree tracking `fixture`'s files, plus the
        `--scope` path binding for feature-a/feature-b it implies."""
        files = _REPO_FILES_BY_FIXTURE[fixture]
        _git(self.repo_dir, "init", "-q")
        _git(self.repo_dir, "config", "user.email", "t@t")
        _git(self.repo_dir, "config", "user.name", "t")
        _git(self.repo_dir, "config", "--local", "core.hooksPath", ".git/hooks")
        for relpath, content in files.items():
            target = self.repo_dir / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        _git(self.repo_dir, "add", "-A")
        _git(self.repo_dir, "commit", "-q", "-m", "base commit")

        paths_a, paths_b = _SCOPE_PATHS_BY_FIXTURE[fixture]
        self._scope_paths[FeatureId("feature-a")] = paths_a
        self._scope_paths[FeatureId("feature-b")] = paths_b

    # --- When: run the report -----------------------------------------------

    def run_measurement_report(
        self,
        pair: tuple[FeatureId, FeatureId],
        forced_timeout: bool,
    ) -> ReportResult:
        """Invoke the production CLI, binding `pair`'s two feature-ids to the
        scope paths `provision_repository_fixture` recorded."""
        argv = [
            "--epic-delta",
            str(self._epic_delta_path),
            "--repo",
            str(self.repo_dir),
        ]
        for feature_id in pair:
            argv += ["--scope", f"{feature_id}={self._scope_paths[feature_id]}"]
        if forced_timeout:
            argv += ["--timeout", str(_FORCED_TIMEOUT_S)]
        return self._invoke(argv)

    def run_report_with_input_source_case(self, case: InputSourceCase) -> ReportResult:
        """CT-8: an ambiguous (both-supplied) or missing (neither-supplied)
        input source -- no measurement is ever attempted."""
        argv: list[str] = ["--repo", str(self.repo_dir)]
        if case is InputSourceCase.BOTH_SUPPLIED:
            self._decoy_feature_delta_path.write_text(
                "# Feature Delta -- decoy\n\n"
                "## Wave: DISCUSS / [REF] Slice Plan\n\n"
                "| Slice | Value statement | Status | Annotation | Justification |\n"
                "|-------|-----------------|--------|------------|----------------|\n"
                "| slice-01 | placeholder. | pending |  |  |\n",
                encoding="utf-8",
            )
            argv += [
                "--epic-delta",
                str(self._epic_delta_path),
                "--feature-delta",
                str(self._decoy_feature_delta_path),
            ]
        # NEITHER_SUPPLIED: neither flag is added -- argv carries only --repo.
        argv += [
            "--scope",
            "feature-a=alpha.py",
            "--scope",
            "feature-b=beta.py",
        ]
        return self._invoke(argv)

    def _invoke(self, argv: list[str]) -> ReportResult:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = parallel_safety_report_main(argv)
        return ReportResult(exit_code=exit_code, output=buffer.getvalue())

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        The report has a read-only contract (Effect Isolation, DESIGN [REF]
        Driving Ports): it reads the epic-delta and MUST NOT mutate it. The
        universe is `active_path`'s existence and bytes -- the state-delta
        guard proves the read-only contract.
        """
        path = self.active_path
        return {
            "document.exists": path is not None and path.exists(),
            "document.bytes": (
                path.read_bytes() if path is not None and path.exists() else None
            ),
        }
