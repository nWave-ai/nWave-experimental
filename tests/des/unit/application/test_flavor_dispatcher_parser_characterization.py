"""Characterization tests pinning flavor-file parsing behavior.

Locks the parsed structure of the sole REAL shipped flavor file
(`nWave/flavors/atdd_pure.yaml`) so the consolidation of
`flavor_dispatcher`'s private YAML-subset parser onto the SSOT
(`des._internal.subset_parser`) is provably behavior-preserving.

These assert CURRENT behavior (what the dispatcher already parses today) and
are the regression net across the parser swap — NOT a new feature contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des._internal import subset_parser
from des.application import flavor_dispatcher


_FLAVORS_DIR = Path(__file__).resolve().parents[4] / "nWave" / "flavors"


@pytest.mark.parametrize("flavor_id", ["atdd_pure"])
def test_dispatcher_parses_real_flavor_file_identically_to_ssot(flavor_id: str) -> None:
    """The dispatcher's flavor reader and the SSOT agree on the real inputs.

    This is the empirical parity pin: the two known divergent edges
    (block-scalar dedent, strict-indent nested mapping) are NOT exercised by
    the shipped flavor files, so the SSOT and the (now-delegating) dispatcher
    reader return identical dicts.
    """
    path = _FLAVORS_DIR / f"{flavor_id}.yaml"
    via_dispatcher = flavor_dispatcher._parse_flavor_file(path)
    via_ssot = subset_parser.load_file(path)
    assert via_dispatcher == via_ssot


def test_atdd_pure_flavor_parsed_structure_is_pinned() -> None:
    """Pin the parsed shape of the shipped atdd_pure flavor (current behavior)."""
    doc = flavor_dispatcher._parse_flavor_file(_FLAVORS_DIR / "atdd_pure.yaml")

    assert doc["flavor_id"] == "atdd_pure"
    assert doc["description"].startswith(
        "Carpaccio-driven workflow with per-slice atomic delivery."
    )
    assert doc["description"].endswith("\n")
    assert doc["required_artifacts"] == [
        "docs/feature/{feature_id}/feature-delta.md",
        "tests/**/{feature_id}/**/*.feature",
        ".nwave/telemetry/atdd-pure/{feature_id}.jsonl",
    ]

    events = doc["lifecycle_events"]
    assert isinstance(events, dict)
    assert list(events) == [
        "dispatch.pre",
        "subagent.stop",
        "commit.pre",
        "session.init",
    ]

    # f-nonbypassable-attestation slice-05 (DDD-8): dispatch.pre legitimately
    # gains the wave-dispatch guard row ahead of readiness + carpaccio. This is
    # the NEW, intended composition (not a weakening) -- the guard auto-fires on
    # every Agent/Task dispatch the PreToolUse intercept sees. The pin is updated
    # to record the 3-row composition; deleting the guard row regresses the
    # arch-test leg-3 (test_arch_wave_dispatch_guard_home), not this pin.
    # f-design-devops-review-gate slice-03 (CT-9 / DDD-5): dispatch.pre
    # legitimately gains the AT-completeness BACKSTOP row (the EXISTING
    # check-slice-at-completeness CLI, zero new gate logic) after carpaccio, so an
    # incomplete slice cannot enter DELIVER even if the DISTILL gate-out was
    # bypassed. `on_failure: warn` (advisory at the backstop; the PRIMARY block is
    # the DISTILL gate-out, nWave/waves/distill.yaml). The pin records the 4-row
    # composition; deleting the backstop row regresses the slice-03 dispatch.pre
    # AT (AT-11), not just this pin.
    dispatch_pre = events["dispatch.pre"]
    assert [g["gate_id"] for g in dispatch_pre] == [
        "verify-wave-dispatch",
        "verify-readiness-pre-dispatch",
        "carpaccio-slice-gate",
        "check-slice-at-completeness",
    ]
    assert dispatch_pre[0]["on_failure"] == "block"
    assert dispatch_pre[0]["args"] == {
        "subagent_type": "{subagent_type}",
        "prompt_path": "{prompt_path}",
    }
    assert dispatch_pre[1]["args"] == {
        "feature_id": "{feature_id}",
        "slice_id": "{slice_id}",
    }
    assert dispatch_pre[2]["args"] == {
        "feature_id": "{feature_id}",
        "entering_slice": "{slice_id}",
    }
    assert dispatch_pre[3]["on_failure"] == "warn"
    assert dispatch_pre[3]["args"] == {
        "feature_id": "{feature_id}",
        "slice_id": "{slice_id}",
    }

    # `require_reviewed_by: false` must coerce to a Python bool, not "false".
    assert events["commit.pre"][0]["args"]["require_reviewed_by"] is False
    # A gate with no args stays a bare gate dict.
    assert events["session.init"][0] == {"gate_id": "health-check", "on_failure": "log"}


def test_classic_flavor_is_absent_instead_of_parseable() -> None:
    """No parser input can reconstruct classic as an installed flavor."""
    path = _FLAVORS_DIR / "classic.yaml"
    assert not path.exists()
    with pytest.raises(FileNotFoundError):
        flavor_dispatcher._parse_flavor_file(path)


# ---------------------------------------------------------------------------
# Empty-flow-list branch characterization (M1 slice-04).
#
# `subset_parser._next_is_empty_flow_list` handles the ONE flow-style construct
# the subset supports: an explicitly empty list `[]` on its own indented line
# under an inner key of a list-of-dicts (the YAML an empty string-list profile
# renders to, e.g. an empty `feature_end_required_records` composition field).
# This branch was previously exercised only end-to-end through the shipped
# flavor files; these tests pin it directly through the public `load` driving
# port (port-to-port — the private branch is reached via the parser's public
# API, never imported directly).
# ---------------------------------------------------------------------------


def test_empty_flow_list_under_inner_key_parses_to_empty_list() -> None:
    """An `[]` on its own indented line under an inner dict key → empty list.

    Pins the `_next_is_empty_flow_list` positive branch: the inner key has an
    empty `after_colon`, and the line beneath it is the sole flow token `[]`,
    so the value coerces to a Python `[]` (NOT the string `"[]"`).
    """
    text = (
        "composition:\n"
        "  - flavor_id: atdd_pure\n"
        "    feature_end_required_records:\n"
        "      []\n"
        "    on_failure: block\n"
    )

    doc = subset_parser.load(text)

    assert doc == {
        "composition": [
            {
                "flavor_id": "atdd_pure",
                "feature_end_required_records": [],
                "on_failure": "block",
            }
        ]
    }


def test_inline_empty_flow_list_scalar_parses_to_empty_list() -> None:
    """A bare inline `key: []` coerces to a Python `[]` (NOT the string `"[]"`).

    Pins the `_coerce_scalar` empty-flow-list branch added for the
    mode-registry-single-locus `skill_load_set` block: the classic flavor
    DECLARES the crafter with `conditional: []` (declared-empty is a real
    answer), and `yaml.safe_load` parity requires the inline shape to parse
    to an empty list.
    """
    text = "skill_load_set:\n  nw-software-crafter:\n    conditional: []\n"

    doc = subset_parser.load(text)

    assert doc == {"skill_load_set": {"nw-software-crafter": {"conditional": []}}}


def test_quoted_empty_brackets_scalar_stays_a_string() -> None:
    """A QUOTED `"[]"` scalar is untouched by the empty-flow-list coercion.

    Pins the boundary of the `_coerce_scalar` extension: quote-stripping
    happens first, so an author who writes the literal two-character string
    `"[]"` keeps a string — exactly `yaml.safe_load` behavior.
    """
    doc = subset_parser.load('marker: "[]"\n')

    assert doc == {"marker": "[]"}


def test_non_empty_flow_list_under_inner_key_stays_unsupported() -> None:
    """A non-empty flow list `[a, b]` under an inner key is NOT silently parsed.

    Pins the negative half of `_next_is_empty_flow_list`: only the bare `[]`
    shape is recognised. A populated flow list falls through to the strict
    mapping walker, which raises `ValueError` rather than mis-parse it — the
    fail-loud contract that keeps an unsupported construct from masking a
    schema-authoring bug.
    """
    text = (
        "composition:\n"
        "  - flavor_id: atdd_pure\n"
        "    feature_end_required_records:\n"
        "      [a, b]\n"
    )

    with pytest.raises(ValueError):
        subset_parser.load(text)
