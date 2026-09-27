#!/usr/bin/env python3
"""Publish the atdd_pure preview to the EXPERIMENTAL channel.

SEGREGATED from the prod/rc/dev release train (Ale 2026-06-07): this is a
standalone publisher for ONE branch (`atdd_pure_staging`) to ONE PUBLIC
target (`nWave-ai/nWave-experimental`). It is wired only to the experimental
workflow, creates NO git tag, and touches NO shared release script except the
privacy gate.

Why it exists
-------------
The atdd_pure version lives on `atdd_pure_staging` (the OSS de-facto
trunk until release), NOT on master. We want a PUBLIC PREVIEW of it without
contaminating beta/prod/rc or the PyPI version namespace. The target repository
is PUBLIC.

Anti-contamination invariants (the whole point)
-----------------------------------------------
* SOURCE is pinned to `atdd_pure_staging` — the script REFUSES any other
  branch (`--allow-branch` to override deliberately).
* Publishes the COMMITTED tree (`git archive <ref>`), never the dirty working
  tree, and never mutates this repo's `.git` (no worktree add, no config writes
  — safe under the shared-.git multi-worktree setup).
* NO PyPI / TestPyPI (pollutes the version sequence). Preview installation is
  from the public experimental repository only.
* NO `v*` tag on nwave-dev (tags wake the dev/rc/prod train).
* Version is stamped with a PEP 440 LOCAL label `+atddpure.<shortsha>` so it can
  never collide with the real dev/rc/prod version sequence.
* Reuses the canonical fail-closed `strip_private_agents.py` gate as the SSOT
  (invoked as a subprocess, not imported) — segregating the *channel* must not
  mean duplicating the stripping contract, or restricted agents would leak to
  public preview users on divergence.

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


# Direct public invocation has ``scripts/release`` on sys.path, not the
# repository root.  Match the canonical release-script bootstrap before using
# the shared public-wheel projection seam.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.release.experimental_migration_decision import (  # noqa: E402
    DecisionRefusal,
    projected_candidate,
    retry_message_matches,
    short_sha_of,
    validate_predecessor_metadata,
)
from scripts.release.patch_pyproject import patch_pyproject, tomli  # noqa: E402
from scripts.release.release_migration_decision import decode_decision  # noqa: E402


# --- constants ------------------------------------------------------------

SOURCE_BRANCH = "atdd_pure_staging"
TARGET_SLUG = "nWave-ai/nWave-experimental"
TARGET_BRANCH = "main"

STRIP_SCRIPT = REPO_ROOT / "scripts" / "release" / "strip_private_agents.py"
BUILD_DIST_SCRIPT = Path("scripts/build_dist.py")
STAGE_PUBLIC_WHEEL_DES_SCRIPT = Path("scripts/release/stage_public_wheel_des.py")
GENERATED_RUNTIME_PATHS = ("lib/python/des", "lib/nwave-runtime/des")

# rsync filter — mirrors release-prod.yml's exclude/include block verbatim so the
# experimental tree carries the SAME public surface as a prod sync (restricted
# agents are then removed by strip_private_agents). `.git`/`.git*` are excluded so
# the TARGET's own .git survives the --delete.
RSYNC_FILTER: tuple[str, ...] = (
    "--exclude=.git",
    # `.gitignore` MUST reach the target, and this include must stay ABOVE the
    # `.git*` exclude below (rsync takes the FIRST matching rule). Without it the
    # target keeps a stale `.gitignore` of its own, and the target's `git add`
    # then silently drops every path whose name collides with a generic pattern
    # there -- measured 2026-07-22: `src/des/adapters/driven/output/`,
    # `src/des/adapters/driven/build/` and 249 of the 250 files under
    # `tests/build/` never reached the published tree, because our own
    # `.gitignore` carries `build/` and `output/` WITH negations re-including
    # exactly those paths, and only the negations were missing on the far side.
    # The failure is silent on both sides: rsync copies the files, `git add`
    # ignores them, the publish exits 0, and a consumer discovers it as a
    # ModuleNotFoundError days later.
    "--include=.gitignore",
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
    "--exclude=.tla-swarm-model/",
    "--exclude=.claude/",
    "--exclude=.test_durations",
    "--exclude=.mailmap",
    "--exclude=ARCH_TECH_DEBT.md",
    "--exclude=CLAUDE.md",
)

#: Rsync deletes what is absent from the source -- but by default it PROTECTS what it
#: was told to EXCLUDE, so a path published once before an exclude existed stays on the
#: target forever and tightening the filter FREEZES it rather than removing it. Measured
#: 2026-07-22: `.github/` was excluded and still published, and eleven `docs/`
#: subdirectories the filter already excluded (analysis, internal, archive, feature,
#: research, evolution, ux, adrs, architecture, marketplace, reports) were all live on
#: the public target. The publish could never UN-publish anything. `--delete-excluded`
#: is what makes an exclude retroactive.
#: `--delete-excluded` is DANGEROUS without the protect rules below: it deletes what the
#: filter excludes, and the filter excludes `.git` PRECISELY so the target's own git
#: directory survives the sync. A blanket `--delete-excluded` therefore destroys the target
#: repository -- caught in a dry run 2026-07-22 with `.git/`, `.git/objects`, `.git/refs`
#: and `.git/HEAD` all listed for deletion. `P` (protect) is the rule that keeps a path on
#: the receiver regardless of exclusion, and it must precede the delete flags.
DELETE_MODE: tuple[str, ...] = (
    "--filter=P /.git/",
    "--filter=P /.git/**",
    "--delete",
    "--delete-excluded",
)


# --- helpers --------------------------------------------------------------


def run(
    cmd: list[str], *, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a command, echoing it; capture nothing (stream to the console)."""
    print(f"  $ {' '.join(cmd)}{f'   (cwd={cwd})' if cwd else ''}")
    return subprocess.run(
        cmd, cwd=cwd, check=check, text=True, stdin=subprocess.DEVNULL, timeout=600
    )


