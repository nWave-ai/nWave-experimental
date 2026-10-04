"""Public boundary for the local reading view of a completed wave.

The real ``des`` commands construct the authority and freeze documentation
density. The host attests whole-wave completion by invoking the public
``des wave-entry --complete`` port with captured terminals. This oracle observes
that port's files and output. A separate installed-host smoke must establish
that an actual host invokes it at the right time.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
PYTHON = Path(sys.executable)
INSTALLER = ROOT / "scripts" / "install" / "install_nwave.py"


def _environment(home: Path) -> dict[str, str]:
    return os.environ.copy() | {
        "NWAVE_AGENTS_HOME": str(home),
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}",
    }


def _run(
    root: Path, environment: dict[str, str], *args: str, input: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PYTHON), "-P", "-m", "des.cli", *args],
        cwd=root,
        env=environment,
        input=input,
        text=True,
        capture_output=True,
        check=False,
    )


def _complete(
    root: Path,
    environment: dict[str, str],
    wave: str,
    entry_capture: Path,
    *constructor_captures: Path,
) -> subprocess.CompletedProcess[str]:
    arguments = [
        "wave-entry",
        "--repo-root",
        str(root),
        "--wave",
        wave,
        "--complete",
        "--entry-result",
        str(entry_capture),
    ]
    for capture in constructor_captures:
        arguments.extend(("--constructor-result", str(capture)))
    return _run(root, environment, *arguments)


def _capture(path: Path, result: subprocess.CompletedProcess[str]) -> Path:
    path.write_text(result.stdout, encoding="utf-8")
    return path


def _repository(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
    return path


def _config(home: Path, density: str, prompt: str) -> None:
    location = home / ".nwave" / "config.json"
    location.parent.mkdir(parents=True, exist_ok=True)
    location.write_text(
        json.dumps({"documentation": {"density": density, "expansion_prompt": prompt}}),
        encoding="utf-8",
    )


def _discuss_input() -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "request": "Let a reader choose a local account color.",
            "outcomes": ["The reader can choose and verify an account color."],
            "scope": {
                "in_scope": ["Account color selection."],
                "out_of_scope": {
                    "applicability": "not_applicable",
                    "reason": "No exclusions are needed for this brief.",
                    "items": [],
                },
            },
            "decisions": ["Keep account color selection in the account boundary."],
            "values": [
                {
                    "observation": "The reader can choose an account color.",
                    "dependencies": [],
                }
            ],
        }
    )


def _construct_discuss(
    root: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return _run(
        root,
        environment,
        "discuss",
        "--repo-root",
        str(root),
        "--project",
        "--input",
        "-",
        input=_discuss_input(),
    )


@pytest.mark.parametrize(
    ("density", "prompt"),
    [("full", "always-skip"), ("lean", "always-expand")],
)
def test_density_is_frozen_independently_of_explanation(
    tmp_path: Path, density: str, prompt: str
) -> None:
    """The wave's view choice cannot be inferred from its explanation mode."""
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, density, prompt)

    entry = _run(
        root,
        _environment(home),
        "wave-entry",
        "--repo-root",
        str(root),
        "--wave",
        "discuss",
    )
    terminal = entry.stdout + entry.stderr

    assert entry.returncode == 0, (
        "WHAT: a legal density preference failed at wave entry; WHY: the wave "
        "must carry the user's view choice to completion; HOW: resolve both "
        f"documentation fields independently (terminal={terminal!r})."
    )
    density_rows = [
        line
        for line in terminal.splitlines()
        if line.startswith("WAVE-DOCUMENTATION-DENSITY:")
    ]
    assert density_rows == [f"WAVE-DOCUMENTATION-DENSITY: {density}"], (
        "WHAT: the resolved density is absent from the public wave-entry carrier; "
        "WHY: the host cannot know whether to render a local view after the wave; "
        f"HOW: emit the frozen {density!r} density separately from the expansion offer "
        f"(rows={density_rows!r})."
    )
    provenance_rows = [
        line
        for line in terminal.splitlines()
        if line.startswith("WAVE-DOCUMENTATION-PROVENANCE:")
    ]
    assert provenance_rows == ["WAVE-DOCUMENTATION-PROVENANCE: explicit_override"], (
        "WHAT: density lacks one entry-time provenance row; WHY: the host must "
        "carry the resolved preference without rereading configuration at wave "
        "end; HOW: emit the actual cascade provenance once beside density "
        f"(rows={provenance_rows!r})."
    )
    assert f"WAVE-END-OFFER-INTERNAL-MODE: {prompt}" in terminal, (
        "WHAT: the explanation choice changed or disappeared with density; WHY: "
        "optional explanation and local view are separate user choices; HOW: "
        f"retain the selected {prompt!r} expansion mode (terminal={terminal!r})."
    )


