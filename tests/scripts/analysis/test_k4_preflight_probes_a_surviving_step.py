"""The preflight's runtime probe must interrogate a STEP, and decide on output.

ADR-SSOT-002 Section 4b retires `des dispatch` as an orchestrator; the delivery
shape is the invocable steps. A preflight keyed to `des dispatch --help` was
measuring the surface that is going away, and it decided on nothing but an exit
code -- so a `des` that accepted the word and printed anything at all passed.

Three properties, each falsified here against a real console script the test
writes and the probe really executes. No model call, no network, no install.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.analysis.k4 import preflight


#: A step terminal, as `des.cli.step_terminal.render` writes it for `des state`
#: on a root nothing has been decomposed in.
_STEP_TERMINAL = "\n".join(
    (
        "DELIVERY-OUTCOME: Success",
        "REQUEST: (none)",
        "NEXT: des po --repo-root {root} -- one Request on stdin",
        "HOW-TO-INVOKE: every DES step is invoked alone",
    )
)


def _install_fake_des(workspace: Path, body: str) -> Path:
    """Write an executable `des` exactly where the arm's PATH puts the real one."""
    binary = workspace / ".claude-k4" / "bin" / "des"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text(body, encoding="utf-8")
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return binary


def _script(printed: str, exit_code: int = 0) -> str:
    return (
        "#!/usr/bin/env python3\n"
        "import sys\n"
        f"sys.stdout.write({printed!r})\n"
        f"raise SystemExit({exit_code})\n"
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "probe-nwave"
    root.mkdir()
    return root


class TestTheProbeInterrogatesTheStepSurface:
    def test_it_invokes_a_surviving_step_and_never_the_retired_composer(
        self, workspace: Path
    ) -> None:
        """The argv itself is the claim: `des dispatch` must not appear in it."""
        recorder = workspace / "argv.txt"
        _install_fake_des(
            workspace,
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"open({str(recorder)!r}, 'w').write('\\n'.join(sys.argv[1:]))\n"
            f"sys.stdout.write({_STEP_TERMINAL!r})\n",
        )

        problems = preflight.probe_installed_step_surface(workspace, workspace)

        assert problems == []
        recorded = recorder.read_text(encoding="utf-8").splitlines()
        assert recorded[0] == preflight._STEP_PROBE
        assert "dispatch" not in recorded

    def test_the_probed_step_is_read_only(self) -> None:
        """A probe that bought a turn or wrote a byte would not be free to run.

        Pinned as a NAME rather than as behaviour on purpose: the probe cannot
        observe the installed runtime's read-onlyness, so the property it really
        relies on is that it chose the step ADR-SSOT-002 Section 4b calls "the
        read-only projection". A later edit pointing it at `des craft` would buy
        a provider turn in the preflight, and this is where that is caught.
        """
        assert preflight._STEP_PROBE == "state"


class TestWhatTheProbeRefuses:
    def test_a_runtime_without_the_step_surface_is_a_problem(
        self, workspace: Path
    ) -> None:
        """argparse's `invalid choice` is a `des` that is not the expected one."""
        _install_fake_des(
            workspace,
            _script("des: error: argument subcommand: invalid choice: 'state'", 2),
        )

        problems = preflight.probe_installed_step_surface(workspace, workspace)

        assert problems
        assert "exited 2" in problems[0]

    def test_a_console_script_that_crashes_before_argument_parsing_is_a_problem(
        self, workspace: Path
    ) -> None:
        """The original shebang/PATH class, unchanged by the move to steps."""
        _install_fake_des(
            workspace,
            _script("ModuleNotFoundError: No module named 'des'\n", 1),
        )

        problems = preflight.probe_installed_step_surface(workspace, workspace)

        assert any("Python failure marker" in problem for problem in problems)

    def test_exit_zero_without_the_step_grammar_is_a_problem(
        self, workspace: Path
    ) -> None:
        """The half an exit code cannot decide.

        A `des` that accepts the word `state` and prints something else is not
        the runtime this arm measures. Deciding on the exit code alone admits
        it, which is exactly what the retired `--help` probe did.
        """
        _install_fake_des(workspace, _script("state: ok\n", 0))

        problems = preflight.probe_installed_step_surface(workspace, workspace)

        assert problems
        assert "step grammar" in problems[0]

    @pytest.mark.parametrize("absent", preflight._STEP_TERMINAL_ROWS)
    def test_every_declared_terminal_row_is_load_bearing(
        self, workspace: Path, absent: str
    ) -> None:
        """Drop any one row and the probe must still refuse -- no vacuous member."""
        partial = "\n".join(
            line for line in _STEP_TERMINAL.splitlines() if not line.startswith(absent)
        )
        _install_fake_des(workspace, _script(partial + "\n", 0))

        problems = preflight.probe_installed_step_surface(workspace, workspace)

        assert problems, f"the probe admitted a terminal missing {absent!r}"

    def test_an_absent_console_script_is_a_problem_and_never_an_exception(
        self, workspace: Path
    ) -> None:
        problems = preflight.probe_installed_step_surface(workspace, workspace)

        assert problems
        assert "exited 127" in problems[0]


class TestTheEngagementVerdictNamesTheStepSurface:
    def test_the_verdict_that_reports_it_is_wired_to_the_new_probe(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """`probe_engagement` must reach `broken-steps`, not a dead designation."""
        monkeypatch.setattr(preflight, "nwave_setup_steps", lambda venv, auth: [])
        monkeypatch.setattr(
            preflight,
            "probe_installed_step_surface",
            lambda *a, **k: ["the installed des does not carry the steps"],
        )

        verdict, detail = preflight.probe_engagement(
            tmp_path / "root", tmp_path / "venv", tmp_path / "auth"
        )

        assert verdict == "broken-steps"
        assert detail == ["the installed des does not carry the steps"]

    def test_the_filesystem_policy_verdict_stops_before_any_delivery_probe(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An invalid rendered policy must refuse before arms.json/model delivery."""
        monkeypatch.setattr(preflight, "nwave_setup_steps", lambda venv, auth: [])
        monkeypatch.setattr(preflight, "probe_installed_step_surface", lambda *a: [])
        monkeypatch.setattr(preflight, "probe_project_activation", lambda *a: [])
        monkeypatch.setattr(
            preflight, "probe_launcher_is_inside_the_workspace", lambda *a: []
        )
        monkeypatch.setattr(
            preflight,
            "probe_sandbox_filesystem_policy",
            lambda *a: ["denyWrite resolves outside CLAUDE_CONFIG_DIR"],
        )
        monkeypatch.setattr(
            preflight,
            "probe_sandbox_allows_the_model_api",
            lambda *a: (_ for _ in ()).throw(AssertionError("must not run")),
        )

        verdict, detail = preflight.probe_engagement(
            tmp_path / "root", tmp_path / "venv", tmp_path / "auth"
        )

        assert verdict == "sandbox-filesystem-policy-invalid"
        assert detail == ["denyWrite resolves outside CLAUDE_CONFIG_DIR"]

    def test_the_filesystem_policy_refusal_precedes_arms_and_delivery(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture,
    ) -> None:
        """The distinct verdict must stop the full preflight before either output."""
        root = tmp_path / "campaign"
        task = tmp_path / "task.md"
        task.write_text("finite request\n", encoding="utf-8")
        wheel = tmp_path / "nwave.whl"
        wheel.write_bytes(b"wheel")
        monkeypatch.setattr(
            preflight.sut_mirror,
            "resolve_subject_source",
            lambda path: SimpleNamespace(source="subject", detail="test subject"),
        )
        monkeypatch.setattr(preflight, "missing_sandbox_prerequisites", lambda: [])
        monkeypatch.setattr(
            preflight, "resolve_clean_commit_sha", lambda checkout: "a" * 40
        )
        monkeypatch.setattr(
            preflight,
            "build_arm_runtime",
            lambda output, checkout: (output / "venv", wheel),
        )
        monkeypatch.setattr(preflight, "control_setup_steps", lambda auth: [])
        monkeypatch.setattr(preflight, "nwave_setup_steps", lambda venv, auth: [])
        monkeypatch.setattr(preflight, "treatment_steps", lambda venv: [])
        monkeypatch.setattr(
            preflight, "refuse_undeclared_arm_footprint", lambda *a, **k: 0
        )
        monkeypatch.setattr(
            preflight,
            "probe_engagement",
            lambda root, venv, auth: (
                "sandbox-filesystem-policy-invalid",
                ["denyWrite resolves outside CLAUDE_CONFIG_DIR"],
            ),
        )
        monkeypatch.setattr(
            preflight,
            "delivery_argv",
            lambda model: (_ for _ in ()).throw(AssertionError("must not deliver")),
        )

        assert (
            preflight.main(
                [
                    "--root",
                    str(root),
                    "--checkout",
                    str(tmp_path),
                    "--task-file",
                    str(task),
                ]
            )
            == 1
        )

        assert not (root / "arms.json").exists()
        assert "sandbox filesystem policy" in capsys.readouterr().err


class TestTheTwoArmsAreSymmetric:
    """The pair must differ in the treatment and in nothing else.

    ADR-SSOT-002 Section 4b makes the treatment an LLM that invokes the DES
    steps, so both arms are the same agent invocation and the one declared
    difference is a setup step. A harness that timed a `des` command on one side
    would measure the launcher, not nWave.
    """

    def test_both_arms_declare_the_same_timed_invocation(self) -> None:
        assert preflight.delivery_argv("claude-opus-5") == preflight.delivery_argv(
            "claude-opus-5"
        )

    def test_the_timed_invocation_names_no_des_command(self) -> None:
        """The falsifier for the whole move: a `des` word here is the old shape."""
        argv = preflight.delivery_argv("claude-opus-5")

        assert argv[0] == "claude"
        assert not [word for word in argv if word == "des" or word.endswith("/des")]
        assert "dispatch" not in argv

    def test_the_treatment_is_exactly_its_declared_setup_steps(self) -> None:
        """Install AND enable, both declared, and nothing beyond them.

        Installing alone leaves activation opt-in and unset, so the gate exits
        before every hook and the arm carries nWave without running it --
        measured on a real arm workspace 2026-09-13. The guarantee this check
        holds is that the arms differ only in the treatment, never that the
        treatment is one command.
        """
        steps = preflight.treatment_steps(Path("/venv"))
        declared = (
            preflight.TREATMENT_INSTALL_STEP,
            preflight.TREATMENT_ENABLE_STEP,
            preflight.treatment_launcher_link_step(),
        )

        assert len(steps) == len(declared)
        for step, expected in zip(steps, declared, strict=True):
            assert step[1:] == list(expected[1:])
            assert Path(step[0]).name == expected[0]


class TestTheAdmissionGateChecksThatSymmetry:
    """The gate reads what the campaign RECORDED, never what a preflight meant."""

    @staticmethod
    def _campaign(
        tmp_path, *, treatment_argv, control_argv, treatment_setup, control_setup
    ):
        import json

        root = tmp_path / "campaign"
        root.mkdir(exist_ok=True)
        (root / "campaign.json").write_text(
            json.dumps(
                {
                    "arms": {
                        "nwave": {"argv": treatment_argv, "setup": treatment_setup},
                        "control": {"argv": control_argv, "setup": control_setup},
                    }
                }
            ),
            encoding="utf-8",
        )
        return root

    _AGENT = ["claude", "-p", "--output-format", "json"]
    _INSTALL = [["/venv/bin/nwave-ai", "install", "--platform", "claude-code"]]
    _CLONE = [["git", "clone", "url", "."]]

    def test_a_symmetric_pair_is_admitted(self, tmp_path) -> None:
        from scripts.analysis.k4 import admission_verdict

        campaign = self._campaign(
            tmp_path,
            treatment_argv=self._AGENT,
            control_argv=self._AGENT,
            treatment_setup=self._CLONE + self._INSTALL,
            control_setup=self._CLONE,
        )

        paired, why = admission_verdict._arms_are_a_pair(campaign, None, None)

        assert paired, why

    def test_different_invocations_are_refused(self, tmp_path) -> None:
        """The old shape -- a `des` command on one arm -- must not be admitted."""
        from scripts.analysis.k4 import admission_verdict

        campaign = self._campaign(
            tmp_path,
            treatment_argv=["/w/.claude-k4/bin/des", "dispatch", "--json"],
            control_argv=self._AGENT,
            treatment_setup=self._CLONE + self._INSTALL,
            control_setup=self._CLONE,
        )

        paired, why = admission_verdict._arms_are_a_pair(campaign, None, None)

        assert not paired
        assert "DIFFERENT timed invocations" in why

    def test_a_treatment_that_never_installed_nwave_is_refused(self, tmp_path) -> None:
        """Vanilla against vanilla, reported as nWave against vanilla."""
        from scripts.analysis.k4 import admission_verdict

        campaign = self._campaign(
            tmp_path,
            treatment_argv=self._AGENT,
            control_argv=self._AGENT,
            treatment_setup=self._CLONE,
            control_setup=self._CLONE,
        )

        paired, why = admission_verdict._arms_are_a_pair(campaign, None, None)

        assert not paired
        assert "never installed" in why or "never runs" in why

    def test_a_control_that_also_installed_nwave_is_refused(self, tmp_path) -> None:
        """Both arms treated is not a comparison."""
        from scripts.analysis.k4 import admission_verdict

        campaign = self._campaign(
            tmp_path,
            treatment_argv=self._AGENT,
            control_argv=self._AGENT,
            treatment_setup=self._CLONE + self._INSTALL,
            control_setup=self._CLONE + self._INSTALL,
        )

        paired, why = admission_verdict._arms_are_a_pair(campaign, None, None)

        assert not paired
        assert "no control" in why

    def test_an_unreadable_campaign_is_refused_and_never_raises(self, tmp_path) -> None:
        from scripts.analysis.k4 import admission_verdict

        paired, why = admission_verdict._arms_are_a_pair(tmp_path, None, None)

        assert not paired
        assert "two readable arms" in why


def test_the_probe_runs_under_the_one_rendered_arm_env(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Row 22's rule: no call site builds its own env dict.

    Observed rather than read: the fake `des` writes back the value of a
    variable only `_arm_env` declares, so a hand-rolled `{**os.environ, ...}`
    inside the probe would leave it unset and fail here.
    """
    seen = workspace / "env.txt"
    _install_fake_des(
        workspace,
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        f"open({str(seen)!r}, 'w').write(os.environ.get('CLAUDE_CONFIG_DIR', ''))\n"
        f"sys.stdout.write({_STEP_TERMINAL!r})\n",
    )
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)

    preflight.probe_installed_step_surface(workspace, workspace)

    assert seen.read_text(encoding="utf-8") == str(workspace / ".claude-k4")
    assert os.environ.get("CLAUDE_CONFIG_DIR") is None
