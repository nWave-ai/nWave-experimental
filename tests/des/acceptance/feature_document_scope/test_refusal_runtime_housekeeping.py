"""Real refusal preservation and standalone ignore-before-lock observations.

The nested supports expose the original assertions on base and their migration.
These are finite real-filesystem observations, not a new walking skeleton.
@contract-shape: real-io
"""

from __future__ import annotations

import builtins
import json
import os
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

from des.cli.commit import main as commit_main
from des.domain.nwave_dir_gitignore import (
    nested_gitignore_content,
    runtime_gitignore_content,
)
from tests.des.acceptance.feature_document_scope.test_feature_document_scope import (
    MANIFEST,
    _des,
    _discuss_payload,
    _repo,
)
from tests.des.integration.test_des_commit_cli import _git, _init_git_repo


IGNORE = ".nwave/des/.gitignore"
LOCK = ".nwave/des/commit.lock"
HOUSEKEEPING = {IGNORE, LOCK}
REPOSITORY = Path(__file__).resolve().parents[4]
SUPPORTS = (
    (
        "tests/des/acceptance/feature_document_scope/test_feature_document_scope.py"
        "::test_bad_scope_config_and_mismatch_refuse_before_any_write",
        "_tree(root) == before",
    ),
    (
        "tests/des/acceptance/discuss_document_construction/"
        "test_discuss_document_construction.py"
        "::test_discuss_race_reports_indeterminate_with_authority_and_untouched_winner",
        "assert path == handover.handover_path(root)",
    ),
    *(
        (
            "tests/des/acceptance/feature_document_scope/test_feature_document_scope.py"
            "::test_root_document_commands_require_explicit_scope_before_writing"
            f"[{command}]",
            "assert _tree(root) == before",
        )
        for command in ("discuss", "po", "devops")
    ),
    (
        "tests/des/acceptance/feature_document_scope/test_feature_document_scope.py"
        "::test_epic_configuration_is_separate_and_malformed_config_writes_nothing",
        "assert _tree(root) == before",
    ),
)


def test_existing_refusal_and_winner_observations_satisfy_their_assertions(
    tmp_path: Path,
) -> None:
    environment = os.environ.copy()
    environment.pop("PYTEST_ADDOPTS", None)
    report_path = tmp_path / "refusal-supports.xml"
    selectors = (
        SUPPORTS[0][0],
        SUPPORTS[1][0],
        SUPPORTS[2][0].split("[", 1)[0],
        SUPPORTS[-1][0],
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--junitxml",
            str(report_path),
            *selectors,
        ],
        cwd=REPOSITORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    response = completed.stdout + completed.stderr
    assert report_path.is_file(), (
        f"WHAT: child pytest exited {completed.returncode} without its JUnit report.\n"
        "WHY: missing collection/setup evidence cannot count as behavioral RED.\n"
        "HOW: restore the declared native runner/report substrate.\n"
        f"Actual child response:\n{response}"
    )
    try:
        report = ElementTree.parse(report_path).getroot()
    except ElementTree.ParseError as error:
        pytest.fail(
            f"WHAT: child JUnit report is unparseable: {error}.\n"
            "WHY: the oracle cannot establish which behavioral tests ran.\n"
            f"HOW: restore the native JUnit report producer.\n{response}"
        )
    expected = {}
    for selector, checkpoint in SUPPORTS:
        module, name = selector.split("::", 1)
        expected[(module.removesuffix(".py").replace("/", "."), name)] = checkpoint
    testcases = report.findall(".//testcase")
    identities = [
        (
            case.get("classname", "").removesuffix("."),
            case.get("name", ""),
        )
        for case in testcases
    ]
    assert len(identities) == len(expected) and set(identities) == set(expected), (
        f"WHAT: exercised testcase identities={identities!r}; expected={list(expected)!r}.\n"
        "WHY: every declared support case must run exactly once; absent or duplicate "
        "observations cannot establish preservation.\n"
        f"HOW: run exactly the declared six cases.\n{response}"
    )
    failures = {}
    for case, identity in zip(testcases, identities, strict=True):
        failed = case.findall("failure")
        if failed:
            failures[identity] = "\n".join(
                f"{element.get('message', '')}\n{''.join(element.itertext())}"
                for element in failed
            )
    infrastructure = report.findall(".//error")
    skipped = report.findall(".//skipped")
    old_identities = set(list(expected)[:2])
    intended_red = (
        completed.returncode == 1
        and set(failures) == old_identities
        and not infrastructure
        and not skipped
        and all(
            "AssertionError" in failures[identity]
            and expected[identity] in failures[identity]
            for identity in old_identities
        )
    )
    classification = (
        "exact two pre-amendment behavioral assertion checkpoints"
        if intended_red
        else "not the declared two-checkpoint RED; inspect actual testcase outcomes"
    )
    assert (
        completed.returncode == 0
        and not failures
        and not infrastructure
        and not skipped
    ), (
        f"WHAT: child exit={completed.returncode}; {classification}; "
        f"testcase failures with locations={failures!r}; "
        f"errors={[ElementTree.tostring(item, encoding='unicode') for item in infrastructure]!r}; "
        f"skipped={[ElementTree.tostring(item, encoding='unicode') for item in skipped]!r}.\n"
        "WHY: all declared refusal and winner supports must execute and satisfy "
        "their assertions, never silently skip or fail setup.\n"
        "HOW: preserve the strict shared snapshot and align only admitted new "
        "housekeeping and the handover-only race double.\n"
        f"Actual child response:\n{response}"
    )


