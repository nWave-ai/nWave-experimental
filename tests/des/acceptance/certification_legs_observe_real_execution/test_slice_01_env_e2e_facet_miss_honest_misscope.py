"""Feature `certification-legs-observe-real-execution`, slice-01 (DDD-CERT-7).

Value statement (feature-delta.md [REF] Slice Plan, slice-01): a crafter
running ``des verify-environmental-e2e --mode run`` against a cargo-resolved
target with NO registered env-e2e facet gets an honest ``MISSCOPE`` naming
the missing facet, instead of a silent Python-wheel build attempted against a
Rust (or Go) tree.

Found in ``src/des/cli/verify_environmental_e2e.py::_maybe_route_through_
registered_e2e_adapter`` (lines 80-125) and its ``run``-mode caller (lines
527-536): ``resolve_runner(repo, None)`` (``des.ports.test_runner_port.
resolve``) correctly resolves a ``Cargo.toml``-only target to
``RunnerAdapter(name="cargo-test")`` -- but ``GLOBAL_REGISTRY.
lookup_environmental_e2e("cargo-test")`` returns ``None`` (only
``nwave_lang_python.py``/``nwave_lang_typescript.py`` call
``register_environmental_e2e``, Tsunami-verified 0 cargo/go callers), so
``_maybe_route_through_registered_e2e_adapter`` returns ``None`` -- and the
caller (line 527-536) treats EVERY ``None`` return identically, falling
through UNCONDITIONALLY to ``_build_wheel`` (a Python wheel build) regardless
of whether the resolved runner was a real, KNOWN non-pytest runner (cause b,
illegitimate fallthrough) or a genuinely-unrecognized target (cause a,
legitimate fallthrough -- UNCHANGED by this feature). DDD-CERT-7 requires the
caller to disambiguate the two causes: cause (b) must emit
``GateVerdict.MISSCOPED`` (the EXISTING frozen-L1.4 exit-3 value, per
``stdout_token.py``'s NORMATIVE-FROZEN L1.4 contract -- no 5th exit value)
with a diagnostic naming the missing facet, never reach ``_build_wheel``.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL ``des.cli.verify_environmental_e2e.main()`` CLI
driver, captured via ``capsys`` -- same in-process pattern as
``tests/bugs/des/test_verify_environmental_e2e_real_fail_emits_diagnostic.py``
and the Test Reuse & Consolidation Analysis row this slice's AT reuses ("des
CLI gate tests (in-process main() + JSON-verdict + exit-code driving
convention)"). ``_build_wheel`` is monkeypatched to a SPY (records its call
args, then raises) -- the cheapest deterministic way to prove "never
invoked" without shelling a real, multi-second ``python -m build`` against a
tree that has no ``pyproject.toml`` at all (it would fail anyway, just
slower and less precisely-observable). The spy's exception message is
deliberately GENERIC (never embeds the expected runner name) so the
facet-naming assertion below cannot accidentally pass by construction.

Active-RED today (real assertion failures, never an import/collection
error): both fixtures (cargo-test, go-test) resolve a real ``RunnerAdapter``
via the genuine filesystem lockfile scan, hit the genuine facet-miss branch,
and fall through to the spy -- so ``exit_code`` is ``GateExit.PARSE_IO`` (2,
the spy's ``RuntimeError`` mapped by the existing ``except RuntimeError``
branch) instead of the required ``GateExit.MISSCOPED`` (3), and the spy IS
called (proving the illegitimate build attempt) instead of never invoked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from des.cli import verify_environmental_e2e as gate_cli
from des.domain.environmental_e2e import GateExit


_FEATURE_DELTA_TEMPLATE = """\
# Feature Delta: fixture-feature (facet-miss cross-language default AT)

