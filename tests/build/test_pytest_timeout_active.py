"""Regression AT for issue #19: pytest-timeout must be installed and armed.

Today a hanging test (infinite loop / deadlock / stuck subprocess) blocks the
pytest run forever with no failure -- it silently stalls CI. Adding the
pytest-timeout plugin with a generous global per-test cap turns such a hang
into a `Failed: Timeout` after the cap instead of an indefinite stall.

Four properties pinned here:
1. The plugin is a declared dependency AND the project's pytest config
   ([tool.pytest.ini_options] in pyproject.toml) sets a `timeout`.
2. The plugin is ACTUALLY ACTIVE in a live pytest session -- queried
   in-process via `pytestconfig.pluginmanager` / `pytestconfig.getini(...)`,
   cross-checked against the SSOT pyproject.toml value. This is the
   load-independent mechanism-PRESENCE proof (#69, recurrence of #49): no
   subprocess, no timing, no race -- either the plugin is registered in
   THIS session's live config or it is not. It is also resistant to
   `-p no:timeout`: disabling the plugin makes the `timeout` ini key itself
   unknown, which pytest refuses to start with at all (see property 2's
   test docstring).
3. The mechanism actually interrupts a hanging test (proven by running a
   tiny inner pytest, in a subprocess, against a test marked
   `@pytest.mark.timeout(2)` that sleeps 60s). The proof is CONTENT-based,
   not timing-based (#69, recurrence of #49): pytest-timeout emits a fixed,
   distinctive failure message -- `Timeout (>Ns) from pytest-timeout.` --
   that appears in stdout if and only if the plugin actually fired. Under
   box load, subprocess/interpreter startup latency can stretch arbitrarily
   (that's what flaked the old "interrupted within 15s" wall-clock race
   twice); the content marker needs no wall-clock budget at all, so load can
   only ever make this test slower, never wrong. A loose corroborating
   elapsed-time sanity check remains, but its bound is proportional to the
   sleep duration itself (not an independent absolute constant), so it is
   for gross-hang detection only and is not the mechanism's proof.
4. The configured global cap is generous (>= 300s) -- a hang-catcher, not a
   speed-limiter. The slowest known test today is ~130s (BuildTier), so a
   600s cap leaves 4.6x margin. This guards against a future edit quietly
   tightening the cap and false-failing legitimate slow tests.

All assertions here are fast (test 3 costs ~2-4s under normal load,
interrupted well before its 60s inner sleep; the others are near-instant)
-- this file never sleeps for the global cap itself.
"""

import importlib.util
import re
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

# Inner-probe timeout/sleep: deliberately a huge gap (2s cap vs 60s sleep).
# The gap size no longer matters for correctness (property 3's proof is
# content-based, not timing-based -- see module docstring) but is kept wide
# so the loose corroborating elapsed-time sanity check stays meaningful.
INNER_PROBE_TIMEOUT_SECONDS = 2
INNER_PROBE_SLEEP_SECONDS = 60

# pytest-timeout's own failure message template (pytest_timeout.py:
# `PYTEST_FAILURE_MESSAGE = "Timeout (>%ss) from pytest-timeout."`). Matching
# this exact, distinctive string in the inner probe's stdout is the
# load-independent mechanism proof: it appears if and only if pytest-timeout
# actually interrupted the test, regardless of how long the interrupt took
# to fire. This constant is duplicated intentionally (not imported from the
# plugin) -- the AT proves the plugin's *observable behavior* via its own
# process boundary, not its internals.
TIMEOUT_FAILURE_MESSAGE_PATTERN = re.compile(
    r"Timeout \(>"
    + re.escape(str(float(INNER_PROBE_TIMEOUT_SECONDS)))
    + r"s\) from pytest-timeout\."
)

# Subprocess-level safety net: the inner probe must never be allowed to hang
# this AT itself, regardless of whether pytest-timeout is wired correctly.
# This is a coarse "don't literally hang forever" backstop now, not a race
# threshold (the mechanism proof no longer depends on timing) -- generous on
# purpose so no plausible load level can trip it on a healthy interrupt, yet
# still well under the 60s natural-completion sleep so a genuinely broken
# mechanism is caught in bounded time instead of stalling this AT for a
# full minute.
SUBPROCESS_SAFETY_NET_SECONDS = 45

# Loose corroborating sanity bound for the elapsed-time leg: proportional to
# the sleep duration (not an independent absolute constant), so tuning
# INNER_PROBE_SLEEP_SECONDS automatically rescales it. This only guards
# against the inner probe running to full natural completion (a gross
# "the mechanism did nothing at all" case) -- the primary proof is the
# content marker above, so this bound can stay generous without weakening
# the test.
INTERRUPTED_WELL_BEFORE_NATURAL_COMPLETION_SECONDS = INNER_PROBE_SLEEP_SECONDS * 0.9


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


