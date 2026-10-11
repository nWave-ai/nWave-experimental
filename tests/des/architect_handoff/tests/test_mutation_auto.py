"""The generator of mutants is itself code: each site it finds must be applicable, change exactly the behavior it names,
and leave docstrings, decorators, the RULES table and the `__main__` guard alone."""

from __future__ import annotations

import ast
import unittest

from tests.des.architect_handoff.tests import mutation_auto as M


SRC = '''\
import dataclasses as dc


@dc.dataclass(frozen=True)
class Box:
    """A doc that says x == y and True."""
    n: int = 0


RULES = {"R": ("a == b and c",)}


def f(a, b):
    """Doc with a == b."""
    if a == b and a:
        return a + 1
    return not b


def g(items):
    return sorted(items)


if __name__ == "__main__":
    f(1, 1)
'''


def namespace(src: str) -> dict:
    ns: dict = {}
    exec(compile(src, "<m>", "exec"), ns)
    return ns


class Generator(unittest.TestCase):
    def sites(self):
        return [s for s, _ in M.sites_of(SRC, "m.py")]

    def test_each_site_has_a_unique_key_and_is_applicable_and_changes_the_text(self):
        keys = [s.key for s in self.sites()]
        self.assertEqual(len(keys), len(set(keys)))
        for k in keys:
            mutated = M.mutate(SRC, "m.py", k)
            self.assertNotEqual(ast.unparse(ast.parse(SRC)), mutated, k)
            ast.parse(mutated)

    def test_the_operators_found_are_exactly_those_of_the_code_and_not_of_docstrings_decorators_RULES_or_the_main_guard(
        self,
    ):
        ops = sorted((s.line, s.op) for s in self.sites())
        self.assertEqual(
            sorted(
                [
                    (7, "int"),
                    (15, "negate-test"),
                    (15, "and-or"),
                    (15, "compare"),
                    (16, "arith"),
                    (16, "int"),
                    (17, "drop-not"),
                    (21, "drop-sorted"),
                ]
            ),
            ops,
        )
        by_line = {line for line, _ in ops}
        self.assertNotIn(6, by_line)  # the class docstring
        self.assertNotIn(4, by_line)  # the decorator `frozen=True`
        self.assertNotIn(10, by_line)  # the RULES table
        self.assertNotIn(14, by_line)  # the function docstring
        self.assertNotIn(24, by_line)  # the `__main__` guard
        self.assertNotIn(25, by_line)
        self.assertIn((15, "negate-test"), ops)
        self.assertIn((16, "arith"), ops)
        self.assertIn((16, "int"), ops)
        self.assertIn((17, "drop-not"), ops)
        self.assertIn((21, "drop-sorted"), ops)

    def behaviors(self, key: str):
        before, after = namespace(SRC), namespace(M.mutate(SRC, "m.py", key))
        return [
            (before["f"](a, b), after["f"](a, b))
            for a, b in ((1, 1), (1, 2), (0, 0), (2, 1))
        ]

    def test_each_operator_changes_the_behavior_it_names(self):
        by_op: dict[str, list[str]] = {}
        for s in self.sites():
            by_op.setdefault(s.op, []).append(s.key)
        for op in ("negate-test", "and-or", "compare", "drop-not", "arith", "int"):
            for key in by_op[op]:
                if ":15:" in key or ":16:" in key or ":17:" in key:
                    pairs = self.behaviors(key)
                    self.assertTrue(any(x != y for x, y in pairs), (op, key, pairs))
        sorted_key = by_op["drop-sorted"][0]
        before, after = namespace(SRC), namespace(M.mutate(SRC, "m.py", sorted_key))
        self.assertEqual([1, 2, 3], before["g"]([3, 1, 2]))
        self.assertEqual([3, 1, 2], after["g"]([3, 1, 2]))

    def test_two_comparisons_on_one_line_are_two_sites_and_each_changes_only_its_own_operator(
        self,
    ):
        src = "def h(a, b):\n    return a < 1 and b > 2\n"
        sites = [s for s, _ in M.sites_of(src, "h.py") if s.op == "compare"]
        self.assertEqual(2, len(sites))
        outs = [M.mutate(src, "h.py", s.key) for s in sites]
        self.assertEqual(2, len(set(outs)))
        self.assertTrue(all(o.count("<=") + o.count(">=") == 1 for o in outs))

    def test_a_chained_comparison_gets_one_site_per_operator(self):
        src = "def h(a):\n    return 1 < a < 3\n"
        sites = [s for s, _ in M.sites_of(src, "h.py") if s.op == "compare"]
        self.assertEqual(2, len(sites))
        outs = {M.mutate(src, "h.py", s.key) for s in sites}
        self.assertEqual(
            {"def h(a):\n    return 1 <= a < 3", "def h(a):\n    return 1 < a <= 3"},
            outs,
        )


if __name__ == "__main__":
    unittest.main()
