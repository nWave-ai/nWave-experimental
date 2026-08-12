"""The K4 probe workspace (`<root>/probe-nwave`) must be removed after a PASS
engagement check, and ONLY after a PASS -- otherwise the leftover clone under
`<root>/probe-nwave` sits there to be picked up later by an unrelated agent
instead of the measured campaign arm (observed on the installed K4 run).

On `broke` or `absent`-with-detail, the failure messages `main` prints point a
reader at `<root>/probe-nwave` for the HOW; deleting it there would make that
pointer a lie, so cleanup must not fire on those verdicts.

Run: uv run pytest -q tests/scripts/analysis/test_k4_probe_workspace_cleanup.py
"""

from __future__ import annotations

import pytest

from scripts.analysis.k4 import preflight


def _make_probe(root):
    probe = root / "probe-nwave"
    probe.mkdir(parents=True)
    (probe / "marker").write_text("probe contents")
    return probe


def _make_sibling_sentinel(root):
    sibling = root / "sibling-sentinel"
    sibling.mkdir(parents=True)
    (sibling / "keep").write_text("must survive cleanup")
    return sibling


def test_pass_removes_exact_probe_and_leaves_sibling_untouched(tmp_path):
    probe = _make_probe(tmp_path)
    sibling = _make_sibling_sentinel(tmp_path)

    removed = preflight.cleanup_probe_workspace(tmp_path, "absent", [])

    assert removed is True
    assert not probe.exists()
    assert sibling.exists()
    assert (sibling / "keep").read_text() == "must survive cleanup"


@pytest.mark.parametrize(
    "verdict,detail",
    [
        pytest.param("broke", ["`git clone` exited 128", "fatal: ..."], id="broke"),
        pytest.param(
            "absent", ["no CLAUDE.md in the workspace"], id="absent-with-detail"
        ),
    ],
)
def test_failure_verdicts_preserve_the_probe(tmp_path, verdict, detail):
    probe = _make_probe(tmp_path)

    removed = preflight.cleanup_probe_workspace(tmp_path, verdict, detail)

    assert removed is False
    assert probe.exists()
    assert (probe / "marker").read_text() == "probe contents"


def test_main_removes_probe_and_still_writes_arms_json_on_pass(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    probe = _make_probe(root)
    sibling = _make_sibling_sentinel(root)

    monkeypatch.setattr(
        preflight, "build_arm_runtime", lambda root, checkout: root / "venv-stub"
    )
    monkeypatch.setattr(
        preflight, "probe_engagement", lambda root, venv, auth_profile: ("absent", [])
    )

    task_file = tmp_path / "task.md"
    task_file.write_text("do the thing\n")

    code = preflight.main(["--root", str(root), "--task-file", str(task_file)])

    assert code == 0
    assert not probe.exists()
    assert sibling.exists()
    assert (root / "arms.json").exists()
