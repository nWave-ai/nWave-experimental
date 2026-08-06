"""Regression: `des record-prose-delivered` is unreachable (implemented-not-wired).

``src/des/cli/record_prose_delivered.py`` is a complete DDD-5 PRODUCER -- a
working ``main(argv)``, its own argparse, and a real ``record_prose_delivered``
function that appends an honest ``SliceProseDelivered`` record to the
AT-completion ledger. But it has ZERO rows in the dispatcher's ``_REGISTRY``
tuple (``src/des/cli/__main__.py``), so ``des record-prose-delivered ...`` is
not a recognised subcommand at all. A prose slice that reaches doc-review
APPROVED has no way to mint its ``SliceProseDelivered`` record, so
``verify-integrity`` reports ``FeatureUnreconciled`` on an otherwise-complete
feature -- this repo hit the identical implemented-not-wired class this
morning on ``des blast-radius`` (a forgotten ``_SubcommandRow`` registration).

Fix: add ``_SubcommandRow("record-prose-delivered",
"des.cli.record_prose_delivered", "main")`` to ``_REGISTRY`` in
``src/des/cli/__main__.py``.

Obligation -> witness map:
  a) test_is_a_recognised_dispatcher_subcommand           -- reachability
  b) test_appears_in_dispatcher_advertised_help            -- discoverability
  c) test_dispatched_invocation_writes_a_readable_ledger_record -- it records
  d) test_cannot_write_record_never_reports_pretend_success -- no theater
  e) test_missing_required_argument_is_a_clear_usage_error +
     test_unrecognised_option_is_a_clear_usage_error        -- clean usage errors
  f) test_every_cli_subcommand_module_is_registered_or_allow_listed -- structural guard
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

import des.cli as cli_pkg
import des.cli.__main__ as des_main


_SUBCOMMAND = "record-prose-delivered"

# Modules under src/des/cli/ that plainly expose a module-level `main(argv)`
# but are DELIBERATELY not a `des <name>` dispatcher subcommand. Every entry
# carries the evidence for why it is excused -- a silent/unexplained skip
# would recreate the exact blindness this guard exists to remove. Do NOT add
# an entry here to make a failure go away without that evidence.
_ALLOWED_NON_SUBCOMMAND_MODULES: dict[str, str] = {
    # Package/dispatcher scaffolding, not candidate subcommands.
    "__init__": "package marker, no CLI surface.",
    "__main__": "the dispatcher itself.",
    # Leading-underscore = explicit "not a subcommand" per this package's own
    # convention; each is a shared CORE consumed by real registered
    # subcommands, never dispatched by name.
    "_collect_scope_worker": (
        "own docstring: 'spawned by FILE PATH ... never as a des.cli import "
        "module' -- a short-lived pytest-isolation child worker for "
        "run_contract_gate / gate_scope_digest, invoked as "
        "`<python> _collect_scope_worker.py --repo ...`, not `des ...`."
    ),
    "_identity_args": "shared argv-parsing helper module, no main(argv) of its own.",
    "_reverify_core": (
        "shared precondition/gate/record CORE reused by reverify_slice_commit "
        "and attest_bundled_slice (attest_bundled_slice.py's own docstring); "
        "not itself a subcommand entry point."
    ),
    # Deliberately MODULE-DIRECT composition roots -- each module's own
    # docstring documents why it is invoked with `python -m des.cli.<name>`
    # rather than through the `des` dispatcher.
    "carpaccio_precheck": (
        "own docstring: 'Invoked MODULE-DIRECT against the "
        "des.cli.carpaccio_precheck module, NOT as a des dispatcher "
        "subcommand ... F-DES-AT-REVIEW-VERDICT-SUBCOMMAND-SURFACE defers "
        "the subcommand ergonomics'."
    ),
    "phases": (
        "own docstring: 'Module-direct invocation via the runtime "
        "interpreter's -m switch ... never the bare python console name'."
    ),
    "dormant_seam_gate": (
        "own docstring: 'an importable des.cli module run as a subprocess'; "
        "invoked as `python -m des.cli.dormant_seam_gate` -- confirmed by the "
        "literal string in all four oss-dormant-seam-gate composition steps "
        "(tests/des/acceptance/oss-dormant-seam-gate/steps/composition.py:13 "
        "+ composition_slice_02.py:17 + composition_slice_03.py:23 + "
        "composition_slice_04.py:26, each also naming the subprocess helper "
        "`_run_gate` as 'Run `python -m des.cli.dormant_seam_gate` as a "
        "subprocess black box'). The GREEN-phase hook seam taps this same "
        "module-direct invocation (docs/feature/oss-dormant-seam-gate/design/"
        "component-manifest.yaml: 'Component(cli, \"des dormant-seam-gate "
        'CLI", "des.cli module" ...)\'). NOTE: the component-manifest label '
        "reads 'des dormant-seam-gate' in prose, which could be misread as a "
        "dispatcher subcommand name -- but every executable invocation site "
        "found (4 composition files) uses the module-direct `-m` form, never "
        "`des dormant-seam-gate`; if a future slice wires it into _REGISTRY "
        "too, remove this entry then (dual-reachability is fine, silent "
        "staleness here is not)."
    ),
}

# NOT allow-listed, and deliberately so: `commit` (src/des/cli/commit.py).
# ADR-027 (docs/architecture/ADR-027-parallel-deliver-commit-isolation.md:75)
# planned it as its OWN `[project.scripts]` entry (`des-commit`), predating
# the single-entry-point consolidation. `des-commit` was later listed as a
# LEGACY shim REMOVED on upgrade (scripts/install/plugins/des_plugin.py
# LEGACY_DES_SHIMS) alongside log-phase/init-log/verify-integrity/roadmap/
# health-check -- but unlike those five (each now a live _REGISTRY row),
# `commit` never received one. No production code anywhere invokes it --
# `git grep` finds only `from des.cli.commit import main` in
# tests/des/integration/test_des_commit_cli.py (a direct Python import, not a
# subprocess/`-m` boundary like every allow-listed module above). This reads
# as a THIRD implemented-not-wired orphan (the locked, fail-closed commit
# helper ADR-027 built to prevent parallel-DELIVER cross-staging corruption
# is currently unreachable by any agent), not a deliberate module-direct
# design -- reported to the team-lead as a finding, intentionally left OFF
# the allow-list.


def _cli_dir() -> Path:
    return Path(cli_pkg.__file__).resolve().parent


def _module_declares_main(py_file: Path) -> bool:
    """True iff ``py_file`` defines a module-level ``def main(...)``."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    return any(
        isinstance(node, ast.FunctionDef) and node.name == "main" for node in tree.body
    )


