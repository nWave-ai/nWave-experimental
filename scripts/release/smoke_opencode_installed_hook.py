#!/usr/bin/env python3
"""Execute the OpenCode hook from one already-built public wheel.

This is a release-only consumer smoke: it does not rebuild or inspect source
templates.  The caller supplies the exact wheel about to be published, whose
adjacent offline wheelhouse is part of the public distribution contract.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path


_TIMEOUT_ENV = "NWAVE_OPENCODE_SMOKE_TIMEOUT"
_DEFAULT_TIMEOUT_SECONDS = 900.0


def _timeout_seconds() -> float:
    """Return the release-smoke wall-clock bound, with an operator override.

    Installing a wheel and invoking Bun can legitimately take several minutes on
    a cold release runner, so this is deliberately as generous as the offline
    wheelhouse operation.  It is still a real ceiling: a child retaining a pipe
    or waiting for credentials must not pin a publish job forever.
    """
    try:
        timeout = float(os.environ.get(_TIMEOUT_ENV, _DEFAULT_TIMEOUT_SECONDS))
    except ValueError:
        return _DEFAULT_TIMEOUT_SECONDS
    return timeout if timeout > 0 else _DEFAULT_TIMEOUT_SECONDS


def _reap_timed_out_process(process: subprocess.Popen[str]) -> None:
    """Kill the timed-out child and its descendants before collecting output."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            pass
    process.kill()


def _run(
    command: list[str], *, cwd: Path, env: dict[str, str], input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name == "posix",
    )
    timeout = _timeout_seconds()
    try:
        stdout, stderr = process.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        _reap_timed_out_process(process)
        stdout, stderr = process.communicate()
        raise SystemExit(
            "OpenCode installed-hook smoke timed out after "
            f"{timeout:g}s: {' '.join(command)}\n"
            f"Set {_TIMEOUT_ENV}=<seconds> only when this release operation is "
            f"still making legitimate progress.\n{stdout}{stderr}"
        ) from error
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if completed.returncode != 0:
        raise SystemExit(
            f"OpenCode installed-hook smoke failed ({completed.returncode}): "
            f"{' '.join(command)}\n{completed.stdout}{completed.stderr}"
        )
    return completed


def _verify_rendered_adapter_route(
    rendered: str, *, runtime_dir: Path, cwd: Path, environment: dict[str, str]
) -> None:
    """Require the adapter command embedded in the installed shim to work.

    The TypeScript hook deliberately catches adapter failures so that OpenCode
    itself remains fail-open.  A release smoke must be stricter: it invokes the
    exact Python and module rendered into that shim with the same Write event
    that the Bun harness sends, then requires a successful adapter exit.
    """
    adapter_match = re.search(r'\["([^"]+)", "-m", "([^"]+)", action\]', rendered)
    if adapter_match is None:
        raise SystemExit("installed OpenCode shim has no adapter command")
    python_path, module = adapter_match.groups()
    adapter_environment = environment.copy()
    adapter_environment["PYTHONPATH"] = str(runtime_dir)
    _run(
        [python_path, "-m", module, "pre-write"],
        cwd=cwd,
        env=adapter_environment,
        input_text=json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "probe.txt", "content": "probe"},
            }
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute the installed OpenCode shim from a public wheel."
    )
    parser.add_argument("--wheel", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    wheel = args.wheel.resolve()
    wheelhouse = wheel.parent / "offline-wheelhouse"
    requirements_lock = wheelhouse / "requirements.lock"
    if not wheel.is_file() or not requirements_lock.is_file():
        raise SystemExit(
            "OpenCode smoke requires the wheel and its adjacent "
            f"offline-wheelhouse/requirements.lock; got wheel={wheel}, "
            f"lock={requirements_lock}"
        )

    with tempfile.TemporaryDirectory(prefix="nwave-opencode-smoke-") as temporary:
        consumer = Path(temporary)
        venv = consumer / "venv"
        _run([sys.executable, "-m", "venv", str(venv)], cwd=consumer, env=os.environ)
        binary_dir = venv / ("Scripts" if os.name == "nt" else "bin")
        pip = binary_dir / ("pip.exe" if os.name == "nt" else "pip")
        console = binary_dir / ("nwave-ai.exe" if os.name == "nt" else "nwave-ai")
        fake_home = consumer / "home"
        opencode_home = consumer / "opencode"
        fake_home.mkdir()
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        environment.update(
            {
                "HOME": str(fake_home),
                "USERPROFILE": str(fake_home),
                "PATH": f"{binary_dir}{os.pathsep}{environment.get('PATH', '')}",
                "PYTHONNOUSERSITE": "1",
                "PIP_CONFIG_FILE": os.devnull,
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PIP_NO_INDEX": "1",
                "OPENCODE_CONFIG_DIR": str(opencode_home),
            }
        )
        _run(
            [
                str(pip),
                "--isolated",
                "install",
                "--quiet",
                "--no-index",
                "--find-links",
                ".",
                "-r",
                requirements_lock.name,
            ],
            cwd=wheelhouse,
            env=environment,
        )
        _run(
            [str(console), "install", "--yes", "--platform", "opencode"],
            cwd=consumer,
            env=environment,
        )
        shim = opencode_home / "plugins" / "nwave-des.ts"
        rendered = shim.read_text(encoding="utf-8")
        runtime_match = re.search(r'PYTHONPATH: "([^"]+)"', rendered)
        if runtime_match is None:
            raise SystemExit("installed OpenCode shim has no literal PYTHONPATH")
        runtime_dir = Path(runtime_match.group(1))
        if not (runtime_dir / "des" / "__init__.py").is_file():
            raise SystemExit(
                f"installed OpenCode runtime is missing des: {runtime_dir}"
            )
        _verify_rendered_adapter_route(
            rendered,
            runtime_dir=runtime_dir,
            cwd=consumer,
            environment=environment,
        )
        harness = consumer / "run-nwave-opencode-hook.ts"
        harness.write_text(
            "import plugin from " + json.dumps(shim.as_posix()) + ";\n"
            "const hooks = plugin({} as never);\n"
            "await hooks['tool.execute.before'](\n"
            "  { tool: 'write', args: {} },\n"
            "  { args: { file_path: 'probe.txt', content: 'probe' } },\n"
            ");\n"
            "console.log('nwave-opencode-hook-executed');\n",
            encoding="utf-8",
        )
        fired = _run(["bun", "run", str(harness)], cwd=consumer, env=environment)
        if "nwave-opencode-hook-executed" not in fired.stdout:
            raise SystemExit("installed OpenCode hook did not report execution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
