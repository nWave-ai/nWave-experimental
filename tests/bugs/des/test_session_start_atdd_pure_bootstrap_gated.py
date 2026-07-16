"""Regression AT: SessionStart teaches the atdd_pure spine ONLY in atdd_pure
projects -- gated on ``_session_cwd_is_atdd_pure``, never unconditionally.

RCA (empirically confirmed, not assumed): ``handle_session_start()`` already
loads ``nWave/data/orchestrator-affordance/*.md`` (spine-discipline.md +
des-command-catalog.md) via ``load_orchestrator_affordance`` and injects it
as ``hookSpecificOutput.additionalContext`` on EVERY session -- verified by
driving the real handler against a bare ``tmp_path`` (no ``.nwave/``, no
``docs/``) and observing the spine-discipline content on stdout regardless.
The call site (``session_start_handler.py`` ~line 517-526) never consults
``_session_cwd_is_atdd_pure(cwd)`` before injecting this content -- so:

  (a) a NON-nWave / non-atdd_pure cwd gets spine-teaching noise it should
      never see (violates "when cwd is NOT atdd_pure, bootstrap NOT
      injected");
  (b) the shipped bootstrap content never names ``/nw-buddy`` -- the
      producing tool for methodology questions -- so an atdd_pure session
      is taught the spine + ``des dispatch`` + the mode, but never where to
      ask a question.

Fix direction (for the crafter -- this AT pins the OBSERVABLE, not the
implementation): gate the orchestrator-affordance injection (or its
replacement) on ``_session_cwd_is_atdd_pure(cwd)``, and extend the shipped
bootstrap content to name ``/nw-buddy``.

Driving surface (Mandate-13/16 driving-port-only, Layer 3 in-process
default): the REAL ``handle_session_start()`` entry point (the SessionStart
hook's actual driving port -- reads stdin JSON, writes hook-protocol JSON to
stdout), captured via ``capsys``. ``_session_cwd_is_atdd_pure`` is patched
at its call site (the established convention in
``tests/des/acceptance/test_wave_entry_gate_affordance_nudge.py``) rather
than reconstructed via a real ``.nwave/config.yaml`` -- ``resolve_workflow_mode``
defaults an UNCONFIGURED project to ``atdd_pure`` (DDD-7), so a bare
``tmp_path`` cannot be used to witness the "NOT atdd_pure" branch without
either an explicit classic-mode config or patching the predicate directly;
patching mirrors the sibling AT's established harness.

``run_probe`` is patched to return "" in every scenario -- deterministic,
mirrors the ``_silence_probe`` autouse fixture in the unit-test sibling
(``tests/des/unit/adapters/drivers/hooks/test_session_start_handler.py``).

Addendum (2026-07-16, examiner Vera / nw-user-examiner INDETERMINATE on the
NEGATIVE oracle): a plain non-``.nwave`` dir produces 0 bytes stdout + 0 bytes
stderr, exit 0 -- but malformed JSON, missing ``cwd``, ``cwd: null``, and
``cwd`` pointing at a FILE (not a directory) ALL produce that SAME
byte-identical silent output today, while a non-string ``cwd`` (``12345``)
DOES surface a distinct labeled stderr signal
(``[nwave] prior-use adoption error (fail-open): ...``) via
``_parse_cwd`` -> ``Path(12345)`` raising ``TypeError``. The genuine no-op's
silence is therefore, TODAY, indistinguishable from a swallowed parse error --
absence != incapacity. Scenarios 5-7 below pin the fix: every malformed-
envelope class must degrade LOUD (a labeled ``[nwave] ...`` diagnostic on
stderr, still fail-open exit 0) so the genuine-no-op silence becomes the
UNIQUE fully-silent case. Stderr is the correct channel -- Claude Code never
injects it into the model context, so the charter's "plain-dir stays silent /
no nag" (about visible stdout/additionalContext) is preserved.
"""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from des.adapters.drivers.hooks.session_start_handler import handle_session_start
from des.application.update_check_service import UpdateCheckResult, UpdateStatus


_HANDLER = "des.adapters.drivers.hooks.session_start_handler"


