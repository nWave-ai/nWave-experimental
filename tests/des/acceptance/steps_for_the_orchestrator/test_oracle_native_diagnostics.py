"""Public oracle: `des oracle` must not collapse two distinct native failures.

THE INCIDENT THIS MEASURES. `_executed_oracle_set` already computes a per-item
`"diagnostic"` field (the tail of whichever channel the native process spoke
on) alongside `path`, `verdict`, `axis` and `exit` -- but `_oracle_red_facts`,
the ONLY place those measured rows reach the public terminal, prints just
`path`/`verdict`/`axis`/`exit`. Two vectors that are BOTH real native
subprocess runs, BOTH exit nonzero, BOTH ask for no JUnit report (so both earn
the identical `verdict=indeterminate axis=exit-status-only`), and use the SAME
oracle path constant, produce an ORACLE-RED line that is byte-for-byte
IDENTICAL even though the two subprocesses failed for entirely different,
already-observed reasons. The LLM reading the terminal cannot tell an
`assert False` refusal from an `ImportError` refusal -- both facts it needs to
decide the next step -- though the software measured the difference already.

WHAT IS MEASURED HERE, through the one public port and nothing else: `des po`,
`des design`, `des oracle`, run TWICE over two independent checkouts (the
`another` fixture) so neither arm's oracle bytes or turn log leak into the
other. Each arm's native oracle is a small Python script AUTHORED to
`tests/acceptance/test_value.py` and executed as `[sys.executable, ORACLE]`
(a real subprocess run of that file, never `python -c` and never `pytest`),
so the report axis stays `exit-status-only` and the two arms differ ONLY in
what the process itself said.

THIS IS A REPRO, NOT YET A REGRESSION OF THE FIX. `test_the_two_native_refusals_are_distinguishable_in_the_terminal`
is the RED case against the unmodified `_oracle_red_facts`: it is expected to
fail until that function is asked to print the already-measured diagnostic.
Once it does, this becomes the permanent regression guarding against the
surface regressing to path/verdict/axis/exit alone.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    block,
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
            "design_facts": {
                "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": ["one opaque semantic decision"],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": verification,
                "oracle_verification_index": 0,
            },
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
    assert code == 0, out + err
    return out, err


def oracle_red_lines(terminal: str) -> list[str]:
    return [line for line in terminal.splitlines() if line.startswith("ORACLE-RED: ")]


def test_the_two_native_refusals_are_admitted_and_equally_classified(
    root: Path, step, another
) -> None:
    """CONTROL, over the unmodified surface: both arms stay ADMITTED alike.

    Fixing the diagnostic must never move either arm off `Success`, off
    `verdict=indeterminate` or off `axis=exit-status-only` -- ADR-DES-003's own
    routing for an oracle that only offers an exit observation is untouched by
    this change (mirrors `test_a_vector_that_asked_for_no_report_keeps_exit_status_only`).
    """
    alpha_out, alpha_err = measure(root, step, ALPHA_ORACLE)
    other_root, other_step, _ = another()
    beta_out, beta_err = measure(other_root, other_step, BETA_ORACLE)

    for out, err in ((alpha_out, alpha_err), (beta_out, beta_err)):
        lines = block(out, err)
        assert lines["DELIVERY-OUTCOME"] == "Success", lines
        assert "verdict=indeterminate" in lines["ORACLE-RED"], lines["ORACLE-RED"]
        assert "axis=exit-status-only" in lines["ORACLE-RED"], lines["ORACLE-RED"]
        assert "exit=2" in lines["ORACLE-RED"], lines["ORACLE-RED"]


def test_the_two_native_refusals_are_distinguishable_in_the_terminal(
    root: Path, step, another
) -> None:
    """RED against the unmodified `_oracle_red_facts`; GREEN once it prints the
    already-measured diagnostic.

    `path`, `verdict`, `axis` and `exit` are IDENTICAL between the two arms by
    construction (same oracle path constant, same verdict/axis pair, same
    exit code) -- the two ORACLE-RED lines below can differ ONLY if the
    already-computed per-item `diagnostic` (or an equivalent already-measured
    fact) reaches the public terminal.
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

    assert alpha_lines[0] != beta_lines[0], (
        "the two ORACLE-RED lines are identical even though the underlying "
        f"native subprocesses refused for different, already-measured reasons:"
        f"\nALPHA: {alpha_lines[0]}\nBETA:  {beta_lines[0]}"
    )
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

    diagnostic = line.split("diagnostic=", 1)[1]
    decoded = json.loads(diagnostic)
    assert "\x1b" in decoded
    assert "ORACLE-RED: forged" in decoded


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
