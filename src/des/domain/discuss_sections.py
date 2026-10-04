"""Optional, closed DISCUSS sections: JTBD, journey, Gherkin and Quint scenarios.

Every section is always rendered.  An omitted section shows an honest
placeholder; a supplied one shows exactly what the LLM supplied.  Nothing here
verifies or invents content: Quint evidence is recorded, never claimed proven.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, TypeVar

from des.domain.input_defects import Defects, InputDefects


if TYPE_CHECKING:
    from collections.abc import Callable


T = TypeVar("T")


class SectionInvalid(InputDefects):
    pass


STATUSES = ("proposed", "confirmed", "open")
NOT_EXPLORED = "_Not explored._"
NOT_RUN = "_Not run: no Quint model was executed for this brief._"


def _text(value: object, name: str, *, single_line: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SectionInvalid(f"{name} must be a non-empty string")
    normalized = value.strip()
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError as error:
        raise SectionInvalid(f"{name} must be valid UTF-8 text") from error
    if single_line and ("\n" in normalized or "\r" in normalized):
        raise SectionInvalid(f"{name} must be a single line")
    return normalized


def _step(value: object, name: str) -> str:
    """A Gherkin step is one plain line: a code-fence marker would end its block."""
    text = _text(value, name, single_line=True)
    if "```" in text or "~~~" in text:
        raise SectionInvalid(f"{name} must not contain a code-fence marker")
    return text


def _line(value: object, name: str) -> str:
    return _text(value, name, single_line=True)


def _same(value: object, name: str) -> object:
    return value


def _keys_defect(name: str, required: set[str], optional: set[str]) -> str:
    return (
        f"{name} must contain {sorted(required)} and only optionally {sorted(optional)}"
    )


def _record(
    value: object,
    name: str,
    decoders: dict[str, Callable[[object, str], object]],
    optional: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """A closed object: its key-set defect and each present field's, together."""
    if not isinstance(value, dict):
        raise SectionInvalid(f"{name} must be an object")
    required = set(decoders) - optional
    defects = Defects(SectionInvalid)
    if not required <= set(value) <= set(decoders):
        defects.add(_keys_defect(name, required, set(optional)))
    decoded = {
        key: defects.take(partial(decode, value[key], f"{name}.{key}"))
        for key, decode in decoders.items()
        if key in value
    }
    defects.close()
    return decoded


def _status(value: object, name: str) -> str:
    if value not in STATUSES:
        raise SectionInvalid(f"{name} must be one of {list(STATUSES)}")
    return str(value)


def _list(value: object, name: str) -> list:
    if not isinstance(value, list) or not value:
        raise SectionInvalid(f"{name} must be a non-empty array when present")
    return value


def _items(
    value: object, name: str, decode: Callable[[object, str], T]
) -> tuple[T, ...]:
    """A non-empty list whose every item is decoded, its defects refused together."""
    defects = Defects(SectionInvalid)
    items = tuple(
        defects.take(partial(decode, item, f"{name}[{index}]"))
        for index, item in enumerate(_list(value, name))
    )
    defects.close()
    return items  # type: ignore[return-value]


