"""An integrated lane recovers from a moved root without committing runtime state.

@contract-shape: real-io

Real Git/worktrees and native child checks are necessary for the declared
ancestry, persistence and staging observations. DES is driven through the
incumbent CLI stepper, with explicit host facts, not implementation patches.
The existing lane feature's terminal wiring scenarios remain unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    base_repository,
    block,
    stepper,
)
from tests.des.acceptance.steps_for_the_orchestrator.test_verify_and_integrate_close_the_request import (
    ORACLE,
    TARGET,
    crafted,
)


CUSTOM_IGNORE = b"# user policy\r\nscratch/\r\n# deliberately no DES ignore"
NATIVE_ENV = [
    "env",
    "-u",
    "CI",
    "PYTHONDONTWRITEBYTECODE=1",
]
NATIVE_COMMANDS = [
    [
        *NATIVE_ENV,
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        ORACLE,
    ],
    [
        *NATIVE_ENV,
        sys.executable,
        "-c",
        "import subprocess; "
        "print('MEASURED_HEAD=' + "
        "subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip())",
    ],
]


def expect(actual, expected, why: str, how: str) -> None:
    assert actual == expected, (
        f"WHAT: expected {expected!r}, observed {actual!r}. WHY: {why}. HOW: {how}."
    )


def require(condition: bool, what: str, why: str, how: str) -> None:
    assert condition, f"WHAT: {what}. WHY: {why}. HOW: {how}."


@dataclass
class LaneRecovery:
    principal: Path
    lane: Path
    principal_step: Callable
    lane_step: Callable
    trace: list[dict] = field(default_factory=list)

    def git_observation(
        self, root: Path, *argv: str
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", "-C", str(root), *argv],
            capture_output=True,
            text=True,
            check=False,
        )
        self.trace.append(
            {
                "argv": ["git", "-C", str(root), *argv],
                "exit": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        return result

    def git(self, root: Path, *argv: str) -> str:
        result = self.git_observation(root, *argv)
        expect(
            result.returncode,
            0,
            f"the declared Git observation must be available: {argv!r}; {result.stderr}",
            "make the temporary repository support the named public Git operation",
        )
        return result.stdout.strip()

    def runtime_lock_is_ignored(self) -> None:
        path = ".nwave/des/commit.lock"
        result = self.git_observation(self.lane, "check-ignore", "-q", "--", path)
        require(
            result.returncode in (0, 1),
            (
                f"Git check-ignore could not observe {path}: "
                f"exit={result.returncode}, stderr={result.stderr!r}"
            ),
            "an unavailable ignore observation cannot establish runtime policy",
            "restore the Git observation before checking the runtime ignore",
        )
        require(
            result.returncode == 0,
            f"runtime path {path} remains unignored (Git check-ignore exited 1)",
            "runtime must not appear as deliverable work or enter lane history",
            "establish the runtime-only ignore before creating the delivery lock",
        )

    def step(self, *argv: str, answers=None, stdin: str = "") -> tuple[int, str, str]:
        # Reuse crafted's complete public manifests. Only this fixture's native
        # recipe and pre-existing product change: RED is VALUE=0, not an import
        # error, and the child cannot inherit the host's pytest probe/plugin.
        if argv[0] == "design" and answers:
            answers = copy.deepcopy(answers)
            manifest = answers[0]["structured_output"]["manifest"]
            manifest["verification"] = copy.deepcopy(NATIVE_COMMANDS)
            manifest["targets"][0]["decision"] = "EXTEND"
            for candidate in manifest["reuse_analysis"]["candidates"]:
                if candidate["symbol"] == TARGET:
                    candidate["decision"] = "EXTEND"
        root = Path(argv[argv.index("--repo-root") + 1])
        invoke = self.principal_step if root == self.principal else self.lane_step
        # Remove the outer pytest probe before stepper copies the host
        # environment. DES may then add its own child JUnit reporter options;
        # the native argv must preserve those fresh options for measured RED.
        inherited_options = os.environ.pop("PYTEST_ADDOPTS", None)
        try:
            result = invoke(*argv, answers=answers, stdin=stdin)
        finally:
            if inherited_options is not None:
                os.environ["PYTEST_ADDOPTS"] = inherited_options
        # The recorder gets public invocations and their actual terminal bytes,
        # never fixture answers, source/test selectors or producer classifications.
        public_argv = ["des", *argv]
        if argv[0] in {"po", "design", "oracle", "craft"} and "--input" not in argv:
            public_argv.extend(("--input", "-"))
        self.trace.append(
            {
                "argv": public_argv,
                "exit": result[0],
                "stdout": result[1],
                "stderr": result[2],
            }
        )
        return result

    def success(self, *argv: str, **kwargs) -> dict[str, str]:
        code, out, err = self.step(*argv, **kwargs)
        expect(
            code,
            0,
            f"the declared public action must succeed: {argv!r}; terminal={out + err}",
            "make this CLI action honor its declared lifecycle preconditions",
        )
        lines = block(out, err)
        expect(
            lines.get("DELIVERY-OUTCOME"),
            "Success",
            "exit zero must carry the public closed success outcome",
            "emit DELIVERY-OUTCOME Success for the completed action",
        )
        return lines

    def integrated(self) -> tuple[str, dict[str, str]]:
        crafted(self.lane, self.step)
        self.no_runtime_history(require_private=True)
        verified = self.success("verify", "--repo-root", str(self.lane))
        candidate = verified.get("CANDIDATE", "")
        require(
            len(candidate) == 40,
            f"verify did not report a complete candidate SHA: {verified!r}",
            "the host must name the actual verified candidate for integration",
            "report the constructed candidate's full Git SHA",
        )
        integrated = self.success(
            "integrate", "--repo-root", str(self.lane), "--candidate", candidate
        )
        expect(
            self.git(self.lane, "rev-parse", "HEAD"),
            candidate,
            "in-lane integration must advance the lane to its verified candidate",
            "compare-and-swap the lane branch onto that candidate",
        )
        self.closed()
        return candidate, integrated

    def closed(self) -> None:
        expect(
            (self.lane / ".nwave/des/handover.json").exists(),
            False,
            "integrated work is historical, not a revived active Request",
            "keep cleanup complete and read the retained snapshot without reviving it",
        )

    def lane_invocation(self) -> str:
        return (
            f"des lane integrate --repo-root {self.principal} "
            f"--worktree {self.lane} --keep-worktree"
        )

    def no_runtime_history(self, *, require_private: bool = False) -> None:
        refs = self.git(
            self.principal, "for-each-ref", "--format=%(refname)"
        ).splitlines()
        if require_private:
            require(
                any(ref.startswith("refs/nwave/turns/") for ref in refs),
                f"no private producer turn refs were available among {refs!r}",
                "branch-only history cannot witness runtime exclusion from private turns",
                "exercise DESIGN/oracle/craft and inspect private refs before cleanup releases them",
            )
        commits = self.git(self.principal, "rev-list", "--all").splitlines()
        require(
            bool(commits),
            "the all-ref commit population was empty",
            "absence of runtime paths must mean inspected history, not no history",
            "enumerate every commit reachable from the available refs",
        )
        for commit in commits:
            paths = self.git(
                self.principal, "ls-tree", "-r", "--name-only", commit
            ).splitlines()
            runtime = [path for path in paths if path.startswith(".nwave/des/")]
            expect(
                runtime,
                [],
                f"DES runtime is worktree state, never a branch or private-turn payload ({commit})",
                "exclude .nwave/des from each producer's staged/committed tree",
            )

    def merge_and_reverify(self, candidate: str, moved: str, tip: str) -> str:
        snapshot = self.lane / f".nwave/des/candidates/{candidate}/handover.json"
        retained_before = snapshot.read_bytes()
        code, out, err = self.step(
            "lane",
            "integrate",
            "--repo-root",
            str(self.principal),
            "--worktree",
            str(self.lane),
            "--keep-worktree",
        )
        require(
            code != 0,
            f"stale lane integration succeeded: {out + err}",
            "the lane must not overwrite an independently advanced root",
            "refuse IntegrationStale until the root is in the lane's history",
        )
        stale = block(out, err)
        expect(
            stale.get("WHAT"),
            "IntegrationStale",
            "root moved outside the lane",
            "report the stale integration",
        )
        expect(
            stale.get("DELIVERY-OUTCOME"),
            "Refusal",
            "staleness is a recoverable refusal",
            "emit the closed refusal outcome",
        )
        commands = [
            f"git -C {self.lane} merge --no-edit {moved}",
            f"des verify --repo-root {self.lane} --integrated-candidate {candidate}",
            self.lane_invocation(),
        ]
        for command in commands:
            require(
                command in stale.get("HOW", ""),
                f"stale HOW omitted {command!r}: {stale!r}",
                "plain verify cannot recover the closed Request, including after a previous merge",
                "find retained ancestor C and name the exact merge, explicit reverify and lane integration commands",
            )
        expect(
            self.git(self.principal, "rev-parse", "HEAD"),
            moved,
            "stale refusal cannot move root",
            "leave root untouched",
        )
        expect(
            self.git(self.lane, "rev-parse", "HEAD"),
            tip,
            "stale refusal cannot move lane",
            "leave lane untouched",
        )
        self.closed()

        # Execute exactly the recovery operations the public HOW must name.
        self.git(self.lane, "merge", "--no-edit", moved)
        merged = self.git(self.lane, "rev-parse", "HEAD")
        require(
            merged != tip,
            "merge did not create a new tip",
            "old evidence cannot witness newly merged root work",
            "retain both parents in the merged lane tip",
        )
        self.git(self.lane, "merge-base", "--is-ancestor", candidate, merged)
        self.git(self.lane, "merge-base", "--is-ancestor", moved, merged)
        reverified = self.success(
            "verify", "--repo-root", str(self.lane), "--integrated-candidate", candidate
        )
        expect(
            reverified.get("INTEGRATED-CANDIDATE"),
            candidate,
            "each recovery must name the same retained snapshot",
            "report the original integrated candidate, not an invented snapshot for a merge tip",
        )
        expect(
            reverified.get("REVERIFIED"),
            merged,
            "native evidence must measure the current merged tip, not old C",
            "execute the declared checks on current HEAD",
        )
        require(
            "exit=0" in reverified.get("NATIVE", ""),
            f"no successful native execution reported: {reverified!r}",
            "recovery is native re-execution, not an old approval",
            "run and report the declared native checks",
        )
        evidence_locator = reverified.get("NATIVE-EVIDENCE", "")
        require(
            bool(evidence_locator),
            "native evidence locator absent",
            "execution must remain observable",
            "persist and report this native execution",
        )
        evidence_path = Path(evidence_locator)
        if not evidence_path.is_absolute():
            evidence_path = self.lane / evidence_path
        evidence_bytes = evidence_path.read_bytes()
        expect(
            reverified.get("NATIVE-EVIDENCE-SHA256"),
            hashlib.sha256(evidence_bytes).hexdigest(),
            "the printed evidence identity must identify the emitted receipt",
            "hash the exact persisted native evidence bytes",
        )
        evidence = json.loads(evidence_bytes)
        expect(
            [item["argv"] for item in evidence],
            NATIVE_COMMANDS,
            "every declared check must be executed in order",
            "retain the complete declared command population",
        )
        expect(
            evidence[1]["stdout"].strip(),
            f"MEASURED_HEAD={merged}",
            "old candidate or first-merge execution is not evidence for current HEAD",
            "run native commands in the newly merged tip's candidate workspace",
        )
        expect(
            snapshot.read_bytes(),
            retained_before,
            "explicit recovery reads historical authority without rewriting it",
            "keep the integrated candidate snapshot immutable",
        )
        expect(
            (self.lane / f".nwave/des/candidates/{merged}/handover.json").exists(),
            False,
            "reverification must not grant merged heads new candidate/role admission",
            "persist native evidence only and resolve the original retained ancestor for later stale recovery",
        )
        expect(
            reverified.get("NEXT"),
            self.lane_invocation(),
            "reverification owes explicit root integration",
            "name the lane integrate invocation with --keep-worktree",
        )
        self.closed()
        expect(
            self.git(self.lane, "rev-parse", "HEAD"),
            merged,
            "reverification must create no empty commit",
            "measure HEAD without moving it",
        )
        expect(
            self.git(self.principal, "rev-parse", "HEAD"),
            moved,
            "reverification executes no advisory NEXT",
            "leave root unchanged until requested integration",
        )
        return merged

    def recover_after_root_moves(self) -> None:
        before = self.git(self.principal, "rev-parse", "HEAD")
        candidate, integrated = self.integrated()
        for label, expected in {
            "INTEGRATED": candidate,
            "DESTINATION-WORKTREE": str(self.lane),
            "DESTINATION-BRANCH": "lane/recovery",
            "PRINCIPAL-WORKTREE": str(self.principal),
            "PRINCIPAL-HEAD": before,
            "NEXT": self.lane_invocation(),
        }.items():
            expect(
                integrated.get(label),
                expected,
                f"in-lane integration must report its actual destination and remaining root step ({label})",
                "observe Git worktree identity and emit the exact lane integration invocation",
            )
        expect(
            self.git(self.principal, "rev-parse", "HEAD"),
            before,
            "role-level integration in a lane must not imply or enact root integration",
            "leave the principal HEAD unchanged until lane integrate is explicitly invoked",
        )
        self.no_runtime_history()
        tip = candidate
        for filename in ("independent.md", "second-independent.md"):
            (self.principal / filename).write_text(
                f"independent root work: {filename}\n"
            )
            self.git(self.principal, "add", "--", filename)
            self.git(
                self.principal, "commit", "-qm", f"independent root advance: {filename}"
            )
            moved = self.git(self.principal, "rev-parse", "HEAD")
            # On the second refusal C is a retained ancestor, not the lane tip.
            tip = self.merge_and_reverify(candidate, moved, tip)
        merged = tip
        closed = self.success(
            "lane",
            "integrate",
            "--repo-root",
            str(self.principal),
            "--worktree",
            str(self.lane),
            "--keep-worktree",
        )
        expect(
            closed.get("INTEGRATED"),
            merged,
            "root integration must use the exact reverified merge tip",
            "fast-forward root to the lane HEAD",
        )
        expect(
            self.git(self.principal, "rev-parse", "HEAD"),
            merged,
            "root must receive both histories",
            "fast-forward to merged HEAD",
        )
        expect(
            self.git(self.lane, "rev-parse", "HEAD"),
            merged,
            "retained lane must keep its tip",
            "keep the worktree without rewriting its branch",
        )
        self.closed()
        self.runtime_is_ignored()
        self.no_runtime_history()

    def runtime_is_ignored(self) -> None:
        self.runtime_lock_is_ignored()
        expect(
            (self.lane / ".nwave/.gitignore").read_bytes(),
            CUSTOM_IGNORE,
            "runtime ignoring must not overwrite user policy",
            "write only the runtime-local ignore file",
        )
        status = self.git(self.lane, "status", "--porcelain", "--untracked-files=all")
        expect(
            [line for line in status.splitlines() if ".nwave/" in line],
            [],
            "a clean integrated lane must not invite staging runtime as work",
            "keep runtime ignored and reconcile only delivered bytes",
        )

    def ordinary_staging_excludes_runtime(self) -> None:
        self.integrated()
        self.runtime_is_ignored()
        config = self.lane / ".nwave/config.json"
        config.write_text('{"verification": {"reuse": {"outputs": []}}}\n')
        self.git(self.lane, "add", "-A")
        staged = self.git(self.lane, "diff", "--cached", "--name-only").splitlines()
        expect(
            staged,
            [".nwave/config.json"],
            "ordinary staging must keep config trackable while excluding runtime",
            "ignore only .nwave/des, never all of .nwave",
        )
        self.no_runtime_history()

    def refuses_recovery(self, case: str) -> None:
        candidate, _ = self.integrated()
        selected = candidate
        if case == "unknown":
            selected = self.git(self.lane, "rev-parse", f"{candidate}^")
        elif case == "not-in-history":
            base = self.git(self.lane, "rev-parse", f"{candidate}^")
            self.git(self.lane, "checkout", "-qb", "outside-candidate-history", base)
        elif case == "owned-drift":
            (self.lane / TARGET).write_text("VALUE = 2\n")
        before = self.git(self.lane, "rev-parse", "HEAD")
        principal_before = self.git(self.principal, "rev-parse", "HEAD")
        workspace_before = (self.lane / TARGET).read_bytes()
        code, out, err = self.step(
            "verify", "--repo-root", str(self.lane), "--integrated-candidate", selected
        )
        require(
            code != 0,
            f"invalid recovery succeeded: {out + err}",
            "snapshot/history/workspace preconditions must hold before measurement",
            "refuse this declared invalid candidate context",
        )
        refusal = block(out, err)
        expected = {
            "unknown": "IntegratedCandidateUnknown",
            "not-in-history": "IntegratedCandidateNotInHistory",
            "owned-drift": "IntegratedCandidateWorkspaceDrift",
        }[case]
        expect(
            refusal.get("WHAT"),
            expected,
            "distinct recovery failures must remain distinguishable",
            "emit the declared refusal instead of generic parser or handover failure",
        )
        expect(
            refusal.get("DELIVERY-OUTCOME"),
            "Refusal",
            "invalid recovery is not success",
            "report the closed refusal outcome",
        )
        how = refusal.get("HOW", "")
        advice = how.lower()
        if case == "unknown":
            require(
                candidate in how or ("INTEGRATED" in how and "des integrate" in how),
                f"unknown-candidate HOW names no usable snapshot selection: {how!r}",
                "the owner needs the integrated SHA, not a generic retry",
                "name the retained candidate or the INTEGRATED SHA reported by des integrate",
            )
        elif case == "not-in-history":
            require(
                any(action in advice for action in ("choose", "select", "use", "merge"))
                and ("candidate" in advice or selected in how)
                and any(
                    relation in advice for relation in ("ancestor", "history", "merge")
                ),
                f"ancestry HOW names no history repair or valid candidate selection: {how!r}",
                "re-running the same unrelated candidate cannot establish ancestry",
                "explain how to select a retained ancestor or repair the history relation",
            )
        else:
            require(
                any(action in advice for action in ("commit", "restore"))
                and (
                    f"des verify --repo-root {self.lane}" in how
                    or any(action in advice for action in ("re-run", "rerun", "again"))
                ),
                f"owned-drift HOW names no owned-byte repair and verification retry: {how!r}",
                "the owner must reconcile the named owned paths before measuring HEAD",
                "tell the owner to commit or restore the paths, then re-run verification",
            )
        if case == "not-in-history":
            require(
                selected in out + err and before in out + err,
                "ancestry refusal omitted candidate or HEAD",
                "both commits explain the failed relationship",
                "report both measured Git identities",
            )
        elif case == "owned-drift":
            require(
                TARGET in out + err,
                "workspace refusal omitted the drifting owned path",
                "the owner must know what to commit or restore",
                "name the actual drifting path",
            )
        require(
            "REVERIFIED" not in refusal and "NATIVE-EVIDENCE" not in refusal,
            "invalid recovery reported a measurement",
            "these refusals happen before native execution",
            "validate the declared preconditions before running checks",
        )
        expect(
            self.git(self.lane, "rev-parse", "HEAD"),
            before,
            "refusal must preserve lane history",
            "leave HEAD unchanged",
        )
        expect(
            self.git(self.principal, "rev-parse", "HEAD"),
            principal_before,
            "refusal must preserve root history",
            "leave root unchanged",
        )
        expect(
            (self.lane / TARGET).read_bytes(),
            workspace_before,
            "refusal cannot repair owned bytes autonomously",
            "leave workspace changes to the owner",
        )
        self.closed()

    def unknown_recovery_preserves_active_request(self) -> None:
        self.success(
            "po",
            "--project",
            "--repo-root",
            str(self.lane),
            answers=[accepted_values("A")],
            stdin="an active Request must not be replaced by unknown historical work",
        )
        handover = self.lane / ".nwave/des/handover.json"
        active_before = handover.read_bytes()
        before = self.git(self.lane, "rev-parse", "HEAD")
        code, out, err = self.step(
            "verify", "--repo-root", str(self.lane), "--integrated-candidate", before
        )
        require(
            code != 0,
            f"unknown historical recovery succeeded over active work: {out + err}",
            "an active Request does not supply a snapshot for an unknown candidate",
            "refuse IntegratedCandidateUnknown without consuming or replacing active work",
        )
        refusal = block(out, err)
        expect(
            refusal.get("WHAT"),
            "IntegratedCandidateUnknown",
            "active work must not turn an unknown historical candidate into a valid one",
            "look up only the explicitly selected retained candidate snapshot",
        )
        require(
            f"des verify --repo-root {self.lane}" in refusal.get("HOW", ""),
            f"unknown-candidate HOW omitted the active Request's verify route: {refusal!r}",
            "the existing active Request remains the owner's available path",
            "name ordinary verify when no integrated snapshot is available",
        )
        expect(
            handover.read_bytes(),
            active_before,
            "historical recovery must leave active work untouched",
            "preserve the current handover bytes",
        )
        expect(
            self.git(self.lane, "rev-parse", "HEAD"),
            before,
            "unknown recovery cannot advance active work",
            "leave the lane HEAD unchanged",
        )

    def refuses_conflicting_modes(self) -> None:
        for flags in (("--fresh",), ("--integrated-candidate", "0" * 40)):
            mode_code, mode_out, mode_err = self.step(
                "verify", "--repo-root", str(self.lane), *flags
            )
            require(
                mode_code != 2
                and "unrecognized arguments" not in (mode_out + mode_err).lower(),
                (
                    f"individual verification mode {flags!r} was not recognized: "
                    f"{mode_out + mode_err}"
                ),
                "a missing option is not an implemented mutually exclusive mode",
                "recognize each declared verification mode before enforcing their conflict",
            )
        code, out, err = self.step(
            "verify",
            "--repo-root",
            str(self.lane),
            "--fresh",
            "--integrated-candidate",
            "0" * 40,
        )
        expect(
            code,
            2,
            "the two verify modes cannot be combined",
            "declare the options mutually exclusive in the public parser",
        )
        require(
            "--fresh" in out + err and "--integrated-candidate" in out + err,
            f"usage error omitted the conflicting public options: {out + err}",
            "the owner must know which declared modes conflict",
            "name both mutually exclusive options",
        )
        usage = (out + err).lower()
        require(
            "unrecognized arguments" not in usage
            and any(
                contrast in usage
                for contrast in (
                    "not allowed with",
                    "mutually exclusive",
                    "cannot be combined",
                    "cannot be used together",
                    "conflicting",
                )
            ),
            f"combined modes produced no recognized-option conflict: {out + err}",
            "generic unsupported-option usage must not masquerade as mutual exclusion",
            "reject the combination specifically because both recognized modes conflict",
        )

    def commits_work_without_runtime(self) -> None:
        (self.lane / "work.txt").write_text("the lane's design work\n")
        committed = self.success(
            "commit",
            "--repo-root",
            str(self.lane),
            "--owned-paths",
            ".",
            "--step-id",
            "design-1",
            "--message",
            "wip: design 1",
        )
        expect(
            committed.get("COMMIT"),
            self.git(self.lane, "rev-parse", "HEAD"),
            "the commit producer must report the actual lane commit",
            "report the SHA of the committed owned work",
        )
        expect(
            self.git(
                self.lane, "show", "--name-only", "--format=", "HEAD"
            ).splitlines(),
            ["work.txt"],
            "a fresh DES producer commit must contain the work, never its runtime lock",
            "ignore runtime before creating the lock and exclude .nwave/des from staging",
        )
        require(
            (self.lane / ".nwave/des/commit.lock").is_file(),
            "des commit did not leave its actual runtime lock in the worktree",
            "absence from the commit must mean excluded runtime, not an unexercised lock",
            "acquire the producer's runtime lock without committing it",
        )
        self.runtime_lock_is_ignored()
        status = self.git(self.lane, "status", "--porcelain", "--untracked-files=all")
        expect(
            [line for line in status.splitlines() if ".nwave/" in line],
            [],
            "producer runtime must not appear as work left to stage",
            "keep .nwave/des ignored after the owned commit completes",
        )
        self.no_runtime_history()

    def failed_native_recovery_preserves_closed_work(self) -> None:
        candidate, _ = self.integrated()
        snapshot = self.lane / f".nwave/des/candidates/{candidate}/handover.json"
        retained_before = snapshot.read_bytes()
        (self.lane / TARGET).write_text("VALUE = 0\n")
        self.git(self.lane, "add", "-A")
        self.git(self.lane, "commit", "-qm", "committed work fails the value oracle")
        failing = self.git(self.lane, "rev-parse", "HEAD")
        self.git(self.lane, "merge-base", "--is-ancestor", candidate, failing)
        principal_before = self.git(self.principal, "rev-parse", "HEAD")
        index_before = self.git(self.lane, "write-tree")
        workspace_before = (self.lane / TARGET).read_bytes()
        code, out, err = self.step(
            "verify", "--repo-root", str(self.lane), "--integrated-candidate", candidate
        )
        require(
            code != 0,
            f"committed failing work was reverified successfully: {out + err}",
            "ancestry-valid matching bytes still owe the declared native checks",
            "measure the current HEAD and report its actual failing oracle",
        )
        refusal = block(out, err)
        expect(
            refusal.get("DELIVERY-OUTCOME"),
            "Refusal",
            "a measured failing check must not become indeterminate or old GREEN",
            "report the native verification refusal",
        )
        expect(
            refusal.get("WHAT"),
            "VerificationFailed",
            "the failure is the public value assertion, not a recovery precondition",
            "return the existing native-failure vocabulary",
        )
        require(
            failing in out + err,
            f"native failure omitted the measured HEAD {failing}: {out + err}",
            "the owner needs evidence for current committed work rather than old C",
            "identify the measured failing tip",
        )
        locator = refusal.get("NATIVE-EVIDENCE")
        if not locator:
            match = re.search(r"\.nwave/des/logs/native/[^\s;]+\.json", out + err)
            locator = match.group(0) if match else None
        require(
            locator is not None,
            f"failed native execution reported no retained receipt: {out + err}",
            "a failure without its execution evidence cannot establish semantic RED",
            "persist the failed native evidence and report its locator",
        )
        evidence_path = Path(locator)
        if not evidence_path.is_absolute():
            evidence_path = self.lane / evidence_path
        evidence = json.loads(evidence_path.read_bytes())
        expect(
            [item["argv"] for item in evidence],
            NATIVE_COMMANDS,
            "native failure must retain the complete ordered check population",
            "execute and record every declared check",
        )
        expect(
            [item["exit"] for item in evidence],
            [1, 0],
            "the committed value oracle fails while the independent HEAD check runs",
            "retain the actual pytest assertion failure and successful HEAD observation",
        )
        require(
            "test_value" in evidence[0]["stdout"]
            and "failed" in evidence[0]["stdout"].lower(),
            f"receipt does not show the executed failing value test: {evidence[0]!r}",
            "collection or missing instrumentation is not the promised native refusal",
            "run the authored value assertion against the committed failing product",
        )
        expect(
            evidence[1]["stdout"].strip(),
            f"MEASURED_HEAD={failing}",
            "failure evidence must belong to current HEAD",
            "run native commands in that tip's candidate workspace",
        )
        expect(
            self.git(self.lane, "rev-parse", "HEAD"),
            failing,
            "failed recovery cannot create a commit or rewrite the lane",
            "leave the failing committed HEAD unchanged",
        )
        expect(
            self.git(self.principal, "rev-parse", "HEAD"),
            principal_before,
            "failed recovery cannot integrate into the root",
            "leave the principal HEAD unchanged",
        )
        expect(
            self.git(self.lane, "write-tree"),
            index_before,
            "measurement must not stage a repair",
            "leave the index unchanged on native refusal",
        )
        expect(
            (self.lane / TARGET).read_bytes(),
            workspace_before,
            "failed verification cannot repair the product autonomously",
            "preserve the measured workspace bytes",
        )
        expect(
            snapshot.read_bytes(),
            retained_before,
            "native failure must not rewrite historical authority",
            "read the retained snapshot without changing it",
        )
        expect(
            (self.lane / f".nwave/des/candidates/{failing}/handover.json").exists(),
            False,
            "failed remeasurement grants no new candidate admission",
            "persist execution evidence only",
        )
        self.closed()

    def unreadable_owned_bytes_are_unobservable(self) -> None:
        candidate, _ = self.integrated()
        source = self.lane / TARGET
        source_before = source.read_bytes()
        mode_before = source.stat().st_mode & 0o7777
        snapshot = self.lane / f".nwave/des/candidates/{candidate}/handover.json"
        retained_before = snapshot.read_bytes()
        lane_before = self.git(self.lane, "rev-parse", "HEAD")
        principal_before = self.git(self.principal, "rev-parse", "HEAD")
        index_before = self.git(self.lane, "write-tree")
        native = self.lane / ".nwave/des/logs/native"
        receipts_before = {
            str(path.relative_to(native)): path.read_bytes()
            for path in native.rglob("*")
            if path.is_file()
        }
        require(
            bool(receipts_before),
            "no prior native receipt population was available",
            "no new execution must be distinguished from never measuring the fixture",
            "retain the real integrated candidate's native evidence before this refusal",
        )
        self.git(self.lane, "merge-base", "--is-ancestor", candidate, lane_before)
        try:
            source.chmod(0)
            require(
                not os.access(source, os.R_OK),
                f"the host can still read permission-obstructed {TARGET}",
                "this case requires genuine unreadability, not a root bypass",
                "run the permission observation with a non-root user",
            )
            code, out, err = self.step(
                "verify",
                "--repo-root",
                str(self.lane),
                "--integrated-candidate",
                candidate,
            )
            require(
                code != 0,
                f"unreadable owned bytes were reverified: {out + err}",
                "unknown bytes cannot establish coverage or actual drift",
                "return the declared unobservable relation without executing checks",
            )
            refusal = block(out, err)
            expect(
                refusal.get("DELIVERY-OUTCOME"),
                "Indeterminate",
                "unreadability is unavailable evidence, not measured product drift",
                "preserve the Covered/Drifted/Unobservable distinction at the CLI",
            )
            expect(
                refusal.get("WHAT"),
                "IntegratedCandidateUnobservable",
                "permissions do not prove an owned-byte content mismatch",
                "report the unavailable observation instead of WorkspaceDrift",
            )
            diagnostic = refusal.get("WHAT", "") + " " + refusal.get("WHY", "")
            require(
                TARGET in diagnostic
                and "PermissionError" in diagnostic
                and any(probe in diagnostic.lower() for probe in ("read", "open")),
                f"unobservable diagnosis omitted path, probe or exception: {diagnostic}",
                "the owner needs the actual inaccessible observation",
                "name the owned path, its read probe and PermissionError",
            )
            how = refusal.get("HOW", "").lower()
            require(
                any(action in how for action in ("restore", "repair", "grant"))
                and any(subject in how for subject in ("access", "permission", "read"))
                and any(action in how for action in ("re-run", "rerun", "again")),
                f"unobservable HOW names no access restoration and retry: {how!r}",
                "retrying inaccessible bytes cannot make them observable",
                "tell the owner to restore read access, then re-run verification",
            )
            require(
                "NATIVE" not in refusal
                and "REVERIFIED" not in refusal
                and "NATIVE-EVIDENCE" not in refusal,
                f"unobservable recovery reported a native measurement: {refusal!r}",
                "the owned-byte observation must precede native verification",
                "stop before running checks when coverage cannot be observed",
            )
            expect(
                source.stat().st_mode & 0o7777,
                0,
                "the tool cannot restore permissions autonomously",
                "leave the intentional access obstruction to the owner",
            )
        finally:
            source.chmod(mode_before)
        expect(
            source.read_bytes(),
            source_before,
            "unobservable recovery cannot alter the source",
            "preserve bytes while reporting the missing read observation",
        )
        expect(
            self.git(self.lane, "rev-parse", "HEAD"),
            lane_before,
            "unobservable recovery must preserve lane history",
            "leave the lane HEAD unchanged",
        )
        expect(
            self.git(self.principal, "rev-parse", "HEAD"),
            principal_before,
            "unobservable recovery must preserve principal history",
            "leave the root HEAD unchanged",
        )
        expect(
            self.git(self.lane, "write-tree"),
            index_before,
            "unobservable recovery must preserve staging",
            "leave the Git index unchanged",
        )
        expect(
            snapshot.read_bytes(),
            retained_before,
            "unavailable observations cannot rewrite historical authority",
            "preserve the retained candidate snapshot",
        )
        expect(
            {
                str(path.relative_to(native)): path.read_bytes()
                for path in native.rglob("*")
                if path.is_file()
            },
            receipts_before,
            "unobservable owned bytes must produce no native execution or receipt mutation",
            "leave the complete existing native evidence population unchanged",
        )
        self.closed()

    def unavailable_ignore_prevents_runtime_effects(self, owner: str) -> None:
        runtime = self.lane / ".nwave/des"
        obstruction = runtime / ".gitignore"
        obstruction.mkdir(parents=True)
        sentinel = obstruction / "owner-policy.txt"
        sentinel.write_bytes(b"preserve this obstruction\n")
        source = self.lane / "work.txt"
        source.write_bytes(b"preserve this staged source\n")
        self.git(self.lane, "add", "--", "work.txt")
        lane_before = self.git(self.lane, "rev-parse", "HEAD")
        principal_before = self.git(self.principal, "rev-parse", "HEAD")
        index_before = self.git(self.lane, "write-tree")
        status_before = self.git(
            self.lane, "status", "--porcelain", "--untracked-files=all"
        )
        runtime_before = {
            str(path.relative_to(runtime)): None if path.is_dir() else path.read_bytes()
            for path in runtime.rglob("*")
        }
        if owner == "delivery":
            result = self.step(
                "po",
                "--project",
                "--repo-root",
                str(self.lane),
                answers=[accepted_values("A")],
                stdin="runtime ignoring must precede the delivery lock",
            )
            expected = "Indeterminate"
        else:
            result = self.step(
                "commit",
                "--repo-root",
                str(self.lane),
                "--owned-paths",
                ".",
                "--step-id",
                "design-1",
                "--message",
                "wip: design 1",
            )
            expected = "Refusal"
        code, out, err = result
        require(
            code != 0,
            f"{owner} ignored the unusable runtime-ignore path: {out + err}",
            "no runtime byte or commit may precede runtime-only ignoring",
            "stop at the ignore-creation failure before acquiring the lock",
        )
        refusal = block(out, err)
        expect(
            refusal.get("DELIVERY-OUTCOME"),
            expected,
            f"the {owner} lock owner owes its declared unavailable-ignore outcome",
            "translate this ignore-file obstruction through the declared boundary",
        )
        expect(
            refusal.get("WHAT"),
            "DeliveryLockUnavailable",
            "ignore creation failure is not a successful or ordinary commit",
            "name the runtime-ignore prerequisite failure",
        )
        require(
            ".nwave/des/.gitignore" in out + err,
            f"ignore failure omitted the obstructed file: {out + err}",
            "the owner must know the actual prerequisite that failed",
            "name .nwave/des/.gitignore in the failure",
        )
        expect(
            {
                str(path.relative_to(runtime)): (
                    None if path.is_dir() else path.read_bytes()
                )
                for path in runtime.rglob("*")
            },
            runtime_before,
            "unavailable ignore must prevent subsequent runtime/lock writes",
            "leave the obstruction intact and write no delivery runtime",
        )
        expect(
            self.git(self.lane, "rev-parse", "HEAD"),
            lane_before,
            "ignore failure must prevent a lane commit",
            "leave the lane HEAD unchanged",
        )
        expect(
            self.git(self.principal, "rev-parse", "HEAD"),
            principal_before,
            "ignore failure must preserve root history",
            "leave the principal HEAD unchanged",
        )
        expect(
            self.git(self.lane, "write-tree"),
            index_before,
            "ignore failure must not stage or resync any paths",
            "leave the complete Git index unchanged",
        )
        expect(
            self.git(self.lane, "status", "--porcelain", "--untracked-files=all"),
            status_before,
            "ignore failure must preserve all staged and unstaged work",
            "stop before writing authority or committing work",
        )
        expect(
            source.read_bytes(),
            b"preserve this staged source\n",
            "ignore failure cannot change the source payload",
            "leave the owner's staged bytes untouched",
        )


@pytest.fixture
def recovery(tmp_path: Path, record_property):
    root = base_repository(tmp_path / "root")
    # Declare the ignore input; no developer-wide Git exclude may supply the
    # promised runtime policy on behalf of DES.
    subprocess.run(
        ["git", "-C", str(root), "config", "core.excludesFile", "/dev/null"],
        check=True,
        capture_output=True,
    )
    # No .nwave ignore is inherited. A non-ignoring custom policy and a tracked
    # config discriminate runtime-only ignoring from ignoring the whole tree.
    (root / ".nwave").mkdir()
    (root / ".nwave/.gitignore").write_bytes(CUSTOM_IGNORE)
    (root / ".nwave/config.json").write_text("{}\n")
    (root / TARGET).write_text("VALUE = 0\n")
    subprocess.run(
        ["git", "-C", str(root), "add", "-A"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "track config and initial product"],
        check=True,
        capture_output=True,
    )
    principal_step = stepper(root, tmp_path, tmp_path / "principal-turns.json")
    journey = LaneRecovery(root, root, principal_step, principal_step)
    opened = journey.success(
        "lane", "open", "--repo-root", str(root), "--name", "recovery"
    )
    lane = Path(opened["WORKTREE"])
    lane_host = tmp_path / "lane-host"
    lane_host.mkdir()
    journey.lane = lane
    journey.lane_step = stepper(lane, lane_host, lane_host / "turns.json")
    try:
        yield journey
    finally:
        record_property("public_trace", json.dumps(journey.trace))


@pytest.fixture
def wip_lane(tmp_path: Path, record_property):
    """The independent commit producer runs before any delivery runtime writer."""
    root = base_repository(tmp_path / "root")
    subprocess.run(
        ["git", "-C", str(root), "config", "core.excludesFile", "/dev/null"],
        check=True,
        capture_output=True,
    )
    principal_step = stepper(root, tmp_path, tmp_path / "principal-turns.json")
    journey = LaneRecovery(root, root, principal_step, principal_step)
    opened = journey.success("lane", "open", "--repo-root", str(root), "--name", "wip")
    lane_host = tmp_path / "lane-host"
    lane_host.mkdir()
    journey.lane = Path(opened["WORKTREE"])
    journey.lane_step = stepper(journey.lane, lane_host, lane_host / "turns.json")
    try:
        yield journey
    finally:
        record_property("public_trace", json.dumps(journey.trace))


def test_first_des_commit_keeps_runtime_out_of_lane_history(
    wip_lane: LaneRecovery,
) -> None:
    wip_lane.commits_work_without_runtime()


def test_integrated_lane_recovers_from_a_moved_root(recovery: LaneRecovery) -> None:
    recovery.recover_after_root_moves()


def test_runtime_is_not_staged_but_custom_policy_and_config_remain_trackable(
    recovery: LaneRecovery,
) -> None:
    recovery.ordinary_staging_excludes_runtime()


@pytest.mark.parametrize("case", ["unknown", "not-in-history", "owned-drift"])
def test_integrated_candidate_recovery_refuses_invalid_context_without_mutation(
    recovery: LaneRecovery,
    case: str,
) -> None:
    recovery.refuses_recovery(case)


def test_unknown_integrated_candidate_preserves_the_active_request(
    recovery: LaneRecovery,
) -> None:
    recovery.unknown_recovery_preserves_active_request()


def test_fresh_and_integrated_candidate_are_mutually_exclusive(
    recovery: LaneRecovery,
) -> None:
    recovery.refuses_conflicting_modes()


def test_committed_native_failure_preserves_the_closed_lane(
    recovery: LaneRecovery,
) -> None:
    recovery.failed_native_recovery_preserves_closed_work()


@pytest.mark.parametrize("owner", ["delivery", "commit"])
def test_unavailable_runtime_ignore_prevents_lock_staging_and_commit_effects(
    wip_lane: LaneRecovery,
    owner: str,
) -> None:
    wip_lane.unavailable_ignore_prevents_runtime_effects(owner)


@pytest.mark.skipif(
    os.geteuid() == 0,
    reason="real unreadable-owned-file observation requires a non-root user",
)
def test_unreadable_owned_bytes_are_unknown_not_measured_drift(
    recovery: LaneRecovery,
) -> None:
    recovery.unreadable_owned_bytes_are_unobservable()
