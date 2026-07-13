"""Feature `examinable-gate-surface`, slice-01.

Value statement (feature-delta.md [REF] Slice Plan, slice-01): an examiner
runs ONE command (`des examine-fixture`) and gets a repository the REAL
certification gate (`des verify-slice-commit`) ACCEPTS on the clean case --
a genuinely SHIPPED+attested slice, an entering slice, and a
deliberately-red work-ahead slice -- each flippable red/green by editing one
line, so she can break already-delivered work and observe the gate's actual
verdict WITHOUT ever reading the gate's source.

Measured, 2026-07-13 (feature-delta.md [REF] Observable): an examiner who
cannot read source BY CONSTRUCTION rationally defected to running the
producer's own test suite and reporting its results -- a mirror, void
verdict -- because no command handed her a drivable world. A hand-built
fixture (full source access, RCA in hand) was STILL refused by the real
gate, because the regression-file naming convention it requires
(`_regression_file_glob_candidates`, `verify_slice_commit_completeness.py`)
lives only in the gate's own implementation. This file pins the round trip
(tool -> REAL gate -> verdict) that ends the mirror.

Pinned CLI contract for `des examine-fixture --out <dir>` (the spec this AT
hands to DELIVER, not yet implemented):

  - Builds a real git repo AT `<dir>` containing a genuinely SHIPPED+attested
    slice (a real `Slice-Id:`-trailered commit AND a real `SliceCommitVerified`
    ledger record written through `AtCompletionLedger.append_gate_event` --
    never hand-written ledger bytes), a real entering slice (the tip commit's
    `Slice-Id:` trailer), and a deliberately-red work-ahead slice.
  - Every slice's regression test is a real pytest file the gate's OWN
    `_regression_file_glob_candidates` convention resolves
    (`tests/**/{feature_dir}/test_{slice_id}_*.py`), containing exactly one
    `assert True` (green) or `assert False` (red) line -- so it is flippable
    by a single textual substitution, never a hand-guessed convention.
  - Prints exactly one JSON object on stdout (a human-readable line may
    precede/follow it) naming: `repo`, `feature_id`, `shipped_slice`,
    `entering_slice`, `work_ahead_slice` (each `{slice_id, test_file,
    currently_passing}`), and `flip_instructions` -- everything an examiner
    needs to drive and BREAK the fixture without opening the product's own
    `src/`/`tests/`.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition, IN-PROCESS
default): the REAL `des.cli.__main__.main(["examine-fixture", ...])`
dispatcher and the REAL `des.cli.verify_slice_commit_completeness.main(...)`
gate, both called in-process and captured via `capsys` -- mirrors the proven
sibling pattern in
`tests/bugs/des/test_contract_gate_scopes_shipped_plus_entering.py`. No
mocking of the gate: C1's whole promise is that the REAL, unstubbed gate
accepts a REAL, unstubbed produced world.

Active-RED today (real assertion failures, never an import/collection
error): `examine-fixture` is not a registered subcommand yet
(`des.cli.__main__._REGISTRY` has no such row) -- the real argparse
dispatcher exits 2 with `error: argument subcommand: invalid choice:
'examine-fixture'`. Every test below calls the SAME `_run_examine_fixture`
helper and its `_parsed_payload` assertion fails first on `exit_code == 0`
(a semantic AssertionError on the CLI's real, observed response), never on
an import of a not-yet-existing module.
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import __main__ as des_dispatch
from des.cli import verify_slice_commit_completeness as vscc


# ---------------------------------------------------------------------------
# Shared driving helpers -- reused across every test below (Pillar 2: one
# shared Given/When, never re-derived per scenario).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FixtureRun:
    exit_code: int
    stdout: str
    stderr: str


def _run_des(argv: list[str], capsys: pytest.CaptureFixture[str]) -> _FixtureRun:
    """Drive the REAL `des` dispatcher in-process, capturing its output.

    argparse's own `parser.error()` raises `SystemExit` on an unrecognized
    subcommand -- caught here so the CLI's real observable response (exit
    code + stderr) becomes an ordinary return value the caller can assert
    on, never an uncaught exception masquerading as a collection error.
    """
    try:
        exit_code = des_dispatch.main(list(argv))
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    captured = capsys.readouterr()
    return _FixtureRun(exit_code=exit_code, stdout=captured.out, stderr=captured.err)


def _run_examine_fixture(
    out_dir: Path, capsys: pytest.CaptureFixture[str]
) -> _FixtureRun:
    return _run_des(["examine-fixture", "--out", str(out_dir)], capsys)


def _last_json_object(text: str) -> dict[str, object]:
    lines = [ln for ln in text.splitlines() if ln.strip().startswith("{")]
    return json.loads(lines[-1]) if lines else {}


def _parsed_payload(run: _FixtureRun) -> dict[str, object]:
    """Assert the tool produced a drivable world, return its JSON payload.

    Ordered so the FIRST assertion is the one that fails today: the command
    is unregistered, so `exit_code` is 2 (`invalid choice`), never 0. This is
    the single point every test below fails at right now -- a real,
    semantic AssertionError on the dispatcher's observed exit code, not an
    ImportError.
    """
    assert run.exit_code == 0, (
        "`des examine-fixture --out <dir>` must exit 0 and hand back a "
        f"drivable world -- got exit_code={run.exit_code!r} "
        f"stdout={run.stdout!r} stderr={run.stderr!r}"
    )
    payload = _last_json_object(run.stdout)
    assert payload, (
        "`des examine-fixture` must print a JSON object naming the repo, "
        "feature-id, and every slice's test file -- an examiner who cannot "
        f"read source has nothing else to go on. got stdout={run.stdout!r}"
    )
    return payload


def _run_gate(
    repo: Path, feature_id: str, capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    """Drive the REAL `des verify-slice-commit` gate in-process (C1/C2/C4/C5's
    round-trip target) -- never mocked, per the feature's whole promise.
    """
    argv = ["--repo", str(repo), "--commit", "HEAD", "--feature-id", feature_id]
    exit_code = vscc.main(argv)
    stdout = capsys.readouterr().out
    return exit_code, _last_json_object(stdout)


def _slice_entry(payload: dict[str, object], role: str) -> dict[str, object]:
    entry = payload.get(role)
    assert isinstance(entry, dict), (
        f"the printed payload must carry a {role!r} object -- payload={payload!r}"
    )
    for field in ("slice_id", "test_file"):
        assert field in entry, (
            f"{role} must name its {field!r} in the printed payload so an "
            f"examiner can drive it without reading source -- entry={entry!r}"
        )
    return entry


# ---------------------------------------------------------------------------
# C1 -- the produced world is ACCEPTED by the REAL gate on the clean case.
# ---------------------------------------------------------------------------


def test_examine_fixture_world_is_accepted_by_the_real_gate_on_the_clean_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """If the gate refuses a fixture the tool itself produced, the tool has
    failed at its only job (feature-delta.md C1)."""
    out_dir = tmp_path / "world"
    payload = _parsed_payload(_run_examine_fixture(out_dir, capsys))

    repo = Path(str(payload.get("repo", "")))
    feature_id = str(payload.get("feature_id", ""))
    assert repo.is_dir(), (
        f"the printed `repo` path must exist on disk -- payload={payload!r}"
    )
    assert feature_id, (
        f"the printed `feature_id` must be non-empty -- payload={payload!r}"
    )

    exit_code, gate_payload = _run_gate(repo, feature_id, capsys)
    assert exit_code == 0, (
        "the REAL `des verify-slice-commit` must ACCEPT the world "
        f"`des examine-fixture` produced -- got exit_code={exit_code!r} "
        f"gate_payload={gate_payload!r} fixture_payload={payload!r}"
    )
    assert gate_payload.get("event") in (
        "SliceCommitVerified",
        "SliceCommitComplete",
    ), (
        f"expected an accepted verdict on the clean case -- gate_payload={gate_payload!r}"
    )


# ---------------------------------------------------------------------------
# C2 -- the lever actually moves the world: breaking a SHIPPED slice refuses.
# ---------------------------------------------------------------------------


def test_flipping_the_shipped_slices_test_the_real_gate_refuses_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An examiner must be able to break already-delivered work and see the
    gate catch it (feature-delta.md C2) -- a fixture you cannot break is a
    demo, not a surface."""
    out_dir = tmp_path / "world"
    payload = _parsed_payload(_run_examine_fixture(out_dir, capsys))
    repo = Path(str(payload.get("repo", "")))
    feature_id = str(payload.get("feature_id", ""))
    shipped = _slice_entry(payload, "shipped_slice")
    shipped_slice_id = str(shipped["slice_id"])
    shipped_test_file = repo / str(shipped["test_file"])

    assert shipped_test_file.is_file(), (
        f"the printed shipped-slice test file must exist -- {shipped_test_file}"
    )
    text = shipped_test_file.read_text(encoding="utf-8")
    assert "assert True" in text, (
        "the shipped slice's test must start GREEN as a single `assert True` "
        f"line, per the pinned flip convention -- got: {text!r}"
    )
    shipped_test_file.write_text(
        text.replace("assert True", "assert False"), encoding="utf-8"
    )

    exit_code, gate_payload = _run_gate(repo, feature_id, capsys)
    assert exit_code != 0, (
        "breaking an already-SHIPPED slice's regression test must make the "
        f"REAL gate REFUSE -- got exit_code={exit_code!r} gate_payload={gate_payload!r}"
    )
    haystack = json.dumps(gate_payload)
    assert shipped_slice_id in haystack, (
        f"the refusal must NAME the broken shipped slice ({shipped_slice_id}), "
        f"not just the entering one -- gate_payload={gate_payload!r}"
    )


