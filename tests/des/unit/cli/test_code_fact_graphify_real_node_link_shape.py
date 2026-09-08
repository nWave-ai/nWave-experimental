"""Regression oracle: `des code-fact query.callers-of` must answer from a
REAL graphify node-link graph shape, not the `edges`/bare-label stand-in
`tests/.../fixtures/graphify.py` produces.

defects.md (des-integrated-a-fixture-only-fix-the-real-query-still-answers-empty):
a prior architect turn declared this defect fixed by touching only the
fixture producer -- the real adapter, reading a real materialized
`graphify-out/graph.json`, kept answering an empty site set, because real
graphify emits top-level `"links"` (not `"edges"`) and callable labels with
a trailing `"()"` suffix (`"target()"`, not `"target"`). Both shapes are
hand-authored directly in this file so no future turn can "fix" this again
by touching only a fixture stand-in.

This file drives the public CLI in-process (`des.cli.code_fact.main`), never
touching `GraphifyAdapter` internals directly -- the oracle is the same
public port surface a real operator invokes.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _invoke(argv: list[str], capsys: pytest.CaptureFixture) -> tuple[int, dict]:
    from des.cli.code_fact import main

    exit_code = main(argv)
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def _write_real_shaped_graphify_out(
    tmp_path: Path,
    *,
    source_relative: str,
    recorded_mtime: float,
) -> None:
    """A real graphify-out pair, node-link shaped exactly as this repo's
    own `graphify-out/graph.json` is measured to be: top-level `nodes` and
    `links` (never `edges`), callable labels carrying a trailing `()`
    call-suffix (`"target()"`, `"caller()"`), and `calls`/`imports` edges
    at EXTRACTED confidence carrying `confidence`/`source_file`/
    `source_location` -- never produced by shelling out to the `edges`/
    bare-label fixture stand-in."""
    out_dir = tmp_path / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "mod_target",
                        "label": "target()",
                        "source_file": source_relative,
                        "source_location": "L1",
                        "file_type": "code",
                    },
                    {
                        "id": "mod_caller",
                        "label": "caller()",
                        "source_file": source_relative,
                        "source_location": "L5",
                        "file_type": "code",
                    },
                    {
                        "id": "mod_uncalled",
                        "label": "uncalled()",
                        "source_file": source_relative,
                        "source_location": "L8",
                        "file_type": "code",
                    },
                ],
                "links": [
                    {
                        "source": "mod_caller",
                        "target": "mod_target",
                        "relation": "calls",
                        "confidence": "EXTRACTED",
                        "source_file": source_relative,
                        "source_location": "L6",
                        "weight": 1.0,
                        "context": "call",
                        "_origin": "ast",
                    },
                    {
                        "source": "mod_caller",
                        "target": "mod_target",
                        "relation": "imports",
                        "confidence": "EXTRACTED",
                        "source_file": source_relative,
                        "source_location": "L1",
                        "weight": 1.0,
                        "context": "import",
                        "_origin": "ast",
                    },
                ],
                "hyperedges": [],
                "input_tokens": 0,
                "output_tokens": 0,
            }
        ),
        encoding="utf-8",
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                source_relative: {
                    "ast_hash": "deadbeef",
                    "mtime": recorded_mtime,
                    "semantic_hash": "deadbeef",
                }
            }
        ),
        encoding="utf-8",
    )


def _seed_source_with_caller(tmp_path: Path) -> Path:
    source = tmp_path / "subject.py"
    source.write_text(
        "def target():\n    return 1\n\n\ndef caller():\n    return target()\n\n\n"
        "def uncalled():\n    return 3\n",
        encoding="utf-8",
    )
    return source


class TestRealNodeLinkShapeCallersOf:
    def test_callers_of_reports_real_extracted_call_sites_from_links_key(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        source = _seed_source_with_caller(tmp_path)
        _write_real_shaped_graphify_out(
            tmp_path,
            source_relative="subject.py",
            recorded_mtime=source.stat().st_mtime,
        )

        exit_code, result = _invoke(
            ["query.callers-of", "target", "--root", str(tmp_path)], capsys
        )

        assert exit_code == 0
        assert result["provider"] == "graphify"
        assert result["confidence"] == "binding-resolved"
        assert result["payload"]["sites"] == [f"{tmp_path / 'subject.py'}:6"]

    def test_imports_edges_are_excluded_from_call_sites(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """The `imports` edge in the same fixture names the same
        source/target pair as the real `calls` edge -- if it leaked into
        the site set, this would answer two sites instead of one."""
        source = _seed_source_with_caller(tmp_path)
        _write_real_shaped_graphify_out(
            tmp_path,
            source_relative="subject.py",
            recorded_mtime=source.stat().st_mtime,
        )

        exit_code, result = _invoke(
            ["query.callers-of", "target", "--root", str(tmp_path)], capsys
        )

        assert exit_code == 0
        assert len(result["payload"]["sites"]) == 1

    def test_genuinely_uncalled_symbol_answers_a_verified_empty_site_set(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Empty must be a VERIFIED absence (whole-tree completeness), not
        a default: binding-resolved confidence, `scope == "complete"`, and
        `fault_count == 0` on the answering trace entry."""
        source = _seed_source_with_caller(tmp_path)
        _write_real_shaped_graphify_out(
            tmp_path,
            source_relative="subject.py",
            recorded_mtime=source.stat().st_mtime,
        )

        exit_code, result = _invoke(
            ["query.callers-of", "uncalled", "--root", str(tmp_path)], capsys
        )

        assert exit_code == 0
        assert result["provider"] == "graphify"
        assert result["confidence"] == "binding-resolved"
        assert result["payload"]["sites"] == []
        answering_entries = [
            entry for entry in result["trace"] if entry["event"] == "answered"
        ]
        assert len(answering_entries) == 1
        assert answering_entries[0]["provider_id"] == "graphify"
        assert answering_entries[0]["scope"] == "complete"
        assert answering_entries[0]["fault_count"] == 0
