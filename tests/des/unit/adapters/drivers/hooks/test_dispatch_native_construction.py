"""E1 construction consumes only parent foreground Agent-result pairs."""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from des.adapters.drivers.hooks.pre_tool_use_handler import (
    _candidate_agent_rewrite,
    _candidate_binding,
    _closure_authority,
    _crafter_agent_rewrite,
    _dispatch_closure_rewrite,
    _finalize_candidate_rewrite,
    _review_agent_prompt_rewrite,
    _review_prompt_header_for_atd,
    handle_pre_tool_use,
)
from des.application.delivery_snapshot import recognize_closure
from des.cli import dispatch as dispatch_cli
from des.cli.dispatch import closure_digest


def _git(root: Path, *argv: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *argv], check=True, text=True, capture_output=True
    ).stdout.strip()


def _pair(
    *, tool: str, role: str, prompt: str, terminal: str
) -> list[dict[str, object]]:
    source = f"source-{tool}"
    call = {
        "type": "assistant",
        "uuid": source,
        "sessionId": "s",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool,
                    "name": "Agent",
                    "input": {
                        "subagent_type": role,
                        "run_in_background": False,
                        "prompt": prompt,
                    },
                }
            ]
        },
    }
    result = {
        "type": "user",
        "sessionId": "s",
        "sourceToolAssistantUUID": source,
        "message": {
            "content": [
                {"type": "tool_result", "tool_use_id": tool, "content": "display-only"}
            ]
        },
        "toolUseResult": {
            "status": "completed",
            "prompt": prompt,
            "agentId": f"agent-{tool}",
            "agentType": role,
            "content": [{"type": "text", "text": terminal}],
        },
    }
    return [call, result]


def _at_review_terminal(*, contract_digest: str, verdict: str) -> str:
    return "\n".join(
        (
            "AT-REVIEW",
            f"verdict: {verdict}",
            f"contract: delivery.json@sha256:{contract_digest}",
            "oracle: oracle.py",
            "findings: none",
        )
    )


_CHARTER_BODY_TEMPLATE = """\
# Observable delivery
ID: EXP-delivery-{index} · Spec rows: n/a · Persona: a developer

## Intent
Observe the delivered behavior through its public surface.

## Preconditions
The installed product is available.

## Charter
Exercise the user-visible outcome without reading source.

## Expected observations (oracle)
- The promised outcome is observable.
- Negative: a failed outcome never reports PASS.

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""


def _write_charter_member(root: Path, delivery_id: str, name: str, index: int) -> Path:
    path = root / "docs" / "product" / "expectations" / delivery_id / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_CHARTER_BODY_TEMPLATE.format(index=index), encoding="utf-8")
    return path


def _seed(
    tmp_path: Path,
    *,
    design_at_base: bool = False,
    charter_members_at_base: int = 0,
) -> tuple[Path, Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "test")
    _git(root, "config", "user.email", "test@example.invalid")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("before\n")
    (root / "verify.sh").write_text("#!/bin/sh\nexit 0\n")
    (root / "verify.sh").chmod(0o755)
    if design_at_base:
        (root / "docs").mkdir()
        (root / "docs" / "brief.md").write_text("# Brief\n")
    for index in range(charter_members_at_base):
        _write_charter_member(root, "delivery", f"charter-{index}.md", index)
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    base = _git(root, "rev-parse", "HEAD")
    if not design_at_base:
        (root / "docs").mkdir(exist_ok=True)
        (root / "docs" / "brief.md").write_text("# Brief\n")
    (root / "oracle.py").write_text("assert True\n")
    contract = {
        "schema-version": "1.3",
        "delivery-id": "delivery",
        "outcome": "change a",
        "paradigm": "object_oriented",
        "delivery-route": "RED_TO_GREEN",
        "obligations": ["PRESERVATION"],
        "repository": {"worktree": ".", "base-revision": f"git-sha1:{base}"},
        "targets": {
            "src/a.py": {
                "candidate": "src/a.py",
                "overlap": "none",
                "decision": "EXTEND",
                "justification": "test",
                "declared-imports": [],
                "contract-shape": "bounded-change",
                "boundary": {
                    "failure-behavior": "raise",
                    "substrate-lie": "none",
                    "substrate-probe": "test",
                    "double-blind-spot": "none",
                },
            }
        },
        "applicability": {"independent-review": True, "examine": False},
        "budget": {"token-limit": 1, "wall-clock-minutes": 1},
        "acceptance-tests": {"locator": "oracle.py"},
        "verification-scope": {
            "commands": [
                {
                    "executable": {"kind": "repository", "path": "verify.sh"},
                    "arguments": [],
                }
            ]
        },
    }
    (root / "delivery.json").write_text(json.dumps(contract))
    transcript = tmp_path / "parent.jsonl"
    records = [
        *_pair(
            tool="architect",
            role="nw-solution-architect",
            prompt="design",
            terminal="ARCHITECTURE-COVERED: docs/brief.md#brief",
        ),
        *_pair(
            tool="atd",
            role="nw-acceptance-designer",
            prompt="distill",
            terminal="\n".join(
                (
                    "DISTILL-RESULT: CONTRACT_READY",
                    f"REPO-ROOT: {root}",
                    "DELIVERY-CONTRACT: delivery.json",
                )
            ),
        ),
    ]
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    return transcript, root, base


def _construct_c(
    transcript: Path, root: Path, capsys: pytest.CaptureFixture[str]
) -> dict[str, object]:
    assert (
        _dispatch_closure_rewrite(
            {"transcript_path": str(transcript)},
            {
                "command": f"des dispatch --repo-root {root} --delivery-contract delivery.json"
            },
        )
        == 0
    )
    return json.loads(capsys.readouterr().out)


def test_dispatch_constructs_c_from_real_foreground_results(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript, root, base = _seed(tmp_path)
    calls = 0
    original = dispatch_cli.main

    def count_once(argv: list[str]) -> int:
        nonlocal calls
        calls += 1
        return original(argv)

    monkeypatch.setattr(dispatch_cli, "main", count_once)
    payload = _construct_c(transcript, root, capsys)
    handoff = "\n".join(_review_prompt_header_for_atd(root).splitlines()[:2]) + "\n"
    assert calls == 1
    assert payload["hookSpecificOutput"]["updatedInput"]["command"] == (
        f"printf %s {json.dumps(handoff)}"
    )
    assert _git(root, "rev-parse", "HEAD^") == base


def test_dispatch_allows_atd_only_when_architecture_authority_is_already_b(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript, root, base = _seed(tmp_path, design_at_base=True)
    atd_terminal = "\n".join(
        (
            "DISTILL-RESULT: CONTRACT_READY",
            f"REPO-ROOT: {root}",
            "DELIVERY-CONTRACT: delivery.json",
        )
    )
    transcript.write_text(
        "\n".join(
            json.dumps(record)
            for record in _pair(
                tool="atd-only",
                role="nw-acceptance-designer",
                prompt="distill",
                terminal=atd_terminal,
            )
        )
        + "\n"
    )

    _construct_c(transcript, root, capsys)

    assert _git(root, "rev-parse", "HEAD^") == base
    assert _git(root, "diff", "--name-only", base, "HEAD") == "delivery.json\noracle.py"


def test_dispatch_admits_an_already_valid_charter_namespace_with_no_po_attempt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REUSE route (ADR-SSOT-002 Section 4b): examine=true with a namespace
    already valid at base -- two filled charter members, no PO transcript
    attempt at all -- must admit closure construction and carry both
    members in `closure.authority_paths`, never demand a fresh PO attempt
    for a namespace that already satisfies Discover/Resolve."""
    transcript, root, base = _seed(tmp_path, charter_members_at_base=2)
    contract_path = root / "delivery.json"
    contract = json.loads(contract_path.read_text())
    contract["applicability"]["examine"] = True
    contract_path.write_text(json.dumps(contract))

    _construct_c(transcript, root, capsys)

    closure = recognize_closure(root, _git(root, "rev-parse", "HEAD"))
    expected_charter_paths = {
        f"docs/product/expectations/delivery/charter-{index}.md" for index in range(2)
    }
    assert expected_charter_paths <= set(closure.authority_paths)
    assert _git(root, "rev-parse", "HEAD^") == base