def _valid_argv(
    repo_root: Path,
    *,
    feature_id: str = "feat-demo",
    slice_id: str = "slice-01",
) -> list[str]:
    return [
        _SUBCOMMAND,
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--verdict",
        "APPROVED",
        "--reviewer-agent-id",
        "reviewer-x",
        "--doc-review-ref",
        f"docs/feature/{feature_id}/design/peer-review.md",
        "--repo-root",
        str(repo_root),
    ]


def _fail_unreachable(exc: SystemExit, captured_err: str) -> None:
    pytest.fail(
        "'des record-prose-delivered' is NOT a recognised subcommand: "
        f"argparse rejected it (SystemExit code={exc.code}). stderr="
        f"{captured_err!r}. src/des/cli/record_prose_delivered.py exists "
        "with a working main(argv) but has ZERO rows for it in the "
        "_REGISTRY tuple of src/des/cli/__main__.py, so `des "
        "record-prose-delivered ...` is unreachable. Fix: add "
        "_SubcommandRow('record-prose-delivered', "
        "'des.cli.record_prose_delivered', 'main') to _REGISTRY."
    )


class TestRecordProseDeliveredReachability:
    """(a) headline: the subcommand must be dispatchable from the outside."""

    def test_is_a_recognised_dispatcher_subcommand(self, tmp_path, capsys):
        argv = _valid_argv(tmp_path)
        try:
            exit_code = des_main.main(argv)
        except SystemExit as exc:
            captured = capsys.readouterr()
            _fail_unreachable(exc, captured.err)
        else:
            assert exit_code == 0, (
                f"des record-prose-delivered was reached but exited "
                f"{exit_code!r} against a valid hermetic invocation."
            )


