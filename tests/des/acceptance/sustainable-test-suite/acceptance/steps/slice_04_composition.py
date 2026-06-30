"""Test-side composition for slice-04: arrange a feature-delta + (optionally) a real
git repo, drive the spine CLI with the metrics + blind-add cross-check extension.

slice-04 of sustainable-test-suite — the BALANCED DENOMINATOR (DDD-4 + DDD-5 + DDD-10).
Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
`des validate-feature-delta --require-sustainability --with-metrics --format=json`
invoked as a real subprocess. The subprocess IS the SUT — NO production module is
imported and called at the step boundary. Feature-delta + test-LOC fixtures are written
to a hermetic tmp_path; the blind-add cross-check scenarios initialise a REAL git repo on
that tmp_path (the `@real-io` git-diff cross-check), while the degrade-LOUD scenario
arranges a NON-git tmp_path so the cross-check cannot run.

`des` is never required by the assertions themselves — they read a JSON verdict +
`metrics` + `blind_add` object + exit code from the subprocess. `git` is required ONLY by
the real-io blind-add scenarios (and its ABSENCE is itself the assertion of the
degrade-LOUD scenario); the gate-core stays Python + filesystem.

Active-RED: at HEAD `des validate-feature-delta` has NO `--with-metrics` mode (and after
slice-03, no metrics/blind_add payload), so the subprocess emits no metrics evidence and
no blind_add cross-check object. Every scenario asserts a post-implementation
metric/verdict token, so the relevant `*_payload()` accessor raises AssertionError (the
key is absent) — a clean MISSING_FUNCTIONALITY signal, not an ImportError. DELIVER makes
them GREEN by adding the A+C metrics calculator (`sustainability_metrics.py`) + the
git-diff cross-check adapter + the `--with-metrics` mode.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .slice_02_domain_types import (
    CANONICAL_SECTION_COLUMNS,
    CANONICAL_SECTION_HEADING,
)


if TYPE_CHECKING:
    from collections.abc import Sequence

    from .slice_04_domain_types import BlindAddVerdict, Verdict


# This file lives at tests/des/acceptance/sustainable-test-suite/acceptance/steps/, so
# parents[6] is the repo root. The subprocess runs with cwd=repo-root so `python -m des`
# resolves exactly as in production (mirrors slice-03).
_REPO_ROOT = Path(__file__).resolve().parents[6]


@dataclass(frozen=True)
class CliResult:
    """The observable surface of a `des validate-feature-delta` subprocess call."""

    exit_code: int
    stdout: str
    stderr: str

    def verdict_payload(self) -> dict[str, object]:
        """Parse the last JSON object carrying a `verdict` key from stdout.

        The spine prefixes an unrelated freshness JSON line in a developer checkout; the
        verdict is the LAST decodable JSON object that is a mapping with a `verdict` key.

        Active-RED at HEAD: with no `--require-sustainability --with-metrics` mode the
        subprocess emits no JSON verdict, so this assertion fires (MISSING_FUNCTIONALITY)
        — the right reason, not an ImportError.
        """
        payload: dict[str, object] | None = None
        for raw in self.stdout.splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "verdict" in obj:
                payload = obj
        assert payload is not None, (
            "no JSON verdict object on stdout — the `des validate-feature-delta "
            "--require-sustainability --with-metrics` metrics + blind-add gate is not "
            f"yet implemented (MISSING_FUNCTIONALITY); got stdout {self.stdout!r} "
            f"(exit {self.exit_code}, stderr {self.stderr!r})"
        )
        return payload

    def metrics_payload(self) -> dict[str, object]:
        """The `metrics` evidence object the `--with-metrics` mode attaches.

        Active-RED at HEAD: no `metrics` object is emitted, so this fires
        (MISSING_FUNCTIONALITY) — the A+C metrics calculator is not yet implemented.
        """
        payload = self.verdict_payload()
        metrics = payload.get("metrics")
        assert isinstance(metrics, dict), (
            "no `metrics` evidence object on the verdict payload — the A+C metrics "
            "calculator (consolidation-delta net test-LOC + adoption-ratio) is not yet "
            f"implemented (MISSING_FUNCTIONALITY); got {payload!r}"
        )
        return metrics

    def blind_add_payload(self) -> dict[str, object]:
        """The `blind_add` cross-check object the `--with-metrics` mode attaches.

        Active-RED at HEAD: no `blind_add` object is emitted, so this fires
        (MISSING_FUNCTIONALITY) — the git-diff cross-check leg is not yet implemented.
        """
        payload = self.verdict_payload()
        blind_add = payload.get("blind_add")
        assert isinstance(blind_add, dict), (
            "no `blind_add` cross-check object on the verdict payload — the git-diff "
            "blind-add cross-check leg is not yet implemented (MISSING_FUNCTIONALITY); "
            f"got {payload!r}"
        )
        return blind_add


def _run(args: Sequence[str]) -> CliResult:
    proc = subprocess.run(
        [sys.executable, "-m", "des", "validate-feature-delta", *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    return CliResult(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


# ---------------------------------------------------------------------------
# Section-block builders — the metrics-bearing SCHEMA the maintainer authors
# (DDD-3, 5 columns) PLUS the declared sustainability INTENT (CONSOLIDATE/REUSE) the
# blind-add cross-check tests against the REAL git diff. Test-arrangement only.
# ---------------------------------------------------------------------------

_HEADER_ROW = "| " + " | ".join(CANONICAL_SECTION_COLUMNS) + " |"
_SEPARATOR_ROW = "|" + "|".join(["---"] * len(CANONICAL_SECTION_COLUMNS)) + "|"


def _delta_with_section(section_block: str) -> str:
    return (
        "# Feature Delta: slice-04 fixture\n\n"
        "## Wave: DISTILL / [REF] Test Reuse & Consolidation Analysis\n\n"
        f"{section_block}\n"
    )


def _consolidate_section(decision: str) -> str:
    """A schema-valid section declaring a `decision` (CONSOLIDATE/REUSE) intent.

    The blind-add cross-check compares THIS declared intent against the real net added
    test-LOC: a CONSOLIDATE/REUSE claim with a net test-LOC INCREASE is the blind-add
    the cross-check unmasks.
    """
    row = (
        "| the registry-section subprocess idiom "
        "| tests/des/acceptance/sustainable-test-suite/acceptance/steps/composition.py "
        "| the Layer-3 subprocess + closed-verdict assertion shape "
        f"| {decision} "
        "| folds the duplicated subprocess-driving steps into the shared driver |"
    )
    return "\n".join([CANONICAL_SECTION_HEADING, "", _HEADER_ROW, _SEPARATOR_ROW, row])


class SustainabilityMetricsDriver:
    """Test-side driving facade over the spine metrics + blind-add gate (the SUT).

    Arranges a feature-delta + a test-LOC delta on tmp_path (and, for the cross-check
    scenarios, a REAL git repo), runs `--require-sustainability --with-metrics` as a real
    subprocess, and exposes the closed verdict token + the `metrics` evidence object + the
    `blind_add` cross-check verdict + exit code for assertion.
    """

    def __init__(self) -> None:
        self._delta_path: Path | None = None
        self._workdir: Path | None = None
        self._is_git_repo: bool = False
        self._result: CliResult | None = None

    # -- arrange (Given) -----------------------------------------------------

    def given_consolidation_work_declared(self, tmp_path: Path) -> None:
        """A section declaring CONSOLIDATE + a real net test-LOC REDUCTION in git.

        The happy/metrics path: the declared intent is consistent with a net test-LOC
        delta ≤ 0, so the gate reports the evidence cells and accepts on trend.
        """
        self._init_git_repo(tmp_path)
        self._commit_baseline_test_loc(tmp_path, lines=40)
        self._reduce_test_loc(tmp_path, lines=25)
        self._write_delta(
            tmp_path, _delta_with_section(_consolidate_section("CONSOLIDATE"))
        )

    def given_consolidate_claim_but_net_add(self, tmp_path: Path) -> None:
        """A section CLAIMING CONSOLIDATE but a real git diff with a net test-LOC INCREASE.

        The blind-add path slice-03 deferred here: the claim is inconsistent with the
        observed diff, so the cross-check unmasks it as `blind-add` → top-level
        `blind-add-detected`.
        """
        self._init_git_repo(tmp_path)
        self._commit_baseline_test_loc(tmp_path, lines=20)
        self._grow_test_loc(tmp_path, lines=120)
        self._write_delta(
            tmp_path, _delta_with_section(_consolidate_section("CONSOLIDATE"))
        )

    def given_consolidation_declared_outside_git(self, tmp_path: Path) -> None:
        """A CONSOLIDATE section on a NON-git tmp_path — the cross-check cannot run.

        DDD-4 / DDD-10 degrade-LOUD: the git-diff cross-check has no repo to read, so the
        `blind_add` leg must return INDETERMINATE (exit non-zero), NEVER a fabricated pass.
        """
        # Deliberately NO `git init` — the cross-check has no diff to compute.
        self._workdir = tmp_path
        self._is_git_repo = False
        self._write_delta(
            tmp_path, _delta_with_section(_consolidate_section("CONSOLIDATE"))
        )

    def given_trend_non_regressing_consolidation(self, tmp_path: Path) -> None:
        """A section whose net test-LOC delta ≤ 0 — trend non-regression (DDD-5).

        Proves the advisory nature: the gate checks slice-on-slice non-regression, not an
        absolute reuse/lean threshold, so a non-regressing slice is accepted with NO
        absolute-cliff rejection.
        """
        self._init_git_repo(tmp_path)
        self._commit_baseline_test_loc(tmp_path, lines=60)
        self._reduce_test_loc(tmp_path, lines=10)
        self._write_delta(tmp_path, _delta_with_section(_consolidate_section("REUSE")))

    def given_metrics_requested_on_section_without_evidence(
        self, tmp_path: Path
    ) -> None:
        """A malformed path: metrics requested on a section that cannot supply evidence.

        The section omits the metrics-bearing rows entirely (heading only), so the A+C
        evidence cells cannot be computed — a closed malformed-section error, not a
        silent zero.
        """
        self._init_git_repo(tmp_path)
        self._commit_baseline_test_loc(tmp_path, lines=10)
        body = (
            "# Feature Delta: slice-04 fixture\n\n"
            "## Wave: DISTILL / [REF] Test Reuse & Consolidation Analysis\n\n"
            f"{CANONICAL_SECTION_HEADING}\n\n(no rows — evidence cannot be supplied)\n"
        )
        self._write_delta(tmp_path, body)

    # -- act (When) ----------------------------------------------------------

    def when_metrics_check_runs(self) -> None:
        assert self._delta_path is not None, "no feature-delta was arranged"
        self._result = _run(
            [
                "--require-sustainability",
                "--with-metrics",
                "--format=json",
                str(self._delta_path),
            ]
        )

    # -- assert (Then) -------------------------------------------------------

    def then_accepts(self) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert result.exit_code == 0, (
            "an accepted sustainability section must exit 0; "
            f"got exit {result.exit_code}, {payload!r}"
        )

    def then_rejects(self) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert result.exit_code != 0, (
            "a rejected/indeterminate sustainability check must exit non-zero; "
            f"got exit {result.exit_code}, {payload!r}"
        )

    def then_verdict_is(self, expected: Verdict) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert payload["verdict"] == expected.value, (
            f"the metrics gate must emit the {expected.value!r} verdict for this "
            f"feature-delta; got {payload!r} (exit {result.exit_code})"
        )

    def then_reports_consolidation_delta_evidence(self) -> None:
        """The `metrics` object carries the A (consolidation-delta net test-LOC) cell."""
        metrics = self._require_result().metrics_payload()
        assert "consolidation_delta_loc" in metrics, (
            "the metrics evidence must carry the A cell `consolidation_delta_loc` "
            f"(net test-LOC delta); got {metrics!r}"
        )

    def then_reports_adoption_ratio_evidence(self) -> None:
        """The `metrics` object carries the C (generic-framework-adoption-ratio) cell."""
        metrics = self._require_result().metrics_payload()
        assert "adoption_ratio" in metrics, (
            "the metrics evidence must carry the C cell `adoption_ratio` "
            f"(generic-framework-adoption-ratio); got {metrics!r}"
        )

    def then_consolidation_delta_is_non_positive(self) -> None:
        """The numeric invariant: net test-LOC delta ≤ 0 for a consolidating slice (A)."""
        metrics = self._require_result().metrics_payload()
        delta = metrics.get("consolidation_delta_loc")
        assert isinstance(delta, (int, float)) and delta <= 0, (
            "a consolidating slice must report a net test-LOC delta ≤ 0 "
            f"(the A invariant); got {delta!r} in {metrics!r}"
        )

    def then_blind_add_cross_check_is(self, expected: BlindAddVerdict) -> None:
        """The git-diff cross-check leg reports the expected closed verdict."""
        blind_add = self._require_result().blind_add_payload()
        assert blind_add.get("verdict") == expected.value, (
            f"the blind-add cross-check must report {expected.value!r} for this diff; "
            f"got {blind_add!r}"
        )

    # -- internals -----------------------------------------------------------

    def _write_delta(self, tmp_path: Path, body: str) -> None:
        workdir = self._workdir or tmp_path
        path = workdir / "feature-delta.md"
        path.write_text(body, encoding="utf-8")
        self._delta_path = path

    def _init_git_repo(self, tmp_path: Path) -> None:
        self._workdir = tmp_path
        self._is_git_repo = True
        subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
        subprocess.run(
            ["git", "config", "user.email", "slice04@test.local"],
            cwd=str(tmp_path),
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "slice04"], cwd=str(tmp_path), check=True
        )

    def _test_file(self, tmp_path: Path) -> Path:
        return tmp_path / "tests" / "test_fixture_slice.py"

    def _commit_baseline_test_loc(self, tmp_path: Path, *, lines: int) -> None:
        f = self._test_file(tmp_path)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(
            "\n".join(f"# baseline test line {i}" for i in range(lines)) + "\n"
        )
        subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "baseline test-LOC"],
            cwd=str(tmp_path),
            check=True,
        )

    def _reduce_test_loc(self, tmp_path: Path, *, lines: int) -> None:
        """Working-tree net REDUCTION of test-LOC (consolidation): delta ≤ 0."""
        f = self._test_file(tmp_path)
        f.write_text("\n".join(f"# test line {i}" for i in range(lines)) + "\n")

    def _grow_test_loc(self, tmp_path: Path, *, lines: int) -> None:
        """Working-tree net INCREASE of test-LOC (blind add): delta > 0."""
        f = self._test_file(tmp_path)
        f.write_text("\n".join(f"# test line {i}" for i in range(lines)) + "\n")

    def _require_result(self) -> CliResult:
        assert self._result is not None, "the sustainability metrics check was not run"
        return self._result
