"""Unit tests for des.cli.health_check CLI module.

Tests the health_check CLI tool that runs diagnostic checks on the nWave
installation and reports status with exit codes.

Test Budget: 4 behaviors x 2 = 8 unit tests max.

Behaviors:
1. All checks pass -> exit 0, HEALTHY status, all checks reported
2. Any check fails -> exit 1, UNHEALTHY status
3. --json flag -> JSON output with status/checks/version
4. Individual check failure does not block other checks
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def healthy_environment(tmp_path):
    """Set up a mock environment where all 7 checks pass."""
    version_dir = tmp_path / "version_dir"
    version_dir.mkdir()
    version_file = version_dir / "VERSION"
    version_file.write_text("2.5.1\n")

    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "step-tdd-cycle-schema.json").write_text("{}")

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    for i in range(3):
        (agents_dir / f"nw-agent-{i}.md").write_text("")

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    for i in range(5):
        skill_dir = skills_dir / f"nw-skill-{i}"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("")

    return {
        "version_file": version_file,
        "templates_dir": templates_dir,
        "logs_dir": logs_dir,
        "agents_dir": agents_dir,
        "skills_dir": skills_dir,
    }


class TestHealthCheckAllPass:
    """When all checks pass, health_check exits 0 and reports HEALTHY."""

    def test_exits_zero_and_reports_healthy_when_all_checks_pass(
        self, healthy_environment, tmp_path, capsys
    ):
        from des.cli.health_check import main

        result = main(
            [],
            version_file=healthy_environment["version_file"],
            templates_dir=healthy_environment["templates_dir"],
            logs_dir=healthy_environment["logs_dir"],
            agents_dir=healthy_environment["agents_dir"],
            skills_dir=healthy_environment["skills_dir"],
        )

        assert result == 0

        captured = capsys.readouterr()
        assert "nWave Health Check" in captured.out
        assert "HEALTHY" in captured.out
        assert "7/7" in captured.out
        assert "version" in captured.out
        assert "module_import" in captured.out
        assert "templates" in captured.out
        assert "hook_actions" in captured.out
        assert "log_directory" in captured.out
        assert "agents_installed" in captured.out
        assert "skills_installed" in captured.out


class TestHealthCheckAnyFails:
    """When any check fails, health_check exits 1 and reports UNHEALTHY."""

    def test_exits_one_and_reports_unhealthy_when_version_missing(
        self, healthy_environment, tmp_path, capsys, monkeypatch
    ):
        from des.cli.health_check import main

        # Remove version file to trigger failure
        healthy_environment["version_file"].unlink()
        # Move CWD away from repo to prevent pyproject.toml fallback
        monkeypatch.chdir(tmp_path)

        result = main(
            [],
            version_file=healthy_environment["version_file"],
            templates_dir=healthy_environment["templates_dir"],
            logs_dir=healthy_environment["logs_dir"],
            agents_dir=healthy_environment["agents_dir"],
            skills_dir=healthy_environment["skills_dir"],
        )

        assert result == 1

        captured = capsys.readouterr()
        assert "UNHEALTHY" in captured.out


class TestHealthCheckJsonOutput:
    """--json flag produces machine-readable JSON output."""

    def test_json_flag_produces_valid_json_with_status_and_checks(
        self, healthy_environment, capsys
    ):
        from des.cli.health_check import main

        result = main(
            ["--json"],
            version_file=healthy_environment["version_file"],
            templates_dir=healthy_environment["templates_dir"],
            logs_dir=healthy_environment["logs_dir"],
            agents_dir=healthy_environment["agents_dir"],
            skills_dir=healthy_environment["skills_dir"],
        )

        assert result == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "healthy"
        assert len(data["checks"]) == 7
        assert data["version"] == "2.5.1"
        for check in data["checks"]:
            assert "name" in check
            assert "passed" in check
            assert "detail" in check

    def test_json_output_reports_unhealthy_when_check_fails(
        self, healthy_environment, capsys, monkeypatch
    ):
        from des.cli.health_check import main

        healthy_environment["version_file"].unlink()
        monkeypatch.chdir(healthy_environment["logs_dir"])

        result = main(
            ["--json"],
            version_file=healthy_environment["version_file"],
            templates_dir=healthy_environment["templates_dir"],
            logs_dir=healthy_environment["logs_dir"],
            agents_dir=healthy_environment["agents_dir"],
            skills_dir=healthy_environment["skills_dir"],
        )

        assert result == 1

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "unhealthy"


class TestHealthCheckIsolation:
    """Individual check failure does not block other checks from running."""

    def test_all_seven_checks_reported_even_when_some_fail(
        self, healthy_environment, capsys, monkeypatch
    ):
        from des.cli.health_check import main

        # Break version and templates to cause 2 failures
        healthy_environment["version_file"].unlink()
        (healthy_environment["templates_dir"] / "step-tdd-cycle-schema.json").unlink()
        monkeypatch.chdir(healthy_environment["logs_dir"])

        result = main(
            ["--json"],
            version_file=healthy_environment["version_file"],
            templates_dir=healthy_environment["templates_dir"],
            logs_dir=healthy_environment["logs_dir"],
            agents_dir=healthy_environment["agents_dir"],
            skills_dir=healthy_environment["skills_dir"],
        )

        assert result == 1

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data["checks"]) == 7

        check_names = [c["name"] for c in data["checks"]]
        assert "version" in check_names
        assert "module_import" in check_names
        assert "templates" in check_names
        assert "hook_actions" in check_names
        assert "log_directory" in check_names
        assert "agents_installed" in check_names
        assert "skills_installed" in check_names

        # version and templates should fail, others should pass
        version_check = next(c for c in data["checks"] if c["name"] == "version")
        assert version_check["passed"] is False

        templates_check = next(c for c in data["checks"] if c["name"] == "templates")
        assert templates_check["passed"] is False

        # module_import should still pass
        module_check = next(c for c in data["checks"] if c["name"] == "module_import")
        assert module_check["passed"] is True
