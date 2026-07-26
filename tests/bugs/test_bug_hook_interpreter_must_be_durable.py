"""Regression: the installer captures a non-durable interpreter path.

Reported defect (2026-07-24 incident): the installer resolves the Python
interpreter for persisted hook artifacts from ``sys.executable`` and guards
against exactly ONE known-bad shape (``"/.venv/" in path``). It never asks
the property that actually matters for a value written into a config file
consumed *later*: **will this path still be here when the hook fires?**

On 2026-07-24, ``sys.executable`` was ``/tmp/nwave-test-venv/bin/python3.12``
-- a venv created under ``tempfile.gettempdir()`` by a Windows-only smoke
test run directly against the real ``~/.claude/``. It does not contain
``.venv`` (no leading dot, and it is not preceded by a path separator right
before the token boundary the existing guard matches), so the guard let it
through untouched. All 11 wired hooks pointed at that path; when the temp
directory was reaped, every hook failed "not found", non-blocking, for
~53 minutes with zero surfaced signal.

Full analysis: docs/feature/fix-hook-interpreter-durability/rca.md

Authorised fix (this test defines its contract, not its implementation): a
shared durability predicate ``is_durable_interpreter_path(path: str) -> bool``
in ``scripts/shared/install_paths.py`` that rejects anything rooted under
``tempfile.gettempdir()``, consumed by all four write sites:

1. ``scripts/install/plugins/des_plugin.py`` ``DESPlugin._resolve_python_path``
   -- ``~/.claude/settings.json`` (Claude Code hooks)
2. ``scripts/install/attribution_utils.py`` ``_resolve_python_path``
   -- git ``prepare-commit-msg`` shim
3. ``scripts/shared/install_paths.py`` ``resolve_python_command_for_spawn``
   -- Copilot / Codex / OpenCode hook configs
4. ``scripts/install/install_des_hooks.py`` ``DESHookInstaller._add_des_hooks``
   -- ``~/.claude/settings.json`` (legacy hook path) -- has **no guard at
   all** today, not even the ``.venv`` check.

``is_durable_interpreter_path`` does not exist yet. Every assertion below is
driven through the four PUBLIC resolvers exactly as a real install exercises
them (monkeypatched ``sys.executable``, real string output), never by
importing the not-yet-created predicate directly and never by inspecting
source text.
"""

from __future__ import annotations

import stat
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.install.attribution_utils import (
    _resolve_python_path as attribution_resolve_python_path,
)
from scripts.install.install_des_hooks import DESHookInstaller
from scripts.install.plugins.des_plugin import DESPlugin
from scripts.shared.install_paths import resolve_python_command_for_spawn


# ---------------------------------------------------------------------------
# The four write sites (RCA docs/feature/fix-hook-interpreter-durability/
# rca.md §4). Each callable reproduces exactly what the real installer does
# with the currently-monkeypatched sys.executable, and returns the string
# that ends up persisted to disk.
# ---------------------------------------------------------------------------


def _install_des_hooks_command(tmp_path: Path) -> str:
    """Drive write site #4 -- the one with NO guard at all today."""
    installer = DESHookInstaller(config_dir=tmp_path)
    config: dict = {}
    installer._ensure_hooks_structure(config)
    installer._add_des_hooks(config)
    return config["hooks"]["PreToolUse"][0]["hooks"][0]["command"]


_SITES: dict[str, Callable[[Path], str]] = {
    "des_plugin.DESPlugin._resolve_python_path (settings.json hooks)": (
        lambda tmp_path: DESPlugin._resolve_python_path()
    ),
    "attribution_utils._resolve_python_path (git prepare-commit-msg shim)": (
        lambda tmp_path: attribution_resolve_python_path()
    ),
    "install_paths.resolve_python_command_for_spawn (copilot/codex/opencode)": (
        lambda tmp_path: resolve_python_command_for_spawn()
    ),
    "install_des_hooks.DESHookInstaller._add_des_hooks (NO guard today)": (
        _install_des_hooks_command
    ),
}