# ---------------------------------------------------------------------------
# C3 -- the shipped slice's attestation is written through the REAL ledger.
# ---------------------------------------------------------------------------


def test_shipped_slice_attestation_is_written_through_the_real_ledger_writer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fabricated ledger record is worse than no fixture at all -- it lies
    in the exact dimension the gate reads (feature-delta.md C3)."""
    out_dir = tmp_path / "world"
    payload = _parsed_payload(_run_examine_fixture(out_dir, capsys))
    repo = Path(str(payload.get("repo", "")))
    feature_id = str(payload.get("feature_id", ""))
    shipped_slice_id = str(_slice_entry(payload, "shipped_slice")["slice_id"])

    ledger_path = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    assert ledger_path.is_file(), (
        "the shipped slice's attestation must land on the REAL M7 ledger "
        f"substrate -- {ledger_path} does not exist. fixture_payload={payload!r}"
    )
    records = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    shipped_records = [
        r
        for r in records
        if r.get("event") == "SliceCommitVerified"
        and r.get("slice_id") == shipped_slice_id
    ]
    assert shipped_records, (
        f"no SliceCommitVerified record for {shipped_slice_id} on the real "
        f"ledger substrate -- records={records!r}"
    )
    for field in ("seq", "record_hash"):
        assert field in shipped_records[0], (
            f"the SliceCommitVerified record is missing the M7 {field!r} "
            "integrity field -- only `AtCompletionLedger.append_gate_event` "
            "mints these; a hand-written ledger line would have to forge "
            f"them. record={shipped_records[0]!r}"
        )

    # Round-trip through the REAL reader -- a forged record cannot silently
    # masquerade as real, because the reader fail-closes on a broken M7
    # hash chain (`AtCompletionLedger.read_records`).
    verified = AtCompletionLedger(feature_id, repo).verified_slices()
    assert shipped_slice_id in verified, (
        f"the real AtCompletionLedger reader must recognize {shipped_slice_id} "
        f"as verified -- verified={sorted(verified)!r}"
    )


# ---------------------------------------------------------------------------
# Negative AT #1 -- anti-mirror: stdout alone must be enough to drive it.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_stdout_alone_drives_the_round_trip_no_product_source_read_required(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The examiner must reach a verdict WITHOUT reading any file under
    `src/` or `tests/` of the product (feature-delta.md, the heart of it).
    Asserts the WRONG outcome (a payload silently missing a field an
    examiner would need) is NOT produced, then proves the printed payload
    alone -- no other knowledge -- is sufficient to drive the fixture to an
    accepted verdict."""
    out_dir = tmp_path / "world"
    payload = _parsed_payload(_run_examine_fixture(out_dir, capsys))

    for key in (
        "repo",
        "feature_id",
        "shipped_slice",
        "entering_slice",
        "work_ahead_slice",
        "flip_instructions",
    ):
        assert key in payload, (
            f"an examiner who cannot read source needs {key!r} printed by "
            f"the command itself -- payload={payload!r}"
        )
    for role in ("shipped_slice", "entering_slice", "work_ahead_slice"):
        _slice_entry(payload, role)
    flip_instructions = str(payload["flip_instructions"])
    assert "assert" in flip_instructions.lower(), (
        "flip_instructions must actually describe the flip mechanism (the "
        f"single `assert` line) -- got: {flip_instructions!r}"
    )

    # Drive the ENTIRE round trip using ONLY values extracted from stdout.
    repo = Path(str(payload["repo"]))
    feature_id = str(payload["feature_id"])
    work_ahead = _slice_entry(payload, "work_ahead_slice")
    work_ahead_file = repo / str(work_ahead["test_file"])
    assert work_ahead_file.is_file(), (
        f"the printed work-ahead test file must exist -- {work_ahead_file}"
    )
    assert work_ahead["currently_passing"] is False, (
        "the work-ahead slice must be RED on purpose (deliberately "
        f"unimplemented) -- entry={work_ahead!r}"
    )

    exit_code, gate_payload = _run_gate(repo, feature_id, capsys)
    assert exit_code == 0, (
        "driving the fixture using ONLY the printed payload must reach the "
        f"same accepted verdict as C1 -- exit_code={exit_code!r} "
        f"gate_payload={gate_payload!r}"
    )


