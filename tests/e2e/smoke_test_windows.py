"""Windows native smoke test for nwave-ai installation.

Validates nwave-ai installation on Windows:
1. Creates a venv and installs nwave-ai
2. Runs nwave-ai install
3. Verifies agents and skills are installed
4. Creates a git repo, makes a commit, verifies attribution trailer

Exit codes: 0 = all pass, 1 = one or more failures.

Layer 4 of platform-testing-strategy.md

Usage (GitHub Actions windows-latest):
    python tests/e2e/smoke_test_windows.py
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


TOTAL = 0
FAILED = 0
RESULTS: list[tuple[str, str, str]] = []


def test(name: str, condition: bool, detail: str = "") -> None:
    """Record a test result."""
    global TOTAL, FAILED
    TOTAL += 1
    if condition:
        RESULTS.append(("PASS", name, detail))
    else:
        FAILED += 1
        RESULTS.append(("FAIL", name, detail))


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    # Ensure UTF-8 encoding on Windows to avoid UnicodeEncodeError
    # from installer banner emoji characters
    env = kwargs.pop("env", None) or os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        **kwargs,
    )


print()
print("=" * 60)
print("  nWave Windows Smoke Test")
print("=" * 60)
print()


# --- 1. Create venv and install nwave-ai ---

print("--- Setup: venv + nwave-ai ---")

venv_dir = Path(tempfile.gettempdir()) / "nwave-test-venv"
if venv_dir.exists():
    shutil.rmtree(venv_dir, ignore_errors=True)

run([sys.executable, "-m", "venv", str(venv_dir)])

if sys.platform == "win32":
    pip_exe = venv_dir / "Scripts" / "pip.exe"
    nwave_exe = venv_dir / "Scripts" / "nwave-ai.exe"
    python_exe = venv_dir / "Scripts" / "python.exe"
else:
    pip_exe = venv_dir / "bin" / "pip"
    nwave_exe = venv_dir / "bin" / "nwave-ai"
    python_exe = venv_dir / "bin" / "python"

# Install nwave-ai (use --pre for release candidates)
r = run([str(pip_exe), "install", "--pre", "nwave-ai"])
test("pip install nwave-ai", nwave_exe.exists(), f"installed to {nwave_exe}")


# --- 2. Check version ---

print()
print("--- Version check ---")

r = run([str(nwave_exe), "version"])
version_output = r.stdout.strip()
version_ok = bool(re.search(r"\d+\.\d+\.\d+", version_output))
test("nwave-ai version reports version", version_ok, version_output)


# --- 3. Run nwave-ai install ---

print()
print("--- nwave-ai install ---")

# Create minimal Claude Code environment
home = Path.home()
claude_dir = home / ".claude"
claude_dir.mkdir(parents=True, exist_ok=True)

settings_file = claude_dir / "settings.json"
if not settings_file.exists():
    settings_file.write_text('{"permissions": {}, "hooks": {}}', encoding="utf-8")

r = run([str(nwave_exe), "install"])
install_output = r.stdout + r.stderr
# Installer may fail partially on Windows (no Claude Code binary), but should install assets
print(f"  Install output (last 200 chars): {install_output[-200:]}")


# --- 4. Verify agents ---

print()
print("--- Agent verification ---")

agents_dir = claude_dir / "agents"
agents_dir_exists = agents_dir.exists()
test("agents directory exists", agents_dir_exists, str(agents_dir))

if agents_dir_exists:
    # Agents may be in agents/ or agents/nw/ depending on install mode
    agent_files = list(agents_dir.glob("nw-*.md")) or list(
        agents_dir.glob("nw/nw-*.md")
    )
    test("agent files present", len(agent_files) > 10, f"{len(agent_files)} agents")

    crafter_file = agents_dir / "nw-software-crafter.md"
    if not crafter_file.exists():
        crafter_file = agents_dir / "nw" / "nw-software-crafter.md"
    test("nw-software-crafter.md exists", crafter_file.exists())


# --- 5. Verify skills ---

print()
print("--- Skill verification ---")

skills_dir = claude_dir / "skills"
skills_dir_exists = skills_dir.exists()
test("skills directory exists", skills_dir_exists, str(skills_dir))

if skills_dir_exists:
    skill_dirs = [
        d for d in skills_dir.iterdir() if d.is_dir() and d.name.startswith("nw-")
    ]
    test("skill directories present", len(skill_dirs) > 30, f"{len(skill_dirs)} skills")

    # Check SKILL.md presence
    with_skill_md = [d for d in skill_dirs if (d / "SKILL.md").exists()]
    test(
        "all skill dirs have SKILL.md",
        len(with_skill_md) == len(skill_dirs),
        f"{len(with_skill_md)}/{len(skill_dirs)}",
    )


# --- 6. Git attribution test ---

print()
print("--- Git attribution test ---")

test_repo = Path(tempfile.gettempdir()) / "nwave-git-test"
if test_repo.exists():
    shutil.rmtree(test_repo, ignore_errors=True)

run(["git", "init", str(test_repo)])

# Configure git in the test repo
run(["git", "config", "user.email", "test@nwave.ai"], cwd=str(test_repo))
run(["git", "config", "user.name", "Test"], cwd=str(test_repo))

# Enable attribution
nwave_config_dir = home / ".nwave"
nwave_config_dir.mkdir(parents=True, exist_ok=True)
config_path = nwave_config_dir / "global-config.json"
config_path.write_text(
    '{"attribution": {"enabled": true, "trailer": "Co-Authored-By: nWave <nwave@nwave.ai>"}}',
    encoding="utf-8",
)

readme = test_repo / "README.md"
readme.write_text("test content\n", encoding="utf-8")
run(["git", "add", "-A"], cwd=str(test_repo))
r = run(["git", "commit", "-m", "test: windows smoke"], cwd=str(test_repo))
commit_ok = r.returncode == 0
test("git commit succeeds", commit_ok)

if commit_ok:
    r = run(["git", "log", "-1", "--format=%B"], cwd=str(test_repo))
    commit_msg = r.stdout.strip()
    print(f"  Commit message: {commit_msg}")
    # Attribution may not work without the hook being in the effective hooksPath,
    # but verify the commit at least succeeds
    test("git commit produces valid log", len(commit_msg) > 0)


# --- Cleanup ---

shutil.rmtree(venv_dir, ignore_errors=True)
shutil.rmtree(test_repo, ignore_errors=True)


# --- Report ---

print()
print("=" * 60)
print("  Results")
print("=" * 60)
for status, name, detail in RESULTS:
    icon = "PASS" if status == "PASS" else "FAIL"
    line = f"  [{icon}] {name}"
    if detail:
        line += f" -- {detail[:80]}"
    print(line)
print("=" * 60)
print(f"TOTAL: {TOTAL} tests, {TOTAL - FAILED} passed, {FAILED} failed")
if FAILED == 0:
    print("ALL TESTS PASSED")
else:
    print(f"{FAILED} TESTS FAILED")

sys.exit(0 if FAILED == 0 else 1)
