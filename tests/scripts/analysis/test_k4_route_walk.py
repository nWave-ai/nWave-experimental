"""`route_walk` -- the permanent, no-model-call proof that preflight walks
the canonical Auto route through the deterministic layer before any paid K4
run.

Genesis: an offline replay (session 0185uzgcpND7qvXqmyttBUeQ) manually
proved the route end to end -- `des prepare-ordinary-request` (heredoc) ->
`des resolve-charters` -> ATD dispatch envelope -> charter-scaffold ->
DeliveryContract -> `des validate-delivery-contract` -> `des dispatch` ->
crafter dispatch envelope -> crafter's subagent Bash calls -> the subagent
host-scan block -- against a scratch substrate, catching one drift class
(`des resolve-charters` missing from the Auto-root Bash allowlist, fixed in
`fix(auto): allow every des subcommand the root route mandates`). This test
makes that walk a standing gate instead of a one-off manual replay: GDP-1,
intercept before the paid run, not after.

Two tiers:

* `TestRouteWalkStepsClassification` -- `route_walk_steps` is the pure(ish)
  evaluator: it takes injected `hook_run`/`cli_run` callables and never
  touches a subprocess or the filesystem beyond the DeliveryContract/oracle
  files it writes into the given `repo_root`. Fakes drive RED (a mandated
  step observed denied/failing must flip `status` to "blocked" and name
  that step first) and GREEN (every step allowed/passing yields "proven")
  without paying for a real installed hook or venv.
* `TestRouteWalkRealHookCases` -- the two cases the genesis defect actually
  lived in (the seed heredoc, `des resolve-charters`) exercised against the
  REAL installed `pre_tool_use_handler.handle_pre_tool_use()`, in-process,
  the same monkeypatched-stdin pattern
  `test_auto_root_bash_lockdown.py::_run` already uses -- no subprocess, no
  built venv, but genuinely the production hook code, not a fake.
"""

from __future__ import annotations

import inspect
import io
import json
import subprocess
from pathlib import Path

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler
from scripts.analysis.k4 import preflight as k4_preflight


# ---------------------------------------------------------------------------
# Tier 1: pure(ish) step-classification tests, fully faked hook/CLI runners.
# ---------------------------------------------------------------------------


#: Substrings that identify a NEGATIVE-control command -- one route_walk_steps
#: itself expects to be DENIED (the allowlist/host-scan must stay closed).
#: `_faithful_hook` denies exactly these and allows everything else, so a
#: "GREEN, every mandated step behaves as mandated" fixture doesn't have to
#: reimplement the real hook's tokenizer to be faithful to its CONTRACT.
_NEGATIVE_CONTROL_MARKERS = (
    "git log",
    "route-walk-probe-unknown-subcommand",
    "find / ",
)


def _always_allow_hook(_payload: dict) -> tuple[int, str]:
    """No discrimination at all -- used ONLY to simulate the inverse
    regression (a control that should deny silently starting to allow
    everything, host-scan included)."""
    return 0, ""


def _faithful_hook(payload: dict) -> tuple[int, str]:
    """Fake hook_run for the fully-GREEN case: allows every mandated call,
    denies exactly the negative-control shapes `route_walk_steps` itself
    probes (an unrelated git subcommand, an unknown des subcommand, a
    host-wide find) -- mirroring the real hook's CONTRACT, not its
    implementation."""
    blob = json.dumps(payload)
    if any(marker in blob for marker in _NEGATIVE_CONTROL_MARKERS):
        return 2, json.dumps({"decision": "block", "reason": "fake deny"})
    return 0, ""


def _deny_only(
    *, deny_tool_names: set[str] | None = None, deny_names: set[str] | None = None
):
    """Fake hook_run: allow everything except calls whose `tool_input`
    `command` (or subagent_type-bearing prompt) matches a name we're told
    to deny. `deny_names` matches on any substring appearing in the
    JSON-encoded payload, which is enough to target one specific fake case
    without re-implementing the real allowlist/tokenizer here."""

    def _run(payload: dict) -> tuple[int, str]:
        blob = json.dumps(payload)
        names = deny_names or set()
        if any(marker in blob for marker in names):
            return 2, json.dumps({"decision": "block", "reason": "fake deny"})
        return 0, ""

    return _run


