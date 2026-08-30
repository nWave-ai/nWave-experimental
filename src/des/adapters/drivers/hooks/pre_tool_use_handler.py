"""PreToolUse handler — validates Task/Agent tool invocations.

Translates Claude Code's PreToolUse hook event (JSON stdin) into
PreToolUseService decisions (allow/block), manages DES task signal creation,
and emits audit events through hook_protocol.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition.

The U1 carpaccio entry-gate intercept that used to run here is gone: a dispatch
is no longer refused by a hook for slice order, readiness, or marker
completeness. Reuse, architecture conformance and AT-first are practices carried
in the dispatch itself, not preconditions a hook re-litigates.
"""

import contextlib
import io
import json
import shlex
import stat
import time
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath

from des.adapters.drivers.hooks import des_task_signal
from des.adapters.drivers.hooks.bash_command_guards import (
    _split_subcommands,
    evaluate_git_stash_command,
    evaluate_worktree_add_command,
    evaluate_worktree_remove_command,
    git_stash_guard_target_root,
    worktree_guard_target_root,
    write_bash_guard_audit_event,
)
from des.adapters.drivers.hooks.hook_protocol import (
    EXIT_CODE_TO_DECISION,
    STDERR_CAPTURE_MAX_CHARS,
    extract_transcript_path,
    log_hook_completed,
    log_hook_error,
    log_hook_invoked,
    read_and_parse_stdin,
)
from des.adapters.drivers.hooks.native_agent_result import completed_agent_results
from des.adapters.drivers.hooks.root_activation_context import (
    build_root_mode_select_context,
    hook_input_has_agent_identity,
    resolve_subagent_agent_type,
    resolve_subagent_own_transcript_path,
    root_mode_gate_repo_is_active,
    root_mode_handoff_block_reason,
)
from des.application.commit_attribution_service import CommitAttributionService
from des.application.delivery_snapshot import construct_closure
from des.application.ordinary_request import (
    ATD_BODY_LINE_COUNT,
    compute_delivery_id,
    contract_locator_for,
    is_lexical_repo_relative_json_locator,
    is_valid_arch_header_line,
    is_well_formed_po_envelope,
    is_well_formed_po_revision_envelope,
)
from des.application.skill_tracking_service import (
    RootModeState,
    resolve_root_mode_state,
)
from des.domain.agent_capability import resolve_declared_max_turns


# Non-zero exit code paired with a `{decision:block}` body for an atdd_pure
# U1 intercept block (matches the existing block path's exit_code convention).
_ATDD_PURE_BLOCK_EXIT_CODE = 2

# Auto-root Bash lockdown (K4 architecture gap): tool names that carry DES
# task-signal authority. Auto's root process must never call these directly
# once nw-auto is engaged -- that authority belongs to a dispatched role.
_AUTO_ROOT_BLOCKED_TASK_TOOL_NAMES = ("TaskCreate", "TaskUpdate")
_ROOT_MODE_HANDOFF_TOOL_NAMES = frozenset(
    {"Agent", "Bash", "SendMessage", "TaskCreate", "TaskUpdate"}
)

# Auto-root crafter first-dispatch THIN header gate (K4 architecture gap):
# the exact role names for which an Auto-root Agent dispatch must carry a
# well-formed THIN-DELIVERY-CONTRACT authority as the prompt's first bytes.
# Deliberately exact match -- a reviewer or any other nw-* role is untouched.
_AUTO_ROOT_CRAFTER_ROLES = frozenset(
    {"nw-software-crafter", "nw-functional-software-crafter"}
)


def evaluate_agent_worktree_isolation(
    tool_input: dict[str, object],
) -> dict[str, str] | None:
    """Refuse harness-selected worktree residence for every Agent dispatch."""

    if tool_input.get("isolation") != "worktree":
        return None
    return {
        "decision": "block",
        "reason": (
            "WHAT: Agent isolation='worktree' was blocked. "
            "WHY: the harness selects that residence before nWave can measure "
            "durability, so WIP could exist before admission. "
            "HOW: run `des worktree-admit --repo <root> --lane <name>`, then "
            "dispatch the role in the admitted execution root without Agent "
            "worktree isolation."
        ),
    }


def _result_field(text: str, key: str) -> str | None:
    prefix = f"{key}: "
    values = [
        line.removeprefix(prefix)
        for line in text.splitlines()
        if line.startswith(prefix)
    ]
    return values[0] if len(values) == 1 else None


def _result_path(text: str, key: str) -> str | None:
    value = _result_field(text, key)
    if (
        value is None
        or not value
        or Path(value).is_absolute()
        or ".." in Path(value).parts
        or "\\" in value
    ):
        return None
    return value


def _is_exact_native_design_terminal(text: str) -> bool:
    """Admit exactly the one-line public DESIGN authority grammar."""
    return "\n" not in text and "\r" not in text and is_valid_arch_header_line(text)


def _is_exact_native_atd_terminal(
    text: str, *, root: Path, contract_locator: str
) -> bool:
    """Bind ATD readiness to the current physical root and contract locator."""
    return text == (
        "DISTILL-RESULT: CONTRACT_READY\n"
        f"REPO-ROOT: {root.resolve()}\n"
        f"DELIVERY-CONTRACT: {contract_locator}"
    )


def _canonical_dispatch_args(command: object) -> tuple[Path, str] | None:
    if not isinstance(command, str):
        return None
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if len(argv) < 5 or argv[0] != "des" or argv[1] != "dispatch":
        return None
    try:
        root = Path(argv[argv.index("--repo-root") + 1])
        locator = argv[argv.index("--delivery-contract") + 1]
    except (ValueError, IndexError):
        return None
    if not root.is_absolute() or not _result_path(f"path: {locator}", "path"):
        return None
    # Keep the caller's lexical absolute root until the public CLI performs
    # its own no-symlink/non-directory refusal. Resolving here would turn an
    # invalid public root into a valid physical path before that boundary.
    return root, locator


def _review_prompt_header_for_atd(root: Path) -> str:
    """Build the existing C authority header from its current admitted bytes."""
    try:
        from des.application.delivery_snapshot import _git, recognize_closure
        from des.cli.dispatch import closure_digest

        head = _git(root, "rev-parse", "HEAD").stdout.strip()
        closure = recognize_closure(root, head)
        contracts = []
        for path in closure.authority_paths:
            if not path.endswith(".json"):
                continue
            try:
                contract = json.loads((root / path).read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(contract, dict) and isinstance(
                contract.get("delivery-id"), str
            ):
                contracts.append((path, contract))
        if len(contracts) != 1:
            raise ValueError("current closure has no unique delivery contract")
        locator, contract = contracts[0]
        oracle = str(contract["acceptance-tests"]["locator"])
        support = tuple(
            (path, (root / path).read_bytes())
            for path in contract["acceptance-tests"].get("supporting-locators", [])
        )
        digest = closure_digest(
            (root / locator).read_bytes(),
            (root / oracle.split("::", 1)[0]).read_bytes(),
            oracle_locator=oracle,
            supporting_files=support,
        )
        if closure.commit != head:
            raise ValueError("current closure does not equal HEAD")
    except (
        KeyError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "current AT-review closure authority is not recognized"
        ) from exc
    return (
        f"THIN-DELIVERY-CONTRACT: {locator}\n"
        f"THIN-DELIVERY-CONTRACT-DIGEST: sha256:{digest}\n"
        f"REPO-ROOT: {root}\n"
    )


def _review_agent_prompt_rewrite(
    hook_input: dict[str, object],
    tool_input: dict[str, object],
    *,
    is_root_invocation: bool = True,
) -> int | None:
    """Prefix canonical reviewer Agents with hook-derived C/K authority.

    This is a private PreToolUse rewrite of the existing Agent invocation, not
    a persisted receipt or public grammar.  Later result recognition reads the
    platform's Agent tool_use input and therefore proves the review happened
    for this exact C or K attempt.
    """
    if not is_root_invocation:
        return None
    role = tool_input.get("subagent_type")
    if role != "nw-acceptance-designer-reviewer":
        return None
    cwd, transcript, prompt = (
        hook_input.get("cwd"),
        hook_input.get("transcript_path"),
        tool_input.get("prompt"),
    )
    if (
        not isinstance(cwd, str)
        or not isinstance(transcript, str)
        or not isinstance(prompt, str)
    ):
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": "INDETERMINATE: reviewer host supplied no root/transcript/prompt",
                }
            )
        )
        return 2
    try:
        root = Path(cwd).resolve()
        header = _review_prompt_header_for_atd(root)
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": f"INDETERMINATE: reviewer invocation refused ({exc})",
                }
            )
        )
        return 2
    body = prompt[len(header) :] if prompt.startswith(header) else prompt
    updated = {**tool_input, "prompt": header + body}
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": updated,
                }
            }
        )
    )
    return 0


def _integration_delta(root: Path, parent: str) -> set[str]:
    from des.application.delivery_snapshot import _changed_paths, _git

    committed = _changed_paths(root, parent, "HEAD")
    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if status.returncode:
        raise ValueError("integration root status is unreadable")
    pending = {
        field[3:] for field in status.stdout.split("\0") if field and len(field) >= 4
    }
    return committed | pending


def _dispatch_closure_rewrite(
    hook_input: dict[str, object],
    tool_input: dict[str, object],
    *,
    is_root_invocation: bool = True,
) -> int | None:
    """Construct C once from completed native producer invocations.

    The CLI remains an unchanged reader/emitter.  This hook is the only
    installed route that can move the isolated ATD root from P to C.
    """
    if not is_root_invocation:
        return None
    parsed = _canonical_dispatch_args(tool_input.get("command"))
    if parsed is None:
        return None
    try:
        from des.application.delivery_snapshot import (
            _git,
            _no_follow_path,
            recognize_closure,
        )
        from des.cli.dispatch import main as dispatch_main

        repo_root, locator = parsed
        public_stdout, public_stderr = io.StringIO(), io.StringIO()
        # Run the semantic validator once.  The hook becomes the one producer
        # of its public two-line handoff after it has admitted/replayed C.
        with (
            contextlib.redirect_stdout(public_stdout),
            contextlib.redirect_stderr(public_stderr),
        ):
            validation = dispatch_main(
                ["--repo-root", str(repo_root), "--delivery-contract", locator]
            )
        validation_handoff = public_stdout.getvalue()
        if validation:
            detail = public_stderr.getvalue().strip() or f"exit status {validation}"
            raise ValueError(f"dispatch semantic validation refused: {detail}")

        contract_file = _no_follow_path(repo_root, locator)
        if contract_file.is_symlink() or not contract_file.is_file():
            raise ValueError("integration contract is not a regular file")
        contract_bytes = contract_file.read_bytes()
        contract = json.loads(contract_bytes.decode("utf-8"))
        base = str(contract["repository"]["base-revision"]).split(":", 1)[1]
        head = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        replay = head != base
        if replay:
            closure = recognize_closure(repo_root, head)
            if closure.base != base or locator not in closure.authority_paths:
                raise ValueError("existing closure is not this contract's replay")
            status = _git(
                repo_root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
            )
            if status.returncode:
                raise ValueError("closure replay status is unreadable")
            if status.stdout:
                raise ValueError("closure replay root is dirty")

        oracle_locator = str(contract["acceptance-tests"]["locator"])
        oracle_path = oracle_locator.split("::", 1)[0]
        support_paths = tuple(
            str(item)
            for item in contract["acceptance-tests"].get("supporting-locators", [])
        )
        oracle_file = _no_follow_path(repo_root, oracle_path)
        if oracle_file.is_symlink() or not oracle_file.is_file():
            raise ValueError("integration oracle bytes are unreadable")
        oracle_bytes = oracle_file.read_bytes()
        supporting = []
        for path in support_paths:
            item = _no_follow_path(repo_root, path)
            if item.is_symlink() or not item.is_file():
                raise ValueError("integration support bytes are unreadable")
            supporting.append((path, item.read_bytes()))
        handoff_lines = validation_handoff.splitlines()
        if handoff_lines[:1] != [f"THIN-DELIVERY-CONTRACT: {locator}"] or (
            len(handoff_lines) != 2
            or not handoff_lines[1].startswith("THIN-DELIVERY-CONTRACT-DIGEST: sha256:")
        ):
            raise ValueError("dispatch success stdout is not a two-line handoff")

        if not replay:
            transcript = hook_input.get("transcript_path")
            if not isinstance(transcript, str) or not transcript:
                raise ValueError("root supplied no parent transcript")
            atd = completed_agent_results(
                transcript, role=_ATD_ROLE_NAME, prompt_prefix=""
            )
            if atd is None or not _is_exact_native_atd_terminal(
                atd.terminal_text, root=repo_root, contract_locator=locator
            ):
                raise ValueError("missing completed ATD native attempt")
            design_result = completed_agent_results(
                transcript, role=_ARCHITECT_ROLE_NAME, prompt_prefix=""
            )
            design_path = None
            if design_result is not None:
                if not _is_exact_native_design_terminal(design_result.terminal_text):
                    raise ValueError("DESIGN terminal has no safe authority locator")
                design_path = design_result.terminal_text.split("#", 1)[0].removeprefix(
                    "ARCHITECTURE-COVERED: "
                )
            charter_path = None
            if bool(contract.get("applicability", {}).get("examine")):
                charter = completed_agent_results(
                    transcript, role="nw-product-owner", prompt_prefix=""
                )
                if charter is None:
                    raise ValueError("missing applicable PO native attempt")
                charter_path = _result_path(charter.terminal_text, "path")
                if charter_path is None:
                    raise ValueError("PO terminal has no safe charter path")
            allowed = {locator, oracle_path, *support_paths}
            if design_path is not None:
                allowed.add(design_path)
            if charter_path is not None:
                allowed.add(charter_path)
            if _integration_delta(repo_root, base) != allowed:
                raise ValueError(
                    "integration pending delta is not the complete allowed authority set"
                )
            if set(contract["targets"]) & allowed:
                raise ValueError("contract targets intersect AuthorityPaths")
            imports: list[tuple[str, bytes, int]] = []
            authority_imports = (
                *((design_path,) if design_path else ()),
                *((charter_path,) if charter_path else ()),
            )
            for path in authority_imports:
                item = _no_follow_path(repo_root, path)
                info = item.lstat()
                if item.is_symlink() or not stat.S_ISREG(info.st_mode):
                    raise ValueError("integration authority path is not regular")
                imports.append(
                    (path, item.read_bytes(), stat.S_IMODE(info.st_mode) | stat.S_IFREG)
                )
            closure = construct_closure(
                repo_root,
                contract=contract,
                contract_locator=locator,
                contract_bytes=contract_bytes,
                oracle_locator=oracle_locator,
                oracle_bytes=oracle_bytes,
                supporting=tuple(supporting),
                imports=tuple(imports),
                constructor_root=repo_root,
            )
            if closure.commit != _git(repo_root, "rev-parse", "HEAD").stdout.strip():
                raise ValueError("integration closure readback differs from HEAD")
        # Hooks may normalize contract/oracle bytes while committing C.  The
        # public carrier must therefore be derived from admitted C, never from
        # the pre-commit bytes the unchanged CLI just inspected.
        sealed_locator, _sealed_contract, _sealed_oracle, sealed_digest = (
            _closure_authority(repo_root, closure, contract_locator=locator)
        )
        if sealed_locator != locator:
            raise ValueError("admitted closure changed its contract locator")
        handoff = _thin_contract_header(sealed_locator, sealed_digest)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": f"INDETERMINATE: integration closure construction refused ({exc})",
                }
            )
        )
        return 2
    updated = {**tool_input, "command": f"printf %s {json.dumps(handoff)}"}
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": updated,
                }
            }
        )
    )
    return 0