# ---------------------------------------------------------------------------
# Negative AT #2 -- fault-injection / positive control: the fixture can say
# NO in either direction, and still says YES on the clean case.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_a_broken_entering_slice_still_refuses_the_fixture_is_not_a_rubber_stamp(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A fixture that cannot fail proves nothing. Breaking the ENTERING
    slice's own test (not the shipped one -- C2's target) must also refuse,
    proving the tool did not produce a world where everything always
    passes."""
    out_dir = tmp_path / "world"
    payload = _parsed_payload(_run_examine_fixture(out_dir, capsys))
    repo = Path(str(payload.get("repo", "")))
    feature_id = str(payload.get("feature_id", ""))
    entering = _slice_entry(payload, "entering_slice")
    entering_test_file = repo / str(entering["test_file"])

    text = entering_test_file.read_text(encoding="utf-8")
    assert "assert True" in text, (
        f"the entering slice's test must start GREEN -- got: {text!r}"
    )
    entering_test_file.write_text(
        text.replace("assert True", "assert False"), encoding="utf-8"
    )

    exit_code, gate_payload = _run_gate(repo, feature_id, capsys)
    assert exit_code != 0, (
        "breaking the ENTERING slice's own test must also make the REAL "
        f"gate REFUSE -- a fixture that only ever refuses on the shipped "
        f"slice would prove nothing about the entering path. got "
        f"exit_code={exit_code!r} gate_payload={gate_payload!r}"
    )


# ---------------------------------------------------------------------------
# Base observable -- the command must exist at all.
# ---------------------------------------------------------------------------


def test_examine_fixture_subcommand_is_registered_on_the_des_dispatcher(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The round-trip promise (C1-C3 above) is unreachable until the `des`
    dispatcher recognizes the subcommand. Pins the dispatcher's OWN
    observable response -- not an ImportError: today argparse's registry
    (`des.cli.__main__._REGISTRY`) has no `examine-fixture` row, so the real
    subparser rejects it with `invalid choice`, exit code 2."""
    run = _run_examine_fixture(tmp_path / "world", capsys)
    assert run.exit_code == 0, (
        "`des examine-fixture` must be a REGISTERED subcommand that exits 0 "
        f"on a clean build -- today it is UNREGISTERED: "
        f"exit_code={run.exit_code!r} stderr={run.stderr!r}"
    )


