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
  `git apply`-able unified diff against that workspace's own HEAD, built in a
  throwaway copy and cleaned up before `seal` returns;
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

Stdlib only.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import random
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


#: Never copied into a review packet. Measured 2026-08-07, before the first seal:
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
_NEVER_SEAL = (
    ".claude-k4",
    ".credentials.json",
    ".claude.json",
    ".nwave",
    "CLAUDE.md",
    ".venv*",
    ".k4-acceptance-venv",
    ".mypy_cache",
    ".hypothesis",
    "__pycache__",
    ".git",
    "AGENTS.md",
    "test_k4_acceptance.py",
)


#: The exact block `nwave-ai project enable` appends to the subject's own
#: `.gitignore`. It cannot be handled by excluding the file: `.gitignore` is a
#: real project file a delivery may legitimately edit, so dropping it would hide
#: delivery content. But leaving it identified the treatment arm in exactly 3 of
#: 6 packets -- a perfect discriminator, found by auditing the sealed output
#: rather than by trusting the exclusion list.
#:
#: Same rule as `_NEVER_SEAL`, applied inside a file instead of to a path:
#: strip what SETUP wrote, keep what DELIVERY wrote.
_SETUP_GITIGNORE_BLOCK = (
    "# nWave activation marker (keep .nwave/local-config.json trackable)",
    ".nwave/*",
    "!.nwave/local-config.json",
)


def strip_setup_traces(delivery: Path) -> None:
    """Remove setup-written lines that would name the arm."""
    gitignore = delivery / ".gitignore"
    if not gitignore.is_file():
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
    """True if any component of `rel_path` matches a `_NEVER_SEAL` pattern.

    Mirrors `shutil.ignore_patterns`, which matches basenames per directory
    level during the walk -- so a manifest entry never names a path that
    `seal`'s own copytree would have refused to copy.
    """
    return any(
        fnmatch.fnmatch(part, pattern)
        for part in Path(rel_path).parts
        for pattern in _NEVER_SEAL
    )


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


def _classify_status(code: str) -> str | None:
    """One of the four manifest buckets, or None if the code can't be represented."""
    if code == "??":
        return _STATUS_ADDED
    if code[0] in ("R", "C"):
        return _STATUS_RENAMED
    if "D" in code:
        return _STATUS_DELETED
    if "A" in code:
        return _STATUS_ADDED
    if "M" in code:
        return _STATUS_MODIFIED
    return None