class TestRecordProseDeliveredDiscoverability:
    """(b) a user who does not already know the name can find it."""

    def test_appears_in_dispatcher_advertised_help(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            des_main.main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert _SUBCOMMAND in captured.out, (
            f"'{_SUBCOMMAND}' is missing from `des --help`'s advertised "
            "subcommand list -- a user who does not already know the exact "
            f"module name cannot discover it. Actual help text:\n{captured.out}"
        )


class TestRecordProseDeliveredActuallyRecords:
    """(c) invoked properly, the claimed record is really written and readable."""

    def test_dispatched_invocation_writes_a_readable_ledger_record(self, tmp_path):
        feature_id = "feat-demo"
        ledger_path = (
            tmp_path / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
        )
        argv = _valid_argv(tmp_path, feature_id=feature_id)
        try:
            des_main.main(argv)
        except SystemExit as exc:
            _fail_unreachable(exc, "")

        assert ledger_path.exists(), (
            "des record-prose-delivered reported success but wrote no "
            f"ledger file at {ledger_path}."
        )
        records = [
            json.loads(line)
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        prose_records = [r for r in records if r.get("event") == "SliceProseDelivered"]
        assert prose_records, (
            f"ledger file {ledger_path} exists but contains no readable "
            f"SliceProseDelivered record among {records!r}."
        )
        record = prose_records[0]
        assert record["slice_id"] == "slice-01"
        assert record["verdict"] == "APPROVED"
        assert record["attested"] is True
        assert record["at_verified"] is False


class TestRecordProseDeliveredNeverPretends:
    """(d) the negative that matters most: never claim success while writing nothing."""

    def test_cannot_write_record_never_reports_pretend_success(self, capsys, tmp_path):
        # A regular FILE where a directory must be created -- the ledger's
        # own `mkdir(parents=True, exist_ok=True)` cannot succeed under it.
        blocking_file = tmp_path / "repo-root-is-a-file"
        blocking_file.write_text("not a directory\n", encoding="utf-8")
        argv = _valid_argv(blocking_file)

        try:
            exit_code = des_main.main(argv)
        except SystemExit as exc:
            captured = capsys.readouterr()
            if "invalid choice" in captured.err or "invalid choice" in captured.out:
                _fail_unreachable(exc, captured.err)
            exit_code = exc.code
        except OSError:
            exit_code = 1
            captured = capsys.readouterr()
        else:
            captured = capsys.readouterr()

        assert "SliceProseDeliveredCLI" not in captured.out, (
            "des record-prose-delivered printed a success event "
            f"({captured.out!r}) even though its ledger write target under "
            f"{blocking_file} cannot hold a directory -- this is exactly the "
            "pretend-success class the record's consumer (the carpaccio "
            "in-order gate) must never see."
        )
        assert exit_code != 0, (
            "des record-prose-delivered must exit non-zero when it cannot "
            f"write the record; got exit_code={exit_code!r} for an "
            f"unwritable --repo-root {blocking_file}."
        )
        ledger_file = (
            blocking_file / ".nwave" / "telemetry" / "atdd-pure" / "feat-demo.jsonl"
        )
        assert not ledger_file.exists()


class TestRecordProseDeliveredUsageErrors:
    """(e) wrong/missing arguments produce a clear usage error, never a bare
    traceback or silence -- and never get mistaken for the dispatcher's own
    'unknown subcommand' rejection."""

    @pytest.mark.parametrize(
        "missing_flag",
        [
            "--feature-id",
            "--slice-id",
            "--verdict",
            "--reviewer-agent-id",
            "--doc-review-ref",
        ],
    )
    def test_missing_required_argument_is_a_clear_usage_error(
        self, capsys, tmp_path, missing_flag
    ):
        argv = _valid_argv(tmp_path)
        idx = argv.index(missing_flag)
        argv = argv[:idx] + argv[idx + 2 :]

        with pytest.raises(SystemExit) as exc_info:
            des_main.main(argv)
        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert "invalid choice" not in captured.err, (
            "the failure is the DISPATCHER rejecting "
            f"'{_SUBCOMMAND}' as an unknown subcommand, not the module's own "
            "argument validation -- src/des/cli/__main__.py's _REGISTRY has "
            f"zero rows for {_SUBCOMMAND}. stderr={captured.err!r}"
        )
        assert missing_flag in captured.err, (
            f"expected a usage error naming the missing {missing_flag!r}; "
            f"got stderr={captured.err!r}."
        )

    def test_unrecognised_option_is_a_clear_usage_error(self, capsys, tmp_path):
        argv = [*_valid_argv(tmp_path), "--not-a-real-flag", "bogus"]

        with pytest.raises(SystemExit) as exc_info:
            des_main.main(argv)
        assert exc_info.value.code == 2

        captured = capsys.readouterr()
        assert "invalid choice" not in captured.err, (
            f"the failure is the DISPATCHER rejecting '{_SUBCOMMAND}' as an "
            "unknown subcommand, not the module's own argument validation. "
            f"stderr={captured.err!r}"
        )
        assert "--not-a-real-flag" in captured.err or "unrecognized" in captured.err, (
            f"expected a usage error naming the unrecognised option; got "
            f"stderr={captured.err!r}."
        )


class TestNoOrphanedCliSubcommands:
    """(f) structural guard: catch ANY future orphaned CLI module of this class.

    Every module under src/des/cli/ that exposes a module-level main(argv)
    and is plainly a subcommand entry point must be registered in _REGISTRY.
    Modules deliberately NOT meant to be dispatcher subcommands must appear
    in the explicit, justified _ALLOWED_NON_SUBCOMMAND_MODULES allow-list
    above -- a silent skip would recreate the blindness this test removes.
    """

    def test_every_cli_subcommand_module_is_registered_or_allow_listed(self):
        registered = {row.module_path.rsplit(".", 1)[-1] for row in des_main._REGISTRY}
        cli_dir = _cli_dir()

        orphans = []
        for py_file in sorted(cli_dir.glob("*.py")):
            name = py_file.stem
            if name in _ALLOWED_NON_SUBCOMMAND_MODULES:
                continue
            if name in registered:
                continue
            if not _module_declares_main(py_file):
                continue
            orphans.append(name)

        assert not orphans, (
            "the following src/des/cli/*.py modules expose a module-level "
            "main(argv) but are neither registered in _REGISTRY "
            "(src/des/cli/__main__.py) nor allow-listed in "
            "_ALLOWED_NON_SUBCOMMAND_MODULES (this test file): "
            f"{orphans!r}. Each is unreachable as `des <name>` today "
            "(the implemented-not-wired class). Either add a _SubcommandRow "
            "for it, or add a justified entry to the allow-list above."
        )