# ---------------------------------------------------------------------------
# The documented round trip -- the examiner's actual FAIL (2026-07-13).
#
# She never read a line of this tool's or the gate's source. She drove the
# EXACT command `des examine-fixture` printed in `flip_instructions`, and the
# REAL gate refused the clean case:
#
#     {"event": "SliceCommitRefused", "refused_half": "E2",
#      "contract_gate_exit_code": 2,
#      "why": "no .feature file resolves under feature id
#              'examine-fixture-demo' -- the scoped contract gate would pass
#              vacuously"}
#
# The 6 tests above are all GREEN and STILL do not witness this: every one
# of them drives the gate through `_run_gate` (or `_run_des`), and that
# helper's argv -- `--repo <repo> --commit HEAD --feature-id <feature_id>` --
# happens to be BYTE-IDENTICAL to what `flip_instructions` documents. Their
# green is not proof the documented path works in general; it is proof this
# particular helper matches the tool's advice TODAY, by construction, because
# both were authored by hand against the SAME literal string. Nothing in the
# 6 tests would notice if the tool's advice and the gate's real requirement
# ever drifted apart again -- the exact mirror this section closes: it reads
# the command from the tool's OWN stdout, at test time, and drives THAT.
# ---------------------------------------------------------------------------


_DOCUMENTED_GATE_COMMAND_RE = re.compile(r"`([^`]*verify-slice-commit[^`]*)`")


