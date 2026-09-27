"""Optional, closed DISCUSS sections: JTBD, journey, Gherkin and Quint scenarios.

Every section is always rendered.  An omitted section shows an honest
placeholder; a supplied one shows exactly what the LLM supplied.  Nothing here
verifies or invents content: Quint evidence is recorded, never claimed proven.
"""

from __future__ import annotations

from dataclasses import dataclass


class SectionInvalid(ValueError):
    pass


STATUSES = ("proposed", "confirmed", "open")
SECTION_KEYS = ("jtbd", "journey", "gherkin", "quint_scenarios")
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


def _closed(value: object, name: str, required: set[str], optional: set[str]) -> dict:
    if not isinstance(value, dict):
        raise SectionInvalid(f"{name} must be an object")
    keys = set(value)
    if not required <= keys <= required | optional:
        raise SectionInvalid(
            f"{name} must contain {sorted(required)} and only optionally {sorted(optional)}"
        )
    return value


def _status(value: object, name: str) -> str:
    if value not in STATUSES:
        raise SectionInvalid(f"{name} must be one of {list(STATUSES)}")
    return str(value)


def _list(value: object, name: str) -> list:
    if not isinstance(value, list) or not value:
        raise SectionInvalid(f"{name} must be a non-empty array when present")
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
        v2 (current): every section key is required and tagged
        ``{"status": "not_explored"}`` or ``{"status": "provided", ...typed data}``.
        """
        if version == 1:
            return cls(
                *cls._jtbd(payload["jtbd"]) if "jtbd" in payload else ((), ()),
                cls._journey(payload["journey"]) if "journey" in payload else (),
                cls._gherkin(payload["gherkin"]) if "gherkin" in payload else (),
                cls._quint(payload["quint_scenarios"])
                if "quint_scenarios" in payload
                else None,
            )
        missing = [k for k in SECTION_KEYS if k not in payload]
        if missing:
            raise SectionInvalid(
                f"schema_version 2 requires an explicit entry for {missing}; "
                'use {"status": "not_explored"} for an unexpanded section'
            )
        human, llm = cls._tagged(payload["jtbd"], "jtbd", cls._jtbd, {"human", "llm"})
        journey = cls._tagged(
            payload["journey"], "journey", cls._journey, {"steps"}, "steps"
        )
        gherkin = cls._tagged(
            payload["gherkin"], "gherkin", cls._gherkin, {"scenarios"}, "scenarios"
        )
        return cls(human, llm, journey, gherkin, cls._quint(payload["quint_scenarios"]))

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
            _closed(value, name, {"status"}, set())
            return empty
        _closed(value, name, {"status"}, keys)
        data = {k: v for k, v in value.items() if k != "status"}
        if not data:
            raise SectionInvalid(
                f"{name} with status provided must carry {sorted(keys)}"
            )
        return parse(data[only] if only else data)

    @classmethod
    def _jtbd(cls, jobs: object) -> tuple[tuple[Job, ...], tuple[Job, ...]]:
        jobs = _closed(jobs, "jtbd", set(), {"human", "llm"})
        if not jobs:
            raise SectionInvalid("jtbd must contain human and/or llm when present")
        return (
            cls._jobs(jobs["human"], "jtbd.human") if "human" in jobs else (),
            cls._jobs(jobs["llm"], "jtbd.llm") if "llm" in jobs else (),
        )

    @staticmethod
    def _journey(value: object) -> tuple[JourneyStep, ...]:
        steps = []
        for i, raw in enumerate(_list(value, "journey")):
            name = f"journey[{i}]"
            raw = _closed(raw, name, {"step", "status"}, {"human_emotion"})
            steps.append(
                JourneyStep(
                    _text(raw["step"], f"{name}.step"),
                    _text(raw["human_emotion"], f"{name}.human_emotion")
                    if "human_emotion" in raw
                    else None,
                    _status(raw["status"], f"{name}.status"),
                )
            )
        return tuple(steps)

    @staticmethod
    def _gherkin(value: object) -> tuple[GherkinScenario, ...]:
        scenarios = []
        for i, raw in enumerate(_list(value, "gherkin")):
            name = f"gherkin[{i}]"
            raw = _closed(raw, name, {"scenario", "steps", "status"}, set())
            scenarios.append(
                GherkinScenario(
                    _text(raw["scenario"], f"{name}.scenario", single_line=True),
                    tuple(
                        _step(s, f"{name}.steps[{j}]")
                        for j, s in enumerate(_list(raw["steps"], f"{name}.steps"))
                    ),
                    _status(raw["status"], f"{name}.status"),
                )
            )
        return tuple(scenarios)

    @staticmethod
    def _jobs(value: object, name: str) -> tuple[Job, ...]:
        jobs = []
        for i, raw in enumerate(_list(value, name)):
            raw = _closed(raw, f"{name}[{i}]", {"job", "status"}, set())
            jobs.append(
                Job(
                    _text(raw["job"], f"{name}[{i}].job"),
                    _status(raw["status"], f"{name}[{i}].status"),
                )
            )
        return tuple(jobs)

    @staticmethod
    def _quint(value: object) -> QuintEvidence | None:
        name = "quint_scenarios"
        if not isinstance(value, dict) or value.get("status") not in (
            "not_run",
            "generated",
        ):
            raise SectionInvalid(f"{name}.status must be not_run or generated")
        if value["status"] == "not_run":
            _closed(value, name, {"status"}, set())
            return None
        raw = _closed(
            value,
            name,
            {"status", "model", "tool", "trace", "scenarios"},
            set(),
        )
        model = _closed(raw["model"], f"{name}.model", {"path", "identity"}, set())
        tool = _closed(
            raw["tool"], f"{name}.tool", {"name", "version", "command"}, set()
        )
        trace = _closed(raw["trace"], f"{name}.trace", {"path"}, set())
        scenarios = []
        for i, item in enumerate(_list(raw["scenarios"], f"{name}.scenarios")):
            label = f"{name}.scenarios[{i}]"
            item = _closed(item, label, {"title", "events"}, set())
            events = []
            for j, event in enumerate(_list(item["events"], f"{label}.events")):
                event = _closed(
                    event, f"{label}.events[{j}]", {"trace_index", "text"}, set()
                )
                index = event["trace_index"]
                if not isinstance(index, int) or isinstance(index, bool) or index < 0:
                    raise SectionInvalid(
                        f"{label}.events[{j}].trace_index must be a non-negative integer"
                    )
                events.append(
                    (
                        index,
                        _text(
                            event["text"], f"{label}.events[{j}].text", single_line=True
                        ),
                    )
                )
            scenarios.append(
                QuintScenario(
                    _text(item["title"], f"{label}.title", single_line=True),
                    tuple(events),
                )
            )
        return QuintEvidence(
            _text(model["path"], f"{name}.model.path", single_line=True),
            _text(model["identity"], f"{name}.model.identity", single_line=True),
            _text(tool["name"], f"{name}.tool.name", single_line=True),
            _text(tool["version"], f"{name}.tool.version", single_line=True),
            _text(tool["command"], f"{name}.tool.command", single_line=True),
            _text(trace["path"], f"{name}.trace.path", single_line=True),
            tuple(scenarios),
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