def _repository_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def _assert_refusal_preserves_repository(
    before: dict[str, bytes], after: dict[str, bytes], *, pre_lock: bool = False
) -> None:
    created = after.keys() - before.keys()
    deleted = before.keys() - after.keys()
    modified = {
        path for path in before.keys() & after.keys() if before[path] != after[path]
    }
    allowed = set() if pre_lock else HOUSEKEEPING
    forbidden = (created | modified) - allowed
    message = (
        f"WHAT: refusal created {sorted(created)}, modified {sorted(modified)}, "
        f"deleted {sorted(deleted)}; forbidden writes {sorted(forbidden)}.\n"
        "WHY: refusal permits only literal commit.lock housekeeping and a newly "
        "created canonical runtime ignore; every other repository byte is preserved.\n"
        "HOW: retain in-lock validation and prevent all non-housekeeping writes "
        "and every deletion on refusal."
    )
    assert not forbidden and not deleted, message
    if IGNORE in before:
        assert after.get(IGNORE) == before[IGNORE], (
            "WHAT: the existing runtime ignore changed or disappeared.\n"
            "WHY: the housekeeping exception never authorizes rewriting user bytes.\n"
            "HOW: create the runtime ignore only when absent; preserve existing bytes."
        )
    elif IGNORE in after:
        assert after[IGNORE] == runtime_gitignore_content(), (
            f"WHAT: new runtime ignore bytes are {after[IGNORE]!r}.\n"
            "WHY: only exactly canonical ignore content is admitted on refusal.\n"
            "HOW: write runtime_gitignore_content() without alteration."
        )
    runtime_after = {path for path in after if path.startswith(".nwave/des/")}
    runtime_before = {path for path in before if path.startswith(".nwave/des/")}
    assert runtime_after <= runtime_before | allowed, message


