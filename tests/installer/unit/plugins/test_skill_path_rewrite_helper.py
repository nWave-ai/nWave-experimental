"""AC-6 acceptance test -- rewrite_host_paths helper unit contract.

Feature: installer-per-host-skill-path-portability.

The shared pure-function helper scripts.shared.skill_path_rewrite:

  rewrite_host_paths(body: str, host: str) -> str

Contract:
  (a) host="claude_code" returns input unchanged (no-op canonical host);
  (b) content with no ~/.claude/ refs returns unchanged;
  (c) applying twice equals applying once (idempotent fixpoint);
  (d) opencode preserves the ~/.claude/lib/python exception;
  (e) the function performs no IO (pure);
  (f) refinement -- codex has an EMPTY exception set: a ~/.claude/lib/python-like
      token is governed only by whether a CODEX rule matches it (no codex
      exception guard). Codex rules target skills/agents/hooks/nWave, NOT lib/,
      so a lib/python token is untouched by absence-of-rule, not by exception.

ACTIVE-RED (atdd_pure): the helper module does NOT exist yet, so importing it
raises ModuleNotFoundError (an ImportError subclass) at collection time ->
right-reason RED.
"""

# Right-reason RED anchor: helper not yet created -> ModuleNotFoundError here.
from scripts.shared.skill_path_rewrite import rewrite_host_paths


class TestRewriteHostPathsHelperContract:
    """Pure-function contract for the shared per-host rewrite helper."""

    def test_claude_code_host_is_noop(self):
        """
        GIVEN: A body with ~/.claude/skills/ references
        WHEN: rewrite_host_paths(body, "claude_code")
        THEN: The body is returned unchanged (canonical no-op host).

        CONTRACT_SHAPE: pure-function
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        body = "see `~/.claude/skills/nw-foo/SKILL.md`\n"
        assert rewrite_host_paths(body, "claude_code") == body

    def test_no_refs_returns_unchanged(self):
        """
        GIVEN: A body with no ~/.claude/ references
        WHEN: rewrite_host_paths(body, "opencode")
        THEN: The body is returned unchanged (no match -> no-op).

        CONTRACT_SHAPE: pure-function
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        body = "nothing to rewrite here\n"
        assert rewrite_host_paths(body, "opencode") == body

    def test_idempotent_fixpoint_opencode(self):
        """
        GIVEN: A body with ~/.claude/skills/ references
        WHEN: rewrite_host_paths is applied twice for opencode
        THEN: Applying twice equals applying once (already-at-base untouched).

        CONTRACT_SHAPE: pure-function
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        body = "load `~/.claude/skills/nw-foo/SKILL.md`\n"
        once = rewrite_host_paths(body, "opencode")
        twice = rewrite_host_paths(once, "opencode")
        assert once == twice
        assert "~/.config/opencode/skills/" in once
        assert "~/.claude/skills/" not in once

    def test_idempotent_fixpoint_codex(self):
        """
        GIVEN: A body with ~/.claude/skills/ references
        WHEN: rewrite_host_paths is applied twice for codex
        THEN: Applying twice equals applying once; result uses ~/.agents/skills/.

        CONTRACT_SHAPE: pure-function
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        body = "load `~/.claude/skills/nw-foo/SKILL.md`\n"
        once = rewrite_host_paths(body, "codex")
        twice = rewrite_host_paths(once, "codex")
        assert once == twice
        assert "~/.agents/skills/" in once
        assert "~/.claude/skills/" not in once

    def test_opencode_preserves_lib_python_exception(self):
        """
        GIVEN: A body referencing ~/.claude/lib/python
        WHEN: rewrite_host_paths(body, "opencode")
        THEN: The ~/.claude/lib/python exception is NOT rewritten.

        CONTRACT_SHAPE: pure-function
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        body = "DES at `~/.claude/lib/python` and `~/.claude/skills/nw-foo/`\n"
        out = rewrite_host_paths(body, "opencode")
        assert "~/.claude/lib/python" in out, "exception must be preserved"
        assert "~/.config/opencode/skills/nw-foo/" in out
        assert "~/.claude/skills/" not in out

    def test_codex_has_empty_exception_set(self):
        """
        GIVEN: A body with a ~/.claude/lib/python-like token under codex
        WHEN: rewrite_host_paths(body, "codex")
        THEN: lib/python is untouched because NO codex rule targets lib/ (not
              because of an exception guard) -- codex exception set is empty.
              A codex skills token IS rewritten in the same body, proving rules
              fire and only the unmatched lib/ token is left alone.

        CONTRACT_SHAPE: pure-function
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        body = "DES at `~/.claude/lib/python` and `~/.claude/skills/nw-foo/`\n"
        out = rewrite_host_paths(body, "codex")
        assert "~/.claude/lib/python" in out, (
            "codex leaves lib/python because no codex rule matches it"
        )
        assert "~/.agents/skills/nw-foo/" in out, (
            "codex skills token must be rewritten (rules do fire)"
        )

    def test_helper_performs_no_io(self, tmp_path, monkeypatch):
        """
        GIVEN: The rewrite_host_paths helper
        WHEN: It is invoked
        THEN: It performs no filesystem IO (pure function) -- open() raising
              would surface any disk access.

        CONTRACT_SHAPE: pure-function
        Outcome anchor: design.md value (DISCUSS wave skipped — optional)
        """
        import builtins

        original_open = builtins.open

        def _no_io_open(*args, **kwargs):
            raise AssertionError("rewrite_host_paths must perform no IO (pure)")

        monkeypatch.setattr(builtins, "open", _no_io_open)
        body = "load `~/.claude/skills/nw-foo/SKILL.md`\n"
        # No exception from _no_io_open => no IO performed.
        result = rewrite_host_paths(body, "opencode")
        assert "~/.config/opencode/skills/" in result
        monkeypatch.setattr(builtins, "open", original_open)
