"""K4 campaign evidence must reach a DURABLE substrate, as a harness step.

`F-K4-EVIDENCE-WIPED-NO-ARCHIVE-STEP` (backlog U17), second occurrence of the
same defect class. The paired campaign writes its whole evidence tree under an
ephemeral `/tmp` root and NO step of the harness copies it anywhere else, so a
`/tmp` wipe or a box reboot destroys evidence that was already PAID for --
camp6 ($43.32 / 1h51m), the campaign root `/tmp/nwave-k4-150242df2/campaign`
explicitly marked ARCHIVE REQUIRED in the admission-row registry and never
archived, run 18 (the first terminal run), runs 11-17, and the scoring inputs
`arms.json` / `nwave.json` / `control.json` / `blindscore-v2.json`.

The correctness criterion these tests pin, stated as the backlog's own
falsifier: after a campaign, the scoring scripts run on the evidence of THAT
campaign and find it INTACT even after `/tmp` is wiped, and a LATER campaign
never overwrites an earlier one.

The headline test below is execution-observing on purpose: it does not assert
that files were copied, it re-runs a real scoring script
(`paired_quality_join.py`) against the archived copy AFTER deleting the
ephemeral root. A file-existence assertion would pass on an archive the
scorers cannot actually read, which is exactly the class of comfort the
ARCHIVE REQUIRED marker already provided for a year without being honoured.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.analysis import campaign_archive, paired_campaign, paired_quality_join


@pytest.fixture(autouse=True)
def fake_tmp(tmp_path, monkeypatch):
    """pytest's own `tmp_path` lives under the real `/tmp`, and the durability
    guard refuses to archive there -- correctly. So the ephemeral substrate is
    SIMULATED: `campaign_archive` is told the system temp directory is
    `tmp_path/ephemeral-tmp`, which the wipe test then deletes for real. This
    models the incident more faithfully than borrowing the real `/tmp` would,
    and keeps the guard un-weakened in production.
    """
    ephemeral = tmp_path / "ephemeral-tmp"
    ephemeral.mkdir()
    monkeypatch.setattr(
        campaign_archive,
        "tempfile",
        SimpleNamespace(gettempdir=lambda: str(ephemeral)),
    )
    return ephemeral


def _run_payload(session_id: str) -> str:
    """The minimum shape `paired_spread.classify` accepts as `Usable` -- every
    field present, no `is_error`, non-zero cost. Hand-built rather than copied
    from a real campaign because every real campaign's evidence was wiped."""
    return json.dumps(
        {
            "session_id": session_id,
            "total_cost_usd": 1.25,
            "num_turns": 7,
            "duration_ms": 123_000,
            "is_error": False,
            "usage": {
                "input_tokens": 100,
                "output_tokens": 200,
                "cache_creation_input_tokens": 10,
                "cache_read_input_tokens": 20,
            },
        }
    )


def _write_completed_campaign(campaign_root: Path, *, pairs: int = 1) -> None:
    """The exact layout `paired_campaign.main` writes: `campaign.json` at the
    top, `pair-N/<arm>.json` + `.err` + `.setup.json` per pair, plus a fat
    per-arm workspace that must NOT be dragged into the archive."""
    campaign_root.mkdir(parents=True, exist_ok=True)
    (campaign_root / "campaign.json").write_text(
        json.dumps({"task": "t", "pairs": pairs, "trunk": "deadbeef"}),
        encoding="utf-8",
    )
    for index in range(1, pairs + 1):
        pair_dir = campaign_root / f"pair-{index}"
        pair_dir.mkdir(exist_ok=True)
        for arm in ("nwave", "control"):
            (pair_dir / f"{arm}.json").write_text(
                _run_payload(f"session-{arm}-{index}"), encoding="utf-8"
            )
            (pair_dir / f"{arm}.err").write_text("", encoding="utf-8")
            (pair_dir / f"{arm}.setup.json").write_text(
                json.dumps({"ok": True, "seconds": 1.0, "steps": []}),
                encoding="utf-8",
            )
            workspace = pair_dir / arm / ".git"
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "pack").write_bytes(b"0" * 4096)