def _collect_additional_context(raw_stdout: str) -> str:
    """Concatenate every ``additionalContext`` value across all emitted JSON lines.

    ``handle_session_start`` prints one JSON object per ``print(json.dumps(...))``
    call (update notice, gate-affordance nudge, skew finding, orchestrator
    affordance -- each independent). Accepts both the wrapped
    ``hookSpecificOutput.additionalContext`` form and the bare
    ``{"additionalContext": ...}`` form (the skew finding uses the bare form).
    Non-JSON / unrelated lines are skipped, never raised.
    """
    collected: list[str] = []
    for line in raw_stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        hso = payload.get("hookSpecificOutput")
        if isinstance(hso, dict) and isinstance(hso.get("additionalContext"), str):
            collected.append(hso["additionalContext"])
        elif isinstance(payload.get("additionalContext"), str):
            collected.append(payload["additionalContext"])
    return "\n".join(collected)


def _run_and_capture(
    capsys: pytest.CaptureFixture[str],
    cwd: str,
    *,
    is_atdd_pure: bool,
    update_status: UpdateStatus = UpdateStatus.SKIP,
    latest: str = "",
) -> tuple[int, str]:
    """Drive handle_session_start(), returning (exit_code, full_raw_stdout)."""
    stdin_payload = json.dumps({"cwd": cwd})
    result = UpdateCheckResult(status=update_status, latest=latest)

    with (
        patch(f"{_HANDLER}._session_cwd_is_atdd_pure", return_value=is_atdd_pure),
        patch(f"{_HANDLER}._build_update_check_service") as mock_factory,
        patch(f"{_HANDLER}.run_probe", return_value=""),
        patch("sys.stdin", io.StringIO(stdin_payload)),
    ):
        mock_service = MagicMock()
        mock_service.check_for_updates.return_value = result
        mock_factory.return_value = mock_service
        exit_code = handle_session_start()

    return exit_code, capsys.readouterr().out


def _run_with_raw_stdin(
    capsys: pytest.CaptureFixture[str],
    raw_stdin_text: str,
    *,
    update_status: UpdateStatus = UpdateStatus.SKIP,
    latest: str = "",
) -> tuple[int, str, str]:
    """Drive handle_session_start() with a RAW stdin envelope, returning
    (exit_code, stdout, stderr).

    Unlike ``_run_and_capture``, this does NOT shape stdin from a ``cwd``
    string and does NOT patch ``_session_cwd_is_atdd_pure`` -- these
    scenarios probe the REAL ``_parse_cwd`` / prior-use-adoption degrade-loud
    behaviour for malformed envelopes (scenarios 1/2 already cover the
    content-gating logic via the patched predicate). Captures stderr as well
    as stdout -- the discriminating signal for this bug lives on stderr.
    """
    result = UpdateCheckResult(status=update_status, latest=latest)

    with (
        patch(f"{_HANDLER}._build_update_check_service") as mock_factory,
        patch(f"{_HANDLER}.run_probe", return_value=""),
        patch("sys.stdin", io.StringIO(raw_stdin_text)),
    ):
        mock_service = MagicMock()
        mock_service.check_for_updates.return_value = result
        mock_factory.return_value = mock_service
        exit_code = handle_session_start()

    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


# ---------------------------------------------------------------------------
# Scenario 1 (POSITIVE, RED-today core) -- atdd_pure cwd teaches the spine,
# des dispatch, the mode, AND names /nw-buddy for questions.
# ---------------------------------------------------------------------------


def test_atdd_pure_cwd_bootstrap_names_spine_dispatch_mode_and_buddy(tmp_path, capsys):
    exit_code, raw = _run_and_capture(capsys, str(tmp_path), is_atdd_pure=True)
    ctx = _collect_additional_context(raw)

    assert exit_code == 0, "SessionStart must stay fail-open (exit 0)"
    assert ctx.strip() != "", "expected additionalContext output for an atdd_pure cwd"

    # (1) names the /nw-* spine -- at least one real /nw-* command literal.
    assert "/nw-" in ctx, "bootstrap must name the /nw-* spine by literal command"

    # (2) names des dispatch, the crafter-envelope generator.
    assert "des dispatch" in ctx, "bootstrap must name `des dispatch` by literal string"

    # (3) names the atdd_pure mode explicitly.
    assert "atdd_pure" in ctx, "bootstrap must name the atdd_pure mode explicitly"

    # (4) names /nw-buddy for methodology questions -- RED today: the shipped
    # orchestrator-affordance content (spine-discipline.md +
    # des-command-catalog.md) never mentions /nw-buddy.
    assert "/nw-buddy" in ctx, (
        "bootstrap must name /nw-buddy as the producing tool for questions -- "
        "absent from the shipped orchestrator-affordance content today"
    )


