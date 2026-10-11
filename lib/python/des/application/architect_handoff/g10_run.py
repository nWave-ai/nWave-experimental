"""The sole writer of receipts (GDP-0: keep one writer for shared state; never ask the author to compile
fields the tree already derives). `execute` runs a command and records what was OBSERVED: the literal
argv, the real exit status, the duration, the output bytes, the trace bytes (if a trace path was given
and the command wrote it) and, for the quint tool kinds, the version printed by argv[0] (other kinds:
the version printed by the caller-declared version command). Everything else in a receipt is DECLARED
by the caller: tool kind, target, variant, model id, checks, seed, measure, violation exit, trace path,
timeout, working directory. The result class comes from evidence, not from the exit status alone: a
quint run/verify is a `violation` only when the kept trace says `#meta.status == "violation"` or, with
no kept trace, when stdout has a `[violation]` line; every other non-zero exit is an `error` unless the
caller declared `violation_exit` and the process ended with exactly that status. `record_authored`
stores a claim about a run that was not executed here; such a run has no artifacts, which is how the
grammar tells a claim from a measurement.

Both command and version spawns use the shared boundary's closed stdin and
POSIX timeout process-group reaping. The version probe retains its 60-second
bound; execution retains the caller's declared timeout, including --timeout.

Failures leave the recorded state intact: everything is validated before the command runs, the output
artifact and the receipts file are written through a temporary file and os.replace, and the receipts
read-modify-write happens under an exclusive flock on <dir>/.g10.lock where fcntl is available.
The standalone API defaults to g10.receipts.json. Native integration supplies ReceiptStore,
whose atomic append owns the accumulated handover; no standalone receipt file is then written."""

from __future__ import annotations


try:
    import fcntl
except ImportError:
    fcntl = None
import contextlib
import json
import os
import stat
import subprocess
import tempfile
import time
import typing as t
from pathlib import Path

from des.runtime.spawn import spawn

from . import g10_codec as C
from . import g10_types as T
from .g10_defect import Defect


RECEIPTS_FILE = "g10.receipts.json"
_QUINT_TOOLS = frozenset(
    {"quint_typecheck", "quint_run", "quint_verify"}
)  # this tool reads their output
# tools whose output this tool cannot read: a violation is only what the caller declares
_DECLARED_TOOLS = frozenset({"tlc", "apalache", "test", "script", "agda"})
_MAX_OUTPUT = 4_000_000  # bytes kept per stream
_TIMEOUT_MAX = 86_400  # seconds


class ReceiptStore(t.Protocol):
    """Canonical semantic storage; append atomically preserves unrelated handover facts.

    Implementations must refuse duplicate IDs unless replace is true, including races
    after load, and report persistence failures rather than silently losing receipts.
    Artifact files remain driven evidence, not a second semantic receipt authority.
    """

    def load(self) -> tuple[T.Run, ...]: ...

    def append(
        self,
        run: T.Run,
        *,
        replace: bool = False,
        publication: contextlib.AbstractContextManager[None] | None = None,
    ) -> None: ...


class RunError(Exception):
    def __init__(self, defect: Defect):
        super().__init__(defect.what)
        self.defect = defect


def _err(rule: str, what: str, why: str, how: str) -> RunError:
    return RunError(Defect(rule, "g10 run", what, why, how))


def _require_file_lock() -> None:
    if fcntl is None:
        raise _err(
            "RUN5",
            "standalone receipt-file storage is unavailable: this platform has no fcntl",
            "updating the receipt file without an exclusive lock can lose another writer's receipts",
            "use the native des CLI with its canonical handover ReceiptStore, or run standalone storage on POSIX",
        )


def _first_line(*streams: bytes) -> str:
    for s in streams:
        for line in s.decode("utf-8", "replace").splitlines():
            if line.strip():
                return line.strip()
    return ""


