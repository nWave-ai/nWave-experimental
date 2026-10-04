from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given
from hypothesis import strategies as st

from des.cli.role_packet_views import read_views, write_views


@given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=16000))
def test_views_reconstruct_sealed_nested_input_without_losing_large_fields(text):
    with TemporaryDirectory(prefix="role-views-property-") as temporary:
        root = Path(temporary)
        payload = {
            "role": "reviewer",
            "diff": text,
            "approved_oracles": [["test/check.ml", text]],
            "empty": {},
            "other": [None, False, 42, []],
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        source = root / "input.json"
        source.write_bytes(raw)
        manifest = write_views(source, raw)
        recovered = read_views(
            manifest, expected_input_sha256=hashlib.sha256(raw).hexdigest()
        )
        assert recovered == raw
        index = json.loads(manifest.read_bytes())
        assert index["input_sha256"] == hashlib.sha256(recovered).hexdigest()
        assert all(
            (manifest.parent / part["file"]).stat().st_size <= 8192
            for field in index["fields"]
            for part in field["parts"]
        )


def test_views_refuse_missing_tampered_and_escaping_chunks(tmp_path):
    source = tmp_path / "input.json"
    raw = json.dumps(
        {"diff": "business observation"}, sort_keys=True, ensure_ascii=False
    ).encode()
    source.write_bytes(raw)
    manifest = write_views(source, raw)
    index = json.loads(manifest.read_bytes())
    part = index["fields"][0]["parts"][0]
    chunk = manifest.parent / part["file"]
    original = chunk.read_bytes()
    chunk.write_bytes(b'{"value":"different observation"}')
    with pytest.raises(ValueError, match="digest"):
        read_views(manifest, expected_input_sha256=hashlib.sha256(raw).hexdigest())
    chunk.unlink()
    with pytest.raises(ValueError, match="unavailable"):
        read_views(manifest, expected_input_sha256=hashlib.sha256(raw).hexdigest())
    chunk.write_bytes(original)
    part["file"] = "../input.json"
    manifest.write_text(json.dumps(index))
    with pytest.raises(ValueError, match="confined"):
        read_views(manifest, expected_input_sha256=hashlib.sha256(raw).hexdigest())


def test_resealed_view_cannot_substitute_evidence_or_escape_directory(tmp_path):
    source = tmp_path / "input.json"
    raw = json.dumps(
        {"diff": "agreed behavior"}, sort_keys=True, ensure_ascii=False
    ).encode()
    source.write_bytes(raw)
    manifest = write_views(source, raw)
    index = json.loads(manifest.read_bytes())
    part = index["fields"][0]["parts"][0]
    replacement = json.dumps(
        {"value": "replacement behavior"}, sort_keys=True, ensure_ascii=False
    ).encode()
    (manifest.parent / part["file"]).write_bytes(replacement)
    part["sha256"] = hashlib.sha256(replacement).hexdigest()
    index["input_sha256"] = hashlib.sha256(
        json.dumps(
            {"diff": "replacement behavior"}, sort_keys=True, ensure_ascii=False
        ).encode()
    ).hexdigest()
    manifest.write_text(json.dumps(index))
    with pytest.raises(ValueError, match="trusted INPUT"):
        read_views(manifest, expected_input_sha256=hashlib.sha256(raw).hexdigest())
    directory = manifest.parent
    preserved = directory.with_name("outside-views")
    directory.rename(preserved)
    directory.symlink_to(preserved, target_is_directory=True)
    with pytest.raises(ValueError, match="confined"):
        read_views(manifest, expected_input_sha256=hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize("descendant_first", [True, False])
def test_overlapping_fields_are_refused_in_either_order(tmp_path, descendant_first):
    raw = json.dumps({"a": {}}, sort_keys=True, ensure_ascii=False).encode()
    source = tmp_path / "input.json"
    source.write_bytes(raw)
    manifest = write_views(source, raw)
    index = json.loads(manifest.read_bytes())
    name = "field-000002-part-000001.json"
    extra = json.dumps({"value": False}, sort_keys=True, ensure_ascii=False).encode()
    (manifest.parent / name).write_bytes(extra)
    child = {
        "path": ["a", "x"],
        "kind": "value",
        "parts": [{"file": name, "sha256": hashlib.sha256(extra).hexdigest()}],
    }
    index["fields"].insert(0 if descendant_first else 1, child)
    manifest.write_text(json.dumps(index))
    with pytest.raises(ValueError, match="overlap"):
        read_views(manifest, expected_input_sha256=hashlib.sha256(raw).hexdigest())