def _closure_authority(
    root: Path, closure: object, *, contract_locator: str | None = None
) -> tuple[str, dict[str, object], str, str]:
    """Read current authority only when it is exactly the admitted C bytes."""
    from des.application.delivery_snapshot import (
        Snapshot,
        _git_bytes,
        _no_follow_path,
        _require_schema_valid,
    )
    from des.cli.dispatch import closure_digest

    if not isinstance(closure, Snapshot):
        raise ValueError("closure snapshot is not admitted")

    def admitted_regular_bytes(path: str, *, noun: str) -> bytes:
        if path not in closure.authority_paths:
            raise ValueError(f"closure {noun} path is not admitted: {path}")
        item = _no_follow_path(root, path)
        try:
            mode = item.lstat().st_mode
        except OSError as exc:
            raise ValueError(f"closure {noun} is unreadable: {path}") from exc
        if item.is_symlink() or not stat.S_ISREG(mode):
            raise ValueError(f"closure {noun} is not a regular file: {path}")
        try:
            current = item.read_bytes()
        except OSError as exc:
            raise ValueError(f"closure {noun} is unreadable: {path}") from exc
        admitted = _git_bytes(root, "show", f"{closure.commit}:{path}")
        if admitted.returncode or admitted.stdout != current:
            raise ValueError(f"closure {noun} differs from admitted C bytes: {path}")
        return current

    if contract_locator is not None:
        raw_contract = admitted_regular_bytes(contract_locator, noun="contract")
        try:
            contract = json.loads(raw_contract.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("closure contract authority is unreadable") from exc
        if not isinstance(contract, dict):
            raise ValueError("closure contract authority is not an object")
        _require_schema_valid(contract)
        locator = contract_locator
    else:
        contracts: list[tuple[str, dict[str, object]]] = []
        for path in closure.authority_paths:
            if not path.endswith(".json"):
                continue
            try:
                candidate = json.loads(
                    admitted_regular_bytes(path, noun="contract").decode("utf-8")
                )
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(candidate, dict) and isinstance(
                candidate.get("delivery-id"), str
            ):
                _require_schema_valid(candidate)
                contracts.append((path, candidate))
        if len(contracts) != 1:
            raise ValueError("closure has no unique readable delivery contract")
        locator, contract = contracts[0]

    try:
        oracle = contract["acceptance-tests"]["locator"]
        supporting_locators = contract["acceptance-tests"].get(
            "supporting-locators", []
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("closure contract authority is unreadable") from exc
    if (
        not isinstance(oracle, str)
        or not isinstance(supporting_locators, list)
        or any(not isinstance(path, str) for path in supporting_locators)
    ):
        raise ValueError("closure contract authority has invalid oracle locators")
    oracle_path = oracle.split("::", 1)[0]
    oracle_bytes = admitted_regular_bytes(oracle_path, noun="oracle")
    supporting = tuple(
        (path, admitted_regular_bytes(path, noun="support"))
        for path in supporting_locators
    )
    digest = closure_digest(
        admitted_regular_bytes(locator, noun="contract"),
        oracle_bytes,
        oracle_locator=oracle,
        supporting_files=supporting,
    )
    return locator, contract, oracle, digest


def _thin_contract_header(locator: str, digest: str) -> str:
    return (
        f"THIN-DELIVERY-CONTRACT: {locator}\n"
        f"THIN-DELIVERY-CONTRACT-DIGEST: sha256:{digest}\n"
    )


def _terminal_fields(text: str, header: str) -> dict[str, str] | None:
    """Parse one exact structured terminal; prose and duplicate keys refuse."""
    lines = text.splitlines()
    if not lines or lines[0] != header:
        return None
    result: dict[str, str] = {}
    for line in lines[1:]:
        if ": " not in line:
            return None
        key, value = line.split(": ", 1)
        if not key or not value or key in result:
            return None
        result[key] = value
    return result or None


def _is_exact_review(
    text: str, *, header: str, required: dict[str, str], verdicts: frozenset[str]
) -> bool:
    """Accept one complete, current review grammar and nothing else."""
    fields = _terminal_fields(text, header)
    if fields is None or set(fields) != set(required) | {"verdict"}:
        return False
    return fields.get("verdict") in verdicts and all(
        fields.get(key) == value for key, value in required.items()
    )


def _at_review_approved(
    text: str,
    *,
    contract_locator: str,
    contract_digest: str,
    oracle_locator: str,
) -> bool:
    """Bind an unconditional AT approval to the current C contract digest and oracle locator."""
    return _is_exact_review(
        text,
        header="AT-REVIEW",
        required={
            "contract": f"{contract_locator}@sha256:{contract_digest}",
            "oracle": oracle_locator,
            "findings": "none",
        },
        verdicts=frozenset({"APPROVE", "APPROVED"}),
    )


def _crafter_agent_rewrite(
    hook_input: dict[str, object], tool_input: dict[str, object]
) -> int | None:
    """E3: admit a crafter only from the current C-bound AT foreground result."""
    if tool_input.get("subagent_type") not in _AUTO_ROOT_CRAFTER_ROLES:
        return None
    cwd, transcript, prompt = (
        hook_input.get("cwd"),
        hook_input.get("transcript_path"),
        tool_input.get("prompt"),
    )
    if (
        not isinstance(cwd, str)
        or not isinstance(transcript, str)
        or not isinstance(prompt, str)
    ):
        return None
    try:
        from des.application.delivery_snapshot import _git, recognize_closure

        root = Path(cwd).resolve()
        closure = recognize_closure(
            root, _git(root, "rev-parse", "HEAD").stdout.strip()
        )
        locator, _contract, oracle, digest = _closure_authority(root, closure)
        review_header = _thin_contract_header(locator, digest) + f"REPO-ROOT: {root}\n"
        result = completed_agent_results(
            transcript,
            role="nw-acceptance-designer-reviewer",
            prompt_prefix=review_header,
        )
        if result is None or not _at_review_approved(
            result.terminal_text,
            contract_locator=locator,
            contract_digest=digest,
            oracle_locator=oracle,
        ):
            raise ValueError("missing exact C-bound AT REVIEW APPROVE")
        header = _thin_contract_header(locator, digest)
        body = (
            prompt[len(header) :].lstrip("\n") if prompt.startswith(header) else prompt
        )
        updated = {**tool_input, "prompt": f"{header}\nexecution-root: {root}\n{body}"}
    except Exception as exc:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": f"INDETERMINATE: crafter admission refused ({exc})",
                }
            )
        )
        return 2
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": updated,
                }
            }
        )
    )
    return 0


def _reported_targets(value: object) -> set[str]:
    if not isinstance(value, str):
        raise ValueError("crafter did not report target paths")
    paths = {
        piece.strip() for piece in value.replace(",", " ").split() if piece.strip()
    }
    if not paths or any(
        path.startswith("/") or ".." in Path(path).parts for path in paths
    ):
        raise ValueError("crafter reported unsafe or empty target paths")
    return paths


def _candidate_binding(
    root: Path, transcript: str, *, cited_candidate: object | None = None
) -> tuple[object, object, str, str, set[str]]:
    """E4: prove PASS/current-C delta, then seal or replay exactly one K."""
    from des.application.delivery_snapshot import (
        ApprovedClosure,
        CandidateConstructor,
        _changed_paths,
        _DeliveryPaths,
        _git,
        closure_for_candidate,
        recognize_candidate,
        recognize_closure,
    )

    status = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if status.returncode:
        raise ValueError("candidate root status is unreadable")
    pending = {item[3:] for item in status.stdout.split("\0") if len(item) >= 4}
    candidate = cited_candidate
    if candidate is None:
        head = _git(root, "rev-parse", "HEAD").stdout.strip()
        try:
            candidate = recognize_candidate(root, head)
            closure = closure_for_candidate(root, head)
        except ValueError:
            closure = recognize_closure(root, head)
    else:
        if not hasattr(candidate, "commit"):
            raise ValueError("replayed final has no cited candidate")
        candidate = recognize_candidate(root, candidate.commit)
        closure = closure_for_candidate(root, candidate.commit)
    locator, contract, oracle, digest = _closure_authority(root, closure)
    header = _thin_contract_header(locator, digest)
    results = [
        result
        for role in _AUTO_ROOT_CRAFTER_ROLES
        for result in [
            completed_agent_results(transcript, role=role, prompt_prefix=header)
        ]
        if result is not None
    ]
    if len(results) != 1:
        raise ValueError("no unique C-bound completed crafter result")
    fields = _terminal_fields(results[0].terminal_text, "CRAFTER-RESULT")
    if fields is None or fields.get("verdict") != "PASS":
        raise ValueError("crafter terminal is not exact PASS")
    if fields.get("contract") != f"{locator}@sha256:{digest}" or fields.get(
        "execution-root"
    ) != str(root):
        raise ValueError("crafter result is not bound to current C/root")
    reported = _reported_targets(fields.get("changed-targets"))
    oracle_dependencies = {
        locator,
        oracle.split("::", 1)[0],
        *(
            str(path)
            for path in contract["acceptance-tests"].get("supporting-locators", [])
        ),
    }
    paths = _DeliveryPaths.build(
        authority=set(closure.authority_paths) - oracle_dependencies,
        oracle_dependencies=oracle_dependencies,
        crafter_writable=set(contract["targets"]),
    )
    reported_delta = paths.crafter_expected_delta(reported)
    if candidate is not None:
        if pending:
            raise ValueError("post-seal dirt makes candidate replay indeterminate")
        if _changed_paths(root, closure.commit, candidate.commit) != reported_delta:
            raise ValueError("replayed K differs from the completed crafter report")
        return candidate, closure, locator, digest, set(reported_delta)
    expected_delta = paths.crafter_expected_delta(pending)
    if not expected_delta or expected_delta != reported_delta:
        raise ValueError("crafter PASS does not equal complete pending target delta")
    if expected_delta & set(closure.authority_paths):
        raise ValueError("crafter modified closure authority")
    approved = ApprovedClosure(
        closure, locator, oracle, digest, contract, closure.authority_paths
    )
    candidate = CandidateConstructor().seal(approved, root, set(expected_delta))
    residue = _git(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    ).stdout
    if residue:
        raise ValueError(f"candidate constructor left dirty worktree: {residue!r}")
    if _changed_paths(root, closure.commit, candidate.commit) != expected_delta:
        raise ValueError("sealed K differs from completed crafter report")
    return candidate, closure, locator, digest, set(expected_delta)


def _candidate_agent_rewrite(
    hook_input: dict[str, object], tool_input: dict[str, object]
) -> int | None:
    """E4: put an admitted K only into implementation review/examination prompts."""
    role = tool_input.get("subagent_type")
    if role not in {"nw-software-crafter-reviewer", "nw-user-examiner"}:
        return None
    cwd, transcript, prompt = (
        hook_input.get("cwd"),
        hook_input.get("transcript_path"),
        tool_input.get("prompt"),
    )
    if (
        not isinstance(cwd, str)
        or not isinstance(transcript, str)
        or not isinstance(prompt, str)
    ):
        return None
    try:
        from des.application.delivery_snapshot import _git

        root = Path(cwd).resolve()
        candidate, _closure, _locator, _digest, _reported = _candidate_binding(
            root, transcript
        )
        algorithm = _git(root, "rev-parse", "--show-object-format").stdout.strip()
        if algorithm not in {"sha1", "sha256"}:
            raise ValueError("unsupported git object format")
        header = (
            f"candidate: git-{algorithm}:{candidate.commit}\nexecution-root: {root}\n"
        )
        body = prompt[len(header) :] if prompt.startswith(header) else prompt
        updated = {**tool_input, "prompt": header + body}
    except Exception as exc:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": f"INDETERMINATE: candidate admission refused ({exc})",
                }
            )
        )
        return 2
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": updated,
                }
            }
        )
    )
    return 0


def _replay_candidate_from_review_prompt(root: Path, transcript: str) -> object:
    """Recover K only from the one real review invocation that bound it."""
    from des.application.delivery_snapshot import _git, recognize_candidate

    review = completed_agent_results(
        transcript, role="nw-software-crafter-reviewer", prompt_prefix="candidate: "
    )
    if review is None:
        raise ValueError("replayed final has no unique K-bound implementation review")
    lines = review.applied_prompt.splitlines()
    if len(lines) < 2 or lines[1] != f"execution-root: {root}":
        raise ValueError("replayed final review is not bound to this root")
    candidate_text = lines[0].removeprefix("candidate: ")
    try:
        algorithm, commit = candidate_text.split(":", 1)
    except ValueError as exc:
        raise ValueError("replayed final review has no exact candidate") from exc
    object_format = _git(root, "rev-parse", "--show-object-format")
    if (
        object_format.returncode
        or algorithm != f"git-{object_format.stdout.strip()}"
        or not commit
    ):
        raise ValueError("replayed final review has invalid candidate identity")
    return recognize_candidate(root, commit)


