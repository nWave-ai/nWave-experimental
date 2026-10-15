"""The paths that fail: a file that cannot be read, a directory that cannot be made, two files that disagree, a decoder with no case.

Line and branch coverage of the suite (coverage.py, `branch = True`, subprocesses included) showed these lines were never run.
Each test makes the real failure happen on the real file system and reads what the command says.
Run:  cd analysis/g10 && python3 -W ignore -m unittest tests.test_surv_edges
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.des.architect_handoff.tests.test_g10 import fixture_context
from tests.des.architect_handoff.tests.test_surv_run import Sidecar, script

from des.application.architect_handoff import g10 as G
from des.application.architect_handoff import g10_codec as C
from des.application.architect_handoff import g10_itf as I
from des.application.architect_handoff import g10_run as RUN
from des.application.architect_handoff import g10_types as T


NOT_ROOT = unittest.skipIf(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    "a superuser can read what mode 000 forbids",
)


def cli(*args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = G.main(list(args))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue()


class TwoFilesThatDisagree(unittest.TestCase):
    def test_two_files_that_give_one_section_two_contents_are_refused_naming_the_section_by_every_command(
        self,
    ):
        with tempfile.TemporaryDirectory() as d:
            names = ("a.json", "b.json")
            wire, catalog, _ = fixture_context(
                {
                    "sections": [
                        {
                            "kind": "laws",
                            "scope": "shared",
                            "status": {
                                "tag": "not_applicable",
                                "reason": reason,
                            },
                        }
                        for reason in ("one reason", "another reason")
                    ]
                }
            )
            manifest = Path(d, "design.json")
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "facts": [
                            {"id": record.id, "text": record.text}
                            for record in catalog.records
                        ],
                    }
                ),
                encoding="utf-8",
            )
            context = [
                {
                    "path": manifest.name,
                    "sha256": T.sha256_bytes(manifest.read_bytes()),
                }
            ]
            for name, section in zip(names, wire["sections"], strict=True):
                with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                    json.dump({"sections": [section], "catalog": context}, fh)
            for command in ("check", "render", "summary"):
                code, out = cli(
                    command, os.path.join(d, "a.json"), os.path.join(d, "b.json")
                )
                self.assertEqual(1, code, command)
                self.assertIn("laws", out, command)
                self.assertIn("1 defect(s).", out, command)
            code, out = cli(
                "check",
                os.path.join(d, "a.json"),
                os.path.join(d, "a.json"),
                "--dir",
                d,
            )
            self.assertNotIn("two files", out)


class ADecoderWithNoCase(unittest.TestCase):
    def test_a_type_the_grammar_cannot_decode_is_a_loud_grammar_bug_and_never_a_silent_pass(
        self,
    ):
        with self.assertRaises(TypeError) as cm:
            C.dec(complex, 1, "$.x", [])
        self.assertIn("grammar bug", str(cm.exception))
        self.assertIn("$.x", str(cm.exception))


class ATraceFileThatCannotBeRead(unittest.TestCase):
    def test_a_missing_file_and_a_file_that_is_not_json_say_so_and_so_does_a_file_nested_beyond_what_json_allows(
        self,
    ):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "none.json")
            with self.assertRaises(I.ItfError) as cm:
                I.load(missing)
            self.assertIn(f"cannot read {missing}", str(cm.exception))
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            with self.assertRaises(I.ItfError) as cm:
                I.load(bad)
            self.assertIn(f"{bad} is not valid JSON", str(cm.exception))
            deep = os.path.join(d, "deep.json")
            with open(deep, "w", encoding="utf-8") as fh:
                fh.write("[" * 200000 + "]" * 200000)
            with self.assertRaises(I.ItfError) as cm:
                I.load(deep)
            self.assertIn("is not valid JSON", str(cm.exception))


class TheFirstLineOfAVersion(unittest.TestCase):
    def test_blank_lines_are_skipped_and_the_next_stream_is_read_when_the_first_has_no_text(
        self,
    ):
        self.assertEqual("real", RUN._first_line(b"  \n\t\nreal\nlater\n"))
        self.assertEqual("second", RUN._first_line(b" \n", b"\nsecond\n"))
        self.assertEqual("", RUN._first_line(b"", b" \n\n"))

    def test_a_version_command_that_cannot_start_is_refused_with_the_command_named(
        self,
    ):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RUN.RunError) as cm:
                RUN.tool_version(
                    "script", [os.path.join(d, "no-such-binary"), "--version"], d
                )
        self.assertEqual("RUN1", cm.exception.defect.rule)
        self.assertIn("did not run", cm.exception.defect.what)
        self.assertIn("no-such-binary", cm.exception.defect.what)


class TheSidecarThatCannotBeUsed(Sidecar):
    def test_a_sidecar_that_is_a_file_or_whose_parent_is_missing_is_refused_before_anything_runs(
        self,
    ):
        plain = os.path.join(self.dir, "plain")
        with open(plain, "w", encoding="utf-8") as fh:
            fh.write("x")
        d = self.refused("RUN5", self.go, "E1", argv=self.marking(), directory=plain)
        self.assertIn("is not a directory", d.what)
        d = self.refused(
            "RUN5",
            self.go,
            "E2",
            argv=self.marking(),
            directory=os.path.join(self.dir, "no", "such"),
        )
        self.assertIn("its parent", d.what)
        self.assertFalse(os.path.exists(self.marker()))

    @NOT_ROOT
    def test_a_directory_that_cannot_be_created_or_written_is_refused_with_the_reason_of_the_system(
        self,
    ):
        parent = os.path.join(self.dir, "closed")
        Path(parent).mkdir()
        Path(parent).chmod(0o555)
        self.addCleanup(Path(parent).chmod, 0o755)
        d = self.refused(
            "RUN5",
            self.go,
            "E3",
            argv=self.marking(),
            directory=os.path.join(parent, "sidecar"),
        )
        self.assertIn("cannot create the sidecar directory", d.what)
        d = self.refused("RUN5", self.go, "E4", argv=self.marking(), directory=parent)
        self.assertIn("is not writable", d.what)
        self.assertFalse(os.path.exists(self.marker()))

    def test_an_artifacts_path_that_is_a_file_is_refused_before_the_command_runs(self):
        with open(os.path.join(self.dir, "artifacts"), "w", encoding="utf-8") as fh:
            fh.write("in the way")
        d = self.refused("RUN5", self.go, "E5", argv=self.marking())
        self.assertIn("cannot create the artifacts directory", d.what)
        self.assertFalse(os.path.exists(self.marker()))

    @NOT_ROOT
    def test_an_unreadable_kept_trace_prevents_replacement_before_the_command_runs(
        self,
    ):
        trace = os.path.join(self.dir, "t.json")
        self.go(
            "TRACE", trace="t.json", argv=script(f"open({trace!r}, 'w').write('{{}}')")
        )
        with open(self.receipts_path(), "rb") as fh:
            before = fh.read()
        Path(trace).chmod(0o000)
        self.addCleanup(Path(trace).chmod, 0o644)
        d = self.refused(
            "RUN3", self.go, "TRACE", trace="t.json", replace=True, argv=self.marking()
        )
        self.assertIn("cannot read the trace file", d.what)
        self.assertIn(trace, d.what)
        self.assertFalse(os.path.exists(self.marker()))
        with open(self.receipts_path(), "rb") as fh:
            self.assertEqual(before, fh.read())

    @NOT_ROOT
    def test_a_receipts_file_that_cannot_be_read_is_refused_and_a_run_is_not_wasted(
        self,
    ):
        self.note("A1")
        Path(self.receipts_path()).chmod(0o000)
        self.addCleanup(Path(self.receipts_path()).chmod, 0o644)
        d = self.refused("G12", self.go, "E6", argv=self.marking())
        self.assertIn("cannot read the file", d.what)
        self.assertFalse(os.path.exists(self.marker()))
        d = self.refused("G12", self.note, "A2")
        self.assertIn("cannot read the file", d.what)

    def test_a_violation_exit_is_refused_for_a_quint_command_before_it_runs(self):
        with open(os.path.join(self.dir, "quint"), "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\ntouch ran.marker\n")
        (Path(self.dir) / "quint").chmod(0o755)
        d = self.refused(
            "RUN7",
            self.go,
            "E7",
            tool="quint_run",
            target="model",
            variant="base",
            argv=[os.path.join(self.dir, "quint"), "run", "m.qnt"],
            violation_exit=1,
        )
        self.assertIn("--violation-exit is declared", d.what)
        self.assertFalse(os.path.exists(self.marker()))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "ran.marker")))


if __name__ == "__main__":
    unittest.main()
