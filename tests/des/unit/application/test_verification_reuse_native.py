"""Real compiler and executable observations through the candidate runner."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
)
from tests.des.unit.application.test_delivery_continuation import git


LIMIT = 100 * 1024 * 1024


def _allocated(root: Path) -> int:
    seen = set()
    total = 0
    for path in root.rglob("*"):
        stat = path.lstat()
        identity = stat.st_dev, stat.st_ino
        if identity not in seen:
            seen.add(identity)
            total += stat.st_blocks * 512
    return total


def _record(label: str, receipt: dict) -> None:
    destination = os.environ.get("NWAVE_REUSE_PROOF_DIR")
    if destination:
        path = Path(destination)
        path.mkdir(parents=True, exist_ok=True)
        (path / f"{label}.json").write_text(
            json.dumps(receipt, indent=2, default=str) + "\n"
        )


def _measure(root: Path, stack: str, label: str, expected: int = 1):
    candidate = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    runner = DeliveryContinuationRunner()
    started = time.monotonic()
    result = runner._with_candidate_worktree(
        root, candidate, ((sys.executable, "native.py", stack, str(expected)),)
    )
    duration = time.monotonic() - started
    records = sorted(
        (root / ".nwave/des/logs/native").glob("*.json"),
        key=lambda p: p.stat().st_mtime_ns,
    )
    evidence = json.loads(records[-1].read_text()) if records else []
    receipt = {
        "label": label,
        "candidate": candidate,
        "source_tree": subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip(),
        "root": str(root),
        "project_configuration": json.loads((root / ".nwave/config.json").read_text()),
        "elapsed_seconds": duration,
        "allocated_bytes": _allocated(root),
        "evidence": evidence,
        "outcome": dataclasses.asdict(result)
        if dataclasses.is_dataclass(result)
        else "measured",
    }
    compiler_lines = [
        line.removeprefix("COMPILER_INVOCATIONS=")
        for item in evidence
        for line in item["stdout"].splitlines()
        if line.startswith("COMPILER_INVOCATIONS=")
    ]
    receipt["compiler_invocations"] = (
        json.loads(compiler_lines[-1]) if compiler_lines else []
    )
    transient_bytes = sum(
        int(line.removeprefix("GENERATED_ALLOCATED_BYTES="))
        for item in evidence
        if not Path(item["cwd"]).is_relative_to(root)
        for line in item["stdout"].splitlines()
        if line.startswith("GENERATED_ALLOCATED_BYTES=")
    )
    receipt["retained_and_transient_bound_bytes"] = (
        receipt["allocated_bytes"] + transient_bytes
    )
    _record(f"{stack}-{label}", receipt)
    assert receipt["retained_and_transient_bound_bytes"] < LIMIT, receipt
    return result, receipt


def _success(result, receipt: dict, expected: int) -> Path:
    assert not isinstance(result, DeliveryOutcome), receipt
    stdout = receipt["evidence"][0]["stdout"]
    assert f"EXECUTED_TEST value={expected} independent=7" in stdout
    assert "TEST_EXECUTION=" in stdout
    assert "FRESH_EXECUTION=" in stdout
    return Path(
        next(
            line.removeprefix("FIXTURE_CWD=")
            for line in stdout.splitlines()
            if line.startswith("FIXTURE_CWD=")
        )
    )


def _units(receipt: dict) -> list[str]:
    return [
        item["unit"]
        for item in receipt["compiler_invocations"]
        if item["unit"] != "probe"
    ]


@pytest.mark.parametrize("stack", ["c", "rust"])
def test_fresh_native_reuse_delta_failures_and_native_configuration(
    tmp_path: Path, stack: str
) -> None:
    root = native_repository(tmp_path / stack, stack)
    changed = "changed.c" if stack == "c" else "changed/src/lib.rs"
    independent = "independent.c" if stack == "c" else "independent/src/lib.rs"
    result, cold = _measure(root, stack, "cold")
    workspace = _success(result, cold, 1)
    assert workspace != root
    assert (workspace / "target").resolve() == root / "target"
    source_mtime = (workspace / independent).stat().st_mtime_ns
    assert _units(cold)
    artifacts = {
        str(p.relative_to(root / "target")): p.stat().st_mtime_ns
        for p in (root / "target").rglob("*")
        if p.is_file() and "independent" in p.name
    }
    assert artifacts

    result, warm = _measure(root, stack, "unchanged-fresh")
    assert _success(result, warm, 1) == workspace
    assert warm["candidate"] == cold["candidate"]
    assert _units(warm) == _units(cold)
    assert (workspace / independent).stat().st_mtime_ns == source_mtime
    assert warm["evidence"][0]["stdout"] != cold["evidence"][0]["stdout"]
    executions = [
        next(
            line
            for line in receipt["evidence"][0]["stdout"].splitlines()
            if line.startswith("TEST_EXECUTION=")
        )
        for receipt in (cold, warm)
    ]
    assert executions[0] != executions[1], (
        "The compiled test's own process marker was replayed."
    )

    original = (root / changed).read_text()
    modified = (
        original.replace("return 1", "return 2")
        if stack == "c"
        else original.replace("{ 1 +", "{ 2 +")
    )
    assert len(modified) == len(original) and modified != original
    (root / changed).write_text(modified)
    commit(root)
    result, delta = _measure(root, stack, "same-size-delta", 2)
    _success(result, delta, 2)
    compiled = _units(delta)[len(_units(warm)) :]
    assert any("changed" in name for name in compiled)
    assert not any("independent" in name for name in compiled)
    if stack == "rust":
        assert "dependent" in compiled
    for relative, mtime in artifacts.items():
        assert (root / "target" / relative).stat().st_mtime_ns == mtime
    assert (workspace / independent).stat().st_mtime_ns == source_mtime
    assert (workspace / changed).read_text() == modified

    old_records = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / ".nwave/des/logs/native").glob("*.json")
    }
    (root / changed).write_text("deliberate compile error\n")
    commit(root)
    result, broken = _measure(root, stack, "compile-error", 2)
    assert isinstance(result, DeliveryOutcome), broken
    assert broken["evidence"][0]["exit"] != 0
    (root / changed).write_text(modified)
    commit(root)
    result, failed = _measure(root, stack, "test-failure", 99)
    assert isinstance(result, DeliveryOutcome), failed
    assert failed["evidence"][0]["exit"] != 0
    assert "EXECUTED_TEST value=2 independent=7" in failed["evidence"][0]["stdout"]
    for path, digest in old_records.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest

    (root / "flags.json").write_text('{"bias": 1}\n')
    commit(root)
    result, flags = _measure(root, stack, "native-flags", 3)
    _success(result, flags, 3)
    assert len(_units(flags)) > len(_units(failed))
    compiler = root / "compiler.py"
    compiler.write_text(compiler.read_text().replace("TOOL_BIAS = 0", "TOOL_BIAS = 1"))
    commit(root)
    result, toolchain = _measure(root, stack, "native-toolchain-wrapper", 4)
    _success(result, toolchain, 4)
    assert len(_units(toolchain)) > len(_units(flags))

    if stack == "c":
        (root / "changed.c").rename(root / "renamed.c")
        configuration = root / "CMakeLists.txt"
        configuration.write_text(
            configuration.read_text().replace("changed.c", "renamed.c")
        )
    else:
        (root / "changed/src/lib.rs").rename(root / "changed/src/renamed.rs")
        configuration = root / "changed/Cargo.toml"
        configuration.write_text(
            configuration.read_text() + '\n[lib]\npath = "src/renamed.rs"\n'
        )
    commit(root)
    (workspace / "undeclared-input").write_text("must not survive")
    (workspace / "ignored-residue").mkdir()
    (workspace / "ignored-residue/stale-input").write_text(
        "ignored is not retained authority"
    )
    result, renamed = _measure(root, stack, "rename-contamination", 4)
    _success(result, renamed, 4)
    assert not (workspace / changed).exists()
    assert not (workspace / "undeclared-input").exists()
    assert not (workspace / "ignored-residue").exists()

    config = root / ".nwave/config.json"
    config.write_text("{}\n")
    result, reference = _measure(root, stack, "cold-equivalence", 4)
    _success(result, reference, 4)
    assert reference["candidate"] == renamed["candidate"]
    assert Path(reference["evidence"][0]["cwd"]) != workspace
    shutil.rmtree(root / "target")


def test_repeated_candidate_measurement_keeps_isolated_cwd(tmp_path: Path) -> None:
    from tests.des.unit.application.test_delivery_continuation import repo

    root = repo(tmp_path / "repo", "value.txt", "one\n")
    (root / ".nwave").mkdir()
    (root / ".nwave/config.json").write_text(
        '{"verification":{"reuse":{"outputs":["target"]}}}'
    )
    candidate = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    command = ((sys.executable, "-c", "from pathlib import Path; print(Path.cwd())"),)
    first = DeliveryContinuationRunner()._with_candidate_worktree(
        root, candidate, command
    )
    second = DeliveryContinuationRunner()._with_candidate_worktree(
        root, candidate, command
    )
    assert not isinstance(first, DeliveryOutcome), first
    assert not isinstance(second, DeliveryOutcome), second
    assert first[1][0].stdout == second[1][0].stdout
    assert Path(second[1][0].stdout.strip()) != root


RECORDER = """#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path
TOOL_BIAS = 0
args = sys.argv[1:]
if os.environ.get("FIXTURE_STACK") == "rust":
    if "--crate-name" in args and any(arg.startswith("--emit") for arg in args):
        name = args[args.index("--crate-name") + 1]
    else:
        name = "probe"
    if TOOL_BIAS:
        args += ["--cfg", "tool_changed"]
