"""Regression (GDP-3): the env-e2e gate's genuine-FAIL branch must emit a
human what/why/how, not ONLY a machine ``StdoutToken``.

Charter: ``docs/product/expectations/fix-env-e2e-real-fail-emits-diagnostic/
the-real-fail-path-emits-a-human-what-why-how.md``.

Found in ``src/des/cli/verify_environmental_e2e.py::_run_mode`` (lines
581-583): once the verdict is computed from the JUnit XML
(``_verdict_from_junit``, lines 294-312) and the L1.4 stdout token is emitted
(``_emit_token``, stdout-only), the CHECK_FAILED branch returns bare --

    if verdict is GateVerdict.PASS:
        return int(GateExit.PASS)
    return int(GateExit.CHECK_FAILED)

-- with ZERO human-readable diagnostic. Contrast with the parse/IO
(``_emit_parse_error``) and misscoped (``_emit_misscoped``) branches, which
already print a ``diagnostic: ...`` line on stderr AND a colored
``print_human_summary`` line. This file is specifically the genuine-test-FAIL
branch those two helpers do NOT cover. The check itself (exit ==
``GateExit.CHECK_FAILED`` == 1, a genuinely-failing e2e still FAILs) is
pinned and must stay intact -- the fix adds a diagnostic, it never softens
the floor.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL ``des.cli.verify_environmental_e2e.main()`` CLI
driver, captured via ``capsys`` -- same in-process pattern as
``tests/bugs/des/test_gate_g_verdict_self_explains_how_and_human_surface.py``.
No subprocess fork.

Cheapest deterministic route to the CHECK_FAILED branch (no Docker, no real
build): the L1.4 CLI already ships a documented test seam,
``--fixture-junit-xml``, that substitutes a pre-baked JUnit XML for the real
pytest subprocess run (``_consume_fixture_junit``) -- this is the SAME seam
the (now-consolidated) slice-01 walking-skeleton AT used, reused verbatim
here. What that precedent did NOT cheapen is the build/install step (it ran a
REAL ``python -m build`` + ``pip install --target`` against a hatchling
fixture package). This AT goes one step cheaper: ``_build_wheel`` and
``_install_into_prefix`` are monkeypatched to a no-op stand-in (the module-
level seam boundary an infra-treatment fake occupies -- analogous to how the
project's own docstring describes the Docker-capability probe as "the only
non-deterministic thing faked"), so the whole gate run is in-process,
sub-second, and hits the REAL ``_verdict_from_junit`` -> real-FAIL branch
with no filesystem build tool invoked at all. The fixture source tree carries
no lockfile (pyproject.toml/pytest.ini/...), so the runner check is
unrecognized and the explicit build/install/run path remains applicable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli import verify_environmental_e2e as gate_cli
from des.domain.environmental_e2e import GateExit


_FEATURE_DELTA_TEMPLATE = """\
# Feature Delta: fixture-feature (real-FAIL diagnostic regression AT)

## Environmental E2E
- seam: fixture composition root
- test: {e2e_rel_path}
"""

_JUNIT_FAIL_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="environmental_e2e" tests="1" failures="1" errors="0" skipped="0">
    <testcase classname="tests.test_environmental" name="test_environmental_e2e_fails">
      <failure message="AssertionError">advertise() != 'installed'</failure>
    </testcase>
  </testsuite>
</testsuites>
"""

_JUNIT_PASS_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="environmental_e2e" tests="1" failures="0" errors="0" skipped="0">
    <testcase classname="tests.test_environmental" name="test_environmental_e2e_passes"/>
  </testsuite>
