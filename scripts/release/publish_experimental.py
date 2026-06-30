#!/usr/bin/env python3
"""Publish the atdd_pure preview to the EXPERIMENTAL channel.

SEGREGATED from the prod/rc/dev release train (Ale 2026-06-07): this is a
standalone publisher for ONE branch (`feature/atdd-pure-staging`) to ONE private
target (`nWave-ai/nWave-experimental`). It is wired into NO workflow, creates NO
git tag, and touches NO shared release script except the privacy gate.

Why it exists
-------------
The atdd_pure version lives on `feature/atdd-pure-staging` (the OSS de-facto
trunk until release), NOT on master. We want access-controlled PREVIEW of it
without contaminating beta/prod/rc or the PyPI version namespace. The target repo
is PRIVATE, so access == repo collaborators.

Anti-contamination invariants (the whole point)
-----------------------------------------------
* SOURCE is pinned to `feature/atdd-pure-staging` — the script REFUSES any other
  branch (`--allow-branch` to override deliberately).
* Publishes the COMMITTED tree (`git archive <ref>`), never the dirty working
  tree, and never mutates this repo's `.git` (no worktree add, no config writes
  — safe under the shared-.git multi-worktree setup).
* NO PyPI / TestPyPI (public, un-access-controllable, pollutes the version
  sequence). Preview install is from the private repo only.
* NO `v*` tag on nwave-dev (tags wake the dev/rc/prod train).
* Version is stamped with a PEP 440 LOCAL label `+atddpure.<shortsha>` so it can
  never collide with the real dev/rc/prod version sequence.
* Reuses the canonical fail-closed privacy gate `strip_private_agents.py` as the
  SSOT (invoked as a subprocess, not imported) — segregating the *channel* must
  not mean duplicating the *privacy contract*, or private agents would leak to
  preview users on divergence.

Usage
-----
    # dry run (default): do everything, push nothing
    python scripts/release/publish_experimental.py

    # actually publish
    python scripts/release/publish_experimental.py --push
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


# --- constants ------------------------------------------------------------

SOURCE_BRANCH = "feature/atdd-pure-staging"
TARGET_SLUG = "nWave-ai/nWave-experimental"
TARGET_BRANCH = "main"

REPO_ROOT = Path(__file__).resolve().parents[2]
STRIP_SCRIPT = REPO_ROOT / "scripts" / "release" / "strip_private_agents.py"

# rsync filter — mirrors release-prod.yml's exclude/include block verbatim so the
# experimental tree carries the SAME public surface as a prod sync (private
# agents are then removed by strip_private_agents). `.git`/`.git*` are excluded so
# the TARGET's own .git survives the --delete.
RSYNC_FILTER: tuple[str, ...] = (
    "--exclude=.git",
    "--exclude=.git*",
    "--exclude=.github/",
    "--exclude=CLAUDE.local.md",
    "--exclude=SESSION_STATE*",
    "--exclude=build.log",
    "--exclude=setup.cfg",
    "--exclude=Pipfile",
    "--exclude=Pipfile.lock",
    "--exclude=_tmp/",
    "--exclude=htmlcov/",
    "--exclude=reports/",
    "--exclude=mutants/",
    "--exclude=nwave.egg-info/",
    "--exclude=nwave-ai.egg-info/",
    "--exclude=.execute-command-updated",
    "--exclude=.dependency-map.yaml",
    # docs: only guides + reference are public (override-before-exclude order)
    "--include=docs/",
    "--include=docs/guides/",
    "--include=docs/guides/**",
    "--include=docs/reference/",
    "--include=docs/reference/**",
    "--exclude=docs/analysis/",
    "--exclude=docs/internal/",
    "--exclude=docs/*",
    "--exclude=nWave/checklists/",
    "--exclude=nWave/public-workflows/",
    "--exclude=__pycache__/",
    "--exclude=.pytest_cache/",
    "--exclude=.mypy_cache/",
    "--exclude=.ruff_cache/",
    "--exclude=.coverage",
    "--exclude=.DS_Store",
    "--exclude=.venv/",
    "--exclude=.des/",
    "--exclude=.nwave/",
    "--exclude=mutation-reports/",
    "--exclude=.nwave-audit.log",
    "--exclude=.mutmut-cache",
    "--exclude=*.sqlite",
    "--exclude=test-des-hooks/",
    "--exclude=test-des-manual/",
    "--exclude=CHANGELOG.md",
    "--exclude=.commitlintrc.json",
    "--exclude=.pre-commit-config.yaml",
    "--exclude=.mcp.json",
    "--exclude=uv.lock",
)


# --- helpers --------------------------------------------------------------


def run(
    cmd: list[str], *, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a command, echoing it; capture nothing (stream to the console)."""
    print(f"  $ {' '.join(cmd)}{f'   (cwd={cwd})' if cwd else ''}")
    return subprocess.run(cmd, cwd=cwd, check=check, text=True)


