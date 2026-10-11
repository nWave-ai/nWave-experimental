"""Raw trace -> domain-language events, mechanically (nw-po-scenario-exploration:61-65, 83-88).

A scenario is never authored: its steps are read from the raw Quint trace kept as an artifact of its
source run, and printed through the explicit domain templates of the model's action atoms. The same
trace and model give the same text; an action or variable the model does not cover is REPORTED, never
narrated. The output has the shape DES already records for DISCUSS: events of {trace_index, text}."""

from __future__ import annotations

import dataclasses as dc
import hashlib
import html
import json
import os
import re
import typing as t

from . import g10_codec as C
from . import g10_itf as I
from . import g10_scope as S
from . import g10_types as T


_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(@pre)?\}")


def _actions(model: T.Model) -> dict[str, T.ActionAtom]:
    """Action atoms by name; if a model repeats a name (rule M1 reports it) the lookup still never depends on list order."""
    return C.index_by(
        (a for a in model.atoms if isinstance(a, T.ActionAtom)), lambda a: a.name
    )


def mutant_description(model: T.Model, mutant_id: str) -> str | None:
    m = C.index_by(model.mutants, lambda x: x.id).get(mutant_id)
    return m.description if m is not None else None


def template_problems(model: T.Model) -> list[str]:
    """Static (rule M2): every action template names only state atoms of its own model."""
    states = {a.name for a in model.atoms if isinstance(a, T.StateAtom)}
    out = []
    for a in model.atoms:
        if isinstance(a, T.ActionAtom):
            for name, _pre in _PLACEHOLDER.findall(a.template):
                if name not in states:
                    out.append(
                        f"action {a.name!r}: template names {name!r}, which is not a state atom of model {model.id}"
                    )
    return out


def trace_problems(model: T.Model, trace: I.Trace) -> list[str]:
    """Dynamic (rule S3): why this trace cannot be rendered through this model; empty means renderable."""
    actions = _actions(model)
    out: list[str] = []
    if not trace.states:
        out.append("the trace has no state")
    for i, st in enumerate(trace.states):
        if st.action is None:
            out.append(
                f"state {i}: the trace names no action (it was written without --mbt)"
            )
            continue
        a = actions.get(st.action)
        if a is None:
            out.append(
                f"state {i}: action {st.action!r} is not an action atom of model {model.id}"
            )
            continue
        for name, pre in _PLACEHOLDER.findall(a.template):
            if pre and i == 0:
                out.append(
                    f"state 0: template of {a.name!r} asks for {name}@pre, but a first state has no before"
                )
                continue
            src = trace.states[i - 1] if pre else st
            if name not in src.vars:
                out.append(f"state {i}: variable {name!r} is not in the trace")
    return out


def render_trace(
    model: T.Model, trace: I.Trace, checks: t.Sequence[str]
) -> list[tuple[int, str]]:
    problems = trace_problems(model, trace)
    if problems:
        raise ValueError("; ".join(problems))
    actions = _actions(model)
    events: list[tuple[int, str]] = []
    for i, st in enumerate(trace.states):

        def sub(m: re.Match[str], i: int = i, st: I.State = st) -> str:
            src = trace.states[i - 1] if m.group(2) else st
            return I.fmt(src.vars[m.group(1)])

        events.append(
            (st.index, _PLACEHOLDER.sub(sub, actions[st.action or ""].template))
        )
    if trace.status == "violation" and len(checks) == 1:
        prop = C.index_by(
            (p for p in model.atoms if isinstance(p, T.PropertyAtom)), lambda p: p.name
        ).get(checks[0])
        events.append(
            (
                trace.states[-1].index,
                "The check fails in this state: "
                + (prop.statement if prop else checks[0]),
            )
        )
    return events


# --------------------------------------------------------------------------- scenarios from runs
@dc.dataclass(frozen=True)
class Rendered:
    scenario: T.Scenario
    run: T.Run
    model: T.Model
    trace_sha256: str
    events: tuple[tuple[int, str], ...]
    trace_status: str  # `#meta.status` of the kept trace: ok | violation | ...


@dc.dataclass(frozen=True)
class Skipped:
    reason: str  # the check could not run; it is neither a pass nor a defect