def test_archive_keeps_only_transcripts_from_isolated_profiles(tmp_path):
    campaign = tmp_path / "campaign"
    profile = campaign / "pair-1" / "nwave" / ".claude-k4"
    transcript = profile / "projects" / "project" / "session.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text('{"timestamp":"2026-01-01T00:00:00Z"}\n')
    for name in (".credentials.json", ".claude.json", "settings.json"):
        (profile / name).write_text("secret")

    archived = campaign_archive.archive_campaign(
        campaign, archive_root=tmp_path / "durable", campaign_id="secrets"
    )

    assert (archived / transcript.relative_to(campaign)).is_file()
    assert not any(
        (archived / profile.relative_to(campaign) / name).exists()
        for name in (".credentials.json", ".claude.json", "settings.json")
    )


def _verdicts_for(campaign_root: Path, pairs: int = 1) -> Path:
    verdicts = {
        f"session-{arm}-{index}": {"accepted": True, "evidence": "hidden 6/6"}
        for index in range(1, pairs + 1)
        for arm in ("nwave", "control")
    }
    path = campaign_root / "verdicts.json"
    path.write_text(json.dumps(verdicts), encoding="utf-8")
    return path


def test_campaign_evidence_is_still_rescorable_after_the_ephemeral_root_is_wiped(
    tmp_path, fake_tmp, capsys
):
    """THE falsifier for `F-K4-EVIDENCE-WIPED-NO-ARCHIVE-STEP`.

    A campaign completes under an ephemeral root; the harness archives it; the
    ephemeral root is then destroyed exactly as the real `/tmp` wipe destroyed
    camp6. A scoring script must still produce a verdict for THAT campaign.
    """
    ephemeral = fake_tmp / "nwave-k4-camp9-abc123"
    campaign_root = ephemeral / "campaign"
    _write_completed_campaign(campaign_root)
    _verdicts_for(campaign_root)
    durable = tmp_path / "durable"

    archived = campaign_archive.archive_campaign(campaign_root, archive_root=durable)

    shutil.rmtree(ephemeral)
    assert not campaign_root.exists(), "the wipe must actually destroy the source"

    exit_code = paired_quality_join.main(
        [
            "--campaign",
            str(archived),
            "--verdicts",
            str(archived / "verdicts.json"),
        ]
    )

    assert exit_code == 0, (
        "the scoring script must run on the ARCHIVED evidence of that campaign "
        "after the ephemeral root is gone"
    )
    assert "JOINED" in capsys.readouterr().out


def test_a_later_campaign_never_overwrites_an_earlier_archive(tmp_path):
    """Non-negotiable second half of the criterion. Two campaigns land in the
    same durable root; the first one's evidence stays byte-identical."""
    durable = tmp_path / "durable"
    first_root = tmp_path / "eph-1" / "campaign"
    _write_completed_campaign(first_root)
    first_archive = campaign_archive.archive_campaign(
        first_root, archive_root=durable, campaign_id="camp-first"
    )
    first_bytes = (first_archive / "pair-1" / "nwave.json").read_text()

    second_root = tmp_path / "eph-2" / "campaign"
    _write_completed_campaign(second_root)
    (second_root / "pair-1" / "nwave.json").write_text(
        _run_payload("a-completely-different-session"), encoding="utf-8"
    )
    second_archive = campaign_archive.archive_campaign(
        second_root, archive_root=durable, campaign_id="camp-second"
    )

    assert first_archive != second_archive
    assert (first_archive / "pair-1" / "nwave.json").read_text() == first_bytes
    assert len(campaign_archive.list_archives(durable)) == 2


def test_archiving_twice_under_one_id_refuses_rather_than_clobbering(tmp_path):
    """Same id twice is the clobber the criterion forbids -- and a silent
    overwrite would destroy paid evidence exactly like the wipe did."""
    durable = tmp_path / "durable"
    campaign_root = tmp_path / "eph" / "campaign"
    _write_completed_campaign(campaign_root)
    campaign_archive.archive_campaign(
        campaign_root, archive_root=durable, campaign_id="camp-x"
    )

    with pytest.raises(campaign_archive.ArchiveAlreadyExistsError):
        campaign_archive.archive_campaign(
            campaign_root, archive_root=durable, campaign_id="camp-x"
        )


def test_an_archive_root_under_the_system_temp_dir_is_refused_loud(tmp_path, fake_tmp):
    """The whole defect in one line: a "durable" root that is itself ephemeral
    is not durable. Degrade LOUD, never silently archive into the thing that
    gets wiped."""
    campaign_root = tmp_path / "eph" / "campaign"
    _write_completed_campaign(campaign_root)
    ephemeral_root = fake_tmp / "nwave-k4-not-durable"

    with pytest.raises(campaign_archive.EphemeralArchiveRootError) as excinfo:
        campaign_archive.archive_campaign(campaign_root, archive_root=ephemeral_root)

    message = str(excinfo.value)
    assert "WHAT:" in message and "WHY:" in message and "HOW:" in message