def tool_version(tool: str, version_argv: t.Sequence[str] | None, cwd: str) -> str:
    argv = list(version_argv) if version_argv else None
    if not argv:
        raise _err(
            "RUN1",
            f"no way to read the version of tool {tool!r}",
            "a receipt without the tool version cannot be repeated (E-V2-A-70)",
            "pass --version-argv with the command that prints it, for example --version-argv 'java -version'",
        )
    try:
        p = spawn(
            argv,
            cwd=cwd,
            capture_output=True,
            timeout=60,
            check=False,
            reap_process_group=(os.name == "posix"),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _err(
            "RUN1",
            f"the version command {argv!r} did not run: {exc}",
            "a receipt without the tool version cannot be repeated",
            "install the tool or fix --version-argv",
        ) from exc
    v = _first_line(p.stdout, p.stderr)
    if not v:
        raise _err(
            "RUN1",
            f"the version command {argv!r} printed nothing",
            "a receipt without the tool version cannot be repeated",
            "pass --version-argv with a command that prints the version",
        )
    return v


def result_class(
    tool: str,
    exit_status: int,
    timed_out: bool,
    *,
    violation_exit: int | None = None,
    evidence: bool = False,
) -> str:
    """The class comes from evidence, never from the exit status alone."""
    if timed_out:
        return "timeout"
    if exit_status == 0:
        return "ok"
    if tool in ("quint_run", "quint_verify"):
        return "violation" if evidence else "error"
    if tool in _DECLARED_TOOLS:
        return (
            "violation"
            if violation_exit is not None and exit_status == violation_exit
            else "error"
        )
    return "error"


def _trace_says_violation(directory: str, rel: str) -> bool:
    """The kept ITF trace is the evidence: #meta.status == "violation"."""
    try:
        with open(os.path.join(directory, rel), "rb") as fh:
            doc = json.loads(fh.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        return False
    meta = doc.get("#meta") if isinstance(doc, dict) else None
    return isinstance(meta, dict) and meta.get("status") == "violation"


def _stdout_says_violation(out: bytes) -> bool:
    """Without a kept trace, the `[violation] ...` line quint prints is the evidence."""
    return any(
        line.lstrip().startswith("[violation]")
        for line in out.decode("utf-8", "replace").splitlines()
    )


def _load(path: str) -> T.Handoff:
    if not os.path.exists(path):
        return {}
    doc, ds = C.load_json(path)
    h, more = C.decode_handoff(doc) if not ds else (None, [])
    if h is None:
        raise RunError((ds + more)[0])
    return h


def _store(path: str, h: T.Handoff) -> None:
    fd, tmp = tempfile.mkstemp(dir=Path(path).parent, prefix=".g10-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(C.to_json(h), fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    Path(tmp).chmod(
        0o644
    )  # mkstemp makes a private file; every role and CI reads receipts
    Path(tmp).replace(path)


def _runs_of(path: str) -> tuple[T.Handoff, list[T.Run]]:
    h = _load(path)
    e = h.get(("receipts", "shared"))
    return h, (
        list(e.status.payload.runs)
        if e is not None and isinstance(e.status, T.Applicable)
        else []
    )


def _refuse_repeat(
    runs: list[T.Run], run_id: str, receipts_file: str, replace: bool
) -> None:
    if not replace and any(r.id == run_id for r in runs):
        raise _err(
            "RUN2",
            f"run {run_id!r} is already recorded in {receipts_file}",
            "a receipt is cited by id; a silent overwrite would change what other sections cite",
            "choose another --id, or pass --replace to record this run in its place",
        )


def _decode_run(raw: dict) -> T.Run:
    ds: list[Defect] = []
    r = C.dec(T.Run, raw, "$.run", ds)
    if r is C.BAD:
        raise RunError(ds[0])
    return r


def _relpath(p: str, what: str) -> str:
    if not T.valid("RelPath", p):
        raise _err(
            "RUN3",
            f"{what} {p!r} is not a relative path inside the directory of the sidecar",
            "kept files are found by a path beside the sidecar",
            "use a path such as traces/walk.itf.json",
        )
    return p


def _keep(directory: str, rel: str, ran: tuple[int, str]) -> tuple[str, str]:
    """The path and hash of the trace the command was told to write; a command that ran and wrote none records nothing."""
    try:
        with open(os.path.join(directory, rel), "rb") as fh:
            return rel, T.sha256_bytes(fh.read())
    except OSError as exc:
        raise _err(
            "RUN3",
            f"the command ran (exit {ran[0]}, output sha256 {ran[1]}) but NOTHING was recorded: "
            f"the file {rel} was not written by the command ({exc.strerror})",
            "a receipt must not cite a trace that this run did not produce",
            "pass the same path to the command (for quint: --out-itf=<path>) and to --trace, then run it again",
        ) from exc


def _check_timeout(timeout_s: int) -> None:
    if not isinstance(timeout_s, int) or not 1 <= timeout_s <= _TIMEOUT_MAX:
        raise _err(
            "RUN6",
            f"the timeout {timeout_s!r} is not an integer number of seconds in 1..{_TIMEOUT_MAX}",
            "a timeout this tool cannot honour would be recorded as one that it did",
            "pass a number of seconds in 1..86400",
        )


def _preflight_dir(directory: str) -> None:
    """The sidecar directory must exist (or its parent, to create just it) and be writable, before anything runs."""
    try:
        if os.path.lexists(directory) and not os.path.isdir(directory):
            raise _err(
                "RUN5",
                f"the sidecar directory {directory!r} is not a directory",
                "receipts and artifacts are kept beside the sidecar",
                "pass --dir a directory, not a file or a symlink to one",
            )
        if not os.path.isdir(directory):
            parent = str(Path(directory).parent)
            if not os.path.isdir(parent):
                raise _err(
                    "RUN5",
                    f"the sidecar directory {directory!r} does not exist and its parent {parent!r} does not exist",
                    "receipts and artifacts are kept beside the sidecar",
                    "create the directory (and its parent), or pass --dir an existing directory",
                )
            try:
                Path(directory).mkdir()
            except OSError as exc:
                raise _err(
                    "RUN5",
                    f"cannot create the sidecar directory {directory!r}: {exc.strerror}",
                    "receipts and artifacts are kept beside the sidecar",
                    "create it yourself, or pass --dir a directory you may write",
                ) from exc
        fd, probe = tempfile.mkstemp(dir=directory, prefix=".g10-probe-")
        os.close(fd)
        Path(probe).unlink()
    except OSError as exc:
        raise _err(
            "RUN5",
            f"the sidecar directory {directory!r} is not writable: {exc.strerror}",
            "the receipts file and the artifacts are written in this directory",
            "make it writable (chmod u+w) or pass --dir a writable directory",
        ) from exc


def _preflight_artifacts(directory: str, run_id: str) -> str:
    """Refuse symlinked escape routes before anything runs: artifacts stay inside the sidecar directory."""
    root = os.path.realpath(directory)
    arts = os.path.join(directory, "artifacts")
    if Path(arts).is_symlink() or not os.path.realpath(arts).startswith(root + os.sep):
        raise _err(
            "RUN5",
            f"the artifacts path {arts!r} is a symlink or resolves outside {directory!r}",
            "a symlink there would make the writer touch files outside the sidecar",
            "remove the symlink; artifacts/<run id>.out must be a plain file inside the sidecar directory",
        )
    try:
        Path(arts).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _err(
            "RUN5",
            f"cannot create the artifacts directory {arts!r}: {exc.strerror}",
            "the output artifact is kept at artifacts/<run id>.out",
            "make the sidecar directory writable or remove what is in the way",
        ) from exc
    out_abs = os.path.join(arts, f"{run_id}.out")
    _regular_output(out_abs)
    return out_abs


def _regular_output(path: str) -> os.stat_result | None:
    """Inspect the directory entry without opening or following its destination."""
    try:
        observed = Path(path).lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise _err(
            "RUN5",
            f"cannot inspect output artifact {path!r}: {exc}",
            "output custody must be known before execution or publication",
            "restore access to the artifact directory before retrying",
        ) from exc
    if stat.S_ISLNK(observed.st_mode):
        raise _err(
            "RUN5",
            f"the output artifact {path!r} is a symlink",
            "writing through it would touch a file outside the sidecar",
            "remove the symlink; g10 run replaces the file itself, never what it points to",
        )
    if not stat.S_ISREG(observed.st_mode):
        raise _err(
            "RUN5",
            f"the output artifact {path!r} is not a regular file",
            "a FIFO, device, socket or directory is not a safe output artifact",
            "remove the non-regular destination or choose another --dir before retrying",
        )
    return observed


def _preflight_trace(
    directory: str, trace: str, runs: list[T.Run], run_id: str, replace: bool
) -> str | None:
    """A trace that already exists is stale unless the run being replaced cites exactly it."""
    p = os.path.join(directory, trace)
    if not os.path.lexists(p):
        return None
    cited = [r.id for r in runs if any(a.path == trace for a in r.artifacts)]
    if replace and cited == [run_id]:
        return p  # the one receipt that cites this file is the run being replaced: refresh it in place
    raise _err(
        "RUN3",
        f"the trace file {trace!r} already exists before the command runs",
        "the receipt would hash a file the command may not have written",
        "delete it yourself, or pass --replace when this run replaces the run that cites it",
    )


def _signature(path: str) -> tuple[int, int, str]:
    """What a trace looks like before a command that may rewrite it: modification time, size and hash."""
    try:
        st = Path(path).stat()
        with open(path, "rb") as fh:
            return st.st_mtime_ns, st.st_size, T.sha256_bytes(fh.read())
    except OSError as exc:
        raise _err(
            "RUN3",
            f"cannot read the trace file {path!r} before the command runs: {exc.strerror}",
            "the run being replaced cites this file; it is kept until the command has rewritten it",
            "fix the file or its permissions, then run it again",
        ) from exc


def _upsert(
    directory: str,
    receipts_file: str,
    run: T.Run,
    replace: bool,
    ran: tuple[int, str] | None = None,
) -> None:
    """Read-modify-write the receipts under an exclusive lock, so parallel writers cannot lose a receipt."""
    _require_file_lock()
    lock_path = os.path.join(directory, ".g10.lock")
    try:
        fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o644)
    except OSError as exc:
        raise _err(
            "RUN5",
            (
                f"the command ran (exit {ran[0]}, output sha256 {ran[1]}) but NOTHING was recorded: "
                f"cannot open the lock file {lock_path!r}: {exc.strerror}"
            )
            if ran
            else f"cannot open the lock file {lock_path!r}: {exc.strerror}",
            "the receipts file is updated under a lock, one writer at a time",
            "make the sidecar directory writable, then run it again",
        ) from exc
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        path = os.path.join(directory, receipts_file)
        h, runs = _runs_of(path)
        if not replace and any(r.id == run.id for r in runs):
            if ran is not None:
                raise _err(
                    "RUN2",
                    f"run {run.id!r} is already recorded in {receipts_file}: "
                    f"the command ran (exit {ran[0]}, output sha256 {ran[1]}) but NOTHING was recorded",
                    "another writer recorded this id while the command was running",
                    "run it again with another --id, or with --replace to record it in the other one's place",
                )
            raise _err(
                "RUN2",
                f"run {run.id!r} is already recorded in {receipts_file}",
                "a receipt is cited by id; a silent overwrite would change what other sections cite",
                "choose another --id, or pass --replace to record this run in its place",
            )
        runs = [r for r in runs if r.id != run.id]
        h[("receipts", "shared")] = T.Entry(
            kind="receipts",
            scope="shared",
            status=T.Applicable(payload=T.Receipts(runs=(*runs, run))),
        )
        _store(path, h)
    finally:
        os.close(fd)


# Original measured receipt metadata/API arity is a design fact preserved by this port.
def execute(  # noqa: PLR0913, PLR0917
    directory: str,
    run_id: str,
    tool: str,
    target: str,
    variant: str,
    argv: t.Sequence[str],
    *,
    model_id: str | None = None,
    model_file: str | None = None,
    checks: t.Sequence[str] = (),
    seed: str | None = None,
    measure: tuple[str, int] | None = None,
    trace: str | None = None,
    cwd: str | None = None,
    version_argv: t.Sequence[str] | None = None,
    timeout_s: int = 600,
    replace: bool = False,
    receipts_file: str = RECEIPTS_FILE,
    violation_exit: int | None = None,
    receipt_store: ReceiptStore | None = None,
) -> T.Run:
    if receipt_store is None:
        _require_file_lock()
    # Lexical normalization must not resolve symlinks before custody preflight.
    directory = os.path.abspath(directory)  # noqa: PTH100
    work = os.path.abspath(cwd) if cwd else directory  # noqa: PTH100
    argv = list(argv)
    _check_timeout(timeout_s)
    model_sha = None
    if model_file is not None:
        _relpath(model_file, "--model-file")
        try:
            with open(os.path.join(directory, model_file), "rb") as fh:
                model_sha = T.sha256_bytes(fh.read())
        except OSError as exc:
            raise _err(
                "RUN3",
                f"cannot read the model file {model_file}: {exc.strerror}",
                "the identity of the model text is recorded with the run",
                "give --model-file as a path relative to the sidecar directory",
            ) from exc
    if trace is not None:
        _relpath(trace, "--trace")
    pre: dict[str, t.Any] = {
        "id": run_id,
        "tool": tool,
        "tool_version": "preflight",
        "target": target,
        "variant": variant,
        "argv": argv,
        "exit_status": 0,
        "result_class": "ok",
        "checks": list(checks),
    }
    for k, v in (("model_id", model_id), ("seed", seed)):
        if v is not None:
            pre[k] = v
    if measure is not None:
        pre["measure"] = {"kind": measure[0], "value": measure[1]}
    _decode_run(
        pre
    )  # every shape defect is refused BEFORE the command runs, so a run is never wasted
    runs = (
        list(receipt_store.load())
        if receipt_store is not None
        else _runs_of(os.path.join(directory, receipts_file))[1]
    )
    _refuse_repeat(runs, run_id, receipts_file, replace)
    stale_trace = (
        _preflight_trace(directory, trace, runs, run_id, replace)
        if trace is not None
        else None
    )
    stale_signature = _signature(stale_trace) if stale_trace is not None else None
    _preflight_dir(directory)
    out_abs = _preflight_artifacts(directory, run_id)
    if tool in _QUINT_TOOLS:
        if not argv or os.path.basename(argv[0]) != "quint":
            raise _err(
                "RUN7",
                f"the command is not quint: {argv!r}",
                "the receipt would claim a quint tool that did not run, and the version of another binary",
                "pass the quint command (for example `quint run model.qnt`), or pick the tool kind of the command",
            )
        if violation_exit is not None:
            raise _err(
                "RUN7",
                "--violation-exit is declared for tools whose output this tool cannot read",
                "quint evidence (trace status or the [violation] line) is read from the output, not declared",
                "drop --violation-exit; the quint output itself says whether a check failed",
            )
    version = tool_version(
        tool,
        version_argv
        if version_argv
        else ([argv[0], "--version"] if tool in _QUINT_TOOLS else None),
        work,
    )
    start = time.monotonic()
    timed_out = False
    try:
        p = spawn(
            argv,
            cwd=work,
            capture_output=True,
            timeout=timeout_s,
            check=False,
            reap_process_group=(os.name == "posix"),
        )
        status, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out, status, out, err = True, 124, exc.stdout or b"", exc.stderr or b""
    except OSError as exc:
        raise _err(
            "RUN4",
            f"the command {argv!r} did not start: {exc.strerror}",
            "a receipt is only written for a command that ran",
            "fix the command or install the tool",
        ) from exc
    duration = round(time.monotonic() - start, 3)
    kept_out = out[:_MAX_OUTPUT] + b"\n--- stderr ---\n" + err[:_MAX_OUTPUT]
    ran: tuple[int, str] = (status, T.sha256_bytes(kept_out))
    if trace is not None:
        _keep(directory, trace, ran)  # must exist: validated before anything is written
        if (
            stale_signature is not None
            and _signature(os.path.join(directory, trace)) == stale_signature
        ):
            raise _err(
                "RUN3",
                f"the command ran (exit {status}, output sha256 {ran[1]}) but NOTHING was recorded: "
                f"the trace file {trace!r} was not rewritten by the command",
                "a receipt must not cite a trace that this run did not produce; the old receipt and the old file stay as they were",
                "pass the same path to the command (for quint: --out-itf=<path>) and to --trace, then run it again",
            )
    out_rel = f"artifacts/{run_id}.out"
    arts: list[dict[str, str]] = [{"role": "output", "path": out_rel, "sha256": ran[1]}]
    reads_evidence = tool in ("quint_run", "quint_verify")
    if trace is not None:
        rel, digest = _keep(directory, trace, ran)
        arts.append({"role": "trace", "path": rel, "sha256": digest})
    evidence = reads_evidence and (
        _trace_says_violation(directory, trace)
        if trace is not None
        else _stdout_says_violation(out)
    )
    raw: dict[str, t.Any] = {
        "id": run_id,
        "tool": tool,
        "tool_version": version,
        "target": target,
        "variant": variant,
        "argv": argv,
        "exit_status": status,
        "result_class": result_class(
            tool, status, timed_out, violation_exit=violation_exit, evidence=evidence
        ),
        "checks": list(checks),
        "duration_s": duration,
        "artifacts": arts,
    }
    if model_id is not None:
        raw["model_id"] = model_id
    if model_sha is not None:
        raw["model_sha256"] = model_sha
    if seed is not None:
        raw["seed"] = seed
    if measure is not None:
        raw["measure"] = {"kind": measure[0], "value": measure[1]}
    run = _decode_run(raw)
    if receipt_store is None:
        _write_output(out_abs, kept_out, ran)
        _upsert(directory, receipts_file, run, replace, ran)
    else:
        receipt_store.append(
            run,
            replace=replace,
            publication=_output_publication(out_abs, kept_out, ran),
        )
    return run


def _write_output(path: str, output: bytes, ran: tuple[int, str]) -> None:
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(
            dir=Path(path).parent,
            prefix=".g10-",
            suffix=".tmp",
        )
        with os.fdopen(fd, "wb") as fh:
            fh.write(output)
        Path(temporary).chmod(0o644)
        Path(temporary).replace(
            path
        )  # swaps the entry; never follows a destination symlink
    except OSError as exc:
        raise _err(
            "RUN5",
            f"the command ran (exit {ran[0]}, output sha256 {ran[1]}) but NOTHING was recorded: "
            f"cannot write the output artifact {path!r}: {exc.strerror}",
            "a receipt cites the artifact by hash; half state is worse than none",
            "fix the artifacts directory, then run it again",
        ) from exc
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


@contextlib.contextmanager
def _output_publication(
    path: str, output: bytes, ran: tuple[int, str]
) -> t.Iterator[None]:
    """Entered only after the native store reserves its current snapshot under lock."""
    previous = _regular_output(path)
    backup = None
    try:
        if previous is not None:
            try:
                fd, backup = tempfile.mkstemp(
                    dir=Path(path).parent,
                    prefix=".g10-previous-",
                    suffix=".tmp",
                )
                os.close(fd)
                Path(backup).unlink()
                # pathlib.hardlink_to has no no-follow option on supported Python versions.
                os.link(path, backup, follow_symlinks=False)
                saved = _regular_output(backup)
                current = _regular_output(path)
                if (
                    saved is None
                    or current is None
                    or (saved.st_dev, saved.st_ino)
                    != (previous.st_dev, previous.st_ino)
                    or (current.st_dev, current.st_ino)
                    != (previous.st_dev, previous.st_ino)
                ):
                    raise _err(
                        "RUN5",
                        f"the output artifact {path!r} changed before publication",
                        "the retained directory entry must match the observed regular file",
                        "inspect the artifact destination and retry from the current handover",
                    )
            except OSError as exc:
                raise _err(
                    "RUN5",
                    f"cannot reserve previous output {path!r}: {exc}",
                    "rollback requires retaining the original regular-file entry without reading it",
                    "restore artifact-directory access and hard-link support before retrying",
                ) from exc
        _write_output(path, output, ran)
        try:
            yield
        except BaseException:
            if backup is None:
                Path(path).unlink(missing_ok=True)
            else:
                Path(backup).replace(path)
            raise
    finally:
        if backup is not None:
            Path(backup).unlink(missing_ok=True)


# Original measured receipt metadata/API arity is a design fact preserved by this port.
def record_authored(  # noqa: PLR0913, PLR0917
    directory: str,
    run_id: str,
    tool: str,
    tool_version: str,
    target: str,
    variant: str,
    argv: t.Sequence[str],
    exit_status: int,
    result: str,
    *,
    model_id: str | None = None,
    model_sha256: str | None = None,
    checks: t.Sequence[str] = (),
    seed: str | None = None,
    measure: tuple[str, int] | None = None,
    duration_s: float | None = None,
    replace: bool = False,
    receipts_file: str = RECEIPTS_FILE,
    receipt_store: ReceiptStore | None = None,
) -> T.Run:
    """A claim about a run that was not executed here: no artifacts, so every reader can tell it from a measurement."""
    if receipt_store is None:
        _require_file_lock()
    raw: dict[str, t.Any] = {
        "id": run_id,
        "tool": tool,
        "tool_version": tool_version,
        "target": target,
        "variant": variant,
        "argv": list(argv),
        "exit_status": exit_status,
        "result_class": result,
        "checks": list(checks),
    }
    for k, v in (
        ("model_id", model_id),
        ("model_sha256", model_sha256),
        ("seed", seed),
        ("duration_s", duration_s),
    ):
        if v is not None:
            raw[k] = v
    if measure is not None:
        raw["measure"] = {"kind": measure[0], "value": measure[1]}
    run = _decode_run(raw)
    # Lexical normalization must not resolve symlinks before custody preflight.
    directory = os.path.abspath(directory)  # noqa: PTH100
    _preflight_dir(directory)
    if receipt_store is None:
        _upsert(directory, receipts_file, run, replace)
    else:
        receipt_store.append(run, replace=replace)
    return run