def test_dispatch_refuses_pending_design_without_bound_design_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript, root, base = _seed(tmp_path)
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    transcript.write_text(
        "\n".join(json.dumps(record) for record in records[2:]) + "\n"
    )

    assert (
        _dispatch_closure_rewrite(
            {"transcript_path": str(transcript)},
            {
                "command": f"des dispatch --repo-root {root} --delivery-contract delivery.json"
            },
        )
        == 2
    )
    assert "complete allowed authority set" in capsys.readouterr().out
    assert _git(root, "rev-parse", "HEAD") == base


def test_dispatch_handoff_binds_post_hook_normalized_closure_bytes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """C's public digest must name the bytes admitted after ordinary hooks."""
    transcript, root, base = _seed(tmp_path)
    pre_format_digest = closure_digest(
        (root / "delivery.json").read_bytes(), (root / "oracle.py").read_bytes()
    )
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir()
    hook.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' 'assert True  # formatted' > oracle.py\n"
        "git add oracle.py\n"
    )
    hook.chmod(0o755)

    payload = _construct_c(transcript, root, capsys)

    digest = closure_digest(
        (root / "delivery.json").read_bytes(), (root / "oracle.py").read_bytes()
    )
    expected_handoff = (
        "THIN-DELIVERY-CONTRACT: delivery.json\n"
        f"THIN-DELIVERY-CONTRACT-DIGEST: sha256:{digest}\n"
    )
    command = payload["hookSpecificOutput"]["updatedInput"]["command"]
    assert command == f"printf %s {json.dumps(expected_handoff)}"
    assert pre_format_digest not in command
    assert _git(root, "rev-parse", "HEAD^") == base


