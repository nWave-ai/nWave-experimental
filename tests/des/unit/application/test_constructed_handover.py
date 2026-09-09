from __future__ import annotations

from des.application import handover
from des.application.handover import HandoverValue, create_constructed_handover


def test_constructed_handover_does_not_decode_its_own_canonical_bytes(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        handover,
        "read_handover",
        lambda raw: (_ for _ in ()).throw(
            AssertionError("decoder must only validate external bytes")
        ),
    )
    stored = create_constructed_handover(
        tmp_path, "request", (HandoverValue("first", (), None),)
    )
    assert stored.request == "request" and stored.values[0].observation == "first"
