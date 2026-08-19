"""Unit tests for `oracle_structure_findings` (K4 Run 10 admission).

Real defect repro: `test_it_saves_maintenance_windows` spliced into the
MIDDLE of `test_it_works`'s own body -- syntactically valid, structurally
broken (a test method nested inside another, never collected by any
runner; the outer method silently lost its own tail assertions).
"""

from __future__ import annotations

from des.domain.oracle_structure_resolver import oracle_structure_findings


#: Mirrors the exact Run 10 defect shape: `test_it_saves_maintenance_windows`
#: is a nested function INSIDE `test_it_works`'s body, sitting before that
#: method's own original tail assertions (now silently absorbed into the
#: nested function instead).
_SPLICED_SOURCE = """\
from hc.test import BaseTestCase


class CreateCheckTestCase(BaseTestCase):
    def test_it_works(self) -> None:
        r = self.post({"name": "Foo"})
        self.assertEqual(r.status_code, 201)
        doc = r.json()
        self.assertEqual(doc["maintenance_windows"], [])

        def test_it_saves_maintenance_windows(self) -> None:
            r = self.post({"name": "Foo", "maintenance_windows": []})
            self.assertEqual(r.status_code, 201)

        self.assertEqual(doc["start_kw"], "START")
        self.assertEqual(doc["tags"], "bar,baz")
"""

_WELL_FORMED_SOURCE = """\
from hc.test import BaseTestCase


class CreateCheckTestCase(BaseTestCase):
    def test_it_works(self) -> None:
        r = self.post({"name": "Foo"})
        self.assertEqual(r.status_code, 201)
        doc = r.json()
        self.assertEqual(doc["maintenance_windows"], [])
        self.assertEqual(doc["start_kw"], "START")
        self.assertEqual(doc["tags"], "bar,baz")

    def test_it_saves_maintenance_windows(self) -> None:
        r = self.post({"name": "Foo", "maintenance_windows": []})
        self.assertEqual(r.status_code, 201)


def test_a_pytest_function() -> None:
    assert 1 + 1 == 2
"""

_NO_ASSERTION_SOURCE = """\
class SomeTestCase:
    def test_does_nothing(self) -> None:
        r = 1 + 1
"""

_SYNTAX_ERROR_SOURCE = "def test_broken(:\n    pass\n"


def test_nested_test_method_is_flagged_with_its_own_line() -> None:
    findings = oracle_structure_findings(_SPLICED_SOURCE, "test_create_check.py")

    assert ("nested-test", 11) in findings


def test_well_formed_file_with_class_and_module_level_tests_is_clean() -> None:
    assert oracle_structure_findings(_WELL_FORMED_SOURCE, "test_x.py") == []


def test_test_method_with_no_assertion_is_flagged() -> None:
    findings = oracle_structure_findings(_NO_ASSERTION_SOURCE, "test_x.py")

    assert findings == [("no-assertion", 2)]


def test_file_that_does_not_compile_is_flagged_at_its_syntax_error_line() -> None:
    findings = oracle_structure_findings(_SYNTAX_ERROR_SOURCE, "test_x.py")

    assert findings and findings[0][0] == "does-not-compile"


def test_pytest_raises_counts_as_an_assertion() -> None:
    source = (
        "import pytest\n\n\n"
        "def test_it_raises() -> None:\n"
        "    with pytest.raises(ValueError):\n"
        "        raise ValueError()\n"
    )

    assert oracle_structure_findings(source, "test_x.py") == []
