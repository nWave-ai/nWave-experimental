"""Executable coverage for the BASE oracle-execution probe (K4 Run 13).

Real, bounded subprocess execution against tiny synthetic oracle files in
`tmp_path` -- never this repo's own tree, so there is no recursive-pytest
risk. The probe is NEVER switchable off (GDP-7) and language-agnostic
(roadmap: "language agnostic is an outcome constraint, not authorization
to build or retain a universal language-adapter framework"): a declared-
symbol token match is RED (accepted); a language-neutral build/compile
marker is `UNACCEPTABLE_BUILD` (refused, output quoted); anything else is
`INDETERMINATE` (an informational note, never a refusal).
"""

from __future__ import annotations

import sys
from pathlib import Path

from des.cli._oracle_red_reason_refusal import oracle_red_reason_check


def _contract(oracle_relative: str, route: str = "RED_TO_GREEN") -> dict:
    return {
        "delivery-route": route,
        "acceptance-tests": {"locator": oracle_relative},
        "targets": {
            "pkg/mod.py": {
                "justification": "The new NotBuiltYet symbol lives beside mod.",
                "overlap": "",
            }
        },
        "verification-scope": {
            "commands": [
                {
                    "executable": {"kind": "repository", "path": sys.executable},
                    "arguments": ["-m", "pytest", "-q", oracle_relative],
                }
            ]
        },
    }


def test_probe_always_fires_even_from_inside_this_repos_own_pytest_run(
    tmp_path: Path,
) -> None:
    """GDP-7: no environment can switch this probe off. Run under this
    repo's own ambient pytest process (no monkeypatch involved at all) --
    a real, isolated `tmp_path` subprocess, so no recursion risk either way."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text("def test_it(:\n    pass\n", encoding="utf-8")  # SyntaxError

    findings, notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert len(findings) == 1
    assert notes == []


def test_oracle_failing_for_the_right_reason_yields_no_finding_and_no_note(
    tmp_path: Path,
) -> None:
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text(
        "from pkg.mod import NotBuiltYet\n\n"
        "def test_it():\n    assert NotBuiltYet() == 1\n",
        encoding="utf-8",
    )

    findings, notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert findings == []
    assert notes == []


def test_oracle_with_a_syntax_error_is_refused_with_quoted_output(
    tmp_path: Path,
) -> None:
    """A SyntaxError matches the language-neutral build-marker table --
    refused, the real output quoted, no declared-symbol correlation
    needed."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text("def test_it(:\n    pass\n", encoding="utf-8")

    findings, notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert len(findings) == 1
    what, why, how = findings[0]
    assert "quoted output" in what
    assert why
    assert how
    assert notes == []


def test_oracle_failing_with_no_symbol_and_no_build_marker_is_indeterminate(
    tmp_path: Path,
) -> None:
    """A fixture/setup gap this classifier has no vocabulary for -- an
    honest INDETERMINATE note, never a refusal."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text(
        "def test_it():\n    raise RuntimeError('unrelated dependency missing')\n",
        encoding="utf-8",
    )

    findings, notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert findings == []
    assert len(notes) == 1
    assert "INFO:" in notes[0]
    assert "INDETERMINATE" in notes[0]


def test_already_green_oracle_for_red_to_green_is_refused(tmp_path: Path) -> None:
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text("def test_it():\n    assert 1 == 1\n", encoding="utf-8")

    findings, notes = oracle_red_reason_check(tmp_path, _contract("test_oracle.py"))

    assert len(findings) == 1
    what, _why, _how = findings[0]
    assert "already passes at BASE" in what
    assert notes == []


def test_already_green_oracle_for_green_to_green_is_accepted(tmp_path: Path) -> None:
    """GREEN_TO_GREEN expects the oracle already green at base -- no defect."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text("def test_it():\n    assert 1 == 1\n", encoding="utf-8")

    findings, notes = oracle_red_reason_check(
        tmp_path, _contract("test_oracle.py", route="GREEN_TO_GREEN")
    )

    assert findings == []
    assert notes == []


def test_command_that_cannot_even_start_is_an_informational_note_never_green(
    tmp_path: Path,
) -> None:
    """A missing executable / unresolvable interpreter raises `OSError`
    before any return code exists -- GDP-6: this must never be silent
    (an empty findings/notes pair would otherwise read as nothing to
    report, indistinguishable from a genuine GREEN)."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text(
        "from pkg.mod import NotBuiltYet\n\n"
        "def test_it():\n    assert NotBuiltYet() == 1\n",
        encoding="utf-8",
    )
    contract = _contract("test_oracle.py")
    contract["verification-scope"]["commands"] = [
        {
            "executable": {
                "kind": "repository",
                "path": "does-not-exist-nowhere-nohow",
            },
            "arguments": ["-m", "pytest", "-q", "test_oracle.py"],
        }
    ]

    findings, notes = oracle_red_reason_check(tmp_path, contract)

    assert findings == []
    assert len(notes) == 1
    assert "COULD-NOT-RUN" in notes[0]
    assert "could not even START" in notes[0]


def test_already_green_unrelated_command_is_not_flagged(tmp_path: Path) -> None:
    """An oracle-UNLINKED command that legitimately already passes (this
    repo's own shared dispatch-test fixture also declares `git diff
    --check`) must never be flagged -- the exact regression class CI
    caught once already."""
    oracle = tmp_path / "test_oracle.py"
    oracle.write_text(
        "from pkg.mod import NotBuiltYet\n\n"
        "def test_it():\n    assert NotBuiltYet() == 1\n",
        encoding="utf-8",
    )
    contract = _contract("test_oracle.py")
    contract["verification-scope"]["commands"].append(
        {"executable": {"kind": "toolchain", "name": "true"}, "arguments": []}
    )

    findings, _notes = oracle_red_reason_check(tmp_path, contract)

    assert findings == []
