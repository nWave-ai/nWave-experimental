"""Control-plane ATs that prevent a classic execution path from surviving.

These examples deliberately drive the legacy public seams.  Removing only the
new selector is insufficient if an older resolver, hook carrier, falsifier, or
packaged instruction can still construct the retired spine.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.common.in_process_cli import run_cli_in_process, run_hook_in_process


_CLASSIC_REMOVED = "CLASSIC_MODE_REMOVED"
_MIGRATION_REQUIRED = "MIGRATION_REQUIRED"
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


def _is_explicit_read_only_history(line: str) -> bool:
    lowered = line.lower()
    return (
        "read-only" in lowered
        and ("replay" in lowered or "migration" in lowered)
        and _ACTIVE_MODE_ALIAS.search(lowered) is not None
    )


def _active_mode_carriers(path: Path, *, display_root: Path) -> list[str]:
    """Find executable aliases while preserving explicit read-only history."""
    offenders: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _is_explicit_read_only_history(line):
            continue
        if _EXECUTABLE_CARRIER.search(line):
            offenders.append(
                f"{path.relative_to(display_root)}:{line_number}: {line.strip()!r}"
            )
    return offenders


def _write_mode(project: Path, mode: str) -> bytes:
    config = project / ".nwave" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(f"workflow:\n  mode: {mode}\n", encoding="utf-8")
    return config.read_bytes()


def _assert_removal_payload(payload: dict[str, object]) -> None:
    assert payload.get("outcome") == _CLASSIC_REMOVED, payload
    assert payload.get("reason_code") == _MIGRATION_REQUIRED, payload
    assert payload.get("effective_mode") is None, payload
    diagnostic = str(payload.get("diagnostic", ""))
    assert all(word in diagnostic for word in ("WHAT", "WHY", "HOW")), diagnostic


def _as_payload(result: object) -> dict[str, object]:
    if isinstance(result, dict):
        return result
    return vars(result)


@pytest.mark.parametrize(
    "resolver_name", ("resolve_workflow_mode", "resolve_dispatch_mode")
)
def test_every_legacy_mode_resolver_refuses_instead_of_returning_active_classic(
    tmp_path: Path,
    resolver_name: str,
) -> None:
    _write_mode(tmp_path, "classic")
    if resolver_name == "resolve_workflow_mode":
        from des.application.workflow_mode import resolve_workflow_mode

        result = resolve_workflow_mode(tmp_path)
    else:
        from des.cli.init_log import resolve_dispatch_mode

        result = resolve_dispatch_mode(tmp_path)

    assert not isinstance(result, str), (
        f"{resolver_name} leaked the executable mode string {result!r}"
    )
    _assert_removal_payload(_as_payload(result))


@pytest.mark.parametrize(
    "mode",
    (
        "classic",
        "'classic'",
        '"classic"',
        "classic # copied legacy config",
    ),
)
@pytest.mark.parametrize(
    "resolver_name", ("resolve_workflow_mode", "resolve_dispatch_mode")
)
def test_legacy_resolvers_cannot_reactivate_classic_from_copied_config_bytes(
    tmp_path: Path,
    mode: str,
    resolver_name: str,
) -> None:
    """Quoting, comments, and copied text cannot turn classic into a mode."""
    config = tmp_path / ".nwave" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(f"workflow:\n  mode: {mode}\n", encoding="utf-8")
    before = config.read_bytes()

    if resolver_name == "resolve_workflow_mode":
        from des.application.workflow_mode import resolve_workflow_mode

        result = resolve_workflow_mode(tmp_path)
    else:
        from des.cli.init_log import resolve_dispatch_mode

        result = resolve_dispatch_mode(tmp_path)

    assert not isinstance(result, str), (
        f"{resolver_name} made classic executable with {result!r}"
    )
    _assert_removal_payload(_as_payload(result))
    assert config.read_bytes() == before
    assert not (tmp_path / "execution-log.json").exists()


def test_pre_tool_use_refuses_classic_marker_before_legacy_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from des.adapters.drivers.hooks import pre_tool_use_handler

    legacy_service_called = False

    class LegacyService:
        def validate(self, *_args: object, **_kwargs: object) -> SimpleNamespace:
            nonlocal legacy_service_called
            legacy_service_called = True
            return SimpleNamespace(action="allow")

    monkeypatch.setattr(
        pre_tool_use_handler,
        "_peek_wave_entering",
        lambda *_args: (False, None),
    )
    monkeypatch.setattr(
        pre_tool_use_handler,
        "_arm_inferred_fallback",
        lambda *_args: (False, None),
    )
    monkeypatch.setattr(
        pre_tool_use_handler,
        "_resolve_deliverable_type",
        lambda: None,
    )
    monkeypatch.setattr(
        pre_tool_use_handler.service_factory,
        "create_pre_tool_use_service",
        lambda **_kwargs: LegacyService(),
    )
    hook_input = {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "nw-software-crafter",
            "prompt": "\n".join(
                (
                    "<!-- DES-VALIDATION : required -->",
                    "<!-- DES-MODE : classic -->",
                    "<!-- DES-PROJECT-ID : retired-spine -->",
                    "<!-- DES-STEP-ID : 01-01 -->",
                )
            ),
        },
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
    output = io.StringIO()
    monkeypatch.setattr("sys.stdout", output)

    exit_code = pre_tool_use_handler.handle_pre_tool_use()

    assert exit_code != 0
    _assert_removal_payload(json.loads(output.getvalue()))
    assert legacy_service_called is False


def test_subagent_stop_direct_classic_carrier_refuses_before_execution_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from des.adapters.drivers.hooks import subagent_stop_handler

    execution_log = tmp_path / "execution-log.json"
    execution_log.write_text(
        '{"schema_version":"5.0","feature_id":"retired-spine","events":[]}',
        encoding="utf-8",
    )
    before = execution_log.read_bytes()
    legacy_service_called = False

    def forbidden_service() -> object:
        nonlocal legacy_service_called
        legacy_service_called = True
        raise AssertionError("classic service must be unreachable")

    monkeypatch.setattr(
        subagent_stop_handler.service_factory,
        "create_subagent_stop_service",
        forbidden_service,
    )
    hook_input = {
        "executionLogPath": str(execution_log),
        "projectId": "retired-spine",
        "stepId": "01-01",
        "workflowMode": "classic",
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(hook_input)))
    output = io.StringIO()
    monkeypatch.setattr("sys.stdout", output)

    exit_code = subagent_stop_handler.handle_subagent_stop()

    assert exit_code != 0
    _assert_removal_payload(json.loads(output.getvalue()))
    assert execution_log.read_bytes() == before
    assert legacy_service_called is False


def test_init_log_refuses_classic_without_creating_or_touching_a_log(
    tmp_path: Path,
) -> None:
    before = _write_mode(tmp_path, "classic")
    exit_code, stdout, stderr = run_cli_in_process(
        ["init-log", "--project-dir", str(tmp_path), "--feature-id", "retired-spine"],
        cwd=tmp_path,
    )
    assert exit_code != 0
    assert _CLASSIC_REMOVED in stdout + stderr
    assert _MIGRATION_REQUIRED in stdout + stderr
    assert (tmp_path / ".nwave" / "config.yaml").read_bytes() == before
    assert not (tmp_path / "execution-log.json").exists()


def test_shipped_registry_and_manifest_contain_only_atdd_pure_as_active_flavor() -> (
    None
):
    repo = Path(__file__).resolve().parents[4]
    flavors = repo / "nWave" / "flavors"
    assert {path.name for path in flavors.glob("*.yaml")} == {
        "_schema.yaml",
        "atdd_pure.yaml",
    }
    schema = (flavors / "_schema.yaml").read_text(encoding="utf-8")
    assert "classic" not in schema.lower()
    manifest_text = (repo / "pyproject.toml").read_text(encoding="utf-8")
    assert "classic.yaml" not in manifest_text


@pytest.mark.parametrize(
    ("member", "content"),
    (
        ("nWave/flavors/classic.yaml", "flavor_id: classic\n"),
        (
            "nWave/nWave/tasks/nw/execute.md",
            "workflow.mode = retired workflow: use this dispatch template verbatim\n",
        ),
        (
            "nWave/nWave/skills/nw-deliver-atdd-pure-slice-gates/SKILL.md",
            "On breach patch .nwave/config.yaml workflow.mode = retired workflow\n",
        ),
    ),
    ids=("literal-classic", "retired-workflow-template", "retired-workflow-mutation"),
)
def test_candidate_archive_cannot_contain_a_classic_flavor_or_dispatch_template(
    tmp_path: Path,
    member: str,
    content: str,
) -> None:
    """An archive-shaped candidate with retired executable assets is rejected.

    The release lane passes a candidate as an explicit input.  This test only
    creates the hostile input; it deliberately never builds or downloads a
    wheel, which would examine a different artifact than the one under test.
    """
    stale_candidate = tmp_path / "nwave_ai-legacy.whl"
    with zipfile.ZipFile(stale_candidate, "w") as archive:
        archive.writestr(member, content)

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    exit_code, stdout, stderr = run_cli_in_process(
        [
            "resolve-workflow-mode",
            "--project-dir",
            str(workspace),
            "--operation",
            "deliver",
            "--candidate-wheel",
            str(stale_candidate),
            "--json",
        ],
        cwd=workspace,
    )
    payload = json.loads(stdout)
    assert exit_code != 0, stdout + stderr
    assert payload["outcome"] == "CANDIDATE_INCOMPATIBLE"
    assert payload["effective_mode"] is None
    assert not (workspace / ".nwave").exists()


def test_live_tasks_skills_help_and_injection_offer_no_selectable_classic_branch() -> (
    None
):
    repo = Path(__file__).resolve().parents[4]
    live_roots = (
        repo / "nWave" / "tasks",
        repo / "nWave" / "skills",
        repo / "nWave" / "agents",
        repo / "nWave" / "data" / "orchestrator-affordance",
    )
    offenders: list[str] = []
    saw_removal_guidance = False
    for root in live_roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".md", ".yaml", ".json"}:
                continue
            text = path.read_text(encoding="utf-8").lower()
            saw_removal_guidance |= (
                "classic" in text and "removed" in text and "migration" in text
            )
            offenders.extend(_active_mode_carriers(path, display_root=repo))
    assert not offenders, "\n".join(offenders)
    assert saw_removal_guidance, "classic residue must explain removal and migration"


def test_live_catalog_has_no_classic_only_task_or_skill_template() -> None:
    """A discoverable classic-named asset is itself a selectable carrier."""
    repo = Path(__file__).resolve().parents[4]
    catalog_roots = (repo / "nWave" / "tasks", repo / "nWave" / "skills")
    classic_assets = [
        path.relative_to(repo)
        for root in catalog_roots
        for path in root.rglob("*")
        if path.is_file() and "classic" in path.relative_to(repo).as_posix().lower()
    ]
    assert not classic_assets, "\n".join(str(path) for path in classic_assets)


# ---------------------------------------------------------------------------
# RELOOP_B — exercise the live hook paths and semantic asset surface, not a
# resolver/helper or a line-local alias regex.
# ---------------------------------------------------------------------------


def _seed_legacy_deliver_state(
    project: Path, project_id: str
) -> tuple[Path, Path, Path]:
    """Create a valid old-style state whose mutation would be observable."""
    deliver = project / "docs" / "feature" / project_id / "deliver"
    deliver.mkdir(parents=True)
    roadmap = deliver / "roadmap.json"
    execution_log = deliver / "execution-log.json"
    progress = deliver / ".develop-progress.json"
    roadmap.write_text(
        json.dumps({"project_id": project_id, "steps": [{"id": "01-01"}]})
    )
    execution_log.write_text(json.dumps({"project_id": project_id, "events": []}))
    return roadmap, execution_log, progress


def _legacy_transcript(path: Path, project_id: str) -> Path:
    """Write the same JSONL shape the live SubagentStop hook consumes."""
    entry = {
        "type": "user",
        "message": {
            "role": "user",
            "content": "\n".join(
                (
                    "<!-- DES-VALIDATION : required -->",
                    "<!-- DES-MODE : classic -->",
                    f"<!-- DES-PROJECT-ID : {project_id} -->",
                    "<!-- DES-STEP-ID : 01-01 -->",
                )
            ),
        },
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    return path


def _bytes_or_absent(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def test_real_router_refuses_legacy_deliver_progress_before_any_legacy_write(
    tmp_path: Path,
) -> None:
    """A registered ``deliver-progress`` hook must not replay classic state.

    This drives ``hook_router.main`` -- including activation gating and the
    installed command token -- rather than testing the selection helper or a
    candidate archive string.  The seeded roadmap/log make a surviving legacy
    path write ``.develop-progress.json`` deterministically.
    """
    from des.adapters.drivers.hooks import hook_router

    project = tmp_path / "project"
    project.mkdir()
    nwave = project / ".nwave"
    nwave.mkdir()
    # The real router must be active to reach the registered handler.  This is
    # setup state, so its bytes are included in the no-write witness below.
    local_config = nwave / "local-config.json"
    local_config.write_text('{"enabled_for_repo": true}\n', encoding="utf-8")
    config = nwave / "config.yaml"
    config.write_text("workflow:\n  mode: classic\n", encoding="utf-8")
    nested_gitignore = nwave / ".gitignore"
    nested_gitignore.write_text("existing nested rule\n", encoding="utf-8")
    root_gitignore = project / ".gitignore"
    root_gitignore.write_text("existing root rule\n", encoding="utf-8")

    project_id = "legacy-feature"
    roadmap, execution_log, progress = _seed_legacy_deliver_state(project, project_id)
    transcript = _legacy_transcript(project / "legacy-agent.jsonl", project_id)
    watched = (
        roadmap,
        execution_log,
        progress,
        config,
        local_config,
        nested_gitignore,
        root_gitignore,
    )
    before = {path: _bytes_or_absent(path) for path in watched}
    envelope = json.dumps(
        {
            "hook_event_name": "SubagentStop",
            "cwd": str(project),
            "agent_transcript_path": str(transcript),
        }
    )

    exit_code, stdout, stderr = run_hook_in_process(
        hook_router.main,
        stdin_text=envelope,
        cwd=project,
        argv=["hook_router", "deliver-progress"],
    )

    assert exit_code != 0, stdout + stderr
    payload = json.loads(stdout)
    _assert_removal_payload(payload)
    assert {path: _bytes_or_absent(path) for path in watched} == before


def _quieten_session_start_side_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the real SessionStart ordering while silencing unrelated services."""
    from des.adapters.drivers.hooks import session_start_handler

    monkeypatch.setattr(
        session_start_handler, "_apply_pending_update_if_any", lambda *_: None
    )
    monkeypatch.setattr(session_start_handler, "_run_housekeeping", lambda *_: None)
    monkeypatch.setattr(
        session_start_handler,
        "_build_update_check_service",
        lambda *_: SimpleNamespace(
            check_for_updates=lambda: SimpleNamespace(status=None)
        ),
    )
    monkeypatch.setattr(session_start_handler, "run_probe", lambda: None)
    monkeypatch.setattr(
        session_start_handler, "build_gate_affordance_nudge", lambda *_: None
    )
    monkeypatch.setattr(
        session_start_handler, "_emit_hook_version_skew_finding", lambda *_: None
    )
    monkeypatch.setattr(
        session_start_handler, "_maybe_tick_work_exhausted", lambda *_: None
    )
    monkeypatch.setattr(
        session_start_handler, "_maybe_tick_bugfix_pipeline", lambda *_: None
    )
    monkeypatch.setattr(
        session_start_handler, "_maybe_tick_consolidation_intake", lambda *_: None
    )


