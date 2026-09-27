"""Issue one explicitly selected host role through the configured adapter."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.task_invocation.configured_task_adapter import (
    ConfiguredTaskAdapter,
)
from des.application.delivery_steps import DeliverySteps
from des.cli.role_artifacts import (
    ModelInvocation,
    load_prepared,
    load_prepared_at,
    load_selected_revision_recovery,
    record_model,
    record_selected_revision_recovery,
)
from des.cli.role_guidance import role_id, successor_next
from des.cli.step_terminal import (
    NOTHING_OWED,
    StepRefusal,
    refuse,
    resolved_root,
    succeed,
)
from des.domain.model_runtime import ModelRuntimeConfigError
from des.runtime.packaged_asset import installed_package_root
from des.runtime.spawn import GIT_TIMEOUT_ENV, SpawnTimeout, git_timeout_seconds, spawn


def main(argv=None):
    parser = argparse.ArgumentParser(prog="des invoke-role")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--role",
        choices=("reviewer", "examiner", "acceptance-designer"),
        required=True,
        help="reviewer/examiner require --candidate; acceptance-designer requires the recovery task",
    )
    parser.add_argument(
        "--candidate", help="verified candidate; reviewer/examiner only"
    )
    parser.add_argument(
        "--task",
        choices=("selected-revision-recovery",),
        help="acceptance-designer only",
    )
    parser.add_argument("--provider", choices=("claude", "codex"), required=True)
    parser.add_argument(
        "--input", required=True, help="exact INPUT printed by des prepare-role"
    )
    args = parser.parse_args(argv)
    root = resolved_root(args.repo_root)
    if isinstance(root, StepRefusal):
        return refuse(root, NOTHING_OWED)
    recovery = args.role == "acceptance-designer"
    try:
        if recovery:
            if args.task != "selected-revision-recovery" or args.candidate is not None:
                raise ValueError(
                    "acceptance-designer requires --task selected-revision-recovery and no --candidate"
                )
            match = re.fullmatch(
                r"value-([1-9][0-9]*)-acceptance-designer-selected-revision-recovery(?:-[0-9a-f]{64})?-input\.json",
                Path(args.input).name,
            )
            if match is None:
                raise ValueError("input is not a persisted recovery artifact")
            value = int(match.group(1))
            expected = root / ".nwave/des/logs/roles" / Path(args.input).name
            if (root / args.input).resolve() != expected.resolve():
                raise ValueError("input is not the persisted recovery artifact")
            _, payload, _ = load_selected_revision_recovery(root, value, expected)
        else:
            if args.candidate is None or args.task is not None:
                raise ValueError(
                    "reviewer and examiner require --candidate and no --task"
                )
            if args.role == "examiner":
                expected, payload, _ = load_prepared_at(
                    root, args.role, args.candidate, Path(args.input)
                )
            else:
                expected = (
                    root
                    / ".nwave/des/logs/roles"
                    / f"{args.candidate}-{args.role}-input.json"
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
    config = DESConfig(cwd=root)
    selected_role_id = role_id(args.role)
    try:
        runtime = config.role_runtime(
            selected_role_id, framework_root=installed_package_root()
        )
    except ModelRuntimeConfigError as error:
        return refuse(
            StepRefusal(
                "RoleRuntimeUnavailable",
                str(error),
                "configure one provider and model for the selected role",
            ),
            NOTHING_OWED,
        )
    if runtime.provider.value != args.provider:
        return refuse(
            StepRefusal(
                "ProviderSelectionMismatch",
                f"configured {runtime.provider.value} does not match requested {args.provider}",
                "select the configured provider",
            ),
            NOTHING_OWED,
        )
    port = ConfiguredTaskAdapter(
        root, config, resolved_runtimes={selected_role_id: runtime}
    )
    steps = DeliverySteps(invoker=port)
    # Recovery binds to the sealed B revision's declared oracle target and
    # acceptance supports: the role must read them to realign or extend, so
    # its execution cwd is the real working tree that names them, never an
    # empty scratch directory. Read-only-by-construction comes from the
    # adapter's tool ceiling for this task, not from filesystem isolation.
    if recovery:
        cwd = root
    else:
        context_root = Path.home() / ".nwave" / "recovery" / "role-contexts"
        context_root.mkdir(parents=True, exist_ok=True)
        cwd = Path(
            tempfile.mkdtemp(prefix=f"{args.role}-{args.candidate}-", dir=context_root)
        )
    terminal: StepRefusal | None = None
    success: tuple[str, str, str, str | None, str | None] | None = None
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
            invocation = steps.invoke_role(
                root,
                cwd,
                selected_role_id,
                json.dumps(payload),
                "selected-revision-recovery" if recovery else None,
            )
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
                if recovery:
                    success = record_selected_revision_recovery(
                        root,
                        value,
                        ModelInvocation(
                            provider=args.provider,
                            model=runtime.model,
                            run=invocation.model_run,
                        ),
                        expected,
                    )
                else:
                    outcome, result, digest = record_model(
                        root,
                        args.role,
                        args.candidate,
                        ModelInvocation(
                            provider=args.provider,
                            model=runtime.model,
                            run=invocation.model_run,
                        ),
                        expected if args.role == "examiner" else None,
                    )
                    success = (outcome, result, digest, None, None)
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
        elif not recovery:
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
    outcome, result, digest, document, document_digest = success
    facts = [
        f"ROLE: {args.role}",
        f"OUTCOME: {outcome}",
        f"RESULT: {result}",
        f"RESULT-SHA256: {digest}",
        *(() if cleanup_note is None else (cleanup_note,)),
    ]
    if recovery:
        facts.extend(("TASK: selected-revision-recovery", f"VALUE: {value}"))
        if document is not None:
            facts.extend(
                (
                    f"DISTILL-DOCUMENT: {document}",
                    f"DISTILL-DOCUMENT-SHA256: {document_digest}",
                )
            )
        next_step = "caller may pass the exact DISTILL-DOCUMENT bytes unchanged to des distill --replace-current --input -"
    else:
        facts.insert(1, f"CANDIDATE: {args.candidate}")
        next_step = successor_next(root, args.role, args.candidate)
    return succeed(
        facts,
        next_step,
        turns_bought=turns_bought,
        role=invoked_role,
    )
