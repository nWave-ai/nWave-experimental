"""Read PACKED git objects in pure Python, so a gate's coverage stops decaying.

WHY THIS EXISTS. The tree-coherence gate reads git objects straight off
``.git/`` with no ``git`` binary, because the target-machine-agnosticism
mandate forbids making an external tool a dependency of gate logic. Its first
reader decoded LOOSE objects only. That is correct but it decays: ``git gc``
packs objects on its own schedule, so every closure note naming an artifact
becomes unverifiable the moment its objects are packed. Measured 2026-07-30:
tree ``da2b37fb3`` exists (``git cat-file -t`` says ``tree``) with no loose
file on disk, and the gate refused D36's closure for that reason alone.

The failure mode made it urgent rather than cosmetic: the gate exits non-zero
on the third state, pre-commit blocks on non-zero, so an environmental fact
the author did not cause made the document uncommittable.

WHAT IT REFUSES TO DO. It never guesses. A delta chain it cannot resolve, a
truncated pack, an index it cannot parse -- each returns ``None`` and the
caller keeps its honest INDETERMINATE. Resolving one delta level and calling
it done would return silently wrong bytes, which is strictly worse than the
refusal it replaces.

``git`` is used as an ORACLE in the tests (compare these bytes against
``git cat-file -p``), never in the implementation.
"""

from __future__ import annotations

import struct
import zlib
from typing import TYPE_CHECKING


if TYPE_CHECKING:  # `Path` appears only in annotations, never at runtime
    from pathlib import Path


#: Pack object type ids (pack format v2). 5 is unused; 0 is invalid.
_OBJ_COMMIT, _OBJ_TREE, _OBJ_BLOB, _OBJ_TAG = 1, 2, 3, 4
_OBJ_OFS_DELTA, _OBJ_REF_DELTA = 6, 7

_TYPE_NAMES = {
    _OBJ_COMMIT: "commit",
    _OBJ_TREE: "tree",
    _OBJ_BLOB: "blob",
    _OBJ_TAG: "tag",
}

#: Upper bound on delta-chain depth followed for one object. Real chains are
#: shallow (git's own default window keeps them under ~50); a deeper one means
#: a malformed or hostile pack, and the honest answer is a refusal rather than
#: an unbounded walk inside a pre-commit hook.
_MAX_DELTA_DEPTH = 64

#: Upper bound on the decompressed size of one object, so a corrupt length
#: cannot make a hook allocate without limit.
_MAX_OBJECT_BYTES = 64 * 1024 * 1024