@dc.dataclass(frozen=True)
class Bad:
    problems: tuple[str, ...]  # the trace is present and cannot be rendered


def render_scenario(
    v: S.Visible, sc: T.Scenario, base_dir: str | None
) -> Rendered | Skipped | Bad:
    run = v.runs.get(sc.source_run)
    model = v.models.get(run.model_id) if run is not None and run.model_id else None
    if run is None or model is None:
        return Skipped(
            "the source run or its model is missing (rules S2, CL7 and R3 report that)"
        )
    art = T.trace_of(run)
    if art is None:
        return Skipped(f"run {run.id} keeps no trace artifact (rule S2 reports that)")
    if base_dir is None:
        return Skipped(
            f"trace {art.path} cannot be read: no directory was given for the sidecar files"
        )
    path = os.path.join(base_dir, art.path)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return Skipped(f"trace {art.path} is not there (rule R6 reports that)")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != art.sha256:
        return Skipped(f"trace {art.path} changed after the run (rule R6 reports that)")
    try:
        trace = I.parse(json.loads(raw.decode("utf-8")))
    except (ValueError, I.ItfError, RecursionError) as exc:
        return Bad((f"trace {art.path} cannot be read: {exc}",))
    problems = trace_problems(model, trace)
    if problems:
        return Bad(tuple(problems))
    return Rendered(
        sc,
        run,
        model,
        digest,
        tuple(render_trace(model, trace, run.checks)),
        trace.status,
    )


def quint_scenarios(items: list[Rendered]) -> dict:
    """The same data in the shape of DISCUSS `quint_scenarios` (src/des/domain/discuss_contract.py:61-65),
    derived from the real run, never stored twice."""
    first = items[0]
    return {
        "status": "generated",
        "model": {"path": first.model.path, "identity": first.model.sha256},
        "tool": {
            "name": first.run.tool,
            "version": first.run.tool_version,
            "command": " ".join(first.run.argv),
        },
        "trace": {"path": T.trace_of(first.run).path},
        "scenarios": [
            {
                "title": r.scenario.title,
                "events": [{"trace_index": i, "text": x} for i, x in r.events],
            }
            for r in items
        ],
    }


# --------------------------------------------------------------------------- human view (E-G09-03 asks for HTML)
def _header(r: Rendered) -> str:
    review = r.scenario.review
    state = (
        "pending"
        if isinstance(review, T.Pending)
        else f"judged {review.judgment} by {review.by}"
    )
    return f"{r.scenario.title} [{r.scenario.kind}; run {r.run.id}; model {r.model.sha256[:12]}; trace {r.trace_sha256[:12]}; review {state}]"


def _mutant_line(r: Rendered) -> str | None:
    if r.scenario.kind != "mutant":
        return None
    mid = r.run.variant.removeprefix("mutant:")
    d = mutant_description(r.model, mid)
    return f"What this bug does: {d}" if d is not None else None


def scenario_text(r: Rendered) -> str:
    lines = [_header(r)]
    if (extra := _mutant_line(r)) is not None:
        lines.append(extra)
    lines += [f"{n}. {x}" for n, (_, x) in enumerate(r.events)]
    return "\n".join(lines)


def scenarios_html(items: list[Rendered], not_rendered: list[str]) -> str:
    """A self-contained page: no script, no external reference; every value is escaped."""
    e = html.escape
    body = ["<h1>Scenarios for review</h1>"]
    for r in items:
        body.append(f"<h2>{e(r.scenario.title)}</h2><p>{e(_header(r))}</p>")
        if (extra := _mutant_line(r)) is not None:
            body.append(f"<p><em>{e(extra)}</em></p>")
        body.append("<ol>" + "".join(f"<li>{e(x)}</li>" for _, x in r.events) + "</ol>")
    if not_rendered:
        body.append(
            "<h2>Not rendered</h2><ul>"
            + "".join(f"<li>{e(x)}</li>" for x in not_rendered)
            + "</ul>"
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>G10 scenarios</title>'
        "<style>body{font-family:sans-serif;max-width:60em;margin:2em auto}li{margin:.3em 0}</style></head><body>"
        + "".join(body)
        + "</body></html>\n"
    )
