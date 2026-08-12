"""D1 regression -- dash's builtin `echo` corrupts hook JSON under `/bin/sh`.

k3a-hook-payload-dash-safety, slice-01. Evidence:
`docs/analysis/2026-08-07-k3a-root-activation-evidence-report.md` Section 4.1.

`scripts.shared.hook_definitions.build_guard_command` and the two `_BASH_*`
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
never emitted. The two `_BASH_*` guards share the identical
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
decision), never on a setup exception. `test_git_stash_guard_...` and
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
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.shared.hook_definitions import build_guard_command


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
        below covers. Root-write-boundary slice: the guard's own fast-path
        pre-filter is now a `.nwave/local-config.json` EXISTENCE check
        (content- and path-blind), not a `file_path` regex -- `_activate_project`
        creates that candidate marker so the guard reaches the downstream
        command at all."""
        _activate_project(tmp_path)
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
            f"fast-path existence check did not find the candidate marker; "
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
        each Hypothesis example fully isolated. Each example activates its
        own temp dir (`_activate_project`) so the guard's `.nwave/local-
        config.json` existence pre-filter reaches the downstream command --
        the property is about payload identity, not about activation."""
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp_path = Path(raw_tmp)
            _activate_project(tmp_path)
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
# Root-write-boundary slice -- the shell candidate-existence pre-filter
# itself (falsifiers E/F/G): whether the guard invokes the downstream
# command at all, proven with the same byte-capture sentinel as Case 1
# above, never by inspecting stdout/exit-code prose that a differently-wired
# guard could coincidentally reproduce.
# ---------------------------------------------------------------------------


class TestGuardCandidateExistenceGate:
    """The shell fast-path's ONLY pre-filter left is `.nwave/local-config.json`
    EXISTENCE -- content-blind, path-blind. These pin that the downstream
    command is/isn't reached purely on that file's presence."""

    @_skip_unless_sh_exists
    def test_no_marker_ordinary_path_never_invokes_downstream_command(
        self, tmp_path: Path
    ) -> None:
        """Falsifier E: an unactivated project (no `.nwave/local-config.json`
        at all), no deliver session, ordinary path -- the shell must exit 0
        before ever spawning the downstream (Python) command. Proven via the
        byte-capture sentinel (`capture_file` absence), not via stdout/exit-
        code prose that a differently-wired guard could reproduce by luck."""
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(tmp_path / "src" / "widget.py")},
            }
        ).encode("utf-8")

        result, capture_file = _capture_bytes_through_build_guard_command(
            payload, tmp_path
        )

        assert result.returncode == 0
        assert not capture_file.exists(), (
            "the guard invoked the downstream command despite no "
            f".nwave/local-config.json candidate marker; stdout="
            f"{result.stdout!r} stderr={result.stderr!r}"
        )

    @_skip_unless_sh_exists
    def test_malformed_marker_still_invokes_downstream_command(
        self, tmp_path: Path
    ) -> None:
        """Falsifier G (shell half): a `.nwave/local-config.json` that exists
        but is NOT valid JSON still passes the shell's `test -f` -- the shell
        never parses the marker's content, so a malformed marker reaches
        Python exactly like a well-formed one. Only Python (`DESConfig`'s
        JSON load + `activation_gate`'s fail-open) may decide what a
        malformed marker means."""
        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir(parents=True, exist_ok=True)
        (nwave_dir / "local-config.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(tmp_path / "src" / "widget.py")},
            }
        ).encode("utf-8")

        result, capture_file = _capture_bytes_through_build_guard_command(
            payload, tmp_path
        )

        assert capture_file.exists(), (
            "the guard did not reach the downstream command for a malformed "
            f"but PRESENT marker; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )
        assert capture_file.read_bytes().rstrip(b"\n") == payload

    @_skip_unless_sh_exists
    def test_malformed_marker_reaches_python_and_fails_open_to_allow(
        self, tmp_path: Path
    ) -> None:
        """Falsifier G (Python half): driven through the REAL installed
        pre-write handler (not the sentinel), a malformed marker resolves
        `enabled_for_repo` to `None` (`DESConfig._load_json_file`'s
        malformed -> `{}` collapse) and falls through to the existing
        `activation_gate` opt-in default -- inactive, silent allow -- the
        existing fail-open-to-handler behaviour, never a shell-level bypass
        (the sentinel sibling test already proves Python IS reached)."""
        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir(parents=True, exist_ok=True)
        (nwave_dir / "local-config.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(tmp_path / "src" / "widget.py")},
            }
        )

        result = _run_installed_write_guard(payload, tmp_path)

        assert result.returncode == 0
        assert result.stdout.strip() == ""


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
            (".nwave/telemetry/probe.jsonl", True),
            ("tests/.nwave/fixture.json", True),
        ),
        ids=("dot-nwave-root", "tests-dot-nwave"),
    )
    def test_no_root_activation_reminder_for_nwave_bookkeeping_paths(
        self, tmp_path: Path, relative_path: str, expect_python_invoked: bool
    ) -> None:
        """Case 4 -- sibling-branch pin (Critical Rules: pin the correct
        behaviour of neighbouring branches). The root-write-boundary slice
        must NOT start emitting the root-activation reminder for `.nwave/**`
        / `tests/.nwave/**` bookkeeping writes -- `is_nwave_adjacent_write`'s
        own exclusion must keep them silent. It guards against the fix
        accidentally widening the reminder's scope while it repairs the
        JSON-survival path.

        Team-lead review (2026-08-07, amended for the root-write-boundary
        slice): the absence assertion alone cannot tell WHICH of two
        structurally different mechanisms produced the silence. The shell
        guard's own fast-path pre-filter is now a content-blind
        `.nwave/local-config.json` EXISTENCE check, not a `file_path` regex
        -- once a project carries that candidate marker (`_activate_project`
        below), EVERY Write/Edit reaches Python regardless of target path,
        including both `.nwave/**` cases here. It is exclusively
        `is_nwave_adjacent_write`'s `.nwave`-segment exclusion (inside
        Python) that keeps both silent now. Asserting the mechanism per
        branch (`_python_hook_was_invoked` -- a HOOK_INVOKED audit-event
        witness) makes a future change that collapses this onto a
        shell-level path filter again -- or otherwise swaps which layer
        excludes which path -- visible, instead of silently absorbed into
        "still passes"."""
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

    @_skip_unless_sh_exists
    def test_arbitrary_top_level_write_blocks_after_authentic_mode_select_and_nw_auto(
        self, tmp_path: Path
    ) -> None:
        """Falsifier B, end-to-end through the real installed `/bin/sh`
        guard: an active project's root Write/Edit under an ARBITRARY
        top-level directory (`hc/...`, no fixed-allowlist membership) still
        reaches Python (the shell's only filter is the candidate-marker
        existence check), and once the transcript carries an authentic
        `Skill(nw-mode-select)` followed by an authentic `Skill(nw-auto)`
        (both nested under a real assistant `message.content` entry, the
        actual Claude Code transcript shape), the write BLOCKS with the
        existing auto-root reason -- unchanged by this slice."""
        _activate_project(tmp_path)
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text(
            "\n".join(
                json.dumps(entry)
                for entry in [
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Skill",
                                    "input": {"skill": "nw-mode-select"},
                                }
                            ]
                        },
                    },
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Skill",
                                    "input": {"skill": "nw-auto"},
                                }
                            ]
                        },
                    },
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        target = tmp_path / "hc" / "generated_plan.py"
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(target)},
                "transcript_path": str(transcript),
            }
        )

        result = _run_installed_write_guard(payload, tmp_path)

        assert result.returncode == 2
        assert json.loads(result.stdout) == {
            "decision": "block",
            "reason": (
                "Auto root cannot author or repair role-owned artifacts or "
                "production directly -- dispatch the owning role instead."
            ),
        }, (
            "the auto-root gate never blocked an arbitrary top-level "
            f"(hc/...) write -- exit={result.returncode} "
            f"stdout={result.stdout!r} stderr={result.stderr[-2000:]!r}"
        )

    @_skip_unless_sh_exists
    @pytest.mark.parametrize(
        "agent_identity",
        [{"agent_id": "agent-123"}, {"agent_type": "general-purpose"}],
        ids=["agent_id", "agent_type"],
    )
    def test_subagent_write_stays_allowed_through_real_shell_guard(
        self, tmp_path: Path, agent_identity: dict[str, str]
    ) -> None:
        """Falsifier C, end-to-end: the SAME handler envelope, only carrying
        `agent_id` OR `agent_type`, remains allowed through the real
        installed `/bin/sh` guard -- a legitimate subagent write is never
        subject to the root-only mode-select/auto-root gates."""
        _activate_project(tmp_path)
        target = tmp_path / "hc" / "generated_plan.py"
        payload_dict = {
            "tool_name": "Write",
            "tool_input": {"file_path": str(target)},
        }
        payload_dict.update(agent_identity)
        payload = json.dumps(payload_dict)

        result = _run_installed_write_guard(payload, tmp_path)

        assert result.returncode == 0
        assert result.stdout.strip() == "" or (
            json.loads(result.stdout).get("decision") != "block"
        )

    @_skip_unless_sh_exists
    def test_enabled_for_repo_false_stays_silent_through_real_shell_guard(
        self, tmp_path: Path
    ) -> None:
        """Falsifier D, end-to-end: `enabled_for_repo=false` in the marker
        resolves inactive through `activation_gate.apply_gate` -- the write
        is silently allowed even though the shell DID invoke Python (the
        marker exists), and even for an nWave-adjacent target."""
        nwave_dir = tmp_path / ".nwave"
        nwave_dir.mkdir(parents=True, exist_ok=True)
        (nwave_dir / "local-config.json").write_text(
            json.dumps({"enabled_for_repo": False}), encoding="utf-8"
        )
        target = tmp_path / "src" / "widget.py"
        payload = json.dumps(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(target)},
            }
        )

        result = _run_installed_write_guard(payload, tmp_path)

        assert result.returncode == 0
        assert result.stdout.strip() == ""
