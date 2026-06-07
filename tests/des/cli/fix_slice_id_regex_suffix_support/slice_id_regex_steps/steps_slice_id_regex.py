"""Step bindings for the slice-id regex carpaccio slice.

Per Mandate-12: step bodies ≤2 statements, no control flow, all delegating
to the composition root. Per Mandate-13: drive via the regex object loaded
from production import, never internal field introspection.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when


@given("the Slice-Id trailer regex is loaded from verify_slice_commit_completeness")
def given_regex_loaded(extraction) -> None:
    # Composition fixture already loaded the regex via direct import; this
    # step is a Background anchor for the slice's driving-port boundary.
    assert extraction is not None


@given(parsers.parse('the commit message body is exactly "{body}"'))
def given_body(extraction, body: str) -> None:
    extraction.stage_body(body)


@when("the trailer regex extracts the slice-id")
def when_extract(extraction) -> None:
    extraction.extract()


@then(parsers.parse('the extracted slice-id is exactly "{expected}"'))
def then_extracted(extraction, expected: str) -> None:
    assert extraction.extracted == expected, (
        f"Expected slice-id {expected!r}, got {extraction.extracted!r}"
    )
