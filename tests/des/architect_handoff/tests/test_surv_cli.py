"""What the command line says and returns, and the two small modules under it (scope visibility, the numbered report).

A first tool-chosen mutation run showed that no test read these facts: the words a command prints when it succeeds, the exit status
of the commands that only print, the options that are required, the bounds of `--measure` and `--timeout`, the order of the
directories named in a refusal and the numbering of a report.
Run:  cd analysis/g10 && python3 -W ignore -m unittest tests.test_surv_cli
"""

from __future__ import annotations

import contextlib
import dataclasses as dc
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from tests.des.architect_handoff.tests.test_g10 import (
    FIX,
    MINIMAL,
    base_doc,
    decode,
    fresh_copy,
    section,
)

from des.application.architect_handoff import g10 as G
from des.application.architect_handoff import g10_codec as C
from des.application.architect_handoff import g10_defect as D
from des.application.architect_handoff import g10_project as P
from des.application.architect_handoff import g10_rules as RU
from des.application.architect_handoff import g10_scope as S
from des.application.architect_handoff import g10_types as T


PY = sys.executable
VERSION = f"{PY} -c print(1)"


def cli(*args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = G.main(list(args))
        except SystemExit as exc:  # argparse refuses a wrong command line
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class Printing(unittest.TestCase):
    def test_describe_and_rules_print_their_text_and_succeed(self):
        code, out, _ = cli("describe")
        self.assertEqual((0, P.describe_types() + "\n"), (code, out))
        code, out, _ = cli("rules")
        self.assertEqual((0, RU.rules_markdown() + "\n"), (code, out))

    def test_summary_prints_one_json_object_with_sorted_keys_and_a_file_that_does_not_decode_exits_one(
        self,
    ):
        code, out, _ = cli("summary", MINIMAL)
        self.assertEqual(0, code)
        keys = list(json.loads(out))
        self.assertEqual(sorted(keys), keys)
        self.assertEqual(P.summary(G.load_files([MINIMAL])[0]), json.loads(out))
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("{}")
            code, out, _ = cli("summary", bad)
        self.assertEqual(1, code)
        self.assertIn("G4", out)
        self.assertIn("Not run:", out)

    def test_render_to_a_page_says_where_it_wrote_and_without_a_page_prints_markdown(
        self,
    ):
        with tempfile.TemporaryDirectory() as d:
            page = os.path.join(d, "page.html")
            code, out, _ = cli("render", MINIMAL, "--html", page)
            self.assertEqual((0, f"wrote {page}\n"), (code, out))
            with open(page, encoding="utf-8") as fh:
                self.assertTrue(fh.read().startswith("<!doctype html>"))
            code, out, _ = cli(
                "render", MINIMAL, "--html", os.path.join(d, "no-such-dir", "page.html")
            )
            self.assertEqual(1, code)
            self.assertIn("cannot write the page", out)
        code, out, _ = cli("render", MINIMAL)
        self.assertEqual(0, code)
        self.assertIn("## laws (shared)", out)

    def test_every_command_that_reads_files_exits_one_and_says_what_it_could_not_read(
        self,
    ):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "absent.json")
            for args in (
                ("check", missing),
                ("render", missing),
                ("summary", missing),
                ("prompt", missing, "--role", "human"),
            ):
                code, out, _ = cli(*args)
                self.assertEqual(1, code, args)
                self.assertIn("G12", out, args)
                self.assertIn("cannot read the file", out, args)


