"""JSON-conversion faithfulness + fail-closed contract for the omission-classes SSOT.

R2-hardening (option E, Ale-ratified 2026-06-03): the bundled DES runtime carries
ONE forbidden external import -- ``import yaml`` at
``src/des/application/coverage_map_verify_service.py:37`` -- the SOLE violation of
the stdlib-only DES-bundle invariant (CI-enforced by
``tests/build/acceptance/plugin/steps/test_des_bundle_steps.py:142``, which scans
the bundled ``scripts/des/**`` and fails on any of {yaml, pyyaml, pydantic,
requests, toml}). The import is used in EXACTLY one place: ``_load_omission_class_ids``
(``:214-246``) parses ``nWave/data/omission-classes.yaml`` via ``yaml.safe_load``
to extract the ordered list of ``omission-classes[].id`` strings.

Option E is PURE single-SSOT: the data is RE-AUTHORED as JSON
(``nWave/data/omission-classes.json``), ``_load_omission_class_ids`` reads it with
stdlib ``json``, ``import yaml`` is removed, AND the old ``omission-classes.yaml`` is
DELETED so JSON becomes the ONLY representation. JSON is stdlib on both tiers -- no
hand-rolled parser, no build-compile step, and CRUCIALLY NO DRIFT SURFACE (one
representation, not two gated copies). This is the whole point of E over the rejected
F (yaml-kept-and-gated): a second representation that must be kept in sync is exactly
the drift surface E exists to remove. Matches the SF I3 'JSON for contracts'
convention (cross-tier-coherent).

Because there is only ONE SSOT after the conversion, this test MUST depend only on
the JSON -- it CANNOT re-derive an oracle from a live YAML that is being deleted (that
would recreate the very two-representation drift surface E removes). So the faithful
class-id set is pinned HERE as the Published-Language CONTRACT LITERAL: the six ids
the YAML authored, frozen in this test. The one-time conversion-faithfulness check
(does the JSON match the old YAML ids?) is the CRAFTER's A_GREEN responsibility during
the conversion; the pinned 6-id contract below IS the faithful set the JSON must
satisfy thereafter, with no YAML dependency.

This is a CONTRACT / drift-guard test (NOT an acceptance test driving the feature
through a port). It legitimately imports the production ``_load_omission_class_ids``
(the SUT of THIS contract test IS the parser's behaviour over the real JSON data).
Same Mandate-13 carve-out as the sibling
``test_coverage_map_verify_core_port_parity.py``: a focused integration test of a
pure config-parsing application function is the right tier -- it is not a hook/CLI
driving-port case, so a direct call to the parse function under
``tests/des/integration/`` is appropriate per the codebase convention (this file
sits beside that sibling drift-guard for the SAME module). The test is stdlib +
production-import only (no ``yaml`` import -- the oracle is the pinned literal).

RED-FOR-RIGHT-REASON (pre-DELIVER gate): ``nWave/data/omission-classes.json`` does
NOT exist yet AND ``_load_omission_class_ids`` still reads the ``.yaml``. The
pinned-contract vectors (JSON absent) and the fail-closed vectors (reader still on
YAML) fail with a SEMANTIC ``pytest.fail`` carrying a ``MISSING_FUNCTIONALITY``
marker -- a RED classification, NOT a BROKEN ``ImportError`` (Mandate 7: RED not
BROKEN). DELIVER clears RED by (a) authoring ``omission-classes.json`` as a faithful
conversion of the six pinned ids, (b) swapping the reader to ``json.load`` (removing
``import yaml``), and (c) deleting the now-orphan ``omission-classes.yaml``.

Layer note (Mandate 9): this is a layer-1/2 pure-ish config-parse over a FIXED real
data file and a CLOSED, enumerable set of fail-closed vectors -> pinned literal +
parametrize, NOT PBT (falsifier-gate §4-bis: finite + listable; the faithful id-tuple
is a single fixed contract, the fail-closed cases are a closed set).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


# --- locate the real SSOT data + the production parser ------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_JSON_SSOT = _REPO_ROOT / "nWave" / "data" / "omission-classes.json"

_PRODUCTION_MODULE = "des.application.coverage_map_verify_service"

# The Published-Language CONTRACT: the exact ordered class-ids the omission-classes
# SSOT authors. Pinned as a literal so this test depends ONLY on the JSON SSOT, never
# on the YAML being deleted (option E single-SSOT). These six ids were captured from
# the canonical omission-classes.yaml at conversion time; the JSON the crafter authors
# MUST parse to exactly this tuple. Adding/removing a class is a deliberate contract
# change that updates BOTH the JSON and this literal -- the cardinality-agnostic gate
# in production honours whatever the JSON publishes, while this test pins the current
# authored set.
_EXPECTED_CLASS_IDS: tuple[str, ...] = (
    "environmental-domain-dropped",
    "behavioural-state-or-transition-dropped",
    "process-mode-or-flag-combination-dropped",
    "negative-or-robustness-domain-dropped",
    "residue-was-not-carried-forward",
    "not-applicable-marker-without-attestation",
)


def _load_class_ids():
    """Return the production ``_load_omission_class_ids`` callable.

    Imports the production parser. The module exists today (it still reads YAML);
    the RED signal in this file comes from the DATA layer (JSON absent) + the
    reader-still-on-YAML state, surfaced per-test as semantic MISSING_FUNCTIONALITY,
    never a BROKEN import error.
    """
    module = importlib.import_module(_PRODUCTION_MODULE)
    return module._load_omission_class_ids


# --- 1. Conversion faithfulness (pinned contract over the REAL JSON data) ------


@pytest.mark.integration
def test_json_parse_returns_pinned_contract_class_ids() -> None:
    """The JSON-based parse returns EXACTLY the pinned ordered id-tuple contract.

    Loads ``nWave/data/omission-classes.json`` through the PRODUCTION
    ``_load_omission_class_ids`` and asserts the result equals the six pinned
    Published-Language class-ids -- so the JSON conversion is provably faithful to
    the authored omission classes: no class silently dropped, added, reordered, or
    renamed. The assertion depends ONLY on the JSON SSOT (option E single-SSOT); the
    expected set is the frozen contract literal, NOT a live-YAML oracle.

    RED-for-right-reason: until DELIVER authors ``omission-classes.json`` AND swaps
    the reader to ``json``, this fails with MISSING_FUNCTIONALITY (the JSON file is
    absent; the production parser still reads the to-be-deleted YAML).
    """
    if not _JSON_SSOT.is_file():
        pytest.fail(
            "MISSING_FUNCTIONALITY: nWave/data/omission-classes.json does not exist "
            "yet (option E removes `import yaml` by re-authoring the omission-classes "
            "data as JSON, reading it with stdlib `json`, and deleting the YAML). "
            "DELIVER must author it so it parses to the six pinned class-ids."
        )

    production_parse = _load_class_ids()
    produced = production_parse(_JSON_SSOT)

    assert produced is not None, (
        "MISSING_FUNCTIONALITY: _load_omission_class_ids returned None over the real "
        "omission-classes.json -- the reader has not been swapped to `json` yet, or "
        "the JSON shape does not satisfy the omission-classes[].id contract."
    )
    assert produced == _EXPECTED_CLASS_IDS, (
        "JSON conversion is UNFAITHFUL to the pinned class-id contract: "
        f"json-parse produced {produced!r} but the contract is {_EXPECTED_CLASS_IDS!r}. "
        "The conversion dropped / added / reordered / renamed a class-id."
    )


@pytest.mark.integration
def test_json_parse_preserves_all_six_authored_classes() -> None:
    """The conversion preserves the FULL authored cardinality (no silent N-1 drop).

    A complementary, cardinality-explicit guard on the same faithfulness property:
    the SSOT authors exactly six classes; the JSON parse MUST return a tuple of that
    length with no duplicates. Pins "all authored classes survive the conversion"
    against the pinned contract length -- json-only, no YAML dependency.
    """
    if not _JSON_SSOT.is_file():
        pytest.fail(
            "MISSING_FUNCTIONALITY: nWave/data/omission-classes.json does not exist "
            "yet -- DELIVER authors it as the option-E faithful conversion."
        )

    production_parse = _load_class_ids()
    produced = production_parse(_JSON_SSOT)

    assert produced is not None, (
        "MISSING_FUNCTIONALITY: parser returned None over real omission-classes.json."
    )
    assert len(produced) == len(_EXPECTED_CLASS_IDS), (
        f"cardinality drift: json-parse has {len(produced)} classes, "
        f"the pinned contract has {len(_EXPECTED_CLASS_IDS)}."
    )
    assert len(set(produced)) == len(produced), (
        f"duplicate class-id in json-parse output: {produced!r}."
    )


# --- 2. Fail-closed contract preserved across the format swap (RC-G1) ---------
#
# Closed, enumerable set of malformed/empty JSON shapes the swapped reader MUST
# refuse with ``None`` (RC-G1 non-empty floor, §4.1a -- the caller treats ``None``
# as MalformedInput). These probe the JSON reader directly via tmp files, so they
# exercise the post-swap branch even before the real SSOT is converted -- but the
# json reader does not exist yet, so they too are RED-for-right-reason until DELIVER.

# (label, file-contents-or-None). ``None`` contents => the file is absent.
_FAIL_CLOSED_VECTORS: dict[str, str | None] = {
    "absent-file": None,
    "empty-file": "",
    "malformed-json": "{ not valid json ",
    "json-not-an-object": "[1, 2, 3]",
    "missing-omission-classes-key": '{"schema-version": "2026-05-24"}',
    "omission-classes-not-a-list": '{"omission-classes": {"id": "x"}}',
    "empty-omission-classes-list": '{"omission-classes": []}',
    "entry-not-an-object": '{"omission-classes": ["just-a-string"]}',
    "entry-missing-id": '{"omission-classes": [{"title": "no id here"}]}',
    "entry-blank-id": '{"omission-classes": [{"id": "   "}]}',
    "entry-non-string-id": '{"omission-classes": [{"id": 42}]}',
}


@pytest.mark.integration
@pytest.mark.parametrize("label", sorted(_FAIL_CLOSED_VECTORS))
def test_json_reader_fails_closed_on_malformed_or_empty(
    label: str, tmp_path: Path
) -> None:
    """The swapped JSON reader returns ``None`` for every malformed / empty shape.

    Preserves the RC-G1 fail-closed contract across the yaml->json swap: file
    absent, empty file, malformed JSON, wrong document shape, and per-entry id
    defects (missing / blank / non-string) ALL yield ``None`` so the caller refuses
    rather than vacuously passing a zero-class or garbage file.

    NOTE: the ``empty-omission-classes-list`` vector returns an EMPTY TUPLE today
    under the YAML reader (parseable, zero classes). This vector pins the SWAPPED
    reader's behaviour to MATCH whatever the YAML reader did -- the crafter must
    keep empty-list => empty-tuple (the caller, not the parser, applies the RC-G1
    non-empty floor). It is included to lock parse-shape parity, not to assert
    ``None`` for the empty-list case.

    RED-for-right-reason: until DELIVER swaps ``_load_omission_class_ids`` to
    ``json.load``, feeding it a ``.json`` file is undefined behaviour (the function
    still calls ``yaml.safe_load``). We assert the post-swap contract; before the
    swap the test fails because the reader is not yet JSON-based.
    """
    production_parse = _load_class_ids()
    module = importlib.import_module(_PRODUCTION_MODULE)

    # Guard: the reader must be JSON-based for this contract to be meaningful.
    # `import yaml` still present => the swap has not happened => RED.
    module_source = Path(module.__file__).read_text(encoding="utf-8")
    if "import yaml" in module_source or "yaml.safe_load" in module_source:
        pytest.fail(
            "MISSING_FUNCTIONALITY: _load_omission_class_ids still parses YAML "
            "(`import yaml` / `yaml.safe_load` present in "
            f"{Path(module.__file__).name}). Option E swaps it to stdlib `json`; "
            "the fail-closed contract is asserted against the JSON reader."
        )

    contents = _FAIL_CLOSED_VECTORS[label]
    if contents is None:
        target = tmp_path / "omission-classes.json"  # never created => absent
    else:
        target = tmp_path / "omission-classes.json"
        target.write_text(contents, encoding="utf-8")

    result = production_parse(target)

    if label == "empty-omission-classes-list":
        assert result == (), (
            "empty omission-classes list must parse to an EMPTY TUPLE (parseable, "
            "zero classes) -- the RC-G1 non-empty floor is the caller's job, not "
            f"the parser's. Got {result!r}."
        )
    else:
        assert result is None, (
            f"fail-closed contract broken for {label!r}: expected None "
            f"(MalformedInput, RC-G1 §4.1a) but got {result!r}."
        )
