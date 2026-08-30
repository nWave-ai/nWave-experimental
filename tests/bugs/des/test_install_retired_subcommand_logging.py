"""RED oracle: F-INSTALL-REMOVAL-TRANSPARENCY deliverable (1) -- one log
line per retired `des` subcommand name (reopened; previously covered only
retired SCRIPT files via ``sweep_retired_assets``, which does not see
inside ``_REGISTRY``).

Design decision this oracle pins:

* ``des.cli.registry_diff.log_retired_subcommand_removals(logger, diff,
  retired)`` -- ``logger`` is any object exposing ``.info(str)`` (duck-typed,
  matches ``InstallContext.logger`` used elsewhere in
  ``scripts/install/plugins/des_plugin.py``); ``diff`` is a ``RegistryDiff``
  (see the sibling summary-oracle file for its shape); ``retired`` is a
  ``Mapping[str, object]`` where each value exposes a ``.replacement:
  str | None`` attribute (the same shape as ``des.cli.__main__``'s
  ``_RETIRED`` map -- see the sibling usage-error oracle file).
* Emits exactly one ``logger.info(...)`` call per name in ``diff.removed``,
  in the SAME retired-script log style already used by
  ``_sweep_retired_scripts``: ``f"  \U0001f9f9 Removed retired des
  subcommand: {name}"``.
* When ``retired`` names that removed subcommand with a KNOWN
  ``.replacement``, the SAME line carries an appended
  ``f" -> replaced by {replacement}"`` -- never a separate line, never
  invented for a name absent from (or with no replacement in) ``retired``.
* Emits nothing for names not in ``diff.removed`` (added names are not
  logged here -- only removals are noteworthy on the removal-transparency
  axis).
* Emits nothing at all when ``diff.removed`` is empty.
"""

from __future__ import annotations

from collections import namedtuple


_RetiredEntry = namedtuple("_RetiredEntry", ["reason", "replacement"])


class _RecordingLogger:
    def __init__(self) -> None:
        self.info_calls: list[str] = []

    def info(self, message: str) -> None:
        self.info_calls.append(message)


def _diff(removed: frozenset[str], added: frozenset[str] = frozenset()):
    from des.cli.registry_diff import RegistryDiff

    return RegistryDiff(
        old_count=len(removed) + 2,
        new_count=2 + len(added),
        removed=removed,
        added=added,
    )


def test_logs_one_line_per_removed_name() -> None:
    from des.cli.registry_diff import log_retired_subcommand_removals

    logger = _RecordingLogger()
    diff = _diff(frozenset({"foo", "bar"}))

    log_retired_subcommand_removals(logger, diff, retired={})

    assert len(logger.info_calls) == 2
    logged = set(logger.info_calls)
    assert "  \U0001f9f9 Removed retired des subcommand: foo" in logged
    assert "  \U0001f9f9 Removed retired des subcommand: bar" in logged


def test_appends_replacement_only_when_retired_map_declares_one() -> None:
    from des.cli.registry_diff import log_retired_subcommand_removals

    logger = _RecordingLogger()
    diff = _diff(frozenset({"old-name", "gone-name"}))
    retired = {
        "old-name": _RetiredEntry(reason="renamed", replacement="new-name"),
        "gone-name": _RetiredEntry(reason="dropped entirely", replacement=None),
    }

    log_retired_subcommand_removals(logger, diff, retired=retired)

    logged = set(logger.info_calls)
    assert (
        "  \U0001f9f9 Removed retired des subcommand: old-name -> replaced by "
        "new-name" in logged
    )
    assert "  \U0001f9f9 Removed retired des subcommand: gone-name" in logged
    assert not any("gone-name -> replaced by" in line for line in logged)


def test_no_logging_when_nothing_removed() -> None:
    from des.cli.registry_diff import log_retired_subcommand_removals

    logger = _RecordingLogger()
    diff = _diff(frozenset())

    log_retired_subcommand_removals(logger, diff, retired={})

    assert logger.info_calls == []


def test_does_not_log_added_names() -> None:
    from des.cli.registry_diff import log_retired_subcommand_removals

    logger = _RecordingLogger()
    diff = _diff(removed=frozenset({"x"}), added=frozenset({"brand-new"}))

    log_retired_subcommand_removals(logger, diff, retired={})

    assert len(logger.info_calls) == 1
    assert "brand-new" not in logger.info_calls[0]