def _gitignore_setup_only(workspace: Path) -> bool:
    """True if `.gitignore`'s only difference from HEAD is the setup block.

    A delivery may legitimately edit `.gitignore` too; only the exact block
    `nwave-ai project enable` appends is setup noise, so this diffs the
    stripped working copy against HEAD rather than excluding the path outright.
    """
    gitignore = workspace / ".gitignore"
    if not gitignore.is_file():
        return False
    shown = subprocess.run(
        ["git", "-C", str(workspace), "show", "HEAD:.gitignore"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )
    head_lines = shown.stdout.splitlines() if shown.returncode == 0 else []
    current_lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
    stripped = [ln for ln in current_lines if ln.strip() not in _SETUP_GITIGNORE_BLOCK]
    return stripped == head_lines


def write_delivery_manifest(workspace: Path, target: Path) -> int:
    """`DELIVERY-CHANGES.txt`: the git evidence of what this delivery changed.

    Built from `git status` against the workspace's own HEAD, after setup-only
    traces are excluded -- never from the arm label or session, so the file
    itself cannot leak identity the rest of `seal` withholds.
    """
    manifest_path = target / _MANIFEST_NAME
    if not (workspace / ".git").is_dir():
        sys.stderr.write(
            "WHAT: the delivery workspace is missing or is not a git checkout.\n"
            f"      - {workspace}\n"
            "WHY:  writing an empty manifest here would look identical to a delivery\n"
            "      that legitimately changed nothing -- silent-empty and\n"
            "      silent-unsupported must not be the same output.\n"
            "HOW:  point the campaign at a real git checkout for this run, then\n"
            "      re-seal. Nothing was written for this delivery.\n"
        )
        return 1

    try:
        entries = _git_status(workspace)
    except RuntimeError as exc:
        sys.stderr.write(
            "WHAT: could not read the delivery-manifest git evidence for a packet.\n"
            f"      - {exc}\n"
            "WHY:  a manifest built without evidence would either be empty (looks\n"
            "      like nothing changed) or invented, and both are dishonest.\n"
            "HOW:  make sure the delivery workspace is a readable git checkout, then\n"
            "      re-seal.\n"
        )
        return 1

    lines: list[str] = []
    unrepresentable: list[tuple[str, str]] = []
    for code, path, old_path in entries:
        if _excluded_path(path) or (old_path and _excluded_path(old_path)):
            continue
        if path == ".gitignore" and "M" in code and _gitignore_setup_only(workspace):
            continue
        bucket = _classify_status(code)
        if bucket is None:
            unrepresentable.append((code, path))
            continue
        if bucket == _STATUS_RENAMED:
            lines.append(f"{_STATUS_RENAMED} {old_path} -> {path}")
        else:
            lines.append(f"{bucket} {path}")

    if unrepresentable:
        sys.stderr.write(
            "WHAT: a delivery-changed path cannot be represented honestly in its manifest.\n"
            + "".join(f"      - {code} {path}\n" for code, path in unrepresentable)
            + "WHY:  an unrecognised git status (typechange, unmerged conflict, ...)\n"
            "      dropped silently would make DELIVERY-CHANGES.txt claim completeness\n"
            "      it does not have.\n"
            "HOW:  resolve the working tree state, or teach `_classify_status` the new\n"
            "      status honestly, then re-seal. Do not hand out this packet.\n"
        )
        return 1

    lines.sort()
    manifest_path.write_text(
        ("\n".join(lines) + "\n") if lines else "", encoding="utf-8"
    )
    return 0


_PATCH_NAME = "DELIVERY.patch"


def _patchable_entries(
    entries: list[tuple[str, str, str | None]],
) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """`(pathspec, untracked-among-it, unrepresentable)`, filtered like the manifest.

    Excludes the same `_NEVER_SEAL` paths the manifest excludes, and fails the
    same way on a status code neither honestly represents -- one filter, used
    twice, so the manifest and the patch can never disagree about what a
    delivery changed.
    """
    paths: list[str] = []
    untracked: list[str] = []
    unrepresentable: list[tuple[str, str]] = []
    for code, path, old_path in entries:
        if _excluded_path(path) or (old_path and _excluded_path(old_path)):
            continue
        bucket = _classify_status(code)
        if bucket is None:
            unrepresentable.append((code, path))
            continue
        paths.append(path)
        if old_path:
            paths.append(old_path)
        if code == "??":
            untracked.append(path)
    return paths, untracked, unrepresentable


def write_delivery_patch(workspace: Path, target: Path) -> int:
    """`DELIVERY.patch`: every non-setup delivery change against this
    workspace's own HEAD, as one `git apply`-able unified diff -- the compact
    substitute for copying the workspace wholesale.

    Built inside a throwaway copy of `workspace`, so the source lane's git
    index is never touched. `strip_setup_traces` runs there first: a
    setup-only `.gitignore` edit then stops differing from HEAD and never
    reaches `git status`, while a legitimate edit mixed into the same file
    still shows up, minus the setup lines. The copy (including `.git`, needed
    to diff at all) is removed before this function returns.
    """
    patch_path = target / _PATCH_NAME
    if not (workspace / ".git").is_dir():
        sys.stderr.write(
            "WHAT: the delivery workspace is missing or is not a git checkout.\n"
            f"      - {workspace}\n"
            "WHY:  writing an empty patch here would look identical to a delivery\n"
            "      that legitimately changed nothing -- silent-empty and\n"
            "      silent-unsupported must not be the same output.\n"
            "HOW:  point the campaign at a real git checkout for this run, then\n"
            "      re-seal. Nothing was written for this delivery.\n"
        )
        return 1

    with tempfile.TemporaryDirectory(prefix="blind-review-patch-") as tmp:
        tmp_ws = Path(tmp) / "ws"
        try:
            # Ignore the same bulk `_NEVER_SEAL` would exclude from the
            # packet -- credentials, venvs, caches -- so the throwaway copy
            # never holds them even transiently. `.git` is the one exception:
            # the diff below needs it, and it was never in `_NEVER_SEAL` for
            # a leak reason, only so manifest paths never name it.
            shutil.copytree(
                workspace,
                tmp_ws,
                symlinks=True,
                ignore=shutil.ignore_patterns(
                    *(name for name in _NEVER_SEAL if name != ".git")
                ),
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

        try:
            entries = _git_status(tmp_ws)
        except RuntimeError as exc:
            sys.stderr.write(
                "WHAT: could not read the delivery-patch git evidence for a packet.\n"
                f"      - {exc}\n"
                "WHY:  a patch built without evidence would either be empty (looks\n"
                "      like nothing changed) or invented, and both are dishonest.\n"
                "HOW:  make sure the delivery workspace is a readable git checkout, then\n"
                "      re-seal.\n"
            )
            return 1

        paths, untracked, unrepresentable = _patchable_entries(entries)
        if unrepresentable:
            sys.stderr.write(
                "WHAT: a delivery-changed path cannot be represented honestly in its patch.\n"
                + "".join(f"      - {code} {path}\n" for code, path in unrepresentable)
                + "WHY:  an unrecognised git status (typechange, unmerged conflict, ...)\n"
                "      dropped silently would make DELIVERY.patch claim completeness it\n"
                "      does not have.\n"
                "HOW:  resolve the working tree state, or teach `_classify_status` the new\n"
                "      status honestly, then re-seal. Do not hand out this packet.\n"
            )
            return 1

        if not paths:
            patch_path.write_text("", encoding="utf-8")
            return 0

        if untracked:
            # `-N` (intent-to-add) is what makes `git diff HEAD` see an
            # untracked path at all -- without it, a path git never indexed
            # is invisible to the diff machinery, staged or not.
            added = subprocess.run(
                ["git", "-C", str(tmp_ws), "add", "-N", "--", *untracked],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=30,
            )
            if added.returncode != 0:
                sys.stderr.write(
                    "WHAT: could not stage untracked delivery paths to build the patch.\n"
                    f"      - git add -N: {added.stderr.strip()}\n"
                    "WHY:  without intent-to-add, an untracked delivery file is invisible\n"
                    "      to `git diff HEAD`, so the patch would silently omit it.\n"
                    "HOW:  make sure the delivery workspace is a readable git checkout, then\n"
                    "      re-seal.\n"
                )
                return 1

        diff = subprocess.run(
            [
                "git",
                "-C",
                str(tmp_ws),
                "diff",
                "--no-color",
                "--binary",
                "-M",
                "HEAD",
                "--",
                *paths,
            ],
            capture_output=True,
            text=True,
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
        patch_path.write_text(diff.stdout, encoding="utf-8")
    return 0


#: JSON keys specific to the OAuth credential file `seed_auth.py` copies
#: (`claudeAiOauth`) and its usual shape (`accessToken`/`refreshToken`) --
#: structural, unlike a generic filename a legitimate delivery could
#: plausibly mention in its own code or docs.
_CREDENTIAL_SENTINELS = ("claudeAiOauth", "accessToken", "refreshToken")


def _diff_header_paths(patch_text: str) -> set[str]:
    """Every path named in a unified diff's own structural headers.

    Independent of `_patchable_entries`' filtering: if that filter ever had a
    bug, the paths git actually wrote into `diff --git`/`---`/`+++`/rename
    headers would still be exactly what a reviewer's `git apply` sees, so
    checking them is a second axis on the same claim, not a repeat of it.
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
        # Neither call copies the workspace into `target`: the manifest reads
        # `git status`, the patch builds its own throwaway copy and cleans it
        # up, so `target` only ever holds the two files a reviewer needs.
        workspace = payload_path.parent / payload_path.stem
        if write_delivery_manifest(workspace, target) != 0:
            return 1
        if write_delivery_patch(workspace, target) != 0:
            return 1

        leaks = _leak_scan(target, session_id=session_id, arm=payload_path.stem)
        if leaks:
            sys.stderr.write(
                "WHAT: a sealed packet still contains material that must never be in it.\n"
                + "".join(f"      - {leak}\n" for leak in leaks)
                + "WHY:  this is the tool whose whole claim is that blinding is STRUCTURAL\n"
                "      rather than promised. A packet carrying the runtime config leaks\n"
                "      the arm three ways and a live credential once.\n"
                "HOW:  if this is a missed filename, add it to _NEVER_SEAL; if it is the\n"
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


_CRITERIA_KEYS = {str(n) for n in range(1, 13)}
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
                f"{opaque}: criteria keys must be exactly '1'..'12' ("
                + ", ".join(detail)
                + ")"
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
        sys.stderr.write(
            "WHAT: the scored file contains malformed reviewer verdicts.\n"
            + "".join(f"      - {p}\n" for p in malformed)
            + "WHY:  the rubric is source-blind but not shape-blind: a verdict that\n"
            "      does not carry all 12 scored criteria, or whose total the reviewer\n"
            "      cannot add up, is not a disagreement about quality -- it is not a\n"
            "      verdict this instrument can trust downstream.\n"
            "HOW:  fix the verdict JSON so each delivery is exactly {criteria, total,\n"
            "      blocking_quality_findings, summary}, with 'criteria' an object\n"
            "      keyed '1'..'12' of {score: int 0..2, evidence: str}, an int\n"
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
