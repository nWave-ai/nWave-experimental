"""Owner-bound application service for the mutating public update journey."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal


if TYPE_CHECKING:
    from packaging.version import Version

from des.adapters.driven.package_managers.package_manager_detector import (
    PMBackend,
    detect_running_interpreter_owner,
)


UpdateState = Literal["succeeded", "up-to-date", "refused"]
_PROCESS_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class UpdateResult:
    """Immutable public outcome of one update application attempt."""

    state: UpdateState
    version: Version | None
    completed_stages: tuple[str, ...] = ()
    failed_stage: str | None = None
    command: tuple[str, ...] = ()
    cause: str = ""


class UpdateService:
    """Run replacement, proof, synchronization, and migration fail-closed."""

    def __init__(self, interpreter: Path | None = None) -> None:
        self._interpreter = interpreter or Path(sys.executable)

    def apply(
        self,
        *,
        current_version: Version,
        discovered_version: Version,
        root: Path,
    ) -> UpdateResult:
        """Apply a newer release only when its running-install owner is known."""
        if discovered_version <= current_version:
            return UpdateResult(state="up-to-date", version=discovered_version)

        owner = detect_running_interpreter_owner(self._interpreter)
        if owner == "unknown":
            return UpdateResult(
                state="refused",
                version=discovered_version,
                cause=(
                    "the package owner of the running interpreter is unknown; "
                    "choosing an installer from PATH is unsafe"
                ),
            )

        console = self._interpreter.with_name("nwave-ai")
        proof_command = (str(console), "--version")
        if not console.is_file() or not os.access(console, os.X_OK):
            return self._refusal(
                "verify-executable",
                proof_command,
                "the owned nwave-ai console sibling is missing or is not executable",
            )

        replacement = self._replacement_command(owner, discovered_version)
        result = self._run_stage("replace-package", replacement)
        if result is not None:
            return result

        result = self._run_stage(
            "verify-executable",
            proof_command,
            expected_version=discovered_version,
        )
        if result is not None:
            return result

        synchronization = (str(console), "install", "--yes")
        result = self._run_stage("synchronize-framework", synchronization)
        if result is not None:
            return result

        migration = ("des", "update", "--apply", "--root", str(root))
        result = self._run_stage("migrate-artifacts", migration)
        if result is not None:
            return result

        return UpdateResult(
            state="succeeded",
            version=discovered_version,
            completed_stages=(
                "replace-package",
                "verify-executable",
                "synchronize-framework",
                "migrate-artifacts",
            ),
        )

    def _replacement_command(
        self, owner: PMBackend, version: Version
    ) -> tuple[str, ...]:
        package = f"nwave-ai=={version}"
        if owner == "uv":
            return ("uv", "tool", "install", "--reinstall", package)
        if owner == "pipx":
            return ("pipx", "install", "--force", package)
        # ``pip`` ownership can only originate from the detector's explicit
        # override; executing through the owned interpreter preserves that bind.
        return (str(self._interpreter), "-m", "pip", "install", "--upgrade", package)

    def _run_stage(
        self,
        stage: str,
        command: tuple[str, ...],
        *,
        expected_version: Version | None = None,
    ) -> UpdateResult | None:
        try:
            completed = subprocess.run(
                list(command),
                check=False,
                capture_output=True,
                text=True,
                timeout=_PROCESS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return self._refusal(stage, command, "timed out")
        except OSError as exc:
            return self._refusal(stage, command, str(exc))

        if completed.returncode != 0:
            output = (completed.stderr or completed.stdout or "").strip()
            cause = f"exit {completed.returncode}"
            if output:
                cause = f"{cause}: {output}"
            return self._refusal(stage, command, cause)

        if expected_version is not None:
            observed = (completed.stdout or "").strip()
            expected = f"nwave-ai {expected_version}"
            if observed != expected:
                return self._refusal(
                    stage,
                    command,
                    f"expected {expected!r}, observed {observed!r}",
                )
        return None

    @staticmethod
    def _refusal(stage: str, command: tuple[str, ...], cause: str) -> UpdateResult:
        return UpdateResult(
            state="refused",
            version=None,
            failed_stage=stage,
            command=command,
            cause=cause,
        )