@pytest.mark.parametrize(
    "case",
    (
        "invalid-feature-id",
        "missing-scope-discuss",
        "missing-scope-po",
        "missing-scope-devops",
        "malformed-config",
        "existing-custom-ignore",
        "existing-other-lock",
        "scope-mismatch",
        "malformed-epic-config",
    ),
)
def test_refusal_preserves_every_file_except_literal_housekeeping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    root = _repo(tmp_path, monkeypatch)
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(tmp_path / "agents-home"))
    discuss = ["discuss", "--repo-root", str(root), "--input", "-"]
    raw = json.dumps(_discuss_payload())
    feature = "feature-a"
    pre_lock = case == "invalid-feature-id" or case.startswith("missing-scope-")
    if case == "invalid-feature-id":
        feature = "Bad_ID"
    elif case in {
        "malformed-config",
        "existing-custom-ignore",
        "existing-other-lock",
    }:
        configuration = root / ".nwave/features/feature-a/config.json"
        configuration.parent.mkdir(parents=True, exist_ok=True)
        configuration.write_bytes(b"{not json")
        if case == "existing-custom-ignore":
            ignore = root / IGNORE
            ignore.parent.mkdir(parents=True, exist_ok=True)
            ignore.write_bytes(b"# User policy\r\ncustom-only\r\n")
        elif case == "existing-other-lock":
            lock = root / ".nwave/des/other.lock"
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_bytes(b"existing unrelated lock\r\n")
    elif case == "malformed-epic-config":
        configuration = root / ".nwave/config.json"
        configuration.parent.mkdir(parents=True, exist_ok=True)
        configuration.write_text(
            json.dumps(
                {
                    "documents": {
                        "epic": {
                            "discuss": {"destination": "docs/epic/{epic}/product.md"}
                        }
                    }
                }
            )
        )
        code, response = _des(root, *discuss, "--epic", "orders", stdin=raw)
        assert code == 0, (
            f"WHAT: initial epic DISCUSS failed: {response}\n"
            "WHY: epic refusal must start with a successfully published authority.\n"
            "HOW: complete public epic DISCUSS before submitting malformed override."
        )
        override = root / ".nwave/epics/orders/config.json"
        override.parent.mkdir(parents=True, exist_ok=True)
        override.write_bytes(b"{broken")
    elif case == "scope-mismatch":
        code, response = _des(root, *discuss, "--feature", feature, stdin=raw)
        assert code == 0, (
            f"WHAT: initial feature-a DISCUSS failed: {response}\n"
            "WHY: scope mismatch requires a successfully bound feature authority.\n"
            "HOW: complete the public DISCUSS before observing the refused DESIGN."
        )
    before = _repository_bytes(root)
    if case.startswith("missing-scope-"):
        command = case.removeprefix("missing-scope-")
        code, response = _des(root, command, "--repo-root", str(root), stdin="{}")
    elif case == "scope-mismatch":
        code, response = _des(
            root,
            "design",
            "--repo-root",
            str(root),
            "--value",
            "1",
            "--feature",
            "feature-b",
            "--input",
            "-",
            stdin=json.dumps(MANIFEST),
        )
    elif case == "malformed-epic-config":
        code, response = _des(
            root, *discuss, "--epic", "orders", "--replace-current", stdin=raw
        )
    else:
        code, response = _des(root, *discuss, "--feature", feature, stdin=raw)
    assert code != 0 and "Traceback" not in response, (
        f"WHAT: {case} returned {code}: {response}\n"
        "WHY: this must be an actual public refusal, not success or a setup crash.\n"
        "HOW: refuse the invalid scope/configuration through the public outcome."
    )
    _assert_refusal_preserves_repository(
        before, _repository_bytes(root), pre_lock=pre_lock
    )


@pytest.mark.parametrize(
    "violation",
    (
        "other-lock",
        "handover",
        "surviving-temporary",
        "wrong-ignore",
        "existing-ignore-rewrite",
        "existing-ignore-deletion",
        "pre-lock-ignore",
        "pre-lock-lock",
    ),
)
def test_refusal_guard_distinguishes_forbidden_writes_from_preservation(
    tmp_path: Path, violation: str
) -> None:
    preserved = tmp_path / "README.md"
    preserved.write_bytes(b"preserved\n")
    ignore = tmp_path / IGNORE
    if violation.startswith("existing-ignore-"):
        ignore.parent.mkdir(parents=True, exist_ok=True)
        ignore.write_bytes(b"# Existing custom policy\r\n")
    pre_lock = violation.startswith("pre-lock-")
    before = _repository_bytes(tmp_path)
    _assert_refusal_preserves_repository(
        before, _repository_bytes(tmp_path), pre_lock=pre_lock
    )
    planted = {
        "other-lock": (".nwave/des/other.lock", b"0"),
        "handover": (".nwave/des/handover.json", b"{}"),
        "surviving-temporary": (".nwave/des/.handover-unremoved", b"temporary"),
        "wrong-ignore": (IGNORE, b"not canonical\n"),
        "existing-ignore-rewrite": (IGNORE, runtime_gitignore_content()),
        "pre-lock-ignore": (IGNORE, runtime_gitignore_content()),
        "pre-lock-lock": (LOCK, b"0"),
    }
    if violation == "existing-ignore-deletion":
        ignore.unlink()
    else:
        name, content = planted[violation]
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    with pytest.raises(AssertionError, match="WHAT:"):
        _assert_refusal_preserves_repository(
            before, _repository_bytes(tmp_path), pre_lock=pre_lock
        )


