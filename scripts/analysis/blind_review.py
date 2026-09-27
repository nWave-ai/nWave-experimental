#!/usr/bin/env python3
"""Make source-blind review STRUCTURAL, then map the verdicts back.

Lane C's contract says the rubric must be source-blind. A rubric that merely
*asks* a reviewer not to look at the arm label is a promise; this makes the label
unavailable, which is a different kind of guarantee. The reviewer receives
opaque delivery ids and cannot recover the arm from them, so "I did not know
which arm this was" stops being a claim about their discipline.

Two operations, and the sealing between them is the whole point:

    blind_review.py seal    --campaign <dir> --out <dir>
    blind_review.py unseal  --sealed <dir> --verdicts <scored.json> --out verdicts.json

`seal` writes into `--out` — safe to hand over WHOLE, because it cannot
physically contain the map:

* `deliveries/<opaque>/` — one directory per run, carrying exactly
  `DELIVERY-CHANGES.txt` and `DELIVERY.patch` — NOTHING that names the arm,
  the pair, the session, or the delivery's own workspace tree. `seal` never
  copies the workspace wholesale into the packet; `DELIVERY.patch` is a
  `git apply`-able unified diff against the arm's recorded BASELINE — the
  setup checkout commit read from the campaign's own `campaign.json`, falling
  back to the workspace's HEAD when no pin is recorded — built in a throwaway
  copy and cleaned up before `seal` returns. Diffing from the baseline rather
  than HEAD is what captures a delivery the arm COMMITTED: against HEAD, the
  tidier arm sealed as empty while a dirty one sealed in full;
* `REVIEW-THESE.txt` — the opaque ids to score, one per line, shuffled.

`seal` writes the opaque -> session map separately, to `--map`, which MUST be
a path outside `--out`. The reviewer must never read it; `unseal` needs it.

The opaque id is `sha256(session_id + salt)[:12]` with a random salt per campaign,
and the directories are emitted in shuffled order. Both matter: a hash without a
salt is stable across campaigns, so a reviewer who scored one campaign could
recognise a repeat; unshuffled emission leaks the arm through ordering, because
`pair-1/control` sorts before `pair-1/nwave` every single time. An id that is
merely "not the arm name" is not blind if its position tells you the same thing.

`unseal` takes verdicts keyed by opaque id and emits the `session_id`-keyed file
`paired_quality_join.py` consumes. It refuses on any opaque id it did not issue
and on any issued id the reviewer did not score — the same conservation rule the
join itself enforces, applied one step earlier, because a delivery that silently
loses its verdict here reappears downstream as a shrinking denominator.

The scored criteria keys ('1'..N) are NOT hardcoded here — they are read from
`scripts.analysis.k4.quality_rubric.CRITERIA_KEYS`, the single place the rubric
TEXT and its ADR-SSOT-002 Section 1a citations live. Fix a criterion or extend
the rubric there; this module only enforces the SHAPE that module's key set
implies.

Stdlib only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import secrets
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.domain.filesystem_projection import (
    STRICT_DELIVERY_POLICY,
    FilesystemProjectionError,
    GitPath,
    PathTransition,
    ProjectionIndeterminate,
    WorkspaceProjection,
    observe_workspace,
)
from scripts.analysis.k4 import quality_rubric
from scripts.analysis.paired_campaign import git_checkout_targets


if TYPE_CHECKING:
    from collections.abc import Callable


#: The strict delivery policy excludes setup content from every packet. Measured
#: 2026-08-07, before the first seal:
#: copying the arm's workspace wholesale would have shipped, to a reviewer,
#:
#:   * `.claude-k4/.credentials.json` -- a LIVE subscription OAuth token;
#:   * `.claude-k4/projects/<...>-pair-1-nwave/*.jsonl` -- the transcript, whose
#:     own directory NAME contains the arm;
#:   * `CLAUDE.md` and `.nwave/` -- artifacts only the treatment arm's setup
#:     creates.
#:
#: So the tool whose entire claim is that blinding is structural would have
#: broken blinding three ways and exfiltrated a credential once.
#:
#: The line drawn here is principled, not merely defensive: **exclude what SETUP
#: created, keep everything DELIVERY created.** The installer's own footprint
#: existed before any work and is not part of the work; it is scored, if at all,
#: from the campaign record, never from a packet that would name its own arm.
#: The exact block `nwave-ai project enable` appends to the subject's own
#: `.gitignore`. It cannot be handled by excluding the file: `.gitignore` is a
#: real project file a delivery may legitimately edit, so dropping it would hide
#: delivery content. But leaving it identified the treatment arm in exactly 3 of
#: 6 packets -- a perfect discriminator, found by auditing the sealed output
#: rather than by trusting the exclusion list.
#:
#: Same strict-delivery policy, applied inside a file instead of to a path:
#: strip what SETUP wrote, keep what DELIVERY wrote.
_SETUP_GITIGNORE_BLOCK = (
    "# nWave configuration (keep .nwave/config.json trackable)",
    ".nwave/*",
    "!.nwave/config.json",
)


def strip_setup_traces(delivery: Path) -> None:
    """Remove setup-written lines from a regular local `.gitignore` only.

    A packet workspace can contain delivery-controlled links.  ``Path.is_file``
    and ``write_text`` follow them, so treating a `.gitignore` symlink as a
    normal file would mutate its target while merely preparing a packet.
    Links are delivery content, never setup residue to rewrite.
    """
    gitignore = delivery / ".gitignore"
    if gitignore.is_symlink() or not gitignore.is_file():
        return
    lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
    kept = [ln for ln in lines if ln.strip() not in _SETUP_GITIGNORE_BLOCK]
    if len(kept) != len(lines):
        gitignore.write_text("\n".join(kept) + "\n", encoding="utf-8")


_MANIFEST_NAME = "DELIVERY-CHANGES.txt"

_STATUS_ADDED = "A"
_STATUS_MODIFIED = "M"
_STATUS_DELETED = "D"
_STATUS_RENAMED = "R"


def _excluded_path(rel_path: str) -> bool:
    """True when the canonical strict policy excludes this relative path."""
    try:
        return STRICT_DELIVERY_POLICY.excludes(GitPath(os.fsencode(rel_path)))
    except FilesystemProjectionError:
        # Git evidence paths must be valid GitPaths.  Treat an invalid value as
        # non-delivery here; the independent canonical observer still refuses
        # an unrepresentable filesystem path before capture can publish.
        return True


def _manifest_path(path: str) -> str:
    """Render any native path as unambiguous UTF-8 manifest text."""
    raw = os.fsencode(path)
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        decoded = ""
    if (
        decoded
        and not decoded.startswith("@b64:")
        and "\n" not in decoded
        and "\r" not in decoded
        and " -> " not in decoded
    ):
        return decoded
    return "@b64:" + base64.b64encode(raw).decode("ascii")


def _git_status(workspace: Path) -> list[tuple[str, str, str | None]]:
    """`(XY code, path, old_path-if-renamed)` for every entry, relative to HEAD.

    `-z` makes this path-safe: porcelain's default quoting is not reversible
    for every legal filename, and NUL-separated records are.
    """
    done = subprocess.run(
        [
            "git",
            "-C",
            str(workspace),
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
        stdin=subprocess.DEVNULL,
        timeout=30,
    )
    if done.returncode != 0:
        raise RuntimeError(f"git status failed in {workspace}: {done.stderr.strip()}")

    tokens = done.stdout.split("\0")
    entries: list[tuple[str, str, str | None]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if not tok:
            continue
        code, path = tok[:2], tok[3:]
        old_path = None
        if code[0] in ("R", "C"):
            # `-z` records renames as NEW-path NUL OLD-path NUL, in that
            # order -- verified against `git status --porcelain=v1 -z`
            # output for a `git mv`, not the manpage's prose description.
            old_path = tokens[i]
            i += 1
        entries.append((code, path, old_path))
    return entries


def _classify_diff_status(status: str) -> str | None:
    """One of the four manifest buckets, or None if the status can't be represented.

    These are `git diff --name-status` letters, not `git status` porcelain XY
    codes: the two encodings disagree (porcelain has no similarity score, the
    diff form has no `??`), and after intent-to-add an untracked path surfaces
    here as `A`. Anything outside A/M/D/R/C (typechange `T`, unmerged `U`, ...)
    is refused loudly by the caller rather than mislabelled.
    """
    letter = status[:1]
    if letter in ("R", "C"):
        return _STATUS_RENAMED
    if letter == "A":
        return _STATUS_ADDED
    if letter == "D":
        return _STATUS_DELETED
    if letter == "M":
        return _STATUS_MODIFIED
    return None


def _parse_name_status(raw: str) -> list[tuple[str, str, str | None]]:
    """`(status, path, old_path-if-renamed)` from `git diff --name-status -z`.

    `-z` records a rename as STATUS NUL OLD-path NUL NEW-path NUL -- the
    OPPOSITE order from `git status --porcelain=v1 -z`, verified against
    actual `git diff --name-status -z -M` output for a `git mv`, not the
    manpage's prose description.
    """
    tokens = raw.split("\0")
    entries: list[tuple[str, str, str | None]] = []
    i = 0
    while i + 1 < len(tokens):
        status = tokens[i]
        i += 1
        if not status:
            continue
        if status[0] in ("R", "C"):
            old_path, path = tokens[i], tokens[i + 1]
            i += 2
        else:
            old_path, path = None, tokens[i]
            i += 1
        entries.append((status, path, old_path))
    return entries


def _arm_baselines(campaign: Path) -> dict[str, str]:
    """Arm name -> pinned checkout commit, from the campaign's own config.

    The baseline is what makes a COMMITTED delivery capturable: a patch built
    against HEAD sees only the uncommitted remainder, so an arm that committed
    its delivery -- the better-behaved arm -- sealed as EMPTY while an arm
    that left everything dirty sealed in full, a systematic asymmetry
    penalising exactly the right behaviour. Read from `campaign.json`, never
    hardcoded. Recognition is delegated to
    `paired_campaign.git_checkout_targets` -- the same matcher the campaign
    runner validates setups with -- so a bare `git checkout <ref>` pins
    exactly like the `--detach` form; the last checkout step wins, as it
    would have in the actual setup sequence. An arm the config LISTS whose
    setup has no recognisable checkout step raises instead of falling back
    to HEAD: that silent fallback is the empty-packet bug again for any
    unmatched setup shape. Only a campaign with no `campaign.json` at all
    keeps the documented HEAD fallback -- there `seal` has no honest way to
    know where the subject's own history ends.
    """
    config = campaign / "campaign.json"
    if not config.is_file():
        return {}
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{config}: {exc}") from exc

    arms = data.get("arms")
    baselines: dict[str, str] = {}
    for arm, spec in arms.items() if isinstance(arms, dict) else ():
        setup = spec.get("setup", []) if isinstance(spec, dict) else []
        steps = tuple(
            tuple(step)
            for step in setup
            if isinstance(step, list) and all(isinstance(t, str) for t in step)
        )
        targets = git_checkout_targets(steps)
        if not targets:
            raise RuntimeError(
                f"{config}: arm '{arm}' has no recognisable `git checkout` "
                "setup step to pin its baseline"
            )
        baselines[arm] = targets[-1]
    return baselines


_PATCH_NAME = "DELIVERY.patch"


@dataclass(frozen=True)
class DeliveryCapture:
    """A strict, reconstructible delivery packet published at ``target``.

    ``baseline`` is the resolved commit the packet applies to. ``paths`` is
    the complete, sorted delivery projection that was compared after applying
    the packet in a new checkout of that commit. The projection itself stays
    private: it can carry delivery bytes, while the packet is the handoff.
    """

    workspace: Path
    target: Path
    baseline: str
    paths: tuple[str, ...]
    projection: WorkspaceProjection | None = None
    transitions: tuple[PathTransition, ...] = ()


class DeliveryCaptureError(RuntimeError):
    """A capture refusal that names WHAT failed, WHY, and a safe recovery."""


def _capture_refusal(what: str, why: str, how: str) -> DeliveryCaptureError:
    return DeliveryCaptureError(f"WHAT: {what}\nWHY:  {why}\nHOW:  {how}\n")


def _run_capture_git(
    workspace: Path, *args: str, timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    """Run a bounded git read/write inside an isolated capture workspace."""
    try:
        return subprocess.run(
            ["git", "-C", str(workspace), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _capture_refusal(
            "git could not complete a strict delivery capture",
            f"the capture cannot prove its baseline or reconstruction ({exc}).",
            "Make git and the delivery checkout readable, then capture again.",
        ) from exc


def _require_strict_baseline(workspace: Path, baseline: str) -> str:
    """Resolve the caller-supplied baseline without ever choosing HEAD."""
    if (
        not isinstance(baseline, str)
        or not baseline.strip()
        or baseline.upper() == "HEAD"
    ):
        raise _capture_refusal(
            "strict capture has no exact baseline commit",
            "a HEAD-relative patch loses delivery changes that were committed after the baseline.",
            "Pass the recorded immutable checkout commit as baseline, then capture again.",
        )
    resolved = _run_capture_git(
        workspace, "rev-parse", "--verify", "--quiet", f"{baseline}^{{commit}}"
    )
    if resolved.returncode != 0:
        raise _capture_refusal(
            "the requested baseline is not reachable from the delivery workspace",
            "a packet cannot be reconstructed against a commit this checkout does not have.",
            "Restore or fetch the recorded baseline commit, then capture again.",
        )
    return resolved.stdout.strip()


def _refuse_unsupported_delivery_state(workspace: Path) -> None:
    """Reject states the legacy writer could otherwise describe incompletely."""
    if not (workspace / ".git").is_dir():
        raise _capture_refusal(
            "the delivery workspace is not a supported git checkout",
            "strict capture needs its repository metadata to create and verify a patch.",
            "Point capture at a readable git checkout, then capture again.",
        )

    try:
        status = _git_status(workspace)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise _capture_refusal(
            "git status could not describe the delivery workspace",
            "strict capture must reject an unobservable working-tree state.",
            "Repair the checkout so `git status --porcelain=v1 -z` succeeds, then capture again.",
        ) from exc

    allowed = {" ", "?", "A", "M", "D", "R", "C"}
    unsupported = [
        code for code, _, _ in status if any(mark not in allowed for mark in code)
    ]
    if unsupported:
        raise _capture_refusal(
            "the delivery workspace has an unsupported git status",
            "unmerged, type-changed, or otherwise unrepresentable paths could make a packet incomplete.",
            "Resolve the working tree to ordinary add, modify, delete, rename, or clean paths, then capture again.",
        )

    staged = _run_capture_git(workspace, "ls-files", "--stage", "-z")
    if staged.returncode != 0:
        raise _capture_refusal(
            "git could not inspect tracked path modes",
            "strict capture must reject a packet when it cannot rule out submodules.",
            "Repair the checkout so `git ls-files --stage` succeeds, then capture again.",
        )
    if any(
        record.startswith("160000 ") for record in staged.stdout.split("\0") if record
    ):
        raise _capture_refusal(
            "the delivery workspace contains a submodule",
            "a submodule is a separate repository, not bytes a delivery patch can reconstruct safely.",
            "Replace the submodule with captured project files or remove it, then capture again.",
        )


def _delivery_projection(root: Path) -> WorkspaceProjection:
    """Use the canonical observer with the strict delivery policy directly."""
    try:
        return observe_workspace(root, STRICT_DELIVERY_POLICY)
    except ProjectionIndeterminate as exc:
        what = (
            "a delivery symlink has an unsafe target"
            if "symlink" in str(exc).lower()
            else "the delivery projection could not be observed canonically"
        )
        raise _capture_refusal(
            what,
            f"a packet cannot prove paths, bytes, modes, or links it could not inspect ({exc}).",
            "Make every delivery path stable and Git-representable, then capture again.",
        ) from exc


def _copy_delivery_projection(workspace: Path, target: Path) -> None:
    """Copy exactly the canonical strict delivery projection input shape.

    The caller validates links before it invokes ``strip_setup_traces``. This
    helper must not transform the copy: transformation before that validation
    could follow a delivery-controlled `.gitignore` link.
    """
    try:
        shutil.copytree(
            workspace,
            target,
            symlinks=True,
            ignore=_strict_delivery_ignore(workspace),
        )
    except OSError as exc:
        raise _capture_refusal(
            "the original delivery projection could not be prepared",
            f"a partial copy would make successful reconstruction a false claim ({exc}).",
            "Make the checkout readable and stable, then capture again.",
        ) from exc


def _strict_delivery_ignore(
    workspace: Path, *, retain_root_git: bool = False
) -> Callable[[str, list[str]], set[str]]:
    """Translate the canonical policy for ``copytree`` without a glob engine."""

    def ignore(directory: str, names: list[str]) -> set[str]:
        parent = Path(directory).relative_to(workspace)
        prefix = b"" if parent == Path() else os.fsencode(parent.as_posix())
        ignored: set[str] = set()
        for name in names:
            raw_name = os.fsencode(name)
            raw_path = raw_name if not prefix else prefix + b"/" + raw_name
            path = GitPath(raw_path)
            if retain_root_git and path.raw == b".git":
                continue
            if STRICT_DELIVERY_POLICY.excludes(path):
                ignored.add(name)
        return ignored

    return ignore


def _parse_delivery_manifest(manifest: Path) -> tuple[str, ...]:
    """Read the writer's compact manifest without accepting an invented form."""
    try:
        raw = manifest.read_bytes()
    except OSError as exc:
        raise _capture_refusal(
            "the delivery manifest could not be read for reconstruction",
            f"strict capture cannot verify a manifest it could not inspect ({exc}).",
            "Repair the packet writer and capture again.",
        ) from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _capture_refusal(
            "the delivery manifest is not UTF-8 text",
            "the established writer publishes a UTF-8 manifest, so this packet cannot be its complete result.",
            "Repair the packet writer and capture again.",
        ) from exc
    if not text:
        return ()
    if not text.endswith("\n"):
        raise _capture_refusal(
            "the delivery manifest has an unsupported shape",
            "the established writer terminates every non-empty manifest entry with a newline.",
            "Repair the packet writer and capture again.",
        )

    lines = tuple(text[:-1].split("\n"))
    for line in lines:
        if line.startswith(("A ", "M ", "D ")) and line[2:]:
            continue
        if line.startswith("R "):
            old_path, separator, new_path = line[2:].partition(" -> ")
            if old_path and separator and new_path:
                continue
        raise _capture_refusal(
            "the delivery manifest has an unsupported entry",
            "a strict packet needs the writer's exact A, M, D, or R path form.",
            "Repair the packet writer and capture again.",
        )
    return lines