else:
    name = next((a for a in args if a.endswith(".c")), "probe")
    args += ["-DTOOL_BIAS=" + str(TOOL_BIAS)]
with open(os.environ["FIXTURE_COMPILER_LOG"], "a") as log:
    log.write(json.dumps({"unit": name, "argv": args}) + "\\n")
sys.exit(subprocess.run(args, timeout=30).returncode)
"""

NATIVE = """import hashlib, json, os, subprocess, sys, uuid
from pathlib import Path
root = Path.cwd()
stack, expected = sys.argv[1], int(sys.argv[2])
out = root / "target"
out.mkdir(exist_ok=True)
env = dict(os.environ, FIXTURE_STACK=stack, EXPECTED=str(expected), FIXTURE_COMPILER_LOG=str(out / "compiler.jsonl"))
config = json.loads(Path("flags.json").read_text())
signature = hashlib.sha256(Path("compiler.py").read_bytes()).hexdigest()[:16]
if stack == "rust":
    env.pop("CARGO_TARGET_DIR", None)
    env.pop("CARGO_BUILD_TARGET_DIR", None)
    env["RUSTC_WRAPPER"] = str(root / "compiler.py")
    env["CARGO_INCREMENTAL"] = "0"
    env["RUSTFLAGS"] = "-Cmetadata=" + signature + (" --cfg flag_changed" if config["bias"] else "")
    commands = [["cargo", "test", "--offline", "--locked", "--workspace", "-j1", "--", "--nocapture"]]