def _finalize_candidate_rewrite(
    hook_input: dict[str, object], tool_input: dict[str, object]
) -> int | None:
    """E7: finalize only a current K with one K-bound implementation APPROVE."""
    command, cwd, transcript = (
        tool_input.get("command"),
        hook_input.get("cwd"),
        hook_input.get("transcript_path"),
    )
    if not isinstance(command, str):
        return None
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if not argv or argv[0] != "git" or _git_subcommand(argv) != "commit":
        return None
    if not isinstance(cwd, str) or not isinstance(transcript, str):
        return None
    # E7 is a P5 route interceptor, not a general replacement for Git's
    # ordinary commit/attribution path.  Establish its admitted lineage
    # before attempting the fail-closed K join; a repository without C or K
    # must pass through untouched.
    try:
        from des.application.delivery_snapshot import (
            _FINAL_ID,
            _git,
            _metadata,
            recognize_candidate,
            recognize_closure,
        )

        root = Path(cwd).resolve()
        head = _git(root, "rev-parse", "HEAD")
        if head.returncode:
            return None
        revision = head.stdout.strip()
        replay_final = False
        try:
            recognize_candidate(root, revision)
        except (RuntimeError, ValueError):
            try:
                recognize_closure(root, revision)
            except (RuntimeError, ValueError):
                parents, message, *_rest = _metadata(root, revision)
                if not parents or message != _FINAL_ID[2] + "\n":
                    return None
                replay_final = True
    except OSError:
        return None
    try:
        from des.application.delivery_snapshot import (
            _changed_paths,
            _git,
            finalize_candidate,
        )

        cited_candidate = (
            _replay_candidate_from_review_prompt(root, transcript)
            if replay_final
            else None
        )
        candidate, closure, locator, digest, reported = _candidate_binding(
            root, transcript, cited_candidate=cited_candidate
        )
        algorithm = _git(root, "rev-parse", "--show-object-format").stdout.strip()
        if algorithm not in {"sha1", "sha256"}:
            raise ValueError("unsupported git object format")
        candidate_text = f"git-{algorithm}:{candidate.commit}"
        header = f"candidate: {candidate_text}\nexecution-root: {root}\n"
        review = completed_agent_results(
            transcript, role="nw-software-crafter-reviewer", prompt_prefix=header
        )
        if review is None or not _is_exact_review(
            review.terminal_text,
            header="IMPLEMENTATION-REVIEW",
            required={
                "contract": f"{locator}@sha256:{digest}",
                "candidate": candidate_text,
                "oracle-unchanged": "true",
                "findings": "none",
            },
            verdicts=frozenset({"APPROVE", "APPROVED"}),
        ):
            raise ValueError("missing exact K-bound IMPLEMENTATION-REVIEW APPROVE")
        paths = _changed_paths(root, closure.base or "", candidate.commit)
        if not reported <= paths or not paths <= set(closure.authority_paths) | set(
            _closure_authority(root, closure)[1]["targets"]
        ):
            raise ValueError("K delta is not closure authority plus reported targets")
        target_ref = _git(root, "symbolic-ref", "-q", "HEAD").stdout.strip()
        if not target_ref:
            raise ValueError("finalizer root has no symbolic target ref")
        _bound_locator, _contract, _oracle, _bound_digest = _closure_authority(
            root, closure
        )
        if _bound_locator != locator or _bound_digest != digest:
            raise ValueError("finalizer closure authority changed during admission")
        base = closure.base or ""
        finalized = finalize_candidate(
            root,
            candidate=candidate,
            base=base,
            authorized_paths=paths,
            target_ref=target_ref,
            contract_locator=locator,
        )
        if not finalized.clean_checkout:
            raise ValueError("final verification did not prove a clean checkout")
    except Exception as exc:
        print(
            json.dumps(
                {
                    "decision": "block",
                    "reason": f"INDETERMINATE: final projection refused ({exc})",
                }
            )
        )
        return 2
    binding = (
        f"Commit: git-{algorithm}:{finalized.commit}\n"
        "Clean-checkout: true\n"
        "Verdict: PASS\n"
    )
    updated = {**tool_input, "command": f"printf %s {json.dumps(binding)}"}
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": updated,
                }
            }
        )
    )
    return 0


_THIN_HEADER_LOCATOR_PREFIX = "THIN-DELIVERY-CONTRACT: "
_THIN_HEADER_DIGEST_PREFIX = "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"
_THIN_HEADER_DIGEST_HEX_LEN = 64
_THIN_HEADER_DIGEST_HEX_ALPHABET = frozenset("0123456789abcdef")

# K4: exact-match roles whose Auto-root Agent dispatch must carry the
# value-only six-line PO envelope `des resolve-charters` prints on AUTHOR
# (`des.application.ordinary_request.build_po_envelope`) -- never an
# ARCHITECTURE-COVERED anchor, which disqualifies `nw-product-owner` as
# charter author by its own role logic the instant its context carries one.
_AUTO_ROOT_PO_ENVELOPE_ROLES = frozenset({"nw-product-owner"})
_ATD_ROLE_NAME = "nw-acceptance-designer"


_DELIVERY_ROUTE_TOKENS = frozenset({"RED_TO_GREEN", "GREEN_TO_GREEN"})
_ARCHITECT_ROLE_NAME = "nw-solution-architect"
_AUTO_ARCH_CONSULT_LINE_PREFIX = "AUTO-ARCHITECTURE-CONSULT: "
_AUTO_ARCH_ROOT_LINE_PREFIX = "AUTO-ARCHITECTURE-ROOT: "
_AUTO_ARCH_DELIVERY_ROUTE_LINE_PREFIX = "AUTO-DELIVERY-ROUTE: "
#: The repair-consult's OPTIONAL fourth field -- carries `des compile-
#: contract`'s own BLOCKED stdout verbatim into a re-consult of the
#: architect after it rejects the authored architecture brief (GDP-0, K4
#: camp7 2026-08-23: a hand-paraphrase of the rejection dropped the Target-
#: cell detail the architect never saw, three dispatches to converge). Same
#: quoted-heredoc discipline as `_is_value_seed_stdin_heredoc`'s NW_SEED
#: carrier -- a DIFFERENT delimiter (never NW_SEED itself), so a rejection
#: payload can never be mistaken for a value-seed payload.
_AUTO_ARCH_REJECTION_LINE_PREFIX = "AUTO-ARCHITECTURE-REJECTION: "
_AUTO_ARCH_REJECTION_HEREDOC_DELIMITER = "NW_REJECTION"
_AUTO_ARCH_REJECTION_HEREDOC_HEADER = (
    _AUTO_ARCH_REJECTION_LINE_PREFIX
    + "<<'"
    + _AUTO_ARCH_REJECTION_HEREDOC_DELIMITER
    + "'"
)
_ATD_ROOT_LINE_PREFIX = "ROOT: "
_ATD_VALUE_SEED_LINE_PREFIX = "VALUE-SEED: "
_ATD_DELIVERY_ROUTE_LINE_PREFIX = "DELIVERY-ROUTE: "


# K4 (nw-auto ADR-SSOT-002 Section 4c total constructor): the twelve named
# non-empty facts an Auto-root ATD dispatch body must carry, each on its own
# line and in this exact order, after the architecture authority line and one
# blank line.
_ATD_CONTRACT_LOCATOR_LINE_PREFIX = "CONTRACT-LOCATOR: "
_ATD_CONTRACT_SCHEMA_LINE_PREFIX = "CONTRACT-SCHEMA: "
_ATD_DELIVERY_ID_LINE_PREFIX = "DELIVERY-ID: "
_ATD_OUTCOME_LINE_PREFIX = "OUTCOME: "
_ATD_BASE_REVISION_LINE_PREFIX = "BASE-REVISION: "
_ATD_EXAMINE_LINE_PREFIX = "EXAMINE: "
_ATD_INDEPENDENT_REVIEW_LINE_PREFIX = "INDEPENDENT-REVIEW: "
_ATD_BUDGET_TOKEN_LIMIT_LINE_PREFIX = "BUDGET-TOKEN-LIMIT: "
_ATD_BUDGET_WALL_CLOCK_MINUTES_LINE_PREFIX = "BUDGET-WALL-CLOCK-MINUTES: "

_ATD_BASE_REVISION_TAGS = {"git-sha1:": 40, "git-sha256:": 64}
_HEX_ALPHABET = frozenset("0123456789abcdef")

# Tool names for which the resolved Auto-root lockdown applies. Root mode is
# projected once per root tool event and reused by every decision below.
_AUTO_ROOT_TASK_TOOL_LOCKDOWN_NAMES = ("Bash", *_AUTO_ROOT_BLOCKED_TASK_TOOL_NAMES)

# Shell-composition operators rejected BEFORE `shlex.split` runs: `shlex` has
# no concept of &&/||/pipe/redirection/command-substitution/newline, so a
# smuggled second command would otherwise survive tokenization undetected.
_AUTO_ROOT_BASH_INJECTION_MARKERS = (
    "&&",
    "||",
    ";",
    "|",
    "&",
    "`",
    "$(",
    "<",
    ">",
    "\n",
    "\r",
)

# The closed set of git subcommands an Auto-root Bash call may run: read-only
# inspection (status/diff/rev-parse/branch/worktree/ls-files) plus the two
# staging/commit verbs Auto's own commit-attribution flow needs. `ls-files`
# (design docs/analysis/2026-08-24-design-perimetro-auto-root.md, Candidata
# B1): same read-only risk profile as `status`, already admitted; its prior
# absence carried no explaining comment, unlike every other entry here --
# an unrevisited omission, not a deliberate exclusion.
_AUTO_ROOT_BASH_ALLOWED_GIT_SUBCOMMANDS = frozenset(
    {
        "status",
        "diff",
        "rev-parse",
        "branch",
        "worktree",
        "add",
        "commit",
        "ls-files",
    }
)

# The closed set of `des` CLI subcommands an Auto-root Bash call may run
# directly (K4: the direct-cutover spine has no hook controller between
# Auto-root and the dispatched role's own DES CLI invocation). Arguments
# after this verb are literal argv already protected by the injection-marker
# and shlex tokenization above -- never re-interpreted as shell.
_AUTO_ROOT_BASH_ALLOWED_DES_SUBCOMMANDS = frozenset(
    {
        "dispatch",
        "validate-delivery-contract",
        "charter-scaffold",
        "prepare-ordinary-request",
        "resolve-charters",
        "code-fact",
        "compile-contract",
        "construct-design-closure",
        # SF friction report 2026-08-20, item 5: `_is_well_formed_atd_
        # revision_body` REQUIRES the REVISE dispatch body come verbatim
        # from the former mutable-round producer's stdout, but this SAME
        # allowlist never named the subcommand -- root's own Bash call to
        # PRODUCE that body was blocked before it could ever run,
        # deadlocking the exact flow nw-auto/SKILL.md's routing table
        # documents. The two gates (body-shape check, subcommand
        # allowlist) must agree on which producers root may invoke; the
        # drift guard below (`TestAutoRootBashAllowlistCoversSkillMandat
        # edSubcommands`) is extended with a hand-anchored assertion for
        # this exact historical class, since it was named in
        # SKILL.md as inline backtick prose (a routing-table cell), never
        # inside a fenced block the general parser scans.
        # The charter-side sibling: `is_well_formed_po_revision_envelope`
        # REQUIRES the PO revision dispatch envelope come verbatim from
        # `des revise-charter-round`'s own stdout -- same deadlock class as
        # SF friction report 2026-08-20, item 5, if the producer itself is
        # not allowlisted.
        "revise-charter-round",
    }
)


def _auto_root_task_tool_block(tool_name: str) -> dict[str, str]:
    """Render the block payload for an Auto-root TaskCreate/TaskUpdate call."""
    return {
        "decision": "block",
        "reason": (
            f"WHAT: an Auto-root {tool_name} call was blocked. "
            "WHY: Auto's root process owns no task-signal authority once "
            "nw-auto is engaged -- TaskCreate/TaskUpdate belong to a "
            "dispatched role, not the root orchestrator. "
            f"HOW: dispatch the appropriate nw-* role instead of calling "
            f"{tool_name} directly from Auto root."
        ),
    }


def _auto_root_bash_block(reason: str) -> dict[str, str]:
    return {"decision": "block", "reason": reason}


# ADR-SSOT-002 "VALUE-SEED transport": the value seed must reach every
# producer that consumes it as raw UTF-8 bytes on stdin -- never argv,
# env, temp file or transcript scrape, and never re-interpreted by the
# shell (the seed is arbitrary human text, not a safe shell token). The
# blanket injection-marker block above would otherwise make those
# producers permanently unreachable from Auto-root Bash: every
# stdin-feeding construct needs either `|` or `<<`, both unconditionally
# rejected.
#
# Exactly one shape is carved out below, generalized over the CLOSED SET
# of seed-bearing producers nw-auto/SKILL.md's route mandates root run
# with the seed on stdin (Run 7: `des resolve-charters` joined `des
# prepare-ordinary-request` here once it started building the PO envelope
# and needed the same seed -- the carve-out must generalize to every such
# producer, not be hand-extended one subcommand at a time; THE one place
# both this hook and the SKILL.md-coverage guard read is the dict below):
# a single `des <one of these subcommands> <ITS OWN bounded argv>` header
# line ending in a QUOTED heredoc redirect (`<<'NW_SEED'` or `<<"NW_SEED"`
# -- quoting is mandatory so the shell performs zero expansion inside the
# body, the same "opaque bytes" guarantee a pipe would give), followed by
# an arbitrary-content body, terminated by a line that is exactly the
# delimiter and nothing after it. A quoted heredoc body is never
# shell-interpreted, so it is the one construct that can carry a seed
# containing quotes, `|`, backticks or any other byte without escaping.
# Every other shape -- a subcommand outside this set, a flag from a
# DIFFERENT producer's vocabulary, an unquoted delimiter, unterminated
# body, trailing content after the terminator, any composition marker in
# the header -- still falls through to the generic block.
_VALUE_SEED_HEREDOC_DELIMITER = "NW_SEED"
_VALUE_SEED_HEREDOC_HEADER_SUFFIXES = (
    f" <<'{_VALUE_SEED_HEREDOC_DELIMITER}'",
    f' <<"{_VALUE_SEED_HEREDOC_DELIMITER}"',
)
# THE one place naming which `des` subcommands may take the seed heredoc,
# and each one's own closed flag vocabulary (never shared across
# subcommands -- prepare-ordinary-request's `--size` must never leak into
# resolve-charters' argv, and vice versa). `des <sub> --help`
# (src/des/cli/prepare_ordinary_request.py `_parser`,
# src/des/cli/resolve_charters.py `_build_parser`) is each vocabulary's
# own source. `tests/build/test_des_examples_are_executable.py` imports
# this SAME dict to assert nw-auto/SKILL.md's fenced heredoc examples
# name exactly this set, in both directions -- one drift class, one fix.
_VALUE_SEED_HEREDOC_ALLOWED_COMMANDS: dict[str, frozenset[str]] = {
    "prepare-ordinary-request": frozenset(
        {
            "--size",
            "--repo-root",
            "--architecture-authority",
            "--delivery-route",
            "--examine",
            "--independent-review",
            "--budget-token-limit",
            "--budget-wall-clock-minutes",
        }
    ),
    "resolve-charters": frozenset(
        {
            "--repo-root",
            "--delivery-id",
            "--examine",
        }
    ),
}