class Directories(unittest.TestCase):
    def test_files_in_different_directories_are_refused_naming_every_directory_in_sorted_order(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            files, dirs = [], []
            for name in ("f", "c", "e", "a", "d", "b"):
                d = os.path.join(tmp, name)
                Path(d).mkdir()
                shutil.copy(MINIMAL, os.path.join(d, "g10.json"))
                files.append(os.path.join(d, "g10.json"))
                dirs.append(d)
            code, out, err = cli("check", *files)
            self.assertEqual((2, ""), (code, out))
            listed = err.split("(", 1)[1].split(")", 1)[0].split(", ")
            self.assertEqual(sorted(dirs), listed)
            self.assertIn("give --dir", err)
            _, _, err = cli("check", *files, "--dir", FIX)
            self.assertNotIn("different directories", err)


class RequiredOptions(unittest.TestCase):
    def test_each_required_option_is_refused_by_name_when_it_is_missing(self):
        full = {
            "run": [
                "--dir",
                "D",
                "--id",
                "X",
                "--tool",
                "script",
                "--target",
                "prototype",
                "--variant",
                "fixed",
            ],
            "record": [
                "--dir",
                "D",
                "--id",
                "X",
                "--tool",
                "script",
                "--tool-version",
                "v",
                "--target",
                "prototype",
                "--variant",
                "fixed",
                "--exit",
                "0",
                "--result",
                "ok",
            ],
        }
        for cmd, options in full.items():
            names = [o for o in options if o.startswith("--")]
            for name in names:
                shown = [
                    x
                    for pair in zip(options[::2], options[1::2], strict=True)
                    if pair[0] != name
                    for x in pair
                ]
                code, _out, err = cli(cmd, *shown, "--", "x")
                self.assertEqual(2, code, (cmd, name, err))
                self.assertIn("required", err, (cmd, name))
                self.assertIn(name, err, (cmd, name))
        code, _, err = cli("prompt", MINIMAL)
        self.assertEqual(2, code)
        self.assertIn("--role", err)
        code, _, err = cli("check")
        self.assertEqual(2, code)

    def test_a_tool_a_target_a_role_and_a_result_are_one_of_their_closed_words(self):
        base = ["--dir", "D", "--id", "X", "--variant", "fixed"]
        for cmd, extra, flag in (
            ("run", ["--tool", "bogus", "--target", "prototype"], "--tool"),
            ("run", ["--tool", "script", "--target", "bogus"], "--target"),
            (
                "record",
                [
                    "--tool",
                    "script",
                    "--tool-version",
                    "v",
                    "--target",
                    "prototype",
                    "--exit",
                    "0",
                    "--result",
                    "bogus",
                ],
                "--result",
            ),
        ):
            code, _, err = cli(cmd, *base, *extra, "--", "x")
            self.assertEqual(2, code, (cmd, flag))
            self.assertIn("invalid choice", err)
        code, _, err = cli("prompt", MINIMAL, "--role", "nobody")
        self.assertEqual(2, code)
        self.assertIn("invalid choice", err)


class Declarations(unittest.TestCase):
    def record(self, *extra: str, directory: str):
        return cli(
            "record",
            "--dir",
            directory,
            "--id",
            "M1",
            "--tool",
            "script",
            "--tool-version",
            "v",
            "--target",
            "prototype",
            "--variant",
            "fixed",
            "--exit",
            "0",
            "--result",
            "ok",
            *extra,
            "--",
            "x",
        )

    def test_a_measure_is_a_kind_and_one_to_fifteen_ascii_digits_with_a_value_of_one_or_more(
        self,
    ):
        good = {
            "states=1": 1,
            "cases=7": 7,
            "samples=007": 7,
            "states=999999999999999": 999999999999999,
            "states=10": 10,
            "states=9": 9,
        }
        bad = (
            "states=0",
            "states=00",
            "states=",
            "states",
            "=5",
            "states=1000000000000000",
            "states=-1",
            "states=1.5",
            "states=\u0663",
            "stats=5",
            "cases=5 ",
            "STATES=5",
            "states=+5",
        )
        for text, value in good.items():
            with tempfile.TemporaryDirectory() as d:
                code, _out, err = self.record("--measure", text, directory=d)
                self.assertEqual(0, code, (text, err))
                with open(os.path.join(d, "g10.receipts.json"), encoding="utf-8") as fh:
                    run = json.load(fh)["sections"][0]["status"]["payload"]["runs"][0]
                self.assertEqual(value, run["measure"]["value"], text)
                self.assertEqual(text.split("=")[0], run["measure"]["kind"], text)
        for text in bad:
            with tempfile.TemporaryDirectory() as d:
                code, _out, err = self.record("--measure", text, directory=d)
                self.assertEqual(2, code, text)
                self.assertIn("is not a measurement declaration", err, text)
                self.assertIn("HOW:", err, text)
                self.assertFalse(
                    os.path.exists(os.path.join(d, "g10.receipts.json")), text
                )

    def test_a_timeout_is_a_whole_number_of_seconds_from_one_to_a_day(self):
        for text in ("0", "-1", "86401", "abc", "", "1.5", " ", "1e3"):
            with tempfile.TemporaryDirectory() as d:
                code, out, err = cli(
                    "run",
                    "--dir",
                    d,
                    "--id",
                    "T1",
                    "--tool",
                    "script",
                    "--target",
                    "prototype",
                    "--variant",
                    "fixed",
                    "--version-argv",
                    VERSION,
                    "--timeout",
                    text,
                    "--",
                    PY,
                    "-c",
                    "pass",
                )
                self.assertEqual(2, code, text)
                self.assertIn("is not a timeout this tool can honour", err, text)
                self.assertFalse(
                    os.path.exists(os.path.join(d, "g10.receipts.json")), text
                )
        for text in ("1", "86400", "30"):
            with tempfile.TemporaryDirectory() as d:
                code, out, err = cli(
                    "run",
                    "--dir",
                    d,
                    "--id",
                    "T1",
                    "--tool",
                    "script",
                    "--target",
                    "prototype",
                    "--variant",
                    "fixed",
                    "--version-argv",
                    VERSION,
                    "--timeout",
                    text,
                    "--",
                    PY,
                    "-c",
                    "pass",
                )
                self.assertEqual(0, code, (text, err, out))


class Commands(unittest.TestCase):
    def test_a_run_says_what_it_recorded_and_a_claim_says_that_it_is_one(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = cli(
                "run",
                "--dir",
                d,
                "--id",
                "R1",
                "--tool",
                "script",
                "--target",
                "prototype",
                "--variant",
                "fixed",
                "--version-argv",
                VERSION,
                "--",
                PY,
                "-c",
                "print('x')",
            )
            self.assertEqual(0, code)
            self.assertRegex(
                out, r"^recorded R1: exit 0 ok in [0-9.]+s; kept artifacts/R1\.out\n$"
            )
            code, out, _ = cli(
                "record",
                "--dir",
                d,
                "--id",
                "C1",
                "--tool",
                "script",
                "--tool-version",
                "v",
                "--target",
                "prototype",
                "--variant",
                "fixed",
                "--exit",
                "1",
                "--result",
                "error",
                "--",
                "x",
            )
            self.assertEqual(
                (0, "recorded the CLAIM C1: exit 1 error (not executed here)\n"),
                (code, out),
            )

    def test_a_refused_run_or_claim_prints_the_defect_with_its_what_why_and_how_and_exits_one(
        self,
    ):
        with tempfile.TemporaryDirectory() as d:
            cli(
                "record",
                "--dir",
                d,
                "--id",
                "C1",
                "--tool",
                "script",
                "--tool-version",
                "v",
                "--target",
                "prototype",
                "--variant",
                "fixed",
                "--exit",
                "0",
                "--result",
                "ok",
                "--",
                "x",
            )
            for args in (
                ("record", "--tool-version", "v", "--exit", "0", "--result", "ok"),
                ("run", "--version-argv", VERSION),
            ):
                code, out, _ = cli(
                    args[0],
                    "--dir",
                    d,
                    "--id",
                    "C1",
                    "--tool",
                    "script",
                    "--target",
                    "prototype",
                    "--variant",
                    "fixed",
                    *args[1:],
                    "--",
                    PY,
                    "-c",
                    "pass",
                )
                self.assertEqual(1, code, args[0])
                for word in ("1 defect(s).", "[RUN2]", "WHAT:", "WHY:", "HOW:"):
                    self.assertIn(word, out, (args[0], word))

    def test_a_violation_exit_is_refused_for_quint_with_a_message_on_stderr_and_exit_two(
        self,
    ):
        for tool in ("quint_typecheck", "quint_run", "quint_verify"):
            with tempfile.TemporaryDirectory() as d:
                code, out, err = cli(
                    "run",
                    "--dir",
                    d,
                    "--id",
                    "Q1",
                    "--tool",
                    tool,
                    "--target",
                    "model",
                    "--variant",
                    "base",
                    "--violation-exit",
                    "1",
                    "--",
                    "quint",
                    "run",
                    "m.qnt",
                )
                self.assertEqual((2, ""), (code, out), tool)
                self.assertIn(
                    "--violation-exit is for tools whose output this tool cannot read",
                    err,
                )
        with tempfile.TemporaryDirectory() as d:
            code, out, err = cli(
                "run",
                "--dir",
                d,
                "--id",
                "S1",
                "--tool",
                "script",
                "--target",
                "prototype",
                "--variant",
                "fixed",
                "--version-argv",
                VERSION,
                "--violation-exit",
                "3",
                "--",
                PY,
                "-c",
                "import sys; sys.exit(3)",
            )
            self.assertEqual(0, code, err)
            self.assertIn("violation", out)


class Scope(unittest.TestCase):
    def test_a_scope_sees_the_shared_entries_and_its_own_and_the_shared_scope_only_itself(
        self,
    ):
        self.assertEqual(("shared",), S.scopes_for("shared"))
        self.assertEqual(("shared", "value:3"), S.scopes_for("value:3"))

    def test_when_two_scopes_define_one_run_the_value_wins_whatever_the_order_of_the_handoff(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            twin = json.loads(json.dumps(section(doc, "receipts")["runs"][0]))
            twin["tool_version"] = "the version in the value scope"
            doc["sections"].append(
                {
                    "kind": "receipts",
                    "scope": "value:1",
                    "status": {"tag": "applicable", "payload": {"runs": [twin]}},
                }
            )
            h = decode(doc)
        flipped = dict(reversed(list(h.items())))
        self.assertEqual(list(reversed(list(h))), list(flipped))
        for handoff in (h, flipped):
            seen = S.visible(handoff, "value:1").runs[twin["id"]]
            self.assertEqual("the version in the value scope", seen.tool_version)
            self.assertNotEqual(
                "the version in the value scope",
                S.visible(handoff, "shared").runs[twin["id"]].tool_version,
            )

    def test_a_repeated_id_in_one_section_resolves_to_the_same_entry_whatever_the_order_of_the_list(
        self,
    ):
        with fresh_copy() as d:
            h = decode(base_doc(d))
        runs = h[("receipts", "shared")].status.payload.runs
        models = h[("model", "shared")].status.payload.models
        a, b = (
            dc.replace(runs[0], tool_version="version a"),
            dc.replace(runs[0], tool_version="version b"),
        )
        ma, mb = (
            dc.replace(models[0], path="a.qnt"),
            dc.replace(models[0], path="b.qnt"),
        )
        seen = set()
        for rs, ms in (((a, b), (ma, mb)), ((b, a), (mb, ma))):
            changed = C.replace(
                C.replace(
                    h,
                    T.Entry(
                        kind="receipts",
                        scope="shared",
                        status=T.Applicable(payload=T.Receipts(runs=rs)),
                    ),
                ),
                T.Entry(
                    kind="model",
                    scope="shared",
                    status=T.Applicable(payload=T.Models(models=ms)),
                ),
            )
            v = S.visible(changed, "shared")
            seen.add((v.runs[a.id].tool_version, v.models[ma.id].path))
        self.assertEqual(1, len(seen), seen)

    def test_a_closure_may_rest_on_the_construction_claims_of_its_scope_and_only_on_those(
        self,
    ):
        with fresh_copy() as d:
            doc = base_doc(d)
            ids = [c["id"] for c in section(doc, "construction")["claims"]]
            closure_ = section(doc, "closure")["closures"][0]
            closure_["safety"]["basis"] = {"tag": "constructed", "claims": ids}
            self.assertEqual(
                [],
                [
                    x.rule
                    for x in RU.check(decode(doc), None, "auto", d)[0]
                    if x.rule == "CL7"
                ],
            )
            closure_["safety"]["basis"] = {
                "tag": "constructed",
                "claims": [*ids, "E99"],
            }
            self.assertEqual(
                ["CL7"],
                [
                    x.rule
                    for x in RU.check(decode(doc), None, "auto", d)[0]
                    if x.rule == "CL7"
                ],
            )


class Types(unittest.TestCase):
    def test_the_kept_trace_of_a_run_is_the_same_whatever_the_order_of_its_artifacts(
        self,
    ):
        with fresh_copy() as d:
            run = decode(base_doc(d))[("receipts", "shared")].status.payload.runs[0]
        t1 = T.Artifact(role="trace", path="traces/a.json", sha256="1" * 64)
        t2 = T.Artifact(role="trace", path="traces/a.json", sha256="0" * 64)
        t3 = T.Artifact(role="trace", path="traces/0.json", sha256="f" * 64)
        out = T.Artifact(role="output", path="artifacts/0.out", sha256="0" * 64)
        for order in ((t1, t2, t3, out), (out, t3, t2, t1), (t2, out, t1, t3)):
            self.assertEqual(t3, T.trace_of(dc.replace(run, artifacts=order)))
        self.assertIsNone(T.trace_of(dc.replace(run, artifacts=(out,))))
        self.assertIsNone(T.trace_of(dc.replace(run, artifacts=())))

    def test_a_typed_value_cannot_be_changed_and_is_built_by_field_name(self):
        pending = T.Pending()
        with self.assertRaises(dc.FrozenInstanceError):
            pending.tag = "judged"
        with self.assertRaises(TypeError):
            T.Pending("pending")
        self.assertEqual(T.Pending(), T.Pending(tag="pending"))

    def test_a_path_that_leaves_the_sidecar_is_not_a_relative_path_and_a_locator_may_not_either(
        self,
    ):
        for good in ("traces/a.json", "a", "a/b/c.txt", "x-y_z@1+2/f.json"):
            self.assertTrue(T.valid("RelPath", good), good)
        for bad in ("../a", "a/../b", "/abs/a", "..", "", "a b", "a\n", "a/.."):
            self.assertFalse(T.valid("RelPath", bad), repr(bad))
        self.assertTrue(T.valid("Locator", "pagination.py::paginate"))
        self.assertFalse(T.valid("Locator", "../pagination.py::paginate"))
        self.assertFalse(T.valid("Locator", "/etc/passwd"))


class Report(unittest.TestCase):
    def test_a_report_counts_first_numbers_each_defect_from_one_and_names_what_could_not_run(
        self,
    ):
        ds = [
            D.Defect("L1", "laws:a", "what a", "why a", "how a"),
            D.Defect("R2", "receipts:b", "what b", "why b", "how b"),
        ]
        text = D.report(ds, "S3 needs a directory")
        self.assertEqual(
            [
                "2 defect(s).",
                "1. [L1] laws:a",
                "   WHAT: what a",
                "   WHY: why a",
                "   HOW: how a",
                "2. [R2] receipts:b",
                "   WHAT: what b",
                "   WHY: why b",
                "   HOW: how b",
                "Not run: S3 needs a directory",
            ],
            text.splitlines(),
        )
        self.assertEqual(["0 defects.", "Not run: x"], D.report([], "x").splitlines())
        self.assertEqual(["0 defects."], D.report([]).splitlines())


if __name__ == "__main__":
    unittest.main()
