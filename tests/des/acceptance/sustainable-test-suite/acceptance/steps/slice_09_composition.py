"""Test-side composition for slice-09: arrange a feature-delta + an AST step-shape corpus
on tmp_path, drive the spine CLI with the existing-base near-duplicate-step trend leg.

slice-09 of sustainable-test-suite — EXISTING-BASE CONTINUOUS REDUCTION (DDD-16C + DDD-17C,
the ACTIVE counter-gradient). The shipped A+C metrics + the slice-07 consolidate-on-add gain
measure reuse at the ADD boundary; they are PASSIVE w.r.t. the thousands of pre-existing
near-duplicate steps. slice-09 closes that: each `/nw-distill` run measurably REDUCES the
EXISTING base's duplication, the gate REPORTS the existing-base near-duplicate-step ratio
(AST step-similarity behind the `CodeFactPort`, git-free) as an EVIDENCE cell, and the trend
must NOT regress slice-on-slice (advisory-LOUD first, gated on a downward trend).

Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
`des validate-feature-delta --require-sustainability --with-metrics --existing-base-trend
[--prior-existing-base-ratio=<float>] [--corpus-root=<dir>] --format=json` invoked as a real
subprocess. The subprocess IS the SUT — NO production module is imported and called at the
step boundary. The feature-delta + the AST step-shape corpus (a real tree of test files whose
step-definition bodies the CodeFactPort AST adapter parses into normalized shapes) are written
to a hermetic tmp_path (the `@real-io` AST step-shape extraction). The degrade-LOUD scenario
arranges a corpus the AST tier cannot read (absent / unparseable) so the CodeFactPort returns
no step-shape fact and the leg degrades to INDETERMINATE.

DISCRIMINATOR (mirrors the slice-07 design-defect FIX): `--existing-base-trend` is an explicit
MODE flag, DISTINCT from the `--prior-existing-base-ratio` VALUE and from `--consolidate-on-add`.
The existing-base leg fires ONLY when the mode flag is present, so a plain `--with-metrics` run
(slice-04 accept-on-trend) and a `--consolidate-on-add` run (slice-07) are never routed through
the existing-base trend path. The routing over the (corpus-available?, prior-supplied?, ratio)
space:
  * `--existing-base-trend`, corpus parseable, ratio < prior          -> `improved`, accept (sc1);
  * `--existing-base-trend`, corpus parseable, ratio > prior          -> `regressed`, reject (sc2,
    top verdict `existing-base-duplication-regressed`);
  * `--existing-base-trend`, AST corpus unavailable                   -> `indeterminate`
    degrade-LOUD, reject (sc3) — NEVER a fabricated `0.0` ratio / downward trend (DDD-17C);
  * `--existing-base-trend`, parseable corpus but NO prior ratio      -> `indeterminate`
    degrade-LOUD, reject (sc4) — the prior committed value is the trend denominator; with no
    prior, the trend cannot be decided (boundary-zero / no-baseline robustness, C3);
  * NO `--existing-base-trend`                                        -> slice-04/07 paths,
    UNCHANGED.

The prior committed ratio is read GIT-FREE from the prior feature-delta sustainability section
(not from git history, DDD-17C); the AT supplies it as the `--prior-existing-base-ratio` VALUE,
exactly as slice-07 supplies the add-only baseline as a CLI value.

Active-RED: at HEAD `des validate-feature-delta --with-metrics` reports the slice-04 cells +
the slice-07 consolidate-on-add leg, but accepts NO `--existing-base-trend` flag, NO
`--prior-existing-base-ratio` argument, and NO `--corpus-root` argument, and emits NO
`existing_base_duplication_ratio` cell nor an `existing_base_trend` cross-check object
(`sustainability_metrics.py` has no `existing_base_duplication_ratio` symbol and
`code_fact_port.py` has no step-shape capability). The `--existing-base-trend` flag does not
exist at HEAD, so argparse rejects it and the subprocess emits no JSON verdict object — every
scenario's existing-base accessor raises a clean AssertionError (MISSING_FUNCTIONALITY — the
pure ratio calc + the CodeFactPort step-shape leg + the `--existing-base-trend` mode are not
yet implemented), NOT an ImportError. DELIVER makes them GREEN by adding the pure
`existing_base_duplication_ratio` calc to `sustainability_metrics.py` + the CodeFactPort
step-shape extraction leg + the `--existing-base-trend` mode flag + the
`--prior-existing-base-ratio` / `--corpus-root` values — it does NOT unskip anything.

The reusable subprocess + section-builder idioms MIRROR slice-04/07's driver — authored reuse
of the same domain-concept arrangement (DDD-2C: composition in code), specialized here with the
existing-base corpus + prior-ratio arguments.
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

    from .slice_09_domain_types import ExistingBaseTrendVerdict, Verdict


# This file lives at tests/des/acceptance/sustainable-test-suite/acceptance/steps/, so
# parents[6] is the repo root. The subprocess runs with cwd=repo-root so `python -m des`
# resolves exactly as in production (mirrors slice-03/04/07).
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

        Active-RED at HEAD: the `--existing-base-trend` mode flag does not exist, so argparse
        rejects the invocation and the subprocess emits no JSON verdict object — this assertion
        fires (MISSING_FUNCTIONALITY), the right reason, not an ImportError.
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
            "--require-sustainability --with-metrics --existing-base-trend "
            "[--prior-existing-base-ratio=<float>] [--corpus-root=<dir>]` existing-base trend "
            "gate is not yet implemented (MISSING_FUNCTIONALITY — the `--existing-base-trend` "
            "mode flag does not exist at HEAD, so argparse rejects it); "
            f"got stdout {self.stdout!r} (exit {self.exit_code}, stderr {self.stderr!r})"
        )
        return payload

    def metrics_payload(self) -> dict[str, object]:
        """The `metrics` evidence object the `--with-metrics` mode attaches."""
        payload = self.verdict_payload()
        metrics = payload.get("metrics")
        assert isinstance(metrics, dict), (
            "no `metrics` evidence object on the verdict payload — the metrics mode is "
            f"not reporting evidence (MISSING_FUNCTIONALITY); got {payload!r}"
        )
        return metrics

    def existing_base_trend_payload(self) -> dict[str, object]:
        """The `existing_base_trend` cross-check object the existing-base leg attaches.

        Active-RED at HEAD: no `existing_base_trend` object is emitted (the leg + the
        `--existing-base-trend` mode are not implemented), so this fires
        (MISSING_FUNCTIONALITY) — the existing-base trend calc is not yet implemented.
        """
        payload = self.verdict_payload()
        trend = payload.get("existing_base_trend")
        assert isinstance(trend, dict), (
            "no `existing_base_trend` cross-check object on the verdict payload — the "
            "existing-base near-duplicate-step trend leg (current run's ratio vs the prior "
            "committed ratio) is not yet implemented (MISSING_FUNCTIONALITY); "
            f"got {payload!r}"
        )
        return trend


def _run(args: Sequence[str]) -> CliResult:
    proc = subprocess.run(
        [sys.executable, "-m", "des", "validate-feature-delta", *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    return CliResult(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


# ---------------------------------------------------------------------------
# Section-block builders — the sustainability SCHEMA the maintainer authors (DDD-3, 5
# columns) declaring the existing-base boy-scout consolidation intent. Test-arrangement only.
# ---------------------------------------------------------------------------

_HEADER_ROW = "| " + " | ".join(CANONICAL_SECTION_COLUMNS) + " |"
_SEPARATOR_ROW = "|" + "|".join(["---"] * len(CANONICAL_SECTION_COLUMNS)) + "|"


def _delta_with_section(section_block: str) -> str:
    return (
        "# Feature Delta: slice-09 fixture\n\n"
        "## Wave: DISTILL / [REF] Test Reuse & Consolidation Analysis\n\n"
        f"{section_block}\n"
    )


def _existing_base_section(decision: str) -> str:
    """A schema-valid section declaring a `decision` (CONSOLIDATE/REUSE) intent.

    The existing-base trend leg compares the current run's near-duplicate-step ratio against
    the prior committed ratio: a run whose ratio is NOT below the prior committed value is the
    regression the downward-trend gate (DDD-16C) blocks.
    """
    row = (
        "| an existing near-duplicate step cluster folded into the shared vocabulary "
        "| tests/des/acceptance/sustainable-test-suite/acceptance/steps/slice_09_composition.py "
        "| folds a pre-existing near-duplicate step cluster into the shared step vocabulary "
        f"| {decision} "
        "| reduces the existing-base near-duplicate-step ratio (DDD-16C boy-scout consolidation) |"
    )
    return "\n".join([CANONICAL_SECTION_HEADING, "", _HEADER_ROW, _SEPARATOR_ROW, row])


class ExistingBaseTrendDriver:
    """Test-side driving facade over the spine existing-base trend gate (the SUT).

    Arranges a sustainability feature-delta + an AST step-shape corpus (a real test tree the
    CodeFactPort AST adapter parses) on tmp_path, and (where the scenario supplies one) a
    declared prior committed ratio, runs `--require-sustainability --with-metrics
    --existing-base-trend [--prior-existing-base-ratio=<N>] [--corpus-root=<dir>]
    --format=json` as a real subprocess, and exposes the closed verdict token + the `metrics`
    evidence object + the `existing_base_duplication_ratio` cell + the `existing_base_trend`
    cross-check verdict + exit code for assertion.
    """

    def __init__(self) -> None:
        self._delta_path: Path | None = None
        self._workdir: Path | None = None
        self._prior_ratio: float | None = None
        self._corpus_root: Path | None = None
        # The DISCRIMINATING SIGNAL (mirrors slice-07 option B): an explicit existing-base-trend
        # MODE flag, distinct from the `--prior-existing-base-ratio` VALUE. Every slice-09 Given
        # DECLARES existing-base-trend intent by setting this True, so the gate's leg fires ONLY
        # on declared intent — never on slice-04's plain `--with-metrics` trend-check nor
        # slice-07's `--consolidate-on-add` run.
        self._existing_base_trend: bool = False
        self._result: CliResult | None = None

    # -- arrange (Given) -----------------------------------------------------

    def given_existing_base_improved_below_prior(self, tmp_path: Path) -> None:
        """A run that folded ≥1 cluster: the existing-base ratio is BELOW the prior committed.

        The happy/improved path: the corpus, after this run's consolidation, has FEWER
        near-duplicate step clusters than the prior committed ratio reflected, so the
        existing-base ratio is strictly below the prior → `improved`, accepted on trend.
        """
        # A corpus where most step definitions are already distinct (few near-dup clusters)
        # → a LOW current ratio, below the (higher) prior committed value.
        self._corpus_root = self._build_corpus(
            tmp_path, near_dup_clusters=1, distinct=9
        )
        self._prior_ratio = 0.30
        self._existing_base_trend = True
        self._write_delta(
            tmp_path, _delta_with_section(_existing_base_section("CONSOLIDATE"))
        )

    def given_existing_base_regressed_above_prior(self, tmp_path: Path) -> None:
        """A run whose existing-base ratio ROSE above the prior committed value — regressed.

        The regression path: the corpus has MORE near-duplicate step clusters than the prior
        committed ratio reflected (duplication got worse), so the existing-base ratio is above
        the prior → `regressed` → top verdict `existing-base-duplication-regressed`, gated.
        """
        # A corpus dense with near-duplicate clusters → a HIGH current ratio, above the
        # (lower) prior committed value.
        self._corpus_root = self._build_corpus(
            tmp_path, near_dup_clusters=6, distinct=4
        )
        self._prior_ratio = 0.20
        self._existing_base_trend = True
        self._write_delta(
            tmp_path, _delta_with_section(_existing_base_section("CONSOLIDATE"))
        )

    def given_ast_corpus_unavailable(self, tmp_path: Path) -> None:
        """An existing-base-trend run where the AST step-shape corpus cannot be read.

        DDD-17C degrade-LOUD: the CodeFactPort AST tier cannot parse the corpus (the corpus
        root points at a directory with no parseable step definitions), so it returns no
        step-shape fact and the ratio cannot be computed. The leg must return INDETERMINATE
        (exit non-zero), NEVER a fabricated `0.0` ratio and NEVER a fabricated downward trend.
        """
        # An empty / unparseable corpus root — no step-shape fact extractable.
        self._corpus_root = tmp_path / "no_parseable_steps"
        self._corpus_root.mkdir(parents=True, exist_ok=True)
        (self._corpus_root / "not_python.txt").write_text(
            "this is not a parseable step-definition module\n", encoding="utf-8"
        )
        self._prior_ratio = 0.25
        self._existing_base_trend = True
        self._write_delta(
            tmp_path, _delta_with_section(_existing_base_section("REUSE"))
        )

    def given_existing_base_trend_without_prior(self, tmp_path: Path) -> None:
        """An existing-base-trend run with NO prior committed ratio supplied — indeterminate.

        Boundary-zero / no-baseline robustness (C3): the prior committed ratio is the trend
        denominator (the value to compare against). With no prior, the trend cannot be
        decided, so the leg must degrade LOUD to INDETERMINATE (exit non-zero), NEVER falling
        back to a silent accept and NEVER fabricating a downward trend.

        DISCRIMINATOR: this run DECLARES existing-base-trend intent via the explicit
        `--existing-base-trend` MODE flag while WITHHOLDING the `--prior-existing-base-ratio`
        VALUE — the mode flag is what pries this scenario apart from any plain `--with-metrics`
        accept path; a coa/plain run can never carry the existing-base-trend mode flag.
        """
        self._corpus_root = self._build_corpus(
            tmp_path, near_dup_clusters=2, distinct=8
        )
        # DECLARE existing-base-trend intent (the discriminating MODE flag) ...
        self._existing_base_trend = True
        # ... but deliberately WITHHOLD the `--prior-existing-base-ratio` VALUE — no
        # denominator to compare against, so the leg must degrade LOUD to INDETERMINATE.
        self._prior_ratio = None
        self._write_delta(
            tmp_path, _delta_with_section(_existing_base_section("CONSOLIDATE"))
        )

    # -- act (When) ----------------------------------------------------------

    def when_existing_base_trend_check_runs(self) -> None:
        assert self._delta_path is not None, "no feature-delta was arranged"
        args = ["--require-sustainability", "--with-metrics"]
        # The DISCRIMINATING MODE flag — emitted by EVERY slice-09 scenario that declares
        # existing-base-trend intent. Its PRESENCE activates the existing-base leg; its ABSENCE
        # is exactly the SHIPPED slice-04 plain `--with-metrics` / slice-07 `--consolidate-on-add`
        # paths, so the gate routes them to distinct exit codes from DISTINCT inputs.
        if self._existing_base_trend:
            args.append("--existing-base-trend")
        # The AST step-shape corpus root the CodeFactPort reads (the `@real-io` AST extraction).
        if self._corpus_root is not None:
            args.append(f"--corpus-root={self._corpus_root}")
        # The prior committed ratio VALUE is a SEPARATE argument from the MODE flag: a run can
        # declare intent (mode flag) yet withhold the prior (sc4) → INDETERMINATE.
        if self._prior_ratio is not None:
            args.append(f"--prior-existing-base-ratio={self._prior_ratio}")
        args += ["--format=json", str(self._delta_path)]
        self._result = _run(args)

    # -- assert (Then) -------------------------------------------------------

    def then_accepts(self) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert result.exit_code == 0, (
            "an accepted existing-base-trend section must exit 0; "
            f"got exit {result.exit_code}, {payload!r}"
        )

    def then_rejects(self) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert result.exit_code != 0, (
            "a rejected/indeterminate existing-base-trend check must exit non-zero; "
            f"got exit {result.exit_code}, {payload!r}"
        )

    def then_verdict_is(self, expected: Verdict) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert payload["verdict"] == expected.value, (
            f"the existing-base-trend gate must emit the {expected.value!r} verdict for this "
            f"feature-delta; got {payload!r} (exit {result.exit_code})"
        )

    def then_reports_existing_base_ratio(self) -> None:
        """The `metrics` object carries the existing-base near-duplicate-step ratio cell."""
        metrics = self._require_result().metrics_payload()
        assert "existing_base_duplication_ratio" in metrics, (
            "the metrics evidence must carry the `existing_base_duplication_ratio` cell "
            "(near-duplicate step groups / total step definitions over the AST step-shape "
            f"corpus); got {metrics!r}"
        )

    def then_existing_base_ratio_is_a_real_fraction(self) -> None:
        """The reported existing-base ratio is a real number in [0.0, 1.0] (not fabricated)."""
        metrics = self._require_result().metrics_payload()
        ratio = metrics.get("existing_base_duplication_ratio")
        assert isinstance(ratio, (int, float)) and 0.0 <= ratio <= 1.0, (
            "the existing-base near-duplicate-step ratio must be a real fraction in [0.0, 1.0] "
            "computed over the AST step-shape corpus (a near-duplicate-group / total-step-def "
            f"ratio), never a fabricated value; got {ratio!r} in {metrics!r}"
        )

    def then_existing_base_ratio_below_prior(self) -> None:
        """The numeric trend invariant: the current ratio is strictly below the prior committed."""
        assert self._prior_ratio is not None, (
            "this assertion needs a declared prior ratio"
        )
        metrics = self._require_result().metrics_payload()
        ratio = metrics.get("existing_base_duplication_ratio")
        assert isinstance(ratio, (int, float)) and ratio < self._prior_ratio, (
            "an improving run must have an existing-base ratio strictly BELOW the prior "
            f"committed ratio ({self._prior_ratio}) — the downward trend (DDD-16C); "
            f"got {ratio!r} in {metrics!r}"
        )

    def then_existing_base_trend_is(self, expected: ExistingBaseTrendVerdict) -> None:
        """The existing-base leg reports the expected closed cross-check verdict."""
        trend = self._require_result().existing_base_trend_payload()
        assert trend.get("verdict") == expected.value, (
            f"the existing-base trend cross-check must report {expected.value!r} for this run "
            f"vs its prior committed ratio; got {trend!r}"
        )

    # -- internals -----------------------------------------------------------

    def _build_corpus(
        self, tmp_path: Path, *, near_dup_clusters: int, distinct: int
    ) -> Path:
        """Write a real AST step-shape corpus: `near_dup_clusters` near-duplicate step-def
        clusters (2 step defs each, identical normalized shape) + `distinct` distinct step
        defs. The CodeFactPort AST adapter parses these into normalized shapes; the ratio is
        near-duplicate groups / total step definitions. Test-arrangement only.
        """
        corpus = tmp_path / "corpus"
        corpus.mkdir(parents=True, exist_ok=True)
        lines: list[str] = ["from pytest_bdd import given, then\n\n"]
        # near-duplicate clusters: each cluster = 2 step defs with the SAME normalized body
        # shape (a near-duplicate the existing-base metric counts as ONE collapsible group).
        for c in range(near_dup_clusters):
            for dup in range(2):
                lines.append(
                    f'@given("near dup cluster {c} variant {dup}")\n'
                    f"def near_dup_{c}_{dup}(driver):\n"
                    f"    driver.do_the_same_thing()\n\n"
                )
        # distinct step defs: each a unique normalized shape.
        for d in range(distinct):
            lines.append(
                f'@then("distinct outcome {d}")\n'
                f"def distinct_{d}(driver):\n"
                f"    driver.assert_unique_thing_{d}()\n\n"
            )
        (corpus / "test_corpus_steps.py").write_text("".join(lines), encoding="utf-8")
        return corpus

    def _write_delta(self, tmp_path: Path, body: str) -> None:
        workdir = self._workdir or tmp_path
        path = workdir / "feature-delta.md"
        path.write_text(body, encoding="utf-8")
        self._delta_path = path

    def _require_result(self) -> CliResult:
        assert self._result is not None, "the existing-base-trend check was not run"
        return self._result
