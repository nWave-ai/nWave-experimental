"""Trustworthy diagnostics and provenance through the real DES CLI.

@contract-shape: real-io

The host may record ``_drive`` / ``run_cli_in_process`` for complete terminal
streams and ``PUBLIC-STATE`` for actual candidate, receipt and child observations.
Those streams are source-tree/mock-provider observations, not installed-release
evidence. Source-blind packets must replace incidental paths consistently rather
than substitute summaries for the observed environment or terminal response.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_cli_in_process
from tests.des._helpers.host_facts import design_manifest, product_manifest
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    PACKAGE_PARENT,
    block,
    git,
)


REQUEST = "fix the broken feature and add a capability described by this Request"
OBSERVATION = "the installed command observably reports the recorded public answer"
ORACLE = "tests/acceptance/test_answer.py"
TARGET = "answer.txt"
FEATURE = "trustworthy-diagnostics"
OTHER_RECORDED_TYPES = (
    "feat",
    "docs",
    "style",
    "refactor",
    "perf",
    "build",
    "ci",
    "chore",
    "revert",
)
NOT_APPLICABLE = {
    "applicability": "not_applicable",
    "reason": "This fixture changes no additional boundary or preserving move.",
}
ENVIRONMENT_NAMES = (
    "PATH",
    "INVOCATION_ID",
    "PYTHONDONTWRITEBYTECODE",
    "PYTHONPATH",
    "PYTEST_ADDOPTS",
    "NWAVE_PROBE_SELECTOR",
)
CHILD_CAPTURE = (
    "import json, os, shutil, sys\n"
    f"names = {ENVIRONMENT_NAMES!r}\n"
    "seen = ({name: value for name, value in os.environ.items()\n"
    "         if name not in {'DEPLOY_TOKEN', 'CC'}}\n"
    "        if 'NWAVE_PROBE_SELECTOR' in os.environ and 'pytest' not in sys.modules else\n"
    "        {name: os.environ[name] for name in names if name in os.environ})\n"
    'print("CHILD-ENVIRONMENT: " + json.dumps(seen, sort_keys=True))\n'
    "executable = shutil.which('python')\n"
    'print("CHILD-EXECUTABLE: " + json.dumps({\n'
    "    'path': executable,\n"
    "    'exists': executable is not None and os.path.isfile(executable),\n"
    "    'executable': executable is not None and os.access(executable, os.X_OK),\n"
    "}, sort_keys=True))\n"
)


@pytest.fixture(autouse=True)
def no_inherited_pytest_probe(monkeypatch):
    # DES owns each child's new probe. An outer DES verification's probe must
    # not be inherited by another pytest session in this regression oracle.
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)


def _message(what: str, why: str, how: str, actual=None) -> str:
    return f"WHAT: {what}; actual={actual!r}. WHY: {why}. HOW: {how}."


def _public_state(**state) -> None:
    print("PUBLIC-STATE: " + json.dumps(state, sort_keys=True))


def _drive(step, *argv: str, **kwargs):
    result = step(*argv, **kwargs)
    print(result[1], end="")
    print(result[2], end="", file=sys.stderr)
    return result


def _success(result, action: str) -> dict[str, str]:
    code, out, err = result
    assert code == 0, _message(
        f"{action} did not complete through its public command",
        "the promised observation requires this admitted public state",
        f"make {action} accept the declared inputs and return Success",
        out + err,
    )
    return block(out, err)


def _manifest(changes=(None,)) -> dict:
    observations = [
        OBSERVATION if index == 0 else f"{OBSERVATION} for dependent value {index + 1}"
        for index in range(len(changes))
    ]
    manifest = product_manifest(REQUEST, observations)
    for value, change in zip(manifest["values"], changes, strict=True):
        if change is not None:
            value["change"] = dict(change)
    return manifest


def _product(root, step, manifest=None, *flags):
    manifest = _manifest() if manifest is None else manifest
    result = _drive(
        step,
        "po",
        "--repo-root",
        str(root),
        "--feature",
        FEATURE,
        *flags,
        "--input",
        "-",
        stdin=json.dumps(manifest),
    )
    return result, manifest


def _design(  # noqa: PLR0913 - independent public DESIGN fixture inputs
    root,
    step,
    *,
    target=TARGET,
    verification=None,
    prefactoring=None,
    observations=(OBSERVATION,),
):
    facts = {
        "targets": [{"path": target, "decision": "CREATE_NEW"}],
        "paradigm": "procedural",
        "decisions": ["Observe only the declared public answer."],
        "oracle": ORACLE,
        "acceptance_supports": [],
        "verification": verification
        or [["python", "-m", "pytest", "-q", "-s", ORACLE]],
        "oracle_verification_index": 0,
        "architectural_tests": NOT_APPLICABLE,
        "contract_tests": NOT_APPLICABLE,
        "agreement_analysis": NOT_APPLICABLE,
        "prefactoring": prefactoring or NOT_APPLICABLE,
    }
    if prefactoring is not None:
        facts["targets"][0]["decision"] = "EXTEND"
        facts["oracle"] = "oracle.sh"
    # One value binds its own facts. A dependency-related batch shares one
    # decision set: the shared DESIGN defines each fact once and every value
    # references those definitions instead of redefining them.
    manifest = design_manifest(facts, observations[0], 1)
    if len(observations) > 1:
        shared = design_manifest(facts, observations[0], 0)
        _success(
            _drive(
                step,
                "design",
                "--repo-root",
                str(root),
                "--shared",
                "--input",
                "-",
                stdin=json.dumps(shared),
            ),
            "shared design",
        )
        manifest = dict(shared, facts=[])
    for position in range(1, len(observations) + 1):
        _success(
            _drive(
                step,
                "design",
                "--repo-root",
                str(root),
                "--value",
                str(position),
                "--input",
                "-",
                stdin=json.dumps(manifest),
            ),
            "design",
        )


def _answer_oracle(target: str) -> str:
    return (
        "from pathlib import Path\n" + CHILD_CAPTURE + "\n\ndef test_public_answer():\n"
        "    root = Path(__file__).resolve().parents[2]\n"
        f"    answer = root / {target!r}\n"
        "    actual = answer.read_text() if answer.exists() else None\n"
        "    assert actual == 'forty-two\\n', (\n"
        "        'WHAT: public answer is not forty-two; actual=' + repr(actual) + "
        "'. WHY: the recorded value promises that answer. "
        "HOW: publish forty-two through the declared answer surface.'\n"
        "    )\n"
    )


def _craft(root, step, *, changes=(None,), target=TARGET, verification=None):
    baseline = git(root, "rev-parse", "HEAD")
    result, manifest = _product(root, step, _manifest(changes))
    product = _success(result, "po optional recorded change intent")
    observations = tuple(value["observation"] for value in manifest["values"])
    _design(
        root, step, target=target, verification=verification, observations=observations
    )
    path = root / ORACLE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_answer_oracle(target), encoding="utf-8")
    for position in range(1, len(observations) + 1):
        _success(
            _drive(
                step,
                "oracle",
                "--repo-root",
                str(root),
                "--value",
                str(position),
                "--baseline",
                baseline,
                "--input",
                "-",
                stdin=json.dumps(
                    {
                        "structured_output": {
                            "outcome": "accepted",
                            "diagnostic": "The public answer is falsifiable.",
                        }
                    }
                ),
            ),
            "oracle",
        )
    answer = root / target
    answer.parent.mkdir(parents=True, exist_ok=True)
    answer.write_text("forty-two\n", encoding="utf-8")
    for position in range(1, len(observations) + 1):
        _success(
            _drive(
                step,
                "craft",
                "--repo-root",
                str(root),
                "--value",
                str(position),
                "--input",
                "-",
                stdin=json.dumps(
                    {
                        "structured_output": {
                            "outcome": "accepted",
                            "diagnostic": "Published the recorded answer.",
                            "blocked_by": None,
                        }
                    }
                ),
            ),
            "craft",
        )
    return root / product["DOCUMENT"], manifest


def _verify(root, step):
    result = _drive(step, "verify", "--repo-root", str(root))
    lines = _success(result, "verify")
    candidate = lines.get("CANDIDATE", "")
    assert re.fullmatch(r"[0-9a-f]{40}", candidate), _message(
        "verify did not identify its candidate",
        "the subject needs an actual Git commit",
        "emit the constructed CANDIDATE identity",
        lines,
    )
    return candidate, lines


def _restart_verify(root, directory):
    environment = _native_environment(directory) | {
        "PYTHONPATH": str(PACKAGE_PARENT),
    }
    command = [sys.executable, "-m", "des.cli", "verify", "--repo-root", str(root)]
    completed = subprocess.run(
        command,
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        timeout=120,
    )
    print(completed.stdout, end="")
    print(completed.stderr, end="", file=sys.stderr)
    lines = _success(
        (completed.returncode, completed.stdout, completed.stderr),
        "fresh-process verify from persisted product authority",
    )
    return lines["CANDIDATE"], lines


def _assert_field_diagnostic(result, code, unexpected, missing):
    status, out, err = result
    lines = block(out, err)
    _public_state(diagnostic=lines)
    assert status != 0 and lines.get("DELIVERY-OUTCOME") == "Refusal", _message(
        "malformed structured output was not refused",
        "closed envelopes must not be admitted",
        "return Refusal before recording or executing the malformed result",
        lines,
    )
    assert lines.get("WHAT") == code, _message(
        "the machine diagnostic code changed",
        "existing consumers bind this WHAT code",
        f"retain WHAT {code} and put field details in WHY and HOW",
        lines,
    )
    why, how = lines.get("WHY", ""), lines.get("HOW", "")
    assert "ModelOutcomeMalformed" in why, _message(
        "the diagnostic lost the envelope failure",
        "users need the causal diagnostic",
        "retain the ModelOutcomeMalformed diagnostic in WHY",
        why,
    )
    for label, names in (("unexpected", unexpected), ("missing", missing)):
        rendered = ", ".join(names) if names else "none"
        assert f"{label} fields [{rendered}]" in why, _message(
            f"WHY does not name the exact {label} fields",
            "users cannot repair an unnamed mismatch",
            f"render sorted {label} fields [{rendered}] in WHY",
            why,
        )
        for name in names:
            verb = "remove" if label == "unexpected" else "supply"
            assert re.search(rf"{verb}[^;]*\b{re.escape(name)}\b", how, re.I), _message(
                f"HOW does not say to {verb} {name}",
                "field names without an action are not actionable",
                f"carry the decoder's structured HOW directing the caller to {verb} {name}",
                how,
            )
    assert "structured_output" in how, _message(
        "HOW does not identify the result to resubmit",
        "repair needs the complete structured envelope",
        "direct the caller to resubmit the complete structured_output",
        how,
    )


@pytest.mark.parametrize(
    ("payload", "unexpected", "missing"),
    [
        ({"outcome": "accepted", "verdict": "green"}, ("verdict",), ("diagnostic",)),
        (
            {"outcome": "accepted", "diagnostic": "supplied", "verdict": "green"},
            ("verdict",),
            (),
        ),
        ({"outcome": "accepted"}, (), ("diagnostic",)),
        (
            {"z_extra": 1, "a_extra": 2},
            ("a_extra", "z_extra"),
            ("diagnostic", "outcome"),
        ),
    ],
    ids=[
        "unexpected-and-missing",
        "unexpected-only",
        "missing-only",
        "all-fields-sorted",
    ],
)
def test_malformed_host_result_names_every_field_and_its_repair(
    root,
    step,
    payload,
    unexpected,
    missing,
):
    _success(_product(root, step)[0], "po")
    _design(root, step)
    _assert_field_diagnostic(
        _drive(
            step,
            "oracle",
            "--repo-root",
            str(root),
            "--value",
            "1",
            "--input",
            "-",
            stdin=json.dumps({"structured_output": payload}),
        ),
        "HostResultMalformed",
        unexpected,
        missing,
    )


def test_charter_result_keeps_its_code_and_names_the_envelope_repair(root, step):
    _success(_product(root, step)[0], "po")
    _assert_field_diagnostic(
        _drive(
            step,
            "po",
            "--repo-root",
            str(root),
            "--feature",
            FEATURE,
            "--charter",
            "--value",
            "1",
            "--input",
            "-",
            stdin=json.dumps(
                {
                    "schema_version": 1,
                    "intent": "Observe trustworthy public diagnostics.",
                    "observation": OBSERVATION,
                    "public_start_recipe": "Invoke the public command in the prepared checkout.",
                    "structured_output": {"outcome": "accepted", "verdict": "green"},
                }
            ),
        ),
        "CharterResultMalformed",
        ("verdict",),
        ("charter", "diagnostic"),
    )


def test_recorded_role_result_keeps_its_code_and_names_the_envelope_repair(root, step):
    _craft(root, step)
    candidate, _ = _verify(root, step)
    prepared = _success(
        _drive(
            step,
            "prepare-role",
            "--repo-root",
            str(root),
            "--role",
            "reviewer",
            "--candidate",
            candidate,
        ),
        "prepare-role",
    )
    _assert_field_diagnostic(
        _drive(
            step,
            "record-role-result",
            "--repo-root",
            str(root),
            "--role",
            "reviewer",
            "--candidate",
            candidate,
            "--provider",
            "claude",
            "--model",
            "host-selected",
            "--session-id",
            "malformed-role-result",
            "--prepared-input",
            prepared["INPUT"],
            "--input",
            "-",
            stdin=json.dumps(
                {"structured_output": {"outcome": "accepted", "verdict": "green"}}
            ),
        ),
        "RoleResultMalformed",
        ("verdict",),
        ("diagnostic",),
    )


@pytest.mark.parametrize(
    "case",
    [
        (
            ({"type": "fix", "description": "repair the reported value"},),
            TARGET,
            "fix",
            "repair the reported value",
            False,
        ),
        (
            (
                {
                    "type": "test",
                    "description": "repair the reported regression examples",
                },
            ),
            "tests/recorded_answer.txt",
            "test",
            "repair the reported regression examples",
            False,
        ),
        *[
            (
                ({"type": kind, "description": "repair the reported value"},),
                TARGET,
                kind,
                "repair the reported value",
                False,
            )
            for kind in OTHER_RECORDED_TYPES
        ],
        ((None,), TARGET, "chore", OBSERVATION, True),
        (
            (None, {"type": "docs", "description": "describe the repaired behavior"}),
            TARGET,
            "docs",
            "describe the repaired behavior",
            True,
        ),
        (
            (
                {"type": "test", "description": "repair the recorded examples"},
                {"type": "fix", "description": "add the requested capability"},
            ),
            TARGET,
            "test",
            "repair the recorded examples",
            False,
        ),
    ],
    ids=[
        "recorded-repair",
        "test-only-intent",
        *[f"recorded-{kind}" for kind in OTHER_RECORDED_TYPES],
        "legacy-unrecorded",
        "first-recorded-after-unrecorded",
        "canonical-first-not-prose",
    ],
)
def test_candidate_subject_uses_recorded_authority_across_restart(
    root,
    step,
    tmp_path,
    case,
):
    changes, target, kind, description, unrecorded = case
    product, _ = _craft(root, step, changes=changes, target=target)
    raw = (root / ".nwave/des/handover.json").read_bytes()
    stored = json.loads(raw)
    actual_changes = [value.get("change") for value in stored["values"]]
    _public_state(recorded_changes=actual_changes)
    assert actual_changes == list(changes), _message(
        "persisted values lost or invented a change intent",
        "verify restarts from these producer bytes",
        "round-trip each optional typed intent without adding a member for unrecorded values",
        actual_changes,
    )
    text = product.read_text(encoding="utf-8")
    if any(change is not None for change in changes):
        for change in changes:
            if change is not None:
                assert change["type"] in text and change["description"] in text, (
                    _message(
                        "the brief omits its recorded intent",
                        "brief and restart authority must agree",
                        "publish the recorded type and description in the Change intent table",
                        text,
                    )
                )
    else:
        assert all("change" not in value for value in stored["values"]), _message(
            "legacy producer bytes gained a change member",
            "old wire projections must remain unchanged",
            "omit absent change members rather than writing null",
            stored["values"],
        )
        assert "## Change intent" not in text, _message(
            "an unrecorded brief gained a change table",
            "legacy authority bytes must remain compatible",
            "render the table only when at least one value records intent",
            text,
        )
    candidate, _ = _restart_verify(root, tmp_path / "restart-bin")
    subject = git(root, "log", "-1", "--format=%s", candidate)
    body = git(root, "log", "-1", "--format=%b", candidate)
    _public_state(candidate_subject=subject, candidate_body=body)
    match = re.fullmatch(r"([a-z]+)(?:\([^()\n]+\))?: (.+)", subject)
    assert match is not None and match.group(1) == kind, _message(
        "candidate conventional type does not match recorded authority",
        "Request prose must not classify release impact",
        f"compose type {kind} from the first recorded intent, or chore when unrecorded",
        subject,
    )
    actual_description = match.group(2)
    assert actual_description == description, _message(
        "candidate subject does not describe the recorded change",
        "the Request is not a change description",
        "use the complete recorded description or first admitted observation within the subject budget",
        subject,
    )
    assert REQUEST not in subject, _message(
        "candidate subject repeats the Request",
        "subject provenance belongs to admitted value authority",
        "remove the Request from subject composition",
        subject,
    )
    assert ("change-intent unrecorded" in body.splitlines()) == unrecorded, _message(
        "candidate body misstates whether intent was recorded",
        "legacy or mixed batches must be explicit",
        "emit the unrecorded identity line exactly when any admitted value lacks intent",
        body,
    )
    assert (root / ".nwave/des/handover.json").read_bytes() == raw, _message(
        "verification mutated the persisted product facts",
        "a restart reader must preserve producer bytes",
        "consume the handover without rewriting its optional change facts",
    )


@pytest.mark.parametrize(
    ("change", "fields"),
    [
        (
            {"type": "fix", "description": "", "surprise": True},
            ("description", "surprise"),
        ),
        ({"type": "feature", "description": "repair the value"}, ("type",)),
        ({"type": "fix", "description": "repair\nthe value"}, ("description",)),
        ({"type": "fix", "description": "123 repair"}, ("description",)),
        ({"description": "repair the value"}, ("type",)),
        ({"type": "fix"}, ("description",)),
    ],
    ids=[
        "all-independent-defects",
        "unknown-type",
        "multiple-lines",
        "non-letter-initial",
        "missing-type",
        "missing-description",
    ],
)
def test_invalid_recorded_intent_names_all_defects_without_publishing(
    root, step, change, fields
):
    before = _owned_bytes(root)
    result, _ = _product(root, step, _manifest((change,)))
    lines = block(result[1], result[2])
    assert result[0] != 0 and lines.get("WHAT") == "InvalidDiscussDocument", _message(
        "malformed change intent was not refused",
        "a typed authority must be admissible before publication",
        "validate the optional closed change object through des po",
        lines,
    )
    for field in fields:
        assert f"values[0].change.{field}" in result[1] + result[2], _message(
            f"the change defect {field} was omitted",
            "independent defects must be repaired in one turn",
            "name every invalid change member in InvalidDiscussDocument",
            lines,
        )
    assert _owned_bytes(root) == before, _message(
        "invalid intent published authority or handover bytes",
        "refusal must preserve the admitted state",
        "collect defects before writing the brief, config or handover",
    )


def _owned_bytes(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for directory in (root / "docs", root / ".nwave")
        if directory.exists()
        for path in directory.rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    }


def test_changed_intent_requires_explicit_replacement_and_preserves_authority(
    root, step
):
    original = _manifest(({"type": "fix", "description": "repair the reported value"},))
    product = _success(_product(root, step, original)[0], "po recorded intent")
    before = _owned_bytes(root)
    changed = _manifest(
        ({"type": "test", "description": "repair the regression examples"},)
    )
    result, _ = _product(root, step, changed)
    lines = block(result[1], result[2])
    assert result[0] != 0 and lines.get("WHAT") == "DiscussHandoverConflict", _message(
        "a different intent silently replaced bound authority",
        "brief and handover must never disagree",
        "compare observation, dependencies and change and require --replace-current",
        lines,
    )
    assert _owned_bytes(root) == before, _message(
        "intent conflict changed persisted bytes",
        "a rejected resubmission preserves the existing authority",
        "refuse before publishing either projection",
    )
    git(root, "add", "--", product["DOCUMENT"])
    git(root, "commit", "-qm", "Record product authority")
    _success(
        _product(root, step, changed, "--replace-current")[0],
        "po explicit intent replacement",
    )
    stored = json.loads((root / ".nwave/des/handover.json").read_text())
    assert stored["values"][0].get("change") == changed["values"][0]["change"], (
        _message(
            "explicit replacement did not carry the new intent",
            "intent is part of the replaced product fact",
            "retain supplied change during bound-fact reconciliation",
            stored["values"][0],
        )
    )


@pytest.mark.parametrize(
    ("change", "defect"),
    [
        ({"type": "not-conventional", "description": "repair the value"}, "type"),
        ({"type": "fix", "description": ""}, "description"),
    ],
    ids=["persisted-type", "persisted-description"],
)
def test_malformed_persisted_intent_is_not_consumed_as_valid_authority(
    root, step, change, defect
):
    _craft(root, step)
    path = root / ".nwave/des/handover.json"
    stored = json.loads(path.read_bytes())
    stored["values"][0]["change"] = change
    raw = json.dumps(stored).encode()
    path.write_bytes(raw)
    result = _drive(step, "verify", "--repo-root", str(root))
    lines = block(result[1], result[2])
    assert result[0] != 0 and lines.get("WHAT") == "HandoverMalformed", _message(
        "invalid persisted change intent was consumed",
        "restart readers cannot trust malformed authority",
        "validate persisted type and description and return HandoverMalformed",
        lines,
    )
    assert lines.get("DELIVERY-OUTCOME") == "Indeterminate" and "change" in lines.get(
        "WHY", ""
    ), _message(
        "persisted intent failure lost its provenance",
        "the host must know which restart fact is broken",
        "report Indeterminate naming the change defect",
        lines,
    )
    assert defect in lines.get("WHY", ""), _message(
        f"persisted intent diagnostic omits its {defect} defect",
        "an unqualified change failure does not identify the broken input",
        f"name the inadmissible persisted change.{defect} in WHY",
        lines,
    )
    how = lines.get("HOW", "").lower()
    re_elicitation = (
        "delete" in how
        and ".nwave/des/handover.json" in how
        and "re-elicit" in how
        and "durable authorities" in how
    )
    assert re_elicitation or any(word in how for word in ("restore", "replace")), (
        _message(
            "persisted intent failure has no concrete recovery instruction",
            "unreadable authority requires repair without inventing a new recovery flow",
            "name restoration, replacement, or deletion of the handover followed by "
            "re-elicitation from its durable authorities in HOW",
            lines,
        )
    )
    assert path.read_bytes() == raw, _message(
        "verification rewrote malformed authority",
        "the reader must not silently repair admitted facts",
        "leave the supplied bytes unchanged on HandoverMalformed",
    )


def test_repository_type_vocabulary_can_refuse_the_unrecorded_fallback(root, step):
    (root / ".gitlint").write_text(
        "[general]\ncontrib = contrib-title-conventional-commits\n"
        "[contrib-title-conventional-commits]\ntypes = feat\n",
        encoding="utf-8",
    )
    git(root, "add", "--", ".gitlint")
    git(root, "commit", "-qm", "feat: record repository vocabulary")
    _craft(root, step)
    result = _drive(step, "verify", "--repo-root", str(root))
    lines = block(result[1], result[2])
    assert result[0] != 0 and lines.get("WHAT") == "IntegrationMessageNonConforming", (
        _message(
            "an excluded fallback type produced a candidate",
            "recorded repository vocabulary remains binding",
            "refuse the chore fallback when .gitlint admits only feat",
            lines,
        )
    )
    assert lines.get("DELIVERY-OUTCOME") == "Indeterminate" and ".gitlint" in lines.get(
        "HOW", ""
    ), _message(
        "the repository-rule refusal is not actionable",
        "the maintainer owns its narrowed vocabulary",
        "name the .gitlint repair without inferring feat from the Request",
        lines,
    )


def _native_environment(directory):
    directory.mkdir()
    for name in ("git", "sh"):
        executable = shutil.which(name)
        assert executable is not None, _message(
            f"fixture cannot resolve {name}",
            "the declared real native boundary requires this tool",
            f"provide {name} in the host verification runtime",
        )
        (directory / name).symlink_to(executable)
    (directory / "python").symlink_to(sys.executable)
    return {
        "PATH": str(directory),
        "NWAVE_PYTHON": sys.executable,
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }


def _native_call(root, argv, environment):
    result = run_cli_in_process(
        argv,
        cwd=root,
        env=environment,
        catch_all=True,
    )
    print(result[1], end="")
    print(result[2], end="", file=sys.stderr)
    return result


@pytest.mark.parametrize(
    ("changed_name", "expected_success"),
    [("INVOCATION_ID", True), ("JAVA_HOME", False)],
    ids=["invocation-is-not-identity", "toolchain-remains-identity"],
)
def test_prefactoring_context_ignores_invocation_only_not_toolchain(
    root,
    step,
    tmp_path,
    changed_name,
    expected_success,
):
    (root / "product.txt").write_text("before\n")
    (root / "support.txt").write_text("preserved support\n")
    (root / "preserve.sh").write_text(
        "IFS= read -r answer < product.txt\n"
        'case "$answer" in before|after) exit 0;; *) exit 1;; esac\n'
    )
    (root / "oracle.sh").write_text(
        'IFS= read -r answer < product.txt\ntest "$answer" = feature\n'
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "Record existing preservation witness")
    _success(_product(root, step)[0], "po")
    _design(
        root,
        step,
        target="product.txt",
        verification=[["sh", "oracle.sh"]],
        prefactoring={
            "applicability": "applicable",
            "existing_oracle": "preserve.sh",
            "move": "Rewrite before as after without changing the accepted public answer.",
            "preserved_observation": "The native witness accepts the public representation.",
            "verification": [["sh", "preserve.sh"]],
            "acceptance_supports": ["support.txt"],
        },
    )
    environment = _native_environment(tmp_path / "preservation-bin") | {
        "INVOCATION_ID": "one",
        "JAVA_HOME": "/declared/sdk-one",
    }
    before = _success(
        _native_call(
            root,
            [
                "craft",
                "--repo-root",
                str(root),
                "--value",
                "1",
                "--prefactoring-phase",
                "before-move",
            ],
            environment,
        ),
        "craft before-move",
    )
    first = json.loads((root / before["NATIVE-EVIDENCE"]).read_bytes())
    (root / "product.txt").write_text("after\n")
    changed = environment | {
        changed_name: "two" if changed_name == "INVOCATION_ID" else "/declared/sdk-two",
    }
    result = _native_call(
        root,
        [
            "craft",
            "--repo-root",
            str(root),
            "--value",
            "1",
            "--prefactoring-phase",
            "after-move-before-behavior",
        ],
        changed,
    )
    lines = block(result[1], result[2])
    _public_state(
        before_context=first["context"],
        after_terminal=lines,
        changed_environment_name=changed_name,
    )
    if expected_success:
        assert (
            result[0] == 0
            and lines.get("PREFACTORING-PHASE") == "after-move-before-behavior"
        ), _message(
            "INVOCATION_ID alone changed preservation identity",
            "launch identity is not the executed toolchain",
            "exclude INVOCATION_ID from the child digest without removing it from execution",
            lines,
        )
        second = json.loads((root / lines["NATIVE-EVIDENCE"]).read_bytes())
        _public_state(
            after_context=second["context"],
            before_environment=first["environment_public"],
            after_environment=second["environment_public"],
        )
        assert second["context"] == first["context"], _message(
            "public preservation contexts differ for invocation-only change",
            "the receipt must bind an otherwise unchanged executor and environment",
            "keep the context digest stable across INVOCATION_ID changes",
            (first["context"], second["context"]),
        )
    else:
        assert result[0] != 0 and lines.get("WHAT") == "PrefactoringWitnessChanged", (
            _message(
                "a changed JAVA_HOME kept preservation identity",
                "the selected toolchain is semantically significant",
                "retain every nonvolatile, nonsecret toolchain selector in the digest",
                lines,
            )
        )


def test_native_log_matches_each_actual_child_environment_and_hides_credentials(
    root,
    step,
    tmp_path,
):
    vectors = [
        ["python", "-m", "pytest", "-q", "-s", ORACLE],
        ["python", "-c", CHILD_CAPTURE.strip()],
    ]
    _craft(root, step, verification=vectors)
    synthetic_secret = "ghp_" + "s" * 30
    environment = _native_environment(tmp_path / "native-bin") | {
        "INVOCATION_ID": "probe-1",
        "NWAVE_PROBE_SELECTOR": "alpha",
        "DEPLOY_TOKEN": "hidden-credential",
        "CC": synthetic_secret,
    }
    lines = _success(
        _native_call(root, ["verify", "--repo-root", str(root)], environment),
        "verify native environment",
    )
    records = json.loads((root / lines["NATIVE-EVIDENCE"]).read_bytes())
    raw_evidence = (root / lines["NATIVE-EVIDENCE"]).read_text(encoding="utf-8")
    _public_state(
        native_records=records,
        parent_environment={
            name: value
            for name, value in environment.items()
            if name not in {"DEPLOY_TOKEN", "CC"}
        },
    )
    assert [record["argv"] for record in records] == vectors, _message(
        "native evidence did not conserve the declared vector population",
        "each executed vector needs its own actual environment",
        "retain one ordered observation for each declared argv",
        records,
    )
    for record in records:
        captures = [
            json.loads(line.removeprefix("CHILD-ENVIRONMENT: "))
            for line in record["stdout"].splitlines()
            if line.startswith("CHILD-ENVIRONMENT: ")
        ]
        assert len(captures) == 1, _message(
            "the executed child did not report its environment",
            "a parent-side summary cannot prove what the vector received",
            "retain the actual child's CHILD-ENVIRONMENT stdout",
            record["stdout"],
        )
        actual = captures[0]
        logged = record.get("declared_environment") or {}
        # pytest may add its own session variables after spawn. Its observer
        # pins the promised adaptations; the plain Python observer captures
        # the complete controlled spawn environment before any test runner.
        observed_log = (
            {name: logged.get(name) for name in actual}
            if record["argv"] == vectors[0]
            else logged
        )
        assert observed_log == actual, _message(
            "native log differs from the vector's actual environment",
            "PATH, invocation and per-vector probe adaptations must have truthful provenance",
            "serialize the final secret-safe command environment passed to that spawn",
            {"actual_child": actual, "logged": logged},
        )
        witnesses = [
            json.loads(line.removeprefix("CHILD-EXECUTABLE: "))
            for line in record["stdout"].splitlines()
            if line.startswith("CHILD-EXECUTABLE: ")
        ]
        assert witnesses == [
            {
                "path": record["executable"],
                "exists": True,
                "executable": True,
            }
        ], _message(
            "the shim was not observed live by its own child",
            "a retained path after runtime cleanup is not executable-existence evidence",
            "resolve and observe the actual executable while the child runs",
            witnesses,
        )
        assert list(logged) == sorted(logged), _message(
            "the complete execution environment is not sorted",
            "native provenance has a deterministic public order",
            "serialize the secret-safe command_env entries in name order",
            list(logged),
        )
        assert logged.get("PYTHONDONTWRITEBYTECODE") == "1", _message(
            "the Python runtime adaptation is missing from the log",
            "the record must describe the adapted child rather than its parent",
            "include PYTHONDONTWRITEBYTECODE from the final command_env",
            logged,
        )
        entries = logged.get("PATH", "").split(os.pathsep)
        assert entries[1:] == environment["PATH"].split(os.pathsep) and (
            entries[0] not in environment["PATH"].split(os.pathsep)
            and Path(entries[0]) == Path(record["executable"]).parent
        ), _message(
            "logged PATH does not identify the executed ephemeral interpreter shim",
            "the shim precedes the parent PATH for this actual Python vector",
            "record PATH after constructing the candidate runtime, not from the parent",
            record,
        )
        assert logged.get("INVOCATION_ID") == "probe-1", _message(
            "INVOCATION_ID disappeared from the actual environment record",
            "excluding a launch identifier from identity does not remove its provenance",
            "keep the child's INVOCATION_ID in execution and native evidence",
            logged,
        )
        assert (
            logged.get("NWAVE_PROBE_SELECTOR") == environment["NWAVE_PROBE_SELECTOR"]
        ), _message(
            "a custom nonsecret execution input is absent from the native record",
            "a fixed whitelist cannot describe the actual per-vector environment",
            "record all sorted command_env entries except secret names and secret values",
            logged,
        )
        assert (
            "DEPLOY_TOKEN" not in logged
            and "CC" not in logged
            and (
                synthetic_secret not in json.dumps(logged)
                and environment["DEPLOY_TOKEN"] not in json.dumps(logged)
            )
        ), _message(
            "native evidence exposed a credential name or credential-shaped value",
            "truthful provenance must remain secret-safe",
            "apply the existing secret-name and secret-value policy to every recorded entry",
        )
    pytest_environment = records[0]["declared_environment"]
    plain_environment = records[1]["declared_environment"]
    assert (
        "PYTEST_ADDOPTS" in pytest_environment
        and "PYTEST_ADDOPTS" not in plain_environment
    ), _message(
        "native vectors were logged with one shared probe environment",
        "only the pytest vector receives the pytest observation adapter",
        "record each vector's final command_env separately",
        {"pytest": pytest_environment, "plain": plain_environment},
    )
    assert (
        synthetic_secret not in raw_evidence
        and environment["DEPLOY_TOKEN"] not in raw_evidence
    ), _message(
        "native evidence retained a credential-shaped or credential-name value",
        "the retained artifact must be safe to share as public execution evidence",
        "omit credentials before serializing any native environment record",
    )