def test_standalone_commit_installs_canonical_ignore_before_opening_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(tmp_path / "agents-home"))
    root = tmp_path / "repository"
    root.mkdir()
    _init_git_repo(root)
    _git(root, "config", "core.excludesFile", "/dev/null")
    (root / "owned.py").write_bytes(b"owned = True\n")
    real_open = builtins.open
    openings: list[tuple[bool, bytes | None, int, str]] = []

    def observed_open(file, *args, **kwargs):
        if isinstance(file, (str, os.PathLike)) and Path(file) == root / LOCK:
            ignore = root / IGNORE
            regular = ignore.is_file() and not ignore.is_symlink()
            checked = subprocess.run(
                ["git", "-C", str(root), "check-ignore", "-v", LOCK],
                capture_output=True,
                text=True,
                check=False,
            )
            openings.append(
                (
                    regular,
                    ignore.read_bytes() if regular else None,
                    checked.returncode,
                    checked.stdout,
                )
            )
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", observed_open)
    code = commit_main(
        [
            "--repo-dir",
            str(root),
            "--owned-paths",
            "owned.py",
            "--step-id",
            "runtime-housekeeping",
            "--message",
            "feat: owned file",
        ]
    )
    assert len(openings) == 1, (
        f"WHAT: observed lock openings were {openings!r}.\n"
        "WHY: this standalone commit must open its literal commit.lock exactly once.\n"
        "HOW: retain one actual lock opening, after installing the runtime ignore."
    )
    regular, content, ignore_code, ignore_output = openings[0]
    assert regular and content == runtime_gitignore_content(), (
        f"WHAT: pre-open runtime ignore regular={regular}, bytes={content!r}.\n"
        "WHY: standalone commit must protect the lock before it exists, without prewarming.\n"
        "HOW: ensure the canonical regular ignore before opening commit.lock."
    )
    assert ignore_code == 0 and ignore_output.split(":", 1)[0] == IGNORE, (
        f"WHAT: pre-open check-ignore exited {ignore_code}: {ignore_output!r}.\n"
        "WHY: real Git must ignore commit.lock using the literal runtime ignore.\n"
        "HOW: install that ignore before opening the lock, not after acquisition."
    )
    committed = set(_git(root, "show", "--name-only", "--format=", "HEAD").splitlines())
    assert code == 0 and committed == {"owned.py"}, (
        f"WHAT: standalone commit exited {code}, committed paths={committed!r}.\n"
        "WHY: the caller's owned file must commit without any .nwave/des runtime path.\n"
        "HOW: retain scoped-index commit and exclude runtime housekeeping from history."
    )


MERGE_OWNED_PATHS = tuple(
    f"{directory}/{prefix}{change}{number}{suffix}"
    for directory, prefix, suffix in (
        ("docs/guide", "", ".md"),
        ("nWave/skills/sample", "", ".md"),
        ("src/sample", "", ".py"),
        ("tests/sample", "test_", ".py"),
    )
    for change in ("a", "m", "d")
    for number in (1, 2)
)


def _write_fixture(root: Path, name: str, content: bytes) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _version_bytes(name: str, version: str) -> bytes:
    return f"{name}: {version}\n".encode()


def _blob_identity(root: Path, content: bytes, *, write: bool = False) -> str:
    return (
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "hash-object",
                *(["-w"] if write else []),
                "--stdin",
            ],
            input=content,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )


def _stage_foreign_blob(
    root: Path, name: str, mode: str, content: bytes
) -> tuple[str, str, str]:
    blob = _blob_identity(root, content, write=True)
    _git(root, "update-index", "--cacheinfo", mode, blob, name)
    return mode, blob, "0"


def _committed_tree(root: Path, ref: str) -> dict[str, tuple[str, str, str]]:
    entries = {}
    for line in _git(root, "ls-tree", "-r", "--full-tree", ref).splitlines():
        metadata, name = line.split("\t", 1)
        mode, kind, blob = metadata.split()
        entries[name] = mode, kind, blob
    return entries


def _shared_index(root: Path) -> dict[str, tuple[str, str, str]]:
    entries = {}
    for line in _git(root, "ls-files", "--stage").splitlines():
        metadata, name = line.split("\t", 1)
        mode, blob, stage = metadata.split()
        entries[name] = mode, blob, stage
    return entries