def test_the_manifest_detects_a_corrupted_archived_file(tmp_path):
    """An archive nobody can verify is a designation, not evidence."""
    durable = tmp_path / "durable"
    campaign_root = tmp_path / "eph" / "campaign"
    _write_completed_campaign(campaign_root)
    archived = campaign_archive.archive_campaign(
        campaign_root, archive_root=durable, campaign_id="camp-v"
    )

    assert campaign_archive.verify_archive(archived) == []

    (archived / "pair-1" / "nwave.json").write_text("{}", encoding="utf-8")

    problems = campaign_archive.verify_archive(archived)
    assert any("pair-1/nwave.json" in problem for problem in problems)


def test_the_archive_skips_fat_workspaces_and_says_so_in_the_manifest(tmp_path):
    """Archiving whole git clones and venvs would make the step so expensive
    it gets switched off -- which is how the previous marker died. The archive
    carries the SCORING evidence and names, in the manifest, what it left
    behind and why."""
    durable = tmp_path / "durable"
    campaign_root = tmp_path / "eph" / "campaign"
    _write_completed_campaign(campaign_root)

    archived = campaign_archive.archive_campaign(
        campaign_root, archive_root=durable, campaign_id="camp-s"
    )

    manifest = json.loads((archived / "MANIFEST.json").read_text())
    assert not (archived / "pair-1" / "nwave" / ".git").exists()
    assert any(
        entry["path"] == "pair-1/nwave" and entry["reason"]
        for entry in manifest["skipped"]
    )
    assert {entry["path"] for entry in manifest["files"]} >= {
        "campaign.json",
        "pair-1/nwave.json",
        "pair-1/control.json",
        "pair-1/nwave.setup.json",
    }


def test_the_campaign_run_archives_without_anyone_remembering_to(
    tmp_path, monkeypatch, capsys
):
    """GDP-4/GDP-7: archiving is a STEP of the harness, not a note in a
    registry. `paired_campaign.main` must land durable evidence on its own,
    with no extra flag and no operator memory involved -- the ARCHIVE REQUIRED
    marker proved that a reminder is not a step.

    Everything paid-for is stubbed: no auth, no model call, no network. What
    is observed is the archive, which is the whole point.
    """
    out = tmp_path / "eph" / "campaign"
    durable = tmp_path / "durable"
    monkeypatch.setenv(campaign_archive.ARCHIVE_ROOT_ENV_VAR, str(durable))

    spec = {
        "task": "add recurring maintenance windows",
        "arms": {
            "control": {"argv": ["echo"]},
            "nwave": {"argv": ["echo"]},
        },
    }
    spec_path = tmp_path / "arms.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    monkeypatch.setattr(paired_campaign, "_auth_is_live", lambda: (True, ""))
    monkeypatch.setattr(paired_campaign, "_attested_trunk", lambda: "deadbeef")

    def _fake_setup(arm, pair_dir):
        (pair_dir / f"{arm.name}.setup.json").write_text(
            json.dumps({"ok": True, "seconds": 0.1, "steps": []}), encoding="utf-8"
        )
        return True, 0.1

    def _fake_delivery(arm, task, pair_dir, timeout):
        (pair_dir / f"{arm.name}.json").write_text(
            _run_payload(f"session-{arm.name}"), encoding="utf-8"
        )
        (pair_dir / f"{arm.name}.err").write_text("", encoding="utf-8")
        return True

    monkeypatch.setattr(paired_campaign, "_run_pair_setup", _fake_setup)
    monkeypatch.setattr(paired_campaign, "_run_delivery", _fake_delivery)

    exit_code = paired_campaign.main(
        ["--arms", str(spec_path), "--pairs", "1", "--out", str(out)]
    )

    assert exit_code == 0
    archives = campaign_archive.list_archives(durable)
    assert len(archives) == 1, (
        "the campaign run itself must leave exactly one durable archive behind"
    )
    assert (archives[0] / "pair-1" / "nwave.json").exists()
    assert str(archives[0]) in capsys.readouterr().out, (
        "the durable path must be printed: an archive nobody is told about is "
        "not findable evidence"
    )
