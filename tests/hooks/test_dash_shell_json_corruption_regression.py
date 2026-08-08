"""D1 regression -- dash's builtin `echo` corrupts hook JSON under `/bin/sh`.

k3a-hook-payload-dash-safety, slice-01. Evidence:
`docs/analysis/2026-08-07-k3a-root-activation-evidence-report.md` Section 4.1.

`scripts.shared.hook_definitions.build_guard_command` and the three `_BASH_*`
guard constants wrap the hook envelope as `INPUT=$(cat); echo "$INPUT" | ...`.
Claude Code runs every installed hook command through `/bin/sh`, which on
Debian/Ubuntu (and this box) is **dash** -- and dash's builtin `echo`
interprets backslash escapes in its argument. Every `\\n` inside a JSON
string value (as `tool_input.old_string` / `tool_input.new_string` /
`tool_input.command` routinely carry, since a real multi-line Edit or Bash
invocation is exactly that) becomes a raw newline byte, and the envelope
stops being valid JSON before any handler ever sees it.

`handle_pre_write` fails OPEN on the parse error and returns 0 several
branches above the K3-A root-activation reminder -- the reminder is silently
never emitted. The three `_BASH_*` guards share the identical
`CMD=$(echo "$INPUT" | python3 -c '...json.load...')` extraction prefix;
under the same corruption `CMD` comes back empty, the guard's own
`grep ... || exit 0` fast-path fires, and the downstream Python guard never
runs -- a silent disarm, not a visible failure.

Driving port: the shell command STRINGS themselves (`build_guard_command`'s
return value and each `_BASH_*` constant), run through `subprocess` with
`executable="/bin/sh"` / `["/bin/sh", "-c", ...]` -- never `bash -c`. Every
existing test in `tests/build/unit/shared/test_hook_definitions.py`
(`TestBashGuardIntegration._run_guard`) drives these same strings through
`["bash", "-c", ...]`, which is exactly why this defect class was invisible:
bash's builtin `echo` does NOT expand backslash escapes by default, dash's
does. This module is the second axis (GDP-8 witness corollary) the existing
suite never measured on.

RED at HEAD, for the diagnosed reason (JSON corruption -- not an import or
fixture error): every corruption-dependent test in this module was run
against HEAD before authoring and observed failing on the assertion that
encodes the correct behaviour (byte-identity / reminder presence / guard
decision), never on a setup exception. `test_execution_log_guard_...`,
`test_git_stash_guard_...`, and
`test_worktree_removal_guard_...` each flip GREEN once the shared
`echo "$INPUT"` idiom is replaced with `printf '%s' "$INPUT"` (the remedy the
evidence report verified in isolation, Section 4.1).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.shared.hook_definitions import (
    _BASH_EXECUTION_LOG_GUARD,
    _BASH_GIT_STASH_GUARD,
    _BASH_WORKTREE_REMOVAL_GUARD,
    build_guard_command,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# /bin/sh reproducibility preflight -- explicit, named skip (never a silent
# pass) when this box's `/bin/sh` is not a real dash-shaped shell.
# ---------------------------------------------------------------------------


def _sh_echo_expands_backslash_escapes() -> bool:
    """True iff `/bin/sh`'s builtin `echo` interprets `\\n` as a real newline.

    This is dash's behaviour (Debian/Ubuntu default `/bin/sh`), the exact
    mechanism D1 exploits. POSIX does not mandate it -- a `/bin/sh` that is
    bash running in posix mode leaves the escape untouched, and on such a
    box this defect class does not reproduce via `echo` at all.
    """
    if not Path("/bin/sh").exists():
        return False
    try:
        probe = subprocess.run(
            ["/bin/sh", "-c", 'echo "a\\nb"'],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError:
        return False
    return probe.stdout == "a\nb\n"


_SH_EXISTS = Path("/bin/sh").exists()
_DASH_CLASS_REPRODUCIBLE = _sh_echo_expands_backslash_escapes()
_SKIP_REASON = (
    "no /bin/sh on this platform -- the POSIX-sh corruption class is inapplicable"
    if not _SH_EXISTS
    else (
        "this box's /bin/sh does not expand backslash escapes in echo's "
        "argument (not dash) -- the D1 corruption class does not reproduce "
        "here; see docs/analysis/2026-08-07-k3a-root-activation-evidence-"
        "report.md Section 4.1"
    )
)

_skip_unless_dash_reproducible = pytest.mark.skipif(
    not _DASH_CLASS_REPRODUCIBLE, reason=_SKIP_REASON
)
_skip_unless_sh_exists = pytest.mark.skipif(
    not _SH_EXISTS,
    reason="no /bin/sh on this platform -- cannot drive the guard through it",
)


# ---------------------------------------------------------------------------
# Shared subprocess plumbing
# ---------------------------------------------------------------------------


def _hook_pythonpath() -> str:
    """`PYTHONPATH` covering both `des.*` (under `src/`) and `scripts.*`."""
    return str(_REPO_ROOT / "src") + os.pathsep + str(_REPO_ROOT)


def _activate_project(root: Path) -> None:
    """Write the `.nwave/local-config.json` marker the activation gate reads.

    `hook_router.main()` gates every dispatch on `activation_gate.apply_gate`
    (ADR-AG-001): an unactivated project exits 0 before `handle_pre_write`
    ever runs, which would masquerade as the D1 defect without being it
    (evidence report Section 3, "B-1"). This activates the isolated
    `tmp_path` project so the ONLY thing under test is D1's JSON corruption.
    """
    nwave_dir = root / ".nwave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    (nwave_dir / "local-config.json").write_text(
        json.dumps({"enabled_for_repo": True}), encoding="utf-8"
    )


def _run_installed_write_guard(
    payload: str, cwd: Path
) -> subprocess.CompletedProcess[str]:
    """Run `build_guard_command` wrapping the REAL installed pre-write handler.

    Mirrors the production installer/plugin call shape (`des_plugin.py`
    `_installer_guard_command`): `build_guard_command(python_cmd)` where
    `python_cmd` invokes `claude_code_hook_adapter` with the action appended.
    """
    python_cmd = (
        f"{sys.executable} -m "
        "des.adapters.drivers.hooks.claude_code_hook_adapter pre-write"
    )
    guard_cmd = build_guard_command(python_cmd)
    env = dict(os.environ)
    env["PYTHONPATH"] = _hook_pythonpath() + os.pathsep + env.get("PYTHONPATH", "")
    env["NWAVE_FRESHNESS"] = "skip"
    # `tests/conftest.py`'s autouse `_isolate_nwave_root` fixture has already
    # set DES_PROJECT_DIR to ITS OWN per-test tmp root, and
    # `resolve_nwave_root()` prefers that env var over cwd by design
    # (DDD-14). Without this override the subprocess resolves `.nwave` under
    # the fixture's root, never under `cwd` -- where `_activate_project`
    # wrote `local-config.json` -- and the activation gate reads "not
    # activated" regardless of what this test actually set up. Same pattern
    # as `tests/des/acceptance/test_hook_protocol_conformance.py`.
    env["DES_PROJECT_DIR"] = str(cwd)
    return subprocess.run(
        ["/bin/sh", "-c", guard_cmd],
        input=payload,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


_ROOT_REMINDER_MARKER = "nw-mode-select available"


def _python_hook_was_invoked(root: Path) -> bool:
    """True iff `.nwave/des/logs/*.log` under `root` carries a HOOK_INVOKED
    event -- the positive witness that the Python handler actually ran.

    Distinguishes "looked and confirmed absent" from "never looked" (the
    SILENCE/ABSENCE closure obligation, `nw-test-design-mandates`): a
    reminder's ABSENCE from stdout is produced by two structurally
    different mechanisms in this codebase -- the shell-level fast-path grep
    filtering the write out before Python ever runs, or Python running and
    `is_nwave_adjacent_write` correctly excluding it. Both look identical
    from stdout alone.
    """
    log_dir = root / ".nwave" / "des" / "logs"
    if not log_dir.is_dir():
        return False
    return any(
        '"HOOK_INVOKED"' in log_file.read_text(encoding="utf-8")
        for log_file in log_dir.glob("*.log")
    )


# ---------------------------------------------------------------------------
# Case 1 -- build_guard_command must preserve the hook JSON byte-for-byte.
# ---------------------------------------------------------------------------


_CAPTURE_STDIN_SCRIPT = textwrap.dedent(
    """\
    import sys, pathlib
    pathlib.Path(sys.argv[1]).write_bytes(sys.stdin.buffer.read())
    """
)


def _capture_bytes_through_build_guard_command(
    payload: bytes, cwd: Path
) -> tuple[subprocess.CompletedProcess[bytes], Path]:
    """Run `build_guard_command` wrapping a byte-capture script.

    A capture script stands in for the downstream command (the real
    `claude_code_hook_adapter`, or any of the three `_BASH_*` guards' own
    inner `python3 -c` extraction) so the assertion can be on the bytes that
    actually crossed the pipe -- not on an exit code, since `handle_pre_write`
    fails OPEN and returns 0 whether the JSON survived or not (dispatch
    intent: "assert on the bytes the handler receives, not on the exit
    code"). Returns the completed process and the path the downstream
    command wrote to (exists only if the guard's own fast-path grep matched
    and reached it).
    """
    capture_script = cwd / "capture_stdin.py"
    capture_script.write_text(_CAPTURE_STDIN_SCRIPT, encoding="utf-8")
    capture_file = cwd / "captured.bin"

    python_cmd = f"{sys.executable} {capture_script} {capture_file}"
    guard_cmd = build_guard_command(python_cmd)

    result = subprocess.run(
        ["/bin/sh", "-c", guard_cmd],
        input=payload,
        cwd=cwd,
        capture_output=True,
        timeout=15,
    )
    return result, capture_file


# --- Property-test domain (nw-algebraic-design-protocol frame) -------------
#
# OBSERVATION. Given any hook envelope E -- JSON bytes built from `tool_name`
# + `tool_input` whose string fields carry arbitrary content -- run E through
# `build_guard_command`'s shell pipeline and observe what the downstream
# consumer receives on stdin: `capture(E)`.
#
# EQUALITY under this observation: `E ~ capture(E)` iff
# `capture(E).rstrip(b"\n") == E` -- byte-identity, modulo the single
# trailing newline `echo`/`printf` always appends. That rstrip is the ONE
# thing this observation deliberately cannot distinguish (a harmless shell
# artefact orthogonal to D1); every other byte difference must be visible.
#
# LAW (the property under test): `build_guard_command` is the IDENTITY on
# the payload -- `E ~ capture(E)` for every legal envelope E. Team-lead
# review (2026-08-07): an example-based test pinned to `\n` covers exactly
# ONE inhabitant of an unbounded domain. dash's builtin `echo` also expands
# `\t \r \" \\ \a \b \f \v \0NNN(octal)` and `\c` -- and `\c` is the most
# interesting inhabitant, because it TRUNCATES the rest of the argument
# rather than corrupting one character: a payload whose `old_string` carries
# a literal backslash-c (a LaTeX command, a Windows path, a regex
# control-char escape -- all realistic file content) would be silently cut
# in half. `\\` (a literal backslash in the source, which JSON encodes as
# `\\`) is the worst shape of all: it COLLAPSES two characters into one, so
# the wire JSON stays PARSEABLE while carrying different content -- valid
# output, wrong data, and no exception anywhere to notice it.
#
# PUBLIC SURFACE + REACHABILITY. `old_string`/`new_string` are arbitrary
# Python `str` -- the real, unbounded domain (any Unicode text a file's
# content can hold, restricted to what `codec="utf-8"` can actually encode:
# a lone UTF-16 surrogate is a legal Python `str` character but never
# occurs in well-formed UTF-8 file content, so it is excluded as an
# impossible inhabitant, not tolerated as a real one -- caught live while
# authoring this module: `st.text()` unrestricted generated `'\ud800'` and
# `.encode("utf-8")` raised `UnicodeEncodeError` in the test HARNESS itself,
# a minimized impossible case that is evidence to audit the generator, not
# the guard, per `nw-algebraic-design-protocol` §4) -- serialized by
# `json.dumps` (`ensure_ascii=True`, Python's default and what a real Claude
# Code envelope's encoder uses), never hand-escaped, so every generated
# envelope is legal by construction and shrinking cannot manufacture an
# illegal one. `ensure_ascii=True` means
# the WIRE bytes are always 7-bit ASCII -- every codepoint above 0x7E
# becomes a `\uXXXX` escape -- which is exactly where dash's XSI escape
# table lives; a broad `st.text()` alone would almost NEVER land a raw
# backslash immediately followed by one of dash's escape letters (the space
# is enormous, the dangerous substrings a sliver of it), so a purely random
# generator would report false confidence. The strategy below therefore
# MIXES (a) unrestricted `st.text()` -- proving the law generally and open
# to discovering an inhabitant nobody named -- with (b) a curated set of the
# concrete characters/substrings `json.dumps` is KNOWN to produce and dash's
# XSI table is KNOWN to misinterpret (verified empirically against this
# box's `/bin/sh`, not assumed), guaranteeing those specific inhabitants are
# actually reached every run rather than left to chance.
_JSON_NATIVE_ESCAPE_CHARS = ("\n", "\t", "\r", '"', "\\", "\x08", "\x0c", "\x00")
# json.dumps' OWN single-character escapes (\n \t \r \" \\ \b \f) plus NUL
# (-> \u0000) -- each reached purely by encoding a real control character,
# never by hand-escaping.
_DASH_XSI_LITERAL_FRAGMENTS = (
    "\\",  # bare backslash -> JSON `\\` (the collapse: valid JSON, wrong data)
    "\\c",  # backslash + 'c' -> JSON `\\c` (dash's TRUNCATING escape)
    "\\0",  # backslash + '0' -> JSON `\\0` (start of an octal escape)
    "\\0177",  # backslash + octal digits -> JSON `\\0177`
    "\\a",  # backslash + 'a' -> JSON `\\a` (dash: BEL)
    "\\b",  # backslash + 'b' -> JSON `\\\\b` (dash: backspace; distinct from
    # json.dumps' OWN native `\b` above, which arrives via a real 0x08 char)
    "\\f",  # backslash + 'f' -> JSON `\\\\f` (dash: formfeed; ditto vs native `\f`)
    "\\v",  # backslash + 'v' -> JSON `\\v` (dash: vertical tab)
)
# Realistic SOURCE substrings (a literal backslash followed by an
# XSI-meaningful letter/digit) as they appear in real file content -- LaTeX
# commands, Windows paths, regex word-boundaries, octal escapes in C/shell
# snippets. json.dumps DOUBLES the leading backslash of each, exactly the
# shape a multi-line Edit riddled with code/regex snippets carries on the
# wire.
_curated_fragment = st.one_of(
    st.sampled_from(_JSON_NATIVE_ESCAPE_CHARS),
    st.sampled_from(_DASH_XSI_LITERAL_FRAGMENTS),
)
_ordinary_ascii_fragment = st.text(
    alphabet=st.characters(
        min_codepoint=0x20, max_codepoint=0x7E, exclude_characters='\\"'
    ),
    max_size=8,
)
_broad_unicode_fragment = st.text(
    alphabet=st.characters(codec="utf-8"), max_size=8
)  # unrestricted except for `codec="utf-8"` (excludes lone surrogates --
# not a real inhabitant of file content, see the REACHABILITY note above) --
# the genuinely unbounded half of the domain; open to an inhabitant this
# module did not name.
_field_value = st.lists(
    st.one_of(_curated_fragment, _ordinary_ascii_fragment, _broad_unicode_fragment),
    min_size=1,
    max_size=6,
).map("".join)

_PROPERTY_MAX_EXAMPLES = 60


class TestBuildGuardCommandBytePreservation:
    """The guard's `echo "$INPUT" | <downstream>` pipe must be byte-preserving."""

    @_skip_unless_dash_reproducible
    def test_installed_guard_survives_escaped_json_under_posix_sh(
        self, tmp_path: Path
    ) -> None:
        """A Write/Edit envelope whose `old_string`/`new_string` carry an
        escaped newline (as every real Edit does) must reach the downstream
        command byte-identical. Fails at HEAD: dash's `echo "$INPUT"`
        expands the embedded `\\n` into a raw newline, corrupting the JSON
        mid-payload -- the captured bytes diverge from what was sent. Green
        once `build_guard_command` switches to `printf '%s' "$INPUT"`
        (verified remedy, evidence report Section 4.1). Concrete,
        documentation-shaped instance of the universal law the property test
        below covers."""
        payload = json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(tmp_path / "src" / "widget.py"),
                    "old_string": "def foo():\n    pass",
                    "new_string": "def foo():\n    return 1",
                },
            }
        ).encode("utf-8")

        result, capture_file = _capture_bytes_through_build_guard_command(
            payload, tmp_path
        )

        assert capture_file.exists(), (
            "the guard never reached the downstream command -- its own "
            f"fast-path grep did not match the file_path pattern; "
            f"exit={result.returncode} stderr={result.stderr!r}"
        )
        captured = capture_file.read_bytes()
        # `echo` (correctly or not) always appends exactly one trailing
        # newline; that shell artefact is orthogonal to D1 and is tolerated
        # here so the assertion isolates the escape-expansion defect, which
        # corrupts bytes IN THE MIDDLE of the payload, not just at the end.
        assert captured.rstrip(b"\n") == payload, (
            'the guard\'s `echo "$INPUT"` wrapper corrupted the JSON '
            "payload under /bin/sh (D1) -- captured bytes diverge from "
            f"what was sent.\n  sent:     {payload!r}\n  captured: {captured!r}"
        )

    @_skip_unless_dash_reproducible
    @given(old_string=_field_value, new_string=_field_value)
    @settings(max_examples=_PROPERTY_MAX_EXAMPLES, deadline=None)
    def test_build_guard_command_is_the_identity_on_the_payload(
        self, old_string: str, new_string: str
    ) -> None:
        """Universal law: `build_guard_command` is the identity on the
        payload -- for ANY hook envelope, the bytes the downstream consumer
        receives equal the bytes the hook was handed (see the module-level
        OBSERVATION / EQUALITY / LAW / REACHABILITY block above `_field_value`
        for the full algebraic frame). `old_string`/`new_string` mix (a)
        unrestricted `st.text()` -- the genuinely unbounded domain, open to
        an inhabitant nobody named -- with (b) a curated set of the concrete
        characters/substrings `json.dumps` is known to produce and dash's
        XSI `echo` table is known to misinterpret (`\\n \\t \\r \\" \\\\
        \\a \\b \\f \\v \\0NNN \\c`), so the specific dangerous inhabitants
        are reached every run rather than left to chance. Every fragment is
        a real Python character/substring, serialized by `json.dumps` --
        never hand-escaped -- so every generated payload is a legal envelope
        by construction and shrinking cannot manufacture an illegal one.
        Asserts BYTE equality, never mere parseability: `json.loads`
        succeeding proves nothing for the `\\\\` collapse case (valid JSON,
        wrong content -- the worst failure shape, since nothing signals it).
        A dedicated temp dir per example (not the `tmp_path` fixture) keeps
        each Hypothesis example fully isolated."""
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            payload = json.dumps(
                {
                    "tool_name": "Edit",
                    "tool_input": {
                        "file_path": str(tmp_path / "src" / "widget.py"),
                        "old_string": old_string,
                        "new_string": new_string,
                    },
                }
            ).encode("utf-8")

            result, capture_file = _capture_bytes_through_build_guard_command(
                payload, tmp_path
            )

            assert capture_file.exists(), (
                "the guard never reached the downstream command for a "
                f"generated payload; exit={result.returncode} "
                f"stderr={result.stderr!r} payload={payload!r}"
            )
            captured = capture_file.read_bytes()
            assert captured.rstrip(b"\n") == payload, (
                "guard is not the identity on this generated payload -- "
                f"sent {payload!r}, captured {captured!r}"
            )