def capture(cmd: list[str], *, cwd: Path | None = None) -> str:
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    ).stdout.strip()


def current_branch() -> str:
    return capture(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT)


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
        stdin=subprocess.DEVNULL,
        timeout=120,
    )
    subprocess.run(
        ["tar", "-x", "-C", str(dest)],
        input=archive.stdout,
        check=True,
        timeout=120,
    )


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


def prepare_experimental_distribution(target: Path, sha: str) -> None:
    """Project the preview tree through the canonical public-wheel patcher."""
    stamp_experimental_version(target, sha)
    pyproject = target / "pyproject.toml"
    if not pyproject.is_file():
        raise RuntimeError("experimental target has no pyproject.toml")
    version = tomli.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    patch_pyproject(
        input_path=str(pyproject),
        output_path=str(pyproject),
        target_name="nwave-ai",
        target_version=version,
    )


def prepare_experimental_public_tree(
    target: Path,
    sha: str,
    full_sha: str,
    *,
    command_runner=None,
) -> None:
    """Produce the experimental public tree in the same wheel-ready shape as CI."""
    runner = run if command_runner is None else command_runner
    prepare_experimental_distribution(target, sha)
    runner(
        [
            sys.executable,
            str(target / BUILD_DIST_SCRIPT),
            "--project-root",
            str(target),
        ]
    )
    runner(
        [
            sys.executable,
            str(target / STAGE_PUBLIC_WHEEL_DES_SCRIPT),
            "--project-root",
            str(target),
            "--cleanup-dist",
        ]
    )
    # The public target's .gitignore excludes output/ and build/, including
    # these generated package paths. They are publisher-owned wheel inputs and
    # must be staged explicitly before the ordinary later `git add -A`.
    runner(["git", "-C", str(target), "add", "-f", *GENERATED_RUNTIME_PATHS])
    write_experimental_readme(target, sha, full_sha)


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