def test_dispatch_refuses_post_hook_structurally_incomplete_contract(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript, root, _base = _seed(tmp_path)
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir()
    hook.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' '{\"schema-version\": \"1.3\"}' > delivery.json\n"
        "git add delivery.json\n"
    )
    hook.chmod(0o755)

    assert (
        _dispatch_closure_rewrite(
            {"transcript_path": str(transcript)},
            {
                "command": f"des dispatch --repo-root {root} --delivery-contract delivery.json"
            },
        )
        == 2
    )
    assert "schema-valid" in capsys.readouterr().out


@pytest.mark.parametrize("kind", ("oracle", "support"))
def test_dispatch_refuses_post_hook_locator_not_admitted_in_c(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    transcript, root, _base = _seed(tmp_path)
    if kind == "support":
        contract = json.loads((root / "delivery.json").read_text())
        contract["schema-version"] = "1.4"
        contract["acceptance-tests"]["supporting-locators"] = ["support.py"]
        (root / "delivery.json").write_text(json.dumps(contract))
        (root / "support.py").write_text("support = True\n")
        old, replacement = "support.py", "src/a.py"
    else:
        old, replacement = "oracle.py", "src/a.py"
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir()
    hook.write_text(
        "#!/bin/sh\n"
        f"sed -i 's#{old}#{replacement}#' delivery.json\n"
        "git add delivery.json\n"
    )
    hook.chmod(0o755)

    assert (
        _dispatch_closure_rewrite(
            {"transcript_path": str(transcript)},
            {
                "command": f"des dispatch --repo-root {root} --delivery-contract delivery.json"
            },
        )
        == 2
    )
    assert "not admitted" in capsys.readouterr().out


@pytest.mark.parametrize("kind", ("oracle", "support"))
def test_closure_authority_refuses_symlinked_oracle_or_support(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    transcript, root, _base = _seed(tmp_path)
    path = "oracle.py"
    if kind == "support":
        contract = json.loads((root / "delivery.json").read_text())
        contract["schema-version"] = "1.4"
        contract["acceptance-tests"]["supporting-locators"] = ["support.py"]
        (root / "delivery.json").write_text(json.dumps(contract))
        (root / "support.py").write_text("support = True\n")
        path = "support.py"
    _construct_c(transcript, root, capsys)
    item = root / path
    item.unlink()
    item.symlink_to("src/a.py")
    closure = recognize_closure(root, _git(root, "rev-parse", "HEAD"))

    with pytest.raises(ValueError, match="regular"):
        _closure_authority(root, closure)


def test_atd_review_dispatch_publishes_admitted_closure_bytes_not_a_working_reread(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The published ATD handoff names the admitted closure, never a reread.

    C is admitted by a real construction, then the working contract is dirtied
    without any new commit.  The identity the real PreToolUse entry publishes
    into the reviewer prompt must still be the one the admitted bytes carry: a
    digest that moves with the mutable worktree would let a post-admission edit
    rename C while the admitted-authority reader on the same tree refuses those
    very bytes.  Driven through the public stdin/stdout hook entry, so the
    published value is the one a real reviewer dispatch would receive.
    """
    transcript, root, _base = _seed(tmp_path)
    _construct_c(transcript, root, capsys)
    admitted_digest = closure_digest(
        (root / "delivery.json").read_bytes(), (root / "oracle.py").read_bytes()
    )

    contract = json.loads((root / "delivery.json").read_text())
    contract["outcome"] = "dirtied after admission"
    (root / "delivery.json").write_text(json.dumps(contract))
    working_digest = closure_digest(
        (root / "delivery.json").read_bytes(), (root / "oracle.py").read_bytes()
    )
    assert working_digest != admitted_digest

    stdin = json.dumps(
        {
            "tool_name": "Agent",
            "cwd": str(root),
            "transcript_path": str(transcript),
            "tool_input": {
                "subagent_type": "nw-acceptance-designer-reviewer",
                "prompt": "review",
            },
        }
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    exit_code = handle_pre_tool_use()
    published = capsys.readouterr().out

    assert exit_code == 0, published
    payload = json.loads(published)
    prompt = payload["hookSpecificOutput"]["updatedInput"]["prompt"]
    assert f"THIN-DELIVERY-CONTRACT-DIGEST: sha256:{admitted_digest}" in prompt
    assert working_digest not in prompt


def test_dispatch_never_admits_authority_bytes_replaced_after_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """C carries the authority bytes the validator admitted, never a reread.

    The hook validates the contract, oracle and support members and then needs
    their bytes.  If it reaches back to the locator for those bytes, the file
    the validator accepted and the file C records are two different
    observations, and an ordinary regular-file replacement in between -- itself
    perfectly legitimate -- is admitted unvalidated.  Driven through the real
    PreToolUse stdin/stdout entry, with the oracle deterministically replaced
    once the validator has returned.  Either the boundary fails closed, or C
    carries the acquired original bytes; foreign bytes are admitted in neither
    case.  A single-acquisition hook consumes the bytes it already holds and
    satisfies this without any path probe at all.
    """
    transcript, root, base = _seed(tmp_path)
    validated_oracle = (root / "oracle.py").read_bytes()
    foreign_oracle = b"assert True  # replaced after validation\n"
    assert foreign_oracle != validated_oracle
    original_main = dispatch_cli.main

    def validate_then_replace_the_oracle(argv: list[str]) -> int:
        exit_code = original_main(argv)
        replacement = root / "foreign-oracle.py"
        replacement.write_bytes(foreign_oracle)
        replacement.replace(root / "oracle.py")
        return exit_code

    monkeypatch.setattr(dispatch_cli, "main", validate_then_replace_the_oracle)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(
            json.dumps(
                {
                    "tool_name": "Bash",
                    "cwd": str(root),
                    "transcript_path": str(transcript),
                    "tool_input": {
                        "command": (
                            f"des dispatch --repo-root {root} "
                            "--delivery-contract delivery.json"
                        )
                    },
                }
            )
        ),
    )
    exit_code = handle_pre_tool_use()
    published = capsys.readouterr().out
    monkeypatch.undo()

    head = _git(root, "rev-parse", "HEAD")
    admitted = (
        None
        if head == base
        else subprocess.run(
            ["git", "-C", str(root), "show", f"{head}:oracle.py"],
            check=True,
            capture_output=True,
        ).stdout
    )
    assert admitted != foreign_oracle, published
    if exit_code == 0:
        assert admitted == validated_oracle, published
    else:
        assert admitted in (None, validated_oracle), published


def test_dispatch_refuses_authority_replaced_before_independent_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hook must refuse, not seal A, when it validated B.

    The hook pre-acquires the oracle's authority bytes A *before* invoking the
    semantic validator.  If a controlled replacement swaps the oracle for
    distinct-but-otherwise-valid bytes B in the gap between that acquisition
    and the validator call, `dispatch_main` independently validates B, yet the
    hook still holds A.  Sealing A under a validation performed against B
    admits a member the validator never saw; the hook must refuse with a
    clear digest-divergence reason instead.
    """
    transcript, root, base = _seed(tmp_path)
    acquired_oracle = (root / "oracle.py").read_bytes()
    validated_oracle = b"assert True  # validated in place of acquired bytes\n"
    assert validated_oracle != acquired_oracle
    original_main = dispatch_cli.main

    def replace_before_independent_validation(argv: list[str]) -> int:
        replacement = root / "foreign-oracle.py"
        replacement.write_bytes(validated_oracle)
        replacement.replace(root / "oracle.py")
        return original_main(argv)

    monkeypatch.setattr(dispatch_cli, "main", replace_before_independent_validation)

    outcome = _dispatch_closure_rewrite(
        {"transcript_path": str(transcript)},
        {
            "command": f"des dispatch --repo-root {root} --delivery-contract delivery.json"
        },
    )
    published = capsys.readouterr().out

    assert outcome == 2, published
    assert "digest-divergence" in published, published
    assert _git(root, "rev-parse", "HEAD") == base


def test_dispatch_refuses_stale_wrong_foreground_result(tmp_path: Path, capsys) -> None:
    transcript, root, base = _seed(tmp_path)
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    records[-1]["toolUseResult"]["prompt"] = "stale"
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    assert (
        _dispatch_closure_rewrite(
            {"transcript_path": str(transcript)},
            {
                "command": f"des dispatch --repo-root {root} --delivery-contract delivery.json"
            },
        )
        == 2
    )
    assert "INDETERMINATE" in capsys.readouterr().out
    assert _git(root, "rev-parse", "HEAD") == base


@pytest.mark.parametrize(
    "mutation",
    (
        "design-prefix",
        "design-suffix",
        "design-duplicate",
        "atd-prefix",
        "atd-suffix",
        "atd-wrong-root",
        "atd-wrong-locator",
        "atd-duplicate",
    ),
)
def test_dispatch_refuses_nonexact_native_design_and_atd_terminals(
    tmp_path: Path, capsys, mutation: str
) -> None:
    transcript, root, base = _seed(tmp_path)
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    design = "ARCHITECTURE-COVERED: docs/brief.md#brief"
    atd = "\n".join(
        (
            "DISTILL-RESULT: CONTRACT_READY",
            f"REPO-ROOT: {root}",
            "DELIVERY-CONTRACT: delivery.json",
        )
    )
    if mutation == "design-prefix":
        design = f"completed\n{design}"
    elif mutation == "design-suffix":
        design = f"{design}\ncompleted"
    elif mutation == "design-duplicate":
        design = f"{design}\n{design}"
    elif mutation == "atd-prefix":
        atd = f"completed\n{atd}"
    elif mutation == "atd-suffix":
        atd = f"{atd}\ncompleted"
    elif mutation == "atd-wrong-root":
        atd = atd.replace(f"REPO-ROOT: {root}", "REPO-ROOT: /wrong-root")
    elif mutation == "atd-wrong-locator":
        atd = atd.replace(
            "DELIVERY-CONTRACT: delivery.json", "DELIVERY-CONTRACT: wrong.json"
        )
    else:
        atd = f"{atd}\nDELIVERY-CONTRACT: delivery.json"
    records[1]["toolUseResult"]["content"][0]["text"] = design  # type: ignore[index]
    records[3]["toolUseResult"]["content"][0]["text"] = atd  # type: ignore[index]
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    assert (
        _dispatch_closure_rewrite(
            {"transcript_path": str(transcript)},
            {
                "command": f"des dispatch --repo-root {root} --delivery-contract delivery.json"
            },
        )
        == 2
    )
    assert "INDETERMINATE" in capsys.readouterr().out
    assert _git(root, "rev-parse", "HEAD") == base


@pytest.mark.parametrize(
    "fault", ["placeholder", "oracle-path", "red-reason", "charter"]
)
def test_dispatch_refuses_every_semantic_preflight_before_constructing_c(
    tmp_path: Path, capsys, fault: str
) -> None:
    transcript, root, base = _seed(tmp_path)
    contract_path = root / "delivery.json"
    contract = json.loads(contract_path.read_text())
    if fault == "placeholder":
        contract["outcome"] = "<ATD: fill>"
    elif fault == "oracle-path":
        contract["acceptance-tests"]["locator"] = "missing-oracle.py"
    elif fault == "red-reason":
        (root / "verify.sh").write_text(
            "#!/bin/sh\necho 'SyntaxError: synthetic'\nexit 1\n"
        )
    else:
        contract["applicability"]["examine"] = True
    contract_path.write_text(json.dumps(contract))

    outcome = _dispatch_closure_rewrite(
        {"transcript_path": str(transcript)},
        {
            "command": f"des dispatch --repo-root {root} --delivery-contract delivery.json"
        },
    )
    assert outcome == 2
    assert _git(root, "rev-parse", "HEAD") == base
    assert "INDETERMINATE" in capsys.readouterr().out


def test_dispatch_preserves_a_symlink_root_for_public_cli_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript, root, base = _seed(tmp_path)
    symlink_root = tmp_path / "repo-link"
    symlink_root.symlink_to(root, target_is_directory=True)

    outcome = _dispatch_closure_rewrite(
        {"transcript_path": str(transcript)},
        {
            "command": f"des dispatch --repo-root {symlink_root} --delivery-contract delivery.json"
        },
    )
    assert outcome == 2
    assert _git(root, "rev-parse", "HEAD") == base
    assert "INDETERMINATE" in capsys.readouterr().out


def test_closure_replay_refuses_any_dirty_worktree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript, root, _base = _seed(tmp_path)
    _construct_c(transcript, root, capsys)
    closure = _git(root, "rev-parse", "HEAD")
    (root / "evil.py").write_text("dirt\n")

    outcome = _dispatch_closure_rewrite(
        {"transcript_path": str(transcript)},
        {
            "command": f"des dispatch --repo-root {root} --delivery-contract delivery.json"
        },
    )
    assert outcome == 2
    assert _git(root, "rev-parse", "HEAD") == closure
    assert "INDETERMINATE" in capsys.readouterr().out


def test_nonroot_review_and_dispatch_never_rewrite_or_construct(tmp_path: Path) -> None:
    transcript, root, base = _seed(tmp_path)
    assert (
        _review_agent_prompt_rewrite(
            {"cwd": str(root), "transcript_path": str(transcript)},
            {"subagent_type": "nw-acceptance-designer-reviewer", "prompt": "review"},
            is_root_invocation=False,
        )
        is None
    )
    assert (
        _dispatch_closure_rewrite(
            {"transcript_path": str(transcript)},
            {
                "command": f"des dispatch --repo-root {root} --delivery-contract delivery.json"
            },
            is_root_invocation=False,
        )
        is None
    )
    assert _git(root, "rev-parse", "HEAD") == base


def test_finalizer_leaves_ordinary_git_commit_outside_the_p5_lineage_alone(
    tmp_path: Path,
) -> None:
    transcript, root, _base = _seed(tmp_path)

    assert (
        _finalize_candidate_rewrite(
            {"cwd": str(root), "transcript_path": str(transcript)},
            {"command": "git commit -m ordinary"},
        )
        is None
    )


def test_finalizer_does_not_treat_commit_prefix_as_git_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript, root, _base = _seed(tmp_path)
    _construct_c(transcript, root, capsys)

    assert (
        _finalize_candidate_rewrite(
            {"cwd": str(root), "transcript_path": str(transcript)},
            {"command": "git commit-not-really -m no"},
        )
        is None
    )


@pytest.mark.parametrize(
    "verdict, mutation, expected",
    [
        ("APPROVED WITH CONDITIONS", "", 2),
        ("APPROVED", "plain", 2),
        ("APPROVED", "missing", 2),
        ("APPROVED", "extra", 2),
        ("APPROVED", "raw-digest", 2),
        ("APPROVED", "", 0),
    ],
)
def test_crafter_admission_requires_current_c_bound_unconditional_at_approval(
    tmp_path: Path, capsys, verdict: str, mutation: str, expected: int
) -> None:
    transcript, root, _base = _seed(tmp_path)
    _construct_c(transcript, root, capsys)
    header = _review_prompt_header_for_atd(root)
    digest = header.splitlines()[1].removeprefix(
        "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"
    )
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    terminal = _at_review_terminal(contract_digest=digest, verdict=verdict)
    if mutation == "plain":
        terminal = "APPROVED"
    elif mutation == "missing":
        terminal = terminal.removesuffix("\nfindings: none")
    elif mutation == "extra":
        terminal += "\nextra: no"
    elif mutation == "raw-digest":
        # The retired grammar carried a redundant raw oracle-file SHA; closure-v2
        # already binds oracle bytes into the contract digest, so this must be
        # rejected as a mismatched value, not silently accepted as legacy shape.
        oracle_digest = hashlib.sha256((root / "oracle.py").read_bytes()).hexdigest()
        terminal = terminal.replace(
            "oracle: oracle.py", f"oracle: oracle.py@sha256:{oracle_digest}"
        )
    records.extend(
        _pair(
            tool="review",
            role="nw-acceptance-designer-reviewer",
            prompt=header + "review",
            terminal=terminal,
        )
    )
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    outcome = _crafter_agent_rewrite(
        {"cwd": str(root), "transcript_path": str(transcript)},
        {"subagent_type": "nw-software-crafter", "prompt": "craft"},
    )
    assert outcome == expected
    payload = capsys.readouterr().out
    if expected == 0:
        assert "execution-root" in payload
    else:
        assert "INDETERMINATE" in payload


def test_crafter_admission_blocks_when_oracle_bytes_drift_after_review(
    tmp_path: Path, capsys
) -> None:
    """Dropping the redundant raw oracle SHA from AT-REVIEW must not open a
    gap: mutated oracle bytes still diverge from the admitted C commit, so
    closure authority itself -- not a review-terminal digest -- catches the
    drift and blocks crafter admission."""
    transcript, root, _base = _seed(tmp_path)
    _construct_c(transcript, root, capsys)
    header = _review_prompt_header_for_atd(root)
    digest = header.splitlines()[1].removeprefix(
        "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"
    )
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    terminal = _at_review_terminal(contract_digest=digest, verdict="APPROVED")
    records.extend(
        _pair(
            tool="review",
            role="nw-acceptance-designer-reviewer",
            prompt=header + "review",
            terminal=terminal,
        )
    )
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    (root / "oracle.py").write_text("assert True  # tampered after review\n")

    outcome = _crafter_agent_rewrite(
        {"cwd": str(root), "transcript_path": str(transcript)},
        {"subagent_type": "nw-software-crafter", "prompt": "craft"},
    )
    assert outcome == 2
    assert "INDETERMINATE" in capsys.readouterr().out


def test_crafter_admission_blocks_when_charter_bytes_drift_after_review(
    tmp_path: Path, capsys
) -> None:
    """A charter member admitted into C's authority is also part of the
    closure's integrity: mutating its bytes after AT review must diverge from
    the admitted C commit and block crafter admission, the same as an
    oracle-bytes drift, and the refusal must name the charter divergence, not
    a bare generic INDETERMINATE."""
    transcript, root, _base = _seed(tmp_path)
    contract_path = root / "delivery.json"
    contract = json.loads(contract_path.read_text())
    contract["applicability"]["examine"] = True
    contract_path.write_text(json.dumps(contract))
    charter_path = _write_charter_member(root, "delivery", "charter.md", 0)
    charter_relpath = "docs/product/expectations/delivery/charter.md"

    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    records.extend(
        _pair(
            tool="po",
            role="nw-product-owner",
            prompt="author",
            terminal="\n".join(
                ("CHARTER-RESULT", "verdict: PASS", f"path: {charter_relpath}")
            ),
        )
    )
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    _construct_c(transcript, root, capsys)
    header = _review_prompt_header_for_atd(root)
    digest = header.splitlines()[1].removeprefix(
        "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"
    )
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    terminal = _at_review_terminal(contract_digest=digest, verdict="APPROVED")
    records.extend(
        _pair(
            tool="review",
            role="nw-acceptance-designer-reviewer",
            prompt=header + "review",
            terminal=terminal,
        )
    )
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    charter_path.write_text(
        _CHARTER_BODY_TEMPLATE.format(index=0) + "tampered after review\n"
    )

    outcome = _crafter_agent_rewrite(
        {"cwd": str(root), "transcript_path": str(transcript)},
        {"subagent_type": "nw-software-crafter", "prompt": "craft"},
    )
    payload = capsys.readouterr().out
    assert outcome == 2
    assert "charter" in payload and charter_relpath in payload


@pytest.mark.parametrize("mutation", ["none", "outside-target", "authority-drift"])
def test_candidate_admission_requires_complete_target_only_crafter_delta(
    tmp_path: Path, capsys, mutation: str
) -> None:
    transcript, root, _base = _seed(tmp_path)
    _construct_c(transcript, root, capsys)
    review_header = _review_prompt_header_for_atd(root)
    digest = review_header.splitlines()[1].removeprefix(
        "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"
    )
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    records.extend(
        _pair(
            tool="review",
            role="nw-acceptance-designer-reviewer",
            prompt=review_header + "review",
            terminal="APPROVED",
        )
    )
    reported = "src/a.py"
    if mutation == "none":
        pass
    elif mutation == "outside-target":
        (root / "evil.py").write_text("outside\n")
        reported = "evil.py"
    else:
        (root / "delivery.json").write_text("{}")
    crafter_prompt = "\n".join(
        (
            review_header.splitlines()[0],
            review_header.splitlines()[1],
            "",
            f"execution-root: {root}",
            "craft",
        )
    )
    terminal = "\n".join(
        (
            "CRAFTER-RESULT",
            "verdict: PASS",
            f"contract: delivery.json@sha256:{digest}",
            f"execution-root: {root}",
            f"changed-targets: {reported}",
        )
    )
    records.extend(
        _pair(
            tool="crafter",
            role="nw-software-crafter",
            prompt=crafter_prompt,
            terminal=terminal,
        )
    )
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    outcome = _candidate_agent_rewrite(
        {"cwd": str(root), "transcript_path": str(transcript)},
        {"subagent_type": "nw-software-crafter-reviewer", "prompt": "review"},
    )
    assert outcome == 2
    assert "INDETERMINATE" in capsys.readouterr().out


def test_candidate_replay_requires_clean_post_seal_worktree(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    transcript, root, _base = _seed(tmp_path)
    _construct_c(transcript, root, capsys)
    review_header = _review_prompt_header_for_atd(root)
    digest = review_header.splitlines()[1].removeprefix(
        "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"
    )
    crafter_prompt = "\n".join(
        (
            review_header.splitlines()[0],
            review_header.splitlines()[1],
            "",
            f"execution-root: {root}",
            "craft",
        )
    )
    terminal = "\n".join(
        (
            "CRAFTER-RESULT",
            "verdict: PASS",
            f"contract: delivery.json@sha256:{digest}",
            f"execution-root: {root}",
            "changed-targets: src/a.py",
        )
    )
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    records.extend(
        _pair(
            tool="review",
            role="nw-acceptance-designer-reviewer",
            prompt=review_header + "review",
            terminal="APPROVED",
        )
    )
    records.extend(
        _pair(
            tool="crafter",
            role="nw-software-crafter",
            prompt=crafter_prompt,
            terminal=terminal,
        )
    )
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    (root / "src/a.py").write_text("after\n")

    first, *_rest = _candidate_binding(root, str(transcript))
    replay, *_rest = _candidate_binding(root, str(transcript))
    assert replay.commit == first.commit
    (root / "src/a.py").write_text("post-seal dirt\n")
    with pytest.raises(ValueError, match="post-seal dirt"):
        _candidate_binding(root, str(transcript))


@pytest.mark.parametrize(
    "verdict, mutation, expected",
    [
        ("APPROVED", "", 0),
        ("APPROVED WITH CONDITIONS", "", 2),
        ("APPROVED", "missing", 2),
        ("APPROVED", "extra", 2),
        ("APPROVED", "legacy-root", 2),
    ],
)
def test_finalizer_accepts_only_exact_unconditional_implementation_approval(
    tmp_path: Path, capsys, verdict: str, mutation: str, expected: int
) -> None:
    transcript, root, _base = _seed(tmp_path)
    _construct_c(transcript, root, capsys)
    review_header = _review_prompt_header_for_atd(root)
    digest = review_header.splitlines()[1].removeprefix(
        "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"
    )
    crafter_prompt = "\n".join(
        (*review_header.splitlines()[:2], "", f"execution-root: {root}", "craft")
    )
    crafter_terminal = "\n".join(
        (
            "CRAFTER-RESULT",
            "verdict: PASS",
            f"contract: delivery.json@sha256:{digest}",
            f"execution-root: {root}",
            "changed-targets: src/a.py",
        )
    )
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    records.extend(
        _pair(
            tool="crafter",
            role="nw-software-crafter",
            prompt=crafter_prompt,
            terminal=crafter_terminal,
        )
    )
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    (root / "src/a.py").write_text("after\n")
    candidate, *_rest = _candidate_binding(root, str(transcript))
    candidate_text = (
        f"git-{_git(root, 'rev-parse', '--show-object-format')}:{candidate.commit}"
    )
    implementation_prompt = (
        f"candidate: {candidate_text}\nexecution-root: {root}\nreview"
    )
    implementation_terminal = "\n".join(
        (
            "IMPLEMENTATION-REVIEW",
            f"verdict: {verdict}",
            f"contract: delivery.json@sha256:{digest}",
            f"candidate: {candidate_text}",
            "oracle-unchanged: true",
            "findings: none",
        )
    )
    if mutation == "missing":
        implementation_terminal = implementation_terminal.removesuffix(
            "\nfindings: none"
        )
    elif mutation == "extra":
        implementation_terminal += "\nextra: no"
    elif mutation == "legacy-root":
        implementation_terminal = "\n".join(
            (
                "IMPLEMENTATION-REVIEW",
                "verdict: APPROVED",
                f"candidate: {candidate_text}",
                f"execution-root: {root}",
            )
        )
    records.extend(
        _pair(
            tool="implementation-review",
            role="nw-software-crafter-reviewer",
            prompt=implementation_prompt,
            terminal=implementation_terminal,
        )
    )
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    outcome = _finalize_candidate_rewrite(
        {"cwd": str(root), "transcript_path": str(transcript)},
        {"command": "git commit -m finalize"},
    )
    assert outcome == expected
    payload = capsys.readouterr().out
    assert (
        ("Verdict: PASS" in payload) if expected == 0 else ("INDETERMINATE" in payload)
    )
    if expected == 0:
        assert "Clean-checkout: true" in payload
        assert (
            f"Commit: git-{_git(root, 'rev-parse', '--show-object-format')}:" in payload
        )
        replay = _finalize_candidate_rewrite(
            {"cwd": str(root), "transcript_path": str(transcript)},
            {"command": "git commit -m finalize"},
        )
        replay_payload = capsys.readouterr().out
        assert replay == 0
        assert replay_payload == payload
        assert _git(root, "rev-list", "--count", "HEAD") == "2"
        (root / "src/a.py").write_text("dirty final\n")
        assert (
            _finalize_candidate_rewrite(
                {"cwd": str(root), "transcript_path": str(transcript)},
                {"command": "git commit -m finalize"},
            )
            == 2
        )
        assert "INDETERMINATE" in capsys.readouterr().out
        _git(root, "checkout", "--", "src/a.py")
        final = _git(root, "rev-parse", "HEAD")
        forged = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "commit-tree",
                _git(root, "rev-parse", f"{final}^{{tree}}"),
                "-p",
                _git(root, "rev-parse", f"{final}^"),
            ],
            input="chore(des): finalize delivery\n",
            text=True,
            capture_output=True,
            check=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "forged",
                "GIT_AUTHOR_EMAIL": "forged@example.invalid",
                "GIT_COMMITTER_NAME": "forged",
                "GIT_COMMITTER_EMAIL": "forged@example.invalid",
                "GIT_AUTHOR_DATE": "@1 +0000",
                "GIT_COMMITTER_DATE": "@1 +0000",
            },
        ).stdout.strip()
        _git(root, "update-ref", "refs/heads/master", forged, final)
        assert (
            _finalize_candidate_rewrite(
                {"cwd": str(root), "transcript_path": str(transcript)},
                {"command": "git commit -m finalize"},
            )
            == 2
        )
        assert "INDETERMINATE" in capsys.readouterr().out


def test_at_review_cannot_be_replayed_across_closure_commits_with_same_contract_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An AT review names the current C's contract/oracle/support digest, but
    that digest deliberately ignores charter authority bytes -- so a review
    approving closure commit C1 must not silently authorize a DIFFERENT
    closure commit C2 whose charter bytes changed while contract/oracle/
    support stayed byte-identical.  Today `_crafter_agent_rewrite` admits
    C2 from a review that only ever saw C1: the review-prompt header carries
    no closure-commit identity, only the digest the two closures share."""
    transcript, root, _base = _seed(tmp_path)
    contract_path = root / "delivery.json"
    contract = json.loads(contract_path.read_text())
    contract["applicability"]["examine"] = True
    contract_path.write_text(json.dumps(contract))
    _write_charter_member(root, "delivery", "charter.md", 0)
    charter_relpath = "docs/product/expectations/delivery/charter.md"

    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    records.extend(
        _pair(
            tool="po",
            role="nw-product-owner",
            prompt="author",
            terminal="\n".join(
                ("CHARTER-RESULT", "verdict: PASS", f"path: {charter_relpath}")
            ),
        )
    )
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    _construct_c(transcript, root, capsys)
    review_header_c1 = _review_prompt_header_for_atd(root)

    from des.application.delivery_snapshot import (
        _git,
        construct_closure_correction,
        recognize_closure,
    )

    c1_commit = _git(root, "rev-parse", "HEAD").stdout.strip()
    c1 = recognize_closure(root, c1_commit)
    branch = _git(root, "symbolic-ref", "--short", "HEAD").stdout.strip()

    contract_bytes = (root / "delivery.json").read_bytes()
    oracle_bytes = (root / "oracle.py").read_bytes()
    changed_charter_bytes = (
        _CHARTER_BODY_TEMPLATE.format(index=0) + "PO revision after C1.\n"
    ).encode("utf-8")
    charter_mode = stat.S_IFREG | 0o644

    c2 = construct_closure_correction(
        root,
        cited=c1,
        contract=json.loads(contract_bytes.decode("utf-8")),
        contract_locator="delivery.json",
        contract_bytes=contract_bytes,
        oracle_locator="oracle.py",
        oracle_bytes=oracle_bytes,
        supporting=(),
        imports=((charter_relpath, changed_charter_bytes, charter_mode),),
    )
    assert c2.commit != c1.commit

    _git(root, "update-ref", f"refs/heads/{branch}", c2.commit)
    _git(root, "reset", "--hard", c2.commit)

    review_header_c2 = _review_prompt_header_for_atd(root)
    assert review_header_c2.splitlines()[:2] == review_header_c1.splitlines()[:2]

    digest = review_header_c1.splitlines()[1].removeprefix(
        "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"
    )
    terminal = _at_review_terminal(contract_digest=digest, verdict="APPROVED")
    records = [json.loads(line) for line in transcript.read_text().splitlines()]
    records.extend(
        _pair(
            tool="review",
            role="nw-acceptance-designer-reviewer",
            prompt=review_header_c1 + "review",
            terminal=terminal,
        )
    )
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    outcome = _crafter_agent_rewrite(
        {"cwd": str(root), "transcript_path": str(transcript)},
        {"subagent_type": "nw-software-crafter", "prompt": "craft"},
    )
    payload = capsys.readouterr().out
    # A review that only saw C1 cannot authorize C2, even when their public
    # contract/oracle/support digest is identical.
    assert outcome == 2, payload