_FIXED_SKILL_MD = """
## Root inputs and spatial AB batch

1. Run exactly once, with VALUE-SEED bytes on stdin.

   ```
   des prepare-ordinary-request \\
     --size <M|L> --repo-root <absolute physical root> <<'NW_SEED'
   <exact value-seed text>
   NW_SEED
   ```

2. On `Prepared(SeededAuthority)`, run exactly one command:

   ```
   des resolve-charters --repo-root <root> --delivery-id <producer id> --examine <true|false>
   ```

3. Validate the charter, then run the one `des dispatch` command.
"""


_PRODUCER_STDOUT = (
    "ARCHITECTURE-COVERED: docs/product/architecture/route-walk-probe.md#route-walk-probe\n"
    "\n"
    "CONTRACT-LOCATOR: docs/delivery-contracts/auto-fakefakefakefake.json\n"
    "CONTRACT-SCHEMA: /fake/thin-delivery-contract.schema.json\n"
    "DELIVERY-ID: auto-fakefakefakefake\n"
    'OUTCOME: "fake outcome"\n'
    "ROOT: /fake/repo\n"
    "BASE-REVISION: git-sha1:0000000000000000000000000000000000000000\n"
    "DELIVERY-ROUTE: RED_TO_GREEN\n"
    "EXAMINE: true\n"
    "INDEPENDENT-REVIEW: false\n"
    "BUDGET-TOKEN-LIMIT: 2000000\n"
    "BUDGET-WALL-CLOCK-MINUTES: 30\n"
    'VALUE-SEED: "fake outcome"'
)

_DISPATCH_STDOUT = (
    "THIN-DELIVERY-CONTRACT: docs/delivery-contracts/auto-fakefakefakefake.json\n"
    "THIN-DELIVERY-CONTRACT-DIGEST: sha256:" + "0" * 64
)


def _fake_cli_all_pass(argv: list[str], stdin: str | None = None) -> tuple[int, str]:
    joined = " ".join(argv)
    if "prepare-ordinary-request" in joined:
        return 0, _PRODUCER_STDOUT
    if "charter-scaffold" in joined:
        return 0, json.dumps({"verdict": "accepted"})
    if "validate-delivery-contract" in joined:
        return 0, json.dumps({"verdict": "VALID"})
    if joined.strip() == "des dispatch" or (
        "dispatch" in joined and "validate-delivery-contract" not in joined
    ):
        return 0, _DISPATCH_STDOUT
    raise AssertionError(f"unexpected fake CLI call: {argv!r}")


