"""The Claude-local driven adapter for one model turn (ADR-SSOT-002 13d.2).

Everything provider-shaped lives HERE and never crosses
:class:`~des.ports.driven_ports.task_invocation_port.TaskInvocationPort`: the
executable, the effort level, the permission mode, the output format and the
argv shape are all adapter-local settings.

THE MODEL IS THE ONE EXCEPTION, and deliberately so.  It is the only one of
those settings that ALSO has a home in the role's published spec, so keeping a
copy here made every role's model true in two places at once -- and the copy the
provider honours is not always the one a reader opens.  It is therefore read
from the spec, by :func:`~des.domain.agent_capability.resolve_declared_capability`,
and projected into ``--model``; this module holds no model constant.

THE ENVELOPE IS NOT A TERMINAL GRAMMAR.  With ``--output-format json`` stdout is
a document whose result is constrained by the provider's ``--json-schema`` to
one semantic outcome.  Diagnostics remain opaque evidence; the runner never
derives control flow from model-authored prose.
"""

from __future__ import annotations

import json
import shutil
import stat
import time
from pathlib import Path
from typing import Any

from des.adapters.driven.task_invocation.model_envelope import (
    _SOLUTION_ARCHITECT,
    _acceptance_reviewer_schema,  # noqa: F401 - compatibility re-export
    _schema_for,
    decode_model_run,
)
from des.adapters.driven.task_invocation.turn_recorder import TurnRecorder
from des.domain.agent_capability import (
    ClaimRegister,
    provider_tool_name,
    resolve_declared_capability,
)
from des.ports.driven_ports.task_invocation_port import (
    MalformedModelEnvelope,
    ModelAccounting,
    ModelOutcome,
    ModelRun,
    TaskInvocationPort,
)
from des.runtime.spawn import AGENT_TIMEOUT_ENV, SpawnTimeout, agent_timeout_seconds


_LAUNCHER_NAME = "claude"

#: The reasoning budget one turn spawns with.  Adapter-local on purpose: no
#: caller supplies it and no contract field carries it.
#:
#: OPEN QUESTION, deliberately not answered here (recorded in `defects.md`, row
#: `reviewer-effort-low-is-unmeasured`): `low` for a reviewer that must read a
#: whole candidate diff is a choice nobody has measured.  It is left as it is
#: because changing it without a measurement would trade one unevidenced
#: setting for another.
_EFFORT = "low"
_PERMISSION_MODE = "dontAsk"
_OUTPUT_FORMAT = "json"
_STRUCTURED_OUTPUT_TOOL = "StructuredOutput"
#: Declared entries whose whole reach is a read-only query.  A turn holding only
#: these stays retry-safe after a failed spawn.  A scoped grant on the
#: provider-neutral code-fact port reads; it never writes.
_READ_ONLY_PROVIDER_TOOLS = frozenset(
    {
        "Read",
        _STRUCTURED_OUTPUT_TOOL,
        "Bash(des code-fact:*)",
    }
)


def _effort_for(role_id: str) -> str:
    """The adapter-owned reasoning budget for one declared role.

    Effort, unlike the model, has no home in the published spec: it is a
    provider-shaped knob with no Claude Code frontmatter key, so the adapter is
    the only place it can live and there is no second definition to reconcile.
    """
    if role_id == _SOLUTION_ARCHITECT:
        return "high"
    return _EFFORT


def resolve_launcher() -> Path | None:
    """The absolute model launcher on ``PATH``, or ``None`` when unresolvable.

    Separate from construction so the owned runner can admit the executable
    BEFORE any model spend and refuse with its own typed outcome, rather than
    discovering the absence as an exception mid-run (13d.3).
    """
    found = shutil.which(_LAUNCHER_NAME)
    if not found:
        return None
    launcher = Path(found)
    try:
        mode = launcher.lstat().st_mode
    except OSError:
        return None
    # Decide on the PROPERTY, never the designation: a name on PATH is not
    # evidence of a spawnable regular file.
    if launcher.is_symlink():
        try:
            resolved = launcher.resolve(strict=True)
            mode = resolved.lstat().st_mode
        except OSError:
            return None
        launcher = resolved
    if not stat.S_ISREG(mode):
        return None
    return launcher


