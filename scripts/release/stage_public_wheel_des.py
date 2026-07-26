"""Stage the public-wheel DES payload into both Hatch source locations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path


TEMPORARY = ".nwave-wheel-lib.tmp"
BACKUP = ".nwave-wheel-lib.backup"
JOURNAL = ".nwave-wheel-lib.journal.json"
_STATES = frozenset({"PREPARED", "OLD_MOVED", "NEW_PROMOTED", "COMMITTED"})
_REPARSE_ATTRIBUTE = 0x400


class StageError(Exception):
    """A finite, caller-safe staging failure."""

    def __init__(self, code: str, action: str = "") -> None:
        self.code = code
        self.action = action
        super().__init__(code)


def _indirection(path: Path, metadata: os.stat_result) -> bool:
    return (
        stat.S_ISLNK(metadata.st_mode)
        or bool(getattr(path, "is_junction", lambda: False)())
        or bool(int(getattr(metadata, "st_file_attributes", 0)) & _REPARSE_ATTRIBUTE)
    )


def _exists(path: Path) -> bool:
    return os.path.lexists(path)


def _under(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _overlaps(first: Path, second: Path) -> bool:
    return _under(first, second) or _under(second, first)


def _scan(path: Path) -> None:
    """Refuse links, junctions and reparse points in an existing tree."""
    if not _exists(path):
        return
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise StageError("STAGE_REPARSE_POINT") from exc
    if _indirection(path, metadata):
        raise StageError("STAGE_REPARSE_POINT")
    if stat.S_ISDIR(metadata.st_mode):
        try:
            entries = tuple(os.scandir(path))
        except OSError as exc:
            raise StageError("STAGE_REPARSE_POINT") from exc
        for entry in entries:
            _scan(Path(entry.path))


def _scan_ancestors(root: Path, path: Path) -> None:
    current = path
    chain: list[Path] = []
    while True:
        chain.append(current)
        if current == root:
            break
        parent = current.parent
        if parent == current:
            raise StageError("STAGE_PATH_ESCAPE")
        current = parent
    for component in reversed(chain):
        if _exists(component):
            try:
                metadata = os.lstat(component)
            except OSError as exc:
                raise StageError("STAGE_REPARSE_POINT") from exc
            if _indirection(component, metadata):
                raise StageError("STAGE_REPARSE_POINT")


def _protected_paths(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    return (
        root / "dist" / "lib" / "python" / "des",
        root / "lib",
        root / TEMPORARY,
        root / BACKUP,
        root / JOURNAL,
    )


def _validate_paths(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    source, candidate, temporary, backup, journal = _protected_paths(root)
    resolved_root = root.resolve(strict=False)
    resolved = tuple(
        path.resolve(strict=False)
        for path in (source, candidate, temporary, backup, journal)
    )
    if not all(_under(resolved_root, path) for path in resolved) or any(
        _overlaps(source_path, other)
        for index, source_path in enumerate(resolved)
        for other in resolved[index + 1 :]
    ):
        raise StageError("STAGE_PATH_ESCAPE")
    _scan_ancestors(root, root)
    for path in (source, candidate, temporary, backup, journal):
        _scan_ancestors(root, path)
        _scan(path)
    return source, candidate, temporary, backup, journal


def _manifest(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        raise StageError("STAGE_SOURCE_INVALID")
    init = root / "__init__.py"
    if not init.is_file() or not stat.S_ISREG(os.lstat(init).st_mode):
        raise StageError("STAGE_SOURCE_INVALID")
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            metadata = os.lstat(path)
            if not stat.S_ISREG(metadata.st_mode):
                raise StageError("STAGE_SOURCE_INVALID")
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    if not result:
        raise StageError("STAGE_SOURCE_INVALID")
    return result


def _digest(manifest: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative, payload in sorted(manifest.items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def _stage_manifest(
    root: Path, source_manifest: dict[str, bytes]
) -> dict[str, bytes] | None:
    if not root.is_dir():
        return None
    expected = {
        **{f"python/des/{name}": payload for name, payload in source_manifest.items()},
        **{
            f"nwave-runtime/des/{name}": payload
            for name, payload in source_manifest.items()
        },
    }
    found: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            found[path.relative_to(root).as_posix()] = path.read_bytes()
    return found if found == expected else None


def _flush_directory(directory: Path) -> None:
    try:
        descriptor = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError as exc:
        raise StageError("STAGE_FLUSH_FAILED") from exc
    finally:
        os.close(descriptor)


def _write_journal(path: Path, state: str, old_present: bool, digest: str) -> None:
    payload = {
        "schema_version": 1,
        "state": state,
        "old_present": old_present,
        "source_manifest_sha256": digest,
        "new_manifest_sha256": digest,
        "paths": {"candidate": "lib", "temporary": TEMPORARY, "backup": BACKUP},
    }
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        _flush_directory(path.parent)
    except StageError:
        raise
    except OSError as exc:
        raise StageError("STAGE_FLUSH_FAILED") from exc


def _read_journal(path: Path, digest: str) -> tuple[str, bool]:
    try:
        journal = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageError("STAGE_JOURNAL_INVALID") from exc
    required = {
        "schema_version",
        "state",
        "old_present",
        "source_manifest_sha256",
        "new_manifest_sha256",
        "paths",
    }
    if not isinstance(journal, dict) or set(journal) != required:
        raise StageError("STAGE_JOURNAL_INVALID")
    if (
        journal["schema_version"] != 1
        or journal["state"] not in _STATES
        or type(journal["old_present"]) is not bool
        or not isinstance(journal["paths"], dict)
    ):
        raise StageError("STAGE_JOURNAL_INVALID")
    if journal["paths"] != {
        "candidate": "lib",
        "temporary": TEMPORARY,
        "backup": BACKUP,
    }:
        raise StageError("STAGE_RECOVERY_AMBIGUOUS")
    if (
        journal["source_manifest_sha256"] != digest
        or journal["new_manifest_sha256"] != digest
    ):
        raise StageError("STAGE_RECOVERY_AMBIGUOUS")
    return str(journal["state"]), bool(journal["old_present"])


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif _exists(path):
        path.unlink()


def _rollback(
    candidate: Path, temporary: Path, backup: Path, old_present: bool
) -> None:
    try:
        _remove(temporary)
        _remove(candidate)
        if old_present:
            if not backup.is_dir():
                raise OSError("backup missing")
            backup.rename(candidate)
    except OSError as exc:
        raise StageError("STAGE_ROLLBACK_FAILED") from exc


def _fail_verify(
    candidate: Path, temporary: Path, backup: Path, old_present: bool
) -> None:
    _rollback(candidate, temporary, backup, old_present)
    raise StageError("STAGE_VERIFY_FAILED", "restored the prior candidate")


def _recover(
    candidate: Path,
    temporary: Path,
    backup: Path,
    journal: Path,
    source_manifest: dict[str, bytes],
) -> bool:
    if not _exists(journal):
        if _exists(backup):
            raise StageError("STAGE_RECOVERY_AMBIGUOUS")
        if _exists(temporary):
            if not temporary.is_dir():
                raise StageError("STAGE_RECOVERY_AMBIGUOUS")
            _remove(temporary)
        return False

    state, old_present = _read_journal(journal, _digest(source_manifest))
    new_temp = _stage_manifest(temporary, source_manifest)
    new_candidate = _stage_manifest(candidate, source_manifest)
    has_candidate = _exists(candidate)
    has_temporary = _exists(temporary)
    has_backup = _exists(backup)

    valid = False
    if state == "PREPARED":
        valid = (
            old_present
            and (
                (has_candidate and new_temp is not None and not has_backup)
                or (has_backup and new_temp is not None and not has_candidate)
            )
        ) or (
            not old_present
            and new_temp is not None
            and not has_candidate
            and not has_backup
        )
        if not valid:
            if has_backup and not old_present:
                raise StageError("STAGE_RECOVERY_AMBIGUOUS")
            if old_present and has_candidate and has_temporary and not has_backup:
                _remove(temporary)
                raise StageError("STAGE_VERIFY_FAILED", "kept the prior candidate")
            if old_present and has_backup and has_temporary:
                _fail_verify(candidate, temporary, backup, old_present)
            if not old_present and has_temporary:
                _fail_verify(candidate, temporary, backup, old_present)
            raise StageError("STAGE_RECOVERY_AMBIGUOUS")
        if has_candidate:
            candidate.rename(backup)
        _write_journal(journal, "OLD_MOVED", old_present, _digest(source_manifest))
        temporary.rename(candidate)
        _write_journal(journal, "NEW_PROMOTED", old_present, _digest(source_manifest))
    elif state == "OLD_MOVED":
        valid = (
            old_present
            and has_backup
            and (
                (new_temp is not None and not has_candidate)
                or (new_candidate is not None and not has_temporary)
            )
        ) or (
            not old_present
            and (
                (new_temp is not None and not has_candidate and not has_backup)
                or (new_candidate is not None and not has_temporary and not has_backup)
            )
        )
        if not valid:
            if (old_present and has_backup) or (
                not old_present and (has_temporary or has_candidate)
            ):
                _fail_verify(candidate, temporary, backup, old_present)
            raise StageError("STAGE_RECOVERY_AMBIGUOUS")
        if new_temp is not None:
            temporary.rename(candidate)
        _write_journal(journal, "NEW_PROMOTED", old_present, _digest(source_manifest))
    elif state in {"NEW_PROMOTED", "COMMITTED"}:
        valid = (
            new_candidate is not None
            and not has_temporary
            and (
                (old_present and has_backup)
                or (not old_present and not has_backup)
                or (state == "COMMITTED" and old_present and not has_backup)
            )
        )
        if not valid:
            if old_present and has_backup:
                _fail_verify(candidate, temporary, backup, old_present)
            if not old_present and (has_candidate or has_temporary):
                _fail_verify(candidate, temporary, backup, old_present)
            raise StageError("STAGE_RECOVERY_AMBIGUOUS")
    if _stage_manifest(candidate, source_manifest) is None:
        _fail_verify(candidate, temporary, backup, old_present)
    _write_journal(journal, "COMMITTED", old_present, _digest(source_manifest))
    if _exists(backup):
        _remove(backup)
    _remove(journal)
    return True


def _stage(root: Path) -> None:
    source, candidate, temporary, backup, journal = _validate_paths(root)
    if not _exists(source):
        raise StageError("STAGE_SOURCE_MISSING")
    source_manifest = _manifest(source)
    if _recover(candidate, temporary, backup, journal, source_manifest):
        _remove(root / "dist")
        return

    old_present = _exists(candidate)
    try:
        temporary.mkdir()
        shutil.copytree(source, temporary / "python" / "des")
        shutil.copytree(source, temporary / "nwave-runtime" / "des")
    except OSError as exc:
        _remove(temporary)
        raise StageError("STAGE_COPY_FAILED") from exc
    if _stage_manifest(temporary, source_manifest) is None:
        _remove(temporary)
        raise StageError("STAGE_VERIFY_FAILED")
    _write_journal(journal, "PREPARED", old_present, _digest(source_manifest))
    try:
        if old_present:
            candidate.rename(backup)
        _write_journal(journal, "OLD_MOVED", old_present, _digest(source_manifest))
        temporary.rename(candidate)
        _write_journal(journal, "NEW_PROMOTED", old_present, _digest(source_manifest))
    except (OSError, StageError) as exc:
        _rollback(candidate, temporary, backup, old_present)
        if isinstance(exc, StageError):
            raise
        raise StageError("STAGE_RENAME_FAILED") from exc
    if _stage_manifest(candidate, source_manifest) is None:
        _fail_verify(candidate, temporary, backup, old_present)
    _write_journal(journal, "COMMITTED", old_present, _digest(source_manifest))
    _remove(backup)
    _remove(journal)
    try:
        _remove(root / "dist")
    except OSError as exc:
        raise StageError("STAGE_CLEANUP_FAILED") from exc


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--cleanup-dist", action="store_true", required=True)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    try:
        _stage(args.project_root.absolute())
    except StageError as exc:
        suffix = f": {exc.action}" if exc.action else ""
        print(f"{exc.code}{suffix}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
