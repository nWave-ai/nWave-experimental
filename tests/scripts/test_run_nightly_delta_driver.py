"""Focused driver-level test for the pinned mutmut==3.6.0 programmatic seam.

`_run_mutmut_scoped` in scripts/mutation/run_nightly_delta.py depends on two
private mutmut internals: `mutmut.configuration._load_config` /
`mutmut.configuration._config` (the Config.get() cache) and
`mutmut.__main__._run`. This test proves the exact changed-file list lands
in `_config.only_mutate` and that `_run` is invoked exactly once — without
ever launching a real mutation run.
"""

from __future__ import annotations

import dataclasses

import mutmut.__main__ as mutmut_main
from mutmut import configuration

from scripts.mutation.run_nightly_delta import _run_mutmut_scoped


@dataclasses.dataclass
class _FakeConfig:
    only_mutate: object = None


def test_run_mutmut_scoped_sets_only_mutate_and_calls_run_once(monkeypatch) -> None:
    calls: list[tuple[list[str], int | None]] = []

    def fake_load_config() -> _FakeConfig:
        return _FakeConfig(only_mutate=None)

    def fake_run(mutant_names: list[str], max_children: int | None) -> None:
        calls.append((mutant_names, max_children))

    monkeypatch.setattr(configuration, "_load_config", fake_load_config)
    monkeypatch.setattr(configuration, "_config", None, raising=False)
    monkeypatch.setattr(mutmut_main, "_run", fake_run)

    changed = ["src/des/a.py", "src/des/b.py"]
    _run_mutmut_scoped(changed)

    assert configuration._config.only_mutate == changed
    assert calls == [([], None)]
