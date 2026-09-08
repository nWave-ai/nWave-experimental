"""Each DES role runs on the model ITS OWN SPEC declares -- one definition.

MEASURED, 2026-09-06, against the installed launcher (Claude Code 2.1.261).
Two probes, run as one command each:

* ``--agents`` carrying ``{"model": "haiku"}`` with the outer argv at
  ``--model sonnet`` produced a turn whose work landed on ``claude-sonnet-5``
  (``cacheReadInputTokens`` 2869, ``outputTokens`` 81) while the only
  ``claude-haiku-4-5`` entry stayed at the ambient ``in=1795 out=10`` baseline
  that appears in EVERY turn, declared model or not.
* The mirror probe, ``--agents`` ``{"model": "sonnet"}`` with the outer argv at
  ``--model haiku``, produced NO sonnet entry at all: ``claude-haiku-4-5``
  carried the whole turn (``in=4609 out=453``).

So the honoured channel is the outer ``--model``; the ``model`` key inside the
``--agents`` JSON is ignored, and the ambient haiku entry is not evidence that
a role ran on haiku.  This test pins the projection to the honoured channel:
whatever a role's published spec declares is what its turn spawns with, so the
model has ONE definition and it is the one a reader can open.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from des.adapters.driven.task_invocation.claude_code_task_adapter import (
    ClaudeCodeTaskAdapter,
)
from des.domain.agent_capability import resolve_declared_capability
from des.ports.driven_ports.task_invocation_port import ModelOutcome


#: Every role id `des` spawns a turn for: the two adapter-local constants plus
#: the role ids `DeliveryContinuationRunner` dispatches.  Kept explicit so a
#: role added to the runner without a declared model fails here rather than
#: silently inheriting one.
DES_ROLE_IDS = (
    "nw-product-owner",
    "nw-solution-architect",
    "nw-acceptance-designer",
    "nw-acceptance-designer-reviewer",
    "nw-software-crafter",
    "nw-functional-software-crafter",
    "nw-software-crafter-reviewer",
    "nw-user-examiner",
)

REPO_ROOT = Path(__file__).resolve().parents[6]


@dataclass
class _Completed:
    returncode: int
    stdout: str
    stderr: str


def _declared_model(role_id: str) -> str | None:
    return resolve_declared_capability(
        role_id, repo_root=REPO_ROOT, claude_dir=Path("/nonexistent")
    ).declared_model


def _spawned_argv(monkeypatch: pytest.MonkeyPatch, role_id: str) -> list[str]:
    """The argv one real turn would spawn, captured at the spawn boundary."""
    seen: list[list[str]] = []

    def _fake_spawn(argv, **kwargs):
        seen.append(list(argv))
        return _Completed(
            returncode=0,
            stdout='{"structured_output":{"outcome":"indeterminate",'
            '"diagnostic":"captured"}}',
            stderr="",
        )

    monkeypatch.setattr("des.runtime.spawn.spawn", _fake_spawn)
    adapter = ClaudeCodeTaskAdapter(Path("/usr/bin/claude"))
    try:
        adapter.invoke(role_id=role_id, prompt="probe", cwd=REPO_ROOT)
    except Exception:  # a payload role refuses this generic envelope; argv stands
        pass
    assert seen, f"no turn was spawned for {role_id}"
    return seen[0]


@pytest.mark.parametrize("role_id", DES_ROLE_IDS)
def test_every_des_role_declares_its_model_in_its_own_spec(role_id: str) -> None:
    assert _declared_model(role_id) is not None, (
        f"{role_id} has no `model:` in its frontmatter; the adapter would have "
        "nothing to project and the model would live in a second place"
    )


@pytest.mark.parametrize("role_id", DES_ROLE_IDS)
def test_the_spawned_model_is_the_one_the_spec_declares(
    role_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    argv = _spawned_argv(monkeypatch, role_id)

    assert argv[argv.index("--model") + 1] == _declared_model(role_id)


def test_reviewing_roles_are_declared_on_opus() -> None:
    """Ale, 2026-09-08: «analisi implementazioni e review a opus 5 low».

    This supersedes the 2026-09-06 sonnet preference for reviewing roles.
    """
    for role_id in (
        "nw-acceptance-designer-reviewer",
        "nw-software-crafter-reviewer",
        "nw-user-examiner",
        "nw-product-owner-reviewer",
    ):
        assert _declared_model(role_id) == "claude-opus-5"


def test_a_spec_with_no_declared_model_degrades_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No silent default: an undeclared model is INDETERMINATE, never `opus`."""
    spec = tmp_path / "nWave" / "agents" / "zz-role.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("---\ntools: Read\n---\njudge\n", encoding="utf-8")
    monkeypatch.setattr(
        "des.runtime.spawn.spawn",
        lambda *a, **k: pytest.fail("a role with no declared model must not spawn"),
    )

    run = ClaudeCodeTaskAdapter(Path("/usr/bin/claude")).invoke(
        role_id="zz-role", prompt="probe", cwd=tmp_path
    )

    assert run.outcome is ModelOutcome.Indeterminate
    assert "model" in run.diagnostic
