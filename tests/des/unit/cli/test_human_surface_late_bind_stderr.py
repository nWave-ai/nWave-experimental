"""Regression: ``print_human_summary`` late-binds ``sys.stderr`` at CALL-time.

node-D enabler. The default ``file`` previously bound ``sys.stderr`` at
DEF-TIME (function definition, executed at module import). An in-process
``contextlib.redirect_stderr`` patches ``sys.stderr`` AFTER the module is
imported, so it never wrapped the call -> a test driving a gate in-process
could not capture ``print_human_summary``'s loud advisory diagnostic, forcing
those corpus forks to stay slow subprocesses (faithful-limit / node-D).

The fix is a 1-line late-bind (``file=None`` -> resolve ``sys.stderr`` inside
the body). These tests pin the three observable facts that make the seam
in-process-capturable WITHOUT changing production behaviour:

  (a) with no ``file=`` arg, the output goes to the CURRENT ``sys.stderr``, so a
      ``redirect_stderr`` around the call captures it (the late-bind);
  (b) an explicit ``file=`` still writes exactly there (backward-compatible);
  (c) the production default still lands on stderr, not stdout.
"""

from __future__ import annotations

import contextlib
import io

from des.cli.human_surface import Verdict, print_human_summary


def test_default_late_binds_current_stderr_so_redirect_captures_it() -> None:
    # (a) THE late-bind: redirect_stderr patches sys.stderr AFTER import; the
    # call with no file= must resolve sys.stderr at CALL-time and write there.
    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        print_human_summary(Verdict.DEGRADED, "advisory diagnostic line")

    out = captured.getvalue()
    assert "DEGRADED" in out
    assert "advisory diagnostic line" in out


def test_explicit_file_argument_still_writes_there() -> None:
    # (b) backward-compatible: an explicit file= sink receives the line, and the
    # ambient stderr does NOT (the explicit arg wins over the late-bound default).
    explicit = io.StringIO()
    ambient = io.StringIO()
    with contextlib.redirect_stderr(ambient):
        print_human_summary(Verdict.PASS, "explicit sink", file=explicit)

    assert "PASS" in explicit.getvalue()
    assert "explicit sink" in explicit.getvalue()
    assert ambient.getvalue() == ""


def test_default_goes_to_stderr_not_stdout() -> None:
    # (c) production default unchanged: the line lands on stderr, never stdout.
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        print_human_summary(Verdict.FAIL, "verdict on stderr")

    assert "verdict on stderr" in err.getvalue()
    assert out.getvalue() == ""