# ---------------------------------------------------------------------------
# Scenario 2 (NEGATIVE, no noise) -- a non-atdd_pure cwd gets NO spine
# bootstrap. RED today: the orchestrator-affordance injection fires
# unconditionally, regardless of _session_cwd_is_atdd_pure.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_non_atdd_pure_cwd_never_emits_spine_bootstrap(tmp_path, capsys):
    exit_code, raw = _run_and_capture(capsys, str(tmp_path), is_atdd_pure=False)
    ctx = _collect_additional_context(raw)

    assert exit_code == 0, "SessionStart must stay fail-open (exit 0)"

    assert "des dispatch" not in ctx, (
        "a non-atdd_pure cwd must NOT be taught `des dispatch` -- the "
        "orchestrator-affordance injection fires unconditionally today "
        "(not gated on _session_cwd_is_atdd_pure), which is the bug"
    )
    assert "/nw-buddy" not in ctx, (
        "a non-atdd_pure cwd must NOT receive the /nw-buddy spine pointer"
    )
    assert "atdd_pure" not in ctx, (
        "a non-atdd_pure cwd must NOT see atdd_pure-mode teaching content"
    )
    assert "spine" not in ctx.lower(), (
        "a non-atdd_pure cwd must NOT see any spine-discipline teaching text"
    )


# ---------------------------------------------------------------------------
# Scenario 3 (NEGATIVE, honest real tools) -- the bootstrap names REAL
# producing tools by literal string, not a fabricated/stale list.
# ---------------------------------------------------------------------------