## Environmental E2E
- seam: fixture composition root
- test: {e2e_rel_path}
"""

# Two non-pytest fixtures whose lockfile resolves a REAL, KNOWN RunnerAdapter
# (cargo-test / go-test, per src/des/ports/test_runner_port.py's registry)
# but for which NO environmental-e2e facet is registered anywhere in this
# repo (Tsunami-verified: only the python/typescript plugins call
# register_environmental_e2e).
_CARGO_FIXTURE: dict[str, Any] = {
    "expected_runner": "cargo-test",
    "lockfile_name": "Cargo.toml",
    "lockfile_content": (
        '[package]\nname = "widget"\nversion = "0.1.0"\nedition = "2021"\n'
    ),
    "extra_files": {"src/main.rs": "fn main() {}\n"},
}

_GO_FIXTURE: dict[str, Any] = {
    "expected_runner": "go-test",
    "lockfile_name": "go.mod",
    "lockfile_content": "module widget\n\ngo 1.21\n",
    "extra_files": {"main.go": "package main\n\nfunc main() {}\n"},
}

_FIXTURES = [_CARGO_FIXTURE, _GO_FIXTURE]
_FIXTURE_IDS = ["cargo-test", "go-test"]


def _stage_fixture_source(tmp_path: Path, fixture: dict[str, Any]) -> tuple[Path, Path]:
    """Stage a minimal, real non-Python target tree + its feature-delta.

    NO ``pyproject.toml``/``pytest.ini``/``package.json`` is staged -- only the
    ONE lockfile the fixture names -- so ``resolve()``'s single-lockfile
    fast-path resolves unambiguously to the expected ``RunnerAdapter``
    (verified against ``test_runner_port.py::resolve`` -- 1 matched lockfile
    -> that runner, ``feature`` context ignored).
    """
    source = tmp_path / "fixture-feature"
    source.mkdir(parents=True)
    (source / fixture["lockfile_name"]).write_text(
        fixture["lockfile_content"], encoding="utf-8"
    )
    for rel_path, content in fixture["extra_files"].items():
        full = source / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")

    # The e2e test path is never read on the facet-miss path (routing happens
    # BEFORE the `e2e_abs.is_file()` check) -- any placeholder is sufficient.
    feature_delta = source / "feature-delta.md"
    feature_delta.write_text(
        _FEATURE_DELTA_TEMPLATE.format(e2e_rel_path="tests/never_read.py"),
        encoding="utf-8",
    )
    return source, feature_delta


def _run_gate_in_run_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    fixture: dict[str, Any],
    *,
    build_wheel_calls: list[tuple[Path, str, Path]],
) -> tuple[int, str, str]:
    """Drive the REAL `verify_environmental_e2e.main(["--mode", "run", ...])`
    in-process against a real cargo/go fixture, with `_build_wheel` replaced
    by a recording spy that raises a GENERIC error (never names the runner,
    so no assertion below can pass by construction). Returns
    `(exit_code, stdout, stderr)`.
    """

    def _spy_build_wheel(
        source_tree: Path, build_command: str, build_outdir: Path
    ) -> Path:
        build_wheel_calls.append((source_tree, build_command, build_outdir))
        raise RuntimeError(
            "PROBE: _build_wheel invoked -- this must never happen on a "
            "resolved non-pytest runner with no registered env-e2e facet"
        )

    monkeypatch.setattr(gate_cli, "_build_wheel", _spy_build_wheel)

    source, feature_delta = _stage_fixture_source(tmp_path, fixture)
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
        ]
    )
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


@pytest.mark.parametrize("fixture", _FIXTURES, ids=_FIXTURE_IDS)
def test_facet_miss_on_resolved_non_pytest_runner_emits_honest_misscope_naming_the_facet(
    fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): a real cargo-test/go-test-resolved
    target with no registered env-e2e facet must get ``GateVerdict.MISSCOPED``
    (exit 3, the EXISTING frozen-L1.4 value -- DDD-CERT-7 never adds a 5th
    exit value) with a diagnostic naming the missing facet's runner. Today
    the caller does not disambiguate the facet-miss cause from a genuinely-
    unrecognized target, so it falls through to ``_build_wheel`` and the
    build failure is reported as generic PARSE_IO (exit 2, verdict=broken)
    instead -- these assertions are what fails.
    """
    build_wheel_calls: list[tuple[Path, str, Path]] = []
    exit_code, stdout, stderr = _run_gate_in_run_mode(
        monkeypatch, capsys, tmp_path, fixture, build_wheel_calls=build_wheel_calls
    )

    assert exit_code == int(GateExit.MISSCOPED), (
        f"a resolved {fixture['expected_runner']!r} target with no registered "
        "env-e2e facet must exit MISSCOPED "
        f"({int(GateExit.MISSCOPED)}), confessing the gap honestly -- got "
        f"{exit_code} (stdout={stdout!r}, stderr={stderr!r})"
    )
    assert "verdict=misscoped" in stdout, (
        "the L1.4 stdout token must carry verdict=misscoped for a facet-miss "
        f"on a resolved non-pytest runner: {stdout!r}"
    )
    assert fixture["expected_runner"] in stderr, (
        "the diagnostic must NAME the missing facet's runner "
        f"({fixture['expected_runner']!r}) so a crafter knows exactly what "
        f"is missing -- got stderr: {stderr!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("fixture", _FIXTURES, ids=_FIXTURE_IDS)
def test_facet_miss_never_falls_through_to_a_python_wheel_build(
    fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (anti-recurrence, active-RED today): given the SAME
    facet-less cargo/go fixture, the gate must NEVER emit a green/PASS
    verdict AND must NEVER attempt a Python wheel build (``_build_wheel``
    must not be called; no ``*.whl`` artifact may ever be produced under the
    fixture tree). Today ``_build_wheel`` IS invoked unconditionally on
    every facet-miss (the illegitimate cross-language fallthrough this
    feature closes) -- the build-invocation assertion is what fails.
    """
    build_wheel_calls: list[tuple[Path, str, Path]] = []
    exit_code, stdout, _stderr = _run_gate_in_run_mode(
        monkeypatch, capsys, tmp_path, fixture, build_wheel_calls=build_wheel_calls
    )

    assert exit_code != int(GateExit.PASS), (
        f"a facet-less {fixture['expected_runner']!r} target must never "
        f"PASS -- got exit {exit_code}"
    )
    assert "verdict=pass" not in stdout, (
        f"a facet-less {fixture['expected_runner']!r} target must never "
        f"emit verdict=pass: {stdout!r}"
    )
    assert build_wheel_calls == [], (
        "_build_wheel must NEVER be invoked when the resolved runner is a "
        f"real, known non-pytest runner ({fixture['expected_runner']!r}) "
        "with no registered env-e2e facet -- a Python wheel build attempted "
        f"against a {fixture['expected_runner']!r} tree is exactly the "
        f"illegitimate cross-language default this AT guards against. Got "
        f"{len(build_wheel_calls)} call(s): {build_wheel_calls!r}"
    )
