"""Installed-public observation for the G2 update chain.

Run directly: ``uv run python tests/nwave_ai/update_installed_public_oracle.py``.
The candidate is built and installed into a temporary virtual environment.  The
initial ``nwave-ai`` and ``des`` commands are therefore the installed entry
points, never imports from this checkout.  The check row performs its actual
read-only PyPI request.  Apply rows use explicitly labelled, local external
process fixtures for the package-manager and post-replacement executables;
they prove CLI wiring and stage order, never a remote vendor upgrade.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import venv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[2]
TIMEOUT = 90
_VERSION = re.compile(r"^(?:Installed version|Latest stable release):\s*(.+)$", re.M)


@dataclass(frozen=True)
class ProcessObservation:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


def _run(argv: list[str], *, env: dict[str, str], cwd: Path) -> ProcessObservation:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=TIMEOUT,
        check=False,
    )
    return ProcessObservation(
        argv, completed.returncode, completed.stdout, completed.stderr
    )


def _tree_hashes(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _json_process(process: ProcessObservation) -> dict[str, Any]:
    return asdict(process)


def _read_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _build_wheel(work: Path, env: dict[str, str]) -> tuple[Path, dict[str, str]]:
    """Build the release-shaped, controlled lower-version baseline in isolation."""
    producer = work / "producer"
    ignored = shutil.ignore_patterns(
        ".git", ".venv", "dist", ".hypothesis", "__pycache__"
    )
    shutil.copytree(REPO, producer, ignore=ignored)
    subject = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()
    baseline = "0.0.0.dev0"
    commands = [
        [
            sys.executable,
            "scripts/release/patch_pyproject.py",
            "--input",
            "pyproject.toml",
            "--output",
            "pyproject.toml",
            "--target-name",
            "nwave-ai",
            "--target-version",
            baseline,
        ],
        [sys.executable, "scripts/build_dist.py"],
        [sys.executable, "scripts/release/stage_public_wheel_des.py", "--cleanup-dist"],
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(producer / "wheelhouse"),
        ],
    ]
    for command in commands:
        result = _run(command, env=env, cwd=producer)
        if result.returncode:
            raise RuntimeError(
                f"factory build failed for {command!r}: {result.stderr or result.stdout}"
            )
    wheels = sorted((producer / "wheelhouse").glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one factory wheel, found {wheels!r}")
    return wheels[0], {
        "subject_sha": subject,
        "producer_baseline_version": baseline,
        "factory": "patch_pyproject -> build_dist -> stage_public_wheel_des -> python -m build --wheel",
    }


def _install_candidate(
    wheel: Path, work: Path, env: dict[str, str]
) -> tuple[Path, Path, Path]:
    environment = work / "installed-candidate"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
    bindir = environment / ("Scripts" if os.name == "nt" else "bin")
    python = bindir / ("python.exe" if os.name == "nt" else "python")
    installed = _run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
        env=env,
        cwd=work,
    )
    if installed.returncode:
        raise RuntimeError(
            f"candidate wheel install failed: {installed.stderr or installed.stdout}"
        )
    console = bindir / ("nwave-ai.exe" if os.name == "nt" else "nwave-ai")
    des = bindir / ("des.exe" if os.name == "nt" else "des")
    if not console.is_file() or not des.is_file():
        raise RuntimeError("wheel lacks installed nwave-ai or des console")
    return python, console, des


def _versions(check: ProcessObservation) -> tuple[str, str] | None:
    values = _VERSION.findall(check.stdout)
    return (values[0], values[1]) if len(values) == 2 else None


def _write_controlled_tools(tools: Path, events: Path, console: Path) -> None:
    """Create external boundary fixtures, never injected into product code.

    The controlled ``uv`` represents only package replacement. On a success it
    replaces the sibling console just as a package manager would. That
    replacement console and ``des`` are explicitly labelled controlled; the
    initial update invocation always enters the real installed console first.
    """
    tools.mkdir(parents=True, exist_ok=True)
    controlled_console = f"""#!{sys.executable}
import json, os, pathlib, sys
events = pathlib.Path(os.environ["G2_EVENTS"])
with events.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({{"kind": "controlled-owned-console", "argv": sys.argv[1:]}}) + "\\n")
scenario = os.environ["G2_SCENARIO"]
if sys.argv[1:] == ["--version"]:
    suffix = "-wrong" if scenario == "proof-mismatch" else ""
    print("nwave-ai " + os.environ["G2_VERSION"] + suffix)
    sys.exit(0)