class TestRouteWalkStepsClassification:
    def test_every_step_allowed_and_passing_yields_proven(self, tmp_path: Path) -> None:
        result = k4_preflight.route_walk_steps(
            repo_root=str(tmp_path),
            hook_run=_faithful_hook,
            cli_run=_fake_cli_all_pass,
            skill_md_text=_FIXED_SKILL_MD,
            transcript_path="/fake/transcript.jsonl",
        )
        assert result["status"] == "proven", result
        assert result["steps"], "a proven walk must still report every step it ran"
        assert all(step["passed"] for step in result["steps"])

    def test_a_mandated_allow_observed_as_deny_blocks_and_names_the_step_first(
        self, tmp_path: Path
    ) -> None:
        """The genesis regression, reproduced with a fake: `des
        resolve-charters` denied instead of allowed must flip the walk to
        `blocked` and name that exact step as the first failure -- never a
        downstream step that merely couldn't proceed because of it."""
        hook_run = _deny_only(deny_names={"resolve-charters"})
        result = k4_preflight.route_walk_steps(
            repo_root=str(tmp_path),
            hook_run=hook_run,
            cli_run=_fake_cli_all_pass,
            skill_md_text=_FIXED_SKILL_MD,
            transcript_path="/fake/transcript.jsonl",
        )
        assert result["status"] == "blocked"
        failing = [step for step in result["steps"] if not step["passed"]]
        assert failing, "a denied mandated step must appear as a failing step"
        assert failing[0]["name"] == "resolve-charters-allow", failing[0]

    def test_a_mandated_deny_observed_as_allow_also_blocks(
        self, tmp_path: Path
    ) -> None:
        """The inverse regression: the subagent host-scan control silently
        starting to ALLOW `find /` is exactly as dangerous as a wrongly
        denied mandated step, and must block the walk too."""
        result = k4_preflight.route_walk_steps(
            repo_root=str(tmp_path),
            hook_run=_always_allow_hook,
            cli_run=_fake_cli_all_pass,
            skill_md_text=_FIXED_SKILL_MD,
            transcript_path="/fake/transcript.jsonl",
        )
        assert result["status"] == "blocked"
        names = {step["name"]: step["passed"] for step in result["steps"]}
        assert names["subagent-find-root-denied"] is False

    def test_a_failing_cli_step_blocks_and_names_itself(self, tmp_path: Path) -> None:
        def _cli_run(argv: list[str], stdin: str | None = None) -> tuple[int, str]:
            if "prepare-ordinary-request" in " ".join(argv):
                return 2, "WHAT: fake stub failure"
            raise AssertionError(
                f"unexpected fake CLI call after the failing step: {argv!r}"
            )

        result = k4_preflight.route_walk_steps(
            repo_root=str(tmp_path),
            hook_run=_faithful_hook,
            cli_run=_cli_run,
            skill_md_text=_FIXED_SKILL_MD,
            transcript_path="/fake/transcript.jsonl",
        )
        assert result["status"] == "blocked"
        by_name = {step["name"]: step for step in result["steps"]}
        assert by_name["cli-prepare-ordinary-request"]["passed"] is False
        # every step whose input the failed producer would have supplied is
        # reported as an explicit failing entry, never silently absent.
        assert by_name["cli-dispatch"]["passed"] is False
        assert by_name["atd-dispatch-envelope-allow"]["passed"] is False
        # every step that depended on the failed producer stdout is reported
        # as blocked too, never silently skipped out of the table.
        assert not all(step["passed"] for step in result["steps"])

    def test_mandate_text_is_never_empty(self, tmp_path: Path) -> None:
        """Every step must cite the SKILL.md/hook line that mandates it --
        an empty mandate would make the eventual WHAT/WHY/HOW un-groundable."""
        result = k4_preflight.route_walk_steps(
            repo_root=str(tmp_path),
            hook_run=_faithful_hook,
            cli_run=_fake_cli_all_pass,
            skill_md_text=_FIXED_SKILL_MD,
            transcript_path="/fake/transcript.jsonl",
        )
        assert all(step["mandate"].strip() for step in result["steps"])

    def test_result_is_json_serializable(self, tmp_path: Path) -> None:
        """This dict is written verbatim into `arms.json` -- a step carrying
        a non-JSON-safe value would only surface as a crash at write time."""
        result = k4_preflight.route_walk_steps(
            repo_root=str(tmp_path),
            hook_run=_faithful_hook,
            cli_run=_fake_cli_all_pass,
            skill_md_text=_FIXED_SKILL_MD,
            transcript_path="/fake/transcript.jsonl",
        )
        json.dumps(result)  # must not raise


class TestDesSubcommandsSkillMdParserIsTheOneSharedSource:
    """`route_walk_steps`' root-Bash coverage loop and
    `test_auto_root_bash_lockdown.py`'s allowlist-coverage guard must derive
    the mandated `des <subcommand>` set from the SAME parser -- never two
    hand-typed lists that can silently drift apart (the exact drift class
    the genesis defect was)."""

    def test_parser_finds_the_fenced_commands_not_the_prose(self) -> None:
        found = k4_preflight.des_subcommands_root_is_told_to_run(_FIXED_SKILL_MD)
        assert found == {"prepare-ordinary-request", "resolve-charters"}


# ---------------------------------------------------------------------------
# Tier 2: real installed hook, in-process, for the two genesis cases.
# ---------------------------------------------------------------------------


def _transcript(tmp_path: Path) -> Path:
    path = tmp_path / "transcript.jsonl"
    entries = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Skill",
                        "input": {"skill": "nw-mode-select"},
                    }
                ]
            },
        },
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "nw-auto"}}
                ]
            },
        },
    ]
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return path