def _value_seed_heredoc_header_argv(header: str) -> list[str] | None:
    """`shlex`-tokenized argv of a matched heredoc header's pre-`<<` argv
    prefix, or `None` if the prefix carries any composition marker, fails
    to tokenize, is not `des <allowed-subcommand>`, or carries any flag
    token outside THAT subcommand's own closed vocabulary."""
    prefix = None
    for suffix in _VALUE_SEED_HEREDOC_HEADER_SUFFIXES:
        if header.endswith(suffix):
            prefix = header[: -len(suffix)]
            break
    if prefix is None:
        return None
    if any(marker in prefix for marker in _AUTO_ROOT_BASH_INJECTION_MARKERS):
        return None
    try:
        argv = shlex.split(prefix)
    except ValueError:
        return None
    if len(argv) < 2 or argv[0] != "des":
        return None
    allowed_flags = _VALUE_SEED_HEREDOC_ALLOWED_COMMANDS.get(argv[1])
    if allowed_flags is None:
        return None
    flags = argv[2:]
    i = 0
    while i < len(flags):
        token = flags[i]
        flag_name = token.partition("=")[0]
        if flag_name not in allowed_flags:
            return None
        if "=" in token:
            # `--flag=value` is one self-contained token.
            i += 1
            continue
        # `--flag value` is two tokens -- a flag with no following value
        # token is malformed, not a value-less flag in this vocabulary.
        if i + 1 >= len(flags):
            return None
        i += 2
    return argv


def _is_value_seed_stdin_heredoc(command: str) -> bool:
    """True iff `command` is one hook-permitted seed-transport heredoc: a
    bounded `des <subcommand>` header, where `<subcommand>` is one of
    `_VALUE_SEED_HEREDOC_ALLOWED_COMMANDS`, ending in a quoted
    `<<'NW_SEED'`/`<<"NW_SEED"` redirect, an opaque body, and a terminator
    line that is exactly the delimiter with nothing after it. Fails closed
    (`False`) on anything else -- an unquoted delimiter, a missing/
    duplicated terminator, trailing content past it, or a header that does
    not tokenize into `des <allowed-subcommand>` plus THAT subcommand's own
    closed flag vocabulary.
    """
    if "\r" in command or "\n" not in command:
        return False
    header, _, rest = command.partition("\n")
    if _value_seed_heredoc_header_argv(header) is None:
        return False
    body_lines = rest.split("\n")
    try:
        terminator_index = body_lines.index(_VALUE_SEED_HEREDOC_DELIMITER)
    except ValueError:
        return False
    return terminator_index == len(body_lines) - 1


def _git_subcommand(argv: list[str]) -> str | None:
    """The git subcommand token in *argv* (``argv[0]`` already known to be
    ``"git"``), skipping a leading ``-C <path>`` global-flag pair when
    present.

    Representation fix, not a scope change (design
    docs/analysis/2026-08-24-design-perimetro-auto-root.md, Candidata B2):
    positional ``argv[1]`` is right for ``git status`` but wrong for
    ``git -C <path> status`` -- there ``argv[1]`` is the literal string
    ``"-C"``, never a real subcommand, so every ``-C``-prefixed git call
    (the idiom this repo's own memory prescribes -- ``git -C <canonical>
    ...``, never ``cd`` first) was blocked regardless of how safe the
    trailing subcommand was. No new subcommand is admitted here; this only
    changes WHERE the parser looks for the one the allowlist already
    checks.
    """
    rest = argv[1:]
    if rest[:1] == ["-C"]:
        rest = rest[2:]  # drop "-C" and its path argument, if any
    return rest[0] if rest else None


def _evaluate_auto_root_bash_command(command: object) -> dict[str, str] | None:
    """Pure Auto-root Bash allowlist decision.

    Restricts Auto-root's OWN Bash calls to either a single, literal `git
    status|diff|rev-parse|branch|worktree|ls-files|add|commit` invocation
    (optionally preceded by a `-C <path>` global flag, resolved by
    `_git_subcommand`), or a single, literal `des dispatch|
    validate-delivery-contract|
    charter-scaffold|prepare-ordinary-request|resolve-charters|code-fact|
    compile-contract` invocation
    (the direct-cutover spine has no hook controller between Auto-root and
    the dispatched role's own DES CLI call). Lexically rejects any
    shell-composition operator (see
    `_AUTO_ROOT_BASH_INJECTION_MARKERS`) BEFORE `shlex.split` runs -- a
    string like ``"git status; rm -rf /"`` tokenizes cleanly under shlex,
    so the composition check must happen on the raw string first. Returns
    `None` (allow) or a `{decision: block, reason: ...}` payload. A missing,
    empty, whitespace-only, or non-string command fails CLOSED (blocked),
    not allowed: once Auto-root is armed, there is no well-formed command
    to fall through to the allowlist below on. Arguments after the allowed
    `git`/`des` verb are literal argv, already protected from shell
    composition by the injection-marker check above -- never re-interpreted
    as shell.
    """
    if not isinstance(command, str) or not command.strip():
        return _auto_root_bash_block(
            "WHAT: an Auto-root Bash call carried no usable command. "
            "WHY: Auto-root Bash is restricted to a single, literal git or "
            "des call -- a missing, empty, or whitespace-only command "
            "cannot be that call. "
            "HOW: run one git or des subcommand per Bash call, or dispatch "
            "a role instead."
        )
    if _is_value_seed_stdin_heredoc(command):
        return None
    if any(marker in command for marker in _AUTO_ROOT_BASH_INJECTION_MARKERS):
        return _auto_root_bash_block(
            "WHAT: an Auto-root Bash command carrying a shell-composition "
            "operator (&&, ||, ;, |, &, `, $(...), <, >, or a newline/CR) was "
            "blocked. "
            "WHY: Auto-root Bash is restricted to a single, literal git or "
            "des call -- composition operators can smuggle a second "
            "command past that allowlist. "
            "HOW: run one git or des subcommand per Bash call; drop the "
            "operator."
        )
    try:
        argv = shlex.split(command)
    except ValueError:
        return _auto_root_bash_block(
            "WHAT: an Auto-root Bash command failed to tokenize. "
            "WHY: Auto-root Bash must be a single well-formed git or des "
            "call. "
            "HOW: fix the quoting, or dispatch a role to run it."
        )
    if not argv or argv[0] not in ("git", "des"):
        return _auto_root_bash_block(
            "WHAT: an Auto-root Bash command is not a `git` or `des` "
            "invocation. "
            "WHY: Auto-root Bash is restricted to git status/diff/"
            "rev-parse/branch/worktree/add/commit, or des "
            f"{'/'.join(sorted(_AUTO_ROOT_BASH_ALLOWED_DES_SUBCOMMANDS))}. "
            "HOW: dispatch a role for other work, or run the equivalent "
            "git/des subcommand."
        )
    if argv[0] == "git":
        subcommand = _git_subcommand(argv)
        if subcommand not in _AUTO_ROOT_BASH_ALLOWED_GIT_SUBCOMMANDS:
            return _auto_root_bash_block(
                f"WHAT: an Auto-root `git {subcommand}` call was blocked. "
                "WHY: Auto-root Bash only allows git status/diff/rev-parse/"
                "branch/worktree/ls-files/add/commit. "
                "HOW: dispatch the appropriate nw-* role for any other git "
                "subcommand."
            )
        return None
    subcommand = argv[1] if len(argv) > 1 else None
    if subcommand not in _AUTO_ROOT_BASH_ALLOWED_DES_SUBCOMMANDS:
        return _auto_root_bash_block(
            f"WHAT: an Auto-root `des {subcommand}` call was blocked. "
            "WHY: Auto-root Bash only allows des "
            f"{'/'.join(sorted(_AUTO_ROOT_BASH_ALLOWED_DES_SUBCOMMANDS))}. "
            "HOW: dispatch the appropriate nw-* role for any other des "
            "subcommand."
        )
    return None


# Ale's construction-over-file correction (2026-08-20): ATD's ENTIRE Bash
# surface is `des fill-contract` -- mirrors the Auto-root Bash lockdown's
# own shape (shared injection-marker check, shared quoted-heredoc
# discipline for a value payload) rather than a second, independently
# hand-rolled mechanism. Admitted shapes: (a) a single-line, non-heredoc
# `--status` query; (b) one `--batch` call whose JSON array value arrives
# ONLY on a quoted `<<'NW_FILL'` heredoc (never a bare argv token -- the
# same opaque-bytes guarantee the Auto-root VALUE-SEED heredoc gives a
# quoted body no shell expansion); (c) one `--batch --batch-file` call
# with NO heredoc and NO JSON anywhere on the command line at all -- the
# provider-safe batch-file carrier transport (`des fill_contract`'s own
# `_acquire_batch_carrier`): a provider-side Bash safety heuristic can
# reject a heredoc whose body mixes a brace with a quote character (JSON
# necessarily has both) before nWave ever sees the call, so ATD writes the
# identical JSON array to the deterministic carrier file instead and this
# shape's Bash command carries only the deterministic path, never JSON.
# Flags are order-insensitive: `--status`/`--batch`/`--batch-file` are all
# value-less flags accepted at any position (K4 camp6 denial-RCA C-f1 -- a
# last-token-only `--status` rule falsely rejected the gate's own
# prescribed call shape).
_FILL_VALUE_HEREDOC_DELIMITER = "NW_FILL"
_FILL_VALUE_HEREDOC_HEADER_SUFFIXES = (
    f" <<'{_FILL_VALUE_HEREDOC_DELIMITER}'",
    f' <<"{_FILL_VALUE_HEREDOC_DELIMITER}"',
)
# THE one place naming `des fill-contract`'s allowed flag vocabulary --
# `des fill-contract --help` (`src/des/cli/fill_contract.py` `_parser`) is
# its own source; `tests/build/test_des_examples_are_executable.py`-style
# drift coverage, if any fenced example exists, would import this SAME
# frozenset rather than re-declare it.
_ATD_FILL_CONTRACT_ALLOWED_FLAGS = frozenset(
    {"--repo-root", "--delivery-id", "--status", "--batch", "--batch-file"}
)
#: The value-less flags in `_ATD_FILL_CONTRACT_ALLOWED_FLAGS` -- accepted
#: at any position, never followed by a value token.
_ATD_FILL_CONTRACT_VALUELESS_FLAGS = frozenset({"--status", "--batch", "--batch-file"})


def _atd_bash_block(reason: str) -> dict[str, str]:
    return {"decision": "block", "reason": reason}


def _fill_contract_argv(prefix: str) -> list[str] | None:
    """`shlex`-tokenized argv of `prefix`, or `None` if it carries a
    composition marker, fails to tokenize, is not `des fill-contract`,
    carries a flag outside `_ATD_FILL_CONTRACT_ALLOWED_FLAGS`, or gives
    (the batch shape is validated by the application constructor)."""
    if any(marker in prefix for marker in _AUTO_ROOT_BASH_INJECTION_MARKERS):
        return None
    try:
        argv = shlex.split(prefix)
    except ValueError:
        return None
    if len(argv) < 2 or argv[0] != "des" or argv[1] != "fill-contract":
        return None
    flags = argv[2:]
    seen: set[str] = set()
    i = 0
    while i < len(flags):
        token = flags[i]
        flag_name, _, inline_value = token.partition("=")
        if flag_name not in _ATD_FILL_CONTRACT_ALLOWED_FLAGS or flag_name in seen:
            return None
        seen.add(flag_name)
        if "=" in token:
            if flag_name in _ATD_FILL_CONTRACT_VALUELESS_FLAGS or not inline_value:
                return None
            i += 1
            continue
        if flag_name in _ATD_FILL_CONTRACT_VALUELESS_FLAGS:
            # Value-less flag, accepted at ANY position. K4 camp6
            # denial-RCA C-f1: a former last-token-only rule rejected the
            # prescribed `--status`-first query as "not well-formed" while
            # the identical invocation with `--status` last passed --
            # a position-sensitive parser turns the gate's own HOW into a
            # false rejection.
            i += 1
            continue
        # Every OTHER flag here takes a following value token.
        if i + 1 >= len(flags):
            return None
        i += 2
    if not {"--repo-root", "--delivery-id"}.issubset(seen):
        return None
    modes = seen & {"--status", "--batch"}
    if len(modes) != 1:
        return None
    if "--batch-file" in seen and "--batch" not in seen:
        return None
    return argv


def _fill_heredoc_header_prefix(command: str) -> str | None:
    """Header-line prefix (the argv text before the quoted `<<'NW_FILL'`
    redirect) iff `command` has the exact quoted NW_FILL heredoc TRANSPORT
    shape: one header line ending in `<<'NW_FILL'`/`<<"NW_FILL"`, an
    opaque body, and a terminator line that is exactly the delimiter,
    optionally followed by ONE final newline (`...\\nNW_FILL\\n` and
    `...\\nNW_FILL` are the same shell construct -- a Bash tool call
    routinely ends with a trailing newline). `None` on anything else --
    unquoted delimiter, missing terminator, any non-empty content after it
    -- which fails closed to the full-command composition scan.

    Shape only, on purpose: header VALIDITY is the caller's judgment.
    K4 camp6 denial-RCA C-f2: a QUOTED heredoc body is opaque to the
    shell by definition, so the composition-operator scan must never read
    it -- scanning the whole command on any header defect rejected body
    DATA containing `checks/<uuid:code>` as a "shell-composition
    operator". The opacity carve-out covers ONLY the bytes between the
    quoted-delimiter header and the terminator line."""
    if "\r" in command or "\n" not in command:
        return None
    header, _, rest = command.partition("\n")
    prefix = None
    for suffix in _FILL_VALUE_HEREDOC_HEADER_SUFFIXES:
        if header.endswith(suffix):
            prefix = header[: -len(suffix)]
            break
    if prefix is None:
        return None
    body_lines = rest.split("\n")
    try:
        terminator_index = body_lines.index(_FILL_VALUE_HEREDOC_DELIMITER)
    except ValueError:
        return None
    if body_lines[terminator_index + 1 :] not in ([], [""]):
        return None
    return prefix