def test_completed_full_density_wave_renders_the_des_document_as_an_adjacent_local_view(
    tmp_path: Path,
) -> None:
    """The renderer consumes the actual DES document and preserves its source."""
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)

    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    assert (
        entry.returncode == 0 and "WAVE-DOCUMENTATION-DENSITY: full" in entry.stdout
    ), (
        "WHAT: full density was not frozen at wave entry; WHY: the later local view "
        "must follow the selected preference; HOW: emit a successful full density "
        f"carrier (stdout={entry.stdout!r}, stderr={entry.stderr!r})."
    )

    constructed = _construct_discuss(root, environment)
    assert constructed.returncode == 0, (
        "WHAT: DES did not construct the authoritative DISCUSS document; WHY: a "
        "local view must come from a real completed constructor's output; HOW: "
        f"repair the public discuss construction (stdout={constructed.stdout!r}, "
        f"stderr={constructed.stderr!r})."
    )
    documents = [
        line.removeprefix("DOCUMENT: ").split("#", 1)[0]
        for line in constructed.stdout.splitlines()
        if line.startswith("DOCUMENT: ")
    ]
    assert len(documents) == 1, (
        "WHAT: DES did not identify exactly one authoritative document; WHY: the "
        "view must follow the constructor's actual document rather than a guessed "
        f"path; HOW: emit one DOCUMENT row (stdout={constructed.stdout!r})."
    )
    source = root / documents[0]
    assert source.is_file() and source.suffix == ".md", (
        "WHAT: the DOCUMENT row does not identify a real Markdown authority; "
        "WHY: the renderer must use the DES document; HOW: return an existing "
        f"repository-relative Markdown path (row={documents[0]!r})."
    )
    original = source.read_bytes()
    view = source.with_suffix(".html")
    assert not view.exists(), (
        "WHAT: a view existed before the renderer ran; WHY: the test must observe "
        "a new projection of this DES document; HOW: start from a clean local view."
    )

    completed = _complete(
        root,
        environment,
        "discuss",
        _capture(tmp_path / "entry.txt", entry),
        _capture(tmp_path / "constructor.txt", constructed),
    )
    assert completed.returncode == 0 and view.is_file(), (
        "WHAT: completed full-density wave did not produce an adjacent local "
        "view; WHY: the wave promises a readable projection of its DES authority; "
        "HOW: consume captured Success terminals in des wave-entry --complete "
        f"and invoke the packaged renderer (stdout={completed.stdout!r}, "
        f"stderr={completed.stderr!r})."
    )
    page = view.read_text(encoding="utf-8")
    assert (
        "The reader can choose an account color." in page and "nwave-brand" in page
    ), (
        "WHAT: the local page lacks DES content or nWave styling; WHY: it must "
        "be a readable projection of the actual authority; HOW: render the "
        "source through the packaged nWave renderer."
    )
    assert source.read_bytes() == original, (
        "WHAT: rendering changed the authoritative Markdown; WHY: HTML is only "
        "a local reading view; HOW: leave the DES source unchanged."
    )
    assert documents[0] in completed.stdout and str(view) in completed.stdout, (
        "WHAT: completion did not report both the authoritative source and local "
        "view; WHY: the reader must identify the view's source; HOW: report the "
        f"DES locator and generated view path (stdout={completed.stdout!r})."
    )


