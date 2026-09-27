"""`des state` over a handover that is not a regular file answers, and never hangs.

ADR-DES-003 §4 class C: a substrate the software cannot read as its own handover
is `Indeterminate`, with WHAT / WHY / HOW. A FIFO is the sharp case -- opening it
for reading waits for a writer that never comes -- so the step is driven on a
worker thread and "promptly" is measured as a bounded join, not assumed.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    asked,
    block,
    nexts,
)


#: Far above any honest read of a local file, far below a hang.
PROMPT_SECONDS = 10.0

HANDOVER_REPAIR = (
    "delete .nwave/des/handover.json to re-elicit this Request from its "
    "durable authorities; the generated artifacts themselves are never removed"
)


def _make_fifo(path: Path) -> None:
    os.mkfifo(path)


def _make_directory(path: Path) -> None:
    path.mkdir()


def _make_symbolic_link(path: Path) -> None:
    target = path.parent / "elsewhere.json"
    target.write_text("{}\n")
    path.symlink_to(target)


@pytest.mark.parametrize(
    ("kind", "make"),
    [
        ("FIFO", _make_fifo),
        ("directory", _make_directory),
        ("symbolic link", _make_symbolic_link),
    ],
)
def test_state_refuses_a_handover_that_is_not_a_regular_file(
    root: Path, step, turns: Path, kind: str, make
) -> None:
    handover = root / ".nwave" / "des" / "handover.json"
    handover.parent.mkdir(parents=True)
    make(handover)

    outcome: dict[str, object] = {}

    def run() -> None:
        outcome["result"] = step("state", "--repo-root", str(root))

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(PROMPT_SECONDS)
    if worker.is_alive():
        # Release a reader blocked opening the FIFO, so the suite does not hang
        # behind the failure it just measured.
        try:
            os.close(os.open(handover, os.O_WRONLY | os.O_NONBLOCK))
        except OSError:
            pass
        worker.join(PROMPT_SECONDS)
        pytest.fail(
            f"des state did not return within {PROMPT_SECONDS}s over a {kind} handover"
        )

    code, stdout, stderr = outcome["result"]  # type: ignore[misc]
    rows = block(stdout, stderr)

    assert code != 0, stdout + stderr
    assert rows.get("DELIVERY-OUTCOME") == "Indeterminate", stdout + stderr
    assert rows.get("WHAT") == "HandoverUnavailable", stdout
    assert rows.get("WHY") == (
        f".nwave/des/handover.json is not a regular file: it is a {kind}"
    ), stdout
    assert rows.get("HOW") == HANDOVER_REPAIR, stdout
    assert rows.get("TURNS-BOUGHT") == "0", stdout
    assert nexts(stdout) == [
        f"des state --repo-root {root.resolve()} -- after the HOW above"
    ], stdout
    assert asked(turns) == []
    # Read-only: the non-regular handover is left exactly as it was found.
    assert handover.is_symlink() == (kind == "symbolic link")
    if kind == "directory":
        assert handover.is_dir() and not any(handover.iterdir())
