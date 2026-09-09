"""Public oracle: `des project --html`, the layer the human reads.

`docs/architecture/adr-ssot-document-model.md`, «Feature Brief — The Human
Layer»: «The SSOT files serve agents. The delta files serve the delivery
pipeline. Neither is designed for human consumption.»  The handover and the
typed design facts are exactly that -- machine-first -- and the human who has to
choose between an interactive and an autonomous session reads neither happily.

`docs/product/architecture/ADR-BOARD-001-shared-slice-state-projection.md` fixes
what such a page may be: «The shared slice-state model is a projection function,
never a fourth persisted store», recomputed on every read. So this step reads
the two owned facts, writes ONE html file and nothing else, and holds no state
of its own. Run it twice over an unchanged repository and the page is the same.

It carries NO new content. Every line of the page is either a label the step
terminals already use or a value read verbatim from the owned state, and the
renderer is the one that already exists -- `des.adapters.driven.rendering.
nwave_document`, with the nWave palette and its dark mode. A second renderer or
a second stylesheet would be a second answer to "what does an nWave document
look like".
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
    nexts,
    observation,
)


REQUEST = "one Request whose state a human reads before choosing how to run it"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "product_value.py"
HANDOVER = Path(".nwave") / "des" / "handover.json"


def design_facts() -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "design_facts": {
                "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": ["one opaque semantic decision"],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": [["python", "-m", "pytest", ORACLE]],
            },
        }
    }


def bound(root: Path, step) -> None:
    assert (
        step(
            "po",
            "--repo-root",
            str(root),
            answers=[accepted_values("A", "B")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
        )[0]
        == 0
    )


def test_the_page_carries_the_request_the_values_and_the_typed_facts(
    root: Path, step, tmp_path: Path, turns: Path
) -> None:
    bound(root, step)
    out = tmp_path / "projection.html"
    code, stdout, stderr = step("project", "--repo-root", str(root), "--html", str(out))
    assert code == 0, stdout + stderr
    lines = block(stdout, stderr)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["HTML"] == str(out)
    page = out.read_text()
    assert REQUEST in page
    assert observation("A") in page
    assert observation("B") in page
    assert ORACLE in page
    assert TARGET in page
    assert "object_oriented" in page
    assert "python -m pytest" in page
    # Rendered through the ONE nWave renderer: its palette and its provenance
    # banner, never a second stylesheet invented here.
    assert "--paper" in page
    assert "Projection, not source" in page
    assert str(HANDOVER) in page
    assert asked(turns) == ["nw-product-owner", "nw-solution-architect"]


def test_the_page_is_a_self_contained_offline_nwave_document(
    root: Path, step, tmp_path: Path
) -> None:
    """A person can open the project page without trusting a network origin."""
    bound(root, step)
    out = tmp_path / "projection.html"

    code, stdout, stderr = step("project", "--repo-root", str(root), "--html", str(out))

    assert code == 0, (
        "WHAT: `des project --html` did not produce a page. "
        "WHY: the offline human projection is unavailable to its user. "
        "HOW: make the public project command render the validated local brand assets.\n"
        + stdout
        + stderr
    )
    page = out.read_text(encoding="utf-8")
    brand_directory = Path(__file__).parents[4] / "nWave" / "data" / "brand"
    manifest = json.loads(
        (brand_directory / "manifest.json").read_text(encoding="utf-8")
    )
    stylesheet = (brand_directory / manifest["stylesheet"]).read_text(encoding="utf-8")
    brand = '<meta name="nwave-brand" content="nwave-oss-neutral-v1">'
    csp = (
        '<meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        "font-src data:; connect-src 'none'\">"
    )
    assert page.count(brand) == 1, (
        "WHAT: the page does not carry exactly one versioned nWave brand marker. "
        "WHY: a browser-readable projection must identify the neutral OSS brand it applies. "
        "HOW: load the v1 manifest and emit its identity once in the document head."
    )
    assert page.count(csp) == 1, (
        "WHAT: the page does not carry exactly the offline content-security policy. "
        "WHY: a self-contained projection must not contact a remote origin. "
        "HOW: emit the declared CSP once in the document head."
    )
    assert "<style>" in page and "</style>" in page, (
        "WHAT: the page has no embedded stylesheet. "
        "WHY: an offline projection cannot depend on a separately fetched style asset. "
        "HOW: embed the validated local nWave stylesheet in the page."
    )
    assert (
        "--nwave-font-stack:ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"
        in page
    ), (
        "WHAT: the document does not emit the manifest's neutral font stack as a custom property. "
        "WHY: the renderer must carry the versioned manifest value into its self-contained stylesheet. "
        "HOW: emit the validated font stack in `--nwave-font-stack` before the selected stylesheet."
    )
    assert "font-family:var(--nwave-font-stack)" in page, (
        "WHAT: the embedded stylesheet does not consume the emitted font custom property. "
        "WHY: a manifest value that is never used cannot brand the rendered projection. "
        "HOW: make the selected local stylesheet use `var(--nwave-font-stack)` for the page font."
    )
    embedded = re.search(r"<style>(.*?)</style>", page, re.DOTALL)
    assert embedded is not None, (
        "WHAT: the page has no single inspectable embedded stylesheet payload. "
        "WHY: an offline projection must carry its complete local visual asset in the document. "
        "HOW: emit one `<style>` element containing the manifest-selected stylesheet."
    )
    assert (
        embedded.group(1)
        == f":root{{--nwave-font-stack:{manifest['font-stack']};}}\n{stylesheet}"
    ), (
        "WHAT: the embedded CSS is not exactly the manifest-selected local stylesheet plus its font property. "
        "WHY: the projection may embed only the finite v1 asset selected by the neutral OSS manifest. "
        "HOW: load that stylesheet by its manifest name and embed it without adding another asset."
    )
    assert not re.search(r"https?://", page, re.IGNORECASE), (
        "WHAT: the generated page contains a remote URL. "
        "WHY: the projection is promised to remain readable without network access. "
        "HOW: embed only validated local assets and remove remote asset references."
    )


@pytest.mark.parametrize(
    "break_brand",
    [
        pytest.param(
            lambda directory: None,
            id="manifest-missing",
        ),
        pytest.param(
            lambda directory: (directory / "manifest.json").write_text(
                "not valid json", encoding="utf-8"
            ),
            id="manifest-malformed",
        ),
        pytest.param(
            lambda directory: (directory / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema-version": 1,
                        "identity": "nwave-oss-neutral-v1",
                        "stylesheet": "../outside.css",
                        "font-stack": "sans-serif",
                    }
                ),
                encoding="utf-8",
            ),
            id="stylesheet-escapes-packaged-brand-set",
        ),
        pytest.param(
            lambda directory: (directory / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema-version": 1,
                        "identity": "nwave-oss-neutral-v1",
                        "stylesheet": "nwave.css",
                        "font-stack": "sans-serif",
                    }
                ),
                encoding="utf-8",
            ),
            id="manifest-selected-stylesheet-missing",
        ),
    ],
)
def test_invalid_brand_assets_refuse_before_the_project_page_is_written(
    root: Path, step, tmp_path: Path, break_brand
) -> None:
    """Brand validation is translated at the public project boundary, not after a write."""
    bound(root, step)
    brand_directory = root / "nWave" / "data" / "brand"
    brand_directory.mkdir(parents=True)
    break_brand(brand_directory)
    out = tmp_path / "projection.html"
    out.write_text("the earlier page remains intact", encoding="utf-8")

    code, stdout, stderr = step("project", "--repo-root", str(root), "--html", str(out))

    assert code == 1, (
        "WHAT: invalid brand assets did not make `des project` refuse. "
        "WHY: a malformed package asset must never become a misleading human page. "
        "HOW: translate brand-asset validation failure to BrandAssetsInvalid at project.main."
    )
    assert block(stdout, stderr)["WHAT"] == "BrandAssetsInvalid", (
        "WHAT: the public refusal names the wrong failure. "
        "WHY: callers need the declared BrandAssetsInvalid outcome to repair packaged assets. "
        "HOW: catch brand-asset validation only at project.main and render that outcome."
    )
    assert out.read_text(encoding="utf-8") == "the earlier page remains intact", (
        "WHAT: project output changed after brand validation failed. "
        "WHY: invalid brand assets must be refused before any output write. "
        "HOW: finish brand validation before creating or replacing the requested HTML file."
    )


def test_an_installed_wheel_projects_the_same_offline_page_as_the_source_tree(
    root: Path, step, tmp_path: Path
) -> None:
    """The customer-facing console script consumes the exact built wheel, not this checkout."""
    bound(root, step)
    source_page = tmp_path / "source.html"
    source_code, source_stdout, source_stderr = step(
        "project", "--repo-root", str(root), "--html", str(source_page)
    )
    assert source_code == 0, (
        "WHAT: the source-tree `des project` command did not render its page. "
        "WHY: byte identity can only compare two projections that the same public journey produced. "
        "HOW: make the source-tree CLI render the validated offline projection.\n"
        + source_stdout
        + source_stderr
    )

    repository = Path(__file__).parents[4]
    release_root = tmp_path / "release-source"
    for name in ("nWave", "nwave_ai", "scripts", "src"):
        shutil.copytree(repository / name, release_root / name)
    for name in ("README.md", "pyproject.toml", "uv.lock"):
        shutil.copy2(repository / name, release_root / name)

    patched = subprocess.run(
        [
            sys.executable,
            "scripts/release/patch_pyproject.py",
            "--input",
            "pyproject.toml",
            "--output",
            "pyproject.toml",
            "--target-name",
            "nwave-ai",
            "--target-version",
            "4.0.0",
        ],
        cwd=release_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert patched.returncode == 0, (
        "WHAT: the release-source package configuration could not be prepared. "
        "WHY: the installed-user journey must build the same source candidate that supplies its brand assets. "
        "HOW: keep the public release preparation pipeline runnable before its no-isolation wheel build.\n"
        + patched.stdout
        + patched.stderr
    )
    prepared = subprocess.run(
        [sys.executable, "scripts/build_dist.py", "--project-root", str(release_root)],
        cwd=release_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert prepared.returncode == 0, (
        "WHAT: the release-source runtime could not be staged. "
        "WHY: the installed `des` command must come from the release candidate, not this test checkout. "
        "HOW: make the standard release preparation produce its DES runtime staging tree.\n"
        + prepared.stdout
        + prepared.stderr
    )
    staged = subprocess.run(
        [
            sys.executable,
            "scripts/release/stage_public_wheel_des.py",
            "--project-root",
            str(release_root),
            "--cleanup-dist",
        ],
        cwd=release_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert staged.returncode == 0, (
        "WHAT: the public wheel DES payload could not be staged. "
        "WHY: the no-deps installation must execute the candidate's packaged CLI. "
        "HOW: stage the release runtime at the wheel build paths before building.\n"
        + staged.stdout
        + staged.stderr
    )

    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(wheel_dir),
        ],
        cwd=release_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert built.returncode == 0, (
        "WHAT: the public wheel could not be built for the installed-user journey. "
        "WHY: archive inspection and clean installation must consume one immutable release candidate. "
        "HOW: make the standard `python -m build --wheel` pipeline produce a wheel.\n"
        + built.stdout
        + built.stderr
    )
    candidates = list(wheel_dir.glob("*.whl"))
    assert len(candidates) == 1, (
        "WHAT: the build did not produce exactly one wheel candidate. "
        "WHY: the archive inspection and installed projection must examine the same immutable artifact. "
        "HOW: have the wheel build write one `.whl` to the requested output directory."
    )
    wheel = candidates[0]
    source_manifest = (repository / "nWave/data/brand/manifest.json").read_bytes()
    with zipfile.ZipFile(wheel) as archive:
        manifest_member = "nWave/data/brand/manifest.json"
        assert manifest_member in archive.namelist(), (
            "WHAT: the wheel omits the versioned brand manifest at its stable package-relative path. "
            "WHY: the installed renderer needs its declared local brand without a checkout fallback. "
            "HOW: include `nWave/data/brand/manifest.json` in the wheel."
        )
        assert archive.read(manifest_member) == source_manifest, (
            "WHAT: the wheel's brand manifest differs from the source-tree manifest. "
            "WHY: both public projections must select the same versioned local assets. "
            "HOW: package the source manifest unchanged at `nWave/data/brand/manifest.json`."
        )
        manifest = json.loads(source_manifest)
        stylesheet = manifest["stylesheet"]
        stylesheet_member = f"nWave/data/brand/{stylesheet}"
        assert stylesheet_member in archive.namelist(), (
            "WHAT: the wheel omits the local stylesheet selected by its brand manifest. "
            "WHY: an installed offline projection must resolve every manifest-selected asset locally. "
            "HOW: include the manifest-selected stylesheet under `nWave/data/brand/`."
        )
        assert (
            archive.read(stylesheet_member)
            == (repository / "nWave/data/brand" / stylesheet).read_bytes()
        ), (
            "WHAT: the wheel's manifest-selected stylesheet differs from the source asset. "
            "WHY: byte-identical source and installed projections require identical local brand inputs. "
            "HOW: package the selected stylesheet unchanged at its manifest-relative path."
        )

    environment_dir = tmp_path / "installed"
    venv.EnvBuilder(with_pip=True).create(environment_dir)
    python = environment_dir / "bin" / "python"
    installed = subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert installed.returncode == 0, (
        "WHAT: the clean environment could not install the built wheel. "
        "WHY: the user journey must run the immutable release candidate without checkout dependencies. "
        "HOW: make the wheel self-consistent for `pip install --no-deps`.\n"
        + installed.stdout
        + installed.stderr
    )
    installed_page = tmp_path / "installed.html"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    projected = subprocess.run(
        [
            str(environment_dir / "bin" / "des"),
            "project",
            "--repo-root",
            str(root),
            "--html",
            str(installed_page),
        ],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert projected.returncode == 0, (
        "WHAT: the installed `des project` console script did not render the projection. "
        "WHY: a customer must be able to use the wheel without borrowing the source checkout. "
        "HOW: resolve the manifest and local stylesheet from the installed package.\n"
        + projected.stdout
        + projected.stderr
    )
    assert installed_page.read_bytes() == source_page.read_bytes(), (
        "WHAT: the installed wheel produced different HTML from the source-tree CLI. "
        "WHY: the same public projection must have one stable offline representation in both distributions. "
        "HOW: package and resolve the same manifest-selected assets at stable package-relative paths."
    )


def test_the_projection_writes_only_the_page_and_never_a_store(
    root: Path, step, tmp_path: Path
) -> None:
    """ADR-BOARD-001: a visualization is a projection, never a fourth store."""
    bound(root, step)
    before = (root / HANDOVER).read_bytes()
    refs_before = git(root, "for-each-ref", "--format=%(refname)")
    head_before = git(root, "rev-parse", "HEAD")
    status_before = git(root, "status", "--porcelain")

    out = tmp_path / "projection.html"
    assert step("project", "--repo-root", str(root), "--html", str(out))[0] == 0

    assert (root / HANDOVER).read_bytes() == before
    assert git(root, "for-each-ref", "--format=%(refname)") == refs_before
    assert git(root, "rev-parse", "HEAD") == head_before
    assert git(root, "status", "--porcelain") == status_before


def test_the_same_state_renders_the_same_page(root: Path, step, tmp_path: Path) -> None:
    """Recomputed on every read, so it cannot drift from what it projects."""
    bound(root, step)
    first, second = tmp_path / "a.html", tmp_path / "b.html"
    assert step("project", "--repo-root", str(root), "--html", str(first))[0] == 0
    assert step("project", "--repo-root", str(root), "--html", str(second))[0] == 0
    assert first.read_text() == second.read_text()


def test_the_page_says_what_each_value_already_carries(
    root: Path, step, tmp_path: Path
) -> None:
    bound(root, step)
    out = tmp_path / "projection.html"
    step("project", "--repo-root", str(root), "--html", str(out))
    page = out.read_text()
    text = re.sub(r"<[^>]+>", " ", page)
    assert "bound" in text
    assert "absent" in text


def test_an_undecomposed_repository_refuses_and_names_the_step_that_starts_one(
    root: Path, step, tmp_path: Path
) -> None:
    out = tmp_path / "projection.html"
    code, stdout, stderr = step("project", "--repo-root", str(root), "--html", str(out))
    assert code == 1
    assert block(stdout, stderr)["WHAT"] == "HandoverAbsent"
    assert not out.exists()
    assert any(item.startswith(f"des po --repo-root {root}") for item in nexts(stdout))
