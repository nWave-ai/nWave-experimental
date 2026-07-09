"""Regression AT for issue #19: pytest-timeout must be installed and armed.

Today a hanging test (infinite loop / deadlock / stuck subprocess) blocks the
pytest run forever with no failure -- it silently stalls CI. Adding the
pytest-timeout plugin with a generous global per-test cap turns such a hang
into a `Failed: Timeout` after the cap instead of an indefinite stall.

Three properties pinned here:
1. The plugin is a declared dependency AND the project's pytest config
   ([tool.pytest.ini_options] in pyproject.toml) sets a `timeout`.
2. The mechanism actually interrupts a hanging test (proven by running a
   tiny inner pytest, in a subprocess, against a test marked
   `@pytest.mark.timeout(2)` that sleeps 60s -- it must report a Timeout
   failure, not a pass). The 2s-cap-vs-60s-sleep gap is deliberately huge
   (not 1s-vs-2s) so the "interrupted early" assertion has a wide,
   load-tolerant margin instead of racing subprocess startup overhead.
3. The configured global cap is generous (>= 300s) -- a hang-catcher, not a
   speed-limiter. The slowest known test today is ~130s (BuildTier), so a
   600s cap leaves 4.6x margin. This guards against a future edit quietly
   tightening the cap and false-failing legitimate slow tests.

All assertions here are fast (test 2 costs ~2-4s, interrupted well before
its 60s inner sleep; the others are near-instant) -- this file never sleeps
for the global cap itself.
"""

import importlib.util
import subprocess
import sys
import time
from pathlib import Path


try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


PYPROJECT_PATH = Path(__file__).parent.parent.parent / "pyproject.toml"

# Slowest known test today is ~130s (BuildTier); require >= 4x margin.
MINIMUM_GENEROUS_CAP_SECONDS = 300

# Inner-probe timeout/sleep: deliberately a HUGE gap (2s cap vs 60s sleep),
# not a tight 1s-vs-2s race. A tight gap flakes under build-tier load because
# inner-pytest startup overhead alone can eat the whole margin (#49). With a
# 60s sleep, "interrupted early" vs "ran to completion" is unmistakable even
# under heavy parallel load.
INNER_PROBE_TIMEOUT_SECONDS = 2
INNER_PROBE_SLEEP_SECONDS = 60

# Subprocess-level safety net: the inner probe must never be allowed to hang
# this AT itself, regardless of whether pytest-timeout is wired correctly.
# Comfortably above the "interrupted early" threshold (below) and well
# below the 60s natural-completion sleep, so a broken mechanism still fails
# fast via TimeoutExpired instead of blocking the outer test for 60s.
SUBPROCESS_SAFETY_NET_SECONDS = 20

# "Interrupted early" threshold for the elapsed-time assertion: a real
# interrupt lands around INNER_PROBE_TIMEOUT_SECONDS (+ startup/scheduling
# overhead, even under heavy load); natural completion is 60s. 15s cleanly
# separates the two without racing subprocess startup cost.
INTERRUPTED_EARLY_THRESHOLD_SECONDS = 15


def _load_pytest_ini_options() -> dict:
    with open(PYPROJECT_PATH, "rb") as f:
        data = tomllib.load(f)
    return data["tool"]["pytest"]["ini_options"]


def test_pytest_timeout_plugin_is_declared_and_configured() -> None:
    """pytest-timeout must be importable AND the project must set `timeout`
    in [tool.pytest.ini_options]. Uses find_spec (not a bare import) so a
    missing plugin surfaces as a semantic AssertionError, not a collection
    error on this test's own imports."""
    assert importlib.util.find_spec("pytest_timeout") is not None, (
        "pytest-timeout is not installed. Add it as a dependency "
        "(pyproject.toml [dependency-groups] dev) so hanging tests fail "
        "loudly instead of stalling the suite forever (#19)."
    )
    config = _load_pytest_ini_options()
    assert "timeout" in config, (
        "pyproject.toml [tool.pytest.ini_options] is missing a `timeout` "
        "key. Without it pytest-timeout (once installed) has no global "
        "per-test cap and a hanging test still blocks the suite forever."
    )