def test_completed_lean_wave_keeps_its_authority_without_a_local_view(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "lean", "always-expand")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    constructed = _construct_discuss(root, environment)
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: lean fixture could not reach a real DES authority; WHY: the "
        "completion observation needs a successful constructor; HOW: retain "
        f"the public discuss path (entry={entry.stdout!r}, step={constructed.stdout!r})."
    )
    before = source.read_bytes()
    result = _complete(
        root,
        environment,
        "discuss",
        _capture(tmp_path / "entry.txt", entry),
        _capture(tmp_path / "step.txt", constructed),
    )
    assert result.returncode == 0 and source.read_bytes() == before, (
        "WHAT: lean completion failed or changed its DES authority; WHY: lean "
        "retains the handoff without a generated view; HOW: finish without "
        f"mutating the source (terminal={result.stdout + result.stderr!r})."
    )
    assert not source.with_suffix(".html").exists(), (
        "WHAT: lean completion generated local HTML; WHY: only full density "
        "requests the automatic view; HOW: keep lean as a document handoff."
    )


@pytest.mark.parametrize("failure", ("Refusal", "Indeterminate"))
def test_non_success_constructor_capture_cannot_render(
    tmp_path: Path, failure: str
) -> None:
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    constructed = _construct_discuss(root, environment)
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: refusal fixture lacks a real DES document; WHY: a non-Success "
        "capture must be distinguished from an unavailable source; HOW: "
        "construct the real source before changing only the captured outcome."
    )
    refused = constructed.stdout.replace(
        "DELIVERY-OUTCOME: Success", f"DELIVERY-OUTCOME: {failure}", 1
    )
    assert refused != constructed.stdout, (
        "WHAT: constructor terminal has no Success outcome to replace; WHY: "
        "the refusal probe would otherwise be a second successful capture; "
        "HOW: retain the real terminal outcome in the fixture."
    )
    step_path = tmp_path / "step.txt"
    step_path.write_text(refused, encoding="utf-8")
    result = _complete(
        root, environment, "discuss", _capture(tmp_path / "entry.txt", entry), step_path
    )
    assert result.returncode != 0 and "DELIVERY-OUTCOME: Refusal" in result.stdout, (
        "WHAT: a non-Success constructor was accepted for rendering; WHY: "
        "a stopped or indeterminate wave has no completed authority to project; "
        f"HOW: refuse completion before writes (terminal={result.stdout + result.stderr!r})."
    )
    assert not source.with_suffix(".html").exists(), (
        "WHAT: a stopped or indeterminate capture generated HTML; WHY: only "
        "successful whole-wave authority may be projected; HOW: perform all "
        "capture checks before invoking the renderer."
    )


def test_missing_capture_is_indeterminate_without_a_view(tmp_path: Path) -> None:
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    constructed = _construct_discuss(root, environment)
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: missing-capture probe lacks a real completed DES source; WHY: "
        "capture absence must be distinguished from document absence; HOW: "
        "construct the source before withholding its terminal capture."
    )
    missing = tmp_path / "missing-step.txt"
    result = _complete(
        root, environment, "discuss", _capture(tmp_path / "entry.txt", entry), missing
    )
    terminal = result.stdout + result.stderr
    assert result.returncode != 0 and "DELIVERY-OUTCOME: Indeterminate" in terminal, (
        "WHAT: missing constructor capture was treated as success or refusal; "
        "WHY: the port cannot tell whether that step completed; HOW: report "
        f"Indeterminate and name the missing capture (terminal={terminal!r})."
    )
    assert str(missing) in terminal and not source.with_suffix(".html").exists(), (
        "WHAT: capture absence lost its path or produced HTML; WHY: the user "
        "needs the missing evidence and no unearned view; HOW: name the path "
        "and stop before rendering."
    )


