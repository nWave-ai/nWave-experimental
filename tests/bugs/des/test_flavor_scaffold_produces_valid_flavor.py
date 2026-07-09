"""Regression (WS-17-D, GDP-5): a producing tool for the mode 4-tuple.

Charter: ``docs/product/expectations/fix-flavor-scaffold-producing-tool/
des-flavor-scaffold-produces-a-valid-flavor.md``.

``mode-registry-completeness`` (``src/des/cli/mode_registry_completeness.py``)
refuses a half-declared workflow flavor (a missing/duplicated required
field, a second ``default: true``) but its HOW routes only to a MANUAL
repair -- an operator hand-assembles the 4-tuple
(``flavor_id``/``display_name``/``default``/``selection``/``skill_load_set``)
against ``nWave/flavors/_schema.yaml`` by reading the schema + an existing
flavor side by side. This closes the GDP-4/5 gap: the HOW should invoke a
PRODUCING TOOL, not a manual edit.

This AT specifies the NOT-YET-BUILT ``des flavor-scaffold`` subcommand: it
must emit a structurally-complete flavor skeleton (5 required fields, each
exactly once, ``flavor_id: <id>``, ``default: false`` -- never minting a
second default) that ``mode-registry-completeness`` accepts structurally.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL ``des.cli.__main__.main()`` dispatcher --
the single entry point every ``des <subcommand>`` invocation resolves
through (``src/des/cli/__main__.py``) -- captured via ``capsys``. No
subprocess fork; this is a regression/producing-tool AT, not the one
walking-skeleton per command.

RED mechanism (semantic, not an import error): ``flavor-scaffold`` is NOT
in the dispatcher's ``_REGISTRY`` today. Driving the REAL dispatcher with
``["flavor-scaffold", ...]`` does not raise an ``ImportError`` -- the
dispatcher module itself already exists and imports cleanly; only the
`flavor-scaffold` subcommand row is absent from its registry. `argparse`
rejects the unregistered subcommand name via its own `required=True`
subparsers choice validation, which raises `SystemExit(2)` INSIDE
`parse_known_args` (a normal, well-defined control-flow event for this
dispatcher, not a crash). The helper `_invoke_dispatcher` below catches
that `SystemExit` and normalizes it to an ordinary `(exit_code, stdout,
stderr)` tuple -- exactly like a real CLI process exit -- so the test body
makes plain semantic assertions on BEHAVIOR (expected exit code, expected
YAML content) rather than on an exception type. Today those assertions
FAIL with a normal `AssertionError` (RED for the right reason: the
producing tool does not exist yet) -- never an `ImportError`, never an
uncaught `SystemExit` bubbling into a test ERROR.
"""

from __future__ import annotations

import re

import pytest

from des._internal import subset_parser
from des.cli.__main__ import main as dispatcher_main


_REQUIRED_FIELDS: tuple[str, ...] = (
    "flavor_id",
    "display_name",
    "default",
    "selection",
    "skill_load_set",
)


def _invoke_dispatcher(argv: list[str], capsys: pytest.CaptureFixture[str]):
    """Drive the REAL `des` dispatcher (`des.cli.__main__.main`) in-process.

    Normalizes BOTH control-flow shapes the dispatcher can produce for a
    given argv into one `(exit_code, stdout, stderr)` tuple:

    * Today (`flavor-scaffold` unregistered): `argparse`'s required-subparser
      choice validation raises `SystemExit(2)` from inside
      `parser.parse_known_args` -- caught here and normalized to exit code 2,
      exactly as a real subprocess exit would report it.
    * After the subcommand is registered and implemented: `main()` returns an
      ordinary `int` (the subcommand's own return value, DDD-6 passthrough),
      no exception involved.

    Either way the caller receives a plain tuple -- semantic assertions only,
    no exception-shaped branching leaks into the test bodies below.
    """
    try:
        exit_code = dispatcher_main(list(argv))
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def _top_level_field_count(raw_text: str, field: str) -> int:
    """How many times `field` is declared at column 0 -- mirrors the exact
    duplicate-declaration check `mode_registry_completeness._top_level_
    declaration_count` runs against a real flavor file."""
    return len(re.findall(rf"^{re.escape(field)}:", raw_text, flags=re.MULTILINE))