class PackedObjectStore:
    """Locate and decode objects inside ``.git/objects/pack/*.pack``.

    Indexes are parsed lazily and cached: a gate that resolves one object
    usually resolves several from the same pack, and re-reading the fanout for
    each would turn a cheap check into a slow one.
    """

    def __init__(self, objects_dir: Path) -> None:
        self._pack_dir = objects_dir / "pack"
        #: idx path -> {sha_hex: offset}; None marks an index we could not parse,
        #: so a broken pack is skipped once instead of retried per lookup.
        self._indexes: dict[Path, dict[str, int] | None] = {}
        self._loaded = False

    # -- index ------------------------------------------------------------

    def _load_indexes(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._pack_dir.is_dir():
            return
        for idx in sorted(self._pack_dir.glob("*.idx")):
            self._indexes[idx] = self._parse_idx(idx)

    @staticmethod
    def _parse_idx(idx_path: Path) -> dict[str, int] | None:
        """Parse a v2 pack index into ``{sha_hex: pack_offset}``.

        Returns None for anything this reader does not understand -- a v1
        index, a truncated file, an unreadable path. None means "not mine",
        never "empty": the caller must not read absence as absence-of-object.
        """
        try:
            raw = idx_path.read_bytes()
        except OSError:
            return None
        if len(raw) < 8 or raw[:4] != b"\xfftOc":
            return None  # v1 index (no magic) or not an index at all
        (version,) = struct.unpack_from(">I", raw, 4)
        if version != 2:
            return None
        fanout_at = 8
        table_at = fanout_at + 256 * 4
        if len(raw) < table_at:
            return None
        (count,) = struct.unpack_from(">I", raw, table_at - 4)
        names_at = table_at
        crc_at = names_at + count * 20
        small_at = crc_at + count * 4
        large_at = small_at + count * 4
        if len(raw) < large_at:
            return None
        offsets: dict[str, int] = {}
        for i in range(count):
            sha = raw[names_at + i * 20 : names_at + (i + 1) * 20].hex()
            (small,) = struct.unpack_from(">I", raw, small_at + i * 4)
            if small & 0x80000000:
                # MSB set: the real offset lives in the 8-byte table.
                big_index = small & 0x7FFFFFFF
                at = large_at + big_index * 8
                if len(raw) < at + 8:
                    return None
                (offset,) = struct.unpack_from(">Q", raw, at)
            else:
                offset = small
            offsets[sha] = offset
        return offsets

    def _locate(self, sha: str) -> tuple[Path, int] | None:
        """Return ``(pack_path, offset)`` for ``sha``, or None if not packed."""
        self._load_indexes()
        for idx_path, offsets in self._indexes.items():
            if offsets is None:
                continue
            offset = offsets.get(sha)
            if offset is not None:
                pack = idx_path.with_suffix(".pack")
                if pack.is_file():
                    return pack, offset
        return None

    # -- object -----------------------------------------------------------

    def read(self, sha: str) -> tuple[str, bytes] | None:
        """Return ``(type_name, body)`` for a packed object, or None.

        None is returned for every case this reader cannot complete HONESTLY:
        the object is not in any pack it could parse, a delta base is missing,
        the chain is deeper than the bound, a size is implausible, or zlib
        refuses the stream. The caller's INDETERMINATE is the right answer to
        all of them.
        """
        found = self._locate(sha)
        if found is None:
            return None
        pack_path, offset = found
        try:
            raw = pack_path.read_bytes()
        except OSError:
            return None
        resolved = self._read_at(raw, offset, depth=0)
        if resolved is None:
            return None
        type_id, body = resolved
        name = _TYPE_NAMES.get(type_id)
        return None if name is None else (name, body)

    def _read_at(self, raw: bytes, offset: int, depth: int) -> tuple[int, bytes] | None:
        """Decode the object at ``offset``, following deltas to their base."""
        if depth > _MAX_DELTA_DEPTH or offset >= len(raw):
            return None
        header = self._read_object_header(raw, offset)
        if header is None:
            return None
        type_id, size, cursor = header

        if type_id in (_OBJ_COMMIT, _OBJ_TREE, _OBJ_BLOB, _OBJ_TAG):
            body = self._inflate(raw, cursor, size)
            return None if body is None else (type_id, body)

        if type_id == _OBJ_OFS_DELTA:
            back = self._read_offset_delta_base(raw, cursor)
            if back is None:
                return None
            distance, cursor = back
            base_offset = offset - distance
            if base_offset < 0:
                return None
            base = self._read_at(raw, base_offset, depth + 1)
        elif type_id == _OBJ_REF_DELTA:
            if cursor + 20 > len(raw):
                return None
            base_sha = raw[cursor : cursor + 20].hex()
            cursor += 20
            # A REF_DELTA may point into ANOTHER pack. Resolving it means a
            # fresh lookup, not an offset inside this one.
            located = self._locate(base_sha)
            if located is None:
                return None
            base_pack, base_offset = located
            try:
                base_raw = base_pack.read_bytes()
            except OSError:
                return None
            base = self._read_at(base_raw, base_offset, depth + 1)
        else:
            return None

        if base is None:
            return None
        delta = self._inflate(raw, cursor, size)
        if delta is None:
            return None
        patched = self._apply_delta(base[1], delta)
        return None if patched is None else (base[0], patched)

    @staticmethod
    def _read_object_header(raw: bytes, offset: int) -> tuple[int, int, int] | None:
        """Parse the type+size varint. Returns ``(type_id, size, next_offset)``."""
        if offset >= len(raw):
            return None
        byte = raw[offset]
        type_id = (byte >> 4) & 0x07
        size = byte & 0x0F
        shift = 4
        cursor = offset + 1
        while byte & 0x80:
            if cursor >= len(raw) or shift > 60:
                return None
            byte = raw[cursor]
            size |= (byte & 0x7F) << shift
            shift += 7
            cursor += 1
        if size > _MAX_OBJECT_BYTES:
            return None
        return type_id, size, cursor

    @staticmethod
    def _read_offset_delta_base(raw: bytes, cursor: int) -> tuple[int, int] | None:
        """Parse the OFS_DELTA negative offset. Returns ``(distance, next)``."""
        if cursor >= len(raw):
            return None
        byte = raw[cursor]
        cursor += 1
        distance = byte & 0x7F
        steps = 0
        while byte & 0x80:
            if cursor >= len(raw) or steps > 8:
                return None
            byte = raw[cursor]
            cursor += 1
            distance = ((distance + 1) << 7) | (byte & 0x7F)
            steps += 1
        return distance, cursor

    @staticmethod
    def _inflate(raw: bytes, cursor: int, expected: int) -> bytes | None:
        """Inflate one deflate stream and CHECK its length against the header.

        The length check is not decoration: a stream that inflates to the
        wrong size means the pack disagrees with itself, and returning those
        bytes would be the silently-wrong read this module exists to avoid.
        """
        try:
            body = zlib.decompressobj().decompress(raw[cursor:], _MAX_OBJECT_BYTES + 1)
        except zlib.error:
            return None
        return body if len(body) == expected else None

    @staticmethod
    def _apply_delta(base: bytes, delta: bytes) -> bytes | None:
        """Apply a git delta to ``base``, refusing anything inconsistent."""
        cursor = 0

        def varint() -> int | None:
            nonlocal cursor
            value = 0
            shift = 0
            while True:
                if cursor >= len(delta) or shift > 60:
                    return None
                byte = delta[cursor]
                cursor += 1
                value |= (byte & 0x7F) << shift
                if not byte & 0x80:
                    return value
                shift += 7

        base_size = varint()
        result_size = varint()
        if base_size is None or result_size is None or base_size != len(base):
            return None
        out = bytearray()
        while cursor < len(delta):
            opcode = delta[cursor]
            cursor += 1
            if opcode & 0x80:
                # COPY: offset and size are assembled from the flagged bytes.
                offset = 0
                size = 0
                for bit in range(4):
                    if opcode & (1 << bit):
                        if cursor >= len(delta):
                            return None
                        offset |= delta[cursor] << (bit * 8)
                        cursor += 1
                for bit in range(3):
                    if opcode & (1 << (4 + bit)):
                        if cursor >= len(delta):
                            return None
                        size |= delta[cursor] << (bit * 8)
                        cursor += 1
                if size == 0:
                    size = 0x10000
                if offset + size > len(base):
                    return None
                out += base[offset : offset + size]
            elif opcode:
                # INSERT: the next `opcode` bytes are literal.
                if cursor + opcode > len(delta):
                    return None
                out += delta[cursor : cursor + opcode]
                cursor += opcode
            else:
                return None  # opcode 0 is reserved and must never appear
        return bytes(out) if len(out) == result_size else None