# ---------------------------------------------------------------------------
# Case 2 + Case 4 -- the K3-A root-activation reminder on the pre-write path.
# ---------------------------------------------------------------------------


class TestRootActivationReminderThroughPosixSh:
    """The pre-write path's K3-A reminder must survive the real /bin/sh guard."""

    @_skip_unless_dash_reproducible
    def test_root_activation_reminder_reaches_stdout_for_nwave_adjacent_write(
        self, tmp_path: Path
    ) -> None:
        """Case 2 -- an nWave-adjacent Write/Edit (escaped-newline old_string,
        as every real Edit carries) must reach the root mode-selection gate.
        Corrupted JSON would make `handle_pre_write` fail open before that
        gate; the exact block response therefore witnesses byte preservation
        through the installed POSIX-sh guard."""
        _activate_project(tmp_path)
        target = tmp_path / "src" / "widget.py"
        payload = json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target),
                    "old_string": "def foo():\n    pass",
                    "new_string": "def foo():\n    return 1",
                },
            }
        )

        result = _run_installed_write_guard(payload, tmp_path)

        assert result.returncode == 2
        assert json.loads(result.stdout) == {
            "decision": "block",
            "reason": "Invoke nw-mode-select before the first mutation.",
        }, (
            "the root mode-selection gate never reached stdout for an "
            f"nWave-adjacent write -- exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr[-2000:]!r}"
        )

    @_skip_unless_sh_exists
    @pytest.mark.parametrize(
        "relative_path,expect_python_invoked",
        (
            (".nwave/telemetry/probe.jsonl", False),
            ("tests/.nwave/fixture.json", True),
        ),
        ids=("dot-nwave-root", "tests-dot-nwave"),
    )
    def test_no_root_activation_reminder_for_nwave_bookkeeping_paths(
        self, tmp_path: Path, relative_path: str, expect_python_invoked: bool
    ) -> None:
        """Case 4 -- sibling-branch pin (Critical Rules: pin the correct
        behaviour of neighbouring branches). Fixing D1's JSON corruption must
        NOT start emitting the root-activation reminder for `.nwave/**` /
        `tests/.nwave/**` bookkeeping writes -- `is_nwave_adjacent_write`'s
        own exclusion must keep them silent. This holds BOTH before and
        after the D1 fix; it guards against the fix accidentally widening
        the reminder's scope while it repairs the JSON-survival path.

        Team-lead review (2026-08-07): the absence assertion alone cannot
        tell WHICH of two structurally different mechanisms produced the
        silence. `.nwave/telemetry/**` never matches `build_guard_command`'s
        own shell-level fast-path grep (`/src/|/nWave/|/tests/|/scripts/`),
        so Python NEVER RUNS. `tests/.nwave/fixture.json` DOES match that
        grep (it contains `/tests/`), reaches Python, and it is
        `is_nwave_adjacent_write`'s `.nwave`-segment exclusion that keeps it
        silent. Asserting the mechanism per branch (`_python_hook_was_invoked`
        -- a HOOK_INVOKED audit-event witness) makes a future change that
        collapses BOTH branches onto the same mechanism -- or swaps which
        one filters which path -- visible, instead of silently absorbed
        into "still passes"."""
        _activate_project(tmp_path)
        target = tmp_path / relative_path
        payload = json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {
                    "file_path": str(target),
                    "old_string": "old",
                    "new_string": "new",
                },
            }
        )

        result = _run_installed_write_guard(payload, tmp_path)

        assert _ROOT_REMINDER_MARKER not in result.stdout, (
            f"reminder leaked for bookkeeping path {relative_path!r}: "
            f"stdout={result.stdout!r}"
        )
        actual_invoked = _python_hook_was_invoked(tmp_path)
        assert actual_invoked == expect_python_invoked, (
            f"silence for {relative_path!r} came from the WRONG mechanism -- "
            f"expected python_invoked={expect_python_invoked} (shell "
            "fast-path filter vs Python's own is_nwave_adjacent_write "
            f"exclusion), observed {actual_invoked}. A mechanism swap "
            "changes nothing about the reminder's absence but IS a real "
            "regression this discriminator exists to catch."
        )


