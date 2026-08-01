"""Release-shaped, installed-artifact composition for the sole walking skeleton."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .composition import provision_feature_plan
from .domain_types import CommandObservation


@dataclass(frozen=True)
class InstalledSchedulerRun:
    """What the installed candidate answered, and what the project looked like."""

    help: CommandObservation
    first: CommandObservation
    second: CommandObservation
    before: tuple[tuple[str, bytes], ...]
    after: tuple[tuple[str, bytes], ...]
    answering_module_path: str


@dataclass
class InstalledCandidateComposition:
    project_root: Path
    venv_root: Path

    @property
    def executable(self) -> Path:
        candidates = (
            self.venv_root / "bin" / "des",
            self.venv_root / "Scripts" / "des.exe",
            self.venv_root / "Scripts" / "des",
        )
        return next(
            (candidate for candidate in candidates if candidate.is_file()),
            candidates[0],
        )

    def provision_project(self) -> None:
        provision_feature_plan(self.project_root)

    def invoke_public_surface(self) -> InstalledSchedulerRun:
        before = self._snapshot()
        # No PYTHONPATH, no developer HOME, no PATH beyond the candidate's own
        # bin: the answer must come from the installed artifact alone.
        strict_env = {
            "HOME": str(self.project_root / ".home"),
            "PATH": str(self.executable.parent),
            "DES_PROJECT_DIR": str(self.project_root),
        }
        if os.name == "nt" and "SystemRoot" in os.environ:
            strict_env["SystemRoot"] = os.environ["SystemRoot"]
        observations = [
            self._run(args, strict_env)
            for args in (
                ("--help",),
                ("schedule", "--feature-id", "scheduler-demo", "--format", "json"),
                ("schedule", "--feature-id", "scheduler-demo", "--format", "json"),
            )
        ]
        return InstalledSchedulerRun(
            *observations,
            before=before,
            after=self._snapshot(),
            answering_module_path=self._answering_module_path(strict_env),
        )

    def _answering_module_path(self, env: dict[str, str]) -> str:
        """Ask the candidate itself where the code that answered actually lives.

        Asserting that the test omitted PYTHONPATH would only restate the
        test's own setup. Asking the installed interpreter for the resolved
        module file is a fact about the artifact under test, so a candidate
        that silently answered from the source checkout is detectable.
        """
        python = self.venv_root / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        if not python.is_file():
            return ""
        completed = subprocess.run(
            [
                str(python),
                "-c",
                "import des, sys; sys.stdout.write(des.__file__ or '')",
            ],
            cwd=self.project_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return completed.stdout.strip()

    def _run(self, args: tuple[str, ...], env: dict[str, str]) -> CommandObservation:
        if not self.executable.is_file():
            return CommandObservation(
                127, "", f"installed command not found: {self.executable}"
            )
        completed = subprocess.run(
            [str(self.executable), *args],
            cwd=self.project_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return CommandObservation(
            completed.returncode, completed.stdout, completed.stderr
        )

    def _snapshot(self) -> tuple[tuple[str, bytes], ...]:
        return tuple(
            (str(path.relative_to(self.project_root)), path.read_bytes())
            for path in sorted(self.project_root.rglob("*"))
            if path.is_file()
        )

    @staticmethod
    def event(observation: CommandObservation) -> dict[str, object]:
        for line in observation.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                return event
        raise AssertionError(
            "WHAT: the installed command emitted no lane-snapshot JSON event; "
            "WHY: an in-checkout dispatcher cannot substitute for the assembled "
            "candidate a user actually receives; "
            "HOW: include and register the scheduler in the release-shaped wheel. "
            f"Captured exit={observation.exit_code}, stderr={observation.stderr!r}."
        )
