"""Six acceptance tests for public-wheel DES staging."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import pytest
import yaml
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import InvalidWheelFilename, parse_wheel_filename


pytestmark = [pytest.mark.acceptance, pytest.mark.slice_01]

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "scripts" / "release" / "stage_public_wheel_des.py"
E2E_FIXTURE = REPO_ROOT / "tests" / "e2e" / "conftest.py"
STAGE_NAMES = ("lib/python/des", "lib/nwave-runtime/des")
JOURNAL = ".nwave-wheel-lib.journal.json"
TEMPORARY = ".nwave-wheel-lib.tmp"
BACKUP = ".nwave-wheel-lib.backup"
CANDIDATE_VERSION = "0.0.0.dev0"
REPARSE_ATTRIBUTE = 0x400


@dataclass(frozen=True)
class RecoveryTopology:
    state: str
    old_present: bool
    window: str


@dataclass(frozen=True)
class AssembledCandidate:
    sandbox: Path
    wheel: Path
    source_manifest: dict[str, bytes]
    version: str
    digest: str


@dataclass(frozen=True)
class ShellCommand:
    step_index: int
    command_index: int
    argv: tuple[str, ...]


def _require(
    condition: bool,
    *,
    what: str,
    why: str = "assembled release contract mismatch",
    how: str = "implement the locked feature-delta contract",
) -> None:
    if not condition:
        raise AssertionError(f"WHAT: {what}\nWHY: {why}\nHOW: {how}")


_PYTHONPATH_LITERAL_RE = re.compile(r"PYTHONPATH=(\S+)")


def _configured_runtime_dir(command: str, *, host: str) -> Path:
    """Extract the PYTHONPATH literal a generated hook command points at.

    Hook commands are rendered from HOOK_COMMAND_TEMPLATE
    ("PYTHONPATH={lib_path} {python_path} -m ..."), so the runtime
    directory a host will actually import from is always the literal
    immediately following ``PYTHONPATH=``. That literal may itself be
    unexpanded (e.g. Claude's ``$HOME``-relative form, per the
    target-machine-portability convention) -- callers on that path
    ``str()`` this return, substitute the token, and re-wrap in ``Path``;
    every other caller uses the returned ``Path`` as-is.
    """
    match = _PYTHONPATH_LITERAL_RE.search(command)
    _require(
        match is not None,
        what=f"{host} hook command has no PYTHONPATH literal: {command!r}",
        why="the installed hook must point at a concrete runtime directory",
        how="verify HOOK_COMMAND_TEMPLATE still renders 'PYTHONPATH=<dir> ...'",
    )
    assert match is not None  # narrows for type-checkers; _require already asserted
    return Path(match.group(1))


def _require_hook_runtime(runtime_dir: Path, *, host: str) -> None:
    """Fail loud if a hook's declared runtime directory is a dangling reference.

    A hook that fires successfully today can still point at a runtime
    directory nothing installed -- silent until the day the host's
    working directory changes. This closes that gap by requiring the
    directory, and a real `des` package inside it, to exist on disk.
    """
    _require(
        runtime_dir.is_dir(),
        what=f"{host} hook runtime directory does not exist: {runtime_dir}",
        why="a hook command must point at an actually-installed runtime",
        how="verify the install step that writes this hook also provisions this path",
    )
    _require(
        (runtime_dir / "des" / "__init__.py").is_file(),
        what=f"{host} hook runtime directory has no des package: {runtime_dir}",
        why="a runtime dir without des/__init__.py cannot serve the hook it is named in",
        how="verify the runtime provisioning step copies/links the des package here",
    )


def _manifest(root: Path) -> dict[str, bytes]:
    assert root.is_dir(), f"manifest population absent: {root}"
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _manifest_digest(manifest: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative, payload in sorted(manifest.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def _zip_manifest(wheel: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        duplicates = sorted(
            name for name, count in Counter(names).items() if count != 1
        )
        assert not duplicates, f"non-unique wheel members: {duplicates}"
        return {name: archive.read(name) for name in names if not name.endswith("/")}


def _lock_reference(line: str) -> str | None:
    requirement_text = re.split(r"\s+--hash(?:=|\s)", line, maxsplit=1)[0].strip()
    try:
        requirement = Requirement(requirement_text)
    except InvalidRequirement:
        return requirement_text.split(maxsplit=1)[0] if requirement_text else None
    return requirement.url


def _local_lock_path(reference: str) -> Path | None:
    parsed = urlsplit(reference)
    if parsed.scheme == "file":
        raw_path = unquote(parsed.path)
    elif parsed.scheme:
        return None
    else:
        raw_path = reference
    portable_path = raw_path.replace("\\", "/")
    if not (
        "/" in portable_path or portable_path.endswith((".whl", ".tar.gz", ".zip"))
    ):
        return None
    return Path(portable_path)


def _is_indirection(path: Path, metadata: os.stat_result) -> bool:
    is_junction = bool(getattr(path, "is_junction", lambda: False)())
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return (
        stat.S_ISLNK(metadata.st_mode)
        or is_junction
        or bool(attributes & REPARSE_ATTRIBUTE)
    )


def _path_snapshot(path: Path) -> tuple[Any, ...]:
    """Snapshot without following filesystem indirection."""
    if not os.path.lexists(path):
        return ("absent",)
    metadata = os.lstat(path)
    if _is_indirection(path, metadata):
        try:
            target = str(path.readlink())
        except OSError:
            target = "<opaque-reparse-target>"
        return ("indirection", stat.S_IFMT(metadata.st_mode), target)
    if stat.S_ISREG(metadata.st_mode):
        return ("file", path.read_bytes())
    if stat.S_ISDIR(metadata.st_mode):
        return (
            "directory",
            tuple(
                (entry.name, _path_snapshot(Path(entry.path)))
                for entry in sorted(os.scandir(path), key=lambda item: item.name)
            ),
        )
    return ("other", stat.S_IFMT(metadata.st_mode), metadata.st_size)


def _protected_snapshot(
    root: Path, extra: tuple[Path, ...] = ()
) -> dict[str, tuple[Any, ...]]:
    protected = (
        root / "dist",
        root / "lib",
        root / TEMPORARY,
        root / BACKUP,
        root / JOURNAL,
        *extra,
    )
    return {str(path): _path_snapshot(path) for path in protected}


def _copy_population(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=True)


def _make_complete_stage(
    source: Path,
    destination: Path,
    *,
    old: bool,
) -> tuple[dict[str, bytes], dict[str, bytes]]:
    _copy_population(source, destination / "python" / "des")
    _copy_population(source, destination / "nwave-runtime" / "des")
    if old:
        for population in (
            destination / "python" / "des",
            destination / "nwave-runtime" / "des",
        ):
            (population / "previous_release.py").write_text(
                "old = True\n",
                encoding="utf-8",
            )
    return _manifest(destination), _manifest(destination / "python" / "des")


def _run(
    command: list[str] | str,
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 600,
    input_text: str | None = None,
    shell: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        input=input_text,
        shell=shell,
    )


def _sandbox(tmp_path: Path) -> Path:
    root = tmp_path / "candidate"
    for name in ("nWave", "scripts", "src", "nwave_ai", "schemas"):
        shutil.copytree(REPO_ROOT / name, root / name, symlinks=True)
    for name in ("pyproject.toml", "README.md", "LICENSE"):
        shutil.copy2(REPO_ROOT / name, root / name)
    return root


def _clone_sandbox(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination, symlinks=True)
    return destination


def _stamp_module_version(root: Path, version: str) -> None:
    module_init = root / "nwave_ai" / "__init__.py"
    original = module_init.read_text(encoding="utf-8")
    changed, replacements = re.subn(
        r'(?m)^__version__ = ".*"$',
        f'__version__ = "{version}"',
        original,
    )
    assert replacements == 1, f"module version assignments: {replacements}"
    module_init.write_text(changed, encoding="utf-8")


def _build_des(root: Path) -> Path:
    built = _run([sys.executable, "scripts/build_dist.py"], cwd=root)
    assert built.returncode == 0, built.stderr or built.stdout
    return root / "dist" / "lib" / "python" / "des"


def _patch_stamp_and_build_des(root: Path, version: str = CANDIDATE_VERSION) -> Path:
    patched = _run(
        [
            sys.executable,
            "scripts/release/patch_pyproject.py",
            "--input",
            "pyproject.toml",
            "--output",
            "pyproject.toml",
            "--target-name",
            "nwave-ai",
            "--target-version",
            version,
        ],
        cwd=root,
    )
    assert patched.returncode == 0, patched.stderr or patched.stdout
    _stamp_module_version(root, version)
    return _build_des(root)


def _shared_prepared_seed(tmp_path_factory: Any) -> Path:
    """The one immutable patched+built seed the mutation-driving tests clone from.

    `_patch_stamp_and_build_des` is expensive: it copies ~23MB of source
    (`_sandbox`), runs `patch_pyproject.py`, and builds DES. The tests that
    call it directly (dual-stage indirection refusal, invalid-source
    recovery, durable-recovery-topology idempotency) each need their OWN
    independent, freely-mutable copy -- but the pre-mutation state is
    identical across all of them. Build it here ONCE (cached the same way
    `_assembled_candidate` caches its own expensive build, via an attribute
    on the session-scoped `tmp_path_factory`) and let each test clone
    (a cheap file copy) instead of repeating the patch+build from scratch.
    """
    cache_name = "_release_staging_ssot_prepared_seed"
    cached = getattr(tmp_path_factory, cache_name, None)
    if cached is not None:
        return cached

    seed = _sandbox(tmp_path_factory.mktemp("release_staging_prepared_seed"))
    _patch_stamp_and_build_des(seed)
    setattr(tmp_path_factory, cache_name, seed)
    return seed


def _build_wheel(root: Path, output_name: str) -> Path:
    output = root / output_name
    built = _run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(output),
        ],
        cwd=root,
    )
    assert built.returncode == 0, built.stderr or built.stdout
    wheels = tuple(output.glob("nwave_ai-*.whl"))
    assert len(wheels) == 1, f"candidate wheel count: {len(wheels)}"
    return wheels[0]


def _run_stage(root: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            sys.executable,
            str(root / "scripts" / "release" / "stage_public_wheel_des.py"),
            "--project-root",
            str(root),
            "--cleanup-dist",
        ],
        cwd=root,
    )


def _require_driving_port() -> None:
    assert HELPER.is_file(), "missing scripts/release/stage_public_wheel_des.py"


def _create_indirection(
    *,
    kind: str,
    link: Path,
    target: Path,
    directory: bool,
) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if kind == "symlink":
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError as exc:
            pytest.fail(
                f"required symlink unsupported; explicit failure: {link}: {exc}"
            )
        return

    assert os.name == "nt" and directory, f"unsupported junction case: {link}"
    command = ["cmd.exe", "/c", "mklink", "/J", str(link), str(target)]
    created = subprocess.run(command, capture_output=True, text=True, check=False)
    if created.returncode != 0 or not os.path.lexists(link):
        pytest.fail(
            "required junction unsupported; explicit failure: "
            f"{created.stdout}{created.stderr}"
        )


def _indirection_kinds() -> tuple[str, ...]:
    return ("symlink", "junction") if os.name == "nt" else ("symlink",)


def _install_indirection_case(root: Path, surface: str, kind: str) -> tuple[Path, ...]:
    source = root / "dist" / "lib" / "python" / "des"
    target = root / f".at-{surface}-{kind}-target"

    if surface == "project-root":
        target = root.with_name(f"{root.name}-{kind}-target")
        root.rename(target)
        _create_indirection(kind=kind, link=root, target=target, directory=True)
        return (root, target)
    elif surface in {"dist", "dist-lib", "dist-lib-python"}:
        original = {
            "dist": root / "dist",
            "dist-lib": root / "dist" / "lib",
            "dist-lib-python": root / "dist" / "lib" / "python",
        }[surface]
        original.rename(target)
        _create_indirection(kind=kind, link=original, target=target, directory=True)
    elif surface == "source":
        source.rename(target)
        _create_indirection(kind=kind, link=source, target=target, directory=True)
    elif surface == "source-member":
        if kind == "junction":
            target.mkdir()
            (target / "escaped.py").write_text("escaped = True\n", encoding="utf-8")
            _create_indirection(
                kind=kind,
                link=source / "escaped-dir",
                target=target,
                directory=True,
            )
        else:
            target.write_text("escaped = True\n", encoding="utf-8")
            _create_indirection(
                kind=kind,
                link=source / "escaped.py",
                target=target,
                directory=False,
            )
    elif surface in {"lib", "temporary", "backup"}:
        target.mkdir()
        (target / "evidence.txt").write_text("do not mutate\n", encoding="utf-8")
        link = {
            "lib": root / "lib",
            "temporary": root / TEMPORARY,
            "backup": root / BACKUP,
        }[surface]
        _create_indirection(kind=kind, link=link, target=target, directory=True)
    elif surface in {"lib-member", "temporary-member", "backup-member"}:
        parent = {
            "lib-member": root / "lib",
            "temporary-member": root / TEMPORARY,
            "backup-member": root / BACKUP,
        }[surface]
        _make_complete_stage(source, parent, old=True)
        target.mkdir()
        (target / "escaped.py").write_text("escaped = True\n", encoding="utf-8")
        _create_indirection(
            kind=kind,
            link=parent / "foreign",
            target=target,
            directory=True,
        )
    elif surface == "journal":
        if kind == "junction":
            target.mkdir()
            _create_indirection(
                kind=kind,
                link=root / JOURNAL,
                target=target,
                directory=True,
            )
        else:
            target.write_text("{}\n", encoding="utf-8")
            _create_indirection(
                kind=kind,
                link=root / JOURNAL,
                target=target,
                directory=False,
            )
    elif surface == "source-destination-alias":
        _create_indirection(
            kind=kind,
            link=root / "lib",
            target=root / "dist" / "lib",
            directory=True,
        )
        target = root / "dist" / "lib"
    else:
        raise AssertionError(f"unknown indirection surface: {surface}")
    return (target,)


def _write_journal(
    root: Path,
    *,
    state: str,
    old_present: bool,
    source_manifest: dict[str, bytes],
) -> None:
    digest = _manifest_digest(source_manifest)
    journal = {
        "schema_version": 1,
        "state": state,
        "old_present": old_present,
        "source_manifest_sha256": digest,
        "new_manifest_sha256": digest,
        "paths": {
            "candidate": "lib",
            "temporary": TEMPORARY,
            "backup": BACKUP,
        },
    }
    (root / JOURNAL).write_text(json.dumps(journal), encoding="utf-8")


def _seed_recovery_topology(
    root: Path,
    source: Path,
    topology: RecoveryTopology,
) -> tuple[dict[str, bytes] | None, dict[str, bytes]]:
    candidate = root / "lib"
    temporary = root / TEMPORARY
    backup = root / BACKUP
    new_candidate, source_manifest = _make_complete_stage(
        source,
        temporary,
        old=False,
    )
    old_candidate: dict[str, bytes] | None = None
    if topology.old_present:
        old_candidate, _ = _make_complete_stage(source, candidate, old=True)

    if topology.state == "PREPARED":
        if topology.window == "after-old-rename":
            assert topology.old_present, "after-old-rename requires old_present"
            candidate.rename(backup)
    elif topology.state == "OLD_MOVED":
        if topology.old_present:
            candidate.rename(backup)
        if topology.window == "after-new-rename":
            temporary.rename(candidate)
    elif topology.state in {"NEW_PROMOTED", "COMMITTED"}:
        if topology.old_present:
            candidate.rename(backup)
        temporary.rename(candidate)
        if topology.state == "COMMITTED" and topology.window == "backup-removed":
            assert topology.old_present, "backup-removed requires old_present"
            shutil.rmtree(backup)
    else:
        raise AssertionError(f"unsupported recovery state: {topology.state}")

    _write_journal(
        root,
        state=topology.state,
        old_present=topology.old_present,
        source_manifest=source_manifest,
    )
    return old_candidate, new_candidate


def _logical_shell_segments(script: str) -> tuple[tuple[str, ...], ...]:
    logical = script.replace("\\\n", " ")
    segments: list[tuple[str, ...]] = []
    for line in logical.splitlines():
        lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        current: list[str] = []
        for token in lexer:
            if token and all(character in ";&|" for character in token):
                if current:
                    segments.append(tuple(current))
                    current = []
            else:
                current.append(token)
        if current:
            segments.append(tuple(current))
    return tuple(segments)


def _workflow_commands(path: Path) -> tuple[ShellCommand, ...]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps = data["jobs"]["pypi-publish"]["steps"]
    commands: list[ShellCommand] = []
    for step_index, step in enumerate(steps):
        for command_index, argv in enumerate(
            _logical_shell_segments(str(step.get("run", "")))
        ):
            commands.append(ShellCommand(step_index, command_index, argv))
    return tuple(commands)


def _has_script(command: ShellCommand, script: str) -> bool:
    return script in command.argv


def _is_wheel_build(command: ShellCommand) -> bool:
    argv = command.argv
    return "-m" in argv and "build" in argv and "--wheel" in argv


def _github_refs(tokens: tuple[str, ...]) -> tuple[str, ...]:
    joined = " ".join(tokens)
    return tuple(
        re.sub(r"\s+", "", match) for match in re.findall(r"\$\{\{[^}]+\}\}", joined)
    )


def _sed_replacement(token: str) -> str | None:
    if len(token) < 4 or not token.startswith("s"):
        return None
    parts = token.split(token[1])
    return parts[2] if len(parts) >= 4 and "__version__" in parts[1] else None


def _stamp_version_value(token: str) -> str | None:
    replacement = _sed_replacement(token)
    if replacement is None:
        return None
    match = re.fullmatch(r"""__version__\s*=\s*(["'])(.*?)\1""", replacement)
    return match.group(2) if match is not None else None


def _normalized_version_value(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _command_name(argv: tuple[str, ...]) -> str:
    ignored = {"if", "then", "do", "sudo", "command"}
    for token in argv:
        lowered = token.lower()
        if lowered in ignored or ("=" in token and not token.startswith(("/", "./"))):
            continue
        return Path(lowered).name
    return ""


def _python_inline_fs_calls(argv: tuple[str, ...]) -> tuple[str, ...]:
    if "-c" not in argv:
        return ()
    index = argv.index("-c")
    if index + 1 >= len(argv):
        return ()
    try:
        tree = ast.parse(argv[index + 1])
    except SyntaxError:
        return ("unparseable-python-inline",)
    forbidden = {"copy", "copy2", "copyfile", "copytree", "move", "rmtree", "unlink"}
    return tuple(
        sorted(
            {
                node.func.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in forbidden
            }
        )
    )


def _forbidden_choreography(command: ShellCommand) -> tuple[str, ...]:
    shell_families = {
        "cp",
        "install",
        "mkdir",
        "mv",
        "remove-item",
        "copy-item",
        "move-item",
        "new-item",
        "rm",
        "rmdir",
        "rsync",
    }
    findings: list[str] = []
    name = _command_name(command.argv)
    if name in shell_families:
        findings.append(name)
    if name.startswith(("$", "%")):
        findings.append("indirect-shell-command")
    for token in command.argv:
        lowered = token.lower()
        assigned = lowered.partition("=")[2] if "=" in lowered else ""
        if assigned in shell_families:
            findings.append(lowered)
    function_definition = any(
        token in {"function", "{"} or "()" in token for token in command.argv
    )
    if function_definition:
        findings.extend(
            token.lower() for token in command.argv if token.lower() in shell_families
        )
    if name in {"bash", "sh", "zsh", "pwsh", "powershell"} and "-c" in command.argv:
        payload = command.argv[command.argv.index("-c") + 1]
        for nested in _logical_shell_segments(payload):
            nested_command = ShellCommand(
                command.step_index,
                command.command_index,
                nested,
            )
            findings.extend(_forbidden_choreography(nested_command))
    findings.extend(_python_inline_fs_calls(command.argv))
    return tuple(findings)


def _workflow_contract_violations(path: Path) -> list[str]:
    commands = _workflow_commands(path)
    categories = {
        "patch": tuple(
            command
            for command in commands
            if _has_script(command, "scripts/release/patch_pyproject.py")
        ),
        "stamp": tuple(
            command for command in commands if "nwave_ai/__init__.py" in command.argv
        ),
        "build_des": tuple(
            command
            for command in commands
            if _has_script(command, "scripts/build_dist.py")
        ),
        "stage": tuple(
            command
            for command in commands
            if _has_script(command, "scripts/release/stage_public_wheel_des.py")
        ),
        "wheel": tuple(command for command in commands if _is_wheel_build(command)),
    }
    violations: list[str] = []
    for name, nodes in categories.items():
        if len(nodes) != 1:
            violations.append(
                f"{name}: expected exactly one executable node, found {len(nodes)}"
            )
    if all(len(nodes) == 1 for nodes in categories.values()):
        ordered = [
            commands.index(categories[name][0])
            for name in ("patch", "stamp", "build_des", "stage", "wheel")
        ]
        if ordered != sorted(ordered):
            violations.append(f"release command order is not canonical: {ordered}")
        stage = categories["stage"][0]
        if stage.argv.count("--cleanup-dist") != 1:
            violations.append("stage helper must receive --cleanup-dist exactly once")
        patch = categories["patch"][0]
        stamp = categories["stamp"][0]
        version_flags = [
            index
            for index, token in enumerate(patch.argv)
            if token == "--target-version"
        ]
        patch_values = (
            (patch.argv[version_flags[0] + 1],)
            if len(version_flags) == 1 and version_flags[0] + 1 < len(patch.argv)
            else ()
        )
        stamp_values = tuple(
            version
            for token in stamp.argv
            if (version := _stamp_version_value(token)) is not None
        )
        patch_refs = _github_refs(patch_values)
        values_match = (
            len(patch_values) == 1
            and len(stamp_values) == 1
            and _normalized_version_value(patch_values[0])
            == _normalized_version_value(stamp_values[0])
        )
        if len(patch_refs) != 1 or not values_match:
            violations.append(
                f"version dataflow differs: patch={patch_values}, "
                f"module_stamp={stamp_values}"
            )
        build_index = commands.index(categories["build_des"][0])
        wheel_index = commands.index(categories["wheel"][0])
        allowed = {"scripts/release/stage_public_wheel_des.py"}
        for command in commands[build_index + 1 : wheel_index]:
            wrappers: set[str] = set()
            for index, token in enumerate(command.argv):
                normalized = token.removeprefix("./")
                if normalized in allowed:
                    continue
                if token.startswith("./") or token.endswith((".py", ".sh", ".ps1")):
                    wrappers.add(token)
                if token == "-m" and index + 1 < len(command.argv):
                    wrappers.add(f"python -m {command.argv[index + 1]}")
            if wrappers:
                violations.append(
                    f"unexpected staging wrapper scripts: {sorted(wrappers)}"
                )
    for command in commands:
        forbidden = _forbidden_choreography(command)
        if forbidden:
            violations.append(
                f"step {command.step_index} retains staging choreography {forbidden}"
            )
    return violations


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _ast_list_argument(call: ast.Call) -> list[ast.expr] | None:
    if not call.args or not isinstance(call.args[0], (ast.List, ast.Tuple)):
        return None
    return list(call.args[0].elts)


def _string_constants(nodes: list[ast.expr]) -> tuple[str, ...]:
    return tuple(
        node.value
        for node in nodes
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def _node_uses_name(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(descendant, ast.Name)
        and isinstance(descendant.ctx, ast.Load)
        and descendant.id == name
        for descendant in ast.walk(node)
    )


def _value_flows_from(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, ast.JoinedStr):
        return any(
            isinstance(value, ast.FormattedValue)
            and _value_flows_from(value.value, name)
            for value in node.values
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return _value_flows_from(node.left, name) or _value_flows_from(
            node.right,
            name,
        )
    return False


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name] = item.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for item in node.names:
                aliases[item.asname or item.name] = f"{node.module}.{item.name}"
    return aliases


def _resolved_name(name: str, aliases: dict[str, str]) -> str:
    seen: set[str] = set()
    while name not in seen:
        seen.add(name)
        head, separator, tail = name.partition(".")
        replacement = aliases.get(head)
        if replacement is None:
            break
        name = replacement + (separator + tail if separator else "")
    return name


def _scope_nodes(scope: ast.AST) -> tuple[ast.AST, ...]:
    roots = list(getattr(scope, "body", ()))
    nodes: list[ast.AST] = []
    pending = roots[:]
    while pending:
        node = pending.pop()
        nodes.append(node)
        if isinstance(
            node,
            (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef, ast.Lambda),
        ):
            continue
        pending.extend(ast.iter_child_nodes(node))
    return tuple(nodes)


def _callable_alias_value(node: ast.expr, aliases: dict[str, str]) -> str:
    if isinstance(node, (ast.Name, ast.Attribute)):
        return _resolved_name(_dotted_name(node), aliases)
    if (
        isinstance(node, ast.Call)
        and _resolved_name(_dotted_name(node.func), aliases) == "functools.partial"
        and node.args
    ):
        return _callable_alias_value(node.args[0], aliases)
    return ""


def _assignment_aliases(scope: ast.AST, inherited: dict[str, str]) -> dict[str, str]:
    aliases = dict(inherited)
    nodes = _scope_nodes(scope)
    for node in nodes:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name] = item.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for item in node.names:
                aliases[item.asname or item.name] = f"{node.module}.{item.name}"

    bindings: list[tuple[str, ast.expr]] = []
    for node in nodes:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            bindings.append((node.targets[0].id, node.value))
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.value is not None
        ):
            bindings.append((node.target.id, node.value))

    if isinstance(scope, (ast.AsyncFunctionDef, ast.FunctionDef)):
        positional = [*scope.args.posonlyargs, *scope.args.args]
        if scope.args.defaults:
            default_args = positional[-len(scope.args.defaults) :]
            bindings.extend(
                (argument.arg, default)
                for argument, default in zip(
                    default_args,
                    scope.args.defaults,
                    strict=True,
                )
            )
        bindings.extend(
            (argument.arg, default)
            for argument, default in zip(
                scope.args.kwonlyargs,
                scope.args.kw_defaults,
                strict=True,
            )
            if default is not None
        )

    for _ in range(len(bindings) + 1):
        changed = False
        for target, value in bindings:
            resolved = _callable_alias_value(value, aliases)
            if resolved and aliases.get(target) != resolved:
                aliases[target] = resolved
                changed = True
        if not changed:
            break
    return aliases


def _canonical_call(call: ast.Call, aliases: dict[str, str]) -> str:
    return _resolved_name(_dotted_name(call.func), aliases)


def _reachable_functions(
    entry: ast.FunctionDef,
    functions: dict[str, ast.FunctionDef],
    aliases: dict[str, str],
) -> tuple[ast.FunctionDef, ...]:
    pending, seen = [entry], set()
    while pending:
        function = pending.pop()
        if function.name in seen:
            continue
        seen.add(function.name)
        local_aliases = _assignment_aliases(function, aliases)
        pending.extend(
            functions[name]
            for call in ast.walk(function)
            if isinstance(call, ast.Call)
            and (name := _canonical_call(call, local_aliases)) in functions
        )
    return tuple(functions[name] for name in seen)


def _fixture_contract_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {
        node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
    }
    function = functions.get("_build_pypi_shape_wheel")
    if function is None:
        return ["real _build_pypi_shape_wheel callable is absent"]

    violations: list[str] = []
    nested = [
        node
        for node in ast.walk(function)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
        and node is not function
    ]
    if nested:
        violations.append(
            f"fixture pipeline contains nested/dead callable witnesses at "
            f"{sorted(node.lineno for node in nested)}"
        )
    aliases = _assignment_aliases(tree, _import_aliases(tree))
    aliases = _assignment_aliases(function, aliases)
    parents = {
        child: parent
        for parent in ast.walk(function)
        for child in ast.iter_child_nodes(parent)
    }
    run_calls = sorted(
        (
            call
            for call in ast.walk(function)
            if isinstance(call, ast.Call)
            and _canonical_call(call, aliases) == "_wheel_build_run"
        ),
        key=lambda call: (call.lineno, call.col_offset),
    )
    pipeline: dict[str, list[tuple[ast.Call, list[ast.expr]]]] = {
        name: [] for name in ("patch", "build_des", "stage", "wheel")
    }
    for call in run_calls:
        ancestor = parents.get(call)
        while ancestor is not None and ancestor is not function:
            if isinstance(ancestor, (ast.If, ast.For, ast.While, ast.Try, ast.Match)):
                violations.append(f"conditional pipeline call at line {call.lineno}")
                break
            ancestor = parents.get(ancestor)
        argv = _ast_list_argument(call)
        if argv is None:
            violations.append(f"non-literal pipeline argv at line {call.lineno}")
            continue
        constants = _string_constants(argv)
        if "scripts/release/patch_pyproject.py" in constants:
            pipeline["patch"].append((call, argv))
        if "scripts/build_dist.py" in constants:
            pipeline["build_des"].append((call, argv))
        if "scripts/release/stage_public_wheel_des.py" in constants:
            pipeline["stage"].append((call, argv))
        if {"-m", "build", "--wheel"}.issubset(constants):
            pipeline["wheel"].append((call, argv))

    for name, nodes in pipeline.items():
        if len(nodes) != 1:
            violations.append(f"fixture {name}: expected one call, found {len(nodes)}")
    if not all(len(nodes) == 1 for nodes in pipeline.values()):
        return violations

    patch, build, stage, wheel = (
        pipeline[name][0] for name in ("patch", "build_des", "stage", "wheel")
    )
    if _string_constants(stage[1]).count("--cleanup-dist") != 1:
        violations.append("fixture stage must pass --cleanup-dist exactly once")

    flag_positions = [
        index
        for index, node in enumerate(patch[1])
        if isinstance(node, ast.Constant) and node.value == "--target-version"
    ]
    version_name = ""
    if len(flag_positions) == 1:
        value_index = flag_positions[0] + 1
        if value_index < len(patch[1]) and isinstance(patch[1][value_index], ast.Name):
            version_name = patch[1][value_index].id
    if not version_name:
        violations.append("fixture patch has no single named candidate-version flow")

    stores = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Store)
        and node.id == version_name
    ]
    if version_name and (len(stores) != 1 or stores[0].lineno >= patch[0].lineno):
        violations.append(f"candidate version {version_name!r} is not single-source")

    subn_assignments = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and _canonical_call(node.value, aliases).endswith("re.subn")
        and len(node.value.args) >= 2
        and _value_flows_from(node.value.args[1], version_name)
    ]
    changed_name = replacement_name = ""
    if len(subn_assignments) == 1:
        targets = subn_assignments[0].targets
        if len(targets) == 1 and isinstance(targets[0], (ast.Tuple, ast.List)):
            names = [item.id for item in targets[0].elts if isinstance(item, ast.Name)]
            if len(names) == 2:
                changed_name, replacement_name = names
    if not changed_name:
        violations.append("fixture needs one Python re.subn module-version stamp")

    module_paths = {
        target.id
        for assignment in ast.walk(function)
        if isinstance(assignment, (ast.Assign, ast.AnnAssign))
        and assignment.value is not None
        and {"nwave_ai", "__init__.py"}.issubset(
            {
                value.value
                for value in ast.walk(assignment.value)
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            }
        )
        for target in (
            assignment.targets
            if isinstance(assignment, ast.Assign)
            else [assignment.target]
        )
        if isinstance(target, ast.Name)
    }
    stamp_writes = [
        call
        for call in ast.walk(function)
        if isinstance(call, ast.Call)
        and _dotted_name(call.func).endswith(".write_text")
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id in module_paths
        and bool(call.args)
        and _node_uses_name(call.args[0], changed_name)
    ]
    exact_one = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Assert)
        and _node_uses_name(node.test, replacement_name)
        and any(
            isinstance(value, ast.Constant) and value.value == 1
            for value in ast.walk(node.test)
        )
    ]
    if len(stamp_writes) != 1 or len(exact_one) != 1:
        violations.append("module stamp must write once and assert one replacement")

    stamp_line = stamp_writes[0].lineno if len(stamp_writes) == 1 else -1
    order = [
        patch[0].lineno,
        stamp_line,
        build[0].lineno,
        stage[0].lineno,
        wheel[0].lineno,
    ]
    if -1 in order or order != sorted(order):
        violations.append(f"fixture order is not patch→stamp→DES→stage→wheel: {order}")

    forbidden_exact = {
        "os.remove",
        "os.removedirs",
        "os.rmdir",
        "os.unlink",
        "shutil.copy",
        "shutil.copy2",
        "shutil.copyfile",
        "shutil.copytree",
        "shutil.move",
        "shutil.rmtree",
    }
    forbidden_suffixes = (".rmdir", ".unlink")
    for reachable in _reachable_functions(function, functions, aliases):
        reachable_aliases = _assignment_aliases(reachable, aliases)
        for call in (
            node for node in ast.walk(reachable) if isinstance(node, ast.Call)
        ):
            canonical = _canonical_call(call, reachable_aliases)
            if canonical in forbidden_exact or canonical.endswith(forbidden_suffixes):
                violations.append(
                    f"reachable staging copy/delete {canonical} at line {call.lineno}"
                )
    return violations