# ---------------------------------------------------------------------------
# Case 3 -- each _BASH_* guard's shared CMD-extraction prefix.
# ---------------------------------------------------------------------------

# The literal reason text `_BASH_EXECUTION_LOG_GUARD` prints on its OWN
# block decision (see `scripts/shared/hook_definitions.py`,
# `_BASH_EXECUTION_LOG_GUARD`'s trailing `printf '%s\n' '{"decision":...}'`)
# -- copied here so the test below can assert byte-EXACT equality, not mere
# parseability (team-lead review, 2026-08-07: `json.loads` succeeding proves
# nothing for a `\\`-collapse-shaped corruption that leaves valid JSON with
# different content).
_EXECUTION_LOG_BLOCK_REASON = (
    "Direct modification of execution-log.json via Bash is blocked.\n"
    "To read it, use the Read tool.\n"
    "This retired artifact must not be recreated or modified."
)


# --- Property-test domain: the shared CMD-extraction pipe ------------------
#
# Team-lead review (2026-08-07): the three `_BASH_*` guards below are pinned
# by ONE example each against the identical `INPUT=$(cat); CMD=$(printf
# '%s' "$INPUT" | python3 -c '...json.load...')` prefix -- the same identity
# law generalized above for `build_guard_command`, left ungeneralized here.
# Generalize it ONCE, over the shared pipe, parametrized across the three
# guards it is sliced from -- three separate property tests would be
# duplication pretending to be coverage, since it is the same law.
#
# OBSERVATION. Given any `tool_input.command` string, run the shared
# extraction prefix -- SLICED verbatim out of a REAL `_BASH_*` constant,
# never hand-copied -- through `/bin/sh` and observe `$CMD`.
#
# EQUALITY: `command ~ CMD` iff `CMD == command.rstrip("\n")`. Command
# substitution `$(...)` itself strips ALL trailing newlines from its own
# captured output -- a universal POSIX shell property, unrelated to D1 --
# and that is the ONE thing this observation deliberately cannot
# distinguish; embedded/internal newlines are untouched by that stripping
# and must survive exactly.
#
# REACHABILITY. Reuses `_field_value`'s domain (curated dash-XSI
# inhabitants + unrestricted `st.text()`) minus NUL: `$CMD` is captured into
# a real shell VARIABLE here (unlike `build_guard_command`'s `$INPUT`, which
# is only ever piped as a raw byte stream to a script reading `stdin.buffer`
# directly) and a POSIX shell variable cannot hold an embedded NUL byte at
# all -- a universal C-string limitation of every `sh`, independent of D1.
_GUARDS_SHARING_CMD_EXTRACTION: dict[str, str] = {
    "execution_log": _BASH_EXECUTION_LOG_GUARD,
    "git_stash": _BASH_GIT_STASH_GUARD,
    "worktree_removal": _BASH_WORKTREE_REMOVAL_GUARD,
}

