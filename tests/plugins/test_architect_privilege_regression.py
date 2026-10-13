"""Maintainers retain restricted architect Write without granting Edit.

@contract-shape: real-io
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_maintainer_accepts_all_managed_role_tool_contracts():
    """The existing four-role check accepts permitted Write and excludes Edit."""
    environment = os.environ.copy()
    environment.pop("CI", None)
    result = subprocess.run(
        [
            "python3",
            "-m",
            "pytest",
            "tests/plugins/test_agent_frontmatter.py::TestAgentFrontmatterAcceptance::test_managed_roles_declare_least_privilege_tools",
            "-q",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"WHAT: managed-role check exited {result.returncode}, expected 0. "
        "WHY: permitted architect Write must pass without granting Edit or changing "
        "the other managed roles. HOW: align only the architect expected tool list "
        f"with its existing six declared tools.\n{output}"
    )
    payloads = [
        line.partition("NWAVE_TEST_RESULT:")[2]
        for line in result.stdout.splitlines()
        if "NWAVE_TEST_RESULT:" in line
    ]
    try:
        results = [json.loads(payload) for payload in payloads]
    except json.JSONDecodeError as error:
        pytest.fail(
            f"WHAT: the managed-role check emitted unreadable native JSON: {error}. "
            "WHY: an unreadable result cannot establish that all four roles passed. "
            "HOW: restore the native NWAVE_TEST_RESULT JSON emission."
            f"\n{output}"
        )
    expected_result = {
        "passed": 4,
        "failed": 0,
        "skipped": 0,
        "xfailed": 0,
        "exit_status": 0,
    }
    passed = (
        len(results) == 1
        and isinstance(results[0], dict)
        and all(results[0].get(key) == value for key, value in expected_result.items())
    )
    assert passed, (
        f"WHAT: managed-role native results are {results!r}; expected one result "
        f"containing {expected_result!r}. "
        "WHY: the population is architect, product owner, acceptance reviewer and "
        "user examiner; none may be silently deselected, skipped or unexecuted. "
        "HOW: retain the complete existing managed-role parametrization and "
        f"native NWAVE_TEST_RESULT JSON emission.\n{output}"
    )


def test_architect_keeps_existing_declared_tools():
    """Removing Write or granting Edit cannot make the repair pass."""
    role = PROJECT_ROOT / "nWave/agents/nw-solution-architect.md"
    frontmatter = role.read_text(encoding="utf-8").split("---", 2)[1]
    tools_lines = [
        line for line in frontmatter.splitlines() if line.startswith("tools:")
    ]
    assert tools_lines == ["tools: Read, Write, Glob, Grep, Bash, StructuredOutput"], (
        f"WHAT: architect tool declaration changed to {tools_lines!r}. "
        "WHY: the accepted capability includes Write but never Edit. "
        "HOW: preserve the original tools line and repair the check, not the role."
    )


def test_architect_rationale_reserves_document_writes_to_des():
    """The rationale limits Write to cited external formal sources."""
    source = (PROJECT_ROOT / "tests/plugins/test_agent_frontmatter.py").read_text(
        encoding="utf-8"
    )
    rationale = (
        "            # DES owns architecture-document writes; the architect has no Edit.\n"
        "            # Write is restricted to external formal model/proof source files\n"
        "            # cited by Model.source, not authority, handover or oracle files.\n"
    )
    assert rationale in source, (
        "WHAT: the exact three-line restricted-Write rationale is missing. "
        "WHY: permitting Write must not transfer authority, handover or oracle "
        "document ownership from DES. HOW: replace only the stale architect "
        "rationale with the three approved sibling comment lines."
    )
