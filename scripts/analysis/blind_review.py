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

`seal` writes two things into `--out`:

* `deliveries/<opaque>/` — one directory per run, carrying its artifacts and
  NOTHING that names the arm, the pair, or the session;
* `SEALED-do-not-open.json` — the opaque -> session map, which the reviewer must
  not read and `unseal` needs.

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
import hashlib
import json
import random
import secrets
import shutil
import sys
from pathlib import Path


_SEAL_NAME = "SEALED-do-not-open.json"

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
    "__pycache__",
    ".git",
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


def opaque_id(session_id: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{session_id}".encode()).hexdigest()[:12]


def seal(campaign: Path, out: Path, map_path: Path) -> int:
    """Emit blinded delivery packets plus the sealed map."""
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
        workspace = payload_path.parent / payload_path.stem
        if workspace.is_dir():
            shutil.copytree(
                workspace,
                target / "delivery",
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(*_NEVER_SEAL),
            )
        strip_setup_traces(target / "delivery")
        leaks = sorted(
            str(found.relative_to(target))
            for name in _NEVER_SEAL
            for found in target.rglob(name)
        )
        if leaks:
            sys.stderr.write(
                "WHAT: a sealed packet still contains material that must never be in it.\n"
                + "".join(f"      - {leak}\n" for leak in leaks)
                + "WHY:  this is the tool whose whole claim is that blinding is STRUCTURAL\n"
                "      rather than promised. A packet carrying the runtime config leaks\n"
                "      the arm three ways and a live credential once.\n"
                "HOW:  add the offending name to _NEVER_SEAL and re-seal. Do not hand out\n"
                "      the packets produced by this run.\n"
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


def unseal(sealed: Path, scored: Path, out: Path) -> int:
    """Map opaque verdicts back to sessions, refusing an incomplete set."""
    # `sealed` is the MAP FILE now, not a directory beside the packets.
    seal_data = json.loads(sealed.read_text(encoding="utf-8"))
    issued: dict[str, str] = seal_data["opaque_to_session"]
    verdicts: dict[str, dict] = json.loads(scored.read_text(encoding="utf-8"))

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
        bundle, mapped = args.out.resolve(), args.map_path.resolve()
        if bundle == mapped or bundle in mapped.parents:
            sys.stderr.write(
                f"WHAT: the map {mapped} is inside the bundle {bundle}.\n"
                "WHY:  the bundle exists to be handed over WHOLE. A map inside it turns\n"
                "      blinding back into a procedure that one `cp -r` defeats.\n"
                "HOW:  point --map somewhere outside --out.\n"
            )
            return 2
        return seal(args.campaign, args.out, mapped)
    return unseal(args.sealed, args.verdicts, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