def capture(cmd: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.run(
        cmd, cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


def current_branch() -> str:
    return capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT)


def short_sha(ref: str) -> str:
    return capture(["git", "rev-parse", "--short", ref], cwd=REPO_ROOT)


def export_committed_tree(ref: str, dest: Path) -> None:
    """Materialise the COMMITTED tree of `ref` into `dest` via git archive.

    git archive never touches `.git` config/refs (safe under the shared-.git
    multi-worktree setup) and excludes uncommitted + gitignored files by
    construction — we publish exactly what is committed, reproducibly.
    """
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", ref],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
    )
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, check=True)


def stamp_experimental_version(target: Path, sha: str) -> None:
    """Append a PEP 440 local label `+atddpure.<sha>` to project.version.

    Local labels are never part of the dev/rc/prod sequence, so this build can
    never collide with a real release version. Best-effort + non-fatal: the
    preview is installable regardless of the cosmetic version.
    """
    pyproject = target / "pyproject.toml"
    if not pyproject.is_file():
        print("  ! pyproject.toml absent in target — skipping version stamp")
        return
    import re

    text = pyproject.read_text(encoding="utf-8")
    # the first `version = "..."` line under [project]
    pattern = re.compile(r'(?m)^(version\s*=\s*")([^"]+)(")')
    label = f"+atddpure.{sha}"

    def _repl(m: re.Match[str]) -> str:
        base = m.group(2).split("+", 1)[0]
        return f"{m.group(1)}{base}{label}{m.group(3)}"

    new, n = pattern.subn(_repl, text, count=1)
    if n:
        pyproject.write_text(new, encoding="utf-8")
        print(f"  • version stamped {label}")
    else:
        print("  ! no version line matched — skipping version stamp")


README_TEMPLATE = REPO_ROOT / "nWave" / "templates" / "experimental-readme.md"


def write_experimental_readme(target: Path, sha: str, full_sha: str) -> None:
    """Overwrite the target README with experimental-channel install docs.

    The synced README is PyPI/installer-oriented (curl bootstrap, `pip install
    nwave-ai`). This channel has NO PyPI (Ale 2026-06-07) — preview users install
    LOCALLY from this clone. We replace README.md in the TARGET only (never the
    source repo's README, which prod legitimately ships with PyPI instructions),
    keeping the channel segregated and accurate.

    The content is authored as a template (`nWave/templates/experimental-readme.md`,
    nw-documentarist-owned) with three literal placeholders bound here. `.replace`
    (not `.format`) so any stray brace in the markdown is harmless.
    """
    readme = (
        README_TEMPLATE.read_text(encoding="utf-8")
        .replace("{sha}", sha)
        .replace("{full_sha}", full_sha)
        .replace("{target_slug}", TARGET_SLUG)
    )
    (target / "README.md").write_text(readme, encoding="utf-8")
    print("  • wrote experimental README.md (local-install, no PyPI)")


