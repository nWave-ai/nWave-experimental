"""Regression: ``des verify-catalog-coherence`` crashes with a NAKED Python
traceback when run from a directory that is NOT an nWave-dev source checkout.

Charter: docs/product/expectations/fix-catalog-coherence-loud-outside-checkout/
         verify-catalog-coherence-explains-itself-outside-a-checkout.md

Root cause (measured 2026-07-18): ``src/des/cli/verify_catalog_coherence.py``
``_parse_registry_names(repo_root)`` (~line 103) does
``(<repo_root>/src/des/cli/__main__.py).read_text(...)`` and lets a bare
``FileNotFoundError`` propagate all the way to the top of ``main()`` -- no
what/why/how message. Two defects folded into one bug: (1) a NAKED TRACEBACK
(violates the standing every-failure-explains-what-why-how + ZERO-DEFECTS
mandates); (2) TARGET-AGNOSTICISM -- ``src/des/cli/__main__.py`` is
nWave-dev's OWN source layout, hardcoded into a gate meant to run on
arbitrary repos.

Driving surface (Mandate-13/16 driving-port-only): the REAL ``des
verify-catalog-coherence`` CLI entry point, driven as a subprocess so the
test observes exactly what an operator's terminal would show (stdout +
stderr + exit code) -- the bug is literally about what leaks into that
surface, so a subprocess is the faithful driving port here (an in-process
capsys call cannot observe an uncaught exception the same way a real
process boundary does).

Runs the SOURCE ``des`` (``python -m des.cli``, ``PYTHONPATH`` pointed at
this repo's ``src/``) -- NOT the installed ``des`` binary -- so a crafter's
fix to ``src/des/cli/verify_catalog_coherence.py`` turns this test GREEN
without a reinstall step. ``NWAVE_FRESHNESS=skip`` bypasses the separate,
already-passing runtime-freshness gate (``des.runtime.freshness``) that
would otherwise intercept the invocation before it ever reaches the
catalog-coherence code under test -- that gate is a different, orthogonal
concern from the one this regression pins.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"

_TRACEBACK_MARKERS = (
    "Traceback (most recent call last)",
    "FileNotFoundError",
    "cli/__main__.py",
)

# Loose, stable relevance check for the positive guidance line -- deliberately
# NOT pinned to exact wording (the crafter owns the copy), only that the
# message is topically about the right thing.
_GUIDANCE_KEYWORDS = ("checkout", "nwave", "catalog", "repo")

_OUTSIDE_CHECKOUT_CASES = (
    "bare-empty-dir",
    "unrelated-project-dir",
    "repo-root-nonexistent",
    "repo-root-dot-explicit",
)


def _run_verify_catalog_coherence(
    cwd: Path, extra_args: list[str]
) -> subprocess.CompletedProcess[str]:
    """Drive the REAL SOURCE ``des verify-catalog-coherence`` CLI as a
    subprocess from ``cwd``, capturing stdout/stderr/returncode."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_SRC_ROOT)
    env["NWAVE_FRESHNESS"] = "skip"
    return subprocess.run(
        [sys.executable, "-m", "des.cli", "verify-catalog-coherence", *extra_args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _combined_output(proc: subprocess.CompletedProcess[str]) -> str:
    return proc.stdout + proc.stderr


def _guidance_lines(output: str) -> list[str]:
    """Non-empty, non-JSON-telemetry lines that appear BEFORE any Python
    traceback marker.

    Cutting at the traceback marker (rather than line-by-line pattern
    matching) is deliberate: a real traceback's source-code-echo lines
    (e.g. ``    text = main_py.read_text(...)``) look, in isolation, like
    ordinary prose -- a per-line classifier would misclassify them as
    "guidance" and make this oracle pass vacuously against today's bug. Once
    the ``Traceback (most recent call last):`` marker is seen, everything
    from there to the end of output is traceback content, never guidance.
    """
    lines = output.splitlines()
    cutoff = len(lines)
    for index, line in enumerate(lines):
        if "Traceback (most recent call last):" in line:
            cutoff = index
            break
    return [
        line
        for line in lines[:cutoff]
        if line.strip() and not line.lstrip().startswith("{")
    ]


def _build_outside_checkout_case(kind: str, tmp_path: Path) -> tuple[Path, list[str]]:
    """Return ``(cwd, extra_args)`` for one outside-checkout charter variant
    (charter §Charter: "a bare empty directory, an unrelated existing project
    directory, --repo-root pointed at a path that doesn't exist, --repo-root .
    from outside a checkout, and no --repo-root flag at all")."""
    if kind == "bare-empty-dir":
        cwd = tmp_path / "bare"
        cwd.mkdir()
        return cwd, []
    if kind == "unrelated-project-dir":
        cwd = tmp_path / "unrelated-project"
        cwd.mkdir()
        (cwd / "package.json").write_text(
            '{"name": "some-other-project"}\n', encoding="utf-8"
        )
        (cwd / "README.md").write_text("# Some other project\n", encoding="utf-8")
        return cwd, []
    if kind == "repo-root-nonexistent":
        cwd = tmp_path / "bare-for-nonexistent-repo-root"
        cwd.mkdir()
        missing = tmp_path / "does-not-exist-xyz"
        return cwd, ["--repo-root", str(missing)]
    if kind == "repo-root-dot-explicit":
        cwd = tmp_path / "bare-for-explicit-dot"
        cwd.mkdir()
        return cwd, ["--repo-root", "."]
    raise AssertionError(f"unknown outside-checkout case kind: {kind!r}")


# ===========================================================================
# 1. NEGATIVE + POSITIVE witness -- active-RED today (the core bug observable)
# ===========================================================================


@pytest.mark.negative_at
@pytest.mark.parametrize("case_kind", _OUTSIDE_CHECKOUT_CASES)
def test_verify_catalog_coherence_explains_itself_outside_a_checkout(
    case_kind: str, tmp_path: Path
) -> None:
    """Outside an nWave-dev checkout, `des verify-catalog-coherence` must
    print one clear, human-readable message (WHAT/WHY/HOW) and exit non-zero
    -- never a raw Python traceback.

    RED today for the right reason (semantic, not a crash): today's output
    is the freshness-skip JSON line immediately followed by a raw
    ``Traceback (most recent call last)`` ending in ``FileNotFoundError`` --
    the negative marker assertion below fires as a genuine ``AssertionError``
    quoting the exact leaked traceback text.
    """
    cwd, extra_args = _build_outside_checkout_case(case_kind, tmp_path)
    proc = _run_verify_catalog_coherence(cwd, extra_args)
    output = _combined_output(proc)

    # NEGATIVE (critical-fail oracle -- the defect itself): no raw Python
    # crash artifact may leak into the CLI output.
    for marker in _TRACEBACK_MARKERS:
        assert marker not in output, (
            f"[{case_kind}] a raw Python crash artifact ({marker!r}) leaked "
            "into `des verify-catalog-coherence` output outside a checkout "
            f"-- must be a loud, human-readable message instead. "
            f"output=\n{output}"
        )

    # POSITIVE: at least one human-readable guidance line naming
    # what/why/how, distinct from JSON telemetry and traceback content.
    guidance = _guidance_lines(output)
    assert guidance, (
        f"[{case_kind}] expected at least one human-readable guidance line "
        "explaining WHAT the check needs, WHY it can't run here, and a "
        f"concrete next step -- got none. output=\n{output}"
    )
    guidance_text = " ".join(guidance).lower()
    assert any(keyword in guidance_text for keyword in _GUIDANCE_KEYWORDS), (
        f"[{case_kind}] the guidance line(s) do not mention any of "
        f"{_GUIDANCE_KEYWORDS} -- got {guidance!r}"
    )

    # Exit code: non-zero, a normal CLI failure -- never silently succeed.
    assert proc.returncode != 0, (
        f"[{case_kind}] outside a checkout the exit code must be non-zero "
        f"-- got {proc.returncode}, output=\n{output}"
    )


def test_verify_catalog_coherence_exit_code_is_consistent_outside_a_checkout(
    tmp_path: Path,
) -> None:
    """The exit code outside a checkout must be a normal CLI failure that
    does NOT differ across the missing-context cases (charter negative:
    "not a crash-style code that differs across the different missing-context
    cases"). Companion invariant to the parametrized test above -- not
    expected to be the RED witness by itself (an uncaught exception already
    exits uniformly at 1 today), but must keep holding after the fix."""
    exit_codes: set[int] = set()
    for case_kind in _OUTSIDE_CHECKOUT_CASES:
        cwd, extra_args = _build_outside_checkout_case(case_kind, tmp_path)
        proc = _run_verify_catalog_coherence(cwd, extra_args)
        exit_codes.add(proc.returncode)

    assert 0 not in exit_codes, (
        f"outside-checkout must never silently succeed -- got exit codes {exit_codes}"
    )
    assert len(exit_codes) == 1, (
        "outside-checkout exit code must be UNIFORM across missing-context "
        "cases (bare dir / unrelated project / missing --repo-root / "
        f"explicit '--repo-root .') -- got {exit_codes}"
    )


# ===========================================================================
# 2. POSITIVE CONTROL -- guards over-correction: the fix must not blunt the
#    real in-checkout check (charter: "confirm the fix didn't blunt the
#    tool's real job").
# ===========================================================================


def test_verify_catalog_coherence_still_checks_real_drift_inside_a_checkout() -> None:
    """Inside a real nWave-dev checkout the command must still run its real
    check and report normally -- it must NOT collapse into the same
    "not applicable / can't check here" response it gives outside a
    checkout. Already GREEN today; pins the invariant the fix must preserve.
    """
    proc = _run_verify_catalog_coherence(_REPO_ROOT, ["--repo-root", "."])
    output = _combined_output(proc)

    for marker in _TRACEBACK_MARKERS:
        assert marker not in output, (
            f"in-checkout run must never crash either -- found {marker!r}. "
            f"output=\n{output}"
        )

    # The catalog-coherence verdict is printed to STDOUT specifically
    # (`print(json.dumps(verdict))` in verify_catalog_coherence.main());
    # the freshness-skip telemetry goes to STDERR. `_combined_output`
    # concatenates stdout THEN stderr (not chronological interleaving), so
    # the real verdict event must be located in stdout alone, not by
    # "last JSON line of the combined text".
    stdout_json_lines = [
        line for line in proc.stdout.splitlines() if line.lstrip().startswith("{")
    ]
    assert stdout_json_lines, (
        f"expected at least one JSON event line on stdout -- output=\n{output}"
    )

    import json as _json

    last_event = _json.loads(stdout_json_lines[-1])
    assert last_event.get("event") == "CatalogCoherenceChecked", (
        "inside a real checkout the command must run its REAL check (the "
        "`CatalogCoherenceChecked` event) -- it must never collapse into the "
        "outside-checkout 'can't look here' response. "
        f"last_event={last_event!r}, output=\n{output}"
    )
    verdict = last_event.get("verdict")
    assert verdict in ("coherent", "drifted", "indeterminate"), (
        f"unexpected verdict shape -- {last_event!r}"
    )
    if verdict == "coherent":
        assert proc.returncode == 0, (
            f"a coherent verdict must exit 0 -- got {proc.returncode}, "
            f"last_event={last_event!r}"
        )
    else:
        assert proc.returncode != 0, (
            f"a drifted/indeterminate verdict must exit non-zero -- got "
            f"{proc.returncode}, last_event={last_event!r}"
        )