def _documented_gate_argv(
    flip_instructions: str, *, repo: Path, feature_id: str
) -> list[str]:
    """Extract the `des verify-slice-commit ...` invocation `flip_instructions`
    tells the examiner to run, substitute the concrete `<repo>`/`<feature_id>`
    placeholders, and return it as a `des`-dispatcher argv (subcommand +
    flags, the `des` program name stripped).

    Never hardcodes the expected command string: whatever the tool prints
    TODAY is what gets parsed and driven. If the tool's advice changes (more
    flags, fewer, different placeholders), this AT tracks it -- it only
    fails when the ADVICE and the GATE'S REAL REQUIREMENT disagree, not when
    the advice's wording changes.
    """
    match = _DOCUMENTED_GATE_COMMAND_RE.search(flip_instructions)
    assert match, (
        "flip_instructions must name the exact `des verify-slice-commit ...` "
        "command an examiner who cannot read source is told to run -- got: "
        f"{flip_instructions!r}"
    )
    concrete = (
        match.group(1).replace("<repo>", str(repo)).replace("<feature_id>", feature_id)
    )
    tokens = shlex.split(concrete)
    assert tokens and tokens[0] == "des", (
        "the documented command must be a `des <subcommand>` invocation an "
        f"examiner can run verbatim from a shell -- got: {tokens!r}"
    )
    return tokens[1:]


