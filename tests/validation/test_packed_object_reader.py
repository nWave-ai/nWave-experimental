"""The packed-object reader must read what git reads, and refuse everything else.

WHY THESE TESTS EXIST. The tree-coherence gate reads git objects in pure
Python because `git` must never become a dependency of gate logic. Its first
reader decoded LOOSE objects only, which decays silently: `git gc` packs on its
own schedule, so a closure note naming an artifact became unverifiable for an
environmental reason its author never caused -- and because the gate exits
non-zero on that third state and pre-commit blocks on non-zero, the document
became uncommittable.

`git` appears here as an ORACLE (do these bytes match `git cat-file`) and never
in the implementation. That asymmetry is the point: the test may depend on the
tool, the gate may not.

TWO OF THE FIRST PROBES WRITTEN FOR THIS COULD NOT FAIL. They truncated the
second half of a pack while the object under test sat near the beginning, and
they reported "reads correctly" while proving nothing. The negative cases below
therefore corrupt the pack AT the object's own offset, which is the only place
a corruption can actually reach it. A check you expect to pass tells you
nothing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "validation"))

from git_commit_reachability import locate_git_dirs
from git_packed_objects import PackedObjectStore


REPO = Path(__file__).resolve().parents[2]

# ``REPO / ".git"`` is a FILE (a ``gitdir:`` pointer), not a directory, in a
# linked worktree -- every lane in this swarm works from one. Naming
# ``REPO / ".git" / "objects"`` directly therefore names a path that can never
# exist there, silently satisfying `needs_pack`'s skip condition and hiding
# this whole oracle suite (the one that proves the packed reader agrees with
# `git cat-file`) from every worktree checkout. `locate_git_dirs` -- the same
# resolution the production code already uses -- follows the pointer AND the
# `commondir` indirection to the SHARED object store where packs actually
# live. Fall back to the naive path only when `locate_git_dirs` cannot find a
# checkout at all (e.g. a released tarball with no `.git`), in which case
# `needs_pack` must still skip, not error.
_located = locate_git_dirs(REPO)
_commondir = _located[1] if _located is not None else (REPO / ".git")
OBJECTS = _commondir / "objects"


def _git(*args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, check=False
    ).stdout


def _packed_samples(limit: int) -> list[tuple[str, str]]:
    """`(sha, type)` for objects that live in a pack, or an empty list."""
    out: list[tuple[str, str]] = []
    for idx in sorted((OBJECTS / "pack").glob("*.idx")):
        listing = _git("verify-pack", "-v", str(idx)).decode(errors="replace")
        for line in listing.splitlines():
            parts = line.split()
            if len(parts) > 2 and parts[1] in {"commit", "tree", "blob", "tag"}:
                out.append((parts[0], parts[1]))
            if len(out) >= limit:
                return out
    return out


needs_pack = pytest.mark.skipif(
    not (OBJECTS / "pack").is_dir() or not _packed_samples(1),
    # Name the path actually looked in -- a skip reason with no path is how
    # this suite went unnoticed while silently checking a location that could
    # never exist in a linked worktree (see the OBJECTS derivation above).
    reason=f"no packfile found under `{OBJECTS / 'pack'}`: nothing for a packed reader to read",
)


@needs_pack
def test_every_sampled_packed_object_matches_git_byte_for_byte() -> None:
    """The oracle check. Disagreement on ONE object invalidates the reader.

    Type and body are both compared: a reader that returned the right bytes
    under the wrong type would corrupt a caller that dispatches on type, and a
    reader that returned the right type with truncated bytes would corrupt a
    diff. Neither is caught by comparing only one of them.
    """
    store = PackedObjectStore(OBJECTS)
    samples = _packed_samples(200)
    assert samples, "sampling found no packed object, so this test proved nothing"

    disagreements: list[str] = []
    for sha, kind in samples:
        mine = store.read(sha)
        if mine is None:
            disagreements.append(
                f"{sha[:9]} {kind}: reader refused an object git reads"
            )
            continue
        expected = _git("cat-file", kind, sha)
        if mine[0] != kind:
            disagreements.append(f"{sha[:9]}: type {mine[0]!r} != git's {kind!r}")
        elif mine[1] != expected:
            disagreements.append(
                f"{sha[:9]} {kind}: {len(mine[1])} bytes != git's {len(expected)}"
            )
    assert not disagreements, "\n".join(disagreements)


@needs_pack
def test_a_loose_only_reader_would_have_missed_these() -> None:
    """Pins the REASON this reader exists, not just that it works.

    Without this, a future change could quietly narrow the reader back to loose
    objects and every test above would still pass on a checkout that happens to
    have loose copies. The assertion is that the sampled objects have NO loose
    file on disk -- so reading them is only possible through a pack.
    """
    samples = _packed_samples(50)
    loose_on_disk = [
        sha for sha, _ in samples if (OBJECTS / sha[:2] / sha[2:]).is_file()
    ]
    assert len(loose_on_disk) < len(samples), (
        "every sampled object also exists loose, so this suite cannot show that "
        "packed reading is what makes them readable"
    )


def _mutated_store(mutate, sha: str) -> PackedObjectStore | None:
    """A store over a COPY of the pack holding `sha`, after `mutate` ran.

    Returns None when the owning pack cannot be found, so a caller never reads
    a copy that does not contain its object -- the mistake that made two
    earlier probes vacuous.
    """
    owner = None
    for idx in sorted((OBJECTS / "pack").glob("*.idx")):
        listing = _git("verify-pack", "-v", str(idx)).decode(errors="replace")
        if any(line.startswith(sha) for line in listing.splitlines()):
            owner = idx
            break
    if owner is None:
        return None
    tmp = Path(tempfile.mkdtemp())
    pack_dir = tmp / "objects" / "pack"
    pack_dir.mkdir(parents=True)
    for source in (owner, owner.with_suffix(".pack")):
        target = pack_dir / source.name
        shutil.copy(source, target)
        target.chmod(0o644)  # git keeps packs read-only
    mutate(pack_dir / owner.name, pack_dir / owner.with_suffix(".pack").name)
    return PackedObjectStore(tmp / "objects")


@needs_pack
@pytest.mark.parametrize(
    "label",
    ["truncated_before_the_object", "zlib_stream_destroyed", "declared_size_altered"],
)
def test_a_corrupt_pack_is_refused_never_partially_read(label: str) -> None:
    """Each corruption must yield None, never plausible-looking bytes.

    `declared_size_altered` is the sharpest of the three: the stream still
    inflates, so a reader that trusted the deflate result and skipped the
    length check would hand back bytes that look fine. That is the
    silently-wrong read this module exists to prevent.
    """
    sha, _ = _packed_samples(1)[0]
    store = PackedObjectStore(OBJECTS)
    offset_map = store._parse_idx(next(iter(sorted((OBJECTS / "pack").glob("*.idx")))))
    control = _mutated_store(lambda i, p: None, sha)
    assert control is not None and control.read(sha) is not None, (
        "the unmutated control could not be read, so the negative cases below "
        "would prove nothing"
    )
    at = (offset_map or {}).get(sha)
    if at is None:
        pytest.skip("sampled object is not in the first index: offset unavailable")

    def truncate_before(_idx: Path, pack: Path) -> None:
        pack.write_bytes(pack.read_bytes()[:at])

    def destroy_stream(_idx: Path, pack: Path) -> None:
        body = bytearray(pack.read_bytes())
        body[at + 3 : at + 40] = b"\xff" * 37
        pack.write_bytes(bytes(body))

    def alter_size(_idx: Path, pack: Path) -> None:
        body = bytearray(pack.read_bytes())
        body[at] = (body[at] & 0xF0) | 0x0F
        pack.write_bytes(bytes(body))

    mutation = {
        "truncated_before_the_object": truncate_before,
        "zlib_stream_destroyed": destroy_stream,
        "declared_size_altered": alter_size,
    }[label]
    broken = _mutated_store(mutation, sha)
    assert broken is not None
    assert broken.read(sha) is None, f"{label}: returned bytes instead of refusing"


@needs_pack
@pytest.mark.parametrize("label", ["magic_destroyed", "index_truncated"])
def test_an_unparsable_index_is_skipped_not_guessed(label: str) -> None:
    """A broken index means "not mine", never "the object is absent"."""
    sha, _ = _packed_samples(1)[0]

    def kill_magic(idx: Path, _pack: Path) -> None:
        idx.write_bytes(b"\x00" * 8 + idx.read_bytes()[8:])

    def truncate(idx: Path, _pack: Path) -> None:
        idx.write_bytes(idx.read_bytes()[:200])

    mutation = {"magic_destroyed": kill_magic, "index_truncated": truncate}[label]
    broken = _mutated_store(mutation, sha)
    assert broken is not None
    assert broken.read(sha) is None


def test_an_absent_pack_directory_refuses_instead_of_raising() -> None:
    """A checkout with no packs must degrade quietly to "not packed"."""
    empty = Path(tempfile.mkdtemp()) / "objects"
    empty.mkdir(parents=True)
    assert PackedObjectStore(empty).read("0" * 40) is None
