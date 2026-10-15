"""What the trace reader prints and what the renderer says, beyond the cases of tests/test_g10.py (class Renderer).

A first tool-chosen mutation run showed that no test read these facts: the exact depth at which a trace is too deep, how a set,
a tuple and a variant are printed, which state a `@pre` placeholder reads, the reasons a scenario cannot be rendered, the words of
the human view and the hash prefixes of its header.
Run:  cd analysis/g10 && python3 -W ignore -m unittest tests.test_surv_render
"""

from __future__ import annotations

import copy
import dataclasses as dc
import hashlib
import html
import os
import re
import unittest
from pathlib import Path

from tests.des.architect_handoff.tests.test_g10 import (
    atom_,
    base_doc,
    decode,
    fixture_catalog,
    fresh_copy,
    itf,
    model_,
    run_,
    scn,
)

from des.application.architect_handoff import g10_itf as I
from des.application.architect_handoff import g10_render as R
from des.application.architect_handoff import g10_scope as S
from des.application.architect_handoff import g10_types as T


def nested(levels: int):
    """`levels` lists inside each other with an integer in the innermost one."""
    v = {"#bigint": "1"}
    for _ in range(levels):
        v = [v]
    return v


def trace_of(*states) -> I.Trace:
    return I.parse(itf("ok", list(states)))


def model_of(doc: dict, mid: str = "walk") -> T.Model:
    return next(
        m for m in decode(doc)[("model", "shared")].status.payload.models if m.id == mid
    )


class Depth(unittest.TestCase):
    def test_a_value_nested_a_hundred_levels_is_read_and_one_more_level_is_refused(
        self,
    ):
        self.assertEqual(100, I.MAX_DEPTH)
        I.parse({"#meta": {}, "states": [{"x": nested(100)}]})
        with self.assertRaises(I.ItfError) as cm:
            I.parse({"#meta": {}, "states": [{"x": nested(101)}]})
        self.assertIn("more than 100 levels", str(cm.exception))
        I.parse(
            {"#meta": {}, "states": [{"x": {"#set": [nested(98)]}}]}
        )  # a set is one more level, a bigint is not
        with self.assertRaises(I.ItfError):
            I.parse({"#meta": {}, "states": [{"x": {"#set": [nested(100)]}}]})


class PrintedValues(unittest.TestCase):
    def test_a_set_of_numbers_is_printed_in_numeric_order_and_anything_else_in_the_order_of_its_printed_text(
        self,
    ):
        self.assertEqual("{2, 9, 10}", I.fmt(I.QSet([10, 9, 2])))
        self.assertEqual(
            "{(10, 1), (9, 2)}", I.fmt(I.QSet([I.QTup([9, 2]), I.QTup([10, 1])]))
        )
        self.assertEqual("{false, true}", I.fmt(I.QSet([True, False])))
        self.assertEqual("{a, b, c}", I.fmt(I.QSet(["c", "a", "b"])))
        self.assertEqual("{2 -> x, 10 -> y}", I.fmt(I.QMap([(10, "y"), (2, "x")])))
        self.assertEqual(
            "{(10, 1) -> a, (9, 2) -> b}",
            I.fmt(I.QMap([(I.QTup([9, 2]), "b"), (I.QTup([10, 1]), "a")])),
        )

    def test_a_variant_without_a_value_prints_its_tag_and_one_with_a_value_prints_both(
        self,
    ):
        self.assertEqual("None", I.fmt(I.QVariant("None", I.QTup([]))))
        self.assertEqual("Some(0)", I.fmt(I.QVariant("Some", 0)))
        self.assertEqual("Some(5)", I.fmt(I.QVariant("Some", 5)))
        self.assertEqual("Pair((1, 2))", I.fmt(I.QVariant("Pair", I.QTup([1, 2]))))
        self.assertEqual("Some(false)", I.fmt(I.QVariant("Some", False)))

    def test_lists_tuples_and_records_print_their_items_in_their_own_order_or_in_key_order(
        self,
    ):
        self.assertEqual("[3, 1, 2]", I.fmt([3, 1, 2]))
        self.assertEqual("(3, 1)", I.fmt(I.QTup([3, 1])))
        self.assertEqual("()", I.fmt(I.QTup([])))
        self.assertEqual("{a: 1, b: true}", I.fmt({"b": True, "a": 1}))
        self.assertEqual("[]", I.fmt([]))
        self.assertEqual("true", I.fmt(True))
        self.assertEqual("false", I.fmt(False))
        self.assertEqual("null", I.fmt(None))