def target_snapshot(local_target: Path | None) -> tuple[str, str, str]:
    """Read predecessor commit, metadata and footer before any clone/write."""
    if local_target is not None:
        commit = capture(
            [
                "git",
                "--git-dir",
                str(local_target),
                "rev-parse",
                f"refs/heads/{TARGET_BRANCH}",
            ]
        )
        pyproject = capture(
            ["git", "--git-dir", str(local_target), "show", f"{commit}:pyproject.toml"]
        )
        message = capture(
            [
                "git",
                "--git-dir",
                str(local_target),
                "log",
                "-1",
                "--format=%B",
                TARGET_BRANCH,
            ]
        )
        return commit, pyproject, message
    commit = capture(
        [
            "gh",
            "api",
            f"repos/{TARGET_SLUG}/git/ref/heads/{TARGET_BRANCH}",
            "--jq",
            ".object.sha",
        ]
    )
    encoded = capture(
        [
            "gh",
            "api",
            f"repos/{TARGET_SLUG}/contents/pyproject.toml?ref={commit}",
            "--jq",
            ".content",
        ]
    )
    pyproject = subprocess.run(
        ["base64", "--decode"],
        input=encoded,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout
    message = capture(
        [
            "gh",
            "api",
            f"repos/{TARGET_SLUG}/commits/{commit}",
            "--jq",
            ".commit.message",
        ]
    )
    return commit, pyproject, message


def _branch_publication_unit(decision: object, branch: str):
    """Return the sole git_branch unit targeting ``branch``.

    The experimental publisher writes exactly one branch on one target; its
    staleness/lease value is that unit's declared ``predecessor`` commit, the
    same fact a real dev/rc/prod ``git_branch`` publication unit already
    carries. It is no longer read off a top-level ``decision.predecessor``
    (the package-identity fact), which never named a git commit under the
    real producer's schema.
    """
    matches = [
        unit
        for unit in decision.units  # type: ignore[attr-defined]
        if unit.kind == "git_branch" and unit.body.get("branch") == branch
    ]
    if len(matches) != 1:
        raise DecisionRefusal(
            f"migration decision must declare exactly one git_branch unit for {branch}"
        )
    return matches[0]


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
        "--migration-decision",
        type=Path,
        help="External migration decision bundle required with --push.",
    )
    ap.add_argument(
        "--target-local-repo",
        type=Path,
        help="Existing local bare Git target for controlled CLI verification.",
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
    ap.add_argument(
        "--project-into",
        type=Path,
        default=None,
        help="Non-publishing mode: materialise the publishable projection of "
        "--ref at DIR/target and stop BEFORE committing anything. Writes "
        "nothing to any target and refuses together with --push, so this "
        "publisher stays the single definition of what would be published.",
    )
    args = ap.parse_args()

    # Refuse the impossible combination before the branch guard and any clone:
    # the projection mode must never be reachable as a publication path.
    if args.project_into is not None and args.push:
        print(
            "WHAT: --project-into was combined with --push. WHY: the projection "
            "mode writes nothing and must never become a publication path. HOW: "
            "run --project-into DIR to inspect, then --push separately to publish.",
            file=sys.stderr,
        )
        return 2

    if args.target_local_repo is not None:
        local = args.target_local_repo.resolve()
        bare = subprocess.run(
            ["git", "--git-dir", str(local), "rev-parse", "--is-bare-repository"],
            capture_output=True,
            text=True,
            check=False,
            stdin=subprocess.DEVNULL,
            timeout=30,
        )
        if bare.returncode or bare.stdout.strip() != "true":
            print(
                "WHAT: local target is not an existing bare Git repository. WHY: controlled publication must not fall back to a public target. HOW: pass --target-local-repo PATH to a bare repository.",
                file=sys.stderr,
            )
            return 2
        args.target_local_repo = local
    if args.push and args.migration_decision is None:
        print(
            "WHAT: migration decision is required before publication. WHY: --push may write the public experimental channel. HOW: pass --migration-decision PATH with a bound record.",
            file=sys.stderr,
        )
        return 2

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

    full_sha = capture(["git", "rev-parse", args.ref], cwd=REPO_ROOT)
    sha = short_sha_of(full_sha)
    target_commit: str | None = None
    try:
        candidate = projected_candidate(REPO_ROOT, full_sha)
        if args.push:
            decision = decode_decision(args.migration_decision, REPO_ROOT)
            if (
                decision.candidate.source_sha,
                decision.candidate.name,
                decision.candidate.version,
            ) != (candidate.source_sha, candidate.name, candidate.version):
                raise DecisionRefusal(
                    "migration decision candidate does not match this projected source"
                )
            target_commit = _branch_publication_unit(decision, TARGET_BRANCH).body[
                "predecessor"
            ]
        else:
            decision = None
    except DecisionRefusal as error:
        print(
            f"WHAT: migration decision was refused. WHY: {error}. HOW: provide retained bytes and identities bound to this source and candidate.",
            file=sys.stderr,
        )
        return 2
    print(f"source: {branch} @ {sha} ({full_sha})")
    print(f"target: {TARGET_SLUG}@{TARGET_BRANCH}  (PUBLIC)")
    print(f"mode:   {'PUSH' if args.push else 'DRY RUN (no push)'}")

    if not STRIP_SCRIPT.is_file():
        print(f"ERROR: privacy gate not found: {STRIP_SCRIPT}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="nwave-exp-") as tmp:
        tmpd = Path(tmp)
        export = tmpd / "source"
        # In projection mode the materialised tree must OUTLIVE this process, so
        # it is placed beside the caller's directory rather than in the tempdir
        # that is cleaned on exit.  Everything else below is the identical
        # inline sequence that publication itself runs.
        if args.project_into is not None:
            args.project_into.mkdir(parents=True, exist_ok=True)
            target = args.project_into.resolve() / "target"
        else:
            target = tmpd / "target"

        # The target is read before clone/source projection, so stale records
        # refuse without spending work or touching the clone boundary.
        if decision is not None:
            try:
                commit, pyproject, message = target_snapshot(args.target_local_repo)
                if retry_message_matches(message, decision):
                    print(
                        "ALREADY_PUBLISHED: target footer matches Source, Candidate, and Decision-SHA256."
                    )
                    return 0
                validate_predecessor_metadata(
                    commit, pyproject, decision, target_commit
                )
            except (DecisionRefusal, subprocess.CalledProcessError) as error:
                print(
                    f"WHAT: migration decision was refused. WHY: {error}. HOW: refresh the record from the current target predecessor.",
                    file=sys.stderr,
                )
                return 2
        print("\n[1/5] clone and bind experimental predecessor")
        if args.target_local_repo is not None:
            run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    TARGET_BRANCH,
                    str(args.target_local_repo),
                    str(target),
                ]
            )
        else:
            run(["gh", "repo", "clone", TARGET_SLUG, str(target), "--", "--depth", "1"])
        # Prevent detached git maintenance in temporary clone: synchronize cleanup
        # to avoid "Directory not empty" failures when the tempdir is removed.
        # Both gc.autodetach and maintenance.autodetach must be false so that
        # subsequent git add/commit/push operations do not spawn background processes.
        run(["git", "-C", str(target), "config", "gc.autodetach", "false"])
        run(["git", "-C", str(target), "config", "maintenance.autodetach", "false"])
        if (
            decision is not None
            and capture(["git", "rev-parse", "HEAD"], cwd=target) != target_commit
        ):
            print(
                "WHAT: target predecessor changed during clone. WHY: the decision is stale. HOW: refresh the record and retry.",
                file=sys.stderr,
            )
            return 2

        # 2) export the committed tree ------------------------------------
        print("\n[2/5] export committed tree (git archive)")
        export_committed_tree(args.ref, export)

        # 4) rsync the public surface + strip restricted agents (fail-closed) -
        print("\n[3/5] rsync public surface (prod filter) + --delete --delete-excluded")
        rsync_exit = run(
            [
                "rsync",
                "-a",
                *DELETE_MODE,
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

        print("\n[4/5] strip restricted agents (canonical fail-closed SSOT)")
        run([sys.executable, str(STRIP_SCRIPT), str(target)])

        prepare_experimental_public_tree(target, sha, full_sha)

        # 5) commit + push ------------------------------------------------
        print("\n[5/5] commit + push")
        run(["git", "add", "-A"], cwd=target)

        # Projection mode stops HERE, before any commit exists: the index and
        # worktree now hold exactly what publication would commit, and the
        # caller reads it with plain `git write-tree` / `git diff`.
        if args.project_into is not None:
            print(f"PROJECTED: {target}")
            return 0

        status = capture(["git", "status", "--porcelain"], cwd=target)
        if not status:
            print("  • no changes vs current experimental HEAD — nothing to publish")
            return 0

        msg = (
            f"experimental: atdd-pure preview @ {sha}\n\n"
            f"Source: {full_sha}\n"
            f"Candidate: {candidate.name} {candidate.version}\n"
            f"Decision-SHA256: {decision.digest if decision else 'dry-run'}\n"
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

        lease = f"--force-with-lease=refs/heads/{TARGET_BRANCH}:{target_commit}"
        pushed_result = run(
            ["git", "push", lease, "origin", f"HEAD:{TARGET_BRANCH}"],
            cwd=target,
            check=False,
        )
        if pushed_result.returncode:
            print(
                "WHAT: target changed during publication. WHY: the predecessor lease no longer matches. HOW: re-read the target and revalidate the migration decision before retrying.",
                file=sys.stderr,
            )
            return 3
        pushed = capture(["git", "rev-parse", "--short", "HEAD"], cwd=target)
        target_label = (
            str(args.target_local_repo)
            if args.target_local_repo is not None
            else TARGET_SLUG
        )
        print(
            f"\n✅ PUBLISHED to {target_label}@{TARGET_BRANCH} "
            f"(commit {pushed}) — atdd-pure preview @ {sha}"
        )
        if args.target_local_repo is None:
            print(
                f"   Preview access = PUBLIC repository https://github.com/{TARGET_SLUG}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