else:
    commands = [
        ["cmake", "-S", ".", "-B", "target", "-DFLAG_BIAS=" + str(config["bias"]), "-DTOOL_SIGNATURE=" + signature, "-DCMAKE_C_COMPILER_LAUNCHER=" + str(root / "compiler.py")],
        ["cmake", "--build", "target", "--parallel", "1", "--verbose"],
        [str(out / "check"), str(expected)],
    ]
print("FIXTURE_CWD=" + str(root), flush=True)
print("FIXTURE_OUTPUT=" + str(out.resolve()), flush=True)
tracked = subprocess.run(["git", "ls-files", "-z"], check=True, capture_output=True, text=True).stdout.split("\\0")
print("SOURCE_SNAPSHOT=" + json.dumps({name: {"sha256": hashlib.sha256(Path(name).read_bytes()).hexdigest(), "mtime_ns": Path(name).stat().st_mtime_ns} for name in tracked if name}), flush=True)
for command in commands:
    print("NATIVE_COMMAND=" + json.dumps(command), flush=True)
    result = subprocess.run(command, env=env, timeout=60)
    if result.returncode:
        break
compiler_log = out / "compiler.jsonl"
print("COMPILER_INVOCATIONS=" + json.dumps([json.loads(line) for line in compiler_log.read_text().splitlines()] if compiler_log.exists() else []), flush=True)
allocated = sum(p.stat().st_blocks * 512 for p in out.rglob("*") if p.is_file())
print("GENERATED_ALLOCATED_BYTES=" + str(allocated), flush=True)
assert allocated < 100 * 1024 * 1024, allocated
if result.returncode:
    sys.exit(result.returncode)