def _scoped_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for variable, directory in (
        ("HOME", "home"),
        ("XDG_CONFIG_HOME", "xdg"),
        ("NWAVE_AGENTS_HOME", "agents-home"),
    ):
        monkeypatch.setenv(variable, str(tmp_path / directory))
    root = tmp_path / "scoped-repository"
    root.mkdir()
    _init_git_repo(root)
    _git(root, "branch", "-M", "main")
    _git(root, "config", "core.excludesFile", "/dev/null")
    return root


def _install_ignore_style(root: Path, style: str) -> str:
    if style == "root-style":
        _write_fixture(root, ".gitignore", b".nwave/*\n!.nwave/config.json\n")
        _git(root, "add", ".gitignore")
        _git(root, "commit", "--only", ".gitignore", "-m", "Declare root ignore")
        return ".gitignore"
    _write_fixture(root, ".nwave/.gitignore", nested_gitignore_content().encode())
    _git(root, "commit", "--allow-empty", "-m", "Declare parent ignore start")
    return ".nwave/.gitignore"


def _scoped_start(root: Path, ignore_source: str) -> dict:
    ignored = _git(root, "check-ignore", "--no-index", "-v", ".nwave/des")
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    assert ignored.split(":", 1)[0] == ignore_source, (
        f"WHAT: runtime directory ignore source is {ignored!r}.\n"
        "WHY: this observation requires the declared root or parent ignored-directory state.\n"
        "HOW: construct that explicit ignore rule before invoking public des commit."
    )
    assert not any(line.startswith("?? .nwave/des/") for line in status.splitlines()), (
        f"WHAT: ignored runtime appears as untracked work in {status!r}.\n"
        "WHY: the scenario must actually exercise ignored runtime, not a traversable control.\n"
        "HOW: keep the declared directory ignore effective."
    )
    merge_head = root / ".git/MERGE_HEAD"
    return {
        "head": _git(root, "rev-parse", "HEAD").strip(),
        "parents": _git(root, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:],
        "merge_head": merge_head.read_text().strip() if merge_head.exists() else None,
        "tree": _committed_tree(root, "HEAD"),
        "index": _shared_index(root),
        "index_lines": _git(root, "ls-files", "--stage"),
        "files": _repository_bytes(root),
        "status": status,
        "ignore": ignored,
    }


