"""Acceptance oracle: ``des update --dry-run`` (ADR-AUM-001, G2 slice 1).

Discovery + classification only, zero writes. Four falsifiers this ADR names
(obligation 6, ARCHITECTURE_BOUNDARY_CHANGE) drive the CLI-level tests below;
one Hypothesis property covers BROAD_INPUT_DOMAIN (obligation 5) over the
full artifact status x tag-mappability cross-product; one example covers
PRESERVATION (obligation 3) at the real driving boundary.

Real driving surface under test: ``des.cli.update.main`` -- the new
subcommand ``_REGISTRY`` wires (``src/des/cli/__main__.py``), invoked
directly with argv (no subprocess: same-process CLI invocation is this
repo's existing convention for CLI unit tests in this tier). Real fixture
files live under ``tmp_path`` -- this is the "real, unmodified box"
obligation 6(a) requires, never a mocked FileSystemPort at this layer.

Artifact conventions used by these fixtures (mirroring the ALREADY-LANDED
global-config consumer, ``src/des/adapters/driven/config/des_config.py``):
  - ``<root>/.nwave/des-config.json`` is the "global-config" artifact type.
    Its kernel-known current version is 1 (one landed v0->v1 upcaster,
    ``des_config.py:_GLOBAL_CONFIG_VERSIONING``) -- a declared
    ``schema-version`` of 2 or higher is "from the future" for this type.
  - ``<root>/.nwave/expectation-charters/*.json`` are step-cycle-family
    workflow artifacts carrying a ``phase`` terminal-phase field (ADR-025
    vocabulary): ``"COMPLETED"`` marks the artifact done (never touched,
    Decision 6); any other phase (e.g. ``"RED"``) marks it in flight.
  - An artifact under ``<root>/.nwave/unregistered/*.json`` belongs to no
    family Decision 8 extends with string-to-int coercion -- a string
    ``schema-version`` there must surface as ``Indeterminate``, never
    silently default to version 0 the way the bare, un-extended
    ``read_version`` would for a present-but-non-int value
    (``artifact_versioning.py:91``-``:103``).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from des.cli.update import main


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


class TestUpdateDryRun:
    """Consolidated oracle for ``des update --dry-run`` (obligation 6)."""

    def test_string_schema_version_reports_indeterminate_not_silent_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """(a) A present-but-string schema-version is reported Indeterminate.

        Proves Decision 8's coercion boundary: this artifact belongs to no
        Layer-1-coerced family, so a string value must never silently fall
        through to ``read_version``'s missing-key default of 0.
        """
        artifact = tmp_path / ".nwave" / "unregistered" / "widget.json"
        _write(artifact, {"schema-version": "1", "kind": "widget"})

        exit_code = main(["--dry-run", "--root", str(tmp_path)])

        out = capsys.readouterr().out
        assert exit_code == 0
        assert str(artifact) in out
        assert "Indeterminate" in out
        assert '"1"' in out or "'1'" in out  # declared version reported verbatim
        assert "0" not in out.split(str(artifact), 1)[1].split("\n", 1)[0], (
            "the string version must never be silently reported as the "
            "missing-key default 0"
        )

    def test_completed_charter_differs_from_inflight_charter(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """(b) Completed vs InFlight classified from the artifact's own field."""
        completed = tmp_path / ".nwave" / "expectation-charters" / "done.json"
        in_flight = tmp_path / ".nwave" / "expectation-charters" / "wip.json"
        _write(completed, {"schema-version": 1, "phase": "COMPLETED"})
        _write(in_flight, {"schema-version": 1, "phase": "RED"})

        exit_code = main(["--dry-run", "--root", str(tmp_path)])

        out = capsys.readouterr().out
        assert exit_code == 0

        completed_line = next(
            line for line in out.splitlines() if str(completed) in line
        )
        in_flight_line = next(
            line for line in out.splitlines() if str(in_flight) in line
        )
        assert "Completed" in completed_line
        assert "PreserveHistory" in completed_line
        assert "InFlight" in in_flight_line
        assert "PreserveHistory" not in in_flight_line
        assert completed_line != in_flight_line

    def test_future_schema_version_refuses_loud_never_silent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """(c) A schema-version newer than this runtime's current one refuses LOUD."""
        artifact = tmp_path / ".nwave" / "des-config.json"
        _write(artifact, {"schema-version": 2})

        exit_code = main(["--dry-run", "--root", str(tmp_path)])

        captured = capsys.readouterr()
        assert exit_code != 0
        assert "WHAT" in captured.err
        assert "WHY" in captured.err
        assert "HOW" in captured.err
        assert "Traceback" not in captured.err

    def test_dry_run_writes_nothing_content_hash_unchanged(
        self, tmp_path: Path
    ) -> None:
        """(d) Every discovered artifact is byte-identical before and after."""
        artifacts = [
            tmp_path / ".nwave" / "des-config.json",
            tmp_path / ".nwave" / "expectation-charters" / "done.json",
            tmp_path / ".nwave" / "expectation-charters" / "wip.json",
            tmp_path / ".nwave" / "unregistered" / "widget.json",
        ]
        _write(artifacts[0], {"schema-version": 1})
        _write(artifacts[1], {"schema-version": 1, "phase": "COMPLETED"})
        _write(artifacts[2], {"schema-version": 1, "phase": "RED"})
        _write(artifacts[3], {"schema-version": "1", "kind": "widget"})

        before = {path: _sha256(path) for path in artifacts}

        exit_code = main(["--dry-run", "--root", str(tmp_path)])

        after = {path: _sha256(path) for path in artifacts}
        assert exit_code == 0
        assert before == after


