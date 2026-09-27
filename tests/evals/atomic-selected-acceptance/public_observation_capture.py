"""Public-observation capture producer (v1 packet writer).

Maps caller-selected raw public calls to a `nwave.public_observations` v1 packet.
It selects only the seqs the caller names; it never runs DES or a native command,
never judges a trace and synthesizes no product behavior. The grammar owner
`des.domain.public_observations.read_packet` self-checks the written packet.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


PRODUCER = {"id": "atomic-selected-acceptance-capture", "version": "1"}
SUBSTRATES = ("installed_host", "source_tree", "mock_provider")
RAW_KEYS = (
    "seq",
    "argv_repo_root_normalised",
    "stdin_present",
    "exit",
    "stdout",
    "stderr",
    "handover_before",
    "handover_after",
)


class CaptureRefused(ValueError):
    """WHAT/WHY/HOW refusal; the message is the whole explanation."""


def refuse(what: str, why: str, how: str) -> CaptureRefused:
    return CaptureRefused(f"WHAT: {what}\nWHY: {why}\nHOW: {how}")


def _scrub(value, replacements):
    if isinstance(value, str):
        for old, new in replacements:
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [_scrub(v, replacements) for v in value]
    if isinstance(value, dict):
        return {
            _scrub(k, replacements): _scrub(v, replacements) for k, v in value.items()
        }
    return value


class _States:
    def __init__(self) -> None:
        self.by_text: dict[str, str] = {}
        self.values: dict[str, object] = {}

    def ref(self, value):
        if value is None:
            return None
        text = json.dumps(value, sort_keys=True)
        if text not in self.by_text:
            key = f"S{len(self.by_text) + 1}"
            self.by_text[text] = key
            self.values[key] = value
        return self.by_text[text]


def _count(files, seq: int, side: str):
    if not isinstance(files, dict) or len(files) != 1:
        raise refuse(
            f"seq {seq} {side} counter is not one declared file",
            "the counter must be exactly one declared invocation file",
            "select records whose declared counter names one file",
        )
    (content,) = files.values()
    if not isinstance(content, str) or set(content) - {"1"}:
        raise refuse(
            f"seq {seq} {side} counter content is not invocation marks",
            "one '1' mark per declared invocation is the only readable count",
            "select records from a capture that wrote marks",
        )
    return len(content)


def _stdin(row, states: _States, replacements):
    if not row["stdin_present"]:
        return None
    text = row.get("stdin")
    if not isinstance(text, str):
        raise refuse(
            f"seq {row['seq']} declares stdin but carries none",
            "stdin_present is true without the stdin text",
            "recapture the call with its stdin",
        )
    try:
        value = json.loads(text)
    except ValueError:
        value = text
    return states.ref(_scrub(value, replacements))


def build_packet(
    rows, selection, candidate: str, tree: str, repo_root: str = ""
) -> dict:
    """Pure mapping of selected raw rows to a v1 packet (no self-check here)."""
    if (
        not isinstance(selection, dict)
        or set(selection) != {"scenarios"}
        or not isinstance(selection["scenarios"], list)
    ):
        raise refuse(
            'selection must be exactly {"scenarios": [...]}',
            "the caller owns selection and its shape is closed",
            "list scenarios as {id, substrate, purpose, seqs}",
        )
    by_seq = {}
    for row in rows:
        by_seq.setdefault(row.get("seq"), []).append(row)
    replacements = [(repo_root, "<repo>")] if repo_root else []
    states = _States()
    scenarios = []
    for entry in selection["scenarios"]:
        if not isinstance(entry, dict) or set(entry) != {
            "id",
            "substrate",
            "purpose",
            "seqs",
        }:
            raise refuse(
                "selection scenario has wrong keys",
                "each scenario is exactly id, substrate, purpose, seqs",
                "fix the selection entry",
            )
        seqs = entry["seqs"]
        if (
            not isinstance(seqs, list)
            or not seqs
            or any(type(s) is not int for s in seqs)
            or seqs != sorted(set(seqs))
        ):
            raise refuse(
                f"scenario {entry['id']!r} seqs are not strictly increasing integers",
                "original global seqs (gaps allowed) are kept in order",
                "list distinct raw seqs ascending",
            )
        events = []
        for seq in seqs:
            found = by_seq.get(seq, [])
            if len(found) != 1:
                raise refuse(
                    f"seq {seq} matches {len(found)} raw records",
                    "each selected seq must name exactly one record",
                    "select a seq present once in the raw calls",
                )
            row = found[0]
            missing = [k for k in RAW_KEYS if k not in row]
            if missing:
                raise refuse(
                    f"seq {seq} lacks {missing}",
                    "only public call records can be mapped",
                    "select public call records",
                )
            counter = None
            counter_before = row.get("declared_counter_before")
            counter_after = row.get("declared_counter_after")
            sides = [
                ("declared_counter_before", counter_before),
                ("declared_counter_after", counter_after),
            ]
            declared_sides = [(name, files) for name, files in sides if files]
            if declared_sides:
                if len(declared_sides) != 2:
                    raise refuse(
                        f"seq {seq} declares only one counter side",
                        "a counter needs both before and after",
                        "select records that carry both declared counter sides",
                    )
                counter = {
                    "before": _count(counter_before, seq, "before"),
                    "after": _count(counter_after, seq, "after"),
                }
            events.append(
                {
                    "seq": seq,
                    "stimulus": {
                        "argv": _scrub(row["argv_repo_root_normalised"], replacements),
                        "stdin": _stdin(row, states, replacements),
                    },
                    "response": {
                        "exit": row["exit"],
                        "stdout": _scrub(row["stdout"], replacements),
                        "stderr": _scrub(row["stderr"], replacements),
                    },
                    "state": {
                        "before": states.ref(
                            _scrub(row["handover_before"], replacements)
                        ),
                        "after": states.ref(
                            _scrub(row["handover_after"], replacements)
                        ),
                    },
                    "counter": counter,
                }
            )
        scenarios.append(
            {
                "id": entry["id"],
                "substrate": entry["substrate"],
                "purpose": entry["purpose"],
                "events": events,
            }
        )
    return {
        "schema": "nwave.public_observations",
        "version": 1,
        "candidate_sha": candidate,
        "candidate_tree_sha": tree,
        "producer": dict(PRODUCER),
        "states": states.values,
        "scenarios": scenarios,
    }


def _load_rows(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


@dataclass(frozen=True)
class _SelfCheckBinding:
    """The candidate tree and owned-path facts a written packet is checked against."""

    candidate: str
    tree: str
    owned: list[str]


def _write_checked(
    packet: dict,
    output: Path,
    binding: _SelfCheckBinding,
    read_packet,
    refused,
) -> None:
    """Write beside OUTPUT, self-check with the grammar owner, publish only on success."""
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=output.parent, prefix=".packet-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(packet, stream, ensure_ascii=False)
        try:
            read_packet(Path(temp), binding.candidate, binding.tree, binding.owned)
        except refused as error:
            raise refuse(
                "capture packet failed its self-check",
                "; ".join(f"{d.pointer} [{d.code}] {d.detail}" for d in error.defects)
                or "no defects reported",
                "select fewer events (seq gaps are allowed, cap 65536 bytes) or fix the named defect; no packet was written",
            ) from error
        Path(temp).replace(output)
    finally:
        temporary = Path(temp)
        if temporary.exists():
            temporary.unlink()


def _des(repo: Path):
    sys.path.insert(0, str(repo / "src"))
    from des.application.delivery_continuation import DeliveryContinuationRunner
    from des.application.delivery_steps import _prepared
    from des.application.handover import stored_handover
    from des.domain.public_observations import ObservationPacketRefused, read_packet

    return (
        DeliveryContinuationRunner,
        _prepared,
        stored_handover,
        ObservationPacketRefused,
        read_packet,
    )


def produce(
    root: Path, candidate: str, calls: Path, selection: Path, output: Path
) -> None:
    runner_type, prepared_of, stored_handover, refused, read_packet = _des(
        Path(__file__).resolve().parents[3]
    )
    stored = stored_handover(root)
    if stored is None or not hasattr(stored, "request"):
        raise refuse(
            "handover unavailable",
            "the owned-path population comes from the stored handover",
            "run from a prepared repository",
        )
    runner = runner_type()
    prepared = prepared_of(runner, root, stored)
    if not isinstance(prepared, list):
        raise refuse(
            "selected revision unavailable",
            "the owned-path population needs prepared values",
            "repair the selected revision",
        )
    tree = runner._git(root, "rev-parse", f"{candidate}^{{tree}}")
    if tree.returncode:
        raise refuse(
            "candidate tree unavailable",
            "the packet binds the candidate tree",
            "pass an existing candidate SHA",
        )
    owned = runner._request_owned_paths(prepared)
    packet = build_packet(
        _load_rows(calls),
        json.loads(selection.read_text(encoding="utf-8")),
        candidate,
        tree.stdout.strip(),
        str(root),
    )
    _write_checked(
        packet,
        output,
        _SelfCheckBinding(candidate=candidate, tree=tree.stdout.strip(), owned=owned),
        read_packet,
        refused,
    )


def self_test() -> None:
    """Deterministic offline control: mapping, interning, gaps, refusal writes nothing."""
    *_, refused, read_packet = _des(Path(__file__).resolve().parents[3])
    row = {
        "seq": 5,
        "argv_repo_root_normalised": ["des", "state", "--repo-root", "<repo>"],
        "stdin_present": True,
        "stdin": '{"a": 1}',
        "exit": 0,
        "stdout": "ok /r/x",
        "stderr": "",
        "handover_before": {"h": 1},
        "handover_after": {"h": 1},
        "declared_counter_before": {"c": ""},
        "declared_counter_after": {"c": "1"},
    }
    rows = [row, {**row, "seq": 9}]
    sel = {
        "scenarios": [
            {
                "id": "T1",
                "substrate": "mock_provider",
                "purpose": "self test",
                "seqs": [5, 9],
            }
        ]
    }
    sha = "a" * 40
    packet = build_packet(rows, sel, sha, "b" * 40, "/r")
    assert [e["seq"] for e in packet["scenarios"][0]["events"]] == [5, 9], "gap lost"
    assert len(packet["states"]) == 2, "equal snapshots not interned"
    assert packet["scenarios"][0]["events"][0]["response"]["stdout"] == "ok <repo>/x"
    assert packet["scenarios"][0]["events"][0]["counter"] == {"before": 0, "after": 1}
    empty_counter = dict(row)
    empty_counter["declared_counter_before"] = {}
    empty_counter["declared_counter_after"] = {}
    empty_packet = build_packet(
        [empty_counter],
        {"scenarios": [{**sel["scenarios"][0], "seqs": [5]}]},
        sha,
        "b" * 40,
        "/r",
    )
    assert empty_packet["scenarios"][0]["events"][0]["counter"] is None, (
        "empty recorder maps mean no declared native counter, not a malformed counter"
    )
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "ok.json"
        _write_checked(
            packet,
            good,
            _SelfCheckBinding(candidate=sha, tree="b" * 40, owned=["src/owned.py"]),
            read_packet,
            refused,
        )
        bad = Path(tmp) / "bad.json"
        broken_binding = _SelfCheckBinding(
            candidate=sha, tree="b" * 40, owned=["<repo>"]
        )
        try:
            _write_checked(packet, bad, broken_binding, read_packet, refused)
        except CaptureRefused:
            assert not bad.exists(), "unusable packet was published"
        else:
            raise AssertionError("path-bearing packet was accepted")
        try:
            _write_checked(packet, bad, broken_binding, read_packet, refused)
        except CaptureRefused as error:
            assert "[" in str(error) and "observation packet refused" not in str(
                error
            ), "defects hidden"
    for name, mutate in (
        ("one side", lambda r: r.pop("declared_counter_after")),
        ("empty side", lambda r: r.update(declared_counter_after={})),
        ("two files", lambda r: r.update(declared_counter_after={"a": "1", "b": "1"})),
        ("bad marks", lambda r: r.update(declared_counter_after={"c": "2"})),
    ):
        broken = dict(row)
        mutate(broken)
        try:
            build_packet(
                [broken],
                {
                    "scenarios": [
                        {
                            "id": "T",
                            "substrate": "mock_provider",
                            "purpose": "p",
                            "seqs": [5],
                        }
                    ]
                },
                sha,
                "b" * 40,
            )
        except CaptureRefused:
            continue
        raise AssertionError(f"partial counter accepted: {name}")
    print("self-test ok")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Write a caller-selected public_observations v1 packet; runs no DES or native command."
    )
    parser.add_argument("--self-test", action="store_true")
    for name in ("repo-root", "candidate", "calls-jsonl", "selection-json", "output"):
        parser.add_argument(f"--{name}")
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            self_test()
            return 0
        if not all(
            (
                args.repo_root,
                args.candidate,
                args.calls_jsonl,
                args.selection_json,
                args.output,
            )
        ):
            parser.error(
                "--repo-root --candidate --calls-jsonl --selection-json --output are required"
            )
        produce(
            Path(args.repo_root).resolve(),
            args.candidate,
            Path(args.calls_jsonl),
            Path(args.selection_json),
            Path(args.output),
        )
    except CaptureRefused as error:
        print(error, file=sys.stderr)
        return 1
    print(f"packet written: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
