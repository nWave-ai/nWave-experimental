# @feature-f-context-consumption-probe
"""Acceptance tests -- D71 `context_admission` EMITTER (component 1 of 2).

Feature: f-context-consumption-probe, slice-01. Full design:
`docs/feature/f-context-consumption-probe/feature-delta.md` +
`docs/product/architecture/ADR-D71-context-consumption-probe.md`.

SCOPE: extends `scripts/hooks/orchestrator_affordance_refresh.py` (EXTEND
reuse row) with one `context_admission` PARENT record plus flat CHILD
records appended per hook firing to
`.nwave/staging/d71/context-admission.jsonl`. This file authors NET-NEW
acceptance tests against that extension only -- zero production code is
written here (DISTILL boundary).

MEASURED FACTS overriding the feature-delta's frozen `context_admission`
schema where they conflict (lane-ctxprobe, verified against the live
transcript corpus -- encoded as ATs here, never re-derived):

  - `correlation_id`/`correlationId` does not exist as a JSON key in any
    transcript (0 matches, whole project transcript store). No AT here
    expects one.
  - `tool_use_id` is NOT a per-hook key (one SessionStart toolUseID is
    shared by 4 distinct hook commands in a single firing; the literal
    value "SessionStart" recurs 11 times). The EMITTER CANNOT fill it at
    all -- the harness assigns `toolUseID` AFTER the hook process exits
    (same causality boundary as `bytes_admitted`). The record must carry
    `tool_use_id: null` always, never an invented value.
  - The honest EMITTER-side join key is `stdout_sha256` -- sha256 of the
    exact bytes this process wrote to stdout for the envelope. The emitter
    can fill this truthfully; the reducer's pairing leg
    (`test_context_consumption_reducer.py`) recomputes it from
    `hook_success.stdout` and joins on it instead of `tool_use_id`.

RECORD-SHAPE CORRECTION (lane-d71deliver, post-crafter real-hook-fire
finding -- this file's ORIGINAL authoring missed the dispatch's own
"payloads is NORMALIZED into child rows... NOT nested" instruction and
wrote a nested `payloads: [...]` array; fixed here, not just appended
around): a firing writes exactly ONE PARENT record (`kind:
"context_admission"`, scalar fields only: schema_version, ts, session_id,
agent_name, agent_id, event, hook, tool_use_id, total_bytes_offered,
bytes_admitted, stdout_sha256, feature_id, scope) plus N FLAT CHILD
records -- `kind: "context_admission_payload"` per successfully-offered
asset (path, bytes_offered, role) and `kind:
"context_admission_dropped_asset"` per asset whose read failed (path,
reason) -- each child joining back to its parent on `stdout_sha256`. NO
record in the ledger ever carries a nested list value (pinned by a
dedicated negative AT below).

GAP-CLOSING (lane-d71deliver, same finding, three completeness gaps a
real hook fire exposed with zero AT holding the crafter to them):

  1. `session_id` must come from the stdin JSON envelope Claude Code pipes
     (established in-repo pattern: `hook_router.py:82-85`,
     `sys.stdin.read()` inside a fail-open try/except) -- the ORIGINAL
     scenarios below never fed stdin, so nothing caught `session_id`
     staying `null` even on a well-formed envelope.
  2. `payloads` nesting (see RECORD-SHAPE CORRECTION above).
  3. `feature_id` (nullable) + `scope` (`feature|session|node`
     discriminator) were entirely absent from every record; the ORIGINAL
     scenarios below never asserted their presence.

Driving port (Mandate 16, no-direct-domain-testing): every scenario below
drives the REAL script `scripts/hooks/orchestrator_affordance_refresh.py`
via subprocess, argv[1] = the hook event name, exactly as Claude Code
invokes it. This continues the EXACT precedent already established for
this same script in the sibling regression file
`test_orchestrator_affordance_refresh_independent.py`: "the script's
shipped surface IS the subprocess boundary (a Claude Code hook has no
other entry point), so subprocess-driving here is the L2 'composition
root' for this artifact class, not a Layer-3 e2e shortcut." No new
`@walking_skeleton` is declared in this file -- the script's end-to-end
wiring (installer registration, DES-independence, host-neutral asset
resolution) is already proven by that sibling file's existing scenarios;
this file adds the net-new `context_admission` emission behaviour on the
same already-wired surface, per Mandate 2's "explicit justification for
additional E2E" clause.

RED-for-right-reason: `_build_admission_record` and the JSONL-append call
site do not exist yet in `orchestrator_affordance_refresh.py`. Because the
subprocess boundary isolates the SUT, the current (unmodified) script
simply never writes `.nwave/staging/d71/context-admission.jsonl` -- every
scenario below fails on a semantic `AssertionError` (missing ledger file /
missing field), never a collection-time ImportError on THIS test file
(stdlib + `subprocess` + `pytest` only).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.common.orchestrator_affordance_paths import affordance_asset_names


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "hooks" / "orchestrator_affordance_refresh.py"
_LEDGER_RELATIVE = Path(".nwave") / "staging" / "d71" / "context-admission.jsonl"
_PERMITTED_SCOPES = {"feature", "session", "node"}


# ===========================================================================
# Shared driving + assertion helpers
# ===========================================================================


def _run(
    script: Path,
    event: str,
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    stdin: str = "",
) -> subprocess.CompletedProcess[str]:
    """Invoke the hook script exactly as Claude Code would: argv[1] = event,
    the JSON hook-payload envelope (if any) piped on stdin.
    """
    return subprocess.run(
        [sys.executable, str(script), event],
        cwd=cwd,
        capture_output=True,
        text=True,
        input=stdin,
        timeout=30,
        env=env,
    )


def _parse_json_or_fail(stdout: str) -> dict:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"expected exactly one JSON object on stdout -- got {stdout!r}"
        ) from exc


def _read_ledger_lines(cwd: Path) -> list[str]:
    ledger = cwd / _LEDGER_RELATIVE
    if not ledger.exists():
        return []
    return [line for line in ledger.read_text(encoding="utf-8").splitlines() if line]


def _parse_ledger_records(cwd: Path) -> list[dict]:
    records = []
    for line in _read_ledger_lines(cwd):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"context-admission.jsonl line is not well-formed JSON: {line!r}"
            ) from exc
    return records


def _split_kind(records: list[dict], kind: str) -> list[dict]:
    return [r for r in records if r.get("kind") == kind]


def _one_parent(records: list[dict]) -> dict:
    parents = _split_kind(records, "context_admission")
    assert len(parents) == 1, (
        f"expected exactly one context_admission PARENT record -- got "
        f"{len(parents)}: {records!r}"
    )
    return parents[0]


def _snapshot_files(root: Path) -> set[Path]:
    if not root.exists():
        return set()
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


def _elapsed_sentinel(cwd: Path) -> Path:
    """A sentinel comfortably past the 900s UserPromptSubmit gate."""
    sentinel = cwd / ".nwave" / "orchestrator-affordance-last-injected"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.touch()
    stale_mtime = time.time() - 1_000
    os.utime(sentinel, (stale_mtime, stale_mtime))
    return sentinel


def _isolated_script_with_assets(tmp_path: Path, asset_files: dict[str, str]) -> Path:
    """Copy the real script to an isolated location + fabricate an assets dir
    it resolves via the dev-checkout candidate (three `.parent` hops).
    """
    isolated_root = tmp_path / "isolated-install"
    script_dir = isolated_root / "scripts" / "hooks"
    script_dir.mkdir(parents=True)
    isolated_script = script_dir / _SCRIPT.name
    isolated_script.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    assets_dir = isolated_root / "nWave" / "data" / "orchestrator-affordance"
    assets_dir.mkdir(parents=True)
    for name, content in asset_files.items():
        (assets_dir / name).write_text(content, encoding="utf-8")
    return isolated_script


def _no_nested_list_values(records: list[dict]) -> list[str]:
    """Return a list of `record_index.field` violations where a top-level
    field value is a `list`/`tuple` -- the flat-ledger invariant.
    """
    violations = []
    for idx, record in enumerate(records):
        for field, value in record.items():
            if isinstance(value, (list, tuple)):
                violations.append(f"record[{idx}].{field}={value!r}")
    return violations


# ===========================================================================
# 1. ONE parent + flat child rows per firing, no other path touched -- R1
# ===========================================================================


@pytest.mark.parametrize(
    ("event", "prepare"),
    [
        pytest.param(
            "SessionStart", lambda cwd: None, id="session-start-unconditional"
        ),
        pytest.param(
            "UserPromptSubmit",
            _elapsed_sentinel,
            id="user-prompt-submit-sentinel-elapsed",
        ),
    ],
)
def test_a_firing_appends_one_parent_and_flat_child_rows_and_touches_no_other_new_path(
    tmp_path: Path, event: str, prepare
) -> None:
    # covers: R1
    # @contract-shape:bounded-change
    prepare(tmp_path)
    before = _snapshot_files(tmp_path)

    result = _run(_SCRIPT, event, cwd=tmp_path)

    assert result.returncode == 0, (
        f"{event} must exit 0 -- got returncode={result.returncode}, "
        f"stderr={result.stderr!r}"
    )
    records = _parse_ledger_records(tmp_path)
    assert records, f"{event} firing must append >=1 JSONL line -- got none"

    parent = _one_parent(records)
    children = _split_kind(records, "context_admission_payload")
    assert children, (
        f"{event} firing must append >=1 flat child payload row -- got "
        f"records={records!r}"
    )
    for child in children:
        assert child.get("stdout_sha256") == parent.get("stdout_sha256"), (
            "every child row must join back to its parent on stdout_sha256 "
            f"-- child={child!r}, parent={parent!r}"
        )

    after = _snapshot_files(tmp_path)
    new_paths = after - before
    unexpected = {p for p in new_paths if p != _LEDGER_RELATIVE}
    # The UserPromptSubmit branch also refreshes its pre-existing sentinel
    # file -- that touch is NOT a new path (the sentinel already existed
    # from `prepare`), so no exemption is needed here for that case.
    assert not unexpected, (
        f"{event} firing touched unexpected new path(s) beyond the ledger -- "
        f"got {sorted(str(p) for p in unexpected)!r}"
    )


def test_user_prompt_submit_below_sentinel_threshold_appends_no_admission_record(
    tmp_path: Path,
) -> None:
    # covers: R1
    # @contract-shape:bounded-change
    sentinel = tmp_path / ".nwave" / "orchestrator-affordance-last-injected"
    sentinel.parent.mkdir(parents=True)
    sentinel.touch()
    fresh_mtime = time.time() - 100  # comfortably < 900s old
    os.utime(sentinel, (fresh_mtime, fresh_mtime))

    result = _run(_SCRIPT, "UserPromptSubmit", cwd=tmp_path)

    assert result.returncode == 0
    lines = _read_ledger_lines(tmp_path)
    assert lines == [], (
        "a firing that does not actually inject (sentinel not yet elapsed) "
        f"must append NO admission record -- got {lines!r}"
    )


# ===========================================================================
# 2. bytes_offered == real UTF-8 byte length of what was written -- R2
# ===========================================================================


def test_bytes_offered_equals_the_real_utf8_byte_length_of_the_written_asset(
    tmp_path: Path,
) -> None:
    # covers: R2
    # @contract-shape:bounded-change
    content = "# Orchestrator discipline\ncafé ☕ multi-byte payload\n"
    isolated_script = _isolated_script_with_assets(
        tmp_path, {"spine-discipline.md": content}
    )
    _elapsed_sentinel(tmp_path)

    result = _run(isolated_script, "UserPromptSubmit", cwd=tmp_path)

    assert result.returncode == 0, (
        f"got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    records = _parse_ledger_records(tmp_path)
    parent = _one_parent(records)
    children = _split_kind(records, "context_admission_payload")
    assert children, f"expected >=1 child payload row -- got records={records!r}"

    expected_bytes = len(content.encode("utf-8"))
    matching = [c for c in children if c.get("bytes_offered") == expected_bytes]
    assert matching, (
        f"expected a child row with bytes_offered == {expected_bytes} "
        f"(the REAL UTF-8 byte length, not the character count "
        f"{len(content)}) -- got children={children!r}"
    )

    total_bytes_offered = parent.get("total_bytes_offered")
    assert total_bytes_offered == sum(c.get("bytes_offered", 0) for c in children), (
        "the parent's total_bytes_offered must equal the sum of every "
        f"child's bytes_offered -- got total_bytes_offered="
        f"{total_bytes_offered!r}, children={children!r}"
    )


# ===========================================================================
# 3. NEGATIVE -- never a non-null bytes_admitted, never an invented
#    tool_use_id; the honest stdout_sha256 join key is always present -- R3
# ===========================================================================


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("event", "prepare"),
    [
        pytest.param("SessionStart", lambda cwd: None, id="session-start"),
        pytest.param("UserPromptSubmit", _elapsed_sentinel, id="user-prompt-submit"),
    ],
)
def test_the_record_never_invents_bytes_admitted_or_tool_use_id(
    tmp_path: Path, event: str, prepare
) -> None:
    # covers: R3
    # @contract-shape:bounded-change
    prepare(tmp_path)

    result = _run(_SCRIPT, event, cwd=tmp_path)

    assert result.returncode == 0
    records = _parse_ledger_records(tmp_path)
    parent = _one_parent(records)

    assert parent.get("bytes_admitted") is None, (
        "the emitter can NEVER observe admission (harness assigns it after "
        "the hook process exits) -- bytes_admitted must be null, got "
        f"parent={parent!r}"
    )
    assert parent.get("tool_use_id") is None, (
        "the emitter CANNOT fill tool_use_id (measured: harness assigns "
        "toolUseID after process exit; one SessionStart toolUseID is "
        "shared by 4 distinct hook commands) -- must be null, never an "
        f"invented value. got parent={parent!r}"
    )

    stdout_sha256 = parent.get("stdout_sha256")
    assert isinstance(stdout_sha256, str) and len(stdout_sha256) == 64, (
        "the parent must carry the honest emitter-side join key "
        "stdout_sha256 (sha256 hex digest of the exact stdout bytes this "
        f"process wrote) -- got stdout_sha256={stdout_sha256!r}"
    )


# ===========================================================================
# 4. Fail-open on an unwritable staging directory -- R4
# ===========================================================================


def test_unwritable_staging_directory_degrades_loud_but_still_fails_open(
    tmp_path: Path,
) -> None:
    # covers: R4
    # @contract-shape:bounded-change
    # `.nwave/staging` exists as a FILE, not a directory -- any attempt to
    # `mkdir(parents=True)` the `d71/` ledger directory beneath it raises
    # an OSError (NotADirectoryError), portably, without chmod/root tricks.
    staging_as_file = tmp_path / ".nwave" / "staging"
    staging_as_file.parent.mkdir(parents=True)
    staging_as_file.write_text("not a directory", encoding="utf-8")

    result = _run(_SCRIPT, "SessionStart", cwd=tmp_path)

    assert result.returncode == 0, (
        "SessionStart must NEVER block on a broken ledger (fail-open) -- "
        f"got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    payload = _parse_json_or_fail(result.stdout)
    assert payload.get("hookSpecificOutput", {}).get("hookEventName") == (
        "SessionStart"
    ), (
        "the hook must still print its envelope even when the ledger "
        f"append failed -- got payload={payload!r}"
    )

    stderr = result.stderr.strip()
    assert stderr, (
        "an unwritable staging directory must produce a non-silent stderr "
        "diagnostic -- got EMPTY stderr"
    )
    lowered = stderr.lower()
    assert "staging" in lowered or "d71" in lowered or str(staging_as_file) in stderr, (
        f"the diagnostic must NAME the path -- got stderr={stderr!r}"
    )
    assert (
        "oserror" in lowered
        or "not a directory" in lowered
        or "notadirectory" in (lowered.replace(" ", ""))
    ), f"the diagnostic must NAME the OSError -- got stderr={stderr!r}"


# ===========================================================================
# 5. Asset read failure -- could_not_verify note, never silent
#    under-reporting -- R5
# ===========================================================================


def test_a_dropped_asset_contributes_a_dropped_child_row_not_silent_underreport(
    tmp_path: Path,
) -> None:
    # covers: R5
    # @contract-shape:bounded-change
    isolated_script = _isolated_script_with_assets(
        tmp_path, {"readable.md": "# Readable asset\n"}
    )
    # A `.md` "file" that is actually a directory: `assets_dir.glob("*.md")`
    # matches it, but `Path.read_text()` raises `IsADirectoryError` (an
    # `OSError` subclass) -- the exact failure `_load_affordance`'s
    # existing `except OSError: continue` silently swallows today.
    assets_dir = (
        isolated_script.parent.parent.parent
        / "nWave"
        / "data"
        / ("orchestrator-affordance")
    )
    (assets_dir / "broken.md").mkdir()
    _elapsed_sentinel(tmp_path)

    result = _run(isolated_script, "UserPromptSubmit", cwd=tmp_path)

    assert result.returncode == 0, (
        f"got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    records = _parse_ledger_records(tmp_path)
    parent = _one_parent(records)
    dropped = _split_kind(records, "context_admission_dropped_asset")

    assert dropped, (
        "a firing whose asset read failed must contribute a FLAT dropped-"
        "asset child row rather than silently under-reporting the byte "
        f"count -- got records={records!r}"
    )
    for entry in dropped:
        assert entry.get("stdout_sha256") == parent.get("stdout_sha256"), (
            "the dropped-asset row must join back to its parent on "
            f"stdout_sha256 -- entry={entry!r}, parent={parent!r}"
        )
    dropped_paths = " ".join(str(entry.get("path", "")) for entry in dropped)
    assert "broken.md" in dropped_paths, (
        f"the dropped-asset row must NAME the broken file -- got dropped={dropped!r}"
    )


# ===========================================================================
# 6. GAP 1 -- session_id comes from the stdin envelope
#    (hook_router.py:82-85 pattern: fail-open sys.stdin.read())
# ===========================================================================


def test_a_well_formed_stdin_envelope_records_its_session_id(tmp_path: Path) -> None:
    # covers: R3
    # @contract-shape:bounded-change
    envelope = json.dumps(
        {
            "session_id": "1f30bf31-caf3-49f3-bc0c-1dc7d4f82612",
            "cwd": str(tmp_path),
            "hook_event_name": "UserPromptSubmit",
        }
    )
    _elapsed_sentinel(tmp_path)

    result = _run(_SCRIPT, "UserPromptSubmit", cwd=tmp_path, stdin=envelope)

    assert result.returncode == 0, (
        f"got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    records = _parse_ledger_records(tmp_path)
    parent = _one_parent(records)

    assert parent.get("session_id") == "1f30bf31-caf3-49f3-bc0c-1dc7d4f82612", (
        "a firing given a well-formed stdin envelope must record THAT "
        f"exact session_id -- got parent={parent!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    ("label", "stdin_payload"),
    [
        pytest.param("empty-stdin", "", id="empty-stdin"),
        pytest.param("malformed-json", "{not-well-formed-json,,,", id="malformed-json"),
        pytest.param(
            "no-session-id",
            json.dumps({"cwd": "/tmp/whatever", "hook_event_name": "SessionStart"}),
            id="envelope-without-session-id",
        ),
    ],
)
def test_missing_or_malformed_stdin_never_invents_a_session_id_and_never_blocks(
    tmp_path: Path, label: str, stdin_payload: str
) -> None:
    # covers: R3
    # @contract-shape:bounded-change
    result = _run(_SCRIPT, "SessionStart", cwd=tmp_path, stdin=stdin_payload)

    assert result.returncode == 0, (
        f"[{label}] reading stdin must NEVER block or fail the hook -- got "
        f"returncode={result.returncode}, stderr={result.stderr!r}"
    )
    payload = _parse_json_or_fail(result.stdout)
    assert payload.get("hookSpecificOutput", {}).get("hookEventName") == (
        "SessionStart"
    ), f"[{label}] the hook must still print its envelope -- got payload={payload!r}"

    records = _parse_ledger_records(tmp_path)
    parent = _one_parent(records)
    assert parent.get("session_id") is None, (
        f"[{label}] must NEVER invent a session_id from absent/malformed/"
        f"incomplete stdin -- got parent={parent!r}"
    )


# ===========================================================================
# 6b. TWO FIRINGS -- the parent<->child key is PER-FIRING, and stdout_sha256
#     is explicitly NOT one (lane-store DD-6 reconciliation)
# ===========================================================================


@pytest.mark.negative_at
def test_two_firings_get_distinct_correlation_ids_even_with_byte_identical_stdout(
    tmp_path: Path,
) -> None:
    # covers: R3
    # @contract-shape:bounded-change
    # SessionStart's stdout is a MODULE CONSTANT, so every firing writes
    # byte-identical bytes and therefore hashes to an identical
    # `stdout_sha256`. Measured: two firings -> ONE distinct digest. A reader
    # joining children to parents on that digest gets a CROSS PRODUCT --
    # every child of firing 2 also joins the parent of firing 1, silently.
    # `stdout_sha256` is a designation of CONTENT; the parent<->child join
    # needs an identity of the EVENT (GDP-8). Hence an emitter-generated
    # `correlation_id`, unique by construction.
    for _ in range(2):
        result = _run(_SCRIPT, "SessionStart", cwd=tmp_path)
        assert result.returncode == 0, f"stderr={result.stderr!r}"

    records = _parse_ledger_records(tmp_path)
    parents = _split_kind(records, "context_admission")
    assert len(parents) == 2, f"two firings must append two parents -- {records!r}"

    # The premise this AT rests on -- assert it rather than assume it, so the
    # test cannot silently start passing for the wrong reason.
    assert len({p["stdout_sha256"] for p in parents}) == 1, (
        "premise broken: this scenario exists BECAUSE two SessionStart "
        "firings share one stdout digest. If they now differ, this test is "
        f"no longer measuring what it was written for -- parents={parents!r}"
    )

    correlation_ids = [p.get("correlation_id") for p in parents]
    assert all(isinstance(c, str) and c for c in correlation_ids), (
        f"every parent must carry a correlation_id -- got {correlation_ids!r}"
    )
    assert len(set(correlation_ids)) == 2, (
        "two distinct firings must carry two DISTINCT correlation_ids -- a "
        "shared one makes the parent<->child join a cross product -- got "
        f"{correlation_ids!r}"
    )


def test_each_child_joins_exactly_one_parent_across_two_identical_firings(
    tmp_path: Path,
) -> None:
    # covers: R1
    # @contract-shape:bounded-change
    for _ in range(2):
        assert _run(_SCRIPT, "SessionStart", cwd=tmp_path).returncode == 0

    records = _parse_ledger_records(tmp_path)
    parents = _split_kind(records, "context_admission")
    children = _split_kind(records, "context_admission_payload")
    assert len(parents) == 2 and len(children) == 2, f"got records={records!r}"

    by_correlation = {p["correlation_id"] for p in parents}
    for child in children:
        matches = [
            p for p in parents if p["correlation_id"] == child.get("correlation_id")
        ]
        assert len(matches) == 1, (
            "a child must join EXACTLY ONE parent -- joining zero or many is "
            f"the cross-product defect -- child={child!r}, parents={parents!r}"
        )
    assert {c.get("correlation_id") for c in children} == by_correlation, (
        "every firing's child must carry ITS OWN firing's correlation_id -- "
        f"children={children!r}, parents={parents!r}"
    )


# ===========================================================================
# 7. GAP 2 -- payloads NORMALIZED into flat child rows, never nested
# ===========================================================================


def test_a_firing_yields_1_parent_and_1_flat_child_per_asset_joined_on_stdout_sha256(
    tmp_path: Path,
) -> None:
    # covers: R1
    # @contract-shape:bounded-change
    # Pinned against the actual production corpus. Both the COUNT and the
    # basenames come from an independent filesystem read (a genuine two-source
    # comparison vs. the emitted ledger), never a literal: assets are added
    # and their numeric injection-order prefixes churn (mikado D50), and a
    # hardcoded count turns this red on an asset addition that says nothing
    # about the one-child-per-asset property under test.
    _elapsed_sentinel(tmp_path)

    result = _run(_SCRIPT, "UserPromptSubmit", cwd=tmp_path)

    assert result.returncode == 0, (
        f"got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    records = _parse_ledger_records(tmp_path)
    parent = _one_parent(records)
    children = _split_kind(records, "context_admission_payload")

    expected_paths = affordance_asset_names(_REPO_ROOT)
    assert len(children) == len(expected_paths), (
        f"expected exactly {len(expected_paths)} flat child payload rows (one "
        f"per real *.md asset) -- got {len(children)}: {children!r}"
    )
    child_paths = {c.get("path") for c in children}
    assert child_paths == expected_paths, (
        f"got child_paths={child_paths!r}, expected {expected_paths!r} "
        "(real shipped orchestrator-affordance basenames)"
    )

    for child in children:
        assert child.get("stdout_sha256") == parent.get("stdout_sha256"), (
            f"every child must join to the parent on stdout_sha256 -- "
            f"child={child!r}, parent={parent!r}"
        )
    assert parent.get("total_bytes_offered") == sum(
        c.get("bytes_offered", 0) for c in children
    ), f"got parent={parent!r}, children={children!r}"


@pytest.mark.negative_at
def test_no_ledger_record_ever_contains_a_nested_list_value(tmp_path: Path) -> None:
    # covers: R1
    # @contract-shape:bounded-change
    _elapsed_sentinel(tmp_path)

    result = _run(_SCRIPT, "UserPromptSubmit", cwd=tmp_path)

    assert result.returncode == 0, (
        f"got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    records = _parse_ledger_records(tmp_path)
    assert records, "expected >=1 ledger record"

    violations = _no_nested_list_values(records)
    assert not violations, (
        "the hash domain and every existing reader assume a FLAT record -- "
        f"no ledger record may carry a nested list value -- got "
        f"violations={violations!r}"
    )


# ===========================================================================
# 8. GAP 3 -- feature_id (nullable) + scope discriminator
# ===========================================================================


def test_every_record_carries_a_feature_id_key_and_a_permitted_scope(
    tmp_path: Path,
) -> None:
    # covers: R3
    # @contract-shape:bounded-change
    result = _run(_SCRIPT, "SessionStart", cwd=tmp_path)

    assert result.returncode == 0, (
        f"got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    records = _parse_ledger_records(tmp_path)
    assert records, "expected >=1 ledger record"

    for record in records:
        assert "feature_id" in record, (
            f"every record must carry a feature_id KEY (nullable) -- got "
            f"record={record!r}"
        )
        scope = record.get("scope")
        assert scope in _PERMITTED_SCOPES, (
            f"scope must be one of {sorted(_PERMITTED_SCOPES)!r} -- got "
            f"scope={scope!r} on record={record!r}"
        )


@pytest.mark.negative_at
def test_feature_id_null_is_legal_and_never_coerced_to_a_placeholder(
    tmp_path: Path,
) -> None:
    # covers: R3
    # @contract-shape:bounded-change
    # A firing with no feature context declared (no `DES-PROJECT-ID`-style
    # signal available to this hook) is the common case -- "most dispatches
    # are not feature work". `feature_id: null` must be the honest,
    # UNCOERCED answer.
    result = _run(_SCRIPT, "SessionStart", cwd=tmp_path)

    assert result.returncode == 0
    records = _parse_ledger_records(tmp_path)
    parent = _one_parent(records)

    assert parent.get("feature_id") is None, (
        "a firing with no feature context must record feature_id: null -- "
        f"NEVER a placeholder like 'unknown'/'' -- got parent={parent!r}"
    )
    forbidden_placeholders = {"unknown", "", "n/a", "none", "null"}
    assert str(parent.get("feature_id")).lower() not in forbidden_placeholders or (
        parent.get("feature_id") is None
    ), (
        "feature_id must be the JSON literal null, never a string "
        f"placeholder -- got feature_id={parent.get('feature_id')!r}"
    )
