"""Layer-1 structural presence check for the gate-outcome wired-gate
criterion (gate-outcome-record-seam, slice-06). Reads
`nWave/data/gate-outcome-wired-gates.json` (the wired allowlist) and asserts,
for each named gate, that its module's source genuinely carries the
outcome-recording call the allowlist claims -- mirrors the existing
`tests/des/unit/cli/test_no_duplicate_emit_json_helper.py` precedent:
AST-based, stdlib-only, presence-of-a-shape rather than name-matching.

Explicit scope (feature-delta.md `[REF] Architecture & Contract Tests`):
Layer 1 only -- "this module's source calls the seam", never "this module
calls the seam on every terminating path with the correct outcome". An
allowlist entry means a wiring call exists, not that path-exhaustive
recording is proven. Layer 2/3 (fault-injection, behavioral) is named there
as a deferred BACKLOG follow-up, not built here.

Two wiring SHAPES are recognised, both measured against real code, never
guessed (GDP-8 -- decide on the property, never a designation that matches
only one shape):

  * `call_kwarg` -- the 5 named CLI gates (run-contract-gate, run-slice-ats,
    validate-feature-delta, mode-locus-gate, verify-deliver-entry-contract)
    each call `AtCompletionLedger.append_gate_event(..., outcome=<value>)`
    at their own terminating path.
  * `dict_literal` -- the 4 RM-1 heartbeat-leg families (environmental-e2e,
    fresh-clone, execution-reach, doc-coherence) live inside
    `at_completion_ledger.py` itself and retrofit their existing
    `append_*_verified`/`append_*_not_applicable` methods with an
    `"outcome"` dict-literal key passed to the shared `_append_record`
    writer -- these methods never call `append_gate_event` (measured: zero
    call sites to it anywhere in that module outside its own definition), so
    the `call_kwarg` shape does not apply to them. A literal reading of the
    seam's own criterion sentence ("a call to append_gate_event(...) with an
    outcome= kwarg") would falsely flag this genuinely-wired family; this
    module checks the PROPERTY (an outcome is durably recorded) via the
    shape the code actually uses, not a single hardcoded call pattern.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST_PATH = REPO_ROOT / "nWave" / "data" / "gate-outcome-wired-gates.json"


def _load_allowlist() -> list[dict[str, Any]]:
    payload = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    return payload["wired_gates"]


def _parse(module_path: Path) -> ast.Module:
    return ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))


def _has_append_gate_event_call_with_outcome(tree: ast.AST) -> bool:
    """True iff `tree` contains any Call to `append_gate_event` carrying an
    `outcome=` keyword argument -- anywhere in the given AST, regardless of
    enclosing function (module-wide presence check, per the Layer-1 scope).
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_target = (
            isinstance(func, ast.Attribute) and func.attr == "append_gate_event"
        ) or (isinstance(func, ast.Name) and func.id == "append_gate_event")
        if not is_target:
            continue
        if any(kw.arg == "outcome" for kw in node.keywords):
            return True
    return False


def _function_defs_by_name(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }


def _has_outcome_dict_literal(func: ast.FunctionDef) -> bool:
    """True iff `func`'s body contains a dict literal with a string key
    literally "outcome" -- the RM-1 heartbeat-leg retrofit shape."""
    for node in ast.walk(func):
        if not isinstance(node, ast.Dict):
            continue
        for key in node.keys:
            if isinstance(key, ast.Constant) and key.value == "outcome":
                return True
    return False


def _check_entry(entry: dict[str, Any]) -> str | None:
    """Return None if `entry` is satisfied, else a WHAT/WHY/HOW failure
    string (GDP-3: every failure explains what/why/how)."""
    gate = entry["gate"]
    module_rel = entry["module"]
    module_path = REPO_ROOT / module_rel
    shape = entry["shape"]

    if not module_path.is_file():
        return (
            f"gate {gate!r}: WHAT module {module_rel} does not exist -- "
            f"WHY the allowlist claims a module that is not on disk -- "
            f"HOW fix the module path in {ALLOWLIST_PATH.name} or restore the file"
        )

    tree = _parse(module_path)

    if shape == "call_kwarg":
        if _has_append_gate_event_call_with_outcome(tree):
            return None
        return (
            f"gate {gate!r}: WHAT no call to append_gate_event(..., outcome=...) "
            f"found in {module_rel} -- WHY the allowlist claims this gate is "
            f"wired but its source carries no such call -- HOW add "
            f"AtCompletionLedger.append_gate_event(..., outcome=<GateVerdict>) "
            f"on this gate's terminating path, or remove the allowlist entry "
            f"if the gate is not actually wired"
        )

    if shape == "dict_literal":
        functions = entry.get("functions") or []
        defs = _function_defs_by_name(tree)
        missing_fn = [name for name in functions if name not in defs]
        if missing_fn:
            return (
                f"gate {gate!r}: WHAT function(s) {missing_fn} not found in "
                f"{module_rel} -- WHY the allowlist names a function that "
                f"does not exist in this module -- HOW fix the function "
                f"name(s) in {ALLOWLIST_PATH.name} or restore the function"
            )
        undercovered = [
            name for name in functions if not _has_outcome_dict_literal(defs[name])
        ]
        if undercovered:
            return (
                f"gate {gate!r}: WHAT function(s) {undercovered} in "
                f'{module_rel} carry no "outcome" dict-literal key -- WHY '
                f"the allowlist claims these functions record an explicit "
                f"outcome but their body builds no such key -- HOW add "
                f'`"outcome": GateVerdict.<value>` to the fields dict each '
                f"listed function passes to _append_record"
            )
        return None

    return (
        f"gate {gate!r}: WHAT unknown shape {shape!r} -- WHY only "
        f"'call_kwarg' and 'dict_literal' are recognised checks -- HOW fix "
        f"the 'shape' field in {ALLOWLIST_PATH.name}"
    )


