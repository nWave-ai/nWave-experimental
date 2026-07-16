"""Regression AT (RCA-confirmed, clear locus): ``des charter-scaffold`` reads
its expectation-charter template via a REPO-ROOT-RELATIVE path ONLY
(``_TEMPLATE_RELATIVE_PATH = Path("nWave/templates/expectation-charter.md")``,
resolved as ``repo_root / _TEMPLATE_RELATIVE_PATH`` in
``_load_template_skeleton_or_degrade``, ``src/des/cli/charter_scaffold.py``
~line 399).

In a CONSUMER repo (one that installed nWave but carries no ``nWave/``
source tree of its own) the template is absent at that repo-root-relative
path -- the tool degrades LOUD with ``missing-charter-template``
(``VERDICT_MISSING_CHARTER_TEMPLATE``). But the template genuinely SHIPS
with the install: it lives at ``<install-lib>/nWave/templates/
expectation-charter.md`` (installed layout) and at
``<repo-root>/nWave/templates/expectation-charter.md`` in the dev checkout
-- i.e. it always sits alongside the ``charter_scaffold.py`` module itself,
``Path(__file__).parents[3] / "nWave/templates/expectation-charter.md"``,
regardless of where ``--repo-root`` points. The tool never looks there.

Fix direction (for the crafter -- NOT implemented here): resolve the
template MODULE-RELATIVE first (works in both the dev checkout and the
installed lib, since both keep the same ``.../nWave/templates/...``
sibling-of-source-root shape relative to ``charter_scaffold.py``), falling
back to ``repo_root``-relative, and degrade LOUD (naming BOTH locations it
tried) only when the shipped template is found in NEITHER.

covers: RCA -- `des charter-scaffold` consumer-repo template resolution
(`src/des/cli/charter_scaffold.py::_load_template_skeleton_or_degrade`)

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`): NOT
a missing-module RED (the tool is already shipped) -- this is a BEHAVIOURAL
RED. `test_consumer_repo_without_own_nwave_templates_still_produces_
charter_scaffold` drives the real, already-shipped
`des.cli.charter_scaffold.main(argv)` IN-PROCESS against a `tmp_path`
fixture repo that deliberately has NO local `nWave/templates/` (the
consumer shape) and asserts the DESIRED (not-yet-true) outcome -- a
successful scaffold, found via the shipped module-relative template. The
CURRENT implementation's actual outcome (a `missing-charter-template`
degrade) makes the assertion raise a plain `AssertionError` --
fail-for-the-right-reason, never a collection or import error.

Driving surface: `des.cli.charter_scaffold.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture repo (composition-root driving port
-- Mandate 16, driving-port-only boundary). No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli import charter_scaffold
from des.cli.charter_scaffold import VERDICT_MISSING_CHARTER_TEMPLATE
from des.cli.validate_feature_delta import VERDICT_ACCEPTED


FEATURE_ID = "consumer-charter-template-fix"

VALUE_STATEMENT = "A visitor books a seat and sees a confirmation"

SLICE_PLAN_FEATURE_DELTA = f"""# Feature-delta -- {FEATURE_ID}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | {VALUE_STATEMENT} | pending |  | first observable slice |
"""

#: The real, shipped `nWave/templates/expectation-charter.md` "Template"
#: section headings -- what a correctly-resolved scaffold must carry
#: regardless of WHICH location the tool found the template at.
_TEMPLATE_SECTION_HEADINGS = (
    "## Intent",
    "## Preconditions",
    "## Charter",
    "## Expected observations (oracle)",
    "## Session log (append-only)",
)

#: The real shipped template asset, located via the MODULE's own position --
#: `src/des/cli/charter_scaffold.py` -> `parents[3]` is the repo root in this
#: dev checkout, mirroring the fix direction's own resolution shape. Used
#: only to sanity-check the fixture precondition (the shipped asset exists),
#: never to duplicate/hardcode the template's byte content in this test.
_REAL_REPO_ROOT = Path(charter_scaffold.__file__).resolve().parents[3]
_REAL_TEMPLATE_PATH = _REAL_REPO_ROOT / "nWave" / "templates" / "expectation-charter.md"

#: A byte-faithful copy of the shipped template's "Template" skeleton block,
#: used ONLY to seed a fixture repo's OWN `nWave/templates/` in the dev-case
#: pin scenario (mirrors `test_charter_scaffold.py::TEMPLATE_SKELETON`).
DEV_TEMPLATE_SKELETON = """# <intent, as a human sentence>
ID: EXP-<feature>-<n> · Spec rows: <R…> · Persona: <who>

## Intent
<the value statement: what the user accomplishes, why it matters>

## Preconditions
<start recipe: how to run the system from a clean state, seed state>