print("FRESH_EXECUTION=" + str(uuid.uuid4()), flush=True)
"""

C_SOURCES = {
    "CMakeLists.txt": """cmake_minimum_required(VERSION 3.16)
project(reuse_fixture C)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -DFLAG_BIAS=${FLAG_BIAS} -DTOOL_SIGNATURE=${TOOL_SIGNATURE}")
add_library(changed STATIC changed.c)
add_library(independent STATIC independent.c)
add_executable(check check.c)
target_link_libraries(check PRIVATE changed independent)
""",
    "changed.c": "int changed(void) { return 1 + FLAG_BIAS + TOOL_BIAS; }\n",
    "independent.c": "int independent(void) { return 7; }\n",
    "check.c": """#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
int changed(void);
int independent(void);
int main(int argc, char **argv) {
    int actual = changed();
    printf("EXECUTED_TEST value=%d independent=%d\\n", actual, independent());
    printf("TEST_EXECUTION=%ld\\n", (long)getpid());
    return argc != 2 || actual != atoi(argv[1]) || independent() != 7;
}
""",
}

RUST_SOURCES = {
    "Cargo.toml": """[workspace]
members = ["changed", "independent", "dependent"]
resolver = "2"
[profile.dev]
debug = 0
incremental = false
""",
    "Cargo.lock": """# This file is automatically @generated by Cargo.
version = 4
[[package]]
name = "changed"
version = "0.1.0"
[[package]]
name = "dependent"
version = "0.1.0"
dependencies = ["changed", "independent"]
[[package]]
name = "independent"
version = "0.1.0"
""",
    "changed/Cargo.toml": '[package]\nname = "changed"\nversion = "0.1.0"\nedition = "2021"\n',
    "changed/src/lib.rs": "pub fn changed() -> i32 { 1 + if cfg!(flag_changed) { 1 } else { 0 } + if cfg!(tool_changed) { 1 } else { 0 } }\n",
    "independent/Cargo.toml": '[package]\nname = "independent"\nversion = "0.1.0"\nedition = "2021"\n',
    "independent/src/lib.rs": "pub fn independent() -> i32 { 7 }\n",
    "dependent/Cargo.toml": """[package]
name = "dependent"
version = "0.1.0"
edition = "2021"
[dependencies]
changed = { path = "../changed" }
independent = { path = "../independent" }
""",
    "dependent/src/lib.rs": """#[test]
fn observes_native_behavior() {
    let actual = changed::changed();
    println!("EXECUTED_TEST value={} independent={}", actual, independent::independent());
    println!("TEST_EXECUTION={}", std::process::id());
    assert_eq!(actual, std::env::var("EXPECTED").unwrap().parse::<i32>().unwrap());
    assert_eq!(independent::independent(), 7);
}
""",
}


def native_repository(root: Path, stack: str) -> Path:
    required = ("cargo", "rustc") if stack == "rust" else ("cmake", "cc", "make")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        pytest.skip("installed native fixture tools unavailable: " + ", ".join(missing))
    sources = RUST_SOURCES if stack == "rust" else C_SOURCES
    files = sources | {
        "native.py": NATIVE,
        "compiler.py": RECORDER,
        "flags.json": '{"bias": 0}\n',
        ".gitignore": "target/\n.nwave/des/\nlanes/\nignored-residue/\n",
        ".nwave/config.json": json.dumps(
            {"verification": {"reuse": {"outputs": ["target"]}}}
        ),
    }
    root.mkdir(parents=True)
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (root / "compiler.py").chmod(0o755)
    git(root, "init", "-q")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "Native reuse fixture")
    commit(root)
    return root


def commit(root: Path) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-qm", "native fixture state")
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