def _is_fill_value_stdin_heredoc(command: str) -> bool:
    """True iff `command` is one hook-permitted fill-value heredoc: the
    quoted NW_FILL transport shape (`_fill_heredoc_header_prefix`) whose
    header validates as a batch `des fill-contract` argv with NO
    --batch-file. --batch-file and the heredoc are mutually exclusive JSON
    transports -- heredoc compatibility is preserved only in the absence
    of --batch-file."""
    prefix = _fill_heredoc_header_prefix(command)
    if prefix is None:
        return False
    argv = _fill_contract_argv(prefix)
    return argv is not None and "--batch" in argv and "--batch-file" not in argv


def _evaluate_atd_fill_contract_bash_command(
    command: object,
) -> dict[str, str] | None:
    """Pure ATD Bash allowlist decision (see the module comment above this
    section). Returns `None` (allow) or a `{decision: block, reason: ...}`
    payload. A missing, empty, whitespace-only, or non-string command
    fails CLOSED."""
    if not isinstance(command, str) or not command.strip():
        return _atd_bash_block(
            "WHAT: an ATD Bash call carried no usable command. "
            "WHY: ATD's entire Bash surface is `des fill-contract` -- a "
            "missing, empty, or whitespace-only command cannot be that "
            "call. "
            "HOW: run `des fill-contract --repo-root <root> --delivery-id "
            "<id> --status`, or one --batch call with its JSON on a quoted "
            "<<'NW_FILL' heredoc."
        )
    if _is_fill_value_stdin_heredoc(command):
        return None
    heredoc_prefix = _fill_heredoc_header_prefix(command)
    if heredoc_prefix is not None:
        heredoc_argv = _fill_contract_argv(heredoc_prefix)
        if (
            heredoc_argv is not None
            and "--batch" in heredoc_argv
            and "--batch-file" in heredoc_argv
        ):
            return _atd_bash_block(
                "WHAT: an ATD `des fill-contract` call combined "
                "--batch-file with a quoted <<'NW_FILL' heredoc. "
                "WHY: --batch-file and the heredoc are mutually exclusive "
                "JSON transports -- combining them leaves it ambiguous "
                "which one carries the batch. "
                "HOW: use exactly one transport -- either --batch "
                "<<'NW_FILL' with the JSON in the heredoc body, or "
                "--batch --batch-file with no heredoc at all."
            )
        # Quoted-heredoc TRANSPORT shape whose header does not validate:
        # the body between the quoted delimiter and the terminator line is
        # shell-opaque by definition and is NEVER scanned for composition
        # operators -- the defect is in the header line, and the rejection
        # must say so (K4 camp6 denial-RCA C-f2: the former whole-command
        # scan rejected inert body data as a "shell-composition
        # operator"). The header prefix's own composition check still runs
        # inside `_fill_contract_argv`, so a smuggled operator BEFORE the
        # redirect stays blocked.
        return _atd_bash_block(
            "WHAT: an ATD `des fill-contract` heredoc call has an invalid "
            "header line (the quoted NW_FILL body is opaque data and was "
            "not scanned). "
            "WHY: the header must be `des fill-contract` with only "
            "--repo-root/--delivery-id/--status/--batch, "
            "and exactly one read-only --status or write-capable --batch. "
            "HOW: fix the header line only; keep the value in the quoted "
            "<<'NW_FILL' ... NW_FILL body."
        )
    if any(marker in command for marker in _AUTO_ROOT_BASH_INJECTION_MARKERS):
        return _atd_bash_block(
            "WHAT: an ATD Bash command carrying a shell-composition "
            "operator was blocked. "
            "WHY: ATD's entire Bash surface is one `des fill-contract` "
            "call, quoted-heredoc value only -- composition operators can "
            "smuggle a second command past that allowlist. "
            "HOW: run one `des fill-contract` call per Bash call; drop "
            "the operator."
        )
    argv = _fill_contract_argv(command)
    if argv is None:
        return _atd_bash_block(
            "WHAT: an ATD Bash command is not a well-formed `des "
            "fill-contract` invocation. "
            "WHY: ATD's entire Bash surface is `des fill-contract "
            "--repo-root/--delivery-id/--status/--batch/--batch-file`, "
            "nothing else -- the batch is the sole write route. "
            "HOW: run exactly `des fill-contract ...` with only these "
            "flags."
        )
    if "--batch" in argv and "--batch-file" not in argv:
        return _atd_bash_block(
            "WHAT: an ATD `des fill-contract --batch` call did not use "
            "the quoted <<'NW_FILL' heredoc for its JSON value, and did "
            "not carry --batch-file either. "
            "WHY: the batch payload must arrive as opaque heredoc bytes "
            "or through the deterministic --batch-file carrier, never a "
            "bare argv token. "
            "HOW: run `des fill-contract ... --batch <<'NW_FILL'`, put "
            "the JSON payload in the heredoc body, and close it with "
            "`NW_FILL`; or write the JSON array to the deterministic "
            "carrier path and run `des fill-contract ... --batch "
            "--batch-file` with no heredoc."
        )
    return None


# nWave subagent host-scan lockdown (K4 architecture gap): a dispatched nw-*
# subagent's own Bash `find`/`bfs` call is restricted to a repo-scoped
# traversal root -- `find /` (or an option-prefixed equivalent) walks the
# whole host instead of the active project. Root/user Bash and non-nWave
# agents are untouched (see `_is_nwave_subagent`).
_HOST_SCAN_COMMAND_NAMES = frozenset({"find", "bfs"})


def _is_nwave_subagent(hook_input: dict[str, object]) -> bool:
    """True iff this dispatch is a running nWave subagent -- resolved via
    `root_activation_context.resolve_subagent_agent_type` (the ONE shared
    resolver: live envelope field, or its transcript meta-sidecar; see Run
    9/10 correction there) -- never root/user (neither source resolves) and
    never a non-nWave agent (some other prefix on both sources)."""
    return resolve_subagent_agent_type(hook_input) is not None


# Run 8 (Vera hit maxTurns:40 mid-work, zero terminal result -- the same
# silent-kill class as ATD in run 3): a subagent's OWN declared `maxTurns`
# is a hard boundary Claude Code enforces by simply stopping the agent --
# no terminal <ROLE>-RESULT, and root cannot tell that apart from "still
# working". A subagent must never be killed silently: once its own
# transcript shows its budget nearly exhausted, every further tool call is
# denied so its NEXT turn has no option left but the terminal text result
# (INDETERMINATE, with the reason, if the work genuinely is not done).
#
# Margin: `maxTurns - 2`, not `- 1` or `- 0` -- the agent needs the CURRENT
# turn free to actually emit the terminal result text, and one turn of
# slack for a hook round-trip; team lead's own spec ("allow up to N-3, deny
# at N-2") is the exact threshold this implements.
_SUBAGENT_BUDGET_MARGIN = 2


def _subagent_transcript_turn_count(transcript_path: str) -> int | None:
    """Tool-use count so far in a subagent's OWN transcript -- calibrated
    live against three real killed transcripts (run 8's nw-user-examiner,
    maxTurns 40; run 3's two nw-acceptance-designer dispatches, maxTurns
    12): counting `tool_use` content BLOCKS across every recorded
    assistant message reproduces the SDK's OWN self-reported `tool_uses`
    usage field EXACTLY in all three (40, 17, 18) -- raw assistant-entry
    count does not (it also counts pure thinking/text-only assistant
    messages that carry no tool call at all, and was found ~2x inflated
    against the real kill point in the same evidence). Blocks, not
    tool-use-bearing MESSAGES, so a future batched turn (several
    `tool_use` blocks in one assistant message) is still counted
    faithfully rather than undercounted by one. `None` on a missing,
    unreadable or non-UTF-8 transcript -- the caller must never guess a
    count it cannot observe.

    Residual, disclosed limitation: this reproduces the SDK's own
    `tool_uses` counter exactly, but that counter is not always identical
    to the declared `maxTurns` AT THE ACTUAL KILL POINT -- run 3's two
    ATD dispatches were cut off at `tool_uses` 17 and 18 against a
    declared `maxTurns: 12` (5-6 over), an older build's enforcement
    apparently allowing some slack this hook cannot see or control. This
    guard's margin (`_SUBAGENT_BUDGET_MARGIN`) denies well before either
    the declared budget or that observed slack in both real cases, but a
    third SDK behavior this evidence does not cover remains possible.
    """
    count = 0
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                message = entry.get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, list):
                    continue
                count += sum(
                    1
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "tool_use"
                )
    except (OSError, UnicodeDecodeError):
        return None
    return count


def _subagent_budget_exhaustion_block(
    role: str, *, max_turns: int, turn_count: int
) -> dict[str, str]:
    """The HOW text names no SPECIFIC marker: `subagent_stop_handler.py`'s
    own registry-free grammar (`_TERMINAL_HEADER_RE`) is the SSOT for what
    counts as a terminal result -- ANY `<TOKEN>-RESULT` a role's own spec
    already uses, never one synthesized from the role NAME. Measured
    2026-08-23 against every checked-in agent spec (`nWave/agents/*.md`,
    51 files): 0 declare the role-derived shape this text used to name
    (`f"{role.upper()}-RESULT"`) -- that branch was unreachable for every
    real role. Naming it here anyway would tell a subagent, under budget
    pressure, to emit a marker its OWN spec never established -- the exact
    class `subagent_stop_handler.py`'s docstring documents as already
    fixed on the READ side; this was the one remaining producer still
    emitting the old shape."""
    return {
        "decision": "block",
        "reason": (
            f"WHAT: {role}'s declared budget (maxTurns: {max_turns}) is "
            f"nearly exhausted -- {turn_count} assistant turns already "
            "observed in its own transcript. "
            "WHY: a subagent silently stopped at its hard maxTurns boundary "
            "mid-work returns NO terminal result at all -- root cannot "
            "distinguish that from a subagent still working, and the whole "
            "dispatch becomes unusable evidence. "
            "HOW: emit your own role's terminal <TOKEN>-RESULT line now -- "
            "the exact short marker your own role's spec already uses, "
            f"never a marker synthesized from the role name ({role!r}, "
            "which no role's own convention actually matches) -- verdict "
            "INDETERMINATE with the exact reason it is unfinished if the "
            "work genuinely is not done -- instead of spending another "
            "tool call; this is the last turn with budget to do so."
        ),
    }


def _evaluate_subagent_budget_exhaustion(
    hook_input: dict[str, object],
) -> dict[str, str] | None:
    """GDP-0 / stable-design report 2026-08-19 §1.1 -- REMOVE FALSIFIER (do
    not delete yet): this is a LAW re-deriving a fact
    `subagent_stop_handler.py`'s SubagentStop handler now consumes
    authoritatively (the platform's own completion event, `agent_type`
    always present there, `agent_transcript_path` needing no parent-session
    derivation). This function survives ONLY as a PRE-EMPTION courtesy --
    denying a tool call BEFORE the budget is exhausted is strictly better
    than a SubagentStop-time synthesized INDETERMINATE after the fact, when
    the heuristic count happens to be right. REMOVE this function once ALL
    of: (a) the SubagentStop handler has been running in production long
    enough to show its synthesized-terminal-result path reliably fires on
    every real silent stop (no third Run-9/10-class miss), (b) the
    preemption benefit is shown empirically not to matter economically
    (the report's own §4 found 6/6 sampled real firings already followed a
    clean terminal result even without SubagentStop -- the preemption case
    is not yet proven to earn its own maintenance cost), (c) team-lead/Ale
    authorizes the removal explicitly (GDP-0: a gate's removal is an
    authorization act, not a self-granted one). Until then this stays,
    unchanged in behaviour.

    Pure budget-exhaustion decision for a dispatched nw-* subagent's OWN
    tool call. `None` (allow) unless ALL of: this is a real nWave subagent
    (`root_activation_context.resolve_subagent_agent_type` -- live envelope
    field OR transcript meta-sidecar, see Run 9/10 correction), its own
    published spec declares a positive `maxTurns` (`resolve_declared_max_turns`
    -- `None` for a role that declares none is never gated here, matching
    Claude Code's own unlimited-turn default), and its OWN transcript
    already shows `maxTurns - _SUBAGENT_BUDGET_MARGIN` or more assistant
    turns. Applies to every tool call uniformly -- there is no "terminal"
    tool call to exempt; the terminal result is plain text, never a tool
    call, so this guard denying every tool call is exactly what forces it.

    Run 10 correction: turn-counting reads the subagent's OWN transcript
    (`resolve_subagent_own_transcript_path`), never the raw envelope field
    on faith -- a real crafter's `transcript_path` was verified to name the
    PARENT/root session log, not her own file; counting tool_use blocks
    there would count ROOT's activity, not hers."""
    agent_type = resolve_subagent_agent_type(hook_input)
    if agent_type is None:
        return None
    own_transcript_path = resolve_subagent_own_transcript_path(hook_input)
    if own_transcript_path is None:
        return None
    cwd = hook_input.get("cwd")
    repo_root = Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
    max_turns = resolve_declared_max_turns(agent_type, repo_root=repo_root)
    if max_turns is None:
        return None
    turn_count = _subagent_transcript_turn_count(own_transcript_path)
    if turn_count is None:
        return None
    if turn_count < max_turns - _SUBAGENT_BUDGET_MARGIN:
        return None
    return _subagent_budget_exhaustion_block(
        agent_type, max_turns=max_turns, turn_count=turn_count
    )


# Run 8 (B): root Read four test files plus models.py, drafted a full test
# addition, THEN had its Edit denied for touching role-owned source -- the
# denial arrived after the wasted reads, not before (GDP-1 violated). Root
# never Reads implementation/test source at all: only the docs/config
# authority roots below, or a physical path outside the repo entirely (the
# arm's own installed config, never this repo's source). Everything else is
# denied -- `nw-auto`'s "Root verification discipline" names the one
# permitted deterministic spot-check (`des code-fact`) and the only other
# route (dispatch the owning role) for anything a code-fact query cannot
# answer.
_AUTO_ROOT_SOURCE_READ_TOOL_NAMES = frozenset({"Read", "Grep", "Glob"})
_AUTO_ROOT_ALLOWED_READ_PATH_ROOTS = ("docs", "templates/docs", ".nwave")
_AUTO_ROOT_ALLOWED_READ_PATH_PREFIXES = tuple(
    f"{root}/" for root in _AUTO_ROOT_ALLOWED_READ_PATH_ROOTS
)
_AUTO_ROOT_ALLOWED_TOP_LEVEL_FILES = frozenset({"CLAUDE.md", "AGENTS.md"})