def _public_scoped_commit(
    root: Path,
    owned: tuple[str, ...],
    step: str,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[int, str]:
    real_run = subprocess.run
    commands: list[tuple[str, ...]] = []

    def recorded_run(*args, **kwargs):
        argv = args[0] if args else kwargs.get("args")
        if isinstance(argv, (list, tuple)) and argv and Path(argv[0]).name == "git":
            commands.append(tuple(str(argument) for argument in argv))
        return real_run(*args, **kwargs)

    with monkeypatch.context() as recording:
        recording.setattr(subprocess, "run", recorded_run)
        code, response = _des(
            root,
            "commit",
            "--repo-dir",
            str(root),
            "--owned-paths",
            *owned,
            "--step-id",
            step,
            "--message",
            message,
        )
    staging = [argv for argv in commands if "add" in argv]
    staging_options = [
        argv[argv.index("add") + 1 : argv.index("--") if "--" in argv else len(argv)]
        for argv in staging
    ]
    assert staging and not any(
        option in {"--force", "--ignore-errors"}
        or option.startswith(("--force=", "--ignore-errors="))
        or (
            option.startswith("-") and not option.startswith("--") and "f" in option[1:]
        )
        for options in staging_options
        for option in options
    ), (
        f"WHAT: actual staging commands were {staging!r}.\n"
        "WHY: scoped commits must use ordinary non-force Git add, never suppress errors.\n"
        "HOW: correct runtime exclusion while preserving honest staging refusal."
    )
    assert not any(
        "update-index" in argv
        or any("advice." in argument.lower() for argument in argv)
        for argv in commands
    ), (
        f"WHAT: actual public-invocation Git commands were {commands!r}.\n"
        "WHY: content must not be staged through update-index or advice overrides.\n"
        "HOW: use ordinary Git add without hiding Git's refusal advice."
    )
    return code, response


def _assert_scoped_success(
    root: Path, code: int, response: str, step: str, parents: list[str]
) -> str:
    assert code == 0, (
        f"WHAT: public scoped commit exited {code}: {response}\n"
        "WHY: ignored runtime must not refuse an owned non-runtime commit.\n"
        "HOW: correct the runtime subtree exclusion without force staging."
    )
    head = _git(root, "rev-parse", "HEAD").strip()
    rows = dict(line.split(": ", 1) for line in response.splitlines() if ": " in line)
    assert (
        rows.get("DELIVERY-OUTCOME") == "Success"
        and rows.get("COMMIT") == head
        and rows.get("STEP-ID") == step
    ), (
        f"WHAT: scoped commit terminal facts={rows!r}, actual HEAD={head}.\n"
        "WHY: the public result must identify the actual committed state and caller's step.\n"
        "HOW: emit truthful Success, COMMIT and STEP-ID facts."
    )
    actual_parents = _git(root, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
    assert actual_parents == parents, (
        f"WHAT: commit parents={actual_parents!r}, expected={parents!r}.\n"
        "WHY: scoped commit must preserve starting HEAD and ordered merge ancestry.\n"
        "HOW: complete the real pending merge with both parents in order."
    )
    return head


@pytest.mark.parametrize("style", ("root-style", "parent-style"))
def test_scoped_commit_completes_pending_merge_with_ignored_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, style: str
) -> None:
    root = _scoped_repository(tmp_path, monkeypatch)
    base_bytes = {
        ".nwave/config.json": b'{"path":".nwave/config.json","version":"C0"}\n',
        "foreign/staged.txt": _version_bytes("foreign/staged.txt", "F0"),
    }
    changed = {}
    expected_status = {}
    for name in MERGE_OWNED_PATHS:
        filename = Path(name).name.removeprefix("test_")
        action = filename[0]
        expected_status[name] = {"a": "A", "m": "M", "d": "D"}[action]
        if action != "a":
            base_bytes[name] = _version_bytes(name, "base")
        if action != "d":
            changed[name] = _version_bytes(name, "side")
    for name, content in base_bytes.items():
        _write_fixture(root, name, content)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "Seed merge inputs before ignore")
    ignore_source = _install_ignore_style(root, style)
    base = _git(root, "rev-parse", "HEAD").strip()
    _git(root, "checkout", "-b", "side", base)
    for name in MERGE_OWNED_PATHS:
        if name in changed:
            _write_fixture(root, name, changed[name])
        else:
            (root / name).unlink()
    _git(root, "add", "-A", "--", *MERGE_OWNED_PATHS)
    _git(root, "commit", "-m", "Side adds modifies and deletes")
    side = _git(root, "rev-parse", "HEAD").strip()
    _git(root, "checkout", "main")
    _write_fixture(
        root, "notes/main-only.txt", _version_bytes("notes/main-only.txt", "M")
    )
    _git(root, "add", "notes/main-only.txt")
    _git(root, "commit", "-m", "Main independent change")
    main = _git(root, "rev-parse", "HEAD").strip()
    _git(root, "merge", "--no-ff", "--no-commit", "side")
    foreign = "foreign/staged.txt"
    staged_bytes = _version_bytes(foreign, "F1")
    foreign_entry = _stage_foreign_blob(root, foreign, "100755", staged_bytes)
    _write_fixture(root, foreign, _version_bytes(foreign, "F2"))
    runtime = ".nwave/des/session.json"
    _write_fixture(root, runtime, _version_bytes(runtime, "session"))
    before = _scoped_start(root, ignore_source)
    assert before["head"] == main and before["merge_head"] == side, (
        f"WHAT: pending merge HEAD={before['head']}, MERGE_HEAD={before['merge_head']}.\n"
        "WHY: the observation requires the constructed two-parent pending merge.\n"
        "HOW: retain main HEAD and side MERGE_HEAD before the public invocation."
    )
    expected_tree = dict(before["tree"])
    for name in MERGE_OWNED_PATHS:
        if name in changed:
            expected_tree[name] = "100644", "blob", _blob_identity(root, changed[name])
        else:
            expected_tree.pop(name)
    expected_index = dict(before["index"])
    for name in MERGE_OWNED_PATHS:
        if name in expected_tree:
            mode, _kind, blob = expected_tree[name]
            expected_index[name] = mode, blob, "0"
        else:
            expected_index.pop(name, None)
    code, response = _public_scoped_commit(
        root, MERGE_OWNED_PATHS, "merge-24", "merge: integrate side", monkeypatch
    )
    _assert_scoped_success(root, code, response, "merge-24", [main, side])
    assert not (root / ".git/MERGE_HEAD").exists(), (
        "WHAT: MERGE_HEAD remains after scoped commit. "
        "WHY: successful commit must complete the pending merge. "
        "HOW: record both parents and finish Git's merge state."
    )
    assert _committed_tree(root, "HEAD") == expected_tree, (
        "WHAT: full committed tree differs from starting HEAD plus declared owned bytes. "
        "WHY: side changes must land without foreign or runtime changes. "
        "HOW: stage exactly the owned add/modify/delete population outside runtime."
    )
    actual_status = {
        name: status
        for status, name in (
            line.split("\t", 1)
            for line in _git(root, "diff", "--name-status", main, "HEAD").splitlines()
        )
    }
    assert actual_status == expected_status, (
        f"WHAT: owned delta={actual_status!r}, expected population={expected_status!r}. "
        "WHY: all 24 paths, partitioned as 8 additions, 8 modifications and 8 deletions, "
        "must be conserved with no unrelated path. "
        "HOW: commit exactly the constructed owned population."
    )
    assert _git(root, "log", "-1", "--format=%B").strip() == (
        "merge: integrate side\n\nStep-Id: merge-24"
    ), (
        "WHAT: merge commit message or trailers differ from the public request. "
        "WHY: exactly one caller Step-Id trailer must identify this commit. "
        "HOW: preserve the message and append that one trailer without extras."
    )
    assert _shared_index(root) == expected_index, (
        "WHAT: shared index differs from the declared owned resync and foreign preservation. "
        "WHY: every foreign stage/mode/blob must remain exact. "
        "HOW: resync only owned non-runtime entries."
    )
    assert (
        _shared_index(root)[foreign] == foreign_entry
        and _git(root, "cat-file", "-p", foreign_entry[1]).encode() == staged_bytes
        and (root / foreign).read_bytes() == before["files"][foreign]
    ), (
        "WHAT: foreign staged mode/blob/recoverable bytes or working bytes changed. "
        "WHY: this caller does not own the foreign staged source. "
        "HOW: leave foreign index and working bytes untouched."
    )
    assert not _git(
        root, "diff", "--name-only", "--", *MERGE_OWNED_PATHS
    ).strip() and not (
        _git(root, "diff", "--cached", "--name-only", "--", *MERGE_OWNED_PATHS).strip()
    ), (
        "WHAT: an owned merge path remains dirty after commit. "
        "WHY: committed owned changes must be resynced to the new HEAD. "
        "HOW: resync the owned non-runtime population."
    )
    _assert_refusal_preserves_repository(before["files"], _repository_bytes(root))
    assert runtime not in _shared_index(root) and not any(
        line.startswith("?? .nwave/des/")
        for line in _git(
            root, "status", "--porcelain", "--untracked-files=all"
        ).splitlines()
    ), (
        "WHAT: session runtime became tracked or visible as untracked work. "
        "WHY: runtime must remain outside the commit and shared index. "
        "HOW: retain runtime ignoring and exact subtree exclusion."
    )