def test_the_documented_flip_instructions_command_verifies_the_clean_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The examiner's actual path: parse the command `flip_instructions`
    prints, run it VERBATIM -- no flag she was never shown -- and the real
    gate must ACCEPT the clean case.

    This is the assertion the examiner's real run failed on
    (`SliceCommitRefused`, `refused_half: E2`, `contract_gate_exit_code: 2`).
    The principle this pins: the HOW a tool prints must WORK. A suggested
    command that fails is worse than no suggestion -- it is a broken promise
    at the moment of maximum trust.
    """
    out_dir = tmp_path / "world"
    payload = _parsed_payload(_run_examine_fixture(out_dir, capsys))
    repo = Path(str(payload["repo"]))
    feature_id = str(payload["feature_id"])
    flip_instructions = str(payload["flip_instructions"])

    documented_argv = _documented_gate_argv(
        flip_instructions, repo=repo, feature_id=feature_id
    )
    run = _run_des(documented_argv, capsys)
    gate_payload = _last_json_object(run.stdout)

    assert run.exit_code == 0, (
        "running EXACTLY the command `des examine-fixture` printed in "
        "`flip_instructions` must let the examiner reach an ACCEPTED "
        f"verdict on the clean case -- got exit_code={run.exit_code!r} "
        f"documented_argv={documented_argv!r} gate_payload={gate_payload!r}. "
        "An examiner who cannot read source has no other command to try; a "
        "printed command that fails IS the defect, regardless of whether "
        "some other, unprinted invocation would have succeeded."
    )
    assert gate_payload.get("event") in (
        "SliceCommitVerified",
        "SliceCommitComplete",
    ), (
        "the documented command must reach an accepted verdict, not merely "
        f"exit 0 -- gate_payload={gate_payload!r}"
    )


@pytest.mark.negative_at
def test_no_flag_beyond_what_flip_instructions_prints_is_ever_needed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Anti-mirror: an invocation the tool never shows the examiner must
    NEVER be required to reach a verdict.

    Proves this on the tool's OWN OUTPUT, not by trusting the previous test:
    every flag the real gate's argument parser could possibly need to reach
    a DECISIVE verdict (accept or refuse -- never a malformed-input error)
    on this fixture is a flag that already appears, verbatim, in
    `flip_instructions`. If driving the gate to a decisive verdict required
    a flag `flip_instructions` never mentions, the tool would have moved the
    problem onto the examiner instead of solving it -- exactly the shape
    the 6 pre-existing tests missed by hardcoding the same flags the tool
    happens to print today.
    """
    out_dir = tmp_path / "world"
    payload = _parsed_payload(_run_examine_fixture(out_dir, capsys))
    repo = Path(str(payload["repo"]))
    feature_id = str(payload["feature_id"])
    flip_instructions = str(payload["flip_instructions"])

    documented_argv = _documented_gate_argv(
        flip_instructions, repo=repo, feature_id=feature_id
    )
    documented_flags = {token for token in documented_argv if token.startswith("--")}

    run = _run_des(documented_argv, capsys)
    gate_payload = _last_json_object(run.stdout)
    event = str(gate_payload.get("event", ""))

    # A malformed-input refusal (E1/E2 "malformed"/argparse error) means the
    # documented flags were NOT sufficient to reach a real accept/refuse
    # verdict -- the tool's advice under-informs the examiner. A decisive
    # verdict (accepted OR a genuine behavioural refusal naming a failed
    # slice) means the documented flags were enough.
    decisive_events = {
        "SliceCommitVerified",
        "SliceCommitComplete",
        "SliceCommitRefused",
        "SliceCommitIndeterminate",
    }
    assert event in decisive_events, (
        "every flag needed to drive the gate to a DECISIVE verdict must "
        f"appear in what `des examine-fixture` prints -- got event={event!r} "
        f"(documented_flags={sorted(documented_flags)!r}) "
        f"gate_payload={gate_payload!r}. Reaching a verdict required "
        "knowledge the tool never emitted -- the tool moved the problem, "
        "it did not solve it."
    )
    if event == "SliceCommitRefused":
        assert gate_payload.get("refused_half") != "E2" or "vacuously" not in str(
            gate_payload.get("why", gate_payload.get("error", ""))
        ), (
            "a vacuous-scope refusal on the documented-flags-only invocation "
            "means the printed command cannot reach a real verdict at all -- "
            f"gate_payload={gate_payload!r}"
        )


