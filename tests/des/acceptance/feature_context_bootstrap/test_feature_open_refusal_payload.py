"""Public refusal contract for ``des feature-open`` (GDP-3 / GDP-4).

Every way of refusing to open a feature context is observed HERE, through the
same public dispatcher an operator uses -- never by reading the source for a
string.  A refusal string that exists in the module but is unreachable would
pass a source read and fail every assertion below.

The refusal paths are provoked, not enumerated from the implementation: each
parameter builds the argv that reaches one refusal, and the payload the
operator actually receives is the only thing asserted.

CONTRACT_SHAPE: unbounded-preservation -- a refusal must explain itself AND
leave the whole repository universe byte-identical.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest


# The producing tool a refusal may lawfully route the operator to. A HOW that
# names none of these is telling a human to repair an artifact by hand (GDP-4).
_PRODUCING_TOOLS = ("des feature-open", "des next", "/nw-")

# Language that hands the repair back to the operator instead of to a tool.
_MANUAL_REPAIR_PHRASES = (
    "by hand",
    "manually",
    "edit the file",
    "open the file",
)


def _tree_hashes(root: Path) -> dict[str, str]:
    """Observe every regular file beneath the repository boundary."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _make_repo(tmp_path: Path) -> Path:
    """Build the fixture repository every refusal path is provoked against."""
    (tmp_path / "existing-work").mkdir()
    (tmp_path / "existing-work" / "public_check.py").write_text(
        "assert True\n", encoding="utf-8"
    )
    (tmp_path / "loose.txt").write_text("not a directory\n", encoding="utf-8")
    owned = tmp_path / "docs" / "feature" / "already-owned" / "feature-delta.md"
    owned.parent.mkdir(parents=True)
    owned.write_bytes(b"# A judged feature document\n")
    return tmp_path


def _argv(case: str, repo: Path) -> list[str]:
    """Compose the argv that reaches exactly one refusal path."""
    base = ["feature-open", "--feature-id", "probe-context", "--repo", str(repo)]
    if case == "empty-intent":
        return [*base, "--intent", "   "]
    ok = [*base, "--intent", "A maintainer opens a context."]
    if case == "adopt-wip-without-adopt-root":
        return [*ok, "--adopt-wip"]
    if case == "adopt-root-without-adopt-wip":
        return [*ok, "--adopt-root", "existing-work"]
    if case == "adopt-root-is-repo-root":
        return [*ok, "--adopt-wip", "--adopt-root", "."]
    if case == "adopt-root-outside-repo":
        return [*ok, "--adopt-wip", "--adopt-root", "../.."]
    if case == "adopt-root-not-a-directory":
        return [*ok, "--adopt-wip", "--adopt-root", "loose.txt"]
    if case == "feature-context-conflict":
        return [
            "feature-open",
            "--feature-id",
            "already-owned",
            "--intent",
            "A maintainer starts a different discussion.",
            "--repo",
            str(repo),
        ]
    raise AssertionError(f"unmapped refusal case {case!r}")


REFUSAL_CASES = (
    "empty-intent",
    "adopt-wip-without-adopt-root",
    "adopt-root-without-adopt-wip",
    "adopt-root-is-repo-root",
    "adopt-root-outside-repo",
    "adopt-root-not-a-directory",
    "feature-context-conflict",
)


def _refuse(
    case: str, repo: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    """Provoke one refusal through the public dispatcher and read its reply.

    An uncaught exception escaping ``main`` IS the bare-traceback defect, so it
    is converted here into the assertion failure it deserves rather than an
    error the reader must decode.
    """
    from des.cli.__main__ import main

    try:
        exit_code = main(_argv(case, repo))
    except BaseException as exc:
        raise AssertionError(
            f"WHAT: refusal path {case!r} ended in an uncaught "
            f"{type(exc).__name__} instead of a payload. "
            "WHY: a traceback is a malfunction the operator must decode, not a refusal "
            "that explains itself (GDP-3). "
            "HOW: return a structured WHAT/WHY/HOW refusal from des/cli/feature_open.py "
            "instead of raising."
        ) from exc

    stdout = capsys.readouterr().out.strip().splitlines()
    assert len(stdout) == 1, (
        f"WHAT: refusal path {case!r} emitted {len(stdout)} stdout lines, not one. "
        "WHY: an operator (and any wrapping tool) needs one unambiguous refusal record. "
        "HOW: emit exactly one JSON refusal line from the command boundary."
    )
    try:
        payload = json.loads(stdout[0])
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"WHAT: refusal path {case!r} emitted non-JSON text: {stdout[0]!r}. "
            "WHY: a refusal must be machine-readable to be routed, logged, or asserted. "
            "HOW: serialize the refusal as one JSON object."
        ) from exc
    assert isinstance(payload, dict)
    return exit_code, payload


