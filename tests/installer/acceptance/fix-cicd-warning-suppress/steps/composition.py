"""Composition root for slice-01 (pytest-warning-filter) of fix-cicd-warning-suppress.

Wires a REAL `uv run pytest <known-noisy-file> --collect-only -q`
subprocess (Layer 3 driving port per Mandate-13) and captures the combined
stdout+stderr output for two universe-bound observations:

  1. ZERO occurrences of the literal substring "PytestUnknownMarkWarning"
     in the captured output (AT-1 absent-warnings contract).
  2. Captured-output line count ≤ 20% of the pre-fix baseline AND ≤ 15
     lines absolute (AT-2 bounded-output-size contract — proxy for the
     BlockingIOError root cause in friction #14).

The only driven ports are:
  - the real subprocess (`uv run pytest <file> --collect-only -q`),
  - the real filesystem (the known-noisy file exists at a fixed repo path),
  - the real `pyproject.toml` (the production fix lives there; the SUT
    reads it implicitly via pytest's own startup).

Business logic — subprocess construction, output capture, baseline line-
count constant, warning-substring search — lives here as the single source
of truth; step bodies delegate to `WarningFilterFixture` methods and never
inline logic (Mandate-12 criterion 3, ≤2 statements per step body).

RED-for-the-right-reason: the production fix
(`pyproject.toml[tool.pytest.ini_options].filterwarnings` entry) does NOT
EXIST YET (it lands in DELIVER per the feature-delta `Wave: DELIVER
(pending)` ordering; slice-01 authors ATs + composition only). When
`run_collect_only_on_known_noisy_file()` invokes the real pytest
subprocess, the captured stdout contains 9 `PytestUnknownMarkWarning`
occurrences (empirically measured 2026-05-28 at DISTILL time) and the
total line count is 46. The fixture surfaces this as `AssertionError` on
the first `Then` step (`assert_zero_unknown_mark_warnings_in_output` for
AT-1; `assert_output_volume_reduction_at_least_eighty_percent_vs_baseline`
for AT-2). That is the correct RED: the assertion fires because the
warnings filter is unimplemented, not because of an import error or
fixture setup bug.

Pre-fix baseline (empirically measured 2026-05-28 against
tests/installer/acceptance/atdd-spine-ledger-enforcement-gate-v2/steps/
test_slice_02_pre_tool_use_hook.py with `uv run pytest <file>
--collect-only -q`):

  - PytestUnknownMarkWarning occurrences: 9
  - Combined stdout+stderr line count: 46
  - 80% reduction target: ≤ 10 lines (the AT uses ≤ 15 as a conservative
    bound to account for pytest version drift on the unrelated boilerplate
    header/footer lines).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


# Repo root: tests/installer/acceptance/<feature>/steps/composition.py -> up five levels.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# The known-noisy target file. Empirically chosen 2026-05-28: this file
# carries 3 pytest-bdd scenarios with 9 unique unregistered custom marks
# (slice-02, walking_skeleton, driving_port, real-io, contract-shape:*,
# fast-path, matcher-collision-spike, feature-atdd-spine-ledger-...).
_KNOWN_NOISY_FILE_RELPATH = Path(
    "tests/installer/acceptance/atdd-spine-ledger-enforcement-gate-v2/"
    "steps/test_slice_02_pre_tool_use_hook.py"
)

# Pre-fix baseline (empirically measured 2026-05-28 at DISTILL time, see
# module docstring). Both fields are constants the AT can refer to without
# re-measuring at run time.
_PRE_FIX_BASELINE_LINE_COUNT = 46
_PRE_FIX_BASELINE_WARNING_COUNT = 9

# Post-fix bounds (per AT-2 contract).
_POST_FIX_MAX_LINE_COUNT = 15
_POST_FIX_LINE_COUNT_RATIO_OF_BASELINE = 0.20

# The substring whose absence in captured output is the AT-1 contract.
_UNKNOWN_MARK_WARNING_SUBSTRING = "PytestUnknownMarkWarning"


@dataclass(frozen=True)
class PytestRunCapture:
    """One captured invocation of `uv run pytest <file> --collect-only -q`.

    The `combined_output` field holds stdout+stderr merged in the order the
    subprocess wrote them — that is the surface the developer sees in the
    pre-push terminal and the surface that fills the pipe buffer in
    friction #14. The two derived properties expose the universe-bound
    observables (warning-substring count + line count).
    """

    exit_code: int
    combined_output: str
    target_file: Path

    @property
    def unknown_mark_warning_count(self) -> int:
        """Count occurrences of the literal substring "PytestUnknownMarkWarning"."""
        return self.combined_output.count(_UNKNOWN_MARK_WARNING_SUBSTRING)

    @property
    def line_count(self) -> int:
        """Count non-empty lines in the combined output."""
        return sum(1 for line in self.combined_output.splitlines() if line.strip())


class WarningFilterFixture:
    """Drives a real `uv run pytest <known-noisy-file> --collect-only -q`
    subprocess and exposes universe-bound observations of the captured output.

    Each instance is bound to one isolated `tmp_path` workspace (the fixture
    does not need to write into the workspace — the SUT reads the known-
    noisy file from the repo at its fixed path — but the tmp_path is held
    for future per-AT state isolation if the contract grows).

    The fixture exposes composition methods that step bodies invoke; no
    business logic is inlined in any step.
    """

    def __init__(self, target_root: Path) -> None:
        self._target_root = target_root
        self._target_root.mkdir(parents=True, exist_ok=True)
        self._known_noisy_file = _REPO_ROOT / _KNOWN_NOISY_FILE_RELPATH

    # ---- Precondition setup (Given step delegates) ----

    def assert_known_noisy_file_exists(self) -> None:
        """Assert the known-noisy pytest-bdd file exists at its fixed repo path.

        Defensive precondition: if the slice-02 test file has been moved or
        renamed since slice-01 DISTILL time, the AT surfaces this clearly
        rather than failing later with a confusing pytest collection error.
        """
        assert self._known_noisy_file.exists(), (
            f"Known-noisy target file not found at expected path: "
            f"{self._known_noisy_file!s}. The AT relies on this fixed-path "
            f"reference for the empirical baseline; if the slice-02 test "
            f"file was moved, update _KNOWN_NOISY_FILE_RELPATH in this "
            f"composition module."
        )

    def acknowledge_known_custom_mark_namespace(self) -> None:
        """Document the known custom mark namespace covered by the contract.

        No-op composition method: the namespace itself lives in the Gherkin
        Background as the human-readable enumeration; the SUT's filter
        configuration in pyproject.toml is what mechanically suppresses
        them. This step exists so the Gherkin reads as a business
        precondition (Pillar 1).
        """
        # No filesystem state to seed; this step exists for Pillar 1 readability.

    def acknowledge_pytest_bdd_tag_conversion(self) -> None:
        """Document that pytest-bdd auto-converts each Gherkin tag to a mark.

        No-op composition method: the auto-conversion is a pytest-bdd
        runtime behaviour (`pytest_bdd/plugin.py:137 mark = getattr(
        pytest.mark, tag)`); the AT does not need to seed anything for it.
        This step exists so the Gherkin reads as a business precondition
        (Pillar 1).
        """
        # No filesystem state to seed; this step exists for Pillar 1 readability.

    def acknowledge_production_filter_declared_in_pyproject(self) -> None:
        """Document the production fix surface: pyproject.toml filterwarnings.

        No-op composition method: the SUT (pytest subprocess) reads the
        project's pyproject.toml at startup and applies the filterwarnings
        entries; the AT does not need to read or assert on the
        pyproject.toml file directly. The empirical contract is observed
        on the captured pytest output, not on the configuration file.
        This step exists so the Gherkin reads as a business precondition
        (Pillar 1) AND so the DELIVER scope is unambiguously named.
        """
        # No filesystem state to seed; this step exists for Pillar 1 readability.

    # ---- Action (When step delegates) ----

    def run_collect_only_on_known_noisy_file(self) -> PytestRunCapture:
        """Invoke `uv run pytest <known-noisy-file> --collect-only -q` as
        a real subprocess from the repo root and capture combined output.

        Combines stdout + stderr into one stream (mirrors what the pre-push
        terminal sees and what fills the pipe buffer in friction #14). The
        subprocess timeout is 60s — generous because `uv run` can take
        ~5-10s to resolve the virtualenv on cold cache.
        """
        completed = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                str(self._known_noisy_file),
                "--collect-only",
                "-q",
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        # Merge stdout + stderr in the order subprocess.run made them
        # available — both streams contribute to the pipe-buffer fill in
        # friction #14, so the AT observes the union.
        combined = (completed.stdout or "") + (completed.stderr or "")
        return PytestRunCapture(
            exit_code=completed.returncode,
            combined_output=combined,
            target_file=self._known_noisy_file,
        )

    # ---- Observation (Then step delegates) ----

    def assert_zero_unknown_mark_warnings_in_output(
        self, capture: PytestRunCapture
    ) -> None:
        """Assert the captured output contains ZERO `PytestUnknownMarkWarning`.

        Universe-bound (Mandate 8): the universe is the set of warning
        classes pytest emits on the captured output; the contract names
        ONE class (`PytestUnknownMarkWarning`) and requires zero
        occurrences. Other warning classes (DeprecationWarning,
        UserWarning from hypothesis, etc.) remain UNCHANGED — the filter
        targets only the unknown-mark class.

        Surfaces a clear AssertionError when the production fix is absent
        (pre-fix: 9 occurrences on the slice-02 target file). That is the
        RED-for-right-reason for AT-1.
        """
        actual = capture.unknown_mark_warning_count
        assert actual == 0, (
            f"Expected ZERO occurrences of {_UNKNOWN_MARK_WARNING_SUBSTRING!r} "
            f"in the captured pytest output for {capture.target_file!s}; "
            f"got {actual} (pre-fix baseline at DISTILL time: "
            f"{_PRE_FIX_BASELINE_WARNING_COUNT}). The production fix in "
            f"pyproject.toml[tool.pytest.ini_options].filterwarnings is "
            f"either absent or misconfigured.\n"
            f"---captured output (first 2000 chars)---\n"
            f"{capture.combined_output[:2000]}"
        )

    def assert_pytest_exit_code_zero(self, capture: PytestRunCapture) -> None:
        """Assert the pytest subprocess exited 0 (collection succeeded).

        Defensive: if pytest itself fails (e.g. pyproject.toml parse error
        introduced by the production fix), exit code surfaces it clearly.
        """
        assert capture.exit_code == 0, (
            f"Expected pytest collection to exit 0; got {capture.exit_code}. "
            f"This indicates pytest itself failed (likely a pyproject.toml "
            f"misconfiguration introduced by the production fix).\n"
            f"---captured output (first 2000 chars)---\n"
            f"{capture.combined_output[:2000]}"
        )

    def assert_no_warning_surfaced_for_known_namespace(
        self, capture: PytestRunCapture
    ) -> None:
        """Assert no per-tag warning lines surface for the known custom marks.

        Stronger form of `assert_zero_unknown_mark_warnings_in_output`:
        for each known custom mark substring, asserts the captured output
        contains NO line matching the pytest warning shape
        ("Unknown pytest.mark.<tag>"). This catches the edge case where
        the filter suppresses the class label but not the individual
        warning records.
        """
        known_tags = [
            "slice-01",
            "slice-02",
            "walking_skeleton",
            "driving_port",
            "real-io",
            "e2e_smoke",
            "fast-path",
            "matcher-collision-spike",
            "contract-shape",
            "feature-",
            "coupled",
            "infrastructure",
            "partial-failure-tolerance",
        ]
        offending = [
            tag
            for tag in known_tags
            if f"Unknown pytest.mark.{tag}" in capture.combined_output
        ]
        assert offending == [], (
            f"Expected ZERO per-tag warning lines for the known custom mark "
            f"namespace; got warnings for: {offending!r}.\n"
            f"---captured output (first 2000 chars)---\n"
            f"{capture.combined_output[:2000]}"
        )

    def assert_output_volume_reduction_at_least_eighty_percent_vs_baseline(
        self, capture: PytestRunCapture
    ) -> None:
        """Assert post-fix line count ≤ 20% of the pre-fix baseline.

        Universe-bound (Mandate 8): the universe is the captured-output
        line count on the SAME pytest invocation against the SAME target
        file; the contract requires the post-fix value to be at most 20%
        of the pre-fix baseline measured at DISTILL time.

        This is the proxy observable for the BlockingIOError root cause
        in friction #14: reducing line volume below the pipe-buffer-fill
        threshold eliminates the stdout-drain race condition that surfaced
        empirically on slice-04 pre-push 2026-05-28.

        Surfaces a clear AssertionError when the production fix is absent
        (pre-fix: 46 lines on the slice-02 target file). That is the
        RED-for-right-reason for AT-2.
        """
        actual = capture.line_count
        threshold = (
            _PRE_FIX_BASELINE_LINE_COUNT * _POST_FIX_LINE_COUNT_RATIO_OF_BASELINE
        )
        assert actual <= threshold, (
            f"Expected captured output line count ≤ {threshold:.0f} "
            f"(20% of pre-fix baseline {_PRE_FIX_BASELINE_LINE_COUNT}); "
            f"got {actual}. The warnings filter in pyproject.toml is "
            f"either absent or insufficiently broad to suppress the "
            f"PytestUnknownMarkWarning volume.\n"
            f"---captured output (first 2000 chars)---\n"
            f"{capture.combined_output[:2000]}"
        )

    def assert_output_line_count_at_most_fifteen(
        self, capture: PytestRunCapture
    ) -> None:
        """Assert post-fix line count ≤ 15 absolute (defensive secondary bound).

        The 80%-reduction ratio bound (above) is the primary contract; this
        absolute bound is a defensive secondary check in case the pre-fix
        baseline drifts on subsequent pytest version upgrades (the
        boilerplate header/footer line count may grow). 15 lines is
        comfortably above the ~6-8 lines the post-fix output should carry
        (3 collected items + 1 result line + 2-3 pytest header lines).
        """
        actual = capture.line_count
        assert actual <= _POST_FIX_MAX_LINE_COUNT, (
            f"Expected captured output line count ≤ {_POST_FIX_MAX_LINE_COUNT} "
            f"(absolute bound); got {actual}. The warnings filter in "
            f"pyproject.toml is either absent or insufficiently broad.\n"
            f"---captured output (first 2000 chars)---\n"
            f"{capture.combined_output[:2000]}"
        )
