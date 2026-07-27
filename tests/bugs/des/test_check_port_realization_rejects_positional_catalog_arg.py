"""Regression AT -- `--check-port-realization` silently ignored a positional
catalog-path argument instead of refusing it (GDP-6).

Defect (defects.md: check-port-realization-silently-ignores-positional-
catalog-arg): every OTHER mode of `scripts/cli/validate_language_adapter_
catalog.py` takes a catalog file path (e.g. `validate_catalog(Path(args[0]))`
for the base mode), so an operator habitually appends `catalog.yaml` after
`--check-port-realization` too. That mode reads the live `nwave.lang.adapter`
registry (or the plugins named via repeatable `--plugin <module>:<Class>`
flags) and never a catalog file -- `main()` dispatched straight into
`_parse_plugin_flags(args[1:])`, which recognizes only `--plugin` pairs and
silently drops anything else. Measured before the fix: passing a real path
(existent or not) produced IDENTICAL output to passing no path at all --
exit 0, the live-registry summary, zero signal that the argument was ignored.

RED before the fix: a positional catalog arg after `--check-port-realization`
runs the gate over the live registry anyway (exit 0, same output as no arg).
GREEN after: `main` refuses LOUD (exit 2) naming the unrecognized argument,
never running the gate.
"""

from __future__ import annotations

from pathlib import Path

from scripts.cli.validate_language_adapter_catalog import (
    _CHECK_PORT_REALIZATION_FLAG,
    main,
)


def test_check_port_realization_refuses_a_positional_catalog_arg(
    tmp_path: Path, capsys
) -> None:
    catalog_path = tmp_path / "language-adapter-ports.yaml"
    catalog_path.write_text("ports: {}\n", encoding="utf-8")

    exit_code = main([_CHECK_PORT_REALIZATION_FLAG, str(catalog_path)])

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert exit_code == 2, (
        f"expected the refusal lane for an unrecognized positional argument "
        f"-- got exit {exit_code}. output={combined!r}"
    )
    assert str(catalog_path) in combined, (
        f"the refusal must NAME the ignored argument (GDP-3): {combined!r}"
    )
    assert "conformant" not in combined.lower(), (
        f"the gate must never run when an unrecognized argument is present: "
        f"{combined!r}"
    )


def test_check_port_realization_refuses_a_nonexistent_positional_catalog_arg(
    capsys,
) -> None:
    """The pre-fix bug ignored the argument regardless of whether the named
    path even existed -- pin that the refusal fires either way (the fix is
    about UNRECOGNIZED ARGUMENTS, not file-existence)."""
    exit_code = main([_CHECK_PORT_REALIZATION_FLAG, "does-not-exist.yaml"])

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert exit_code == 2, (
        f"expected the refusal lane -- got exit {exit_code}. output={combined!r}"
    )
    assert "does-not-exist.yaml" in combined, (
        f"the refusal must name the ignored argument: {combined!r}"
    )


def test_check_port_realization_with_only_plugin_flags_is_unaffected(
    capsys,
) -> None:
    """NEGATIVE control: a well-formed --plugin invocation (no stray
    positional) must still degrade to the existing INDETERMINATE lane for an
    unresolvable target, never the new refusal lane -- the fix must not
    over-reject legitimate invocations."""
    exit_code = main([_CHECK_PORT_REALIZATION_FLAG, "--plugin", "not.a.module:Nope"])

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert exit_code == 3, (
        f"a well-formed --plugin invocation must reach the existing "
        f"unresolvable-target INDETERMINATE lane, not the new refusal lane "
        f"-- got exit {exit_code}. output={combined!r}"
    )
