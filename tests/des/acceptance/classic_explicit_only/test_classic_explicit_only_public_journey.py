"""Public ATs for the one-spine ``atdd_pure`` workflow contract.

The selection boundary is deliberately the only oracle for mode semantics:

    des resolve-workflow-mode --project-dir <dir> --operation <operation> --json

``classic`` is historical input, never a selectable value.  These tests must
stay RED until the installed CLI, its packaged assets, and every runtime carrier
all project that same rule.  The single subprocess test is the feature's
walking skeleton; the remaining cases use the public dispatcher in-process so
they remain fast and diagnose the selection algebra precisely.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process


_COMMAND = "resolve-workflow-mode"
_OPERATION = "deliver"
_WHAT_WHY_HOW = ("WHAT", "WHY", "HOW")
_ACTIVE_MODE_ALIAS = re.compile(r"\b(?:classic|retired workflow)\b", re.IGNORECASE)
_EXECUTABLE_CARRIER = re.compile(
    r"(?:"
    r"workflow\.mode[^\n]{0,40}\b(?:classic|retired workflow)\b|"
    r"\b(?:default|fallback|fall back)\b[^\n]{0,100}\b(?:classic|retired workflow)\b|"
    r"\b(?:classic|retired workflow)\b[^\n]{0,100}\b(?:default|fallback|"
    r"dispatch template|dispatches?|roadmap|execution-log)\b|"
    r"\b(?:use|run|route|select|dispatch)\b[^\n]{0,100}\b(?:classic|retired workflow)\b|"
    r"\bpatch\b[^\n]{0,100}\bworkflow\.mode\b[^\n]{0,40}\b(?:classic|retired workflow)\b"
    r")",
    re.IGNORECASE,
)


def _installed_active_mode_carriers(path: Path, display_root: Path) -> list[str]:
    offenders: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line_number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        read_only_history = (
            "read-only" in lowered
            and ("replay" in lowered or "migration" in lowered)
            and _ACTIVE_MODE_ALIAS.search(lowered) is not None
        )
        if not read_only_history and _EXECUTABLE_CARRIER.search(line):
            offenders.append(
                f"{path.relative_to(display_root)}:{line_number}: {line.strip()!r}"
            )
    return offenders


@dataclass(frozen=True)
class ModeRun:
    exit_code: int
    payload: dict[str, object] | None
    output: str


def _last_json_event(stdout: str) -> dict[str, object] | None:
    events = [line for line in stdout.splitlines() if line.lstrip().startswith("{")]
    return json.loads(events[-1]) if events else None


def _run_mode_in_process(
    project: Path,
    *,
    operation: str = _OPERATION,
    extra_args: tuple[str, ...] = (),
    falsifier_state: str | None = None,
) -> ModeRun:
    argv = [
        _COMMAND,
        "--project-dir",
        str(project),
        "--operation",
        operation,
        *extra_args,
        "--json",
    ]
    if falsifier_state is not None:
        argv.extend(("--falsifier-state", falsifier_state))
    exit_code, stdout, stderr = run_cli_in_process(argv, cwd=project)
    return ModeRun(exit_code, _last_json_event(stdout), stdout + stderr)


def _fresh_workspace(root: Path) -> Path:
    workspace = root / "fresh"
    workspace.mkdir()
    return workspace


def _configured_workspace(root: Path, mode: str | None) -> Path:
    workspace = root / ("unset" if mode is None else mode.replace("_", "-"))
    config = workspace / ".nwave" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "workflow: {}\n" if mode is None else f"workflow:\n  mode: {mode}\n",
        encoding="utf-8",
    )
    return workspace


def _assert_selected_atdd_pure(run: ModeRun) -> None:
    assert run.exit_code == 0, run.output
    assert run.payload is not None, run.output
    assert run.payload.get("outcome") == "SELECTED", run.payload
    assert run.payload.get("effective_mode") == "atdd_pure", run.payload
    assert run.payload.get("dispatch_mode") == "atdd_pure", run.payload


def _assert_refused(run: ModeRun, *, outcome: str, reason: str | None = None) -> None:
    assert run.exit_code != 0, run.output
    assert run.payload is not None, run.output
    assert run.payload.get("outcome") == outcome, run.payload
    assert run.payload.get("effective_mode") is None, run.payload
    if reason is not None:
        assert run.payload.get("reason_code") == reason, run.payload
    diagnostic = str(run.payload.get("diagnostic", ""))
    assert all(marker in diagnostic for marker in _WHAT_WHY_HOW), diagnostic


_CANDIDATE_MANIFEST_ENV = "NWAVE_PUBLIC_CANDIDATE_MANIFEST"
_CANDIDATE_SCHEMA = "nwave.public-candidate.v1"


def _candidate_manifest() -> tuple[Path, dict[str, object]]:
    """Load the release-lane handoff; DISTILL must never build or fetch it."""
    raw_path = os.environ.get(_CANDIDATE_MANIFEST_ENV)
    assert raw_path, (
        "WHAT: no immutable public-candidate manifest was supplied. "
        "WHY: this walking skeleton must examine the release candidate, not build "
        "a convenient substitute from source. HOW: candidate service must set "
        f"{_CANDIDATE_MANIFEST_ENV} to a JSON {_CANDIDATE_SCHEMA!r} manifest "
        "containing artifact.path, artifact.sha256, offline_dependency_closure."
    )
    manifest_path = Path(raw_path).resolve()
    assert manifest_path.is_file(), f"candidate manifest is not a file: {manifest_path}"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert (
        isinstance(payload, dict) and payload.get("schema_version") == _CANDIDATE_SCHEMA
    ), (
        "WHAT: candidate handoff has no recognised immutable manifest schema. "
        "WHY: path-only input can silently substitute a different artifact. "
        f"HOW: emit schema_version={_CANDIDATE_SCHEMA!r} with artifact bytes and "
        "offline dependency-closure coordinates."
    )
    return manifest_path, payload


def _manifest_path(payload: dict[str, object], section: str, key: str) -> Path:
    value = payload.get(section)
    assert isinstance(value, dict) and isinstance(value.get(key), str), (
        f"candidate manifest missing {section}.{key}"
    )
    return Path(value[key]).resolve()


def _verified_candidate(payload: dict[str, object]) -> tuple[Path, Path, Path]:
    artifact = payload.get("artifact")
    assert isinstance(artifact, dict)
    candidate = _manifest_path(payload, "artifact", "path")
    expected_digest = artifact.get("sha256")
    assert isinstance(expected_digest, str) and re.fullmatch(
        r"[0-9a-f]{64}", expected_digest
    ), "candidate manifest artifact.sha256 must be a lowercase SHA-256 digest"
    assert candidate.is_file(), f"candidate artifact is absent: {candidate}"
    observed_digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    assert observed_digest == expected_digest, (
        "WHAT: the candidate bytes do not match their release handoff digest. "
        "WHY: an artifact changed after candidate preparation is stale or substituted. "
        "HOW: reject it; candidate service must prepare a new manifest for the exact "
        f"immutable bytes. expected={expected_digest}; observed={observed_digest}"
    )
    closure = payload.get("offline_dependency_closure")
    assert isinstance(closure, dict)
    wheelhouse = _manifest_path(
        payload, "offline_dependency_closure", "wheelhouse_path"
    )
    requirements_lock = _manifest_path(
        payload, "offline_dependency_closure", "requirements_lock_path"
    )
    assert wheelhouse.is_dir() and requirements_lock.is_file(), (
        "WHAT: the verified candidate has no offline dependency closure. "
        "WHY: an install that resolves from the network is not the reviewed public "
        "artifact journey. HOW: candidate service must prepare wheelhouse_path and a "
        "pinned requirements_lock_path before this test is scheduled."
    )
    candidate_requirement = candidate.as_uri()
    candidate_lock_entries = [
        line.strip()
        for line in requirements_lock.read_text(encoding="utf-8").splitlines()
        if candidate_requirement in line
    ]
    assert len(candidate_lock_entries) == 1 and (
        f"--hash=sha256:{observed_digest}" in candidate_lock_entries[0]
    ), (
        "WHAT: the hashed offline lock does not name exactly the manifest-verified "
        "candidate. WHY: passing a wheel separately lets pip reject it under "
        "--require-hashes or select a second authority. HOW: candidate service must "
        "place one file-URI requirement for the exact wheel and its SHA-256 hash in "
        f"requirements.lock. candidate={candidate_requirement}; matches={candidate_lock_entries}"
    )
    return candidate, wheelhouse, requirements_lock


def _isolated_env(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    environment = tmp_path / "candidate-env"
    created = subprocess.run(
        [sys.executable, "-m", "venv", str(environment)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr
    bin_dir = environment / ("Scripts" if os.name == "nt" else "bin")
    clean_env = {
        "HOME": str(tmp_path / "home"),
        "PATH": str(bin_dir),
        "PIP_NO_INDEX": "1",
        "PYTHONNOUSERSITE": "1",
    }
    return bin_dir, clean_env


def _run_installed_session_start(
    python: Path,
    workspace: Path,
    clean_env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Drive the installed SessionStart handler, not a synthetic guidance flag."""
    return subprocess.run(
        [
            str(python),
            "-c",
            (
                "from des.adapters.drivers.hooks.session_start_handler "
                "import handle_session_start; "
                "raise SystemExit(handle_session_start())"
            ),
        ],
        cwd=workspace,
        env=clean_env,
        input=json.dumps({"hook_event_name": "SessionStart", "cwd": str(workspace)}),
        text=True,
        capture_output=True,
        check=False,
    )


