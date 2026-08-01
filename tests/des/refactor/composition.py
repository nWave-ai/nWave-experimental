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
from des.domain.refactor.entry_gate import EntryGateVerdict

from .domain_types import EntryGateAgentVerdict


# Repo root -- three-level-up parent of this file
# (tests/des/refactor/composition.py).
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The default paradigm carried by a seeded pile item (slice-05 consumes this
#: field; slice-01 only needs it to round-trip).
_DEFAULT_PARADIGM = "object-oriented"

#: The maintainer's OWN fixer script -- the executable a real operator writes
#: and points ``--agent-cmd`` at (the charter's precondition: "the fixer
#: command as the product's own --help and documentation instruct"). Named as
#: a repo-relative script because that is what an operator naturally writes
#: next to their pile; the placement (inside the repo vs outside it) and the
#: committed-ness are exactly the variables
#: ``test_bug_entry_gate_how_is_actionable.py`` holds under control.
_FIXER_SCRIPT_NAME = "fixer.sh"

#: What the fixer DOES: a real, benign, suite-green-preserving edit to the
#: already-committed toy test (mirrors ``agent_cmd_that_makes_a_benign_real_
#: change``'s inline body, so a script-file fixer and the inline stand-in do
#: the same work). Runs with ``cwd=<worktree>`` -- the path is relative to the
#: worktree, never to the operator's own tree.
_FIXER_WORK_LINE = (
    "printf '\\n# refactored: benign no-behaviour note\\n' >> test_toy.py\n"
)

#: What a fixer that FORGOT the entry-gate verdict prints: free-form
#: commentary carrying no recognized ``EntryGateVerdict`` token anywhere
#: (``classify_entry_gate`` word-boundary-searches the WHOLE output, so this
#: line must stay token-free).
_FIXER_COMMENTARY_LINE = "printf 'looked at the item and applied the fix\\n'\n"


def _fixer_verdict_line() -> str:
    """The line a maintainer appends when following the entry-gate refusal's
    own ``Fix:`` instruction verbatim ("make your own --agent-cmd print exactly
    one of those tokens on its stdout as its last act -- for example
    `your-agent ... && echo REFACTOR_SAFE`"). The token is read off the typed
    enum, never re-typed, so a renamed verdict cannot silently make the
    "operator followed the advice" arrangement stop following it."""
    return f"printf '{EntryGateAgentVerdict.REFACTOR_SAFE.value}\\n'\n"


@dataclass(frozen=True)
class CliResult:
    """Observable result of one ``des refactor`` subprocess invocation."""

    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ScopeReport:
    """Observable outcome of one drain driven with an INJECTED impacted-test
    selector (feature impacted-test-selector-arity-fix, slice-01) -- the
    Mandate-8 port-exposed universe an AT asserts on without ever reading
    ``DrainResult`` internals directly.

    ``selection_reason`` reads ``DrainResult.selection_reason`` DEFENSIVELY
    (``getattr(..., None)``) because that field does not exist on
    ``DrainResult`` yet -- reading it via ``getattr`` turns "the field is
    still missing" into a clean ``AssertionError`` (``None`` compared against
    an expected reason) instead of an ``AttributeError``, so a not-yet-wired
    scenario fails for the RIGHT reason (MISSING_FUNCTIONALITY), never a
    setup/collection error.

    ``drained is False`` with ``refusal_reason`` naming a raised exception is
    how a drain that RAISED (rather than returning a refusal ``DrainResult``)
    is represented here -- "refused loudly" (CT-3) covers both a graceful
    refusal AND an uncaught exception the drain's own cleanup wrapper
    re-raises; this report collapses both into the SAME observable shape so
    an AT does not have to guess which one DELIVER chooses.
    """

    drained: bool
    merged: bool
    test_target_scope: str | None
    selection_reason: str | None
    refusal_reason: str | None


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
        # SIBLING to project_root (mirrors the worktree-placement convention
        # `RefactorDrainService.drain_one` itself uses -- `repo.parent /
        # f"{repo.name}-refactor-{item_id}"`), never INSIDE it: a path
        # inside project_root would show up as untracked content the next
        # time `git status --porcelain` runs there (`GitWorktreeAdapter.
        # _is_dirty`), spuriously tripping the D4 dirty-tree merge refusal
        # for any AT that both captures agent input AND expects the drain
        # to actually merge (fix-slice-05-agent-cmd-observation-marker-
        # pollutes-repo-tree, caught by the slice-05 AT review).
        self._observed_agent_input = (
            project_root.parent / f"{project_root.name}-observed-agent-input.txt"
        )

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

    def seed_disjoint_pile_items(self, item_ids: tuple[str, ...]) -> None:
        """Seed N pending items into a real ``techdebt.md`` -- the slice-02
        DISJOINT-items arrangement (design doc §9): each item is a distinct,
        independently-fixable defect, never sharing a file with a sibling."""
        lines = [
            f"- [ ] {item_id}: paradigm={_DEFAULT_PARADIGM} "
            f'defect="isolated defect for {item_id}" '
            f'proposed_solution="fix {item_id} in its own file"'
            for item_id in item_ids
        ]
        self.pile_path.write_text(
            "# Tech debt pile\n\n" + "\n".join(lines) + "\n", encoding="utf-8"
        )
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

        Emits REFACTOR_SAFE on stdout after the capture so slice-04's entry
        gate permits a proceeding drain -- the capture (a file copy) leaves
        stdout free for the verdict token.
        """
        return f"cp {{prompt}} {self._observed_agent_input} && echo REFACTOR_SAFE"

    def observed_agent_cmd_input(self) -> str:
        """The content the configured ``agent_cmd`` actually received."""
        return self._observed_agent_input.read_text(encoding="utf-8")

    def agent_was_never_invoked(self) -> bool:
        """True iff the configured ``agent_cmd`` never ran -- the observable
        surface for 'refused BEFORE dispatch, never silently guessed'
        (slice-05, D10). Reuses the SAME observation marker
        ``capturing_agent_cmd`` writes to (see ``observed_agent_cmd_input``);
        absence of that file is proof the harness never invoked the agent for
        this item.
        """
        return not self._observed_agent_input.exists()

    # --- Given: misbehaving-agent stand-ins (the harness's own safety nets) -

    def agent_cmd_that_breaks_the_test_suite(self) -> str:
        """A shell command standing in for a MISBEHAVING agent that leaves the
        fast+impacted test subset RED after its own change -- the false-green
        oracle's arrangement (the toy passing test must already exist, see
        ``seed_toy_passing_test``)."""
        return "sh -c \"printf '\\ndef test_broken():\\n    assert False\\n' >> test_toy.py\""

    def agent_cmd_that_breaks_the_test_suite_after_passing_entry_gate(self) -> str:
        """Same misbehaving agent as ``agent_cmd_that_breaks_the_test_suite``,
        but ALSO emits ``REFACTOR_SAFE`` on stdout -- so the drain proceeds
        PAST slice-04's entry gate and actually reaches the tests-red
        green-to-green refusal (``MergeBlockedTestsRed``) rather than being
        refused earlier for an unrecognized entry-gate verdict. The tests-red
        cleanup arrangement (bugfix-drain-cleanup-on-every-exit) needs this
        combined command -- the bare ``agent_cmd_that_breaks_the_test_suite``
        prints nothing on stdout, so it is refused at the entry gate instead."""
        return (
            "sh -c \"printf '\\ndef test_broken():\\n    assert False\\n' "
            ">> test_toy.py && printf 'REFACTOR_SAFE\\n'\""
        )

    def agent_cmd_that_makes_a_benign_real_change(self) -> str:
        """A stand-in for an agent that makes a REAL, suite-green-preserving
        code change (appends a no-behaviour comment to the already-committed
        toy test) -- so a genuine fix commit exists to land on the operator's
        branch, distinguishable from a no-op drain. Requires
        ``seed_toy_passing_test`` first (the file this appends to must be
        tracked so the change produces a real commit).

        Emits REFACTOR_SAFE on stdout so slice-04's entry gate permits the
        merge -- a well-behaved agent self-reports its verdict; the comment
        is appended to a file, so stdout carries only the verdict token."""
        return (
            "sh -c \"printf '\\n# refactored: benign no-behaviour note\\n' "
            ">> test_toy.py && printf 'REFACTOR_SAFE\\n'\""
        )

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

    # --- Given: the maintainer's OWN fixer script (placement x committed) ---

    def install_committed_fixer_script(self, *, emits_verdict: bool) -> str:
        """Write the maintainer's own fixer script INSIDE the repo, make it
        executable, COMMIT it, and return the repo-relative ``--agent-cmd``
        (``./fixer.sh``) the operator types.

        Repo-relative and committed is the shape a maintainer reaches for
        first: a script next to their pile, tracked by their own repo. It is
        also the shape whose behaviour is counter-intuitive -- the drain runs
        it with ``cwd=<an isolated worktree checked out from the last
        commit>``, so ``./fixer.sh`` there resolves to the COMMITTED copy,
        never the one in the operator's working tree.

        Only ``fixer.sh`` is staged (never ``git add -A``): the pile files are
        harness bookkeeping and must stay untracked, exactly as a real
        operator's ``techdebt.md`` does before their first drain.
        """
        script_path = self.project_root / _FIXER_SCRIPT_NAME
        self._write_fixer_script(script_path, emits_verdict=emits_verdict)
        self._git("add", "--", _FIXER_SCRIPT_NAME)
        self._git("commit", "-q", "-m", "chore: add my fixer script")
        return f"./{_FIXER_SCRIPT_NAME}"

    def install_out_of_repo_fixer_script(self, *, emits_verdict: bool) -> str:
        """Write the SAME fixer script OUTSIDE the repo (a sibling of the
        project root, so git never sees it at all), leave it uncommitted --
        there is nothing to commit it to -- and return the ABSOLUTE
        ``--agent-cmd`` the operator types.

        The other placement a maintainer reaches for, and the one that already
        behaves as they expect: an absolute path resolves to the same live file
        from inside any worktree, so an edit takes effect on the very next run.
        """
        script_path = (
            self.project_root.parent / f"{self.project_root.name}-{_FIXER_SCRIPT_NAME}"
        )
        self._write_fixer_script(script_path, emits_verdict=emits_verdict)
        return str(script_path)

    def operator_edits_fixer_to_emit_verdict_without_committing(self) -> None:
        """Append the verdict line to the repo-relative fixer's WORKING-TREE
        copy and leave the change UNCOMMITTED -- the maintainer following the
        entry-gate refusal's own ``Fix:`` instruction verbatim, with nothing in
        that instruction telling them a commit is involved."""
        script_path = self.project_root / _FIXER_SCRIPT_NAME
        script_path.write_text(
            script_path.read_text(encoding="utf-8") + _fixer_verdict_line(),
            encoding="utf-8",
        )

    def committed_fixer_script_text(self) -> str:
        """The fixer script content git has COMMITTED -- i.e. the copy that
        actually lands in an isolated worktree cut from the last commit.
        Arrangement-integrity witness: proves the working-tree edit really is
        invisible to the drain, rather than the test asserting it on faith."""
        return self._git("show", f"HEAD:{_FIXER_SCRIPT_NAME}")

    def fixer_script_change_is_uncommitted(self) -> bool:
        """True iff the repo-relative fixer script has an uncommitted
        working-tree change -- the second half of the arrangement-integrity
        witness above (port-exposed: real ``git status`` output)."""
        return bool(
            self._git("status", "--porcelain", "--", _FIXER_SCRIPT_NAME).strip()
        )

    def _write_fixer_script(self, path: Path, *, emits_verdict: bool) -> None:
        """Write an executable ``/bin/sh`` fixer that does real work and either
        emits the entry-gate verdict or (``emits_verdict=False``) prints only
        free-form commentary -- the default state of any project's first
        hand-written fixer."""
        body = "#!/bin/sh\n" + _FIXER_WORK_LINE + _FIXER_COMMENTARY_LINE
        if emits_verdict:
            body += _fixer_verdict_line()
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    # --- Given: entry-gate verdict stand-ins (slice-04, AT-7/AT-8) ---------

    def agent_cmd_emitting_verdict(self, verdict: EntryGateAgentVerdict) -> str:
        """A shell command standing in for an agent that emits ``verdict``
        as the ONLY line on stdout -- the entry-gate Given-arrangement
        (feature-delta D9, AT-7/AT-8). ``AgentInvocationResult.stdout`` is
        the seam slice-04 wires into ``classify_entry_gate``."""
        return f"sh -c \"printf '{verdict.value}\\n'\""

    def agent_cmd_emitting_no_recognized_verdict(self) -> str:
        """A shell command standing in for an agent whose stdout carries
        free-form commentary but NO recognized entry-gate verdict token
        (AT-7) -- the ``EntryGateVerdictMissing`` Given-arrangement."""
        return "sh -c \"printf 'Investigated the item, looks fine to me.\\n'\""

    # --- Given/When: what the fixer is ACTUALLY ASKED (fix-fixer-emits-entry-
    # --- gate-verdict) ------------------------------------------------------

    def run_drain_capturing_delivered_prompt(self) -> str:
        """Drive a REAL drain whose ``agent_cmd`` copies the rendered prompt
        FILE aside, and return the exact text the fixer received.

        This is the real artefact the fixer reads (the file
        ``RefactorDrainService._dispatch_agent`` renders into the worktree and
        hands to ``agent_cmd``), never a harness constant -- so an assertion
        on it is an assertion on what a real fixer would actually be asked.
        """
        self.run_drain_one_item(agent_cmd=self.capturing_agent_cmd())
        return self.observed_agent_cmd_input()

    # --- Given/When: the REAL actuator boundary (scripts/refactor_agent.py) --

    def stub_fixer_cli_that_prints(self, output: str) -> Path:
        """Create an executable stand-in for the headless assistant CLI the
        actuator drives (``NWAVE_REFACTOR_AGENT_CLI``).

        It records the argv it received (so the AT can assert on the text the
        actuator actually delivered to the fixer) and writes ``output`` to its
        OWN stdout -- the fd the actuator inherits. No ``claude`` on PATH is
        needed, and no network call is made.
        """
        stub = self.project_root.parent / f"{self.project_root.name}-stub-fixer-cli"
        stub.write_text(
            f"#!{sys.executable}\n"
            "import pathlib\n"
            "import sys\n"
            f'pathlib.Path({str(self._observed_cli_argv)!r}).write_text("\\n".join(sys.argv[1:]), '
            'encoding="utf-8")\n'
            f"sys.stdout.write({output!r})\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        return stub

    @property
    def _observed_cli_argv(self) -> Path:
        return self.project_root.parent / f"{self.project_root.name}-stub-cli-argv.txt"

    def text_the_headless_cli_received(self) -> str:
        """Every argv token the stub CLI was handed, joined -- the observable
        surface for 'the ask survives the actuator's own crafter framing'."""
        return self._observed_cli_argv.read_text(encoding="utf-8")

    def run_refactor_actuator(self, *, prompt_text: str, cli: Path) -> CliResult:
        """Run the REAL ``scripts/refactor_agent.py`` actuator against a stub
        headless CLI, capturing the actuator's own stdout/stderr.

        This is the boundary NO test covered: the actuator's ``subprocess.run``
        deliberately carries no ``capture_output``, so the fixer's stdout is
        INHERITED straight through to whoever invoked the actuator (the
        harness's ``AgentInvocationPort``). Capturing here pins that transport:
        a future ``capture_output=True`` would silently swallow the verdict.

        ``NWAVE_CRAFTER_SPEC`` points at a stub spec so the actuator's
        crafter-spec lookup never depends on the host's ``~/.claude`` install.
        """
        prompt_file = (
            self.project_root.parent / f"{self.project_root.name}-actuator-prompt.md"
        )
        prompt_file.write_text(prompt_text, encoding="utf-8")
        spec = self.project_root.parent / f"{self.project_root.name}-stub-crafter.md"
        spec.write_text(
            "# Stub crafter spec\n\nStand-in for the paradigm-selected "
            "crafter specification.\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["NWAVE_REFACTOR_AGENT_CLI"] = str(cli)
        env["NWAVE_CRAFTER_SPEC"] = str(spec)
        proc = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "refactor_agent.py"),
                str(prompt_file),
                str(self.project_root),
            ],
            cwd=self.project_root,
            env=env,
            capture_output=True,
            text=True,
        )
        return CliResult(proc.returncode, proc.stdout, proc.stderr)

    def techdebt_item_annotated_escalated(self, item_id: str) -> bool:
        """Whether ``item_id`` is STILL present in ``techdebt.md`` AND its
        own line carries an ``escalated`` annotation -- the Mikado-escalation
        observable (AT-8): NOT merged, NOT moved to ``paidtechdebt.md``, but
        flagged in place for human follow-up. Port-exposed (file content),
        never an internal struct field (Mandate 8 universe)."""
        if not self.pile_path.exists():
            return False
        for line in self.pile_path.read_text(encoding="utf-8").splitlines():
            if item_id in line:
                return "escalated" in line.lower()
        return False

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

    def run_drain_one_item(
        self, agent_cmd: str = "sh -c \"printf 'REFACTOR_SAFE\\n'\""
    ) -> object:
        """Layer 3 composition: drive ``RefactorDrainService.drain_one`` in-process."""
        return self.drain_service().drain_one(
            repo=self.project_root,
            pile_path=self.pile_path,
            paid_path=self.paid_path,
            agent_cmd=agent_cmd,
            integration_branch=self.integration_branch,
        )

    # --- Given/When: impacted-test-selector-arity-fix slice-01 --------------
    # -- INJECTED selector treatment: "what does the drain DO with a given --
    # -- answer" (WS Strategy dual-treatment rule) ----------------------------

    def drain_service_with_selector(self, selector) -> RefactorDrainService:
        """Composition root wiring the REAL ``GitWorktreeAdapter``/agent/env
        adapters (unchanged from ``drain_service()``) but an INJECTED
        ``ImpactedTestSelectorPort`` -- the seam a configured
        ``SelectorAnsweringOutcome`` (``.doubles``) is wired through so an AT
        can arrange 'the selector answered X' without depending on what the
        real heuristic happens to compute for a given tiny hermetic repo."""
        return RefactorDrainService(
            git_worktree=GitWorktreeAdapter(),
            agent_invocation=ShellAgentInvocationAdapter(),
            env_provision=UvEnvProvisionAdapter(),
            impacted_test_selector=selector,
            ledger=AtCompletionLedger(self.feature_id, self.project_root),
        )

    def observe_reported_scope(
        self, *, selector, agent_cmd: str | None = None
    ) -> ScopeReport:
        """Layer 3 composition: drive ``RefactorDrainService.drain_one``
        in-process with ``selector`` injected, and reduce the outcome to a
        ``ScopeReport`` -- whether ``drain_one`` returned a refusal
        ``DrainResult`` or RAISED (both are "refused loudly", CT-3's
        arrangement; see ``ScopeReport``'s own docstring)."""
        service = self.drain_service_with_selector(selector)
        try:
            result = service.drain_one(
                repo=self.project_root,
                pile_path=self.pile_path,
                paid_path=self.paid_path,
                agent_cmd=agent_cmd or self.agent_cmd_that_makes_a_benign_real_change(),
                integration_branch=self.integration_branch,
            )
        except Exception as exc:
            return ScopeReport(
                drained=False,
                merged=False,
                test_target_scope=None,
                selection_reason=None,
                refusal_reason=f"raised: {exc}",
            )
        return ScopeReport(
            drained=result.drained,
            merged=result.merged,
            test_target_scope=result.test_target_scope,
            selection_reason=getattr(result, "selection_reason", None),
            refusal_reason=result.refusal_reason,
        )

    def drain_service_for_batch_with_selector(
        self,
        *,
        selector,
        merge_lock,
        env_provision,
        barrier_parties: int,
    ) -> RefactorDrainService:
        """The slice-02 batch composition shape (``drain_service_for_batch``),
        with the impacted-test selector ALSO injected -- so scenario 5's
        batch leg can arrange the same configured answer the single-item leg
        arranges via ``drain_service_with_selector``."""
        from .doubles import BarrierGatedAgentInvocationPort

        return RefactorDrainService(
            git_worktree=GitWorktreeAdapter(),
            agent_invocation=BarrierGatedAgentInvocationPort(
                delegate=ShellAgentInvocationAdapter(), parties=barrier_parties
            ),
            env_provision=env_provision,
            impacted_test_selector=selector,
            ledger=AtCompletionLedger(self.feature_id, self.project_root),
        )

    def observe_reported_scope_for_batch(
        self, *, selector, item_ids: tuple[str, ...] = ("TD-001", "TD-002")
    ) -> tuple[ScopeReport, ...]:
        """Layer 3 composition: drive ``RefactorDrainService.drain_batch``
        in-process with ``selector`` injected for every lane, reduced to one
        ``ScopeReport`` per seeded item (conservation: exactly ``len(item_ids)``
        reports, success or refusal alike -- the SAME conservation contract
        ``BatchDrainResult.results`` already carries)."""
        from .doubles import FakeEnvProvisionPort, RecordingMergeLock

        merge_lock = RecordingMergeLock()
        env_provision = FakeEnvProvisionPort()
        service = self.drain_service_for_batch_with_selector(
            selector=selector,
            merge_lock=merge_lock,
            env_provision=env_provision,
            barrier_parties=len(item_ids),
        )
        batch_result = service.drain_batch(
            repo=self.project_root,
            pile_path=self.pile_path,
            paid_path=self.paid_path,
            agent_cmd=self.agent_cmd_that_fixes_the_items_own_file(),
            integration_branch=self.integration_branch,
            max_parallel=len(item_ids),
            merge_lock=merge_lock,
        )
        return tuple(
            ScopeReport(
                drained=result.drained,
                merged=result.merged,
                test_target_scope=result.test_target_scope,
                selection_reason=getattr(result, "selection_reason", None),
                refusal_reason=result.refusal_reason,
            )
            for result in batch_result.results
        )

    # --- Given/When: bugfix-drain-cleanup-on-every-exit mid-drain crash -----

    def drain_service_with_exploding_env_provision(self) -> RefactorDrainService:
        """Composition root wiring a REAL ``GitWorktreeAdapter`` (the
        worktree/branch survival claim needs a real git tree to mean
        anything) but a FAKE ``EnvProvisionPort`` whose ``.provision(...)``
        raises AFTER the item's worktree already exists -- proves the
        try/except-cleanup window between worktree creation and the eventual
        cleanup/return actually fires on a genuine mid-lifecycle crash
        (bugfix-drain-cleanup-on-every-exit scope point 2), not merely on a
        refusal branch."""
        from .doubles import ExplodingEnvProvisionPort

        return RefactorDrainService(
            git_worktree=GitWorktreeAdapter(),
            agent_invocation=ShellAgentInvocationAdapter(),
            env_provision=ExplodingEnvProvisionPort(),
            impacted_test_selector=HeuristicImpactedTestSelectorAdapter(),
            ledger=AtCompletionLedger(self.feature_id, self.project_root),
        )

    def run_drain_one_item_with_exploding_provision(
        self, agent_cmd: str = "sh -c \"printf 'REFACTOR_SAFE\\n'\""
    ) -> object:
        """Layer 3 composition: drive ``RefactorDrainService.drain_one``
        in-process with a mid-drain-crashing env-provisioning port. The
        exception propagates uncaught (that IS the bug under test) -- the
        caller wraps this in ``pytest.raises`` and then inspects
        git-observable state, never a returned ``DrainResult``."""
        return self.drain_service_with_exploding_env_provision().drain_one(
            repo=self.project_root,
            pile_path=self.pile_path,
            paid_path=self.paid_path,
            agent_cmd=agent_cmd,
            integration_branch=self.integration_branch,
        )

    # --- Given/When: slice-02 concurrent-drain doubles + driving surface ----

    def agent_cmd_that_fixes_the_items_own_file(self) -> str:
        """A shell command standing in for a well-behaved agent: reads the
        item id out of the rendered prompt FILE it was handed (never a
        harness internal -- the prompt content IS the item's own identity,
        per D6/D7) and creates a file scoped to THAT item only. Two
        concurrently-drained items therefore produce genuinely DISJOINT
        diffs without the harness ever passing an item id on the command
        line -- the same ``agent_cmd`` template runs unmodified for every
        item, exactly as D6 (one shared shell-command knob) requires.

        Emits REFACTOR_SAFE on stdout so slice-04's entry gate permits the
        merge: the file-fix output is redirected to a file, so stdout carries
        only the verdict token the gate classifies."""
        return (
            'sh -c \'ITEM=$(grep -oE "TD-[0-9]+" {prompt} | head -1); '
            "echo fixed >> fixed-$ITEM.txt && git add fixed-$ITEM.txt "
            "&& echo REFACTOR_SAFE'"
        )

    def drain_service_for_batch(
        self,
        *,
        merge_lock,
        env_provision,
        barrier_parties: int,
    ) -> RefactorDrainService:
        """The slice-02 composition root: REAL ``GitWorktreeAdapter`` (the
        worktree/venv isolation claim needs a real git tree to mean
        anything) + a REAL ``ShellAgentInvocationAdapter`` wrapped in the
        barrier-gated double (deterministic reasoning-lane-concurrency
        proof) + the injected fake env-provisioning + merge-lock doubles
        (deterministic serialization proof, Architecture of Reference:
        driven-external ports default to a fake with output capture)."""
        from .doubles import BarrierGatedAgentInvocationPort

        return RefactorDrainService(
            git_worktree=GitWorktreeAdapter(),
            agent_invocation=BarrierGatedAgentInvocationPort(
                delegate=ShellAgentInvocationAdapter(), parties=barrier_parties
            ),
            env_provision=env_provision,
            impacted_test_selector=HeuristicImpactedTestSelectorAdapter(),
            ledger=AtCompletionLedger(self.feature_id, self.project_root),
        )

    def run_drain_batch(
        self,
        *,
        merge_lock,
        env_provision,
        item_count: int,
        max_parallel: int | None = None,
        agent_cmd: str | None = None,
    ) -> object:
        """Layer 3 composition: drive ``RefactorDrainService.drain_batch``
        in-process -- the slice-02 driving surface every non-walking-skeleton
        AT in this file uses (slice-02 has no NEW walking-skeleton of its
        own; the feature's single WS is slice-01's, per the one-per-FEATURE
        rule)."""
        service = self.drain_service_for_batch(
            merge_lock=merge_lock,
            env_provision=env_provision,
            barrier_parties=item_count,
        )
        return service.drain_batch(
            repo=self.project_root,
            pile_path=self.pile_path,
            paid_path=self.paid_path,
            agent_cmd=agent_cmd or self.agent_cmd_that_fixes_the_items_own_file(),
            integration_branch=self.integration_branch,
            max_parallel=max_parallel or item_count,
            merge_lock=merge_lock,
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

    def call_refactor_main_in_process_without_agent_cmd(self) -> int:
        """Layer 2 in-process: call the REAL ``des refactor`` CLI entry with NO
        ``--agent-cmd`` token at all -- the DEFAULT-actuator surface
        (bugfix-refusal-names-none). ``main`` then resolves nWave's own
        installed actuator and dispatches THAT, so every refusal the run
        renders is about a command the SYSTEM chose rather than one the
        operator typed. Mirrors ``call_refactor_main_in_process`` exactly, only
        omitting the ``--agent-cmd`` argv pair -- the one variable under test.
        """
        from des.cli.refactor import main as refactor_main

        previous_cwd = Path.cwd()
        os.chdir(self.project_root)
        try:
            return refactor_main(["--pile", str(self.pile_path)])
        finally:
            os.chdir(previous_cwd)

    def env_making_the_default_actuator_emit_no_verdict(self) -> dict[str, str]:
        """Environment that lets the SYSTEM-RESOLVED actuator
        (``scripts/refactor_agent.py``, what ``des refactor`` runs when no
        ``--agent-cmd`` is given) run hermetically and finish WITHOUT emitting
        any recognized entry-gate verdict -- the ``EntryGateVerdictMissing``
        Given-arrangement for the default path.

        Both variables are the actuator's OWN documented tuning knobs, so this
        drives the real actuator rather than standing in for it: the headless
        assistant it dispatches becomes a stub that prints free-form commentary
        (no ``EntryGateVerdict`` token anywhere, so ``classify_entry_gate``
        finds nothing), and the crafter-spec lookup is pinned to a stub file so
        the arrangement never depends on the host's ``~/.claude`` install. No
        network call is made and no real assistant is invoked.
        """
        cli = self.stub_fixer_cli_that_prints(
            "looked at the item and applied the fix\n"
        )
        spec = self.project_root.parent / f"{self.project_root.name}-stub-crafter.md"
        spec.write_text(
            "# Stub crafter spec\n\nStand-in for the paradigm-selected "
            "crafter specification.\n",
            encoding="utf-8",
        )
        return {
            "NWAVE_REFACTOR_AGENT_CLI": str(cli),
            "NWAVE_CRAFTER_SPEC": str(spec),
        }

    def call_refactor_main_in_process_with_max_parallel(
        self, *, max_parallel: int, agent_cmd: str
    ) -> int:
        """Layer 2 in-process: call the REAL ``des refactor`` CLI entry with
        ``--max-parallel`` > 1 -- the CLI-to-``drain_batch`` wiring surface
        (bugfix-refactor-cli-max-parallel-unwired). Mirrors
        ``call_refactor_main_in_process`` exactly, only adding the
        ``--max-parallel`` argv token."""
        from des.cli.refactor import main as refactor_main

        previous_cwd = Path.cwd()
        os.chdir(self.project_root)
        try:
            return refactor_main(
                [
                    "--pile",
                    str(self.pile_path),
                    "--agent-cmd",
                    agent_cmd,
                    "--max-parallel",
                    str(max_parallel),
                ]
            )
        finally:
            os.chdir(previous_cwd)

    def call_refactor_main_in_process_with_pile(
        self, *, pile_path: Path, agent_cmd: str = "true"
    ) -> int:
        """Layer 2 in-process: call the REAL ``des refactor`` CLI entry against
        an EXPLICIT ``--pile`` path -- the operator-typo surface
        (fix-drain-single-item-silent-noop): a pile path that does not exist,
        that sits under a directory which does not exist, or that names a
        directory rather than a file. Mirrors ``call_refactor_main_in_process``
        exactly, only swapping ``self.pile_path`` for the caller's path, so the
        unreadable-pile and genuinely-empty-pile outcomes are produced by the
        very same driving surface and can be compared against each other."""
        from des.cli.refactor import main as refactor_main

        previous_cwd = Path.cwd()
        os.chdir(self.project_root)
        try:
            return refactor_main(["--pile", str(pile_path), "--agent-cmd", agent_cmd])
        finally:
            os.chdir(previous_cwd)

    def call_refactor_main_in_process_with_driver(
        self, *, driver: str, agent_cmd: str
    ) -> int:
        """Layer 2 in-process: call the REAL ``des refactor`` CLI entry with an
        explicit ``--driver`` value -- the CLI-to-driver wiring surface
        (bugfix-refactor-driver-loop-dead-code). Mirrors
        ``call_refactor_main_in_process_with_max_parallel`` exactly, only
        swapping the ``--max-parallel`` argv token for ``--driver``."""
        from des.cli.refactor import main as refactor_main

        previous_cwd = Path.cwd()
        os.chdir(self.project_root)
        try:
            return refactor_main(
                [
                    "--pile",
                    str(self.pile_path),
                    "--agent-cmd",
                    agent_cmd,
                    "--driver",
                    driver,
                ]
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

    def operator_branch(self) -> str:
        """The operator's currently checked-out branch -- where a maintainer's
        own ``git log`` looks and where a landed fix must become reachable."""
        return self._git("branch", "--show-current").strip()

    def operator_branch_tracked_paths(self) -> set[str]:
        """Every path git tracks at the operator branch's tip -- the observable
        surface for '.venv never committed' once the fix is landed onto the
        operator's own branch (the integration branch is landed-then-removed,
        so the committed content is read HERE, not on a surviving integration
        branch)."""
        output = self._git("ls-tree", "-r", "--name-only", self.operator_branch())
        return {line.strip() for line in output.splitlines() if line.strip()}

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


def explanation_beside_token(text: str, token: str) -> str:
    """The explanatory prose accompanying ``token`` in ``text``.

    Every line that mentions ``token``, with the token itself stripped out and
    the remainder joined -- so an AT can distinguish a prompt that merely
    LISTS the five entry-gate tokens from one that tells the fixer what each
    one MEANS. Longer-token-first removal keeps a substring token
    (``REFACTOR_SAFE``) from being counted as explanation for a
    longer sibling that contains it.
    """
    lines = [line for line in text.splitlines() if token in line]
    stripped = []
    for line in lines:
        remainder = line
        for other in sorted(_ALL_VERDICT_TOKENS, key=len, reverse=True):
            remainder = remainder.replace(other, " ")
        stripped.append(remainder.strip(" \t-*:.|`"))
    return " ".join(part for part in stripped if part).strip()


#: Every entry-gate token spelling, read from the PRODUCTION enum -- a token
#: added to the production closed set is automatically in scope for the
#: explanation check above, never silently exempt.
_ALL_VERDICT_TOKENS = tuple(verdict.value for verdict in EntryGateVerdict)
