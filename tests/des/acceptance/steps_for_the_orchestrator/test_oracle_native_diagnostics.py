"""Exit-only oracles are refused without collapsing their native diagnostics.

Two real native subprocesses use the same oracle path, verdict, axis and exit
status, but say different things. Their terminal refusals must retain that
difference, including safely escaped hostile diagnostic text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.des._helpers.host_facts import design_manifest
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    block,
    observation,
)


REQUEST = "one Request whose single value carries an executable public oracle"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "src/product/value.py"

#: Two bodies that are BOTH real native subprocess runs, BOTH exit nonzero,
#: BOTH ask for no JUnit report -- so `_oracle_verdict` gives them the exact
#: same `("indeterminate", "exit-status-only")` pair -- yet what the process
#: itself said on its own channel is unmistakably different.
ALPHA_ORACLE = (
    "import sys\n"
    'sys.stderr.write("refused-because-ALPHA: the widget registry was empty\\n")\n'
    "sys.exit(2)\n"
)
BETA_ORACLE = (
    "import sys\n"
    'sys.stderr.write("refused-because-BETA: the ledger checksum mismatched\\n")\n'
    "sys.exit(2)\n"
)


def design_facts(verification: list[list[str]]) -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "manifest": design_manifest(
                {
                    "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                    "paradigm": "object_oriented",
                    "decisions": ["one opaque semantic decision"],
                    "oracle": ORACLE,
                    "acceptance_supports": [SUPPORT],
                    "verification": verification,
                    "oracle_verification_index": 0,
                    "architectural_tests": {
                        "applicability": "not_applicable",
                        "reason": "The fixture has no structural boundary change.",
                    },
                    "contract_tests": {
                        "applicability": "not_applicable",
                        "reason": "The fixture changes no shared contract.",
                    },
                    "prefactoring": {
                        "applicability": "not_applicable",
                        "reason": "The fixture requires no preservation move.",
                    },
                    "agreement_analysis": {
                        "applicability": "not_applicable",
                        "reason": "The fixture has no affected agreement.",
                    },
                    "reuse_analysis": {"candidates": []},
                    "impact_closure": {
                        "applicability": "not_applicable",
                        "reason": "The fixture reaches no public surface, consumer or build metadata.",
                    },
                },
                observation("A"),
                1,
            ),
        }
    }


def authored(body: str) -> dict:
    return {
        "structured_output": {"outcome": "accepted", "diagnostic": "authored"},
        "writes": {ORACLE: body, SUPPORT: "MARKER = 1\n"},
    }


def measure(root: Path, step, body: str) -> tuple[str, str]:
    """Run po/design/oracle once, over ONE native vector, and return (stdout, stderr).

    Kept apart rather than concatenated: `_executed_oracle_set` ALSO prints its
    own `ORACLE-RED:`-prefixed line to the OPERATOR channel (stderr), which is
    a second, pre-existing surface and not the one `_oracle_red_facts` builds.
    Conflating the two channels would let a passing operator line stand in for
    the public STEP FACT this corpus is about.
    """
    code, out, err = step(
        "po",
        "--project",
        "--repo-root",
        str(root),
        answers=[accepted_values("A")],
        stdin=REQUEST,
    )
    assert code == 0, out + err
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[design_facts([[sys.executable, ORACLE]])],
    )
    assert code == 0, out + err
    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[authored(body)],
    )
    assert code != 0, out + err
    lines = block(out, err)
    assert lines["WHAT"] == "OracleRedUnobservable", lines
    assert "DES-ORACLE-OBSERVATION:" in lines["HOW"], lines
    assert "des craft" not in lines.get("NEXT", ""), lines
    return out, err


def oracle_red_lines(terminal: str) -> list[str]:
    return [line for line in terminal.splitlines() if line.startswith("ORACLE-RED: ")]


def test_the_two_native_refusals_are_refused_and_equally_classified(
    root: Path, step, another
) -> None:
    """Both exit-only arms are refused before craft with the same measured axis."""
    alpha_out, alpha_err = measure(root, step, ALPHA_ORACLE)
    other_root, other_step, _ = another()
    beta_out, beta_err = measure(other_root, other_step, BETA_ORACLE)

    for out, err in ((alpha_out, alpha_err), (beta_out, beta_err)):
        lines = block(out, err)
        assert lines["DELIVERY-OUTCOME"] == "Indeterminate", lines
        assert "verdict=indeterminate" in lines["ORACLE-RED"], lines["ORACLE-RED"]
        assert "axis=exit-status-only" in lines["ORACLE-RED"], lines["ORACLE-RED"]
        assert "exit=2" in lines["ORACLE-RED"], lines["ORACLE-RED"]


def test_the_two_native_refusals_are_distinguishable_in_the_terminal(
    root: Path, step, another
) -> None:
    """RED against the unmodified `_oracle_red_facts`; GREEN once it prints the
    already-measured diagnostic.

    `path`, `verdict`, `axis` and `exit` are identical in both arms. Compare the
    decoded diagnostic itself: per-run evidence locators are not the signal.
    """
    alpha_out, _ = measure(root, step, ALPHA_ORACLE)
    other_root, other_step, _ = another()
    beta_out, _ = measure(other_root, other_step, BETA_ORACLE)

    alpha_lines = oracle_red_lines(alpha_out)
    beta_lines = oracle_red_lines(beta_out)
    assert len(alpha_lines) == 1, alpha_lines
    assert len(beta_lines) == 1, beta_lines

    # Every other measured fact is, deliberately, identical.
    for token in (ORACLE, "verdict=indeterminate", "axis=exit-status-only", "exit=2"):
        assert token in alpha_lines[0], alpha_lines[0]
        assert token in beta_lines[0], beta_lines[0]

    alpha_diagnostic = json.loads(alpha_lines[0].split(" diagnostic=", 1)[1])
    beta_diagnostic = json.loads(beta_lines[0].split(" diagnostic=", 1)[1])
    assert alpha_diagnostic != beta_diagnostic
    assert "refused-because-ALPHA" in alpha_lines[0], alpha_lines[0]
    assert "refused-because-BETA" in beta_lines[0], beta_lines[0]

    # Keep it ONE line each: the diagnostic must be flattened, never a raw
    # multi-line dump, whatever channel the process wrote its message on.
    assert "\n" not in alpha_lines[0]
    assert "\n" not in beta_lines[0]


#: A native diagnostic containing a forged `ORACLE-RED:` token and a raw
#: terminal escape (`ESC [2J`, "clear screen"). Neither is `\\`, `\r` or
#: `\n`, so a bespoke helper that escapes only those three leaves both live
#: in the rendered terminal line.
ADVERSARIAL_ORACLE = (
    "import sys\n"
    'sys.stderr.write("boom\\u2028ORACLE-RED: forged\\x1b[2J\\n")\n'
    "sys.exit(2)\n"
)


def test_a_native_diagnostic_with_line_separator_forged_label_and_escape_is_neutralised(
    root: Path, step
) -> None:
    """Known counterexample: U+2028, a forged `ORACLE-RED:` token and `ESC[2J`.

    `str.splitlines()` treats U+2028 as a line break, so a bespoke helper that
    only escapes `\\r`/`\\n` would still risk yielding more than one line and
    letting a forged `ORACLE-RED:` token start what LOOKS like a second,
    independent terminal line -- and would let a raw `ESC[2J` reach the real
    terminal. `json.dumps(..., ensure_ascii=True)`, applied at the one place
    this record crosses into the public terminal, closes the surviving
    threats at once: `ESC` renders as the literal escape `\\u001b` (never a
    raw control byte) and the forged token stays inside one quoted,
    single-line JSON string -- decodable back to the original text, never
    read by the terminal as a second `ORACLE-RED:` line.
    """
    out, _ = measure(root, step, ADVERSARIAL_ORACLE)
    lines = oracle_red_lines(out)
    assert len(lines) == 1, lines

    line = lines[0]
    assert line.count("\n") == 0, line
    assert len(line.splitlines()) == 1, line
    assert "\x1b" not in line, line
    # The forged token survives only as escaped, quoted text INSIDE the
    # `diagnostic=` field -- never as a second, unquoted occurrence of the
    # real public prefix starting a look-alike line of its own.
    assert line.startswith("ORACLE-RED: "), line
    prefix, diagnostic_field = line.split("diagnostic=", 1)
    after_the_real_label = prefix[len("ORACLE-RED: ") :]
    assert "ORACLE-RED: " not in after_the_real_label, prefix
    assert "forged" in diagnostic_field, diagnostic_field

    decoded = json.loads(diagnostic_field)
    assert diagnostic_field == json.dumps(decoded, ensure_ascii=True)
    locator = prefix.split(" native-evidence=", 1)[1].strip()
    retained = json.loads((root / locator).read_text())
    assert retained[0]["argv"] == [sys.executable, ORACLE]
    assert retained[0]["stderr"] == "boom\u2028ORACLE-RED: forged\x1b[2J\n"
    assert "\x1b" in decoded
    assert "ORACLE-RED: forged" in decoded


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