def _reconstructed_manifest_lines(workspace: Path, baseline: str) -> tuple[str, ...]:
    """Rebuild the writer-format manifest from an applied reconstruction."""
    try:
        entries = _git_status(workspace)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise _capture_refusal(
            "git status could not describe the reconstructed delivery",
            "strict capture cannot verify manifest paths and statuses without git evidence.",
            "Repair the reconstruction checkout and capture again.",
        ) from exc

    untracked = [
        path for code, path, _ in entries if code == "??" and not _excluded_path(path)
    ]
    if untracked:
        added = _run_capture_git(workspace, "add", "-N", "--", *untracked)
        if added.returncode != 0:
            raise _capture_refusal(
                "git could not inspect untracked reconstructed delivery paths",
                "untracked paths must be included before the manifest can prove complete delivery coverage.",
                "Repair the reconstruction checkout and capture again.",
            )

    listed = _run_capture_git(workspace, "diff", "--name-status", "-z", "-M", baseline)
    if listed.returncode not in (0, 1):
        raise _capture_refusal(
            "git could not list reconstructed delivery changes",
            "strict capture cannot verify manifest paths and statuses without a complete diff.",
            "Repair the reconstruction checkout and capture again.",
        )

    lines: list[str] = []
    for status, path, old_path in _parse_name_status(listed.stdout):
        if _excluded_path(path) or (old_path and _excluded_path(old_path)):
            continue
        bucket = _classify_diff_status(status)
        if bucket is None:
            raise _capture_refusal(
                "the reconstructed delivery has an unsupported git status",
                "a strict manifest cannot represent this reconstructed change honestly.",
                "Repair the delivery state or packet writer, then capture again.",
            )
        if bucket == _STATUS_RENAMED:
            lines.append(
                f"{_STATUS_RENAMED} {_manifest_path(old_path or '')} -> {_manifest_path(path)}"
            )
        else:
            lines.append(f"{bucket} {_manifest_path(path)}")
    return tuple(sorted(lines))


