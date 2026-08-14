"""Regression: `des charter-scaffold` must refuse LOUD, never silently prefer
the installed copy, when its own developer-checkout has a DIFFERENT charter
template from the shipped/installed one (Mikado D82).

Prior behaviour (`_load_template_skeleton_or_degrade`,
`src/des/cli/charter_scaffold.py`): tried the module-relative (shipped/
installed) location FIRST, falling back to `repo_root`-relative only on an
`OSError` (i.e. only when the module-relative copy was ABSENT). When BOTH
existed but disagreed, the module-relative copy always won -- silently, with
no signal that the operator's own checkout carried a different template.
DISTILL produces every feature's charters through this tool, so a divergence
here propagates into every feature scaffolded while it stood.

Fix: routed through the same `des.runtime.packaged_asset.resolve_packaged_asset`
producer `skill_normative_gate` and `wave_gate_stack_dispatch` already use
(the direct migration precedent, commit `0435584c7`). Two copies whose content
digests differ classify as `AssetOrigin.AMBIGUOUS`; the caller now refuses with
`VERDICT_AMBIGUOUS_CHARTER_TEMPLATE`, naming both paths, instead of choosing.

Fixture convention mirrors the existing AMBIGUOUS pins for the same producer
(`tests/bugs/des/test_skill_normative_gate_manifest_resolves_regardless_of_cwd.py
::test_two_disagreeing_copies_are_refused_instead_of_silently_picked`,
`tests/bugs/des/test_installed_waves_registry_silent_empty.py
::test_resolve_packaged_asset_classifies_divergent_waves_copies_as_ambiguous`):
`resolve_packaged_asset`'s checkout detection walks `.git` adjacency from
`start`, so the fixture repo must carry a `.git` marker for the developer
checkout side of the comparison to be considered at all.

Driving surface: `des.cli.charter_scaffold.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture repo (composition-root driving port --
Mandate 16, driving-port-only boundary). No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli import charter_scaffold
from des.cli.charter_scaffold import (
    VERDICT_AMBIGUOUS_CHARTER_TEMPLATE,
    VERDICT_MISSING_CHARTER_TEMPLATE,
)


FEATURE_ID = "ambiguous-charter-template-fix"
DIRECT_VALUE = "Operator sees the expected system behavior"

#: The real, shipped template -- located via the module's own position, same
#: anchor `_load_template_skeleton_or_degrade` uses for its `installed`
#: candidate. Used only to read real bytes / confirm the fixture precondition,
#: never to duplicate the template's content by hand.
_REAL_REPO_ROOT = Path(charter_scaffold.__file__).resolve().parents[3]
_REAL_TEMPLATE_PATH = _REAL_REPO_ROOT / "nWave" / "templates" / "expectation-charter.md"


def _expectations_dir(repo_root: Path, feature_id: str) -> Path:
    return repo_root / "docs" / "product" / "expectations" / feature_id


def _seed_checkout_template(repo_root: Path, content: str) -> Path:
    """Mark `repo_root` as a developer checkout (`.git` adjacency, the exact
    signal `resolve_packaged_asset`'s checkout search keys on) and give it
    its own copy of the charter template."""
    (repo_root / ".git").mkdir(parents=True)
    template_dir = repo_root / "nWave" / "templates"
    template_dir.mkdir(parents=True)
    path = template_dir / "expectation-charter.md"
    path.write_text(content, encoding="utf-8")
    return path


def _invoke(repo_root: Path, capsys, feature_id: str = FEATURE_ID) -> tuple[int, dict]:
    exit_code = charter_scaffold.main(
        [
            "--feature-id",
            feature_id,
            "--repo-root",
            str(repo_root),
            "--seed-mode",
            "direct-value",
            "--value",
            DIRECT_VALUE,
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


@pytest.mark.negative_at
def test_divergent_checkout_template_is_refused_not_silently_shadowed(
    tmp_path: Path, capsys
) -> None:
    """The exact defect this migration closes: a developer checkout carrying
    its OWN, DIFFERENT charter template from the shipped/installed one must
    make `des charter-scaffold` refuse LOUD -- never silently scaffold from
    the installed copy while ignoring the operator's own template."""
    assert _REAL_TEMPLATE_PATH.is_file(), (
        "test precondition: the shipped nWave/templates/expectation-charter.md "
        f"must exist at {_REAL_TEMPLATE_PATH} for this AT to be meaningful"
    )
    real_bytes = _REAL_TEMPLATE_PATH.read_bytes()

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    divergent_content = (
        "## Template\n\nDIVERGENT local edit, not the shipped template.\n"
    )
    assert divergent_content.encode("utf-8") != real_bytes, (
        "fixture bug: the checkout's own template must differ from the real "
        "shipped one for this to exercise AMBIGUOUS, not IDENTICAL"
    )
    checkout_template_path = _seed_checkout_template(checkout, divergent_content)

    exit_code, payload = _invoke(checkout, capsys)

    assert exit_code != 0, (
        "a checkout template that DIFFERS from the shipped/installed copy "
        f"must refuse LOUD (non-zero exit); got exit_code={exit_code!r}, "
        f"payload={payload!r}"
    )
    assert payload.get("verdict") == VERDICT_AMBIGUOUS_CHARTER_TEMPLATE, (
        "expected the AMBIGUOUS-charter-template verdict naming the "
        f"divergence, got payload={payload!r}"
    )
    assert payload.get("verdict") != VERDICT_MISSING_CHARTER_TEMPLATE, (
        "a genuinely divergent (found-on-both-sides) template must never be "
        "reported as merely missing -- that would hide the real defect "
        f"(silent installed-preference) behind an unrelated verdict. "
        f"payload={payload!r}"
    )

    detail = str(payload.get("detail", ""))
    assert str(checkout_template_path) in detail, (
        "the refusal detail must name the operator's own checkout copy so "
        f"they know where to look -- detail={detail!r}"
    )
    assert str(_REAL_TEMPLATE_PATH) in detail, (
        "the refusal detail must also name the installed/shipped copy it "
        f"disagreed with -- detail={detail!r}"
    )

    expectations_dir = _expectations_dir(checkout, FEATURE_ID)
    assert not expectations_dir.is_dir() or not list(expectations_dir.glob("*.md")), (
        "no scaffold file may exist after an AMBIGUOUS degrade-LOUD refusal -- "
        f"expectations_dir={expectations_dir}"
    )


def test_checkout_template_identical_to_shipped_resolves_without_ceremony(
    tmp_path: Path, capsys
) -> None:
    """The `differs` test is load-bearing (mirrors
    `packaged_asset`'s own `test_identical_copies_resolve_without_ceremony`):
    a checkout copy that is byte-IDENTICAL to the shipped template is not
    ambiguity -- refusing there would charge the operator for nothing."""
    real_bytes = _REAL_TEMPLATE_PATH.read_bytes()

    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / ".git").mkdir(parents=True)
    template_dir = checkout / "nWave" / "templates"
    template_dir.mkdir(parents=True)
    (template_dir / "expectation-charter.md").write_bytes(real_bytes)

    exit_code, payload = _invoke(checkout, capsys)

    assert exit_code == 0, (
        "identical checkout/installed templates must resolve without "
        f"ceremony -- got exit_code={exit_code!r}, payload={payload!r}"
    )
    assert payload.get("verdict") == "accepted", payload
