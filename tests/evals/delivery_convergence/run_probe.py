"""Invoke one delivery-convergence fixture through its installed public role.

This is a bounded oracle consumer.  It never stubs a provider judgment and it
does not turn the fixture's semantic expectation into a provider response.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from contextlib import nullcontext
from pathlib import Path

from des.adapters.driven.task_invocation.model_envelope import (
    _schema_for,
    codex_schema_for,
    decode_model_run,
)
from des.adapters.driven.task_invocation.role_instructions import load_role_instructions
from des.domain.agent_capability import REPLY_CHANNEL_TOOLS
from des.ports.driven_ports.task_invocation_port import ModelRun
from scripts.install.plugins.opencode_common import parse_frontmatter


CASES_PATH = Path(__file__).with_name("cases.json")
NATIVE_ROLES = {
    "nw-user-examiner",
    "nw-acceptance-designer",
    "nw-acceptance-designer-reviewer",
}


def _case_by_id(case_id: str) -> dict[str, object]:
    corpus = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    for case in corpus["cases"]:
        if case["id"] == case_id:
            return case
    known = ", ".join(case["id"] for case in corpus["cases"])
    raise ValueError(f"unknown case {case_id!r}; known cases: {known}")


_CODEX_TOOL_FREE_VERSION = "codex-cli 0.156.1"
_CODEX_TOOL_FREE_FEATURES = (
    "apps",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "shell_tool",
    "unified_exec",
    "code_mode",
    "code_mode_host",
    "code_mode_only",
    "computer_use",
    "multi_agent",
    "multi_agent_v2",
    "image_generation",
    "in_app_browser",
    "in_app_local_automation",
    "js_repl",
    "js_repl_tools_only",
    "plugins",
    "request_permissions_tool",
    "skill_search",
    "sleep_tool",
    "standalone_web_search",
    "view_image",
)


def _codex_tool_free_options(run_root: Path, model: str) -> list[str]:
    """Preserve the original audited native profile; refuse drift before a turn."""
    version = subprocess.run(
        ["codex", "--version"],
        cwd=run_root,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    if version.stdout.strip() != _CODEX_TOOL_FREE_VERSION:
        raise ValueError("Codex tools-empty profile differs from audited CLI version")
    features = subprocess.run(
        ["codex", "features", "list"],
        cwd=run_root,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    observed = {line.split()[0] for line in features.stdout.splitlines() if line}
    if not set(_CODEX_TOOL_FREE_FEATURES).issubset(observed):
        raise ValueError("Codex tools-empty feature controls are unavailable")
    bundled = subprocess.run(
        ["codex", "debug", "models", "--bundled"],
        cwd=run_root,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    catalog = json.loads(bundled.stdout)
    models = catalog["models"]
    selected = [entry for entry in models if entry.get("slug") == model]
    if len(selected) != 1:
        raise ValueError("Codex tools-empty profile requires one exact bundled model")
    entry = selected[0]
    if (
        not isinstance(entry.get("base_instructions"), str)
        or not entry["base_instructions"]
        or not isinstance(entry.get("experimental_supported_tools"), list)
        or not all(
            isinstance(tool, str) for tool in entry["experimental_supported_tools"]
        )
        or "apply_patch_tool_type" not in entry
        or (
            entry["apply_patch_tool_type"] is not None
            and not isinstance(entry["apply_patch_tool_type"], str)
        )
        or (
            entry.get("tool_mode") is not None
            and not isinstance(entry["tool_mode"], str)
        )
    ):
        raise ValueError("Codex bundled model tool metadata is unusable")
    entry.update(
        apply_patch_tool_type=None,
        experimental_supported_tools=[],
        tool_mode=None,
    )
    catalog_path = run_root / "native-model-catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    options = [
        "-c",
        "model_catalog_json=" + json.dumps(str(catalog_path)),
        "-c",
        "mcp_servers={}",
        "-c",
        'web_search="disabled"',
        "-c",
        "project_doc_max_bytes=0",
        "-c",
        "skills.include_instructions=false",
        "-c",
        "orchestrator.skills.enabled=false",
        "-c",
        "orchestrator.mcp.enabled=false",
        "-c",
        "agents.enabled=false",
        "-c",
        "tools.experimental_request_user_input.enabled=false",
        "--enable",
        "skip_host_skill_discovery",
    ]
    for feature in (
        "memories",
        "goals",
        "send_message_to_user_async",
        "default_mode_request_user_input",
        *_CODEX_TOOL_FREE_FEATURES,
    ):
        options.extend(("--disable", feature))
    return options


def invoke_native_role(  # noqa: PLR0913 -- Keep role, provider, schema, and evidence context explicit.
    *,
    role: str,
    prompt: str,
    run_root: Path,
    framework_root: Path,
    model: str,
    provider: str = "claude",
    defect_values: tuple[str, ...] = (),
) -> tuple[ModelRun, dict[str, object], int]:
    """Eval-owned native invocation; never a production DES model executor."""
    if provider not in {"claude", "codex"}:
        raise ValueError(f"unsupported native eval provider: {provider}")
    spec = framework_root.resolve() / "nWave" / "agents" / f"{role}.md"
    instructions = load_role_instructions(spec)
    frontmatter, _ = parse_frontmatter(spec.read_text(encoding="utf-8"))
    declared = frontmatter["tools"]
    tools = (
        [tool.strip() for tool in declared.split(",") if tool.strip()]
        if isinstance(declared, str)
        else list(declared or [])
    )
    real_tools = set(tools) - REPLY_CHANNEL_TOOLS
    run_root = run_root.resolve()
    instructions_path = run_root / "role-instructions.txt"
    instructions_path.write_text(instructions, encoding="utf-8")
    schema_path = run_root / "result-schema.json"
    execution_cwd = run_root
    if provider == "claude":
        schema = _schema_for(role, defect_values=defect_values)
        schema_path.write_text(schema, encoding="utf-8")
        agents = {
            role: {
                "description": frontmatter["description"],
                "prompt": "Follow your complete role and mandatory skills in the appended system prompt.",
                "tools": tools,
            }
        }
        argv = [
            "claude",
            "-p",
            "--model",
            model,
            "--output-format",
            "json",
            "--agent",
            role,
            "--agents",
            json.dumps(agents),
            "--append-system-prompt-file",
            str(instructions_path),
            "--tools",
            ",".join(tools),
            "--allowedTools",
            ",".join([*tools, "StructuredOutput"]),
            "--json-schema",
            schema,
            "--setting-sources",
            "user",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--no-chrome",
            "--no-session-persistence",
        ]
    else:
        if not real_tools.issubset({"Read", "Glob", "Grep", "Bash", "Edit", "Write"}):
            raise ValueError("Codex cannot preserve this role's declared capabilities")
        schema_path.write_text(
            json.dumps(codex_schema_for(role, defect_values=defect_values)),
            encoding="utf-8",
        )
        terminal_path = run_root / "native.answer.json"
        options = []
        if not real_tools:
            options = _codex_tool_free_options(run_root, model)
        sandbox = "workspace-write" if real_tools & {"Edit", "Write"} else "read-only"
        argv = [
            "codex",
            "exec",
            "--strict-config",
            "--ephemeral",
            "--ignore-user-config",
            "--skip-git-repo-check",
            "--sandbox",
            sandbox,
            "--model",
            model,
            "-c",
            "developer_instructions="
            + json.dumps(
                f"Native eval role: {role}. Follow these exact role instructions and mandatory skills.\n"
                + instructions
            ),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(terminal_path),
            "--json",
            "-C",
            str(execution_cwd),
            *options,
        ]
    workspace = (
        tempfile.TemporaryDirectory(prefix="nwave-native-eval-")
        if not real_tools
        else nullcontext(str(run_root))
    )
    with workspace as native_root:
        if provider == "codex":
            argv[argv.index("-C") + 1] = native_root
        (run_root / "native.argv.json").write_text(json.dumps(argv), encoding="utf-8")
        native = subprocess.run(
            argv,
            input=prompt,
            text=True,
            capture_output=True,
            cwd=native_root,
            timeout=300,
        )
    (run_root / "native.stdout.json").write_text(native.stdout, encoding="utf-8")
    (run_root / "native.stderr.txt").write_text(native.stderr, encoding="utf-8")
    (run_root / "native.exit-status").write_text(
        str(native.returncode), encoding="utf-8"
    )
    if native.returncode != 0:
        raise RuntimeError(
            f"native {provider} exited {native.returncode}; see native.stderr.txt"
        )
    if provider == "claude":
        envelope = json.loads(native.stdout)
        if envelope.get("is_error"):
            raise RuntimeError(
                "native Claude returned an error envelope; see native.stdout.json"
            )
    else:
        # Codex stdout is event transport; only its terminal file supplies the answer.
        envelope = {
            "structured_output": json.loads(terminal_path.read_text(encoding="utf-8"))[
                "answer"
            ]
        }
        for line in native.stdout.splitlines():
            event = json.loads(line)
            if event.get("type") == "thread.started":
                envelope["session_id"] = event.get("thread_id")
            elif event.get("type") == "turn.completed":
                envelope["usage"] = event.get("usage")
    run = decode_model_run(
        envelope["structured_output"],
        role_id=role,
        defect_values=defect_values,
    )
    return run, envelope, native.returncode


def _decoded_judgment(run: ModelRun) -> dict[str, object]:
    """Project the shared decoder's typed outcome without parsing diagnostic prose."""
    # ``run`` is a ModelRun; keeping this narrow projection local avoids making
    # provider stdout a second semantic channel.
    review_defect = run.review_defect
    return {
        "outcome": run.outcome.value,
        "diagnostic": run.diagnostic,
        "review_defect": (
            None
            if review_defect is None
            else {"owner": review_defect.owner.value, "value": review_defect.value}
        ),
    }


