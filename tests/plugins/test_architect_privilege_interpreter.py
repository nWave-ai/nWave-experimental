"""Developers retain managed-role checks with the running interpreter.

@contract-shape: real-io
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_managed_role_regression_uses_running_interpreter_without_venv_on_path(
    tmp_path,
):
    """The supported local run executes all four roles in this Python."""
    records = tmp_path / "records"
    records.mkdir()
    (tmp_path / "architect_interpreter_recorder.py").write_text(
        "import json\nimport os\nimport sys\nfrom pathlib import Path\n\n"
        "def pytest_sessionfinish(session, exitstatus):\n"
        '    if any("test_managed_roles_declare_least_privilege_tools" in str(arg)\n'
        "           for arg in session.config.args):\n"
        '        record = {"executable": sys.executable,\n'
        '                  "collected": session.testscollected,\n'
        '                  "failed": session.testsfailed, "exit": int(exitstatus)}\n'
        '        directory = Path(os.environ["ARCHITECT_INTERPRETER_RECORD_DIR"])\n'
        '        (directory / f"{os.getpid()}.json").write_text(\n'
        '            json.dumps(record), encoding="utf-8")\n',
        encoding="utf-8",
    )
    environment = os.environ.copy()
    # Outer runner instrumentation must not leak plugins or JUnit destinations
    # into the independently observed child sessions.
    for name in (
        "CI",
        "NWAVE_TEST_RESULT_FILE",
        "NWAVE_TEST_DURATIONS_FILE",
        "PYTEST_ADDOPTS",
    ):
        environment.pop(name, None)
    environment["PATH"] = "/usr/bin:/bin"
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(tmp_path), environment.get("PYTHONPATH", "")) if part
    )
    environment["PYTEST_PLUGINS"] = "architect_interpreter_recorder"
    environment["ARCHITECT_INTERPRETER_RECORD_DIR"] = str(records)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/plugins/test_architect_privilege_regression.py",
            "tests/plugins/test_agent_frontmatter.py",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    output = result.stdout + result.stderr
    record_paths = list(records.glob("*.json"))
    assert result.returncode == 0, (
        f"WHAT: supported local regression exited {result.returncode}, expected 0; "
        f"nested interpreter records: {record_paths!r}. "
        "WHY: PATH=/usr/bin:/bin must not prevent the existing privilege checks "
        "from running in the project interpreter. HOW: replace only the target's "
        "nested argv[0] with sys.executable and add import sys, preserving its "
        f"selection and assertions.\n{output}"
    )
    payloads = [
        line.partition("NWAVE_TEST_RESULT:")[2]
        for line in result.stdout.splitlines()
        if "NWAVE_TEST_RESULT:" in line
    ]
    try:
        results = [json.loads(payload) for payload in payloads]
        nested_records = [
            json.loads(path.read_text(encoding="utf-8")) for path in record_paths
        ]
    except json.JSONDecodeError as error:
        pytest.fail(
            f"WHAT: observed result or interpreter record is unreadable JSON: {error}. "
            "WHY: the completed role population and interpreter cannot be established. "
            f"HOW: retain native result emission and the session recorder.\n{output}"
        )
    expected = {
        "passed": 12,
        "failed": 0,
        "skipped": 0,
        "xfailed": 0,
        "exit_status": 0,
    }
    assert (
        len(results) == 1
        and isinstance(results[0], dict)
        and all(results[0].get(key) == value for key, value in expected.items())
    ), (
        f"WHAT: child results are {results!r}, expected one containing {expected!r}. "
        "WHY: the population is the unchanged regression and frontmatter files' "
        "12 cases; skipping or deselecting checks must not disguise interpreter failure. "
        f"HOW: preserve both file selections and all existing privilege checks.\n{output}"
    )
    assert "No module named pytest" not in output, (
        "WHAT: child output reports 'No module named pytest'. "
        "WHY: the supported environment must execute the checks, not a PATH-resolved "
        f"Python without pytest. HOW: launch the nested check with sys.executable.\n{output}"
    )
    assert len(nested_records) == 1, (
        f"WHAT: nested-selection records are {nested_records!r}, expected exactly one. "
        "WHY: a successful child alone cannot prove the four-role check actually ran. "
        "HOW: retain the nested four-role selection and launch it with sys.executable."
    )
    expected_record = {
        "executable": sys.executable,
        "collected": 4,
        "failed": 0,
        "exit": 0,
    }
    assert isinstance(nested_records[0], dict) and all(
        nested_records[0].get(key) == value for key, value in expected_record.items()
    ), (
        f"WHAT: nested session is {nested_records[0]!r}, expected {expected_record!r}. "
        "WHY: architect, product owner, acceptance reviewer and user examiner must "
        "all pass in the exact running interpreter, not a PATH Python or a "
        "deselected subset. HOW: use sys.executable without resolving its symlink "
        "and preserve the complete existing four-role selection."
    )
    _assert_privilege_regression_rejects_weakened_contracts(tmp_path)


def _assert_privilege_regression_rejects_weakened_contracts(tmp_path):
    """Privilege violations and incomplete nested results cannot pass the regression."""
    sandbox = tmp_path / "repository"
    sandbox.mkdir()
    for directory in ("scripts", "src", "nWave/agents", "tests/support"):
        shutil.copytree(
            PROJECT_ROOT / directory,
            sandbox / directory,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (sandbox / "tests/plugins").mkdir()
    for filename in (
        "pyproject.toml",
        "tests/__init__.py",
        "tests/conftest.py",
        "tests/plugins/__init__.py",
        "tests/plugins/test_agent_frontmatter.py",
        "tests/plugins/test_architect_privilege_regression.py",
    ):
        shutil.copy2(PROJECT_ROOT / filename, sandbox / filename)

    environment = os.environ.copy()
    for name in (
        "CI",
        "NWAVE_TEST_RESULT_FILE",
        "NWAVE_TEST_DURATIONS_FILE",
        "PYTEST_PLUGINS",
        "PYTEST_ADDOPTS",
    ):
        environment.pop(name, None)
    environment["PATH"] = "/usr/bin:/bin"
    environment["PYTHONPATH"] = str(sandbox / "src")
    initialized = subprocess.run(
        ["git", "-c", "init.templateDir=", "init", "-q", str(sandbox)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert initialized.returncode == 0, (
        f"WHAT: disposable repository initialization exited {initialized.returncode}. "
        "WHY: native test guards require isolated Git state before testing rejection. "
        f"HOW: provide a working git on the declared PATH.\n{initialized.stderr}"
    )
    regression = "tests/plugins/test_architect_privilege_regression.py::"
    managed_check = (
        regression + "test_maintainer_accepts_all_managed_role_tool_contracts"
    )
    tools_check = regression + "test_architect_keeps_existing_declared_tools"
    rationale_check = (
        regression + "test_architect_rationale_reserves_document_writes_to_des"
    )
    scenarios = []
    for agent, tools in (
        (
            "nw-solution-architect",
            "Read, Write, Edit, Glob, Grep, Bash, StructuredOutput",
        ),
        ("nw-solution-architect", "Read, Glob, Grep, Bash, StructuredOutput"),
        ("nw-product-owner", "Read, Edit, StructuredOutput"),
        ("nw-acceptance-designer-reviewer", "Read, Edit, StructuredOutput"),
        ("nw-user-examiner", "Read, StructuredOutput"),
    ):
        role = sandbox / f"nWave/agents/{agent}.md"
        original = role.read_text(encoding="utf-8")
        tools_line = next(
            line for line in original.splitlines() if line.startswith("tools:")
        )
        violated = original.replace(tools_line, f"tools: {tools}", 1)
        scenarios.append(
            (
                f"{agent} tools={tools}",
                role,
                original,
                violated,
                managed_check,
                "WHAT: managed-role check exited 1",
            )
        )
        if agent == "nw-solution-architect":
            scenarios.append(
                (
                    f"architect declaration tools={tools}",
                    role,
                    original,
                    violated,
                    tools_check,
                    "WHAT: architect tool declaration changed",
                )
            )

    frontmatter = sandbox / "tests/plugins/test_agent_frontmatter.py"
    original_frontmatter = frontmatter.read_text(encoding="utf-8")
    scenarios.append(
        (
            "restricted-Write rationale removed",
            frontmatter,
            original_frontmatter,
            original_frontmatter.replace(
                "# DES owns architecture-document writes; the architect has no Edit.",
                "# Restricted-Write rationale deliberately removed for this counterexample.",
                1,
            ),
            rationale_check,
            "WHAT: the exact three-line restricted-Write rationale is missing",
        )
    )

    conftest = sandbox / "tests/conftest.py"
    original_conftest = conftest.read_text(encoding="utf-8")
    emission = "    print(line)\n"
    nested_only = (
        '    if any("test_managed_roles_declare_least_privilege_tools" in str(arg)\n'
        "           for arg in session.config.args):\n"
    )
    for field, incorrect in (
        ("passed", 3),
        ("failed", 1),
        ("skipped", 1),
        ("xfailed", 1),
        ("exit_status", 1),
    ):
        replacement = (
            nested_only + f'        result["{field}"] = {incorrect}\n'
            '        line = "NWAVE_TEST_RESULT:" + json.dumps(result)\n' + emission
        )
        scenarios.append(
            (
                f"nested result {field}={incorrect}",
                conftest,
                original_conftest,
                original_conftest.replace(emission, replacement, 1),
                managed_check,
                "WHAT: managed-role native results",
            )
        )
    for label, replacement, message in (
        (
            "missing",
            nested_only + '        line = "RESULT_WITHHELD"\n' + emission,
            "WHAT: managed-role native results",
        ),
        (
            "duplicate",
            nested_only + "        print(line)\n" + emission,
            "WHAT: managed-role native results",
        ),
        (
            "unreadable",
            nested_only + '        line = "NWAVE_TEST_RESULT:not-json"\n' + emission,
            "WHAT: the managed-role check emitted unreadable native JSON",
        ),
    ):
        scenarios.append(
            (
                f"{label} nested result",
                conftest,
                original_conftest,
                original_conftest.replace(emission, replacement, 1),
                managed_check,
                message,
            )
        )

    # Each counterexample changes disposable input, never the lane's craft target.
    # Select the owning regression alone so a sibling check cannot mask its weakening.
    for label, path, original, violated, selection, message in scenarios:
        path.write_text(violated, encoding="utf-8")
        # Do not reuse bytecode from an earlier counterexample of the same source.
        shutil.rmtree(path.parent / "__pycache__", ignore_errors=True)
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    selection,
                ],
                cwd=sandbox,
                env=environment,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        finally:
            path.write_text(original, encoding="utf-8")
        output = result.stdout + result.stderr
        payloads = re.findall(
            r"^(?:[.FE]+[ \t]+\[[ \t]*\d+%\][ \t]*)?NWAVE_TEST_RESULT:([^\n]*)$",
            result.stdout,
            flags=re.MULTILINE,
        )
        try:
            results = [json.loads(payload) for payload in payloads]
        except json.JSONDecodeError as error:
            pytest.fail(
                f"WHAT: counterexample {label!r} has unreadable outer results: {error}. "
                "WHY: setup failure cannot prove a privilege assertion rejected bad input. "
                f"HOW: preserve native outer-session result emission.\n{output}"
            )
        expected = {
            "passed": 0,
            "failed": 1,
            "skipped": 0,
            "xfailed": 0,
            "exit_status": 1,
        }
        assert (
            result.returncode == 1
            and message in output
            and len(results) == 1
            and isinstance(results[0], dict)
            and all(results[0].get(key) == value for key, value in expected.items())
        ), (
            f"WHAT: counterexample {label!r} exited {result.returncode} with "
            f"{results!r}; expected the single selected regression {selection!r} "
            f"to fail with {message!r} and {expected!r}. "
            "WHY: successful interpreter selection must not conceal weakened "
            "privilege, rationale or complete-four-role result assertions. "
            "HOW: retain the regression's original assertions and reject the "
            f"violated contract rather than skipping checks or accepting bad results.\n{output}"
        )
