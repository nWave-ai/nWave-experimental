"""Dense tests for the batching fragment helper and its host projections."""

from __future__ import annotations

import importlib
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.shared.batching_fragment import (
    append_batching_fragment,
    load_batching_fragment,
)


FRAGMENT = "**Batch independent tool calls in one turn.**"
NEAR_MATCH = "**Batch independent tool calls in one turn, mostly.**"
_NAMES = ("nw-alpha-agent", "nw-beta-agent")
# host -> (module, class, target-dir patch attr or None, installed-file suffix)
_HOSTS = {
    "claude": ("agents_plugin", "AgentsPlugin", None, "md"),
    "codex": ("codex_agents_plugin", "CodexAgentsPlugin", "_codex_agents_dir", "toml"),
    "opencode": (
        "opencode_agents_plugin",
        "OpenCodeAgentsPlugin",
        "_opencode_agents_dir",
        "md",
    ),
}


@pytest.mark.parametrize(
    "body,expected",
    [
        ("", f"{FRAGMENT}\n"),
        ("BODY", f"BODY\n{FRAGMENT}\n"),
        ("BODY\n", f"BODY\n{FRAGMENT}\n"),
    ],
)
def test_append_batching_fragment_pure(body, expected):
    assert append_batching_fragment(body, FRAGMENT) == expected


def test_append_batching_fragment_idempotent_away_from_tail():
    body = f"HEADER\n{FRAGMENT}\nFOOTER"
    assert append_batching_fragment(body, FRAGMENT) == body


def test_append_batching_fragment_near_match_still_appends():
    body = f"BODY\n{NEAR_MATCH}"
    result = append_batching_fragment(body, FRAGMENT)
    assert result != body
    assert result.count(f"\n{FRAGMENT}\n") == 1


def test_load_batching_fragment_strips_and_validates(tmp_path):
    nwave = tmp_path / "nWave"
    (nwave / "templates").mkdir(parents=True)
    (nwave / "templates" / "tool-batching-fragment.md").write_text(f"  {FRAGMENT}  \n")
    assert load_batching_fragment(nwave) == FRAGMENT


def _make_sources(tmp_path):
    nwave = tmp_path / "nWave"
    (nwave / "templates").mkdir(parents=True)
    (nwave / "templates" / "tool-batching-fragment.md").write_text(FRAGMENT)
    (nwave / "agents").mkdir()
    originals = {n: f"---\nname: {n}\ndescription: Test\n---\nBODY {n}" for n in _NAMES}
    for name, content in originals.items():
        (nwave / "agents" / f"{name}.md").write_text(content)
    return nwave, originals


def _make_context(tmp_path, host):
    return InstallContext(
        claude_dir=tmp_path / ".claude",
        scripts_dir=tmp_path,
        templates_dir=tmp_path,
        logger=MagicMock(),
        project_root=tmp_path,
        framework_source=tmp_path,
        dev_mode=False,
        target_platforms={"codex"} if host == "codex" else {"claude_code"},
    )


def _target_dir(host, tmp_path, context):
    targets = {
        "claude": context.claude_dir / "agents" / "nw",
        "codex": tmp_path / ".codex" / "agents",
    }
    return targets.get(host, tmp_path / ".config" / "opencode" / "agents")


def _run_install(host, tmp_path, context):
    module, cls_name, dir_patch, suffix = _HOSTS[host]
    plugin_cls = getattr(
        importlib.import_module(f"scripts.install.plugins.{module}"), cls_name
    )
    target_dir = _target_dir(host, tmp_path, context)
    ctx_mgr = (
        patch(f"scripts.install.plugins.{module}.{dir_patch}", return_value=target_dir)
        if dir_patch
        else nullcontext()
    )
    with ctx_mgr:
        result = plugin_cls().install(context)
    return result, {name: target_dir / f"{name}.{suffix}" for name in _NAMES}


@pytest.mark.parametrize("host", _HOSTS)
def test_host_projection_and_single_fragment_load(tmp_path, host):
    nwave, originals = _make_sources(tmp_path)
    context = _make_context(tmp_path, host)
    module = _HOSTS[host][0]
    public_names = {f"{name}.md" for name in _NAMES}
    with (
        patch(
            f"scripts.install.plugins.{module}.load_public_agents",
            return_value=public_names,
        ),
        patch(f"scripts.install.plugins.{module}.is_public_agent", return_value=True),
        patch(
            f"scripts.install.plugins.{module}.load_batching_fragment",
            return_value=FRAGMENT,
        ) as load_spy,
    ):
        result, targets = _run_install(host, tmp_path, context)

    assert result.success
    assert load_spy.call_count == 1
    for name, target in targets.items():
        content = target.read_text(encoding="utf-8")
        assert content.count(FRAGMENT) == 1
        assert (nwave / "agents" / f"{name}.md").read_text(
            encoding="utf-8"
        ) == originals[name]