def _make_alive_temp_interpreter() -> tuple[tempfile.TemporaryDirectory, Path]:
    """Build a temp-rooted, genuinely EXISTING fake interpreter.

    Uses ``tempfile.TemporaryDirectory`` (not a hardcoded ``/tmp`` literal)
    so the resulting path is honestly rooted under ``tempfile.gettempdir()``
    on any platform -- exactly the property the fix must reject on. The file
    is written and made executable so it EXISTS at the moment it is
    captured, mirroring the 2026-07-24 incident precisely: the venv was
    alive when ``sys.executable`` resolved to it.
    """
    tmp_dir = tempfile.TemporaryDirectory(prefix="nwave-test-venv-")
    fake_python = Path(tmp_dir.name) / "bin" / "python3.12"
    fake_python.parent.mkdir(parents=True, exist_ok=True)
    fake_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)
    assert fake_python.exists(), "fixture bug: fake interpreter must exist"
    return tmp_dir, fake_python


# ===========================================================================
# 1. PRIMARY ORACLE -- the temporary location is rejected at every write site
# ===========================================================================


@pytest.mark.parametrize("site_name", list(_SITES))
def test_temp_rooted_interpreter_is_never_persisted(
    site_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PRIMARY ORACLE (RCA Branch A+B) -- the headline assertion of this file.

    ``/tmp/nwave-test-venv/bin/python3.12`` EXISTED when it was captured on
    2026-07-24 -- the venv was alive. A test built on "the recorded
    interpreter must exist" would have observed NOTHING on the day of the
    incident. Only rejecting anything rooted under ``tempfile.gettempdir()``
    (never hardcoded ``/tmp`` -- honest on any platform) catches it.

    Every one of the four write sites must independently honour this
    property. ``install_des_hooks`` has no guard whatsoever today, so its
    parametrized case is expected to fail hardest.
    """
    tmp_dir, fake_python = _make_alive_temp_interpreter()
    try:
        monkeypatch.setattr(sys, "executable", str(fake_python))
        persisted = _SITES[site_name](tmp_path)
    finally:
        tmp_dir.cleanup()

    assert str(fake_python) not in persisted, (
        f"[{site_name}] embedded a temp-directory interpreter path into a "
        f"persisted artifact.\n"
        f"  Rejected path (existed at capture time): {fake_python}\n"
        f"  Persisted output:                        {persisted!r}\n"
        "This is the exact defect class from the 2026-07-24 incident: "
        "sys.executable pointed at a venv living under "
        "tempfile.gettempdir(), which gets reaped and silently takes every "
        "wired hook down with it (non-blocking failures, no surfaced "
        "signal). The guard must reject anything rooted under "
        "tempfile.gettempdir() -- not just paths containing '.venv'."
    )


# ===========================================================================
# 2. NEGATIVE EXAMPLES -- durable interpreters must be ACCEPTED, as-is
# ===========================================================================


def _pipx_venv(home: Path) -> str:
    return str(home / ".local" / "pipx" / "venvs" / "nwave-ai" / "bin" / "python3")


def _conda_env(home: Path) -> str:
    return str(home / "miniconda3" / "envs" / "nwave" / "bin" / "python3")


def _system_python(_home: Path) -> str:
    return "/usr/bin/python3"


def _uv_managed_python(home: Path) -> str:
    return str(
        home
        / ".local"
        / "share"
        / "uv"
        / "python"
        / "cpython-3.12.7-linux-x86_64-gnu"
        / "bin"
        / "python3"
    )


_DURABLE_EXAMPLES: list[tuple[str, Callable[[Path], str]]] = [
    ("pipx-venv", _pipx_venv),
    ("conda-env", _conda_env),
    ("system-python", _system_python),
    ("uv-managed-python", _uv_managed_python),
]


def _expected_home_substituted(raw: str, home: str) -> str:
    """Mirror the $HOME-portability substitution des_plugin/attribution do.

    Unrelated to durability: this is the pre-existing "make it portable
    across machines synced via ~/.claude" behaviour, applied AFTER the
    durability judgment accepts the path.
    """
    if raw.startswith(home):
        return "$HOME" + raw[len(home) :]
    return raw


@pytest.mark.parametrize(
    "case_id,build_path", _DURABLE_EXAMPLES, ids=[c[0] for c in _DURABLE_EXAMPLES]
)
def test_durable_interpreters_are_recorded_not_replaced(
    case_id: str,
    build_path: Callable[[Path], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NEGATIVE EXAMPLES -- mandatory, carrying EQUAL weight to the oracle.

    A guard that rejects the temp-dir shape and ALSO rejects legitimate
    durable interpreters is worthless: it degenerates into "always fall
    back to python3", which may lack DES's dependencies (RCA §5.3, a
    separate, real risk). pipx / conda / system / uv interpreters must
    survive the guard and be recorded with their real path, not silently
    downgraded to the fallback.
    """
    home = str(Path.home())
    raw = build_path(Path.home())
    monkeypatch.setattr(sys, "executable", raw)

    des_plugin_result = DESPlugin._resolve_python_path()
    attribution_result = attribution_resolve_python_path()
    spawn_result = resolve_python_command_for_spawn()

    expected_home_substituted = _expected_home_substituted(raw, home)

    assert des_plugin_result == expected_home_substituted, (
        f"[{case_id}] des_plugin.DESPlugin._resolve_python_path over-rejected "
        f"a durable interpreter.\n"
        f"  Given interpreter: {raw}\n"
        f"  Expected:          {expected_home_substituted}\n"
        f"  Got:               {des_plugin_result}\n"
        "Durability means 'is this rooted in a known-ephemeral location "
        "(tempfile.gettempdir())', not 'is this any venv-shaped path' -- "
        "this interpreter must be recorded, not replaced by the 'python3' "
        "fallback."
    )
    assert attribution_result == expected_home_substituted, (
        f"[{case_id}] attribution_utils._resolve_python_path over-rejected "
        f"a durable interpreter.\n"
        f"  Given interpreter: {raw}\n"
        f"  Expected:          {expected_home_substituted}\n"
        f"  Got:               {attribution_result}"
    )
    assert spawn_result == raw, (
        f"[{case_id}] install_paths.resolve_python_command_for_spawn "
        f"over-rejected a durable interpreter.\n"
        f"  Given interpreter: {raw}\n"
        f"  Expected (unchanged, no shell, no $HOME substitution): {raw}\n"
        f"  Got:               {spawn_result}"
    )


# ===========================================================================
# 3. PORTABILITY GUARD -- separate concern, unchanged by this fix
# ===========================================================================


def test_project_local_dot_venv_falls_back_for_portability_not_durability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PORTABILITY guard (RCA §3, item 3) -- pre-existing, separate, unchanged.

    A project-local ``.venv`` interpreter is replaced by ``python3`` because
    that exact path would not exist on a DIFFERENT machine (portability),
    not because a ``.venv`` is inherently ephemeral (durability). Under the
    fixed contract, ``is_durable_interpreter_path`` would answer True for
    THIS exact path -- a ``$HOME``-rooted ``.venv`` is durable, merely not
    portable. This test pins the PRE-EXISTING fallback-to-``python3``
    behaviour for ``.venv`` paths; it must keep passing unchanged after the
    durability fix lands, proving the two concerns were not folded together.
    """
    project_venv = Path.home() / "some-project" / ".venv" / "bin" / "python3"
    monkeypatch.setattr(sys, "executable", str(project_venv))

    assert DESPlugin._resolve_python_path() == "python3", (
        "des_plugin.DESPlugin._resolve_python_path must still fall back to "
        "'python3' for a project-local .venv interpreter -- this is the "
        "portability guard, not the durability guard, and must be "
        "preserved unchanged."
    )
    assert attribution_resolve_python_path() == "python3", (
        "attribution_utils._resolve_python_path must still fall back to "
        "'python3' for a project-local .venv interpreter."
    )
    assert resolve_python_command_for_spawn() == "python3", (
        "install_paths.resolve_python_command_for_spawn must still fall "
        "back to 'python3' for a project-local .venv interpreter."
    )


# ===========================================================================
# 4. Existence is defence-in-depth, labelled as such -- NOT the fix
# ===========================================================================


def test_existence_check_alone_would_not_have_caught_the_incident(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Existence-at-write-time is defence-in-depth for a DIFFERENT, narrower
    failure mode (RCA §3(a) precision note) -- this test does NOT validate
    the fix for the 2026-07-24 incident, it validates that existence
    checking is orthogonal to it.

    ``/tmp/nwave-test-venv/bin/python3.12`` EXISTED when it was captured;
    the venv was alive. A guard keyed ONLY on "does this path exist right
    now" would have observed a perfectly healthy path and said yes --
    exactly what happened in the real incident. This test proves an
    EXISTING, temp-rooted interpreter is still rejected: the
    temp-directory-root check is what catches it, existence has nothing to
    do with it. Existence checking covers a narrower, different failure
    mode (e.g. a path deleted or corrupted between resolution and use) and
    must never be sold as "the fix" for this defect.
    """
    tmp_dir, fake_python = _make_alive_temp_interpreter()
    try:
        assert fake_python.exists(), (
            "fixture invariant: interpreter is alive at capture time, "
            "exactly like the real 2026-07-24 incident"
        )
        monkeypatch.setattr(sys, "executable", str(fake_python))
        result = DESPlugin._resolve_python_path()
    finally:
        tmp_dir.cleanup()

    assert str(fake_python) not in result, (
        f"An EXISTING temp-rooted interpreter was still embedded in the "
        f"persisted output.\n"
        f"  Interpreter (existed at capture time): {fake_python}\n"
        f"  Persisted output:                      {result!r}\n"
        "Existence at write-time is NOT sufficient on its own -- the "
        "interpreter existed at capture time in the real incident too, "
        "which is exactly why an existence-only check would have missed "
        "it. Only rejecting paths rooted under tempfile.gettempdir() "
        "catches this class."
    )


# ===========================================================================
# 5. SYMLINK EVASION -- lexical prefix comparison is not enough
# (follow-up, 2026-07-24, post-fix implementation review)
# ===========================================================================


def test_interpreter_reaching_temp_dir_through_a_symlink_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path that reaches the temp directory THROUGH A SYMLINK must still
    be rejected -- lexical prefix comparison alone is not enough.

    The shipped guard compares ``path`` to ``tempfile.gettempdir()`` by
    LEXICAL prefix only (``Path(path).relative_to(Path(tempfile.gettempdir()))``),
    never resolving either side. A path that reaches the temp directory
    through a differently-named symlink is therefore judged durable even
    though it is, physically, inside the temp directory -- exactly the
    class this guard exists to reject.

    This is not an exotic case: on macOS the per-process ``$TMPDIR`` lives
    under ``/var/folders/...`` while ``/tmp`` is a SEPARATE path that is
    itself a symlink to ``/private/tmp``. An interpreter captured with the
    literal ``/tmp/...`` shape -- the exact shape of the 2026-07-24
    incident this file exists for -- resolves through that symlink into
    the real temp root and would escape a lexical-only comparison
    entirely. Both sides must be resolved before comparing, or the "honour
    any platform" property the primary-oracle test (§1) relies on does not
    actually hold on the platform where this bites hardest.

    The symlink, its target, and the fake interpreter are all built under
    ``tmp_path`` (self-cleaning, nothing written outside pytest's own
    scratch dir, no access to the real system temp dir or the user's
    home) -- ``tempfile.gettempdir()`` is monkeypatched to a
    ``tmp_path``-scoped fake temp root so the whole reproduction is
    self-contained and platform-independent.
    """
    fake_temp_root = tmp_path / "fake-temp-root"
    fake_temp_root.mkdir()
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_temp_root))

    # A differently-named directory that is NOT a lexical descendant of
    # fake_temp_root but RESOLVES into it -- the macOS /tmp -> real-temp
    # shape, reproduced portably without touching the real filesystem.
    alias_dir = tmp_path / "looks-durable-but-is-a-symlink"
    alias_dir.symlink_to(fake_temp_root, target_is_directory=True)

    fake_python = alias_dir / "nwave-test-venv" / "bin" / "python3.12"
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    # Ground truth: this path IS physically inside the (fake) temp root.
    assert fake_python.resolve().is_relative_to(fake_temp_root.resolve()), (
        "fixture bug: the symlinked interpreter must actually resolve "
        "inside the fake temp root, or this test proves nothing"
    )
    # And a naive lexical check would say it is NOT -- that is the gap
    # this test exists to close.
    assert not str(fake_python).startswith(str(fake_temp_root)), (
        "fixture bug: the alias path must NOT be a lexical descendant of "
        "the temp root, or the guard could reject it without ever "
        "resolving the symlink -- this test would then prove nothing "
        "about resolve-before-compare"
    )

    monkeypatch.setattr(sys, "executable", str(fake_python))
    persisted = DESPlugin._resolve_python_path()

    assert str(fake_python) not in persisted, (
        f"An interpreter reaching the temp directory through a symlink "
        f"was still embedded in the persisted output.\n"
        f"  Symlinked path (resolves inside the temp root): {fake_python}\n"
        f"  Persisted output:                               {persisted!r}\n"
        "The durability guard compares the path to tempfile.gettempdir() "
        "lexically, without resolving either side. On macOS, /tmp is "
        "itself a symlink to a different real path than the per-process "
        "$TMPDIR -- a literal /tmp/... interpreter (the exact shape of "
        "the 2026-07-24 incident) can resolve through that symlink and "
        "escape a lexical-only comparison. Both sides must be resolved "
        "before comparing."
    )


# ===========================================================================
# 6. THE ROOT SET IS BIGGER THAN gettempdir() -- AND SMALLER THAN "any
# candidate the stdlib would try". (second follow-up, 2026-07-24, post-fix
# implementation review)
# ===========================================================================


@pytest.mark.parametrize(
    "root_name,literal_path",
    [
        ("/var/tmp", "/var/tmp/nwave-test-venv/bin/python3.12"),
        ("/usr/tmp", "/usr/tmp/nwave-test-venv/bin/python3.12"),
    ],
)
def test_other_standard_posix_temp_roots_are_rejected_not_just_gettempdir(
    root_name: str, literal_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``tempfile.gettempdir()`` returns exactly ONE candidate -- comparing
    against it alone leaves every OTHER standard POSIX temp root wide open.

    The stdlib's own candidate search (``tempfile._candidate_tempdir_list``,
    a private function this test does NOT couple to -- see below) tries, in
    order, ``$TMPDIR``, ``$TEMP``, ``$TMP``, then ``/tmp``, ``/var/tmp``,
    ``/usr/tmp`` on POSIX, and only returns the FIRST one that is writable.
    On an ordinary box that first winner is ``/tmp`` -- so ``/var/tmp`` and
    ``/usr/tmp`` are just as standard and just as ephemeral, yet invisible
    to a guard that only asks "is this under gettempdir()?". That is the
    exact one-shape-enumeration anti-pattern this entire file exists to
    close, found one level down inside the function written to close it:
    the authorised-scope text for the original fix asserted
    ``tempfile.gettempdir()`` "covers /tmp, /var/tmp ... in one call" --
    that claim is false, ``gettempdir()`` is single-valued, and the shipped
    predicate inherited the error verbatim.

    Both roots are asserted as LITERAL, hardcoded strings -- not sourced
    from ``tempfile._candidate_tempdir_list()`` (private stdlib API; keying
    to it would smuggle CPython's own enumeration, CWD entry included, in
    as if it were this guard's contract) and not exercised against the real
    filesystem (``/usr/tmp`` does not exist on this box -- confirmed
    neither a directory nor a symlink here -- and is used specifically AS a
    nonexistent path). The guard must act on WHERE a path is rooted, never
    on whether it exists: this is
    ``test_existence_check_alone_would_not_have_caught_the_incident``'s
    argument made from the other side -- existence is not sufficient
    reason to ACCEPT a path either, just as it was not sufficient reason to
    REJECT one.
    """
    monkeypatch.setattr(sys, "executable", literal_path)

    persisted = DESPlugin._resolve_python_path()

    assert literal_path not in persisted, (
        f"An interpreter rooted under the standard POSIX temp directory "
        f"{root_name} was still embedded in the persisted output.\n"
        f"  Rejected path:     {literal_path}\n"
        f"  Persisted output:  {persisted!r}\n"
        f"tempfile.gettempdir() returns exactly one candidate (typically "
        f"/tmp) -- comparing against it alone leaves every OTHER standard "
        f"POSIX temp root, including {root_name}, wrongly judged durable."
    )


def test_cwd_rooted_interpreter_stays_accepted_when_gettempdir_returns_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CWD-as-last-resort candidate must NEVER be treated as a temp
    root -- or the guard bricks every developer checkout on exactly the
    machines where this matters most.

    The stdlib's candidate search appends the current working directory as
    its FINAL fallback: when every standard root (``/tmp``, ``/var/tmp``,
    ``/usr/tmp``, ``$TMPDIR``/``$TEMP``/``$TMP``) is unwritable,
    ``tempfile.gettempdir()`` itself returns the CWD. On such a machine, a
    guard that treats "whatever gettempdir() returns" as inherently
    ephemeral would reject EVERY interpreter rooted anywhere under the
    repository -- including the project's own checkout-local interpreter,
    the exact one a developer actually runs. This hazard is not new: it is
    latent in today's single-root comparison already (confirmed by running
    the shipped predicate with ``gettempdir()`` mocked to return the CWD --
    it rejects a legitimate CWD-rooted interpreter right now). A
    well-intentioned "reject every standard temp root" widening (the fix
    the two cases above require) makes the hazard easy to reintroduce by
    accident if the CWD is folded into that root set instead of being
    excluded from it on purpose.

    This test BINDS the two conditions together rather than checking them
    separately: it sets the resolved temp root TO a directory, then places
    the candidate interpreter UNDER THAT SAME DIRECTORY. A case that only
    checked "a path under some directory is accepted while the temp root
    is unrelated" would prove nothing -- it would pass under today's
    broken behaviour and under any future one, including a bricked one.
    Only binding temp-root-equals-checkout-root proves the CWD is excluded
    on purpose, not merely untested.

    FIXTURE NOTE (revised): the checkout root must NOT be built from
    ``tmp_path``. ``tmp_path`` is real infrastructure physically nested
    under the real ``/tmp`` -- so a fixture built that way is, in fact,
    genuinely rooted inside the exact directory the PRIMARY oracle (§1)
    and the symlink case (§5) require to be rejected. No implementation
    can satisfy both at once for such a fixture: a guard that trusts
    ``gettempdir()`` dynamically rejects it because it is literally under
    the patched root; a guard that instead checks real, resolved
    containment against an owned root list (``/tmp``, ``/var/tmp``,
    ``/usr/tmp``, ...) rejects it too, because it is REALLY inside real
    ``/tmp`` regardless of what ``gettempdir()`` was mocked to return.
    That is not a hazard this case can pin -- it is a self-contradiction
    baked into the fixture, indistinguishable from the incident itself
    once you strip the mock away.

    The corrected fixture is a purely SYNTHETIC, never-materialised
    absolute path -- disjoint from every real standard temp root AND
    from ``$HOME``/the repository -- so it is neither lexically nor
    (after ``.resolve()``) physically contained in any of them. Nothing
    is ever created on disk (none of the four write-site resolvers this
    file exercises call ``.exists()`` on the candidate path -- the same
    fact already relied on for the ``/var/tmp``/``/usr/tmp`` literal
    cases directly above), so there is nothing to clean up and no risk of
    writing under the real ``/tmp``, ``$HOME``, or this repository. The
    property under test -- "the resolved temp root IS the directory
    holding the interpreter, and it is still accepted" -- is preserved
    exactly via the ``tempfile.gettempdir()`` monkeypatch; only the
    fixture's physical location changed. Placed under a directory name
    that avoids the substring ``.venv`` deliberately, so this case cannot
    accidentally trip the separate, pre-existing PORTABILITY guard (§3)
    instead of exercising the durability guard this case targets.
    """
    checkout_root = "/synthetic-developer-checkout-root-for-this-test-only"
    monkeypatch.setattr(tempfile, "gettempdir", lambda: checkout_root)

    raw = f"{checkout_root}/project-python/bin/python3"
    monkeypatch.setattr(sys, "executable", raw)

    persisted = DESPlugin._resolve_python_path()

    expected = _expected_home_substituted(raw, str(Path.home()))
    assert persisted == expected, (
        f"An interpreter rooted under the SAME directory gettempdir() "
        f"resolved to (the CWD-as-last-resort scenario) was rejected and "
        f"replaced with the fallback.\n"
        f"  Resolved temp root (== checkout root): {checkout_root}\n"
        f"  Interpreter under that same root:      {raw}\n"
        f"  Expected (accepted, as-is):            {expected}\n"
        f"  Got:                                   {persisted!r}\n"
        "tempfile.gettempdir() returns the current working directory as "
        "its documented last resort when every standard temp root is "
        "unwritable. A guard that treats 'whatever gettempdir() returns' "
        "as inherently ephemeral would reject every interpreter under a "
        "developer's own checkout on such a machine -- the CWD must be "
        "excluded from the rejected root set on purpose, not merely "
        "absent from it by accident."
    )