def _trace_index(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SectionInvalid(f"{name} must be a non-negative integer")
    return value


def _cell(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _md(text: str) -> str:
    return "\n".join(
        f"    {line}" for line in text.replace("\r", "").split("\n")
    ).lstrip()


def _arc_line(text: str) -> str:
    """One fence-safe line for the monospace arc; the table keeps the exact text."""
    return " ".join(text.split()).replace("`", "'")


@dataclass(frozen=True, slots=True)
class Job:
    job: str
    status: str


@dataclass(frozen=True, slots=True)
class JourneyStep:
    step: str
    human_emotion: str | None
    status: str

    def arc(self, position: int, last: bool) -> list[str]:
        emotion = (
            _arc_line(self.human_emotion)
            if self.human_emotion
            else "UNKNOWN (not explored)"
        )
        lines = [f"[{self.status}] {position}. {_arc_line(self.step)}"]
        lines.append(f"    emotion: {emotion}")
        return lines if last else [*lines, "    |", "    v"]


@dataclass(frozen=True, slots=True)
class GherkinScenario:
    scenario: str
    steps: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class QuintScenario:
    title: str
    events: tuple[tuple[int, str], ...]


@dataclass(frozen=True, slots=True)
class QuintEvidence:
    model: str
    model_identity: str
    tool: str
    tool_version: str
    command: str
    trace: str
    scenarios: tuple[QuintScenario, ...]


@dataclass(frozen=True, slots=True)
class DiscussSections:
    jtbd_human: tuple[Job, ...] = ()
    jtbd_llm: tuple[Job, ...] = ()
    journey: tuple[JourneyStep, ...] = ()
    gherkin: tuple[GherkinScenario, ...] = ()
    quint: QuintEvidence | None = None

    @classmethod
    def from_payload(cls, payload: dict, version: int = 1) -> DiscussSections:
        """Parse the section keys of a DISCUSS payload; refuse anything malformed.

        v1 (legacy): each section key is optional and holds the typed data directly.
        v2 (current): each section key holds ``{"status": "not_explored"}`` or
        ``{"status": "provided", ...typed data}``; the DISCUSS key set, which
        the caller refuses, requires every one.  The sections are independent:
        every present one is parsed and all their defects are refused together.
        """
        defects = Defects(SectionInvalid)

        def section(key: str, parse: Callable[[object], T], absent: T) -> T:
            if key not in payload:
                return absent
            return defects.take(partial(parse, payload[key]))  # type: ignore[return-value]

        if version == 1:
            jtbd = section("jtbd", cls._jtbd, ((), ()))
            journey = section("journey", cls._journey, ())
            gherkin = section("gherkin", cls._gherkin, ())
        else:
            jtbd = section(
                "jtbd",
                partial(
                    cls._tagged, name="jtbd", parse=cls._jtbd, keys={"human", "llm"}
                ),
                ((), ()),
            )
            journey = section(
                "journey",
                partial(
                    cls._tagged,
                    name="journey",
                    parse=cls._journey,
                    keys={"steps"},
                    only="steps",
                ),
                (),
            )
            gherkin = section(
                "gherkin",
                partial(
                    cls._tagged,
                    name="gherkin",
                    parse=cls._gherkin,
                    keys={"scenarios"},
                    only="scenarios",
                ),
                (),
            )
        quint = section("quint_scenarios", cls._quint, None)
        defects.close()
        return cls(*jtbd, journey, gherkin, quint)  # type: ignore[misc]

    @staticmethod
    def _tagged(
        value: object, name: str, parse, keys: set[str], only: str | None = None
    ):
        """Unwrap ``{"status": not_explored|provided, ...}`` into the typed data."""
        empty = ((), ()) if name == "jtbd" else ()
        if not isinstance(value, dict) or value.get("status") not in (
            "not_explored",
            "provided",
        ):
            raise SectionInvalid(f"{name}.status must be not_explored or provided")
        if value["status"] == "not_explored":
            _record(value, name, {"status": _same})
            return empty
        data = {k: v for k, v in value.items() if k != "status"}
        if not data:
            raise SectionInvalid(
                f"{name} with status provided must carry {sorted(keys)}"
            )
        defects = Defects(SectionInvalid)
        if not set(data) <= keys:
            defects.add(_keys_defect(name, {"status"}, keys))
        known = {k: v for k, v in data.items() if k in keys}
        parsed = (
            defects.take(partial(parse, known[only] if only else known))
            if known
            else None
        )
        defects.close()
        return parsed

    @classmethod
    def _jtbd(cls, jobs: object) -> tuple[tuple[Job, ...], tuple[Job, ...]]:
        decoded = _record(
            jobs,
            "jtbd",
            {"human": cls._jobs, "llm": cls._jobs},
            frozenset({"human", "llm"}),
        )
        if not jobs:
            raise SectionInvalid("jtbd must contain human and/or llm when present")
        return decoded.get("human", ()), decoded.get("llm", ())  # type: ignore[return-value]

    @staticmethod
    def _journey(value: object) -> tuple[JourneyStep, ...]:
        def step(raw: object, name: str) -> JourneyStep:
            decoded = _record(
                raw,
                name,
                {"step": _text, "human_emotion": _text, "status": _status},
                frozenset({"human_emotion"}),
            )
            return JourneyStep(
                decoded["step"],  # type: ignore[arg-type]
                decoded.get("human_emotion"),  # type: ignore[arg-type]
                decoded["status"],  # type: ignore[arg-type]
            )

        return _items(value, "journey", step)

    @staticmethod
    def _gherkin(value: object) -> tuple[GherkinScenario, ...]:
        def scenario(raw: object, name: str) -> GherkinScenario:
            decoded = _record(
                raw,
                name,
                {
                    "scenario": _line,
                    "steps": lambda steps, label: _items(steps, label, _step),
                    "status": _status,
                },
            )
            return GherkinScenario(**decoded)  # type: ignore[arg-type]

        return _items(value, "gherkin", scenario)

    @staticmethod
    def _jobs(value: object, name: str) -> tuple[Job, ...]:
        def job(raw: object, label: str) -> Job:
            return Job(**_record(raw, label, {"job": _text, "status": _status}))  # type: ignore[arg-type]

        return _items(value, name, job)

    @staticmethod
    def _quint(value: object) -> QuintEvidence | None:
        name = "quint_scenarios"
        if not isinstance(value, dict) or value.get("status") not in (
            "not_run",
            "generated",
        ):
            raise SectionInvalid(f"{name}.status must be not_run or generated")
        if value["status"] == "not_run":
            _record(value, name, {"status": _same})
            return None

        def event(raw: object, label: str) -> tuple[int, str]:
            decoded = _record(raw, label, {"trace_index": _trace_index, "text": _line})
            return decoded["trace_index"], decoded["text"]  # type: ignore[return-value]

        def scenario(raw: object, label: str) -> QuintScenario:
            decoded = _record(
                raw,
                label,
                {
                    "title": _line,
                    "events": lambda events, at: _items(events, at, event),
                },
            )
            return QuintScenario(decoded["title"], decoded["events"])  # type: ignore[arg-type]

        decoded = _record(
            value,
            name,
            {
                "status": _same,
                "model": lambda raw, at: _record(
                    raw, at, {"path": _line, "identity": _line}
                ),
                "tool": lambda raw, at: _record(
                    raw, at, {"name": _line, "version": _line, "command": _line}
                ),
                "trace": lambda raw, at: _record(raw, at, {"path": _line}),
                "scenarios": lambda raw, at: _items(raw, at, scenario),
            },
        )
        model, tool, trace = decoded["model"], decoded["tool"], decoded["trace"]
        return QuintEvidence(
            model["path"],  # type: ignore[index]
            model["identity"],  # type: ignore[index]
            tool["name"],  # type: ignore[index]
            tool["version"],  # type: ignore[index]
            tool["command"],  # type: ignore[index]
            trace["path"],  # type: ignore[index]
            decoded["scenarios"],  # type: ignore[arg-type]
        )

    def markdown(self) -> list[str]:
        lines = ["## Jobs to be done", ""]
        for heading, jobs in (("Human", self.jtbd_human), ("LLM", self.jtbd_llm)):
            lines += [f"### {heading}"]
            lines += (
                [f"- [{j.status}] {_md(j.job)}" for j in jobs]
                if jobs
                else [NOT_EXPLORED]
            )
            lines.append("")
        lines += ["## User journey", ""]
        if self.journey:
            lines += ["| Step | Human emotion | Status |", "| --- | --- | --- |"]
            lines += [
                f"| {_cell(s.step)} | "
                f"{_cell(s.human_emotion) if s.human_emotion else 'not explored'} | {s.status} |"
                for s in self.journey
            ]
            last = len(self.journey) - 1
            lines += [
                "",
                "Qualitative journey arc (stated emotions; NOT measured intensity)",
            ]
            lines += ["```text"]
            for i, s in enumerate(self.journey):
                lines += s.arc(i + 1, i == last)
            lines += ["```"]
        else:
            lines += [NOT_EXPLORED, "", "Journey arc: UNKNOWN (journey not explored)"]
        lines += ["", "## Gherkin scenarios", ""]
        if self.gherkin:
            for g in self.gherkin:
                lines += [
                    f"### {g.scenario} ({g.status})",
                    "```gherkin",
                    *g.steps,
                    "```",
                    "",
                ]
            lines.pop()
        else:
            lines.append(NOT_EXPLORED)
        lines += ["", "## Quint scenarios", ""]
        q = self.quint
        if q is None:
            lines.append(NOT_RUN)
        else:
            lines += [
                "Recorded evidence, not verified by DES:",
                f"- Model: {_md(q.model)} (identity {_md(q.model_identity)})",
                f"- Tool: {_md(q.tool)} {_md(q.tool_version)}; command: {_md(q.command)}",
                f"- Trace: {_md(q.trace)}",
                "",
            ]
            for s in q.scenarios:
                lines += [f"### {s.title}"]
                lines += [f"- [trace {i}] {t}" for i, t in s.events]
                lines.append("")
            lines.pop()
        lines.append("")
        return lines