def test_flavor_scaffold_emits_a_structurally_complete_flavor_skeleton(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """POSITIVE AT (active-RED today): `des flavor-scaffold --flavor-id
    demo_flavor --stdout` must emit a YAML flavor skeleton carrying ALL 5
    required mode-4-tuple fields, each declared EXACTLY ONCE, with
    `flavor_id: demo_flavor` and `default: false` (never minting a second
    `default: true` -- the exactly-one-default invariant
    `mode-registry-completeness` enforces across the registry).

    Today `flavor-scaffold` is not a registered subcommand: the dispatcher
    exits 2 (argparse invalid-choice) and emits no YAML at all -- the first
    assertion below fails with a genuine `AssertionError` naming the missing
    behavior, not a crash.
    """
    argv = ["flavor-scaffold", "--flavor-id", "demo_flavor", "--stdout"]
    exit_code, stdout, stderr = _invoke_dispatcher(argv, capsys)

    assert exit_code == 0, (
        "expected `des flavor-scaffold --flavor-id demo_flavor --stdout` to "
        "succeed (exit 0) and print a flavor YAML skeleton to stdout -- the "
        "subcommand does not exist yet (dispatcher exits "
        f"{exit_code}); stderr={stderr!r}"
    )

    assert stdout.strip(), (
        "expected non-empty YAML on stdout from `flavor-scaffold --stdout`, "
        f"got nothing: stdout={stdout!r} stderr={stderr!r}"
    )

    for field in _REQUIRED_FIELDS:
        count = _top_level_field_count(stdout, field)
        assert count == 1, (
            f"expected the scaffold to declare required mode field {field!r} "
            f"exactly once at the top level, found {count} time(s) in: "
            f"{stdout!r}"
        )

    parsed = subset_parser.load(stdout)
    assert parsed.get("flavor_id") == "demo_flavor", (
        "expected the scaffold's `flavor_id` to echo the `--flavor-id` "
        f"argument (`demo_flavor`), got {parsed.get('flavor_id')!r}"
    )
    assert parsed.get("default") is False, (
        "expected the scaffold to declare `default: false` -- it must never "
        "mint a second `default: true` and break the registry's "
        f"exactly-one-default invariant, got {parsed.get('default')!r}"
    )


@pytest.mark.negative_at
def test_flavor_scaffold_never_mints_a_second_default_true(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """NEGATIVE AT (control -- green today, stays green after the fix):
    whatever `des flavor-scaffold --stdout` produces (or, today, the empty
    output of the not-yet-registered subcommand) NEVER carries a top-level
    `default: true` declaration -- the exactly-one-default invariant across
    the flavor registry must never be broken by the scaffold.

    Green today: the subcommand does not exist, so nothing is minted at
    all -- vacuously no `default: true` is produced. Stays green after the
    fix: the scaffold is specified (see the POSITIVE AT above) to always
    emit `default: false`, so this invariant continues to hold once
    `flavor-scaffold` is implemented.
    """
    argv = ["flavor-scaffold", "--flavor-id", "demo_flavor", "--stdout"]
    _exit_code, stdout, stderr = _invoke_dispatcher(argv, capsys)

    combined = stdout + stderr
    assert not re.search(r"^default:\s*true\s*$", combined, flags=re.MULTILINE), (
        "the flavor-scaffold output must never mint a second `default: true` "
        f"(exactly-one-default invariant): {combined!r}"
    )


# ---------------------------------------------------------------------------
# Regression (FLAG-1, Vera examine 2026-07-09): the scaffold's PLACEHOLDER
# fields (`descriptor`, `deliver_phase_shape`, `lifecycle_events` comments)
# are unresolved TODO markers, not structurally-valid values. GDP-5 requires
# the SYSTEM to produce a valid artifact, not one requiring hand-repair --
# `deliver_phase_shape: "TODO_PHASE -> TODO_PHASE"` is not a real phase
# shape (compare `nWave/flavors/classic.yaml`'s `"RED -> GREEN -> COMMIT"`),
# so a maintainer cannot use the produced flavor as-is. Charter:
# `docs/product/expectations/fix-flavor-scaffold-producing-tool/
# des-flavor-scaffold-produces-a-valid-flavor.md`.
# ---------------------------------------------------------------------------

_PHASE_SHAPE_PATTERN = re.compile(r"^\w+(?: -> \w+)+$")


@pytest.mark.negative_at
def test_flavor_scaffold_output_does_not_contain_unresolved_placeholder(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """NEGATIVE AT (the FLAG-1 defect): the emitted YAML must carry NO
    unresolved `TODO` placeholder text anywhere -- not in a field value, not
    in a comment. Today the scaffold emits four: the `description` block
    scalar, the `skill_load_set` comment, the `descriptor` folded scalar, and
    the `lifecycle_events` comment (`src/des/cli/flavor_scaffold.py`
    `_render_flavor_yaml`) -- so this fails with a genuine `AssertionError`
    naming the leaked placeholder text, not a collection/import error.
    """
    argv = ["flavor-scaffold", "--flavor-id", "demo_flavor", "--stdout"]
    _exit_code, stdout, stderr = _invoke_dispatcher(argv, capsys)

    assert "todo" not in stdout.lower(), (
        "expected the flavor-scaffold output to carry no unresolved `TODO` "
        "placeholder (GDP-5: the system must produce a valid artifact, not "
        f"one requiring hand-repair), found: {stdout!r}; stderr={stderr!r}"
    )


def test_flavor_scaffold_emits_a_real_deliver_phase_shape(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """POSITIVE AT (active-RED today): the emitted `deliver_phase_shape`
    must be a REAL phase shape -- `<PHASE> -> <PHASE>[ -> <PHASE>]` with
    every token a real phase name, never the literal placeholder
    `TODO_PHASE` (`nWave/flavors/classic.yaml`'s `"RED -> GREEN -> COMMIT"`
    and `atdd_pure.yaml`'s `"A_GREEN -> EXAMINE -> COMMIT"` are the real
    shapes this mirrors). Today the scaffold hardcodes
    `"TODO_PHASE -> TODO_PHASE"` (`_render_flavor_yaml`), so this fails with
    a genuine `AssertionError`, not a parse error.
    """
    argv = ["flavor-scaffold", "--flavor-id", "demo_flavor", "--stdout"]
    exit_code, stdout, stderr = _invoke_dispatcher(argv, capsys)
    assert exit_code == 0, (
        f"expected flavor-scaffold to succeed, got exit_code={exit_code} "
        f"stdout={stdout!r} stderr={stderr!r}"
    )

    parsed = subset_parser.load(stdout)
    phase_shape = parsed.get("deliver_phase_shape")
    assert isinstance(phase_shape, str) and "TODO_PHASE" not in phase_shape, (
        "expected `deliver_phase_shape` to never contain the literal "
        f"placeholder `TODO_PHASE`, got {phase_shape!r}"
    )
    assert phase_shape is not None and _PHASE_SHAPE_PATTERN.fullmatch(phase_shape), (
        "expected `deliver_phase_shape` to match the real phase-shape "
        r"pattern `\w+( -> \w+)+` (e.g. `RED -> GREEN -> COMMIT`), got "
        f"{phase_shape!r}"
    )
