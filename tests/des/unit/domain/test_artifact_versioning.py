"""Unit tests for the artifact-versioning kernel (F-ARTIFACT-VERSIONING-UPCASTING).

Covers: a v0->v2 chain over a fake type with two upcasters, the LOUD refusal
when a doc's declared version is newer than the runtime knows, and
idempotence when upcasting a doc already at the current version.
"""

import pytest

from des.domain.artifact_versioning import (
    SCHEMA_VERSION_KEY,
    ArtifactFromFutureRuntime,
    ArtifactVersioningKernel,
    read_version,
)


FAKE_TYPE = "fake-artifact"


def _v0_to_v1(doc: dict) -> dict:
    """v0 (bare ``name``) -> v1: adds ``greeting`` derived from ``name``."""
    result = dict(doc)
    result["greeting"] = f"hello {result.get('name', 'unknown')}"
    return result


def _v1_to_v2(doc: dict) -> dict:
    """v1 -> v2: uppercases ``greeting``."""
    result = dict(doc)
    result["greeting"] = result["greeting"].upper()
    return result


def _two_step_kernel() -> ArtifactVersioningKernel:
    return ArtifactVersioningKernel(upcasters={FAKE_TYPE: (_v0_to_v1, _v1_to_v2)})


class TestReadVersion:
    def test_absent_key_is_version_zero(self):
        assert read_version({"name": "x"}) == 0

    def test_reads_declared_integer_version(self):
        assert read_version({SCHEMA_VERSION_KEY: 2}) == 2

    def test_non_int_declared_version_degrades_to_zero(self):
        assert read_version({SCHEMA_VERSION_KEY: "two"}) == 0

    def test_bool_declared_version_degrades_to_zero(self):
        # bool is an int subclass in Python but never a meaningful version.
        assert read_version({SCHEMA_VERSION_KEY: True}) == 0


class TestCurrentVersion:
    def test_current_version_is_chain_length(self):
        kernel = _two_step_kernel()

        assert kernel.current_version(FAKE_TYPE) == 2

    def test_unregistered_type_is_version_zero(self):
        kernel = _two_step_kernel()

        assert kernel.current_version("never-registered") == 0


class TestUpcastToCurrentChain:
    def test_v0_doc_runs_the_full_two_step_chain(self):
        kernel = _two_step_kernel()
        doc = {"name": "ada"}

        result = kernel.upcast_to_current(doc, FAKE_TYPE)

        assert result == {
            "name": "ada",
            "greeting": "HELLO ADA",
            SCHEMA_VERSION_KEY: 2,
        }

    def test_v1_doc_runs_only_the_remaining_step(self):
        kernel = _two_step_kernel()
        doc = {"name": "ada", "greeting": "hello ada", SCHEMA_VERSION_KEY: 1}

        result = kernel.upcast_to_current(doc, FAKE_TYPE)

        assert result == {
            "name": "ada",
            "greeting": "HELLO ADA",
            SCHEMA_VERSION_KEY: 2,
        }

    def test_never_mutates_the_input_doc(self):
        kernel = _two_step_kernel()
        doc = {"name": "ada"}
        original = dict(doc)

        kernel.upcast_to_current(doc, FAKE_TYPE)

        assert doc == original

    def test_unregistered_type_returns_doc_with_schema_version_zero_stamped(self):
        kernel = _two_step_kernel()
        doc = {"name": "ada"}

        result = kernel.upcast_to_current(doc, "never-registered")

        assert result == {"name": "ada", SCHEMA_VERSION_KEY: 0}


class TestUpcastToCurrentIdempotence:
    def test_doc_already_at_current_version_is_unchanged(self):
        kernel = _two_step_kernel()
        doc = {"name": "ada", "greeting": "HELLO ADA", SCHEMA_VERSION_KEY: 2}

        result = kernel.upcast_to_current(doc, FAKE_TYPE)

        assert result == doc

    def test_upcasting_twice_is_the_same_as_once(self):
        kernel = _two_step_kernel()
        doc = {"name": "ada"}

        once = kernel.upcast_to_current(doc, FAKE_TYPE)
        twice = kernel.upcast_to_current(once, FAKE_TYPE)

        assert once == twice


class TestUpcastToCurrentRefusesFutureVersions:
    def test_doc_newer_than_runtime_raises_loud(self):
        kernel = _two_step_kernel()
        doc = {SCHEMA_VERSION_KEY: 5, "name": "ada"}

        with pytest.raises(ArtifactFromFutureRuntime) as excinfo:
            kernel.upcast_to_current(doc, FAKE_TYPE)

        error = excinfo.value
        assert error.artifact_type == FAKE_TYPE
        assert error.doc_version == 5
        assert error.runtime_version == 2

    def test_future_version_message_carries_what_why_how(self):
        kernel = _two_step_kernel()
        doc = {SCHEMA_VERSION_KEY: 5}

        with pytest.raises(ArtifactFromFutureRuntime) as excinfo:
            kernel.upcast_to_current(doc, FAKE_TYPE)

        message = str(excinfo.value)
        assert "WHAT:" in message
        assert "WHY:" in message
        assert "HOW:" in message
