"""Did the treatment arm actually EXERCISE the method, or only carry it?

An admission precondition, read from an archived campaign's own transcripts.
A campaign that fails it is INDETERMINATE about the method whatever its ratios
say: on 2026-09-12 three pairs reported cost, tokens and wall-clock all below
parity while the treatment arm had typed every line by hand, and those numbers
described an installation that idles.

## Presence of an invocation is not use

The first wording of this precondition was "at least one DES step invoked". It
would have ADMITTED the campaign it was written to exclude. `des state` is
read-only by construction -- it writes no byte, invokes no role and spawns no
provider -- so one reflex call satisfies that rule while the delivery is still
hand-typed. A detector that cannot reject the case that motivated it is not a
detector.

So the steps are split by what they BUY. A step that buys a role turn is the
method doing the work; a step that reports state is the method being consulted.
Only the first kind counts. `des integrate`, `des lane`, and `des commit` sit
with the second because they transfer or move git; none buys authorship.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


try:  # package import for tests; direct import for script execution
    from scripts.analysis.k4 import delivery_attribution
except ImportError:  # pragma: no cover - exercised by direct CLI use
    import delivery_attribution  # type: ignore[no-redef]


#: Steps that buy a role turn: the method produces something.
ROLE_BUYING_STEPS = frozenset(
    {
        "po",
        "design",
        "oracle",
        "craft",
        "verify",
        "devops",
        "discuss",
        "distill",
        "evolution",
        "verify-agreement",
    }
)

#: Steps that report or move state without buying a role turn. Named, not
#: merely omitted, so that a step added later is a deliberate classification
#: rather than a silent pass.
REPORTING_STEPS = frozenset(
    {"state", "project", "code-fact", "lane", "commit", "integrate"}
)

#: Wave commands. Each dispatches the spine, so each is role-buying.
WAVE_COMMANDS = frozenset(
    {
        "/nw-discover",
        "/nw-diverge",
        "/nw-discuss",
        "/nw-design",
        "/nw-devops",
        "/nw-distill",
        "/nw-deliver",
        "/nw-bugfix",
        "/nw-review",
        "/nw-optimize-tests",
        "/nw-mutation-test",
    }
)

#: The route the treatment arm is expected to take, named by the phases a
#: whole feature travels: clarify the outcome, bind the design facts, author the
#: public oracle, deliver against it, and close the delivered work.
#:
#: A single role-buying step admits a run that merely touched the method. The
#: phases below are what "exercised" means for a whole feature, so the check
#: reports which of them the transcript shows and which it does not.
ROUTE_PHASES: dict[str, frozenset[str]] = {
    "clarify": frozenset(
        {"des po", "des discuss", "/nw-discuss", "/nw-discover", "/nw-diverge"}
    ),
    "design": frozenset({"des design", "/nw-design"}),
    "oracle": frozenset({"des oracle", "des distill", "/nw-distill"}),
    "deliver": frozenset({"des craft", "des verify", "/nw-deliver"}),
    "finalize": frozenset({"des evolution"}),
}

EXERCISED = "EXERCISED"
NOT_EXERCISED = "NOT_EXERCISED"
INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class ArmExercise:
    """What one arm's transcript shows about the method producing the work."""

    arm: str
    role_buying: tuple[str, ...]
    reporting_only: tuple[str, ...]
    delegated_turns: int
    attributions: tuple[delivery_attribution.AttributionAssessment, ...] = ()

    @property
    def phases_present(self) -> tuple[str, ...]:
        """Route phases the transcript shows, in the order the route names them."""
        ran = set(self.role_buying)
        return tuple(phase for phase, steps in ROUTE_PHASES.items() if ran & steps)

    @property
    def phases_missing(self) -> tuple[str, ...]:
        present = set(self.phases_present)
        return tuple(phase for phase in ROUTE_PHASES if phase not in present)

    @property
    def verdict(self) -> str:
        """EXERCISED only when the whole route ran, never on one touched step.

        A delivery that bought a single role turn and typed the rest is not the
        method delivering the work; it is the method being consulted once.
        """
        if self.phases_missing:
            return NOT_EXERCISED
        if not self.attributions or any(
            item.status != delivery_attribution.ATTRIBUTED for item in self.attributions
        ):
            return INDETERMINATE
        return EXERCISED

    @property
    def why(self) -> str:
        if not self.phases_missing:
            if not self.attributions:
                return (
                    "whole route command text is present, but no "
                    "DeliveryAttributionV2 joins a completed native crafter turn "
                    "to the captured final delivery projection"
                )
            failed = [
                item.why
                for item in self.attributions
                if item.status != delivery_attribution.ATTRIBUTED
            ]
            if failed:
                return "delivery attribution is unjoinable: " + "; ".join(failed)
            return f"whole route ran and {self.attributions[0].why}"
        if self.phases_present:
            return (
                f"only {', '.join(self.phases_present)}; "
                f"missing {', '.join(self.phases_missing)}"
            )
        if self.delegated_turns:
            return (
                f"{self.delegated_turns} delegated role turn(s) but no route "
                "phase is visible"
            )
        if self.reporting_only:
            return (
                "only reporting steps, which buy no role turn: "
                f"{', '.join(sorted(set(self.reporting_only)))}"
            )
        return "no DES step, no wave command and no delegated turn"


