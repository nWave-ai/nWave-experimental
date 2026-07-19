"""Regression: every advertised `des verify-environmental-e2e --mode` must
either run a real check or refuse honestly -- never a naked traceback, never
a silent false-pass, never an exit code that collides with CHECK_FAILED.

RCA (sister instance, mid feature-end on `fix-oss-environmental-e2e-gate`):

    $ uv run des verify-environmental-e2e --mode verify-authored \\
        --feature-id fix-oss-environmental-e2e-gate \\
        --feature-delta docs/feature/fix-oss-environmental-e2e-gate/feature-delta.md
    Traceback (most recent call last):
      ...
      File "src/des/cli/verify_environmental_e2e.py", line 556, in _verify_authored_mode
        raise NotImplementedError(
    NotImplementedError: --mode verify-authored authored+genuine checks not
    implemented in slice-03
    EXIT=1

The reported `verify-authored` crash is the LEAST bad of FOUR broken
surfaces in `src/des/cli/verify_environmental_e2e.py`:

  - `--mode verify-present` / `--mode verify-merge-ready` / `--mode audit`
    crash UNCONDITIONALLY at `main()` (the trailing
    `raise NotImplementedError(...)`, ~line 698) -- BEFORE any argument
    validation. `--mode audit` alone, no other flags, crashes.
  - `--mode verify-authored` crashes only on ITS happy path (~line 556) --
    a real feature-delta carrying a `## Environmental E2E` block. Exactly
    the case of someone using it for real.
  - `--mode run` is implemented and correct. Not touched, not weakened.

TWO independent defects pinned here:

  (A) NAKED TRACEBACK -- the file already has a proven degrade-loud pattern
      used 3x for exactly this class of refusal (`_emit_parse_error` /
      `_emit_misscoped` / `_emit_misscoped_facet`, ~lines 372-470): stdout
      token + stderr diagnostic + human summary. The two
      `raise NotImplementedError` sites bypass it entirely, and nothing
      between them and `__main__.py:main()` catches it.

  (B) EXIT-CODE COLLISION -- the uncaught exception exits 1, byte-identical
      to `GateExit.CHECK_FAILED = 1`
      (`src/des/domain/environmental_e2e/stdout_token.py`). A caller reading
      `$?` cannot distinguish "the tool REFUSED to run this check" from
      "the check RAN and FAILED". The frozen L1.4 exit-code grid already has
      a value for capability-gap refusals -- `GateExit.MISSCOPED = 3`,
      reused (not a 5th value invented) by `_emit_misscoped_facet` for
      exactly this class of "this isn't built for you yet" refusal. This
      regression pins that same remedy.

Charter (authored independently, before the RCA, blind to the diagnosis):
`docs/product/expectations/fix-verify-authored-mode-not-implemented/
developer-gets-actionable-guidance-for-unbuilt-e2e-mode.md`. Its negative
oracles drive the assertions below:
  - a courteous "not implemented" that still leaves the developer stuck is
    the wall moved, not removed -- the refusal must carry a HOW.
  - a silent false-pass is worse than the raw traceback -- pinned as its own
    negative AT below.
  - fixing only the reported mode and leaving the other three raw is
    incomplete -- every advertised mode is exercised here, enumerated from
    argparse `choices` itself (never a hand-copied literal list) so a future
    6th mode is covered BY CONSTRUCTION, the exact staleness that let this
    defect ship unnoticed on 3 of 4 broken surfaces.
  - the refusal must let the developer tell misuse / misconfiguration /
    capability-gap apart, not a generic error any of the three could mean.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL `des.cli.verify_environmental_e2e.main()` CLI
driver, captured via `capsys` -- same in-process pattern as
`tests/bugs/des/test_verify_environmental_e2e_real_fail_emits_diagnostic.py`.
No subprocess fork. `_build_wheel` / `_install_into_prefix` are monkeypatched
to no-op stand-ins (same seam boundary as the sibling regression AT) purely
so `--mode run` -- the one genuinely-implemented mode, included here for
completeness and as a negative control -- completes in-process without a
real build; the four broken modes never reach that code at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from des.cli import verify_environmental_e2e as gate_cli
from des.domain.environmental_e2e import GateExit


# The one mode the RCA identifies as genuinely implemented. Deliberately an
# ALLOW-list of the GOOD mode, not a deny-list of the BAD ones: a future
# advertised mode defaults to the "must refuse honestly" contract below
# unless someone explicitly proves it real by adding it here -- the inverse
# of the staleness bug that let 3 of 4 broken modes ship unnoticed.
_MODES_WITH_SHIPPED_BEHAVIOR = frozenset({"run"})


def _advertised_modes() -> tuple[str, ...]:
    """Read `--mode`'s choices from the REAL argparse parser -- never a
    hand-copied literal list. A 6th advertised mode is picked up here
    automatically the moment it's added to `_build_parser()`."""
    parser = gate_cli._build_parser()
    for action in parser._actions:
        if action.dest == "mode":
            assert action.choices, "the --mode action must advertise choices"
            return tuple(action.choices)
    raise AssertionError("des verify-environmental-e2e: no --mode action found")


