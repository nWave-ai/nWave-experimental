"""`des state --repo-root <a ~6000-character path>` refuses; it never crashes.

ADR-DES-003 §4: an unresolvable root is the class-A `InvalidRepositoryRoot`
refusal, 0 turns, WHAT / WHY / HOW.  A path longer than PATH_MAX on every
supported platform (1024 on darwin, 4096 on Linux) made the filesystem raise
ENAMETOOLONG out of the root check, and the orchestrator read an OSError
traceback instead of a closed block.
"""

from __future__ import annotations

from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    asked,
    block,
    nexts,
)


def too_long_root(anchor: Path) -> Path:
    """An absolute path of about 6000 characters whose every component is legal.

    Each component stays under NAME_MAX, so the only thing the filesystem can
    object to is the length of the whole name.
    """
    path = anchor
    while len(str(path)) < 6000:
        path = path / ("d" * 200)
    return path


def test_state_refuses_a_root_path_too_long_to_resolve(step, tmp_path, turns):
    raw = too_long_root(tmp_path)
    assert 5900 <= len(str(raw)) <= 6300

    _code, stdout, stderr = step("state", "--repo-root", str(raw))

    assert "Traceback" not in stdout + stderr
    assert "OSError" not in stdout + stderr
    rows = block(stdout)
    assert rows["DELIVERY-OUTCOME"] == "Refusal"
    assert rows["WHAT"] == "InvalidRepositoryRoot"
    assert rows["WHY"] == (
        f"the --repo-root path of {len(str(raw))} characters is too long to "
        "resolve: the filesystem refused the name as too long"
    )
    assert (
        rows["HOW"]
        == "pass the physical repository root as a path the filesystem can resolve"
    )
    assert rows["TURNS-BOUGHT"] == "0"
    assert nexts(stdout) == ["des state --repo-root <root> -- after the HOW above"]
    # The raw path is never echoed: no multi-kilobyte terminal line.
    assert str(raw) not in stdout + stderr
    assert all(len(line) < 1000 for line in stdout.splitlines())
    assert asked(turns) == []