def _is_auto_root_allowed_read_path(relative_posix: str) -> bool:
    """True iff a repo-relative POSIX path sits under a docs/config
    authority root: `docs` itself or anything under `docs/**` (which
    already covers `docs/delivery-contracts/**`; `templates/docs` is
    separate since that tree does not nest under `docs/`), `.nwave` itself
    or anything under `.nwave/**`, or a top-level `CLAUDE.md`/`AGENTS.md`/
    `README*`/`*.md`. Bare `relative_posix in _AUTO_ROOT_ALLOWED_READ_PATH_
    ROOTS` covers a `Grep`/`Glob` `path` naming the directory ITSELF with
    no trailing content (`"docs"`, not `"docs/x"`) -- `startswith` alone
    never matches that exact string. A "top-level" file has no `/` in its
    relative path -- a same-named file nested in a subdirectory (a
    package's own README, a vendored CLAUDE.md) is NOT this repo's own
    root-level authority file and is not exempted by name alone."""
    if relative_posix in _AUTO_ROOT_ALLOWED_READ_PATH_ROOTS:
        return True
    if relative_posix.startswith(_AUTO_ROOT_ALLOWED_READ_PATH_PREFIXES):
        return True
    if "/" in relative_posix:
        return False
    return (
        relative_posix in _AUTO_ROOT_ALLOWED_TOP_LEVEL_FILES
        or relative_posix.startswith("README")
        or relative_posix.endswith(".md")
    )


def _auto_root_source_read_block(tool_name: str, relative_posix: str) -> dict[str, str]:
    return {
        "decision": "block",
        "reason": (
            f"WHAT: an Auto-root {tool_name} of {relative_posix!r} was "
            "blocked -- outside the docs/config authority roots root may "
            "read. "
            "WHY: root fact-checking implementation/test source duplicates "
            "work the architect/ATD/crafter already do and do again "
            "downstream (Run 5: 263s/185K tokens root spent re-reading "
            "files a role reads again); Run 8: root Read four test files "
            "plus models.py and drafted a test addition before its own Edit "
            "was denied for the same reason -- the wasted reads must never "
            "happen at all, not merely be caught one tool later. "
            "HOW: for a structural code fact, run the one bounded "
            "`des code-fact` call (`nw-auto`, 'Root verification "
            "discipline'); for anything needing real judgment about the "
            "source, dispatch the owning nw-* role instead of reading it "
            "yourself."
        ),
    }


def _evaluate_auto_root_source_read(
    tool_name: str, tool_input: dict[str, object], hook_input: dict[str, object]
) -> dict[str, str] | None:
    """Pure Auto-root Read/Grep/Glob allowlist decision. `None` (allow) for
    a path under a docs/config authority root, or a path resolving OUTSIDE
    the repo entirely (the arm's own installed config, never this repo's
    source). Denies everything else under the repo. `Grep`/`Glob` with no
    explicit `path` (their default, unscoped cwd search) is outside this
    guard's evidenced scope -- Run 8's own defect was `Read` of named
    files, never an unscoped Grep/Glob -- and is never denied here."""
    raw_path = (
        tool_input.get("file_path") if tool_name == "Read" else tool_input.get("path")
    )
    if not isinstance(raw_path, str) or not raw_path:
        return None
    cwd_raw = hook_input.get("cwd")
    repo_root = Path(cwd_raw) if isinstance(cwd_raw, str) and cwd_raw else Path.cwd()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    try:
        resolved = candidate.resolve()
        resolved_repo_root = repo_root.resolve()
    except OSError:
        return None
    if not resolved.is_relative_to(resolved_repo_root):
        return None
    relative_posix = resolved.relative_to(resolved_repo_root).as_posix()
    if _is_auto_root_allowed_read_path(relative_posix):
        return None
    return _auto_root_source_read_block(tool_name, relative_posix)


def _host_scan_traversal_roots(argv: list[str]) -> list[str]:
    """The traversal-root path arguments of a `find`/`bfs` argv.

    Options may precede the roots (`find -H /`); once at least one root has
    been collected, the next `-`-prefixed token starts the predicate/
    expression list and ends the scan -- `find /repo -name find` must not
    see a later bare `find` token in a predicate as a second root.
    """
    roots: list[str] = []
    for token in argv[1:]:
        if token.startswith("-"):
            if roots:
                break
            continue
        roots.append(token)
    return roots


def _is_host_wide_traversal_root(root: str) -> bool:
    """True iff `root` is the filesystem root itself (`/`, `//`, ...) --
    never a scoped path like `/repo`, `/tmp/project`, `.`, or `AUTO-ARCHITECTURE-ROOT`."""
    return root.rstrip("/") == ""


def _nwave_host_scan_block(command: str) -> dict[str, str]:
    return {
        "decision": "block",
        "reason": (
            f"WHAT: an nWave subagent Bash call ({command!r}) traverses the "
            "filesystem root instead of the active project. "
            "WHY: a host-wide find/bfs scan can spend minutes walking the "
            "entire machine instead of the project tree -- discovery must "
            "stay repo-scoped so a consult's critical path is not spent "
            "scanning the host. "
            "HOW: use repo-scoped Glob/Grep/find rooted at the project "
            "directory or the absolute AUTO-ARCHITECTURE-ROOT, or inspect "
            "the exact module path directly (e.g. `python -c "
            '"import inspect, <module>; print(inspect.getsourcefile(<module>))"` '
            "and read the returned path)."
        ),
    }


def _evaluate_nwave_subagent_host_scan(command: object) -> dict[str, str] | None:
    """Pure nWave-subagent `find`/`bfs` host-scan decision.

    Returns `None` (allow) for anything that is not, in some `&&`/`||`/`;`/
    `|`/`&`-separated sub-command, an actual `find`/`bfs` invocation whose
    traversal root is the filesystem root -- including quoted mentions
    (shlex tokenizes those into one non-command argument, never `argv[0]`)
    and repo-/cwd-/AUTO-root-scoped invocations. Fails open (`None`) on an
    unparsable command, matching `find_worktree_remove_target`'s contract.
    """
    if not isinstance(command, str) or not command.strip():
        return None
    sub_commands = _split_subcommands(command)
    if sub_commands is None:
        return None
    for argv in sub_commands:
        if not argv or argv[0] not in _HOST_SCAN_COMMAND_NAMES:
            continue
        roots = _host_scan_traversal_roots(argv)
        if any(_is_host_wide_traversal_root(root) for root in roots):
            return _nwave_host_scan_block(command)
    return None


# Lexical locator/anchor/header-line checks and the deterministic
# `DeliveryId` projection are shared with `des.cli.prepare_ordinary_request`
# (the producer for this gate's input) via `des.application.ordinary_request`, so the
# two sides of the same boundary cannot drift apart.


def _auto_root_crafter_thin_header_block() -> dict[str, str]:
    """Render the block payload for a malformed Auto-root crafter THIN header."""
    return {
        "decision": "block",
        "reason": (
            "WHAT: Auto-root crafter thin authority malformed -- the Agent "
            "prompt's first bytes are not exactly the two-line "
            "THIN-DELIVERY-CONTRACT / THIN-DELIVERY-CONTRACT-DIGEST header. "
            "WHY: the first bytes are the deterministic authority boundary "
            "-- no prose, fence, BOM, duplication, or reconstructed JSON may "
            "precede or follow it; validating this only downstream, inside "
            "the crafter itself, wastes an entire wave/service activation on "
            "a dispatch that was already doomed to AUTHORITY_REFUSED. "
            "HOW: forward ATD's exact two-line THIN-DELIVERY-CONTRACT / "
            "THIN-DELIVERY-CONTRACT-DIGEST block verbatim as the prompt's "
            "first bytes, with no reconstruction, hashing, or repair."
        ),
    }


def _evaluate_auto_root_crafter_thin_header(prompt: object) -> dict[str, str] | None:
    """Pure lexical Auto-root crafter THIN-header gate.

    Validates ONLY the shape of the prompt's first bytes -- never reads,
    hashes, opens, or schema-validates the referenced contract file. Returns
    `None` (allow -- fall through unchanged) when the prompt's first two
    lines are exactly a well-formed THIN-DELIVERY-CONTRACT /
    THIN-DELIVERY-CONTRACT-DIGEST pair, optionally followed by one blank
    line and unrelated context carrying no duplicate header. Otherwise
    returns the block payload.
    """
    if not isinstance(prompt, str):
        return _auto_root_crafter_thin_header_block()
    lines = prompt.split("\n")
    if len(lines) < 2:
        return _auto_root_crafter_thin_header_block()

    locator_line, digest_line = lines[0], lines[1]
    if not locator_line.startswith(_THIN_HEADER_LOCATOR_PREFIX):
        return _auto_root_crafter_thin_header_block()
    locator = locator_line[len(_THIN_HEADER_LOCATOR_PREFIX) :]
    if not is_lexical_repo_relative_json_locator(locator):
        return _auto_root_crafter_thin_header_block()

    if not digest_line.startswith(_THIN_HEADER_DIGEST_PREFIX):
        return _auto_root_crafter_thin_header_block()
    digest_hex = digest_line[len(_THIN_HEADER_DIGEST_PREFIX) :]
    if (
        len(digest_hex) != _THIN_HEADER_DIGEST_HEX_LEN
        or not set(digest_hex) <= _THIN_HEADER_DIGEST_HEX_ALPHABET
    ):
        return _auto_root_crafter_thin_header_block()

    remainder = lines[2:]
    if remainder:
        if remainder[0] != "":
            return _auto_root_crafter_thin_header_block()
        context = "\n".join(remainder[1:])
        if (
            _THIN_HEADER_LOCATOR_PREFIX.rstrip() in context
            or _THIN_HEADER_DIGEST_PREFIX.rstrip() in context
        ):
            return _auto_root_crafter_thin_header_block()

    return None


def _auto_root_po_envelope_block() -> dict[str, str]:
    """Render the block payload for a malformed/hand-authored Auto-root PO
    dispatch prompt."""
    return {
        "decision": "block",
        "reason": (
            "WHAT: Auto-root PO dispatch envelope malformed -- the Agent "
            "prompt is not exactly the six-line value-only "
            "DELIVERY-ID/NAMESPACE/ROOT/EXAMINE/DISCOVER/VALUE-SEED "
            "envelope, or it carries an ARCHITECTURE-COVERED anchor. "
            "WHY: `nw-product-owner` disqualifies itself as charter author "
            "the instant its own context carries an architecture-authority "
            "anchor (ADR-SSOT-002 Section 2 authority typing, Section 4c "
            "single-author route); root must never hand-compose this "
            "envelope -- a malformed or contaminated retry burns a full PO "
            "activation before the role's own refusal is even reached. "
            "HOW: run `des resolve-charters --repo-root <root> "
            "--delivery-id <id> --examine <true|false>` with the SAME "
            "VALUE-SEED bytes on stdin already piped to "
            "`des prepare-ordinary-request`, then paste its printed "
            "`AUTHOR` envelope verbatim as the prompt -- never author, "
            "reconstruct or augment it by hand; OR, to revise an EXISTING "
            "charter on a reviewer's value-side citation, run "
            "`des revise-charter-round --repo-root <root> --delivery-id "
            "<id> --citation <text>` and paste its exact eight-line stdout "
            "verbatim."
        ),
    }


def _evaluate_auto_root_po_envelope(prompt: object) -> dict[str, str] | None:
    """Lexical Auto-root PO envelope gate: shape-only. `None` (allow) iff
    `prompt` is exactly the six-line value-only envelope
    `des.application.ordinary_request.build_po_envelope` emits, OR exactly
    the eight-line charter-revision envelope `build_po_revision_envelope`
    emits (`des revise-charter-round`'s stdout), with no
    ARCHITECTURE-COVERED-shaped line anywhere; else the block payload."""
    if not isinstance(prompt, str):
        return _auto_root_po_envelope_block()
    if is_well_formed_po_envelope(prompt) or is_well_formed_po_revision_envelope(
        prompt
    ):
        return None
    return _auto_root_po_envelope_block()


def _auto_root_atd_body_block() -> dict[str, str]:
    return {
        "decision": "block",
        "reason": (
            "WHAT: Auto-root ATD dispatch body malformed. "
            "WHY: extra, missing, reordered or invalid facts make ATD infer "
            "or default upstream authority it must never guess. "
            "HOW: send exactly the architecture authority line, one blank "
            "line, then CONTRACT-LOCATOR, CONTRACT-SCHEMA, DELIVERY-ID, "
            "OUTCOME, ROOT, BASE-REVISION, DELIVERY-ROUTE, EXAMINE, "
            "INDEPENDENT-REVIEW, BUDGET-TOKEN-LIMIT, "
            "BUDGET-WALL-CLOCK-MINUTES, VALUE-SEED, each on its own line in "
            "that exact order, and nothing else. Contract/oracle correction "
            "is a strict closure child from the cited approved closure; no "
            "mutable revision body is admitted."
        ),
    }