def _unbuilt_modes() -> tuple[str, ...]:
    return tuple(
        mode for mode in _advertised_modes() if mode not in _MODES_WITH_SHIPPED_BEHAVIOR
    )


_FEATURE_DELTA_TEMPLATE = """\
# Feature Delta: fixture-feature (unbuilt-mode-crash regression AT)

## Environmental E2E
- seam: fixture composition root
- test: {e2e_rel_path}
"""

_JUNIT_PASS_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="environmental_e2e" tests="1" failures="0" errors="0" skipped="0">
    <testcase classname="tests.test_environmental" name="test_environmental_e2e_passes"/>
  </testsuite>
</testsuites>
"""


def _stage_fixture_source(tmp_path: Path) -> tuple[Path, Path]:
    """Stage a minimal source tree: a `feature-delta.md` carrying a REAL
    `## Environmental E2E` block (the `verify-authored` happy path that
    triggers its diagnosed crash) + the e2e test file it names. No lockfile
    is staged, so `_maybe_route_through_registered_e2e_adapter` resolves
    Indeterminate and `--mode run` falls through to the legacy path -- same
    staging shape as the sibling real-FAIL regression AT.
    """
    source = tmp_path / "fixture-feature"
    source.mkdir(parents=True)
    e2e_rel = "tests/test_environmental.py"
    e2e_path = source / e2e_rel
    e2e_path.parent.mkdir(parents=True, exist_ok=True)
    e2e_path.write_text(
        "def test_environmental_e2e() -> None:\n    assert True\n", encoding="utf-8"
    )
    feature_delta = source / "feature-delta.md"
    feature_delta.write_text(
        _FEATURE_DELTA_TEMPLATE.format(e2e_rel_path=e2e_rel), encoding="utf-8"
    )
    return source, feature_delta


def _fake_build_wheel(
    source_tree: Path, build_command: str, build_outdir: Path
) -> Path:
    """Stand-in for the real `python -m build` -- never shells out. Only
    `--mode run` ever reaches this; the 4 broken modes never do."""
    build_outdir.mkdir(parents=True, exist_ok=True)
    wheel = build_outdir / "fixture_feature-0.0.1-py3-none-any.whl"
    wheel.write_bytes(b"fixture-wheel-bytes")
    return wheel


def _fake_install_into_prefix(wheel: Path, prefix: Path) -> None:
    """Stand-in for the real `pip install --target` -- never shells out."""
    prefix.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class _ModeInvocationResult:
    mode: str
    exit_code: int | None
    raised: BaseException | None
    stdout: str
    stderr: str

    @property
    def combined(self) -> str:
        return self.stdout + self.stderr


def _invoke_mode(
    mode: str,
    *,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> _ModeInvocationResult:
    """Drive the REAL `verify_environmental_e2e.main()` in-process with one
    UNIFIED superset of flags every mode tolerates (argparse marks all but
    `--mode` optional, so an unused flag is harmless to a mode that ignores
    it). The exception is caught HERE -- deliberately -- and reified into
    `result.raised` so every test below asserts via `pytest`'s own
    AssertionError machinery, never lets a bare exception propagate out of
    the test body.
    """
    monkeypatch.setattr(gate_cli, "_build_wheel", _fake_build_wheel)
    monkeypatch.setattr(gate_cli, "_install_into_prefix", _fake_install_into_prefix)

    source, feature_delta = _stage_fixture_source(tmp_path)
    junit_path = tmp_path / "junit.xml"
    junit_path.write_text(_JUNIT_PASS_XML, encoding="utf-8")
    clean_prefix = tmp_path / "clean-prefix"
    results_json = tmp_path / "results.json"

    argv = [
        "--mode",
        mode,
        "--feature-id",
        "fixture-feature",
        "--feature-delta",
        str(feature_delta),
        "--source-tree",
        str(source),
        "--clean-prefix",
        str(clean_prefix),
        "--fixture-junit-xml",
        str(junit_path),
        "--reruns",
        "1",
        "--results-json",
        str(results_json),
        "--tests-root",
        str(source / "tests"),
        "--max-age-days",
        "30",
    ]

    exit_code: int | None = None
    raised: BaseException | None = None
    try:
        exit_code = gate_cli.main(argv)
    except Exception as exc:
        raised = exc

    captured = capsys.readouterr()
    return _ModeInvocationResult(
        mode=mode,
        exit_code=exit_code,
        raised=raised,
        stdout=captured.out,
        stderr=captured.err,
    )


@pytest.mark.parametrize("mode", _advertised_modes())
def test_no_advertised_mode_produces_an_unhandled_traceback(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today for 4 of 5 modes): every mode
    `--help` advertises -- enumerated from the REAL argparse `choices`, not
    a hand-copied list -- must complete `main()` without an unhandled
    exception escaping. Today `verify-present`, `verify-merge-ready`,
    `audit` crash unconditionally and `verify-authored` crashes on its
    happy path; only `run` (the negative control here) is clean.
    """
    result = _invoke_mode(
        mode, monkeypatch=monkeypatch, capsys=capsys, tmp_path=tmp_path
    )

    assert result.raised is None, (
        f"--mode {mode} let an unhandled exception escape main() -- this is "
        "the exact naked-traceback defect the RCA diagnosed: the existing "
        "degrade-loud pattern (_emit_parse_error / _emit_misscoped / "
        "_emit_misscoped_facet) must catch this and emit an honest refusal "
        f"instead. Raised: {result.raised!r}"
    )


