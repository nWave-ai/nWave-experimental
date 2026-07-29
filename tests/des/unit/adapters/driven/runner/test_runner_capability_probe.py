"""Unit tests for des.adapters.driven.runner.runner_capability_probe.

QW5 (mikado.md:47): the runner-capability probe must record `supported`,
`unsupported`, or `indeterminate` against the DECLARED (live, probed)
environment -- never inferred from a static reference. Every test here
drives the module against a fully-controlled fake environment (tmp_path
executables + monkeypatch), never the host's actual toolchains, so the
suite's verdict does not depend on what happens to be installed on the box
running it.

Behaviors:
1. binary discovered + version probe exits 0 -> supported
2. binary absent from every discovery rung -> unsupported, remediation set
   via the SPEC's own install_hint threaded into resolve_tool (never
   resolve_tool's tool-agnostic no-hint fallback -- team-lead review
   2026-07-29: `des runner-probe` was reporting `cargo install go` / `cargo
   install vitest` / `cargo install gradlew` / `cargo install mvn`, none of
   which exist. A rejection message that names the wrong fix is worse than
   a bare traceback. Root cause traced one layer down to `resolve_tool`
   itself, fixed there plus at all six call sites.)
3. binary discovered but version probe exits non-zero -> indeterminate
4. binary discovered but version probe raises (timeout/OSError) -> indeterminate
5. pytest routes through python_for -> supported / unsupported
6. probe_all_runner_capabilities returns one entry per declared runner,
   pytest first, in declaration order
7. every declared runner's install_hint names ITS OWN real producer
   (never a shared template) -- this is the regression guard for behavior 2:
   it fails if a future edit collapses the per-runner remediations back to
   one shared string.
"""

from __future__ import annotations

import stat
import sys

from des.adapters.driven.runner import runner_capability_probe as probe_module
from des.adapters.driven.runner.runner_capability_probe import (
    RunnerCapability,
    _probe_binary_capability,
    _probe_pytest_capability,
    _RunnerProbeSpec,
    probe_all_runner_capabilities,
)
from des.runtime.interpreter import InterpreterUnavailable
from des.runtime.spawn import SpawnTimeout


