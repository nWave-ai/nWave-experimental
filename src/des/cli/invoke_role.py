"""Issue one explicitly selected host role through the configured adapter."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.task_invocation.configured_task_adapter import (
    ConfiguredTaskAdapter,
)
from des.application.delivery_steps import DeliverySteps
from des.cli.role_artifacts import load_prepared, record_model
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    refuse,
    resolved_root,
    succeed,
)
from des.runtime.packaged_asset import installed_package_root
from des.runtime.spawn import GIT_TIMEOUT_ENV, SpawnTimeout, git_timeout_seconds, spawn


def main(argv=None):
    parser = argparse.ArgumentParser(prog="des invoke-role")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--role", choices=("reviewer", "examiner"), required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--provider", choices=("claude", "codex"), required=True)
    parser.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(root, NOTHING_OWED)
    try:
        expected = (
            root / ".nwave/des/logs/roles" / f"{args.candidate}-{args.role}-input.json"
        )
        if (root / args.input).resolve() != expected.resolve():
            raise ValueError("input is not the persisted prepared artifact")
        _, payload, _ = load_prepared(root, args.role, args.candidate)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        return refuse(
            StepRefusal(
                "RoleInputUnavailable", str(error), "use the exact prepare-role INPUT"
            ),
            NOTHING_OWED,
        )
    role_id = (
        "nw-software-crafter-reviewer"
        if args.role == "reviewer"
        else "nw-user-examiner"
    )
    config = DESConfig(cwd=root)
    runtime = config.role_runtime(role_id, framework_root=installed_package_root())
    if runtime.provider.value != args.provider:
        return refuse(
            StepRefusal(
                "ProviderSelectionMismatch",
                f"configured {runtime.provider.value} does not match requested {args.provider}",
                "select the configured provider",
            ),
            NOTHING_OWED,
        )
    port = ConfiguredTaskAdapter(root, config, resolved_runtimes={role_id: runtime})
    steps = DeliverySteps(invoker=port)
    context_root = Path.home() / ".nwave" / "recovery" / "role-contexts"
    context_root.mkdir(parents=True, exist_ok=True)
    cwd = Path(
        tempfile.mkdtemp(prefix=f"{args.role}-{args.candidate}-", dir=context_root)
    )
    terminal: StepRefusal | None = None
    success: tuple[str, str, str] | None = None
    cleanup_note: str | None = None
    checkout_created = False
    turns_bought = 0
    invoked_role: str | None = None
    if args.role == "reviewer":
        try:
            cwd.rmdir()
            observed = spawn(
                ["git", "worktree", "add", "--detach", str(cwd), args.candidate],
                cwd=root,
                timeout=git_timeout_seconds(),
                timeout_env=GIT_TIMEOUT_ENV,
                capture_output=True,
                text=True,
            )
        except (OSError, SpawnTimeout) as error:
            terminal = StepRefusal(
                "CandidateCheckoutUnavailable",
                str(error),
                "restore candidate checkout",
            )
            cleanup_note = f"RETAINED-CONTEXT: {cwd}: checkout was not created"
        else:
            if observed.returncode:
                terminal = StepRefusal(
                    "CandidateCheckoutUnavailable",
                    observed.stderr,
                    "restore candidate checkout",
                )
                cleanup_note = f"RETAINED-CONTEXT: {cwd}: checkout was not created"
            else:
                checkout_created = True
    try:
        if terminal is None:
            invocation = steps.invoke_role(root, cwd, role_id, json.dumps(payload))
            turns_bought = invocation.outcome.turns_bought
            invoked_role = invocation.outcome.role
            if not invocation.outcome.succeeded:
                assert invocation.outcome.failure is not None
                terminal = StepRefusal(
                    invocation.outcome.failure.what,
                    invocation.outcome.failure.why,
                    invocation.outcome.failure.how,
                    invocation.outcome.disposition,
                )
            else:
                assert invocation.model_run is not None
                success = record_model(
                    root,
                    args.role,
                    args.candidate,
                    args.provider,
                    runtime.model,
                    invocation.model_run,
                )
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        terminal = StepRefusal(
            "RoleResultUnrecordable", str(error), "inspect role result storage"
        )
    finally:
        if args.role == "reviewer" and checkout_created:
            try:
                removed = spawn(
                    ["git", "worktree", "remove", str(cwd)],
                    cwd=root,
                    timeout=git_timeout_seconds(),
                    timeout_env=GIT_TIMEOUT_ENV,
                    capture_output=True,
                    text=True,
                )
            except (OSError, SpawnTimeout) as error:
                cleanup_note = f"RETAINED-CONTEXT: {cwd}: {error}"
            else:
                if removed.returncode:
                    cleanup_note = f"RETAINED-CONTEXT: {cwd}: {removed.stderr.strip()}"
        elif args.role == "examiner":
            try:
                cwd.rmdir()
            except OSError as error:
                cleanup_note = f"RETAINED-CONTEXT: {cwd}: {error}"
    if terminal is not None:
        why = terminal.why + ("; " + cleanup_note if cleanup_note else "")
        return refuse(
            StepRefusal(terminal.what, why, terminal.how, terminal.disposition),
            NOTHING_OWED,
            turns_bought=turns_bought,
            role=invoked_role,
        )
    assert success is not None
    outcome, result, digest = success
    return succeed(
        [
            f"ROLE: {args.role}",
            f"CANDIDATE: {args.candidate}",
            f"OUTCOME: {outcome}",
            f"RESULT: {result}",
            f"RESULT-SHA256: {digest}",
            *(() if cleanup_note is None else (cleanup_note,)),
        ],
        NOTHING_OWED,
        turns_bought=turns_bought,
        role=invoked_role,
    )