def test_pytest_timeout_kills_hanging_test_as_failure() -> None:
    """Mechanism proof: a test marked `@pytest.mark.timeout(2)` that sleeps
    60s must be interrupted and reported as a Timeout FAILURE, not a pass and
    not an indefinite hang. Run in an isolated inner pytest (subprocess,
    tmp_path rootdir with no inherited pyproject.toml) so this proves the
    plugin's own interrupt mechanism, not the project's global config.

    Margins are deliberately wide (2s cap vs 60s sleep, <15s "interrupted
    early" threshold) so this stays robust under build-tier parallel load
    instead of racing subprocess startup overhead (#49)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        inner_test_file = tmp_path / "test_inner_hang_probe.py"
        inner_test_file.write_text(
            "import time\n"
            "import pytest\n"
            "\n"
            f"@pytest.mark.timeout({INNER_PROBE_TIMEOUT_SECONDS})\n"
            "def test_hangs():\n"
            f"    time.sleep({INNER_PROBE_SLEEP_SECONDS})\n"
        )

        started_at = time.monotonic()
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(inner_test_file), "-q", "--no-header"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_SAFETY_NET_SECONDS,
        )
        elapsed_seconds = time.monotonic() - started_at

    assert result.returncode != 0, (
        f"Inner probe test (@pytest.mark.timeout({INNER_PROBE_TIMEOUT_SECONDS}), "
        f"sleeps {INNER_PROBE_SLEEP_SECONDS}s) did not fail. Without "
        "pytest-timeout wired, the marker is unrecognized and the test just "
        "sleeps to completion and passes -- proving the hang-interrupt "
        "mechanism is not active.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "1 failed" in result.stdout, (
        "Expected the inner probe's summary to report '1 failed' (a "
        "Timeout failure), got:\n"
        f"{result.stdout}"
    )
    # If the plugin actually interrupted the sleep, the subprocess returns
    # well before the full 60s sleep completes naturally. The threshold is
    # a huge margin above the real interrupt point (~2-4s even under heavy
    # load) and far below natural completion (60s), so it cleanly separates
    # "interrupted" from "ran to completion" without flaking on startup
    # overhead (#49).
    assert elapsed_seconds < INTERRUPTED_EARLY_THRESHOLD_SECONDS, (
        f"Inner probe took {elapsed_seconds:.2f}s -- expected it to be "
        f"interrupted around {INNER_PROBE_TIMEOUT_SECONDS}s (well under the "
        f"{INTERRUPTED_EARLY_THRESHOLD_SECONDS}s threshold), long before "
        f"the full {INNER_PROBE_SLEEP_SECONDS}s sleep naturally completes. "
        "This suggests the test ran to completion instead of being "
        "interrupted by pytest-timeout."
    )


def test_pytest_timeout_global_cap_is_generous() -> None:
    """The configured global cap must be a hang-catcher, not a
    speed-limiter -- guards against a future edit quietly tightening it and
    false-failing legitimate slow tests (slowest known today ~130s
    BuildTier)."""
    config = _load_pytest_ini_options()
    assert "timeout" in config, (
        "pyproject.toml [tool.pytest.ini_options] is missing a `timeout` "
        "key -- cannot assert its generosity until it exists."
    )
    timeout_value = config["timeout"]
    assert isinstance(timeout_value, (int, float)), (
        f"`timeout` must be numeric (seconds), got {timeout_value!r} "
        f"({type(timeout_value).__name__})."
    )
    assert timeout_value >= MINIMUM_GENEROUS_CAP_SECONDS, (
        f"Configured timeout={timeout_value}s is tighter than the "
        f"{MINIMUM_GENEROUS_CAP_SECONDS}s floor. The slowest known test "
        "today is ~130s (BuildTier); a too-tight cap will false-fail "
        "legitimate slow tests instead of only catching true hangs."
    )
