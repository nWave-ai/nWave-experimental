"""Regression AT: `nwave-ai outcomes register` works from an INSTALL shape.

Issue: nWave-ai/nWave#63 — "Registering an outcome is therefore impossible from
a normal install; the registry has to be hand-written."
Charter: docs/product/expectations/fix-outcomes-register-schema-path/
         register-an-outcome.md

RCA (confirmed from source, reproduced live in a non-editable install):
`nwave_ai/outcomes/application/registry_service.py` resolves its JSON Schema by
walking OUT of the package —

    _SCHEMA_PATH = Path(__file__).resolve().parents[3] / "docs" / "product" /
                   "outcomes" / "schema.json"

In a source checkout `parents[3]` happens to be the repo root, so the read
resolves. In an install `nwave_ai` lives in site-packages, `parents[3]` IS
site-packages, and `docs/` is stripped from every distribution channel — so the
lazy `@lru_cache _load_validator()` (reached ONLY by `register` ->
`_validate_against_schema`) dies with a raw `FileNotFoundError` on
`<site-packages>/docs/product/outcomes/schema.json`. `check` never validates,
which is why the READ path has always worked; that asymmetry is pinned below
(scenario 4).

WHY THIS FILE EXISTS AND `tests/outcomes/` DOES NOT CATCH IT
------------------------------------------------------------
`tests/outcomes` is 53/53 GREEN while the bug ships in production: every one of
those tests runs from the repo root, where `parents[3]` accidentally resolves.
A test that does not RELOCATE the package away from the repo checkout cannot
catch this bug no matter what it asserts. Five releases shipped through exactly
that blindness.

So the mechanism here is load-bearing in two parts, and neither is a style
choice:

1. `shutil.copytree` of ONLY `nwave_ai/` into a `tmp_path` site-packages — no
   `docs/` anywhere, and `tmp_path` sits outside the checkout so there is no
   repo ancestor for `parents[3]` to accidentally land on. (Copying `docs/`
   next to the package would fake the environment into the very shape that
   HIDES the defect.)
2. The REAL CLI is driven in a SUBPROCESS with `PYTHONPATH` pointed at that
   copy. In-process is not an option: `_load_validator` is `@lru_cache`d and
   `nwave_ai` is already imported by the test session from the repo, so an
   in-process call would silently read the repo copy and pass vacuously.

`_installed_shape` asserts the child actually resolved the relocated package
(`nwave_ai.__file__` under tmp) before any scenario runs — the vacuous-pass
guard, permanently.

THE FIX THIS TARGETS
--------------------
The schema MOVES INTO the package (`nwave_ai/outcomes/schema.json`, one
canonical copy) and is loaded via `importlib.resources`. Plus a LOUD refusal
path: a `SchemaUnavailableError` ("could NOT be checked", distinct from
`InvalidOutcomeError` = "was checked, failed"), surfaced by the CLI as a
self-explaining WHAT/WHY/HOW refusal with exit code 3, having written NOTHING.

Exit-code contract (extends nwave_ai/outcomes/cli.py):
    0  registered
    2  refused — validated and invalid (or duplicate id)
    3  refused — COULD NOT validate (schema resource unavailable)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPO_ROOT / "nwave_ai"

# The schema's post-fix home: INSIDE the package, so it ships with it.
SCHEMA_RESOURCE = Path("nwave_ai") / "outcomes" / "schema.json"

# Exit code for "I could not check it, so I refused" (distinct from 2 =
# "I checked it and it was invalid"). New in this fix.
EXIT_SCHEMA_UNAVAILABLE = 3
EXIT_REFUSED_INVALID = 2

_TRACEBACK_MARKER = "Traceback (most recent call last)"

_EMPTY_REGISTRY = 'schema_version: "0.1"\noutcomes: []\n'

_SEEDED_REGISTRY = """schema_version: "0.1"
outcomes:
  - id: OUT-EXISTING
    kind: specification
    summary: a row that was already here
    feature: legacy-feature
    inputs:
      - shape: legacy input
    output:
      shape: legacy output
    keywords:
      - legacy
    artifact: docs/legacy.md
    related: []
    superseded_by: null
