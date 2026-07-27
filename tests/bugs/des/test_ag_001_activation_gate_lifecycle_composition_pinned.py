"""AG-001 regression AT -- pins the activation-gate-to-lifecycle composition.

Defect (pile `ag-001-lifecycle-seam-untested`): ``activation_gate.apply_gate``
``sys.exit(0)``s an INACTIVE project before the real PreToolUse handler ever
runs. A hook-gate test that never activates its tmp project therefore never
exercises the real enforcement policy at all -- it only proves the gate's own
``sys.exit(0)`` fast path, which is INDISTINGUISHABLE, by outcome alone (exit 0,
empty stdout), from a genuinely active project whose gate happens to pass. Such
a test is a false-green: it would stay green even if the real PreToolUse
enforcement policy regressed to always-allow, because it never reaches that
code at all.

This test drives the REAL production entry point (``claude_code_hook_adapter.main``
-> ``hook_router.main`` -> ``activation_gate.apply_gate`` -> ``handle_pre_tool_use``)
over the SAME genuinely-block-worthy payload (an Agent dispatch naming a step-id
with no DES markers -- the exact shape ``test_hook_protocol_conformance.py``'s
"PreToolUse block produces structured JSON on stdout" scenario pins as a REAL
enforcement block when the project is active) under TWO real tmp projects that
differ ONLY in activation:

  * INACTIVE (no ``.nwave/local-config.json`` marker, default opt-in global
    mode) -- ``apply_gate`` must short-circuit BEFORE the enforcement policy
    ever runs: exit 0, empty stdout (allow), even though the payload is
    block-worthy. This is the ``ALLOWED_EXIT_0`` gate outcome.
  * ACTIVE (marker ``enabled_for_repo: true``) -- the SAME payload must reach
    the real ``handle_pre_tool_use()`` -> ``PreToolUseService`` and BLOCK for
    real: exit 2, structured JSON block reason on stdout. This is the
    ``DISPATCHED`` gate outcome, with the handler actually running and
    actually failing.

The two outcomes are asserted to be OBSERVABLY DISTINCT for the identical
payload -- proving the inactive-project ``sys.exit(0)`` path is a different,
distinguishable code path from a genuinely active-but-failing gate, and that
omitting project activation from a hook-gate test is a silent bypass of the
entire lifecycle composition (never a substitute for exercising it).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.drivers.hooks import claude_code_hook_adapter
from tests.common.in_process_cli import run_hook_in_process


def _block_worthy_pretooluse_stdin(project_root: Path) -> str:
    """The exact block-worthy shape: a step-id-naming Agent dispatch with no
    DES markers (mirrors ``test_hook_protocol_conformance.py``'s
    ``given_agent_with_step_id_no_markers``), plus an explicit ``cwd`` so
    activation resolution is hermetic (no reliance on ``DES_PROJECT_DIR`` /
    the real checkout's own activation state)."""
    return json.dumps(
        {
            "tool_name": "Agent",
            "tool_input": {
                "prompt": "Execute step 01-01: implement the login feature.",
                "subagent_type": "software-crafter",
            },
            "cwd": str(project_root),
        }
    )


def _invoke_pre_tool_use(project_root: Path) -> tuple[int, str, str]:
    return run_hook_in_process(
        claude_code_hook_adapter.main,
        stdin_text=_block_worthy_pretooluse_stdin(project_root),
        cwd=str(project_root),
        argv=["claude_code_hook_adapter", "pre-tool-use"],
    )


@pytest.fixture
def sandbox_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated $HOME so the global-config activation mode (default opt-in)
    resolves hermetically, independent of the real machine's own config."""
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    # DES_PROJECT_DIR must not leak from the outer test session's isolation
    # root -- stdin always carries an explicit "cwd", so apply_gate's
    # _parse_cwd never needs to fall back to it, but clearing it removes any
    # doubt about which project resolution path is under test.
    monkeypatch.delenv("DES_PROJECT_DIR", raising=False)
    return home_dir


def _write_marker(project_root: Path, *, enabled: bool) -> None:
    nwave = project_root / ".nwave"
    nwave.mkdir(parents=True, exist_ok=True)
    (nwave / "local-config.json").write_text(
        json.dumps({"enabled_for_repo": enabled}) + "\n", encoding="utf-8"
    )


@pytest.mark.negative_at
def test_inactive_project_allows_a_block_worthy_payload_via_the_gate_fast_path(
    tmp_path: Path, sandbox_home: Path
) -> None:
    """An INACTIVE project allows the block-worthy payload -- the enforcement
    policy never runs; the gate itself decides the outcome (ALLOWED_EXIT_0)."""
    project_root = tmp_path / "inactive_project"
    project_root.mkdir()
    # No marker written -- default opt-in + absent marker resolves inactive
    # (des.domain.activation_policy.resolve_activation).

    exit_code, stdout, _stderr = _invoke_pre_tool_use(project_root)

    assert exit_code == 0, (
        "an inactive project must ALLOW (exit 0) via the activation gate's own "
        f"fast path, never reach the enforcement policy; got exit {exit_code}"
    )
    assert stdout == "", (
        "the inactive-project allow path must be silent (empty stdout) -- the "
        f"enforcement policy never ran; got stdout={stdout!r}"
    )


@pytest.mark.negative_at
def test_active_project_blocks_the_identical_block_worthy_payload_for_real(
    tmp_path: Path, sandbox_home: Path
) -> None:
    """The SAME payload, in an ACTIVE project, reaches the real PreToolUseService
    and is genuinely BLOCKED -- proving the DISPATCHED path actually runs the
    handler rather than being masked by the gate's own allow outcome."""
    project_root = tmp_path / "active_project"
    project_root.mkdir()
    _write_marker(project_root, enabled=True)

    exit_code, stdout, _stderr = _invoke_pre_tool_use(project_root)

    assert exit_code == 2, (
        "an active project with a step-id-naming, marker-less Agent dispatch "
        f"must BLOCK for real (exit 2) via the real enforcement policy; got "
        f"exit {exit_code}, stdout={stdout!r}"
    )
    assert stdout.strip(), (
        "a genuine block must carry structured JSON with a reason on stdout "
        "(the DISPATCHED path's real handler output), not empty stdout"
    )
    payload = json.loads(stdout)
    assert "reason" in payload or "decision" in payload, (
        f"the block payload must self-explain (WHAT/WHY) -- got {payload!r}"
    )


@pytest.mark.negative_at
def test_activation_state_is_the_only_difference_between_allow_and_block(
    tmp_path: Path, sandbox_home: Path
) -> None:
    """Same payload, same code path, ONLY the marker differs -- the two
    outcomes (allow vs block) must be observably distinct, pinning that the
    inactive sys.exit(0) fast path never masks a genuinely active-but-failing
    gate (and, symmetrically, that a hook-gate test omitting activation is not
    equivalent to one that includes it)."""
    inactive_root = tmp_path / "twin_inactive"
    active_root = tmp_path / "twin_active"
    inactive_root.mkdir()
    active_root.mkdir()
    _write_marker(active_root, enabled=True)

    inactive_exit, inactive_stdout, _ = _invoke_pre_tool_use(inactive_root)
    active_exit, active_stdout, _ = _invoke_pre_tool_use(active_root)

    assert (inactive_exit, inactive_stdout) != (active_exit, active_stdout), (
        "activation must be outcome-determining for an otherwise-identical "
        "block-worthy payload: inactive="
        f"{(inactive_exit, inactive_stdout)!r} active={(active_exit, active_stdout)!r}"
    )
    assert inactive_exit == 0 and active_exit == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
