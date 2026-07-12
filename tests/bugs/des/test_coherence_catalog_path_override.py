"""Regression (Rex round-2 RCA, 2026-07-12): ``des verify-wave-contract-coherence``
isolates its registry read behind ``--waves-dir`` but HARDCODES its catalog read
(``_CATALOG_PATH``, ``src/des/cli/verify_wave_contract_coherence.py:57``): every
coherence-check subprocess -- from every xdist worker -- reads the SAME live repo
file ``nWave/gates/_catalog.yaml`` with no override.

Charter: ``docs/feature/fix-coherence-catalog-path-isolation/feature-delta.md``.

Bug observable (the oracle): if that live read transiently resolves as absent, the
gate's catalog id-set collapses to empty and EVERY registry ``gate_id`` is reported
as an "orphan gate_id" content-drift -- a fabricated verdict about files that are
valid on disk. The asymmetry also blocks harnesses from pointing the gate at a
fixture catalog the way they already point it at a fixture registry.

The fix direction (charter, NOT implemented here): thread an optional
``--catalog-path`` argument (mirroring the existing ``--waves-dir`` pattern, same
help style, ``type=Path``, default ``_CATALOG_PATH``) from ``main()`` through
``evaluate_coherence`` down to ``_catalog_gate_ids(catalog_path)``. No new module,
no behavior change on the default path.

Driving surface (Mandate-13 driving-port-only): the REAL ``des
verify-wave-contract-coherence`` subcommand invoked as a real OS subprocess
(``sys.executable -m des ...``) -- reuses the subprocess idiom already established
by ``tests/des/acceptance/f-wave-contract-coherence/acceptance/steps/
composition_coherence_check.py`` (Test Reuse & Consolidation Analysis, feature-delta
§Reuse). Every fixture below is a real on-disk file under ``tmp_path`` -- a
PRECONDITION, never the expected verdict (Critical Rule 7, no fixture theater).

Active-RED today: ``--catalog-path`` is an unrecognized argument -- argparse exits
2 with a usage error naming it on stderr and the gate emits no JSON verdict line at
all. Every ``Then`` below that drives the override therefore fails with a semantic
``AssertionError`` on the missing/wrong verdict, never a collection/import error.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


# tests/bugs/des/<this file> -> parents[3] = REPO_ROOT (mirrors the production
# constant's own derivation in verify_wave_contract_coherence.py).
_REPO_ROOT = Path(__file__).resolve().parents[3]

_GATE_SUBCOMMAND = "verify-wave-contract-coherence"

# A gate_id guaranteed absent from the live catalog (nWave/gates/_catalog.yaml) --
# confirmed empirically (grep -c on the shipped file returns 0). Referencing it in a
# fixture registry means: read via the LIVE catalog -> orphan (FAIL); read via a
# fixture catalog that DECLARES it -> resolves (PASS). Flipping PASS/FAIL by
# swapping only --catalog-path is the isolation proof.
_FIXTURE_ONLY_GATE_ID = "fixture-only-catalog-path-override-probe"

# A gate_id that DOES exist in the live catalog today (nWave/gates/_catalog.yaml:153)
# -- used to prove the omitted-flag default path is byte-identical to today.
_LIVE_CATALOG_GATE_ID = "validate-feature-delta"

_WAVE = "fixture-wave"


def _write_catalog(path: Path, gate_ids: list[str]) -> None:
    """A minimal fixture catalog -- the narrow line-scan reader only needs
    `gate_id: <id>` lines (no real YAML parse, per the gate's TextSearch-floor
    contract), but the full shape is mirrored for readability."""
    lines = ['version: "1.0.0"', "", "gates:"]
    for gate_id in gate_ids:
        lines.append(f"  - gate_id: {gate_id}")
        lines.append('    responsibility: "fixture"')
        lines.append("    module: fixture.module")
        lines.append("    entry_function: main")
        lines.append("    language_neutral_contract: true")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_registry(waves_dir: Path, wave: str, gate_id: str) -> None:
    """A minimal fixture wave-contract registry carrying BOTH SSOTs
    (``gate_stack`` + ``output_contract``) and one gate_stack entry naming
    ``gate_id`` -- the orphan-detection target."""
    (waves_dir / f"{wave}.yaml").write_text(
        f"wave: {wave}\n"
        "gate_stack:\n"
        "  gate-out:\n"
        f"    - gate_id: {gate_id}\n"
        "      on_failure: block\n"
        "output_contract:\n"
        "  ref_sections: []\n",
        encoding="utf-8",
    )


def _write_prose(path: Path, wave: str) -> None:
    """Valid pointers, zero inline restatement -- the cured prose shape."""
    path.write_text(
        f"# {wave} wave\n\n"
        f"<!-- gates-ref: {wave} -->\n"
        f"<!-- outputs-ref: {wave} -->\n\n"
        "Fixture prose narrating intent only.\n",
        encoding="utf-8",
    )


def _run_gate(argv: list[str]) -> tuple[int, str, str]:
    """Invoke the REAL `des verify-wave-contract-coherence` subcommand as a real
    OS subprocess. Returns (exit_code, stdout, stderr)."""
    completed = subprocess.run(
        [sys.executable, "-m", "des", _GATE_SUBCOMMAND, *argv],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
    )
    return completed.returncode, completed.stdout, completed.stderr


def _parse_json(stdout: str) -> dict[str, object] | None:
    """The last JSON line of stdout, or None (RED at HEAD: argparse's usage
    error goes to stderr and emits no JSON line at all)."""
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


# ===========================================================================
# POSITIVE AT -- override isolation, active-RED today
# ===========================================================================


def test_catalog_path_override_isolates_catalog_read_from_live_repo(
    tmp_path: Path,
) -> None:
    """Swapping ONLY --catalog-path flips the verdict PASS/FAIL for the SAME
    registry -- proving the live repo catalog is never consulted under the
    override.

    Leg A (no override, today's default): the registry references a gate_id
    absent from the LIVE catalog -> orphan -> FAIL. This leg is unaffected by
    the fix and passes today already.

    Leg B (override): the SAME registry, with --catalog-path pointing at a
    fixture catalog that DECLARES that gate_id -> resolves -> PASS. RED
    today: --catalog-path is unrecognized, so the gate emits no verdict at
    all and this leg's assertion fails with a semantic AssertionError.
    """
    waves_dir = tmp_path / "waves"
    waves_dir.mkdir()
    _write_registry(waves_dir, _WAVE, _FIXTURE_ONLY_GATE_ID)
    prose = tmp_path / f"{_WAVE}.md"
    _write_prose(prose, _WAVE)

    base_argv = [
        "--wave",
        _WAVE,
        "--prose",
        str(prose),
        "--waves-dir",
        str(waves_dir),
    ]

    # Leg A -- default (live) catalog: the fixture-only gate_id is a genuine
    # orphan against the live nWave/gates/_catalog.yaml.
    exit_code_a, stdout_a, stderr_a = _run_gate(base_argv)
    payload_a = _parse_json(stdout_a)
    assert payload_a is not None and payload_a.get("verdict") == "fail", (
        "sanity leg: the live catalog must NOT contain the fixture-only "
        f"gate_id {_FIXTURE_ONLY_GATE_ID!r}, so the default (unoverridden) "
        f"read must report it as orphan (FAIL) -- got exit_code={exit_code_a}, "
        f"stdout={stdout_a!r}, stderr={stderr_a!r}"
    )
    assert _FIXTURE_ONLY_GATE_ID in str(payload_a.get("diagnostic", "")), (
        f"the FAIL diagnostic must name the orphan gate_id; got {payload_a!r}"
    )

    # Leg B -- override: a fixture catalog that DECLARES the gate_id. If the
    # live repo catalog were read instead, this would still be FAIL (leg A
    # proves it) -- PASS here is only possible if the override was honored.
    catalog_path = tmp_path / "fixture-catalog.yaml"
    _write_catalog(catalog_path, [_FIXTURE_ONLY_GATE_ID])
    exit_code_b, stdout_b, stderr_b = _run_gate(
        [*base_argv, "--catalog-path", str(catalog_path)]
    )
    payload_b = _parse_json(stdout_b)
    assert payload_b is not None and payload_b.get("verdict") == "pass", (
        "the `des verify-wave-contract-coherence` gate must accept "
        "--catalog-path and read the catalog id-set from THAT file -- the "
        "live repo catalog must never be touched under the override. It "
        "does not exist yet: DELIVER must thread an optional catalog_path "
        "parameter from main() argparse (mirroring --waves-dir) down to "
        f"_catalog_gate_ids(catalog_path). Got exit_code={exit_code_b!r}, "
        f"stdout={stdout_b!r}, stderr={stderr_b!r}"
    )


# ===========================================================================
# CONTROL AT -- omitted flag is byte-identical to today (unaffected by fix)
# ===========================================================================


def test_catalog_path_omitted_preserves_default_live_catalog_behavior(
    tmp_path: Path,
) -> None:
    """Omitting --catalog-path entirely must parse and behave exactly as
    today: a registry referencing a REAL live-catalog gate_id resolves via
    the default (live) catalog path -> PASS, no orphan.

    Must stay GREEN both before and after the fix -- an optional argument
    with a default preserving today's constant changes nothing on the
    omitted-flag path (feature-delta oracle: "default = the live repo
    path").
    """
    waves_dir = tmp_path / "waves"
    waves_dir.mkdir()
    _write_registry(waves_dir, _WAVE, _LIVE_CATALOG_GATE_ID)
    prose = tmp_path / f"{_WAVE}.md"
    _write_prose(prose, _WAVE)

    exit_code, stdout, stderr = _run_gate(
        [
            "--wave",
            _WAVE,
            "--prose",
            str(prose),
            "--waves-dir",
            str(waves_dir),
        ]
    )
    payload = _parse_json(stdout)

    assert payload is not None and payload.get("verdict") == "pass", (
        "omitting --catalog-path must preserve today's default behavior -- a "
        f"registry naming the live catalog's real gate_id "
        f"{_LIVE_CATALOG_GATE_ID!r} must resolve (PASS) via the default "
        f"live-repo catalog path; got exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}"
    )


# ===========================================================================
# NEGATIVE-PATH AT -- override still rejects orphans, active-RED today
# ===========================================================================


@pytest.mark.parametrize(
    "fixture_catalog_gate_ids",
    [
        pytest.param(["some-other-gate"], id="catalog-missing-the-id"),
        pytest.param([], id="catalog-empty"),
    ],
)
def test_override_still_rejects_orphan_gate_id_absent_from_fixture_catalog(
    tmp_path: Path, fixture_catalog_gate_ids: list[str]
) -> None:
    """The override changes WHERE the catalog is read, never WHAT is
    checked: a fixture catalog missing a gate_id the fixture registry
    declares must still FAIL, naming that orphan gate_id.

    RED today: --catalog-path is unrecognized, so no verdict is emitted at
    all -- this fails with a semantic AssertionError on the missing FAIL
    verdict / missing diagnostic, not a collection/import error.
    """
    waves_dir = tmp_path / "waves"
    waves_dir.mkdir()
    _write_registry(waves_dir, _WAVE, _FIXTURE_ONLY_GATE_ID)
    prose = tmp_path / f"{_WAVE}.md"
    _write_prose(prose, _WAVE)
    catalog_path = tmp_path / "fixture-catalog.yaml"
    _write_catalog(catalog_path, fixture_catalog_gate_ids)

    exit_code, stdout, stderr = _run_gate(
        [
            "--wave",
            _WAVE,
            "--prose",
            str(prose),
            "--waves-dir",
            str(waves_dir),
            "--catalog-path",
            str(catalog_path),
        ]
    )
    payload = _parse_json(stdout)

    assert payload is not None and payload.get("verdict") == "fail", (
        "an overridden catalog missing a gate_id the registry declares must "
        f"still FAIL (orphan gate_id {_FIXTURE_ONLY_GATE_ID!r}) -- the "
        "override relocates WHERE the catalog is read, never WHAT is "
        f"checked. Got exit_code={exit_code}, stdout={stdout!r}, "
        f"stderr={stderr!r}"
    )
    assert _FIXTURE_ONLY_GATE_ID in str(payload.get("diagnostic", "")), (
        f"the FAIL diagnostic must name the orphan gate_id under the "
        f"override too; got {payload!r}"
    )