</testsuites>
"""


def _stage_fixture_source(tmp_path: Path) -> tuple[Path, Path]:
    """Stage a minimal source tree: a `feature-delta.md` `## Environmental E2E`
    block + the e2e test FILE it names (never executed -- the JUnit fixture
    seam supplies the outcome). No lockfile is staged (no pyproject.toml /
    pytest.ini), so the explicit build/install/run path remains applicable.
    """
    source = tmp_path / "fixture-feature"
    source.mkdir(parents=True)
    (source / "pyproject.toml").write_text(
        '[project]\nname = "fixture-feature"\nversion = "0.0.1"\n',
        encoding="utf-8",
    )
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
    """Stand-in for the real `python -m build` -- writes a placeholder wheel
    byte-blob so `_sha256_file` has real bytes to hash; never shells out."""
    build_outdir.mkdir(parents=True, exist_ok=True)
    wheel = build_outdir / "fixture_feature-0.0.1-py3-none-any.whl"
    wheel.write_bytes(b"fixture-wheel-bytes")
    return wheel


def _fake_install_into_prefix(wheel: Path, prefix: Path) -> None:
    """Stand-in for the real `pip install --target` -- no-op, never shells out."""
    prefix.mkdir(parents=True, exist_ok=True)


def _run_gate_in_run_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    *,
    junit_xml: str,
) -> tuple[int, str, str]:
    """Drive the REAL `verify_environmental_e2e.main(["--mode", "run", ...])`
    in-process, with the build/install seam faked and the JUnit-verdict seam
    fed the caller-supplied XML. Returns `(exit_code, stdout, stderr)`.
    """
    monkeypatch.setattr(gate_cli, "_build_wheel", _fake_build_wheel)
    monkeypatch.setattr(gate_cli, "_install_into_prefix", _fake_install_into_prefix)

    source, feature_delta = _stage_fixture_source(tmp_path)
    junit_path = tmp_path / "junit.xml"
    junit_path.write_text(junit_xml, encoding="utf-8")
    clean_prefix = tmp_path / "clean-prefix"

    exit_code = gate_cli.main(
        [
            "--mode",
            "run",
            "--feature-id",
            "fixture-feature",
            "--feature-delta",
            str(feature_delta),
            "--source-tree",
            str(source),
            "--clean-prefix",
            str(clean_prefix),
            "--reruns",
            "1",
            "--fixture-junit-xml",
            str(junit_path),
        ]
    )
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


@pytest.mark.parametrize("foreign_manifest", ("Cargo.toml", "go.mod", "package.json"))
def test_polyglot_python_tooling_refuses_before_building_or_running_pytest(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    foreign_manifest: str,
) -> None:
    """A Python wheel config is not proof that a polyglot root wants pytest."""
    source, feature_delta = _stage_fixture_source(tmp_path)
    (source / foreign_manifest).write_text(
        "# foreign project marker\n", encoding="utf-8"
    )

    def _must_not_build(*_args: object, **_kwargs: object) -> Path:
        raise AssertionError("ambiguous project must refuse before the Python build")

    monkeypatch.setattr(gate_cli, "_build_wheel", _must_not_build)

    exit_code = gate_cli.main(
        [
            "--mode",
            "run",
            "--feature-id",
            "fixture-feature",
            "--feature-delta",
            str(feature_delta),
            "--source-tree",
            str(source),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == int(GateExit.MISSCOPED)
    assert foreign_manifest in captured.err
    assert "already-declared matching verification command" in captured.err


def test_real_fail_verdict_emits_a_human_what_why_how_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): a genuinely-FAILING JUnit XML drives
    `--mode run` into the CHECK_FAILED branch. The floor stays intact (exit ==
    CHECK_FAILED == 1). Today the branch emits ONLY the machine
    `StdoutToken` line -- this assertion is what fails: the output must ALSO
    carry a human-readable diagnostic naming WHAT (the e2e suite failed), WHY
    (the FAIL verdict), and HOW (how to reproduce -- the run-mode invocation
    or where the JUnit outcome lives).
    """
    exit_code, stdout, stderr = _run_gate_in_run_mode(
        monkeypatch, capsys, tmp_path, junit_xml=_JUNIT_FAIL_XML
    )

    # The floor: a genuinely-failing e2e still FAILs. Already true today.
    assert exit_code == int(GateExit.CHECK_FAILED), (
        "the real-FAIL floor must stay intact -- a genuinely-failing e2e run "
        f"must exit CHECK_FAILED ({int(GateExit.CHECK_FAILED)}), got {exit_code}"
    )

    # The machine token is on stdout, unchanged. Already true today.
    assert "verdict=fail" in stdout, (
        f"expected the L1.4 stdout token to carry verdict=fail: {stdout!r}"
    )

    # WHAT/WHY/HOW -- MISSING today (the GDP-3 defect this AT is red for).
    # The L1.4 machine token is a single `environmental_e2e mode=...` line
    # (not JSON) -- filter it out to isolate any human-readable addition.
    combined = stdout + stderr
    human_lines = [
        line
        for line in combined.splitlines()
        if line.strip() and not line.strip().startswith("environmental_e2e mode=")
    ]
    assert human_lines, (
        "the real-FAIL branch must emit >=1 human-readable line beyond the "
        f"machine StdoutToken -- got only machine output: {combined!r}"
    )

    names_what = "e2e" in combined.lower() and "fail" in combined.lower()
    assert names_what, (
        "the human diagnostic must name WHAT failed (the e2e suite did not "
        f"pass): {combined!r}"
    )

    names_how = (
        "verify-environmental-e2e" in combined
        or "verify_environmental_e2e" in combined
        or "--mode run" in combined
        or "junit" in combined.lower()
    )
    assert names_how, (
        "the human diagnostic must carry a HOW (reproduce via "
        "'verify-environmental-e2e --mode run' or point at the JUnit "
        f"outcome): {combined!r}"
    )


@pytest.mark.negative_at
def test_passing_run_never_emits_a_spurious_failure_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (control -- green today, stays green after the fix): an
    all-passing JUnit XML drives `--mode run` to the PASS branch. Exit stays
    PASS (0), and -- unlike the FAIL branch -- the output must NOT carry a
    spurious failure-diagnostic; the WHAT/WHY/HOW addition belongs only on
    the real-FAIL branch, never leaking onto a passing run.
    """
    exit_code, stdout, stderr = _run_gate_in_run_mode(
        monkeypatch, capsys, tmp_path, junit_xml=_JUNIT_PASS_XML
    )

    assert exit_code == int(GateExit.PASS), (
        f"an all-passing JUnit XML must yield exit PASS (0), got {exit_code}"
    )
    assert "verdict=pass" in stdout, (
        f"expected the L1.4 stdout token to carry verdict=pass: {stdout!r}"
    )

    combined = stdout + stderr
    assert "diagnostic:" not in combined, (
        f"a PASS run must never emit a failure-diagnostic line: {combined!r}"
    )
    assert "❌" not in combined, (
        f"a PASS run must never emit the FAIL human-surface marker: {combined!r}"
    )