class ClaudeCodeTaskAdapter(TaskInvocationPort):
    """Invoke one Claude turn through the shared spawn boundary."""

    def __init__(
        self,
        launcher: Path | None = None,
        *,
        model: str | None = None,
        recorder: TurnRecorder | None = None,
        record_root: Path | None = None,
        framework_root: Path | None = None,
    ) -> None:
        """Bind this adapter to one already-admitted absolute executable.

        ``launcher=None`` resolves it now, which is what the runtime smoke and
        any ad-hoc caller want.  The owned runner passes the executable it
        admitted before model spend, so the process that admitted the executable
        is the process that spawns it and no later ``PATH`` re-resolution can
        substitute a different one.

        The adapter carries its own :class:`TurnRecorder` because the runner
        builds exactly one adapter per run, so the adapter's lifetime IS the
        run: that makes the run id and the turn numbering derivable here,
        without widening the port with parameters no caller has.  ``record_root``
        anchors those records to the run's repository, because one turn -- the
        implementation review -- runs with the candidate worktree as its cwd.
        """
        resolved = launcher if launcher is not None else resolve_launcher()
        if resolved is None:
            raise ValueError(
                f"no {_LAUNCHER_NAME} model launcher is resolvable on PATH"
            )
        self._launcher = Path(resolved)
        self._model = model
        self._framework_root = framework_root
        self._recorder = (
            recorder if recorder is not None else TurnRecorder(root=record_root)
        )

    @property
    def launcher(self) -> Path:
        """The absolute executable every turn of this adapter spawns."""
        return self._launcher

    @property
    def run_id(self) -> str:
        """The id naming this run's turn-record directory (diagnostic only)."""
        return self._recorder.run_id

    def argv_for(
        self,
        *,
        role_id: str,
        model: str,
        agents: dict[str, object] | None = None,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
    ) -> list[str]:
        """The exact argv one turn spawns -- built once, here, and nowhere else.

        THE PROMPT IS NOT A PARAMETER.  Linux caps a SINGLE ``execve`` argument
        at ``MAX_ARG_STRLEN`` (128 KiB), and a prompt grows with the evidence the
        runner inlines, so ``-p <prompt>`` made that ceiling reachable by ordinary
        content: measured 2026-09-05, run 12 died with ``[Errno 7] Argument list
        too long`` before the provider process existed, which no ``HOW: observe
        the provider result`` can remedy.  ``claude -p`` reads the prompt from
        stdin when no positional prompt is given (``--input-format text``, the
        default), so :meth:`invoke` passes it there: the ceiling is gone BY
        CONSTRUCTION for every role, not bounded per call site.  Keeping the
        prompt out of this signature is the GDP-0 half -- an unrepresentable
        wrong state needs no gate.  Every remaining element is bounded by
        something that does NOT grow with content: the role-static schema, and an
        agent spec, which is a small tracked repository file (measured
        2026-09-05: largest spec 1.9 KB, largest schema 1.2 KB).

        ``model`` IS A PARAMETER BECAUSE IT IS NOT THE ADAPTER'S FACT.  It is
        what the role's published spec declares, read by
        :func:`resolve_declared_capability` from the same frontmatter and the
        same resolved file the declared tools come from.  There is no default:
        a default would silently answer for a spec that declares nothing, which
        is exactly the second definition this signature removes.

        ``--model`` and ``--effort`` configure THE SESSION THIS TURN IS, not
        some inner sub-agent.  ``--agent <role>`` makes the spawned session BE
        that role, so the outer ``--model`` is the model the role thinks with.
        Measured 2026-09-06 against Claude Code 2.1.261: a ``model`` key placed
        inside the ``--agents`` JSON is IGNORED -- declaring ``haiku`` there
        while the argv said ``--model sonnet`` produced a turn whose work landed
        wholly on ``claude-sonnet-5``, and the mirror probe (``sonnet``
        declared, ``--model haiku``) produced no sonnet entry at all.  Every
        turn also carries a small ambient ``claude-haiku-4-5`` entry
        (~1.8k in / ~20 out) that belongs to the launcher, not to the role, so
        a haiku line in ``modelUsage`` is never evidence that a role ran on
        haiku.
        """
        effort = _effort_for(role_id)
        argv = [
            str(self._launcher),
            "-p",
            "--agent",
            role_id,
            "--model",
            model,
            "--effort",
            effort,
            "--output-format",
            _OUTPUT_FORMAT,
            "--json-schema",
            _schema_for(role_id, max_product_values, defect_values),
            "--permission-mode",
            _PERMISSION_MODE,
            "--setting-sources",
            "user",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--no-chrome",
        ]
        if agents is not None:
            argv.extend(("--agents", json.dumps(agents, separators=(",", ":"))))
        return argv

    def invoke(
        self,
        *,
        role_id: str,
        prompt: str,
        cwd: Path,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
    ) -> ModelRun:
        """Run one turn, record it as a diagnostic, and report its terminal.

        The recording wraps :meth:`_run_turn` rather than living inside it so
        there is ONE write per turn on EVERY exit -- spawned or refused before
        spawn -- instead of a line repeated at each early return, where the next
        branch added would silently be the one that records nothing.

        THAT INCLUDES THE EXITS THAT RAISE, and they are the ones that matter
        most: ``_run_turn`` propagates ``MalformedModelEnvelope`` from
        :func:`extract_model_run` and ``OSError`` from the spawn.  Recording only
        the RETURNED ``ModelRun`` recorded nothing at all for those -- measured
        2026-09-05, both cases produced zero records -- and the second of them is
        run 12's own ``[Errno 7] Argument list too long``, the failure this whole
        change exists to explain.  A raised turn has no ``ModelRun``, so the
        record carries the honest ``indeterminate`` plus a ``raised`` field
        naming the exception type, which is what tells a reader (and a later
        replay) that this turn ended by raising rather than by answering.
        """
        started_at = time.time()
        # One mutable slot per CALL, filled by `_run_turn` the moment each piece
        # of evidence exists.  Per-call rather than per-instance so two turns can
        # never interleave their evidence, and filled progressively so a turn
        # that RAISES still records the argv it spawned and whatever the provider
        # had already written.
        captured: dict[str, Any] = {"argv": None, "stdout": None, "stderr": None}
        try:
            run = self._run_turn(
                role_id=role_id,
                prompt=prompt,
                cwd=cwd,
                max_product_values=max_product_values,
                defect_values=defect_values,
                captured=captured,
            )
        except (MalformedModelEnvelope, OSError) as error:
            self._recorder.record(
                root=cwd,
                role_id=role_id,
                prompt=prompt,
                argv=captured["argv"],
                outcome=ModelOutcome.Indeterminate.value,
                diagnostic=f"{type(error).__name__}: {error}",
                exit_status=-1,
                retry_safe=False,
                provider_stdout=captured["stdout"],
                provider_stderr=captured["stderr"],
                started_at=started_at,
                ended_at=time.time(),
                raised=type(error).__name__,
            )
            raise
        self._recorder.record(
            root=cwd,
            role_id=role_id,
            prompt=prompt,
            argv=captured["argv"],
            outcome=run.outcome.value,
            diagnostic=run.diagnostic,
            exit_status=run.exit_status,
            retry_safe=run.retry_safe,
            provider_stdout=captured["stdout"],
            provider_stderr=captured["stderr"],
            started_at=started_at,
            ended_at=time.time(),
        )
        return run

    def _run_turn(
        self,
        *,
        role_id: str,
        prompt: str,
        cwd: Path,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
        captured: dict[str, Any],
    ) -> ModelRun:
        """One turn, filling `captured` with the evidence the recorder wants.

        Evidence is deposited as soon as it exists rather than returned at the
        end, because the two exits that matter most -- a malformed envelope and
        a spawn that never started a provider -- leave by raising and would
        return nothing at all.
        """
        from des.runtime.spawn import spawn

        capability = resolve_declared_capability(
            role_id, repo_root=cwd, framework_root=self._framework_root
        )
        if (
            capability.register is ClaimRegister.UNKNOWN
            or capability.spec_path is None
            or capability.declared_tools is None
        ):
            return ModelRun(
                ModelOutcome.Indeterminate,
                "agent specification is missing, unreadable, or has no explicit tools",
                0,
                False,
                issued=False,
            )
        model = self._model or capability.declared_model
        if not isinstance(model, str) or not model.strip():
            # The model has ONE home, the spec, so a spec that declares none
            # leaves the turn with nothing to spawn on.  Degrade LOUD (GDP-6):
            # falling back to an adapter constant would restore the second
            # definition and hide the omission behind a working run.
            return ModelRun(
                ModelOutcome.Indeterminate,
                "WHAT: the agent specification "
                f"{capability.spec_reference(role_id)} declares no `model:`. "
                "WHY: the model a role thinks with is projected from its own "
                "spec, so an undeclared model has no value to spawn with and a "
                "default would put it back in a second place. "
                "HOW: add a `model:` line to that spec's frontmatter.",
                0,
                True,
                issued=False,
            )
        try:
            agent_spec = capability.spec_path.read_text(encoding="utf-8")
        except OSError:
            return ModelRun(
                ModelOutcome.Indeterminate,
                "agent specification is unreadable",
                0,
                False,
                issued=False,
            )
        declared_entries = tuple(
            dict.fromkeys((*capability.declared_tools, _STRUCTURED_OUTPUT_TOOL))
        )
        provider_tools = tuple(
            dict.fromkeys(provider_tool_name(entry) for entry in declared_entries)
        )
        agents = {
            role_id: {
                "description": role_id,
                "prompt": agent_spec,
                "tools": list(provider_tools),
            },
        }
        argv = self.argv_for(
            role_id=role_id,
            model=model,
            agents=agents,
            max_product_values=max_product_values,
            defect_values=defect_values,
        )
        argv.extend(
            (
                "--restricted",
                "--disable-slash-commands",
                "--tools",
                ",".join(provider_tools),
                "--allowedTools",
                ",".join(declared_entries),
            )
        )
        captured["argv"] = argv
        try:
            completed = spawn(
                argv,
                # The prompt travels on the child's stdin, which the spawn
                # boundary turns into a pipe it writes and CLOSES.  That keeps
                # the boundary's own duty intact -- the descriptor reaches EOF,
                # so no descendant can inherit a stdin that delivers data and
                # never ends -- while removing the 128 KiB per-argument ceiling
                # the prompt used to be subject to.
                input=prompt,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=agent_timeout_seconds(),
                timeout_env=AGENT_TIMEOUT_ENV,
                reap_process_group=True,
            )
        except SpawnTimeout as expired:
            captured["stdout"] = expired.captured_text
            return ModelRun(
                outcome=ModelOutcome.Indeterminate,
                diagnostic=f"provider bound fired: {expired.captured_text}",
                exit_status=-1,
                retry_safe=False,
            )
        captured["stdout"] = completed.stdout
        captured["stderr"] = completed.stderr
        if completed.returncode:
            # The run already failed on its own terms.  Applying the envelope law
            # here would report an envelope defect for what is really a failed
            # turn, so the caller sees the verbatim exit status and whatever
            # terminal could be recovered.
            return ModelRun(
                outcome=ModelOutcome.Indeterminate,
                diagnostic=_best_effort_diagnostic(
                    completed.stdout or "", completed.stderr or ""
                ),
                exit_status=int(completed.returncode),
                retry_safe=(
                    _is_retry_safe_api_error(completed.stdout or "")
                    or set(declared_entries).issubset(_READ_ONLY_PROVIDER_TOOLS)
                ),
                accounting=_accounting_from_stdout(completed.stdout or ""),
            )
        return extract_model_run(
            completed.stdout or "",
            role_id=role_id,
            max_product_values=max_product_values,
            defect_values=defect_values,
        )


