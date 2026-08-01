"""Regression: `des commit` / `des commit-slice` never applied the nWave
attribution trailer -- the PRODUCING TOOLS run `git commit` inside a Python
subprocess the PreToolUse Bash rewriter (`trailer_rewriter.py`) never
observes, so the trailer never landed even with `attribution.enabled: true`
in `~/.nwave/global-config.json` (fix-attribution-trailer-never-applied).

Measured (worktree HEAD ec9ae2a10, before the fix): with attribution ON,
`des commit` produced a message ending in `Step-Id: 01-01` -- sentinel count
0; the `commit-slice` placeholder path produced a message ending in
`Gate-Scope: 000...` -- sentinel count 0. Only 1 of the last 200 commits in
this repo carried the trailer.

Fix (GDP-4, the PRODUCING TOOL attributes itself): a pure domain function
`apply_attribution_trailer` (`src/des/domain/commit_attribution/
attribution_trailer.py`) plus an application seam `attribute_commit_message`
(`src/des/application/commit_message_attribution.py`) that both `commit.py`
and `commit_slice.py` call before their own `git commit`. Five properties
below, each traced to its demonstrated failing shape in the dispatch RCA.

Hermeticity: every test drives a REAL git repo under `tmp_path`, and every
global-config lookup is redirected via `DESConfig._DEFAULT_GLOBAL_CONFIG_PATH`
monkeypatching or an explicit `global_config_path=` override -- the real
`~/.nwave/` and `~/.claude/` are never read or written (there is a live
half-landed install on this machine).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
        text=True,
    ).stdout


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".gitkeep").write_text("")
    _git(repo, "add", ".gitkeep")
    _git(repo, "commit", "-m", "Initial commit")


def _head_message(repo: Path) -> str:
    return _git(repo, "log", "-1", "--format=%B")


def _write_json(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _activate_repo(repo: Path) -> None:
    """Write the per-project activation marker, enabled."""
    _write_json(repo / ".nwave" / "local-config.json", '{"enabled_for_repo": true}\n')


def _global_config_enabled(path: Path, enabled: bool) -> None:
    _write_json(path, f'{{"attribution": {{"enabled": {str(enabled).lower()}}}}}\n')


SENTINEL = "Co-Authored-By: nWave <nwave@nwave.ai>"


# ---------------------------------------------------------------------------
# Property 1 -- IDEMPOTENT BY SENTINEL (pure domain function)
# ---------------------------------------------------------------------------


class TestPropertyOneIdempotentBySentinel:
    def test_pure_function_never_doubles_a_model_typed_trailer(self) -> None:
        from des.domain.commit_attribution.attribution_trailer import (
            apply_attribution_trailer,
        )

        message = f"feat: add x\n\n{SENTINEL}"

        result = apply_attribution_trailer(message, enabled=True)

        assert result == message
        assert result.count(SENTINEL) == 1

    def test_pure_function_never_doubles_when_sentinel_straddles_step_id(
        self,
    ) -> None:
        """Reproduces the exact demonstrated failing shape: a naive unconditional
        append on a message that already carried a model-typed trailer produced
        count=2, straddling the Step-Id: trailer."""
        from des.domain.commit_attribution.attribution_trailer import (
            apply_attribution_trailer,
        )

        message = f"subject\n\n{SENTINEL}\n\nStep-Id: 09-09"

        result = apply_attribution_trailer(message, enabled=True)

        assert result == message
        assert result.count(SENTINEL) == 1

    def test_producing_tool_never_doubles_trailer_when_bash_rewriter_already_injected_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The other source of a pre-existing sentinel: the PreToolUse Bash
        rewriter already injected it on a `-m` path before `des commit` ever
        runs -- the producing tool must not add a second one."""
        from des.adapters.driven.config.des_config import DESConfig
        from des.cli.commit import main

        repo = tmp_path / "repo"
        _init_repo(repo)
        _activate_repo(repo)
        global_config = tmp_path / "global-config.json"
        _global_config_enabled(global_config, enabled=True)
        monkeypatch.setattr(DESConfig, "_DEFAULT_GLOBAL_CONFIG_PATH", global_config)

        (repo / "a.py").write_text("x = 1\n")
        already_attributed = f"feat: add a\n\n{SENTINEL}"

        rc = main(
            [
                "--repo-dir",
                str(repo),
                "--owned-paths",
                "a.py",
                "--step-id",
                "01-01",
                "--message",
                already_attributed,
            ]
        )

        assert rc == 0
        body = _head_message(repo)
        assert body.count(SENTINEL) == 1