@pytest.mark.negative_at
@pytest.mark.parametrize("case", REFUSAL_CASES)
def test_no_refusal_path_ever_emits_a_bare_traceback(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every refusal reaches the operator as a payload, never as a stack trace.

    CONTRACT_SHAPE: unbounded-preservation
    Outcome anchor: DISCUSS Elevator Pitch
    """
    repo = _make_repo(tmp_path)

    exit_code, payload = _refuse(case, repo, capsys)

    assert exit_code != 0 and payload.get("event") == "FeatureContextRefused", (
        f"WHAT: refusal path {case!r} did not return a non-zero exit with a named refusal event. "
        "WHY: callers distinguish a refusal from a receipt by its event and exit status, "
        "and a silent-zero refusal would read as success (GDP-6). "
        "HOW: return exit 1 and emit event FeatureContextRefused from the command boundary."
    )


@pytest.mark.parametrize("case", REFUSAL_CASES)
def test_every_refusal_names_what_why_and_how(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A refusal states the problem, its consequence, and the repair.

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch
    """
    repo = _make_repo(tmp_path)

    _, payload = _refuse(case, repo, capsys)

    missing = [key for key in ("what", "why", "how") if not str(payload.get(key, ""))]
    assert not missing, (
        f"WHAT: refusal path {case!r} omitted {missing}. "
        "WHY: without all three an operator knows something failed but not why it matters "
        "nor what to run next, which is the GDP-3 floor. "
        "HOW: populate what, why and how on every refusal in des/cli/feature_open.py."
    )
    assert payload.get("error") and payload["error"] != payload.get("what"), (
        f"WHAT: refusal path {case!r} carries no stable error slug distinct from its prose. "
        "WHY: tools route on a stable slug while humans read the prose; collapsing them makes "
        "every wording change a breaking change. "
        "HOW: emit a kebab-case error slug alongside the human-readable what."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("case", REFUSAL_CASES)
def test_refusal_how_never_asks_the_operator_to_repair_by_hand(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The repair is a command to run, not manual labour delegated to a human.

    CONTRACT_SHAPE: unbounded-preservation
    Outcome anchor: DISCUSS Elevator Pitch
    """
    repo = _make_repo(tmp_path)

    _, payload = _refuse(case, repo, capsys)

    how = str(payload.get("how", ""))
    assert any(tool in how for tool in _PRODUCING_TOOLS), (
        f"WHAT: refusal path {case!r} offers a HOW that names no producing tool: {how!r}. "
        "WHY: a repair the operator must improvise puts the cost of the gate on the human "
        "instead of on the system (GDP-4/GDP-5). "
        f"HOW: route the repair through one of {_PRODUCING_TOOLS}."
    )
    offending = [
        phrase for phrase in _MANUAL_REPAIR_PHRASES if phrase in how.casefold()
    ]
    assert not offending, (
        f"WHAT: refusal path {case!r} instructs a manual repair via {offending}. "
        "WHY: hand-editing an artifact that a tool owns reintroduces exactly the drift the "
        "producing tool exists to prevent. "
        "HOW: replace the manual instruction with the command that produces the artifact."
    )


@pytest.mark.negative_at
def test_no_command_path_raises_an_exception_the_boundary_cannot_render() -> None:
    """The completeness axis the parametrized cases above structurally cannot reach.

    Those cases prove the SEVEN KNOWN refusals behave; they say nothing about the
    eighth one someone adds next month. This reads the command module itself and
    asserts the PROPERTY -- every raise inside it is a renderable refusal -- so a
    new bare ``raise ValueError`` fails here even though no case names it.

    CONTRACT_SHAPE: unbounded-preservation
    Outcome anchor: DISCUSS Elevator Pitch
    """
    import ast

    from des.cli import feature_open

    source = Path(feature_open.__file__).read_text(encoding="utf-8")
    raised = {
        node.exc.func.id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
    }
    assert raised <= {"_Refusal"}, (
        f"WHAT: des/cli/feature_open.py raises {sorted(raised - {'_Refusal'})}, which the "
        "command boundary does not render. "
        "WHY: any exception the boundary cannot turn into a payload reaches the operator "
        "as a bare traceback, which is the defect this whole module was repaired for. "
        "HOW: raise _Refusal(error, what, why, how) instead, so the boundary renders it."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize("case", REFUSAL_CASES)
def test_refusal_never_changes_a_repository_byte(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Explaining a refusal must not cost the repository any state.

    CONTRACT_SHAPE: unbounded-preservation
    Outcome anchor: DISCUSS Elevator Pitch
    """
    repo = _make_repo(tmp_path)
    before = _tree_hashes(repo)

    _refuse(case, repo, capsys)

    assert _tree_hashes(repo) == before, (
        f"WHAT: refusal path {case!r} created or mutated repository files. "
        "WHY: a refused bootstrap that leaves partial state hands the next reader a document "
        "no lawful step produced. "
        "HOW: decide every refusal before creating directories or writing the feature document."
    )
