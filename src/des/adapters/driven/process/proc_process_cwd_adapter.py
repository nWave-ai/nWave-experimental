"""ProcProcessCwdAdapter -- Linux `/proc` implementation of ProcessCwdProbePort.

fix-worktree-removal-liveness-guard. The concrete OS side of the "is a
process live in this directory right now" boundary: reads every
`/proc/<pid>/cwd` symlink and reports which ones resolve under the probed
path.

`/proc` enters here ONLY (AD-21 target-machine-agnosticism mandate; the
triage predicate in `des.domain.worktree_anti_rot_triage` stays OS-free).
Degrades LOUD to `Indeterminate` when the mechanism is absent (non-Linux
host) or when a SAME-OWNER candidate PID's cwd link could not be read for a
reason other than "the process exited mid-scan" -- a permission-denied link
on OUR OWN process might be hiding exactly the live process this probe
exists to find, so that case is never silently skipped (GDP-8 arity
corollary).

Candidate filtering has two layers, both narrowing WHO can plausibly be
"this lane's own process" rather than weakening what happens once a real
candidate is unreadable:

1. Same-OS-user only (`os.stat` ownership, world-readable regardless of
   `cwd` access). A different OS user's process cannot be a lane's own
   worktree-bound process in the single-user-per-box deployment model every
   lane here runs under -- excluded from the candidate set, not escalated.
2. A short, named non-candidate `comm` allowlist (`_NON_CANDIDATE_COMM_NAMES`)
   for same-user daemons that are STRUCTURALLY non-dumpable (self-protected
   via `prctl(PR_SET_DUMPABLE, 0)`, a standard systemd hardening practice --
   NOT a fact about this one box) and therefore permission-denied on `cwd`
   for every unprivileged reader, including same-user ones: `systemd --user`
   and its child `(sd-pam)`. `/proc/<pid>/comm` is always world-readable
   (unlike `cwd`), so this check costs nothing extra to make. These two
   daemons can categorically never be a git worktree lane process, so
   excluding them by name is a bounded, well-understood exception --
   NOT the "escalate on any unreadable PID" arity corollary being weakened;
   a same-user PID with any OTHER comm that is unreadable still escalates.
   Without this exception the guard would refuse UNCONDITIONALLY on any
   systemd-user-session host (measured on this project's own dev box:
   these two PIDs are always present and always permission-denied),
   training operators to reach for the override reflexively -- the
   normalize-the-bypass failure mode a guard must not create.
"""

from __future__ import annotations

import os
from pathlib import Path

from des.ports.driven_ports.process_cwd_probe_port import (
    Indeterminate,
    ProcessCwdMatch,
    ProcessCwdProbePort,
)


_PROC_ROOT = Path("/proc")

# Same-user daemons that are structurally non-dumpable (systemd hardening,
# not a per-box quirk) and therefore permission-denied on `cwd` for every
# unprivileged reader. See module docstring layer 2.
_NON_CANDIDATE_COMM_NAMES = frozenset({"systemd", "(sd-pam)"})


def _comm(entry: Path) -> str | None:
    """Best-effort read of `/proc/<pid>/comm` (always world-readable)."""
    try:
        return (entry / "comm").read_text(encoding="utf-8").strip()
    except OSError:
        return None


class ProcProcessCwdAdapter(ProcessCwdProbePort):
    """Reads live-process cwd out of Linux `/proc/<pid>/cwd` symlinks."""

    def pids_with_cwd_under(
        self, path: Path
    ) -> tuple[ProcessCwdMatch, ...] | Indeterminate:
        if not _PROC_ROOT.is_dir():
            return Indeterminate(
                f"/proc is not available on this host (checked {_PROC_ROOT}) "
                "-- process liveness cannot be probed mechanically here"
            )
        try:
            pid_dirs = [entry for entry in _PROC_ROOT.iterdir() if entry.name.isdigit()]
        except OSError as exc:
            return Indeterminate(f"/proc could not be listed: {exc}")

        own_uid = os.getuid()
        target = path.resolve()
        matches: list[ProcessCwdMatch] = []
        unreadable: list[int] = []

        for entry in pid_dirs:
            pid = int(entry.name)
            try:
                owner_uid = entry.stat().st_uid
            except OSError:
                # The process exited between listing and stat'ing -- benign race.
                continue
            if owner_uid != own_uid:
                # A different OS user's process cannot be OUR OWN lane's
                # process -- excluded from the candidate set, not escalated.
                continue
            try:
                cwd_path = (entry / "cwd").readlink()
            except (FileNotFoundError, ProcessLookupError):
                # Benign race: the process exited between listing and reading.
                continue
            except OSError:
                if _comm(entry) in _NON_CANDIDATE_COMM_NAMES:
                    # A known, structurally non-dumpable session daemon --
                    # categorically not a lane process. Excluded, not escalated.
                    continue
                # A SAME-owner PID whose cwd link still could not be read:
                # this candidate could not be ruled out -- escalate, never skip.
                unreadable.append(pid)
                continue
            if cwd_path == target or target in cwd_path.parents:
                matches.append(ProcessCwdMatch(pid=pid, cwd=str(cwd_path)))

        if unreadable:
            return Indeterminate(
                f"{len(unreadable)} own-user process cwd link(s) could not be "
                f"read -- PID(s) {sorted(unreadable)}; a live process might be "
                "hiding behind one of them"
            )
        return tuple(matches)


__all__ = ["ProcProcessCwdAdapter"]
