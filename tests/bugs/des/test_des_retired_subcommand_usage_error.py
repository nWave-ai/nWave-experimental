"""RED oracle: F-INSTALL-REMOVAL-TRANSPARENCY deliverable (3) -- `des
<retired-subcommand>` explains WHAT/WHY/HOW instead of argparse's generic
"invalid choice", for the 17 names independently measured (2026-08-24,
docs/analysis/2026-08-24-parita-proiezioni-verbi-des.md, section 2) as
"invalid choice" today despite being documented as live in the stale
affordance catalog.

Design decisions this oracle pins (crafter must not reinterpret):

* ``des.cli.__main__`` gains a frozen dataclass ``RetiredSubcommand(reason:
  str, replacement: str | None = None)`` and a module-level dict
  ``_RETIRED: dict[str, RetiredSubcommand]`` keyed by the retired kebab-case
  name.
* ``main()`` intercepts ``raw_argv[0]`` against ``_RETIRED`` BEFORE
  building/parsing with argparse (between computing ``raw_argv`` and
  ``_build_parser(...)``) -- a name absent from ``_RETIRED`` is completely
  unaffected and still falls through to argparse's own "invalid choice"
  (the existing non-regression test file
  ``tests/bugs/des/test_dispatcher_unknown_subcommand_is_a_clear_usage_error.py``
  must keep passing unmodified).
* On a hit, ``main()`` prints to stderr EXACTLY (four lines, trailing
  newline from ``print``):

  ```
  des <name>: retired.
  WHAT: '<name>' is no longer a des subcommand.
  WHY: <reason>
  HOW: run `des --help` to see current subcommands.
  ```

  When ``_RETIRED[name].replacement`` is not ``None``, the HOW line instead
  reads:
  ``HOW: run `des --help` to see current subcommands, or use `<replacement>` instead.``
* ``main()`` then raises ``SystemExit(3)`` -- exit code 3 is a DELIBERATE,
  new, distinct choice from argparse's own code 2 for "invalid choice", so a
  caller can tell "known-retired, explained" apart from "never existed,
  generic argparse error" programmatically. (Design decision, not measured
  -- crafter implements exactly this; no other code is a valid substitute.)
* The 17 names measured 2026-08-24 all share ONE reason string (no
  per-name fabrication -- the RCA has no per-name evidence):
  ``"retired during the CLI's consolidation to a single entry point; it "
  "remains documented only in the stale affordance catalog, which is 28 "
  "days older than the current CLI "
  "(docs/analysis/2026-08-24-parita-proiezioni-verbi-des.md)."``
  and NONE of the 17 declares a ``replacement`` (not verified per-name --
  omitting is more honest than guessing, per the WHAT/WHY/HOW no-lying
  constraint).
"""

from __future__ import annotations

import pytest


_SHARED_REASON = (
    "retired during the CLI's consolidation to a single entry point; it "
    "remains documented only in the stale affordance catalog, which is 28 "
    "days older than the current CLI "
    "(docs/analysis/2026-08-24-parita-proiezioni-verbi-des.md)."
)

_MEASURED_RETIRED_NAMES = (
    "bugfix-pipeline-tick",
    "carpaccio-slice-gate",
    "check-contract-shape",
    "commit-slice",
    "consolidation-signal-tick",
    "examine-fixture",
    "feature-delta-doctor",
    "flavor-scaffold",
    "next",
    "record-at-review-verdict",
    "record-examine-verdict",
    "refactor",
    "validate-feature-delta",
    "verify-catalog-coherence",
    "verify-readiness-pre-dispatch",
    "verify-slice-commit",
    "work-exhausted-tick",
)


def test_retired_map_declares_all_17_measured_names_with_shared_reason() -> None:
    from des.cli.__main__ import _RETIRED

    for name in _MEASURED_RETIRED_NAMES:
        assert name in _RETIRED, f"{name} missing from _RETIRED"
        assert _RETIRED[name].reason == _SHARED_REASON
        assert _RETIRED[name].replacement is None, (
            f"{name} must not fabricate a replacement -- none verified"
        )


@pytest.mark.parametrize("name", ["commit-slice", "next", "work-exhausted-tick"])
def test_retired_subcommand_exits_with_what_why_how(
    name: str, capsys: pytest.CaptureFixture
) -> None:
    from des.cli.__main__ import main

    with pytest.raises(SystemExit) as exc_info:
        main([name])

    assert exc_info.value.code == 3
    err = capsys.readouterr().err
    assert f"des {name}: retired." in err
    assert f"WHAT: '{name}' is no longer a des subcommand." in err
    assert f"WHY: {_SHARED_REASON}" in err
    assert "HOW: run `des --help` to see current subcommands." in err
    assert "invalid choice" not in err


def test_retired_subcommand_with_replacement_names_it_in_how(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    from des.cli import __main__ as main_module

    monkeypatch.setitem(
        main_module._RETIRED,
        "toy-retired-with-replacement",
        main_module.RetiredSubcommand(
            reason="toy reason for this test only", replacement="toy-new-name"
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        main_module.main(["toy-retired-with-replacement"])

    assert exc_info.value.code == 3
    err = capsys.readouterr().err
    assert (
        "HOW: run `des --help` to see current subcommands, or use "
        "`toy-new-name` instead." in err
    )


def test_unknown_never_retired_name_is_unaffected_and_still_argparse_invalid_choice(
    capsys: pytest.CaptureFixture,
) -> None:
    """Non-regression: must not collide with the existing pinned behaviour in
    test_dispatcher_unknown_subcommand_is_a_clear_usage_error.py -- imported
    and re-run here as part of this oracle's own suite rather than
    duplicating its assertions."""
    from tests.bugs.des.test_dispatcher_unknown_subcommand_is_a_clear_usage_error import (
        test_unknown_subcommand_exits_cleanly_with_usage_message,
        test_unknown_subcommand_never_raises_stopiteration,
    )

    test_unknown_subcommand_exits_cleanly_with_usage_message(capsys)
    test_unknown_subcommand_never_raises_stopiteration()