def test_pytest_timeout_plugin_active_in_live_pytest_session(pytestconfig) -> None:
    """Mechanism-PRESENCE proof (#69, recurrence of #49): query the CURRENT,
    live pytest session's plugin manager and ini config -- not a static
    import check, not a subprocess, no timing of any kind. Either the
    "timeout" plugin is registered in this real session or it is not; this
    can never flake under box load because it measures nothing that takes
    time.

    Resistant to `-p no:timeout`: the `timeout` ini key is registered by the
    plugin's own `pytest_addoption` hook. Disable the plugin and pytest
    refuses to even start ("ERROR: Unknown config option: timeout") because
    pyproject.toml still declares it -- so a disabled plugin fails the whole
    run louder than this test ever could, and this test still correctly
    fails (or never gets the chance to pass) either way.

    Cross-checks the live value against the SSOT pyproject.toml value so a
    stale cached config can never silently diverge from the file on disk.
    """
    plugin_manager = pytestconfig.pluginmanager
    assert plugin_manager.has_plugin("timeout"), (
        "pytest-timeout is not an active plugin in this live pytest "
        "session (pluginmanager.has_plugin('timeout') is False). It may be "
        "installed but disabled (e.g. via `-p no:timeout`), or not "
        "registered at all -- either way hanging tests would not be "
        "interrupted in this actual run (#19)."
    )

    live_timeout = pytestconfig.getini("timeout")
    ssot_timeout = _load_pytest_ini_options().get("timeout")
    assert live_timeout not in (None, ""), (
        "pytestconfig.getini('timeout') returned no value in this live "
        "session even though the plugin is registered -- the global "
        "per-test cap is not actually armed for this run."
    )
    assert float(live_timeout) == float(ssot_timeout), (
        f"Live session timeout ({live_timeout!r}) does not match the SSOT "
        f"pyproject.toml [tool.pytest.ini_options] timeout ({ssot_timeout!r}). "
        "The running session's config has drifted from the file on disk."
    )


def test_pytest_timeout_kills_hanging_test_as_failure() -> None:
    """Mechanism proof: a test marked `@pytest.mark.timeout(2)` that sleeps
    60s must be interrupted and reported as a Timeout FAILURE, not a pass and
    not an indefinite hang. Run in an isolated inner pytest (subprocess,
    tmp_path rootdir with no inherited pyproject.toml) so this proves the
    plugin's own interrupt mechanism, not the project's global config.

    The proof is CONTENT-based (#69, recurrence of #49): pytest-timeout
    emits a fixed, distinctive failure message -- `Timeout (>Ns) from
    pytest-timeout.` -- that can only appear if the plugin actually fired.
    No wall-clock race is needed to establish that, so box load cannot flake
    this assertion. A loose, proportional elapsed-time bound remains as a
    coarse corroborating sanity check only."""
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
    # PRIMARY proof, content-based and load-independent: pytest-timeout's
    # own fixed failure message can only appear in stdout if the plugin
    # actually intervened. This needs no wall-clock budget, so however slow
    # subprocess/interpreter startup gets under box load, this assertion
    # cannot flake -- it is a text match, not a race (#69, recurrence of
    # #49, where a tight elapsed-time threshold flaked under load).
    assert TIMEOUT_FAILURE_MESSAGE_PATTERN.search(result.stdout), (
        f"Inner probe's stdout does not contain pytest-timeout's own "
        f"failure marker ('Timeout (>{float(INNER_PROBE_TIMEOUT_SECONDS)}s) "
        "from pytest-timeout.'). The test failed for some OTHER reason "
        "than a timeout interrupt -- this does not prove the hang-catcher "
        f"mechanism fired.\nstdout:\n{result.stdout}"
    )
    # Loose corroborating sanity check only (not the proof): the probe
    # returned well before the sleep's full natural-completion duration.
    # The bound is proportional to INNER_PROBE_SLEEP_SECONDS itself (not an
    # independent absolute constant), so it only rules out the gross case
    # of "the mechanism did nothing and the sleep ran to completion" --
    # heavy load can only push elapsed_seconds up, never down, and this
    # bound has enough headroom (90% of the sleep) that no plausible
    # startup/scheduling delay reaches it while a genuine non-interrupt
    # (>= 100% of the sleep) still trips it.
    assert elapsed_seconds < INTERRUPTED_WELL_BEFORE_NATURAL_COMPLETION_SECONDS, (
        f"Inner probe took {elapsed_seconds:.2f}s, which is at or beyond "
        f"{INTERRUPTED_WELL_BEFORE_NATURAL_COMPLETION_SECONDS:.1f}s (90% of "
        f"the {INNER_PROBE_SLEEP_SECONDS}s natural-completion sleep). This "
        "suggests the test ran to (near) completion instead of being "
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