@pytest.mark.parametrize(
    ("kind", "config_text", "expected_tokens"),
    (
        ("fresh", None, ("atdd_pure",)),
        ("legacy-unset", "workflow: {}\n", ("WHAT", "WHY", "HOW", "atdd_pure")),
        (
            "classic",
            "workflow:\n  mode: classic\n",
            ("WHAT", "WHY", "HOW", "classic", "removed", "conversion"),
        ),
    ),
)
def test_real_session_start_emits_mode_guidance_without_prior_use_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    config_text: str | None,
    expected_tokens: tuple[str, ...],
) -> None:
    """The full SessionStart handler must guide, not silently adopt or repair."""
    from des.adapters.drivers.hooks import session_start_handler

    project = tmp_path / kind
    project.mkdir()
    # Prior-use evidence is intentional: it proves that SessionStart's earlier
    # adoption branch cannot mutate before the workflow refusal/guidance seam.
    evidence = project / "docs" / "feature" / "old-work" / "feature-delta.md"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("prior nWave use\n", encoding="utf-8")
    config = project / ".nwave" / "config.yaml"
    if config_text is not None:
        config.parent.mkdir()
        config.write_text(config_text, encoding="utf-8")

    watched = (
        config,
        project / ".nwave" / "local-config.json",
        project / ".nwave" / ".gitignore",
        project / ".gitignore",
    )
    before = {path: _bytes_or_absent(path) for path in watched}
    _quieten_session_start_side_services(monkeypatch)
    envelope = json.dumps({"hook_event_name": "SessionStart", "cwd": str(project)})

    exit_code, stdout, stderr = run_hook_in_process(
        session_start_handler.handle_session_start,
        stdin_text=envelope,
        cwd=project,
    )

    assert exit_code == 0, stderr
    # `handle_session_start` folds every contributor into ONE combined JSON
    # object per invocation, always in the wrapped `hookSpecificOutput` form
    # (see its module docstring) -- accept that form here. The bare
    # top-level `{"additionalContext": ...}` form is dropped by current
    # Claude Code and is no longer emitted; a fallback read is kept only so
    # a regression back to the bare form still surfaces guidance instead of
    # silently reading empty.
    guidance_parts: list[str] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        payload = json.loads(stripped)
        hso = payload.get("hookSpecificOutput")
        if isinstance(hso, dict) and isinstance(hso.get("additionalContext"), str):
            guidance_parts.append(hso["additionalContext"])
        elif isinstance(payload.get("additionalContext"), str):
            guidance_parts.append(payload["additionalContext"])
    guidance = "\n".join(guidance_parts).lower()
    assert all(token.lower() in guidance for token in expected_tokens), stdout
    assert {path: _bytes_or_absent(path) for path in watched} == before


