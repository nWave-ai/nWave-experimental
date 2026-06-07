"""Unit tests for ReDoS literal-constraint guard (US-13 AC-4, AC-6, ADR-01).

Test Budget: 1 distinct behavior x 2 = 2 unit tests max.
Using 2 (parametrized across pathological pattern variants -- 1 test,
plus separate probe() raises test).

Behavior:
  B4 -- user-supplied verb patterns containing unbounded-quantifier nesting
       or catastrophic backtracking constructs are rejected by probe()
       with a structured startup-refused event on stderr and exit 70.

Port: PlaintextVerbLoader.probe(cwd_root=<override_with_bad_pattern>) -- driving port.
"""

from __future__ import annotations

import pytest
from nwave_ai.feature_delta.adapters.verbs import PlaintextVerbLoader, ReDoSError


@pytest.mark.parametrize(
    "pattern",
    [
        "(a+)+b",  # unbounded quantifier nesting (AC-4)
        "(a*)*$",  # catastrophic backtracking (AC-6)
    ],
)
def test_pathological_verb_pattern_raises_redos_error(tmp_path, pattern: str) -> None:
    """PlaintextVerbLoader.probe() raises ReDoSError for pathological patterns (US-13 AC-4/AC-6)."""
    override_dir = tmp_path / ".nwave"
    override_dir.mkdir()
    override_file = override_dir / "protocol-verbs.txt"
    override_file.write_text(f"{pattern}\n", encoding="utf-8")

    loader = PlaintextVerbLoader(cwd_root=tmp_path)
    with pytest.raises(ReDoSError) as exc_info:
        loader.probe()

    assert pattern in str(exc_info.value), (
        f"ReDoSError must name the rejected pattern; got: {exc_info.value}"
    )