def test_broad_scoped_commit_preserves_legacy_and_foreign_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _scoped_repository(tmp_path, monkeypatch)
    legacy, retired, fresh = (
        ".nwave/des/legacy.json",
        ".nwave/des/retired.json",
        ".nwave/des/fresh.json",
    )
    original = {
        ".nwave/config.json": b'{"path":".nwave/config.json","version":"C0"}\n',
        "src/app.py": _version_bytes("src/app.py", "A0"),
        legacy: _version_bytes(legacy, "L0"),
        retired: _version_bytes(retired, "R0"),
    }
    for name, content in original.items():
        _write_fixture(root, name, content)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "Seed historical runtime before ignore")
    staged_bytes = _version_bytes(legacy, "L1")
    staged_entry = _stage_foreign_blob(root, legacy, "100644", staged_bytes)
    ignore_source = _install_ignore_style(root, "root-style")
    changed = {
        ".nwave/config.json": b'{"path":".nwave/config.json","version":"C1"}\n',
        "src/app.py": _version_bytes("src/app.py", "A1"),
    }
    for name, content in changed.items():
        _write_fixture(root, name, content)
    _write_fixture(root, legacy, _version_bytes(legacy, "L2"))
    (root / retired).unlink()
    _write_fixture(root, fresh, _version_bytes(fresh, "fresh"))
    before = _scoped_start(root, ignore_source)
    expected_tree = dict(before["tree"])
    expected_index = dict(before["index"])
    for name, content in changed.items():
        blob = _blob_identity(root, content)
        expected_tree[name] = "100644", "blob", blob
        expected_index[name] = "100644", blob, "0"
    code, response = _public_scoped_commit(
        root, (".",), "broad-legacy", "feat: source and config", monkeypatch
    )
    _assert_scoped_success(root, code, response, "broad-legacy", [before["head"]])
    assert _committed_tree(root, "HEAD") == expected_tree, (
        "WHAT: broad commit changed historical runtime or omitted owned config/source. "
        "WHY: runtime must retain starting HEAD modes/blobs while owned work lands. "
        "HOW: exclude precisely runtime from private-index staging."
    )
    assert set(
        _git(root, "diff", "--name-only", before["head"], "HEAD").splitlines()
    ) == set(changed), (
        "WHAT: broad commit delta differs from the declared source/config population. "
        "WHY: legacy deletion, new runtime and runtime modifications are not owned work. "
        "HOW: commit only non-runtime changes."
    )
    assert (
        _shared_index(root) == expected_index
        and _shared_index(root)[legacy] == staged_entry
    ), (
        "WHAT: broad resync changed a foreign runtime index entry. "
        "WHY: staged legacy bytes and retained retired entry must survive broad ownership. "
        "HOW: apply the same runtime exclusion to shared-index resync."
    )
    assert _git(root, "cat-file", "-p", staged_entry[1]).encode() == staged_bytes, (
        "WHAT: foreign staged runtime bytes cannot be recovered unchanged. "
        "WHY: mode/blob identity must retain the caller-external staged content. "
        "HOW: preserve the foreign staged blob."
    )
    assert not _git(root, "diff", "--name-only", "--", *changed).strip() and not (
        _git(root, "diff", "--cached", "--name-only", "--", *changed).strip()
    ), (
        "WHAT: owned source/config remains dirty. "
        "WHY: owned committed work must be clean without resetting foreign runtime. "
        "HOW: resync only owned non-runtime entries."
    )
    _assert_refusal_preserves_repository(before["files"], _repository_bytes(root))