# ---------------------------------------------------------------------------
# The fault-injection probe, reachable via the documented path only.
# ---------------------------------------------------------------------------


def test_breaking_the_shipped_slice_via_the_documented_command_still_refuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The examiner must be able to reach the fault-injection probe (C2)
    using ONLY the printed `flip_instructions` -- not the hand-authored
    `_run_gate` helper the 6 pre-existing tests share. Following the
    documented path alone: flip the already-SHIPPED slice's test red,
    re-run the DOCUMENTED command, and the real gate must REFUSE and NAME
    that slice.
    """
    out_dir = tmp_path / "world"
    payload = _parsed_payload(_run_examine_fixture(out_dir, capsys))
    repo = Path(str(payload["repo"]))
    feature_id = str(payload["feature_id"])
    flip_instructions = str(payload["flip_instructions"])
    shipped = _slice_entry(payload, "shipped_slice")
    shipped_slice_id = str(shipped["slice_id"])
    shipped_test_file = repo / str(shipped["test_file"])

    text = shipped_test_file.read_text(encoding="utf-8")
    assert "assert True" in text, (
        f"the shipped slice's test must start GREEN -- got: {text!r}"
    )
    shipped_test_file.write_text(
        text.replace("assert True", "assert False"), encoding="utf-8"
    )

    documented_argv = _documented_gate_argv(
        flip_instructions, repo=repo, feature_id=feature_id
    )
    run = _run_des(documented_argv, capsys)
    gate_payload = _last_json_object(run.stdout)

    assert run.exit_code != 0, (
        "flipping the shipped slice red and re-running ONLY the documented "
        f"command must make the REAL gate REFUSE -- got "
        f"exit_code={run.exit_code!r} gate_payload={gate_payload!r}. The "
        "examiner could not even reach this probe until the documented "
        "command itself works on the clean case."
    )
    haystack = json.dumps(gate_payload)
    assert shipped_slice_id in haystack, (
        f"the refusal reached via the documented path must NAME the broken "
        f"shipped slice ({shipped_slice_id}) -- gate_payload={gate_payload!r}"
    )


# ---------------------------------------------------------------------------
# The examiner's ACTUAL mistake (2026-07-13, verified on the real surface):
# `flip_instructions` prints `... verify-slice-commit --repo <repo> --commit
# HEAD --feature-id <feature_id>` -- `<repo>` and `<feature_id>` are
# PLACEHOLDERS. She substituted `<repo>` -> `.`, the most natural reading
# there is, and pointed the certification gate at the WORKING REPOSITORY
# ITSELF instead of the fixture. She got an error about missing `.feature`
# files that had nothing to do with her real mistake and chased a phantom.
#
# This is a RECURRENCE: the same class was filed once already (a gate's HOW
# carrying an `<id>` placeholder, "not fully copy-paste"). The two tests
# below pin it so it cannot come back a third time -- the first proves the
# printed command must WORK exactly as printed, byte for byte, with zero
# substitution; the second is the durable one, general enough to catch the
# NEXT placeholder (it will not be spelled `<repo>` or `<feature_id>`).
# ---------------------------------------------------------------------------


_PLACEHOLDER_RE = re.compile(r"<[^<>\s`]+>")


def _all_backticked_commands(payload: dict[str, object]) -> list[str]:
    """Every backtick-quoted command string anywhere in the printed
    payload -- not just `flip_instructions` -- so the placeholder check
    covers the whole printed surface, including any field a future change
    might carry a command in."""
    return re.findall(r"`([^`]+)`", json.dumps(payload))


def test_the_documented_command_works_verbatim_with_zero_substitution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The examiner's real path, unlike the tests above: she does NOT know
    `<repo>` and `<feature_id>` are placeholders needing substitution -- she
    treats the backticked string as a command and runs it AS PRINTED. Take
    the `des verify-slice-commit ...` command out of `flip_instructions`
    verbatim -- no substitution of any kind, not even the ones
    `_documented_gate_argv` performs above -- and shell it exactly as
    emitted. It must reach a decisive, non-error verdict.

    Today it cannot: the literal token `<repo>` is not a directory that
    exists, so the real gate's own `--repo` handling refuses it -- the exact
    failure surface the examiner hit, reached here without a human in the
    loop.
    """
    out_dir = tmp_path / "world"
    payload = _parsed_payload(_run_examine_fixture(out_dir, capsys))
    flip_instructions = str(payload["flip_instructions"])

    match = _DOCUMENTED_GATE_COMMAND_RE.search(flip_instructions)
    assert match, (
        "flip_instructions must name the exact `des verify-slice-commit ...` "
        f"command an examiner is told to run -- got: {flip_instructions!r}"
    )
    verbatim = match.group(1)
    tokens = shlex.split(verbatim)
    assert tokens and tokens[0] == "des", (
        "the documented command must be a `des <subcommand>` invocation an "
        f"examiner can run verbatim from a shell -- got: {tokens!r}"
    )

    run = _run_des(tokens[1:], capsys)
    gate_payload = _last_json_object(run.stdout)
    assert run.exit_code == 0, (
        "the printed command, shelled EXACTLY as printed -- zero "
        "substitution, not even filling in `<repo>`/`<feature_id>` with the "
        "values this test already knows from `payload` -- must reach an "
        f"accepted verdict. got exit_code={run.exit_code!r} tokens={tokens!r} "
        f"gate_payload={gate_payload!r}. This is the examiner's real "
        "failure: she substituted `<repo>` -> `.`, the only plausible "
        "reading available to her, and pointed the certification gate at "
        "her own working repository instead of the fixture."
    )