class TracesAndTemplates(unittest.TestCase):
    """The walk model: `step` reads {offset@pre}, {lim}, {offset} and {count}; `move` reads {offset@pre} and {offset}."""

    def setUp(self):
        self.model = None

    def test_a_placeholder_reads_the_state_it_names_and_a_pre_placeholder_reads_the_state_before(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            model, catalog = model_of(doc), fixture_catalog(doc)
        full = {"n": 1, "lim": 1, "offset": 0, "count": 0}
        self.assertEqual(
            [],
            R.trace_problems(
                model,
                trace_of(("init", full), ("step", {"offset": 1, "lim": 1, "count": 0})),
                catalog,
            ),
        )
        # `{lim}` is read in the state itself, not in the one before it
        only_before = R.trace_problems(
            model,
            trace_of(("init", full), ("step", {"offset": 1, "count": 0})),
            catalog,
        )
        self.assertEqual(["state 1: variable 'lim' is not in the trace"], only_before)
        # `{offset@pre}` is read in the state before, not in the state itself
        none_before = R.trace_problems(
            model,
            trace_of(
                ("init", {"n": 1, "lim": 1, "count": 0}),
                ("step", {"offset": 1, "lim": 1, "count": 0}),
            ),
            catalog,
        )
        self.assertEqual(
            [
                "state 0: variable 'offset' is not in the trace",
                "state 1: variable 'offset' is not in the trace",
            ],
            none_before,
        )

    def test_a_pre_placeholder_reads_exactly_one_state_back(self):
        with fresh_copy() as d:
            doc = base_doc(d)
            atom_(model_(doc, "walk"), "move")["template"] = (
                "The caller moves from count {count@pre} to offset {offset}"
            )
            model = model_of(doc)
            catalog = fixture_catalog(doc)
        trace = trace_of(
            ("init", {"n": 1, "lim": 1, "offset": 0, "count": 0}),
            ("probeEnd", {"n": 1, "offset": 0}),
            ("move", {"offset": 1}),
        )
        self.assertEqual(
            ["state 2: variable 'count' is not in the trace"],
            R.trace_problems(model, trace, catalog),
        )

    def test_a_first_state_cannot_ask_for_a_before_and_a_trace_without_states_or_actions_is_a_problem(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            model, catalog = model_of(doc), fixture_catalog(doc)
        asks = R.trace_problems(model, trace_of(("move", {"offset": 0})), catalog)
        self.assertEqual(1, len(asks))
        self.assertIn("state 0: template of 'move' asks for offset@pre", asks[0])
        self.assertEqual(
            ["the trace has no state"],
            R.trace_problems(
                model, I.parse({"#meta": {"status": "ok"}, "states": []}), catalog
            ),
        )
        self.assertEqual(
            ["state 0: the trace names no action (it was written without --mbt)"],
            R.trace_problems(model, trace_of((None, {"offset": 0})), catalog),
        )
        self.assertEqual(
            ["state 0: action 'nope' is not an action atom of model walk"],
            R.trace_problems(model, trace_of(("nope", {"offset": 0})), catalog),
        )

    def test_a_template_that_names_something_that_is_not_a_state_is_reported_with_the_action_the_name_and_the_model(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            atom_(model_(doc, "walk"), "move")["template"] = (
                "The caller is at {nope} and then at {offset}"
            )
            problems = R.template_problems(model_of(doc), fixture_catalog(doc))
        self.assertEqual(
            [
                "action 'move': template names 'nope', which is not a state atom of model walk"
            ],
            problems,
        )

    def test_a_violation_of_one_check_ends_the_story_with_the_property_in_words_and_the_last_state(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            model, catalog = model_of(doc), fixture_catalog(doc)
        states = [
            ("init", {"n": 1, "lim": 1, "offset": 0, "count": 0}),
            ("step", {"offset": 1, "lim": 1, "count": 0}),
            ("move", {"offset": 2}),
        ]
        bad = I.parse(itf("violation", states))
        events = R.render_trace(model, bad, ["bounded"], catalog)
        self.assertEqual(4, len(events))
        self.assertEqual(
            (2, "The check fails in this state: a page has at most limit items"),
            events[-1],
        )
        self.assertEqual(
            "The check fails in this state: nope",
            R.render_trace(model, bad, ["nope"], catalog)[-1][1],
        )
        self.assertEqual(
            3, len(R.render_trace(model, bad, ["bounded", "completeAtEnd"], catalog))
        )
        self.assertEqual(3, len(R.render_trace(model, bad, [], catalog)))
        self.assertEqual(
            3,
            len(
                R.render_trace(model, I.parse(itf("ok", states)), ["bounded"], catalog)
            ),
        )
        with self.assertRaises(ValueError):
            R.render_trace(
                model,
                I.parse({"#meta": {"status": "violation"}, "states": []}),
                ["bounded"],
                catalog,
            )


class Scenarios(unittest.TestCase):
    def view(self, doc: dict, d: str | None, sid: str):
        h = decode(doc)
        v = S.visible(h, "shared")
        sc = next(
            s
            for s in h[("scenarios", "shared")].status.payload.scenarios
            if s.id == sid
        )
        return v, sc, R.render_scenario(v, sc, d, fixture_catalog(doc))

    @staticmethod
    def append_to(path: str) -> None:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(" ")

    def test_a_scenario_that_cannot_be_rendered_says_why_and_a_good_one_is_rendered_from_its_trace(
        self,
    ):
        def reason(mutate, sid="SC2", base=True):
            with fresh_copy() as d:
                doc = base_doc(d)
                mutate(doc, d)
                out = self.view(doc, d if base else None, sid)[2]
            return out

        cases = {
            "no_run": (
                lambda doc, d: scn(doc, "SC2").__setitem__("source_run", "NOPE"),
                "the source run or its model is missing",
            ),
            "no_model": (
                lambda doc, d: run_(doc, "EX1").pop("model_id"),
                "the source run or its model is missing",
            ),
            "unknown_model": (
                lambda doc, d: run_(doc, "EX1").__setitem__("model_id", "nowhere"),
                "the source run or its model is missing",
            ),
            "no_trace": (
                lambda doc, d: run_(doc, "EX1").__setitem__(
                    "artifacts",
                    [a for a in run_(doc, "EX1")["artifacts"] if a["role"] != "trace"],
                ),
                "run EX1 keeps no trace artifact",
            ),
            "missing_file": (
                lambda doc, d: (Path(d) / "traces/EX1.itf.json").unlink(),
                "is not there",
            ),
            "changed_file": (
                lambda doc, d: Scenarios.append_to(
                    os.path.join(d, "traces", "EX1.itf.json")
                ),
                "changed after the run",
            ),
        }
        for name, (mutate, said) in cases.items():
            out = reason(mutate)
            self.assertIsInstance(out, R.Skipped, name)
            self.assertIn(said, out.reason, name)
        blind = reason(lambda doc, d: None, base=False)
        self.assertIsInstance(blind, R.Skipped)
        self.assertIn("no directory was given", blind.reason)
        broken = reason(self.break_trace)
        self.assertIsInstance(broken, R.Bad)
        self.assertIn("cannot be read", broken.problems[0])
        good = reason(lambda doc, d: None)
        self.assertIsInstance(good, R.Rendered)
        self.assertEqual("ok", good.trace_status)
        self.assertTrue(good.events)

    @staticmethod
    def break_trace(doc: dict, d: str) -> None:
        garbage = b"{not json"
        with open(os.path.join(d, "traces", "EX1.itf.json"), "wb") as fh:
            fh.write(garbage)
        for a in run_(doc, "EX1")["artifacts"]:
            if a["role"] == "trace":
                a["sha256"] = hashlib.sha256(garbage).hexdigest()

    def test_the_text_of_a_scenario_has_a_header_with_twelve_characters_of_each_hash_and_numbered_events(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            _, _, ex = self.view(doc, d, "SC2")
            text = R.scenario_text(ex)
        lines = text.splitlines()
        self.assertRegex(
            lines[0],
            r"^.+ \[example; run EX1; model [0-9a-f]{12}; trace [0-9a-f]{12}; review pending\]$",
        )
        self.assertEqual([f"{n}. {x}" for n, (_, x) in enumerate(ex.events)], lines[1:])
        self.assertFalse(any(x.startswith("What this bug does") for x in lines))
        self.assertEqual(
            ex.model.sha256[:12], re.search(r"model ([0-9a-f]+);", lines[0]).group(1)
        )
        self.assertEqual(
            ex.trace_sha256[:12], re.search(r"trace ([0-9a-f]+);", lines[0]).group(1)
        )

    def test_a_mutant_scenario_says_what_the_bug_does_and_only_when_the_mutant_is_described(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            _, _, mutant = self.view(doc, d, "SC1")
            description = fixture_catalog(doc).resolve(
                next(m for m in model_of(doc).mutants if m.id == "M1").description
            )
            text = R.scenario_text(mutant)
        self.assertEqual(f"What this bug does: {description}", text.splitlines()[1])
        self.assertEqual(f"What this bug does: {description}", R._mutant_line(mutant))
        self.assertEqual(description, R.mutant_description(mutant.model, "M1"))
        self.assertIsNone(R.mutant_description(mutant.model, "M99"))
        unknown = copy.copy(mutant)
        object.__setattr__(unknown, "run", dc.replace(mutant.run, variant="mutant:M99"))
        self.assertIsNone(R._mutant_line(unknown))
        self.assertNotIn("What this bug does", R.scenario_text(unknown))

    def test_the_human_page_has_the_events_the_bug_the_escaped_notes_and_nothing_else(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            items = [self.view(doc, d, sid)[2] for sid in ("SC1", "SC2")]
        page = R.scenarios_html(items, ["scenario X <b>: a & b"])
        self.assertIn("<h1>Scenarios for review</h1>", page)
        self.assertEqual(1, page.count("<em>What this bug does: "))
        self.assertEqual(2, page.count("<ol><li>"))
        for r in items:
            self.assertIn(f"<h2>{html.escape(r.scenario.title)}</h2>", page)
            self.assertIn(
                "<ol>"
                + "".join(f"<li>{html.escape(x)}</li>" for _, x in r.events)
                + "</ol>",
                page,
            )
        self.assertIn(
            "<h2>Not rendered</h2><ul><li>scenario X &lt;b&gt;: a &amp; b</li></ul>",
            page,
        )
        plain = R.scenarios_html(items, [])
        self.assertNotIn("Not rendered", plain)
        self.assertTrue(plain.startswith("<!doctype html>"))
        self.assertTrue(plain.endswith("</body></html>\n"))
        self.assertNotIn("<script", plain)

    def test_the_scenarios_of_a_discuss_record_take_their_model_tool_and_trace_from_the_first_run(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            first, second = self.view(doc, d, "SC1")[2], self.view(doc, d, "SC2")[2]
        record = R.quint_scenarios([first, second])
        self.assertEqual(first.run.tool, record["tool"]["name"])
        self.assertEqual(" ".join(first.run.argv), record["tool"]["command"])
        self.assertEqual(T.trace_of(first.run).path, record["trace"]["path"])
        self.assertEqual(
            {"path": first.model.path, "identity": first.model.sha256}, record["model"]
        )
        self.assertEqual(
            [first.scenario.title, second.scenario.title],
            [s["title"] for s in record["scenarios"]],
        )
        self.assertNotEqual(T.trace_of(first.run).path, T.trace_of(second.run).path)


class MapKeyIdentity(unittest.TestCase):
    def test_map_display_collisions_preserve_each_value_and_entry_order_independence(
        self,
    ):
        pairs = [
            [{"#tup": ["a, b", "c"]}, {"#bigint": "1"}],
            [{"#tup": ["a", "b, c"]}, {"#bigint": "2"}],
        ]
        rendered = []
        for entries in (pairs, list(reversed(pairs))):
            trace = I.parse({"#meta": {}, "states": [{"x": {"#map": entries}}]})
            rendered.append(I.fmt(trace.states[0].vars["x"]))
        self.assertEqual("{(a, b, c) -> 2, (a, b, c) -> 1}", rendered[0])
        self.assertEqual(rendered[0], rendered[1])


if __name__ == "__main__":
    unittest.main()