"""


# ---------------------------------------------------------------------------
# The driving port: the REAL `nwave-ai` CLI, run against a relocated package.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstalledShape:
    """A throwaway install: `nwave_ai` in site-packages, no `docs/` in sight.

    `work` is the user's own scratch project (cwd for the CLI); `registry` is
    the outcomes registry inside it. Every scenario drives the product through
    `run_cli` — the shipped console-script entry (`nwave_ai.cli:main`), never an
    internal function.
    """

    site_packages: Path
    work: Path
    registry: Path

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Invoke the real CLI in a subprocess resolving the RELOCATED package."""
        return subprocess.run(
            [sys.executable, "-m", "nwave_ai.cli", *args],
            cwd=str(self.work),
            env=_relocated_env(self.site_packages),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def register(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self.run_cli("outcomes", "--registry", str(self.registry), *args)

    def schema_resource(self) -> Path:
        return self.site_packages / SCHEMA_RESOURCE

    def registered_ids(self) -> list[str]:
        data = yaml.safe_load(self.registry.read_text(encoding="utf-8")) or {}
        return [row["id"] for row in data.get("outcomes") or []]

    def row(self, outcome_id: str) -> dict | None:
        data = yaml.safe_load(self.registry.read_text(encoding="utf-8")) or {}
        for row in data.get("outcomes") or []:
            if row["id"] == outcome_id:
                return row
        return None


def _relocated_env(site_packages: Path) -> dict[str, str]:
    """Child env whose FIRST import path is the relocated package.

    `PYTHONPATH` entries precede the interpreter's own site-packages (and any
    editable-install `.pth` entry pointing back at this checkout), so
    `import nwave_ai` resolves to the copy — asserted, not assumed, by
    `_assert_child_resolves_relocated_package`.
    """
    return {**os.environ, "PYTHONPATH": str(site_packages)}


def _relocate_package(tmp_path: Path, registry_body: str) -> InstalledShape:
    """Copy ONLY `nwave_ai/` out of the checkout; seed a scratch project."""
    site_packages = tmp_path / "site-packages"
    shutil.copytree(
        PACKAGE_ROOT,
        site_packages / "nwave_ai",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    work = tmp_path / "work"
    work.mkdir()
    registry = work / "registry.yaml"
    registry.write_text(registry_body, encoding="utf-8")
    return InstalledShape(site_packages=site_packages, work=work, registry=registry)


def _assert_child_resolves_relocated_package(shape: InstalledShape) -> None:
    """Harness precondition: the subprocess really loaded the RELOCATED copy.

    Without this the whole file could pass vacuously against the repo checkout —
    the exact blindness that let this bug ship five times.
    """
    probe = subprocess.run(
        [sys.executable, "-c", "import nwave_ai; print(nwave_ai.__file__)"],
        cwd=str(shape.work),
        env=_relocated_env(shape.site_packages),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    resolved = probe.stdout.strip()
    assert resolved.startswith(str(shape.site_packages)), (
        "HARNESS BROKEN: the subprocess resolved nwave_ai from "
        f"{resolved!r}, not from the relocated copy at {shape.site_packages}. "
        "Every scenario in this file would pass vacuously against the repo "
        "checkout (where parents[3] accidentally resolves)."
    )
    assert not (shape.site_packages / "docs").exists(), (
        "HARNESS BROKEN: a `docs/` tree exists next to the relocated package — "
        "that fakes the environment into the shape that HIDES this defect."
    )


def _assert_no_traceback(result: subprocess.CompletedProcess[str]) -> None:
    """Charter negative oracle: no raw Python traceback on ANY path."""
    assert _TRACEBACK_MARKER not in result.stderr, (
        "a raw Python traceback reached the user — a failure of the product "
        "even when the underlying action happened to work.\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.fixture()
def installed_shape(tmp_path: Path) -> InstalledShape:
    """An empty-registry install shape (the reporter's starting point)."""
    shape = _relocate_package(tmp_path, _EMPTY_REGISTRY)
    _assert_child_resolves_relocated_package(shape)
    return shape


@pytest.fixture()
def seeded_shape(tmp_path: Path) -> InstalledShape:
    """An install shape whose registry already holds `OUT-EXISTING`."""
    shape = _relocate_package(tmp_path, _SEEDED_REGISTRY)
    _assert_child_resolves_relocated_package(shape)
    return shape


# ---------------------------------------------------------------------------
# Scenario 1a — THE BUG. Registering from an install shape must actually work.
# RED today: FileNotFoundError on <site-packages>/docs/product/outcomes/schema.json
# ---------------------------------------------------------------------------


def test_register_from_an_installed_package_writes_the_row(
    installed_shape: InstalledShape,
) -> None:
    """Charter oracle 1+2: exit 0, says so readably, and the row is ON DISK.

    The whole of issue #63 in one assertion: a maintainer who installed the tool
    the ordinary way asks for an outcome and gets it recorded in THEIR project.
    """
    result = installed_shape.register(
        "register",
        "--id",
        "OUT-INSTALL-1",
        "--kind",
        "operation",
        "--input-shape",
        "outcome request",
        "--output-shape",
        "registry row",
        "--summary",
        "register an outcome from an installed CLI",
        "--feature",
        "fix-outcomes-register-schema-path",
        "--keywords",
        "outcomes,register",
    )

    assert result.returncode == 0, (
        "`outcomes register` failed from an installed package — the schema is "
        "resolved by walking OUT of the package (parents[3]/docs/...), which in "
        "an install is site-packages, where no docs/ tree exists.\n"
        f"exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    _assert_no_traceback(result)
    assert "REGISTERED: OUT-INSTALL-1" in result.stdout, (
        "the command did not report the registration in language a human can "
        f"read.\nstdout:\n{result.stdout}"
    )

    row = installed_shape.row("OUT-INSTALL-1")
    assert row is not None, (
        "exit code said success but NOTHING was written to the user's registry "
        "— the charter calls that a FAIL, not a pass.\n"
        f"registry:\n{installed_shape.registry.read_text(encoding='utf-8')}"
    )
    assert row["kind"] == "operation"
    assert row["inputs"] == [{"shape": "outcome request"}]
    assert row["output"] == {"shape": "registry row"}
    assert row["feature"] == "fix-outcomes-register-schema-path"
    assert row["keywords"] == ["outcomes", "register"]


# ---------------------------------------------------------------------------
# Scenario 1b — ANTI-CHEAT. The schema must travel INSIDE the package.
# RED today: the schema lives only at docs/product/outcomes/schema.json.
# ---------------------------------------------------------------------------


def test_schema_resource_ships_inside_the_installed_package(
    installed_shape: InstalledShape,
) -> None:
    """The relocated package carries its own schema — no `docs/` dependency.

    This forbids "fixing" scenario 1a by copying `docs/` into the fixture: the
    schema must be a package resource that travels with `nwave_ai` wherever it
    is installed, because `docs/` is stripped from every distribution channel.
    """
    resource = installed_shape.schema_resource()
    assert resource.is_file(), (
        f"{SCHEMA_RESOURCE} is absent from the relocated package at {resource}. "
        "The schema still lives outside the package (docs/product/outcomes/), so "
        "it is stripped from every distribution channel and unreachable from an "
        "install."
    )


# ---------------------------------------------------------------------------
# Scenario 2 — NEGATIVE ORACLE (GDP-6). Cannot check => SAY so and REFUSE.
# RED today: raw FileNotFoundError, exit 1, traceback, no refusal at all.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_register_refuses_and_writes_nothing_when_the_schema_is_unavailable(
    installed_shape: InstalledShape,
) -> None:
    """Charter: '"I checked and it's valid" and "I never checked" must not look
    the same from the outside.'

    With the schema resource missing (a damaged install), the command must NOT
    quietly write the row while claiming all is well, and must NOT dump a
    traceback. It must refuse, LOUDLY and self-explainingly (GDP-3 WHAT/WHY/HOW),
    with exit code 3 — distinct from 2 ("I checked it; it was invalid") — and
    leave the registry byte-for-byte untouched.

    Contract asserted here, for the crafter:
        exit   3
        stderr WHAT: "refused"  WHY: "schema"  HOW: "reinstall"   (case-insens.)
        disk   registry bytes UNCHANGED
    """
    installed_shape.schema_resource().unlink(missing_ok=True)
    before = installed_shape.registry.read_bytes()

    result = installed_shape.register(
        "register",
        "--id",
        "OUT-UNCHECKABLE",
        "--kind",
        "operation",
        "--input-shape",
        "outcome request",
        "--output-shape",
        "registry row",
    )

    assert result.returncode == EXIT_SCHEMA_UNAVAILABLE, (
        "with no schema to validate against, the command must refuse with exit "
        f"{EXIT_SCHEMA_UNAVAILABLE} (could NOT check), not crash and not "
        "succeed.\n"
        f"exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    _assert_no_traceback(result)

    stderr = result.stderr.lower()
    assert "refus" in stderr, (
        "the refusal does not say WHAT happened (that it refused / did not "
        f"register).\nstderr:\n{result.stderr}"
    )
    assert "schema" in stderr, (
        f"the refusal does not say WHY (the schema could not be read).\n"
        f"stderr:\n{result.stderr}"
    )
    assert "reinstall" in stderr, (
        f"the refusal does not say HOW to fix it (reinstall the tool).\n"
        f"stderr:\n{result.stderr}"
    )
    assert "REGISTERED" not in result.stdout, (
        "the command claimed a registration it refused to make.\n"
        f"stdout:\n{result.stdout}"
    )
    assert installed_shape.registry.read_bytes() == before, (
        "the registry was written even though the outcome could not be "
        "validated — writing while quietly claiming everything is fine is the "
        "exact failure the charter forbids.\n"
        f"registry:\n{installed_shape.registry.read_text(encoding='utf-8')}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 — APPEND, not clobber.
# RED today: never reaches the write (crashes in validation first).
# ---------------------------------------------------------------------------


def test_register_appends_without_clobbering_existing_rows(
    seeded_shape: InstalledShape,
) -> None:
    """Charter oracle 4: pre-existing rows survive; nothing is dropped."""
    result = seeded_shape.register(
        "register",
        "--id",
        "OUT-NEW",
        "--kind",
        "invariant",
        "--input-shape",
        "new input",
        "--output-shape",
        "new output",
    )

    assert result.returncode == 0, (
        f"register into a non-empty registry failed.\nexit={result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    _assert_no_traceback(result)

    assert seeded_shape.registered_ids() == ["OUT-EXISTING", "OUT-NEW"], (
        "registering must APPEND: the pre-existing row must survive and the new "
        f"one be added.\nregistry:\n"
        f"{seeded_shape.registry.read_text(encoding='utf-8')}"
    )
    existing = seeded_shape.row("OUT-EXISTING")
    assert existing is not None and existing["summary"] == "a row that was already here"
    data = yaml.safe_load(seeded_shape.registry.read_text(encoding="utf-8"))
    assert data["schema_version"] == "0.1", (
        "the registry's schema_version was dropped or rewritten by the append."
    )


# ---------------------------------------------------------------------------
# Scenario 4 — INVARIANCE PIN. The read path was never broken; keep it so.
# GREEN today, and must STAY green (`check` never validates — that asymmetry is
# precisely why the bug went unnoticed).
# ---------------------------------------------------------------------------


def test_check_still_works_in_an_installed_package(
    installed_shape: InstalledShape,
) -> None:
    """`outcomes check` in the install shape: exit 0, NO COLLISIONS.

    Pins the half that already works, so the fix cannot regress it — e.g. by
    routing `check` through a schema load it never needed.
    """
    result = installed_shape.run_cli(
        "outcomes",
        "--registry",
        str(installed_shape.registry),
        "check",
        "--input-shape",
        "outcome request",
        "--output-shape",
        "registry row",
    )

    _assert_no_traceback(result)
    assert result.returncode == 0, (
        f"`outcomes check` regressed in the install shape.\n"
        f"exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "NO COLLISIONS" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 5 — ANTI-"GREEN SHIRT". Validation must still be ENFORCED.
# RED today: crashes with FileNotFoundError (exit 1) before validation runs.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_register_rejects_invalid_input_from_an_installed_package(
    installed_shape: InstalledShape,
) -> None:
    """Charter: the crash must NOT be cured by deleting the check that crashed.

    `BAD-ID` violates the schema's `^OUT-[A-Z0-9-]+$` id pattern. If a future
    crafter goes green by removing the `_validate_against_schema` call at
    `registry_service.py:81` — or by swallowing its failure — this test turns
    red: the nonsense row would be accepted and written. That is a worse bug in
    a green shirt, and this is the pin that catches it.
    """
    result = installed_shape.register(
        "register",
        "--id",
        "BAD-ID",
        "--kind",
        "operation",
        "--input-shape",
        "outcome request",
        "--output-shape",
        "registry row",
    )

    assert result.returncode == EXIT_REFUSED_INVALID, (
        "genuinely invalid input must be refused after being CHECKED (exit "
        f"{EXIT_REFUSED_INVALID}) — not crashed on, and not accepted.\n"
        f"exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    _assert_no_traceback(result)
    assert "BAD-ID" not in installed_shape.registered_ids(), (
        "an outcome that violates the schema was WRITTEN to the registry — "
        "validation has been removed or defanged to buy the fix.\n"
        f"registry:\n{installed_shape.registry.read_text(encoding='utf-8')}"
    )
    assert result.stderr.strip(), (
        "the refusal said nothing — it must name what is wrong with the input."
    )
