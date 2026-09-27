"""Every terminal accounts for the WHOLE declared population, and never crashes.

These oracles drive the application boundary -- ``cross_agreement`` -- directly,
because that is where the promise "returns a terminal rather than raising" is
owned. A catch at the CLI would leave the in-process drivers, and every future
caller, without it.

The parties here are tiny committed-in-test programs over a synthetic tree rather
than the repository's real producer: the observation under test is about the
CHECKER's accounting, not about any real contract, and the acceptance corpus
already crosses the real one. What is NOT synthesised is the failure itself --
each unresolvable fact below is a real fact about a real run, and none of them
depends on the euid, so none can pass vacuously under a root CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.application import agreement_crossing
from des.application.agreement_crossing import CrossingOutcome, cross_agreement


CONTRACT = "unit.census.contract.v1"

#: A producer that really writes a real artifact, in as few bytes as possible.
PRODUCER_SOURCE = (
    "import sys\n"
    "with open(sys.argv[1], 'w', encoding='utf-8') as handle:\n"
    "    handle.write('{\"ok\": true}')\n"
)

#: A consumer that really reads the artifact and accepts it by its exit code.
ACCEPTING_SOURCE = (
    "import json, sys\n"
    "with open(sys.argv[1], encoding='utf-8') as handle:\n"
    "    json.load(handle)\n"
)

#: An ordinary party whose note is simply not UTF-8. It is not a crash fixture.
LATIN1_SOURCE = (
    "import json, sys\n"
    "with open(sys.argv[1], encoding='utf-8') as handle:\n"
    "    json.load(handle)\n"
    "sys.stderr.buffer.write('donn\\u00e9es conformes\\n'.encode('latin-1'))\n"
)


def _consumer(name: str, source: str) -> dict:
    return {"name": name, "argv": ["python3", "-c", source, "{artifact}"]}


def _write_declaration(root: Path, consumers: list[dict]) -> str:
    """Commit a declaration into a synthetic tree and return its relative path."""
    declaration = {
        "schema_version": 2,
        "contract": CONTRACT,
        "producer": {
            "name": "unit.producer",
            "argv": ["python3", "-c", PRODUCER_SOURCE, "{artifact}"],
        },
        "consumers": consumers,
    }
    (root / "declaration.json").write_text(json.dumps(declaration), encoding="utf-8")
    return "declaration.json"


def _assert_accounts_for_everyone(outcome: CrossingOutcome) -> list[dict]:
    """The invariant EVERY verdict owes, asserted on every terminal below.

    ``verified_consumers + (consumer entries in the census) == declared_consumers``
    -- plus the same counts and the same misses on the human half, so a reader of
    either half learns the same population.
    """
    payload = outcome.payload
    for key in ("unverified", "declared_consumers", "verified_consumers"):
        assert key in payload, f"every verdict must carry {key!r}: {sorted(payload)}"

    census = payload["unverified"]
    assert isinstance(census, list)
    for entry in census:
        assert set(entry) == {"subject", "fact", "detail"}
        assert all(isinstance(v, str) and v.strip() for v in entry.values())

    declared = payload["declared_consumers"]
    verified = payload["verified_consumers"]
    assert f"VERIFIED {verified} of {declared} declared consumer(s)" in outcome.human
    for entry in census:
        clause = f"COULD NOT VERIFY: {entry['subject']} -- {entry['fact']}"
        assert clause in outcome.human, (
            f"the human half must carry {clause!r} so the two halves cannot "
            f"disagree about what went unverified: {outcome.human}"
        )

    # The machine half is ONE single-line JSON object beside the human half, so
    # a captured tail carrying a newline must never split the human line in two.
    assert "\n" not in outcome.human, outcome.human
    return census


def test_a_green_is_gated_on_an_empty_census_with_every_declared_consumer_verified(
    tmp_path: Path,
) -> None:
    """Exit 0 is a STRUCTURAL gate, not an accident of which branch ran first."""
    declaration = _write_declaration(
        tmp_path,
        [
            _consumer("unit.consumer.first", ACCEPTING_SOURCE),
            _consumer("unit.consumer.second", ACCEPTING_SOURCE),
        ],
    )

    outcome = cross_agreement(tmp_path, declaration)

    assert outcome.exit_code == 0, outcome.human
    assert _assert_accounts_for_everyone(outcome) == []
    assert outcome.payload["declared_consumers"] == 2
    assert outcome.payload["verified_consumers"] == 2


def test_a_party_whose_stderr_is_not_utf8_is_verified_rather_than_crashing_the_run(
    tmp_path: Path,
) -> None:
    """Acceptance IS the exit code, which no decoding choice can touch.

    Declared in the MIDDLE of three, so an implementation that lost the run --
    or short-circuited -- would visibly lose the third party too.
    """
    declaration = _write_declaration(
        tmp_path,
        [
            _consumer("unit.consumer.first", ACCEPTING_SOURCE),
            _consumer("unit.consumer.latin1", LATIN1_SOURCE),
            _consumer("unit.consumer.third", ACCEPTING_SOURCE),
        ],
    )

    outcome = cross_agreement(tmp_path, declaration)

    assert outcome.exit_code == 0, outcome.human
    assert _assert_accounts_for_everyone(outcome) == []
    assert [c["name"] for c in outcome.payload["consumers"]] == [
        "unit.consumer.first",
        "unit.consumer.latin1",
        "unit.consumer.third",
    ]
    assert outcome.payload["verified_consumers"] == 3


def test_an_unresolvable_consumer_runtime_is_indeterminate_and_named_never_refused(
    tmp_path: Path,
) -> None:
    """A contained miss is INDETERMINATE (2). Exit 1 would record a verdict
    the checker never reached -- a refusal nobody ever made."""
    declaration = _write_declaration(
        tmp_path,
        [
            _consumer("unit.consumer.first", ACCEPTING_SOURCE),
            {
                "name": "unit.consumer.unresolvable",
                "argv": ["nwave-no-such-program-for-this-unit-census", "{artifact}"],
            },
            _consumer("unit.consumer.third", ACCEPTING_SOURCE),
        ],
    )

    outcome = cross_agreement(tmp_path, declaration)

    assert outcome.exit_code == 2, outcome.human
    assert outcome.payload["verdict"] == "AgreementIndeterminate"
    census = _assert_accounts_for_everyone(outcome)
    assert [entry["subject"] for entry in census] == ["unit.consumer.unresolvable"]
    assert outcome.payload["declared_consumers"] == 3
    assert outcome.payload["verified_consumers"] == 2

    # NO SHORT-CIRCUIT: the party declared AFTER the unresolvable one still ran.
    assert [c["name"] for c in outcome.payload["consumers"]] == [
        "unit.consumer.first",
        "unit.consumer.third",
    ]


def test_an_indeterminate_reached_before_any_party_is_known_still_names_its_subject(
    tmp_path: Path,
) -> None:
    """The EARLIEST indeterminate there is must not be prose-only.

    A machine reader of a payload carrying only ``verdict`` and a sentence
    cannot learn what went unverified, which is the silence this value ends.
    """
    outcome = cross_agreement(tmp_path, "no-such-declaration.json")

    assert outcome.exit_code == 2
    census = _assert_accounts_for_everyone(outcome)
    assert [entry["subject"] for entry in census] == ["declaration"]
    # HONESTLY ZERO: no consumer was ever declared to this run, so claiming any
    # declared population would itself be a count nobody looked at.
    assert outcome.payload["declared_consumers"] == 0
    assert outcome.payload["verified_consumers"] == 0


def test_an_unrunnable_producer_leaves_every_declared_consumer_in_the_census(
    tmp_path: Path,
) -> None:
    """A failure BEFORE the traversal must not report a population never looked at."""
    declaration = {
        "schema_version": 2,
        "contract": CONTRACT,
        "producer": {
            "name": "unit.producer.unresolvable",
            "argv": ["nwave-no-such-producer-for-this-unit-census", "{artifact}"],
        },
        "consumers": [
            _consumer("unit.consumer.first", ACCEPTING_SOURCE),
            _consumer("unit.consumer.second", ACCEPTING_SOURCE),
        ],
    }
    (tmp_path / "declaration.json").write_text(
        json.dumps(declaration), encoding="utf-8"
    )

    outcome = cross_agreement(tmp_path, "declaration.json")

    assert outcome.exit_code == 2, outcome.human
    census = _assert_accounts_for_everyone(outcome)
    subjects = [entry["subject"] for entry in census]
    assert subjects == [
        "unit.producer.unresolvable",
        "unit.consumer.first",
        "unit.consumer.second",
    ], subjects
    assert outcome.payload["declared_consumers"] == 2
    assert outcome.payload["verified_consumers"] == 0


def test_cross_agreement_is_total_and_reports_an_unforeseen_fault_as_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No fault escapes as a traceback with zero bytes on the machine surface.

    The injected fault stands in for the whole class of unforeseen escapes -- a
    permission bit on the artifact, a fault in a dependency -- because the
    promise under test is TOTALITY, which cannot be measured by enumerating the
    faults somebody already thought of. Exit 2 with a named subject, never the
    refusal colour.
    """
    declaration = _write_declaration(
        tmp_path, [_consumer("unit.consumer.first", ACCEPTING_SOURCE)]
    )

    def _erupt(_: bytes) -> None:
        raise RuntimeError("an unforeseen fault nobody enumerated")

    monkeypatch.setattr(agreement_crossing, "declaration_from_bytes", _erupt)

    outcome = cross_agreement(tmp_path, declaration)

    assert outcome.exit_code == 2, outcome.human
    assert outcome.payload["verdict"] == "AgreementIndeterminate"
    census = _assert_accounts_for_everyone(outcome)
    assert [entry["subject"] for entry in census] == ["declaration"]
    assert "an unforeseen fault nobody enumerated" in census[0]["detail"]
