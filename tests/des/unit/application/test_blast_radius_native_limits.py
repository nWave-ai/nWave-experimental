"""Unsupported source analysis is unknown, never measured zero consumers."""

from pathlib import Path

from des.application.blast_radius_measurement import _consumer_counts


def test_native_source_and_interface_consumer_counts_remain_unknown(
    tmp_path: Path,
) -> None:
    (tmp_path / "reservation.ml").write_text("let reserve () = ()\n")
    (tmp_path / "reservation.mli").write_text("val reserve : unit -> unit\n")
    assert _consumer_counts(tmp_path, ["reservation.ml", "reservation.mli"]) == {
        "reservation.ml": None,
        "reservation.mli": None,
    }