def _module_version(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    assert len(values) == 1, f"literal __version__ count: {len(values)}"
    return values[0]


def _project_version(path: Path) -> str:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

    return str(tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"])


def _assembled_candidate(tmp_path_factory: Any) -> AssembledCandidate:
    """Run the published builder route in an isolated copied repository.

    This intentionally does not delegate to the E2E PyPI-shape fixture: the
    release candidate is the wheel *and* its adjacent offline closure, and the
    published builder sequence (patch, version stamp, DES build, stage, wheel)
    is its own driving surface.
    """
    cache_name = "_release_staging_ssot_candidate"
    cached = getattr(tmp_path_factory, cache_name, None)
    if cached is not None:
        return cached

    sandbox = _sandbox(tmp_path_factory.mktemp("release_staging_public_builder"))
    # A development pyproject does not contain the public force-include map.
    # The candidate therefore must start from the same public transformation
    # and version dataflow as RC, production, and the PyPI-shape fixture.
    source = _patch_stamp_and_build_des(sandbox)
    source_manifest = _manifest(source)
    staged = _run(
        [
            sys.executable,
            "scripts/release/stage_public_wheel_des.py",
            "--cleanup-dist",
        ],
        cwd=sandbox,
    )
    assert staged.returncode == 0, staged.stderr or staged.stdout
    assert not (sandbox / "dist").exists(), "stage did not clean its source dist/"
    built = _run([sys.executable, "-m", "build", "--wheel"], cwd=sandbox)
    assert built.returncode == 0, built.stderr or built.stdout
    wheels = sorted((sandbox / "dist").glob("*.whl"))
    assert len(wheels) == 1, f"public builder wheel count: {len(wheels)}"
    wheel = wheels[0]

    project_version = _project_version(sandbox / "pyproject.toml")
    module_version = _module_version(sandbox / "nwave_ai" / "__init__.py")
    assert project_version == module_version, (
        f"metadata {project_version!r} != module {module_version!r}"
    )
    candidate = AssembledCandidate(
        sandbox=sandbox,
        wheel=wheel,
        source_manifest=source_manifest,
        version=project_version,
        digest=hashlib.sha256(wheel.read_bytes()).hexdigest(),
    )
    setattr(tmp_path_factory, cache_name, candidate)
    return candidate


def _clean_install_probe(
    consumer_root: Path,
    *,
    wheel: Path,
    requirements_lock: Path,
) -> dict[str, Any]:
    venv = consumer_root / "venv"
    fake_home = consumer_root / "home"
    fake_home.mkdir(parents=True)
    created = _run([sys.executable, "-m", "venv", str(venv)], cwd=consumer_root)
    assert created.returncode == 0, created.stderr or created.stdout
    binary_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    python = binary_dir / ("python.exe" if os.name == "nt" else "python")
    pip = binary_dir / ("pip.exe" if os.name == "nt" else "pip")
    console = binary_dir / ("nwave-ai.exe" if os.name == "nt" else "nwave-ai")
    des_console = binary_dir / ("des.exe" if os.name == "nt" else "des")
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env.pop("PYTHONHOME", None)
    clean_env.update(
        {
            "HOME": str(fake_home),
            "USERPROFILE": str(fake_home),
            "PATH": f"{binary_dir}{os.pathsep}{clean_env.get('PATH', '')}",
            "PYTHONNOUSERSITE": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
        }
    )
    assert wheel.is_file(), f"relocated candidate wheel is absent: {wheel}"
    installed = _run(
        [
            str(pip),
            "--isolated",
            "install",
            "--quiet",
            "--no-index",
            "--find-links",
            ".",
            "-r",
            requirements_lock.name,
        ],
        cwd=requirements_lock.parent,
        env=clean_env,
    )
    assert installed.returncode == 0, installed.stderr or installed.stdout
    assert console.is_file(), "installed nwave-ai console script is absent"
    assert des_console.is_file(), "installed des console script is absent"
    probe_source = (
        "import json, os, shutil, sys\n"
        "from importlib.metadata import version\n"
        "import des, nwave_ai\n"
        "print(json.dumps({"
        "'metadata': version('nwave-ai'), "
        "'module': nwave_ai.__version__, "
        "'des_file': des.__file__, "
        "'nwave_file': nwave_ai.__file__, "
        "'console': shutil.which('nwave-ai'), "
        "'des_console': shutil.which('des'), "
        "'home': os.path.expanduser('~'), "
        "'sys_path': sys.path"
        "}))\n"
    )
    probed = _run(
        [str(python), "-c", probe_source],
        cwd=consumer_root,
        env=clean_env,
    )
    assert probed.returncode == 0, probed.stderr or probed.stdout
    payload = json.loads(probed.stdout.strip())
    versioned = _run([str(console), "--version"], cwd=consumer_root, env=clean_env)
    assert versioned.returncode == 0, versioned.stderr or versioned.stdout
    des_help = _run([str(des_console), "--help"], cwd=consumer_root, env=clean_env)
    assert des_help.returncode == 0, des_help.stderr or des_help.stdout
    payload["console_version_output"] = versioned.stdout
    payload["des_console_output"] = des_help.stdout + des_help.stderr
    payload["venv"] = str(venv)
    payload["fake_home"] = str(fake_home)
    return payload


@pytest.mark.negative_at
def test_secure_dual_stage_refuses_every_indirection_before_mutation(
    tmp_path: Path,
    tmp_path_factory: Any,
) -> None:
    """Snapshot once, clean after commit, and reject every protected indirection."""
    _require_driving_port()
    seed = _clone_sandbox(_shared_prepared_seed(tmp_path_factory), tmp_path / "seed")

    happy = _clone_sandbox(seed, tmp_path / "happy")
    source_snapshot = _manifest(happy / "dist" / "lib" / "python" / "des")
    staged = _run_stage(happy)
    _require(
        staged.returncode == 0,
        what=f"shared stage failed: {staged.stderr or staged.stdout}",
    )
    _require(
        not (happy / "dist").exists(),
        what="dist survived a successful --cleanup-dist invocation",
    )
    for relative in STAGE_NAMES:
        _require(
            _manifest(happy / relative) == source_snapshot,
            what=f"{relative} differs from the pre-helper source snapshot",
        )
    expected_candidate = {
        **{f"python/des/{name}": data for name, data in source_snapshot.items()},
        **{f"nwave-runtime/des/{name}": data for name, data in source_snapshot.items()},
    }
    _require(
        _manifest(happy / "lib") == expected_candidate,
        what="promoted lib contains stale or unrelated members",
    )

    surfaces = (
        "project-root",
        "dist",
        "dist-lib",
        "dist-lib-python",
        "source",
        "source-member",
        "lib",
        "lib-member",
        "temporary",
        "temporary-member",
        "backup",
        "backup-member",
        "journal",
        "source-destination-alias",
    )
    for kind in _indirection_kinds():
        for surface in surfaces:
            root = _clone_sandbox(
                seed,
                tmp_path / f"refuse-{kind}-{surface}",
            )
            extra = _install_indirection_case(root, surface, kind)
            before = _protected_snapshot(root, extra)
            refused = _run_stage(root)
            output = refused.stdout + refused.stderr
            expected = (
                "STAGE_PATH_ESCAPE"
                if surface == "source-destination-alias"
                else "STAGE_REPARSE_POINT"
            )
            _require(
                refused.returncode != 0 and expected in output,
                what=f"{kind} at {surface} was not refused with {expected}: {output}",
            )
            _require(
                _protected_snapshot(root, extra) == before,
                what=f"protected paths changed after refusing {kind} at {surface}",
            )


@pytest.mark.negative_at
def test_invalid_source_and_recovery_evidence_are_refused_without_fallback(
    tmp_path: Path,
    tmp_path_factory: Any,
) -> None:
    """Zero/malformed inputs and unowned recovery residue fail loud and immutable."""
    _require_driving_port()
    prepared = _clone_sandbox(
        _shared_prepared_seed(tmp_path_factory), tmp_path / "prepared"
    )
    prepared_source = prepared / "dist" / "lib" / "python" / "des"

    cases = (
        ("missing", "STAGE_SOURCE_MISSING"),
        ("source-file", "STAGE_SOURCE_INVALID"),
        ("empty", "STAGE_SOURCE_INVALID"),
        ("truncated", "STAGE_SOURCE_INVALID"),
        ("invalid-journal", "STAGE_JOURNAL_INVALID"),
        ("journal-less-backup", "STAGE_RECOVERY_AMBIGUOUS"),
    )
    for name, diagnostic in cases:
        if name in {"invalid-journal", "journal-less-backup"}:
            root = _clone_sandbox(prepared, tmp_path / name)
            source = root / "dist" / "lib" / "python" / "des"
        else:
            root = _sandbox(tmp_path / name)
            source = root / "dist" / "lib" / "python" / "des"
            if name == "source-file":
                source.parent.mkdir(parents=True)
                source.write_text("not a directory\n", encoding="utf-8")
            elif name == "empty":
                source.mkdir(parents=True)
            elif name == "truncated":
                source.mkdir(parents=True)
                (source / "partial.py").write_text("partial = True\n", encoding="utf-8")
        if name == "invalid-journal":
            (root / JOURNAL).write_text("not-json", encoding="utf-8")
        elif name == "journal-less-backup":
            _make_complete_stage(source, root / BACKUP, old=True)

        before = _protected_snapshot(root)
        refused = _run_stage(root)
        output = refused.stdout + refused.stderr
        _require(
            refused.returncode != 0 and diagnostic in output,
            what=f"{name} did not fail with {diagnostic}: {output}",
        )
        _require(
            str(root) not in output,
            what=f"{name} diagnostic leaked absolute project path {root}",
        )
        _require(
            _protected_snapshot(root) == before,
            what=f"{name} mutated source, candidate, or recovery evidence",
        )

    _require(
        _manifest(prepared_source)
        == _manifest(prepared / "dist" / "lib" / "python" / "des"),
        what="prepared source changed while exercising isolated invalid candidates",
    )


@pytest.mark.negative_at
def test_every_durable_recovery_topology_rolls_back_and_reruns_idempotently(
    tmp_path: Path,
    tmp_path_factory: Any,
) -> None:
    """State×old-presence, lag windows, refusal, rollback, and two reruns close."""
    _require_driving_port()
    seed = _clone_sandbox(_shared_prepared_seed(tmp_path_factory), tmp_path / "seed")
    legal = (
        RecoveryTopology("PREPARED", True, "canonical"),
        RecoveryTopology("PREPARED", True, "after-old-rename"),
        RecoveryTopology("PREPARED", False, "canonical"),
        RecoveryTopology("OLD_MOVED", True, "canonical"),
        RecoveryTopology("OLD_MOVED", True, "after-new-rename"),
        RecoveryTopology("OLD_MOVED", False, "canonical"),
        RecoveryTopology("OLD_MOVED", False, "after-new-rename"),
        RecoveryTopology("NEW_PROMOTED", True, "canonical"),
        RecoveryTopology("NEW_PROMOTED", False, "canonical"),
        RecoveryTopology("COMMITTED", True, "backup-present"),
        RecoveryTopology("COMMITTED", True, "backup-removed"),
        RecoveryTopology("COMMITTED", False, "canonical"),
    )
    for index, topology in enumerate(legal):
        root = _clone_sandbox(seed, tmp_path / f"legal-{index}")
        source = root / "dist" / "lib" / "python" / "des"
        _, expected_new = _seed_recovery_topology(root, source, topology)
        recovered = _run_stage(root)
        _require(
            recovered.returncode == 0,
            what=f"legal recovery {topology} failed: {recovered.stderr or recovered.stdout}",
        )
        observed = _manifest(root / "lib")
        _require(
            observed == expected_new,
            what=(
                f"recovery {topology.state}×old_present={topology.old_present} "
                "did not converge to the exact new population"
            ),
        )
        _require(
            not any((root / name).exists() for name in (TEMPORARY, BACKUP, JOURNAL)),
            what=f"recovery {topology} left temp, backup, or journal residue",
        )
        _require(
            not (root / "dist").exists(),
            what=f"recovery {topology} returned success without mandatory source cleanup",
        )

    for label in (
        "foreign-path",
        "foreign-source-digest",
        "foreign-new-digest",
        "foreign-residual",
        "impossible-topology",
    ):
        root = _clone_sandbox(seed, tmp_path / label)
        source = root / "dist" / "lib" / "python" / "des"
        if label == "foreign-residual":
            (root / TEMPORARY).write_text("foreign\n", encoding="utf-8")
        elif label == "impossible-topology":
            _seed_recovery_topology(
                root,
                source,
                RecoveryTopology("PREPARED", False, "canonical"),
            )
            _make_complete_stage(source, root / BACKUP, old=True)
        else:
            _seed_recovery_topology(
                root,
                source,
                RecoveryTopology("PREPARED", True, "canonical"),
            )
            journal = json.loads((root / JOURNAL).read_text(encoding="utf-8"))
            if label == "foreign-path":
                journal["paths"]["candidate"] = "foreign-lib"
            elif label == "foreign-source-digest":
                journal["source_manifest_sha256"] = "0" * 64
            else:
                journal["new_manifest_sha256"] = "f" * 64
            (root / JOURNAL).write_text(json.dumps(journal), encoding="utf-8")
        before = _protected_snapshot(root)
        refused = _run_stage(root)
        _require(
            refused.returncode != 0
            and "STAGE_RECOVERY_AMBIGUOUS" in refused.stdout + refused.stderr,
            what=f"{label} was not refused as ambiguous",
        )
        _require(
            _protected_snapshot(root) == before,
            what=f"{label} was mutated during ambiguous recovery",
        )

    for old_present in (True, False):
        for state, location in (
            ("PREPARED", TEMPORARY),
            ("NEW_PROMOTED", "lib"),
        ):
            root = _clone_sandbox(
                seed,
                tmp_path / f"rollback-{old_present}-{state}",
            )
            source = root / "dist" / "lib" / "python" / "des"
            old_candidate, _ = _seed_recovery_topology(
                root,
                source,
                RecoveryTopology(state, old_present, "canonical"),
            )
            corrupt = root / location / "python" / "des" / "__init__.py"
            corrupt.write_bytes(corrupt.read_bytes() + b"\n# corrupt\n")
            rolled_back = _run_stage(root)
            _require(
                rolled_back.returncode != 0
                and "STAGE_VERIFY_FAILED" in rolled_back.stdout + rolled_back.stderr,
                what=f"corrupt {location} for old_present={old_present} was accepted",
            )
            restored = _manifest(root / "lib") if (root / "lib").is_dir() else None
            _require(
                restored == old_candidate,
                what=f"rollback from {state} did not restore exact prior state",
            )
            _require(
                (root / "dist").is_dir(),
                what="pre-commit rollback deleted dist evidence",
            )

    rerun = _clone_sandbox(seed, tmp_path / "two-reruns")
    first_source = _manifest(rerun / "dist" / "lib" / "python" / "des")
    first_stage = _run_stage(rerun)
    _require(
        first_stage.returncode == 0,
        what=f"first ordinary staging run failed: {first_stage.stderr or first_stage.stdout}",
    )
    first_candidate = _manifest(rerun / "lib")
    first_wheel = _zip_manifest(_build_wheel(rerun, "wheelhouse-first"))
    for relative in STAGE_NAMES:
        (rerun / relative / "stale.py").write_text("stale = True\n", encoding="utf-8")
    rebuilt_source = _manifest(_build_des(rerun))
    _require(
        rebuilt_source == first_source,
        what="rebuilding the same DES input produced different bytes",
    )
    second_stage = _run_stage(rerun)
    _require(
        second_stage.returncode == 0,
        what=f"second ordinary staging run failed: {second_stage.stderr or second_stage.stdout}",
    )
    _require(
        _manifest(rerun / "lib") == first_candidate,
        what="two ordinary reruns produced different staged manifests",
    )
    _require(
        not any((rerun / relative / "stale.py").exists() for relative in STAGE_NAMES),
        what="second run retained stale files from the prior candidate",
    )
    second_wheel = _zip_manifest(_build_wheel(rerun, "wheelhouse-second"))
    _require(
        second_wheel == first_wheel,
        what="two ordinary reruns produced different wheel manifests",
    )


def test_rc_prod_and_fixture_share_order_version_and_cleanup_dataflow() -> None:
    """Executable structures—not comments or unordered presence—share one chain."""
    violations: list[str] = []
    for workflow in ("release-rc.yml", "release-prod.yml"):
        path = REPO_ROOT / ".github" / "workflows" / workflow
        violations.extend(
            f"{workflow}: {violation}"
            for violation in _workflow_contract_violations(path)
        )
    violations.extend(
        f"tests/e2e/conftest.py: {violation}"
        for violation in _fixture_contract_violations(E2E_FIXTURE)
    )
    _require(
        not violations,
        what="release consumers diverge:\n- " + "\n- ".join(violations),
    )


@pytest.mark.walking_skeleton
@pytest.mark.e2e_smoke
def test_real_pypi_fixture_wheel_installs_with_exact_dual_des_and_version(
    tmp_path: Path,
    tmp_path_factory: Any,
) -> None:
    """One real immutable candidate installs in a source-isolated consumer."""
    _require_driving_port()
    candidate = _assembled_candidate(tmp_path_factory)
    original_bundle = candidate.wheel.parent
    relocated_bundle = tmp_path / "relocated-public-candidate"
    original_bundle_manifest = _manifest(original_bundle)
    shutil.copytree(original_bundle, relocated_bundle)
    _require(
        _manifest(relocated_bundle) == original_bundle_manifest,
        what="relocation did not preserve the complete candidate directory",
    )
    relocated_wheels = sorted(relocated_bundle.glob("*.whl"))
    _require(
        [wheel.name for wheel in relocated_wheels] == [candidate.wheel.name],
        what=(
            "relocation changed the candidate wheel population or filename: "
            f"{[wheel.name for wheel in relocated_wheels]}"
        ),
    )
    relocated_wheel = relocated_wheels[0]
    try:
        parse_wheel_filename(relocated_wheel.name)
    except InvalidWheelFilename as error:
        wheel_filename_error = str(error)
    else:
        wheel_filename_error = ""
    _require(
        not wheel_filename_error,
        what=(
            f"relocated candidate lost its PEP 427 filename "
            f"{relocated_wheel.name!r}: {wheel_filename_error}"
        ),
    )
    requirements_lock = relocated_bundle / "offline-wheelhouse" / "requirements.lock"
    _require(
        requirements_lock.is_file(),
        what="complete candidate has no adjacent offline-wheelhouse/requirements.lock",
    )
    lock_text = requirements_lock.read_text(encoding="utf-8")
    lock_lines = [
        line.strip()
        for line in lock_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    lock_references = [
        (line, reference)
        for line in lock_lines
        if (reference := _lock_reference(line)) is not None
    ]
    absolute_or_remote = [
        reference
        for _, reference in lock_references
        if (
            (parsed := urlsplit(reference)).scheme not in {"", "file"}
            or parsed.netloc not in {"", "localhost"}
            or (
                (local_path := _local_lock_path(reference)) is not None
                and (
                    local_path.is_absolute()
                    or re.match(r"^[A-Za-z]:[\\/]", unquote(parsed.path), re.I)
                )
            )
        )
    ]
    forbidden_roots = (candidate.sandbox.resolve(), REPO_ROOT.resolve(), Path.home())
    leaked_roots = [
        str(root)
        for root in forbidden_roots
        if str(root) in lock_text or root.as_uri() in lock_text
    ]
    _require(
        not absolute_or_remote and not leaked_roots,
        what=(
            "portable candidate lock borrows absolute, build, source, HOME, "
            f"or network locations: tokens={absolute_or_remote}, roots={leaked_roots}"
        ),
    )
    relocated_root = relocated_bundle.resolve()
    resolved_local_references = [
        (
            line,
            (
                local_path
                if local_path.is_absolute()
                else requirements_lock.parent / local_path
            ).resolve(),
        )
        for line, reference in lock_references
        if (local_path := _local_lock_path(reference)) is not None
    ]
    escaped_or_missing = [
        (line, str(resolved))
        for line, resolved in resolved_local_references
        if not resolved.is_relative_to(relocated_root) or not resolved.is_file()
    ]
    _require(
        not escaped_or_missing,
        what=(
            "local lock references do not resolve to files inside the relocated "
            f"candidate bundle: {escaped_or_missing}"
        ),
    )
    candidate_lock_references = [
        (line, resolved)
        for line, resolved in resolved_local_references
        if resolved.name == relocated_wheel.name
    ]
    exact_candidate_reference = (
        len(candidate_lock_references) == 1
        and candidate_lock_references[0][1] == relocated_wheel.resolve()
        and f"--hash=sha256:{candidate.digest}" in candidate_lock_references[0][0]
        and hashlib.sha256(candidate_lock_references[0][1].read_bytes()).hexdigest()
        == candidate.digest
    )
    _require(
        exact_candidate_reference,
        what=(
            "portable lock does not resolve exactly once to the relocated wheel "
            f"with matching lock and byte digests: {candidate_lock_references}"
        ),
    )
    with zipfile.ZipFile(candidate.wheel) as archive:
        names = archive.namelist()
        counts = Counter(names)
        duplicates = sorted(name for name, count in counts.items() if count != 1)
        _require(
            not duplicates,
            what=f"real fixture wheel has duplicate members: {duplicates}",
        )
        for prefix in ("des", "nWave/lib/python/des"):
            payload = {
                name.removeprefix(prefix + "/"): archive.read(name)
                for name in names
                if name.startswith(prefix + "/") and not name.endswith("/")
            }
            _require(
                payload == candidate.source_manifest,
                what=f"wheel prefix {prefix}/ differs from the pre-helper DES snapshot",
            )

    before_install_digest = hashlib.sha256(relocated_wheel.read_bytes()).hexdigest()
    consumer = tmp_path / "clean-consumer"
    consumer.mkdir()
    unavailable_sandbox = candidate.sandbox.with_name(
        f".{candidate.sandbox.name}-unavailable"
    )
    _require(
        not unavailable_sandbox.exists(),
        what=f"sandbox-unavailability witness already exists: {unavailable_sandbox}",
    )
    candidate.sandbox.rename(unavailable_sandbox)
    try:
        _require(
            not candidate.sandbox.exists(),
            what="original build sandbox remained reachable during consumption",
        )
        installed = _clean_install_probe(
            consumer,
            wheel=relocated_wheel,
            requirements_lock=requirements_lock,
        )
    finally:
        unavailable_sandbox.rename(candidate.sandbox)
    _require(
        before_install_digest
        == candidate.digest
        == hashlib.sha256(relocated_wheel.read_bytes()).hexdigest(),
        what="the immutable candidate changed while downstream probes consumed it",
    )
    _require(
        installed["metadata"] == installed["module"] == candidate.version,
        what=(
            "installed versions diverge: "
            f"metadata={installed['metadata']!r}, module={installed['module']!r}, "
            f"candidate={candidate.version!r}"
        ),
    )
    venv = Path(installed["venv"]).resolve()
    for field in ("des_file", "nwave_file", "console", "des_console"):
        resolved = Path(str(installed[field])).resolve()
        _require(
            resolved.is_relative_to(venv),
            what=f"installed {field} borrowed non-venv path {resolved}",
        )
    _require(
        bool(installed["des_console_output"].strip())
        and candidate.version in installed["console_version_output"],
        what="installed des --help or nwave-ai --version surface is unusable",
    )
    _require(
        installed["home"] == installed["fake_home"],
        what=f"clean probe borrowed ambient HOME: {installed['home']}",
    )
    borrowed_roots = tuple(
        str(root)
        for root in (
            REPO_ROOT.resolve(),
            candidate.sandbox.resolve(),
            unavailable_sandbox.resolve(),
            Path.home(),
        )
    )
    _require(
        all(
            not any(root in entry for root in borrowed_roots)
            for entry in installed["sys_path"]
        ),
        what=(
            "clean probe borrowed checkout, build sandbox, or HOME sys.path: "
            f"{installed['sys_path']}"
        ),
    )


@pytest.mark.e2e_smoke
@pytest.mark.negative_at
def test_same_real_wheel_preserves_privacy_and_runtime_asset_population(
    tmp_path_factory: Any,
) -> None:
    """The same real candidate remains public-only and runtime-complete."""
    _require_driving_port()
    candidate = _assembled_candidate(tmp_path_factory)
    verified = _run(
        [
            sys.executable,
            "scripts/release/verify_wheel_privacy.py",
            str(candidate.wheel),
        ],
        cwd=candidate.sandbox,
    )
    _require(
        verified.returncode == 0,
        what=f"real privacy verifier refused the wheel: {verified.stderr or verified.stdout}",
    )
    with zipfile.ZipFile(candidate.wheel) as archive:
        names = archive.namelist()
    forbidden_prefixes = (
        "src/des/",
        "lib/",
        "scripts/release/",
        "nWave/agents/private/",
        "nWave/skills/private/",
    )
    leaks = [
        name
        for name in names
        if any(name.startswith(prefix) for prefix in forbidden_prefixes)
    ]
    _require(
        not leaks,
        what=f"wheel exposes raw stage, release implementation, or private paths: {leaks}",
    )
    required_exact = (
        "nWave/framework-catalog.yaml",
        "nWave/nWave/framework-catalog.yaml",
        "nWave/VERSION",
        "scripts/install/install_nwave.py",
    )
    required_prefixes = (
        "nWave/templates/",
        "nWave/nWave/templates/",
        "nWave/nWave/data/",
        "nWave/nWave/flavors/",
        "nWave/nWave/schemas/",
        "nWave/nWave/dispatch/",
    )
    missing_exact = [name for name in required_exact if names.count(name) != 1]
    missing_prefixes = [
        prefix
        for prefix in required_prefixes
        if not any(name.startswith(prefix) for name in names)
    ]
    _require(
        not missing_exact and not missing_prefixes,
        what=(
            f"wheel lost runtime assets: exact={missing_exact}, "
            f"populations={missing_prefixes}"
        ),
    )


@pytest.mark.e2e_smoke
@pytest.mark.parametrize(
    ("platform", "platform_home_env", "native_surfaces"),
    (
        (
            "claude-code",
            "CLAUDE_CONFIG_DIR",
            ("agents/nw/*.md", "skills/nw-*/SKILL.md"),
        ),
        (
            "copilot",
            "COPILOT_HOME",
            ("hooks/nwave-des.json",),
        ),
        (
            "opencode",
            "OPENCODE_CONFIG_DIR",
            (
                "agents/nw-*.md",
                "skills/nw-*/SKILL.md",
                "plugins/nwave-des.ts",
            ),
        ),
    ),
)
def test_same_real_wheel_installs_public_native_surfaces_for_non_codex_hosts(
    tmp_path: Path,
    tmp_path_factory: Any,
    platform: str,
    platform_home_env: str,
    native_surfaces: tuple[str, ...],
) -> None:
    """C6: one assembled public wheel provisions each non-Codex host in isolation."""
    _require_driving_port()
    candidate = _assembled_candidate(tmp_path_factory)
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    requirements_lock = (
        candidate.wheel.parent / "offline-wheelhouse" / "requirements.lock"
    )
    installed = _clean_install_probe(
        consumer,
        wheel=candidate.wheel,
        requirements_lock=requirements_lock,
    )
    venv = Path(installed["venv"])
    binary_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    console = binary_dir / ("nwave-ai.exe" if os.name == "nt" else "nwave-ai")
    host_home = tmp_path / f"{platform}-home"
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env.pop("PYTHONHOME", None)
    clean_env.update(
        {
            "HOME": str(installed["fake_home"]),
            "USERPROFILE": str(installed["fake_home"]),
            "PATH": f"{binary_dir}{os.pathsep}{clean_env.get('PATH', '')}",
            "PYTHONNOUSERSITE": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            platform_home_env: str(host_home),
        }
    )
    provisioned = _run(
        [str(console), "install", "--yes", "--platform", platform],
        cwd=consumer,
        env=clean_env,
    )
    _require(
        provisioned.returncode == 0,
        what=(
            f"installed public wheel could not provision {platform}: "
            f"{provisioned.stderr or provisioned.stdout}"
        ),
    )
    missing_surfaces = [
        surface for surface in native_surfaces if not tuple(host_home.glob(surface))
    ]
    _require(
        not missing_surfaces,
        what=f"{platform} install omitted native public surfaces: {missing_surfaces}",
    )
    private_artifacts = sorted(
        path.relative_to(host_home).as_posix()
        for path in host_home.rglob("*")
        if path.is_file() and "private" in path.as_posix().lower()
    )
    _require(
        not private_artifacts,
        what=f"{platform} install exposed private agents or skills: {private_artifacts}",
    )


@pytest.mark.e2e_smoke
@pytest.mark.parametrize(
    ("platform", "platform_home_env"),
    (
        ("copilot", "COPILOT_HOME"),
        ("opencode", "OPENCODE_CONFIG_DIR"),
    ),
)
def test_pure_non_claude_source_install_never_creates_claude_discovery_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    platform_home_env: str,
) -> None:
    """C6 source-driving oracle: a pure native host install owns no ``~/.claude``.

    This deliberately drives the real ``NWaveInstaller.install_framework``
    orchestration rather than a plugin in isolation: the regression is the
    post-runtime legacy-DES sequence selected by that orchestration.  It is a
    source-driving acceptance test only, because the exact public-wheel
    witness remains the independent ``test_same_real_wheel_*`` family above.
    The latter must carry this same negative oracle once an offline wheel
    build is available.
    """
    from scripts.install.install_nwave import NWaveInstaller

    fake_home = tmp_path / "fake-home"
    host_home = tmp_path / f"{platform}-home"
    fake_home.mkdir()
    host_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv(platform_home_env, str(host_home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    if platform == "copilot":
        monkeypatch.setenv("COPILOT_CLI", "1")

    installed = NWaveInstaller(
        dry_run=False,
        platform_override={platform},
    ).install_framework()

    _require(installed, what=f"source installer could not provision {platform}")
    _require(
        not (fake_home / ".claude").exists(),
        what=(
            f"pure {platform} installation created a Claude discovery surface "
            f"at {fake_home / '.claude'}"
        ),
        why=(
            "Copilot and OpenCode have their own native surfaces; creating "
            "legacy Claude assets makes an unselected host discover nWave"
        ),
        how=(
            "after installing the host-neutral DES runtime, return for a "
            "target set that does not include claude_code"
        ),
    )


@pytest.mark.e2e_smoke
def test_mixed_claude_copilot_source_install_keeps_claude_hook_on_existing_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C6 source-driving oracle: a mixed install leaves Claude executable.

    Selecting Copilot makes DES use the shared host-neutral runtime.  Adding
    Claude Code must not leave its generated hook on the legacy
    ``~/.claude/lib/python`` path unless that path is also materialised.  The
    observable is stronger than a successful installer return: resolve the
    literal runtime written into Claude's hook and execute that exact command
    with no inherited Python path.

    This is deliberately source-driving.  The same assertion belongs in the
    exact-public-wheel witness once its offline candidate can be assembled.
    """
    from scripts.install.install_nwave import NWaveInstaller

    fake_home = tmp_path / "fake-home"
    claude_home = fake_home / ".claude"
    copilot_home = tmp_path / "copilot-home"
    fake_home.mkdir()
    copilot_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("USERPROFILE", str(fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    monkeypatch.setenv("COPILOT_HOME", str(copilot_home))
    monkeypatch.setenv("COPILOT_CLI", "1")
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.delenv("PYTHONHOME", raising=False)

    installed = NWaveInstaller(
        dry_run=False,
        platform_override={"claude_code", "copilot"},
    ).install_framework()

    _require(installed, what="source installer could not provision Claude+Copilot")
    settings = json.loads((claude_home / "settings.json").read_text(encoding="utf-8"))
    hook = settings["hooks"]["PreToolUse"][0]["hooks"][0]
    command = hook["command"]
    runtime_literal = _configured_runtime_dir(command, host="Claude+Copilot")
    runtime_dir = Path(str(runtime_literal).replace("$HOME", str(fake_home), 1))
    _require_hook_runtime(runtime_dir, host="Claude+Copilot")

    hook_env = os.environ.copy()
    hook_env.pop("PYTHONPATH", None)
    hook_env.pop("PYTHONHOME", None)
    hook_env["HOME"] = str(fake_home)
    hook_env["USERPROFILE"] = str(fake_home)
    fired = subprocess.run(
        ["bash", "-c", command],
        cwd=tmp_path,
        env=hook_env,
        input="{}\n",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    _require(
        fired.returncode == 0,
        what=(
            "mixed Claude+Copilot generated hook did not execute its declared "
            f"DES runtime: {fired.stderr or fired.stdout}"
        ),
        why=(
            "a host-neutral runtime does not make a Claude hook valid when the "
            "hook still names an absent legacy runtime"
        ),
        how=(
            "generate Claude's hook from the shared runtime or materialise the "
            "runtime literally embedded in that hook"
        ),
    )


@pytest.mark.e2e_smoke
def test_standalone_copilot_hook_executes_from_its_installed_runtime(
    tmp_path: Path,
    tmp_path_factory: Any,
) -> None:
    """C6: Copilot's generated command imports and runs DES after installation."""
    _require_driving_port()
    candidate = _assembled_candidate(tmp_path_factory)
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    installed = _clean_install_probe(
        consumer,
        wheel=candidate.wheel,
        requirements_lock=candidate.wheel.parent
        / "offline-wheelhouse"
        / "requirements.lock",
    )
    venv = Path(installed["venv"])
    binary_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    console = binary_dir / ("nwave-ai.exe" if os.name == "nt" else "nwave-ai")
    copilot_home = tmp_path / "copilot-home"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(
        {
            "HOME": str(installed["fake_home"]),
            "USERPROFILE": str(installed["fake_home"]),
            "PATH": f"{binary_dir}{os.pathsep}{environment.get('PATH', '')}",
            "PYTHONNOUSERSITE": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "COPILOT_HOME": str(copilot_home),
            "COPILOT_CLI": "1",
        }
    )
    provisioned = _run(
        [str(console), "install", "--yes", "--platform", "copilot"],
        cwd=consumer,
        env=environment,
    )
    _require(
        provisioned.returncode == 0,
        what=f"standalone Copilot install failed: {provisioned.stderr or provisioned.stdout}",
    )
    config_path = copilot_home / "hooks" / "nwave-des.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    hook = config["preToolUse"][0]["hooks"][0]
    runtime_dir = _configured_runtime_dir(hook["bash"], host="Copilot")
    _require_hook_runtime(runtime_dir, host="Copilot")
    fired = _run(
        ["bash", "-c", hook["bash"]],
        cwd=consumer,
        env=environment,
    )
    _require(
        fired.returncode == 0,
        what=(
            "installed Copilot hook did not execute its DES adapter: "
            f"{fired.stderr or fired.stdout}"
        ),
    )


@pytest.mark.e2e_smoke
def test_standalone_opencode_hook_executes_from_its_installed_runtime(
    tmp_path: Path,
    tmp_path_factory: Any,
) -> None:
    """C6: OpenCode's rendered Bun hook imports and runs DES after installation."""
    _require_driving_port()
    candidate = _assembled_candidate(tmp_path_factory)
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    installed = _clean_install_probe(
        consumer,
        wheel=candidate.wheel,
        requirements_lock=candidate.wheel.parent
        / "offline-wheelhouse"
        / "requirements.lock",
    )
    venv = Path(installed["venv"])
    binary_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    console = binary_dir / ("nwave-ai.exe" if os.name == "nt" else "nwave-ai")
    opencode_home = tmp_path / "opencode-home"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(
        {
            "HOME": str(installed["fake_home"]),
            "USERPROFILE": str(installed["fake_home"]),
            "PATH": f"{binary_dir}{os.pathsep}{environment.get('PATH', '')}",
            "PYTHONNOUSERSITE": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "OPENCODE_CONFIG_DIR": str(opencode_home),
        }
    )
    provisioned = _run(
        [str(console), "install", "--yes", "--platform", "opencode"],
        cwd=consumer,
        env=environment,
    )
    _require(
        provisioned.returncode == 0,
        what=f"standalone OpenCode install failed: {provisioned.stderr or provisioned.stdout}",
    )
    shim = opencode_home / "plugins" / "nwave-des.ts"
    rendered = shim.read_text(encoding="utf-8")
    runtime_match = re.search(r'PYTHONPATH: "([^"]+)"', rendered)
    _require(
        runtime_match is not None,
        what="OpenCode shim has no literal PYTHONPATH for its DES subprocess",
    )
    _require_hook_runtime(Path(runtime_match.group(1)), host="OpenCode")
    harness = consumer / "run-nwave-opencode-hook.ts"
    harness.write_text(
        "import plugin from " + json.dumps(shim.as_posix()) + ";\n"
        "const hooks = plugin({} as never);\n"
        "await hooks['tool.execute.before'](\n"
        "  { tool: 'write', args: {} },\n"
        "  { args: { file_path: 'probe.txt', content: 'probe' } },\n"
        ");\n"
        "console.log('nwave-opencode-hook-executed');\n",
        encoding="utf-8",
    )
    fired = _run(["bun", "run", str(harness)], cwd=consumer, env=environment)
    _require(
        fired.returncode == 0 and "nwave-opencode-hook-executed" in fired.stdout,
        what=(
            "installed OpenCode hook did not execute through Bun: "
            f"{fired.stderr or fired.stdout}"
        ),
    )


@pytest.mark.e2e_smoke
def test_all_target_install_keeps_codex_and_copilot_hooks_on_one_runtime(
    tmp_path: Path,
    tmp_path_factory: Any,
) -> None:
    """C6: the supported all-target flow keeps Codex and Copilot executable."""
    _require_driving_port()
    candidate = _assembled_candidate(tmp_path_factory)
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    installed = _clean_install_probe(
        consumer,
        wheel=candidate.wheel,
        requirements_lock=candidate.wheel.parent
        / "offline-wheelhouse"
        / "requirements.lock",
    )
    venv = Path(installed["venv"])
    binary_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    console = binary_dir / ("nwave-ai.exe" if os.name == "nt" else "nwave-ai")
    home = Path(installed["fake_home"])
    copilot_home = tmp_path / "copilot-home"
    codex_home = tmp_path / "codex-home"
    opencode_home = tmp_path / "opencode-home"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "PATH": f"{binary_dir}{os.pathsep}{environment.get('PATH', '')}",
            "PYTHONNOUSERSITE": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "CODEX_HOME": str(codex_home),
            "COPILOT_HOME": str(copilot_home),
            "COPILOT_CLI": "1",
            "OPENCODE_CONFIG_DIR": str(opencode_home),
        }
    )
    provisioned = _run(
        [str(console), "install", "--yes", "--platform", "all"],
        cwd=consumer,
        env=environment,
    )
    _require(
        provisioned.returncode == 0,
        what=(
            "all-target install failed:\\n"
            f"STDERR: {provisioned.stderr}\\nSTDOUT: {provisioned.stdout}"
        ),
    )
    _require(
        (codex_home / "hooks.json").is_file(),
        what="all-target install omitted its Codex hook document",
    )
    # Execute the command literally rendered into the installed hook document.
    # This proves the public wheel's launcher and host-neutral DES runtime,
    # rather than merely its JSON presence. Native Codex event delivery remains
    # a separate vendor-host witness.
    codex_hooks = json.loads((codex_home / "hooks.json").read_text(encoding="utf-8"))
    codex_manifest = json.loads(
        (codex_home / ".nwave-des-manifest.json").read_text(encoding="utf-8")
    )
    launcher_path = str(codex_manifest["launcher_file"])
    codex_entries = [
        hook
        for group in codex_hooks.get("hooks", {}).get("PreToolUse", [])
        for hook in group.get("hooks", [])
        if launcher_path in hook.get("command", "")
    ]
    _require(
        len(codex_entries) == 1,
        what=f"Codex hook document has {len(codex_entries)} nWave launcher entries",
    )
    audit_dir = consumer / ".nwave" / "des" / "logs"
    environment["DES_AUDIT_LOG_DIR"] = str(audit_dir)
    activation = consumer / ".nwave" / "local-config.json"
    activation.parent.mkdir(parents=True, exist_ok=True)
    activation.write_text('{"enabled_for_repo": true}\n', encoding="utf-8")
    fired_codex = _run(
        codex_entries[0]["command"],
        cwd=consumer,
        env=environment,
        input_text=json.dumps(
            {
                "cwd": str(consumer),
                "tool_name": "exec_command",
                "tool_input": {"command": "printf codex-wheel-witness"},
            }
        )
        + "\n",
        shell=True,
    )
    _require(
        fired_codex.returncode == 0,
        what=(
            "installed Codex launcher could not execute the packaged DES runtime: "
            f"{fired_codex.stderr or fired_codex.stdout}"
        ),
    )
    codex_events = []
    for audit_file in sorted(audit_dir.glob("audit-*.log")):
        for line in audit_file.read_text(encoding="utf-8").splitlines():
            try:
                codex_events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    _require(
        any(
            event.get("event") == "HOOK_INVOKED"
            and event.get("handler") == "pre_tool_use"
            for event in codex_events
        )
        and any(
            event.get("event") == "HOOK_COMPLETED"
            and event.get("handler") == "pre_tool_use"
            and event.get("exit_code") == 0
            for event in codex_events
        ),
        what="installed Codex launcher did not persist paired hook audit evidence",
    )
    # Codex parity also owes the operator its standing-loop / throughput
    # affordance at SessionStart.  Execute the exact public-wheel command: a
    # JSON key in hooks.json is not proof that the resolver shipped, resolves
    # its host-neutral data, and keeps the hook protocol clean.
    session_launcher_path = str(codex_manifest["session_start_launcher_file"])
    session_entries = [
        hook
        for group in codex_hooks.get("hooks", {}).get("SessionStart", [])
        for hook in group.get("hooks", [])
        if session_launcher_path in hook.get("command", "")
    ]
    _require(
        len(session_entries) == 1,
        what=(
            "Codex public wheel must install exactly one standing-loop "
            f"SessionStart launcher, found {len(session_entries)}"
        ),
    )
    resolver_path = Path(codex_manifest["resolver_script_file"])
    _require(
        resolver_path.is_file() and not resolver_path.is_symlink(),
        what=(
            "Codex SessionStart resolver is not a regular installed runtime "
            f"artifact: {resolver_path}"
        ),
    )
    fired_session_start = _run(
        session_entries[0]["command"], cwd=consumer, env=environment, shell=True
    )
    _require(
        fired_session_start.returncode == 0,
        what=(
            "installed Codex SessionStart launcher could not execute the "
            f"packaged affordance resolver: {fired_session_start.stderr or fired_session_start.stdout}"
        ),
    )
    try:
        session_envelope = json.loads(fired_session_start.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            "installed Codex SessionStart launcher did not emit one parseable "
            f"hook envelope: {fired_session_start.stdout!r}"
        ) from exc
    _require(
        session_envelope.get("hookSpecificOutput", {}).get("hookEventName")
        == "SessionStart"
        and bool(
            session_envelope.get("hookSpecificOutput", {}).get("additionalContext")
        ),
        what="Codex SessionStart did not inject the installed standing-loop affordance",
    )
    copilot_config = json.loads(
        (copilot_home / "hooks" / "nwave-des.json").read_text(encoding="utf-8")
    )
    copilot_hook = copilot_config["preToolUse"][0]["hooks"][0]
    runtime_dir = _configured_runtime_dir(copilot_hook["bash"], host="Copilot")
    _require_hook_runtime(runtime_dir, host="Codex+Copilot")
    fired = _run(
        ["bash", "-c", copilot_hook["bash"]],
        cwd=consumer,
        env=environment,
    )
    _require(
        fired.returncode == 0,
        what=(
            "all-target Copilot hook did not execute its shared DES runtime: "
            f"{fired.stderr or fired.stdout}"
        ),
    )


@pytest.mark.e2e_smoke
@pytest.mark.parametrize(
    ("platform", "platform_home_env"),
    (
        ("copilot", "COPILOT_HOME"),
        ("opencode", "OPENCODE_CONFIG_DIR"),
    ),
)
def test_same_real_wheel_native_lifecycle_is_owned_and_never_creates_claude(
    tmp_path: Path,
    tmp_path_factory: Any,
    platform: str,
    platform_home_env: str,
) -> None:
    """C6: public native install/uninstall owns only native and DES assets.

    This is intentionally an exact-wheel witness, rather than an in-process
    installer test.  It starts from the public candidate and its offline
    closure, clears inherited Python state, drives the installed console, and
    checks the host's rendered hook before exercising the installed
    uninstaller.  Thus a source-only success cannot mask an artefact whose
    package data, entry points, or runtime paths differ from the candidate.
    """
    _require_driving_port()
    candidate = _assembled_candidate(tmp_path_factory)
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    installed = _clean_install_probe(
        consumer,
        wheel=candidate.wheel,
        requirements_lock=candidate.wheel.parent
        / "offline-wheelhouse"
        / "requirements.lock",
    )
    venv = Path(installed["venv"])
    binary_dir = venv / ("Scripts" if os.name == "nt" else "bin")
    console = binary_dir / ("nwave-ai.exe" if os.name == "nt" else "nwave-ai")
    fake_home = Path(installed["fake_home"])
    host_home = tmp_path / f"{platform}-home"
    host_home.mkdir()
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment.update(
        {
            "HOME": str(fake_home),
            "USERPROFILE": str(fake_home),
            "PATH": f"{binary_dir}{os.pathsep}{environment.get('PATH', '')}",
            "PYTHONNOUSERSITE": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            platform_home_env: str(host_home),
        }
    )
    if platform == "copilot":
        environment["COPILOT_CLI"] = "1"

    provisioned = _run(
        [str(console), "install", "--yes", "--platform", platform],
        cwd=consumer,
        env=environment,
    )
    _require(
        provisioned.returncode == 0,
        what=(
            f"installed public wheel could not provision {platform}: "
            f"{provisioned.stderr or provisioned.stdout}"
        ),
    )
    _require(
        not (fake_home / ".claude").exists(),
        what=f"pure public {platform} installation created {fake_home / '.claude'}",
        why="a native-only target has no Claude discovery surface",
        how="return after host-neutral DES setup when Claude is unselected",
    )

    if platform == "copilot":
        owned_surface = host_home / "hooks" / "nwave-des.json"
        manifest = host_home / ".nwave-des-manifest.json"
        foreign_surface = host_home / "hooks" / "operator-hook.json"
        foreign_surface.parent.mkdir(parents=True, exist_ok=True)
        foreign_surface.write_text('{"operator": true}\n', encoding="utf-8")
        hook = json.loads(owned_surface.read_text(encoding="utf-8"))["preToolUse"][0][
            "hooks"
        ][0]["bash"]
        runtime_dir = _configured_runtime_dir(hook, host="Copilot public lifecycle")
        _require_hook_runtime(runtime_dir, host="Copilot public lifecycle")
        fired = _run(["bash", "-c", hook], cwd=consumer, env=environment)
        _require(
            fired.returncode == 0,
            what=(
                "installed Copilot hook did not execute before uninstall: "
                f"{fired.stderr or fired.stdout}"
            ),
        )
    else:
        owned_surface = host_home / "plugins" / "nwave-des.ts"
        manifest = host_home / ".nwave-des-manifest.json"
        foreign_surface = host_home / "plugins" / "operator-plugin.ts"
        foreign_surface.parent.mkdir(parents=True, exist_ok=True)
        foreign_surface.write_text("export default {};\n", encoding="utf-8")
        rendered = owned_surface.read_text(encoding="utf-8")
        runtime_match = re.search(r'PYTHONPATH: "([^"]+)"', rendered)
        _require(
            runtime_match is not None,
            what="OpenCode public shim has no literal PYTHONPATH",
        )
        runtime_dir = Path(runtime_match.group(1))
        _require_hook_runtime(runtime_dir, host="OpenCode public lifecycle")
        harness = consumer / "run-nwave-opencode-lifecycle.ts"
        harness.write_text(
            "import plugin from " + json.dumps(owned_surface.as_posix()) + ";\n"
            "const hooks = plugin({} as never);\n"
            "await hooks['tool.execute.before'](\n"
            "  { tool: 'write', args: {} },\n"
            "  { args: { file_path: 'probe.txt', content: 'probe' } },\n"
            ");\n"
            "console.log('nwave-opencode-lifecycle-executed');\n",
            encoding="utf-8",
        )
        fired = _run(["bun", "run", str(harness)], cwd=consumer, env=environment)
        _require(
            fired.returncode == 0
            and "nwave-opencode-lifecycle-executed" in fired.stdout,
            what=(
                "installed OpenCode hook did not execute before uninstall: "
                f"{fired.stderr or fired.stdout}"
            ),
        )

    operator_asset = fake_home / ".nwave" / "nWave" / "operator-state.json"
    operator_asset.parent.mkdir(parents=True, exist_ok=True)
    operator_asset.write_text('{"keep": true}\n', encoding="utf-8")
    global_config = fake_home / ".nwave" / "global-config.json"
    global_config.write_text('{"density": "lean"}\n', encoding="utf-8")

    removed = _run(
        [str(console), "uninstall", "--force"], cwd=consumer, env=environment
    )
    _require(
        removed.returncode == 0,
        what=(
            f"installed public wheel could not uninstall {platform}: "
            f"{removed.stderr or removed.stdout}"
        ),
    )
    _require(
        not owned_surface.exists() and not manifest.exists(),
        what=f"native {platform} nWave-owned surface survived public uninstall",
        how="delete only nWave's dedicated native file and manifest",
    )
    _require(
        not (fake_home / ".nwave" / "runtime" / "des").exists(),
        what="public native uninstall left host-neutral DES runtime behind",
        how="remove only the DES-owned runtime subtree",
    )
    _require(
        foreign_surface.is_file(),
        what=f"public native uninstall deleted operator {platform} surface",
        how="remove only the dedicated nWave file and manifest",
    )
    _require(
        operator_asset.is_file() and global_config.is_file(),
        what="public native uninstall deleted operator-owned shared .nwave asset",
        how="remove declared DES paths, not shared .nwave directories",
    )
    _require(
        not (fake_home / ".claude").exists(),
        what="public native uninstall created a Claude discovery surface",
        how="native-only uninstall must not instantiate Claude logging or reports",
    )