def _commands_and_delegations(transcript: Path) -> tuple[list[str], int]:
    """Every shell command and the count of delegated turns in one transcript."""
    commands: list[str] = []
    delegated = 0
    with transcript.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            for block in message.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name")
                payload = block.get("input") or {}
                if name == "Bash" and isinstance(payload.get("command"), str):
                    commands.append(payload["command"])
                elif name in {"Task", "Agent"}:
                    delegated += 1
                elif name == "Skill" and isinstance(payload.get("skill"), str):
                    commands.append(f"/{payload['skill']}")
    return commands, delegated


def _classify(commands: list[str]) -> tuple[list[str], list[str]]:
    """Split the DES steps and wave commands a transcript ran, by what they buy."""
    role_buying: list[str] = []
    reporting: list[str] = []
    for command in commands:
        for token in command.replace("\n", " ").split():
            if token in WAVE_COMMANDS:
                role_buying.append(token)
        words = command.replace("\n", " ").split()
        for index, word in enumerate(words):
            if word != "des" or index + 1 >= len(words):
                continue
            step = words[index + 1]
            if step in ROLE_BUYING_STEPS:
                role_buying.append(f"des {step}")
            elif step in REPORTING_STEPS:
                reporting.append(f"des {step}")
    return role_buying, reporting


def examine_arm(arm_workspace: Path, arm: str) -> ArmExercise:
    """Read every transcript one arm's workspace kept and classify what it ran."""
    commands: list[str] = []
    delegated = 0
    for transcript in sorted(arm_workspace.rglob("*.jsonl")):
        found, turns = _commands_and_delegations(transcript)
        commands.extend(found)
        delegated += turns
    role_buying, reporting = _classify(commands)
    attributions = tuple(
        delivery_attribution.assess(path)
        for filename in (
            delivery_attribution.ATTRIBUTION_V2_FILE_NAME,
            delivery_attribution.ATTRIBUTION_FILE_NAME,
        )
        for path in sorted(arm_workspace.rglob(filename))
    )
    return ArmExercise(
        arm, tuple(role_buying), tuple(reporting), delegated, attributions
    )


def examine_campaign(campaign: Path, arm: str = "nwave") -> list[ArmExercise]:
    """Read paired measurements or the native D0 single-arm specimen layout."""
    results: list[ArmExercise] = []
    for pair in sorted(campaign.glob("pair-*")):
        workspace = pair / arm
        if workspace.is_dir():
            results.append(examine_arm(workspace, f"{pair.name}/{arm}"))
    if results:
        return results
    try:
        campaign_record = json.loads(
            (campaign / "campaign.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return results
    if not isinstance(campaign_record, dict) or campaign_record.get("arm") != arm:
        return results
    for run in sorted(campaign.glob("run-*")):
        specimen = run / "specimen"
        if specimen.is_dir():
            results.append(examine_arm(specimen, f"{run.name}/{arm}"))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--arm", default="nwave")
    args = parser.parse_args(argv)

    results = examine_campaign(args.campaign, args.arm)
    if not results:
        print(
            f"WHAT: no `{args.arm}` workspace under any pair of {args.campaign}\n"
            "WHY:  the precondition reads the arm's own transcripts, and there "
            "are none to read\n"
            "HOW:  point --campaign at an archived paired campaign holding "
            "pair-*/<arm>/ or a D0 campaign holding run-*/specimen/"
        )
        return 2

    for result in results:
        print(f"{result.arm}: {result.verdict} -- {result.why}")

    failing = [r for r in results if r.verdict != EXERCISED]
    if failing:
        print(
            f"\nWHAT: {len(failing)} of {len(results)} deliveries are not proven "
            "exercised\n"
            "WHY:  command text and integration do not show that a completed DES "
            "producer made the captured delivery diff, so the campaign is "
            "INDETERMINATE about the method\n"
            "HOW:  retain the reserved native run and typed crafter projection, then "
            "construct delivery-attribution-v2.json beside the strict D0 packet and "
            "re-run; do not advance or invoke DES here"
        )
        return 1
    print(f"\nall {len(results)} deliveries exercised the method")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
