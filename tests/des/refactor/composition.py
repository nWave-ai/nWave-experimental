"""Composition root -- des-refactor-fixer-swarm slice-01 acceptance set.

Business logic (build a hermetic git repo, seed pile items, drive the real
drain surfaces, read back observable state) lives here as the single source of
truth (Mandate 12, Pillar 3); test bodies delegate to
``RefactorSwarmComposition`` methods and never inline logic.

Two driving surfaces (Mandate 13's 6-level composition, `nw-test-design-
mandates-composition-contract`):

* **Layer 1 subprocess (`run_refactor_cli_subprocess`)** -- the ONE
  ``@walking_skeleton`` per command: forks ``python -m des.cli.__main__
  refactor ...``, the REAL installed entry, proving the terminal-wiring facet.
* **Layer 3 composition (`run_drain_one_item`)** -- the L2 in-process default
  for every other slice-01 AT: drives ``RefactorDrainService.drain_one``
  directly with the REAL production adapters wired in (Pillar 3), never a
  re-forked interpreter.

RED-scaffold note: ``RefactorDrainService``, the four driven adapters, the pile
domain module, the green-to-green domain module, and ``des.cli.refactor`` are
ALL CREATE_NEW (feature-delta Reuse Analysis) -- every one raises
``AssertionError("RED scaffold: ...")`` the instant its method is called
(Mandate 7). Every AT in this directory therefore currently fails at that
first productive call -- MISSING_FUNCTIONALITY, the correct RED classification
for a not-yet-implemented CREATE_NEW vertical slice.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.adapters.driven.refactor.shell_agent_invocation_adapter import (
    ShellAgentInvocationAdapter,
)
from des.adapters.driven.refactor.tsunami_impacted_test_selector_adapter import (
    HeuristicImpactedTestSelectorAdapter,
)
from des.adapters.driven.refactor.uv_env_provision_adapter import (
    UvEnvProvisionAdapter,
)
from des.application.refactor_drain_service import RefactorDrainService


# Repo root -- three-level-up parent of this file
# (tests/des/refactor/composition.py).
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The default paradigm carried by a seeded pile item (slice-05 consumes this
#: field; slice-01 only needs it to round-trip).
_DEFAULT_PARADIGM = "object-oriented"


@dataclass(frozen=True)
class CliResult:
    """Observable result of one ``des refactor`` subprocess invocation."""

    exit_code: int
    stdout: str
    stderr: str


class RefactorSwarmComposition:
    """Production-wired composition root for the slice-01 acceptance set.

    Builds a hermetic real git repo (``tmp_path``) with a real ``techdebt.md``
    / ``paidtechdebt.md`` pile, then drives ``des refactor`` either via the
    real subprocess CLI (walking-skeleton) or via the in-process
    ``RefactorDrainService`` composition root (every other AT).
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.feature_id = "des-refactor-fixer-swarm"
        self.pile_path = project_root / "techdebt.md"
        self.paid_path = project_root / "paidtechdebt.md"
        self.integration_branch = "refactor-integration"
        self._observed_agent_input = project_root / "observed_agent_input.txt"

    # --- Given: hermetic real git repo ---------------------------------------

    def init_git_repo(self) -> None:
        """Initialise a real local git repo with one base commit."""
        self._git("init", "-q")
        self._git("config", "user.email", "fixture@nwave.test")
        self._git("config", "user.name", "Fixture")
        (self.project_root / "README.md").write_text("seed\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "chore: base commit")

    def repo_head_sha(self) -> str:
        """The repo's current HEAD sha (trimmed)."""
        return self._git("rev-parse", "HEAD").strip()

    def advance_head_with_unrelated_commit(self) -> str:
        """Advance HEAD with an unrelated commit -- simulates the repo moving
        between session start and drain time (D1's empirical failure mode).
        Returns the NEW (current) HEAD sha.
        """
        (self.project_root / "unrelated.txt").write_text("drift\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "chore: unrelated concurrent commit")
        return self.repo_head_sha()

    def prepare_dirty_integration_branch(self) -> None:
        """Create the integration branch and leave it with uncommitted content
        (D4/D5, the TD-003 spike finding: an operator's own uncommitted WIP
        blocks a non-fast-forward merge)."""
        self._git("branch", self.integration_branch)
        self._git("checkout", self.integration_branch)
        (self.project_root / "wip.txt").write_text(
            "uncommitted operator WIP\n", encoding="utf-8"
        )
        self._git("checkout", "-")

    def prepare_clean_integration_branch(self) -> None:
        """Create the integration branch with no uncommitted content."""
        self._git("branch", self.integration_branch)

    def seed_toy_passing_test(self) -> None:
        """Commit ONE real, fast, passing pytest test -- so a genuine
        green -> red transition is observable (the false-green oracle needs a
        concrete test to break, not a vacuous 0-collected run)."""
        (self.project_root / "test_toy.py").write_text(
            "def test_toy_invariant():\n    assert 1 + 1 == 2\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "chore: seed toy passing test")

    def leave_unrelated_dirty_file_in_parent_tree(self) -> None:
        """An UNTRACKED file in the operator's own working tree, unrelated to
        any pile item -- git worktree's own clean-checkout guarantee (D1)
        means this must never appear inside a created item's own worktree or
        its resulting commit (the cross-contamination / scope-creep oracle)."""
        (self.project_root / "operator_wip_unrelated.txt").write_text(
            "unrelated operator scratch work, never part of any pile item\n",
            encoding="utf-8",
        )

    # --- Given: the pile -------------------------------------------------

    def seed_pile_item(
        self,
        item_id: str = "TD-001",
        paradigm: str = _DEFAULT_PARADIGM,
        defect: str = "duplicate helper across two modules",
        proposed_solution: str = "extract a shared function",
    ) -> None:
        """Seed one pending item into a real ``techdebt.md``."""
        self.pile_path.write_text(
            textwrap.dedent(
                f"""\
                # Tech debt pile

                - [ ] {item_id}: paradigm={paradigm} defect="{defect}" \
proposed_solution="{proposed_solution}"
                """
            ),
            encoding="utf-8",
        )
        if not self.paid_path.exists():
            self.paid_path.write_text("# Paid tech debt\n", encoding="utf-8")

    def seed_empty_pile(self) -> None:
        """Seed a real ``techdebt.md`` with zero pending items."""
        self.pile_path.write_text("# Tech debt pile\n", encoding="utf-8")
        self.paid_path.write_text("# Paid tech debt\n", encoding="utf-8")

    def seed_pile_with_unparseable_line(self, line: str) -> None:
        """Seed a real ``techdebt.md`` whose only content line does NOT match
        the item grammar (``_ITEM_LINE_RE``) -- the 'unparseable pile line'
        observability arrangement: zero items parse, but the file is not
        empty either."""
        self.pile_path.write_text(f"# Tech debt pile\n\n{line}\n", encoding="utf-8")
        self.paid_path.write_text("# Paid tech debt\n", encoding="utf-8")

    def seed_pile_with_valid_item_and_unparseable_line(
        self, item_id: str = "TD-001", bad_line: str = "- [ ] hand-typed, wrong shape"
    ) -> None:
        """Seed a real ``techdebt.md`` carrying ONE grammar-valid item AND one
        line that fails the item grammar -- the 'mixed pile' arrangement
        (fix-refactor-pile-grammar-undocumented): a real item still parses
        and drains, but the malformed sibling line must not be silently
        swallowed just because the pile as a whole was not empty."""
        self.pile_path.write_text(
            textwrap.dedent(
                f"""\
                # Tech debt pile

                - [ ] {item_id}: paradigm={_DEFAULT_PARADIGM} defect="duplicate helper" \
proposed_solution="extract a shared function"
                {bad_line}
                """
            ),
            encoding="utf-8",
        )
        if not self.paid_path.exists():
            self.paid_path.write_text("# Paid tech debt\n", encoding="utf-8")

    # --- Given: the user-editable prompt template -------------------------

    def write_user_prompt_template(self, template_text: str) -> None:
        """Write the user-editable prompt-template file the operator edited.

        Real file on disk at ``.nwave/refactor-agent-prompt.md`` -- the SAME
        default location ``des.domain.refactor.prompt_template.
        DEFAULT_TEMPLATE_PATH`` names.
        """
        template_path = self.prompt_template_path
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(template_text, encoding="utf-8")

    @property
    def prompt_template_path(self) -> Path:
        from des.domain.refactor.prompt_template import DEFAULT_TEMPLATE_PATH

        return self.project_root / DEFAULT_TEMPLATE_PATH

    def capturing_agent_cmd(self) -> str:
        """An ``agent_cmd`` template that COPIES the rendered prompt file's
        content to a well-known, absolute observation path -- so the AT can
        assert on what the agent actually received (a real captured effect,
        never a harness internal). Absolute paths only: the real adapter runs
        this command with ``cwd=<worktree>``, not ``project_root``.
        """
        return f"cp {{prompt}} {self._observed_agent_input}"

    def observed_agent_cmd_input(self) -> str:
        """The content the configured ``agent_cmd`` actually received."""
        return self._observed_agent_input.read_text(encoding="utf-8")

    # --- Given: misbehaving-agent stand-ins (the harness's own safety nets) -

    def agent_cmd_that_breaks_the_test_suite(self) -> str:
        """A shell command standing in for a MISBEHAVING agent that leaves the
        fast+impacted test subset RED after its own change -- the false-green
        oracle's arrangement (the toy passing test must already exist, see
        ``seed_toy_passing_test``)."""
        return "sh -c \"printf '\\ndef test_broken():\\n    assert False\\n' >> test_toy.py\""

    def agent_cmd_that_stages_the_venv_directory(self) -> str:
        """A shell command standing in for a MISBEHAVING agent that
        accidentally ``git add``s its own ``.venv`` -- the exact hygiene
        defect AT-4 exists to catch before the commit ever reaches
        merge-back."""
        return 'sh -c "mkdir -p .venv && echo marker > .venv/marker && git add .venv"'

    def unresolvable_agent_cmd(self) -> str:
        """An ``agent_cmd`` whose executable does not exist on PATH -- the
        probe-contract (AT-12) arrangement: a startup refusal must fire
        BEFORE any worktree is created for the first real item."""
        return "this-executable-does-not-exist-xyz123 {prompt}"

    def prepare_colliding_branch_for_item(self, item_id: str) -> None:
        """Pre-create the branch name `des refactor` will try to create for
        ``item_id`` (``refactor-<item_id>``, see ``RefactorDrainService.
        drain_one``) -- forces the real ``git worktree add -b <branch>``
        call to fail with a genuine, reproducible git error (branch already
        exists). The opaque worktree-creation-failure observability
        arrangement (flag 3): today this failure escapes as a raw, uncaught
        ``subprocess.CalledProcessError``."""
        self._git("branch", f"refactor-{item_id}")

    # --- When: drive the drain loop (Layer 3 composition, L2 default) ------

    def drain_service(self) -> RefactorDrainService:
        """The production composition root, wired with the REAL adapters."""
        return RefactorDrainService(
            git_worktree=GitWorktreeAdapter(),
            agent_invocation=ShellAgentInvocationAdapter(),
            env_provision=UvEnvProvisionAdapter(),
            impacted_test_selector=HeuristicImpactedTestSelectorAdapter(),
            ledger=AtCompletionLedger(self.feature_id, self.project_root),
        )

    def run_drain_one_item(self, agent_cmd: str = "true") -> object:
        """Layer 3 composition: drive ``RefactorDrainService.drain_one`` in-process."""
        return self.drain_service().drain_one(
            repo=self.project_root,
            pile_path=self.pile_path,
            paid_path=self.paid_path,
            agent_cmd=agent_cmd,
            integration_branch=self.integration_branch,
        )

    # --- When: drive the real CLI entry in-process (Layer 2, L2 default) ---

    def call_refactor_main_in_process(self, agent_cmd: str = "true") -> int:
        """Layer 2 in-process: call the REAL ``des refactor`` CLI entry
        (``des.cli.refactor.main``) directly -- no interpreter fork. This is
        the driving surface for the CLI's own self-reporting (stdout/stderr)
        -- the concern the composition-root's Layer 3 ``run_drain_one_item``
        cannot exercise, since output-formatting lives in ``main()``, not in
        ``RefactorDrainService``.

        ``main()`` resolves its repo via ``Path.cwd()``, so this chdirs into
        the hermetic repo for the call's duration and always restores the
        previous cwd, even when the call raises.
        """
        from des.cli.refactor import main as refactor_main

        previous_cwd = Path.cwd()
        os.chdir(self.project_root)
        try:
            return refactor_main(
                ["--pile", str(self.pile_path), "--agent-cmd", agent_cmd]
            )
        finally:
            os.chdir(previous_cwd)

    # --- When: drive the CLI (Layer 1 subprocess, walking-skeleton ONLY) ---

    def run_refactor_cli_subprocess(self, agent_cmd: str = "true") -> CliResult:
        """Layer 1 walking-skeleton: fork the REAL installed `des refactor` CLI."""
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "des.cli.__main__",
                "refactor",
                "--pile",
                str(self.pile_path),
                "--agent-cmd",
                agent_cmd,
            ],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        return CliResult(proc.returncode, proc.stdout, proc.stderr)

    # --- git plumbing --------------------------------------------------------

    def _git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout

    def worktree_list(self) -> str:
        """Real ``git worktree list`` output (D5/D6 cleanup witness)."""
        return self._git("worktree", "list")

    def branch_exists(self, branch: str) -> bool:
        proc = subprocess.run(
            ["git", "branch", "--list", branch],
            cwd=self.project_root,
            capture_output=True,
            text=True,
        )
        return bool(proc.stdout.strip())

    def integration_branch_head_sha(self) -> str:
        """The integration branch's current tip sha (before/after witness for
        the merge-commit scope checks below)."""
        return self._git("rev-parse", self.integration_branch).strip()

    def touched_paths_between(self, sha_before: str, sha_after: str) -> set[str]:
        """The set of file paths that changed between two shas -- the
        observable surface for 'no unrelated work swept into the same
        commit' (cross-contamination oracle)."""
        output = self._git("diff", "--name-only", sha_before, sha_after)
        return {line.strip() for line in output.splitlines() if line.strip()}

    def integration_branch_tracked_paths(self) -> set[str]:
        """Every path git tracks at the integration branch's tip -- the
        observable surface for '.venv never staged in the commit' (AT-4)."""
        output = self._git("ls-tree", "-r", "--name-only", self.integration_branch)
        return {line.strip() for line in output.splitlines() if line.strip()}

    def worktree_path_for_branch(self, branch: str) -> Path | None:
        """The filesystem path of the worktree registered against ``branch``
        (per ``git worktree list --porcelain``), or ``None`` if no such
        worktree is currently registered -- the observable surface for
        per-worktree venv isolation (AT-2)."""
        output = self._git("worktree", "list", "--porcelain")
        current_path: Path | None = None
        for line in output.splitlines():
            if line.startswith("worktree "):
                current_path = Path(line[len("worktree ") :])
            elif line.startswith("branch ") and current_path is not None:
                branch_ref = line[len("branch ") :]
                if branch_ref in (f"refs/heads/{branch}", branch):
                    return current_path
        return None

    # --- pile file observables (port-exposed, Mandate 8 universe) -----------

    def pile_contains(self, item_id: str) -> bool:
        return item_id in self.pile_path.read_text(encoding="utf-8")

    def paid_contains(self, item_id: str) -> bool:
        return item_id in self.paid_path.read_text(encoding="utf-8")

    # --- Universe snapshot (Mandate 8) ---------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed observable names the drain loop affects.

        Port-exposed only: the pile file contents, the git worktree list, and
        HEAD -- no internal struct fields.
        """
        return {
            "pile.techdebt_content": self.pile_path.read_text(encoding="utf-8")
            if self.pile_path.exists()
            else "",
            "pile.paidtechdebt_content": self.paid_path.read_text(encoding="utf-8")
            if self.paid_path.exists()
            else "",
            "git.worktree_list": self.worktree_list(),
            "git.head_sha": self.repo_head_sha(),
        }