def test_bootstrap_names_real_producing_tools_not_fabricated(tmp_path, capsys):
    _, raw = _run_and_capture(capsys, str(tmp_path), is_atdd_pure=True)
    ctx = _collect_additional_context(raw)

    real_tools = [
        "des dispatch",
        "des feature-delta-doctor",
        "des charter-scaffold",
        "des commit-slice",
        "/nw-buddy",
    ]
    missing = [tool for tool in real_tools if tool not in ctx]
    assert not missing, (
        f"bootstrap must name every real producing tool by literal string; "
        f"missing (fabricated-list guard): {missing}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 (NEGATIVE, additive contract) -- the bootstrap does NOT clobber
# the existing update-available notice; both co-exist in the same session.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_bootstrap_never_replaces_update_available_notice(tmp_path, capsys):
    exit_code, raw = _run_and_capture(
        capsys,
        str(tmp_path),
        is_atdd_pure=True,
        update_status=UpdateStatus.UPDATE_AVAILABLE,
        latest="9.9.9",
    )
    ctx = _collect_additional_context(raw)

    assert exit_code == 0
    assert "9.9.9" in ctx, (
        "the update-available notice must still be emitted -- the bootstrap "
        "is additive, never a replacement for the existing update-notice "
        "injection"
    )
    assert "/nw-buddy" in ctx, (
        "the spine bootstrap must co-exist with the update-available notice "
        "in the same session -- RED today via the missing /nw-buddy pointer"
    )


# ---------------------------------------------------------------------------
# Scenario 5 (NEGATIVE, genuine no-op regression-guard) -- a REAL, valid
# directory cwd with no .nwave/ produces ZERO bytes on BOTH stdout and
# stderr. This is the ONLY case that may ever be fully silent; scenarios 6-7
# below prove every OTHER silent-looking input is actually a swallowed
# error, not this genuine no-op.
# ---------------------------------------------------------------------------


def test_genuine_plain_dir_is_fully_silent_stdout_and_stderr(tmp_path, capsys):
    raw_stdin_text = json.dumps({"cwd": str(tmp_path)})
    exit_code, stdout, stderr = _run_with_raw_stdin(capsys, raw_stdin_text)

    assert exit_code == 0, "SessionStart must stay fail-open (exit 0)"
    assert stdout == "", (
        "a genuine valid-directory cwd with no .nwave/ must produce ZERO "
        "stdout bytes -- the sole fully-silent case"
    )
    assert stderr == "", (
        "a genuine valid-directory cwd with no .nwave/ must produce ZERO "
        "stderr bytes -- distinguishing it from a swallowed malformed "
        "envelope is the entire point of this scenario"
    )


# ---------------------------------------------------------------------------
# Scenario 6 (NEGATIVE, degrade-LOUD) -- every malformed-envelope class must
# surface a labeled `[nwave] ...` diagnostic on stderr, never swallow
# silently. RED today: malformed JSON / missing cwd / cwd:null / cwd
# pointing at a FILE all return None from `_parse_cwd` and the caller exits
# silently via `if project_root is None: return` -- 0 bytes stderr,
# byte-identical to the genuine no-op above.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "case_id",
    [
        "malformed-json",
        "missing-cwd",
        "cwd-null",
        "cwd-points-at-file",
        "cwd-non-string",
    ],
)
def test_malformed_envelope_degrades_loud_on_stderr(tmp_path, capsys, case_id):
    if case_id == "malformed-json":
        raw_stdin_text = "{not valid json"
    elif case_id == "missing-cwd":
        raw_stdin_text = json.dumps({})
    elif case_id == "cwd-null":
        raw_stdin_text = json.dumps({"cwd": None})
    elif case_id == "cwd-points-at-file":
        a_file = tmp_path / "not-a-directory.txt"
        a_file.write_text("plain file, not a project root")
        raw_stdin_text = json.dumps({"cwd": str(a_file)})
    elif case_id == "cwd-non-string":
        raw_stdin_text = json.dumps({"cwd": 12345})
    else:  # pragma: no cover -- parametrize id exhausted above
        pytest.fail(f"unknown case_id {case_id!r}")

    exit_code, _stdout, stderr = _run_with_raw_stdin(capsys, raw_stdin_text)

    assert exit_code == 0, (
        f"[{case_id}] SessionStart must stay fail-open (exit 0) even for a "
        "malformed envelope -- the session must never be blocked"
    )
    assert "[nwave]" in stderr, (
        f"[{case_id}] a malformed envelope must degrade LOUD -- a labeled "
        "'[nwave] ...' diagnostic on stderr -- RED today: this class is "
        "swallowed silently (0 bytes stderr), indistinguishable from a "
        "genuine valid plain-dir no-op (the exact INDETERMINATE Vera "
        "flagged)"
    )


# ---------------------------------------------------------------------------
# Scenario 7 (NEGATIVE, THE discriminating falsifier) -- pairwise, the
# genuine no-op's (exit_code, stdout, stderr) signature must differ from
# EVERY malformed-envelope case's signature. This is Vera's own probe logic
# ("does a state exist where this surface would lie to me the same way?")
# turned into a mechanical assertion -- it is the direct falsifier of her
# INDETERMINATE verdict.
# ---------------------------------------------------------------------------


def test_genuine_silence_is_distinguishable_from_every_malformed_case(tmp_path, capsys):
    genuine_project = tmp_path / "genuine-project"
    genuine_project.mkdir()
    genuine_signature = _run_with_raw_stdin(
        capsys, json.dumps({"cwd": str(genuine_project)})
    )

    a_file = tmp_path / "not-a-directory.txt"
    a_file.write_text("plain file, not a project root")

    malformed_cases = {
        "malformed-json": "{not valid json",
        "missing-cwd": json.dumps({}),
        "cwd-null": json.dumps({"cwd": None}),
        "cwd-points-at-file": json.dumps({"cwd": str(a_file)}),
        "cwd-non-string": json.dumps({"cwd": 12345}),
    }
    for case_id, raw_stdin_text in malformed_cases.items():
        signature = _run_with_raw_stdin(capsys, raw_stdin_text)
        assert signature != genuine_signature, (
            f"[{case_id}] a swallowed malformed envelope must NOT be "
            f"byte-identical to the genuine no-op's silent signature "
            f"{genuine_signature!r} -- got {signature!r}. This exact "
            "collision is what nw-user-examiner (Vera) flagged as "
            "INDETERMINATE: 'cannot confirm a real decision vs a silent "
            "degrade'"
        )