def test_every_wired_gate_calls_the_outcome_recording_seam():
    entries = _load_allowlist()
    assert entries, "the wired-gate allowlist is empty -- nothing to verify"

    failures = [msg for msg in (_check_entry(entry) for entry in entries) if msg]
    assert failures == [], "wired-gate criterion violated:\n" + "\n".join(failures)


def test_allowlist_schema_is_well_formed():
    payload = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    entries = payload["wired_gates"]
    assert isinstance(entries, list) and entries

    seen_gates: set[str] = set()
    for entry in entries:
        for field in ("gate", "module", "shape"):
            assert field in entry, f"entry missing required field {field!r}: {entry}"
        assert entry["shape"] in ("call_kwarg", "dict_literal")
        assert entry["gate"] not in seen_gates, f"duplicate gate name {entry['gate']!r}"
        seen_gates.add(entry["gate"])


def test_the_call_kwarg_guard_can_fail(tmp_path: Path):
    """Prove the call_kwarg check fails for the right reason: a module that
    calls append_gate_event WITHOUT an outcome= kwarg must be flagged, and a
    module that calls it WITH the kwarg must not."""
    unwired = tmp_path / "unwired_gate.py"
    unwired.write_text(
        "def _record(ledger):\n"
        "    ledger.append_gate_event('SomeEvent', '', gate='x')\n",
        encoding="utf-8",
    )
    wired = tmp_path / "wired_gate.py"
    wired.write_text(
        "def _record(ledger, outcome):\n"
        "    ledger.append_gate_event('SomeEvent', '', gate='x', outcome=outcome)\n",
        encoding="utf-8",
    )

    assert not _has_append_gate_event_call_with_outcome(_parse(unwired))
    assert _has_append_gate_event_call_with_outcome(_parse(wired))


def test_the_dict_literal_guard_can_fail(tmp_path: Path):
    """Same proof for the dict_literal check: a function whose fields dict
    carries no "outcome" key must be flagged; one that does must not."""
    module_path = tmp_path / "heartbeat_family.py"
    module_path.write_text(
        "def append_x_verified(self):\n"
        "    return self._append_record({'event': 'XVerified'})\n\n"
        "def append_y_verified(self):\n"
        "    return self._append_record({'event': 'YVerified', 'outcome': 'PASS'})\n",
        encoding="utf-8",
    )
    defs = _function_defs_by_name(_parse(module_path))
    assert not _has_outcome_dict_literal(defs["append_x_verified"])
    assert _has_outcome_dict_literal(defs["append_y_verified"])


def test_missing_module_is_reported_not_silently_passed():
    fake_entry = {
        "gate": "phantom-gate",
        "module": "src/des/cli/this_module_does_not_exist.py",
        "shape": "call_kwarg",
        "functions": None,
    }
    failure = _check_entry(fake_entry)
    assert failure is not None
    assert "phantom-gate" in failure
    assert "does not exist" in failure


def test_missing_function_is_reported_not_silently_passed():
    fake_entry = {
        "gate": "phantom-family",
        "module": "src/des/adapters/driven/logging/at_completion_ledger.py",
        "shape": "dict_literal",
        "functions": ["this_function_does_not_exist"],
    }
    failure = _check_entry(fake_entry)
    assert failure is not None
    assert "phantom-family" in failure
    assert "not found" in failure


def test_undercovered_function_is_reported_not_silently_passed():
    """A function that exists but whose body has no "outcome" dict key must
    be flagged, not silently accepted -- pick a real, unrelated method known
    to build a fields dict with no "outcome" key (append_full_suite_leg_ran)."""
    fake_entry = {
        "gate": "phantom-uncovered",
        "module": "src/des/adapters/driven/logging/at_completion_ledger.py",
        "shape": "dict_literal",
        "functions": ["append_full_suite_leg_ran"],
    }
    failure = _check_entry(fake_entry)
    assert failure is not None
    assert "phantom-uncovered" in failure
    assert "outcome" in failure
