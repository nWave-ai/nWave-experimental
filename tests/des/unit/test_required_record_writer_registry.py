"""Arch test -- the seeding helper's writer registry matches the U4 frozenset.

This is the safety net for the F-FROZENSET-EXTENSION-FIXTURE-CASCADE defect
class. The shared helper `tests/des/_helpers/feature_end_seeding.py` removes
the cascade pain (one new `_RECORD_WRITERS` entry, not 5-6 fixture-site edits)
BUT only when the helper's registry stays in lockstep with the production
frozenset. If a future slice extends `_REQUIRED_FEATURE_END_RECORDS` without
adding the matching `_RECORD_WRITERS` entry, every helper-using fixture site
silently stops seeding that new record -- the cascade returns, just dressed
in helper clothes.

This test fires loud on that drift: a single assertion comparing the two sets.
"""

from __future__ import annotations

from des.adapters.drivers.hooks.subagent_stop_handler import (
    _REQUIRED_FEATURE_END_RECORDS,
)
from tests.des._helpers.feature_end_seeding import required_record_writer_names


class TestRequiredRecordWriterRegistry:
    """The helper's registry covers every U4-required record name."""

    def test_writer_registry_covers_every_required_record(self) -> None:
        """Every name in the production frozenset has a helper writer.

        Symmetric equality: extending one side without the other surfaces here.
        Drift in either direction (a new required record without a writer, or
        a stale writer for a removed record) breaks the test.
        """
        assert required_record_writer_names() == _REQUIRED_FEATURE_END_RECORDS, (
            "tests/des/_helpers/feature_end_seeding._RECORD_WRITERS is out of "
            "sync with src/des/adapters/drivers/hooks/subagent_stop_handler."
            "_REQUIRED_FEATURE_END_RECORDS -- the F-FROZENSET-EXTENSION-"
            "FIXTURE-CASCADE safety net. Add or remove the matching "
            "_RECORD_WRITERS entry in the seeding helper."
        )
