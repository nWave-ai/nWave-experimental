"""Regression AT: `nwave-ai validate-feature-delta` works from an INSTALL shape.

Feature: fix-feature-delta-schema-path (slice-01, at-kind: pytest-regression)
Charter: docs/product/expectations/fix-feature-delta-schema-path/
         a-maintainer-who-installed-nwave-ai-the-ordinary-way-runs-
         nwave-ai-validate-feature-delta-path.md

Sibling of nWave-ai/nWave#63 (`cfaaaf192`) — same bug class, same fix shape.

THE DEFECT: FOUR SITES, ONE BUG CLASS (feature-delta § SCOPE CORRECTION, D-5a)
------------------------------------------------------------------------------
Every runtime resource `validate-feature-delta` needs is resolved by walking OUT
of the package with `Path(__file__).parent` x4. From a source checkout those hops
land on the repo root, where the assets happen to sit, so everything resolves.
From an install they land in site-packages, where none of it exists:

    adapters/schema.py:12-14    <sp>/schemas/feature-delta-schema.json
    adapters/verbs.py:11-13     <sp>/nWave/data/{protocol,substantive}-verbs/
    adapters/gherkin.py:8-9     <sp>/nWave/data/gherkin-keywords/
    application/validator.py:34 <sp>/nWave/data/feature-delta-rule-maturity.json

`feature_delta/cli.py` runs two probes back to back — `JsonSchemaFileLoader()
.probe()` at :52, then `PlaintextVerbLoader(...).probe()` at :57, unconditional.
:58 catches only `ReDoSError`, so the bare `assert len(verbs) > 0` at
`verbs.py:81` escapes as a RAW TRACEBACK, which the charter's negative oracle
forbids outright.

Which site bites depends on the channel, and BOTH are broken:

    dev wheel        no `schemas/` at all      -> schema probe refuses, exit 70
    published 3.21.0 `schemas/` force-included -> schema probe PASSES, then the
                     (patch_pyproject.py:191)     verbs assert -> raw traceback

So on the SHIPPED PRODUCT the schema is not even the user-facing defect —
`verbs.py` is. Verified by `pip install nwave-ai==3.21.0` into a clean venv.
Fixing the schema alone changes WHICH error the maintainer gets, not whether the
command works. AT1 below is therefore bound to the CHARTER outcome (a verdict
about the maintainer's DOCUMENT) and stays RED until all four sites are fixed.

THE FIX THIS TARGETS (D-6)
--------------------------
All five runtime resources become PACKAGE RESOURCES loaded via
`importlib.resources`, shipping on every channel through the existing
`packages = [... "nwave_ai"]` entry with ZERO force-include lines to remember —
forgetting such a line is the systemic root (`F-PACKAGED-RESOURCE-PATH-GATE`)
that produced all five sites across two features:

    schemas/feature-delta-schema.json           -> nwave_ai/feature_delta/schema.json
    nWave/data/protocol-verbs/                  -> nwave_ai/feature_delta/data/...
    nWave/data/substantive-verbs/               -> nwave_ai/feature_delta/data/...
    nWave/data/gherkin-keywords/                -> nwave_ai/feature_delta/data/...
    nWave/data/feature-delta-rule-maturity.json -> nwave_ai/feature_delta/data/...

Every existing seam is KEPT (D-3): explicit `schema_path=`,
`NWAVE_FEATURE_DELTA_SCHEMA`, the per-repo `.nwave/protocol-verbs.txt` override,
and the ReDoS guard. Only the DEFAULTS move. AT5a/AT5b pin that.

WHY `tests/feature_delta/` DOES NOT CATCH ANY OF THIS
-----------------------------------------------------
That suite is green while the command is unusable from every install, and no
assertion it could add would change that: every test there either injects a path
explicitly or runs from the repo root, where the four-hop walk-out accidentally
resolves. A test that does not RELOCATE the package away from the checkout is
blind to this defect BY CONSTRUCTION. Two things here are load-bearing mechanism,
not style:

1. `shutil.copytree` of the package into a `tmp_path` site-packages, with NO
   `schemas/` and NO `nWave/data/` beside it — and `tmp_path` sits outside the
   checkout, so there is no repo ancestor for the walk-out to land on. Providing
   those trees would fake the environment into the very shape that HIDES the
   defect; `_assert_child_resolves_relocated_package` forbids it, and
   `test_every_runtime_resource_ships_inside_the_installed_package` forbids
   curing AT1 that way.
2. The REAL CLI is driven in a SUBPROCESS with `PYTHONPATH` pointed at that copy.

FIDELITY OF THE MODELLED INSTALL (checked against the published artifact)
-------------------------------------------------------------------------
    nwave_ai/            `packages = [...]`                  (pyproject.toml:22)
    scripts/install/     force-include                       (pyproject.toml:25)
    scripts/shared/      force-include                       (pyproject.toml:26)
    <no schemas/>        the post-fix contract shape — D-2 deletes the
                         force-include that put it in the public wheel
    <no nWave/data/>     the published 3.21.0 payload contains NO nWave/data
                         directory, flat OR nested. The four data assets ship on
                         NO channel. Modelling them present — at any path — would
                         model an install that does not exist.

`scripts/{install,shared}` are copied because `nwave_ai/cli.py:14,24` imports
them at module load; omitting them would let the child silently fall back to the
repo checkout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPO_ROOT / "nwave_ai"
NWAVE_DATA = REPO_ROOT / "nWave" / "data"

# Post-fix home of the schema: INSIDE the package, so it travels with it.
SCHEMA_RESOURCE = Path("nwave_ai") / "feature_delta" / "schema.json"
# Post-fix home of the four data assets (D-6).
DATA_ROOT = Path("nwave_ai") / "feature_delta" / "data"
RULE_MATURITY_RESOURCE = DATA_ROOT / "feature-delta-rule-maturity.json"
# The verb list `PlaintextVerbLoader.probe()` hard-requires at every startup.
PROTOCOL_VERBS_EN = DATA_ROOT / "protocol-verbs" / "en.txt"

# The three asset DIRECTORIES D-6 moves wholesale. Expected contents are DERIVED
# from the repo, not hard-coded: `--lang es|fr|it` is a documented flag, so a fix
# that moved only `en.txt` would silently degrade the other languages to empty
# verb lists (no violations, no complaint) — a quiet widening of what counts as
# valid, which the charter's last negative oracle forbids.
ASSET_DIRS = ("protocol-verbs", "substantive-verbs", "gherkin-keywords")

# Exit codes the tool documents to its users (feature_delta/cli.py:36-42).
EXIT_CLEAN = 0
EXIT_STARTUP_REFUSED = 70
EXIT_VIOLATIONS_FOUND = 1  # --enforce only
EXIT_MISCONFIGURED = 78  # --enforce asked for while rules are still pending

REFUSAL_MARKER = "health.startup.refused"
_TRACEBACK_MARKER = "Traceback (most recent call last)"


def _expected_package_resources() -> tuple[Path, ...]:
    """Every runtime resource that must live INSIDE the package after D-6.

    Derived from what the repo actually carries today, so the pin cannot drift
    from the assets it is meant to protect.
    """
    resources = [SCHEMA_RESOURCE, RULE_MATURITY_RESOURCE]
    for asset_dir in ASSET_DIRS:
        for txt in sorted((NWAVE_DATA / asset_dir).glob("*.txt")):
            resources.append(DATA_ROOT / asset_dir / txt.name)
    return tuple(resources)


# A well-formed feature-delta: canonical wave heading, canonical 4-column
# commitments table. Validates clean from the repo root today ([PASS] all checks).
_WELL_FORMED_DELTA = """\
# Feature Delta — a maintainer's own feature