# The prefix starts right after the (per-guard, differing) `# des-hook:...`
# marker comment, and ends right after the CMD assignment's closing `); `.
_CMD_EXTRACTION_HEAD_MARKER = "INPUT=$(cat); "
_CMD_EXTRACTION_TAIL_MARKER = ".get('tool_input',{}).get('command',''))\"); "


def _cmd_extraction_prefix(guard_source: str) -> str:
    """Slice the shared CMD-extraction prefix out of a REAL guard constant.

    Never hand-copied: this drives the actual production text, so a future
    edit to the extraction pipe is exercised automatically, not silently
    left uncovered by a stale hand-written copy.
    """
    start = guard_source.index(_CMD_EXTRACTION_HEAD_MARKER)
    end = guard_source.index(_CMD_EXTRACTION_TAIL_MARKER) + len(
        _CMD_EXTRACTION_TAIL_MARKER
    )
    return guard_source[start:end]


_command_field_value = st.lists(
    st.one_of(
        st.sampled_from(tuple(c for c in _JSON_NATIVE_ESCAPE_CHARS if c != "\x00")),
        st.sampled_from(_DASH_XSI_LITERAL_FRAGMENTS),
        _ordinary_ascii_fragment,
        # `codec="utf-8"` excludes lone surrogates (not a real inhabitant of
        # file content -- see the REACHABILITY note above `_field_value`);
        # `exclude_characters="\x00"` excludes NUL, which a POSIX shell
        # variable cannot hold at all (see the module comment above).
        st.text(
            alphabet=st.characters(codec="utf-8", exclude_characters="\x00"),
            max_size=8,
        ),
    ),
    min_size=1,
    max_size=6,
).map("".join)