def capture_delivery_packet(
    workspace: Path, target: Path, *, baseline: str
) -> DeliveryCapture:
    """Create a strict packet and prove it reconstructs the complete delivery.

    The caller must supply a reachable, non-``HEAD`` baseline. The legacy
    :func:`write_delivery_packet` remains compatible, including its historical
    fallback; this API intentionally has no fallback. It writes only into a
    private staging directory until a fresh clone at the exact baseline accepts
    the binary patch and has the same paths, file bytes, git modes, safe link
    targets, and deletions as the original delivery projection.

    Raises :class:`DeliveryCaptureError` on refusal. In every refusal case
    ``target`` remains absent; an existing target is never overwritten.
    """
    # All three capture roots must be absolute before any command changes
    # directory. In particular, git resolves clone sources relative to its
    # current directory, which is the private staging directory below.
    workspace = Path(workspace).resolve(strict=False)
    requested_target = Path(target)
    if requested_target.exists() or requested_target.is_symlink():
        raise _capture_refusal(
            f"strict capture target already exists: {requested_target}",
            "publishing over an existing packet could make a prior handoff appear verified.",
            "Choose a new empty target path, then capture again.",
        )
    target = requested_target.resolve(strict=False)
    if target.exists() or target.is_symlink():
        raise _capture_refusal(
            f"strict capture target already exists: {target}",
            "publishing over an existing packet could make a prior handoff appear verified.",
            "Choose a new empty target path, then capture again.",
        )
    _refuse_unsupported_delivery_state(workspace)
    resolved_baseline = _require_strict_baseline(workspace, baseline)

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _capture_refusal(
            "the strict capture target parent could not be created",
            f"a packet cannot be staged for atomic publication there ({exc}).",
            "Choose a writable target parent, then capture again.",
        ) from exc
    with tempfile.TemporaryDirectory(
        prefix="blind-review-strict-", dir=target.parent
    ) as temporary:
        staging = Path(temporary).resolve(strict=False)
        original = staging / "original"
        packet = staging / "packet"
        clone = staging / "clone"
        _copy_delivery_projection(workspace, original)
        # Validate the copied source before `strip_setup_traces`, which reads
        # and may write `.gitignore`. An absolute or escaping link must fail
        # while it is still only a link in our private copy.
        _delivery_projection(original)
        strip_setup_traces(original)
        original_projection = _delivery_projection(original)
        packet.mkdir()

        if write_delivery_packet(workspace, packet, resolved_baseline) != 0:
            raise _capture_refusal(
                "the delivery packet writer refused this workspace",
                "strict capture cannot publish a packet the established writer could not build completely.",
                "Resolve the writer's reported condition, then capture again.",
            )
        if {path.name for path in packet.iterdir()} != {_MANIFEST_NAME, _PATCH_NAME}:
            raise _capture_refusal(
                "the delivery packet has an unsupported shape",
                "a strict handoff is exactly its manifest and binary patch.",
                "Repair the packet writer so it emits only the documented packet files, then capture again.",
            )
        manifest_lines = _parse_delivery_manifest(packet / _MANIFEST_NAME)

        cloned = _run_capture_git(
            staging, "clone", "--no-local", "--no-checkout", str(workspace), str(clone)
        )
        if cloned.returncode != 0:
            raise _capture_refusal(
                "a fresh clone for strict reconstruction could not be created",
                "the packet must be proven in a new checkout, not in the source delivery tree.",
                "Make the source repository cloneable and the baseline reachable, then capture again.",
            )
        checked_out = _run_capture_git(
            clone, "checkout", "--detach", "--quiet", resolved_baseline
        )
        if checked_out.returncode != 0:
            raise _capture_refusal(
                "the exact baseline could not be checked out in a fresh clone",
                "a packet is useful only when its declared baseline can be reconstructed independently.",
                "Make the baseline available to a fresh clone, then capture again.",
            )
        baseline_projection = _delivery_projection(clone)
        try:
            patch_has_changes = bool((packet / _PATCH_NAME).read_bytes())
        except OSError as exc:
            raise _capture_refusal(
                "the binary delivery patch could not be read for reconstruction",
                f"strict capture cannot apply bytes it could not inspect ({exc}).",
                "Repair the packet writer and capture again.",
            ) from exc
        # `git apply --check` calls an empty file "No valid patches". An
        # empty packet is nevertheless valid when the complete original
        # projection equals the baseline; the comparison below proves that
        # case and rejects an empty tampered packet for a changed delivery.
        if patch_has_changes:
            applied = _run_capture_git(
                clone, "apply", "--check", "--binary", str(packet / _PATCH_NAME)
            )
            if applied.returncode != 0:
                raise _capture_refusal(
                    "the binary delivery patch does not apply to its exact baseline",
                    "a reviewer would receive a packet that cannot reconstruct the claimed delivery.",
                    "Repair the delivery state or packet writer, then capture again.",
                )
            applied = _run_capture_git(
                clone, "apply", "--binary", str(packet / _PATCH_NAME)
            )
            if applied.returncode != 0:
                raise _capture_refusal(
                    "the checked delivery patch could not be applied",
                    "a successful preflight without a completed application is not reconstruction proof.",
                    "Repair the patch application failure, then capture again.",
                )

        reconstructed_projection = _delivery_projection(clone)
        if reconstructed_projection != original_projection:
            raise _capture_refusal(
                "the reconstructed delivery projection differs from the original",
                "the packet changed, omitted, or added paths, bytes, modes, link targets, or deletions.",
                "Repair the delivery state or packet writer, then capture again.",
            )
        if manifest_lines != _reconstructed_manifest_lines(clone, resolved_baseline):
            raise _capture_refusal(
                "the delivery manifest differs from the reconstructed delivery",
                "the manifest must name the exact changed paths and statuses, including mode changes represented as M.",
                "Repair the packet writer and capture again.",
            )

        try:
            packet.replace(target)
        except OSError as exc:
            raise _capture_refusal(
                "the verified delivery packet could not be published",
                f"the packet remains staged and no complete target was published ({exc}).",
                "Make the target parent writable and choose an absent target, then capture again.",
            ) from exc

    return DeliveryCapture(
        workspace=workspace,
        target=target,
        baseline=resolved_baseline,
        paths=tuple(os.fsdecode(path.raw) for path, _ in original_projection.states),
        projection=original_projection,
        transitions=baseline_projection.transitions_to(original_projection),
    )