def _write_fake_binary(directory, name: str, script_body: str):
    """Write an executable shell-free fake binary (a Python script with a
    shebang pointed at the running interpreter, so no shell/PATH assumption
    beyond `sys.executable` -- itself a stdlib-only, cross-platform fact)."""
    target = directory / name
    target.write_text(f"#!{sys.executable}\n{script_body}\n")
    target.chmod(target.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return target


class TestProbeBinaryCapabilitySupported:
    def test_binary_found_and_version_succeeds_is_supported(self, tmp_path):
        _write_fake_binary(
            tmp_path, "fake-tool", 'print("fake-tool 1.2.3")\nraise SystemExit(0)'
        )
        spec = _RunnerProbeSpec(
            runner="fake-runner",
            binary="fake-tool",
            known_locations=(".",),
            version_args=("--version",),
            install_hint="unused on the supported path",
        )

        result = _probe_binary_capability(spec, tmp_path)

        assert result.status == "supported"
        assert result.remediation is None
        assert "fake-tool" in result.evidence
        assert "1.2.3" in result.evidence


class TestProbeBinaryCapabilityUnsupported:
    def test_binary_absent_from_every_rung_is_unsupported(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        spec = _RunnerProbeSpec(
            runner="fake-runner",
            binary="definitely-not-a-real-binary-xyz-9182",
            known_locations=(),
            version_args=("--version",),
            install_hint="install fake-tool via the fake-tool installer",
        )

        result = _probe_binary_capability(spec, empty_dir)

        assert result.status == "unsupported"
        assert result.remediation is not None

    def test_unsupported_remediation_carries_the_specs_own_hint_not_a_shared_guess(
        self, tmp_path
    ):
        """The defect this guards (found one layer down, in `resolve_tool`
        itself, by team-lead review 2026-07-29): `resolve_tool`'s OLD default
        remediation was a single template ("install it via rustup or `cargo
        install <name>`") applied identically to every tool it discovers --
        correct only for cargo. Forwarding it verbatim produced FALSE
        remediation (`cargo install go`, which does not exist) for every
        non-cargo runner. The probe must thread the SPEC's own
        install_hint into resolve_tool instead of relying on its
        (now honest-but-generic) no-hint fallback."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        spec = _RunnerProbeSpec(
            runner="fake-runner",
            binary="definitely-not-a-real-binary-xyz-9182",
            known_locations=(),
            version_args=("--version",),
            install_hint="install fake-tool via the fake-tool installer",
        )

        result = _probe_binary_capability(spec, empty_dir)

        assert result.remediation is not None
        assert "install fake-tool via the fake-tool installer" in result.remediation
        assert "cargo install" not in result.remediation


class TestProbeBinaryCapabilityIndeterminate:
    def test_binary_found_but_version_probe_exits_nonzero_is_indeterminate(
        self, tmp_path
    ):
        _write_fake_binary(
            tmp_path,
            "broken-tool",
            'import sys\nsys.stderr.write("permission denied\\n")\nraise SystemExit(1)',
        )
        spec = _RunnerProbeSpec(
            runner="fake-runner",
            binary="broken-tool",
            known_locations=(".",),
            version_args=("--version",),
            install_hint="unused on the indeterminate path",
        )

        result = _probe_binary_capability(spec, tmp_path)

        assert result.status == "indeterminate"
        assert result.remediation is not None
        assert "broken-tool" in result.evidence

    def test_version_probe_raising_spawn_timeout_is_indeterminate(
        self, tmp_path, monkeypatch
    ):
        _write_fake_binary(tmp_path, "slow-tool", "raise SystemExit(0)")
        spec = _RunnerProbeSpec(
            runner="fake-runner",
            binary="slow-tool",
            known_locations=(".",),
            version_args=("--version",),
            install_hint="unused on the indeterminate path",
        )

        def _raise_timeout(argv, **kwargs):
            raise SpawnTimeout(argv, 5.0)

        monkeypatch.setattr(probe_module, "spawn", _raise_timeout)

        result = _probe_binary_capability(spec, tmp_path)

        assert result.status == "indeterminate"
        assert result.remediation is not None

    def test_version_probe_raising_oserror_is_indeterminate(
        self, tmp_path, monkeypatch
    ):
        _write_fake_binary(tmp_path, "denied-tool", "raise SystemExit(0)")
        spec = _RunnerProbeSpec(
            runner="fake-runner",
            binary="denied-tool",
            known_locations=(".",),
            version_args=("--version",),
            install_hint="unused on the indeterminate path",
        )

        def _raise_oserror(argv, **kwargs):
            raise PermissionError("denied")

        monkeypatch.setattr(probe_module, "spawn", _raise_oserror)

        result = _probe_binary_capability(spec, tmp_path)

        assert result.status == "indeterminate"


class TestProbePytestCapability:
    def test_python_for_success_is_supported(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            probe_module,
            "python_for",
            lambda capability, repo_root=None: sys.executable,
        )

        result = _probe_pytest_capability(tmp_path)

        assert result.status == "supported"
        assert result.remediation is None
        assert sys.executable in result.evidence

    def test_interpreter_unavailable_is_unsupported(self, tmp_path, monkeypatch):
        def _raise_unavailable(capability, repo_root=None):
            raise InterpreterUnavailable(capability, probed=["/no/python"])

        monkeypatch.setattr(probe_module, "python_for", _raise_unavailable)

        result = _probe_pytest_capability(tmp_path)

        assert result.status == "unsupported"
        assert result.remediation is not None


class TestProbeAllRunnerCapabilities:
    def test_returns_one_entry_per_declared_runner_pytest_first(self, tmp_path):
        results = probe_all_runner_capabilities(tmp_path)

        assert len(results) == 1 + len(probe_module._PROBE_TABLE)
        assert results[0].runner == "pytest"
        assert all(isinstance(r, RunnerCapability) for r in results)
        runner_names = [r.runner for r in results]
        assert runner_names == [
            "pytest",
            *[s.runner for s in probe_module._PROBE_TABLE],
        ]

    def test_every_result_has_a_declared_status(self, tmp_path):
        results = probe_all_runner_capabilities(tmp_path)

        for result in results:
            assert result.status in ("supported", "unsupported", "indeterminate")

    def test_defaults_target_root_to_cwd(self):
        # No target_root passed -> must not raise, and must resolve against
        # something (cwd), never crash for want of an argument.
        results = probe_all_runner_capabilities()

        assert len(results) == 1 + len(probe_module._PROBE_TABLE)


class TestPerRunnerRemediationNamesCorrectManager:
    """Team-lead review 2026-07-29 (two rounds): `des runner-probe` was
    reporting `cargo install go` / `cargo install vitest` / `cargo install
    gradlew` / `cargo install mvn` as remediation for those runners -- none
    of those commands exist. Round 2 traced the root cause one layer down to
    `tool_discovery.resolve_tool` itself (its old default templated the
    cargo/rustup phrase for EVERY tool), fixed there plus at each of its six
    call sites (this probe module + the five other language-adapter runner
    modules). This class pins each declared runner's install_hint to the
    REAL producer for that ecosystem, so a regression back to one shared
    template (the defect's shape) fails here first.

    RED-verified 2026-07-29: with every `install_hint` in `_PROBE_TABLE`
    temporarily collapsed to the single string
    "install it via rustup or 'cargo install <name>'" (the historical shared
    template), `test_every_remediation_is_distinct` and every
    `test_*_remediation_names_its_own_manager` case below failed. Restoring
    the per-runner strings (now imported from each runner module's own
    `*_INSTALL_HINT` constant) turned the suite green again.
    """

    _EXPECTED_MARKER = {
        "cargo-test": "rustup",
        "go-test": "go.dev",
        "vitest": "devDependency",
        "gradle-test": "GENERATED",
        "dotnet-test": ".NET SDK",
        "maven-test": "Maven",
    }

    def test_every_declared_runner_has_an_expected_marker(self):
        # Guards the guard: a runner added to _PROBE_TABLE without a matching
        # entry here would otherwise pass this class vacuously.
        declared = {spec.runner for spec in probe_module._PROBE_TABLE}
        assert declared == set(self._EXPECTED_MARKER)

    def test_each_remediation_names_its_own_manager(self):
        by_runner = {spec.runner: spec for spec in probe_module._PROBE_TABLE}
        for runner, marker in self._EXPECTED_MARKER.items():
            assert marker in by_runner[runner].install_hint, (
                f"{runner}'s remediation must name its own producer "
                f"(expected {marker!r} in {by_runner[runner].install_hint!r})"
            )

    def test_no_non_cargo_runner_suggests_cargo_install(self):
        for spec in probe_module._PROBE_TABLE:
            if spec.runner == "cargo-test":
                continue
            assert "cargo install" not in spec.install_hint, (
                f"{spec.runner} must not suggest a nonexistent "
                f"`cargo install {spec.binary}`"
            )

    def test_every_remediation_is_distinct(self):
        # The shared-template regression collapses every entry to ONE string;
        # this fails the instant that happens, independent of content.
        remediations = [spec.install_hint for spec in probe_module._PROBE_TABLE]
        assert len(set(remediations)) == len(remediations)

    def test_every_declared_runners_remediation_flows_through_to_the_probe_result(
        self, tmp_path
    ):
        """End-to-end (not just the table): for each declared runner, probing
        an environment where the binary is absent everywhere must surface
        the SAME hint in the returned RunnerCapability.remediation -- proving
        the wiring from spec -> resolve_tool -> result, not merely that the
        table holds the right strings."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        for spec in probe_module._PROBE_TABLE:
            isolated_spec = probe_module._RunnerProbeSpec(
                runner=spec.runner,
                binary="definitely-not-a-real-binary-xyz-9182",
                known_locations=(),
                version_args=spec.version_args,
                install_hint=spec.install_hint,
            )
            result = _probe_binary_capability(isolated_spec, empty_dir)
            assert result.status == "unsupported"
            assert result.remediation is not None
            assert spec.install_hint in result.remediation
