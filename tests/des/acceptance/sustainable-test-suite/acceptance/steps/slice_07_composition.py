"""Test-side composition for slice-07: arrange a consolidate-on-add feature-delta + a real
git repo, drive the spine CLI with the consolidate-on-add (add-AND-improve) metric leg.

slice-07 of sustainable-test-suite — CONSOLIDATE-ON-ADD (DDD-4 + DDD-5 + DDD-6, the
"add-AND-improve" / test-suite REFACTOR phase). The shipped slice-04 `--with-metrics` mode
reports ONE feature's net test-LOC delta against its OWN git diff — it is PASSIVE w.r.t.
whether the run ADDED a slice AND consolidated, or merely added. slice-07 closes that: the
gate measures the consolidate-on-add GAIN — the consolidating run's net test-LOC RELATIVE
to the add-only BASELINE for the same added scope — so the counter-gradient that bends the
+94%/feature curve (slice-06 H) has the same mechanical force as the completeness gate.

Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
`des validate-feature-delta --require-sustainability --with-metrics --consolidate-on-add
--add-only-baseline-loc=<N> --format=json` invoked as a real subprocess. The subprocess IS
the SUT — NO production module is imported and called at the step boundary. Feature-delta +
test-LOC fixtures are written to a hermetic tmp_path with a REAL git repo (the `@real-io`
git-diff that supplies the run's net test-LOC).

DISCRIMINATOR (the design-defect FIX): `--consolidate-on-add` is an explicit MODE flag,
DISTINCT from the `--add-only-baseline-loc` VALUE. The coa-leg fires ONLY when the mode flag
is present. This is what dissolves the byte-identical collision with the SHIPPED slice-04
accept-on-trend AT: slice-04 sends plain `--with-metrics` (NO `--consolidate-on-add`) with no
baseline and is ACCEPTED on trend (exit 0); sc3 sends `--consolidate-on-add` (mode declared)
with no baseline and is rejected INDETERMINATE (exit non-zero). The two are no longer
byte-identical invocations demanding opposite exit codes — the gate routes on the presence of
the coa MODE flag. The routing:
  * `--consolidate-on-add` + `--add-only-baseline-loc=N`, gain ≤ 0 → `realized`, accept (sc1);
  * `--consolidate-on-add` + `--add-only-baseline-loc=N`, gain  > 0 → `not-realized`, reject (sc2);
  * `--consolidate-on-add` + NO baseline → `indeterminate` degrade-LOUD, reject (sc3);
  * `--consolidate-on-add` + no evidence rows → `malformed-sustainability-section`, reject (sc4);
  * NO `--consolidate-on-add` (plain `--with-metrics`) → slice-04 accept-on-trend, UNCHANGED.

Active-RED: at HEAD `des validate-feature-delta --with-metrics` reports the slice-04
`metrics` cells (`consolidation_delta_loc`, `adoption_ratio`) + the `blind_add` cross-check,
but accepts NO `--consolidate-on-add` flag and NO `--add-only-baseline-loc` argument, and
emits NO `consolidate_on_add` leg (`sustainability_metrics.py` has only `adoption_ratio` +
`classify_blind_add` — confirmed via Tsunami atoms-in-file: 7 members, no consolidate-on-add
symbol). The `--consolidate-on-add` flag does not exist at HEAD, so every scenario's
consolidate-on-add accessor raises a clean AssertionError (MISSING_FUNCTIONALITY — the
add-AND-improve calc + the `--consolidate-on-add` mode + the `--add-only-baseline-loc` value
are not yet implemented), NOT the slice-04 collision and NOT an ImportError. DELIVER makes
them GREEN by adding the pure `consolidate_on_add_gain` calc to `sustainability_metrics.py` +
the `--consolidate-on-add` mode flag + the `--add-only-baseline-loc` value — it does NOT
unskip anything.

The reusable subprocess/git idioms (`_init_git_repo`, the test-LOC builders, the section
builders) MIRROR slice-04's driver — authored reuse of the same domain-concept arrangement
(DDD-2C: composition in code), specialized here with the add-only-baseline argument.
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

    from .slice_07_domain_types import ConsolidateOnAddVerdict, Verdict


# This file lives at tests/des/acceptance/sustainable-test-suite/acceptance/steps/, so
# parents[6] is the repo root. The subprocess runs with cwd=repo-root so `python -m des`
# resolves exactly as in production (mirrors slice-03/slice-04).
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
            "--require-sustainability --with-metrics --consolidate-on-add "
            "[--add-only-baseline-loc=<N>]` consolidate-on-add gate is not yet implemented "
            "(MISSING_FUNCTIONALITY — the `--consolidate-on-add` mode flag does not exist at "
            "HEAD, so argparse rejects it; this is the discriminator-missing RED, NOT the "
            "slice-04 byte-identical collision); "
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

    def consolidate_on_add_payload(self) -> dict[str, object]:
        """The `consolidate_on_add` cross-check object the add-AND-improve leg attaches.

        Active-RED at HEAD: no `consolidate_on_add` object is emitted (the leg + the
        `--add-only-baseline-loc` mode are not implemented), so this fires
        (MISSING_FUNCTIONALITY) — the consolidate-on-add calc is not yet implemented.
        """
        payload = self.verdict_payload()
        coa = payload.get("consolidate_on_add")
        assert isinstance(coa, dict), (
            "no `consolidate_on_add` cross-check object on the verdict payload — the "
            "add-AND-improve leg (consolidating run's net test-LOC vs the add-only "
            "baseline) is not yet implemented (MISSING_FUNCTIONALITY); "
            f"got {payload!r}"
        )
        return coa


def _run(args: Sequence[str]) -> CliResult:
    proc = subprocess.run(
        [sys.executable, "-m", "des", "validate-feature-delta", *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )
    return CliResult(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


# ---------------------------------------------------------------------------
# Section-block builders — the consolidate-on-add SCHEMA the maintainer authors
# (DDD-3, 5 columns) declaring the CONSOLIDATE/REUSE intent the add-AND-improve leg tests
# against the run's net test-LOC vs the add-only baseline. Test-arrangement only.
# ---------------------------------------------------------------------------

_HEADER_ROW = "| " + " | ".join(CANONICAL_SECTION_COLUMNS) + " |"
_SEPARATOR_ROW = "|" + "|".join(["---"] * len(CANONICAL_SECTION_COLUMNS)) + "|"


def _delta_with_section(section_block: str) -> str:
    return (
        "# Feature Delta: slice-07 fixture\n\n"
        "## Wave: DISTILL / [REF] Test Reuse & Consolidation Analysis\n\n"
        f"{section_block}\n"
    )


def _consolidate_section(decision: str) -> str:
    """A schema-valid section declaring a `decision` (CONSOLIDATE/REUSE) intent.

    The add-AND-improve leg compares THIS declared consolidate-on-add intent against the
    run's net test-LOC RELATIVE to the declared add-only baseline: a consolidate-on-add
    claim whose net test-LOC is NOT below the add-only baseline is the add-only masquerade
    the counter-gradient unmasks.
    """
    row = (
        "| the slice-04 subprocess-driving step idiom "
        "| tests/des/acceptance/sustainable-test-suite/acceptance/steps/slice_07_composition.py "
        "| folds the per-slice subprocess + CliResult shape into the shared driver "
        f"| {decision} "
        "| extracts the repeated subprocess-driving steps into the shared vocabulary |"
    )
    return "\n".join([CANONICAL_SECTION_HEADING, "", _HEADER_ROW, _SEPARATOR_ROW, row])


class ConsolidateOnAddDriver:
    """Test-side driving facade over the spine consolidate-on-add gate (the SUT).

    Arranges a consolidate-on-add feature-delta + a real git repo with a net test-LOC delta
    on tmp_path, and (where the scenario supplies one) a declared add-only baseline LOC, runs
    `--require-sustainability --with-metrics --add-only-baseline-loc=<N>` as a real
    subprocess, and exposes the closed verdict token + the `metrics` evidence object + the
    `consolidate_on_add` cross-check verdict + the `consolidate_on_add_gain_loc` cell + exit
    code for assertion.
    """

    def __init__(self) -> None:
        self._delta_path: Path | None = None
        self._workdir: Path | None = None
        self._add_only_baseline_loc: int | None = None
        # The DISCRIMINATING SIGNAL (option B): an explicit consolidate-on-add MODE flag,
        # distinct from the `--add-only-baseline-loc` VALUE. Every slice-07 Given DECLARES
        # consolidate-on-add intent by setting this True, so the gate's coa-leg fires ONLY
        # on declared intent — never on slice-04's plain `--with-metrics` trend-check (which
        # never sets this flag). This is what dissolves the byte-identical collision: sc3
        # ("no baseline") now sends `--consolidate-on-add` WITHOUT a baseline value, a signal
        # the plain slice-04 accept-on-trend invocation can never carry.
        self._consolidate_on_add: bool = False
        self._result: CliResult | None = None

    # -- arrange (Given) -----------------------------------------------------

    def given_add_and_improve_below_baseline(self, tmp_path: Path) -> None:
        """A slice that ADDED scope AND consolidated, netting BELOW the add-only baseline.

        The happy/realized path: the run's net test-LOC (a modest add minus the
        consolidation) is below the declared add-only baseline (a pure-add of the same
        scope), so the consolidate-on-add gain ≤ 0 and the gate accepts on trend.
        """
        self._init_git_repo(tmp_path)
        self._commit_baseline_test_loc(tmp_path, lines=100)
        # add-AND-improve: net working tree = 70 lines (added a slice, consolidated more
        # than the addition), so net delta = -30 vs the committed baseline.
        self._set_test_loc(tmp_path, lines=70)
        # the add-only baseline for the same added scope would have netted +40.
        self._add_only_baseline_loc = 40
        # DECLARE consolidate-on-add intent — the discriminating MODE flag (option B).
        self._consolidate_on_add = True
        self._write_delta(
            tmp_path, _delta_with_section(_consolidate_section("CONSOLIDATE"))
        )

    def given_declares_add_and_improve_but_only_added(self, tmp_path: Path) -> None:
        """A section CLAIMING consolidate-on-add but the run only ADDED (gain > baseline).

        The masquerade path: the section declares CONSOLIDATE but the run's net test-LOC is
        NOT below the add-only baseline (it merely added), so the add-AND-improve claim is
        unmasked as `not-realized` → top-level `consolidate-on-add-not-realized`.
        """
        self._init_git_repo(tmp_path)
        self._commit_baseline_test_loc(tmp_path, lines=50)
        # net working tree = 130 lines: a pure add of +80, no consolidation.
        self._set_test_loc(tmp_path, lines=130)
        # the add-only baseline for the same added scope is also +80 — the run did NOT beat
        # it, so the declared consolidate-on-add was not realized.
        self._add_only_baseline_loc = 80
        # DECLARE consolidate-on-add intent — the discriminating MODE flag (option B); the
        # coa-leg fires and unmasks the add-only masquerade.
        self._consolidate_on_add = True
        self._write_delta(
            tmp_path, _delta_with_section(_consolidate_section("CONSOLIDATE"))
        )

    def given_consolidate_on_add_without_baseline(self, tmp_path: Path) -> None:
        """A consolidate-on-add MODE run with NO add-only baseline supplied — indeterminate.

        DDD-4 / DDD-10 degrade-LOUD: the add-only baseline is the denominator of the
        consolidate-on-add gain; with no baseline the gain cannot be computed, so the leg
        must return INDETERMINATE (exit non-zero), NEVER a fabricated realized.

        DISCRIMINATOR (the design-defect FIX, option B): this run DECLARES consolidate-on-add
        intent via the explicit `--consolidate-on-add` MODE flag (`_consolidate_on_add = True`)
        while withholding the `--add-only-baseline-loc` VALUE. That mode flag is the signal
        that pries this scenario apart from the SHIPPED slice-04 accept-on-trend AT: slice-04
        sends plain `--with-metrics` (NO `--consolidate-on-add`) with no baseline and is
        ACCEPTED on trend; sc3 sends `--consolidate-on-add` with no baseline and is rejected
        INDETERMINATE. The two are no longer byte-identical CLI invocations demanding opposite
        exit codes — the gate routes on the presence of the coa MODE flag, so a non-regressing
        plain trend-check (slice-04) and a coa-intent-declared-without-denominator (sc3) are
        mechanically distinguishable. No production code is asked to return both 0 and non-0
        for identical input.
        """
        self._init_git_repo(tmp_path)
        self._commit_baseline_test_loc(tmp_path, lines=60)
        self._set_test_loc(tmp_path, lines=45)
        # DECLARE consolidate-on-add intent (the discriminating MODE flag) ...
        self._consolidate_on_add = True
        # ... but deliberately WITHHOLD the `--add-only-baseline-loc` VALUE — no denominator,
        # so the coa-leg must degrade LOUD to INDETERMINATE (NOT fall back to the slice-04
        # plain-trend accept, which is reachable only WITHOUT the coa mode flag).
        self._add_only_baseline_loc = None
        self._write_delta(tmp_path, _delta_with_section(_consolidate_section("REUSE")))

    def given_metrics_on_section_without_evidence(self, tmp_path: Path) -> None:
        """A malformed path: consolidate-on-add requested on a section with no rows.

        The section omits the metrics-bearing rows entirely (heading only), so the
        consolidate-on-add evidence cannot be computed — a closed malformed-section error,
        not a silent zero gain.
        """
        self._init_git_repo(tmp_path)
        self._commit_baseline_test_loc(tmp_path, lines=20)
        self._set_test_loc(tmp_path, lines=20)
        self._add_only_baseline_loc = 10
        # DECLARE consolidate-on-add intent — the discriminating MODE flag (option B); the
        # evidence is missing, so the coa-leg short-circuits to the malformed-section error.
        self._consolidate_on_add = True
        body = (
            "# Feature Delta: slice-07 fixture\n\n"
            "## Wave: DISTILL / [REF] Test Reuse & Consolidation Analysis\n\n"
            f"{CANONICAL_SECTION_HEADING}\n\n(no rows — evidence cannot be supplied)\n"
        )
        self._write_delta(tmp_path, body)

    # -- act (When) ----------------------------------------------------------

    def when_consolidate_on_add_check_runs(self) -> None:
        assert self._delta_path is not None, "no feature-delta was arranged"
        args = ["--require-sustainability", "--with-metrics"]
        # The DISCRIMINATING MODE flag (option B) — emitted by EVERY slice-07 scenario that
        # declares consolidate-on-add intent. Its PRESENCE is what activates the coa-leg; its
        # ABSENCE is exactly the SHIPPED slice-04 plain `--with-metrics` accept-on-trend path.
        # This is the signal that dissolves the byte-identical collision with slice-04: sc3
        # (no baseline) now carries `--consolidate-on-add`, which slice-04's accept invocation
        # never does, so the gate can route them to opposite exit codes from DISTINCT inputs.
        if self._consolidate_on_add:
            args.append("--consolidate-on-add")
        # The add-only baseline VALUE is a SEPARATE argument from the MODE flag: a coa run can
        # declare intent (mode flag) yet withhold the baseline (sc3) → INDETERMINATE.
        if self._add_only_baseline_loc is not None:
            args.append(f"--add-only-baseline-loc={self._add_only_baseline_loc}")
        args += ["--format=json", str(self._delta_path)]
        self._result = _run(args)

    # -- assert (Then) -------------------------------------------------------

    def then_accepts(self) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert result.exit_code == 0, (
            "an accepted consolidate-on-add section must exit 0; "
            f"got exit {result.exit_code}, {payload!r}"
        )

    def then_rejects(self) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert result.exit_code != 0, (
            "a rejected/indeterminate consolidate-on-add check must exit non-zero; "
            f"got exit {result.exit_code}, {payload!r}"
        )

    def then_verdict_is(self, expected: Verdict) -> None:
        result = self._require_result()
        payload = result.verdict_payload()
        assert payload["verdict"] == expected.value, (
            f"the consolidate-on-add gate must emit the {expected.value!r} verdict for "
            f"this feature-delta; got {payload!r} (exit {result.exit_code})"
        )

    def then_reports_consolidate_on_add_gain(self) -> None:
        """The `metrics` object carries the consolidate-on-add gain evidence cell."""
        metrics = self._require_result().metrics_payload()
        assert "consolidate_on_add_gain_loc" in metrics, (
            "the metrics evidence must carry the `consolidate_on_add_gain_loc` cell "
            "(the consolidating run's net test-LOC minus the add-only baseline); "
            f"got {metrics!r}"
        )

    def then_consolidate_on_add_gain_is_non_positive(self) -> None:
        """The numeric invariant: the consolidate-on-add gain ≤ 0 (curve bent vs add-only)."""
        metrics = self._require_result().metrics_payload()
        gain = metrics.get("consolidate_on_add_gain_loc")
        assert isinstance(gain, (int, float)) and gain <= 0, (
            "a realized add-AND-improve slice must net BELOW the add-only baseline, so the "
            f"consolidate-on-add gain must be ≤ 0 (the counter-gradient); got {gain!r} in "
            f"{metrics!r}"
        )

    def then_consolidate_on_add_cross_check_is(
        self, expected: ConsolidateOnAddVerdict
    ) -> None:
        """The add-AND-improve leg reports the expected closed cross-check verdict."""
        coa = self._require_result().consolidate_on_add_payload()
        assert coa.get("verdict") == expected.value, (
            f"the consolidate-on-add cross-check must report {expected.value!r} for this "
            f"run vs its add-only baseline; got {coa!r}"
        )

    # -- internals -----------------------------------------------------------

    def _write_delta(self, tmp_path: Path, body: str) -> None:
        workdir = self._workdir or tmp_path
        path = workdir / "feature-delta.md"
        path.write_text(body, encoding="utf-8")
        self._delta_path = path

    def _init_git_repo(self, tmp_path: Path) -> None:
        self._workdir = tmp_path
        subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
        subprocess.run(
            ["git", "config", "user.email", "slice07@test.local"],
            cwd=str(tmp_path),
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "slice07"], cwd=str(tmp_path), check=True
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

    def _set_test_loc(self, tmp_path: Path, *, lines: int) -> None:
        """Set the working-tree test-LOC; the git diff yields net = lines - baseline."""
        f = self._test_file(tmp_path)
        f.write_text("\n".join(f"# test line {i}" for i in range(lines)) + "\n")

    def _require_result(self) -> CliResult:
        assert self._result is not None, "the consolidate-on-add check was not run"
        return self._result
