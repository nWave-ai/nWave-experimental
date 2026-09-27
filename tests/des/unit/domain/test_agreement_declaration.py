"""The closed v2 agreement-declaration grammar.

These cases sit BELOW the public crossing oracle deliberately: every refusal
here happens before any child is spawned, which is the property that makes a
hollow green -- a crossing reported as complete that in fact carried nothing --
unrepresentable rather than merely unlikely.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.domain.agreement_declaration import (
    ARTIFACT_TOKEN,
    SCHEMA_VERSION,
    InvalidDeclaration,
    declaration_from_bytes,
    declaration_from_json_text,
    substitute_artifact,
)


#: The real repository root -- this corpus also reads the FIRST SHIPPED
#: declaration from the live tree, so the grammar and the thing it governs
#: cannot drift apart silently.
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SHIPPED_DECLARATION = "schemas/agreements/nwave-test-result-v1.json"


def _valid() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "contract": "example.contract.v1",
        "producer": {"name": "producer", "argv": ["build", "--out", ARTIFACT_TOKEN]},
        "consumers": [{"name": "consumer", "argv": ["read", ARTIFACT_TOKEN]}],
    }


def _text(document: dict) -> str:
    return json.dumps(document)


class TestTheClosedGrammar:
    def test_a_complete_declaration_names_the_contract_and_every_party(self):
        declared = declaration_from_json_text(_text(_valid()))

        assert declared.schema_version == SCHEMA_VERSION
        assert declared.contract == "example.contract.v1"
        assert declared.producer.name == "producer"
        assert declared.producer.argv == ("build", "--out", ARTIFACT_TOKEN)
        assert [consumer.name for consumer in declared.consumers] == ["consumer"]
        assert declared.consumers[0].argv == ("read", ARTIFACT_TOKEN)

    def test_every_declared_consumer_is_read_in_declaration_order(self):
        """Order is data, not an accident: the crossing reaches and reports in it."""
        document = _valid()
        document["consumers"] = [
            {"name": "first", "argv": ["read", ARTIFACT_TOKEN]},
            {"name": "second", "argv": ["check", ARTIFACT_TOKEN]},
            {"name": "third", "argv": ["lint", ARTIFACT_TOKEN]},
        ]

        declared = declaration_from_json_text(_text(document))

        assert [consumer.name for consumer in declared.consumers] == [
            "first",
            "second",
            "third",
        ]

    def test_an_unknown_root_key_is_refused_rather_than_ignored(self):
        document = _valid()
        document["retries"] = 3

        with pytest.raises(InvalidDeclaration) as refusal:
            declaration_from_json_text(_text(document))

        assert "unknown key(s)" in str(refusal.value)
        assert "retries" in str(refusal.value)

    def test_a_stale_v1_declaration_is_refused_by_version_not_by_a_confusing_key_error(
        self,
    ):
        """The 1 -> 2 bump exists so this message is ACCURATE.

        A v1 file carries the singular ``consumer``. Reported as an unknown key
        it would send the operator hunting a typo; reported as a version it says
        what actually happened -- the shape changed.
        """
        document = _valid()
        document["schema_version"] = 1
        document["consumer"] = document.pop("consumers")[0]

        with pytest.raises(InvalidDeclaration) as refusal:
            declaration_from_json_text(_text(document))

        assert "schema_version" in str(refusal.value)
        assert str(SCHEMA_VERSION) in str(refusal.value)

    def test_an_unknown_party_key_is_refused(self):
        document = _valid()
        document["producer"]["cwd"] = "/tmp"

        with pytest.raises(InvalidDeclaration):
            declaration_from_json_text(_text(document))

    @pytest.mark.parametrize("missing", ["schema_version", "contract", "producer"])
    def test_a_missing_required_key_is_refused(self, missing):
        document = _valid()
        del document[missing]

        with pytest.raises(InvalidDeclaration) as refusal:
            declaration_from_json_text(_text(document))

        assert missing in str(refusal.value)

    def test_a_future_schema_version_is_refused_rather_than_guessed(self):
        document = _valid()
        document["schema_version"] = SCHEMA_VERSION + 1

        with pytest.raises(InvalidDeclaration) as refusal:
            declaration_from_json_text(_text(document))

        assert "schema_version" in str(refusal.value)

    def test_text_that_is_not_json_is_refused_as_a_value_not_a_crash(self):
        with pytest.raises(InvalidDeclaration):
            declaration_from_json_text("not json at all")

    def test_bytes_that_are_not_strict_utf8_are_refused(self):
        with pytest.raises(InvalidDeclaration) as refusal:
            declaration_from_bytes(b'{"contract": "\xff\xfe"}')

        assert "UTF-8" in str(refusal.value)


def _set_argv(document: dict, role: str, argv: list) -> None:
    """Reach the producer or the Nth consumer uniformly, so one case covers both."""
    if role == "producer":
        document["producer"]["argv"] = argv
    else:
        document["consumers"][int(role)]["argv"] = argv


class TestTheArtifactTokenMandate:
    """EVERY argv must carry ``{artifact}`` -- the hollow-green guard.

    The mandate now binds each consumer INDIVIDUALLY. One tokenless vector among
    several is the dangerous case: the other parties really cross, so the run
    looks complete while that party was handed nothing at all.
    """

    @pytest.mark.parametrize("role", ["producer", "0"])
    def test_a_party_whose_argv_omits_the_token_is_refused(self, role):
        document = _valid()
        _set_argv(document, role, ["run", "--quiet"])

        with pytest.raises(InvalidDeclaration) as refusal:
            declaration_from_json_text(_text(document))

        assert ARTIFACT_TOKEN in str(refusal.value)
        assert "carry nothing" in str(refusal.value)

    def test_a_later_consumer_whose_argv_omits_the_token_is_refused_and_named(self):
        document = _valid()
        document["consumers"] = [
            {"name": "carries", "argv": ["read", ARTIFACT_TOKEN]},
            {"name": "hollow", "argv": ["read", "--quiet"]},
        ]

        with pytest.raises(InvalidDeclaration) as refusal:
            declaration_from_json_text(_text(document))

        assert ARTIFACT_TOKEN in str(refusal.value)
        assert "consumers[1]" in str(refusal.value)

    @pytest.mark.parametrize("role", ["producer", "0"])
    def test_an_empty_argv_is_refused(self, role):
        document = _valid()
        _set_argv(document, role, [])

        with pytest.raises(InvalidDeclaration):
            declaration_from_json_text(_text(document))


class TestTheConsumersArray:
    """``consumers`` is the ONE list of who reads the contract."""

    @pytest.mark.parametrize("empty", [[], None, {}, "consumer"])
    def test_a_declaration_without_a_non_empty_consumers_array_is_refused(self, empty):
        document = _valid()
        document["consumers"] = empty

        with pytest.raises(InvalidDeclaration) as refusal:
            declaration_from_json_text(_text(document))

        assert "consumers" in str(refusal.value)

    def test_duplicate_consumer_names_are_refused_so_a_refusal_cannot_be_ambiguous(
        self,
    ):
        """The red names WHICH consumer refused; twins make that naming useless."""
        document = _valid()
        document["consumers"] = [
            {"name": "twin", "argv": ["read", ARTIFACT_TOKEN]},
            {"name": "twin", "argv": ["check", ARTIFACT_TOKEN]},
        ]

        with pytest.raises(InvalidDeclaration) as refusal:
            declaration_from_json_text(_text(document))

        assert "twin" in str(refusal.value)
        assert "unique" in str(refusal.value)

    def test_an_unknown_key_on_a_later_consumer_is_refused(self):
        document = _valid()
        document["consumers"].append(
            {"name": "second", "argv": ["read", ARTIFACT_TOKEN], "cwd": "/tmp"}
        )

        with pytest.raises(InvalidDeclaration) as refusal:
            declaration_from_json_text(_text(document))

        assert "unknown key(s)" in str(refusal.value)


class TestSubstitution:
    def test_every_occurrence_in_the_vector_is_replaced(self):
        substituted = substitute_artifact(
            ("tool", f"--in={ARTIFACT_TOKEN}", ARTIFACT_TOKEN), "/run/scoped"
        )

        assert substituted == ("tool", "--in=/run/scoped", "/run/scoped")

    def test_substitution_leaves_no_literal_token_behind(self):
        substituted = substitute_artifact(("read", ARTIFACT_TOKEN), "/run/scoped")

        assert ARTIFACT_TOKEN not in " ".join(substituted)


class TestTheFirstShippedDeclaration:
    """The live tree's own declaration, read rather than synthesised."""

    def test_it_parses_as_the_closed_grammar_and_names_the_shared_contract(self):
        declared = declaration_from_bytes(
            (REPOSITORY_ROOT / SHIPPED_DECLARATION).read_bytes()
        )

        assert declared.schema_version == SCHEMA_VERSION
        assert declared.contract == "nwave.test_result.v1"
        assert ARTIFACT_TOKEN in " ".join(declared.producer.argv)
        for consumer in declared.consumers:
            assert ARTIFACT_TOKEN in " ".join(consumer.argv), (
                f"the shipped declaration's consumer {consumer.name} must be "
                f"handed the artifact, or it crosses nothing"
            )

    def test_it_declares_more_than_one_real_consumer_of_the_shared_contract(self):
        """The whole point of the plural: this contract really has two readers.

        Stated here as well as in the crossing oracle because the grammar and
        the thing it governs must not drift apart silently -- a declaration
        quietly shrunk back to one party would still parse.
        """
        declared = declaration_from_bytes(
            (REPOSITORY_ROOT / SHIPPED_DECLARATION).read_bytes()
        )

        assert len(declared.consumers) >= 2
        names = [consumer.name for consumer in declared.consumers]
        assert len(set(names)) == len(names)