def write_delivery_packet(workspace: Path, target: Path, baseline: str | None) -> int:
    """`DELIVERY-CHANGES.txt` + `DELIVERY.patch`: every non-setup delivery
    change from `baseline` (the arm's recorded checkout commit, or this
    workspace's own HEAD when no pin exists) to the working tree -- one
    manifest and one `git apply`-able unified diff, the compact substitute
    for copying the workspace wholesale.

    Diffing from the BASELINE is the load-bearing choice: a diff against HEAD
    sees only uncommitted work, so an arm that committed its delivery sealed
    as EMPTY while an arm that left everything dirty sealed in full. Measured
    on campaign 6, 2026-08-20: pair-3/nwave committed 8 files (+736/-9) and
    its packet held only runtime residue.

    Both files are built from ONE evidence read (`git diff --name-status`,
    baseline -> working tree) inside a throwaway copy of `workspace`, so the
    manifest and the patch can never disagree about what a delivery changed,
    and the source lane's tree and git index are never touched.
    `strip_setup_traces` runs there first: a setup-only `.gitignore` edit
    then stops differing and never reaches the diff, while a legitimate edit
    mixed into the same file still shows up, minus the setup lines. The copy
    (including `.git`, needed to diff at all) is removed before this function
    returns.
    """
    patch_path = target / _PATCH_NAME
    if not (workspace / ".git").is_dir():
        sys.stderr.write(
            "WHAT: the delivery workspace is missing or is not a git checkout.\n"
            f"      - {workspace}\n"
            "WHY:  writing an empty packet here would look identical to a delivery\n"
            "      that legitimately changed nothing -- silent-empty and\n"
            "      silent-unsupported must not be the same output.\n"
            "HOW:  point the campaign at a real git checkout for this run, then\n"
            "      re-seal. Nothing was written for this delivery.\n"
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="blind-review-patch-") as tmp:
        tmp_ws = Path(tmp) / "ws"
        try:
            # Ignore the canonical strict projection's excluded content so the
            # throwaway copy never holds it. Root `.git` is retained only for
            # the diff command; it remains excluded from packet paths.
            shutil.copytree(
                workspace,
                tmp_ws,
                symlinks=True,
                ignore=_strict_delivery_ignore(workspace, retain_root_git=True),
            )
        except OSError as exc:
            sys.stderr.write(
                "WHAT: could not copy the delivery workspace to build its patch.\n"
                f"      - {exc}\n"
                "WHY:  a patch built on a partial copy could silently omit real\n"
                "      delivery changes.\n"
                "HOW:  make sure the delivery workspace is a readable, well-formed\n"
                "      git checkout, then re-seal.\n"
            )
            return 1
        strip_setup_traces(tmp_ws)

        base = baseline if baseline is not None else "HEAD"
        if baseline is not None:
            resolved = subprocess.run(
                [
                    "git",
                    "-C",
                    str(tmp_ws),
                    "rev-parse",
                    "--verify",
                    "--quiet",
                    f"{baseline}^{{commit}}",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="surrogateescape",
                stdin=subprocess.DEVNULL,
                timeout=30,
            )
            if resolved.returncode != 0:
                sys.stderr.write(
                    "WHAT: the campaign records a baseline commit this workspace does not have.\n"
                    f"      - {baseline} is not a commit in {workspace}\n"
                    "WHY:  silently falling back to HEAD would rebuild the very asymmetry\n"
                    "      the baseline exists to remove: a committed delivery would seal\n"
                    "      as empty again.\n"
                    "HOW:  fix the arm's setup record in campaign.json (or re-run the arm\n"
                    "      so its checkout matches), then re-seal.\n"
                )
                return 1

        try:
            entries = _git_status(tmp_ws)
        except RuntimeError as exc:
            sys.stderr.write(
                "WHAT: could not read the delivery-packet git evidence.\n"
                f"      - {exc}\n"
                "WHY:  a packet built without evidence would either be empty (looks\n"
                "      like nothing changed) or invented, and both are dishonest.\n"
                "HOW:  make sure the delivery workspace is a readable git checkout, then\n"
                "      re-seal.\n"
            )
            return 1

        untracked = [
            path
            for code, path, _ in entries
            if code == "??" and not _excluded_path(path)
        ]
        if untracked:
            # `-N` (intent-to-add) is what makes `git diff` see an
            # untracked path at all -- without it, a path git never indexed
            # is invisible to the diff machinery, staged or not.
            added = subprocess.run(
                ["git", "-C", str(tmp_ws), "add", "-N", "--", *untracked],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="surrogateescape",
                stdin=subprocess.DEVNULL,
                timeout=30,
            )
            if added.returncode != 0:
                sys.stderr.write(
                    "WHAT: could not stage untracked delivery paths to build the packet.\n"
                    f"      - git add -N: {added.stderr.strip()}\n"
                    "WHY:  without intent-to-add, an untracked delivery file is invisible\n"
                    "      to `git diff`, so the packet would silently omit it.\n"
                    "HOW:  make sure the delivery workspace is a readable git checkout, then\n"
                    "      re-seal.\n"
                )
                return 1

        listed = subprocess.run(
            ["git", "-C", str(tmp_ws), "diff", "--name-status", "-z", "-M", base],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            stdin=subprocess.DEVNULL,
            timeout=30,
        )
        if listed.returncode not in (0, 1):
            sys.stderr.write(
                "WHAT: git diff --name-status failed while building a delivery packet.\n"
                f"      - {listed.stderr.strip()}\n"
                "WHY:  a packet built on a failed listing would silently omit real\n"
                "      delivery changes.\n"
                "HOW:  make sure the delivery workspace is a readable git checkout, then\n"
                "      re-seal.\n"
            )
            return 1

        lines: list[str] = []
        paths: list[str] = []
        unrepresentable: list[tuple[str, str]] = []
        for status, path, old_path in _parse_name_status(listed.stdout):
            if _excluded_path(path) or (old_path and _excluded_path(old_path)):
                continue
            bucket = _classify_diff_status(status)
            if bucket is None:
                unrepresentable.append((status, path))
                continue
            paths.append(path)
            if old_path:
                paths.append(old_path)
            if bucket == _STATUS_RENAMED:
                lines.append(
                    f"{_STATUS_RENAMED} {_manifest_path(old_path or '')} -> {_manifest_path(path)}"
                )
            else:
                lines.append(f"{bucket} {_manifest_path(path)}")

        if unrepresentable:
            sys.stderr.write(
                "WHAT: a delivery-changed path cannot be represented honestly in its packet.\n"
                + "".join(
                    f"      - {status} {path}\n" for status, path in unrepresentable
                )
                + "WHY:  an unrecognised git status (typechange, unmerged conflict, ...)\n"
                "      dropped silently would make the packet claim completeness it\n"
                "      does not have.\n"
                "HOW:  resolve the working tree state, or teach `_classify_diff_status`\n"
                "      the new status honestly, then re-seal. Do not hand out this packet.\n"
            )
            return 1

        lines.sort()
        (target / _MANIFEST_NAME).write_text(
            ("\n".join(lines) + "\n") if lines else "", encoding="utf-8"
        )

        if not paths:
            patch_path.write_text("", encoding="utf-8")
            return 0

        diff = subprocess.run(
            [
                "git",
                "-C",
                str(tmp_ws),
                "diff",
                "--no-color",
                "--binary",
                "-M",
                base,
                "--",
                *paths,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="surrogateescape",
            stdin=subprocess.DEVNULL,
            timeout=30,
        )
        if diff.returncode not in (0, 1):
            sys.stderr.write(
                "WHAT: git diff failed while building a delivery patch.\n"
                f"      - {diff.stderr.strip()}\n"
                "WHY:  a patch built on a failed diff would silently ship whatever\n"
                "      partial output git produced.\n"
                "HOW:  make sure the delivery workspace is a readable git checkout, then\n"
                "      re-seal.\n"
            )
            return 1
        patch_path.write_text(diff.stdout, encoding="utf-8", errors="surrogateescape")
    return 0


#: JSON keys specific to the OAuth credential file `seed_auth.py` copies
#: (`claudeAiOauth`) and its usual shape (`accessToken`/`refreshToken`) --
#: structural, unlike a generic filename a legitimate delivery could
#: plausibly mention in its own code or docs.
_CREDENTIAL_SENTINELS = ("claudeAiOauth", "accessToken", "refreshToken")


def _diff_header_paths(patch_text: str) -> set[str]:
    """Every path named in a unified diff's own structural headers.

    Independent of the packet writer's own evidence read (`_parse_name_status`
    over `git diff --name-status`): if that parsing ever had a bug, the paths
    git actually wrote into `diff --git`/`---`/`+++`/rename headers would
    still be exactly what a reviewer's `git apply` sees, so checking them is
    a second axis on the same claim, not a repeat of it.
    """
    paths: set[str] = set()
    for line in patch_text.splitlines():
        if line.startswith("diff --git a/"):
            rest = line[len("diff --git a/") :]
            marker = " b/"
            idx = rest.find(marker)
            if idx != -1:
                paths.add(rest[:idx])
                paths.add(rest[idx + len(marker) :])
        elif line.startswith("--- a/"):
            paths.add(line[len("--- a/") :])
        elif line.startswith("+++ b/"):
            paths.add(line[len("+++ b/") :])
        elif line.startswith(("rename from ", "copy from ", "rename to ", "copy to ")):
            paths.add(line.split(" ", 2)[2])
    return paths


def _leak_scan(target: Path, *, session_id: str, arm: str) -> list[str]:
    """Structural checks over the packet's own two files -- a verification
    net over the exclusion filters above, not a substitute for them.

    Deliberately narrow: a legitimate delivery can mention a generic
    filename like `.git` or `CLAUDE.md` in its own code or prose, so this
    never bans those names as free-text substrings -- that rejects real
    delivery content while an attacker dodges it with a comment. Checked
    instead: the packet holds exactly the two expected files; every path the
    manifest and the patch's own diff headers name would have survived
    `_excluded_path`; none of the setup's exact `.gitignore` lines survived
    as an added patch line; and, the one substring check left because these
    are this packet's own actual identity rather than a generic word, this
    delivery's session id, its arm name, and credential-shaped JSON keys.
    Findings never repeat the identity value they found -- that would leak
    it into the very refusal meant to stop it.
    """
    if not target.is_dir():
        return [f"{target}: packet directory is missing"]

    found: list[str] = []
    present = {p.name for p in target.iterdir()}
    extra = sorted(present - {_MANIFEST_NAME, _PATCH_NAME})
    if extra:
        found.append(
            f"packet holds {extra} too -- a compact packet is exactly "
            f"{_MANIFEST_NAME} + {_PATCH_NAME}, nothing else"
        )

    manifest_path = target / _MANIFEST_NAME
    manifest_text = (
        manifest_path.read_text(encoding="utf-8", errors="replace")
        if manifest_path.is_file()
        else ""
    )
    for line in manifest_text.splitlines():
        entry_paths = line[2:].split(" -> ") if line[:2] == "R " else [line[2:]]
        if any(_excluded_path(p) for p in entry_paths):
            found.append(f"{_MANIFEST_NAME}: an excluded path resurfaced ({line!r})")

    patch_path = target / _PATCH_NAME
    patch_text = (
        patch_path.read_text(encoding="utf-8", errors="replace")
        if patch_path.is_file()
        else ""
    )
    for header_path in _diff_header_paths(patch_text):
        if _excluded_path(header_path):
            found.append(
                f"{_PATCH_NAME}: an excluded path resurfaced ({header_path!r})"
            )
    added_lines = {
        line[1:]
        for line in patch_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    }
    if added_lines & set(_SETUP_GITIGNORE_BLOCK):
        found.append(f"{_PATCH_NAME}: a setup .gitignore line survived stripping")

    for name, text in ((_MANIFEST_NAME, manifest_text), (_PATCH_NAME, patch_text)):
        if session_id and session_id in text:
            found.append(f"{name}: contains this delivery's own session id")
        if arm and arm in text:
            found.append(f"{name}: contains this delivery's own arm name")
        for sentinel in _CREDENTIAL_SENTINELS:
            if sentinel in text:
                found.append(f"{name}: contains a credential-shaped key ({sentinel})")

    return found


def opaque_id(session_id: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{session_id}".encode()).hexdigest()[:12]


def seal(campaign: Path, out: Path, map_path: Path) -> int:
    """Emit blinded delivery packets plus the sealed map."""
    resolved_out = out.resolve()
    resolved_map = map_path.resolve()
    if resolved_out == resolved_map or resolved_out in resolved_map.parents:
        sys.stderr.write(
            f"WHAT: the map {resolved_map} is inside the bundle {resolved_out}.\n"
            "WHY:  the bundle exists to be handed over WHOLE. A map inside it turns\n"
            "      blinding back into a procedure that one `cp -r` defeats.\n"
            "HOW:  point --map somewhere outside --out.\n"
        )
        return 1

    from scripts.analysis.paired_spread import Usable, classify

    runs: list[tuple[str, Path]] = []
    for path in sorted(campaign.glob("pair-*/*.json")):
        outcome = classify(
            f"{path.parent.name}/{path.stem}", path.read_text(errors="replace")
        )
        if isinstance(outcome, Usable):
            runs.append((outcome.session_id, path))

    if not runs:
        sys.stderr.write(
            "WHAT: no usable run found in the campaign.\n"
            "WHY:  sealing nothing produces an empty review that looks conducted.\n"
            "HOW:  check the campaign with paired_spread.py first.\n"
        )
        return 1

    try:
        baselines = _arm_baselines(campaign)
    except RuntimeError as exc:
        sys.stderr.write(
            "WHAT: could not derive baseline commits from the campaign's own config.\n"
            f"      - {exc}\n"
            "WHY:  without a recorded checkout pin per arm, a committed delivery would\n"
            "      silently seal as empty (a diff from HEAD sees only uncommitted\n"
            "      work).\n"
            "HOW:  make campaign.json valid JSON and give every listed arm a\n"
            "      `git checkout` setup step (bare or --detach), then re-seal.\n"
        )
        return 1

    salt = secrets.token_hex(16)
    mapping: dict[str, str] = {}
    deliveries = out / "deliveries"
    deliveries.mkdir(parents=True, exist_ok=True)

    for session_id, payload_path in runs:
        token = opaque_id(session_id, salt)
        mapping[token] = session_id
        target = deliveries / token
        target.mkdir(exist_ok=True)
        # The arm's workspace, not its result payload: the payload carries
        # session and cost, which is exactly what the reviewer must not see.
        # The packet writer never copies the workspace into `target`: it
        # builds its own throwaway copy and cleans it up, so `target` only
        # ever holds the two files a reviewer needs.
        workspace = payload_path.parent / payload_path.stem
        if (
            write_delivery_packet(workspace, target, baselines.get(payload_path.stem))
            != 0
        ):
            return 1

        leaks = _leak_scan(target, session_id=session_id, arm=payload_path.stem)
        if leaks:
            sys.stderr.write(
                "WHAT: a sealed packet still contains material that must never be in it.\n"
                + "".join(f"      - {leak}\n" for leak in leaks)
                + "WHY:  this is the tool whose whole claim is that blinding is STRUCTURAL\n"
                "      rather than promised. A packet carrying the runtime config leaks\n"
                "      the arm three ways and a live credential once.\n"
                "HOW:  if this is a missed filename, add it to the strict delivery policy; if it is the\n"
                "      setup gitignore block or this delivery's own identity, the writers\n"
                "      above have a bug -- fix it there. Then re-seal. Do not hand out the\n"
                "      packets produced by this run.\n"
            )
            return 1

    # Shuffled: ordering alone would rebuild the arm, since `control` sorts
    # before `nwave` in every pair, every time.
    order = list(mapping)
    random.shuffle(order)
    (out / "REVIEW-THESE.txt").write_text(
        "One delivery per line, in no meaningful order.\n"
        "Score each into a JSON object keyed by exactly these ids.\n\n"
        + "\n".join(order)
        + "\n",
        encoding="utf-8",
    )
    # The map lands OUTSIDE the bundle, and that is the whole point. Independent
    # review 2026-08-07: "SEALED-do-not-open.json non ha una barriera tecnica; se
    # viene consegnata l'intera directory, il blinding e' compromesso." A file
    # named do-not-open sitting next to the packets is a PROCEDURE, and the
    # failure it guards against is one careless `cp -r`. A bundle that physically
    # cannot contain the map is safe to hand over whole, by construction -- which
    # is the same standard this module already applies to the opaque ids.
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(
        json.dumps({"salt": salt, "opaque_to_session": mapping}, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"sealed {len(mapping)} deliveries into {deliveries}")
    print(f"HAND OVER, whole and safely : {out}")
    print("   it contains only         : deliveries/ and REVIEW-THESE.txt")
    print(f"KEEP, never in the bundle   : {map_path}")
    return 0


#: Sourced from the rubric module, never hardcoded here — see the module
#: docstring's "Stdlib only" note above.
_CRITERIA_KEYS = quality_rubric.CRITERIA_KEYS
_VERDICT_TOP_KEYS = {"criteria", "total", "blocking_quality_findings", "summary"}


def _validate_one_verdict(opaque: str, verdict: object) -> list[str]:
    """Problem strings for one delivery's verdict, empty if it is well-formed.

    Checked BEFORE anything is mapped back to a session: the rubric criteria
    object is exactly the shape four reviewer attempts got wrong, so this is a
    boundary, not a best-effort read.
    """
    if not isinstance(verdict, dict):
        return [
            f"{opaque}: verdict must be a JSON object, got {type(verdict).__name__}"
        ]

    problems: list[str] = []
    top_keys = set(verdict)
    if top_keys != _VERDICT_TOP_KEYS:
        missing = sorted(_VERDICT_TOP_KEYS - top_keys)
        extra = sorted(top_keys - _VERDICT_TOP_KEYS)
        detail = []
        if missing:
            detail.append(f"missing {missing}")
        if extra:
            detail.append(f"unexpected {extra}")
        problems.append(
            f"{opaque}: verdict keys must be exactly "
            f"{sorted(_VERDICT_TOP_KEYS)} (" + ", ".join(detail) + ")"
        )

    criteria = verdict.get("criteria") if "criteria" in top_keys else None
    criteria_keys: set[str] = set()
    if not isinstance(criteria, dict):
        if "criteria" in top_keys:
            problems.append(f"{opaque}: 'criteria' must be a JSON object")
    else:
        criteria_keys = set(criteria)
        if criteria_keys != _CRITERIA_KEYS:
            missing = sorted(_CRITERIA_KEYS - criteria_keys, key=int)
            extra = sorted(criteria_keys - _CRITERIA_KEYS)
            detail = []
            if missing:
                detail.append(f"missing {missing}")
            if extra:
                detail.append(f"unexpected {extra}")
            problems.append(
                f"{opaque}: criteria keys must be exactly "
                f"'1'..'{len(_CRITERIA_KEYS)}' (" + ", ".join(detail) + ")"
            )

    score_sum = 0
    scores_all_valid = True
    for key in sorted(criteria_keys & _CRITERIA_KEYS, key=int):
        criterion = criteria[key]
        if not isinstance(criterion, dict):
            problems.append(f"{opaque}: criterion {key} must be an object")
            scores_all_valid = False
            continue
        criterion_keys = set(criterion)
        if criterion_keys != {"score", "evidence"}:
            problems.append(
                f"{opaque}: criterion {key} keys must be exactly ['evidence', 'score']"
            )
            scores_all_valid = False
        score = criterion.get("score")
        # `bool` is a subclass of `int`; `type(score) is not int` is the one
        # check that rejects True/False while still accepting 0, 1, 2.
        if type(score) is not int or not (0 <= score <= 2):
            problems.append(
                f"{opaque}: criterion {key}.score must be an int 0..2, got {score!r}"
            )
            scores_all_valid = False
        else:
            score_sum += score
        if not isinstance(criterion.get("evidence"), str):
            problems.append(f"{opaque}: criterion {key}.evidence must be a string")

    total = verdict.get("total")
    if type(total) is not int:
        problems.append(f"{opaque}: 'total' must be an int, got {total!r}")
    elif scores_all_valid and criteria_keys == _CRITERIA_KEYS and total != score_sum:
        problems.append(
            f"{opaque}: 'total' ({total}) does not equal the score sum ({score_sum})"
        )

    findings = verdict.get("blocking_quality_findings")
    if not isinstance(findings, list) or not all(isinstance(f, str) for f in findings):
        problems.append(
            f"{opaque}: 'blocking_quality_findings' must be a list of strings"
        )

    if not isinstance(verdict.get("summary"), str):
        problems.append(f"{opaque}: 'summary' must be a string")

    return problems


def validate_verdict_shape(verdicts: dict) -> list[str]:
    """All problem strings across every scored delivery, in a stable order."""
    problems: list[str] = []
    for opaque in sorted(verdicts):
        problems.extend(_validate_one_verdict(opaque, verdicts[opaque]))
    return problems


def unseal(sealed: Path, scored: Path, out: Path) -> int:
    """Map opaque verdicts back to sessions, refusing a malformed or incomplete set."""
    # `sealed` is the MAP FILE now, not a directory beside the packets.
    seal_data = json.loads(sealed.read_text(encoding="utf-8"))
    issued: dict[str, str] = seal_data["opaque_to_session"]
    verdicts: dict[str, dict] = json.loads(scored.read_text(encoding="utf-8"))

    malformed = validate_verdict_shape(verdicts)
    if malformed:
        n = len(_CRITERIA_KEYS)
        sys.stderr.write(
            "WHAT: the scored file contains malformed reviewer verdicts.\n"
            + "".join(f"      - {p}\n" for p in malformed)
            + "WHY:  the rubric is source-blind but not shape-blind: a verdict that\n"
            f"      does not carry all {n} scored criteria, or whose total the\n"
            "      reviewer cannot add up, is not a disagreement about quality -- it\n"
            "      is not a verdict this instrument can trust downstream.\n"
            "HOW:  fix the verdict JSON so each delivery is exactly {criteria, total,\n"
            "      blocking_quality_findings, summary}, with 'criteria' an object\n"
            f"      keyed '1'..'{n}' of {{score: int 0..2, evidence: str}}, an int\n"
            "      'total' equal to their sum, 'blocking_quality_findings' as a list\n"
            "      of strings, and a string 'summary'. Nothing was mapped.\n"
        )
        return 1

    unknown = sorted(set(verdicts) - set(issued))
    unscored = sorted(set(issued) - set(verdicts))

    print(f"issued  : {len(issued)}")
    print(f"scored  : {len(verdicts)}")
    print(f"unknown : {len(unknown)}   (scored an id never issued)")
    print(f"unscored: {len(unscored)}  (issued and never scored)")
    for token in unknown:
        print(f"     unknown  {token}")
    for token in unscored:
        print(f"     unscored {token}")

    if unknown or unscored:
        sys.stderr.write(
            "WHAT: the scored set does not match the issued set.\n"
            "WHY:  a delivery that loses its verdict here reappears downstream as a\n"
            "      shrinking denominator, and the arm that went unscored looks\n"
            "      cheaper. An id nobody issued means the reviewer scored something\n"
            "      this campaign did not produce.\n"
            "HOW:  return a verdict for every id in REVIEW-THESE.txt, and only those.\n"
        )
        return 1

    out.write_text(
        json.dumps({issued[t]: v for t, v in verdicts.items()}, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {out} — session-keyed, ready for paired_quality_join.py")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="op", required=True)
    s = sub.add_parser("seal")
    s.add_argument("--campaign", required=True, type=Path)
    s.add_argument(
        "--out", required=True, type=Path, help="the bundle; safe to hand over whole"
    )
    s.add_argument(
        "--map",
        required=True,
        type=Path,
        dest="map_path",
        help="where the opaque->session map goes; MUST be outside --out",
    )
    u = sub.add_parser("unseal")
    u.add_argument(
        "--sealed", required=True, type=Path, help="the map file written by seal --map"
    )
    u.add_argument("--verdicts", required=True, type=Path)
    u.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.op == "seal":
        return seal(args.campaign, args.out, args.map_path)
    return unseal(args.sealed, args.verdicts, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