def test_omitted_constructor_capture_is_indeterminate_without_a_view(
    tmp_path: Path,
) -> None:
    """A real document on disk cannot substitute for the missing step terminal."""
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    constructed = _construct_discuss(root, environment)
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: omitted-capture probe lacks a successful real DES constructor; "
        "WHY: this case must distinguish missing evidence from missing work; "
        "HOW: construct the DISCUSS authority before omitting only the "
        f"--constructor-result flag (entry={entry.stdout!r}, step={constructed.stdout!r})."
    )
    result = _complete(
        root, environment, "discuss", _capture(tmp_path / "entry.txt", entry)
    )
    terminal = result.stdout + result.stderr
    assert result.returncode != 0 and "DELIVERY-OUTCOME: Indeterminate" in terminal, (
        "WHAT: full DISCUSS completion accepted an omitted constructor capture; "
        "WHY: a document's presence cannot prove the selected wave completed; "
        f"HOW: require its successful captured terminal (terminal={terminal!r})."
    )
    assert all(marker in terminal for marker in ("WHAT:", "WHY:", "HOW:")), (
        "WHAT: omitted-capture result lacks a concrete recovery; WHY: the host "
        "needs to know which evidence to supply; HOW: report WHAT/WHY/HOW for "
        f"the missing constructor result (terminal={terminal!r})."
    )
    assert not source.with_suffix(".html").exists(), (
        "WHAT: omitted constructor capture generated HTML; WHY: the wave's "
        "successful authority was not attested to the completion port; HOW: "
        "stop before rendering when --constructor-result is absent."
    )


def test_design_heading_locator_selects_markdown_source_but_keeps_report_locator(
    tmp_path: Path,
) -> None:
    """A controlled capture probes fragment handling; it is not DESIGN wiring proof."""
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "design"
    )
    constructed = _construct_discuss(root, environment)
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: fragment probe lacks a real DES Markdown source; WHY: only the "
        "locator fragment should be controlled here; HOW: construct a real "
        "DES document before passing the captured boundary value."
    )
    locator = "docs/product/brief.md#Observations"
    capture = constructed.stdout.replace(
        "DOCUMENT: docs/product/brief.md", f"DOCUMENT: {locator}", 1
    )
    assert capture != constructed.stdout, (
        "WHAT: controlled heading locator was not placed in the capture; WHY: "
        "the test would otherwise miss fragment normalization; HOW: change "
        "the real DOCUMENT row to a heading-bearing locator."
    )
    step_path = tmp_path / "design-step.txt"
    step_path.write_text(capture, encoding="utf-8")
    result = _complete(
        root, environment, "design", _capture(tmp_path / "entry.txt", entry), step_path
    )
    assert result.returncode == 0 and source.with_suffix(".html").is_file(), (
        "WHAT: DESIGN fragment was used as part of the filesystem source or no "
        "view was rendered; WHY: the fragment identifies a section, not another "
        f"file; HOW: render the Markdown before # (terminal={result.stdout + result.stderr!r})."
    )
    assert locator in result.stdout, (
        "WHAT: completion dropped the DESIGN heading from its report; WHY: the "
        "handoff must retain the exact authority locator; HOW: report the "
        f"original PATH.md#Heading (stdout={result.stdout!r})."
    )


@pytest.mark.parametrize(
    "unsafe_locator", ("../outside.md", "docs/product/../brief.md")
)
def test_unsafe_document_locator_refuses_before_rendering(
    tmp_path: Path, unsafe_locator: str
) -> None:
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    constructed = _construct_discuss(root, environment)
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: unsafe-path probe lacks real DES context; WHY: the source path "
        "must be the only controlled variable; HOW: construct the ordinary "
        "document first."
    )
    capture = constructed.stdout.replace(
        "DOCUMENT: docs/product/brief.md", f"DOCUMENT: {unsafe_locator}", 1
    )
    assert capture != constructed.stdout, (
        "WHAT: unsafe locator was not inserted into the captured DOCUMENT row; "
        "WHY: the probe would exercise the safe path; HOW: preserve the real "
        "terminal and vary only the locator."
    )
    step_path = tmp_path / "unsafe.txt"
    step_path.write_text(capture, encoding="utf-8")
    result = _complete(
        root, environment, "discuss", _capture(tmp_path / "entry.txt", entry), step_path
    )
    terminal = result.stdout + result.stderr
    assert result.returncode != 0 and "DELIVERY-OUTCOME: Refusal" in terminal, (
        "WHAT: unsafe source locator was accepted; WHY: completion must not "
        "read outside or traverse a repository path; HOW: refuse before "
        f"rendering (locator={unsafe_locator!r}, terminal={terminal!r})."
    )
    assert all(marker in terminal for marker in ("WHAT:", "WHY:", "HOW:")), (
        "WHAT: unsafe-source refusal lacks a repair path; WHY: the user needs "
        f"the cause and safe retry; HOW: report WHAT/WHY/HOW (terminal={terminal!r})."
    )
    assert not source.with_suffix(".html").exists(), (
        "WHAT: unsafe source produced a view; WHY: preflight refusal must write "
        "nothing; HOW: validate every DOCUMENT path before the renderer runs."
    )


