"""R-8 contract tests -- `session_start_handler.py`'s reconciliation seam.

DEFECT (RCA `docs/feature/fix-affordance-resolver-prefers-stale-copy/rca.md`,
Root Cause E / R-8, Branch E / §11.3): `load_orchestrator_affordance` was
called against a SINGLE hardcoded candidate
(`_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR`), with no reconciliation against a
host-neutral install root and no divergence notice -- the second, unfixed
producer of the same stale-copy defect the standalone hook
(`scripts/hooks/orchestrator_affordance_refresh.py`) already reconciles.

FIX under test: `_resolve_orchestrator_affordance_assets_dir()` builds a
2-candidate list (installed-Claude-scoped, installed-host-neutral) and
delegates the DECISION to the shared, dynamically-loaded
`orchestrator_affordance_resolution` module (never a static import across
the `scripts/**` <-> `src/des/**` boundary, F-D-09).

This file covers contract tests 2 and 3 named in the design's Architecture &
Contract Tests section (`docs/feature/fix-affordance-resolver-prefers-stale-
copy/feature-delta.md`):

  2. DES-side divergence test: two disagreeing INSTALLED_CLAUDE /
     INSTALLED_HOST_NEUTRAL roots produce the same class of in-band notice
     the standalone hook already produces.
  3. Fallback test: the shared-module sibling file missing at the shipped
     location -> SessionStart's resolution is unchanged from today's
     pre-R-8 behaviour (no crash, no notice).

Driven in-process via direct import (Mandate 16 exemption already granted to
this artifact class by the design: "purely-structural checks ... driven
in-process via direct import, since those are plain Python data/constants,
not the hook's own runtime behaviour").
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest


_SPINE_DISCIPLINE_MARKER = "SPINE-DISCIPLINE-MARKER"
_DIVERGENCE_MARKER = "DIVERGED"
_STALE_MARKER = "STALE-CONTENT-MUST-NOT-BE-SERVED"
_FRESH_MARKER = "FRESH-CONTENT-MUST-BE-SERVED"

# The REAL shared module shipped by this repo -- never duplicated here.
_REAL_RESOLUTION_MODULE_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts"
    / "hooks"
    / "orchestrator_affordance_resolution.py"
)


def _write_affordance_tree(root: Path, *, marker: str, mtime: float) -> Path:
    """One `orchestrator-affordance/` tree whose content and age are both pinned."""
    root.mkdir(parents=True, exist_ok=True)
    asset = root / "00-spine-discipline.md"
    asset.write_text(f"# {_SPINE_DISCIPLINE_MARKER}\n{marker}\n", encoding="utf-8")
    os.utime(asset, (mtime, mtime))
    return root


@pytest.fixture()
def handler_module():
    import des.adapters.drivers.hooks.session_start_handler as module

    return module


class TestDesSideDivergenceReconciliation:
    """Contract test 2: DES-side divergence produces the same notice class."""

    def test_fresher_host_neutral_root_is_served_and_announced(
        self, handler_module, tmp_path, monkeypatch
    ) -> None:
        assert _REAL_RESOLUTION_MODULE_PATH.is_file(), (
            f"expected the shared resolution module at {_REAL_RESOLUTION_MODULE_PATH}"
        )
        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_RESOLUTION_MODULE_PATH",
            _REAL_RESOLUTION_MODULE_PATH,
        )
        now = time.time()
        claude_scoped = _write_affordance_tree(
            tmp_path / "claude-scoped",
            marker=_STALE_MARKER,
            mtime=now - 34 * 3600,
        )
        host_neutral = _write_affordance_tree(
            tmp_path / "host-neutral",
            marker=_FRESH_MARKER,
            mtime=now,
        )
        monkeypatch.setattr(
            handler_module, "_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR", claude_scoped
        )
        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_HOST_NEUTRAL_ASSETS_DIR",
            host_neutral,
        )

        resolved_dir, notice = (
            handler_module._resolve_orchestrator_affordance_assets_dir()
        )

        assert resolved_dir == host_neutral, (
            f"the fresher INSTALL root must be served -- got {resolved_dir!r}"
        )
        assert notice is not None and _DIVERGENCE_MARKER in notice, (
            "two disagreeing install roots must degrade LOUD in-band (GDP-6) "
            f"-- got notice={notice!r}"
        )

    def test_agreeing_roots_produce_no_divergence_notice(
        self, handler_module, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_RESOLUTION_MODULE_PATH",
            _REAL_RESOLUTION_MODULE_PATH,
        )
        now = time.time()
        claude_scoped = _write_affordance_tree(
            tmp_path / "claude-scoped", marker=_FRESH_MARKER, mtime=now
        )
        host_neutral = _write_affordance_tree(
            tmp_path / "host-neutral", marker=_FRESH_MARKER, mtime=now - 34 * 3600
        )
        monkeypatch.setattr(
            handler_module, "_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR", claude_scoped
        )
        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_HOST_NEUTRAL_ASSETS_DIR",
            host_neutral,
        )

        resolved_dir, notice = (
            handler_module._resolve_orchestrator_affordance_assets_dir()
        )

        assert resolved_dir == claude_scoped
        assert notice is None, (
            "identical content in both roots is the healthy state -- must "
            f"stay silent however far apart the two mtimes are, got {notice!r}"
        )


class TestPeriodicRefreshUsesTheSameResolution:
    """The 15-minute re-injection must reconcile too, not just SessionStart.

    `user_prompt_submit_handler` re-injects the SAME assets on a cadence. It
    resolved them through the raw single-candidate constant, so importing the
    reconciliation into SessionStart alone would have left every refresh after
    the first prompt serving the stale root -- the defect surviving on the
    path the user actually spends the session in.
    """

    def test_periodic_refresh_serves_the_fresher_root_and_announces(
        self, handler_module, tmp_path, monkeypatch, capsys
    ) -> None:
        import des.adapters.drivers.hooks.user_prompt_submit_handler as ups

        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_RESOLUTION_MODULE_PATH",
            _REAL_RESOLUTION_MODULE_PATH,
        )
        now = time.time()
        claude_scoped = _write_affordance_tree(
            tmp_path / "claude-scoped", marker=_STALE_MARKER, mtime=now - 34 * 3600
        )
        host_neutral = _write_affordance_tree(
            tmp_path / "host-neutral", marker=_FRESH_MARKER, mtime=now
        )
        monkeypatch.setattr(
            handler_module, "_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR", claude_scoped
        )
        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_HOST_NEUTRAL_ASSETS_DIR",
            host_neutral,
        )

        ups._maybe_refresh_orchestrator_affordance(tmp_path / "project")

        emitted = capsys.readouterr().out
        assert _FRESH_MARKER in emitted, (
            "the periodic refresh must serve the fresher INSTALL root, not the "
            f"single-candidate constant -- got {emitted!r}"
        )
        assert _STALE_MARKER not in emitted, (
            f"the 34-hour-stale root must not be re-injected -- got {emitted!r}"
        )
        assert _DIVERGENCE_MARKER in emitted, (
            f"the divergence must be announced on this path too -- got {emitted!r}"
        )


class TestSharedModuleFallback:
    """Contract test 3: an absent/unloadable shared module degrades open."""

    def test_missing_shared_module_falls_back_to_single_candidate_no_notice(
        self, handler_module, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_RESOLUTION_MODULE_PATH",
            tmp_path / "does-not-exist" / "orchestrator_affordance_resolution.py",
        )
        claude_scoped = _write_affordance_tree(
            tmp_path / "claude-scoped", marker=_FRESH_MARKER, mtime=time.time()
        )
        host_neutral = _write_affordance_tree(
            tmp_path / "host-neutral", marker=_STALE_MARKER, mtime=time.time() - 3600
        )
        monkeypatch.setattr(
            handler_module, "_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR", claude_scoped
        )
        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_HOST_NEUTRAL_ASSETS_DIR",
            host_neutral,
        )

        resolved_dir, notice = (
            handler_module._resolve_orchestrator_affordance_assets_dir()
        )

        assert resolved_dir == claude_scoped, (
            "a missing shared module must fall back to the CURRENT "
            f"(pre-R-8) single-candidate resolution -- got {resolved_dir!r}"
        )
        assert notice is None, (
            "no reconciliation is attempted when the shared module cannot "
            f"be loaded -- got notice={notice!r}"
        )

    def test_missing_shared_module_never_raises(
        self, handler_module, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_RESOLUTION_MODULE_PATH",
            tmp_path / "does-not-exist" / "orchestrator_affordance_resolution.py",
        )
        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_ASSETS_DIR",
            tmp_path / "nothing-here",
        )
        monkeypatch.setattr(
            handler_module,
            "_ORCHESTRATOR_AFFORDANCE_HOST_NEUTRAL_ASSETS_DIR",
            tmp_path / "nothing-here-either",
        )

        resolved_dir, notice = (
            handler_module._resolve_orchestrator_affordance_assets_dir()
        )

        assert resolved_dir is None
        assert notice is None