def test_runtime_only_broad_commit_refuses_without_losing_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _scoped_repository(tmp_path, monkeypatch)
    legacy = ".nwave/des/legacy.json"
    _write_fixture(
        root, ".nwave/config.json", b'{"path":".nwave/config.json","version":"C0"}\n'
    )
    _write_fixture(root, legacy, _version_bytes(legacy, "L0"))
    _git(root, "add", ".")
    _git(root, "commit", "-m", "Seed runtime-only start before ignore")
    ignore_source = _install_ignore_style(root, "parent-style")
    _write_fixture(root, legacy, _version_bytes(legacy, "L2"))
    _write_fixture(
        root, ".nwave/des/fresh.json", _version_bytes(".nwave/des/fresh.json", "fresh")
    )
    before = _scoped_start(root, ignore_source)
    code, response = _public_scoped_commit(
        root, (".",), "runtime-only", "chore: runtime only", monkeypatch
    )
    rows = dict(line.split(": ", 1) for line in response.splitlines() if ": " in line)
    assert (
        code == 1
        and rows.get("DELIVERY-OUTCOME") == "Refusal"
        and rows.get("WHAT") == "NothingToCommit"
    ), (
        f"WHAT: runtime-only broad commit exited {code}: {response}\n"
        "WHY: runtime alone is not committable owned work. "
        "HOW: exclude runtime and retain the explicit NothingToCommit refusal."
    )
    assert (
        _git(root, "rev-parse", "HEAD").strip() == before["head"]
        and _git(root, "ls-files", "--stage") == before["index_lines"]
        and _committed_tree(root, "HEAD") == before["tree"]
    ), (
        "WHAT: runtime-only refusal changed HEAD, committed tree or shared index. "
        "WHY: no non-runtime work exists to commit or resync. "
        "HOW: refuse NothingToCommit without changing Git state."
    )
    _assert_refusal_preserves_repository(before["files"], _repository_bytes(root))