# ---------------------------------------------------------------------------
# Property 2 -- OFF MEANS OFF
# ---------------------------------------------------------------------------


class TestPropertyTwoOffMeansOff:
    def test_pure_function_off_means_off_byte_identical(self) -> None:
        from des.domain.commit_attribution.attribution_trailer import (
            apply_attribution_trailer,
        )

        message = "feat: add x\n\nStep-Id: 01-01"

        assert apply_attribution_trailer(message, enabled=False) == message

    def test_producing_tool_off_means_off_via_cli(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from des.adapters.driven.config.des_config import DESConfig
        from des.cli.commit import main

        repo = tmp_path / "repo"
        _init_repo(repo)
        _activate_repo(repo)
        global_config = tmp_path / "global-config.json"
        _global_config_enabled(global_config, enabled=False)
        monkeypatch.setattr(DESConfig, "_DEFAULT_GLOBAL_CONFIG_PATH", global_config)

        (repo / "a.py").write_text("x = 1\n")

        rc = main(
            [
                "--repo-dir",
                str(repo),
                "--owned-paths",
                "a.py",
                "--step-id",
                "01-01",
                "--message",
                "feat: add a",
            ]
        )

        assert rc == 0
        body = _head_message(repo)
        assert SENTINEL not in body
        assert body.rstrip("\n") == "feat: add a\n\nStep-Id: 01-01"


# ---------------------------------------------------------------------------
# Property 3 -- NEVER BLOCKS A COMMIT
# ---------------------------------------------------------------------------


class TestPropertyThreeNeverBlocksACommit:
    def test_seam_degrades_to_disabled_on_corrupt_global_config(
        self, tmp_path: Path
    ) -> None:
        from des.application.commit_message_attribution import (
            attribute_commit_message,
        )

        repo = tmp_path / "repo"
        _init_repo(repo)
        _activate_repo(repo)
        corrupt_global_config = tmp_path / "global-config.json"
        corrupt_global_config.write_text("{not valid json", encoding="utf-8")

        message = "feat: add a\n\nStep-Id: 01-01"

        result = attribute_commit_message(
            repo, message, global_config_path=corrupt_global_config
        )

        assert result == message

    def test_producing_tool_commit_still_lands_despite_corrupt_attribution_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Demonstrated failing shape: a transform that raised gave rc=1 with
        HEAD still at the seed commit -- the commit was LOST. The commit must
        proceed regardless."""
        from des.adapters.driven.config.des_config import DESConfig
        from des.cli.commit import main

        repo = tmp_path / "repo"
        _init_repo(repo)
        _activate_repo(repo)
        seed_head = _git(repo, "rev-parse", "HEAD").strip()
        corrupt_global_config = tmp_path / "global-config.json"
        corrupt_global_config.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(
            DESConfig, "_DEFAULT_GLOBAL_CONFIG_PATH", corrupt_global_config
        )

        (repo / "a.py").write_text("x = 1\n")

        rc = main(
            [
                "--repo-dir",
                str(repo),
                "--owned-paths",
                "a.py",
                "--step-id",
                "01-01",
                "--message",
                "feat: add a",
            ]
        )

        assert rc == 0
        new_head = _git(repo, "rev-parse", "HEAD").strip()
        assert new_head != seed_head
        assert SENTINEL not in _head_message(repo)


# ---------------------------------------------------------------------------
# Property 4 -- GATED ON ACTIVATION (ADR-CA-007)
# ---------------------------------------------------------------------------


class TestPropertyFourGatedOnActivation:
    def test_seam_declines_when_repo_has_no_marker_and_mode_is_opt_in(
        self, tmp_path: Path
    ) -> None:
        """Reproduces the exact demonstrated failing shape: NO activation
        marker + global mode opt-in (resolve_activation(None, "opt-in") ==
        False) + attribution.enabled=true -- the trailer must not be applied."""
        from des.application.commit_message_attribution import (
            attribute_commit_message,
        )

        repo = tmp_path / "repo"
        _init_repo(repo)  # no `_activate_repo`: no marker at all
        global_config = tmp_path / "global-config.json"
        _write_json(
            global_config,
            '{"activation": {"mode": "opt-in"}, "attribution": {"enabled": true}}\n',
        )

        message = "feat: add a\n\nStep-Id: 01-01"

        result = attribute_commit_message(
            repo, message, global_config_path=global_config
        )

        assert result == message

    def test_producing_tools_attribute_when_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The named regression test (dispatch DES-LANE-JUSTIFICATION): an
        ACTIVE repo (marker present) with attribution enabled must see the
        trailer on a real `des commit`."""
        from des.adapters.driven.config.des_config import DESConfig
        from des.cli.commit import main

        repo = tmp_path / "repo"
        _init_repo(repo)
        _activate_repo(repo)
        global_config = tmp_path / "global-config.json"
        _global_config_enabled(global_config, enabled=True)
        monkeypatch.setattr(DESConfig, "_DEFAULT_GLOBAL_CONFIG_PATH", global_config)

        (repo / "a.py").write_text("x = 1\n")

        rc = main(
            [
                "--repo-dir",
                str(repo),
                "--owned-paths",
                "a.py",
                "--step-id",
                "01-01",
                "--message",
                "feat: add a",
            ]
        )

        assert rc == 0
        body = _head_message(repo)
        assert body.count(SENTINEL) == 1
        # subject + Step-Id trailer survive byte-for-byte around the addition.
        assert body.startswith("feat: add a\n\nStep-Id: 01-01")


# ---------------------------------------------------------------------------
# Property 5 -- DEFAULT STAYS ENABLED for a configured install; ABSENT config
# resolves to NOT-enabled (the fail-safe on an unconfigured machine).
# ---------------------------------------------------------------------------


class TestPropertyFiveAbsentConfigResolvesNotEnabled:
    def test_seam_absent_global_config_resolves_not_enabled(
        self, tmp_path: Path
    ) -> None:
        from des.application.commit_message_attribution import (
            attribute_commit_message,
        )

        repo = tmp_path / "repo"
        _init_repo(repo)
        _activate_repo(repo)  # active repo, but...
        missing_global_config = tmp_path / "does-not-exist" / "global-config.json"

        message = "feat: add a\n\nStep-Id: 01-01"

        result = attribute_commit_message(
            repo, message, global_config_path=missing_global_config
        )

        assert result == message

    def test_seam_configured_install_true_plus_active_still_attributes(
        self, tmp_path: Path
    ) -> None:
        """A CONFIGURED install (the key explicitly present, per
        attribution_plugin.py's install-time default) in an active repo must
        still attribute -- absence is the only case that fails safe.

        The message's tail already carries a `Step-Id:` trailer preceded by a
        blank line (an established trailer paragraph), so per
        fix-commit-slice-trailer-contiguity the attribution trailer MERGES
        onto it with a single newline rather than opening a new blank-line
        paragraph -- keeping both trailers in ONE contiguous block git's own
        `interpret-trailers --parse` recognises."""
        from des.application.commit_message_attribution import (
            attribute_commit_message,
        )

        repo = tmp_path / "repo"
        _init_repo(repo)
        _activate_repo(repo)
        global_config = tmp_path / "global-config.json"
        _global_config_enabled(global_config, enabled=True)

        message = "feat: add a\n\nStep-Id: 01-01"

        result = attribute_commit_message(
            repo, message, global_config_path=global_config
        )

        assert result == f"{message}\n{SENTINEL}"


# ---------------------------------------------------------------------------
# commit-slice: the trailer must survive `_amend_trailer`'s Gate-Scope
# digest swap EXACTLY ONCE (duplication/loss risk called out by the dispatch).
# ---------------------------------------------------------------------------


class TestCommitSliceAmendPreservesTrailerExactlyOnce:
    def test_trailer_survives_the_gate_scope_amend_exactly_once(
        self, tmp_path: Path
    ) -> None:
        from des.application.commit_message_attribution import (
            attribute_commit_message,
        )
        from des.cli.commit_slice import _amend_trailer, _commit_with_placeholder

        repo = tmp_path / "repo"
        _init_repo(repo)
        _activate_repo(repo)
        global_config = tmp_path / "global-config.json"
        _global_config_enabled(global_config, enabled=True)

        (repo / "b.py").write_text("y = 1\n")
        _git(repo, "add", "b.py")

        # Mirrors main()'s exact call order: attribute BEFORE the placeholder
        # commit, then amend only the Gate-Scope digest afterwards.
        message = attribute_commit_message(
            repo, "feat: add b\n\nSlice-Id: slice-01", global_config_path=global_config
        )
        assert SENTINEL in message  # sanity: the fixture is actually active+on

        _commit_with_placeholder(repo, message, no_verify=True)
        after_placeholder = _head_message(repo)
        assert after_placeholder.count(SENTINEL) == 1
        assert "Gate-Scope:" in after_placeholder

        _amend_trailer(repo, "a" * 64)  # a real digest is 64 hex chars

        after_amend = _head_message(repo)
        assert after_amend.count(SENTINEL) == 1
        assert f"Gate-Scope: {'a' * 64}" in after_amend
        assert "Slice-Id: slice-01" in after_amend
        assert after_amend.startswith("feat: add b")