def _session_additional_context(stdout: str) -> str:
    contexts: list[str] = []
    for line in stdout.splitlines():
        if not line.lstrip().startswith("{"):
            continue
        payload = json.loads(line)
        if isinstance(payload.get("additionalContext"), str):
            contexts.append(payload["additionalContext"])
        hook_output = payload.get("hookSpecificOutput")
        if isinstance(hook_output, dict) and isinstance(
            hook_output.get("additionalContext"), str
        ):
            contexts.append(hook_output["additionalContext"])
    return "\n".join(contexts)


@pytest.mark.walking_skeleton
@pytest.mark.wiring_e2e
@pytest.mark.negative_at
def test_walking_skeleton_installs_verified_external_candidate_offline_and_proves_classic_unselectable(
    tmp_path: Path,
) -> None:
    """The release candidate—not source—ships one public atdd-pure-only journey."""
    # covers: R1 R2 R3 R4 R5 R6
    _, manifest = _candidate_manifest()
    _candidate, wheelhouse, requirements_lock = _verified_candidate(manifest)
    bin_dir, clean_env = _isolated_env(tmp_path)
    python = bin_dir / ("python.exe" if os.name == "nt" else "python")
    des = bin_dir / ("des.exe" if os.name == "nt" else "des")
    project = _configured_workspace(tmp_path / "project", "classic")

    install = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "--require-hashes",
            "--requirement",
            str(requirements_lock),
        ],
        cwd=tmp_path,
        env=clean_env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert install.returncode == 0 and des.is_file(), (
        "WHAT: the verified public candidate did not install offline into an isolated "
        "environment. WHY: source imports and live resolution cannot prove the shipped "
        "operator artifact. HOW: candidate service must provide one fully hashed lock "
        "which names the independently verified exact wheel and every dependency. "
        f"stdout={install.stdout!r}; stderr={install.stderr!r}"
    )
    invocation = subprocess.run(
        [
            str(des),
            _COMMAND,
            "--project-dir",
            str(project),
            "--operation",
            _OPERATION,
            "--json",
        ],
        cwd=project,
        env=clean_env,
        text=True,
        capture_output=True,
        check=False,
    )
    result = _last_json_event(invocation.stdout)
    assert invocation.returncode != 0 and result is not None, invocation.stderr
    assert result.get("outcome") == "CLASSIC_MODE_REMOVED", result
    assert result.get("reason_code") == "MIGRATION_REQUIRED", result
    assert result.get("effective_mode") is None, result

    session_workspaces = {
        "fresh": tmp_path / "session-fresh",
        "legacy-unset": _configured_workspace(tmp_path / "session-unset", None),
        "classic": _configured_workspace(tmp_path / "session-classic", "classic"),
        "atdd-pure": _configured_workspace(tmp_path / "session-atdd", "atdd_pure"),
    }
    (session_workspaces["fresh"] / ".nwave").mkdir(parents=True)
    for kind, workspace in session_workspaces.items():
        session = _run_installed_session_start(python, workspace, clean_env)
        context = _session_additional_context(session.stdout)
        assert session.returncode == 0, session.stderr
        if kind in {"legacy-unset", "classic"}:
            assert all(marker in context for marker in _WHAT_WHY_HOW), (
                "WHAT: the real installed SessionStart path omitted proactive "
                f"removal/migration guidance for {kind}. WHY: a resolver-only "
                "diagnostic arrives after the agent has already chosen a path. "
                "HOW: inject the closed refusal diagnostic at SessionStart. "
                f"stdout={session.stdout!r}; stderr={session.stderr!r}"
            )
            assert "migration" in context.lower()
            if kind == "classic":
                assert "classic" in context.lower() and "removed" in context.lower()
        else:
            assert "atdd_pure" in context, (
                f"SessionStart did not project the sole active mode for {kind}: {context!r}"
            )

    package_root = subprocess.run(
        [str(python), "-c", "import des; print(des.__file__)"],
        cwd=project,
        env=clean_env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert package_root.returncode == 0, package_root.stderr
    installed_des = Path(package_root.stdout.strip()).resolve().parent
    distribution_root = installed_des.parent
    installed_nwave_root = distribution_root / "nWave" / "nWave"
    active_registry_files = [
        installed_nwave_root / "framework-catalog.yaml",
        installed_nwave_root / "flavors" / "_schema.yaml",
        installed_nwave_root / "flavors" / "atdd_pure.yaml",
        distribution_root / "nWave" / "tasks" / "nw" / "deliver.md",
        distribution_root / "nWave" / "tasks" / "nw" / "execute.md",
        distribution_root / "nWave" / "skills" / "nw-execute" / "SKILL.md",
        distribution_root
        / "nWave"
        / "skills"
        / "nw-deliver-atdd-pure-slice-gates"
        / "SKILL.md",
        installed_des / "application" / "flavor_dispatcher.py",
        installed_des / "application" / "workflow_mode.py",
        installed_des / "cli" / "resolve_workflow_mode.py",
        installed_des / "adapters" / "drivers" / "hooks" / "subagent_stop_handler.py",
    ]
    missing = [
        str(path.relative_to(distribution_root))
        for path in active_registry_files
        if not path.is_file()
    ]
    assert not missing, (
        "WHAT: installed active assets are missing from the assembled candidate. "
        "WHY: silently skipping absent registries can turn a partial inspection into PASS. "
        f"HOW: package every expected asset or repair the installed path contract. missing={missing}"
    )
    assert not (installed_nwave_root / "flavors" / "classic.yaml").exists(), (
        "WHAT: the installed active flavor registry still ships classic.yaml. "
        "WHY: a shipped registry asset can restore classic selection despite source policy. "
        "HOW: omit the retired flavor from the assembled candidate."
    )
    selectable_declarations = {
        str(path.relative_to(distribution_root)): re.findall(
            r"(?mi)^\\s*(?:classic|default_mode)\\s*[:=]\\s*['\"]?classic\\b",
            path.read_text(encoding="utf-8", errors="replace"),
        )
        for path in active_registry_files
    }
    assert not any(selectable_declarations.values()), (
        "WHAT: an installed active registry or handler still declares classic selectable. "
        "WHY: archive/source scans cannot prove the executable installed surface. "
        "HOW: remove the declaration and retain classic only as a migration refusal. "
        f"matches={selectable_declarations}"
    )
    installed_carriers = [
        offender
        for path in active_registry_files
        if path.suffix in {".md", ".yaml", ".yml", ".json"}
        for offender in _installed_active_mode_carriers(path, distribution_root)
    ]
    assert not installed_carriers, (
        "WHAT: the installed candidate still teaches an executable retired workflow. "
        "WHY: renaming classic does not remove its selection or dispatch semantics. "
        "HOW: retain aliases only in explicitly read-only replay/migration history. "
        + "\n".join(installed_carriers)
    )


def test_public_candidate_manifest_rejects_a_stale_or_mismatched_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A digest mismatch fails before install; the test never builds/downloads a replacement."""
    manifest_path, manifest = _candidate_manifest()
    stale = dict(manifest)
    artifact = stale.get("artifact")
    assert isinstance(artifact, dict)
    stale["artifact"] = {**artifact, "sha256": "0" * 64}
    stale_manifest = tmp_path / "stale-candidate-manifest.json"
    stale_manifest.write_text(json.dumps(stale), encoding="utf-8")
    monkeypatch.setenv(_CANDIDATE_MANIFEST_ENV, str(stale_manifest))

    _, supplied = _candidate_manifest()
    with pytest.raises(
        AssertionError, match="do not match their release handoff digest"
    ):
        _verified_candidate(supplied)
    assert manifest_path.is_file(), (
        "the immutable release handoff itself must not be rewritten"
    )


@pytest.mark.parametrize(
    ("workspace_kind", "mode", "expected"),
    [
        ("fresh", "__fresh__", "SELECTED"),
        ("explicit-atdd", "atdd_pure", "SELECTED"),
        ("legacy-unset", None, "MODE_UNDECLARED"),
    ],
)
def test_normal_absence_and_transition_mode_have_closed_atdd_pure_semantics(
    tmp_path: Path, workspace_kind: str, mode: str | None, expected: str
) -> None:
    workspace = (
        _fresh_workspace(tmp_path)
        if mode == "__fresh__"
        else _configured_workspace(tmp_path, mode)
    )
    before = (
        None
        if mode == "__fresh__"
        else (workspace / ".nwave" / "config.yaml").read_bytes()
    )
    run = _run_mode_in_process(workspace)
    if expected == "SELECTED":
        _assert_selected_atdd_pure(run)
    else:
        _assert_refused(run, outcome=expected)
        assert (workspace / ".nwave" / "config.yaml").read_bytes() == before


@pytest.mark.parametrize(
    "classic_signal",
    [
        ("config", (), "classic"),
        ("request", ("--mode", "classic"), "atdd_pure"),
        ("marker", ("--dispatch-marker", "workflow_mode=classic"), "atdd_pure"),
        ("carrier", ("--stop-context-mode", "classic"), "atdd_pure"),
        (
            "legacy-attestation",
            ("--classic-attestation", "copyable-human-proof.json"),
            "atdd_pure",
        ),
        ("legacy-source", ("--dispatch-source", "human"), "atdd_pure"),
    ],
    ids=lambda signal: signal[0],
)
def test_every_classic_selector_or_legacy_carrier_is_non_mutating_migration_refusal(
    tmp_path: Path, classic_signal: tuple[str, tuple[str, ...], str]
) -> None:
    signal, extra_args, configured_mode = classic_signal
    workspace = _configured_workspace(tmp_path, configured_mode)
    config = workspace / ".nwave" / "config.yaml"
    if signal == "config":
        config.write_text("workflow:\n  mode: classic\n", encoding="utf-8")
    before = config.read_bytes()

    run = _run_mode_in_process(workspace, extra_args=extra_args)

    _assert_refused(run, outcome="CLASSIC_MODE_REMOVED", reason="MIGRATION_REQUIRED")
    assert config.read_bytes() == before


def test_markerless_dispatch_is_never_a_synonym_for_classic(tmp_path: Path) -> None:
    workspace = _configured_workspace(tmp_path, "atdd_pure")
    run = _run_mode_in_process(workspace, extra_args=("--require-dispatch-marker",))
    _assert_refused(run, outcome="DISPATCH_MODE_UNRESOLVED")


def test_unhealthy_falsifier_halts_without_patching_or_selecting_a_mode(
    tmp_path: Path,
) -> None:
    workspace = _fresh_workspace(tmp_path)
    run = _run_mode_in_process(workspace, falsifier_state="UNHEALTHY")
    _assert_refused(run, outcome="HALTED_UNHEALTHY")
    assert not (workspace / ".nwave" / "config.yaml").exists(), run.output


def test_public_help_and_injected_guidance_never_offer_classic_as_selectable(
    tmp_path: Path,
) -> None:
    workspace = _fresh_workspace(tmp_path)
    help_run = _run_mode_in_process(workspace, extra_args=("--help",))
    assert help_run.exit_code == 0, help_run.output
    guidance = help_run.output.lower()
    assert "--classic-attestation" not in guidance
    assert "select classic" not in guidance
    assert "classic is removed" in guidance
    assert "migration" in guidance

    injection_run = _run_mode_in_process(
        workspace, extra_args=("--show-agent-guidance",)
    )
    assert injection_run.exit_code == 0, injection_run.output
    injection = injection_run.output.lower()
    assert "classic is removed" in injection
    assert "classic authorization" not in injection
    assert "atdd_pure" in injection


def test_benchmark_refuses_a_classic_request_before_workload_setup(
    tmp_path: Path,
) -> None:
    workspace = _configured_workspace(tmp_path, "classic")
    before = (workspace / ".nwave" / "config.yaml").read_bytes()
    run = _run_mode_in_process(workspace, operation="benchmark")
    _assert_refused(run, outcome="CLASSIC_MODE_REMOVED", reason="MIGRATION_REQUIRED")
    assert (workspace / ".nwave" / "config.yaml").read_bytes() == before