## Wave: DISCUSS

### [REF] Inherited commitments

| Origin | Commitment | DDR | Impact |
|--------|------------|-----|--------|
"""

# A genuinely mangled feature-delta. Two independent, verb-list-INDEPENDENT
# violations (structural rules), so the document stays refusable even when the
# verb assets are unreachable:
#   E1 — '## Wave: DISCUS' is a near-miss of a known wave name (rules/e1:38)
#   E2 — the commitments header is missing 'DDR' and 'Impact' (rules/e2:41)
_MANGLED_DELTA = """\
# Feature Delta — deliberately mangled

## Wave: DISCUS

### [REF] Inherited commitments

| Origin | Commitment |
|--------|------------|
| DISCUSS | something |
"""

# A per-repo protocol-verb override carrying a catastrophic-backtracking pattern.
# `_check_redos` (verbs.py:100) must reject it at startup — AT5 pins that this
# guard survives the move and still fires from an install.
_REDOS_OVERRIDE = "(a+)+b\n"


# ---------------------------------------------------------------------------
# The driving port: the REAL `nwave-ai` CLI, run against a relocated package.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstalledShape:
    """A throwaway install: `nwave_ai` in site-packages, its assets nowhere else.

    `work` is the maintainer's own scratch project (cwd for the CLI) — a
    directory that, as the charter demands, "has nothing to do with the nWave
    source". Every scenario drives the product through `run_cli`, the shipped
    console-script entry (`nwave_ai.cli:main`), never an internal function.
    """

    site_packages: Path
    work: Path
    well_formed: Path
    mangled: Path

    def run_cli(
        self, *args: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Invoke the real CLI in a subprocess resolving the RELOCATED package."""
        return subprocess.run(
            [sys.executable, "-m", "nwave_ai.cli", *args],
            cwd=str(self.work),
            env=env or _relocated_env(self.site_packages),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

    def validate(
        self, document: Path, *flags: str, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return self.run_cli("validate-feature-delta", document.name, *flags, env=env)

    def resource(self, relative: Path) -> Path:
        return self.site_packages / relative


def _relocated_env(site_packages: Path) -> dict[str, str]:
    """Child env whose FIRST import path is the relocated package.

    `PYTHONPATH` entries precede the interpreter's own site-packages (and any
    editable-install `.pth` entry pointing back at this checkout), so
    `import nwave_ai` resolves to the copy — asserted, not assumed, by
    `_assert_child_resolves_relocated_package`.
    """
    return {**os.environ, "PYTHONPATH": str(site_packages)}


def _relocate_package(tmp_path: Path) -> InstalledShape:
    """Lay down the install shape: the package, its force-includes, nothing else.

    See the module docstring's FIDELITY table for why each entry is here — and,
    more importantly, why `schemas/` and `nWave/data/` are NOT.
    """
    site_packages = tmp_path / "site-packages"

    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(PACKAGE_ROOT, site_packages / "nwave_ai", ignore=ignore)

    # Force-included in BOTH wheels (pyproject.toml:25-26); `nwave_ai/cli.py`
    # imports them at module load, so an install without them cannot even boot.
    for sub in ("install", "shared"):
        shutil.copytree(
            REPO_ROOT / "scripts" / sub,
            site_packages / "scripts" / sub,
            ignore=ignore,
        )

    work = tmp_path / "work"
    work.mkdir()
    well_formed = work / "feature-delta.md"
    well_formed.write_text(_WELL_FORMED_DELTA, encoding="utf-8")
    mangled = work / "mangled.md"
    mangled.write_text(_MANGLED_DELTA, encoding="utf-8")

    return InstalledShape(
        site_packages=site_packages,
        work=work,
        well_formed=well_formed,
        mangled=mangled,
    )


def _assert_child_resolves_relocated_package(shape: InstalledShape) -> None:
    """Harness precondition: the subprocess really loaded the RELOCATED copy, and
    the environment is not secretly faked into the shape that hides the defect.

    Without this the whole file could pass vacuously against the repo checkout —
    the exact blindness that keeps `tests/feature_delta` green while
    `validate-feature-delta` is unusable from every install.
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
        "checkout, where the four-hop walk-out accidentally resolves.\n"
        f"stderr:\n{probe.stderr}"
    )
    assert not (shape.site_packages / "schemas").exists(), (
        "HARNESS BROKEN: a top-level `schemas/` tree exists beside the relocated "
        "package — that fakes the environment into the very shape that HIDES "
        "this defect. The fix DELETES the force-include that creates it on the "
        "public wheel (patch_pyproject.py:191, D-2), so no install will have one."
    )
    for candidate in (
        shape.site_packages / "nWave" / "data",
        shape.site_packages / "nWave" / "nWave" / "data",
    ):
        assert not candidate.exists(), (
            f"HARNESS BROKEN: an `nWave/data` tree exists at {candidate}. The "
            "published 3.21.0 payload contains NO nWave/data directory, flat or "
            "nested — the four data assets ship on no channel. A fixture that "
            "provides them models an install that exists nowhere, and every "
            "verbs / gherkin / rule-maturity assertion below would pass vacuously."
        )


def _assert_no_traceback(result: subprocess.CompletedProcess[str]) -> None:
    """Charter negative oracle: 'the maintainer must NOT be shown a raw Python
    traceback, a crash dump, or a bare path pointing inside the tool's own
    installation as the answer to their request'."""
    assert _TRACEBACK_MARKER not in result.stderr, (
        "a raw Python traceback reached the maintainer — output they cannot act "
        "on is not an answer, however the command exited. (Today this is the "
        "`assert len(verbs) > 0` at adapters/verbs.py:81 escaping through "
        "cli.py:58, which catches only ReDoSError.)\n"
        f"stderr:\n{result.stderr}"
    )


@pytest.fixture()
def installed_shape(tmp_path: Path) -> InstalledShape:
    """The reporter's starting point: the tool installed, the repo nowhere near."""
    shape = _relocate_package(tmp_path)
    _assert_child_resolves_relocated_package(shape)
    return shape


# ---------------------------------------------------------------------------
# AT1 — THE BUG. A maintainer validates their own document from a normal install.
# @driving_port @walking_skeleton @real-io  @contract-shape:bounded-change
# ---------------------------------------------------------------------------


def test_validate_feature_delta_reaches_a_verdict_from_an_installed_package(
    installed_shape: InstalledShape,
) -> None:
    """Charter oracle 1: the tool reaches a verdict about the DOCUMENT.

    "Running the command from a normal install, in a directory that has nothing
    to do with the nWave source, on a well-formed feature-delta document,
    produces a verdict about that document ... and the process finishes cleanly
    (exit 0 when the document is clean)."

    The whole bug in one assertion: is the tool telling the maintainer about
    THEIR document, or about ITSELF? Only the first is an answer. This is bound
    to the charter outcome, NOT to a partial one — it stays RED until all four
    walk-out sites are fixed (D-5a), because a maintainer whose command dies on
    the verbs traceback instead of the schema refusal has not been helped.
    """
    result = installed_shape.validate(installed_shape.well_formed)

    _assert_no_traceback(result)
    assert REFUSAL_MARKER not in result.stderr, (
        "the tool refused at startup over one of its OWN files, on a perfectly "
        "fine document and environment — 'a working install must never present "
        "its own internal problem as the outcome of the maintainer's request'.\n"
        f"stderr:\n{result.stderr}"
    )
    assert result.returncode == EXIT_CLEAN, (
        "`validate-feature-delta` did not reach a verdict from an installed "
        "package. Its runtime resources are resolved by walking OUT of the "
        "package (parent x4), which in an install is site-packages, where "
        "neither `schemas/` nor `nWave/data/` exists.\n"
        f"exit={result.returncode}\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "[PASS]" in result.stdout, (
        "the command exited cleanly but said nothing about the maintainer's "
        "document — a verdict they can read and act on is the point of the "
        f"command.\nstdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# AT2 — ANTI-CHEAT. EVERY runtime resource must travel INSIDE the package.
# @driving_port  @contract-shape:pure-function
# ---------------------------------------------------------------------------


def test_every_runtime_resource_ships_inside_the_installed_package(
    installed_shape: InstalledShape,
) -> None:
    """The relocated package carries ALL five of its runtime resources (D-6).

    This forbids "fixing" AT1 by dropping `schemas/` or `nWave/data/` into the
    fixture — i.e. by curing the test into the very shape that HIDES the defect.
    The resources must be PACKAGE RESOURCES that travel with `nwave_ai` into
    every install, because:

      * the fix deletes the one force-include (patch_pyproject.py:191) that was
        accidentally keeping the schema alive on the public wheel; and
      * the four data assets ship on NO channel today — the published 3.21.0
        payload has no `nWave/data` directory at all.

    Expected contents are derived from the repo, so a fix that moves only
    `en.txt` and silently degrades `--lang es|fr|it` to empty verb lists is
    caught here rather than shipping as a quiet widening of what counts as valid.
    """
    missing = [
        str(relative)
        for relative in _expected_package_resources()
        if not installed_shape.resource(relative).is_file()
    ]
    assert not missing, (
        "these runtime resources are absent from the relocated package — they "
        "still live OUTSIDE it (top-level `schemas/` and `nWave/data/`), so they "
        "reach an install on no channel and the command cannot read its own "
        "validation rules:\n  " + "\n  ".join(missing)
    )


# ---------------------------------------------------------------------------
# AT3 — ANTI-"GREEN SHIRT". Validation must still BITE from the install shape.
# @driving_port @error @negative_at  @contract-shape:bounded-change
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_installed_validator_still_refuses_to_pass_a_mangled_document(
    installed_shape: InstalledShape,
) -> None:
    """Charter: '"validated, no violations" and "never validated anything" must
    be impossible to confuse from the outside.'

    The cheapest way to make a validator "work" is to make it stop validating.
    If a future crafter buys AT1's green by defanging a `probe()` or by letting a
    missing verb list quietly widen what passes, the [E1]/[E2] call-outs below
    vanish and this turns red. That is a worse bug wearing a green shirt, and
    this is the pin that catches it. Both violations asserted are verb-list
    independent (structural rules), so they stay observable even in a damaged
    install — the mangled document has nowhere to hide.
    """
    mangled = installed_shape.validate(installed_shape.mangled)
    clean = installed_shape.validate(installed_shape.well_formed)

    _assert_no_traceback(mangled)
    assert mangled.returncode != EXIT_STARTUP_REFUSED, (
        "the tool never got as far as looking at the mangled document — it "
        f"refused at startup ({EXIT_STARTUP_REFUSED}) over its own resources.\n"
        f"stderr:\n{mangled.stderr}"
    )

    # The maintainer reads their TERMINAL, not one file descriptor: the product
    # splits its report across both streams (`[WARN] [E1] …` and `[PASS] all
    # checks` both go to stderr — validator.py:288), so every assertion here is
    # made against the COMBINED stream. Asserting a single stream would pin an
    # incidental plumbing detail instead of what the maintainer actually sees.
    report = mangled.stdout + mangled.stderr
    clean_report = clean.stdout + clean.stderr

    assert "[E1]" in report, (
        "the malformed wave heading '## Wave: DISCUS' was NOT called out (E1). "
        "Either the tool never checked the document, or validation has been "
        f"widened to accept it.\nstdout:\n{mangled.stdout}\nstderr:\n{mangled.stderr}"
    )
    assert "[E2]" in report, (
        "the commitments table missing its 'DDR' and 'Impact' columns was NOT "
        f"called out (E2).\nstdout:\n{mangled.stdout}\nstderr:\n{mangled.stderr}"
    )
    assert installed_shape.mangled.name in report, (
        "the violations do not name the maintainer's document — the report must "
        f"be about THEIR file.\nstdout:\n{mangled.stdout}\nstderr:\n{mangled.stderr}"
    )

    # Charter oracle 3: "The distinction between a good and a bad document is
    # visible in the output." A validator that passes everything is worse than
    # one that refuses to start, because the maintainer would trust it. The
    # contrast still bites: on the real CLI "all checks" appears exactly once in
    # the clean report and zero times in the mangled one, so a crafter who
    # defanged validation would turn the second assertion red.
    assert "all checks" in clean_report, (
        "the well-formed document did not come back clean, so the contrast "
        f"below proves nothing.\nstdout:\n{clean.stdout}\nstderr:\n{clean.stderr}"
    )
    assert "all checks" not in report, (
        "the mangled document was waved through with the same clean verdict as "
        "the well-formed one. A maintainer cannot tell the two apart — the "
        f"charter calls that a FAIL, not a pass.\nstdout:\n{mangled.stdout}\n"
        f"stderr:\n{mangled.stderr}"
    )


# ---------------------------------------------------------------------------
# AT8 — `--enforce` REACHES THE DOCUMENT from an install. The charter's exit-1
# oracle. @driving_port @error @negative_at  @contract-shape:bounded-change
#
# The third walk-out on this command's path: `validator.py:34` resolves the rule
# maturity manifest at `<sp>/nWave/data/feature-delta-rule-maturity.json`, which
# ships on no channel — so `--enforce` dies at the maturity GATE (exit 78,
# "maturity manifest not found") without ever reading the maintainer's document.
# D-6 packages the manifest, so this should come green with the rest. PINNED, not
# assumed: assumed-but-unpinned is precisely the mechanism that let this bug class
# ship five times.
#
# Chosen oracle: exit 1 on a document WITH violations, contrasted against exit 0
# on a clean one. Exit-1 exercises the whole chain (the maturity gate must PASS,
# the document must be READ, and the enforce severity must be APPLIED); a
# clean-document exit-0 alone would not discriminate — it is indistinguishable
# from warn-only and would stay green under a crafter who turned enforce into a
# no-op. Verified reachable: the manifest's `required_stable` (E1, E2, E3, E3b,
# E5) are all `stable`, zero pending, so nothing unrelated to this bug blocks the
# exit-1 path.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_enforce_mode_still_fails_a_mangled_document_from_an_installed_package(
    installed_shape: InstalledShape,
) -> None:
    """Charter oracle 2: "in `--enforce` mode, fails with exit 1 rather than
    waving it through."

    Today the maintainer never gets that far: the command refuses over its own
    missing resources long before the maturity gate, and even past that would
    stop at exit 78 because the manifest is not in the install either. Post-fix
    the manifest is a package resource, so `--enforce` must reach the document
    and hold it to account.
    """
    mangled = installed_shape.validate(installed_shape.mangled, "--enforce")
    clean = installed_shape.validate(installed_shape.well_formed, "--enforce")

    _assert_no_traceback(mangled)
    assert mangled.returncode != EXIT_MISCONFIGURED, (
        "`--enforce` was refused as a MISCONFIGURATION (exit "
        f"{EXIT_MISCONFIGURED}) — the tool could not read its own rule maturity "
        "manifest, which it resolves by walking out of the package "
        "(validator.py:34). The maintainer is being told about the tool's "
        f"internals, not their document.\nstderr:\n{mangled.stderr}"
    )
    assert mangled.returncode != EXIT_STARTUP_REFUSED, (
        "the tool refused at startup over its own resources before `--enforce` "
        f"ever reached the document.\nstderr:\n{mangled.stderr}"
    )
    assert mangled.returncode == EXIT_VIOLATIONS_FOUND, (
        "a document with real violations must FAIL under `--enforce` with exit "
        f"{EXIT_VIOLATIONS_FOUND} rather than being waved through.\n"
        f"exit={mangled.returncode}\nstdout:\n{mangled.stdout}\n"
        f"stderr:\n{mangled.stderr}"
    )

    report = mangled.stdout + mangled.stderr
    assert "[FAIL]" in report, (
        "`--enforce` exited non-zero but never reported the violations as "
        "failures — the maintainer cannot see WHAT is wrong with their "
        f"document.\nstdout:\n{mangled.stdout}\nstderr:\n{mangled.stderr}"
    )

    # The contrast that makes the exit code MEAN something: enforce must
    # discriminate, not merely always-fail. Without this a crafter could satisfy
    # the assertions above by making `--enforce` reject everything.
    _assert_no_traceback(clean)
    assert clean.returncode == EXIT_CLEAN, (
        "a well-formed document was FAILED under `--enforce` — the mode rejects "
        "everything, so its exit code carries no information about the "
        f"document.\nexit={clean.returncode}\nstdout:\n{clean.stdout}\n"
        f"stderr:\n{clean.stderr}"
    )
    assert "[FAIL]" not in clean.stdout, (
        f"a well-formed document was reported as failing.\nstdout:\n{clean.stdout}"
    )


# ---------------------------------------------------------------------------
# AT4 — HONEST FAILURE (GDP-3 / GDP-6). Cannot read the rules => SAY so, REFUSE.
# @driving_port @error @negative_at @real-io  @contract-shape:bounded-change
#
# Parametrized over the two resources on the UNCONDITIONAL startup path
# (cli.py:52 schema probe, cli.py:57 verb probe). Both must refuse identically:
# a damaged install is a damaged install, whichever asset is the casualty.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("resource", "adapter"),
    [
        pytest.param(SCHEMA_RESOURCE, "JsonSchemaFileLoader", id="schema"),
        pytest.param(PROTOCOL_VERBS_EN, "PlaintextVerbLoader", id="protocol-verbs"),
    ],
)
def test_validate_refuses_loud_when_a_runtime_resource_cannot_be_read(
    installed_shape: InstalledShape, resource: Path, adapter: str
) -> None:
    """Charter: '"I could not check this" is an acceptable, honest answer — as
    long as it is unmistakably that, and never dressed up as a pass.'

    With a runtime resource removed (a damaged / half-installed copy), the
    command must not quietly return a clean verdict on a document it never
    checked, and must not dump a traceback. It must refuse LOUDLY: the structured
    `health.startup.refused` event naming the adapter, exit 70, and a cure the
    maintainer can act on.

    This is the pin that stops a crafter buying AT1's green by making a `probe()`
    tolerant of a missing resource. The `protocol-verbs` case is red for a second
    reason today: `verbs.py:81` refuses with a bare `assert`, so the maintainer
    gets an `AssertionError` traceback and exit 1 rather than the structured
    refusal — the loud-failure discipline the schema adapter already has
    (schema.py:43-70) has to be extended to it (D-6, GDP-3 / GDP-6).
    """
    target = installed_shape.resource(resource)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    assert not target.exists()

    result = installed_shape.validate(installed_shape.well_formed)

    _assert_no_traceback(result)
    assert result.returncode == EXIT_STARTUP_REFUSED, (
        f"with `{resource}` unreadable, the command must refuse with exit "
        f"{EXIT_STARTUP_REFUSED} (could NOT check) — not crash, and above all "
        "not succeed.\n"
        f"exit={result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert REFUSAL_MARKER in result.stderr, (
        "the refusal was not the structured, machine-readable "
        f"`{REFUSAL_MARKER}` event.\nstderr:\n{result.stderr}"
    )
    assert adapter in result.stderr, (
        f"the refusal does not name WHICH adapter refused (expected {adapter}).\n"
        f"stderr:\n{result.stderr}"
    )
    # DESIGN commitment: the refusal names the packaged resource and the reinstall
    # cure, matching the parent fix's WHAT/WHY/HOW shape (feature-delta, Wave:
    # DESIGN, 'Failure path already correct'; D-6). Accepted by the maintainer
    # 2026-07-14 as a real contract row that otherwise had no covering AT.
    assert "reinstall" in result.stderr.lower(), (
        "the refusal does not tell the maintainer HOW to fix it (reinstall the "
        "tool). A bare path pointing inside the tool's own installation is not "
        f"an answer they can act on (GDP-3).\nstderr:\n{result.stderr}"
    )
    assert "[PASS]" not in result.stdout, (
        "the tool reported a passing verdict on a document it could not check. "
        "'Validated, no violations' and 'never validated anything' must be "
        f"impossible to confuse from the outside.\nstdout:\n{result.stdout}"
    )


# ---------------------------------------------------------------------------
# AT5a — INVARIANCE PIN, in-process. The injection seams survive the fix.
# GREEN today, must stay GREEN after.  @contract-shape:pure-function
#
# In-process ON PURPOSE: these seams are path INJECTION (schema.py:17-24,
# verbs.py:38-44), whose whole point is that they do not depend on where the
# package sits. Five existing test sites already exercise them exactly this way.
# The CLI-driven half of the same contract is AT5b.
# ---------------------------------------------------------------------------


def test_explicit_arg_and_env_override_still_resolve_the_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Schema seams: explicit arg > env var > default (schema.py:17-24).

    D-3 keeps both deliberately — the parent fix refused to ADD an override; that
    is not an argument for DELETING an existing, relied-upon one. Only the
    DEFAULT moves. This fails if the fix rips the injection chain out while
    relocating the default.
    """
    from nwave_ai.feature_delta.adapters.schema import JsonSchemaFileLoader

    explicit = tmp_path / "explicit-schema.json"
    explicit.write_text('{"title": "explicit"}', encoding="utf-8")
    via_env = tmp_path / "env-schema.json"
    via_env.write_text('{"title": "from-env"}', encoding="utf-8")

    monkeypatch.delenv("NWAVE_FEATURE_DELTA_SCHEMA", raising=False)
    assert JsonSchemaFileLoader(schema_path=explicit).load_schema() == {
        "title": "explicit"
    }, "the explicit `schema_path=` argument no longer resolves"

    monkeypatch.setenv("NWAVE_FEATURE_DELTA_SCHEMA", str(via_env))
    assert JsonSchemaFileLoader().load_schema() == {"title": "from-env"}, (
        "the NWAVE_FEATURE_DELTA_SCHEMA override no longer resolves"
    )

    assert JsonSchemaFileLoader(schema_path=explicit).load_schema() == {
        "title": "explicit"
    }, "the documented precedence (explicit > env > default) has been inverted"


def test_per_repo_verb_override_and_redos_guard_still_hold(tmp_path: Path) -> None:
    """Verb seams: the per-repo override UNIONS with the packaged defaults, and
    the ReDoS guard still rejects a catastrophic-backtracking pattern (D-3).

    `.nwave/protocol-verbs.txt` is the maintainer's own extension point. Moving
    the framework verb list into the package must not silently drop it, must not
    let it REPLACE the packaged defaults, and must not drop the guard that keeps
    a hostile override from hanging the tool.
    """
    from nwave_ai.feature_delta.adapters.verbs import PlaintextVerbLoader, ReDoSError

    project = tmp_path / "project"
    (project / ".nwave").mkdir(parents=True)

    # 1. The per-repo override is UNIONED with the packaged framework defaults —
    #    it extends them, it does not replace them.
    (project / ".nwave" / "protocol-verbs.txt").write_text(
        "bespoke-house-verb\n", encoding="utf-8"
    )
    verbs = PlaintextVerbLoader(cwd_root=project).load_protocol_verbs("en")
    assert "bespoke-house-verb" in verbs, (
        "the per-repo .nwave/protocol-verbs.txt override was dropped"
    )
    assert len(verbs) > 1, (
        "the override REPLACED the packaged framework verb list instead of "
        f"extending it — only {verbs!r} survived"
    )

    # 2. The ReDoS guard still refuses a nested unbounded quantifier (verbs.py:100).
    (project / ".nwave" / "protocol-verbs.txt").write_text(
        _REDOS_OVERRIDE, encoding="utf-8"
    )
    with pytest.raises(ReDoSError):
        PlaintextVerbLoader(cwd_root=project).probe()


# ---------------------------------------------------------------------------
# AT5b — INVARIANCE PIN, through the REAL CLI, from the install shape.
# @driving_port @error  @contract-shape:bounded-change
#
# The same seams as AT5a, but driven through the shipped entry point rather than
# the adapter — a seam that survives in-process and dies through the CLI has not
# survived. The ReDoS half is only REACHABLE once the walk-outs are fixed (today
# the schema probe refuses before the maintainer's override is ever consulted),
# which is exactly why it is red and the env half is green.
# ---------------------------------------------------------------------------


def test_env_schema_override_still_takes_precedence_from_an_installed_package(
    installed_shape: InstalledShape, tmp_path: Path
) -> None:
    """`NWAVE_FEATURE_DELTA_SCHEMA` still beats the PACKAGED default (D-3).

    Observed through the refusal itself: point the override at a corrupt schema
    and the tool must refuse naming THAT path. If the fix hard-wires the packaged
    resource and stops consulting the env var, the refusal would name the
    packaged schema instead — and this turns red.
    """
    corrupt = tmp_path / "corrupt-schema.json"
    corrupt.write_text("{ not json", encoding="utf-8")
    env = {
        **_relocated_env(installed_shape.site_packages),
        "NWAVE_FEATURE_DELTA_SCHEMA": str(corrupt),
    }

    result = installed_shape.validate(installed_shape.well_formed, env=env)

    assert result.returncode == EXIT_STARTUP_REFUSED, (
        "a corrupt schema supplied through NWAVE_FEATURE_DELTA_SCHEMA must be "
        f"refused at startup (exit {EXIT_STARTUP_REFUSED}).\n"
        f"exit={result.returncode}\nstderr:\n{result.stderr}"
    )
    assert str(corrupt) in result.stderr, (
        "the refusal does not name the schema supplied via "
        "NWAVE_FEATURE_DELTA_SCHEMA — the env override is no longer consulted, "
        f"so the documented escape hatch is dead.\nstderr:\n{result.stderr}"
    )


@pytest.mark.negative_at
def test_installed_cli_still_refuses_a_redos_verb_override(
    installed_shape: InstalledShape,
) -> None:
    """The ReDoS guard still fires through the real CLI, from an install (D-3).

    A hostile `.nwave/protocol-verbs.txt` must be refused at startup with exit 70
    and a message about the maintainer's PATTERN — not about a missing framework
    file of the tool's own, and not as a traceback. Today this is red: the schema
    probe (cli.py:52) refuses first, so the maintainer is told about the tool's
    own missing schema and the guard is never reached.
    """
    override_dir = installed_shape.work / ".nwave"
    override_dir.mkdir()
    (override_dir / "protocol-verbs.txt").write_text(_REDOS_OVERRIDE, encoding="utf-8")

    result = installed_shape.validate(installed_shape.well_formed)

    _assert_no_traceback(result)
    assert result.returncode == EXIT_STARTUP_REFUSED, (
        "a ReDoS-prone verb override must be refused with exit "
        f"{EXIT_STARTUP_REFUSED}.\nexit={result.returncode}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "JsonSchemaFileLoader" not in result.stderr, (
        "the tool refused over its OWN schema before it ever looked at the "
        "maintainer's override — the ReDoS guard is unreachable from an "
        f"install.\nstderr:\n{result.stderr}"
    )
    assert "redos" in result.stderr.lower(), (
        "the refusal does not say the maintainer's own verb PATTERN is the "
        f"problem.\nstderr:\n{result.stderr}"
    )