def _best_effort_diagnostic(stdout: str, stderr: str) -> str:
    """Preserve failed-turn evidence without assigning it semantics."""
    return stderr or stdout


def _is_retry_safe_api_error(stdout: str) -> bool:
    """Recognize a complete API failure before any operational iteration.

    Provider bookkeeping may charge or report an internal model attempt before
    it fails (for example HTTP 529).  It is not repository work.  Only the
    explicit empty operational-iteration record makes the failed invocation
    safe for the runner to retry.
    """
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    if not isinstance(document, dict):
        return False
    usage = document.get("usage")
    return (
        document.get("is_error") is True
        and document.get("terminal_reason") == "api_error"
        and isinstance(usage, dict)
        and usage.get("iterations") == []
    )


def _accounting(document: dict[str, object]) -> ModelAccounting | None:
    """Read one complete native accounting record without inventing zeroes."""
    cost = document.get("total_cost_usd")
    turns = document.get("num_turns")
    session_id = document.get("session_id")
    usage = document.get("modelUsage")
    if (
        not isinstance(cost, (int, float))
        or isinstance(cost, bool)
        or cost < 0
        or not isinstance(turns, int)
        or isinstance(turns, bool)
        or turns < 0
        or not isinstance(session_id, str)
        or not session_id
        or not isinstance(usage, dict)
        or not usage
    ):
        return None
    totals = [0, 0, 0, 0]
    for record in usage.values():
        if not isinstance(record, dict):
            return None
        values = (
            record.get("inputTokens"),
            record.get("outputTokens"),
            record.get("cacheCreationInputTokens"),
            record.get("cacheReadInputTokens"),
        )
        if not all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in values
        ):
            return None
        totals = [total + value for total, value in zip(totals, values, strict=True)]
    return ModelAccounting(float(cost), turns, *totals, session_id)