class TestBashGuardsExtractCommandDespiteEscapedNewline:
    """Each `_BASH_*` guard shares the `CMD=$(echo "$INPUT" | python3 -c
    '...json.load...')` extraction prefix. Under dash, an escaped newline
    anywhere in `tool_input.command` (a real multi-line Bash invocation, as
    Claude Code routinely issues) corrupts the JSON the extraction parses,
    `CMD` comes back empty, and the guard's own `grep ... || exit 0`
    fast-path silently disarms it -- the downstream Python guard never runs.
    """

    @_skip_unless_dash_reproducible
    def test_execution_log_guard_blocks_despite_escaped_newline_in_command(
        self,
    ) -> None:
        """A command touching execution-log.json, with an escaped newline
        elsewhere in the same string, must still be BLOCKED (exit 2). Fails
        at HEAD: CMD extraction corrupts, comes back empty, `grep -q
        'execution-log' || exit 0` fires -- silent disarm (exit 0, no
        block)."""
        command = "python3 -c \"import json\nprint('reading execution-log.json')\""
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})

        result = subprocess.run(
            ["/bin/sh", "-c", _BASH_EXECUTION_LOG_GUARD],
            input=payload,
            capture_output=True,
            text=True,
            timeout=15,
        )

        assert result.returncode == 2, (
            "guard should block a command touching execution-log.json even "
            "when the JSON carries an escaped newline elsewhere; "
            f"exit={result.returncode} stdout={result.stdout!r}"
        )
        assert json.loads(result.stdout)["decision"] == "block"

    @_skip_unless_dash_reproducible
    def test_execution_log_guard_own_block_message_parses_with_clean_command(
        self,
    ) -> None:
        """Distinct from the CMD-extraction defect above: `_BASH_EXECUTION_LOG_GUARD`
        carries its OWN static block-decision string with a literal `\\n`
        baked into its `reason` text (a JSON newline escape) -- independent
        of anything the incoming command carries. Even a perfectly CLEAN
        command (no escapes anywhere in the envelope) must still yield a
        block body BYTE-EXACT to the known reason text -- not merely
        parseable. Team-lead review (2026-08-07): `json.loads` succeeding
        proves nothing for a `\\\\`-collapse-shaped corruption that leaves
        valid JSON with DIFFERENT content, which is the exact class this
        module's own property test (`test_build_guard_command_is_the_...`)
        exists to catch elsewhere; a parseability-only check here would
        carry the identical blind spot. Fails at HEAD (pre-D1-fix
        reconstruction): dash's `echo` expands the guard's own hardcoded
        `\\n`s when it prints `echo '{"decision":"block","reason":"...
        blocked.\\nTo read it..."}'`, so the block correctly triggers
        (exit 2) but the JSON it prints is invalid -- Claude Code would
        receive a malformed block body. This is the site the crafter found
        unprompted during A_GREEN and confirmed byte-for-byte; this test is
        its dedicated regression lock, isolated from the CMD-extraction
        case above so a future regression here cannot hide behind that
        other test's escaped input."""
        command = "cat execution-log.json"  # no escapes anywhere in the
        # envelope -- isolates the guard's OWN literal-echo corruption from
        # the CMD-extraction corruption the sibling test above covers.
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})

        result = subprocess.run(
            ["/bin/sh", "-c", _BASH_EXECUTION_LOG_GUARD],
            input=payload,
            capture_output=True,
            text=True,
            timeout=15,
        )

        assert result.returncode == 2, (
            "guard should block a clean execution-log.json-touching command; "
            f"exit={result.returncode} stdout={result.stdout!r}"
        )
        try:
            body = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(
                "the guard's OWN block-decision message is not valid JSON "
                f"under /bin/sh -- {exc}; raw stdout={result.stdout!r}"
            )
        assert body == {"decision": "block", "reason": _EXECUTION_LOG_BLOCK_REASON}, (
            "the guard's OWN block-decision body is not byte-exact to the "
            "known reason text -- valid JSON, but possibly WRONG content "
            f"(the `\\\\`-collapse failure shape); got {body!r}, expected "
            f"reason={_EXECUTION_LOG_BLOCK_REASON!r}"
        )

    @_skip_unless_dash_reproducible
    def test_git_stash_guard_blocks_despite_escaped_newline_in_command(
        self,
    ) -> None:
        """A mutating `git stash push` command, with an escaped newline in
        its `-m` message (a real multi-line stash message), must still be
        BLOCKED. Fails at HEAD: same CMD-extraction corruption -- CMD is
        empty, `grep -qE '^\\s*git\\s+stash\\b' || exit 0` fires, and
        `scripts.hooks.git_stash_guard` never runs."""
        command = 'git stash push -u -m "first line\nsecond line"'
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        env = dict(os.environ)
        env["PYTHONPATH"] = _hook_pythonpath() + os.pathsep + env.get("PYTHONPATH", "")

        result = subprocess.run(
            ["/bin/sh", "-c", _BASH_GIT_STASH_GUARD],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )

        assert result.returncode == 2, (
            "guard should block a mutating git-stash command even when the "
            f"JSON carries an escaped newline; exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr[-2000:]!r}"
        )
        assert "git worktree add" in result.stdout

    @_skip_unless_dash_reproducible
    def test_worktree_removal_guard_extracts_command_despite_escaped_newline(
        self, tmp_path: Path
    ) -> None:
        """A `git worktree remove` command riding alongside a second line (a
        real multi-line Bash invocation, escaped as `\\n` in the hook JSON)
        must still reach `scripts.hooks.worktree_removal_guard` so its
        human-authorised bypass records an audit event. Fails at HEAD: CMD
        extraction corrupts, CMD is empty, the guard's own
        `grep -qE 'git\\s+worktree\\s+remove' || exit 0` fires -- zero audit
        events, a silent disarm (exit code alone cannot distinguish this: the
        bypass path also exits 0, so the audit-log side effect is the
        discriminating observable, mirroring the git-stash guard's own
        established AT pattern)."""
        target_path = tmp_path / "lane-to-remove"
        command = f"git worktree remove {target_path}\necho cleanup-done"
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        env = dict(os.environ)
        env["PYTHONPATH"] = _hook_pythonpath() + os.pathsep + env.get("PYTHONPATH", "")
        env["NWAVE_WORKTREE_GUARD_TARGET_ROOT"] = str(tmp_path)
        env["NWAVE_WORKTREE_REMOVE_REASON"] = (
            "k3a regression test confirms this lane is dead"
        )

        subprocess.run(
            ["/bin/sh", "-c", _BASH_WORKTREE_REMOVAL_GUARD],
            input=payload,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        audit_log = tmp_path / ".nwave" / "des" / "logs" / f"audit-{today}.log"
        assert audit_log.exists(), (
            "scripts.hooks.worktree_removal_guard never ran (no audit log "
            "written) -- the shell CMD-extraction prefix silently disarmed "
            f"on the escaped newline; command sent: {command!r}"
        )
        events = [
            json.loads(line)
            for line in audit_log.read_text().splitlines()
            if line.strip()
        ]
        assert any(
            event.get("event") == "WorktreeRemovalBypassUsed"
            and str(target_path) in event.get("command", "")
            for event in events
        ), (
            f"no WorktreeRemovalBypassUsed event recorded for {target_path}; events={events}"
        )

    def test_all_three_bash_guards_share_the_identical_cmd_extraction_prefix(
        self,
    ) -> None:
        """The three `_BASH_*` guards are not three independent implementations
        of CMD-extraction that happen to look alike -- production defines it
        ONCE and repeats the literal text. This is the structural fact the
        property test below generalizes over: if the prefixes ever diverge
        (someone edits one guard's extraction differently from its
        siblings), the shared-pipe property test would silently start
        covering only ONE of three real pipes while its name still claims
        all three."""
        prefixes = {
            name: _cmd_extraction_prefix(source)
            for name, source in _GUARDS_SHARING_CMD_EXTRACTION.items()
        }
        distinct = set(prefixes.values())
        assert len(distinct) == 1, (
            "the three _BASH_* guards' CMD-extraction prefixes have DIVERGED "
            "-- the shared-pipe property test no longer covers all three "
            f"guards with one law; prefixes={prefixes!r}"
        )

    @_skip_unless_dash_reproducible
    @pytest.mark.parametrize("guard_name", sorted(_GUARDS_SHARING_CMD_EXTRACTION))
    @given(command=_command_field_value)
    @settings(max_examples=_PROPERTY_MAX_EXAMPLES, deadline=None)
    def test_cmd_extraction_is_the_identity_on_tool_input_command(
        self, guard_name: str, command: str
    ) -> None:
        """Universal law, generalized ONCE over the shared pipe and
        parametrized across the three guards it is sliced from -- not three
        copies of the same property (team-lead review, 2026-08-07): `CMD`
        extracted by `INPUT=$(cat); CMD=$(printf '%s' "$INPUT" | python3 -c
        '...json.load...')` equals `tool_input.command`, modulo the one
        thing `$(...)` itself strips (trailing newlines -- a universal
        POSIX shell property, not D1). `command` mixes the same curated
        dash-XSI inhabitants and unrestricted `st.text()` as the Write/Edit
        property above, minus NUL (a POSIX shell variable cannot hold an
        embedded NUL byte at all -- not a D1 concern; see the module
        comment above `_command_field_value`). The prefix is sliced from the
        REAL `_BASH_*` constant (`_cmd_extraction_prefix`), never
        hand-copied, so this drives production text, not a
        reimplementation of it. Runs `subprocess` in BYTE mode, never
        `text=True`: Python's universal-newlines translation collapses
        `\r`/`\r\n`/`\n` all into `\n` on the way back, which would have
        masked exactly the kind of byte-level defect this property exists
        to catch -- caught against this test itself while authoring it
        (`command='\\r'` spuriously read back as `'\\n'`), the same class
        of "the harness lied" this whole module is built to avoid."""
        guard_source = _GUARDS_SHARING_CMD_EXTRACTION[guard_name]
        probe = _cmd_extraction_prefix(guard_source) + "printf '%s' \"$CMD\""
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": command}}
        ).encode("utf-8")

        result = subprocess.run(
            ["/bin/sh", "-c", probe],
            input=payload,
            capture_output=True,
            timeout=15,
        )

        expected = command.rstrip("\n").encode("utf-8")
        assert result.stdout == expected, (
            "CMD-extraction is not the identity on tool_input.command for "
            f"guard {guard_name!r} -- sent {command!r}, extracted "
            f"{result.stdout!r} (exit={result.returncode} "
            f"stderr={result.stderr!r})"
        )