def _real_hook_run(
    monkeypatch: pytest.MonkeyPatch, capsys, payload: dict
) -> tuple[int, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    exit_code = pre_tool_use_handler.handle_pre_tool_use()
    return exit_code, capsys.readouterr().out.strip()


class TestRouteWalkRealHookCases:
    """The genesis defect lived here: `des resolve-charters` was blocked by
    the real installed hook while `nw-auto/SKILL.md` mandated root run it
    directly. Both cases now run against the actual production
    `pre_tool_use_handler` module, not a fake -- if either regresses, this
    fails for real, not because a fake happened to agree with itself."""

    def test_seed_heredoc_is_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        transcript = _transcript(tmp_path)
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "des prepare-ordinary-request --size M "
                    f"--repo-root {tmp_path} <<'NW_SEED'\nprobe seed\nNW_SEED"
                )
            },
            "transcript_path": str(transcript),
        }
        code, _ = _real_hook_run(monkeypatch, capsys, payload)
        assert code == 0

    def test_resolve_charters_is_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        transcript = _transcript(tmp_path)
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    f"des resolve-charters --repo-root {tmp_path} "
                    "--delivery-id auto-probeprobeprobe --examine true"
                )
            },
            "transcript_path": str(transcript),
        }
        code, _ = _real_hook_run(monkeypatch, capsys, payload)
        assert code == 0

    def test_an_unrelated_git_subcommand_still_denies(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Negative control alongside the two genesis cases: the allowlist
        must still be CLOSED for everything it never named, or the two
        positive cases above would trivially pass a hook that allows
        anything."""
        transcript = _transcript(tmp_path)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git log --oneline -1"},
            "transcript_path": str(transcript),
        }
        code, _ = _real_hook_run(monkeypatch, capsys, payload)
        assert code == 2


# ---------------------------------------------------------------------------
# Tier 3: `_installed_cli_run` must resolve `des` the way a real Bash call
# would -- via PATH, into the WORKSPACE's own arm-shaped install -- never a
# hardcoded path into the harness's separate build venv.
#
# Genesis (run 5, preflight.stderr): `cli-charter-scaffold` blocked with
# `missing-charter-template: template absent at .../nwave-venv/lib/
# python3.12/nWave/templates/expectation-charter.md`. `des charter_scaffold`
# resolves its packaged template relative to `Path(__file__).resolve()` of
# the `des` package Python actually imported -- correct when `des` is
# imported via the workspace's own `.claude-k4/bin/des` shim (which inserts
# `{workspace}/.claude-k4/lib/python` onto `sys.path`, landing 3 parents up
# on `.claude-k4/lib/`, sibling to the `nWave/` tree `nwave-ai install`
# populated there). `_installed_cli_run` was hardcoding
# `venv / "bin" / "des"` -- the harness's own SHARED build venv's console
# script, whose package-relative template lookup lands in that venv's
# generic `site-packages`, which has no `nWave/` tree at all. Root cause
# was the harness bypassing PATH resolution, not a product defect: `des`
# DOES resolve its installed assets correctly when invoked the way a real
# arm session invokes it.
# ---------------------------------------------------------------------------


class TestInstalledCliRunResolvesTheWorkspaceShim:
    def test_argv_is_never_rewritten_to_a_hardcoded_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`_installed_cli_run` must pass `argv[0]` through as the literal
        string `"des"` -- exactly what a root/subagent Bash call actually
        types -- and let PATH resolve it, never substitute an absolute path
        into some OTHER install (the harness's own build venv, or anything
        else)."""
        captured = {}

        def _fake_run(argv, **kwargs):
            captured["argv"] = argv
            captured["kwargs"] = kwargs

            class _Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            return _Result()

        monkeypatch.setattr(k4_preflight.subprocess, "run", _fake_run)

        workspace = tmp_path / "probe-route-walk"
        workspace.mkdir()
        k4_preflight._installed_cli_run(
            workspace, ["des", "charter-scaffold", "--delivery-id", "x"], None
        )
        assert captured["argv"] == [
            "des",
            "charter-scaffold",
            "--delivery-id",
            "x",
        ], (
            "argv must be the literal command unchanged -- a rewritten "
            "argv[0] is exactly the run-5 regression"
        )
        assert captured["kwargs"]["stdin"] is subprocess.DEVNULL

    def test_env_path_puts_the_workspace_shim_bin_first(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The PATH `_installed_cli_run` hands to `subprocess.run` must put
        `{workspace}/.claude-k4/bin` first -- the SAME directory
        `nwave-ai install` populates the per-arm `des` shim into -- so a
        bare `"des"` argv[0] resolves there, not into any other install on
        the inherited PATH."""
        captured = {}

        def _fake_run(argv, **kwargs):
            captured["env"] = kwargs.get("env")

            class _Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            return _Result()

        monkeypatch.setattr(k4_preflight.subprocess, "run", _fake_run)
        monkeypatch.setenv("PATH", "/some/decoy/bin")

        workspace = tmp_path / "probe-route-walk"
        workspace.mkdir()
        k4_preflight._installed_cli_run(workspace, ["des", "--help"], None)

        path_entries = captured["env"]["PATH"].split(":")
        assert path_entries[0] == str(workspace / ".claude-k4" / "bin")

    def test_installed_cli_run_signature_carries_no_venv_parameter(self) -> None:
        """A `venv` parameter is exactly the surface that invited the run-5
        regression (a hardcoded `venv / "bin" / "des"` substitution) --
        pinned absent so it cannot silently return."""
        params = inspect.signature(k4_preflight._installed_cli_run).parameters
        assert "venv" not in params