def _accounting_from_stdout(stdout: str) -> ModelAccounting | None:
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    return _accounting(document) if isinstance(document, dict) else None


def extract_model_run(
    stdout: str,
    *,
    role_id: str = "",
    max_product_values: int | None = None,
    defect_values: tuple[str, ...] = (),
) -> ModelRun:
    """Unwrap Claude stdout, then apply the provider-neutral envelope law."""
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise MalformedModelEnvelope(
            "ModelEnvelopeNotSingleDocument: the model launcher's stdout is not "
            f"exactly one JSON document ({exc})"
        ) from None
    if not isinstance(document, dict):
        raise MalformedModelEnvelope(
            "ModelEnvelopeNotObject: the model launcher's response document is a "
            f"{type(document).__name__}, not a JSON object"
        )
    if document.get("is_error"):
        raise MalformedModelEnvelope(
            "ModelEnvelopeErrorOutcome: the model launcher reported an error "
            "outcome for this turn"
        )
    if "structured_output" not in document:
        raise MalformedModelEnvelope(
            "ModelEnvelopeStructuredOutputMissing: response carries no structured output"
        )
    structured = document["structured_output"]
    if not isinstance(structured, dict):
        raise MalformedModelEnvelope(
            "ModelOutcomeMalformed: structured output is not an object"
        )
    return decode_model_run(
        structured,
        role_id=role_id,
        max_product_values=max_product_values,
        defect_values=defect_values,
        accounting=_accounting(document),
    )