def _evaluate_auto_root_atd_body(prompt: object) -> dict[str, str] | None:
    """Lexical Auto-root ATD full-body gate: exactly the architecture header,
    one blank line, then the twelve named non-empty facts (ADR-SSOT-002
    Section 4c) in this exact order -- and nothing else. Shape, enum and
    numeric-format validation only, no referenced-file I/O."""
    if not isinstance(prompt, str):
        return _auto_root_atd_body_block()
    lines = prompt.split("\n")
    if len(lines) != ATD_BODY_LINE_COUNT:
        return _auto_root_atd_body_block()

    header_line, blank_line, *fact_lines = lines
    if not is_valid_arch_header_line(header_line):
        return _auto_root_atd_body_block()
    if blank_line != "":
        return _auto_root_atd_body_block()

    (
        contract_locator_line,
        contract_schema_line,
        delivery_id_line,
        outcome_line,
        root_line,
        base_revision_line,
        delivery_route_line,
        examine_line,
        independent_review_line,
        budget_token_limit_line,
        budget_wall_clock_minutes_line,
        value_seed_line,
    ) = fact_lines

    # Shape-only checks for every fact except CONTRACT-LOCATOR, DELIVERY-ID,
    # OUTCOME and VALUE-SEED, which are cross-validated below instead of
    # trusted at face value -- ATD must never infer/default the delivery
    # identity from an unverified pair of independently-typed strings.
    fact_checks = (
        _has_absolute_schema_path_value(
            contract_schema_line, _ATD_CONTRACT_SCHEMA_LINE_PREFIX
        ),
        _has_absolute_value(root_line, _ATD_ROOT_LINE_PREFIX),
        _has_schema_tagged_base_revision(
            base_revision_line, _ATD_BASE_REVISION_LINE_PREFIX
        ),
        _has_route(delivery_route_line, _ATD_DELIVERY_ROUTE_LINE_PREFIX),
        _has_bool_value(examine_line, _ATD_EXAMINE_LINE_PREFIX),
        _has_bool_value(independent_review_line, _ATD_INDEPENDENT_REVIEW_LINE_PREFIX),
        _has_positive_integer_value(
            budget_token_limit_line, _ATD_BUDGET_TOKEN_LIMIT_LINE_PREFIX
        ),
        _has_positive_integer_value(
            budget_wall_clock_minutes_line,
            _ATD_BUDGET_WALL_CLOCK_MINUTES_LINE_PREFIX,
        ),
    )
    if not all(fact_checks):
        return _auto_root_atd_body_block()

    # OUTCOME and VALUE-SEED are compact JSON string literals (produced by
    # `des prepare-ordinary-request` with `ensure_ascii=False`) so arbitrary
    # newlines/quotes/shell metacharacters in the value seed cannot break the
    # fixed 14-line shape. Both must decode to the SAME exact Unicode text --
    # a producer that let them diverge could smuggle an unobserved outcome
    # past ATD. DELIVERY-ID and CONTRACT-LOCATOR are then required to equal
    # the deterministic projection recomputed from that decoded text, never
    # merely lexically well-formed on their own.
    outcome_value = _has_json_string_value(outcome_line, _ATD_OUTCOME_LINE_PREFIX)
    value_seed_value = _has_json_string_value(
        value_seed_line, _ATD_VALUE_SEED_LINE_PREFIX
    )
    if (
        outcome_value is None
        or value_seed_value is None
        or outcome_value != value_seed_value
    ):
        return _auto_root_atd_body_block()

    recomputed_delivery_id = compute_delivery_id(value_seed_value)
    if delivery_id_line != f"{_ATD_DELIVERY_ID_LINE_PREFIX}{recomputed_delivery_id}":
        return _auto_root_atd_body_block()

    recomputed_locator = contract_locator_for(recomputed_delivery_id)
    if (
        contract_locator_line
        != f"{_ATD_CONTRACT_LOCATOR_LINE_PREFIX}{recomputed_locator}"
    ):
        return _auto_root_atd_body_block()

    return None


def _auto_root_architect_envelope_block() -> dict[str, str]:
    return {
        "decision": "block",
        "reason": (
            "WHAT: Auto-root architect envelope malformed. "
            "WHY: DESIGN must consume, never infer, the upstream route. "
            "HOW: send exactly AUTO-ARCHITECTURE-CONSULT, "
            "AUTO-ARCHITECTURE-ROOT, and AUTO-DELIVERY-ROUTE, optionally "
            "followed by one AUTO-ARCHITECTURE-REJECTION: <<'NW_REJECTION' "
            "/ <producer's exact BLOCKED stdout, verbatim> / NW_REJECTION "
            "carrier for a repair re-consult."
        ),
    }


def _has_value(line: str, prefix: str) -> bool:
    return line.startswith(prefix) and bool(line[len(prefix) :].strip())


def _has_json_string_value(line: str, prefix: str) -> str | None:
    """Decode `line`'s value as a compact JSON string literal, or `None`.

    `des prepare-ordinary-request` emits OUTCOME/VALUE-SEED as
    `json.dumps(text, ensure_ascii=False)` so an arbitrary Unicode value
    seed (quotes, newlines, `$()`, globs) survives on one line without a new
    transport carrier. Rejects anything that is not itself a JSON string
    (e.g. a bare unquoted line, or a JSON number/object smuggled in).
    """
    if not line.startswith(prefix):
        return None
    try:
        decoded = json.loads(line[len(prefix) :])
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, str) else None


def _has_absolute_value(line: str, prefix: str) -> bool:
    if not line.startswith(prefix):
        return False
    value = line[len(prefix) :]
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _has_route(line: str, prefix: str) -> bool:
    return line.startswith(prefix) and line[len(prefix) :] in _DELIVERY_ROUTE_TOKENS


def _has_bool_value(line: str, prefix: str) -> bool:
    return line.startswith(prefix) and line[len(prefix) :] in ("true", "false")


def _has_positive_integer_value(line: str, prefix: str) -> bool:
    if not line.startswith(prefix):
        return False
    value = line[len(prefix) :]
    return bool(value) and value.isdigit() and value[0] != "0"


def _has_schema_tagged_base_revision(line: str, prefix: str) -> bool:
    if not line.startswith(prefix):
        return False
    value = line[len(prefix) :]
    for tag, hex_len in _ATD_BASE_REVISION_TAGS.items():
        if value.startswith(tag):
            hex_part = value[len(tag) :]
            return len(hex_part) == hex_len and set(hex_part) <= _HEX_ALPHABET
    return False


def _has_absolute_schema_path_value(line: str, prefix: str) -> bool:
    if not line.startswith(prefix):
        return False
    value = line[len(prefix) :]
    if not value.endswith(".json"):
        return False
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _is_auto_root_architect_rejection_carrier(body_lines: list[str]) -> bool:
    """True iff `body_lines` (everything AFTER the three fixed header
    lines) is exactly one well-formed AUTO-ARCHITECTURE-REJECTION heredoc
    carrier: the quoted header, at least one verbatim body line, then a
    bare `NW_REJECTION` terminator with nothing after it -- the same
    discipline `_is_value_seed_stdin_heredoc` already enforces for
    NW_SEED. Rejects an empty carrier (header immediately followed by the
    terminator): a repair re-consult with nothing to repair against is not
    a rejection carrier at all."""
    if len(body_lines) < 3:
        return False
    if body_lines[0] != _AUTO_ARCH_REJECTION_HEREDOC_HEADER:
        return False
    if body_lines[-1] != _AUTO_ARCH_REJECTION_HEREDOC_DELIMITER:
        return False
    return _AUTO_ARCH_REJECTION_HEREDOC_DELIMITER not in body_lines[1:-1]


def _evaluate_auto_root_architect_envelope(prompt: object) -> dict[str, str] | None:
    """Lexical Auto-root architect envelope gate: exactly three non-empty
    header lines -- AUTO-ARCHITECTURE-CONSULT, AUTO-ARCHITECTURE-ROOT,
    AUTO-DELIVERY-ROUTE -- optionally followed by ONE repair-consult
    rejection carrier (`AUTO-ARCHITECTURE-REJECTION: <<'NW_REJECTION'`,
    one or more verbatim body lines, a bare `NW_REJECTION` terminator,
    nothing after) -- and nothing else. Shape and route vocabulary only,
    no referenced-file I/O.

    The carrier exists so a re-consult after `des compile-contract`
    rejects the architect's own authored target-declaration table can
    forward that producer's exact BLOCKED stdout, byte-for-byte -- the
    same verbatim-envelope discipline this file already enforces for the
    PO/ATD envelopes, never a hand-paraphrase (GDP-0, K4 camp7
    2026-08-23: a paraphrased re-consult omitted the Target-cell detail
    entirely, three dispatches to converge on a shape the compiler had
    already named in full on the first rejection). The base three-line
    shape is BYTE-IDENTICAL to before -- a fresh, non-repair consult is
    unaffected."""
    if not isinstance(prompt, str):
        return _auto_root_architect_envelope_block()
    lines = prompt.split("\n")
    if len(lines) < 3:
        return _auto_root_architect_envelope_block()

    consult_line, root_line, route_line = lines[0], lines[1], lines[2]
    if not _has_value(consult_line, _AUTO_ARCH_CONSULT_LINE_PREFIX):
        return _auto_root_architect_envelope_block()
    if not _has_absolute_value(root_line, _AUTO_ARCH_ROOT_LINE_PREFIX):
        return _auto_root_architect_envelope_block()
    if not _has_route(route_line, _AUTO_ARCH_DELIVERY_ROUTE_LINE_PREFIX):
        return _auto_root_architect_envelope_block()

    if len(lines) == 3:
        return None
    if not _is_auto_root_architect_rejection_carrier(lines[3:]):
        return _auto_root_architect_envelope_block()
    return None


def emit_commit_attribution_mutation(
    tool_input: dict[str, object], *, cwd: Path | None = None
) -> int | None:
    """Net-new mutation branch: rewrite a Bash `git commit` to carry the trailer.

    ADR-CA-006 D4 (Reuse row R4). On a Bash `git commit` command, asks
    :class:`CommitAttributionService` for a :class:`CommitRewritePlan`. On a
    mutate Plan, emits the protocol JSON
    ``{"hookSpecificOutput":{"hookEventName":"PreToolUse",
    "permissionDecision":"allow","updatedInput":{<full tool_input, command
    rewritten>}}}`` on stdout and returns exit 0. On a passthrough Plan, returns
    ``None`` so the caller falls through to the existing validation path
    unchanged.

    This is the ONLY net-new branch in the handler; the existing block/allow
    validation path is not modified.

    Args:
        tool_input: the ``tool_input`` object from the PreToolUse payload. Its
            ``command`` field is the Bash command to consider.
        cwd: Optional working directory for attribution config resolution.

    Returns:
        ``0`` after emitting a mutation; ``None`` to fall through to the existing
        validation path (passthrough / non-Bash / non-commit).
    """
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return None

    # Fail-safe (ADR-CA-006): attribution is best-effort. ANY error here — a
    # raising rewrite core, a JSON-serialization failure — must NOT propagate to
    # the outer `handle_pre_tool_use` `except Exception`, which fail-closes to
    # exit 1 and BLOCKS the commit. A missed trailer is recoverable; a blocked
    # commit is not. On any failure, return None so the caller falls through to
    # the existing validation path and the original command runs unchanged.
    try:
        from des.application.commit_message_attribution import attribution_is_due

        # ONE condition, shared with the producing-tool path (`des commit` /
        # `des commit-slice` -> `attribute_commit_message`): ACTIVE repo AND
        # attribution preference on. Rewriting the user's `git commit` is an
        # action ON THE USER'S WORK, so ADR-AG-005 (opt-in ratified) governs it
        # exactly as it governs the producing tools -- this branch previously
        # read `attribution_enabled` alone and acted in repositories the user
        # never activated (F-ATTRIBUTION-GATING-ASYMMETRY-PRETOOLUSE). The
        # router's `activation_gate` resolving activation upstream is a property
        # of the CONTAINER, not of this seam: it is called directly, and its
        # `cwd` comes from the hook envelope, which need not name the root the
        # gate resolved (GDP-8 witness corollary).
        #
        # `Path.home()` is computed HERE, per call, not taken from
        # `DESConfig._DEFAULT_GLOBAL_CONFIG_PATH` -- that class attribute is
        # bound at import time and would pin a stale home.
        if not attribution_is_due(
            cwd or Path.cwd(),
            global_config_path=Path.home() / ".nwave" / "global-config.json",
        ):
            return None

        plan = _commit_attribution_service.plan_rewrite(command)
        if plan.action != "mutate" or plan.rewritten_command is None:
            return None

        updated_input = {**tool_input, "command": plan.rewritten_command}
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "updatedInput": updated_input,
                    }
                }
            )
        )
        return 0
    except Exception:
        return None


# Bound so step-composition / future wiring reference a single seam, not a free
# constructor call. DELIVER injects the real service here.
_commit_attribution_service = CommitAttributionService()


def evaluate_bash_safety_guards(
    hook_input: dict[str, object], tool_input: dict[str, object]
) -> dict[str, str] | None:
    """The git-stash + worktree-add/remove Bash guard decisions.

    Formerly two standalone PreToolUse/Bash hook registrations
    (`scripts/hooks/git_stash_guard.py`, `scripts/hooks/worktree_removal_guard.py`).
    The single decision authority is `des.adapters.drivers.hooks.bash_command_guards`
    (`evaluate_git_stash_command` / `evaluate_worktree_remove_command`); this
    function is one envelope-parsing wrapper around it. The standalone scripts
    call the shared predicate authority directly (their own CLI envelope
    shape), NOT necessarily this helper. `hook_router.main()` calls THIS
    helper by name, once, BEFORE `activation_gate.apply_gate` (ADR-AG-001
    ordering repair), so an inactive project cannot exit 0 past a live
    stash/worktree mutation -- see the router's pre-activation call site for
    the ordering contract. Returns a `{decision: block, reason: ...}` payload,
    or `None` to allow (paying no triage/filesystem work when neither guard's
    command shape matched).
    """
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return None

    repo = Path(str(hook_input.get("cwd") or Path.cwd()))
    worktree_add_decision = evaluate_worktree_add_command(command, repo)
    if worktree_add_decision is not None:
        if not worktree_add_decision.allow:
            return {
                "decision": "block",
                "reason": worktree_add_decision.reason or "",
            }
        return None

    stash_decision = evaluate_git_stash_command(command)
    if stash_decision is not None:
        if stash_decision.audit_event is not None:
            write_bash_guard_audit_event(
                git_stash_guard_target_root(),
                stash_decision.audit_event,
                {
                    **(stash_decision.audit_data or {}),
                    "session_id": str(hook_input.get("session_id", "")),
                },
            )
        if not stash_decision.allow:
            return {"decision": "block", "reason": stash_decision.reason or ""}
        return None

    worktree_decision = evaluate_worktree_remove_command(command, repo)
    if worktree_decision is not None:
        if worktree_decision.audit_event is not None:
            write_bash_guard_audit_event(
                worktree_guard_target_root(),
                worktree_decision.audit_event,
                {
                    **(worktree_decision.audit_data or {}),
                    "session_id": str(hook_input.get("session_id", "")),
                },
            )
        if not worktree_decision.allow:
            return {"decision": "block", "reason": worktree_decision.reason or ""}
        return None

    return None