class TestPreservationCanonicalExamples:
    """PRESERVATION (obligation 3): a Completed artifact is never mutated."""

    def test_completed_v4_step_cycle_artifact_stays_untouched(
        self, tmp_path: Path
    ) -> None:
        artifact = tmp_path / ".nwave" / "expectation-charters" / "legacy.json"
        _write(artifact, {"schema-version": 0, "phase": "COMPLETED", "tag": "v4"})
        before = _sha256(artifact)

        exit_code = main(["--dry-run", "--root", str(tmp_path)])

        assert exit_code == 0
        assert _sha256(artifact) == before

    def test_inflight_v4_artifact_with_registered_map_reported_migratable(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        artifact = tmp_path / ".nwave" / "expectation-charters" / "wip-v4.json"
        _write(artifact, {"schema-version": 0, "phase": "RED", "tag": "v4"})
        before = _sha256(artifact)

        exit_code = main(["--dry-run", "--root", str(tmp_path)])

        out = capsys.readouterr().out
        assert exit_code == 0
        assert _sha256(artifact) == before, "dry-run must never write"
        line = next(line for line in out.splitlines() if str(artifact) in line)
        assert "InFlight" in line


class TestBroadInputDomainPreservation:
    """BROAD_INPUT_DOMAIN (obligation 5): status x tag-mappability cross-product.

    Generator over a small closed alphabet of shape tags (including at least
    one unregistered tag) crossed with InFlight/Completed status. Invariant:
    a Completed artifact is NEVER reported as anything but PreserveHistory,
    and dry-run never mutates any generated artifact on disk, for every
    generated case (idempotence + no-guessing + preservation, all at once).
    """

    @given(
        phase=st.sampled_from(["COMPLETED", "RED", "GREEN", "COMMIT"]),
        tag=st.sampled_from(["v4", "v4-revised", "v5", "unregistered-tag", ""]),
    )
    def test_completed_always_preserves_regardless_of_tag_mappability(
        self, tmp_path_factory: pytest.TempPathFactory, phase: str, tag: str
    ) -> None:
        root = tmp_path_factory.mktemp("aum-pbt")
        artifact = root / ".nwave" / "expectation-charters" / "gen.json"
        doc: dict = {"schema-version": 0, "phase": phase}
        if tag:
            doc["tag"] = tag
        _write(artifact, doc)
        before = _sha256(artifact)

        exit_code = main(["--dry-run", "--root", str(root)])

        assert _sha256(artifact) == before, "dry-run never mutates any input"
        assert exit_code == 0 or phase != "COMPLETED"
        if phase == "COMPLETED":
            captured_out = artifact.read_text(encoding="utf-8")
            assert json.loads(captured_out)["phase"] == "COMPLETED"


class TestUpdateApply:
    """Persistent execution oracle for the AUM-001-G2 amendment."""

    def test_apply_persists_eligible_v4_and_retains_recoverable_backup(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        artifact = tmp_path / ".nwave" / "expectation-charters" / "wip-v4.json"
        _write(artifact, {"schema-version": 0, "phase": "RED", "tag": "v4"})
        before = artifact.read_bytes()

        exit_code = main(["--apply", "--root", str(tmp_path)])

        captured = capsys.readouterr()
        assert exit_code == 0
        assert artifact.read_bytes() != before
        migrated = json.loads(artifact.read_text(encoding="utf-8"))
        assert migrated["tag"] == "v5"
        assert migrated["phase"] == "RED"
        assert any(
            path != artifact and path.is_file() and path.read_bytes() == before
            for path in tmp_path.rglob("*")
        ), "a byte-exact backup must remain recoverable"
        assert str(artifact) in captured.out

    def test_apply_refuses_incomplete_batch_before_any_write(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        eligible = tmp_path / ".nwave" / "expectation-charters" / "wip-v4.json"
        unmappable = tmp_path / ".nwave" / "expectation-charters" / "unknown.json"
        _write(eligible, {"schema-version": 0, "phase": "RED", "tag": "v4"})
        _write(
            unmappable,
            {
                "schema-version": 0,
                "phase": "RED",
                "tag": "unregistered-tag",
                "unknown-field": True,
            },
        )
        before = {path: _sha256(path) for path in (eligible, unmappable)}

        exit_code = main(["--apply", "--root", str(tmp_path)])

        captured = capsys.readouterr()
        assert exit_code != 0
        assert "WHAT" in captured.err
        assert "WHY" in captured.err
        assert "HOW" in captured.err
        assert before == {path: _sha256(path) for path in before}
        assert not any(
            path.is_file() and path.read_bytes() == eligible.read_bytes()
            for path in tmp_path.rglob("*")
            if path not in (eligible, unmappable)
        ), "preflight refusal must not leave a backup or partial write"

    def test_apply_preserves_completed_history_byte_for_byte(
        self, tmp_path: Path
    ) -> None:
        artifact = tmp_path / ".nwave" / "expectation-charters" / "done-v4.json"
        _write(artifact, {"schema-version": 0, "phase": "COMPLETED", "tag": "v4"})
        before = artifact.read_bytes()

        exit_code = main(["--apply", "--root", str(tmp_path)])

        assert exit_code == 0
        assert artifact.read_bytes() == before
        assert not any(
            path.is_file() and path.read_bytes() == before
            for path in tmp_path.rglob("*")
            if path != artifact
        ), "preserved history must not be backed up or rewritten"

    def test_apply_rerun_is_observationally_idempotent(self, tmp_path: Path) -> None:
        artifact = tmp_path / ".nwave" / "expectation-charters" / "wip-v4.json"
        _write(artifact, {"schema-version": 0, "phase": "RED", "tag": "v4"})

        first_exit = main(["--apply", "--root", str(tmp_path)])
        after_first = artifact.read_bytes()
        files_after_first = sorted(
            path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
        )

        second_exit = main(["--apply", "--root", str(tmp_path)])

        assert first_exit == 0
        assert second_exit == 0
        assert artifact.read_bytes() == after_first
        assert files_after_first == sorted(
            path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file()
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"schema-version": 0, "phase": "RED", "tag": "v4", "unknown-field": True},
            {"schema-version": 0, "phase": "RED"},
            {"schema-version": "1", "phase": "RED", "tag": "v4"},
        ],
    )
    def test_apply_invalid_or_unversioned_input_refuses_without_mutation(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        payload: dict,
    ) -> None:
        artifact = tmp_path / ".nwave" / "expectation-charters" / "invalid.json"
        _write(artifact, payload)
        before = _sha256(artifact)

        exit_code = main(["--apply", "--root", str(tmp_path)])

        captured = capsys.readouterr()
        assert exit_code != 0
        assert "WHAT" in captured.err
        assert "WHY" in captured.err
        assert "HOW" in captured.err
        assert _sha256(artifact) == before
