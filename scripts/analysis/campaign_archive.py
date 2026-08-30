#!/usr/bin/env python3
"""Land a paired campaign's evidence on a DURABLE substrate, as a harness step.

Why this file exists, stated as the incident rather than as a principle.
`F-K4-EVIDENCE-WIPED-NO-ARCHIVE-STEP` (backlog U17): every K4 campaign wrote
its evidence under an ephemeral `/tmp` root and no step of the harness ever
copied it anywhere else. A single `/tmp` wipe on 2026-08-22 destroyed camp6
($43.32, 1h51m of already-paid measurement), the campaign root
`/tmp/nwave-k4-150242df2/campaign` -- which the admission-row registry had
marked **ARCHIVE REQUIRED** since 2026-08-17 and which was never archived --
run 18 (the first terminal run of the lineage), runs 11-17, and the scoring
inputs `arms.json` / `nwave.json` / `control.json` / `blindscore-v2.json`.
Second occurrence of the same class.

The lesson encoded here is narrow and mechanical: **a marker is a designation,
a copy is a step**. `ARCHIVE REQUIRED` was true, visible, and honoured zero
times in five days. So archiving is not a flag, not a reminder and not an
operator habit -- `paired_campaign.main` calls it on its own, on the success
path AND on the give-up paths, because a campaign that died at pair 2 has
already paid for pair 1.

Correctness criterion (the backlog's own falsifier, pinned by
`tests/scripts/analysis/test_k4_campaign_evidence_archive.py`): after a
campaign, the scoring scripts run on the evidence of THAT campaign and find it
intact after `/tmp` is wiped, and a later campaign never overwrites an earlier
one.

Where durable is. In resolution order:

    1. an explicit `archive_root=` / `--archive-root`
    2. `$NWAVE_K4_EVIDENCE_ROOT`
    3. `~/.nwave/k4-evidence`

Not inside the repo by default: a campaign's evidence is measurement output,
not source, and a default that dirties the worktree gets deleted by the first
`git clean` -- swapping one wipe for another. `$HOME` survives both a `/tmp`
wipe and a reboot, which is exactly the property the criterion names.

A resolved root that is itself under the system temp directory is REFUSED
loud (`EphemeralArchiveRootError`), never silently accepted: an archive into
the thing that gets wiped is the original defect wearing the fix's name.

What is copied. The SCORING evidence -- `campaign.json`, every
`pair-*/…json|err|txt|md|log`, `verdicts.json`, and `arms.json` if it sits
beside the campaign -- never the per-arm workspaces, which are git clones and
virtualenvs measured in gigabytes. An archive step expensive enough to be
switched off is how the previous marker died. Everything skipped is NAMED in
`MANIFEST.json` with its reason, so a reader sees what is absent instead of
inferring completeness from silence.

Stdlib only, matching `paired_campaign.py`'s own portability constraint:
Python is the single runtime dependency, and there is deliberately no `des`
import.

    campaign_archive.py archive --campaign ./campaign [--id camp7]
    campaign_archive.py list
    campaign_archive.py verify --archive ~/.nwave/k4-evidence/<id>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


#: Overrides the default durable root. Named after the campaign family rather
#: than the tool so an operator setting it once covers every K4 script.
ARCHIVE_ROOT_ENV_VAR = "NWAVE_K4_EVIDENCE_ROOT"

#: Under `$HOME`, which survives a `/tmp` wipe and a reboot. NOT under the
#: repo: measurement output is not source, and `git clean` is a wipe too.
DEFAULT_ARCHIVE_ROOT = Path.home() / ".nwave" / "k4-evidence"

#: Suffixes an evidence file may carry. An allow-list, not a deny-list: a new
#: fat artifact type appearing in a campaign root must not silently start
#: costing gigabytes per archive.
EVIDENCE_SUFFIXES = (".json", ".err", ".txt", ".md", ".log", ".jsonl", ".csv")

MANIFEST_NAME = "MANIFEST.json"

#: Never archived even when it matches a suffix above: probe scratch space the
#: campaign itself treats as disposable.
SKIPPED_DIR_PREFIXES = (".headroom-probe-",)


class EphemeralArchiveRootError(RuntimeError):
    """The resolved archive root would not survive the thing it protects
    against. Loud by construction -- this is the original defect."""


class ArchiveAlreadyExistsError(RuntimeError):
    """A second campaign claimed an id already on disk. Refusing is the whole
    'a later campaign never overwrites an earlier one' half of the criterion:
    a silent overwrite destroys paid evidence exactly like the wipe did."""


def _explain(what: str, why: str, how: str) -> str:
    return f"WHAT: {what}\nWHY:  {why}\nHOW:  {how}\n"


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def resolve_archive_root(explicit: Path | None = None) -> Path:
    """Explicit > env > `~/.nwave/k4-evidence`, and never the temp directory.

    The refusal is deliberately not a warning: a campaign archived into `/tmp`
    reads as protected right up to the moment the evidence is gone, which is
    the failure mode this module was written after.
    """
    if explicit is not None:
        root = Path(explicit)
    elif os.environ.get(ARCHIVE_ROOT_ENV_VAR):
        root = Path(os.environ[ARCHIVE_ROOT_ENV_VAR])
    else:
        root = DEFAULT_ARCHIVE_ROOT

    root = root.expanduser()
    if _is_under(root, Path(tempfile.gettempdir())):
        raise EphemeralArchiveRootError(
            _explain(
                f"the resolved campaign-evidence root {root} is under the system "
                f"temp directory {tempfile.gettempdir()}.",
                "that root is exactly what a /tmp wipe or a reboot destroys, so "
                "archiving into it protects nothing while looking protected -- "
                "the F-K4-EVIDENCE-WIPED-NO-ARCHIVE-STEP defect wearing the "
                "fix's name.",
                f"point {ARCHIVE_ROOT_ENV_VAR} (or --archive-root) at a path "
                f"that survives a reboot, e.g. {DEFAULT_ARCHIVE_ROOT}.",
            )
        )
    return root


def default_campaign_id(campaign_root: Path, *, now: datetime | None = None) -> str:
    """Unique per archiving act, and readable by a human scanning the root.

    `<campaign-dir-name>-<UTC timestamp>-<6 hex of the source path>`. The
    timestamp carries the uniqueness; the path hash keeps two campaigns
    started in the same second under different roots apart. Never a bare
    directory name: two campaigns are routinely both called `campaign`.
    """
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(str(campaign_root.resolve()).encode()).hexdigest()[:6]
    name = campaign_root.resolve().name or "campaign"
    return f"{name}-{stamp}-{digest}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _classify(campaign_root: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    """Split the campaign tree into evidence to copy and entries to name.

    Total by construction: every entry reaches exactly one list, so nothing is
    dropped without appearing in the manifest's `skipped`.
    """
    keep: list[Path] = []
    skip: list[tuple[Path, str]] = []

    for entry in sorted(campaign_root.rglob("*")):
        relative = entry.relative_to(campaign_root)
        if any(
            part.startswith(SKIPPED_DIR_PREFIXES) for part in relative.parts
        ):  # probe scratch
            if entry.parent == campaign_root:
                skip.append((relative, "headroom-probe scratch workspace"))
            continue
        if entry.is_dir():
            has_evidence = any(
                child.suffix in EVIDENCE_SUFFIXES for child in entry.rglob("*")
            )
            if not has_evidence:
                skip.append(
                    (
                        relative,
                        "arm workspace (git clone / virtualenv): gigabytes, and "
                        "the delivered code is recoverable from its own commit",
                    )
                )
            continue
        if entry.suffix not in EVIDENCE_SUFFIXES:
            skip.append(
                (relative, f"not an evidence suffix ({entry.suffix or 'none'})")
            )
            continue
        if any(
            part
            for part in relative.parts[:-1]
            if part in {".git", "node_modules", ".venv", "__pycache__"}
        ):
            skip.append((relative, "inside a workspace toolchain directory"))
            continue
        keep.append(relative)

    return keep, skip


def archive_campaign(
    campaign_root: Path,
    *,
    archive_root: Path | None = None,
    campaign_id: str | None = None,
) -> Path:
    """Copy one campaign's scoring evidence to a durable, non-clobbering path.

    Returns the archive directory, which is directly consumable by the scoring
    scripts: `paired_quality_join.py --campaign <returned path>`.
    """
    campaign_root = Path(campaign_root)
    if not campaign_root.is_dir():
        raise FileNotFoundError(
            _explain(
                f"no campaign directory at {campaign_root}.",
                "there is nothing to archive, and a silent success here would "
                "report protection that does not exist.",
                "pass the directory `paired_campaign.py --out` wrote.",
            )
        )

    root = resolve_archive_root(archive_root)
    identifier = campaign_id or default_campaign_id(campaign_root)
    destination = root / identifier
    if destination.exists():
        raise ArchiveAlreadyExistsError(
            _explain(
                f"a campaign archive already exists at {destination}.",
                "overwriting it would destroy already-paid evidence -- the same "
                "loss the /tmp wipe caused, this time self-inflicted.",
                "archive under a different --id, or read the existing archive.",
            )
        )

    keep, skip = _classify(campaign_root)

    # `arms.json` is the campaign's own declaration and normally sits beside
    # the campaign directory (preflight writes it at `--root/arms.json`), so a
    # tree-local copy would miss it. Without it the archived numbers cannot be
    # tied back to the argv/env that produced them.
    sibling_arms = campaign_root.parent / "arms.json"

    destination.mkdir(parents=True)
    files: list[dict[str, object]] = []
    for relative in keep:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(campaign_root / relative, target)
        files.append(
            {
                "path": relative.as_posix(),
                "bytes": target.stat().st_size,
                "sha256": _sha256(target),
            }
        )
    if sibling_arms.is_file() and not (destination / "arms.json").exists():
        shutil.copy2(sibling_arms, destination / "arms.json")
        files.append(
            {
                "path": "arms.json",
                "bytes": (destination / "arms.json").stat().st_size,
                "sha256": _sha256(destination / "arms.json"),
                "note": "copied from the campaign's parent root",
            }
        )

    manifest = {
        "campaign_id": identifier,
        "source_root": str(campaign_root.resolve()),
        "source_root_was_ephemeral": _is_under(
            campaign_root, Path(tempfile.gettempdir())
        ),
        "archived_utc": datetime.now(timezone.utc).isoformat(),
        "files": sorted(files, key=lambda entry: str(entry["path"])),
        "skipped": [
            {"path": relative.as_posix(), "reason": reason} for relative, reason in skip
        ],
        "rescore_with": [
            f"paired_quality_join.py --campaign {destination} "
            f"--verdicts {destination / 'verdicts.json'}",
            f"paired_spread.py --campaign {destination}",
        ],
    }
    (destination / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=1) + "\n", encoding="utf-8"
    )
    return destination


def list_archives(archive_root: Path | None = None) -> list[Path]:
    """Every archived campaign under the durable root, oldest name first."""
    root = resolve_archive_root(archive_root)
    if not root.is_dir():
        return []
    return sorted(
        entry
        for entry in root.iterdir()
        if entry.is_dir() and (entry / MANIFEST_NAME).is_file()
    )


def verify_archive(archive: Path) -> list[str]:
    """Re-hash every manifest entry. Empty list means intact.

    An archive nobody can verify is a designation, not evidence -- the exact
    thing `ARCHIVE REQUIRED` turned out to be.
    """
    archive = Path(archive)
    manifest_path = archive / MANIFEST_NAME
    if not manifest_path.is_file():
        return [f"{archive}: no {MANIFEST_NAME}; this is not a campaign archive"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    problems: list[str] = []
    for entry in manifest.get("files", []):
        target = archive / str(entry["path"])
        if not target.is_file():
            problems.append(f"{entry['path']}: missing from the archive")
            continue
        if _sha256(target) != entry["sha256"]:
            problems.append(f"{entry['path']}: sha256 mismatch against the manifest")
    return problems


def archive_or_explain(campaign_root: Path, *, stream=None) -> Path | None:
    """The seam `paired_campaign.main` calls. Never raises.

    A campaign that produced real numbers must not be turned into a failure by
    its own bookkeeping step; but a failure to archive is announced in full,
    because silence here is indistinguishable from the defect.
    """
    stream = stream or sys.stderr
    try:
        destination = archive_campaign(campaign_root)
    except Exception as exc:
        stream.write(
            _explain(
                f"the campaign evidence under {campaign_root} was NOT archived "
                f"({type(exc).__name__}: {exc}).",
                "that evidence now exists only where the campaign wrote it. If "
                "that path is ephemeral, a wipe or a reboot destroys it and the "
                "campaign cannot be re-scored -- "
                "F-K4-EVIDENCE-WIPED-NO-ARCHIVE-STEP, third occurrence.",
                f"copy it yourself now, then archive with `campaign_archive.py "
                f"archive --campaign {campaign_root}`.",
            )
        )
        return None
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    archive_parser = sub.add_parser("archive", help="archive one campaign")
    archive_parser.add_argument("--campaign", required=True, type=Path)
    archive_parser.add_argument("--archive-root", type=Path, default=None)
    archive_parser.add_argument("--id", dest="campaign_id", default=None)

    list_parser = sub.add_parser("list", help="list archived campaigns")
    list_parser.add_argument("--archive-root", type=Path, default=None)

    verify_parser = sub.add_parser("verify", help="re-hash one archive")
    verify_parser.add_argument("--archive", required=True, type=Path)

    args = parser.parse_args(argv)

    try:
        if args.command == "archive":
            destination = archive_campaign(
                args.campaign,
                archive_root=args.archive_root,
                campaign_id=args.campaign_id,
            )
            print(destination)
            return 0
        if args.command == "list":
            for entry in list_archives(args.archive_root):
                print(entry)
            return 0
        problems = verify_archive(args.archive)
        for problem in problems:
            sys.stderr.write(f"{problem}\n")
        return 1 if problems else 0
    except (
        EphemeralArchiveRootError,
        ArchiveAlreadyExistsError,
        FileNotFoundError,
    ) as exc:
        sys.stderr.write(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