def handle_pre_tool_use() -> int:
    """Handle PreToolUse command: validate Task tool invocation.

    Protocol translation only -- all decisions delegated to PreToolUseService.

    Returns:
        0 if validation passes (allow)
        1 if error occurs (fail-closed)
        2 if validation fails (block)
    """
    hook_id = str(uuid.uuid4())
    start_ns = time.perf_counter_ns()
    exit_code = 0
    task_correlation_id: str | None = None
    stderr_buffer = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buffer):
            stdin_result = read_and_parse_stdin("pre_tool_use")

            if stdin_result.is_empty:
                return 0

            if stdin_result.parse_error:
                response = {"status": "error", "reason": stdin_result.parse_error}
                print(json.dumps(response))
                exit_code = 1
                return exit_code

            # The is_empty / parse_error guards above guarantee a parsed dict.
            hook_input = stdin_result.hook_input
            assert hook_input is not None  # narrowed by the guards above

            # Diagnostic: confirm hook was invoked
            tool_input = hook_input.get("tool_input", {})

            tool_name = hook_input.get("tool_name")
            # Run 9/10 correction: `not agent_id and not agent_type` alone
            # misreads a real subagent's own call as root's whenever the
            # live envelope carries neither field (proven true for every
            # ordinary PreToolUse call in run 9 -- see
            # `root_activation_context.hook_input_has_agent_identity`). The
            # shared resolver adds the transcript meta-sidecar as a second
            # axis before concluding "no identity at all -> root".
            is_root_invocation = not hook_input_has_agent_identity(hook_input)
            transcript_path = (
                extract_transcript_path(hook_input) if is_root_invocation else None
            )
            # F-ROOT-MODE-GATE-SCOPE-CAPTURE-AND-LATCH defect 1: gates the
            # mode-select nagging/trap machinery on the SAME repo opt-in
            # every other consumer already honours -- computed only for a
            # root invocation (Python `and` short-circuit; a subagent call
            # never needs it, zero extra I/O for the common case).
            mode_gate_repo_active = (
                is_root_invocation and root_mode_gate_repo_is_active(hook_input)
            )
            root_mode_state = RootModeState.UNSELECTED
            if transcript_path:
                # defect 3: a later, unambiguous non-auto NW-MODE-SELECTED
                # marker may supersede an nw-auto engagement, but only before
                # any delivery artifact exists -- the SAME signal the
                # existing handoff/first-Bash blocks already read below.
                root_mode_state = resolve_root_mode_state(
                    transcript_path,
                    delivery_artifact_exists=des_task_signal.DES_DELIVER_SESSION_FILE.exists(),
                )

            # Run 8: a dispatched nw-* subagent's own declared maxTurns
            # budget nearly exhausted -- deny every further tool call so its
            # terminal result is forced out as text, never silently killed.
            # Runs before every other gate below: no other check should get
            # a chance to allow one more wasted tool call past this point.
            budget_block = _evaluate_subagent_budget_exhaustion(hook_input)
            if budget_block is not None:
                print(json.dumps(budget_block))
                exit_code = 2
                return exit_code

            # Close the state gap between selecting Auto M/L and engaging
            # nw-auto. The selection marker is ephemeral transcript evidence;
            # no controller, receipt, or file is introduced. Established
            # deliver sessions retain their existing route.
            # F-ROOT-MODE-GATE-SCOPE-CAPTURE-AND-LATCH defect 1: this is the
            # exact trap a beta user hit ("Invoke Skill(nw-auto) as the next
            # tool call" -- AUTO_PENDING's own reason text) -- scoped to a
            # repo that actually opted in, mirroring `activation_gate`.
            if (
                is_root_invocation
                and tool_name in _ROOT_MODE_HANDOFF_TOOL_NAMES
                and not des_task_signal.DES_DELIVER_SESSION_FILE.exists()
                and mode_gate_repo_active
            ):
                handoff_reason = root_mode_handoff_block_reason(root_mode_state)
                if handoff_reason is not None:
                    print(json.dumps({"decision": "block", "reason": handoff_reason}))
                    exit_code = 2
                    return exit_code

            # K4 architecture gap: Auto-root lockdown. Runs BEFORE the
            # existing mode-select observation gate and commit-attribution
            # mutation below (both scoped to "Bash"), so a locked-down call
            # never reaches either -- an armed but disallowed call is a
            # terminal block, not a fall-through to the general path.
            if (
                tool_name in _AUTO_ROOT_TASK_TOOL_LOCKDOWN_NAMES
                and root_mode_state is RootModeState.AUTO_ENGAGED
                and is_root_invocation
            ):
                if tool_name in _AUTO_ROOT_BLOCKED_TASK_TOOL_NAMES:
                    print(json.dumps(_auto_root_task_tool_block(tool_name)))
                    exit_code = 2
                    return exit_code
                if tool_name == "Bash":
                    auto_root_bash_block = _evaluate_auto_root_bash_command(
                        tool_input.get("command")
                    )
                    if auto_root_bash_block is not None:
                        print(json.dumps(auto_root_bash_block))
                        exit_code = 2
                        return exit_code

            # Ale's construction-over-file correction (2026-08-20): ATD's
            # entire Bash surface is `des fill-contract` -- mirrors the
            # Auto-root Bash lockdown immediately above, scoped to ATD's
            # own dispatched turn instead of root's.
            if (
                tool_name == "Bash"
                and resolve_subagent_agent_type(hook_input) == _ATD_ROLE_NAME
            ):
                atd_bash_block = _evaluate_atd_fill_contract_bash_command(
                    tool_input.get("command")
                )
                if atd_bash_block is not None:
                    print(json.dumps(atd_bash_block))
                    exit_code = 2
                    return exit_code

            # Run 8 (B): Auto-root Read/Grep/Glob of implementation/test
            # source is denied before the read happens, not caught later at
            # an Edit denial that arrives after the reads already ran.
            if (
                tool_name in _AUTO_ROOT_SOURCE_READ_TOOL_NAMES
                and root_mode_state is RootModeState.AUTO_ENGAGED
                and is_root_invocation
            ):
                source_read_block = _evaluate_auto_root_source_read(
                    tool_name, tool_input, hook_input
                )
                if source_read_block is not None:
                    print(json.dumps(source_read_block))
                    exit_code = 2
                    return exit_code

            # K4 architecture gap: nWave subagent host-scan lockdown. Cheap
            # for the overwhelming majority of Bash calls (non-find/bfs
            # commands, or a non-nWave-subagent caller) -- `_is_nwave_subagent`
            # is a dict-get + prefix check, no I/O.
            if tool_name == "Bash" and _is_nwave_subagent(hook_input):
                host_scan_block = _evaluate_nwave_subagent_host_scan(
                    tool_input.get("command")
                )
                if host_scan_block is not None:
                    print(json.dumps(host_scan_block))
                    exit_code = 2
                    return exit_code

            if hook_input.get("tool_name") == "SendMessage":
                if root_mode_state is RootModeState.AUTO_ENGAGED:
                    print(
                        json.dumps(
                            {
                                "decision": "block",
                                # K4 camp6 denial-RCA RC3: this deny sits at
                                # the exact decision fork where 2/3 campaign
                                # arms aborted -- it was the ONLY gate message
                                # with no HOW (four forbidden actions, zero
                                # permitted routes). p2 inferred "a fresh
                                # dispatch would be a retry in disguise" --
                                # false, and falsified by p3, which
                                # re-dispatched fresh three times and
                                # delivered. The HOW names the permitted
                                # route explicitly. (GDP-3/4/9)
                                "reason": (
                                    "WHAT: an Auto-root SendMessage call was "
                                    "blocked. "
                                    "WHY: Auto roles are single-pass -- do "
                                    "not SendMessage, resume, retry, or "
                                    "correct a role within the same Auto "
                                    "run; a role's first result is terminal. "
                                    "HOW: a FRESH Agent dispatch for a new "
                                    "contract round or a different route "
                                    "step IS allowed -- from CONTRACT_READY "
                                    "run `des dispatch`, and on contract "
                                    "defects run a strict closure correction."
                                ),
                            }
                        )
                    )
                    exit_code = 2
                    return exit_code

            if hook_input.get("tool_name") == "Agent":
                isolation_block = evaluate_agent_worktree_isolation(tool_input)
                if isolation_block is not None:
                    print(json.dumps(isolation_block))
                    exit_code = 2
                    return exit_code
                if is_root_invocation:
                    crafter_exit = _crafter_agent_rewrite(hook_input, tool_input)
                    if crafter_exit is not None:
                        exit_code = crafter_exit
                        return exit_code
                    candidate_exit = _candidate_agent_rewrite(hook_input, tool_input)
                    if candidate_exit is not None:
                        exit_code = candidate_exit
                        return exit_code
                reviewer_exit = _review_agent_prompt_rewrite(
                    hook_input, tool_input, is_root_invocation=is_root_invocation
                )
                if reviewer_exit is not None:
                    exit_code = reviewer_exit
                    return exit_code
                if root_mode_state is RootModeState.AUTO_ENGAGED:
                    role = tool_input.get("subagent_type")
                    if not isinstance(role, str) or not role.startswith("nw-"):
                        print(
                            json.dumps(
                                {
                                    "decision": "block",
                                    "reason": (
                                        f"Auto-root Agent dispatch to "
                                        f"'{role}' was blocked. "
                                        "WHY: Auto-root may only dispatch "
                                        "nWave (nw-*) roles -- a non-nWave "
                                        "subagent_type escapes Auto's own "
                                        "role authority. "
                                        "HOW: dispatch an nw-* role instead "
                                        f"of '{role}'."
                                    ),
                                }
                            )
                        )
                        exit_code = 2
                        return exit_code
                    if role in _AUTO_ROOT_CRAFTER_ROLES and is_root_invocation:
                        crafter_thin_block = _evaluate_auto_root_crafter_thin_header(
                            tool_input.get("prompt")
                        )
                        if crafter_thin_block is not None:
                            print(json.dumps(crafter_thin_block))
                            exit_code = 2
                            return exit_code
                    if role == _ARCHITECT_ROLE_NAME and is_root_invocation:
                        architect_envelope_block = (
                            _evaluate_auto_root_architect_envelope(
                                tool_input.get("prompt")
                            )
                        )
                        if architect_envelope_block is not None:
                            print(json.dumps(architect_envelope_block))
                            exit_code = 2
                            return exit_code
                    if role == _ATD_ROLE_NAME and is_root_invocation:
                        design_consult_block = _evaluate_auto_root_atd_body(
                            tool_input.get("prompt")
                        )
                        if design_consult_block is not None:
                            print(json.dumps(design_consult_block))
                            exit_code = 2
                            return exit_code
                    if role in _AUTO_ROOT_PO_ENVELOPE_ROLES and is_root_invocation:
                        po_envelope_block = _evaluate_auto_root_po_envelope(
                            tool_input.get("prompt")
                        )
                        if po_envelope_block is not None:
                            print(json.dumps(po_envelope_block))
                            exit_code = 2
                            return exit_code

            if hook_input.get("tool_name") == "Bash":
                # The git-stash / worktree-remove safety decision already ran
                # once, pre-activation, in `hook_router.main()` (before
                # `apply_gate`) -- see `evaluate_bash_safety_guards`. Do not
                # re-run it here; that would be a duplicate second evaluation
                # of the same command on the active path.
                # F-ROOT-MODE-GATE-SCOPE-CAPTURE-AND-LATCH defect 1: THE
                # scope-capture trigger a beta user hit -- fired on the FIRST
                # Bash of ANY task in ANY repo, no nWave-adjacency condition.
                # `mode_gate_repo_active` scopes it to a repo that actually
                # declared the SAME opt-in `activation_gate`/attribution
                # already honour.
                if (
                    is_root_invocation
                    and not des_task_signal.DES_DELIVER_SESSION_FILE.exists()
                    and mode_gate_repo_active
                ):
                    if root_mode_state is RootModeState.UNSELECTED:
                        print(
                            json.dumps(
                                {
                                    "decision": "block",
                                    "reason": (
                                        "Invoke nw-mode-select before the "
                                        "first Bash/Write/Edit."
                                    ),
                                }
                            )
                        )
                        exit_code = 2
                        return exit_code

                dispatch_exit = _dispatch_closure_rewrite(
                    hook_input, tool_input, is_root_invocation=is_root_invocation
                )
                if dispatch_exit is not None:
                    exit_code = dispatch_exit
                    return exit_code
                if is_root_invocation:
                    finalizer_exit = _finalize_candidate_rewrite(hook_input, tool_input)
                    if finalizer_exit is not None:
                        exit_code = finalizer_exit
                        return exit_code
                mutation_cwd = None
                if isinstance(hook_input.get("cwd"), str):
                    cwd_str = hook_input.get("cwd")
                    if cwd_str:
                        mutation_cwd = Path(cwd_str)
                mutation_exit = emit_commit_attribution_mutation(
                    tool_input, cwd=mutation_cwd
                )
                if mutation_exit is not None:
                    exit_code = mutation_exit
                    return exit_code
            log_hook_invoked(
                "pre_tool_use",
                {
                    "subagent_type": tool_input.get("subagent_type"),
                },
                hook_id=hook_id,
            )

            # The direct-cutover spine has no marker, slice-order, readiness,
            # review-ledger, or feature-end hook controller.  The explicit
            # Auto envelopes above are the only dispatch-shape checks at this
            # boundary; the validated DeliveryContract is consumed by the
            # dispatched role itself.  Preserve the existing root context
            # projection without re-deriving workflow state.
            prompt = tool_input.get("prompt", "")
            root_context = build_root_mode_select_context(
                prompt=prompt,
                subagent_type=tool_input.get("subagent_type"),
            )
            if root_context:
                print(
                    json.dumps(
                        {
                            "hookSpecificOutput": {
                                "hookEventName": "PreToolUse",
                                "permissionDecision": "allow",
                                "additionalContext": root_context,
                            }
                        }
                    )
                )
            exit_code = 0
            return exit_code

    except Exception as e:
        # Fail-closed: any error blocks execution
        stderr_capture = stderr_buffer.getvalue()[:STDERR_CAPTURE_MAX_CHARS]
        log_hook_error("pre_tool_use", e, stderr_capture)
        response = {"status": "error", "reason": f"Unexpected error: {e!s}"}
        print(json.dumps(response))
        exit_code = 1
        return exit_code
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        decision_str = EXIT_CODE_TO_DECISION.get(exit_code, "error")
        log_hook_completed(
            hook_id=hook_id,
            handler="pre_tool_use",
            exit_code=exit_code,
            decision=decision_str,
            duration_ms=duration_ms,
            task_correlation_id=task_correlation_id,
        )
