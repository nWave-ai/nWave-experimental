"""Prepare the immutable public-candidate handoff the installed-journey lane consumes.

WHY THIS EXISTS AS A SEPARATE SERVICE. The public walking skeleton
(`tests/des/acceptance/classic_explicit_only/test_classic_explicit_only_public_journey.py`)
must examine the RELEASE CANDIDATE, not a convenient substitute built from source
during the test. So the test refuses to build, download, or alter anything: it is
handed an immutable manifest and verifies the bytes against their declared digest
before installing them offline. Something outside the test therefore has to
produce that manifest, and this is it. See
`docs/feature/classic-explicit-only/distill/public-candidate-walking-skeleton.md`
for the contract this file implements.

WHAT IT DOES NOT DO, deliberately. It does not build the wheel and it does not
resolve the dependency closure. The wheel comes from the normal release build;
the offline wheelhouse and its hashed lock are produced by the Hatch build hook
`scripts/release/offline_wheelhouse_hook.py`, which owns that file. This service
only *observes* those artifacts, verifies they satisfy the contract, and writes
the manifest that binds them together. One writer per artifact: a second writer
on `requirements.lock` would silently lose whichever line was written first.

FAIL-LOUD, NEVER FAIL-CONVENIENT. Every refusal below names WHAT is missing, WHY
it matters, and HOW to produce it. A candidate service that quietly emitted a
manifest for a wheel it could not fully verify would hand the acceptance lane a
green that proves nothing -- which is precisely the failure mode the walking
skeleton exists to make impossible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


SCHEMA_VERSION = "nwave.public-candidate.v1"
MANIFEST_ENV = "NWAVE_PUBLIC_CANDIDATE_MANIFEST"
WHEELHOUSE_DIRNAME = "offline-wheelhouse"
LOCK_FILENAME = "requirements.lock"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CandidatePreparationError(Exception):
    """A refusal that names what is missing, why it matters, and how to fix it."""


def _digest(path: Path) -> str:
    """SHA-256 of the exact bytes on disk, lowercase hex."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_artifact(artifact: Path) -> Path:
    resolved = artifact.resolve()
    if not resolved.is_file():
        raise CandidatePreparationError(
            f"WHAT: the candidate artifact does not exist at {resolved}. "
            "WHY: the public journey installs THESE bytes; without them there is "
            "no candidate to certify and any manifest would name a fiction. "
            "HOW: run the public wheel build first "
            "(`uv run python scripts/build_dist.py` then the wheel build), and "
            "point --artifact at the produced .whl."
        )
    if resolved.suffix != ".whl":
        raise CandidatePreparationError(
            f"WHAT: the candidate artifact is not a wheel: {resolved.name}. "
            "WHY: the journey installs it with pip from a hashed lock, which "
            "names a wheel; a sdist or archive would take a different install "
            "path than the one under review. "
            "HOW: pass the built .whl produced by the public wheel build."
        )
    return resolved


def _require_closure(artifact: Path) -> tuple[Path, Path]:
    """Locate the offline closure the build hook wrote beside the wheel.

    The layout is the build hook's, not ours: it writes
    ``Path(artifact_path).parent / "offline-wheelhouse"``. We read that layout
    rather than restating it, so a change there surfaces here as a loud refusal
    instead of a manifest pointing at nothing.
    """
    wheelhouse = (artifact.parent / WHEELHOUSE_DIRNAME).resolve()
    lock = (wheelhouse / LOCK_FILENAME).resolve()
    if not wheelhouse.is_dir():
        raise CandidatePreparationError(
            f"WHAT: no offline dependency closure beside the candidate "
            f"(expected {wheelhouse}). "
            "WHY: an install that resolves from the network is not the reviewed "
            "public artifact journey -- it could pull a different dependency set "
            "than the one certified. "
            "HOW: build the wheel with the offline-wheelhouse Hatch hook enabled "
            "(scripts/release/offline_wheelhouse_hook.py); it writes the "
            "wheelhouse next to the wheel it just produced."
        )
    if not lock.is_file():
        raise CandidatePreparationError(
            f"WHAT: the offline wheelhouse has no {LOCK_FILENAME} ({lock}). "
            "WHY: pip installs with --require-hashes from that lock; without it "
            "there is nothing pinning which bytes get installed. "
            "HOW: the offline-wheelhouse build hook writes it; if the wheelhouse "
            "exists without a lock the hook failed partway -- rebuild rather "
            "than hand-writing the file."
        )
    return wheelhouse, lock


def _require_candidate_pinned_in_lock(artifact: Path, digest: str, lock: Path) -> None:
    """The lock must name THIS wheel by file URI, exactly once, with its hash.

    Why a file URI and not ``name==version``: under ``--require-hashes`` pip
    would accept a name/version requirement satisfied by any wheel carrying that
    name and version, so the lock would authorise a *class* of artifacts rather
    than the one immutable candidate the manifest verified. One file URI closes
    that gap. Why exactly once: two entries let pip choose, and a candidate the
    reviewer never inspected could win.
    """
    requirement = artifact.as_uri()
    matching = [
        line.strip()
        for line in lock.read_text(encoding="utf-8").splitlines()
        if requirement in line
    ]
    if len(matching) != 1:
        raise CandidatePreparationError(
            f"WHAT: {LOCK_FILENAME} names the candidate {len(matching)} times, "
            "expected exactly once. "
            "WHY: zero entries means pip receives the wheel by a second route "
            "(or not at all) and may reject it under --require-hashes; more than "
            "one lets pip pick, so the installed bytes need not be the verified "
            "ones. "
            f"HOW: the offline-wheelhouse hook must emit one line "
            f"`{requirement} --hash=sha256:{digest}` for the candidate itself, "
            "alongside the dependency entries. The candidate is a SIBLING of the "
            "wheelhouse, so a glob over the wheelhouse alone will not find it."
        )
    if f"--hash=sha256:{digest}" not in matching[0]:
        raise CandidatePreparationError(
            "WHAT: the candidate's lock entry carries no matching SHA-256 hash. "
            "WHY: an unhashed or mismatched entry under --require-hashes either "
            "fails the install or authorises bytes other than the ones this "
            "manifest verified. "
            f"HOW: emit `{requirement} --hash=sha256:{digest}`. "
            f"observed entry: {matching[0]}"
        )


def build_manifest(artifact: Path) -> dict[str, object]:
    """Verify the candidate and its closure, then describe them immutably."""
    resolved = _require_artifact(artifact)
    digest = _digest(resolved)
    if not _SHA256_RE.match(digest):  # pragma: no cover - hashlib guarantees form
        raise CandidatePreparationError(
            f"WHAT: computed digest is not a lowercase SHA-256: {digest!r}. "
            "WHY: the consumer matches it against a strict pattern and would "
            "reject the manifest. HOW: report this as a defect in this script."
        )
    wheelhouse, lock = _require_closure(resolved)
    _require_candidate_pinned_in_lock(resolved, digest, lock)
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": {"path": str(resolved), "sha256": digest},
        "offline_dependency_closure": {
            "wheelhouse_path": str(wheelhouse),
            "requirements_lock_path": str(lock),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact", type=Path, required=True, help="the built public .whl"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="where to write the manifest JSON",
    )
    args = parser.parse_args(argv)

    try:
        manifest = build_manifest(args.artifact)
    except CandidatePreparationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    # The path is printed on stdout so a caller can export it without parsing
    # the manifest: `export NWAVE_PUBLIC_CANDIDATE_MANIFEST=$(... --out ...)`.
    print(str(out))
    print(
        f"candidate manifest written; export {MANIFEST_ENV}={out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