if sys.argv[1:] == ["install", "--yes"]:
    sys.exit(42 if scenario == "sync-fails" else 0)
sys.exit(43)
"""
    fixture = tools / "uv"
    fixture.write_text(
        f"""#!{sys.executable}
import json, os, pathlib, sys
events = pathlib.Path(os.environ["G2_EVENTS"])
with events.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({{"kind": "controlled-package-manager", "argv": sys.argv[1:]}}) + "\\n")
if os.environ["G2_SCENARIO"] == "replace-fails":
    sys.exit(41)
console = pathlib.Path(os.environ["G2_OWNED_CONSOLE"])
console.write_text({controlled_console!r}, encoding="utf-8")
console.chmod(0o755)
""",
        encoding="utf-8",
    )
    des = tools / "des"
    des.write_text(
        f"""#!{sys.executable}
import json, os, pathlib, sys
events = pathlib.Path(os.environ["G2_EVENTS"])
with events.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({{"kind": "controlled-des", "argv": sys.argv[1:]}}) + "\\n")
sys.exit(44 if os.environ["G2_SCENARIO"] == "migration-fails" else 0)
""",
        encoding="utf-8",
    )
    fixture.chmod(0o755)
    des.chmod(0o755)


@dataclass(frozen=True)
class _ApplyRowEnvironment:
    """The apply-row fixture that stays fixed across every scenario row."""

    console: Path
    pristine_console: Path
    root: Path
    env: dict[str, str]
    events: Path


def _apply_row(
    environment: _ApplyRowEnvironment, *, scenario: str, latest: str
) -> dict[str, Any]:
    shutil.copy2(environment.pristine_console, environment.console)
    environment.events.unlink(missing_ok=True)
    row_env = dict(environment.env)
    row_env.update(
        {"NWAVE_INSTALLER": "uv", "G2_SCENARIO": scenario, "G2_VERSION": latest}
    )
    invocation = _run(
        [str(environment.console), "update", "--yes", "--root", str(environment.root)],
        env=row_env,
        cwd=environment.root,
    )
    return {
        "fixture": "controlled external package-manager/post-replacement executable/des boundaries; initial command is installed candidate console",
        "scenario": scenario,
        "invocation": _json_process(invocation),
        "external_events": _read_json_lines(environment.events),
    }


def _assert_apply_rows(rows: list[dict[str, Any]], latest: str, root: Path) -> bool:
    expected_replace = ["tool", "install", "--reinstall", f"nwave-ai=={latest}"]
    expected_des = ["update", "--apply", "--root", str(root)]
    by_name = {row["scenario"]: row for row in rows}
    success = by_name["success"]
    events = success["external_events"]
    if success["invocation"]["returncode"] != 0 or [e["kind"] for e in events] != [
        "controlled-package-manager",
        "controlled-owned-console",
        "controlled-owned-console",
        "controlled-des",
    ]:
        return False
    if events[0]["argv"] != expected_replace or events[1]["argv"] != ["--version"]:
        return False
    if events[2]["argv"] != ["install", "--yes"] or events[3]["argv"] != expected_des:
        return False
    expected_stops = {
        "replace-fails": ("replace-package", 1),
        "proof-mismatch": ("verify-executable", 2),
        "sync-fails": ("synchronize-framework", 3),
        "migration-fails": ("migrate-artifacts", 4),
    }
    for name, (stage, count) in expected_stops.items():
        row = by_name[name]
        if (
            row["invocation"]["returncode"] == 0
            or stage not in row["invocation"]["stderr"]
        ):
            return False
        if len(row["external_events"]) != count:
            return False
    return True


def main() -> int:
    observation: dict[str, Any] = {
        "oracle": "G2 installed public update observation",
        "candidate": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip(),
    }
    passed = False
    try:
        with tempfile.TemporaryDirectory(prefix="nwave-g2-installed-") as raw:
            work = Path(raw)
            home, check_root, malformed_root = (
                work / "home",
                work / "check-root",
                work / "malformed-root",
            )
            home.mkdir()
            check_root.mkdir()
            malformed_root.mkdir()
            env = os.environ | {
                "HOME": str(home),
                "NWAVE_AGENTS_HOME": str(home),
                "CLAUDE_CONFIG_DIR": str(home / ".claude"),
                "CODEX_HOME": str(home / ".codex"),
                "NO_COLOR": "1",
            }
            wheel, lineage = _build_wheel(work, env)
            python, console, des = _install_candidate(wheel, work, env)
            bootstrap = _run(
                [str(console), "install", "--yes", "--platform", "codex"],
                env=env,
                cwd=check_root,
            )
            runtime = home / ".nwave" / "runtime"
            runtime_manifest = runtime / "des" / "_install_manifest.json"
            observation["bootstrap"] = {
                "process": _json_process(bootstrap),
                "runtime_manifest_exists": runtime_manifest.is_file(),
                "runtime_files": sorted(
                    path.relative_to(runtime).as_posix()
                    for path in runtime.rglob("*")
                    if path.is_file()
                )[:20],
            }
            if bootstrap.returncode or not runtime_manifest.is_file():
                raise RuntimeError(
                    "isolated public install did not create its installed DES runtime manifest"
                )
            runtime_env = env | {"PYTHONPATH": str(runtime)}
            observation["installed"] = {
                **lineage,
                "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                "console": str(console),
                "wheel_des_console": str(des),
                "runtime_manifest": str(runtime_manifest),
            }

            check_before = {
                "home": _tree_hashes(home),
                "root": _tree_hashes(check_root),
            }
            check = _run([str(console), "update", "--check"], env=env, cwd=check_root)
            check_after = {"home": _tree_hashes(home), "root": _tree_hashes(check_root)}
            parsed = _versions(check)
            observation["check"] = {
                "external_release_discovery": "actual read-only PyPI request",
                "process": _json_process(check),
                "before": check_before,
                "after": check_after,
                "unchanged": check_before == check_after,
                "parsed_versions": parsed,
            }

            inflight = (
                malformed_root / ".nwave" / "expectation-charters" / "inflight.json"
            )
            completed = (
                malformed_root / ".nwave" / "expectation-charters" / "completed.json"
            )
            inflight.parent.mkdir(parents=True)
            inflight.write_text(
                '{"schema-version":0,"phase":"RED","tag":"unregistered-tag"}\n',
                encoding="utf-8",
            )
            completed.write_text(
                '{"schema-version":0,"phase":"COMPLETED","tag":"v4"}\n',
                encoding="utf-8",
            )
            malformed_before = _tree_hashes(malformed_root)
            malformed = _run(
                [
                    str(python),
                    "-m",
                    "des.cli",
                    "update",
                    "--apply",
                    "--root",
                    str(malformed_root),
                ],
                env=runtime_env,
                cwd=malformed_root,
            )
            malformed_after = _tree_hashes(malformed_root)
            observation["malformed_batch"] = {
                "process": _json_process(malformed),
                "before": malformed_before,
                "after": malformed_after,
                "preserved": malformed_before == malformed_after,
            }

            if (
                check.returncode != 0
                or not parsed
                or not observation["check"]["unchanged"]
            ):
                raise RuntimeError(
                    "actual installed --check did not yield a read-only version observation"
                )
            current, latest = parsed
            if latest <= current:
                raise RuntimeError(
                    f"actual PyPI check is not update-available ({current} -> {latest}); no apply sequence was claimed"
                )
            if malformed.returncode == 0 or malformed_before != malformed_after:
                raise RuntimeError(
                    "installed des malformed batch did not refuse before writes"
                )

            tools, events = work / "controlled-tools", work / "controlled-events.jsonl"
            _write_controlled_tools(tools, events, console)
            pristine = work / "pristine-nwave-ai"
            shutil.copy2(console, pristine)
            apply_env = env | {
                "PATH": str(tools) + os.pathsep + env.get("PATH", ""),
                "G2_EVENTS": str(events),
                "G2_OWNED_CONSOLE": str(console),
            }
            row_environment = _ApplyRowEnvironment(
                console=console,
                pristine_console=pristine,
                root=check_root,
                env=apply_env,
                events=events,
            )
            rows = [
                _apply_row(row_environment, scenario=name, latest=latest)
                for name in (
                    "success",
                    "replace-fails",
                    "proof-mismatch",
                    "sync-fails",
                    "migration-fails",
                )
            ]
            observation["apply"] = {
                "actual_release_discovery": "each row reuses the installed CLI and its real PyPI read",
                "rows": rows,
            }
            passed = _assert_apply_rows(rows, latest, check_root)
            if not passed:
                raise RuntimeError(
                    "installed apply stage observations violate ordering or fail-closed stopping"
                )
    except Exception as exc:
        observation["error"] = str(exc)
    observation["passed"] = passed
    print(json.dumps(observation, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