def test_unrelated_html_is_preserved_and_refused(tmp_path: Path) -> None:
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    constructed = _construct_discuss(root, environment)
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: HTML collision probe lacks a real DES source; WHY: the view "
        "destination must derive from a real authority; HOW: construct it first."
    )
    view = source.with_suffix(".html")
    unrelated = b"<html><body>My own page</body></html>"
    view.write_bytes(unrelated)
    result = _complete(
        root,
        environment,
        "discuss",
        _capture(tmp_path / "entry.txt", entry),
        _capture(tmp_path / "step.txt", constructed),
    )
    terminal = result.stdout + result.stderr
    assert result.returncode != 0 and "DELIVERY-OUTCOME: Refusal" in terminal, (
        "WHAT: unrelated HTML destination was accepted; WHY: the view must "
        "not overwrite a user's page; HOW: refuse that destination before "
        f"rendering (terminal={terminal!r})."
    )
    assert view.read_bytes() == unrelated, (
        "WHAT: unrelated HTML was overwritten; WHY: completion may regenerate "
        "only its own projection of the same source; HOW: preserve the file "
        "and report a safe destination repair."
    )


def test_symlinked_des_source_is_refused_without_a_view(tmp_path: Path) -> None:
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    constructed = _construct_discuss(root, environment)
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: symlink-source probe lacks a real DES document; WHY: the unsafe "
        "filesystem state must be the only changed input; HOW: construct the "
        "authority through des discuss first."
    )
    real_source = source.with_name("original-brief.md")
    source.rename(real_source)
    source.symlink_to(real_source.name)
    original = real_source.read_bytes()

    result = _complete(
        root,
        environment,
        "discuss",
        _capture(tmp_path / "entry.txt", entry),
        _capture(tmp_path / "step.txt", constructed),
    )
    terminal = result.stdout + result.stderr
    assert result.returncode != 0 and "DELIVERY-OUTCOME: Refusal" in terminal, (
        "WHAT: completion accepted a symlink at the DES Markdown locator; WHY: "
        "the recorded source could redirect before rendering; HOW: refuse the "
        f"symlinked path (terminal={terminal!r})."
    )
    assert source.is_symlink() and real_source.read_bytes() == original, (
        "WHAT: refusal changed the symlink target or source bytes; WHY: source "
        "preflight must not mutate authority; HOW: stop before rendering."
    )
    assert not source.with_suffix(".html").exists(), (
        "WHAT: a symlinked source produced HTML; WHY: unsafe source refusal "
        "must precede all view writes; HOW: preflight the real path first."
    )


def test_symlinked_html_destination_is_refused_without_following_it(
    tmp_path: Path,
) -> None:
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    constructed = _construct_discuss(root, environment)
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: symlink-destination probe lacks a real DES source; WHY: the "
        "destination is meaningful only beside that authority; HOW: construct "
        "the ordinary brief before introducing the symlink."
    )
    target = tmp_path / "protected.html"
    protected = b"<html><body>Protected local page</body></html>"
    target.write_bytes(protected)
    view = source.with_suffix(".html")
    view.symlink_to(target)

    result = _complete(
        root,
        environment,
        "discuss",
        _capture(tmp_path / "entry.txt", entry),
        _capture(tmp_path / "step.txt", constructed),
    )
    terminal = result.stdout + result.stderr
    assert result.returncode != 0 and "DELIVERY-OUTCOME: Refusal" in terminal, (
        "WHAT: completion accepted a symlinked HTML destination; WHY: "
        "rendering could overwrite an unrelated target; HOW: refuse the "
        f"destination before writes (terminal={terminal!r})."
    )
    assert view.is_symlink() and target.read_bytes() == protected, (
        "WHAT: refusal followed or changed the HTML symlink; WHY: the linked "
        "page belongs to the user; HOW: preserve both link and target."
    )