def _fresh_invocation_directory(output_root: Path, case_id: str) -> Path:
    """Create one new evidence directory without overwriting an earlier run."""
    case_root = output_root / case_id
    case_root.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        candidate = case_root / f"invocation-{index:04d}"
        try:
            candidate.mkdir()
        except FileExistsError:
            index += 1
            continue
        return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--framework-root", type=Path, default=Path(__file__).resolve().parents[3]
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--provider", choices=("claude", "codex"), default="claude")
    args = parser.parse_args()

    case = _case_by_id(args.case)
    role = str(case["target"])
    if role not in NATIVE_ROLES:
        print(
            json.dumps(
                {
                    "case": args.case,
                    "outcome": "not-run",
                    "reason": (
                        f"{role} is an installed skill/outer-route concern, not a native "
                        "specialist role selectable by this native eval; run it through "
                        "the normal installed outer route described in README.md"
                    ),
                }
            )
        )
        return 3

    run_root = _fresh_invocation_directory(args.output_root, args.case)
    prompt = json.dumps(case["public_input"])
    (run_root / "prompt.json").write_text(prompt + "\n", encoding="utf-8")

    started = time.monotonic()
    try:
        review_values = tuple(case.get("review_defect_values", []))
        run, envelope, exit_status = invoke_native_role(
            role=role,
            prompt=prompt,
            run_root=run_root,
            framework_root=args.framework_root,
            model=args.model,
            provider=args.provider,
            defect_values=review_values,
        )
        expected_outcomes = case.get("expected_provider_outcomes")
        typed_match = (
            None
            if expected_outcomes is None
            else run.outcome.value in expected_outcomes
        )
        result: dict[str, object] = {
            "case": args.case,
            "role": role,
            "provider": args.provider,
            "invocation_directory": str(run_root),
            "expected": case["expected"],
            "outcome": run.outcome.value,
            "typed_judgment_matches_expected": typed_match,
            "decoded_judgment": _decoded_judgment(run),
            "raw_structured_judgment": envelope["structured_output"],
            "raw_structured_judgment_note": "Native stdout retained in native.stdout.json.",
            "issued": True,
            "exit_status": exit_status,
            "diagnostic": run.diagnostic,
            "accounting": {
                key: envelope.get(key)
                for key in ("total_cost_usd", "usage", "modelUsage", "duration_ms")
            },
            "seconds": time.monotonic() - started,
            "run_id": envelope.get("session_id"),
        }
    except Exception as error:
        result = {
            "case": args.case,
            "role": role,
            "provider": args.provider,
            "invocation_directory": str(run_root),
            "outcome": "indeterminate",
            "error": type(error).__name__,
            "detail": str(error),
            "seconds": time.monotonic() - started,
            "run_id": None,
        }
    (run_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True), flush=True)
    if not result.get("issued") or result.get("exit_status") != 0:
        return 1
    # A process exit says only that the role run completed. Where the fixture
    # declares a typed expectation, fail on a differing semantic outcome.
    return 1 if result.get("typed_judgment_matches_expected") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