## Charter
Explore <area> via <surface: browser/CLI/API> to verify <intent>.

## Expected observations (oracle)
- <observable outcome, user language>
- <negative: what must NOT happen>

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""


def _write_feature_delta(repo_root: Path, feature_id: str, content: str) -> Path:
    delta_dir = repo_root / "docs" / "feature" / feature_id
    delta_dir.mkdir(parents=True, exist_ok=True)
    path = delta_dir / "feature-delta.md"
    path.write_text(content, encoding="utf-8")
    return path


def _expectations_dir(repo_root: Path, feature_id: str) -> Path:
    return repo_root / "docs" / "product" / "expectations" / feature_id


def _seed_own_template(repo_root: Path) -> None:
    template_dir = repo_root / "nWave" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "expectation-charter.md").write_text(
        DEV_TEMPLATE_SKELETON, encoding="utf-8"
    )


def _invoke(repo_root: Path, capsys, feature_id: str = FEATURE_ID) -> tuple[int, dict]:
    """The driving call every test uses: in-process `main()`, stdout
    captured and parsed as the `--format json` contract token."""
    exit_code = charter_scaffold.main(
        [
            "--feature-id",
            feature_id,
            "--repo-root",
            str(repo_root),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


# ===========================================================================
# 1. RED-today core -- the bug observable in a CONSUMER-shape workspace.
# ===========================================================================


def test_consumer_repo_without_own_nwave_templates_still_produces_charter_scaffold(
    tmp_path: Path, capsys
) -> None:
    """A CONSUMER-shape workspace (a `--repo-root` that carries a
    feature-delta with a Slice Plan but NO `nWave/templates/` directory of
    its own -- e.g. an installed nWave consumer project) must still produce
    the expectation-charter skeleton, found via the SHIPPED template that
    always sits alongside the `charter_scaffold.py` module itself. It must
    NOT emit `missing-charter-template`.

    Deliberately does NOT seed `consumer_repo/nWave/templates/` -- doing so
    would mask the bug; the whole point is that the tool must find the
    SHIPPED template (module-relative), not a copy planted in the fixture.
    """
    assert _REAL_TEMPLATE_PATH.is_file(), (
        "test precondition: the shipped nWave/templates/expectation-charter.md "
        f"must exist at {_REAL_TEMPLATE_PATH} for this AT to be meaningful"
    )

    consumer_repo = tmp_path / "consumer-repo"
    consumer_repo.mkdir()
    _write_feature_delta(consumer_repo, FEATURE_ID, SLICE_PLAN_FEATURE_DELTA)
    assert not (consumer_repo / "nWave").exists(), (
        "fixture bug: the consumer repo must NOT carry its own nWave/ tree "
        "-- seeding one would mask the defect under test"
    )

    exit_code, payload = _invoke(consumer_repo, capsys)

    assert payload.get("verdict") != VERDICT_MISSING_CHARTER_TEMPLATE, (
        "des charter-scaffold degraded with 'missing-charter-template' in a "
        "consumer-shape repo (no local nWave/templates/) even though the "
        f"template genuinely SHIPS at {_REAL_TEMPLATE_PATH} -- today the tool "
        "resolves the template repo-root-relative ONLY "
        "(repo_root / 'nWave/templates/expectation-charter.md'), so a "
        "consumer repo with no nWave/templates/ of its own always misses "
        f"it. payload={payload!r}"
    )
    assert exit_code == 0, (
        "expected a successful scaffold run in the consumer repo, got "
        f"exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("verdict") == VERDICT_ACCEPTED, payload

    expectations_dir = _expectations_dir(consumer_repo, FEATURE_ID)
    created_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )
    assert created_files, (
        f"no charter scaffold file was produced in the consumer repo -- "
        f"payload={payload!r}"
    )
    scaffold_content = (expectations_dir / created_files[0]).read_text(encoding="utf-8")

    # The produced skeleton matches the SHIPPED template's sections.
    for heading in _TEMPLATE_SECTION_HEADINGS:
        assert heading in scaffold_content, (
            f"produced scaffold is missing section {heading!r} from the "
            f"SHIPPED template -- scaffold_content:\n{scaffold_content}"
        )
    assert VALUE_STATEMENT in scaffold_content


# ===========================================================================
# 2. Dev-case pin -- must not regress the existing repo-root-relative path.
# ===========================================================================


def test_dev_checkout_repo_with_its_own_nwave_templates_still_produces_charter_scaffold(
    tmp_path: Path, capsys
) -> None:
    """A workspace that DOES carry its own `nWave/templates/
    expectation-charter.md` (the dev-checkout shape, `--repo-root` pointing
    at a full source tree) keeps working exactly as today -- the
    repo-root-relative resolution stays valid (as a first hit or a
    fallback); it was only INSUFFICIENT ALONE for a consumer repo. Already
    green today; pinned so the fix cannot regress it.
    """
    dev_repo = tmp_path / "dev-repo"
    dev_repo.mkdir()
    _seed_own_template(dev_repo)
    _write_feature_delta(dev_repo, FEATURE_ID, SLICE_PLAN_FEATURE_DELTA)

    exit_code, payload = _invoke(dev_repo, capsys)

    assert exit_code == 0, (
        "expected a successful scaffold run in the dev-checkout repo, got "
        f"exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("verdict") == VERDICT_ACCEPTED, payload

    expectations_dir = _expectations_dir(dev_repo, FEATURE_ID)
    created_files = (
        sorted(p.name for p in expectations_dir.glob("*.md"))
        if expectations_dir.is_dir()
        else []
    )
    assert created_files, f"no scaffold produced -- payload={payload!r}"
    scaffold_content = (expectations_dir / created_files[0]).read_text(encoding="utf-8")
    for heading in _TEMPLATE_SECTION_HEADINGS:
        assert heading in scaffold_content
    assert VALUE_STATEMENT in scaffold_content


# ===========================================================================
# 3. Negative witness (GDP-6) -- loud degrade only when found NOWHERE.
# ===========================================================================


@pytest.mark.negative_at
def test_charter_scaffold_never_silently_succeeds_when_shipped_template_is_found_nowhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """When the shipped charter template can be found at NEITHER the
    module-relative location (next to `charter_scaffold.py`, wherever it is
    installed) NOR the `--repo-root`-relative location, the tool must
    degrade LOUD with `missing-charter-template` AND its `detail` must NAME
    BOTH locations it looked at -- never a silent/empty charter, never a
    one-location-only diagnostic that leaves an operator guessing where
    else to look.

    Simulated by monkeypatching `charter_scaffold.__file__` to an isolated
    location with no `nWave/templates/` nearby -- a runtime module-attribute
    override local to this test, NO production code touched -- combined
    with a `--repo-root` that also carries no `nWave/templates/` of its own.

    RED today for the right reason: the CURRENT implementation only checks
    the repo-root-relative location (it never reads `__file__` at all), so
    its degrade `detail` names ONE path only -- the module-relative
    location this test expects named is never even considered, so the
    detail-naming assertions below fail with a genuine `AssertionError`.
    """
    isolated_install_root = tmp_path / "isolated-install"
    isolated_module_dir = isolated_install_root / "src" / "des" / "cli"
    isolated_module_dir.mkdir(parents=True)
    fake_module_file = isolated_module_dir / "charter_scaffold.py"
    fake_module_file.write_text(
        "# fake module location for this AT -- no nWave/templates/ nearby\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(charter_scaffold, "__file__", str(fake_module_file))

    isolated_repo = tmp_path / "isolated-repo"
    isolated_repo.mkdir()
    _write_feature_delta(isolated_repo, FEATURE_ID, SLICE_PLAN_FEATURE_DELTA)
    assert not (isolated_repo / "nWave").exists()
    assert not (isolated_install_root / "nWave").exists()

    exit_code, payload = _invoke(isolated_repo, capsys)

    # Positive floor: never a silent/empty charter -- a LOUD non-zero reject.
    assert exit_code != 0, (
        "the shipped template is findable at NEITHER the (faked) "
        "module-relative location NOR the repo-root-relative location -- "
        f"the tool must degrade LOUD (non-zero exit), got "
        f"exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("verdict") == VERDICT_MISSING_CHARTER_TEMPLATE, payload
    expectations_dir = _expectations_dir(isolated_repo, FEATURE_ID)
    assert not expectations_dir.is_dir() or not list(expectations_dir.glob("*.md")), (
        "no scaffold file may exist after a degrade-LOUD reject -- "
        f"expectations_dir={expectations_dir}"
    )

    # The negative oracle this AT exists for: the detail must name BOTH
    # locations tried, not just the repo-root-relative one.
    detail = str(payload.get("detail", ""))
    module_relative_hint = str(
        isolated_install_root / "nWave" / "templates" / "expectation-charter.md"
    )
    repo_root_hint = str(
        isolated_repo / "nWave" / "templates" / "expectation-charter.md"
    )
    assert module_relative_hint in detail, (
        "degrade-LOUD detail must name the MODULE-RELATIVE location it "
        "looked at (so an operator sees BOTH paths were tried, not just "
        f"one) -- expected {module_relative_hint!r} in detail={detail!r}"
    )
    assert repo_root_hint in detail, (
        "degrade-LOUD detail must also name the REPO-ROOT-RELATIVE "
        f"location it looked at -- expected {repo_root_hint!r} in "
        f"detail={detail!r}"
    )