@pytest.mark.negative_at
def test_no_emitted_command_carries_an_unsubstituted_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """RECURRENCE of a known defect class (a gate's HOW carrying an `<id>`
    placeholder, filed once already as "not fully copy-paste") -- it came
    back. Phrased generally enough to catch the NEXT placeholder, which will
    not be spelled `<repo>` or `<feature_id>`: no backtick-quoted command
    anywhere in the printed payload may contain any `<...>`-shaped token.

    Not cosmetic: the most plausible wrong substitution an examiner who
    cannot read source will make -- `<repo>` -> `.` -- aims the
    certification gate at the EXAMINER'S OWN working repository instead of
    the fixture. She gets an error about missing `.feature` files that has
    nothing to do with her actual mistake, and chases a phantom. A
    remediation carrying a placeholder is not a remediation.
    """
    out_dir = tmp_path / "world"
    payload = _parsed_payload(_run_examine_fixture(out_dir, capsys))

    commands = _all_backticked_commands(payload)
    assert commands, (
        "expected at least one backtick-quoted command in the printed "
        f"payload to check for placeholders -- payload={payload!r}"
    )
    offenders = {
        cmd: hits for cmd in commands if (hits := _PLACEHOLDER_RE.findall(cmd))
    }
    assert not offenders, (
        "no command the tool prints may contain an unsubstituted "
        f"placeholder -- offenders={offenders!r}. The tool already knows "
        "the repo path and the feature-id -- it just printed them, two "
        "lines above -- so making the examiner re-type them is charging "
        "her for work the tool already did, and the most plausible wrong "
        "substitution (`<repo>` -> `.`) is catastrophic: it aims the "
        "certification gate at her own working repository."
    )
