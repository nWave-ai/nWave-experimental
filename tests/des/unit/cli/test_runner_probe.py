"""Unit tests for des.cli.runner_probe CLI module.

QW5 (mikado.md:47): `des runner-probe` reports supported/unsupported/
indeterminate per declared runner against the live environment. Tests drive
the CLI's `main()` in-process with a monkeypatched probe function, so the
suite's assertions are about the CLI's OWN contract (argv parsing, exit code,
human/JSON rendering) and never about what happens to be installed on the
box running the suite -- `probe_all_runner_capabilities` itself is unit
tested separately in `test_runner_capability_probe.py`.

Behaviors:
1. default invocation -> exit 0, human-readable report on stdout
2. --json -> valid JSON with a `runners` list mirroring the probed results
3. --target-root is threaded through to the probe function
4. remediation line is rendered for a non-supported runner
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.runner.runner_capability_probe import RunnerCapability
from des.cli import runner_probe


_FAKE_RESULTS = (
    RunnerCapability(
        runner="pytest", status="supported", evidence="resolved interpreter: /x/py"
    ),
    RunnerCapability(
        runner="cargo-test",
        status="unsupported",
        evidence="'cargo' not found (rung: not-found)",
        remediation="install cargo via rustup",
    ),
)


@pytest.fixture(autouse=True)
def _stub_probe(monkeypatch):
    calls: list[Path | None] = []

    def _fake_probe(target_root=None):
        calls.append(target_root)
        return _FAKE_RESULTS

    monkeypatch.setattr(runner_probe, "probe_all_runner_capabilities", _fake_probe)
    return calls


class TestRunnerProbeHumanOutput:
    def test_default_invocation_exits_zero_and_reports(self, capsys, _stub_probe):
        exit_code = runner_probe.main([])

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "pytest" in out
        assert "SUPPORTED" in out
        assert "cargo-test" in out
        assert "UNSUPPORTED" in out

    def test_remediation_is_rendered_for_non_supported_runner(
        self, capsys, _stub_probe
    ):
        runner_probe.main([])

        out = capsys.readouterr().out
        assert "install cargo via rustup" in out

    def test_summary_line_counts_each_status(self, capsys, _stub_probe):
        runner_probe.main([])

        out = capsys.readouterr().out
        assert "1 supported" in out
        assert "1 unsupported" in out
        assert "0 indeterminate" in out


class TestRunnerProbeJsonOutput:
    def test_json_flag_emits_valid_json_with_runners_list(self, capsys, _stub_probe):
        exit_code = runner_probe.main(["--json"])

        assert exit_code == 0
        payload = json.loads(capsys.readouterr().out)
        assert "runners" in payload
        assert len(payload["runners"]) == 2
        assert payload["runners"][0]["runner"] == "pytest"
        assert payload["runners"][0]["status"] == "supported"
        assert payload["runners"][1]["remediation"] == "install cargo via rustup"


class TestRunnerProbeTargetRoot:
    def test_target_root_is_threaded_to_probe_function(self, tmp_path, _stub_probe):
        runner_probe.main(["--target-root", str(tmp_path)])

        assert _stub_probe[-1] == tmp_path

    def test_no_target_root_passes_none(self, _stub_probe):
        runner_probe.main([])

        assert _stub_probe[-1] is None