def test_later_collision_preflights_entire_document_batch_before_any_html_write(
    tmp_path: Path,
) -> None:
    """The second locator is a controlled boundary fixture over a real first DES source."""
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    constructed = _construct_discuss(root, environment)
    first = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and first.is_file(), (
        "WHAT: batch probe lacks its real first DES document; WHY: only the "
        "second captured locator is controlled; HOW: construct DISCUSS first."
    )
    second = first.with_name("second-brief.md")
    second.write_bytes(first.read_bytes())
    collision = second.with_suffix(".html")
    unrelated = b"<html><body>Another local page</body></html>"
    collision.write_bytes(unrelated)
    captured = constructed.stdout.replace(
        "DOCUMENT: docs/product/brief.md",
        "DOCUMENT: docs/product/brief.md\nDOCUMENT: docs/product/second-brief.md",
        1,
    )
    assert captured != constructed.stdout and not first.with_suffix(".html").exists(), (
        "WHAT: batch probe did not declare two documents with a clean first "
        "view; WHY: it cannot detect an early first render; HOW: supply both "
        "DOCUMENT locators and start without the first HTML."
    )
    capture_path = tmp_path / "two-documents.txt"
    capture_path.write_text(captured, encoding="utf-8")

    result = _complete(
        root,
        environment,
        "discuss",
        _capture(tmp_path / "entry.txt", entry),
        capture_path,
    )
    terminal = result.stdout + result.stderr
    assert result.returncode != 0 and "DELIVERY-OUTCOME: Refusal" in terminal, (
        "WHAT: completion accepted a batch whose second HTML path collides; "
        "WHY: all destinations need preflight before any rendering; HOW: "
        f"refuse the whole batch (terminal={terminal!r})."
    )
    assert (
        not first.with_suffix(".html").exists() and collision.read_bytes() == unrelated
    ), (
        "WHAT: a batch refusal wrote first HTML or changed the second page; "
        "WHY: a later collision must stop the entire completion before writes; "
        "HOW: validate every source and destination before rendering any view."
    )


def test_same_source_view_is_regenerated_from_authority(tmp_path: Path) -> None:
    root = _repository(tmp_path / "project")
    home = tmp_path / "home"
    _config(home, "full", "always-skip")
    environment = _environment(home)
    entry = _run(
        root, environment, "wave-entry", "--repo-root", str(root), "--wave", "discuss"
    )
    constructed = _construct_discuss(root, environment)
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: regeneration probe lacks a real DES source; WHY: the generated "
        "page must retain its source identity; HOW: construct the document first."
    )
    entry_capture = _capture(tmp_path / "entry.txt", entry)
    step_capture = _capture(tmp_path / "step.txt", constructed)
    first = _complete(root, environment, "discuss", entry_capture, step_capture)
    view = source.with_suffix(".html")
    assert first.returncode == 0 and view.is_file(), (
        "WHAT: first completed wave made no view; WHY: same-source regeneration "
        f"needs a real projection (terminal={first.stdout + first.stderr!r})."
    )
    original_page = view.read_text(encoding="utf-8")
    stale = original_page.replace(
        "The reader can choose an account color.", "Stale local reading text", 1
    )
    assert stale != original_page, (
        "WHAT: source text was absent from the first view; WHY: a stale-page "
        "probe would otherwise have no changed observation; HOW: project the "
        "real DES sentence."
    )
    view.write_text(stale, encoding="utf-8")
    second = _complete(root, environment, "discuss", entry_capture, step_capture)
    assert (
        second.returncode == 0 and view.read_text(encoding="utf-8") == original_page
    ), (
        "WHAT: same-source nWave projection stayed stale or was refused; WHY: "
        "completed full density must refresh the local view from its authority; "
        f"HOW: permit and rerender matching source identity (terminal={second.stdout + second.stderr!r})."
    )


