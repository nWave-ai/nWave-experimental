"""Install the OMP protocol shim; guard decisions remain in the Python DES runtime."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

from scripts.install.plugins.base import (
    InstallationPlugin,
    InstallContext,
    PluginResult,
)
from scripts.install.plugins.omp_common import require_default_profile
from scripts.shared.install_paths import (
    omp_skills_dir,
    resolve_des_lib_path_for_spawn,
    resolve_python_command_for_spawn,
)


OMP_GUARD_CEILING = (
    "OMP DES: tool_call can block task, bash, write and edit calls "
    "(path, hashline and apply_patch file headers, including move targets). "
    "Not enforced: unrecognized edit formats, internal URI writes, eval/workpool spawns, "
    "SendMessage and TaskCreate/TaskUpdate (no equivalent tools), "
    "SubagentStop transcript-based checks (no Claude transcript). "
    "Session lifecycle/update admission guards are not enforced by this extension."
)
_TEMPLATE = "omp-des-extension.ts.template"
_SHIM = "nwave-des.ts"
_MANIFEST = ".nwave-des-manifest.json"


def omp_extensions_dir() -> Path:
    return omp_skills_dir().parent / "extensions"


def working_python() -> str:
    candidate = resolve_python_command_for_spawn()
    try:
        result = subprocess.run(
            [
                candidate,
                "-c",
                "import sys; assert sys.version_info >= (3, 10); print(sys.executable)",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError(
            f"WHAT: Python >=3.10 could not run at {candidate!r}. WHY: {error}. "
            "HOW: install Python >=3.10, put it on PATH, and rerun the installer with that interpreter."
        ) from error


class OmpDESPlugin(InstallationPlugin):
    def __init__(self):
        super().__init__("omp-des", priority=55)
        self.dependencies = ["des", "omp-skills"]

    def install(self, context: InstallContext) -> PluginResult:
        try:
            require_default_profile()
            python = working_python()
            runtime = resolve_des_lib_path_for_spawn()
            template = context.framework_source / "templates" / _TEMPLATE
            if not template.is_file():
                template = context.project_root / "nWave/templates" / _TEMPLATE
            rendered = (
                template.read_text(encoding="utf-8")
                .replace("{{PYTHON_PATH_JSON}}", json.dumps(python))
                .replace("{{PYTHONPATH_JSON}}", json.dumps(runtime))
            )
            if not context.dry_run:
                result = subprocess.run(
                    [
                        python,
                        "-c",
                        "import des.adapters.drivers.hooks.claude_code_hook_adapter",
                    ],
                    env={**os.environ, "PYTHONPATH": runtime},
                    cwd=Path.home(),
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                if result.returncode:
                    raise ValueError(
                        f"WHAT: DES runtime import failed at {runtime}. WHY: {result.stderr.strip()}. "
                        "HOW: rerun the OMP installer with Python >=3.10 and its required dependencies installed."
                    )
            directory = omp_extensions_dir()
            shim = directory / _SHIM
            manifest_path = directory / _MANIFEST
            if (
                directory.is_symlink()
                or shim.is_symlink()
                or manifest_path.is_symlink()
            ):
                raise ValueError(
                    f"Unsafe OMP extension path: {directory}; remove symlinks and rerun install."
                )
            if shim.exists() and not manifest_path.is_file():
                raise ValueError(
                    f"Foreign OMP extension collision: {shim}; back up and remove it before reinstalling."
                )
            if not context.dry_run:
                directory.mkdir(parents=True, exist_ok=True)
                shim.write_text(rendered, encoding="utf-8")
                manifest_path.write_text(
                    json.dumps(
                        {
                            "installed_extensions": [_SHIM],
                            "sha256": hashlib.sha256(rendered.encode()).hexdigest(),
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            message = (
                f"{'Would install' if context.dry_run else 'Installed'} OMP DES extension at {shim}; "
                f"Python: {python}; runtime: {runtime}. {OMP_GUARD_CEILING}"
            )
            context.logger.info(message)
            return PluginResult(True, self.name, message, installed_files=[shim])
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            return PluginResult(
                False,
                self.name,
                f"OMP DES installation refused: {error}",
                errors=[str(error)],
            )

    def verify(self, context: InstallContext) -> PluginResult:
        directory = omp_extensions_dir()
        try:
            manifest = json.loads((directory / _MANIFEST).read_text(encoding="utf-8"))
            digest = hashlib.sha256((directory / _SHIM).read_bytes()).hexdigest()
            if digest != manifest["sha256"]:
                raise ValueError(
                    "OMP DES extension content differs from its installation manifest; rerun install."
                )
            return PluginResult(True, self.name, "OMP DES extension verified")
        except (OSError, ValueError, KeyError) as error:
            return PluginResult(False, self.name, str(error), errors=[str(error)])

    def uninstall(self, context: InstallContext) -> PluginResult:
        directory = omp_extensions_dir()
        if (directory / _MANIFEST).is_file():
            for name in (_SHIM, _MANIFEST):
                (directory / name).unlink(missing_ok=True)
        return PluginResult(True, self.name, "OMP DES extension uninstalled")