@pytest.mark.parametrize("mode", _unbuilt_modes())
def test_unbuilt_mode_refusal_is_self_explaining(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): a not-yet-built mode's refusal must
    name WHAT is unbuilt (the mode itself), state plainly it is not
    implemented, and tell the developer HOW to proceed. A courteous
    "not implemented" with no next action is the wall moved, not removed
    (charter negative oracle) -- so both must be present, and neither may be
    a raw Python traceback dump.
    """
    result = _invoke_mode(
        mode, monkeypatch=monkeypatch, capsys=capsys, tmp_path=tmp_path
    )

    assert result.raised is None, (
        f"--mode {mode} raised instead of refusing honestly: {result.raised!r} "
        "-- see test_no_advertised_mode_produces_an_unhandled_traceback for "
        "the primary defect; this test cannot check message content on a "
        "crash."
    )

    combined = result.combined

    assert "Traceback" not in combined and "NotImplementedError" not in combined, (
        f"--mode {mode} must never surface a raw Python traceback or "
        f"exception-class dump to the developer: {combined!r}"
    )

    assert mode in combined, (
        f"--mode {mode}'s refusal must NAME the unbuilt mode so the "
        f"developer knows exactly which one is not built: {combined!r}"
    )

    not_implemented_markers = (
        "not implemented",
        "not yet implemented",
        "not yet built",
        "unimplemented",
    )
    names_why = any(marker in combined.lower() for marker in not_implemented_markers)
    assert names_why, (
        f"--mode {mode}'s refusal must state plainly that it is NOT "
        f"IMPLEMENTED (the WHY) -- a generic error leaves the developer "
        f"unable to tell misuse / misconfiguration / capability-gap apart: "
        f"{combined!r}"
    )

    how_markers = (
        "instead",
        "use ",
        "--mode",
        "track",
        "workaround",
        "backlog",
        "docs",
    )
    names_how = any(marker in combined.lower() for marker in how_markers)
    assert names_how, (
        f"--mode {mode}'s refusal must tell the developer HOW to proceed "
        "(a different mode to use, a documented workaround, or where the "
        f"gap is tracked) -- a bare 'not implemented' is the wall moved, "
        f"not removed: {combined!r}"
    )


@pytest.mark.parametrize("mode", _unbuilt_modes())
def test_unbuilt_mode_exit_code_is_distinguishable_from_check_failed(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): the exit code for a capability-gap
    refusal must never collide with `GateExit.CHECK_FAILED` (1) -- a caller
    reading `$?` in feature-end automation must be able to tell "the tool
    refused to run this check" apart from "the check ran and found a
    problem". Pinned to `GateExit.MISSCOPED` (3): the frozen L1.4
    exit-code grid already has this value, reused verbatim by
    `_emit_misscoped_facet` for the identical "not built for you yet"
    class of refusal -- the correct fix reuses it, it does not invent a
    5th exit value.
    """
    result = _invoke_mode(
        mode, monkeypatch=monkeypatch, capsys=capsys, tmp_path=tmp_path
    )

    assert result.raised is None, (
        f"--mode {mode} raised instead of returning an exit code: {result.raised!r}"
    )
    assert result.exit_code != int(GateExit.CHECK_FAILED), (
        f"--mode {mode} exited {result.exit_code}, colliding with "
        f"GateExit.CHECK_FAILED ({int(GateExit.CHECK_FAILED)}) -- a script "
        "reading $? cannot tell 'refused to run' from 'ran and failed'."
    )
    assert result.exit_code == int(GateExit.MISSCOPED), (
        f"--mode {mode} must exit GateExit.MISSCOPED "
        f"({int(GateExit.MISSCOPED)}) for a capability-gap refusal, per the "
        f"frozen L1.4 exit-code grid already reused by _emit_misscoped_facet "
        f"-- got {result.exit_code}."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("mode", _unbuilt_modes())
def test_unbuilt_mode_never_emits_a_passing_verdict(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """NEGATIVE AT -- the anti-silent-pass guard, and the one that matters
    most (charter: a silent false-pass is far worse than the raw
    traceback). A not-yet-built mode must NEVER print the L1.4
    `verdict=pass` token or exit `GateExit.PASS` -- a developer must never
    walk away believing an environmental-e2e check ran and passed when it
    was never actually executed.
    """
    result = _invoke_mode(
        mode, monkeypatch=monkeypatch, capsys=capsys, tmp_path=tmp_path
    )

    assert result.raised is None, (
        f"--mode {mode} raised instead of refusing: {result.raised!r}"
    )
    assert "verdict=pass" not in result.stdout, (
        f"--mode {mode} must NEVER emit a passing L1.4 verdict token for a "
        f"check that never ran: {result.stdout!r}"
    )
    assert result.exit_code != int(GateExit.PASS), (
        f"--mode {mode} must NEVER exit GateExit.PASS "
        f"({int(GateExit.PASS)}) for a check that never ran -- got "
        f"{result.exit_code}."
    )