@pytest.mark.wiring_e2e
def test_isolated_installed_completion_renders_offline_branded_des_view(
    tmp_path: Path,
) -> None:
    """One real installer, installed DES runtime, constructor, and completion port."""
    home = tmp_path / "isolated-home"
    home.mkdir()
    install_environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(home),
        "NWAVE_AGENTS_HOME": str(home),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "CODEX_HOME": str(home / ".codex"),
        "OPENCODE_CONFIG_DIR": str(home / ".config" / "opencode"),
    }
    installed = subprocess.run(
        [str(PYTHON), str(INSTALLER), "--platform", "claude-code"],
        cwd=ROOT,
        env=install_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )
    assert installed.returncode == 0, (
        "WHAT: isolated public install failed; WHY: the view must be tested "
        "from the runtime users actually install; HOW: repair the installer "
        f"or its isolated inputs (stdout={installed.stdout[-4000:]!r}, "
        f"stderr={installed.stderr[-4000:]!r})."
    )
    runtime_marker = home / ".nwave" / "active-runtime"
    assert runtime_marker.is_file(), (
        "WHAT: installer did not record its active DES runtime; WHY: the test "
        "cannot distinguish installed code from the checkout; HOW: persist "
        "the installed runtime path."
    )
    runtime = Path(runtime_marker.read_text(encoding="utf-8").strip())
    assert (runtime / "des").is_dir(), (
        "WHAT: active-runtime does not contain DES; WHY: completion could "
        "borrow source code instead of installed code; HOW: install the DES "
        f"package at the recorded runtime (runtime={runtime})."
    )
    environment = install_environment | {"PYTHONPATH": str(runtime)}
    root = _repository(tmp_path / "project")
    _config(home, "full", "always-skip")

    def installed_des(
        *arguments: str, input: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(PYTHON), "-P", "-m", "des.cli", *arguments],
            cwd=root,
            env=environment,
            input=input,
            capture_output=True,
            text=True,
            check=False,
        )

    origin = subprocess.run(
        [str(PYTHON), "-P", "-c", "import des; print(des.__file__)"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert origin.returncode == 0 and Path(origin.stdout.strip()).is_relative_to(
        runtime
    ), (
        "WHAT: DES imported outside the active installed runtime; WHY: a "
        "checkout pass would hide missing packaged assets; HOW: run with only "
        f"the installed runtime on PYTHONPATH (origin={origin.stdout!r}, "
        f"stderr={origin.stderr!r})."
    )
    entry = installed_des("wave-entry", "--repo-root", str(root), "--wave", "discuss")
    constructed = installed_des(
        "discuss",
        "--repo-root",
        str(root),
        "--project",
        "--input",
        "-",
        input=_discuss_input(),
    )
    source = root / "docs/product/brief.md"
    assert entry.returncode == constructed.returncode == 0 and source.is_file(), (
        "WHAT: installed DES did not produce its entry and Markdown authority; "
        "WHY: the installed completion port needs actual Success captures; "
        f"HOW: repair installed DES construction (entry={entry.stdout + entry.stderr!r}, "
        f"step={constructed.stdout + constructed.stderr!r})."
    )
    entry_capture = _capture(tmp_path / "installed-entry.txt", entry)
    step_capture = _capture(tmp_path / "installed-step.txt", constructed)
    completed = installed_des(
        "wave-entry",
        "--repo-root",
        str(root),
        "--wave",
        "discuss",
        "--complete",
        "--entry-result",
        str(entry_capture),
        "--constructor-result",
        str(step_capture),
    )
    view = source.with_suffix(".html")
    assert completed.returncode == 0 and view.is_file(), (
        "WHAT: installed full-density completion did not generate local HTML; "
        "WHY: a source-checkout renderer may have assets absent from the "
        "installed runtime; HOW: package the renderer's brand assets and "
        f"complete through installed DES (terminal={completed.stdout + completed.stderr!r})."
    )
    page = view.read_text(encoding="utf-8")
    for required in (
        '<meta name="nwave-brand"',
        '<div class="provenance">',
        "data:image/svg+xml;base64,",
        "The reader can choose an account color.",
    ):
        assert required in page, (
            f"WHAT: installed HTML lacks {required!r}; WHY: the local view "
            "must carry offline nWave branding, source provenance, and real "
            "DES content; HOW: resolve those assets from the installed runtime "
            f"(view={view})."
        )