# --- main -----------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Publish the atdd_pure preview to nWave-ai/nWave-experimental "
        "(segregated from the prod/rc/dev train)."
    )
    ap.add_argument(
        "--push",
        action="store_true",
        help="Actually push to the experimental repo. Without it, runs a DRY RUN "
        "(builds + strips locally, pushes nothing).",
    )
    ap.add_argument(
        "--ref",
        default="HEAD",
        help="Committed ref to publish (default: HEAD of the current branch).",
    )
    ap.add_argument(
        "--allow-branch",
        action="store_true",
        help=f"Override the {SOURCE_BRANCH}-only guard (use deliberately).",
    )
    args = ap.parse_args()

    print("=== nWave EXPERIMENTAL publisher (segregated) ===")

    # 1) branch guard ------------------------------------------------------
    branch = current_branch()
    if branch != SOURCE_BRANCH and not args.allow_branch:
        print(
            f"REFUSED: current branch is '{branch}', not '{SOURCE_BRANCH}'. "
            "The experimental channel publishes only the atdd_pure branch. "
            "Pass --allow-branch to override deliberately.",
            file=sys.stderr,
        )
        return 2

    sha = short_sha(args.ref)
    full_sha = capture(["git", "rev-parse", args.ref], cwd=REPO_ROOT)
    print(f"source: {branch} @ {sha} ({full_sha})")
    print(f"target: {TARGET_SLUG}@{TARGET_BRANCH}  (PRIVATE)")
    print(f"mode:   {'PUSH' if args.push else 'DRY RUN (no push)'}")

    if not STRIP_SCRIPT.is_file():
        print(f"ERROR: privacy gate not found: {STRIP_SCRIPT}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="nwave-exp-") as tmp:
        tmpd = Path(tmp)
        export = tmpd / "source"
        target = tmpd / "target"

        # 2) export the committed tree ------------------------------------
        print("\n[1/5] export committed tree (git archive)")
        export_committed_tree(args.ref, export)

        # 3) clone the target (its own .git — no shared-.git contention) ---
        print("\n[2/5] clone experimental target")
        run(["gh", "repo", "clone", TARGET_SLUG, str(target), "--", "--depth", "1"])

        # 4) rsync the public surface + strip private agents (fail-closed) -
        print("\n[3/5] rsync public surface (prod filter) + --delete")
        rsync_exit = run(
            [
                "rsync",
                "-a",
                "--delete",
                *RSYNC_FILTER,
                f"{export}/",
                f"{target}/",
            ],
            check=False,
        ).returncode
        # 24 = "some source files vanished" — acceptable (matches prod)
        if rsync_exit not in (0, 24):
            print(f"ERROR: rsync failed ({rsync_exit})", file=sys.stderr)
            return 1

        print("\n[4/5] strip private agents (canonical fail-closed SSOT)")
        run([sys.executable, str(STRIP_SCRIPT), str(target)])

        stamp_experimental_version(target, sha)
        write_experimental_readme(target, sha, full_sha)

        # 5) commit + push ------------------------------------------------
        print("\n[5/5] commit + push")
        run(["git", "add", "-A"], cwd=target)
        status = capture(["git", "status", "--porcelain"], cwd=target)
        if not status:
            print("  • no changes vs current experimental HEAD — nothing to publish")
            return 0

        msg = (
            f"experimental: atdd-pure preview @ {sha}\n\n"
            f"Source: {SOURCE_BRANCH} {full_sha}\n"
            f"Channel: experimental (segregated; not beta/rc/prod, no PyPI)\n"
        )
        run(
            [
                "git",
                "-c",
                "user.name=nWave Experimental",
                "-c",
                "user.email=experimental@nwave.ai",
                "commit",
                "-m",
                msg,
            ],
            cwd=target,
        )

        if not args.push:
            print(
                "\nDRY RUN complete — built + stripped + committed locally, "
                "pushed NOTHING. Re-run with --push to publish."
            )
            print(f"  (staged tree previewable at {target} until this process exits)")
            # keep nothing; tempdir is cleaned on exit
            return 0

        run(["git", "push", "origin", f"HEAD:{TARGET_BRANCH}"], cwd=target)
        pushed = capture(["git", "rev-parse", "--short", "HEAD"], cwd=target)
        print(
            f"\n✅ PUBLISHED to {TARGET_SLUG}@{TARGET_BRANCH} "
            f"(commit {pushed}) — atdd-pure preview @ {sha}"
        )
        print(
            f"   Preview access = collaborators on the PRIVATE repo "
            f"https://github.com/{TARGET_SLUG}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