_RETIRED_EXECUTABLE_INSTRUCTION = re.compile(
    r"(?:"
    r"\b(?:classic|retired[ _-]?workflow)\b[^\n]{0,160}\b(?:default|fallback|"
    r"select|dispatch|spine|authorization|opt-?in|switch|mode|roadmap|"
    r"execution[ _-]?log|run|load|create|resume|skip)\b|"
    r"\b(?:select|dispatch|switch(?:es)?|run|load|use|create|resume|write)\b"
    r"[^\n]{0,160}\b(?:classic|retired[ _-]?workflow)\b"
    r")",
    re.IGNORECASE,
)


def _is_dedicated_read_only_migration_or_replay_surface(path: Path, text: str) -> bool:
    """A notice is not a surface: history needs a dedicated, typed location."""
    typed_directory = any(
        token in {"migration", "migrations", "replay", "replays"}
        for token in path.parts
    )
    header = "\n".join(text.splitlines()[:12]).lower()
    return (
        typed_directory
        and "read-only" in header
        and ("migration" in header or "replay" in header)
    )


def test_active_dispatched_assets_do_not_keep_retired_execution_instructions() -> None:
    """Line-local read-only notices cannot convert an active command into history."""
    repo = Path(__file__).resolve().parents[4]
    active_roots = (
        repo / "nWave" / "tasks",
        repo / "nWave" / "skills",
        repo / "nWave" / "agents",
        repo / "nWave" / "data" / "orchestrator-affordance",
    )
    offenders: list[str] = []
    for root in active_roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {
                ".md",
                ".yaml",
                ".yml",
                ".json",
            }:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if _is_dedicated_read_only_migration_or_replay_surface(path, text):
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if _RETIRED_EXECUTABLE_INSTRUCTION.search(line):
                    offenders.append(
                        f"{path.relative_to(repo)}:{line_number}: {line.strip()!r}"
                    )
    assert not offenders, "\n".join(offenders[:40])
